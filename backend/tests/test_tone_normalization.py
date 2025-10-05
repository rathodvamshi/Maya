from app.services.emotion_service import build_persona_directive, EmotionResult


def test_build_persona_with_override_long():
    dummy = EmotionResult(emotion="neutral", confidence=0.1, tone="neutral", lead_emoji="🙂", palette=["🙂"])  # type: ignore[arg-type]
    directive = build_persona_directive(dummy, None, tone_override="playful")
    assert "playful" in directive.lower()
