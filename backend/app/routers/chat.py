# backend/app/routers/chat.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pymongo.collection import Collection
from bson import ObjectId, errors
from datetime import datetime
from typing import Optional
import asyncio
import json
import re

# -----------------------------
# Core App Imports
# -----------------------------
from app.celery_app import celery_app
from app.security import get_current_active_user
from app.services import ai_service, redis_service
from app.services.neo4j_service import neo4j_service
from app.services.memory_coordinator import gather_memory_context, post_message_update
from app.services import deterministic_extractor, profile_service
import re
from app.database import (
    get_sessions_collection,
    get_tasks_collection,
    get_chat_log_collection,
)
# Celery task names (they are registered in celery_worker)
# we don't import functions directly, just use task names
# extract_and_store_facts, prefetch_destination_info

# -----------------------------
# Router Setup
# -----------------------------
router = APIRouter(prefix="/api/chat", tags=["Chat"])

# -----------------------------
# Pydantic Models
# -----------------------------
class ChatMessage(BaseModel):
    message: str

class TaskCreate(BaseModel):
    content: str
    due_date: str

class TaskUpdate(BaseModel):
    content: Optional[str] = None
    due_date: Optional[str] = None

class NewChatRequest(BaseModel):
    message: str

class NewChatResponse(BaseModel):
    session_id: str
    response_text: str

class ContinueChatRequest(BaseModel):
    message: str

class ContinueChatResponse(BaseModel):
    response_text: str
class FeedbackBody(BaseModel):
    fact_id: str
    correction: str

# =====================================================
# 🔹 Intent Detection (Simple Rule-Based)
# =====================================================
def _detect_intent_and_entities(message: str) -> dict:
    """
    Detects basic intents (e.g., planning trips) and extracts entities.
    Extendable to ML-based NLU in future.
    """
    trip_patterns = [
        r"(?:plan|organize|book|take)\s+(?:a\s+)?(?:trip|vacation|journey)\s+to\s+([\w\s]+)",
        r"(?:go|travel)\s+to\s+([\w\s]+)",
        r"let'?s\s+go\s+to\s+([\w\s]+)"
    ]
    for pattern in trip_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            destination = match.group(1).strip()
            return {"intent": "PLAN_TRIP", "entities": {"destination": destination}}
    return {"intent": "GENERAL_INQUIRY", "entities": {}}

# Removed duplicate _gather_context; unified with memory_coordinator.gather_memory_context


# =====================================================
# 🔹 Start New Chat Session
# =====================================================
@router.post("/new", response_model=NewChatResponse)
async def start_new_chat(
    request: NewChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Starts a new chat session:
    1️⃣ Ensures user exists in Neo4j.
    2️⃣ Gathers Pinecone and Neo4j context concurrently.
    3️⃣ Generates AI response in a threadpool to avoid blocking.
    4️⃣ Saves session in MongoDB & initializes Redis session state.
    5️⃣ Dispatches background fact-extraction task.
    """
    user_id = str(current_user["_id"])
    await neo4j_service.create_user_node(user_id)

    # Inline deterministic extraction BEFORE gathering context so profile is immediately updated
    # This enables cross-session recall even after a single prior message (e.g. "My name is John").
    try:
        det = deterministic_extractor.extract(request.message, "")
        if det.get("profile_update"):
            profile_service.merge_update(user_id, **det["profile_update"])  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        pass

    # Gather all context via unified coordinator (session not yet created -> temp id)
    context = await gather_memory_context(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id="new",  # temp placeholder
        latest_user_message=request.message,
        recent_messages=[],
    )

    # Generate AI response in a threadpool
    # If user just opens with a greeting and we already know their name, craft a polite concise welcome
    lowered = request.message.strip().lower()
    quick_greet = lowered in {"hi", "hello", "hey", "hey there", "hello maya", "hi maya"}
    profile = context.get("profile") or {}
    # --- Fast-path deterministic acknowledgements ---
    ai_response_text = None
    text_lower = request.message.lower().strip()
    name = profile.get("name") if isinstance(profile, dict) else None

    # 1. Pure greeting
    if ai_response_text is None and quick_greet and name:
        ai_response_text = f"Welcome back, {name}! How can I help you today?"

    # 2. Name declaration patterns
    if ai_response_text is None:
        m_name = re.search(r"\bmy name is ([a-zA-Z][a-zA-Z '\-]{1,40})", text_lower)
        if m_name:
            declared = m_name.group(1).strip().title()
            if not name or declared.lower() != name.lower():
                try:
                    profile_service.merge_update(user_id, name=declared)
                    name = declared
                except Exception:  # noqa: BLE001
                    pass
            ai_response_text = f"Nice to meet you, {declared}! I'll remember that."

    # 3. Favorite cuisine declaration
    if ai_response_text is None:
        m_cuisine = re.search(r"\bmy (?:favorite |favourite )?cuisine is ([a-zA-Z][a-zA-Z\s]{1,40})", text_lower)
        if m_cuisine:
            cuisine_val = m_cuisine.group(1).strip().title()
            try:
                profile_service.merge_update(user_id, add_favorites={"cuisine": cuisine_val})
            except Exception:  # noqa: BLE001
                pass
            ai_response_text = f"Got it, you enjoy {cuisine_val} cuisine!"

    # 4. Hobby declaration (simple verbs)
    if ai_response_text is None:
        m_hobby = re.search(r"\bi (?:like|love|enjoy) ([a-z][a-z\s]{2,40})", text_lower)
        if m_hobby:
            hobby = m_hobby.group(1).strip()
            try:
                profile_service.merge_update(user_id, add_hobbies=[hobby])
            except Exception:  # noqa: BLE001
                pass
            ai_response_text = f"Great! I'll remember that you enjoy {hobby}."

    # Fallback to model if none of the deterministic fast-paths applied
    if ai_response_text is None:
        ai_response_text = await run_in_threadpool(
            ai_service.get_response,
            prompt=request.message,
            history=context.get("history"),
            state=context.get("state", "general_conversation"),
            pinecone_context=context.get("pinecone_context"),
            neo4j_facts=context.get("neo4j_facts"),
            profile=profile,
            user_facts_semantic=context.get("user_facts_semantic"),
        )

    # Save session in MongoDB
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    session_data = {
        "userId": current_user["_id"],
        "title": request.message[:50],
        "createdAt": datetime.utcnow(),
        "lastUpdatedAt": datetime.utcnow(),
        "isArchived": False,
        "messages": [user_message, ai_message],
    }
    result = await run_in_threadpool(sessions.insert_one, session_data)
    session_id = str(result.inserted_id)

    # Initialize Redis state
    await redis_service.set_session_state(session_id, "general_conversation")

    # Unified post-message update (history, embeddings, gated fact extraction)
    post_message_update(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        user_message=request.message,
        ai_message=ai_response_text,
        state="general_conversation",
    )

    return {"session_id": session_id, "response_text": ai_response_text}


# =====================================================
# 🔹 Start New Chat Session (Streaming)
# =====================================================
@router.post("/new/stream")
async def start_new_chat_stream(
    request: NewChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Starts a new chat session and streams the assistant's response token-by-token.
    Note: This uses a simulated streaming approach by chunking the final text.
    """
    user_id = str(current_user["_id"])
    await neo4j_service.create_user_node(user_id)

    # Inline deterministic extraction for immediate profile availability
    try:
        det = deterministic_extractor.extract(request.message, "")
        if det.get("profile_update"):
            profile_service.merge_update(user_id, **det["profile_update"])  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        pass

    context = await gather_memory_context(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id="new",
        latest_user_message=request.message,
        recent_messages=[],
    )

    # Generate AI response in background thread
    ai_response_text = await run_in_threadpool(
        ai_service.get_response,
        prompt=request.message,
        history=context.get("history"),
        state=context.get("state", "general_conversation"),
        pinecone_context=context.get("pinecone_context"),
        neo4j_facts=context.get("neo4j_facts"),
        profile=context.get("profile"),
        user_facts_semantic=context.get("user_facts_semantic"),
    )

    # Save session in MongoDB
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    session_data = {
        "userId": current_user["_id"],
        "title": request.message[:50],
        "createdAt": datetime.utcnow(),
        "lastUpdatedAt": datetime.utcnow(),
        "isArchived": False,
        "messages": [user_message, ai_message],
    }
    result = await run_in_threadpool(sessions.insert_one, session_data)
    session_id = str(result.inserted_id)

    await redis_service.set_session_state(session_id, "general_conversation")

    # Post message update (after full response assembled for streaming)
    post_message_update(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        user_message=request.message,
        ai_message=ai_response_text,
        state="general_conversation",
    )

    async def token_stream():
        # Simple word-chunk streaming; adjust chunking as needed
        words = ai_response_text.split()
        chunk = []
        for i, w in enumerate(words, 1):
            chunk.append(w)
            # Stream every ~10 words to reduce overhead
            if i % 10 == 0:
                yield " ".join(chunk) + " "
                chunk = []
                await asyncio.sleep(0)  # yield control
        if chunk:
            yield " ".join(chunk)

    headers = {"X-Session-Id": session_id}
    return StreamingResponse(token_stream(), media_type="text/plain", headers=headers)


# =====================================================
# 🔹 Continue Existing Chat Session
# =====================================================
@router.post("/{session_id}", response_model=ContinueChatResponse)
async def continue_chat(
    session_id: str,
    request: ContinueChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Continues a chat session with full context:
    - Short-term history (last 10 messages, fetched efficiently)
    - Redis session state
    - Pinecone & Neo4j memory (gathered concurrently)
    - Intent detection & proactive prefetch tasks
    - Background fact extraction
    """
    user_id = str(current_user["_id"])

    # Validate session ID
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    # Fetch session and only the last 10 messages for efficiency
    session = await run_in_threadpool(
        sessions.find_one,
        {"_id": session_obj_id, "userId": current_user["_id"]},
        {"messages": {"$slice": -10}},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Gather state and context concurrently
    context = await gather_memory_context(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        latest_user_message=request.message,
        recent_messages=session.get("messages", []),
    )
    current_state = context.get("state", "general_conversation")
    recent_history = context.get("history", [])

    # If in planning mode, check Redis for prefetched data
    prefetched_context = None
    if current_state == "planning_trip":
        cache_key = f"prefetched_info:{session_id}"
        prefetched_data = await redis_service.get_prefetched_data(cache_key)
        if prefetched_data:
            prefetched_context = f"Here is some relevant information: {json.dumps(prefetched_data)}"

    # Merge contexts
    pinecone_context = context.get("pinecone_context")
    if prefetched_context:
        pinecone_context = f"{pinecone_context}\n{prefetched_context}"

    # Generate AI response in a threadpool
    ai_response_text = await run_in_threadpool(
        ai_service.get_response,
        prompt="",  # placeholder, will be overridden if fast-path not triggered
    )  # temp call removed after patch if not needed (will be replaced below)

    # Rebuild with deterministic fast-path (override above placeholder logic)
    profile = context.get("profile") or {}
    text_lower = request.message.lower().strip()
    name = profile.get("name") if isinstance(profile, dict) else None
    fast_answer = None
    import re as _re

    # Name queries
    if any(p in text_lower for p in ["what's my name", "whats my name", "do you know my name", "do u know my name", "tell me my name"]):
        if name:
            fast_answer = ("Yes, your name is " + name + ".") if "do" in text_lower else f"Your name is {name}."
        else:
            fast_answer = "I don't have your name yet. You can tell me and I'll remember it."

    # Cuisine question
    if fast_answer is None and ("what cuisine do i like" in text_lower or "my favorite cuisine" in text_lower or "favorite cuisine" in text_lower):
        favs = profile.get("favorites") or {}
        cuisine = favs.get("cuisine") or favs.get("food")
        fast_answer = f"You enjoy {cuisine} cuisine." if cuisine else "You haven't told me your favorite cuisine yet."

    # General summary
    if fast_answer is None and any(p in text_lower for p in ["what do you know about me", "what do u know about me", "what do you know of me"]):
        favs = profile.get("favorites") or {}
        cuisine = favs.get("cuisine") or favs.get("food")
        hobbies = profile.get("hobbies") or []
        pieces = []
        if name and cuisine:
            pieces.append(f"I know your name is {name} and you enjoy {cuisine} cuisine")
        elif name:
            pieces.append(f"I know your name is {name}")
        elif cuisine:
            pieces.append(f"You enjoy {cuisine} cuisine")
        if hobbies:
            pieces.append("you like " + (", ".join(hobbies[:2]) if len(hobbies) > 1 else hobbies[0]))
        if not pieces:
            fast_answer = "I don't have personal details yet. You can share them and I'll remember."
        else:
            summary = " ".join(pieces).strip()
            if not summary.endswith('.'):
                summary += '.'
            fast_answer = summary

    # Favorites generic
    if fast_answer is None and any(p in text_lower for p in ["what are my favorites", "my favorites?", "do you know my favorites"]):
        favs = profile.get("favorites") or {}
        if favs:
            limited = list(favs.items())[:3]
            fav_str = ", ".join(f"{k}={v}" for k, v in limited)
            fast_answer = f"Your favorites I know: {fav_str}."
        else:
            fast_answer = "I don't have any favorites stored yet."

    if fast_answer is None:
        # Fall back to full model call
        ai_response_text = await run_in_threadpool(
            ai_service.get_response,
            prompt=request.message,
            history=recent_history,
            state=current_state,
            pinecone_context=pinecone_context,
            neo4j_facts=context.get("neo4j_facts"),
            profile=profile,
            user_facts_semantic=context.get("user_facts_semantic"),
        )
    else:
        ai_response_text = fast_answer

    # Intent detection
    detected = _detect_intent_and_entities(request.message)
    next_state = current_state
    if detected["intent"] == "PLAN_TRIP":
        next_state = "planning_trip"
        destination = detected["entities"].get("destination")
        if destination:
            celery_app.send_task(
                "prefetch_destination_info",
                args=[destination, session_id],
            )

    # Update Redis state
    # (state persisted via post_message_update below)

    # Save new messages
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    await run_in_threadpool(
        sessions.update_one,
        {"_id": session_obj_id},
        {
            "$push": {"messages": {"$each": [user_message, ai_message]}},
            "$set": {"lastUpdatedAt": datetime.utcnow()},
        },
    )

    # Unified post message update (embeddings + gated extraction + state)
    post_message_update(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        user_message=request.message,
        ai_message=ai_response_text,
        state=next_state,
    )

    return {"response_text": ai_response_text}


# =====================================================
# 🔹 Continue Chat (Streaming)
# =====================================================
@router.post("/{session_id}/stream")
async def continue_chat_stream(
    session_id: str,
    request: ContinueChatRequest,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
):
    """
    Continues a chat session and streams the assistant's response token-by-token.
    Uses simulated streaming by chunking the generated text.
    """
    user_id = str(current_user["_id"])

    # Validate session ID
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session = await run_in_threadpool(
        sessions.find_one,
        {"_id": session_obj_id, "userId": current_user["_id"]},
        {"messages": {"$slice": -10}},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    context = await gather_memory_context(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        latest_user_message=request.message,
        recent_messages=session.get("messages", []),
    )
    current_state = context.get("state", "general_conversation")
    recent_history = context.get("history", [])

    prefetched_context = None
    if current_state == "planning_trip":
        cache_key = f"prefetched_info:{session_id}"
        prefetched_data = await redis_service.get_prefetched_data(cache_key)
        if prefetched_data:
            prefetched_context = f"Here is some relevant information: {json.dumps(prefetched_data)}"

    pinecone_context = context.get("pinecone_context")
    if prefetched_context:
        pinecone_context = f"{pinecone_context}\n{prefetched_context}"

    ai_response_text = await run_in_threadpool(
        ai_service.get_response,
        prompt=request.message,
        history=recent_history,
        state=current_state,
        pinecone_context=pinecone_context,
        neo4j_facts=context.get("neo4j_facts"),
        profile=context.get("profile"),
        user_facts_semantic=context.get("user_facts_semantic"),
    )

    # Intent detection and background tasks (same as non-streaming)
    detected = _detect_intent_and_entities(request.message)
    next_state = current_state
    if detected["intent"] == "PLAN_TRIP":
        next_state = "planning_trip"
        destination = detected["entities"].get("destination")
        if destination:
            celery_app.send_task(
                "prefetch_destination_info",
                args=[destination, session_id],
            )
    # (state persisted via post_message_update below)

    # Save new messages
    user_message = {"sender": "user", "text": request.message}
    ai_message = {"sender": "assistant", "text": ai_response_text}
    await run_in_threadpool(
        sessions.update_one,
        {"_id": session_obj_id},
        {
            "$push": {"messages": {"$each": [user_message, ai_message]}},
            "$set": {"lastUpdatedAt": datetime.utcnow()},
        },
    )

    # Unified post message update
    post_message_update(
        user_id=user_id,
        user_key=current_user.get("email", user_id),
        session_id=session_id,
        user_message=request.message,
        ai_message=ai_response_text,
        state=next_state,
    )

    async def token_stream():
        words = ai_response_text.split()
        chunk = []
        for i, w in enumerate(words, 1):
            chunk.append(w)
            if i % 10 == 0:
                yield " ".join(chunk) + " "
                chunk = []
                await asyncio.sleep(0)
        if chunk:
            yield " ".join(chunk)

    return StreamingResponse(token_stream(), media_type="text/plain")

# =====================================================
# 🔹 Task Management Endpoints
# =====================================================
@router.post("/tasks")
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Create a new pending task for the user."""
    new_task = {
        "email": current_user["email"],
        "content": task.content,
        "due_date_str": task.due_date,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = tasks.insert_one(new_task)
    return {"status": "success", "task_id": str(result.inserted_id)}

@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task: TaskUpdate,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Update task content or due date."""
    update_data = task.model_dump(exclude_unset=True)
    if "due_date" in update_data:
        update_data["due_date_str"] = update_data.pop("due_date")
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update.")
    try:
        result = tasks.update_one(
            {"_id": ObjectId(task_id), "email": current_user["email"]},
            {"$set": update_data},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")

@router.put("/tasks/{task_id}/done")
async def mark_task_done(
    task_id: str,
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Mark a pending task as completed."""
    try:
        result = tasks.update_one(
            {"_id": ObjectId(task_id), "email": current_user["email"]},
            {"$set": {"status": "done"}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "success"}
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid task ID.")

@router.get("/tasks")
async def get_tasks(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Fetch all pending tasks for the user."""
    cursor = tasks.find({"email": current_user["email"], "status": "pending"}).sort(
        "created_at", -1
    )
    return [
        {"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")}
        for t in cursor
    ]

@router.get("/tasks/history")
async def get_task_history(
    current_user: dict = Depends(get_current_active_user),
    tasks: Collection = Depends(get_tasks_collection),
):
    """Fetch recently completed tasks (limit 10)."""
    cursor = tasks.find({"email": current_user["email"], "status": "done"}).sort(
        "created_at", -1
    ).limit(10)
    return [
        {"id": str(t["_id"]), "content": t["content"], "due_date": t.get("due_date_str")}
        for t in cursor
    ]

# =====================================================
# 🔹 Legacy Chat History Endpoints
# =====================================================
@router.get("/history")
async def get_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection),
    limit: int = 50,
):
    """Retrieve the last `limit` chat messages from the user's legacy chat log."""
    cursor = chat_logs.find({"email": current_user["email"]}).sort("timestamp", -1).limit(limit)
    return [{"sender": m["sender"], "text": m["text"]} for m in cursor]

@router.delete("/history/clear")
async def clear_chat_history(
    current_user: dict = Depends(get_current_active_user),
    chat_logs: Collection = Depends(get_chat_log_collection),
):
    """Clear all legacy chat history for the user and delete Redis session state."""
    result = chat_logs.delete_many({"email": current_user["email"]})
    try:
        if redis_service.redis_client:
            await redis_service.redis_client.delete(current_user["email"])
    except Exception:
        pass
    return {
        "status": "success",
        "message": f"Deleted {result.deleted_count} messages from legacy chat log.",
    }

# =====================================================
# 🔹 Blueprint additions: per-session history & feedback
# =====================================================
@router.get("/{session_id}/history")
async def get_session_history(
    session_id: str,
    current_user: dict = Depends(get_current_active_user),
    sessions: Collection = Depends(get_sessions_collection),
    limit: int = 50,
):
    try:
        session_obj_id = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
    doc = await run_in_threadpool(
        sessions.find_one,
        {"_id": session_obj_id, "userId": current_user["_id"]},
        {"messages": {"$slice": -limit}},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found.")
    return doc.get("messages", [])


@router.post("/{session_id}/feedback")
async def submit_session_feedback(
    session_id: str,
    body: FeedbackBody,
    current_user: dict = Depends(get_current_active_user),
):
    try:
        _ = ObjectId(session_id)
    except errors.InvalidId:
        raise HTTPException(status_code=400, detail="Invalid session ID.")

    celery_app.send_task(
        "process_feedback_task",
        kwargs={"fact_id": body.fact_id, "correction": body.correction, "user_id": str(current_user["_id"])},
    )
    return {"status": "queued"}
