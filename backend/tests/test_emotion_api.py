import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_analyze_heuristic_only():
    os.environ["ADV_EMOTION_ENABLE"] = "false"
    r = client.post("/api/emotion/analyze", json={"text":"I am sooo happy!!!"})
    assert r.status_code == 200
    data = r.json()
    assert "heuristic" in data
    assert "advanced" not in data  # advanced disabled
    h = data["heuristic"]
    assert h["elongated"] is True
    assert h["intensity"] >= 0.3


def test_advanced_when_enabled():
    os.environ["ADV_EMOTION_ENABLE"] = "true"
    r = client.post("/api/emotion/analyze", json={"text":"I am sooo happy!!!"})
    assert r.status_code == 200
    data = r.json()
    assert "heuristic" in data
    assert "advanced" in data
    adv = data["advanced"]
    assert adv.get("triggered") is True
    assert isinstance(adv.get("emotions"), dict)
    assert adv.get("top") is not None
    assert "confidence" in adv
    # gating: emoji may or may not appear depending on thresholds; just ensure key present
    assert "emoji" in adv


def test_toxicity_gate():
    os.environ["ADV_EMOTION_ENABLE"] = "true"
    r = client.post("/api/emotion/analyze", json={"text":"You are stupid and this sucks"})
    data = r.json()
    adv = data.get("advanced")
    assert adv
    if adv.get("top") == "toxic":
        assert adv.get("emoji") is None

