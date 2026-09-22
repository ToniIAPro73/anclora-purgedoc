import hashlib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float

class MatchItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    entity_type: str
    source: List[str] = Field(default_factory=list)
    confidence: float
    original_text_hash: str
    text_preview: str  # Short contextual preview for UI review, e.g. "DNI: 12***78Z" or sanitized snippet
    raw_text: str      # Kept in memory only during active session for exact search & purge
    page: int
    bbox: Optional[BoundingBox] = None
    status: str = "pending"  # pending | accepted | rejected | applied | verification_failed
    rule_id: Optional[str] = None
    profile_id: str
    profile_version: str

    def to_public_dict(self) -> Dict[str, Any]:
        """Returns match data for API, hiding raw_text to protect secrets"""
        data = self.model_dump()
        data.pop("raw_text", None)
        return data

class DocumentMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    batch_id: Optional[str] = None
    filename: str
    mime_type: str
    size_bytes: int
    uploaded_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    profile_id: str
    source_sha256: str
    # Document independent status lifecycle:
    # queued | validating | analyzing | awaiting_review | ready_to_purge | purging | verifying | verified | verification_failed | error | cancelled
    status: str = "uploaded"
    page_count: int = 1
    has_text_layer: bool = True
    is_scanned_ocr: bool = False
    error_message: Optional[str] = None
    output_filename: Optional[str] = None
    output_sha256: Optional[str] = None
    verified_at: Optional[str] = None

class BatchMetadata(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    default_profile_id: str = "rrhh"
    # Batch status: draft | processing | awaiting_review | completed_verified | completed_with_errors | cancelled
    status: str = "draft"
    document_ids: List[str] = Field(default_factory=list)
    ruleset_id: Optional[str] = "custom_ruleset"
    ruleset_version: Optional[str] = "1.0.0"
    completed_at: Optional[str] = None

def hash_text(text: str) -> str:
    cleaned = text.strip()
    return f"sha256:{hashlib.sha256(cleaned.encode('utf-8')).hexdigest()}"

def calculate_file_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()
