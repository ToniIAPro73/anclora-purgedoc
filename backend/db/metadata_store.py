import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from .models import AuditItemRow, AuditRecordRow, BatchRow, DocumentRow, LifecycleTombstoneRow, SessionRow

logger = logging.getLogger(__name__)

class MetadataStore:
    """Metadata mirror. Raw content, filenames, paths and secrets never cross this boundary."""
    def __init__(self):
        url = os.environ.get("DATABASE_URL")
        if url and url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.enabled = bool(url)
        self.engine = create_engine(url, pool_pre_ping=True) if url else None
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False) if self.engine else None

    def startup_recover(self) -> None:
        if not self.enabled:
            return
        with self.Session() as db:
            db.execute(update(SessionRow).where(SessionRow.status.in_(["active", "processing"])).values(status="interrupted"))
            db.commit()

    def _commit(self, operation):
        if not self.enabled:
            return
        with self.Session() as db:
            operation(db)
            db.commit()

    def session_started(self, session_id: str, created_at: datetime) -> None:
        self._commit(lambda db: db.merge(SessionRow(id=session_id, status="active", created_at=created_at, last_activity_at=created_at)))

    def batch_created(self, batch: Any) -> None:
        self._commit(lambda db: db.merge(BatchRow(id=batch.id, session_id=batch.session_id, status=batch.status,
            default_profile_id=batch.default_profile_id, ruleset_id=batch.ruleset_id, ruleset_version=batch.ruleset_version,
            document_count=0, created_at=datetime.fromisoformat(batch.created_at))))

    def document_created(self, doc: Any) -> None:
        self._commit(lambda db: db.merge(DocumentRow(id=doc.id, session_id=doc.session_id, batch_id=doc.batch_id,
            status=doc.status, mime_type=doc.mime_type, size_bytes=doc.size_bytes, source_sha256=doc.source_sha256,
            profile_id=doc.profile_id, page_count=doc.page_count, has_text_layer=doc.has_text_layer,
            is_scanned_ocr=doc.is_scanned_ocr, uploaded_at=datetime.fromisoformat(doc.uploaded_at))))

    def document_updated(self, doc: Any, error_code: Optional[str] = None) -> None:
        def operation(db):
            db.execute(update(DocumentRow).where(DocumentRow.id == doc.id).values(
                status=doc.status, page_count=doc.page_count, has_text_layer=doc.has_text_layer,
                is_scanned_ocr=doc.is_scanned_ocr, output_sha256=doc.output_sha256,
                verified_at=datetime.fromisoformat(doc.verified_at) if doc.verified_at else None, error_code=error_code))
        self._commit(operation)

    def batch_updated(self, batch: Any) -> None:
        def operation(db):
            db.execute(update(BatchRow).where(BatchRow.id == batch.id).values(
                status=batch.status, document_count=len(batch.document_ids),
                completed_at=datetime.fromisoformat(batch.completed_at) if batch.completed_at else None))
        self._commit(operation)

    def audit_completed(self, doc: Any, audit: dict[str, Any], matches: list[Any]) -> None:
        def operation(db):
            record = AuditRecordRow(id=audit["audit_id"], document_id=doc.id, batch_id=doc.batch_id, status=doc.status,
                source_sha256=doc.source_sha256, output_sha256=doc.output_sha256, match_count=len(matches),
                applied_count=sum(m.status == "applied" for m in matches), verification_passed=doc.status == "verified",
                completed_at=datetime.now(timezone.utc), safe_metadata={"profile_id": doc.profile_id, "mime_type": doc.mime_type})
            db.merge(record)
            for match in matches:
                db.merge(AuditItemRow(id=match.id, audit_id=record.id, entity_type=match.entity_type, page=match.page,
                    status=match.status, match_hash=match.original_text_hash, bbox=match.bbox.model_dump() if match.bbox else None))
        self._commit(operation)

    def tombstone(self, resource_type: str, resource_id: str, reason: str) -> None:
        self._commit(lambda db: db.merge(LifecycleTombstoneRow(resource_type=resource_type, resource_id=resource_id,
            reason=reason, created_at=datetime.now(timezone.utc))))

metadata_store = MetadataStore()
