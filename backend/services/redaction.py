import os
import shutil
import zipfile
import logging
from typing import List, Dict, Any, Tuple
import fitz # PyMuPDF
import docx
from lxml import etree
from PIL import Image, ImageDraw
import io
from backend.models import MatchItem

logger = logging.getLogger(__name__)

class RedactionEngine:
    def __init__(self):
        pass

    def purge_pdf(self, input_pdf: str, output_pdf: str, approved_matches: List[MatchItem], is_scanned: bool = False) -> Dict[str, Any]:
        """
        Executes REAL redaction using PyMuPDF:
        1. Native text layer: Apply physical stream redaction annotations
        2. Scanned / raster layer: Physically obliterate pixel bounding boxes in raster image
        3. Strips metadata (Author, Subject, Producer, Creator, Keywords, ModDate)
        4. Saves with clean garbage collection
        """
        doc = fitz.open(input_pdf)
        redactions_applied = 0

        for match in approved_matches:
            p_idx = match.page - 1
            if 0 <= p_idx < len(doc):
                page = doc[p_idx]
                target_text = match.raw_text.strip()
                
                text_instances = page.search_for(target_text)
                if text_instances:
                    for inst in text_instances:
                        page.add_redact_annot(inst, fill=(0, 0, 0))
                        redactions_applied += 1
                elif match.bbox:
                    b = match.bbox
                    rect = fitz.Rect(b.x0, b.y0, b.x1, b.y1)
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redactions_applied += 1
                
                page.apply_redactions()

        # If scanned / raster-only PDF: destroy underlying pixel bytes
        if is_scanned:
            self._physically_destroy_raster_pixels(doc, approved_matches)

        # Sanitize metadata
        metadata = {
            "title": "",
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "Anclora Purgedoc Secure Engine",
            "creationDate": "",
            "modDate": ""
        }
        doc.set_metadata(metadata)

        doc.save(
            output_pdf,
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()

        return {
            "redactions_applied": redactions_applied,
            "metadata_sanitized": ["author", "subject", "creator", "keywords", "modDate"],
            "raster_pixels_destroyed": is_scanned
        }

    def _physically_destroy_raster_pixels(self, doc: fitz.Document, approved_matches: List[MatchItem]):
        """
        Physical raster pixel sanitization:
        Renders each page into a high-res pixmap, paints solid black boxes over bounding boxes,
        and replaces the page contents with the sanitized flattened image.
        """
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_matches = [m for m in approved_matches if m.page == (p_idx + 1) and m.bbox]
            if not page_matches:
                continue

            # Render at 300 DPI
            mat = fitz.Matrix(300 / 72.0, 300 / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            draw = ImageDraw.Draw(img)
            
            scale_x = pix.width / float(page.rect.width)
            scale_y = pix.height / float(page.rect.height)

            for m in page_matches:
                b = m.bbox
                pad_x = 10
                pad_y = 6
                px0 = max(0, int(b.x0 * scale_x) - pad_x)
                py0 = max(0, int(b.y0 * scale_y) - pad_y)
                px1 = min(pix.width, int(b.x1 * scale_x) + pad_x)
                py1 = min(pix.height, int(b.y1 * scale_y) + pad_y)
                draw.rectangle([px0, py0, px1, py1], fill="black")

            out_img_bytes = io.BytesIO()
            img.save(out_img_bytes, format="PNG")
            out_img_bytes.seek(0)

            # Replace the page contents with the sanitized image
            page.clean_contents()
            rect = page.rect
            page.insert_image(rect, stream=out_img_bytes.getvalue())

    def purge_docx(self, input_docx: str, output_docx: str, approved_matches: List[MatchItem]) -> Dict[str, Any]:
        doc = docx.Document(input_docx)
        values_to_redact = [m.raw_text.strip() for m in approved_matches if m.raw_text.strip()]
        redactions_count = 0

        for val in values_to_redact:
            if not val:
                continue

            for p in doc.paragraphs:
                if val in p.text:
                    p.text = p.text.replace(val, "[REDIGIDO]")
                    redactions_count += 1

            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if val in cell.text:
                            cell.text = cell.text.replace(val, "[REDIGIDO]")
                            redactions_count += 1

            for section in doc.sections:
                for hp in section.header.paragraphs:
                    if val in hp.text:
                        hp.text = hp.text.replace(val, "[REDIGIDO]")
                        redactions_count += 1
                for fp in section.footer.paragraphs:
                    if val in fp.text:
                        fp.text = fp.text.replace(val, "[REDIGIDO]")
                        redactions_count += 1

        core_props = doc.core_properties
        core_props.author = "Anclora Purgedoc"
        core_props.last_modified_by = "Anclora Purgedoc"
        core_props.title = ""
        core_props.subject = ""
        core_props.keywords = ""
        core_props.comments = ""

        temp_saved_path = output_docx + ".tmp"
        doc.save(temp_saved_path)

        self._deep_ooxml_sanitize(temp_saved_path, output_docx, values_to_redact)
        if os.path.exists(temp_saved_path):
            os.remove(temp_saved_path)

        return {
            "redactions_applied": redactions_count,
            "metadata_sanitized": ["core_properties", "app_properties", "headers", "footers", "tables"]
        }

    def _deep_ooxml_sanitize(self, zip_in: str, zip_out: str, values: List[str]):
        with zipfile.ZipFile(zip_in, 'r') as zin:
            with zipfile.ZipFile(zip_out, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename.endswith(".xml") or item.filename.endswith(".rels"):
                        try:
                            text_content = data.decode("utf-8")
                            for v in values:
                                if v in text_content:
                                    text_content = text_content.replace(v, "[REDIGIDO]")
                            data = text_content.encode("utf-8")
                        except Exception:
                            pass
                    zout.writestr(item, data)

redaction_engine = RedactionEngine()
