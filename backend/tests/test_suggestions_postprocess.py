from app.services.ai_service import append_suggestions_if_missing, strip_existing_suggestions, SUGGESTION_PREFIX


def test_append_suggestions_basic():
    base = "The capital of Japan is Tokyo."
    out = append_suggestions_if_missing(base, "What is the capital of Japan?", profile={})
    lines = out.splitlines()
    arrows = [l for l in lines if l.strip().startswith(SUGGESTION_PREFIX)]
    assert 1 <= len(arrows) <= 2


def test_append_suggestions_opt_out():
    base = "Here is your answer."
    out = append_suggestions_if_missing(base, "Please answer this, no suggestions", profile={})
    assert SUGGESTION_PREFIX not in out


def test_strip_existing_suggestions_caps():
    txt = "Answer line\n➝ One\n➝ Two\n➝ Three extra"
    cleaned = strip_existing_suggestions(txt)
    assert cleaned.count(SUGGESTION_PREFIX) == 2
