"""Health endpoint: DB check is opt-in (?deep=1) so Neon can scale to zero.

No real database is used: the metadata store is replaced by a stub.
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend import server


class _StubStore:
    def __init__(self, enabled=True, fail=False):
        self.enabled = enabled
        self.fail = fail
        self.calls = 0

    def health_check(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("db down")
        return True


@pytest.fixture(autouse=True)
def local_checks_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "TEMP_ROOT", str(tmp_path))
    monkeypatch.setattr(server.pytesseract, "get_tesseract_version", lambda: "5")
    monkeypatch.setattr(server.pytesseract, "get_languages", lambda config="": ["spa", "eng"])
    monkeypatch.setattr(server.detection_engine, "nlp_models", {"es": object(), "en": object()})


def _call(**kwargs):
    return asyncio.run(server.health_check(**kwargs))


def test_light_mode_does_not_touch_database(monkeypatch):
    store = _StubStore(enabled=True, fail=True)  # would fail if called
    monkeypatch.setattr(server, "metadata_store", store)
    data = _call()
    assert store.calls == 0
    assert data["status"] == "healthy"
    assert data["checks"]["database"] == "skipped"


def test_deep_mode_checks_database(monkeypatch):
    store = _StubStore(enabled=True)
    monkeypatch.setattr(server, "metadata_store", store)
    data = _call(deep=True)
    assert store.calls == 1
    assert data["checks"]["database"] is True


def test_deep_mode_returns_503_when_database_fails(monkeypatch):
    store = _StubStore(enabled=True, fail=True)
    monkeypatch.setattr(server, "metadata_store", store)
    with pytest.raises(HTTPException) as exc:
        _call(deep=True)
    assert exc.value.status_code == 503
    assert exc.value.detail["checks"]["database"] is False


def test_not_configured_database_is_reported(monkeypatch):
    monkeypatch.setattr(server, "metadata_store", _StubStore(enabled=False))
    assert _call(deep=True)["checks"]["database"] == "not_configured"
