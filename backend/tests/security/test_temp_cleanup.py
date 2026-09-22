import pytest
import os
import shutil
import uuid
import time
from pathlib import Path

from backend.services.sessions import session_store, TEMP_ROOT
from backend.services.documents import document_processor
from backend.services.detection import detection_engine
from backend.services.redaction import redaction_engine
from backend.fixtures_generator import FIXTURES_DIR

def test_ephemeral_session_temp_cleanup():
    """
    5. TEMPORAL ARTIFACTS CLEANUP:
    - Creates a dedicated session
    - Loads files, runs OCR, generates previews, purged outputs & audits
    - Explicitly triggers session_store.cleanup_session(session_id)
    - Verifies that /tmp/anclora-purgedoc/{session_id} is completely deleted
    """
    sec_session_id = f"sec_test_session_{uuid.uuid4().hex[:8]}"
    session_dir = session_store.create_session(sec_session_id)
    assert os.path.exists(session_dir)

    test_pdf = os.path.join(session_dir, "confidential_payroll_secret.pdf")
    shutil.copyfile(str(FIXTURES_DIR / "sample_rrhh_payroll.pdf"), test_pdf)

    preview_png = os.path.join(session_dir, "preview_page_1.png")
    with open(preview_png, "wb") as f:
        f.write(document_processor.render_pdf_page_image(test_pdf, 1))

    purged_pdf = os.path.join(session_dir, "purged_confidential.pdf")
    shutil.copyfile(test_pdf, purged_pdf)

    assert os.path.exists(test_pdf)
    assert os.path.exists(preview_png)
    assert os.path.exists(purged_pdf)

    session_store.cleanup_session(sec_session_id)

    assert not os.path.exists(session_dir), f"Directory {session_dir} was not deleted!"
    assert sec_session_id not in session_store.sessions
    assert not any(doc.session_id == sec_session_id for doc in session_store.documents.values())

def test_expired_sessions_automatic_cleanup():
    """Verifies that cleanup_expired() deletes sessions exceeding TTL"""
    old_session_id = f"old_session_{uuid.uuid4().hex[:8]}"
    old_dir = session_store.create_session(old_session_id)
    
    session_store.sessions[old_session_id]["last_active"] = time.time() - 999999

    session_store.cleanup_expired()
    assert not os.path.exists(old_dir)
    assert old_session_id not in session_store.sessions
