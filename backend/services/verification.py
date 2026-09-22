import os
import zipfile
import logging
from typing import List, Dict, Any, Tuple
import fitz # PyMuPDF
from pypdf import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract_text
from backend.models import MatchItem
from backend.services.ocr import local_ocr_engine
from backend.services.normalization import normalize_text, generate_adversarial_variants

logger = logging.getLogger(__name__)

# Non-sensitive OOXML style schema parts that do not contain document text
OOXML_SCHEMA_PARTS = {"word/styles.xml", "word/stylesWithEffects.xml", "word/fontTable.xml", "[Content_Types].xml"}

class VerificationEngine:
    def __init__(self):
        pass

    def verify_pdf(
        self,
        output_pdf_path: str,
        approved_matches: List[MatchItem],
        is_scanned: bool = False
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        if not os.path.exists(output_pdf_path):
            return False, ["Output PDF file does not exist"], {}

        failures = []
        details = {
            "pages_checked": 0,
            "metadata_checked": True,
            "secondary_engine_pypdf_checked": True,
            "tertiary_engine_pdfminer_checked": True,
            "values_verified_absent": 0,
            "ocr_verification_performed": is_scanned
        }

        sensitive_search_tokens = set()
        for match in approved_matches:
            raw = match.raw_text.strip()
            if raw:
                sensitive_search_tokens.add(raw)
                sensitive_search_tokens.update(generate_adversarial_variants(raw))

        try:
            doc = fitz.open(output_pdf_path)
            details["pages_checked"] = len(doc)
            pymupdf_full_text = ""
            for p_idx in range(len(doc)):
                page = doc[p_idx]
                p_text = page.get_text("text")
                pymupdf_full_text += "\n" + p_text

            pypdf_full_text = ""
            try:
                pypdf_reader = PdfReader(output_pdf_path)
                for page in pypdf_reader.pages:
                    pypdf_full_text += "\n" + (page.extract_text() or "")
            except Exception as e:
                failures.append(f"pypdf could not parse output PDF: {e}")

            pdfminer_full_text = ""
            try:
                pdfminer_full_text = pdfminer_extract_text(output_pdf_path) or ""
            except Exception as e:
                failures.append(f"pdfminer.six could not parse output PDF: {e}")

            all_text_raw = pymupdf_full_text + "\n" + pypdf_full_text + "\n" + pdfminer_full_text
            all_text_norm = normalize_text(all_text_raw)
            all_text_compact = "".join(all_text_norm.split())

            for token in sensitive_search_tokens:
                if len(token) < 4:
                    continue
                token_norm = normalize_text(token)
                token_compact = "".join(token_norm.split())

                if token in all_text_raw or token_norm in all_text_norm or (len(token_compact) >= 6 and token_compact in all_text_compact):
                    failures.append(f"Residual sensitive token detected in text streams: '{token[:6]}***'")
                else:
                    details["values_verified_absent"] += 1

            meta = doc.metadata or {}
            for k, val in meta.items():
                if val:
                    val_str = str(val).lower()
                    for token in sensitive_search_tokens:
                        if len(token) >= 4 and token.lower() in val_str:
                            failures.append(f"Sensitive value leaked in PDF metadata field '{k}'")

            for p_idx in range(len(doc)):
                page = doc[p_idx]
                for annot in page.annots() or []:
                    info = annot.info
                    for k, val in (info or {}).items():
                        if val:
                            for token in sensitive_search_tokens:
                                if len(token) >= 4 and token.lower() in str(val).lower():
                                    failures.append(f"Sensitive value leaked in annotation '{k}'")

            doc.close()

            if is_scanned:
                target_strings = [m.raw_text.strip() for m in approved_matches if len(m.raw_text.strip()) >= 3]
                ocr_leaks = local_ocr_engine.scan_raster_pdf_for_text(output_pdf_path, target_strings)
                if ocr_leaks:
                    failures.extend(ocr_leaks)
                else:
                    details["ocr_reverification_passed"] = True

        except Exception as e:
            failures.append(f"Corrupt or unreadable output PDF: {str(e)}")

        is_verified = len(failures) == 0
        return is_verified, failures, details

    def verify_docx(self, output_docx_path: str, approved_matches: List[MatchItem]) -> Tuple[bool, List[str], Dict[str, Any]]:
        if not os.path.exists(output_docx_path):
            return False, ["Output DOCX file does not exist"], {}

        failures = []
        details = {
            "ooxml_parts_checked": 0,
            "values_verified_absent": 0
        }

        sensitive_search_tokens = set()
        for match in approved_matches:
            raw = match.raw_text.strip()
            if raw:
                sensitive_search_tokens.add(raw)
                sensitive_search_tokens.update(generate_adversarial_variants(raw))

        try:
            with zipfile.ZipFile(output_docx_path, 'r') as z:
                all_parts = z.namelist()
                # Inspect all document content XML files, headers, footers, comments, footnotes, properties
                content_xml_files = [f for f in all_parts if (f.endswith(".xml") or f.endswith(".rels")) and f not in OOXML_SCHEMA_PARTS]
                details["ooxml_parts_checked"] = len(content_xml_files)
                
                for xf in content_xml_files:
                    raw_xml = z.read(xf).decode("utf-8", errors="ignore")
                    norm_xml = normalize_text(raw_xml)
                    compact_xml = "".join(norm_xml.split())

                    for token in sensitive_search_tokens:
                        if len(token) < 4:
                            continue
                        token_norm = normalize_text(token)
                        token_compact = "".join(token_norm.split())

                        if token in raw_xml or token_norm in norm_xml or (len(token_compact) >= 6 and token_compact in compact_xml):
                            failures.append(f"Residual sensitive value detected inside OOXML part '{xf}': '{token[:6]}***'")
                        else:
                            details["values_verified_absent"] += 1
        except Exception as e:
            failures.append(f"Invalid or corrupted DOCX zip package: {str(e)}")

        is_verified = len(failures) == 0
        return is_verified, failures, details

verification_engine = VerificationEngine()
