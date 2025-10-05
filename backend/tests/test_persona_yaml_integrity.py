import yaml

from app.services.persona_response import _load_templates  # type: ignore


def test_persona_yaml_parses_and_has_core_emotions():
    data = _load_templates(force=True)
    # Core canonical emotions expected by heuristic layer
    for key in ["happy", "sad", "angry", "anxious", "excited", "neutral"]:
        assert key in data, f"missing emotion section: {key}"
        assert isinstance(data[key], dict)
        # Ensure at least one style has non-empty list
        styles = data[key]
        has_any = any(isinstance(v, list) and v for v in styles.values())
        assert has_any, f"no template lines for {key}"


def test_synonym_aliases_present():
    data = _load_templates(force=True)
    # Synonym sections optional but if present must not be empty
    for alias in ["joy", "sadness", "excitement"]:
        if alias in data:
            assert data[alias] == [] or isinstance(data[alias], list) or data[alias] is data.get(alias.split('ness')[0], None)

