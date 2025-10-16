"""Response Shaper: consistent, friendly, structured replies.

This module centralizes the final shaping of assistant responses so they:
- Greet the user with name and a light personal touch (tone-aware)
- Add a short contextual hook when we have recent memory (optional)
- Present the main answer/message
- Optionally add multi-modal hints (YouTube/news/weather handled upstream; we add prompts)
- Close with 1-2 actionable suggestions using ai_service suggestion helper

Minimal external deps: relies on emotion_service for tone and palette and ai_service for
computing lightweight suggestions. Safe to call for any text reply.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List

from app.services.emotion_service import detect_emotion, enrich_with_emojis
from app.services.ai_service import append_suggestions_if_missing


def _first_name(profile: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(profile, dict):
        return None
    name = profile.get("name") or profile.get("displayName") or profile.get("first_name")
    if not name:
        return None
    # Trim to first token
    return str(name).split()[0]


def _context_hook(ctx: Optional[Dict[str, Any]]) -> Optional[str]:
    """Build a short hook like: "Last time we discussed Java loops…"""
    if not isinstance(ctx, dict):
        return None
    last_topic = ctx.get("last_topic") or ctx.get("recent_focus")
    if last_topic:
        return f"Last time we discussed {last_topic}…"
    return None


def _tone_prefix(emotion_label: str, name: Optional[str]) -> str:
    # Map emotion to greeting style
    if name:
        base = f"Hey {name}!"
    else:
        base = "Hey there!"
    if emotion_label in {"sad", "anxious"}:
        return base.replace("!", "") + " I’m here for you."
    if emotion_label in {"angry"}:
        return base.replace("!", "") + " Let’s sort this out calmly."
    if emotion_label in {"excited", "happy"}:
        return base + " 😄"
    return base


def format_structured_reply(
    *,
    user_message: str,
    main_text: str,
    profile: Optional[Dict[str, Any]] = None,
    short_context: Optional[Dict[str, Any]] = None,
    add_emojis: bool = True,
) -> str:
    """Compose a structured, friendly reply.

    Inputs:
    - user_message: latest user text (for emotion and suggestions)
    - main_text: the core answer already computed upstream (NLU/skills/LLM)
    - profile: optional user profile dict with name/preferences
    - short_context: optional dict with recent topic or hooks
    - add_emojis: toggle emoji enrichment

    Output: final text to send to the client.
    """
    user_text = (user_message or "").strip()
    core = (main_text or "").strip()
    if not core:
        core = "I’m here and ready to help. What would you like to do?"

    # Emotion + tone
    emo = detect_emotion(user_text)

    # Greeting
    name = _first_name(profile)
    greeting = _tone_prefix(emo.emotion, name)

    # Contextual hook
    hook = _context_hook(short_context)

    # Build body
    parts: List[str] = []
    parts.append(greeting)
    if hook:
        parts.append(hook)
    parts.append(core)

    shaped = "\n\n".join([p for p in parts if p])

    # Emoji enrichment (light)
    if add_emojis:
        shaped = enrich_with_emojis(shaped, emo, max_new=2, hard_cap=6)

    # Closing suggestions (at most two, tone-aware; append only if not present)
    shaped = append_suggestions_if_missing(shaped, user_text, profile)

    return shaped


__all__ = ["format_structured_reply"]
