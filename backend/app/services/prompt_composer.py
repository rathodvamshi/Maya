"""Prompt Composer
Central builder for final LLM input combining:
 - Conversation state
 - Recent trimmed history (last N messages)
 - Semantic recall snippets (Pinecone)
 - Structured facts (Neo4j)
 - User's latest input
Applies simple character budgets to keep total size bounded.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Any

DEFAULT_HISTORY_MESSAGES = 5
FACTS_CHAR_BUDGET = 600
SEMANTIC_CHAR_BUDGET = 600
PROFILE_CHAR_BUDGET = 260
USER_FACTS_CHAR_BUDGET = 260
HISTORY_CHAR_BUDGET = 3200

SYSTEM_TEMPLATE = (
    "You are Maya, a helpful, concise assistant. Use provided facts and context when relevant.\n"
    "If information is missing, ask a clarifying question briefly.\n"
    "Always address the user by their known name if provided in the Profile section.\n"
    "Never refer to the user by internal identifiers like User_<hex>. If only an id is available, politely ask for their preferred name.\n"
)

def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"

def compose_prompt(*,
    user_message: str,
    state: str,
    history: List[Dict],
    pinecone_context: Optional[str],
    neo4j_facts: Optional[str],
    profile: Optional[Dict[str, Any]] = None,
    user_facts_semantic: Optional[List[str]] = None,
    history_messages: int = DEFAULT_HISTORY_MESSAGES,
) -> str:
    # 1. Select last N messages and format
    selected = history[-history_messages:] if history_messages > 0 else []
    rendered_history_lines: List[str] = []
    total_hist_chars = 0
    for msg in selected:
        role = msg.get("sender") or msg.get("role") or "user"
        role_label = "Human" if role == "user" else "Assistant"
        content = (msg.get("text") or msg.get("content") or "").strip()
        if not content:
            continue
        # simple budget guard
        if total_hist_chars + len(content) > HISTORY_CHAR_BUDGET:
            break
        rendered_history_lines.append(f"{role_label}: {content}")
        total_hist_chars += len(content)
    rendered_history = "\n".join(rendered_history_lines) if rendered_history_lines else "(No prior messages)"

    # 2. Facts
    facts_block = _truncate(neo4j_facts or "", FACTS_CHAR_BUDGET)

    # 3. Semantic recall (messages)
    semantic_block = _truncate(pinecone_context or "", SEMANTIC_CHAR_BUDGET)

    # 4. Profile block (deterministic attributes)
    profile_lines: List[str] = []
    if profile:
        if profile.get("name"):
            profile_lines.append(f"Name: {profile['name']}")
        if profile.get("birthday"):
            profile_lines.append(f"Birthday: {profile['birthday']}")
        if profile.get("timezone"):
            profile_lines.append(f"Timezone: {profile['timezone']}")
        hobbies = profile.get("hobbies") or []
        if hobbies:
            profile_lines.append("Hobbies: " + ", ".join(hobbies[:5]))
        favorites = profile.get("favorites") or {}
        if favorites:
            fav_items = list(favorites.items())[:5]
            profile_lines.append("Favorites: " + ", ".join(f"{k}={v}" for k, v in fav_items))
    profile_block = _truncate("; ".join(profile_lines), PROFILE_CHAR_BUDGET)

    # 5. User semantic fact snippets (filtered)
    user_fact_block = _truncate("; ".join(user_facts_semantic or []), USER_FACTS_CHAR_BUDGET)

    # 4. Compose sections
    prompt_parts = [
        SYSTEM_TEMPLATE,
        f"State: {state}",
    ]
    if profile_block:
        prompt_parts.append(f"Profile:\n{profile_block}")
    if user_fact_block:
        prompt_parts.append(f"User Facts:\n{user_fact_block}")
    if facts_block:
        prompt_parts.append(f"Facts (may be partial):\n{facts_block}")
    if semantic_block:
        prompt_parts.append(f"Relevant prior snippets:\n{semantic_block}")
    prompt_parts.append(f"Conversation so far:\n{rendered_history}")
    prompt_parts.append(f"Human: {user_message}\nAssistant:")

    return "\n\n".join(part for part in prompt_parts if part)
