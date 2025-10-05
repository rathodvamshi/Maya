from app.services.emotion_service import build_persona_directive, EmotionResult

def test_persona_directive_tone_override():
    dummy = EmotionResult(emotion="happy", confidence=0.9, tone="playful", lead_emoji="😄", palette=["😄"])  # type: ignore[arg-type]
    directive = build_persona_directive(dummy, None, escalation=False, tone_override="concise")
    assert "User preference tone override" in directive
    assert "concise" in directive
