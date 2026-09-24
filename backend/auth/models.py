import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship

AuthBase = declarative_base()


class UserRow(AuthBase):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active", server_default="active")  # active | disabled
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    whitelist_entry = relationship("AuthWhitelistRow", back_populates="user", uselist=False)
    owned_sessions = relationship("SessionOwnerRow", back_populates="user", cascade="all, delete-orphan")


class AuthWhitelistRow(AuthBase):
    __tablename__ = "auth_whitelist"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending | active | revoked
    token_hash = Column(String(64), unique=True, nullable=True)  # SHA-256 hex
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("UserRow", back_populates="whitelist_entry")


class AuthAuditEventRow(AuthBase):
    __tablename__ = "auth_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class SessionOwnerRow(AuthBase):
    __tablename__ = "session_owners"

    session_id = Column(String(128), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("UserRow", back_populates="owned_sessions")
