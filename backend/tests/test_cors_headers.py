from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
ALLOWED_ORIGIN = "http://localhost:3000"


def test_cors_header_on_success_root():
    r = client.get("/", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert r.headers.get("x-debug-cors") == "1"


def test_cors_header_on_404():
    r = client.get("/nonexistent-route-xyz", headers={"Origin": ALLOWED_ORIGIN})
    assert r.status_code == 404
    # Final enforcer middleware should still add the header
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_cors_preflight_options_chat_new():
    r = client.options("/api/chat/new", headers={
        "Origin": ALLOWED_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization"
    })
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert "Access-Control-Allow-Methods" in r.headers
