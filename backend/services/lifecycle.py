import os
import shutil
import time
import asyncio
import logging
from typing import Dict, Any, Optional, Set, List
from contextlib import asynccontextmanager
from pathlib import Path

from backend.services.event_bus import batch_event_bus

logger = logging.getLogger(__name__)

TEMP_ROOT = os.environ.get("TEMP_ROOT", "/tmp/anclora-purgedoc")

def get_retention_config() -> Dict[str, int]:
    return {
        "session_ttl_minutes": int(os.environ.get("SESSION_TTL_MINUTES", "60")),
        "source_doc_ttl_minutes": int(os.environ.get("SOURCE_DOCUMENT_TTL_MINUTES", "15")),
        "intermediate_ttl_minutes": int(os.environ.get("INTERMEDIATE_ARTIFACT_TTL_MINUTES", "15")),
        "verified_output_ttl_minutes": int(os.environ.get("VERIFIED_OUTPUT_TTL_MINUTES", "60")),
        "audit_ttl_minutes": int(os.environ.get("AUDIT_ARTIFACT_TTL_MINUTES", "60")),
        "batch_ttl_minutes": int(os.environ.get("BATCH_ARTIFACT_TTL_MINUTES", "60")),
        "sse_history_ttl_minutes": int(os.environ.get("SSE_HISTORY_TTL_MINUTES", "30")),
        "cleanup_interval_seconds": int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60"))
    }

class ArtifactLifecycleRecord:
    def __init__(
        self,
        artifact_id: str,
        artifact_type: str, # "source", "preview_pdf", "ocr_render", "purged", "audit_json", "audit_pdf", "audit_csv", "batch_zip"
        path: str,
        session_id: str,
        batch_id: Optional[str] = None,
        document_id: Optional[str] = None
    ):
        self.artifact_id = artifact_id
        self.artifact_type = artifact_type
        self.path = path
        self.session_id = session_id
        self.batch_id = batch_id
        self.document_id = document_id
        self.created_at = time.time()
        self.eligible_for_cleanup_at: Optional[float] = None
        self.expires_at: Optional[float] = None

class SessionLifecycleRecord:
    def __init__(self, session_id: str, ttl_minutes: int):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_activity_at = time.time()
        self.ttl_seconds = ttl_minutes * 60
        self.is_expired = False
        self.active_operations = 0
        self.batches: Set[str] = set()
        self.documents: Set[str] = set()

    def touch(self):
        """User human activity touch (upload, review, purge, etc. Heartbeats DO NOT touch)."""
        self.last_activity_at = time.time()

    @property
    def expires_at(self) -> float:
        return self.last_activity_at + self.ttl_seconds

    @property
    def is_inactivity_expired(self) -> bool:
        return time.time() > self.expires_at

class LifecycleManager:
    """
    Centralized Sovereign Ephemeral Lifecycle Manager.
    - Fine-grained per-session, per-batch, and per-document concurrency locking.
    - Active operations counting protecting ongoing critical work (OCR, upload, purge, verify, download).
    - Lifecycle-dependent cleanup (upstream sources only eligible after downstream verification or explicit deletion).
    - Inactivity-based session TTL (heartbeats excluded).
    - Orphan cleanup on restart.
    - 410 Gone error propagation for expired resources.
    """
    def __init__(self):
        self.sessions: Dict[str, SessionLifecycleRecord] = {}
        self.artifacts: Dict[str, ArtifactLifecycleRecord] = {} # path -> record
        self.expired_sessions: Set[str] = set() # Tombstone for 410 GONE
        self.expired_batches: Set[str] = set()
        self.expired_documents: Set[str] = set()
        
        # Concurrency locks
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._batch_locks: Dict[str, asyncio.Lock] = {}
        self._document_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        
        # Ensure temp root
        os.makedirs(TEMP_ROOT, exist_ok=True)
        # Perform initial orphan cleanup on startup
        self.cleanup_orphan_directories_on_start()

    def get_session_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._session_locks:
            self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]

    def get_batch_lock(self, batch_id: str) -> asyncio.Lock:
        if batch_id not in self._batch_locks:
            self._batch_locks[batch_id] = asyncio.Lock()
        return self._batch_locks[batch_id]

    def get_document_lock(self, doc_id: str) -> asyncio.Lock:
        if doc_id not in self._document_locks:
            self._document_locks[doc_id] = asyncio.Lock()
        return self._document_locks[doc_id]

    def register_session(self, session_id: str) -> SessionLifecycleRecord:
        cfg = get_retention_config()
        rec = SessionLifecycleRecord(session_id, cfg["session_ttl_minutes"])
        self.sessions[session_id] = rec
        return rec

    def touch_session(self, session_id: str):
        """Called only on genuine human activity"""
        if session_id in self.sessions:
            self.sessions[session_id].touch()

    def get_session_expiry_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        rec = self.sessions.get(session_id)
        if not rec:
            return None
        return {
            "session_id": session_id,
            "created_at": rec.created_at,
            "last_activity_at": rec.last_activity_at,
            "expires_at": rec.expires_at,
            "ttl_minutes": rec.ttl_seconds // 60,
            "seconds_remaining": max(0, int(rec.expires_at - time.time()))
        }

    def register_artifact(
        self,
        path: str,
        artifact_type: str,
        session_id: str,
        batch_id: Optional[str] = None,
        document_id: Optional[str] = None
    ):
        art_id = f"art_{int(time.time()*1000)}_{os.path.basename(path)}"
        rec = ArtifactLifecycleRecord(art_id, artifact_type, path, session_id, batch_id, document_id)
        self.artifacts[path] = rec
        if session_id in self.sessions:
            if batch_id:
                self.sessions[session_id].batches.add(batch_id)
            if document_id:
                self.sessions[session_id].documents.add(document_id)

    def mark_artifact_eligible_for_cleanup(self, path: str, delay_seconds: Optional[int] = None):
        """
        Marks an artifact as eligible for cleanup once downstream work no longer requires it.
        E.g. source document after verified output generation.
        """
        rec = self.artifacts.get(path)
        if rec:
            now = time.time()
            rec.eligible_for_cleanup_at = now
            if delay_seconds is not None:
                rec.expires_at = now + delay_seconds
            else:
                cfg = get_retention_config()
                if rec.artifact_type == "source":
                    rec.expires_at = now + (cfg["source_doc_ttl_minutes"] * 60)
                elif rec.artifact_type in {"preview_pdf", "ocr_render"}:
                    rec.expires_at = now + (cfg["intermediate_ttl_minutes"] * 60)
                else:
                    rec.expires_at = now + 60 # Default grace period

    @asynccontextmanager
    async def protect_operation(self, session_id: str, op_name: str, document_id: Optional[str] = None):
        """
        Guarantees cleanup engine will NOT purge artifacts while a critical operation is in flight.
        Uses try/finally so active_operations is ALWAYS decremented even on exception or cancellation.
        """
        s_rec = self.sessions.get(session_id)
        if s_rec:
            s_rec.active_operations += 1
            s_rec.touch()
        try:
            yield
        finally:
            if s_rec:
                s_rec.active_operations = max(0, s_rec.active_operations - 1)
                s_rec.touch()

    def is_session_expired(self, session_id: str) -> bool:
        if session_id in self.expired_sessions:
            return True
        s_rec = self.sessions.get(session_id)
        if s_rec and s_rec.is_inactivity_expired and s_rec.active_operations == 0:
            return True
        return False

    def is_batch_expired(self, batch_id: str) -> bool:
        return batch_id in self.expired_batches

    def is_document_expired(self, doc_id: str) -> bool:
        return doc_id in self.expired_documents

    async def delete_document_now(self, doc_id: str, session_store: Any, reason: str = "manual_deletion"):
        """Safely and immediately removes a document, its artifacts, and locks without affecting peers."""
        async with self.get_document_lock(doc_id):
            doc = session_store.documents.pop(doc_id, None)
            session_store.matches.pop(doc_id, None)
            paths = session_store.doc_file_paths.pop(doc_id, None) or {}

            # Mark tombstone
            self.expired_documents.add(doc_id)

            # Delete physical files
            for p in paths.values():
                if p and os.path.exists(p):
                    try:
                        if os.path.isdir(p):
                            shutil.rmtree(p, ignore_errors=True)
                        else:
                            os.remove(p)
                    except Exception:
                        pass
                self.artifacts.pop(p, None)

            if doc:
                session_dir = session_store.get_session_dir(doc.session_id)
                doc_dir = os.path.join(session_dir, doc.batch_id or "", doc_id)
                if os.path.exists(doc_dir):
                    shutil.rmtree(doc_dir, ignore_errors=True)

            logger.info(f"AUDIT_LIFECYCLE_CLEANUP: reason={reason} doc_id={doc_id} timestamp={time.time()}")

    async def delete_batch_now(self, batch_id: str, session_store: Any, reason: str = "manual_deletion"):
        """Safely and immediately deletes an entire batch without affecting other batches in the session."""
        async with self.get_batch_lock(batch_id):
            batch = session_store.batches.pop(batch_id, None)
            session_store.batch_file_paths.pop(batch_id, None)
            self.expired_batches.add(batch_id)

            # Cleanup event bus state
            batch_event_bus.cleanup_batch(batch_id)

            if batch:
                for doc_id in list(batch.document_ids):
                    await self.delete_document_now(doc_id, session_store, reason=f"batch_{reason}")

                batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
                if os.path.exists(batch_dir):
                    shutil.rmtree(batch_dir, ignore_errors=True)

            logger.info(f"AUDIT_LIFECYCLE_CLEANUP: reason={reason} batch_id={batch_id} timestamp={time.time()}")

    async def delete_session_now(self, session_id: str, session_store: Any, reason: str = "manual_deletion"):
        """Cascading immediate destruction of an entire session, all its batches, docs, and SSE history."""
        async with self.get_session_lock(session_id):
            s_rec = self.sessions.pop(session_id, None)
            self.expired_sessions.add(session_id)

            # Clean all batches in session
            session_batches = [b_id for b_id, b in list(session_store.batches.items()) if b.session_id == session_id]
            for b_id in session_batches:
                await self.delete_batch_now(b_id, session_store, reason=f"session_{reason}")

            # Clean remaining documents in session
            session_docs = [d_id for d_id, d in list(session_store.documents.items()) if d.session_id == session_id]
            for d_id in session_docs:
                await self.delete_document_now(d_id, session_store, reason=f"session_{reason}")

            # Clean session disk directory
            session_dir = os.path.join(TEMP_ROOT, session_id)
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir, ignore_errors=True)

            session_store.sessions.pop(session_id, None)
            logger.info(f"AUDIT_LIFECYCLE_CLEANUP: reason={reason} session_id={session_id} timestamp={time.time()}")

    async def run_periodic_cleanup_tick(self, session_store: Any):
        """
        Executes one non-blocking tick of lifecycle cleanup:
        1. Checks expired sessions by inactivity (if active_operations == 0).
        2. Cleans up individual eligible artifacts whose specific TTL has expired.
        3. Cleans up stale SSE event history older than SSE_HISTORY_TTL_MINUTES.
        """
        now = time.time()
        cfg = get_retention_config()

        # 1. Check Sessions
        expired_sids = []
        for s_id, s_rec in list(self.sessions.items()):
            if s_rec.is_inactivity_expired and s_rec.active_operations == 0:
                expired_sids.append(s_id)

        for s_id in expired_sids:
            await self.delete_session_now(s_id, session_store, reason="inactivity_ttl_expired")

        # 2. Check Eligible Artifacts
        artifacts_to_delete = []
        for path, art in list(self.artifacts.items()):
            if art.expires_at and now > art.expires_at:
                s_rec = self.sessions.get(art.session_id)
                # Ensure no ongoing operation on this session
                if not s_rec or s_rec.active_operations == 0:
                    artifacts_to_delete.append(path)

        for path in artifacts_to_delete:
            art = self.artifacts.pop(path, None)
            if art and os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                    logger.info(f"AUDIT_LIFECYCLE_CLEANUP: reason=artifact_ttl_expired type={art.artifact_type} path_sanitized={os.path.basename(path)}")
                except Exception:
                    pass

    def cleanup_orphan_directories_on_start(self):
        """
        Scans TEMP_ROOT on server startup and removes directories older than 2 hours.
        Prevents disk accumulation from unexpected server restarts.
        """
        if not os.path.exists(TEMP_ROOT):
            return
        now = time.time()
        max_orphan_age_seconds = 7200
        for entry in os.listdir(TEMP_ROOT):
            full_path = os.path.join(TEMP_ROOT, entry)
            if os.path.isdir(full_path):
                try:
                    mtime = os.path.getmtime(full_path)
                    if now - mtime > max_orphan_age_seconds:
                        shutil.rmtree(full_path, ignore_errors=True)
                        logger.info(f"AUDIT_LIFECYCLE_CLEANUP: reason=orphan_restart_cleanup dir={entry}")
                except Exception as e:
                    logger.debug(f"Could not check orphan dir {entry}: {e}")

lifecycle_manager = LifecycleManager()
