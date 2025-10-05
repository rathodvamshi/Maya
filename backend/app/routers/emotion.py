from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import re
from app.config import settings
import os
from app.services.emotion_service import detect_emotion  # existing heuristic (unchanged)
from app.services import advanced_emotion

router = APIRouter(prefix="/api/emotion", tags=["Emotion"])


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    style: Optional[str] = Field(default="conservative", pattern="^(conservative|casual|playful)$")


def _derive_heuristic_flags(text: str) -> Dict[str, Any]:
    contains_emoji = bool(re.search(r"[\U0001F300-\U0001FAFF]", text))
    elongated = bool(re.search(r"(.)\1{2,}", text))
    punct_runs = re.findall(r"[!?]{2,}", text)
    punctuation_intensity = min(1.0, sum(len(p) for p in punct_runs) / 10.0) if punct_runs else 0.0
    letters = [c for c in text if c.isalpha()]
    caps = sum(1 for c in letters if c.isupper())
    caps_intensity = (caps / len(letters)) if letters else 0.0
    # crude intensity heuristic: weighted combo
    intensity = min(1.0, (0.4 * punctuation_intensity) + (0.3 * caps_intensity) + (0.3 if elongated else 0))
    return {
        "contains_emoji": contains_emoji,
        "elongated": elongated,
        "punctuation_intensity": round(punctuation_intensity,3),
        "caps_intensity": round(caps_intensity,3),
        "intensity": round(intensity,3),
    }


@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    # Heuristic emotion (existing service) to preserve backward compatibility
    # We don't expose full legacy structure; we expose trigger-relevant flags.
    flags = _derive_heuristic_flags(req.text)
    payload: Dict[str, Any] = {"heuristic": flags}

    adv_env_enabled = os.getenv("ADV_EMOTION_ENABLE", "").lower() in {"1","true","yes","on"}
    # If either static setting or dynamic env enables advanced module, attempt analysis.
    if settings.ADV_EMOTION_ENABLE or adv_env_enabled:
        adv = await advanced_emotion.analyze(req.text, user_id=req.user_id, style=req.style or "conservative", heuristic=flags)
        # Always include the advanced key when enabled, even if not triggered (empty dict) so tests can assert its presence.
        payload["advanced"] = adv
    return payload
