import os
import io
import json
import zipfile
import pytest
import asyncio
from pathlib import Path

from backend.services.sessions import session_store
from backend.services.batch import batch_service, get_batch_config
from backend.services.event_bus import batch_event_bus, InMemoryBatchEventBus
from backend.services.rules import CustomRule
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata, BatchMetadata

@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    generate_all_fixtures()

def test_event_bus_monotonic_sequence_and_history():
    """Verify sequence monotonically increments and ring buffer honors max_history"""
    bus = InMemoryBatchEventBus(max_history_per_batch=5)
    batch_id = "test_b_seq"

    async def run_publishes():
        for i in range(8):
            await bus.publish(
                batch_id=batch_id,
                event_type="document_status_changed",
                status="analyzing",
                phase=f"phase_{i}",
                document_id="doc_1",
                payload={"index": i}
            )

    asyncio.run(run_publishes())

    assert bus._batch_sequences[batch_id] == 8
    # Ring buffer must be capped at 5
    assert len(bus._batch_history[batch_id]) == 5
    # Earliest sequence in ring buffer should be 4, last should be 8
    assert bus._batch_history[batch_id][0]["sequence"] == 4
    assert bus._batch_history[batch_id][-1]["sequence"] == 8

def test_event_bus_isolation_between_batches():
    """Verify client subscribed to batch A never receives events from batch B"""
    bus = InMemoryBatchEventBus()
    b_a = "batch_alpha"
    b_b = "batch_beta"

    q_a = bus.subscribe(b_a)
    q_b = bus.subscribe(b_b)

    async def publish_events():
        await bus.publish(batch_id=b_a, event_type="batch_started", status="processing", phase="start")
        await bus.publish(batch_id=b_b, event_type="batch_cancelled", status="cancelled", phase="cancel")

    asyncio.run(publish_events())

    # Queue A should have 1 item from b_a only
    assert q_a.qsize() == 1
    ev_a = q_a.get_nowait()
    assert ev_a["batchId"] == b_a
    assert ev_a["type"] == "batch_started"

    # Queue B should have 1 item from b_b only
    assert q_b.qsize() == 1
    ev_b = q_b.get_nowait()
    assert ev_b["batchId"] == b_b
    assert ev_b["type"] == "batch_cancelled"

    bus.unsubscribe(b_a, q_a)
    bus.unsubscribe(b_b, q_b)

def test_event_bus_reconnect_with_last_event_id():
    """Verify subscribing with last_event_id replays missed events"""
    bus = InMemoryBatchEventBus()
    batch_id = "test_reconnect"

    async def publish_initial():
        for i in range(1, 6):
            await bus.publish(
                batch_id=batch_id,
                event_type="document_status_changed",
                status="analyzing",
                phase=f"phase_{i}",
                payload={"step": i}
            )

    asyncio.run(publish_initial())

    # Reconnect asking for events after sequence 3 (should receive 4 and 5)
    q = bus.subscribe(batch_id, last_event_id=3)
    assert q.qsize() == 2

    ev4 = q.get_nowait()
    assert ev4["sequence"] == 4
    ev5 = q.get_nowait()
    assert ev5["sequence"] == 5

    bus.unsubscribe(batch_id, q)

def test_event_bus_slow_subscriber_protection():
    """Verify slow consumer does not cause unbounded queue memory growth"""
    bus = InMemoryBatchEventBus(max_queue_size=3)
    batch_id = "test_slow_client"
    q = bus.subscribe(batch_id)

    async def flood():
        for i in range(10):
            await bus.publish(batch_id=batch_id, event_type="tick", status="ok", phase="tick", payload={"i": i})

    asyncio.run(flood())

    # Queue size should not exceed max_queue_size
    assert q.qsize() <= 3
    bus.unsubscribe(batch_id, q)

def test_event_bus_strict_zero_pii_in_payloads():
    """
    CRITICAL PRIVACY TEST:
    Simulate full batch processing with synthetic fixtures containing real test PII (DNI, CIF, IBAN, names).
    Inspect every published event in history and assert that NO plain text PII is ever leaked.
    """
    session_id = "test_sess_zero_pii_stream"
    session_store.create_session(session_id)

    batch_id = "b_stream_privacy"
    batch = BatchMetadata(id=batch_id, session_id=session_id, default_profile_id="rrhh")
    session_store.batches[batch_id] = batch

    doc_id = "doc_stream_p1"
    doc_dir = session_store.get_document_dir(session_id, batch_id, doc_id)
    src_file = os.path.join(doc_dir, "sample_rrhh.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_rrhh_payroll.pdf"), "rb") as fi, open(src_file, "wb") as fo:
        fo.write(fi.read())

    doc_meta = DocumentMetadata(
        id=doc_id, session_id=session_id, batch_id=batch_id,
        filename="sample_rrhh.pdf", mime_type="application/pdf",
        size_bytes=os.path.getsize(src_file), profile_id="rrhh",
        source_sha256="fake_sha", status="queued"
    )
    session_store.documents[doc_id] = doc_meta
    session_store.doc_file_paths[doc_id] = {"source": src_file}
    batch.document_ids.append(doc_id)

    # Subscribe to capture all events
    q = batch_event_bus.subscribe(batch_id)

    async def execute_workflow():
        # 1. Analyze
        await batch_service.analyze_document_in_batch(doc_id, batch_id)
        # 2. Accept matches
        for m in session_store.matches[doc_id].values():
            m.status = "accepted"
        # 3. Purge
        await batch_service.purge_document_in_batch(doc_id, batch_id)

    asyncio.run(execute_workflow())

    # Known sensitive tokens from sample_rrhh_payroll.pdf fixture
    sensitive_tokens = [
        "12345678Z", "ES91 2100 0418 4502 0005 1332",
        "Carmenchu", "García Moreno", "28 12345678 40"
    ]

    captured_events = []
    while not q.empty():
        captured_events.append(q.get_nowait())

    assert len(captured_events) >= 5

    for ev in captured_events:
        ev_str = json.dumps(ev)
        # Verify no sensitive tokens present in any event serialization
        for token in sensitive_tokens:
            assert token not in ev_str, f"LEAK DETECTED! Sensitive token '{token}' found in SSE event: {ev}"

        # Payload keys must never contain raw text
        payload = ev.get("payload", {})
        for forbidden in ["raw_text", "extracted_text", "ocr_text", "text", "sensitive_text"]:
            assert forbidden not in payload

    batch_event_bus.unsubscribe(batch_id, q)
    session_store.cleanup_session(session_id)
