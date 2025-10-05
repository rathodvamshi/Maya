# backend/app/routers/mini_agent.py
"""Mini Inline Agent (Junior Lecturer) API.

MVP Endpoints:
 - POST /api/mini-agent/threads/ensure
 - POST /api/mini-agent/threads/{thread_id}/snippets/add
 - GET  /api/mini-agent/threads/{thread_id}
 - POST /api/mini-agent/threads/{thread_id}/messages

All endpoints are user-scoped (auth required) and isolated from main chat memory.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, AsyncGenerator
import json
from datetime import datetime
from bson import ObjectId
import hashlib

from app.security import get_current_active_user
from app.database import (
    get_mini_threads_collection,
    get_mini_snippets_collection,
    get_mini_messages_collection,
    get_chat_log_collection,
    get_inline_highlights_collection,
)
from pymongo.collection import Collection
from app.services import ai_service
from app.mini_agent.pipeline import (
    run_mini_pipeline, PipelineInput, MiniMessage, PipelineOutput
)

router = APIRouter(prefix="/api/mini-agent", tags=["MiniAgent"])

# ------------------ Models ------------------
class EnsureThreadBody(BaseModel):
    message_id: str

class EnsureThreadResponse(BaseModel):
    mini_thread_id: str
    message_id: str
    session_id: str
    snippets: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []

class AddSnippetBody(BaseModel):
    text: str = Field(..., min_length=1)

class SendMiniMessageBody(BaseModel):
    snippet_id: Optional[str] = None
    content: str = Field(..., min_length=1)

class HighlightBody(BaseModel):
    message_id: str
    text: str = Field(..., min_length=1)
    snippet_id: Optional[str] = None

class HighlightResponse(BaseModel):
    highlight_id: str
    message_id: str
    snippet_id: Optional[str] = None
    text: str
    created_at: datetime

class UpdateSnippetBody(BaseModel):
    text: str = Field(..., min_length=1)

class SummarizeResponse(BaseModel):
    summary_message_id: str
    summary: str

# ------------------ Helpers ------------------

def _oid(val: str) -> ObjectId:
    try:
        return ObjectId(val)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

_DEF_SESSION_PREFIX = "mini_"

def _session_id_for_user(user_id: str) -> str:
    # Deterministic per-user session for now (could randomize if needed)
    h = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    return f"{_DEF_SESSION_PREFIX}{h}"

_SYSTEM_PROMPT = (
    "You are Junior Lecturer, an inline assistant. Your only job is to clarify doubts about the given selected message/snippet. "
    "Do not store long-term memory, do not drift. Be concise, accurate, context-bound."
)

# ------------------ Endpoints ------------------
@router.post("/threads/ensure", response_model=EnsureThreadResponse)
async def ensure_thread(
    body: EnsureThreadBody,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
):
    user_id = str(current_user["_id"])
    msg_id = body.message_id

    existing = mini_threads.find_one({"message_id": msg_id, "user_id": user_id})
    if not existing:
        thread_doc = {
            "message_id": msg_id,
            "user_id": user_id,
            "session_id": _session_id_for_user(user_id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "orphaned": False,
        }
        inserted_id = mini_threads.insert_one(thread_doc).inserted_id
        existing = mini_threads.find_one({"_id": inserted_id})

    snippets = list(mini_snippets.find({"mini_thread_id": str(existing["_id"])}, {"_id": 1, "text": 1, "hash":1}))
    messages = list(mini_messages.find({"mini_thread_id": str(existing["_id"])}, {"_id":1, "role":1, "content":1, "snippet_id":1, "created_at":1, "streaming":1, "aborted":1}))

    return EnsureThreadResponse(
        mini_thread_id=str(existing["_id"]),
        message_id=msg_id,
        session_id=existing["session_id"],
        snippets=[{"snippet_id": str(s["_id"]), "text": s["text"], "hash": s.get("hash") } for s in snippets],
        messages=[{
            "mini_message_id": str(m["_id"]),
            "role": m["role"],
            "content": m["content"],
            "snippet_id": m.get("snippet_id"),
            "created_at": m.get("created_at"),
            "streaming": m.get("streaming", False),
            "aborted": m.get("aborted", False),
        } for m in messages]
    )

@router.post("/threads/{thread_id}/snippets/add")
async def add_snippet(
    thread_id: str,
    body: AddSnippetBody,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
):
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")
    normalized = body.text.strip()
    h = hashlib.sha256(normalized.lower().encode()).hexdigest()[:40]
    existing = mini_snippets.find_one({"mini_thread_id": thread_id, "hash": h})
    if existing:
        return {"snippet_id": str(existing["_id"]), "text": existing["text"], "hash": existing["hash"], "reused": True}
    doc = {
        "mini_thread_id": thread_id,
        "text": normalized,
        "hash": h,
        "created_at": datetime.utcnow(),
    }
    sid = mini_snippets.insert_one(doc).inserted_id
    return {"snippet_id": str(sid), "text": normalized, "hash": h, "reused": False}

@router.patch("/threads/{thread_id}/snippets/{snippet_id}")
async def update_snippet(
    thread_id: str,
    snippet_id: str,
    body: UpdateSnippetBody,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
):
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")
    sdoc = mini_snippets.find_one({"_id": _oid(snippet_id), "mini_thread_id": thread_id})
    if not sdoc:
        raise HTTPException(status_code=404, detail="Snippet not found")
    normalized = body.text.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Empty text")
    new_hash = hashlib.sha256(normalized.lower().encode()).hexdigest()[:40]
    # If unchanged return existing
    if normalized == sdoc["text"]:
        return {"snippet_id": snippet_id, "text": sdoc["text"], "hash": sdoc.get("hash")}
    # Ensure uniqueness
    dup = mini_snippets.find_one({"mini_thread_id": thread_id, "hash": new_hash, "_id": {"$ne": sdoc["_id"]}})
    if dup:
        raise HTTPException(status_code=409, detail="Snippet text duplicates existing snippet")
    mini_snippets.update_one({"_id": sdoc["_id"]}, {"$set": {"text": normalized, "hash": new_hash}})
    return {"snippet_id": snippet_id, "text": normalized, "hash": new_hash, "updated": True}

@router.delete("/threads/{thread_id}/snippets/{snippet_id}")
async def delete_snippet(
    thread_id: str,
    snippet_id: str,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
):
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")
    sdoc = mini_snippets.find_one({"_id": _oid(snippet_id), "mini_thread_id": thread_id})
    if not sdoc:
        raise HTTPException(status_code=404, detail="Snippet not found")
    msg_count = mini_messages.count_documents({"mini_thread_id": thread_id, "snippet_id": snippet_id})
    if msg_count > 0:
        raise HTTPException(status_code=409, detail="Cannot delete snippet with existing messages")
    mini_snippets.delete_one({"_id": sdoc["_id"]})
    return {"deleted": True, "snippet_id": snippet_id}

@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
):
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")
    snippets = list(mini_snippets.find({"mini_thread_id": thread_id}))
    messages = list(mini_messages.find({"mini_thread_id": thread_id}).sort("created_at", 1))
    return {
        "mini_thread_id": thread_id,
        "message_id": tdoc["message_id"],
        "session_id": tdoc["session_id"],
        "snippets": [{"snippet_id": str(s["_id"]), "text": s["text"], "hash": s["hash"]} for s in snippets],
        "messages": [{
            "mini_message_id": str(m["_id"]),
            "role": m["role"],
            "content": m["content"],
            "snippet_id": m.get("snippet_id"),
            "created_at": m.get("created_at"),
            "streaming": m.get("streaming", False),
            "aborted": m.get("aborted", False),
        } for m in messages]
    }

@router.post("/threads/{thread_id}/messages")
async def send_mini_message(
    thread_id: str,
    body: SendMiniMessageBody,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
    chat_logs: Collection = Depends(get_chat_log_collection),
):
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")

    snippet_doc = None
    if body.snippet_id:
        snippet_doc = mini_snippets.find_one({"_id": _oid(body.snippet_id), "mini_thread_id": thread_id})
        if not snippet_doc:
            raise HTTPException(status_code=404, detail="Snippet not found")

    # Persist user mini message
    user_msg_id = mini_messages.insert_one({
        "mini_thread_id": thread_id,
        "role": "user",
        "content": body.content,
        "snippet_id": body.snippet_id,
        "created_at": datetime.utcnow(),
    }).inserted_id

    # Build lightweight context for pipeline (recent messages)
    recent_docs = list(mini_messages.find({"mini_thread_id": thread_id}).sort("created_at", 1).limit(20))
    recent_msgs: list[MiniMessage] = [MiniMessage(role=m["role"], content=m["content"]) for m in recent_docs if m.get("role") in ("user", "assistant")]
    snippet_text = snippet_doc["text"] if snippet_doc else "(no snippet)"

    pipeline_input = PipelineInput(
        snippet_text=snippet_text,
        user_query=body.content,
        recent_messages=recent_msgs,
        system_prompt=_SYSTEM_PROMPT,
        max_history=6,
    )

    pipeline_out: PipelineOutput = await run_mini_pipeline(pipeline_input)

    ai_msg_id = mini_messages.insert_one({
        "mini_thread_id": thread_id,
        "role": "assistant",
        "content": pipeline_out.text,
        "snippet_id": body.snippet_id,
        "created_at": datetime.utcnow(),
        "intent": pipeline_out.intent,
        "strategy": pipeline_out.strategy,
        "confidence": pipeline_out.confidence,
        "fallback_used": pipeline_out.fallback_used,
    }).inserted_id

    mini_threads.update_one({"_id": tdoc["_id"]}, {"$set": {"updated_at": datetime.utcnow()}})

    return {
        "user_message_id": str(user_msg_id),
        "assistant_message_id": str(ai_msg_id),
        "assistant_text": pipeline_out.text,
        "snippet_id": body.snippet_id,
        "mini_thread_id": thread_id,
        "intent": pipeline_out.intent,
        "strategy": pipeline_out.strategy,
        "confidence": pipeline_out.confidence,
        "fallback_used": pipeline_out.fallback_used,
    }


# ------------------ Streaming (SSE) Endpoint ------------------
@router.get("/threads/{thread_id}/messages/stream")
async def stream_mini_message(
    thread_id: str,
    content: str = Query(..., min_length=1),
    snippet_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
    chat_logs: Collection = Depends(get_chat_log_collection),
):
    """Server-Sent Events streaming of an assistant reply.

    Strategy: generate full reply via ai_service, then chunk stream 'token' events to client.
    This is a pseudo-stream (no true token streaming from provider yet) but provides UI responsiveness.
    """
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")

    snippet_doc = None
    if snippet_id:
        snippet_doc = mini_snippets.find_one({"_id": _oid(snippet_id), "mini_thread_id": thread_id})
        if not snippet_doc:
            raise HTTPException(status_code=404, detail="Snippet not found")

    # Persist user message immediately
    user_msg_id = mini_messages.insert_one({
        "mini_thread_id": thread_id,
        "role": "user",
        "content": content,
        "snippet_id": snippet_id,
        "created_at": datetime.utcnow(),
    }).inserted_id

    # Build pipeline input (similar to non-stream)
    recent_docs = list(mini_messages.find({"mini_thread_id": thread_id}).sort("created_at", 1).limit(20))
    recent_msgs: list[MiniMessage] = [MiniMessage(role=m["role"], content=m["content"]) for m in recent_docs if m.get("role") in ("user", "assistant")]
    snippet_text = snippet_doc["text"] if snippet_doc else "(no snippet)"
    pipeline_input = PipelineInput(
        snippet_text=snippet_text,
        user_query=content,
        recent_messages=recent_msgs,
        system_prompt=_SYSTEM_PROMPT,
        max_history=6,
    )

    # Run pipeline (full generation). We still pseudo-stream by chunking after.
    try:
        pipeline_out: PipelineOutput = await run_mini_pipeline(pipeline_input)
    except Exception as e:  # noqa: BLE001
        async def error_gen() -> AsyncGenerator[bytes, None]:
            err_msg = str(e).replace('\\', ' ').replace('\n', ' ')
            payload = json.dumps({"message": err_msg})
            yield ("event: error\n" + f"data: {payload}\n\n").encode()
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    # Persist assistant message with pipeline metadata so ID is stable
    assistant_id = mini_messages.insert_one({
        "mini_thread_id": thread_id,
        "role": "assistant",
        "content": pipeline_out.text,
        "snippet_id": snippet_id,
        "created_at": datetime.utcnow(),
        "intent": pipeline_out.intent,
        "strategy": pipeline_out.strategy,
        "confidence": pipeline_out.confidence,
        "fallback_used": pipeline_out.fallback_used,
    }).inserted_id
    mini_threads.update_one({"_id": tdoc["_id"]}, {"$set": {"updated_at": datetime.utcnow()}})

    async def event_stream() -> AsyncGenerator[bytes, None]:
        # Initial meta event (user & assistant ids)
        meta_payload = {
            "user_message_id": str(user_msg_id),
            "assistant_message_id": str(assistant_id),
            "intent": pipeline_out.intent,
            "strategy": pipeline_out.strategy,
            "confidence": pipeline_out.confidence,
            "fallback_used": pipeline_out.fallback_used,
        }
        yield ("event: meta\n" + f"data: {json.dumps(meta_payload)}\n\n").encode()
        # Chunk the reply into ~40 char pieces without breaking too awkwardly
        reply = pipeline_out.text
        chunk_size = 40
        for i in range(0, len(reply), chunk_size):
            piece = reply[i:i+chunk_size]
            payload = json.dumps({"text": piece})
            yield ("event: token\n" + f"data: {payload}\n\n").encode()
        # Done event
        yield ("event: done\n" + f"data: {{\"assistant_message_id\": \"{assistant_id}\"}}\n\n").encode()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ------------------ Highlight Persistence ------------------
@router.post("/highlights", response_model=HighlightResponse)
async def create_highlight(
    body: HighlightBody,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    inline_highlights: Collection = Depends(get_inline_highlights_collection),
):
    user_id = str(current_user["_id"])
    # Ensure the message has an existing mini thread (or create) so highlight is tied properly
    tdoc = mini_threads.find_one({"message_id": body.message_id, "user_id": user_id})
    if not tdoc:
        # Auto-create thread entry (without snippets/messages) for highlight association
        thread_doc = {
            "message_id": body.message_id,
            "user_id": user_id,
            "session_id": _session_id_for_user(user_id),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "orphaned": False,
        }
        mini_threads.insert_one(thread_doc)

    created_at = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "message_id": body.message_id,
        "snippet_id": body.snippet_id,
        "text": body.text.strip(),
        "created_at": created_at,
    }
    hid = inline_highlights.insert_one(doc).inserted_id
    return HighlightResponse(
        highlight_id=str(hid),
        message_id=body.message_id,
        snippet_id=body.snippet_id,
        text=body.text.strip(),
        created_at=created_at,
    )

@router.get("/highlights")
async def list_highlights(
    message_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    inline_highlights: Collection = Depends(get_inline_highlights_collection),
):
    user_id = str(current_user["_id"])
    q: Dict[str, Any] = {"user_id": user_id}
    if message_id:
        q["message_id"] = message_id
    docs = list(inline_highlights.find(q).sort("created_at", -1))
    return [{
        "highlight_id": str(d["_id"]),
        "message_id": d["message_id"],
        "snippet_id": d.get("snippet_id"),
        "text": d.get("text"),
        "created_at": d.get("created_at"),
    } for d in docs]

# ------------------ Summarization ------------------
@router.post("/threads/{thread_id}/summarize", response_model=SummarizeResponse)
async def summarize_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_active_user),
    mini_threads: Collection = Depends(get_mini_threads_collection),
    mini_snippets: Collection = Depends(get_mini_snippets_collection),
    mini_messages: Collection = Depends(get_mini_messages_collection),
):
    """Produce a concise structured summary of the inline mini-agent session.

    Strategy:
      - Collect all snippets (text truncated if very long)
      - Collect last ~30 user+assistant messages chronologically
      - Prompt model to produce bullet list per snippet + overall insights
    Persist summary as an assistant message (role=assistant, snippet_id=None, summary=True)
    """
    user_id = str(current_user["_id"])
    tdoc = mini_threads.find_one({"_id": _oid(thread_id), "user_id": user_id})
    if not tdoc:
        raise HTTPException(status_code=404, detail="Thread not found")

    snippets = list(mini_snippets.find({"mini_thread_id": thread_id}))
    messages = list(mini_messages.find({"mini_thread_id": thread_id}).sort("created_at", 1))
    # Keep last 30 conversational messages
    convo = [m for m in messages if m.get("role") in ("user", "assistant")][-30:]

    # Build prompt parts
    snippet_section_lines = []
    for idx, s in enumerate(snippets, start=1):
        txt = s.get("text", "")
        if len(txt) > 400:
            txt = txt[:400] + "…"
        snippet_section_lines.append(f"Snippet {idx}: {txt}")
    snippet_block = "\n".join(snippet_section_lines) if snippet_section_lines else "(No snippets)"

    convo_lines = []
    for m in convo:
        role = m.get("role")
        content = m.get("content", "")
        if len(content) > 260:
            content = content[:260] + "…"
        convo_lines.append(f"{role}: {content}")
    convo_block = "\n".join(convo_lines) if convo_lines else "(No messages)"

    summary_prompt = (
        "You are Junior Lecturer summarizing an inline micro-session. Produce a concise, structured summary.\n"
        "Sections required in order: 1) Snippet Overviews 2) Key Q&A Themes 3) Outstanding Questions (if any) 4) Suggested Next Follow-ups (max 3).\n"
        "Use bullet lists, keep total under ~220 words.\n\n"
        f"SNIPPETS:\n{snippet_block}\n\nRECENT EXCHANGES:\n{convo_block}\n\nGenerate the summary now." )

    try:
        summary_text = await ai_service.get_response(
            prompt=summary_prompt,
            history=[],  # isolated summarization
            state="mini_inline_summary",
            pinecone_context=None,
            neo4j_facts=None,
            profile=None,
            user_facts_semantic=None,
            persistent_memories=None,
            system_override=_SYSTEM_PROMPT,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Summarization failed: {e}")

    msg_id = mini_messages.insert_one({
        "mini_thread_id": thread_id,
        "role": "assistant",
        "content": summary_text,
        "snippet_id": None,
        "summary": True,
        "created_at": datetime.utcnow(),
    }).inserted_id

    return SummarizeResponse(summary_message_id=str(msg_id), summary=summary_text)
