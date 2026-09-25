# Anclora Purgedoc — Agent Project Context

AGENT_PROJECT_CONTEXT_VERSION=2.0
STATUS=ACTIVE

## Project identity

APPLICATION_NAME=Anclora Purgedoc
REPOSITORY=anclora-purgedoc
PROJECT_ROLE=Application (private, verified physical redaction of PDF/DOCX with cryptographic audit)
PRODUCT_FAMILY=Anclora Group

## Authority and bootstrap

This repository follows the workspace policy in `../ANCLORA_WORKSPACE_AGENT_POLICY.md`.
Resolve instructions in this order:

1. Current explicit instruction from Toni.
2. Anclora workspace policy (`../ANCLORA_WORKSPACE_AGENT_POLICY.md`), when present.
3. Repository instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`), when present.
4. This file.
5. `.anclora/PRODUCTION_RUNTIME.md`.
6. `.anclora/AOS_ADOPTION.md`.
7. Task-specific documentation and tests.

If an expected contract is missing, report `ANCLORA_CONTRACT_GAP`; do not invent its rules.
No coding-agent vendor is required for runtime, build, CI or development. Purgedoc was
originally generated on Emergent; Emergent is not a dependency of Purgedoc. Historical records
(`test_reports/`, `memory/` notes, Git history) are non-normative context, never authority.

## Canonical QA & Adaptive Execution Bootstrap

Workspace governance defines:
[`../../ANCLORA_WORKSPACE_AGENT_POLICY.md`](../../ANCLORA_WORKSPACE_AGENT_POLICY.md)

Defaults:
- `QA_MODE=AUTO`
- `CAVEMAN_MODE=AUTO`
- `TOKEN_ECONOMY_POLICY=ADAPTIVE`

QA classification determines verification depth:
- `FAST`: minimum sufficient targeted validation; full repository test suites prohibited by default; stops when sufficient evidence exists.
- `STANDARD`: focused functional verification; stops when sufficient evidence exists.
- `FULL`: comprehensive verification; batched at meaningful boundaries.

Caveman classification determines reasoning/exploration economy:
- Dynamically evaluated at task / phase / coherent cluster granularity.
- Deterministic, repetitive, low-ambiguity tasks -> `CAVEMAN=ON`.
- Architectural design, investigation, diagnosis, ambiguity, security, DB design -> `CAVEMAN=OFF`.
- Unexpected failure or ambiguity -> immediate switch `ON -> OFF` before diagnosis.

Task-level historical boilerplate does not override workspace classifications.
Only explicit mission tokens change modes:
- `QA_OVERRIDE=FAST|STANDARD|FULL`
- `CAVEMAN_OVERRIDE=ON|OFF`

Testing, lint, and build execution must follow the workspace batched execution cadence:
no repeated gates per micro-edit, and no rerun of unchanged successful gates without invalidation.
Repository-specific runtime minima are defined in [`PRODUCTION_RUNTIME.md`](PRODUCTION_RUNTIME.md).

## Sources of truth

| Domain | Primary source |
| --- | --- |
| Product behavior | `README.md`, `memory/PRD.md`, `docs/supported-document-scope.md` |
| Privacy and retention model | `docs/privacy-model.md`, `docs/redaction-guarantees.md` |
| Architecture | `docs/architecture.md` |
| HTTP/API surface (`/api`) | `backend/server.py`, `backend/models.py` |
| Detection (spaCy NER + regex) | `backend/services/detection.py`, `backend/services/normalization.py` |
| Rule profiles (YAML) | `backend/config/profiles/{rrhh,legal,soporte}.yaml` |
| Custom rules (RE2 / safe regex) | `backend/services/rules.py` |
| PDF redaction (PyMuPDF) | `backend/services/redaction.py`, `backend/services/documents.py` |
| DOCX / OOXML sanitization | `backend/services/redaction.py`, `backend/services/documents.py` |
| OCR (Tesseract `spa+eng`) | `backend/services/ocr.py` |
| Deskew (OpenCV) | `backend/services/deskew.py` |
| Fail-closed verification | `backend/services/verification.py` |
| Audit artifacts (JSON/PDF/CSV) | `backend/services/audit.py`, `backend/services/csv_audit.py` |
| Encryption (.aprules, AES-256-GCM + Argon2id) | `backend/services/encrypted_rules.py` |
| Sessions, lifecycle, TTL cleanup | `backend/services/sessions.py`, `backend/services/lifecycle.py` |
| Batch queue and SSE | `backend/services/batch.py`, `backend/services/event_bus.py` |
| Synthetic fixtures | `backend/fixtures_generator.py` (generated into `backend/fixtures/`, gitignored) |
| Frontend | `frontend/src/`, CRA/CRACO scripts in `frontend/package.json` |
| Tests | `backend/tests/`, `backend/tests/security/`, `backend/pytest.ini` |
| Runtime and environment | `.anclora/PRODUCTION_RUNTIME.md`, `backend/.env.example`, `frontend/.env.example` |
| CI and promotion | `.github/workflows/ci.yml`, `main-baseline.yml`, `promote.yml` |

## Git and delivery

WORKING_BRANCH=development
DEFAULT_BRANCH=development
FEATURE_BRANCHES=DISALLOWED
PROMOTION_FLOW=development->staging->production->main
AUTO_PROMOTE=false

- Work directly on `development`.
- Do NOT create `feat/*`, `fix/*`, `refactor/*` or any temporary branch unless Toni explicitly orders it.
- Never force-push to any branch.
- Never commit functional changes directly to `staging`, `production` or `main`.
- A normal task ends with, at most: validation → commit → `git push origin development` → STOP.
- Never promote without an explicit instruction from Toni. Promotion only happens through
  `.github/workflows/promote.yml` (manual, fast-forward only, requires green CI on the exact source SHA).

## Non-negotiable invariants

- Never print, log or commit secrets, tokens, `.env*` files or connection strings.
- Commit only `*.env.example` files, with names and safe placeholders.
- Never expose, commit or upload processed or user-supplied documents; tests use synthetic fixtures only.
- Preserve the privacy-first model: 100 % local processing, no remote LLM, OCR or cloud API.
  Do not introduce cloud dependencies that contradict it without Toni's authorization.
- No external analytics, telemetry or session recording, and no third-party scripts that could
  observe document content. Do not reintroduce vendor/platform SDKs (e.g. Emergent) into the app.
- Never weaken fail-closed verification: residual sensitive data must block certification.
- Audit artifacts never contain sensitive text in clear (SHA-256 hashes only).
- Never delete, skip or relax security tests (`backend/tests/security/`) to get a green build.
- Preserve existing `/api` routes and JSON contracts unless the task explicitly changes them.

## Known gaps (not resolved by the governance bootstrap)

- No frontend unit tests exist; the frontend CI gate is install + `--passWithNoTests` + build.
- Four `react-hooks/exhaustive-deps` warnings exist; CI builds with `CI=false` so the configured
  `warn` severity is honored instead of CRA promoting warnings to errors.
- Production deployment target, QA identity and visual QA harness are `NOT_DECLARED`.
