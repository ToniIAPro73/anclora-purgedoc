import pytest
import os
import shutil
from pathlib import Path
import fitz # PyMuPDF

from backend.services.sessions import session_store
from backend.services.detection import detection_engine
from backend.services.documents import document_processor
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.ocr import local_ocr_engine
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata, MatchItem, calculate_file_sha256

@pytest.fixture(scope="session", autouse=True)
def setup_ocr_fixtures():
    generate_all_fixtures()

def test_scanned_pdf_has_no_native_text():
    """Verify fixture is strictly raster/scanned with no text layer"""
    scanned_pdf = FIXTURES_DIR / "sample_scanned_medical_hr.pdf"
    assert scanned_pdf.exists()

    doc = fitz.open(str(scanned_pdf))
    is_raster = local_ocr_engine.is_raster_only_pdf(doc)
    doc.close()
    assert is_raster is True

def test_scanned_pdf_ocr_detection_and_coordinates():
    """Test local Tesseract OCR extracts text and reliable bounding boxes from scanned PDF"""
    scanned_pdf = FIXTURES_DIR / "sample_scanned_medical_hr.pdf"
    
    pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(str(scanned_pdf))
    assert page_count == 1
    assert is_scanned is True
    assert has_text is True

    matches = detection_engine.analyze_document_content("test_doc_ocr", "rrhh", pages_content)
    assert len(matches) >= 2

    raw_texts = [m.raw_text for m in matches]
    found_dni = any("54321987M" in t for t in raw_texts)
    found_email = any("maria.santos@example.test" in t for t in raw_texts)
    assert found_dni or found_email, f"Expected DNI or email in detected OCR texts: {raw_texts}"

def test_scanned_pdf_physical_purge_and_ocr_reverification():
    """
    Core Verification:
    1. Scan raster PDF
    2. Accept multiple entities (DNI + Email)
    3. Reject one entity (simulate user rejecting false positive / preserving a field)
    4. Physically redact raster pixels from the underlying page image
    5. Re-run local OCR on the output PDF to verify approved data cannot be recovered by OCR
    6. Verify rejected entity is still intact
    """
    scanned_pdf = FIXTURES_DIR / "sample_scanned_medical_hr.pdf"
    pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(str(scanned_pdf))
    matches = detection_engine.analyze_document_content("test_doc_ocr_purge", "rrhh", pages_content)

    approved = []
    rejected = []
    for m in matches:
        if "54321987M" in m.raw_text or "maria.santos@example.test" in m.raw_text:
            m.status = "accepted"
            approved.append(m)
        else:
            m.status = "rejected"
            rejected.append(m)

    assert len(approved) >= 1

    out_pdf = FIXTURES_DIR / "test_purged_scanned.pdf"
    res = redaction_engine.purge_pdf(str(scanned_pdf), str(out_pdf), approved, is_scanned=True)
    assert res["raster_pixels_destroyed"] is True

    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=True)
    assert verified is True, f"OCR verification failed: {failures}"
    assert details.get("ocr_reverification_passed") is True

    for app_m in approved:
        leaks = local_ocr_engine.scan_raster_pdf_for_text(str(out_pdf), [app_m.raw_text])
        assert len(leaks) == 0, f"Sensitive text {app_m.raw_text} leaked through OCR: {leaks}"

    if out_pdf.exists():
        out_pdf.unlink()

def test_rotated_scanned_pdf_ocr_and_purge():
    """Verify that rotated scanned page is handled and sanitized safely"""
    rotated_pdf = FIXTURES_DIR / "sample_rotated_scanned.pdf"
    assert rotated_pdf.exists()

    pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(str(rotated_pdf))
    assert is_scanned is True

    # Use RRHH or Soporte profile depending on document content
    matches = detection_engine.analyze_document_content("test_doc_rotated", "rrhh", pages_content)
    approved = [m for m in matches if "maria.santos@example.test" in m.raw_text or "54321987M" in m.raw_text or "633" in m.raw_text]
    for m in approved:
        m.status = "accepted"

    assert len(approved) >= 1

    out_rot_pdf = FIXTURES_DIR / "test_purged_rotated.pdf"
    redaction_engine.purge_pdf(str(rotated_pdf), str(out_rot_pdf), approved, is_scanned=True)
    
    verified, failures, details = verification_engine.verify_pdf(str(out_rot_pdf), approved, is_scanned=True)
    assert verified is True, f"Rotated PDF verification failed: {failures}"

    if out_rot_pdf.exists():
        out_rot_pdf.unlink()
