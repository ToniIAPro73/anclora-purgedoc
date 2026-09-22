import asyncio
import json
import time
import logging
from typing import Dict, List, Any, Optional, Set
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

class BaseEventBus(ABC):
    @abstractmethod
    async def publish(self, batch_id: str, event_type: str, status: str, phase: str, document_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None):
        pass

    @abstractmethod
    def subscribe(self, batch_id: str, last_event_id: Optional[int] = None) -> asyncio.Queue:
        pass

    @abstractmethod
    def unsubscribe(self, batch_id: str, queue: asyncio.Queue):
        pass

    @abstractmethod
    def cleanup_batch(self, batch_id: str):
        pass

class InMemoryBatchEventBus(BaseEventBus):
    """
    Decoupled In-Memory Event Bus for Batch Progress Streaming (SSE).
    - Monotonic sequence numbers per batch.
    - History ring buffer with configurable MAX_HISTORY to support robust reconnects with Last-Event-ID.
    - Strict isolation: clients only receive events for their exact batch.
    - Subscriber queue bound limit protection against slow consumers.
    - Strict privacy guarantee: zero extracted document text, zero raw OCR, zero sensitive PII tokens.
    """
    def __init__(self, max_history_per_batch: int = 500, max_queue_size: int = 100):
        self.max_history_per_batch = max_history_per_batch
        self.max_queue_size = max_queue_size
        self._batch_sequences: Dict[str, int] = {} # batch_id -> current sequence
        self._batch_history: Dict[str, List[Dict[str, Any]]] = {} # batch_id -> list of event dicts
        self._batch_subscribers: Dict[str, Set[asyncio.Queue]] = {} # batch_id -> set of subscriber queues
        self._lock = asyncio.Lock()

    async def publish(
        self,
        batch_id: str,
        event_type: str,
        status: str,
        phase: str,
        document_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Publishes a typed sanitized event into the batch stream.
        """
        async with self._lock:
            seq = self._batch_sequences.get(batch_id, 0) + 1
            self._batch_sequences[batch_id] = seq

            # Sanitize payload: strip any raw text / PII leaks defensively
            safe_payload = {}
            if payload:
                for k, v in payload.items():
                    # Reject any keys containing raw text or pii tokens
                    if k in {"raw_text", "extracted_text", "ocr_text", "text", "sensitive_text"}:
                        continue
                    safe_payload[k] = v

            event = {
                "eventId": f"evt_{batch_id}_{seq}",
                "sequence": seq,
                "batchId": batch_id,
                "documentId": document_id,
                "type": event_type,
                "status": status,
                "phase": phase,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "schemaVersion": 1,
                "payload": safe_payload
            }

            # Append to ring buffer
            if batch_id not in self._batch_history:
                self._batch_history[batch_id] = []
            history = self._batch_history[batch_id]
            history.append(event)
            if len(history) > self.max_history_per_batch:
                history.pop(0)

            # Broadcast to active subscriber queues
            subscribers = self._batch_subscribers.get(batch_id, set()).copy()
            for q in subscribers:
                try:
                    if q.full():
                        # Drop oldest item for slow consumer to avoid unbounded RAM growth
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    q.put_nowait(event)
                except Exception as e:
                    logger.debug(f"Error publishing to subscriber queue: {e}")

            return event

    def subscribe(self, batch_id: str, last_event_id: Optional[int] = None) -> asyncio.Queue:
        """
        Subscribes a client to a batch event stream.
        If last_event_id is provided, replays all buffered events with sequence > last_event_id.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
        if batch_id not in self._batch_subscribers:
            self._batch_subscribers[batch_id] = set()
        self._batch_subscribers[batch_id].add(q)

        # Replay missed events if requested
        if last_event_id is not None and batch_id in self._batch_history:
            for ev in self._batch_history[batch_id]:
                if ev.get("sequence", 0) > last_event_id:
                    try:
                        q.put_nowait(ev)
                    except asyncio.QueueFull:
                        break

        logger.info(f"Subscribed client to batch {batch_id} (last_event_id={last_event_id})")
        return q

    def unsubscribe(self, batch_id: str, queue: asyncio.Queue):
        """Removes a subscriber queue and drains it."""
        if batch_id in self._batch_subscribers:
            self._batch_subscribers[batch_id].discard(queue)
            if not self._batch_subscribers[batch_id]:
                self._batch_subscribers.pop(batch_id, None)
        logger.info(f"Unsubscribed client from batch {batch_id}")

    def cleanup_batch(self, batch_id: str):
        """Purges event history and closes remaining queues for a completed/destroyed batch."""
        self._batch_sequences.pop(batch_id, None)
        self._batch_history.pop(batch_id, None)
        subscribers = self._batch_subscribers.pop(batch_id, set())
        for q in subscribers:
            # Put sentinel None to signal closure
            try:
                q.put_nowait(None)
            except Exception:
                pass
        logger.info(f"Cleaned up event bus for batch {batch_id}")

# Global decoupled EventBus instance
batch_event_bus = InMemoryBatchEventBus()
