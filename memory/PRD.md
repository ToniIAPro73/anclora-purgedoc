# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test, and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction, batch processing, retention management, and forensic verification application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLMs, zero cloud APIs, zero external OCR).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support/DevOps).
- Real physical redaction of underlying file streams (never a cosmetic black overlay) across both PDF (PyMuPDF stream obliteration) and DOCX (OOXML package deep XML sanitization).
- Multi-angle Deskew Normalizer (OpenCV) and Local OCR Engine (Tesseract) for scanned and rotated documents.
- Custom Ruleset Editor with Regex Test Bench powered by safe `google-re2` against catastrophic backtracking (ReDoS).
- Sovereign **Batch Document Queue** with controlled concurrency (`BATCH_MAX_CONCURRENT_DOCUMENTS`), per-document independent lifecycle, and fail-closed batch integrity.
- **Batch Progress Streaming (Server-Sent Events / SSE)**: real-time streaming of batch and document progress phases (`validating`, `extracting`, `ocr_extraction`, `deskew_normalization`, `ner_detection`, `awaiting_review`, `purging`, `verifying`, `generating_audit`, `verified`) with monotonic sequence numbers, ring-buffer history for `Last-Event-ID` reconnection, and strict zero-PII streaming privacy.
- **Export Audit Batch CSV**: Tabular forensic reports (`batch-audit.csv` and `batch-audit-entities.csv`) adhering strictly to UTF-8 BOM, RFC 4180 standard, formula injection defense (`=`, `+`, `-`, `@`, `\t`, `\r`), and Zero-PII source pseudonymization (`document-XXX.ext`).
- **Audit Retention Policies & Ephemeral Lifecycle**: Inactivity-based session TTL (`SESSION_TTL_MINUTES=60`), lifecycle-dependent artifact expiration (`SOURCE_DOCUMENT_TTL_MINUTES=15`, `INTERMEDIATE_ARTIFACT_TTL_MINUTES=15` starting only when upstream operations finish), protection of human review (`awaiting_review`) and active operations (OCR, purge, download), fine-grained locks, startup orphan cleanup, and HTTP 410 Gone tombstone semantics for expired resources.
- Automated post-purge fail-closed verification reopening and inspecting the generated file. If any approved sensitive string remains detectable in text, streams, or metadata, the output is blocked.
- Cryptographic forensic audit generation (individual & batch PDF certificates, structured JSON, and tabular CSVs) with SHA-256 hashes instead of plaintext PII, incorporating deterministic ruleset hashes.
- High-contrast accessible UI with dark default, light/system mode, ES/EN toggle, synchronized document canvas, live worker concurrency meters, and instant manual session/batch expunge buttons.

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

### 2.3 Batch Document Queue & Batch Audit Summary
- Reuses the sovereign single-document pipeline (`upload -> analyze -> review -> purge -> verify -> audit`) as the single source of truth; zero code duplication.
- Independent per-document status lifecycle: `queued`, `validating`, `analyzing`, `awaiting_review`, `ready_to_purge`, `purging`, `verifying`, `verified`, `verification_failed`, `error`, `cancelled`.
- Composite batch status: `draft`, `processing`, `awaiting_review`, `completed_verified`, `completed_with_errors`, `cancelled`.
- Controlled concurrency via `asyncio.Semaphore` per batch, parameterized by `BATCH_MAX_CONCURRENT_DOCUMENTS` (default: 2 workers).
- Configurable limits via environment variables: `BATCH_MAX_DOCUMENTS` (10), `BATCH_MAX_FILE_SIZE_MB` (25MB), `BATCH_MAX_TOTAL_SIZE_MB` (100MB).
- Strict isolation in `/tmp/anclora-purgedoc/{sessionId}/{batchId}/{documentId}/`.
- Secure ZIP generation (`anclora-purgedoc-batch-{batchId}.zip`): includes ONLY `verified` documents inside `documents/`; excludes corrupt or failed documents; defeats Zip-Slip attacks via basename sanitization.

### 2.4 Batch Progress Streaming (SSE)
- Decoupled `InMemoryBatchEventBus` with ring-buffer history (`max_history_per_batch=500`), monotonic sequence numbers, and `Last-Event-ID` replay.
- Bounded subscriber queues (`maxsize=100`) preventing memory bloat.
- Periodic keep-alive heartbeats and Zero-PII event sanitization.

### 2.5 Export Audit Batch CSV
- Canonical derivation from `BatchService.generate_batch_audit_summary()`.
- Dual CSV export: `batch-audit.csv` (summary) and `batch-audit-entities.csv` (per-entity details).
- CSV & Formula Injection neutralization (`sanitize_csv_cell()` prepending `'` on trigger characters).
- Source pseudonymization (`document-001.pdf`) ensuring zero PII leak in metadata.

### 2.6 Audit Retention Policies & Ephemeral Lifecycle (Iteration 10 Certified)
- **Centralized Lifecycle Manager (`services/lifecycle.py`)**:
  - Fine-grained per-session, per-batch, and per-document `asyncio.Lock` to guarantee non-blocking concurrency.
  - Active operations guard (`protect_operation` context manager with `try/finally`) protecting in-flight operations (OCR, purge, verification, download) against concurrent cleanup.
  - Lifecycle-dependent cleanup: source documents remain protected while in `awaiting_review` or actively needed; cleanup eligibility starts only post-verification.
  - Inactivity-based session TTL (60 min default): genuine human actions update `last_activity_at`; technical SSE heartbeats explicitly excluded.
  - Manual instant expunge: `DELETE /api/sessions/{id}` (cascading cleanup of batches, docs, filesystem, memory, and SSE buses) and `DELETE /api/batches/{id}` (isolated batch removal leaving peer batches untouched).
  - Tombstone tracking returning standard `HTTP 410 Gone` with `{ "code": "RESOURCE_EXPIRED", "detail": "RESOURCE_EXPIRED" }`.
  - Startup orphan directory cleanup for paths > 2 hours old.

---

## 3. Test & Verification Status
- **Backend Tests**: 62/62 tests passing in parallel (`pytest-xdist LoadScope`, ~51s execution).
  - `backend/tests/test_lifecycle_retention.py` (6 tests: retention defaults, review protection, active operations lock, batch isolation, cascading session deletion, HTTP 410 response)
  - `backend/tests/test_batch_csv_audit.py` (3 tests)
  - `backend/tests/test_batch_streaming.py` (5 tests)
  - `backend/tests/test_batch_pipeline.py` (6 tests)
  - `backend/tests/test_custom_rules.py` (8 tests)
  - `backend/tests/security/` (7 security hardening and adversarial recovery suites)
  - `backend/tests/test_api_e2e.py`, `test_deskew_pipeline.py`, `test_ocr_pipeline.py`, `test_redaction_pipeline.py`
- **Frontend E2E**: 100% PASS verified via `testing_agent_v3` (Iteration 10 report `/app/test_reports/iteration_10.json`).
  - Session TTL indicator and Delete Session Now button in Header.
  - Delete Batch Now button in Batch Queue view.
  - Cascading deletion of disk artifacts, memory records, and SSE subscribers.
  - Live HTTP verification of `HTTP 410 Gone` for expired/deleted sessions.

---

## 4. Current Limitations & Technical Debt
1. **App.js & server.py file size**:
   - `server.py` and `App.js` have expanded to support batch orchestration, CSV streaming, and retention endpoints. Future refactoring should modularize into FastAPI APIRouters (`routes/batch.py`, `routes/documents.py`, `routes/rules.py`, `routes/sessions.py`).
2. **Client-side Ruleset Scope**:
   - Custom rules remain stored in browser `localStorage`.
3. **Session Download Endpoints**:
   - Download endpoints are session-scoped and ephemeral; no permanent multi-user auth or role-based access control (by intentional MVP design).
4. **Physical Storage Secure Erase**:
   - Deletion removes filesystem references and unlinks files in `/tmp/anclora-purgedoc`; it does not perform physical SSD multi-pass overwrites or control previously downloaded client files.

---

## 5. Prioritized Backlog
- **Batch Deskew Preview**: Visual side-by-side inspection of corrected angles across multiple batch pages prior to OCR.
- **Encrypted Profile Export/Import**: Encrypted JSON/YAML rule packages with optional passphrase protection for secure enterprise sharing across air-gapped stations.
- **Granular Redaction Presets**: Quick toggleable presets for GDPR, HIPAA, and PCI-DSS compliance profiles.
