import os
import io
import sys
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
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures

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

# ----------------- Schemas -----------------
class SessionResponse(BaseModel):
    session_id: str
    status: str

class MatchUpdatePayload(BaseModel):
    status: str # accepted | rejected | pending

class BulkMatchUpdatePayload(BaseModel):
    match_ids: Optional[List[str]] = None
    all_visible: bool = False
    status: str # accepted | rejected

class PurgeResponse(BaseModel):
    document_id: str
    status: str # verified | verification_failed
    verification_passed: bool
    failures: List[str]
    details: Dict[str, Any]
    output_sha256: Optional[str] = None
    audit_id: str

# ----------------- Routes -----------------

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "product": "Anclora Purgedoc",
        "version": "1.0.0",
        "profiles": list(detection_engine.profiles.keys()),
        "ner_models_loaded": list(detection_engine.nlp_models.keys()),
        "privacy": "100% Local / Zero Remote LLM Calls"
    }

@api_router.post("/sessions", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    session_store.create_session(session_id)
    return {"session_id": session_id, "status": "active"}

@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    session_store.cleanup_session(session_id)
    return {"status": "deleted", "session_id": session_id}

@api_router.get("/profiles")
async def get_profiles():
    """Returns available vertical profiles for upload UI"""
    results = []
    for pid, pdata in detection_engine.profiles.items():
        results.append({
            "id": pid,
            "name_es": pdata.get("name_es", pid),
            "name_en": pdata.get("name_en", pid),
            "version": pdata.get("version", "1.0.0"),
            "description": pdata.get("description", ""),
            "rules_count": len(pdata.get("regex_rules", []))
        })
    return results

# Internal session byte cache to avoid permanent pod upload storage
_SESSION_RAW_BYTES: Dict[str, bytes] = {}

def store_in_memory_session(doc_id: str, data: bytes):
    _SESSION_RAW_BYTES[doc_id] = data

def get_in_memory_session(doc_id: str) -> bytes:
    return _SESSION_RAW_BYTES.get(doc_id, b"")

@api_router.post("/sessions/{session_id}/documents")
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    profile_id: str = Form("rrhh")
):
    session_dir = session_store.get_session_dir(session_id)
    doc_id = str(uuid.uuid4())
    
    # Validate extension and mime type
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

    # Temporary staging path inside ephemeral session dir for PyMuPDF/docx processor
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
    session_store.doc_file_paths[doc_id] = {
        "source": dest_file,
        "preview_pdf": dest_file if ext == ".pdf" else None
    }

    return doc_meta.model_dump()

@api_router.post("/fixtures/{fixture_name}/load")
async def load_synthetic_fixture(fixture_name: str, session_id: str, profile_id: Optional[str] = None):
    """Dev/QA endpoint for instant 1-click test file loading"""
    session_dir = session_store.get_session_dir(session_id)
    doc_id = str(uuid.uuid4())
    
    mapping = {
        "rrhh": ("sample_rrhh_payroll.pdf", "rrhh", "application/pdf"),
        "legal": ("sample_legal_contract.docx", "legal", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "soporte": ("sample_soporte_incident.pdf", "soporte", "application/pdf")
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
    session_store.doc_file_paths[doc_id] = {
        "source": dest_file,
        "preview_pdf": dest_file if dest_file.endswith(".pdf") else None
    }
    return doc_meta.model_dump()

@api_router.post("/documents/{doc_id}/analyze")
async def analyze_document(doc_id: str):
    """Executes local parsing, text extraction, NER & Regex detection"""
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    doc_meta = session_store.documents[doc_id]
    paths = session_store.doc_file_paths[doc_id]
    source_file = paths["source"]
    session_dir = session_store.get_session_dir(doc_meta.session_id)

    doc_meta.status = "analyzing"

    if doc_meta.mime_type == "application/pdf":
        pages_content, page_count, has_text = document_processor.extract_pdf_content(source_file)
        doc_meta.page_count = page_count
        doc_meta.has_text_layer = has_text
        paths["preview_pdf"] = source_file
    else: # DOCX
        pages_content, page_count, has_text = document_processor.extract_docx_content(source_file)
        doc_meta.page_count = page_count
        doc_meta.has_text_layer = has_text
        # Generate local headless PDF representation for visual review
        preview_pdf = document_processor.convert_docx_to_preview_pdf(source_file, session_dir)
        paths["preview_pdf"] = preview_pdf

    if not has_text:
        doc_meta.status = "error"
        doc_meta.error_message = "El documento no contiene capa de texto seleccionable. Requiere OCR local (no soportado en esta versión)."
        raise HTTPException(status_code=422, detail=doc_meta.error_message)

    # Run detection
    matches = detection_engine.analyze_document_content(
        doc_id=doc_id,
        profile_id=doc_meta.profile_id,
        pages_content=pages_content
    )

    # Store matches in memory
    session_store.matches[doc_id] = {m.id: m for m in matches}
    doc_meta.status = "ready_for_review"

    return {
        "document": doc_meta.model_dump(),
        "matches_count": len(matches),
        "matches": [m.to_public_dict() for m in matches]
    }

@api_router.get("/documents/{doc_id}/matches")
async def get_document_matches(doc_id: str):
    if doc_id not in session_store.documents:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    
    matches_dict = session_store.matches.get(doc_id, {})
    return [m.to_public_dict() for m in matches_dict.values()]

@api_router.patch("/matches/{match_id}")
async def update_match_status(match_id: str, payload: MatchUpdatePayload):
    """Update single match decision: accepted | rejected | pending"""
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
    """Batch accept or reject matches"""
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
    """Returns exact rendered PNG of PDF page for synchronized high-precision canvas review"""
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
    1. Filter accepted matches
    2. Apply physical content redaction to PDF or OOXML
    3. Reopen generated file and verify absence of values
    4. Produce Cryptographic Audit Manifest & Certificate PDF
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
    purged_filename = f"purged_{doc_meta.filename}"
    purged_path = os.path.join(session_dir, purged_filename)

    # 1. Real Redaction
    if ext == ".pdf":
        redaction_res = redaction_engine.purge_pdf(source_file, purged_path, approved_matches)
        # 2. Automated Verification
        passed, failures, v_details = verification_engine.verify_pdf(purged_path, approved_matches)
    else: # DOCX
        redaction_res = redaction_engine.purge_docx(source_file, purged_path, approved_matches)
        # 2. Automated Verification
        passed, failures, v_details = verification_engine.verify_docx(purged_path, approved_matches)

    # Update match statuses
    for m in approved_matches:
        m.status = "applied" if passed else "verification_failed"

    output_sha = calculate_file_sha256(purged_path) if os.path.exists(purged_path) else None
    doc_meta.output_filename = purged_filename
    doc_meta.output_sha256 = output_sha
    doc_meta.status = "verified" if passed else "verification_failed"

    paths["purged"] = purged_path

    # 3. Generate Audit Records
    audit_json = audit_service.generate_audit_json(doc_meta, all_matches, passed, v_details)
    audit_json_path = os.path.join(session_dir, f"audit_{doc_id}.json")
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump(audit_json, f, indent=2, ensure_ascii=False)
    paths["audit_json"] = audit_json_path

    audit_pdf_path = os.path.join(session_dir, f"audit_{doc_id}.pdf")
    audit_service.generate_audit_pdf(audit_json, audit_pdf_path)
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
    """Downloads purged file only if verified or requested"""
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

# Include Router
app.include_router(api_router)
