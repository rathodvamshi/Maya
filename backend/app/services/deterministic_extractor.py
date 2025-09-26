"""Deterministic fact & preference extractor.

Fast, regex + lightweight heuristics (optionally spaCy later) to emit structured
events from user + assistant message pairs. This runs BEFORE any heavy LLM
extraction so we can persist obvious profile facts immediately.

Outputs a dict with optional keys:
{
  "profile_update": { name?, birthday?, timezone?, add_hobbies: [], add_favorites: {category: value} },
  "preferences": [ {"type": "hobby", "value": "painting"}, ... ],
  "semantic_facts": ["User likes painting", "User's favorite color is blue"],
}

All entries are conservative (high precision). Recall can later be improved with
the existing AI extraction pipeline.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List

HOBBY_PATTERNS = [
    re.compile(r"\bi (?:really\s+)?(?:like|love|enjoy) ([a-z][a-z\s]{2,40})", re.I),
    re.compile(r"\bmy hobby is ([a-z][a-z\s]{2,40})", re.I),
]

# Name patterns: "my name is Priyanka", "I'm Priyanka", "I am Priyanka" (case-insensitive, allow lowercase and normalize)
NAME_PATTERN = re.compile(r"\bmy name is ([A-Za-z][a-zA-Z'-]{1,40})\b")
NAME_ALT_PATTERN_1 = re.compile(r"\bi[' ]?m ([A-Za-z][a-zA-Z'-]{1,40})\b")
NAME_ALT_PATTERN_2 = re.compile(r"\bi am ([A-Za-z][a-zA-Z'-]{1,40})\b")
BIRTHDAY_PATTERN = re.compile(r"\bmy birthday is ([A-Za-z]{3,9}\s+\d{1,2})\b", re.I)
FAV_PATTERN = re.compile(r"\bmy favorite ([a-z]{3,20}) is ([a-zA-Z][\w\s'-]{1,40})", re.I)
TIMEZONE_PATTERN = re.compile(r"\bi am in (GMT|UTC[+-]?\d{0,2}|[A-Z]{2,5}) timezone\b", re.I)


def _clean_phrase(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).strip(" .,!")


def extract(user_message: str, assistant_message: str) -> Dict[str, Any]:
    text = f"{user_message}\n{assistant_message or ''}"[:4000]
    profile_update: Dict[str, Any] = {}
    hobbies: List[str] = []
    semantic_facts: List[str] = []
    preferences: List[Dict[str, str]] = []
    favorites_acc: Dict[str, str] = {}

    # --- Name ---
    name: str | None = None
    for pat in (NAME_PATTERN, NAME_ALT_PATTERN_1, NAME_ALT_PATTERN_2):
        m = pat.search(text)
        if m:
            cand = _clean_phrase(m.group(1))
            if cand:
                # Normalize capitalization (first letter upper, rest as-is unless all caps)
                if cand.islower():
                    cand = cand.capitalize()
                name = cand
                break
    if name:
        profile_update["name"] = name
        semantic_facts.append(f"User's name is {name}")

    # --- Birthday ---
    m = BIRTHDAY_PATTERN.search(text)
    if m:
        bd = _clean_phrase(m.group(1))
        profile_update["birthday"] = bd
        semantic_facts.append(f"User's birthday is {bd}")

    # --- Timezone ---
    m = TIMEZONE_PATTERN.search(text)
    if m:
        tz = _clean_phrase(m.group(1))
        profile_update["timezone"] = tz
        semantic_facts.append(f"User timezone is {tz}")

    # --- Hobbies ---
    for pat in HOBBY_PATTERNS:
        for hm in pat.finditer(text):
            hobby = _clean_phrase(hm.group(1))
            if hobby and 2 < len(hobby) <= 40:
                hobbies.append(hobby)
                preferences.append({"type": "hobby", "value": hobby})
                semantic_facts.append(f"User likes {hobby}")

    # --- Favorites ---
    for fm in FAV_PATTERN.finditer(text):
        cat = _clean_phrase(fm.group(1)).lower()
        val = _clean_phrase(fm.group(2))
        # Strip trailing qualifiers like 'now' / 'for now'
        val = re.sub(r"\b(for\s+now|now)\.?$", "", val, flags=re.I).strip()
        if cat and val:
            favorites_acc[cat] = val
            semantic_facts.append(f"User's favorite {cat} is {val}")

    if hobbies:
        profile_update["add_hobbies"] = hobbies
    if favorites_acc:
        profile_update["add_favorites"] = favorites_acc

    out: Dict[str, Any] = {}
    if profile_update:
        out["profile_update"] = profile_update
    if preferences:
        out["preferences"] = preferences
    if semantic_facts:
        out["semantic_facts"] = semantic_facts
    return out


__all__ = ["extract"]
