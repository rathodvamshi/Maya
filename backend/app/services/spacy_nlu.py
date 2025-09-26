"""spaCy-based NLU: intent + entities with lightweight model and regex fallback."""
import re
import logging
from functools import lru_cache
from typing import Dict, Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_nlp():
    try:
        import spacy
        # Try to load small English model; if missing, load blank and add NER disabled
        try:
            return spacy.load("en_core_web_sm")
        except Exception:
            logger.warning("spaCy model en_core_web_sm not installed; using blank 'en'")
            return spacy.blank("en")
    except Exception as e:
        logger.warning(f"spaCy unavailable: {e}")
        return None


def extract(message: str) -> Dict[str, Any]:
    """Return { intent, entities } using fast regex + spaCy NER if available."""
    # Simple intent rules
    trip_patterns = [
        r"(?:plan|organize|book|take)\s+(?:a\s+)?(?:trip|vacation|journey)\s+to\s+([\w\s]+)",
        r"(?:go|travel)\s+to\s+([\w\s]+)",
        r"let'?s\s+go\s+to\s+([\w\s]+)",
    ]
    for pat in trip_patterns:
        m = re.search(pat, message, re.IGNORECASE)
        if m:
            dest = m.group(1).strip()
            return {"intent": "PLAN_TRIP", "entities": {"destination": dest}}

    intent = "GENERAL_INQUIRY"
    entities: Dict[str, Any] = {}

    nlp = _load_nlp()
    if nlp:
        try:
            doc = nlp(message)
            # Pull named entities
            ents = []
            for ent in getattr(doc, "ents", []):
                ents.append({"text": ent.text, "label": ent.label_})
                if ent.label_ in ("GPE", "LOC") and "destination" not in entities:
                    entities["destination"] = ent.text
            if ents:
                entities["spacy_ents"] = ents
        except Exception:
            pass

    return {"intent": intent, "entities": entities}
