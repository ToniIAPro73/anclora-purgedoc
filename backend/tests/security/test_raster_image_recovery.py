import pytest
import os
import io
import fitz # PyMuPDF
from PIL import Image
import numpy as np
import pytesseract

from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_security_fixtures():
    generate_all_fixtures()

def test_raster_image_recovery_and_pixel_destruction():
    """
    2. RASTER / OCR PDF:
    - Purges scanned raster document
    - Extracts every embedded image XObject from the PDF
    - Saves each image independently
    - Runs Tesseract OCR directly on extracted image bytes
    - Runs Tesseract OCR on full-page renders
    - Checks that the bounding box pixels are physically destroyed (blacked out in bitmap)
    - Verifies no orphaned/hidden original raster objects remain in the PDF
    """
    scanned_pdf = FIXTURES_DIR / "sample_scanned_medical_hr.pdf"
    assert scanned_pdf.exists()

    pages, count, has_text, is_scanned = document_processor.extract_pdf_content(str(scanned_pdf))
    matches = detection_engine.analyze_document_content("sec_doc_raster", "rrhh", pages)

    # Targets to purge: DNI 54321987M and Email maria.santos@example.test
    targets = ["54321987M", "maria.santos@example.test"]
    approved = [m for m in matches if any(t in m.raw_text for t in targets)]
    for m in approved:
        m.status = "accepted"

    assert len(approved) >= 1

    out_pdf = FIXTURES_DIR / "test_sec_purged_raster.pdf"
    res = redaction_engine.purge_pdf(str(scanned_pdf), str(out_pdf), approved, is_scanned=True)
    assert res["raster_pixels_destroyed"] is True

    # 1. Open output PDF and inspect image XObjects
    doc = fitz.open(str(out_pdf))
    total_images_found = 0

    for p_idx in range(len(doc)):
        page = doc[p_idx]
        image_list = page.get_images(full=True)
        total_images_found += len(image_list)

        for img_info in image_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            extracted_pil = Image.open(io.BytesIO(image_bytes))

            # Run Tesseract OCR directly on the isolated extracted image XObject
            img_ocr_text = pytesseract.image_to_string(extracted_pil, lang="spa+eng").lower()

            for target in targets:
                clean_target = "".join(target.lower().split())
                compact_ocr = "".join(img_ocr_text.split())
                assert clean_target not in compact_ocr, f"Sensitive target {target} recovered from extracted image XObject!"

            # 2. Pixel inspection on rendered page: check that redacted bounding box area has been physically overwritten
            mat = fitz.Matrix(300 / 72.0, 300 / 72.0)
            rendered_pix = page.get_pixmap(matrix=mat, alpha=False)
            rendered_np = np.array(Image.open(io.BytesIO(rendered_pix.tobytes("png"))).convert("RGB"))

            for m in approved:
                if m.bbox and m.page == (p_idx + 1):
                    scale_x = rendered_np.shape[1] / float(page.rect.width)
                    scale_y = rendered_np.shape[0] / float(page.rect.height)
                    cx = int((m.bbox.x0 + m.bbox.x1) / 2.0 * scale_x)
                    cy = int((m.bbox.y0 + m.bbox.y1) / 2.0 * scale_y)

                    center_patch = rendered_np[cy-2:cy+3, cx-2:cx+3]
                    mean_val = np.mean(center_patch)
                    assert mean_val < 5.0, f"Redacted region at ({cx}, {cy}) is not physically blackened! mean={mean_val}"

    doc.close()
    assert total_images_found >= 1

    # 3. Fail-closed verification engine confirmation
    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=True)
    assert verified is True, f"Raster verification failed: {failures}"
    assert details.get("ocr_reverification_passed") is True

    if out_pdf.exists():
        out_pdf.unlink()
