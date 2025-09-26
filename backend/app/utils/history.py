"""History utilities: trimming conversation history to control token/cost budget.

Simple heuristic char-based trimming keeps most recent messages while enforcing a
maximum aggregate character budget. This avoids unbounded prompt growth.
"""
from __future__ import annotations
from typing import List, Dict

Message = Dict[str, str]  # expects keys like sender/text OR role/content

def trim_history(messages: List[Message], max_chars: int = 6000) -> List[Message]:
    """Return a trimmed copy of messages whose total text length <= max_chars.

    Strategy: walk backward (most recent first) accumulating until budget
    exhausted, then reverse back to chronological order. Works with either
    {"text"} or {"content"} payload keys.
    """
    if not messages or max_chars <= 0:
        return []
    total = 0
    kept: List[Message] = []
    for msg in reversed(messages):
        text = msg.get("text") or msg.get("content") or ""
        size = len(text)
        if total + size > max_chars:
            break
        kept.append(msg)
        total += size
    return list(reversed(kept))
