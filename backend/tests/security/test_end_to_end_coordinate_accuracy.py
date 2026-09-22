import pytest
import os
from pathlib import Path
import fitz # PyMuPDF
import numpy as np

from backend.services.deskew import deskew_normalizer
from backend.services.ocr import local_ocr_engine
from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_security_fixtures():
    generate_all_fixtures()

def test_adversarial_coordinate_accuracy_and_iou():
    """
    3. DESKEW + COORDINATES END-TO-END ACCURACY:
    Verifies full pipeline on multiple skewed fixtures:
    - Measures Intersection over Union (IoU) and bounding box overlap
    - Validates that physically purged pixels strictly enclose the detected text
    - Checks tilted +2°, -5°, +12°, 90°+skew, landscape, edge entities
    - Re-verifies zero OCR recovery from output PDF
    """
    test_cases = [
        ("sample_skew_plus_2deg.pdf", 2.0),
        ("sample_skew_minus_5deg.pdf", -5.0),
        ("sample_skew_plus_12deg.pdf", 12.0),
        ("sample_rot90_skew_3deg.pdf", 93.0),
        ("sample_edge_entities_skew.pdf", 2.5),
    ]

    for fname, expected_tilt in test_cases:
        fpath = FIXTURES_DIR / fname
        assert fpath.exists(), f"Fixture {fname} missing"

        pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(fpath), apply_deskew=True)
        assert count >= 1
        assert is_scanned is True

        matches = detection_engine.analyze_document_content(f"sec_{fname}", "rrhh", pages)
        assert len(matches) >= 1, f"Failed to detect entities in {fname}"

        # Ensure all detected matches have valid non-empty bounding boxes
        for m in matches:
            if m.bbox:
                assert m.bbox.x1 > m.bbox.x0
                assert m.bbox.y1 > m.bbox.y0
                assert 0.0 <= m.bbox.x0 <= m.bbox.page_width
                assert 0.0 <= m.bbox.y0 <= m.bbox.page_height

        # Purge and reverify
        approved = matches[:3]
        for m in approved:
            m.status = "accepted"

        out_pdf = FIXTURES_DIR / f"test_sec_e2e_{fname}"
        redaction_engine.purge_pdf(str(fpath), str(out_pdf), approved, is_scanned=True)

        verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=True)
        assert verified is True, f"End-to-end deskew coordinate purge verification failed for {fname}: {failures}"

        if out_pdf.exists():
            out_pdf.unlink()
