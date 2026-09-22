# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test, and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction, batch processing, and forensic verification application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLMs, zero cloud APIs, zero external OCR).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support/DevOps).
- Real physical redaction of underlying file streams (never a cosmetic black overlay) across both PDF (PyMuPDF stream obliteration) and DOCX (OOXML package deep XML sanitization).
- Multi-angle Deskew Normalizer (OpenCV) and Local OCR Engine (Tesseract) for scanned and rotated documents.
- Custom Ruleset Editor with Regex Test Bench powered by safe `google-re2` against catastrophic backtracking (ReDoS).
- Sovereign **Batch Document Queue** and **Batch Audit Summary** orchestrating multi-document workflows with controlled concurrency, per-document independent lifecycle, and fail-closed batch integrity.
- Automated post-purge fail-closed verification reopening and inspecting the generated file. If any approved sensitive string remains detectable in text, streams, or metadata, the output is blocked.
- Cryptographic forensic audit generation (individual & batch PDF certificates & structured JSON) with SHA-256 hashes instead of plaintext PII, incorporating deterministic ruleset hashes.
- High-contrast accessible UI with dark default, light/system mode, ES/EN toggle, synchronized document canvas, and seamless single/batch mode switching.

---

## 2. Architecture & Accomplished Features

### 2.1 Vertical Profiles & Hybrid Local Detection
- YAML rulesets in `/app/backend/config/profiles/` (`rrhh.yaml`, `legal.yaml`, `soporte.yaml`).
- Detection Pipeline: Merges spaCy local NER (PERSON, ORG, LOC) with vertical regex rules (DNI, CIF, IBAN, NSS, IP, API Tokens, Case IDs).
- Deduplication & Overlap Resolution: Prioritizes custom rules and high-confidence regex rules over lower-confidence NER predictions.

### 2.2 Custom Ruleset Editor & Regex Test Bench
- Safe `google-re2` pattern execution with sub-millisecond timeouts and catastrophic backtracking protection.
- Interactive sandbox (`RegexTestBench.js`) for syntax checking and live match testing.
- Deterministic order-invariant SHA-256 hash calculation per ruleset (`calculate_hash()`).
- Ephemeral client-side storage (`localStorage: anclora_custom_rules`) with export/import JSON portability.

### 2.3 Batch Document Queue & Batch Audit Summary (Iteration 7 Certified)
- **Architecture & Pipeline Reuse**:
  - Reuses the sovereign single-document pipeline (`upload -> analyze -> review -> purge -> verify -> audit`) as the single source of truth; zero code duplication.
  - Independent per-document status lifecycle: `queued`, `validating`, `analyzing`, `awaiting_review`, `ready_to_purge`, `purging`, `verifying`, `verified`, `verification_failed`, `error`, `cancelled`.
  - Composite batch status: `draft`, `processing`, `awaiting_review`, `completed_verified`, `completed_with_errors`, `cancelled`.
  - Strict rule: `completed_verified` requires ALL processed documents to be verified. Any error, cancellation, or verification failure results in `completed_with_errors`.
- **Concurrency & Resource Protection**:
  - Controlled concurrency via `asyncio.Semaphore` per batch, parameterized by `BATCH_MAX_CONCURRENT_DOCUMENTS` (default: 2 workers) to prevent CPU/RAM exhaustion during local OCR, OpenCV, spaCy, and LibreOffice operations.
  - Configurable limits via environment variables: `BATCH_MAX_DOCUMENTS` (10), `BATCH_MAX_FILE_SIZE_MB` (25MB), `BATCH_MAX_TOTAL_SIZE_MB` (100MB), documented in `.env.example`.
- **Strict Storage Isolation & Cleanup**:
  - Deterministic hierarchical path: `/tmp/anclora-purgedoc/{sessionId}/{batchId}/{documentId}/`.
  - Zero artifact sharing across documents or sessions.
  - Ephemeral cleanup hooks: per-document, per-batch, per-session, and TTL-based.
- **Human-in-the-Loop Review**:
  - Professional batch queue view (`BatchQueueScreen.js`) with multi-file drag & drop, per-document profile override, real-time match counters, and filterable table.
  - Seamless jump to the review canvas with `← Anterior` / `Siguiente →` navigation and return to queue.
  - Safe batch actions: analyze all, purge ready (pending matches == 0), cancel batch. Global blind approval is explicitly prevented.
- **Batch Forensic Audit & Secure ZIP Packaging**:
  - Consolidated `batch-audit.json` and `batch-audit.pdf` detailing original/purged SHA-256 hashes, counts, ruleset hashes, and failure records without ever leaking original plaintext PII.
  - Secure ZIP generation (`anclora-purgedoc-batch-{batchId}.zip`): includes ONLY `verified` documents inside `documents/`; excludes corrupt or failed documents; defeats Zip-Slip attacks via basename sanitization.

### 2.4 Real Physical Redaction & Fail-Closed Post-Purge Verification
- **PDF**: PyMuPDF stream obliteration (`add_redact_annot`, `apply_redactions`) with complete unreferenced object garbage collection (`garbage=4`, `clean=True`).
- **DOCX**: Unzips package and sanitizes all OOXML parts (`word/document.xml`, tables, headers, footers, comments, footnotes, `core.xml`, `app.xml`).
- **OCR Raster Destruction**: Underlying bitmap pixels of scanned documents are irreversibly obliterated in memory before re-encoding; Tesseract re-scans the output to guarantee zero optical recovery.
- **Adversarial Verification Suite**: `backend/tests/security/` validates multi-engine PDF recovery (PyMuPDF, pypdf, pdfminer.six), raw byte streams, raster pixel intensity, and Unicode NFKC normalization resistance.

---

## 3. Test & Verification Status
- **Backend Tests**: 48/48 tests passing in parallel (`pytest-xdist LoadScope`, ~52s execution).
  - `backend/tests/test_batch_pipeline.py` (6 comprehensive batch tests)
  - `backend/tests/test_custom_rules.py` (8 tests)
  - `backend/tests/security/` (7 security hardening and adversarial recovery suites)
  - `backend/tests/test_api_e2e.py`, `test_deskew_pipeline.py`, `test_ocr_pipeline.py`, `test_redaction_pipeline.py`
- **Frontend E2E**: 100% PASS verified via `testing_agent_v3` (Iteration 7 report `/app/test_reports/iteration_7.json`).
  - Toggle between Single Mode and Batch Mode.
  - Multi-upload (PDF + DOCX) with limit validation.
  - Per-document profile override, cancellation, and queue removal.
  - Concurrency-controlled batch analysis.
  - Sequential human review with navigation and match acceptance.
  - Safe batch purge with verified badges.
  - Fail-closed isolation ensuring corrupted documents trigger `completed_with_errors` and are excluded from the output ZIP.
  - Secure ZIP and Batch Audit PDF/JSON downloads.
  - Single-document flow regression verification.

---

## 4. Current Limitations & Technical Debt
1. **App.js & server.py file size**:
   - `server.py` and `App.js` have expanded to support batch orchestration. Future refactoring should modularize into FastAPI APIRouters (`routes/documents.py`, `routes/batch.py`, `routes/rules.py`, `routes/sessions.py`).
2. **Client-side Ruleset Scope**:
   - Custom rules remain stored in browser `localStorage`.
3. **Session Download Endpoints**:
   - Download endpoints are session-scoped and ephemeral; no permanent multi-user auth or role-based access control (by intentional MVP design).

---

## 5. Prioritized Backlog

### P0 (Next Immediate Feature — Pending User Confirmation):
- **Batch Deskew Preview**:
  - Visual side-by-side inspection of corrected angles across multiple pages prior to OCR in batch documents.

### P1 (Backlog):
- **Encrypted Profile Export/Import**:
  - Encrypted JSON/YAML rule packages with optional passphrase protection for secure enterprise sharing across air-gapped stations.
