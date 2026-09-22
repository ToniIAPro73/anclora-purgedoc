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
from backend.services.normalization import generate_adversarial_variants

logger = logging.getLogger(__name__)

class RedactionEngine:
    def __init__(self):
        pass

    def purge_pdf(self, input_pdf: str, output_pdf: str, approved_matches: List[MatchItem], is_scanned: bool = False) -> Dict[str, Any]:
        doc = fitz.open(input_pdf)
        redactions_applied = 0

        for match in approved_matches:
            p_idx = match.page - 1
            if 0 <= p_idx < len(doc):
                page = doc[p_idx]
                target_text = match.raw_text.strip()
                variants = generate_adversarial_variants(target_text)
                
                for variant in variants:
                    text_instances = page.search_for(variant)
                    for inst in text_instances:
                        page.add_redact_annot(inst, fill=(0, 0, 0))
                        redactions_applied += 1

                if match.bbox:
                    b = match.bbox
                    rect = fitz.Rect(b.x0, b.y0, b.x1, b.y1)
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redactions_applied += 1

                page.apply_redactions()

        if is_scanned:
            self._physically_destroy_raster_pixels(doc, approved_matches)

        # Sanitize metadata completely
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

        try:
            for emb_idx in range(doc.embfile_count()):
                doc.embfile_del(emb_idx)
        except Exception:
            pass

        doc.save(
            output_pdf,
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()

        return {
            "redactions_applied": redactions_applied,
            "metadata_sanitized": ["author", "subject", "creator", "keywords", "modDate", "attachments"],
            "raster_pixels_destroyed": is_scanned
        }

    def _physically_destroy_raster_pixels(self, doc: fitz.Document, approved_matches: List[MatchItem]):
        """
        Physical raster pixel sanitization:
        Paints solid black boxes directly onto the underlying image XObjects of the PDF,
        ensuring that any extracted image or rendered page has the pixels destroyed.
        """
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_matches = [m for m in approved_matches if m.page == (p_idx + 1) and m.bbox]
            if not page_matches:
                continue

            # First, modify each embedded image XObject directly if present
            image_list = page.get_images(full=True)
            for img_info in image_list:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                img_data = base_image["image"]
                pil_xobj = Image.open(io.BytesIO(img_data)).convert("RGB")
                draw_xobj = ImageDraw.Draw(pil_xobj)

                scale_x = pil_xobj.width / float(page.rect.width)
                scale_y = pil_xobj.height / float(page.rect.height)

                for m in page_matches:
                    b = m.bbox
                    pad = 12
                    px0 = max(0, int(b.x0 * scale_x) - pad)
                    py0 = max(0, int(b.y0 * scale_y) - pad)
                    px1 = min(pil_xobj.width, int(b.x1 * scale_x) + pad)
                    py1 = min(pil_xobj.height, int(b.y1 * scale_y) + pad)
                    draw_xobj.rectangle([px0, py0, px1, py1], fill="black")

                out_xobj_bytes = io.BytesIO()
                pil_xobj.save(out_xobj_bytes, format="PNG")
                doc.update_stream(xref, out_xobj_bytes.getvalue())

            # Also render page at 300 DPI and paint full black rectangles on the canvas
            mat = fitz.Matrix(300 / 72.0, 300 / 72.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            draw = ImageDraw.Draw(img)
            scale_x = pix.width / float(page.rect.width)
            scale_y = pix.height / float(page.rect.height)

            for m in page_matches:
                b = m.bbox
                pad = 12
                px0 = max(0, int(b.x0 * scale_x) - pad)
                py0 = max(0, int(b.y0 * scale_y) - pad)
                px1 = min(pix.width, int(b.x1 * scale_x) + pad)
                py1 = min(pix.height, int(b.y1 * scale_y) + pad)
                draw.rectangle([px0, py0, px1, py1], fill="black")

            out_img_bytes = io.BytesIO()
            img.save(out_img_bytes, format="PNG")
            out_img_bytes.seek(0)

            page.clean_contents()
            rect = page.rect
            page.insert_image(rect, stream=out_img_bytes.getvalue())

    def purge_docx(self, input_docx: str, output_docx: str, approved_matches: List[MatchItem]) -> Dict[str, Any]:
        doc = docx.Document(input_docx)
        
        all_targets = set()
        for m in approved_matches:
            raw = m.raw_text.strip()
            if raw:
                all_targets.add(raw)
                all_targets.update(generate_adversarial_variants(raw))

        redactions_count = 0

        for val in all_targets:
            if len(val) < 4:
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

        self._deep_ooxml_sanitize(temp_saved_path, output_docx, list(all_targets))
        if os.path.exists(temp_saved_path):
            os.remove(temp_saved_path)

        return {
            "redactions_applied": redactions_count,
            "metadata_sanitized": ["core_properties", "app_properties", "headers", "footers", "tables", "ooxml_all_parts"]
        }

    def _deep_ooxml_sanitize(self, zip_in: str, zip_out: str, values: List[str]):
        """Sanitizes any raw XML / rels files inside the docx zip archive"""
        with zipfile.ZipFile(zip_in, 'r') as zin:
            with zipfile.ZipFile(zip_out, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename.endswith(".xml") or item.filename.endswith(".rels"):
                        try:
                            text_content = data.decode("utf-8")
                            for v in values:
                                if len(v) >= 4 and v in text_content:
                                    text_content = text_content.replace(v, "[REDIGIDO]")
                            data = text_content.encode("utf-8")
                        except Exception:
                            pass
                    zout.writestr(item, data)

redaction_engine = RedactionEngine()
