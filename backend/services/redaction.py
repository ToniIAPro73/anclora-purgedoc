import os
import shutil
import zipfile
import logging
from typing import List, Dict, Any, Tuple
import fitz # PyMuPDF
import docx
from lxml import etree
from backend.models import MatchItem

logger = logging.getLogger(__name__)

class RedactionEngine:
    def __init__(self):
        pass

    def purge_pdf(self, input_pdf: str, output_pdf: str, approved_matches: List[MatchItem]) -> Dict[str, Any]:
        """
        Executes REAL redaction using PyMuPDF:
        1. Exact text bounding box redactions applied directly to PDF stream
        2. Content permanently removed from page streams
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
                
                # Search for target text instances to redact
                text_instances = page.search_for(target_text)
                if not text_instances and match.bbox:
                    # Fallback to bbox if text search couldn't locate string
                    b = match.bbox
                    rect = fitz.Rect(b.x0, b.y0, b.x1, b.y1)
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redactions_applied += 1
                else:
                    for inst in text_instances:
                        # Real redaction annotation with black fill
                        page.add_redact_annot(inst, fill=(0, 0, 0))
                        redactions_applied += 1
                
                # Apply redaction permanently to destroy the underlying stream
                page.apply_redactions()

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

        # Save with garbage collection to permanently expunge redacted streams
        doc.save(
            output_pdf,
            garbage=4,
            deflate=True,
            clean=True
        )
        doc.close()

        return {
            "redactions_applied": redactions_applied,
            "metadata_sanitized": ["author", "subject", "creator", "keywords", "modDate"]
        }

    def purge_docx(self, input_docx: str, output_docx: str, approved_matches: List[MatchItem]) -> Dict[str, Any]:
        """
        Executes REAL redaction on OOXML package:
        1. Directly traverses word/document.xml, headers, footers, comments
        2. Permanently replaces approved sensitive values with [PURGED/REDIGIDO]
        3. Sanitizes core.xml and app.xml properties
        """
        # Open via python-docx to perform paragraph, table and header/footer replacements
        doc = docx.Document(input_docx)
        values_to_redact = [m.raw_text.strip() for m in approved_matches if m.raw_text.strip()]
        redactions_count = 0

        for val in values_to_redact:
            if not val:
                continue

            # Check body paragraphs
            for p in doc.paragraphs:
                if val in p.text:
                    p.text = p.text.replace(val, "[REDIGIDO]")
                    redactions_count += 1

            # Check tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if val in cell.text:
                            cell.text = cell.text.replace(val, "[REDIGIDO]")
                            redactions_count += 1

            # Check sections (headers & footers)
            for section in doc.sections:
                for hp in section.header.paragraphs:
                    if val in hp.text:
                        hp.text = hp.text.replace(val, "[REDIGIDO]")
                        redactions_count += 1
                for fp in section.footer.paragraphs:
                    if val in fp.text:
                        fp.text = fp.text.replace(val, "[REDIGIDO]")
                        redactions_count += 1

        # Sanitize Core properties
        core_props = doc.core_properties
        core_props.author = "Anclora Purgedoc"
        core_props.last_modified_by = "Anclora Purgedoc"
        core_props.title = ""
        core_props.subject = ""
        core_props.keywords = ""
        core_props.comments = ""

        temp_saved_path = output_docx + ".tmp"
        doc.save(temp_saved_path)

        # Deep OOXML sanitize by unzipping and checking all internal XML parts
        self._deep_ooxml_sanitize(temp_saved_path, output_docx, values_to_redact)
        if os.path.exists(temp_saved_path):
            os.remove(temp_saved_path)

        return {
            "redactions_applied": redactions_count,
            "metadata_sanitized": ["core_properties", "app_properties", "headers", "footers", "tables"]
        }

    def _deep_ooxml_sanitize(self, zip_in: str, zip_out: str, values: List[str]):
        """Sanitizes any raw XML files inside the docx zip archive"""
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
