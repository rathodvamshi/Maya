from app.services.ai_service import append_suggestions_if_missing, SUGGESTION_PREFIX

BASE_ANSWER = "The capital of Japan is Tokyo."
QUESTION = "What is the capital of Japan?"


def get_arrows(out: str):
    return [l.strip() for l in out.splitlines() if l.strip().startswith(SUGGESTION_PREFIX)]


def test_formal_tone_suggestions_polite():
    profile = {"preferences": {"tone": "formal"}}
    out = append_suggestions_if_missing(BASE_ANSWER, QUESTION, profile)
    arrows = get_arrows(out)
    assert any("Would" in a or "Shall" in a for a in arrows)
    assert not any("😄" in a for a in arrows)


def test_playful_tone_adds_emoji():
    profile = {"preferences": {"tone": "playful"}}
    out = append_suggestions_if_missing(BASE_ANSWER, QUESTION, profile)
    arrows = get_arrows(out)
    assert any("😄" in a for a in arrows) or any("😉" in a for a in arrows)


def test_concise_tone_keeps_short():
    profile = {"preferences": {"tone": "concise"}}
    out = append_suggestions_if_missing(BASE_ANSWER, QUESTION, profile)
    arrows = get_arrows(out)
    assert all(len(a) <= 70 for a in arrows)
