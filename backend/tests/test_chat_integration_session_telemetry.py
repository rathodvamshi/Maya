import time
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.database import db_client

client = TestClient(app)


def _signup(email: str, password: str):
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user_id"]

def _create_session(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    messages = [{"sender": "user", "text": "Hello there"}]
    resp = client.post("/api/sessions/", json=messages, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]

def test_session_chat_logs_session_id_in_interaction_events():
    # Ensure no leftover auth dependency overrides from other tests (preferences tests)
    from app.security import get_current_active_user as _gcu
    from app.main import app as _app
    _app.dependency_overrides.pop(_gcu, None)
    email = f"itest_{uuid.uuid4().hex[:8]}@example.com"
    token, user_id = _signup(email, "Secretp@ss1")
    session_id = _create_session(token)
    headers = {"Authorization": f"Bearer {token}"}

    # Send chat message
    chat_resp = client.post(f"/api/sessions/{session_id}/chat", json={"message": "What is the capital of France?"}, headers=headers)
    assert chat_resp.status_code == 200, chat_resp.text
    body = chat_resp.json()
    assert "assistant" in body.get("sender", "assistant") or body.get("sender") == "assistant"

    # Poll interaction_events for a short window (telemetry is synchronous so one attempt should work)
    col = db_client.db["interaction_events"]
    found = col.find_one({"session_id": session_id})
    assert found is not None, "Expected interaction event with session_id not found"
    assert found.get("user_id") == user_id
    assert found.get("complexity") in {"factual", "explanatory", "general"}
