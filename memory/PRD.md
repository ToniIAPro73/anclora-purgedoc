# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test, and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction and forensic verification application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLMs, zero cloud APIs, zero external OCR).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support/DevOps).
- Real physical redaction of underlying file streams (never a cosmetic black overlay) across both PDF (PyMuPDF stream obliteration) and DOCX (OOXML package deep XML sanitization).
- Multi-angle Deskew Normalizer (OpenCV) and Local OCR Engine (Tesseract) for scanned and rotated documents.
- Custom Ruleset Editor with Regex Test Bench powered by safe `google-re2` against catastrophic backtracking (ReDoS).
- Automated post-purge fail-closed verification reopening and inspecting the generated file. If any approved sensitive string remains detectable in text, streams, or metadata, the output is blocked.
- Cryptographic forensic audit generation (PDF certificate & structured JSON) with SHA-256 hashes instead of plaintext PII, incorporating deterministic ruleset hashes.
- High-contrast accessible UI with dark default, light/system mode, ES/EN toggle, and synchronized document canvas.

---

## 2. Architecture & Accomplished Features

### 2.1 Vertical Profiles & Hybrid Local Detection
- YAML rulesets in `/app/backend/config/profiles/` (`rrhh.yaml`, `legal.yaml`, `soporte.yaml`).
- Detection Pipeline: Merges spaCy local NER (PERSON, ORG, LOC) with vertical regex rules (DNI, CIF, IBAN, NSS, IP, API Tokens, Case IDs).
- Deduplication & Overlap Resolution: Prioritizes custom rules and high-confidence regex rules over lower-confidence NER predictions.

### 2.2 Custom Ruleset Editor & Regex Test Bench (Iteration 6 Certified)
- **Architecture**:
  - Backend: `backend/services/rules.py` and endpoints in `/api/rules` (`/validate`, `/test`, `/hash`).
  - Frontend: `CustomRulesetEditor.js` (full CRUD, enable/disable toggle, duplication, JSON import/export, factory rule cloning) and `RegexTestBench.js` (interactive sandbox with live match feedback).
- **Security & ReDoS Protection**:
  - Powered by `google-re2` library with sub-millisecond execution timeouts.
  - Strict syntax validation blocking catastrophic backtracking, nested quantifiers, and oversized patterns (>1024 characters).
- **Persistence Model**:
  - Ephemeral client-side storage (`localStorage: anclora_custom_rules`) adhering to sovereign privacy (no database leakage across users/sessions).
  - Export/Import JSON allows portability across air-gapped workstations.
- **Audit Provenance & Cryptographic Hashing**:
  - Computes order-invariant, deterministic SHA-256 hash of active rules (`calculate_hash()`).
  - Recorded in the audit manifest (`ruleset.custom_ruleset_hash`, `ruleset.custom_ruleset_id`, `ruleset.custom_ruleset_version`, `ruleset.active_custom_rules_count`) without logging plaintext sensitive expressions.

### 2.3 Real Physical Redaction & Fail-Closed Post-Purge Verification
- **PDF**: PyMuPDF stream obliteration (`add_redact_annot`, `apply_redactions`) with complete unreferenced object garbage collection (`garbage=4`, `clean=True`).
- **DOCX**: Unzips package and sanitizes all OOXML parts (`word/document.xml`, tables, headers, footers, comments, footnotes, `core.xml`, `app.xml`).
- **OCR Raster Destruction**: Underlying bitmap pixels of scanned documents are irreversibly obliterated in memory before re-encoding; Tesseract re-scans the output to guarantee zero optical recovery.
- **Adversarial Verification Suite**: `backend/tests/security/` validates multi-engine PDF recovery (PyMuPDF, pypdf, pdfminer.six), raw byte streams, raster pixel intensity, and Unicode NFKC normalization resistance.

---

## 3. Test & Verification Status
- **Backend Tests**: 42/42 tests passing in parallel (`pytest-xdist LoadScope`, ~53s execution).
  - `backend/tests/test_custom_rules.py` (8 tests)
  - `backend/tests/security/` (7 security hardening and adversarial recovery suites)
  - `backend/tests/test_api_e2e.py`, `test_deskew_pipeline.py`, `test_ocr_pipeline.py`, `test_redaction_pipeline.py`
- **Frontend E2E**: 100% PASS verified via `testing_agent_v3` (Iteration 6 report `/app/test_reports/iteration_6.json`).
  - Modal opening/closing from Header and UploadScreen badge.
  - Rule CRUD, duplication, status toggle, delete confirmation.
  - Regex Test Bench: valid pattern execution with timing, invalid pattern error handling, ReDoS safety.
  - E2E purge verification on native PDF, scanned OCR PDF, and DOCX.
  - Audit manifest verified to include ruleset hashes with zero sensitive plaintext leakage.

---

## 4. Current Limitations & Technical Debt
1. **App.js & server.py file size**:
   - `server.py` (~470 lines) and `App.js` (~326 lines) are expanding. Modularization using FastAPI `APIRouter` splits (e.g. `routes/documents.py`, `routes/rules.py`, `routes/sessions.py`) is recommended in future iterations.
2. **Client-side Ruleset Scope**:
   - Custom rules are stored in browser `localStorage`. They do not synchronize across different devices/browsers unless exported/imported as JSON.
3. **Session Download Endpoints**:
   - Document download endpoints are session-scoped and ephemeral; no permanent multi-user auth or role-based access control (by intentional MVP design).

---

## 5. Prioritized Backlog

### P0 (Next Immediate Feature — Pending User Confirmation):
- **Batch Document Queue**:
  - Processing of multiple documents within a single ephemeral session.
  - Independent queues, per-document status, cancellation, partial error handling, unified ZIP download, and batch audit summary.

### P1 (Backlog):
- **Batch Deskew Preview**:
  - Visual side-by-side inspection of corrected angles across multiple pages prior to OCR.
- **Encrypted Profile Export/Import**:
  - Encrypted JSON/YAML rule packages with optional passphrase protection for secure enterprise sharing.
