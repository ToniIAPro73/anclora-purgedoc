import os
import io
import json
import zipfile
import pytest
import asyncio
from pathlib import Path
from backend.services.sessions import session_store
from backend.services.batch import batch_service, get_batch_config
from backend.services.rules import CustomRule
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata

@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    generate_all_fixtures()

def test_batch_single_document_flow():
    """Verify batch with 1 document behaves deterministically and reaches completed_verified"""
    session_id = "test_sess_batch_single"
    session_store.create_session(session_id)
    
    # 1. Create batch metadata
    from backend.models import BatchMetadata
    batch = BatchMetadata(id="b_single", session_id=session_id, default_profile_id="rrhh")
    session_store.batches["b_single"] = batch
    
    # 2. Add 1 PDF document
    doc_id = "doc_single_1"
    doc_dir = session_store.get_document_dir(session_id, "b_single", doc_id)
    src_fixture = os.path.join(FIXTURES_DIR, "sample_rrhh_payroll.pdf")
    dest_file = os.path.join(doc_dir, "sample_rrhh_payroll.pdf")
    with open(src_fixture, "rb") as f_in, open(dest_file, "wb") as f_out:
        f_out.write(f_in.read())
        
    doc_meta = DocumentMetadata(
        id=doc_id, session_id=session_id, batch_id="b_single",
        filename="sample_rrhh_payroll.pdf", mime_type="application/pdf",
        size_bytes=os.path.getsize(dest_file), profile_id="rrhh",
        source_sha256="fake_sha", status="queued"
    )
    session_store.documents[doc_id] = doc_meta
    session_store.doc_file_paths[doc_id] = {"source": dest_file}
    batch.document_ids.append(doc_id)
    
    # 3. Analyze
    asyncio.run(batch_service.analyze_document_in_batch(doc_id, "b_single"))
    assert doc_meta.status == "awaiting_review"
    assert doc_id in session_store.matches
    matches = list(session_store.matches[doc_id].values())
    assert len(matches) > 0
    
    # Accept all
    for m in matches:
        m.status = "accepted"
        
    # 4. Purge
    passed = asyncio.run(batch_service.purge_document_in_batch(doc_id, "b_single"))
    assert passed is True
    assert doc_meta.status == "verified"
    
    # Batch status must be completed_verified
    b_status = batch_service.compute_batch_status(batch)
    assert b_status == "completed_verified"
    
    # 5. Summary and ZIP
    summary = batch_service.generate_batch_audit_summary("b_single")
    assert summary["batch_status"] == "completed_verified"
    assert summary["metrics"]["verified"] == 1
    assert summary["metrics"]["verification_failed"] == 0
    
    zip_path = batch_service.build_batch_zip("b_single")
    assert os.path.exists(zip_path)
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "batch-audit.json" in names
        assert "batch-audit.pdf" in names
        assert any(n.startswith("documents/") for n in names)
        assert any(n.startswith("audits/") for n in names)
        # Verify NO original files leaked
        for n in names:
            assert not n.startswith("source")
            assert ".." not in n  # No path traversal

def test_batch_mixed_pdf_and_docx_with_different_profiles():
    """Verify mixed batch (PDF + DOCX) with distinct per-document profiles and custom rules"""
    session_id = "test_sess_batch_mixed"
    session_store.create_session(session_id)
    
    from backend.models import BatchMetadata
    batch = BatchMetadata(id="b_mixed", session_id=session_id, default_profile_id="rrhh")
    session_store.batches["b_mixed"] = batch
    
    # Custom rule for batch
    c_rule = CustomRule(
        id="crule_proj", name="Project Code", entity_type="PROJECT_ID",
        pattern=r"PRJ-[A-Z0-9]{4}", profiles=["rrhh", "legal"]
    )
    batch_service.set_batch_ruleset("b_mixed", [c_rule])
    
    # Doc 1: PDF (rrhh)
    d1_id = "doc_m_pdf"
    d1_dir = session_store.get_document_dir(session_id, "b_mixed", d1_id)
    d1_file = os.path.join(d1_dir, "doc1.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_rrhh_payroll.pdf"), "rb") as fi, open(d1_file, "wb") as fo:
        fo.write(fi.read())
    d1_meta = DocumentMetadata(
        id=d1_id, session_id=session_id, batch_id="b_mixed", filename="doc1.pdf",
        mime_type="application/pdf", size_bytes=os.path.getsize(d1_file),
        profile_id="rrhh", source_sha256="sha1", status="queued"
    )
    session_store.documents[d1_id] = d1_meta
    session_store.doc_file_paths[d1_id] = {"source": d1_file}
    batch.document_ids.append(d1_id)
    
    # Doc 2: DOCX (legal)
    d2_id = "doc_m_docx"
    d2_dir = session_store.get_document_dir(session_id, "b_mixed", d2_id)
    d2_file = os.path.join(d2_dir, "doc2.docx")
    with open(os.path.join(FIXTURES_DIR, "sample_legal_contract.docx"), "rb") as fi, open(d2_file, "wb") as fo:
        fo.write(fi.read())
    d2_meta = DocumentMetadata(
        id=d2_id, session_id=session_id, batch_id="b_mixed", filename="doc2.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=os.path.getsize(d2_file), profile_id="legal", source_sha256="sha2", status="queued"
    )
    session_store.documents[d2_id] = d2_meta
    session_store.doc_file_paths[d2_id] = {"source": d2_file}
    batch.document_ids.append(d2_id)
    
    # Analyze both
    async def run_analyses():
        await asyncio.gather(
            batch_service.analyze_document_in_batch(d1_id, "b_mixed"),
            batch_service.analyze_document_in_batch(d2_id, "b_mixed")
        )
    asyncio.run(run_analyses())
    
    assert d1_meta.status == "awaiting_review"
    assert d2_meta.status == "awaiting_review"
    
    # Accept matches
    for m in session_store.matches[d1_id].values():
        m.status = "accepted"
    for m in session_store.matches[d2_id].values():
        m.status = "accepted"
        
    # Purge both
    async def run_purges():
        return await asyncio.gather(
            batch_service.purge_document_in_batch(d1_id, "b_mixed"),
            batch_service.purge_document_in_batch(d2_id, "b_mixed")
        )
    results = asyncio.run(run_purges())
    assert results == [True, True]
    assert d1_meta.status == "verified"
    assert d2_meta.status == "verified"
    assert batch_service.compute_batch_status(batch) == "completed_verified"

def test_batch_partial_failure_and_isolation():
    """
    CRITICAL REQUIREMENT:
    Document A -> verified
    Document B -> corrupt / error / failed
    Batch must be 'completed_with_errors' and NEVER 'completed_verified'.
    ZIP must ONLY contain Document A in documents/. Never Document B!
    """
    session_id = "test_sess_batch_fail"
    session_store.create_session(session_id)
    
    from backend.models import BatchMetadata
    batch = BatchMetadata(id="b_fail", session_id=session_id, default_profile_id="rrhh")
    session_store.batches["b_fail"] = batch
    
    # Good Doc A (PDF)
    da_id = "doc_good_a"
    da_dir = session_store.get_document_dir(session_id, "b_fail", da_id)
    da_file = os.path.join(da_dir, "good.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_soporte_incident.pdf"), "rb") as fi, open(da_file, "wb") as fo:
        fo.write(fi.read())
    da_meta = DocumentMetadata(
        id=da_id, session_id=session_id, batch_id="b_fail", filename="good.pdf",
        mime_type="application/pdf", size_bytes=os.path.getsize(da_file),
        profile_id="soporte", source_sha256="sha_good", status="queued"
    )
    session_store.documents[da_id] = da_meta
    session_store.doc_file_paths[da_id] = {"source": da_file}
    batch.document_ids.append(da_id)
    
    # Corrupted Doc B (corrupt text / invalid PDF bytes)
    db_id = "doc_bad_b"
    db_dir = session_store.get_document_dir(session_id, "b_fail", db_id)
    db_file = os.path.join(db_dir, "corrupt.pdf")
    with open(db_file, "wb") as fo:
        fo.write(b"%PDF-1.4 corrupt content that cannot be parsed 00000")
    db_meta = DocumentMetadata(
        id=db_id, session_id=session_id, batch_id="b_fail", filename="corrupt.pdf",
        mime_type="application/pdf", size_bytes=len(b"%PDF-1.4 corrupt"),
        profile_id="soporte", source_sha256="sha_bad", status="queued"
    )
    session_store.documents[db_id] = db_meta
    session_store.doc_file_paths[db_id] = {"source": db_file}
    batch.document_ids.append(db_id)
    
    # Analyze both
    async def run_analyses():
        await asyncio.gather(
            batch_service.analyze_document_in_batch(da_id, "b_fail"),
            batch_service.analyze_document_in_batch(db_id, "b_fail")
        )
    asyncio.run(run_analyses())
    
    # Doc A succeeds analysis, Doc B fails
    assert da_meta.status == "awaiting_review"
    assert db_meta.status == "error"
    
    # Purge Doc A
    for m in session_store.matches[da_id].values():
        m.status = "accepted"
    passed_a = asyncio.run(batch_service.purge_document_in_batch(da_id, "b_fail"))
    assert passed_a is True
    assert da_meta.status == "verified"
    
    # Batch status MUST be completed_with_errors
    batch_status = batch_service.compute_batch_status(batch)
    assert batch_status == "completed_with_errors"
    assert batch_status != "completed_verified"
    
    # Verify ZIP contains ONLY Doc A, NEVER Doc B in documents/
    zip_path = batch_service.build_batch_zip("b_fail")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        doc_files = [n for n in names if n.startswith("documents/")]
        assert len(doc_files) == 1
        assert "purged_good.pdf" in doc_files[0]
        assert not any("corrupt" in n for n in doc_files)
        
    # Check Batch Audit JSON records error for Doc B without exposing secrets
    summary = batch_service.generate_batch_audit_summary("b_fail")
    assert summary["batch_status"] == "completed_with_errors"
    assert summary["metrics"]["verified"] == 1
    assert summary["metrics"]["error"] == 1

def test_batch_cancellation_and_cleanup():
    """Verify cancellation leaves no dangling outputs and cleanup wipes directory correctly"""
    session_id = "test_sess_batch_cancel"
    session_store.create_session(session_id)
    
    from backend.models import BatchMetadata
    batch = BatchMetadata(id="b_cancel", session_id=session_id, default_profile_id="rrhh")
    session_store.batches["b_cancel"] = batch
    
    d_id = "doc_to_cancel"
    d_dir = session_store.get_document_dir(session_id, "b_cancel", d_id)
    d_file = os.path.join(d_dir, "cancel.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_soporte_incident.pdf"), "rb") as fi, open(d_file, "wb") as fo:
        fo.write(fi.read())
        
    d_meta = DocumentMetadata(
        id=d_id, session_id=session_id, batch_id="b_cancel", filename="cancel.pdf",
        mime_type="application/pdf", size_bytes=os.path.getsize(d_file),
        profile_id="soporte", source_sha256="sha_cancel", status="queued"
    )
    session_store.documents[d_id] = d_meta
    session_store.doc_file_paths[d_id] = {"source": d_file}
    batch.document_ids.append(d_id)
    
    # Cancel doc
    paths = session_store.doc_file_paths.get(d_id, {})
    d_meta.status = "cancelled"
    assert batch_service.compute_batch_status(batch) == "completed_with_errors"
    
    # Cleanup batch
    session_store.cleanup_batch("b_cancel")
    assert "b_cancel" not in session_store.batches
    assert d_id not in session_store.documents
    assert not os.path.exists(os.path.join(session_store.get_session_dir(session_id), "b_cancel"))

def test_batch_zip_slip_and_path_traversal_protection():
    """Verify ZIP generator rejects path traversal and sanitizes filenames"""
    from backend.models import BatchMetadata
    session_id = "test_sess_zip_slip"
    session_store.create_session(session_id)
    
    batch = BatchMetadata(id="b_slip", session_id=session_id, default_profile_id="rrhh")
    session_store.batches["b_slip"] = batch
    
    # Add doc with suspicious filename
    d_id = "doc_slip"
    d_dir = session_store.get_document_dir(session_id, "b_slip", d_id)
    d_file = os.path.join(d_dir, "purged_suspicious.pdf")
    with open(d_file, "wb") as f:
        f.write(b"%PDF-1.4 dummy safe content")
        
    d_meta = DocumentMetadata(
        id=d_id, session_id=session_id, batch_id="b_slip",
        filename="../../../etc/passwd", mime_type="application/pdf",
        size_bytes=len(b"%PDF-1.4 dummy safe content"), profile_id="rrhh",
        source_sha256="sha_safe", status="verified", output_filename="purged_suspicious.pdf"
    )
    session_store.documents[d_id] = d_meta
    session_store.doc_file_paths[d_id] = {
        "source": d_file,
        "purged": d_file
    }
    batch.document_ids.append(d_id)
    
    zip_path = batch_service.build_batch_zip("b_slip")
    assert os.path.exists(zip_path)
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # Guarantee no path traversal in any entry
            assert not info.filename.startswith("/")
            assert ".." not in info.filename
            assert "\\" not in info.filename

def test_batch_concurrency_limit_enforcement():
    """Verify semaphore enforces BATCH_MAX_CONCURRENT_DOCUMENTS limit"""
    config = get_batch_config()
    max_c = config["max_concurrent"]
    assert max_c >= 1
    
    sem = batch_service.get_semaphore("test_concurrency_batch")
    assert sem._value == max_c
