# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLM or external OCR calls).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support).
- Real physical redaction of underlying file streams (never a cosmetic black overlay).
- Automated post-purge fail-closed verification reopening and inspecting the generated file.
- Cryptographic forensic audit generation (PDF certificate & structured JSON) with SHA-256 hashes instead of plaintext PII.
- High-contrast accessible UI with dark default, ES/EN toggle, and synchronized document canvas.

## 2. Architecture & Tasks Completed
- **Vertical Profiles**: YAML rulesets in `/app/backend/config/profiles/` (`rrhh.yaml`, `legal.yaml`, `soporte.yaml`).
- **Detection Engine**: Hybrid local pipeline merging spaCy NER entities (PERSON, LOC, ORG) with vertical regex rules (DNI, CIF, IBAN, NSS, IP, API Tokens, Case IDs).
- **Redaction Engine**:
  - PDF: PyMuPDF physical stream elimination (`add_redact_annot`, `apply_redactions`) with garbage collection (`garbage=4`, `clean=True`).
  - DOCX: Deep OOXML package sanitization (`word/document.xml`, tables, headers, footers, `core.xml`).
- **Fail-Closed Verifier**: Automated reopening of the output document to scan for any residual matches.
- **Audit Service**: ReportLab PDF certificate and JSON manifest containing cryptographic SHA-256 hashes.
- **Frontend UI**: React 19 + Tailwind CSS with dark slate theme, bilingual support (ES/EN), interactive canvas with synchronized bounding box highlights, and QA fixture loader.

## 3. Prioritized Backlog
- **Local Tesseract OCR Engine**: On-premise OCR with `tesseract-ocr` (spa+eng) and `pytesseract` to detect sensitive entities on scanned raster-only PDFs.
- **Physical Raster Pixel Obliteration**: Eliminates underlying bitmap pixels from the page image so data cannot be extracted even by raw pixel extraction.
- **Post-Purge OCR Reverification**: Re-scans the redacted output PDF with Tesseract OCR to guarantee that sensitive strings are completely unrecoverable before certifying "Purga verificada".

- **P0**: End-to-end PDF & DOCX real redaction, automated verification, audit export (Completed).
- **P1**: Local Tesseract OCR capability for scanned raster-only PDFs.
- **P2**: Batch folder processing and custom organization ruleset editor.
