import pytest
import os
import shutil
from pathlib import Path
from backend.services.sessions import session_store
from backend.services.detection import detection_engine
from backend.services.documents import document_processor
from backend.services.redaction import redaction_engine
from backend.services.verification import verification_engine
from backend.services.audit import audit_service
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata, MatchItem, calculate_file_sha256

@pytest.fixture(scope="session", autouse=True)
def setup_fixtures():
    generate_all_fixtures()

def test_health_and_profiles():
    assert "rrhh" in detection_engine.profiles
    assert "legal" in detection_engine.profiles
    assert "soporte" in detection_engine.profiles
    assert len(detection_engine.nlp_models) > 0

def test_pdf_extraction_detection_purge_and_verification():
    # 1. Load HR PDF
    hr_pdf = FIXTURES_DIR / "sample_rrhh_payroll.pdf"
    assert hr_pdf.exists()
    
    pages_content, page_count, has_text, is_scanned = document_processor.extract_pdf_content(str(hr_pdf))
    assert page_count >= 1
    assert has_text is True
    assert is_scanned is False

    # 2. Detect with RRHH Profile
    doc_id = "test_doc_hr"
    matches = detection_engine.analyze_document_content(doc_id, "rrhh", pages_content)
    assert len(matches) > 0
    
    # Check that DNI, Email and Name were detected
    found_types = {m.entity_type for m in matches}
    assert "DNI_NIE_NIF" in found_types or "EMAIL" in found_types or "PERSON" in found_types
    
    # Check no raw text in public dict
    pub_dict = matches[0].to_public_dict()
    assert "raw_text" not in pub_dict
    assert "original_text_hash" in pub_dict

    # 3. Approve matches
    approved = []
    for m in matches:
        if "12345678Z" in m.raw_text or "laura.martinez@example.test" in m.raw_text:
            m.status = "accepted"
            approved.append(m)

    assert len(approved) >= 1

    # 4. Redact PDF
    out_pdf = FIXTURES_DIR / "test_purged_hr.pdf"
    redact_res = redaction_engine.purge_pdf(str(hr_pdf), str(out_pdf), approved, is_scanned=False)
    assert redact_res["redactions_applied"] >= 1

    # 5. Verify PDF: Must be completely absent from text layer and metadata
    verified, failures, details = verification_engine.verify_pdf(str(out_pdf), approved, is_scanned=False)
    assert verified is True, f"Verification failed with: {failures}"
    assert details["values_verified_absent"] >= len(approved)

    # 6. Audit report generation
    doc_meta = DocumentMetadata(
        id=doc_id,
        session_id="test_session",
        filename="sample_rrhh_payroll.pdf",
        mime_type="application/pdf",
        size_bytes=os.path.getsize(str(hr_pdf)),
        profile_id="rrhh",
        source_sha256=calculate_file_sha256(str(hr_pdf)),
        output_sha256=calculate_file_sha256(str(out_pdf)),
        status="verified"
    )
    audit_json = audit_service.generate_audit_json(doc_meta, matches, verified, details)
    assert audit_json["status"] == "verified"
    assert "12345678Z" not in str(audit_json["items"]) # Privacy guarantee
    
    audit_pdf = FIXTURES_DIR / "test_audit_hr.pdf"
    audit_service.generate_audit_pdf(audit_json, str(audit_pdf))
    assert audit_pdf.exists()
    assert os.path.getsize(str(audit_pdf)) > 1000

    # Cleanup
    if out_pdf.exists():
        out_pdf.unlink()
    if audit_pdf.exists():
        audit_pdf.unlink()

def test_docx_extraction_detection_purge_and_verification():
    # 1. Load Legal DOCX
    legal_docx = FIXTURES_DIR / "sample_legal_contract.docx"
    assert legal_docx.exists()

    pages_content, page_count, has_text = document_processor.extract_docx_content(str(legal_docx))
    assert has_text is True

    # 2. Detect with Legal profile
    doc_id = "test_doc_legal"
    matches = detection_engine.analyze_document_content(doc_id, "legal", pages_content)
    assert len(matches) > 0

    # Approve match for DNI / CIF / Email
    approved = []
    for m in matches:
        if any(target in m.raw_text for target in ["87654321B", "carlos.fernandez@example.test", "A12345678"]):
            m.status = "accepted"
            approved.append(m)

    assert len(approved) >= 1

    # 3. Purge DOCX
    out_docx = FIXTURES_DIR / "test_purged_legal.docx"
    redaction_engine.purge_docx(str(legal_docx), str(out_docx), approved)
    assert out_docx.exists()

    # 4. Verify absence in OOXML
    verified, failures, details = verification_engine.verify_docx(str(out_docx), approved)
    assert verified is True, f"DOCX verification failed: {failures}"
    assert details["values_verified_absent"] >= len(approved)

    if out_docx.exists():
        out_docx.unlink()
