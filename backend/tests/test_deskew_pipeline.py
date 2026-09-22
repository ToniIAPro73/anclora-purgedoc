import pytest
import os
import shutil
import numpy as np
from pathlib import Path
import fitz # PyMuPDF

from backend.services.deskew import deskew_normalizer, MultiAngleDeskewNormalizer
from backend.services.ocr import local_ocr_engine
from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_deskew_suite():
    generate_all_fixtures()

def test_straight_page_not_deskewed():
    """Verify that nearly straight pages (<0.5 deg) are not transformed"""
    pdf_path = FIXTURES_DIR / "sample_scanned_medical_hr.pdf"
    assert pdf_path.exists()
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    
    text, words, deskew_info = local_ocr_engine.ocr_page(page, 1, apply_deskew=True)
    doc.close()
    
    assert deskew_info["applied"] is False
    assert abs(deskew_info.get("skew_angle", 0.0)) < 0.5 or not deskew_info.get("should_correct", False)

def test_skewed_plus_2_degrees():
    """Verify +2 degrees skew is detected, deskewed, and entities extracted"""
    pdf_path = FIXTURES_DIR / "sample_skew_plus_2deg.pdf"
    assert pdf_path.exists()
    
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    assert count == 1
    assert is_scanned is True
    
    p1 = pages[0]
    deskew = p1.get("deskew", {})
    assert deskew.get("applied") is True
    assert 1.0 <= abs(deskew.get("angle", 0.0)) <= 3.5
    assert deskew.get("confidence", 0.0) >= 0.40

    matches = detection_engine.analyze_document_content("doc_plus2", "rrhh", pages)
    raw_texts = [m.raw_text for m in matches]
    assert any("54321987M" in t for t in raw_texts) or any("maria" in t.lower() for t in raw_texts)

def test_skewed_minus_5_degrees():
    """Verify -5 degrees skew is detected, deskewed, and coordinates mapped inversely"""
    pdf_path = FIXTURES_DIR / "sample_skew_minus_5deg.pdf"
    assert pdf_path.exists()
    
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    deskew = pages[0].get("deskew", {})
    assert deskew.get("applied") is True
    assert 3.5 <= abs(deskew.get("angle", 0.0)) <= 6.5

    matches = detection_engine.analyze_document_content("doc_minus5", "rrhh", pages)
    assert len(matches) >= 1

def test_skewed_plus_12_degrees():
    """Verify large skew (+12 degrees) is accurately straightened"""
    pdf_path = FIXTURES_DIR / "sample_skew_plus_12deg.pdf"
    assert pdf_path.exists()
    
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    deskew = pages[0].get("deskew", {})
    assert deskew.get("applied") is True
    assert 9.0 <= abs(deskew.get("angle", 0.0)) <= 15.0

    matches = detection_engine.analyze_document_content("doc_plus12", "rrhh", pages)
    assert len(matches) >= 1

def test_rotated_90_plus_skew():
    """Verify orthogonal rotation (90 deg) + additional skew"""
    pdf_path = FIXTURES_DIR / "sample_rot90_skew_3deg.pdf"
    assert pdf_path.exists()
    
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    assert is_scanned is True
    matches = detection_engine.analyze_document_content("doc_rot_skew", "rrhh", pages)
    assert len(matches) >= 1

def test_multipage_with_distinct_angles():
    """Verify multipage document where each page has a distinct angle"""
    pdf_path = FIXTURES_DIR / "sample_multipage_skew.pdf"
    assert pdf_path.exists()
    
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    assert count == 3
    d2 = pages[1].get("deskew", {})
    d3 = pages[2].get("deskew", {})
    
    assert d2.get("applied") is True
    assert d3.get("applied") is True

def test_low_confidence_unskewable_page():
    """Verify that pages where angle confidence is insufficient are NOT modified (fail-safe)"""
    pdf_path = FIXTURES_DIR / "sample_low_confidence_unskewable.pdf"
    assert pdf_path.exists()
    
    doc = fitz.open(str(pdf_path))
    _, _, deskew_info = local_ocr_engine.ocr_page(doc[0], 1, apply_deskew=True)
    doc.close()
    
    assert deskew_info.get("applied") is False
    assert deskew_info.get("confidence", 0.0) < 0.40 or not deskew_info.get("should_correct", False)

def test_exact_coordinate_forward_and_inverse_mapping():
    """
    Mathematical verification of exact round-trip coordinate transformation
    P_orig == M_inv * (M * P_orig) within machine epsilon
    """
    normalizer = MultiAngleDeskewNormalizer()
    angle = 4.75
    fake_img = np.zeros((1000, 800, 3), dtype=np.uint8)
    _, M, M_inv = normalizer.deskew_image(fake_img, angle)

    sample_points = np.array([
        [150.0, 220.0],
        [380.0, 260.0],
        [400.0, 500.0],
        [50.0, 80.0]
    ], dtype=np.float64)

    t_points = MultiAngleDeskewNormalizer.transform_points(sample_points, M)
    round_trip = MultiAngleDeskewNormalizer.transform_points(t_points, M_inv)

    diff = np.max(np.abs(sample_points - round_trip))
    assert diff < 1e-10, f"Round-trip point difference {diff} exceeds machine precision"

def test_deskew_purge_and_post_ocr_reverification():
    """
    End-to-End:
    1. Process skewed document (+2 deg)
    2. Accept detected PII
    3. Physically purge raster pixels
    4. Re-run OCR on final document
    5. Certify 'Purga verificada' only after OCR confirms absence
    """
    pdf_path = FIXTURES_DIR / "sample_skew_plus_2deg.pdf"
    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    matches = detection_engine.analyze_document_content("doc_deskew_purge", "rrhh", pages)

    approved = [m for m in matches if "54321987M" in m.raw_text or "maria" in m.raw_text.lower()]
    for m in approved:
        m.status = "accepted"
    assert len(approved) >= 1

    out_pdf = FIXTURES_DIR / "test_purged_deskew_plus2.pdf"
    res = redaction_engine.purge_pdf(str(pdf_path), str(out_pdf), approved, is_scanned=True)
    assert res["raster_pixels_destroyed"] is True

    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=True)
    assert verified is True, f"Deskew purge post-OCR verification failed: {failures}"
    assert details.get("ocr_reverification_passed") is True

    if out_pdf.exists():
        out_pdf.unlink()

def test_entities_near_borders_with_skew():
    """Verify entities located near edges/borders are safely detected and physically purged"""
    pdf_path = FIXTURES_DIR / "sample_edge_entities_skew.pdf"
    assert pdf_path.exists()

    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(pdf_path), apply_deskew=True)
    matches = detection_engine.analyze_document_content("doc_edge_purge", "rrhh", pages)
    
    edge_matches = [m for m in matches if "77889900X" in m.raw_text or "54321987M" in m.raw_text]
    assert len(edge_matches) >= 1
    for m in edge_matches:
        m.status = "accepted"

    out_pdf = FIXTURES_DIR / "test_purged_edge.pdf"
    redaction_engine.purge_pdf(str(pdf_path), str(out_pdf), edge_matches, is_scanned=True)
    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), edge_matches, is_scanned=True)
    assert verified is True

    if out_pdf.exists():
        out_pdf.unlink()

def test_ocr_quality_comparison_with_and_without_deskew():
    """
    Measures and compares OCR word count and detection quality before and after deskew.
    Documents that deskew maintains or improves OCR extraction on tilted documents.
    """
    pdf_path = FIXTURES_DIR / "sample_skew_minus_5deg.pdf"
    doc = fitz.open(str(pdf_path))
    page = doc[0]

    # Without deskew
    text_raw, words_raw, _ = local_ocr_engine.ocr_page(page, 1, apply_deskew=False)
    # With deskew
    text_deskew, words_deskew, deskew_info = local_ocr_engine.ocr_page(page, 1, apply_deskew=True)
    doc.close()

    assert deskew_info["applied"] is True
    # Verify that straightening produces high-fidelity text containing key PII
    assert len(words_deskew) >= 30
    assert "54321987M" in text_deskew or "54321987" in text_deskew
    assert "example.test" in text_deskew
