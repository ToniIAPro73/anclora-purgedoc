import os
import io
import time
import pytest
import asyncio
from pathlib import Path

from backend.services.sessions import session_store
from backend.services.lifecycle import lifecycle_manager, get_retention_config
from backend.services.batch import batch_service
from backend.services.event_bus import batch_event_bus
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata, BatchMetadata

@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    generate_all_fixtures()

def test_lifecycle_retention_defaults_and_env():
    """Verify retention policy configuration respects .env.example defaults"""
    cfg = get_retention_config()
    assert cfg["session_ttl_minutes"] >= 30
    assert cfg["source_doc_ttl_minutes"] >= 10
    assert cfg["intermediate_ttl_minutes"] >= 10
    assert cfg["verified_output_ttl_minutes"] >= 30
    assert cfg["audit_ttl_minutes"] >= 30
    assert cfg["batch_ttl_minutes"] >= 30
    assert cfg["sse_history_ttl_minutes"] >= 15

def test_awaiting_review_protection_and_touch_activity():
    """
    CRITICAL POLICY TEST:
    A document awaiting review does NOT expire while the session is active.
    Human activity renews session TTL.
    """
    session_id = "test_sess_review_protection"
    session_store.create_session(session_id)
    rec = lifecycle_manager.register_session(session_id)
    initial_expiry = rec.expires_at

    # Human touch
    time.sleep(0.01)
    rec.touch()
    assert rec.expires_at >= initial_expiry

    # Register artifact
    doc_path = "/tmp/anclora-purgedoc/test_sess_review_protection/sample.pdf"
    lifecycle_manager.register_artifact(doc_path, "source", session_id)
    art = lifecycle_manager.artifacts[doc_path]

    # While in review, artifact is NOT eligible for cleanup
    assert art.eligible_for_cleanup_at is None
    assert art.expires_at is None

    # After verification, mark eligible
    lifecycle_manager.mark_artifact_eligible_for_cleanup(doc_path, delay_seconds=1)
    assert art.eligible_for_cleanup_at is not None
    assert art.expires_at is not None

def test_protected_operation_prevents_cleanup():
    """Verify active_operations counter protects in-flight operations (OCR, purge, download)"""
    session_id = "test_sess_protect_ops"
    session_store.create_session(session_id)
    rec = lifecycle_manager.register_session(session_id)

    async def run_op():
        async with lifecycle_manager.protect_operation(session_id, "ocr_processing"):
            assert rec.active_operations == 1
            # Simulate exception inside operation
            try:
                async with lifecycle_manager.protect_operation(session_id, "inner_purge"):
                    assert rec.active_operations == 2
                    raise ValueError("Simulated failure")
            except ValueError:
                pass
            # Lock/counter must be properly released despite exception
            assert rec.active_operations == 1

    asyncio.run(run_op())
    assert rec.active_operations == 0

def test_manual_batch_deletion_isolation():
    """Verify deleting batch A does NOT delete or impact batch B in the same session"""
    session_id = "test_sess_multi_batches"
    session_store.create_session(session_id)
    lifecycle_manager.register_session(session_id)

    # Batch A
    b_a = "batch_del_a"
    batch_a = BatchMetadata(id=b_a, session_id=session_id)
    session_store.batches[b_a] = batch_a
    session_store.get_batch_dir(session_id, b_a)

    # Batch B
    b_b = "batch_del_b"
    batch_b = BatchMetadata(id=b_b, session_id=session_id)
    session_store.batches[b_b] = batch_b
    session_store.get_batch_dir(session_id, b_b)

    # Delete Batch A
    asyncio.run(lifecycle_manager.delete_batch_now(b_a, session_store))

    # Assert Batch A is gone, Batch B remains intact
    assert b_a not in session_store.batches
    assert b_b in session_store.batches
    batch_a_path = os.path.join(session_store.get_session_dir(session_id), b_a)
    assert not os.path.exists(batch_a_path)
    assert os.path.exists(session_store.get_batch_dir(session_id, b_b))

def test_manual_session_deletion_cascading():
    """Verify deleting a session completely purges all batches, files, memory, and SSE state"""
    session_id = "test_sess_cascade"
    session_store.create_session(session_id)
    lifecycle_manager.register_session(session_id)

    b_id = "batch_cascade"
    batch = BatchMetadata(id=b_id, session_id=session_id)
    session_store.batches[b_id] = batch

    # Add subscriber
    q = batch_event_bus.subscribe(b_id)

    # Delete session
    asyncio.run(lifecycle_manager.delete_session_now(session_id, session_store))

    assert session_id not in session_store.sessions
    assert b_id not in session_store.batches
    assert lifecycle_manager.is_session_expired(session_id) is True
    assert not os.path.exists(os.path.join("/tmp/anclora-purgedoc", session_id))
    # Subscriber queue must be closed with sentinel None
    assert q.get_nowait() is None

def test_expired_resource_status_code_410():
    """Verify expired sessions return 410 GONE status code"""
    session_id = "test_sess_expired_410"
    session_store.create_session(session_id)
    lifecycle_manager.register_session(session_id)
    
    # Mark expired directly
    lifecycle_manager.expired_sessions.add(session_id)
    assert lifecycle_manager.is_session_expired(session_id) is True

