import os
import zipfile
import logging
from typing import List, Dict, Any, Tuple
import fitz # PyMuPDF
from backend.models import MatchItem
from backend.services.ocr import local_ocr_engine

logger = logging.getLogger(__name__)

class VerificationEngine:
    def __init__(self):
        pass

    def verify_pdf(
        self,
        output_pdf_path: str,
        approved_matches: List[MatchItem],
        is_scanned: bool = False
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Mandatory Post-Purge Verification:
        Reopens the generated file and rigorously validates:
        1. Approved text values are NOT present in extracted text across all pages
        2. Sensitive text is NOT present in any metadata key
        3. If scanned / raster: re-runs local Tesseract OCR over the output PDF
           to ensure text cannot be recovered by OCR from the pixel layer
        4. File can be parsed and is not corrupt
        """
        if not os.path.exists(output_pdf_path):
            return False, ["Output PDF file does not exist"], {}

        failures = []
        details = {
            "pages_checked": 0,
            "metadata_checked": True,
            "values_verified_absent": 0,
            "ocr_verification_performed": is_scanned
        }

        try:
            doc = fitz.open(output_pdf_path)
            details["pages_checked"] = len(doc)
            
            # 1. Check all extractable text
            full_extracted_text = ""
            for p_idx in range(len(doc)):
                page = doc[p_idx]
                p_text = page.get_text("text")
                full_extracted_text += "\n" + p_text

            for match in approved_matches:
                raw = match.raw_text.strip()
                if not raw:
                    continue
                if raw in full_extracted_text:
                    failures.append(f"Residual text detected on document stream for match hash {match.original_text_hash[:16]}")
                else:
                    details["values_verified_absent"] += 1

            # 2. Check metadata
            meta = doc.metadata or {}
            for k, val in meta.items():
                if val:
                    for match in approved_matches:
                        raw = match.raw_text.strip()
                        if raw and raw in str(val):
                            failures.append(f"Sensitive value leaked in PDF metadata field '{k}'")

            doc.close()

            # 3. For scanned/raster PDFs, run full local Tesseract OCR post-verification!
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
        """
        Mandatory DOCX Verification:
        Reopens OOXML package and validates absence of approved values in all parts
        """
        if not os.path.exists(output_docx_path):
            return False, ["Output DOCX file does not exist"], {}

        failures = []
        details = {
            "ooxml_parts_checked": 0,
            "values_verified_absent": 0
        }

        try:
            with zipfile.ZipFile(output_docx_path, 'r') as z:
                xml_files = [f for f in z.namelist() if f.endswith(".xml")]
                details["ooxml_parts_checked"] = len(xml_files)
                
                for xf in xml_files:
                    raw_xml = z.read(xf).decode("utf-8", errors="ignore")
                    for match in approved_matches:
                        raw = match.raw_text.strip()
                        if not raw:
                            continue
                        if raw in raw_xml:
                            failures.append(f"Residual sensitive value detected inside OOXML part '{xf}'")
                        else:
                            details["values_verified_absent"] += 1
        except Exception as e:
            failures.append(f"Invalid or corrupted DOCX zip package: {str(e)}")

        is_verified = len(failures) == 0
        return is_verified, failures, details

verification_engine = VerificationEngine()
