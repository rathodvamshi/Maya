from app.services.ai_service import append_suggestions_if_missing, SUGGESTION_PREFIX

SHORT_ANSWER = "Quantum computing uses qubits which can exist in superpositions, enabling new kinds of parallelism."
LONG_ANSWER = SHORT_ANSWER + " " + ("More detail. " * 30)


def extract_arrows(txt: str):
    return [l.strip() for l in txt.splitlines() if l.strip().startswith(SUGGESTION_PREFIX)]


def test_short_answer_gets_expand_prompt():
    out = append_suggestions_if_missing(SHORT_ANSWER, "Explain quantum computing", profile={})
    arrows = extract_arrows(out)
    assert any("expand" in a.lower() or "deeper" in a.lower() or "deeper" in a for a in arrows)


def test_long_answer_gets_summary_prompt():
    out = append_suggestions_if_missing(LONG_ANSWER, "Explain quantum computing", profile={})
    arrows = extract_arrows(out)
    assert any("summary" in a.lower() or "example" in a.lower() for a in arrows)
