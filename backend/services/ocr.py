import os
from pathlib import Path
import io
import re
import logging
from typing import List, Dict, Any, Tuple
import pytesseract
from PIL import Image
import numpy as np
import fitz # PyMuPDF
from backend.models import BoundingBox
from backend.services.deskew import deskew_normalizer

logger = logging.getLogger(__name__)

# Auto-configure TESSDATA_PREFIX if local backend/tessdata exists
_repo_tessdata = Path(__file__).resolve().parent.parent / "tessdata"
if _repo_tessdata.is_dir() and "TESSDATA_PREFIX" not in os.environ:
    os.environ["TESSDATA_PREFIX"] = str(_repo_tessdata)

NON_PII_BOILERPLATE = {
    "informe", "aptitud", "laboral", "centro", "medico", "departamento",
    "rrhh", "trabajador", "contacto", "notas", "confidenciales",
    "puesto", "trabajo", "patologias", "previas", "riesgo", "apto",
    "certificado", "tecnico", "rotado", "asignado", "interna", "nacional"
}

class LocalOcrEngine:
    def __init__(self):
        self.default_langs = "spa+eng"

    def is_raster_only_pdf(self, doc: fitz.Document) -> bool:
        """Determines if PDF has no native selectable text layer (scanned or image-only)"""
        total_text = ""
        for page in doc:
            total_text += page.get_text("text").strip()
            if len(total_text) > 30:
                return False
        return len(total_text) < 10

    def ocr_page(
        self,
        page: fitz.Page,
        page_num: int,
        apply_deskew: bool = True
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Runs local Tesseract OCR on a rendered high-res pixmap of the PDF page.
        Integrates MultiAngleDeskewNormalizer:
        1. Estimates tilt/skew using OpenCV.
        2. If skew exceeds threshold and confidence is sufficient, straightens the image.
        3. Runs Tesseract OCR on the straightened image.
        4. Inversely maps the OCR bounding boxes back to the original PDF page coordinate space
           using the stored affine inverse transformation matrix M_inv.
        Returns:
          page_text: full reconstructed string
          word_rects: list of dicts with {"bbox": [x0, y0, x1, y1], "text": str, "conf": float} in original PDF page coords
          deskew_info: metadata with estimated angle, confidence, applied matrix M and M_inv
        """
        zoom = 300 / 72.0 # 4.1666x
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # Convert pixmap to numpy array for OpenCV deskew analysis
        img_bytes = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_bytes))
        img_np = np.array(pil_img)

        deskew_info = {
            "applied": False,
            "angle": 0.0,
            "confidence": 0.0,
            "reason": "disabled"
        }

        active_img = pil_img
        M = None
        M_inv = None

        if apply_deskew and deskew_normalizer.enabled:
            skew_res = deskew_normalizer.estimate_skew(img_np)
            deskew_info.update(skew_res)
            
            if skew_res.get("should_correct", False):
                angle = skew_res["skew_angle"]
                # In OpenCV coordinate system, rotating by +angle rotates counter-clockwise
                # which straightens text lines with dy/dx > 0
                straightened_np, M, M_inv = deskew_normalizer.deskew_image(img_np, angle)
                active_img = Image.fromarray(straightened_np)
                deskew_info["applied"] = True
                deskew_info["angle"] = float(angle)
                deskew_info["matrix_M"] = M.tolist() if M is not None else None
                deskew_info["matrix_M_inv"] = M_inv.tolist() if M_inv is not None else None
                logger.info(f"Page {page_num}: Applied deskew of {angle:.2f}° (conf: {skew_res['confidence']:.2f})")

        try:
            ocr_data = pytesseract.image_to_data(
                active_img,
                lang=self.default_langs,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            logger.error(f"Local Tesseract OCR execution failed: {e}")
            return "", [], deskew_info

        page_w = page.rect.width
        page_h = page.rect.height
        pix_w = pix.width
        pix_h = pix.height

        scale_x = page_w / float(pix_w)
        scale_y = page_h / float(pix_h)

        words_list = []
        full_text_lines = []
        n_boxes = len(ocr_data['text'])

        current_line = []
        last_line_num = -1

        for i in range(n_boxes):
            word_str = ocr_data['text'][i].strip()
            conf = float(ocr_data['conf'][i])
            line_num = ocr_data.get('line_num', [0])[i]

            if line_num != last_line_num and current_line:
                full_text_lines.append(" ".join(current_line))
                current_line = []
            last_line_num = line_num

            if not word_str or conf < 10:
                continue

            current_line.append(word_str)

            # Raw pixel box on active image
            raw_px_box = [
                float(ocr_data['left'][i]),
                float(ocr_data['top'][i]),
                float(ocr_data['left'][i] + ocr_data['width'][i]),
                float(ocr_data['top'][i] + ocr_data['height'][i])
            ]

            # If deskew was applied, inversely transform bounding box back to original coordinates!
            if deskew_info["applied"] and M_inv is not None:
                orig_px_box = deskew_normalizer.transform_bbox_inverse(
                    raw_px_box,
                    M_inv,
                    float(pix_w),
                    float(pix_h)
                )
            else:
                orig_px_box = raw_px_box

            # Scale to PDF points
            x0 = orig_px_box[0] * scale_x
            y0 = orig_px_box[1] * scale_y
            x1 = orig_px_box[2] * scale_x
            y1 = orig_px_box[3] * scale_y

            words_list.append({
                "bbox": [x0, y0, x1, y1],
                "text": word_str,
                "confidence": conf / 100.0
            })

        if current_line:
            full_text_lines.append(" ".join(current_line))

        full_page_text = "\n".join(full_text_lines)
        return full_page_text, words_list, deskew_info

    def scan_raster_pdf_for_text(self, pdf_path: str, targets: List[str]) -> List[str]:
        """
        Reopens a PDF, renders each page and runs Tesseract OCR from scratch
        to verify whether any target sensitive string is still readable from pixels.
        """
        doc = fitz.open(pdf_path)
        found_leaks = []

        clean_targets = [
            t.strip().lower() for t in targets
            if len(t.strip()) >= 4 and t.strip().lower() not in NON_PII_BOILERPLATE
        ]
        if not clean_targets:
            doc.close()
            return []

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_text, _, _ = self.ocr_page(page, p_idx + 1, apply_deskew=True)
            lower_page_text = page_text.lower()
            
            compact_page = re.sub(r'[\s\-_.:,]+', '', lower_page_text)

            for target in clean_targets:
                compact_target = re.sub(r'[\s\-_.:,]+', '', target)
                if compact_target and compact_target in compact_page:
                    found_leaks.append(f"Page {p_idx + 1}: '{target}' still detected by local Tesseract OCR post-purge")

        doc.close()
        return found_leaks

local_ocr_engine = LocalOcrEngine()
