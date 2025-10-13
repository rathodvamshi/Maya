"""Profile Service

Persistent cross-session user profile storage backed by MongoDB with a small
in-memory (Redis) cache layer provided by `memory_store` if available.

This isolates deterministic, low-cardinality user attributes (name, birthday,
timezone, hobbies, favorites) from semantic or graph memory layers so that:
 - Prompt assembly is cheaper (direct read vs semantic search)
 - Simple factual questions ("What is my hobby?") resolve instantly
 - Downstream layers (Pinecone/Neo4j) can still hold richer, relational or
   paraphrased variants without being the sole source of truth.

Document schema (Mongo `user_profiles` collection):
{
  _id: <user_id>,
  name: str | None,
  timezone: str | None,
  birthday: str | None,            # free-form normalized later
  hobbies: [str],
  favorites: { <category>: <value> },
  preferences: { <key>: <value> }, # generic bucket (tone, style, etc.)
  updated_at: datetime,
  version: int
}

Operations are idempotent; partial updates merge arrays and nested maps while
preventing uncontrolled growth (caps applied).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from pymongo import ReturnDocument

from app.database import get_user_profile_collection
from app.services import memory_store

logger = logging.getLogger(__name__)


MAX_HOBBIES = 25
MAX_FAVORITES = 50  # total distinct favorite categories


def _normalize_str(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    v = val.strip()
    return v or None


def _dedupe_lower(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        if not it:
            continue
        norm = it.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def get_profile(user_id: str) -> Dict[str, Any]:
    col = get_user_profile_collection()
    doc = col.find_one({"_id": user_id}) or {}
    # Normalize expected shape
    return {
        "user_id": user_id,
        "name": doc.get("name"),
        "timezone": doc.get("timezone"),
        "birthday": doc.get("birthday"),
        "hobbies": doc.get("hobbies", []) or [],
        "favorites": doc.get("favorites", {}) or {},
        "preferences": doc.get("preferences", {}) or {},
        "stats": doc.get("stats", {}) or {},
        "recent_tasks": doc.get("recent_tasks", []) or [],
        "last_task_at": doc.get("last_task_at"),
        "updated_at": doc.get("updated_at"),
        "version": doc.get("version", 0),
    }


def cache_profile(user_id: str, profile: Dict[str, Any]):
    try:
        # Best-effort Redis cache (short TTL via memory_store default 600s)
        import asyncio
        asyncio.create_task(memory_store.cache_user_profile(user_id, profile))
    except Exception:  # noqa: BLE001
        pass


def merge_update(
    user_id: str,
    *,
    name: Optional[str] = None,
    timezone: Optional[str] = None,
    birthday: Optional[str] = None,
    add_hobbies: Optional[List[str]] = None,
    add_favorites: Optional[Dict[str, str]] = None,
    add_preferences: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Merge partial updates into the profile.

    - New hobbies appended (case-insensitive dedupe) and capped.
    - favorites/preferences merged key-wise; later values override.
    - Empty inputs ignored.
    Returns the updated profile document.
    """
    col = get_user_profile_collection()
    existing = col.find_one({"_id": user_id}) or {}

    hobbies_existing = existing.get("hobbies", []) or []
    hobbies_new: List[str] = []
    if add_hobbies:
        hobbies_new = _dedupe_lower(add_hobbies)
    merged_hobbies = hobbies_existing + [h for h in hobbies_new if h.lower() not in {e.lower() for e in hobbies_existing}]
    if len(merged_hobbies) > MAX_HOBBIES:
        merged_hobbies = merged_hobbies[-MAX_HOBBIES:]

    favorites_existing: Dict[str, str] = existing.get("favorites", {}) or {}
    if add_favorites:
        for k, v in add_favorites.items():
            nk = k.strip() if k else k
            if not nk or not v:
                continue
            if len(favorites_existing) >= MAX_FAVORITES and nk not in favorites_existing:
                continue
            favorites_existing[nk] = v.strip()

    preferences_existing: Dict[str, str] = existing.get("preferences", {}) or {}
    if add_preferences:
        for k, v in add_preferences.items():
            nk = k.strip() if k else k
            if not nk or not v:
                continue
            preferences_existing[nk] = v.strip()

    update_doc: Dict[str, Any] = {"updated_at": datetime.utcnow()}
    # Ensure user_id field exists for unique index
    update_doc["user_id"] = user_id
    if name := _normalize_str(name):
        update_doc["name"] = name
    if timezone := _normalize_str(timezone):
        update_doc["timezone"] = timezone
    if birthday := _normalize_str(birthday):
        update_doc["birthday"] = birthday
    update_doc["hobbies"] = merged_hobbies
    update_doc["favorites"] = favorites_existing
    update_doc["preferences"] = preferences_existing
    update_doc["version"] = int(existing.get("version", 0)) + 1

    result = col.find_one_and_update(
        {"_id": user_id},
        {"$set": update_doc},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    profile = get_profile(user_id)
    cache_profile(user_id, profile)
    logger.debug("Profile updated", extra={"user_id": user_id, "version": profile.get("version")})
    return profile


def ensure_indexes():
    try:
        col = get_user_profile_collection()
        col.create_index("updated_at")
    except Exception:  # noqa: BLE001
        pass


def record_task_created(user_id: str, *, task_id: str, title: str, due_date):
    """Record a newly created task reference in the user's profile.

    - Prepend a small entry to recent_tasks (capped to 20 most recent)
    - Increment stats.total_tasks
    - Set last_task_at and updated_at
    """
    try:
        col = get_user_profile_collection()
        now = datetime.utcnow()
        entry = {
            "id": task_id,
            "title": title,
            "due_date": due_date,
            "created_at": now,
        }
        update = {
            "$push": {"recent_tasks": {"$each": [entry], "$position": 0, "$slice": 20}},
            "$set": {"last_task_at": now, "updated_at": now},
            "$inc": {"stats.total_tasks": 1},
        }
        col.update_one({"_id": user_id}, update, upsert=True)
        # Refresh cache best-effort
        profile = get_profile(user_id)
        cache_profile(user_id, profile)
    except Exception:  # noqa: BLE001
        logger.debug("record_task_created failed", exc_info=True)


__all__ = [
    "get_profile",
    "merge_update",
    "ensure_indexes",
    "record_task_created",
]
