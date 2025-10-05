from fastapi.testclient import TestClient
from app.main import app
import uuid

client = TestClient(app)

def _signup():
    email = f"prefs_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/signup", json={"email": email, "password": "Secretp@ss1"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["user_id"], email


def test_set_and_get_preferences():
    token, user_id, email = _signup()
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/user/preferences", json={"enable_emojis": True, "enable_emotion_persona": False, "tone": "fun"}, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updated"]["emoji"] == "on"
    assert data["updated"]["emotion_persona"] == "off"
    assert data["updated"]["tone"] == "playful"  # fun normalized to playful

    r2 = client.get("/api/user/preferences", headers=headers)
    assert r2.status_code == 200
    eff = r2.json()["effective"]
    assert eff["emoji"] == "on"
    assert eff["emotion_persona"] == "off"
    assert eff["tone"] == "playful"


def test_reject_invalid_tone():
    token, user_id, email = _signup()
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/user/preferences", json={"tone": "aggressive"}, headers=headers)
    assert r.status_code == 400
