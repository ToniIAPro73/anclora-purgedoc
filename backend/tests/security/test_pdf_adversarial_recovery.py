import pytest
import os
import shutil
from pathlib import Path
import fitz # PyMuPDF
from pypdf import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract

from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.normalization import generate_adversarial_variants, normalize_text
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_security_fixtures():
    generate_all_fixtures()

def test_multi_engine_pdf_adversarial_recovery():
    """
    1. VECTORIAL PDF:
    - Purges synthetic data using real redaction engine
    - Reopens resulting PDF
    - Extracts text with PyMuPDF, pypdf, and pdfminer.six independently
    - Exhaustively searches for raw strings and normalized adversarial variants
    - Inspects raw stream objects and metadata
    """
    hr_pdf = FIXTURES_DIR / "sample_rrhh_payroll.pdf"
    assert hr_pdf.exists()

    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(hr_pdf))
    matches = detection_engine.analyze_document_content("sec_doc_1", "rrhh", pages)

    # Target all detected matches for complete redaction
    approved = matches
    for m in approved:
        m.status = "accepted"

    assert len(approved) >= 3

    out_pdf = FIXTURES_DIR / "test_sec_purged_vector.pdf"
    redaction_engine.purge_pdf(str(hr_pdf), str(out_pdf), approved, is_scanned=False)

    # 1. Independent PyMuPDF inspection
    doc = fitz.open(str(out_pdf))
    mupdf_text = ""
    for p in doc:
        mupdf_text += "\n" + p.get_text("text")

    # 2. Independent pypdf inspection
    pypdf_reader = PdfReader(str(out_pdf))
    pypdf_text = ""
    for p in pypdf_reader.pages:
        pypdf_text += "\n" + (p.extract_text() or "")

    # 3. Independent pdfminer.six inspection
    pdfminer_text = pdfminer_extract(str(out_pdf)) or ""

    # 4. Raw byte streams inspection
    with open(str(out_pdf), "rb") as f:
        raw_bytes = f.read()

    doc.close()

    combined_extracted = mupdf_text + "\n" + pypdf_text + "\n" + pdfminer_text

    # Search for all approved sensitive tokens and their adversarial variants
    target_tokens = ["12345678Z", "laura.martinez@example.test", "ES00 0000 0000 0000 0000 0000", "+34 600 123 456"]
    for token in target_tokens:
        variants = generate_adversarial_variants(token)
        for v in variants:
            assert v.lower() not in combined_extracted.lower(), f"Adversarial leak: variant '{v}' found in multi-engine text!"
            if len(v) >= 6 and not v.startswith("0"):
                assert v.encode("utf-8") not in raw_bytes, f"Adversarial leak: variant '{v}' found in raw binary PDF bytes!"

    # 5. Metadata and attachments verification
    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=False)
    assert verified is True, f"Multi-engine verification failed: {failures}"
    assert details["secondary_engine_pypdf_checked"] is True
    assert details["tertiary_engine_pdfminer_checked"] is True

    if out_pdf.exists():
        out_pdf.unlink()
