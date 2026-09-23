import os
import asyncio
import io
import sys
from datetime import datetime, timezone
import json
import uuid
import shutil
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure /app is in sys.path
APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.models import DocumentMetadata, MatchItem, calculate_file_sha256
from backend.services.sessions import session_store
from backend.services.detection import detection_engine
from backend.services.documents import document_processor
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.audit import audit_service
from backend.services.rules import (
    CustomRule, CustomRuleset, RegexValidator,
    RuleValidationResult, RuleTestResponse
)
from backend.models import BatchMetadata
from backend.services.batch import batch_service, get_batch_config
from backend.services.csv_audit import generate_batch_audit_csv, generate_batch_audit_entities_csv
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.services.event_bus import batch_event_bus
from backend.services.lifecycle import lifecycle_manager, get_retention_config
from backend.services.encrypted_rules import (
    export_encrypted_ruleset,
    preview_encrypted_ruleset,
    EncryptedRulesetError
)
from backend.db import metadata_store

logger = logging.getLogger(__name__)

# Ensure synthetic test fixtures exist on boot
generate_all_fixtures()

app = FastAPI(title="Anclora Purgedoc API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# CORS Setup
origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory document session store for active custom rulesets
_DOC_CUSTOM_RULESETS: Dict[str, Dict[str, Any]] = {}

# In-memory session byte cache to avoid permanent pod upload storage
_SESSION_RAW_BYTES: Dict[str, bytes] = {}

# Recover only sanitized lifecycle state. Raw active content remains ephemeral.
metadata_store.startup_recover()

def store_in_memory_session(doc_id: str, data: bytes):
    _SESSION_RAW_BYTES[doc_id] = data

def get_in_memory_session(doc_id: str) -> bytes:
    return _SESSION_RAW_BYTES.get(doc_id, b"")

# ----------------- Schemas -----------------
class SessionResponse(BaseModel):
    session_id: str
    status: str

class MatchUpdatePayload(BaseModel):
    status: str

class BulkMatchUpdatePayload(BaseModel):
    match_ids: Optional[List[str]] = None
    all_visible: bool = False
    status: str

class PurgeResponse(BaseModel):
    document_id: str
    status: str
    verification_passed: bool
    failures: List[str]
    details: Dict[str, Any]
    output_sha256: Optional[str] = None
    audit_id: str

class AnalyzeDocumentPayload(BaseModel):
    custom_rules: Optional[List[CustomRule]] = None
    ruleset_id: Optional[str] = "custom_ruleset"
    ruleset_version: Optional[str] = "1.0.0"

class TestRulePayload(BaseModel):
    rule: CustomRule
    test_text: str

class ValidateRegexPayload(BaseModel):
    pattern: str
    case_sensitive: bool = False

class CreateBatchPayload(BaseModel):
    default_profile_id: Optional[str] = "rrhh"
    custom_rules: Optional[List[CustomRule]] = None
    ruleset_id: Optional[str] = "custom_ruleset"
    ruleset_version: Optional[str] = "1.0.0"

class UpdateBatchDocumentProfilePayload(BaseModel):
    profile_id: str

class StartBatchAnalysisPayload(BaseModel):
    custom_rules: Optional[List[CustomRule]] = None
    ruleset_id: Optional[str] = "custom_ruleset"
    ruleset_version: Optional[str] = "1.0.0"

class StartBatchPurgePayload(BaseModel):
    document_ids: Optional[List[str]] = None

class ExportEncryptedRulesetPayload(BaseModel):
    ruleset: CustomRuleset
    password: str
    ruleset_name: Optional[str] = None
    description: Optional[str] = None

class PreviewEncryptedRulesetPayload(BaseModel):
    envelope: Dict[str, Any]
    password: str
    current_rules: Optional[List[CustomRule]] = None

# ----------------- Routes -----------------

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "product": "Anclora Purgedoc",
        "version": "1.0.0",
        "profiles": list(detection_engine.profiles.keys()),
        "ner_models_loaded": list(detection_engine.nlp_models.keys()),
        "privacy": "100% Local / Zero Remote LLM Calls",
        "custom_rules_engine": "RE2 / Safe PCRE"
    }

@api_router.post("/sessions", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    session_store.create_session(session_id)
    lifecycle_manager.register_session(session_id)
    metadata_store.session_started(session_id, datetime.now(timezone.utc))
    return {"session_id": session_id, "status": "active"}

@api_router.get("/sessions/{session_id}/expiry")
async def get_session_expiry(session_id: str):
    if lifecycle_manager.is_session_expired(session_id):
        raise HTTPException(
            status_code=410,
            detail={"code": "RESOURCE_EXPIRED", "detail": "RESOURCE_EXPIRED"}
        )
    info = lifecycle_manager.get_session_expiry_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return info

@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await lifecycle_manager.delete_session_now(session_id, session_store, reason="manual_user_action")
    metadata_store.tombstone("session", session_id, "manual_user_action")
    return {"status": "deleted", "session_id": session_id}

@api_router.get("/profiles")
async def get_profiles():
    """Returns available base vertical profiles for upload UI and rule cloning"""
    results = []
    for pid, pdata in detection_engine.profiles.items():
        results.append({
            "id": pid,
            "name_es": pdata.get("name_es", pid),
            "name_en": pdata.get("name_en", pid),
            "version": pdata.get("version", "1.0.0"),
            "description": pdata.get("description", ""),
            "rules_count": len(pdata.get("regex_rules", [])),
            "regex_rules": pdata.get("regex_rules", [])
        })
    return results

# ----------------- Custom Rules Endpoints -----------------

@api_router.post("/rules/validate", response_model=RuleValidationResult)
async def validate_regex_pattern(payload: ValidateRegexPayload):
    """Checks pattern syntax and guards against catastrophic backtracking (ReDoS)"""
    return RegexValidator.validate_pattern(payload.pattern, payload.case_sensitive)

@api_router.post("/rules/test", response_model=RuleTestResponse)
async def test_custom_rule(payload: TestRulePayload):
    """Executes safe Regex Test Bench on synthetic test text without touching real documents"""
    return RegexValidator.test_rule(payload.rule, payload.test_text)

@api_router.post("/rules/hash")
async def compute_ruleset_hash(ruleset: CustomRuleset):
    """Computes deterministic hash for a given ruleset without saving it"""
    return {
        "ruleset_id": ruleset.ruleset_id,
        "version": ruleset.version,
        "hash": ruleset.calculate_hash(),
        "active_rules_count": sum(1 for r in ruleset.rules if r.enabled)
    }

# ----------------- Document Endpoints -----------------

@api_router.post("/sessions/{session_id}/documents")
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    profile_id: str = Form("rrhh")
):
    session_dir = session_store.get_session_dir(session_id)
    doc_id = str(uuid.uuid4())
    
    filename = file.filename or "uploaded_doc"
    ext = Path(filename).suffix.lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Debe ser un archivo .pdf o .docx nativo.")

    content_bytes = await file.read()
    file_size = len(content_bytes)
    max_mb = int(os.environ.get("MAX_UPLOAD_MB", 25))
    if file_size > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"El archivo excede el tamaño máximo permitido ({max_mb} MB).")

    store_in_memory_session(doc_id, content_bytes)

    dest_file = os.path.join(session_dir, f"{doc_id}_{filename}")
    shutil.copyfileobj(io.BytesIO(content_bytes), open(dest_file, "wb"))

    source_sha = calculate_file_sha256(dest_file)
    mime = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    doc_meta = DocumentMetadata(
        id=doc_id,
        session_id=session_id,
        filename=filename,
        mime_type=mime,
        size_bytes=file_size,
        profile_id=profile_id,
        source_sha256=source_sha,
        status="uploaded"
    )

    session_store.documents[doc_id] = doc_meta
    metadata_store.document_created(doc_meta)
    session_store.doc_file_paths[doc_id] = {
        "source": dest_file,
        "preview_pdf": dest_file if ext == ".pdf" else None
    }

    return doc_meta.model_dump()

@api_router.post("/fixtures/{fixture_name}/load")
async def load_synthetic_fixture(fixture_name: str, session_id: str, profile_id: Optional[str] = None):
    session_dir = session_store.get_session_dir(session_id)
    doc_id = str(uuid.uuid4())
    
    mapping = {
        "rrhh": ("sample_rrhh_payroll.pdf", "rrhh", "application/pdf"),
        "legal": ("sample_legal_contract.docx", "legal", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "soporte": ("sample_soporte_incident.pdf", "soporte", "application/pdf"),
        "scanned": ("sample_scanned_medical_hr.pdf", "rrhh", "application/pdf"),
        "rotated": ("sample_rotated_scanned.pdf", "soporte", "application/pdf")
    }

    if fixture_name not in mapping:
        raise HTTPException(status_code=404, detail="Fixture no encontrado.")

    fname, default_prof, mime = mapping[fixture_name]
    chosen_profile = profile_id or default_prof
    src_fixture_path = os.path.join(FIXTURES_DIR, fname)
    if not os.path.exists(src_fixture_path):
        generate_all_fixtures()

    dest_file = os.path.join(session_dir, f"{doc_id}_{fname}")
    shutil.copyfile(src_fixture_path, dest_file)

    source_sha = calculate_file_sha256(dest_file)
    doc_meta = DocumentMetadata(
        id=doc_id,
        session_id=session_id,
        filename=fname,
        mime_type=mime,
        size_bytes=os.path.getsize(dest_file),
        profile_id=chosen_profile,
        source_sha256=source_sha,
        status="uploaded"
    )

    session_store.documents[doc_id] = doc_meta
    metadata_store.document_created(doc_meta)
    session_store.doc_file_paths[doc_id] = {
        "source": dest_file,
        "preview_pdf": dest_file if dest_file.endswith(".pdf") else None
    }
    return doc_meta.model_dump()

@api_router.post("/documents/{doc_id}/analyze")
async def analyze_document(doc_id: str, payload: Optional[AnalyzeDocumentPayload] = None):
    """Executes local parsing, text extraction, NER & Regex detection with optional custom rules"""
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    doc_meta = session_store.documents[doc_id]
    paths = session_store.doc_file_paths[doc_id]
    source_file = paths["source"]
    session_dir = session_store.get_session_dir(doc_meta.session_id)

    doc_meta.status = "analyzing"

    if doc_meta.mime_type == "application/pdf":
        pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(source_file)
        doc_meta.page_count = page_count
        doc_meta.has_text_layer = has_text
        doc_meta.is_scanned_ocr = is_scanned
        paths["preview_pdf"] = source_file
    else: # DOCX
        pages_content, page_count, has_text = document_processor.extract_docx_content(source_file)
        doc_meta.page_count = page_count
        doc_meta.has_text_layer = has_text
        doc_meta.is_scanned_ocr = False
        preview_pdf = document_processor.convert_docx_to_preview_pdf(source_file, session_dir)
        paths["preview_pdf"] = preview_pdf

    if not has_text:
        doc_meta.status = "error"
        doc_meta.error_message = "El documento no contiene texto detectable incluso tras análisis OCR local."
        raise HTTPException(status_code=422, detail=doc_meta.error_message)

    # Process custom rules and calculate deterministic hash
    custom_rules_list = payload.custom_rules if payload else None
    if custom_rules_list:
        ruleset_obj = CustomRuleset(
            ruleset_id=payload.ruleset_id or "custom_ruleset",
            version=payload.ruleset_version or "1.0.0",
            rules=custom_rules_list
        )
        _DOC_CUSTOM_RULESETS[doc_id] = {
            "ruleset_id": ruleset_obj.ruleset_id,
            "version": ruleset_obj.version,
            "hash": ruleset_obj.calculate_hash(),
            "active_rules_count": sum(1 for r in custom_rules_list if r.enabled)
        }
    else:
        _DOC_CUSTOM_RULESETS[doc_id] = {
            "ruleset_id": "none",
            "version": "1.0.0",
            "hash": "sha256:none",
            "active_rules_count": 0
        }

    # Run detection with custom rules overlay
    matches = detection_engine.analyze_document_content(
        doc_id=doc_id,
        profile_id=doc_meta.profile_id,
        pages_content=pages_content,
        custom_rules=custom_rules_list
    )

    session_store.matches[doc_id] = {m.id: m for m in matches}
    doc_meta.status = "ready_for_review"
    metadata_store.document_updated(doc_meta)

    return {
        "document": doc_meta.model_dump(),
        "matches_count": len(matches),
        "matches": [m.to_public_dict() for m in matches],
        "ruleset_meta": _DOC_CUSTOM_RULESETS[doc_id]
    }

@api_router.get("/documents/{doc_id}/matches")
async def get_document_matches(doc_id: str):
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    
    matches_dict = session_store.matches.get(doc_id, {})
    return [m.to_public_dict() for m in matches_dict.values()]

@api_router.patch("/matches/{match_id}")
async def update_match_status(match_id: str, payload: MatchUpdatePayload):
    found_match = None
    for doc_matches in session_store.matches.values():
        if match_id in doc_matches:
            found_match = doc_matches[match_id]
            break
            
    if not found_match:
        raise HTTPException(status_code=404, detail="Coincidencia no encontrada.")

    if payload.status not in ["accepted", "rejected", "pending"]:
        raise HTTPException(status_code=400, detail="Estado no válido.")

    found_match.status = payload.status
    return found_match.to_public_dict()

@api_router.post("/documents/{doc_id}/matches/bulk")
async def bulk_update_matches(doc_id: str, payload: BulkMatchUpdatePayload):
    if doc_id not in session_store.matches:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    doc_matches = session_store.matches[doc_id]
    target_ids = payload.match_ids if (payload.match_ids and not payload.all_visible) else list(doc_matches.keys())

    updated = 0
    for mid in target_ids:
        if mid in doc_matches:
            doc_matches[mid].status = payload.status
            updated += 1

    return {"updated": updated, "status": payload.status}

@api_router.get("/documents/{doc_id}/page-image/{page_num}")
async def get_page_image(doc_id: str, page_num: int):
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    paths = session_store.doc_file_paths.get(doc_id, {})
    preview_pdf = paths.get("preview_pdf")
    if not preview_pdf or not os.path.exists(preview_pdf):
        raise HTTPException(status_code=404, detail="Vista previa no disponible.")

    png_bytes = document_processor.render_pdf_page_image(preview_pdf, page_num)
    return Response(content=png_bytes, media_type="image/png")

@api_router.post("/documents/{doc_id}/purge", response_model=PurgeResponse)
async def purge_and_verify_document(doc_id: str):
    """
    Core Mission: Real Redaction & Post-Purge Fail-Closed Verification
    """
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    doc_meta = session_store.documents[doc_id]
    paths = session_store.doc_file_paths[doc_id]
    source_file = paths["source"]
    session_dir = session_store.get_session_dir(doc_meta.session_id)

    matches_dict = session_store.matches.get(doc_id, {})
    all_matches = list(matches_dict.values())
    approved_matches = [m for m in all_matches if m.status == "accepted"]

    doc_meta.status = "purging"
    ext = Path(source_file).suffix.lower()
    safe_base = "".join(c for c in Path(doc_meta.filename).stem if c.isalnum() or c in ("-", "_")) or "document"
    purged_filename = f"purged_{safe_base}{ext}"
    purged_path = os.path.join(session_dir, purged_filename)

    # 1. Real Redaction
    if ext == ".pdf":
        is_scanned = getattr(doc_meta, "is_scanned_ocr", False)
        redaction_res = redaction_engine.purge_pdf(source_file, purged_path, approved_matches, is_scanned=is_scanned)
        passed, failures, v_details = verification_engine.verify_pdf(purged_path, approved_matches, is_scanned=is_scanned)
    else: # DOCX
        redaction_res = redaction_engine.purge_docx(source_file, purged_path, approved_matches)
        passed, failures, v_details = verification_engine.verify_docx(purged_path, approved_matches)

    for m in approved_matches:
        m.status = "applied" if passed else "verification_failed"

    output_sha = calculate_file_sha256(purged_path) if os.path.exists(purged_path) else None
    doc_meta.output_filename = purged_filename
    doc_meta.output_sha256 = output_sha
    doc_meta.status = "verified" if passed else "verification_failed"

    paths["purged"] = purged_path

    # 3. Generate Audit Records with custom ruleset metadata
    custom_ruleset_meta = _DOC_CUSTOM_RULESETS.get(doc_id)
    audit_json = audit_service.generate_audit_json(doc_meta, all_matches, passed, v_details, custom_ruleset_meta=custom_ruleset_meta)
    audit_json_path = os.path.join(session_dir, f"audit_{doc_id}.json")
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump(audit_json, f, indent=2, ensure_ascii=False)
    paths["audit_json"] = audit_json_path

    audit_pdf_path = os.path.join(session_dir, f"audit_{doc_id}.pdf")
    audit_service.generate_audit_pdf(audit_json, audit_pdf_path)
    metadata_store.document_updated(doc_meta)
    metadata_store.audit_completed(doc_meta, audit_json, all_matches)
    paths["audit_pdf"] = audit_pdf_path

    return {
        "document_id": doc_id,
        "status": doc_meta.status,
        "verification_passed": passed,
        "failures": failures,
        "details": v_details,
        "output_sha256": output_sha,
        "audit_id": audit_json["audit_id"]
    }

@api_router.get("/documents/{doc_id}/download")
async def download_purged_file(doc_id: str):
    paths = session_store.doc_file_paths.get(doc_id, {})
    purged_path = paths.get("purged")
    if not purged_path or not os.path.exists(purged_path):
        raise HTTPException(status_code=404, detail="Archivo purgado no disponible.")

    doc_meta = session_store.documents.get(doc_id)
    out_name = doc_meta.output_filename if doc_meta else "purged_document"
    return FileResponse(purged_path, filename=out_name, media_type="application/octet-stream")

@api_router.get("/documents/{doc_id}/audit.json")
async def download_audit_json(doc_id: str):
    paths = session_store.doc_file_paths.get(doc_id, {})
    json_path = paths.get("audit_json")
    if not json_path or not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Auditoría JSON no disponible.")
    return FileResponse(json_path, filename=f"audit_{doc_id}.json", media_type="application/json")

@api_router.get("/documents/{doc_id}/audit.pdf")
async def download_audit_pdf(doc_id: str):
    paths = session_store.doc_file_paths.get(doc_id, {})
    pdf_path = paths.get("audit_pdf")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Certificado de auditoría PDF no disponible.")
    return FileResponse(pdf_path, filename=f"audit_{doc_id}.pdf", media_type="application/pdf")



# ----------------- Encrypted Ruleset (.aprules) Endpoints -----------------

@api_router.post("/rules/export-encrypted")
async def export_encrypted_ruleset_endpoint(payload: ExportEncryptedRulesetPayload):
    try:
        envelope = export_encrypted_ruleset(
            ruleset=payload.ruleset,
            password=payload.password,
            ruleset_name=payload.ruleset_name,
            description=payload.description
        )
        return envelope
    except EncryptedRulesetError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "detail": e.detail})
    except Exception as e:
        logger.exception("Export encrypted ruleset error")
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_CRYPTO_ERROR", "detail": "Error interno al cifrar ruleset."})

@api_router.post("/rules/preview-encrypted")
async def preview_encrypted_ruleset_endpoint(payload: PreviewEncryptedRulesetPayload):
    try:
        preview_data = preview_encrypted_ruleset(
            envelope=payload.envelope,
            password=payload.password,
            current_rules=payload.current_rules
        )
        return preview_data
    except EncryptedRulesetError as e:
        status_code = 401 if e.code == "ENCRYPTED_RULESET_AUTH_FAILED" else 400
        raise HTTPException(status_code=status_code, detail={"code": e.code, "detail": e.detail})
    except Exception as e:
        logger.exception("Preview encrypted ruleset error")
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_CRYPTO_ERROR", "detail": "Error interno al descifrar ruleset."})

# ----------------- Batch Processing Endpoints -----------------

@api_router.get("/batch/config")
async def get_batch_configuration():
    return get_batch_config()

@api_router.post("/sessions/{session_id}/batches")
async def create_batch(session_id: str, payload: Optional[CreateBatchPayload] = None):
    session_store.touch_session(session_id)
    batch_id = str(uuid.uuid4())
    default_profile = payload.default_profile_id if payload else "rrhh"
    ruleset_id = payload.ruleset_id if payload else "custom_ruleset"
    ruleset_ver = payload.ruleset_version if payload else "1.0.0"
    custom_rules = payload.custom_rules if payload else None

    batch_meta = BatchMetadata(
        id=batch_id,
        session_id=session_id,
        default_profile_id=default_profile,
        ruleset_id=ruleset_id,
        ruleset_version=ruleset_ver,
        status="draft"
    )
    session_store.batches[batch_id] = batch_meta
    session_store.get_batch_dir(session_id, batch_id)
    metadata_store.batch_created(batch_meta)

    # Register ruleset overlay for batch
    batch_service.set_batch_ruleset(batch_id, custom_rules, ruleset_id=ruleset_id, version=ruleset_ver)

    return batch_meta.model_dump()

@api_router.get("/batches/{batch_id}")
async def get_batch_details(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    # Re-compute composite status
    batch.status = batch_service.compute_batch_status(batch)
    docs_list = []
    for d_id in batch.document_ids:
        d = session_store.documents.get(d_id)
        if not d:
            continue
        d_matches = list(session_store.matches.get(d_id, {}).values())
        paths = session_store.doc_file_paths.get(d_id, {})
        docs_list.append({
            **d.model_dump(),
            "matches_count": len(d_matches),
            "accepted_count": sum(1 for m in d_matches if m.status in {"accepted", "applied"}),
            "rejected_count": sum(1 for m in d_matches if m.status == "rejected"),
            "pending_count": sum(1 for m in d_matches if m.status == "pending"),
            "has_purged": bool(paths.get("purged") and os.path.exists(paths.get("purged"))),
            "has_audit": bool(paths.get("audit_json") and os.path.exists(paths.get("audit_json")))
        })

    config = get_batch_config()
    total_bytes = sum(d["size_bytes"] for d in docs_list)

    return {
        "batch": batch.model_dump(),
        "documents": docs_list,
        "limits": {
            **config,
            "current_documents_count": len(docs_list),
            "current_total_bytes": total_bytes
        }
    }

@api_router.post("/batches/{batch_id}/documents")
async def upload_documents_to_batch(
    batch_id: str,
    files: List[UploadFile] = File(...),
    profile_id: Optional[str] = Form(None)
):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    if batch.status not in ["draft", "awaiting_review"]:
        raise HTTPException(status_code=400, detail="No se pueden añadir documentos a un lote en proceso o cerrado.")

    config = get_batch_config()
    current_docs = [session_store.documents.get(d_id) for d_id in batch.document_ids if session_store.documents.get(d_id)]
    
    if len(current_docs) + len(files) > config["max_documents"]:
        raise HTTPException(
            status_code=400,
            detail=f"Límite excedido: El lote permite un máximo de {config['max_documents']} documentos."
        )

    current_total_bytes = sum(d.size_bytes for d in current_docs)
    max_total_bytes = config["max_total_size_mb"] * 1024 * 1024
    max_file_bytes = config["max_file_size_mb"] * 1024 * 1024

    uploaded_docs = []
    chosen_profile = profile_id or batch.default_profile_id

    for file in files:
        filename = file.filename or "uploaded_batch_doc"
        ext = Path(filename).suffix.lower()
        if ext not in [".pdf", ".docx"]:
            raise HTTPException(status_code=400, detail=f"Formato no soportado para '{filename}'. Debe ser .pdf o .docx.")

        content_bytes = await file.read()
        file_size = len(content_bytes)

        if file_size > max_file_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo '{filename}' ({round(file_size/(1024*1024), 2)} MB) excede el tamaño máximo permitido por archivo ({config['max_file_size_mb']} MB)."
            )

        if current_total_bytes + file_size > max_total_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"El tamaño total del lote excede el límite máximo agregado permitido ({config['max_total_size_mb']} MB)."
            )

        current_total_bytes += file_size
        doc_id = str(uuid.uuid4())
        doc_dir = session_store.get_document_dir(batch.session_id, batch_id, doc_id)
        store_in_memory_session(doc_id, content_bytes)
        dest_file = os.path.join(doc_dir, f"{doc_id}_{filename}")
        shutil.copyfileobj(io.BytesIO(content_bytes), open(dest_file, "wb"))

        source_sha = calculate_file_sha256(dest_file)
        mime = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        doc_meta = DocumentMetadata(
            id=doc_id,
            session_id=batch.session_id,
            batch_id=batch_id,
            filename=filename,
            mime_type=mime,
            size_bytes=file_size,
            profile_id=chosen_profile,
            source_sha256=source_sha,
            status="queued"
        )

        session_store.documents[doc_id] = doc_meta
        metadata_store.document_created(doc_meta)
        session_store.doc_file_paths[doc_id] = {
            "source": dest_file,
            "preview_pdf": dest_file if ext == ".pdf" else None
        }
        batch.document_ids.append(doc_id)
        uploaded_docs.append(doc_meta.model_dump())

    batch.status = batch_service.compute_batch_status(batch)
    metadata_store.batch_updated(batch)
    for d in uploaded_docs:
        await batch_event_bus.publish(
            batch_id=batch_id,
            event_type="document_queued",
            status="queued",
            phase="queued",
            document_id=d["id"],
            payload={"filename": d["filename"], "profile": d["profile_id"], "sizeBytes": d["size_bytes"]}
        )
    return {"uploaded_count": len(uploaded_docs), "documents": uploaded_docs}

@api_router.patch("/batches/{batch_id}/documents/{doc_id}/profile")
async def update_batch_document_profile(batch_id: str, doc_id: str, payload: UpdateBatchDocumentProfilePayload):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    doc = session_store.documents.get(doc_id)
    if not doc or doc.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Documento no encontrado en este lote.")

    if doc.status not in ["queued", "uploaded", "awaiting_review"]:
        raise HTTPException(status_code=400, detail="No se puede cambiar el perfil de un documento en análisis o purgado.")

    doc.profile_id = payload.profile_id
    return doc.model_dump()

@api_router.delete("/batches/{batch_id}")
async def delete_batch_endpoint(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        if lifecycle_manager.is_batch_expired(batch_id):
            raise HTTPException(
                status_code=410,
                detail={"code": "RESOURCE_EXPIRED", "detail": "RESOURCE_EXPIRED"}
            )
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    await lifecycle_manager.delete_batch_now(batch_id, session_store, reason="manual_user_action")
    metadata_store.tombstone("batch", batch_id, "manual_user_action")
    return {"status": "deleted", "batch_id": batch_id}
async def remove_document_from_batch(batch_id: str, doc_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    if doc_id not in batch.document_ids:
        raise HTTPException(status_code=404, detail="Documento no pertenece al lote.")

    doc = session_store.documents.get(doc_id)
    if doc and doc.status in ["analyzing", "purging"]:
        raise HTTPException(status_code=400, detail="No se puede eliminar un documento que está en proceso.")

    batch.document_ids.remove(doc_id)
    session_store.cleanup_document(doc_id)
    metadata_store.tombstone("document", doc_id, "removed_from_batch")
    batch.status = batch_service.compute_batch_status(batch)
    metadata_store.batch_updated(batch)

    return {"status": "removed", "document_id": doc_id, "remaining": len(batch.document_ids)}

@api_router.post("/batches/{batch_id}/documents/{doc_id}/cancel")
async def cancel_batch_document(batch_id: str, doc_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch or doc_id not in batch.document_ids:
        raise HTTPException(status_code=404, detail="Documento no pertenece al lote.")

    doc = session_store.documents.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    # Clean partial output if any was created
    paths = session_store.doc_file_paths.get(doc_id, {})
    purged_path = paths.pop("purged", None)
    if purged_path and os.path.exists(purged_path):
        try:
            os.remove(purged_path)
        except Exception:
            pass

    doc.status = "cancelled"
    metadata_store.document_updated(doc)
    batch.status = batch_service.compute_batch_status(batch)
    return {"status": "cancelled", "document_id": doc_id}
    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="document_cancelled",
        status="cancelled",
        phase="cancelled",
        document_id=doc_id,
        payload={"documentId": doc_id}
    )

@api_router.post("/batches/{batch_id}/cancel")
async def cancel_entire_batch(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    batch.status = "cancelled"
    metadata_store.batch_updated(batch)
    for d_id in batch.document_ids:
        doc = session_store.documents.get(d_id)
        if doc and doc.status != "verified":
            doc.status = "cancelled"
            paths = session_store.doc_file_paths.get(d_id, {})
            purged_path = paths.pop("purged", None)
            if purged_path and os.path.exists(purged_path):
                try:
                    os.remove(purged_path)
                except Exception:
                    pass

    return {"status": "cancelled", "batch_id": batch_id}
    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="batch_status_changed",
        status="cancelled",
        phase="cancelled",
        payload={"message": "El lote completo ha sido cancelado por el usuario."}
    )

@api_router.post("/batches/{batch_id}/analyze")
async def start_batch_analysis(batch_id: str, payload: Optional[StartBatchAnalysisPayload] = None):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    if not batch.document_ids:
        raise HTTPException(status_code=400, detail="El lote no contiene documentos para analizar.")

    if payload and payload.custom_rules is not None:
        batch_service.set_batch_ruleset(
            batch_id, payload.custom_rules,
            ruleset_id=payload.ruleset_id or batch.ruleset_id,
            version=payload.ruleset_version or batch.ruleset_version
        )

    # Mark queued documents
    docs_to_analyze = []
    for d_id in batch.document_ids:
        d = session_store.documents.get(d_id)
        if d and d.status in ["queued", "uploaded", "error"]:
            d.status = "queued"
            docs_to_analyze.append(d.id)

    batch.status = "processing"

    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="batch_started",
        status="processing",
        phase="batch_analysis_started",
        payload={"analyzingCount": len(docs_to_analyze)}
    )
    # Concurrency-controlled execution using semaphore inside batch_service
    tasks = [batch_service.analyze_document_in_batch(doc_id, batch_id) for doc_id in docs_to_analyze]
    await asyncio.gather(*tasks, return_exceptions=True)

    batch_status_after_analysis = batch_service.compute_batch_status(batch)
    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="batch_status_changed",
        status=batch_status_after_analysis,
        phase="awaiting_review",
        payload={"batchStatus": batch_status_after_analysis}
    )
    batch.status = batch_service.compute_batch_status(batch)
    return await get_batch_details(batch_id)

@api_router.post("/batches/{batch_id}/purge")
async def start_batch_purge(batch_id: str, payload: Optional[StartBatchPurgePayload] = None):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    # Target documents: if payload provided, use that; otherwise all ready/review documents
    if payload and payload.document_ids:
        target_doc_ids = [d_id for d_id in payload.document_ids if d_id in batch.document_ids]
    else:
        target_doc_ids = []
        for d_id in batch.document_ids:
            doc = session_store.documents.get(d_id)
            if not doc or doc.status in ["verified", "cancelled", "error"]:
                continue
            # Safe purge: can purge if pending matches count == 0
            d_matches = list(session_store.matches.get(d_id, {}).values())
            pending_count = sum(1 for m in d_matches if m.status == "pending")
            if pending_count == 0:
                target_doc_ids.append(d_id)

    if not target_doc_ids:
        raise HTTPException(
            status_code=400,
            detail="No hay documentos listos para purgar (comprueba que no queden coincidencias en estado 'pending')."
        )

    batch.status = "processing"
    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="batch_status_changed",
        status="processing",
        phase="batch_purge_started",
        payload={"purgingCount": len(target_doc_ids)}
    )

    tasks = [batch_service.purge_document_in_batch(doc_id, batch_id) for doc_id in target_doc_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_status = batch_service.compute_batch_status(batch)
    batch.status = final_status
    await batch_event_bus.publish(
        batch_id=batch_id,
        event_type="batch_completed" if "completed" in final_status else "batch_status_changed",
        status=final_status,
        phase="completed" if "completed" in final_status else final_status,
        payload={"batchStatus": final_status}
    )

    return await get_batch_details(batch_id)

@api_router.get("/batches/{batch_id}/audit.json")
async def download_batch_audit_json(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    summary = batch_service.generate_batch_audit_summary(batch_id)
    batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
    json_path = os.path.join(batch_dir, "batch-audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return FileResponse(json_path, filename=f"anclora_batch_{batch_id}_audit.json", media_type="application/json")

@api_router.get("/batches/{batch_id}/audit.pdf")
async def download_batch_audit_pdf(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    summary = batch_service.generate_batch_audit_summary(batch_id)
    batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
    pdf_path = os.path.join(batch_dir, "batch-audit.pdf")
    audit_service.generate_batch_audit_pdf(summary, pdf_path)

    return FileResponse(pdf_path, filename=f"anclora_batch_{batch_id}_audit.pdf", media_type="application/pdf")

@api_router.get("/batches/{batch_id}/audit.csv")
async def download_batch_audit_csv_file(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    summary = batch_service.generate_batch_audit_summary(batch_id)
    batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
    csv_path = os.path.join(batch_dir, "batch-audit.csv")
    csv_content = generate_batch_audit_csv(summary)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)

    return FileResponse(csv_path, filename=f"anclora_batch_{batch_id}_audit.csv", media_type="text/csv; charset=utf-8")

@api_router.get("/batches/{batch_id}/audit-entities.csv")
async def download_batch_audit_entities_csv_file(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    summary = batch_service.generate_batch_audit_summary(batch_id)
    batch_dir = session_store.get_batch_dir(batch.session_id, batch_id)
    csv_path = os.path.join(batch_dir, "batch-audit-entities.csv")
    entities_csv_content = generate_batch_audit_entities_csv(summary, session_store)
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(entities_csv_content)

    return FileResponse(csv_path, filename=f"anclora_batch_{batch_id}_audit_entities.csv", media_type="text/csv; charset=utf-8")


@api_router.get("/batches/{batch_id}/download-zip")
async def download_batch_zip(batch_id: str):
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    zip_path = batch_service.build_batch_zip(batch_id)
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=500, detail="Error al generar archivo ZIP del lote.")

    return FileResponse(
        zip_path,
        filename=f"anclora-purgedoc-batch-{batch_id}.zip",
        media_type="application/zip"
    )

@api_router.get("/batches/{batch_id}/events")
async def stream_batch_events(
    batch_id: str,
    session_id: Optional[str] = None,
    last_event_id: Optional[int] = None
):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time batch progress.
    Validates batch and session ownership for strict isolation.
    Replays history if last_event_id is provided.
    Transmits standard SSE format:
      id: <sequence>
      event: <type>
      data: <json>
    """
    batch = session_store.batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    if session_id and batch.session_id != session_id:
        raise HTTPException(status_code=403, detail="Acceso denegado: el lote no pertenece a esta sesión.")

    queue = batch_event_bus.subscribe(batch_id, last_event_id=last_event_id)

    async def event_generator():
        try:
            # Emit initial connection acknowledgment
            init_event = {
                "eventId": f"init_{batch_id}",
                "sequence": 0,
                "batchId": batch_id,
                "type": "stream_connected",
                "status": batch.status,
                "phase": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "schemaVersion": 1,
                "payload": {"batchStatus": batch.status, "documentsCount": len(batch.document_ids)}
            }
            yield f"id: 0\nevent: stream_connected\ndata: {json.dumps(init_event)}\n\n"

            while True:
                try:
                    # Wait for next event or send heartbeat every 15 seconds
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if event is None:
                        # Sentinel for queue closure / cleanup
                        break

                    seq = event.get("sequence", 0)
                    ev_type = event.get("type", "message")
                    data_str = json.dumps(event)
                    yield f"id: {seq}\nevent: {ev_type}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat (no sensitive data)
                    hb = {
                        "type": "heartbeat",
                        "batchId": batch_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    yield f": heartbeat {json.dumps(hb)}\n\n"
        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected from batch {batch_id}")
        finally:
            batch_event_bus.unsubscribe(batch_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


app.include_router(api_router)
