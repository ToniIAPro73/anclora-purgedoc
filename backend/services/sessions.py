import os
import shutil
import time
import logging
from typing import Dict, Any, Optional
from backend.models import DocumentMetadata, MatchItem

logger = logging.getLogger(__name__)

TEMP_ROOT = os.environ.get("TEMP_ROOT", "/tmp/anclora-purgedoc")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_MINUTES", "60")) * 60

class SessionStore:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.documents: Dict[str, DocumentMetadata] = {}
        self.matches: Dict[str, Dict[str, MatchItem]] = {} # doc_id -> {match_id: MatchItem}
        self.doc_file_paths: Dict[str, Dict[str, str]] = {} # doc_id -> {"source": path, "preview_pdf": path, "purged": path, "audit_pdf": path, "audit_json": path}
        os.makedirs(TEMP_ROOT, exist_ok=True)

    def create_session(self, session_id: str):
        session_dir = os.path.join(TEMP_ROOT, session_id)
        os.makedirs(session_dir, exist_ok=True)
        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_active": time.time(),
            "dir": session_dir
        }
        return session_dir

    def touch_session(self, session_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["last_active"] = time.time()

    def get_session_dir(self, session_id: str) -> str:
        if session_id not in self.sessions:
            return self.create_session(session_id)
        return self.sessions[session_id]["dir"]

    def cleanup_session(self, session_id: str):
        """Immediately and safely cleans up temporary disk artifacts for the session."""
        if session_id in self.sessions:
            session_dir = self.sessions[session_id]["dir"]
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)
            del self.sessions[session_id]

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
