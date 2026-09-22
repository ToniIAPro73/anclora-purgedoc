import io
import re
import logging
from typing import List, Dict, Any, Tuple
import pytesseract
from PIL import Image
import fitz # PyMuPDF
from backend.models import BoundingBox

logger = logging.getLogger(__name__)

# List of generic document labels that shouldn't trigger PII leakage alarms
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

    def ocr_page(self, page: fitz.Page, page_num: int) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Runs local Tesseract OCR on a rendered high-res pixmap of the PDF page.
        Returns:
          page_text: full reconstructed string
          word_rects: list of dicts with {"bbox": [x0, y0, x1, y1], "text": str, "conf": float}
        """
        zoom = 300 / 72.0 # 4.1666x
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img_bytes = pix.tobytes("png")
        pil_img = Image.open(io.BytesIO(img_bytes))

        try:
            ocr_data = pytesseract.image_to_data(
                pil_img,
                lang=self.default_langs,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            logger.error(f"Local Tesseract OCR execution failed: {e}")
            return "", []

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

            x = float(ocr_data['left'][i]) * scale_x
            y = float(ocr_data['top'][i]) * scale_y
            w = float(ocr_data['width'][i]) * scale_x
            h = float(ocr_data['height'][i]) * scale_y

            words_list.append({
                "bbox": [x, y, x + w, y + h],
                "text": word_str,
                "confidence": conf / 100.0
            })

        if current_line:
            full_text_lines.append(" ".join(current_line))

        full_page_text = "\n".join(full_text_lines)
        return full_page_text, words_list

    def scan_raster_pdf_for_text(self, pdf_path: str, targets: List[str]) -> List[str]:
        """
        Reopens a PDF, renders each page and runs Tesseract OCR from scratch
        to verify whether any target sensitive string is still readable from pixels.
        Filters out common boilerplate labels so false positives don't mask true verification.
        """
        doc = fitz.open(pdf_path)
        found_leaks = []

        # Filter out generic dictionary boilerplate words
        clean_targets = [
            t.strip().lower() for t in targets
            if len(t.strip()) >= 4 and t.strip().lower() not in NON_PII_BOILERPLATE
        ]
        if not clean_targets:
            doc.close()
            return []

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_text, _ = self.ocr_page(page, p_idx + 1)
            lower_page_text = page_text.lower()
            
            compact_page = re.sub(r'[\s\-_.:,]+', '', lower_page_text)

            for target in clean_targets:
                compact_target = re.sub(r'[\s\-_.:,]+', '', target)
                if compact_target and compact_target in compact_page:
                    found_leaks.append(f"Page {p_idx + 1}: '{target}' still detected by local Tesseract OCR post-purge")

        doc.close()
        return found_leaks

local_ocr_engine = LocalOcrEngine()
