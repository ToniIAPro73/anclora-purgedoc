# PRD — Anclora Purgedoc MVP

## 1. Problem Statement
Design, implement, test, and deliver end-to-end the production MVP of **Anclora Purgedoc**, a sovereign document redaction, batch processing, retention management, cryptographic profile portability, and forensic verification application for PDF and DOCX documents with:
- 100% private, on-premise/local backend processing (zero remote LLMs, zero cloud APIs, zero external OCR).
- Local hybrid entity detection using spaCy (`es_core_news_sm`, `en_core_web_sm`) and configurable vertical YAML profiles (HR, Legal, Tech Support/DevOps).
- Real physical redaction of underlying file streams (never a cosmetic black overlay) across both PDF (PyMuPDF stream obliteration) and DOCX (OOXML package deep XML sanitization).
- Multi-angle Deskew Normalizer (OpenCV) and Local OCR Engine (Tesseract) for scanned and rotated documents.
- Custom Ruleset Editor with Regex Test Bench powered by safe `google-re2` against catastrophic backtracking (ReDoS).
- Sovereign **Batch Document Queue** with controlled concurrency (`BATCH_MAX_CONCURRENT_DOCUMENTS`), per-document independent lifecycle, and fail-closed batch integrity.
- **Batch Progress Streaming (Server-Sent Events / SSE)**: real-time streaming of batch and document progress phases (`validating`, `extracting`, `ocr_extraction`, `deskew_normalization`, `ner_detection`, `awaiting_review`, `purging`, `verifying`, `generating_audit`, `verified`) with monotonic sequence numbers, ring-buffer history for `Last-Event-ID` reconnection, and strict zero-PII streaming privacy.
- **Export Audit Batch CSV**: Tabular forensic reports (`batch-audit.csv` and `batch-audit-entities.csv`) adhering strictly to UTF-8 BOM, RFC 4180 standard, formula injection defense (`=`, `+`, `-`, `@`, `\t`, `\r`), and Zero-PII source pseudonymization (`document-XXX.ext`).
- **Audit Retention Policies & Ephemeral Lifecycle**: Inactivity-based session TTL (`SESSION_TTL_MINUTES=60`), lifecycle-dependent artifact expiration (`SOURCE_DOCUMENT_TTL_MINUTES=15`, `INTERMEDIATE_ARTIFACT_TTL_MINUTES=15` starting only when upstream operations finish), protection of human review (`awaiting_review`) and active operations (OCR, purge, download), fine-grained locks, startup orphan cleanup, and HTTP 410 Gone tombstone semantics for expired resources.
- **Encrypted Profile Export & Import (`.aprules`)**: Authenticated encryption (AES-256-GCM) with key derivation via Argon2id (64 MiB RAM, 3 iterations, 1 lane, CSPRNG 16-byte salt, 12-byte nonce), AAD metadata binding (format, version, cipher, KDF, salt, nonce, parameters), strict anti-DoS KDF parameter bounds, Zero-PII envelope (no plaintext regexes, names, or examples in outer JSON), transactional preview without premature commit, immutable built-in ruleset conflict protection, and conflict resolution strategies (Import as Copy, Replace existing custom, Skip).
- Automated post-purge fail-closed verification reopening and inspecting the generated file. If any approved sensitive string remains detectable in text, streams, or metadata, the output is blocked.
- Cryptographic forensic audit generation (individual & batch PDF certificates, structured JSON, and tabular CSVs) with SHA-256 hashes instead of plaintext PII, incorporating deterministic ruleset hashes.
- High-contrast accessible UI with dark default, light/system mode, ES/EN toggle, synchronized document canvas, live worker concurrency meters, and instant manual session/batch expunge buttons.

---

## 2. Architecture & Accomplished Features

### 2.1 Vertical Profiles & Hybrid Local Detection
- YAML rulesets in `backend/config/profiles/` (`rrhh.yaml`, `legal.yaml`, `soporte.yaml`).
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

### 2.6 Audit Retention Policies & Ephemeral Lifecycle
- Centralized `LifecycleManager` with fine-grained per-session, per-batch, and per-document `asyncio.Lock`.
- Active operations guard (`protect_operation` context manager) protecting in-flight work against concurrent cleanup.
- Lifecycle-dependent cleanup with inactivity TTL and HTTP 410 Gone tombstone semantics.

### 2.7 Encrypted Profile Export & Import (`.aprules`) — (Iteration 12 Certified)
- **Envelope Structure (`services/encrypted_rules.py`)**:
  ```json
  {
    "format": "anclora-purgedoc-ruleset",
    "format_version": 1,
    "crypto": {
      "cipher": "AES-256-GCM",
      "kdf": "Argon2id",
      "salt": "<base64_16_bytes>",
      "nonce": "<base64_12_bytes>",
      "memory_cost_kib": 65536,
      "time_cost": 3,
      "parallelism": 1
    },
    "ciphertext": "<base64_ciphertext_with_16_byte_auth_tag>"
  }
  ```
- **Cryptographic Specifications**:
  - Cipher: AES-256-GCM authenticated encryption (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
  - KDF: Argon2id (`cryptography.hazmat.primitives.kdf.argon2.Argon2id`).
  - AAD Binding: Deterministic canonical JSON containing format, version, cipher, KDF, salt, nonce, and KDF parameters. Any alteration of envelope metadata causes authentication tag failure.
- **Anti-DoS Parameter Limits**:
  - Memory cost: 8 MiB <= mem_kib <= 256 MiB.
  - Time cost: 1 <= time <= 10.
  - Parallelism: 1 <= parallelism <= 4.
  - Salt length: exactly 16 bytes. Nonce length: exactly 12 bytes.
  - Max ciphertext size: 5 MiB + 1024 bytes.
  - Any parameter out of bounds is rejected with `UNSUPPORTED_CRYPTO_PARAMETERS` prior to KDF execution.
- **Zero-PII Outer Envelope**:
  - Rule names, regex patterns, entity types, examples, and ruleset names are completely encrypted inside the ciphertext. Outer JSON is completely sanitized.
- **Transactional Preview & Conflict Resolution**:
  - `POST /api/rules/preview-encrypted` descifra en memoria y valida reglas con `google-re2`, verificando `canonical_hash` y reportando conflictos sin modificar las reglas del sistema.
  - Estrategias de resolución: Importar como copia (nuevo ID determinista), Reemplazar existentes (solo aplicable a reglas custom), Omitir.
  - Los perfiles de fábrica (`rrhh`, `legal`, `soporte`) son inmutables y rechazan colisiones con `BUILTIN_RULESET_CONFLICT`.

---

## 3. Test & Verification Status
- **Backend Tests**: 76/76 tests passing in parallel (`pytest-xdist LoadScope`, ~57s execution).
  - `backend/tests/test_encrypted_ruleset.py` (9 tests: round-trip hash, zero-PII leak check, unique salt/nonce, wrong password 401, tampered ciphertext 401, tampered AAD 401, anti-DoS limits, unicode password support, built-in ruleset conflict protection)
  - `backend/tests/test_encrypted_ruleset_http.py` (5 live HTTP integration tests)
  - `backend/tests/test_lifecycle_retention.py` (6 tests)
  - `backend/tests/test_batch_csv_audit.py` (3 tests)
  - `backend/tests/test_batch_streaming.py` (5 tests)
  - `backend/tests/test_batch_pipeline.py` (6 tests)
  - `backend/tests/test_custom_rules.py` (8 tests)
  - `backend/tests/security/` (7 security hardening and adversarial recovery suites)
  - `backend/tests/test_api_e2e.py`, `test_deskew_pipeline.py`, `test_ocr_pipeline.py`, `test_redaction_pipeline.py`
- **Frontend E2E**: 100% PASS verified via `testing_agent_v3` (Iteration 12 report `test_reports/iteration_12.json`). Historical record from the original Emergent environment; not a current testing instruction.
  - Open Custom Ruleset Editor cleanly with mounted RegexTestBench.
  - Create and save custom rule (`TEST_APRULE_FISCAL`).
  - Export encrypted `.aprules` file with password and verify zero plaintext leaks in downloaded JSON.
  - Import encrypted `.aprules`: wrong password properly rejected with error notification; correct password unlocks preview with canonical hash, counts, and conflict resolution options.
  - Commit import and verify restored rule functions in the active ruleset.

---

## 4. Current Limitations & Technical Debt
1. **App.js & server.py file size**:
   - `server.py` and `App.js` have expanded to support batch orchestration, CSV streaming, retention, and encryption endpoints. Future refactoring should modularize into FastAPI APIRouters (`routes/batch.py`, `routes/rules.py`, `routes/lifecycle.py`, `routes/documents.py`).
2. **Client-side Ruleset Scope**:
   - Custom rules remain stored in browser `localStorage`.
3. **Session Download Endpoints**:
   - Download endpoints are session-scoped and ephemeral; no permanent multi-user auth or role-based access control (by intentional MVP design).
4. **Physical Storage Secure Erase**:
   - Deletion removes filesystem references and unlinks files in `/tmp/anclora-purgedoc`; it does not perform physical SSD multi-pass overwrites or control previously downloaded client files.

---

## 5. Prioritized Backlog
- **Batch Deskew Preview**: Visual side-by-side inspection of corrected angles across multiple batch pages prior to OCR.
- **Granular Redaction Presets**: Quick toggleable presets for GDPR, HIPAA, and PCI-DSS compliance profiles.
