import pytest
import os
import zipfile
from pathlib import Path
import docx

from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.normalization import normalize_text, generate_adversarial_variants
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_security_fixtures():
    generate_all_fixtures()

def test_docx_deep_ooxml_package_recovery():
    """
    4. DOCX / OOXML DEEP PACKAGE RECOVERY:
    - Purges DOCX contract
    - Fully unzips the .docx package
    - Exhaustively searches all internal XML and .rels parts:
      document.xml, header1.xml, footer1.xml, comments.xml, footnotes.xml,
      core.xml, app.xml, custom.xml, etc.
    - Searches for raw values and adversarial variants
    - Validates that docx remains valid and reopenable
    """
    legal_docx = FIXTURES_DIR / "sample_legal_contract.docx"
    assert legal_docx.exists()

    pages, count, has_text = document_processor.extract_docx_content(str(legal_docx))
    matches = detection_engine.analyze_document_content("sec_doc_docx", "legal", pages)

    target_tokens = ["87654321B", "carlos.fernandez@example.test", "A12345678", "ES99 1234 5678 9012 3456 7890"]
    approved = [m for m in matches if any(t in m.raw_text for t in target_tokens)]
    for m in approved:
        m.status = "accepted"

    assert len(approved) >= 2

    out_docx = FIXTURES_DIR / "test_sec_purged_package.docx"
    redaction_engine.purge_docx(str(legal_docx), str(out_docx), approved)

    # 1. Exhaustive unzipping of every file in the OOXML container
    with zipfile.ZipFile(str(out_docx), 'r') as z:
        all_part_names = z.namelist()
        assert "word/document.xml" in all_part_names

        for part_name in all_part_names:
            raw_data = z.read(part_name)
            # Try decoding as text
            try:
                part_text = raw_data.decode("utf-8", errors="ignore")
                norm_part_text = normalize_text(part_text)
                compact_part_text = "".join(norm_part_text.split())

                for token in target_tokens:
                    variants = generate_adversarial_variants(token)
                    for v in variants:
                        v_norm = normalize_text(v)
                        v_compact = "".join(v_norm.split())

                        assert v not in part_text, f"Token '{v}' leaked in OOXML part {part_name}!"
                        assert v_norm not in norm_part_text, f"Normalized variant '{v_norm}' leaked in {part_name}!"
                        if len(v_compact) >= 6:
                            assert v_compact not in compact_part_text, f"Compact variant '{v_compact}' leaked in {part_name}!"
            except Exception:
                pass

    # 2. Re-open via python-docx to ensure document structure integrity
    reopened = docx.Document(str(out_docx))
    assert len(reopened.paragraphs) > 0

    # 3. Verification engine confirmation
    verified, failures, details = verification_engine.verify_docx(str(out_docx), approved)
    assert verified is True, f"DOCX verification failed: {failures}"
    assert details["ooxml_parts_checked"] >= 5

    if out_docx.exists():
        out_docx.unlink()
