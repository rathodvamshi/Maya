import re
from app.services.emotion_service import detect_emotion, enrich_with_emojis, build_persona_directive, EmotionResult, count_emojis


def test_detect_emotion_sad():
    res = detect_emotion("I feel really down and sad today")
    assert res.emotion == "sad"
    assert res.confidence > 0.5


def test_detect_emotion_neutral():
    res = detect_emotion("What is the weather like?")
    assert res.emotion in ("neutral",)  # heuristic may only return neutral here


def test_enrich_with_emojis_caps():
    res = detect_emotion("I am so excited and thrilled!")
    base = "This is great news. I'm happy we made progress. Let's keep going."
    enriched = enrich_with_emojis(base, res, max_new=3, hard_cap=5)
    # Should not exceed hard cap
    assert count_emojis(enriched) <= 5


def test_no_over_enrichment_when_already_many():
    res = detect_emotion("I am happy")
    base = "😀 😀 😀 😀 Already lots of emojis here"
    enriched = enrich_with_emojis(base, res, max_new=4, hard_cap=6)
    # Should not add because cap almost reached
    assert count_emojis(enriched) <= 6


def test_persona_directive_escalation():
    dummy = EmotionResult(emotion="sad", confidence=0.8, tone="supportive", lead_emoji="😔", palette=["😔"])  # type: ignore[arg-type]
    directive = build_persona_directive(dummy, "You enjoy cricket", escalation=True)
    assert "increase empathy".lower().split()[0] in directive.lower() or "increase" in directive.lower()
    assert "cricket" in directive


def test_detect_emotion_via_emoji_sad():
    res = detect_emotion("Just this 😢")
    assert res.emotion == "sad"
    assert res.confidence >= 0.5


def test_detect_emotion_via_emoji_happy():
    res = detect_emotion("😊")
    assert res.emotion == "happy"


def test_detect_emotion_via_emoji_excited():
    res = detect_emotion("Launch day 🚀")
    assert res.emotion in ("excited", "happy")  # allow excited primary


def test_detect_emotion_via_emoji_angry():
    res = detect_emotion("Ugh 😡")
    assert res.emotion == "angry"


def test_detect_emotion_via_emoji_anxious():
    res = detect_emotion("Feeling this 😬")
    assert res.emotion == "anxious"
