from fastapi.testclient import TestClient
from app.main import app
from app.database import db_client
import uuid

client = TestClient(app)


def signup(email: str, password: str):
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"], data["user_id"]


def test_debug_preferences_endpoint():
    email = f"dbg_{uuid.uuid4().hex[:8]}@example.com"
    token, user_id = signup(email, "StrongP@ss12")
    headers = {"Authorization": f"Bearer {token}"}

    # Trigger a chat to create a telemetry + behavior entry
    session_resp = client.post("/api/sessions/", json=[{"sender": "user", "text": "Hello"}], headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    chat_resp = client.post(f"/api/sessions/{session_id}/chat", json={"message": "Explain the difference between RAM and storage"}, headers=headers)
    assert chat_resp.status_code == 200

    # Call debug endpoint
    dbg = client.get(f"/api/debug/preferences/{user_id}", headers=headers)
    assert dbg.status_code == 200
    payload = dbg.json()
    assert "inferred" in payload and "raw" in payload
    assert isinstance(payload["inferred"], dict)
    # raw may be empty if Redis unavailable; allow empty structure
    assert isinstance(payload["raw"], dict)
