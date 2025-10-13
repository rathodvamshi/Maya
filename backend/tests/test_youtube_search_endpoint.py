from starlette.testclient import TestClient
import os

import pytest
from app.main import app
from app.config import settings
from app.security import get_current_active_user


def _dummy_user():
    return {"_id": "test-user-id", "email": "test@example.com"}


@pytest.mark.skip(reason="/api/youtube/search is now public (no auth required); this test is obsolete.")
def test_youtube_search_requires_auth():
    client = TestClient(app)
    resp = client.get("/api/youtube/search", params={"q": "react tutorial"})
    assert resp.status_code in (200, 503)


def test_youtube_search_503_when_no_api_key(monkeypatch):
    # Ensure key is not set both in env and in already-loaded settings object
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "YOUTUBE_API_KEY", None, raising=False)

    # Override auth to simulate logged-in user
    app.dependency_overrides[get_current_active_user] = _dummy_user
    try:
        client = TestClient(app)
        resp = client.get("/api/youtube/search", params={"q": "react tutorial"})
        assert resp.status_code == 503
        data = resp.json()
        assert data.get("error", {}).get("message") or data.get("detail")
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
