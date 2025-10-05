from fastapi.testclient import TestClient
from app.main import app
from app.services import ai_service
import uuid

client = TestClient(app)


def _signup():
    email = f"metrics_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/signup", json={"email": email, "password": "StrongPass123"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user_id"]


def test_metrics_endpoint_basic(monkeypatch):
    token, _ = _signup()
    headers = {"Authorization": f"Bearer {token}"}
    if hasattr(ai_service, "_INFER_PREFS_CACHE"):
        ai_service._INFER_PREFS_CACHE.clear()

    from app.services import metrics
    metrics.incr("inferred_prefs.source.compute")
    metrics.incr("inferred_prefs.detail.deep")

    resp = client.get("/api/debug/metrics", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "counters" in data
    counters = data["counters"]
    assert any(k.startswith("inferred_prefs.source") for k in counters.keys())
    assert any(k.startswith("inferred_prefs.detail") for k in counters.keys())