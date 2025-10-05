"""Behavior Tracker (Phase 1)

Maintains rolling behavioral signals in Redis to infer emerging preferences.
Stored under key patterns: user:<id>:behav

Signals (initial set):
 - expand_requests (future use)
 - clarification_rate_ewma
 - depth_bias (positive=deep, negative=concise)
 - suggestion_ctr_ewma (requires future explicit click events)
 - complexity_counts.<label>
 - tone_pref_counts.<tone>

For Phase 1, we update depth_bias heuristically:
  * If answer length > 260 chars and user does NOT immediately ask a clarifying question, small positive reinforcement.
  * If answer length < 120 and user follows with immediate clarifying / expansion phrase next turn, negative adjustment.

In this phase we only implement a simple update based on the single interaction (no follow-up context yet).
"""
from __future__ import annotations

from typing import Optional, Dict, Any
import logging
import math

from app.services import redis_service

logger = logging.getLogger(__name__)

redis_client = getattr(redis_service, "redis_client", None)

EWMA_BETA = 0.15


def _ewma(prev: float, new: float, beta: float = EWMA_BETA) -> float:
    return (1 - beta) * prev + beta * new


async def update_behavior_from_event(
    *,
    user_id: Optional[str],
    complexity: Optional[str],
    answer_chars: int,
    tone_used: Optional[str],
) -> None:
    if not user_id or not redis_client:
        return
    key = f"user:{user_id}:behav"
    try:
        pipe = redis_client.pipeline(transaction=False)
        # Complexity counts
        if complexity:
            pipe.hincrby(key, f"complexity_counts.{complexity}", 1)
        # Tone usage counts
        if tone_used:
            pipe.hincrby(key, f"tone_pref_counts.{tone_used}", 1)
        # Depth bias refinement: base delta from length then scale by complexity class
        raw_delta = 0.0
        if answer_chars > 500:
            raw_delta = 0.12
        elif answer_chars > 260:
            raw_delta = 0.07
        elif answer_chars < 80:
            raw_delta = -0.07
        elif answer_chars < 120:
            raw_delta = -0.04

        if raw_delta != 0:
            scale = 1.0
            if complexity == "how_to" or complexity == "explanatory":
                if raw_delta > 0:
                    scale = 1.3
                else:
                    scale = 0.7
            elif complexity in {"factual", "chitchat"}:
                if raw_delta > 0:
                    scale = 0.6
                else:
                    scale = 1.2
            # recommendation/general keep scale 1.0
            adjusted = raw_delta * scale
            current = await redis_client.hget(key, "depth_bias") or "0"
            try:
                curr_val = float(current)
            except ValueError:
                curr_val = 0.0
            new_val = max(-2.0, min(2.0, curr_val + adjusted))
            pipe.hset(key, "depth_bias", f"{new_val:.3f}")
        # Expire key to prevent unbounded retention (30 days)
        pipe.expire(key, 30 * 86400)
        await pipe.execute()
    except Exception:  # noqa: BLE001
        logger.debug("Failed to update behavior state", exc_info=True)


async def get_inferred_preferences(user_id: str) -> Dict[str, Any]:
    if not redis_client:
        return {}
    key = f"user:{user_id}:behav"
    try:
        data = await redis_client.hgetall(key) or {}
        depth_bias = float(data.get("depth_bias", "0") or 0)
        # Determine preferred detail level
        if depth_bias > 0.6:
            detail = "deep"
        elif depth_bias < -0.6:
            detail = "concise"
        else:
            detail = "balanced"
        # Determine tone preference if one tone dominates 60% of counted tones
        tone_counts = {k.split(".",1)[1]: int(v) for k,v in data.items() if k.startswith("tone_pref_counts.")}
        tone_pref = None
        if tone_counts:
            total = sum(tone_counts.values())
            if total > 0:
                top_tone, top_val = max(tone_counts.items(), key=lambda x: x[1])
                if top_val / total >= 0.6:
                    tone_pref = top_tone
        return {
            "detail_level": detail,
            "tone_preference_inferred": tone_pref,
            "depth_bias": depth_bias,
        }
    except Exception:  # noqa: BLE001
        logger.debug("Failed to fetch inferred preferences", exc_info=True)
        return {}


__all__ = ["update_behavior_from_event", "get_inferred_preferences"]
