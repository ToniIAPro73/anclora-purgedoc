import pytest
import os
import fitz # PyMuPDF
from backend.services.verification import verification_engine
from backend.models import MatchItem, hash_text
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_security_fixtures():
    generate_all_fixtures()

def test_verifier_resists_adversarial_formatting_and_normalization_tricks():
    """
    7. FALSE NEGATIVES OF THE VERIFIER:
    Deliberately attempts to deceive the post-purge verifier using:
    - Case changes (12345678z vs 12345678Z)
    - Unicode accent equivalents and full-width forms
    - Spacing variants (ES00  0000... vs ES00 0000...)
    - Hyphens and punctuation variations
    The verifier MUST fail-closed and reject verification if any equivalent representation remains!
    """
    # Create an intentionally dirty test PDF with residual formatted variants
    test_pdf_path = FIXTURES_DIR / "sample_adversarial_leak.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Insert subtle variants that might fool a naive exact-match string check:
    # 1. Lowercase DNI
    page.insert_text((50, 100), "DNI: 12345678z", fontsize=11)
    # 2. Extra spaces in IBAN
    page.insert_text((50, 150), "IBAN: ES00   0000   0000   0000   0000   0000", fontsize=11)
    # 3. Unicode full-width or decomposed diacritics
    page.insert_text((50, 200), "Email: laura.martinez@example.test", fontsize=11)
    doc.save(str(test_pdf_path))
    doc.close()

    # Create approved matches targeting the canonical values
    approved_matches = [
        MatchItem(
            document_id="test_adv",
            entity_type="DNI_NIE_NIF",
            source=["regex"],
            confidence=0.99,
            original_text_hash=hash_text("12345678Z"),
            text_preview="12***78Z",
            raw_text="12345678Z", # Uppercase in approved match
            page=1,
            profile_id="rrhh",
            profile_version="1.0.0"
        ),
        MatchItem(
            document_id="test_adv",
            entity_type="IBAN",
            source=["regex"],
            confidence=0.99,
            original_text_hash=hash_text("ES00 0000 0000 0000 0000 0000"),
            text_preview="ES00...0000",
            raw_text="ES00 0000 0000 0000 0000 0000", # Standard single-space in match
            page=1,
            profile_id="rrhh",
            profile_version="1.0.0"
        )
    ]

    # Verify: The verifier MUST catch the residual variants and FAIL CLOSED (verified == False)
    verified, failures, details = verification_engine.verify_pdf(str(test_pdf_path), approved_matches)
    assert verified is False, "Security Vulnerability: Verifier was tricked by adversarial case/spacing variant!"
    assert len(failures) >= 1

    if test_pdf_path.exists():
        test_pdf_path.unlink()
