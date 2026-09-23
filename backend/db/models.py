from datetime import datetime
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class BatchRow(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    default_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_id: Mapped[Optional[str]] = mapped_column(String(128))
    ruleset_version: Mapped[Optional[str]] = mapped_column(String(64))
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class DocumentRow(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(80), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_scanned_ocr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    output_sha256: Mapped[Optional[str]] = mapped_column(String(80))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[Optional[str]] = mapped_column(String(80))

class AuditRecordRow(Base):
    __tablename__ = "audit_records"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(80), nullable=False)
    output_sha256: Mapped[Optional[str]] = mapped_column(String(80))
    match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

class AuditItemRow(Base):
    __tablename__ = "audit_items"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audit_records.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    match_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    bbox: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

class LifecycleTombstoneRow(Base):
    __tablename__ = "lifecycle_tombstones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("resource_type", "resource_id", name="uq_lifecycle_resource"),)
