import os
import json
import base64
import pytest
from backend.services.rules import CustomRuleset, CustomRule
from backend.services.encrypted_rules import (
    export_encrypted_ruleset,
    preview_encrypted_ruleset,
    EncryptedRulesetError,
    APRULES_FORMAT_NAME,
    APRULES_FORMAT_VERSION,
    SUPPORTED_CIPHER,
    SUPPORTED_KDF,
    DEFAULT_MEMORY_COST_KIB
)

def create_sample_ruleset() -> CustomRuleset:
    rule1 = CustomRule(
        id="rule_prj_1",
        name="Project Sensitive Code",
        description="Confidential code project regex",
        entity_type="PROJECT_CODE",
        pattern=r"PRJ-[A-Z0-9]{5}",
        case_sensitive=True,
        confidence=0.98,
        priority=60,
        profiles=["rrhh", "legal"],
        enabled=True,
        example="PRJ-X892A"
    )
    rule2 = CustomRule(
        id="rule_sec_token",
        name="Internal Security Token",
        description="Internal token signature",
        entity_type="API_KEY",
        pattern=r"SEC_[a-zA-Z0-9]{16}",
        case_sensitive=False,
        confidence=0.99,
        priority=70,
        profiles=["soporte"],
        enabled=True,
        example="SEC_1234567890abcdef"
    )
    return CustomRuleset(
        ruleset_id="test_ruleset_alpha",
        version="1.0.0",
        rules=[rule1, rule2]
    )

def test_encrypted_export_import_canonical_roundtrip():
    """
    Verify complete export -> preview round-trip:
    - Canonical hash before export matches canonical hash after decryption.
    - All functional properties preserved.
    """
    ruleset = create_sample_ruleset()
    canonical_hash_before = ruleset.calculate_hash()
    password = "CorrectSuperSecretPassword123!"

    envelope = export_encrypted_ruleset(
        ruleset=ruleset,
        password=password,
        ruleset_name="Enterprise Alpha Ruleset",
        description="Confidential ruleset for enterprise sharing"
    )

    # Envelope outer schema checks
    assert envelope["format"] == APRULES_FORMAT_NAME
    assert envelope["format_version"] == APRULES_FORMAT_VERSION
    assert envelope["crypto"]["cipher"] == SUPPORTED_CIPHER
    assert envelope["crypto"]["kdf"] == SUPPORTED_KDF
    assert envelope["crypto"]["memory_cost_kib"] == DEFAULT_MEMORY_COST_KIB
    assert "ciphertext" in envelope

    # Preview and decrypt
    preview = preview_encrypted_ruleset(envelope, password)
    assert preview["canonical_hash"] == canonical_hash_before
    assert preview["rules_count"] == 2
    assert preview["name"] == "Enterprise Alpha Ruleset"
    assert "rrhh" in preview["affected_profiles"]
    assert "soporte" in preview["affected_profiles"]

def test_absence_of_plaintext_in_envelope():
    """
    CRITICAL SECURITY & ZERO-PII TEST:
    Inspect the raw .aprules JSON string and bytes.
    Verify that NO known plaintext names, regex patterns, descriptions or examples exist in cleartext.
    """
    ruleset = create_sample_ruleset()
    envelope = export_encrypted_ruleset(ruleset, "StrongPass2026!", ruleset_name="TopSecretRuleset")
    raw_json_str = json.dumps(envelope)

    forbidden_plaintext_tokens = [
        "Project Sensitive Code",
        "Confidential code project regex",
        "PRJ-[A-Z0-9]{5}",
        "PRJ-X892A",
        "Internal Security Token",
        "SEC_[a-zA-Z0-9]{16}",
        "SEC_1234567890abcdef",
        "TopSecretRuleset"
    ]

    for token in forbidden_plaintext_tokens:
        assert token not in raw_json_str, f"LEAK! Plaintext token '{token}' found unencrypted in .aprules envelope!"

def test_different_salt_and_nonce_per_export():
    """Verify two consecutive exports of the exact same ruleset generate unique salts, nonces, and ciphertexts."""
    ruleset = create_sample_ruleset()
    passw = "IdenticalPass456!"

    env1 = export_encrypted_ruleset(ruleset, passw)
    env2 = export_encrypted_ruleset(ruleset, passw)

    assert env1["crypto"]["salt"] != env2["crypto"]["salt"]
    assert env1["crypto"]["nonce"] != env2["crypto"]["nonce"]
    assert env1["ciphertext"] != env2["ciphertext"]

def test_wrong_password_auth_failure():
    """Verify wrong password fails authenticated decryption with ENCRYPTED_RULESET_AUTH_FAILED."""
    ruleset = create_sample_ruleset()
    envelope = export_encrypted_ruleset(ruleset, "RightPassword123")

    with pytest.raises(EncryptedRulesetError) as exc_info:
        preview_encrypted_ruleset(envelope, "WrongPassword456")
    assert exc_info.value.code == "ENCRYPTED_RULESET_AUTH_FAILED"

def test_tampered_ciphertext_auth_failure():
    """Verify tampering with ciphertext bits causes authentication failure via AES-GCM tag check."""
    ruleset = create_sample_ruleset()
    envelope = export_encrypted_ruleset(ruleset, "Password123!")

    # Flip bits in ciphertext
    raw_ct = bytearray(base64.b64decode(envelope["ciphertext"]))
    raw_ct[10] ^= 0xFF
    envelope["ciphertext"] = base64.b64encode(raw_ct).decode('ascii')

    with pytest.raises(EncryptedRulesetError) as exc_info:
        preview_encrypted_ruleset(envelope, "Password123!")
    assert exc_info.value.code == "ENCRYPTED_RULESET_AUTH_FAILED"

def test_tampered_aad_metadata_auth_failure():
    """
    CRITICAL AAD TEST:
    Verify that tampering with envelope metadata (e.g. format_version, salt, nonce, KDF parameters)
    causes AES-GCM authentication failure even if ciphertext is untouched.
    """
    ruleset = create_sample_ruleset()
    passw = "Password123!"
    envelope = export_encrypted_ruleset(ruleset, passw)

    # Tamper with memory_cost_kib in envelope
    envelope["crypto"]["time_cost"] = 4

    with pytest.raises(EncryptedRulesetError) as exc_info:
        preview_encrypted_ruleset(envelope, passw)
    assert exc_info.value.code == "ENCRYPTED_RULESET_AUTH_FAILED"

def test_anti_dos_kdf_limits_enforced():
    """Verify that malicious KDF parameters are rejected BEFORE Argon2 execution."""
    ruleset = create_sample_ruleset()
    envelope = export_encrypted_ruleset(ruleset, "Password123!")

    # Exorbitant memory cost to cause OOM DoS
    envelope["crypto"]["memory_cost_kib"] = 1048576  # 1 GiB > MAX 256 MiB

    with pytest.raises(EncryptedRulesetError) as exc_info:
        preview_encrypted_ruleset(envelope, "Password123!")
    assert exc_info.value.code == "UNSUPPORTED_CRYPTO_PARAMETERS"

def test_unicode_and_spaces_in_password():
    """Verify password with Unicode characters and spaces works deterministically."""
    ruleset = create_sample_ruleset()
    unicode_pass = "  Contraseña Segura con Ñ y Acentos ¡€123!  "

    envelope = export_encrypted_ruleset(ruleset, unicode_pass)
    preview = preview_encrypted_ruleset(envelope, unicode_pass)
    assert preview["rules_count"] == 2

def test_immutable_builtin_ruleset_conflict_protection():
    """Verify rules matching protected built-in names (RRHH, Legal, Soporte) are rejected."""
    malicious_rule = CustomRule(
        id="rrhh",
        name="rrhh",
        pattern=r"\d{8}[A-Z]"
    )
    bad_ruleset = CustomRuleset(ruleset_id="bad", rules=[malicious_rule])
    envelope = export_encrypted_ruleset(bad_ruleset, "Pass123!")

    with pytest.raises(EncryptedRulesetError) as exc_info:
        preview_encrypted_ruleset(envelope, "Pass123!")
    assert exc_info.value.code == "BUILTIN_RULESET_CONFLICT"
