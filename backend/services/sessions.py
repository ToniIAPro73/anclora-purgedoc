import os
import shutil
import time
import logging
from typing import Dict, Any, Optional, List
from backend.models import DocumentMetadata, MatchItem, BatchMetadata

from backend.services.event_bus import batch_event_bus
logger = logging.getLogger(__name__)

TEMP_ROOT = os.environ.get("TEMP_ROOT", "/tmp/anclora-purgedoc")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_MINUTES", "60")) * 60

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.batches: Dict[str, BatchMetadata] = {} # batch_id -> BatchMetadata
        self.documents: Dict[str, DocumentMetadata] = {} # doc_id -> DocumentMetadata
        self.matches: Dict[str, Dict[str, MatchItem]] = {} # doc_id -> {match_id: MatchItem}
        self.doc_file_paths: Dict[str, Dict[str, str]] = {} # doc_id -> paths
        self.batch_file_paths: Dict[str, Dict[str, str]] = {} # batch_id -> paths
        os.makedirs(TEMP_ROOT, exist_ok=True)

    def create_session(self, session_id: str, user_id: Optional[str] = None):
        session_dir = os.path.join(TEMP_ROOT, session_id)
        os.makedirs(session_dir, exist_ok=True)
        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_active": time.time(),
            "dir": session_dir,
            "user_id": user_id
        }
        return session_dir

    def touch_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["last_active"] = time.time()

    def get_session_dir(self, session_id: str) -> str:
        if session_id not in self.sessions:
            raise KeyError(f"Session {session_id} not found or expired")
        return self.sessions[session_id]["dir"]

    def get_document_dir(self, session_id: str, batch_id: Optional[str], doc_id: str) -> str:
        """
        Guarantees strict hierarchical isolation:
        If batch_id provided: /tmp/anclora-purgedoc/{session_id}/{batch_id}/{doc_id}/
        Otherwise: /tmp/anclora-purgedoc/{session_id}/{doc_id}/
        """
        session_dir = self.get_session_dir(session_id)
        if batch_id:
            doc_dir = os.path.join(session_dir, batch_id, doc_id)
        else:
            doc_dir = os.path.join(session_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        return doc_dir

    def get_batch_dir(self, session_id: str, batch_id: str) -> str:
        session_dir = self.get_session_dir(session_id)
        batch_dir = os.path.join(session_dir, batch_id)
        os.makedirs(batch_dir, exist_ok=True)
        return batch_dir

    def cleanup_document(self, doc_id: str):
        """Immediately cleans up temporary disk artifacts and memory state for a single document."""
        doc = self.documents.pop(doc_id, None)
        self.matches.pop(doc_id, None)
        paths = self.doc_file_paths.pop(doc_id, None)

        if doc:
            session_id = doc.session_id
            batch_id = doc.batch_id
            session_dir = self.sessions.get(session_id, {}).get("dir", os.path.join(TEMP_ROOT, session_id))
            if batch_id:
                doc_dir = os.path.join(session_dir, batch_id, doc_id)
            else:
                doc_dir = os.path.join(session_dir, doc_id)

            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir, ignore_errors=True)

        logger.info(f"Cleaned up document {doc_id}")

    def cleanup_batch(self, batch_id: str):
        """Immediately and safely cleans up temporary disk artifacts for an entire batch."""
        batch_event_bus.cleanup_batch(batch_id)
        batch = self.batches.pop(batch_id, None)
        self.batch_file_paths.pop(batch_id, None)

        if batch:
            session_id = batch.session_id
            session_dir = self.sessions.get(session_id, {}).get("dir", os.path.join(TEMP_ROOT, session_id))
            batch_dir = os.path.join(session_dir, batch_id)
            if os.path.exists(batch_dir):
                shutil.rmtree(batch_dir, ignore_errors=True)

            for doc_id in batch.document_ids:
                self.documents.pop(doc_id, None)
                self.matches.pop(doc_id, None)
                self.doc_file_paths.pop(doc_id, None)

        logger.info(f"Cleaned up batch {batch_id}")

    def cleanup_session(self, session_id: str):
        """Immediately and safely cleans up temporary disk artifacts for the session."""
        if session_id in self.sessions:
            session_dir = self.sessions[session_id]["dir"]
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)
            del self.sessions[session_id]

        # Clean batches belonging to session
        batches_to_del = [b_id for b_id, b in self.batches.items() if b.session_id == session_id]
        for b_id in batches_to_del:
            self.batches.pop(b_id, None)
            self.batch_file_paths.pop(b_id, None)
            batch_event_bus.cleanup_batch(b_id)
        # Clean docs belonging to session
        docs_to_del = [doc_id for doc_id, doc in self.documents.items() if doc.session_id == session_id]
        for doc_id in docs_to_del:
            self.documents.pop(doc_id, None)
            self.matches.pop(doc_id, None)
            self.doc_file_paths.pop(doc_id, None)
        logger.info(f"Cleaned up session {session_id}")

    def cleanup_expired(self):
        """Deletes sessions older than TTL"""
        now = time.time()
        expired = [s_id for s_id, s in self.sessions.items() if now - s.get("last_active", 0) > SESSION_TTL_SECONDS]
        for s_id in expired:
            self.cleanup_session(s_id)

session_store = SessionStore()
