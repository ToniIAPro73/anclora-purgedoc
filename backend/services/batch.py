import os
import io
import json
import uuid
import shutil
import zipfile
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

from backend.models import DocumentMetadata, BatchMetadata, MatchItem, calculate_file_sha256
from backend.services.sessions import session_store
from backend.services.detection import detection_engine
from backend.services.documents import document_processor
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.audit import audit_service
from backend.services.rules import CustomRuleset, CustomRule
from backend.services.event_bus import batch_event_bus

logger = logging.getLogger(__name__)
from backend.services.csv_audit import generate_batch_audit_csv, generate_batch_audit_entities_csv

# Configurable environment limits
def get_batch_config():
    return {
        "max_documents": int(os.environ.get("BATCH_MAX_DOCUMENTS", 10)),
        "max_file_size_mb": int(os.environ.get("BATCH_MAX_FILE_SIZE_MB", 25)),
        "max_total_size_mb": int(os.environ.get("BATCH_MAX_TOTAL_SIZE_MB", 100)),
        "max_concurrent": int(os.environ.get("BATCH_MAX_CONCURRENT_DOCUMENTS", 2))
    }

class BatchService:
    def __init__(self):
        self._doc_custom_rulesets: Dict[str, Dict[str, Any]] = {}
        self._batch_custom_rulesets: Dict[str, Dict[str, Any]] = {}
        self._batch_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._active_workers: Dict[str, int] = {} # batch_id -> count of running workers

    def get_semaphore(self, batch_id: str) -> asyncio.Semaphore:
        config = get_batch_config()
        if batch_id not in self._batch_semaphores:
            self._batch_semaphores[batch_id] = asyncio.Semaphore(config["max_concurrent"])
        return self._batch_semaphores[batch_id]

    def get_active_workers_count(self, batch_id: str) -> int:
        return self._active_workers.get(batch_id, 0)

    def set_batch_ruleset(self, batch_id: str, custom_rules: Optional[List[CustomRule]], ruleset_id: str = "custom_ruleset", version: str = "1.0.0"):
        if custom_rules:
            ruleset_obj = CustomRuleset(
                ruleset_id=ruleset_id or "custom_ruleset",
                version=version or "1.0.0",
                rules=custom_rules
            )
            self._batch_custom_rulesets[batch_id] = {
                "ruleset_id": ruleset_obj.ruleset_id,
                "version": ruleset_obj.version,
                "hash": ruleset_obj.calculate_hash(),
                "active_rules_count": sum(1 for r in custom_rules if r.enabled),
                "rules": custom_rules
            }
        else:
            self._batch_custom_rulesets[batch_id] = {
                "ruleset_id": "none",
                "version": "1.0.0",
                "hash": "sha256:none",
                "active_rules_count": 0,
                "rules": []
            }

    def set_doc_ruleset(self, doc_id: str, ruleset_meta: Dict[str, Any]):
        self._doc_custom_rulesets[doc_id] = ruleset_meta

    def get_doc_ruleset(self, doc_id: str, batch_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if doc_id in self._doc_custom_rulesets:
            return self._doc_custom_rulesets[doc_id]
        if batch_id and batch_id in self._batch_custom_rulesets:
            return self._batch_custom_rulesets[batch_id]
        return None

    def compute_batch_status(self, batch: BatchMetadata) -> str:
        """
        Derives composite batch status based on its documents:
        draft | processing | awaiting_review | completed_verified | completed_with_errors | cancelled
        Strict rules:
        - completed_verified ONLY if ALL docs are 'verified' (and at least 1 doc exists).
        - completed_with_errors if any doc is 'verification_failed' or 'error' or 'cancelled' and others are completed/verified.
        - awaiting_review if any doc is 'awaiting_review' or 'ready_to_purge' and none currently analyzing/purging.
        - processing if any doc is 'validating', 'analyzing', 'purging', 'verifying', 'queued'.
        - cancelled if batch status was explicitly cancelled.
        """
        if batch.status == "cancelled":
            return "cancelled"

        if not batch.document_ids:
            return "draft"

        docs = [session_store.documents.get(d_id) for d_id in batch.document_ids]
        valid_docs = [d for d in docs if d is not None]

        statuses = [d.status for d in valid_docs]

        # Check if in-flight
        active_states = {"queued", "validating", "analyzing", "purging", "verifying"}
        if any(s in active_states for s in statuses):
            return "processing"

        # Check if review pending
        review_states = {"awaiting_review", "ready_to_purge", "uploaded"}
        if any(s in review_states for s in statuses):
            return "awaiting_review"

        # Terminal state assessment
        has_verified = any(s == "verified" for s in statuses)
        has_failed = any(s in {"verification_failed", "error", "cancelled"} for s in statuses)

        if has_failed:
            return "completed_with_errors"

        if has_verified and all(s == "verified" for s in statuses):
            return "completed_verified"

        return batch.status

    async def analyze_document_in_batch(self, doc_id: str, batch_id: str):
        """Single document analysis with controlled batch semaphore concurrency and real SSE progress phases"""
        sem = self.get_semaphore(batch_id)
        async with sem:
            self._active_workers[batch_id] = self._active_workers.get(batch_id, 0) + 1
            doc_meta = session_store.documents.get(doc_id)
            if not doc_meta:
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)
                return

            if doc_meta.status == "cancelled":
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)
                return

            doc_meta.status = "validating"
            await batch_event_bus.publish(
                batch_id=batch_id,
                event_type="document_status_changed",
                status="validating",
                phase="validating",
                document_id=doc_id,
                payload={"filename": doc_meta.filename, "activeWorkers": self._active_workers.get(batch_id, 0)}
            )

            paths = session_store.doc_file_paths[doc_id]
            source_file = paths["source"]
            doc_dir = os.path.dirname(source_file)

            try:
                doc_meta.status = "analyzing"
                is_pdf = doc_meta.mime_type == "application/pdf"
                
                # Phase: extraction
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_status_changed",
                    status="analyzing",
                    phase="extracting" if not is_pdf else "extracting_pdf_content",
                    document_id=doc_id,
                    payload={"filename": doc_meta.filename}
                )

                if is_pdf:
                    pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(source_file)
                    doc_meta.page_count = page_count
                    doc_meta.has_text_layer = has_text
                    doc_meta.is_scanned_ocr = is_scanned
                    paths["preview_pdf"] = source_file

                    if is_scanned:
                        await batch_event_bus.publish(
                            batch_id=batch_id,
                            event_type="document_status_changed",
                            status="analyzing",
                            phase="ocr_extraction",
                            document_id=doc_id,
                            payload={"filename": doc_meta.filename, "isScanned": True}
                        )
                else: # DOCX
                    pages_content, page_count, has_text = document_processor.extract_docx_content(source_file)
                    doc_meta.page_count = page_count
                    doc_meta.has_text_layer = has_text
                    doc_meta.is_scanned_ocr = False
                    preview_pdf = document_processor.convert_docx_to_preview_pdf(source_file, doc_dir)
                    paths["preview_pdf"] = preview_pdf

                if not has_text:
                    doc_meta.status = "error"
                    doc_meta.error_message = "El documento no contiene texto detectable incluso tras análisis OCR local."
                    await batch_event_bus.publish(
                        batch_id=batch_id,
                        event_type="document_error",
                        status="error",
                        phase="extraction_failed",
                        document_id=doc_id,
                        payload={"filename": doc_meta.filename, "error": doc_meta.error_message}
                    )
                    return

                # Phase: NER & regex detection
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_status_changed",
                    status="analyzing",
                    phase="ner_detection",
                    document_id=doc_id,
                    payload={"filename": doc_meta.filename, "profile": doc_meta.profile_id}
                )

                ruleset_meta = self.get_doc_ruleset(doc_id, batch_id)
                custom_rules = ruleset_meta.get("rules") if ruleset_meta else None

                matches = detection_engine.analyze_document_content(
                    doc_id=doc_id,
                    profile_id=doc_meta.profile_id,
                    pages_content=pages_content,
                    custom_rules=custom_rules
                )

                session_store.matches[doc_id] = {m.id: m for m in matches}
                doc_meta.status = "awaiting_review"

                # Publish awaiting_review event
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_awaiting_review",
                    status="awaiting_review",
                    phase="awaiting_review",
                    document_id=doc_id,
                    payload={
                        "filename": doc_meta.filename,
                        "matchesCount": len(matches),
                        "pendingCount": len(matches),
                        "activeWorkers": max(0, self._active_workers.get(batch_id, 1) - 1)
                    }
                )
            except Exception as e:
                logger.exception(f"Error analyzing batch document {doc_id}: {e}")
                doc_meta.status = "error"
                doc_meta.error_message = f"Error durante análisis: {str(e)}"
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_error",
                    status="error",
                    phase="error",
                    document_id=doc_id,
                    payload={"filename": doc_meta.filename, "error": doc_meta.error_message}
                )
            finally:
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)

    async def purge_document_in_batch(self, doc_id: str, batch_id: str) -> bool:
        """Single document purge and fail-closed verification reusing sovereign single-doc engine with SSE reporting"""
        sem = self.get_semaphore(batch_id)
        async with sem:
            self._active_workers[batch_id] = self._active_workers.get(batch_id, 0) + 1
            doc_meta = session_store.documents.get(doc_id)
            if not doc_meta:
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)
                return False

            if doc_meta.status == "cancelled":
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)
                return False

            paths = session_store.doc_file_paths[doc_id]
            source_file = paths["source"]
            doc_dir = os.path.dirname(source_file)

            matches_dict = session_store.matches.get(doc_id, {})
            all_matches = list(matches_dict.values())
            approved_matches = [m for m in all_matches if m.status == "accepted"]

            doc_meta.status = "purging"
            await batch_event_bus.publish(
                batch_id=batch_id,
                event_type="document_status_changed",
                status="purging",
                phase="purging",
                document_id=doc_id,
                payload={"filename": doc_meta.filename, "approvedCount": len(approved_matches)}
            )

            ext = Path(source_file).suffix.lower()
            safe_base = "".join(c for c in Path(doc_meta.filename).stem if c.isalnum() or c in ("-", "_")) or "document"
            purged_filename = f"purged_{safe_base}{ext}"
            purged_path = os.path.join(doc_dir, purged_filename)

            try:
                # 1. Real Redaction
                if ext == ".pdf":
                    is_scanned = getattr(doc_meta, "is_scanned_ocr", False)
                    redaction_engine.purge_pdf(source_file, purged_path, approved_matches, is_scanned=is_scanned)
                    doc_meta.status = "verifying"
                    await batch_event_bus.publish(
                        batch_id=batch_id,
                        event_type="document_status_changed",
                        status="verifying",
                        phase="verifying",
                        document_id=doc_id,
                        payload={"filename": doc_meta.filename}
                    )
                    passed, failures, v_details = verification_engine.verify_pdf(purged_path, approved_matches, is_scanned=is_scanned)
                else: # DOCX
                    redaction_engine.purge_docx(source_file, purged_path, approved_matches)
                    doc_meta.status = "verifying"
                    await batch_event_bus.publish(
                        batch_id=batch_id,
                        event_type="document_status_changed",
                        status="verifying",
                        phase="verifying",
                        document_id=doc_id,
                        payload={"filename": doc_meta.filename}
                    )
                    passed, failures, v_details = verification_engine.verify_docx(purged_path, approved_matches)

                for m in approved_matches:
                    m.status = "applied" if passed else "verification_failed"

                output_sha = calculate_file_sha256(purged_path) if (passed and os.path.exists(purged_path)) else None
                doc_meta.output_filename = purged_filename if passed else None
                doc_meta.output_sha256 = output_sha
                doc_meta.status = "verified" if passed else "verification_failed"

                if passed:
                    paths["purged"] = purged_path
                else:
                    paths.pop("purged", None)

                # Phase: Generating individual audit
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_status_changed",
                    status=doc_meta.status,
                    phase="generating_audit",
                    document_id=doc_id,
                    payload={"filename": doc_meta.filename, "passed": passed}
                )

                ruleset_meta = self.get_doc_ruleset(doc_id, batch_id)
                audit_json = audit_service.generate_audit_json(
                    doc_meta, all_matches, passed, v_details, custom_ruleset_meta=ruleset_meta
                )
                audit_json_path = os.path.join(doc_dir, f"audit_{doc_id}.json")
                with open(audit_json_path, "w", encoding="utf-8") as f:
                    json.dump(audit_json, f, indent=2, ensure_ascii=False)
                paths["audit_json"] = audit_json_path

                audit_pdf_path = os.path.join(doc_dir, f"audit_{doc_id}.pdf")
                audit_service.generate_audit_pdf(audit_json, audit_pdf_path)
                paths["audit_pdf"] = audit_pdf_path

                # Publish final document outcome
                if passed:
                    await batch_event_bus.publish(
                        batch_id=batch_id,
                        event_type="document_verified",
                        status="verified",
                        phase="verified",
                        document_id=doc_id,
                        payload={"filename": doc_meta.filename, "outputSha256": output_sha}
                    )
                else:
                    await batch_event_bus.publish(
                        batch_id=batch_id,
                        event_type="document_verification_failed",
                        status="verification_failed",
                        phase="verification_failed",
                        document_id=doc_id,
                        payload={"filename": doc_meta.filename}
                    )

                return passed
            except Exception as e:
                logger.exception(f"Error purging batch document {doc_id}: {e}")
                doc_meta.status = "error"
                doc_meta.error_message = f"Error durante purga: {str(e)}"
                paths.pop("purged", None)
                await batch_event_bus.publish(
                    batch_id=batch_id,
                    event_type="document_error",
                    status="error",
                    phase="error",
                    document_id=doc_id,
                    payload={"filename": doc_meta.filename, "error": doc_meta.error_message}
                )
                return False
            finally:
                self._active_workers[batch_id] = max(0, self._active_workers.get(batch_id, 1) - 1)

    def generate_batch_audit_summary(self, batch_id: str) -> Dict[str, Any]:
        """
        Consolidates audit summary across all documents in batch.
        NO sensitive plaintext is included! Only metadata, SHA-256 hashes, status, counts.
        """
        batch = session_store.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        docs = [session_store.documents.get(d_id) for d_id in batch.document_ids]
        valid_docs = [d for d in docs if d is not None]

        total_docs = len(valid_docs)
        verified_count = sum(1 for d in valid_docs if d.status == "verified")
        failed_count = sum(1 for d in valid_docs if d.status == "verification_failed")
        error_count = sum(1 for d in valid_docs if d.status == "error")
        cancelled_count = sum(1 for d in valid_docs if d.status == "cancelled")
        pending_count = sum(1 for d in valid_docs if d.status in {"uploaded", "queued", "validating", "analyzing", "awaiting_review", "ready_to_purge", "purging", "verifying"})

        total_detected = 0
        total_accepted = 0
        total_rejected = 0
        by_entity_type: Dict[str, int] = {}
        by_profile: Dict[str, int] = {}

        doc_summaries = []
        for d in valid_docs:
            d_matches = list(session_store.matches.get(d.id, {}).values())
            m_count = len(d_matches)
            acc_count = sum(1 for m in d_matches if m.status in {"accepted", "applied"})
            rej_count = sum(1 for m in d_matches if m.status == "rejected")
            total_detected += m_count
            total_accepted += acc_count
            total_rejected += rej_count

            for m in d_matches:
                by_entity_type[m.entity_type] = by_entity_type.get(m.entity_type, 0) + 1

            by_profile[d.profile_id] = by_profile.get(d.profile_id, 0) + 1

            ruleset_meta = self.get_doc_ruleset(d.id, batch_id) or {}
            paths = session_store.doc_file_paths.get(d.id, {})

            doc_summaries.append({
                "document_id": d.id,
                "filename": d.filename,
                "mime_type": d.mime_type,
                "profile_id": d.profile_id,
                "status": d.status,
                "source_sha256": d.source_sha256,
                "output_sha256": d.output_sha256 if d.status == "verified" else None,
                "matches_count": m_count,
                "accepted_count": acc_count,
                "rejected_count": rej_count,
                "ruleset_id": ruleset_meta.get("ruleset_id", "none"),
                "ruleset_version": ruleset_meta.get("version", "1.0.0"),
                "ruleset_hash": ruleset_meta.get("hash", "sha256:none"),
                "has_audit": bool(paths.get("audit_json") and os.path.exists(paths.get("audit_json")))
            })

        batch_status = self.compute_batch_status(batch)
        batch.status = batch_status

        summary = {
            "batch_id": batch.id,
            "session_id": batch.session_id,
            "created_at": batch.created_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "batch_status": batch_status,
            "metrics": {
                "total_documents": total_docs,
                "verified": verified_count,
                "verification_failed": failed_count,
                "error": error_count,
                "cancelled": cancelled_count,
                "pending": pending_count,
                "total_matches_detected": total_detected,
                "total_matches_purged": total_accepted,
                "total_matches_rejected": total_rejected
            },
            "by_entity_type": by_entity_type,
            "by_profile": by_profile,
            "documents": doc_summaries
        }
        return summary

    def build_batch_zip(self, batch_id: str) -> str:
        """
        Creates anclora-purgedoc-batch-{batchId}.zip:
        ├── documents/
        │   ├── document-01-purged.pdf (ONLY VERIFIED)
        ├── audits/
        │   ├── document-01-audit.pdf
        │   ├── document-01-audit.json
        ├── batch-audit.pdf
        └── batch-audit.json
        STRICT SECURITY:
        - NEVER include original files or temporary artifacts.
        - NEVER include failed or unverified documents in documents/.
        - Defends against ZIP Slip/path traversal.
        """
        batch = session_store.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
        zip_path = os.path.join(batch_dir, f"anclora-purgedoc-batch-{batch_id}.zip")

        summary_data = self.generate_batch_audit_summary(batch_id)
        batch_audit_json_path = os.path.join(batch_dir, "batch-audit.json")
        with open(batch_audit_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

        batch_audit_pdf_path = os.path.join(batch_dir, "batch-audit.pdf")
        audit_service.generate_batch_audit_pdf(summary_data, batch_audit_pdf_path)

        # Generate Canonical CSV Audits
        batch_audit_csv_path = os.path.join(batch_dir, "batch-audit.csv")
        csv_content = generate_batch_audit_csv(summary_data)
        with open(batch_audit_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)

        batch_audit_entities_csv_path = os.path.join(batch_dir, "batch-audit-entities.csv")
        entities_csv_content = generate_batch_audit_entities_csv(summary_data, session_store)
        with open(batch_audit_entities_csv_path, "w", encoding="utf-8") as f:
            f.write(entities_csv_content)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(batch_audit_json_path, arcname="batch-audit.json")
            zip_file.write(batch_audit_pdf_path, arcname="batch-audit.pdf")
            zip_file.write(batch_audit_csv_path, arcname="batch-audit.csv")
            zip_file.write(batch_audit_entities_csv_path, arcname="batch-audit-entities.csv")

            for doc_id in batch.document_ids:
                doc = session_store.documents.get(doc_id)
                if not doc:
                    continue

                paths = session_store.doc_file_paths.get(doc_id, {})

                if doc.status == "verified":
                    purged_path = paths.get("purged")
                    if purged_path and os.path.exists(purged_path):
                        safe_name = os.path.basename(purged_path)
                        zip_file.write(purged_path, arcname=f"documents/{safe_name}")

                audit_json_path = paths.get("audit_json")
                if audit_json_path and os.path.exists(audit_json_path):
                    safe_json_name = f"{doc.filename}-audit.json"
                    zip_file.write(audit_json_path, arcname=f"audits/{safe_json_name}")

                audit_pdf_path = paths.get("audit_pdf")
                if audit_pdf_path and os.path.exists(audit_pdf_path):
                    safe_pdf_name = f"{doc.filename}-audit.pdf"
                    zip_file.write(audit_pdf_path, arcname=f"audits/{safe_pdf_name}")

        return zip_path

batch_service = BatchService()
