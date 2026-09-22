import pytest
import time
from backend.services.rules import (
    CustomRule, CustomRuleset, RegexValidator,
    MAX_PATTERN_LENGTH, MAX_TEST_TEXT_LENGTH
)
from backend.services.detection import detection_engine

def test_custom_rule_creation_and_defaults():
    rule = CustomRule(
        name="Clave Secreta Proyecto",
        pattern=r'PROJ-[A-Z0-9]{6}',
        entity_type="CUSTOM_SECRET"
    )
    assert rule.name == "Clave Secreta Proyecto"
    assert rule.enabled is True
    assert rule.priority == 10
    assert "rrhh" in rule.profiles
    assert rule.id.startswith("rule_")

def test_custom_ruleset_deterministic_hash():
    r1 = CustomRule(id="r1", name="Rule 1", pattern=r'TOKEN_[0-9]+', entity_type="TOKEN")
    r2 = CustomRule(id="r2", name="Rule 2", pattern=r'APIKEY_[a-z]+', entity_type="APIKEY")

    ruleset_a = CustomRuleset(rules=[r1, r2])
    ruleset_b = CustomRuleset(rules=[r2, r1]) # Different insertion order

    # The hash must be strictly deterministic and order-invariant
    hash_a = ruleset_a.calculate_hash()
    hash_b = ruleset_b.calculate_hash()
    assert hash_a == hash_b
    assert hash_a.startswith("sha256:")

    # Modifying pattern must change hash
    r2_mod = CustomRule(id="r2", name="Rule 2", pattern=r'APIKEY_[0-9]+', entity_type="APIKEY")
    ruleset_c = CustomRuleset(rules=[r1, r2_mod])
    assert ruleset_c.calculate_hash() != hash_a

def test_regex_validator_valid_and_invalid():
    # Valid
    res_valid = RegexValidator.validate_pattern(r'[A-Z]{3}-\d{4}')
    assert res_valid.valid is True
    assert res_valid.error is None

    # Invalid syntax (unclosed parenthesis)
    res_invalid = RegexValidator.validate_pattern(r'(abc[0-9]+')
    assert res_invalid.valid is False
    assert res_invalid.error is not None

    # Empty pattern
    res_empty = RegexValidator.validate_pattern("")
    assert res_empty.valid is False

def test_regex_validator_redos_protection():
    # Catastrophic backtracking patterns like (a+)+
    redos_pattern = r'((a+)+)+$'
    res_redos = RegexValidator.validate_pattern(redos_pattern)
    assert res_redos.valid is False
    assert "Backtracking" in res_redos.error or "Sintaxis" in res_redos.error

def test_regex_pattern_length_limit():
    huge_pattern = "a" * (MAX_PATTERN_LENGTH + 50)
    res = RegexValidator.validate_pattern(huge_pattern)
    assert res.valid is False
    assert "excede el límite" in res.error

def test_regex_test_bench_matching():
    rule = CustomRule(
        name="Deteccion Passcode",
        pattern=r'PASSCODE:\s*([0-9]{4})',
        entity_type="PASSCODE",
        case_sensitive=False
    )
    test_text = "El usuario tiene PASSCODE: 9812 en su cuenta. Otro PASSCODE: 4321."
    
    test_res = RegexValidator.test_rule(rule, test_text)
    assert test_res.error is None
    assert test_res.count == 2
    assert len(test_res.matches) == 2
    assert test_res.matches[0].match_text == "PASSCODE: 9812"
    assert test_res.matches[1].match_text == "PASSCODE: 4321"
    assert test_res.execution_time_ms >= 0.0

def test_custom_rule_detection_integration_and_priority():
    """Verify custom rules run on document content and respect priority/enablement"""
    custom_rule = CustomRule(
        id="c1",
        name="Numero de Empleado Confidencial",
        pattern=r'EMP#\d{5}',
        entity_type="EMPLOYEE_ID",
        priority=99,
        enabled=True,
        profiles=["rrhh"]
    )

    page_content = [{
        "page_num": 1,
        "text": "Ficha del empleado: EMP#54321. Salario: 2.000 EUR.",
        "rects": [],
        "width": 595.0,
        "height": 842.0
    }]

    # Analyze with custom rule enabled
    matches = detection_engine.analyze_document_content(
        doc_id="test_custom_doc",
        profile_id="rrhh",
        pages_content=page_content,
        custom_rules=[custom_rule]
    )

    assert any(m.raw_text == "EMP#54321" and m.entity_type == "EMPLOYEE_ID" for m in matches)

    # Disable rule and analyze again
    custom_rule.enabled = False
    matches_disabled = detection_engine.analyze_document_content(
        doc_id="test_custom_doc",
        profile_id="rrhh",
        pages_content=page_content,
        custom_rules=[custom_rule]
    )
    assert not any(m.raw_text == "EMP#54321" for m in matches_disabled)

def test_custom_rule_overlapping_with_ner():
    """Verify custom rule cleanly integrates and upgrades confidence over NER"""
    custom_rule = CustomRule(
        id="c2",
        name="Directorio de Directivos",
        pattern=r'Laura Martínez Gómez',
        entity_type="EXECUTIVE_DIRECTOR",
        priority=80,
        enabled=True,
        profiles=["rrhh"]
    )

    page_content = [{
        "page_num": 1,
        "text": "Directora General: Laura Martínez Gómez.",
        "rects": [],
        "width": 595.0,
        "height": 842.0
    }]

    matches = detection_engine.analyze_document_content(
        doc_id="test_custom_overlap",
        profile_id="rrhh",
        pages_content=page_content,
        custom_rules=[custom_rule]
    )

    found = [m for m in matches if "Laura Martínez Gómez" in m.raw_text]
    assert len(found) == 1 # Deduplicated to single card!
    assert found[0].entity_type == "EXECUTIVE_DIRECTOR" # Custom rule entity preserved!
    assert any("custom" in s for s in found[0].source)
