# PurgeDoc production database

Provider: Neon PostgreSQL. Alembic revision `0001_metadata_only_schema` owns
the schema. This is a metadata/audit/lifecycle mirror only: active document
bytes, OCR, extracted text, previews, output files, filenames, paths,
passphrases and raw PII remain in memory or ephemeral local storage.

| Table | Purpose | Allowed content |
|---|---|---|
| `sessions` | Session lifecycle | IDs, statuses, timestamps |
| `batches` | Batch lifecycle | IDs, profile/ruleset IDs, counts |
| `documents` | Document lifecycle | IDs, MIME/size, SHA-256, statuses |
| `audit_records` | Verification summary | IDs, counts, hashes, safe metadata |
| `audit_items` | Redaction audit | type, page, status, hash, bbox |
| `lifecycle_tombstones` | Deletion evidence | ID, reason, timestamps |
| `alembic_version` | Migration state | none |

There is no users/auth table. Runtime processing remains single-instance and
ephemeral. Destructive migrations are forbidden and QA uses synthetic fixtures.
