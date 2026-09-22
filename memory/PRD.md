# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test, and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction, batch processing, and forensic verification application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLMs, zero cloud APIs, zero external OCR).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support/DevOps).
- Real physical redaction of underlying file streams (never a cosmetic black overlay) across both PDF (PyMuPDF stream obliteration) and DOCX (OOXML package deep XML sanitization).
- Multi-angle Deskew Normalizer (OpenCV) and Local OCR Engine (Tesseract) for scanned and rotated documents.
- Custom Ruleset Editor with Regex Test Bench powered by safe `google-re2` against catastrophic backtracking (ReDoS).
- Sovereign **Batch Document Queue** with controlled concurrency (`BATCH_MAX_CONCURRENT_DOCUMENTS`), per-document independent lifecycle, and fail-closed batch integrity.
- **Batch Progress Streaming (Server-Sent Events / SSE)**: real-time streaming of batch and document progress phases (`validating`, `extracting`, `ocr_extraction`, `deskew_normalization`, `ner_detection`, `awaiting_review`, `purging`, `verifying`, `generating_audit`, `verified`) with monotonic sequence numbers, ring-buffer history for `Last-Event-ID` reconnection, and strict zero-PII streaming privacy.
- Automated post-purge fail-closed verification reopening and inspecting the generated file. If any approved sensitive string remains detectable in text, streams, or metadata, the output is blocked.
- Cryptographic forensic audit generation (individual & batch PDF certificates & structured JSON) with SHA-256 hashes instead of plaintext PII, incorporating deterministic ruleset hashes.
- High-contrast accessible UI with dark default, light/system mode, ES/EN toggle, synchronized document canvas, live worker concurrency meters, and seamless single/batch mode switching.

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
- Consolidated `batch-audit.json` and `batch-audit.pdf` detailing original/purged SHA-256 hashes and failure records without ever leaking original plaintext PII.
- Secure ZIP generation (`anclora-purgedoc-batch-{batchId}.zip`): includes ONLY `verified` documents inside `documents/`; excludes corrupt or failed documents; defeats Zip-Slip attacks via basename sanitization.

### 2.4 Batch Progress Streaming (SSE) — (Iteration 8 Certified)
- **Decoupled Architecture (`services/event_bus.py`)**:
  - `BaseEventBus` abstract interface implemented by `InMemoryBatchEventBus` (designed for pluggable future backend migration, e.g. Redis).
  - Ring buffer history per batch (`max_history_per_batch=500`) with monotonic sequence numbers.
  - Per-subscriber bounded queue (`maxsize=100`) with oldest-drop policy to protect server memory against slow or stalled consumers.
- **Streaming Endpoint (`GET /api/batches/{batchId}/events`)**:
  - SSE standard `text/event-stream` with `id: <sequence>`, `event: <type>`, `data: <json>`.
  - Replays missed events on client reconnect using `Last-Event-ID` or `?last_event_id=...`.
  - Periodical keep-alive heartbeat (`: heartbeat ...\n\n`) every 15s to prevent proxy/CDN connection drops.
  - Validates session and batch ownership for cross-session/cross-batch isolation.
- **Contract & Typed Events**:
  - `stream_connected`, `batch_started`, `batch_status_changed`, `document_queued`, `document_status_changed`, `document_awaiting_review`, `document_verified`, `document_verification_failed`, `document_error`, `document_cancelled`, `batch_completed`.
  - Real operational phases: `validating`, `extracting`, `ocr_extraction`, `deskew_normalization`, `ner_detection`, `awaiting_review`, `purging`, `verifying`, `generating_audit`, `verified`.
- **Zero-PII Streaming Enforcement**:
  - Bus-level defensive sanitization: strips any keys matching `{raw_text, extracted_text, ocr_text, text, sensitive_text}`.
  - Verified by automated adversarial test (`test_event_bus_strict_zero_pii_in_payloads`): asserts no sensitive fixture tokens appear in any serialized SSE event.
- **Frontend Resilient Integration (`BatchQueueScreen.js`)**:
  - Live SSE connection indicator (`Stream SSE conectado en vivo`).
  - Real backend active workers badge (`Workers: X / Y máx`).
  - Sequence deduplication (`lastSequenceRef`) to prevent redundant renders.
  - Automatic reconnect with fallback snapshot polling (3.5s) if connection is interrupted.

---

## 3. Test & Verification Status
- **Backend Tests**: 53/53 tests passing in parallel (`pytest-xdist LoadScope`, ~51s execution).
  - `backend/tests/test_batch_streaming.py` (5 comprehensive SSE streaming tests)
  - `backend/tests/test_batch_pipeline.py` (6 batch queue & isolation tests)
  - `backend/tests/test_custom_rules.py` (8 custom rules tests)
  - `backend/tests/security/` (7 security hardening and adversarial recovery suites)
  - `backend/tests/test_api_e2e.py`, `test_deskew_pipeline.py`, `test_ocr_pipeline.py`, `test_redaction_pipeline.py`
- **Frontend E2E**: 100% PASS verified via `testing_agent_v3` (Iteration 8 report `/app/test_reports/iteration_8.json`).
  - Live SSE status badge and active workers concurrency badge.
  - Multi-upload with real-time status and detailed phase streaming.
  - Human review navigation, batch purge, and verified outputs.
  - ZIP and Batch Audit downloads.
  - Single-document and security hardening non-regression.

---

## 4. Current Limitations & Technical Debt
1. **App.js & server.py file size**:
   - `server.py` and `App.js` have grown as batch features expanded. Future refactoring should modularize into FastAPI APIRouters (`routes/batch.py`, `routes/documents.py`, `routes/rules.py`, `routes/sessions.py`).
2. **Client-side Ruleset Scope**:
   - Custom rules remain stored in browser `localStorage`.
3. **Session Download Endpoints**:
   - Download endpoints are session-scoped and ephemeral; no permanent multi-user auth or role-based access control (by intentional MVP design).

---

## 5. Prioritized Backlog
- **Batch Deskew Preview**: Visual side-by-side inspection of corrected angles across multiple batch pages prior to OCR.
- **Encrypted Profile Export/Import**: Encrypted JSON/YAML rule packages with optional passphrase protection for secure enterprise sharing across air-gapped stations.
- **Granular Redaction Presets**: Quick toggleable presets for GDPR, HIPAA, and PCI-DSS compliance profiles.
