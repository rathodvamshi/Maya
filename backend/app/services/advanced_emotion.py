"""Advanced Emotion Detection & Emoji Suggestion (optional, gated).

Implements an async `analyze` function that:
 - Applies trigger heuristics (OR runs unconditionally if ADV_EMOTION_ENABLE=true)
 - Generates a pseudo probability distribution via stub `model_infer` (replace later)
 - Applies toxicity gate
 - Computes entropy & confidence gating
 - Selects one emoji using YAML-driven mapping and user style (conservative|casual|playful)
 - Emits Prometheus metrics and structured log with input hash only (sha256)

Heuristic output from existing `emotion_service` can be passed in to decide triggering.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os
import math
import re
import time
import hashlib
import yaml
from pathlib import Path

from app.config import settings
from app.metrics import EMOTION_REQ_COUNTER, EMOTION_LATENCY_HIST, EMOJI_APPEND_COUNTER

EMOTION_LABELS = ["joy","love","gratitude","surprise","sadness","confusion","anger","fear","disgust","neutral","toxic"]

_EMOJI_MAP_CACHE: Dict[str, Dict[str, List[str]]] | None = None
_EMOJI_MAP_MTIME: float | None = None

ELONGATED = re.compile(r"(.)\1{2,}")
PUNCT = re.compile(r"[!?]{2,}")
CAPS = re.compile(r"[A-Z]{4,}")
WORD_RE = re.compile(r"[\w']+")

POS_WORDS = {"great","awesome","nice","love","thanks","thank","cool","amazing","happy","glad","fantastic"}
NEG_WORDS = {"bad","sad","angry","upset","hate","terrible","awful","worse","anxious","anxiety","fear"}
TOXIC_WORDS = {"stupid","idiot","hate","dumb","trash","kill","worst","sucks"}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_emoji_map(force: bool = False) -> Dict[str, Dict[str, List[str]]]:
    global _EMOJI_MAP_CACHE, _EMOJI_MAP_MTIME
    path = Path(settings.EMOJI_MAP_PATH)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        # Fallback minimal mapping
        return {e: {"conservative":["🙂"],"casual":["🙂"],"playful":["🙂"]} for e in EMOTION_LABELS}
    if (not force) and _EMOJI_MAP_CACHE is not None and _EMOJI_MAP_MTIME == mtime:
        return _EMOJI_MAP_CACHE
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Ensure all base emotions present
        for e in EMOTION_LABELS:
            if e not in data:
                data[e] = {"conservative":["🙂"],"casual":["🙂"],"playful":["🙂"]}
        _EMOJI_MAP_CACHE = data
        _EMOJI_MAP_MTIME = mtime
        return data
    except Exception:
        return {e: {"conservative":["🙂"],"casual":["🙂"],"playful":["🙂"]} for e in EMOTION_LABELS}


def quick_toxicity_check(text: str) -> bool:
    lowered = text.lower()
    return any(w in lowered for w in TOXIC_WORDS)


def triggered_by_heuristics(heuristic: Optional[Dict[str, Any]]) -> bool:
    if not heuristic:
        return False
    return any(heuristic.get(k) for k in ["contains_emoji","elongated"]) or (heuristic.get("punctuation_intensity",0) >= 0.6) or (heuristic.get("caps_intensity",0) >= 0.6)


def entropy_from_probs(probs: Dict[str,float]) -> float:
    h=0.0
    for p in probs.values():
        if p>0:
            h -= p*math.log(p+1e-12)
    return h


def model_infer(text: str) -> Dict[str,float]:
    """Stub model inference producing a pseudo-distribution.
    Replace later with actual model forward. Keeps neutral when weak signal.
    """
    tokens = [t.lower() for t in WORD_RE.findall(text)]
    scores = {k:0.0 for k in EMOTION_LABELS}
    pos = sum(t in POS_WORDS for t in tokens)
    neg = sum(t in NEG_WORDS for t in tokens)
    if pos>neg and pos>0:
        scores["joy"] = 0.55 + 0.07*min(pos,3)
    if neg>pos and neg>0:
        scores["sadness"] = 0.50 + 0.07*min(neg,3)
    if "love" in tokens:
        scores["love"] = max(scores["love"],0.62)
    if any(t.startswith("thank") for t in tokens):
        scores["gratitude"] = max(scores["gratitude"],0.6)
    if "why" in tokens or "how" in tokens:
        scores["confusion"] = max(scores["confusion"],0.5)
    total = sum(scores.values())
    if total == 0:
        scores["neutral"] = 1.0
        return scores
    if total < 1.0:
        scores["neutral"] = 1.0 - total
    # Normalize
    total = sum(scores.values()) or 1.0
    return {k:v/total for k,v in scores.items() if v>0 or k=="neutral"}


def pick_emoji_for_emotions(emotion: str, style: str) -> Optional[str]:
    mapping = _load_emoji_map()
    style = style if style in {"conservative","casual","playful"} else "conservative"
    choices = mapping.get(emotion,{}).get(style) or []
    return choices[0] if choices else None


async def load_model() -> None:  # Placeholder for future heavy model warm-load
    _load_emoji_map(force=True)


async def analyze(text: str, user_id: Optional[str] = None, style: str = "conservative", heuristic: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    start = time.time()
    # Dynamic enable: allow tests or runtime to flip via env without rebuilding settings
    adv_enabled = settings.ADV_EMOTION_ENABLE or os.getenv("ADV_EMOTION_ENABLE", "").lower() in {"1","true","yes","on"}
    triggered = adv_enabled or triggered_by_heuristics(heuristic)
    try:
        EMOTION_REQ_COUNTER.labels(
            path="/api/emotion/analyze",
            advanced=str(adv_enabled).lower(),
            triggered=str(triggered).lower()
        ).inc()
    except Exception:
        pass
    if not triggered:
        return {}

    toxic = quick_toxicity_check(text)
    if toxic:
        probs = {"toxic":1.0}
        top = "toxic"; confidence = 1.0; ent = 0.0
        emoji = None
        reason = "toxic"
    else:
        probs = model_infer(text)
        # Sort + metrics
        ordered = sorted(probs.items(), key=lambda x:x[1], reverse=True)
        top, confidence = ordered[0]
        ent = entropy_from_probs(probs)
        reason = "ok"
        emoji = None
        if top != "neutral" and confidence >= settings.ADV_EMOTION_CONFIDENCE_THRESHOLD and ent <= settings.ADV_EMOTION_ENTROPY_THRESHOLD:
            emoji = pick_emoji_for_emotions(top, style)
            if emoji:
                try:
                    EMOJI_APPEND_COUNTER.labels(emotion=top, style=style).inc()
                except Exception:
                    pass
        else:
            reason = "low_confidence_or_high_entropy"

    latency = time.time() - start
    EMOTION_LATENCY_HIST.observe(latency)
    # Structured log (print for now; integrate with central logger if available)
    try:
        print(f"emotion_log | hash={_hash(text)} top={top} conf={confidence:.3f} ent={ent:.3f} emoji={emoji} toxic={toxic} latency_ms={int(latency*1000)}")
    except Exception:
        pass

    return {
        "triggered": True,
        "emotions": probs,
        "top": top,
        "confidence": round(confidence,4),
        "entropy": round(ent,4),
        "emoji": emoji,
        "reason": reason,
        "latency": round(latency,4),
    }

__all__ = [
    "analyze",
    "load_model",
    "pick_emoji_for_emotions",
    "entropy_from_probs",
    "quick_toxicity_check",
]
