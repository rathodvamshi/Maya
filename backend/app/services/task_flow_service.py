# backend/app/services/task_flow_service.py

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.services.redis_service import get_client as get_redis
from app.services import task_nlp, task_service

logger = logging.getLogger(__name__)


class TaskFlowState:
    """Redis-backed conversation state machine for task creation."""
    
    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.redis_key = f"task_flow:{self.user_id}"
        self.ttl_seconds = 15 * 60  # 15 minutes
    
    async def get_state(self) -> Optional[Dict[str, Any]]:
        """Get current flow state from Redis."""
        client = get_redis()
        if not client:
            return None
        try:
            data = await client.get(self.redis_key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get task flow state for {self.user_id}: {e}")
        return None
    
    async def set_state(self, state: Dict[str, Any]) -> bool:
        """Set flow state in Redis with TTL."""
        client = get_redis()
        if not client:
            return False
        try:
            state["updated_at"] = datetime.utcnow().isoformat()
            await client.setex(self.redis_key, self.ttl_seconds, json.dumps(state))
            logger.info(f"[FLOW_STATE] user_id={self.user_id} step={state.get('step')}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set task flow state for {self.user_id}: {e}")
            return False
    
    async def clear_state(self) -> bool:
        """Clear flow state from Redis."""
        client = get_redis()
        if not client:
            return False
        try:
            await client.delete(self.redis_key)
            logger.info(f"[FLOW_STATE] Cleared state for user_id={self.user_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to clear task flow state for {self.user_id}: {e}")
            return False
    
    async def update_draft_task(self, updates: Dict[str, Any]) -> bool:
        """Update the draft task in the current state."""
        state = await self.get_state()
        if not state:
            return False
        
        if "draft_task" not in state:
            state["draft_task"] = {}
        
        state["draft_task"].update(updates)
        return await self.set_state(state)


async def handle_task_intent(message: str, user_id: str, user_timezone: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for task intent handling with clarification flow.
    Returns response dict with message and next action.
    """
    flow = TaskFlowState(user_id)
    current_state = await flow.get_state()
    
    # If no current state, start fresh
    if not current_state:
        return await _start_new_task_flow(message, user_id, user_timezone, flow)
    
    # Handle continuation based on current step
    step = current_state.get("step")
    
    if step == "awaiting_time":
        return await _handle_time_response(message, current_state, flow)
    elif step == "awaiting_optional":
        return await _handle_optional_response(message, current_state, flow)
    elif step == "awaiting_confirm":
        return await _handle_confirmation_response(message, current_state, flow, user_id)
    else:
        # Unknown state, restart
        await flow.clear_state()
        return await _start_new_task_flow(message, user_id, user_timezone, flow)


async def _start_new_task_flow(message: str, user_id: str, user_timezone: Optional[str], flow: TaskFlowState) -> Dict[str, Any]:
    """Start a new task creation flow."""
    # Extract entities with ambiguity detection
    result = task_nlp.extract_task_entities(message, user_timezone)
    entities = result.get("entities", {})
    
    if result.get("needs_clarification"):
        reason = result.get("clarification_reason")
        
        # Store initial state
        state = {
            "step": "awaiting_time" if reason == "missing_time" else "awaiting_clarification",
            "draft_task": entities,
            "clarification_reason": reason,
            "ambiguities": result.get("ambiguities", {}),
            "validation_issues": result.get("validation_issues", []),
            "user_id": user_id,
            "user_timezone": user_timezone,
            "created_at": datetime.utcnow().isoformat(),
        }
        await flow.set_state(state)
        
        # Generate clarification message
        clarification_msg = _generate_clarification_message(reason, result)
        return {
            "message": clarification_msg,
            "needs_response": True,
            "flow_state": state,
            "action": "clarify"
        }
    
    # All entities present, move to confirmation
    state = {
        "step": "awaiting_confirm",
        "draft_task": entities,
        "user_id": user_id,
        "user_timezone": user_timezone,
        "created_at": datetime.utcnow().isoformat(),
    }
    await flow.set_state(state)
    
    confirmation_msg = _generate_confirmation_message(entities, user_timezone)
    return {
        "message": confirmation_msg,
        "needs_response": True,
        "flow_state": state,
        "action": "confirm"
    }


async def _handle_time_response(message: str, current_state: Dict[str, Any], flow: TaskFlowState) -> Dict[str, Any]:
    """Handle user's time response."""
    user_tz = current_state.get("user_timezone", "UTC")
    result = task_nlp.extract_task_entities(message, user_tz)
    entities = result.get("entities", {})
    
    if not entities.get("due_date"):
        return {
            "message": "I still couldn't understand the time. Can you try something like '8pm today' or 'in 2 hours'?",
            "needs_response": True,
            "action": "retry_time"
        }
    
    # Update draft with time
    await flow.update_draft_task({"due_date": entities["due_date"]})
    
    # Move to optional details
    state = {
        "step": "awaiting_optional",
        "draft_task": {**current_state["draft_task"], "due_date": entities["due_date"]},
        "created_at": current_state["created_at"],
    }
    await flow.set_state(state)
    
    return {
        "message": "Great! Any notes or priority level for this reminder?",
        "needs_response": True,
        "flow_state": state,
        "action": "optional"
    }


async def _handle_optional_response(message: str, current_state: Dict[str, Any], flow: TaskFlowState) -> Dict[str, Any]:
    """Handle optional details (notes, priority)."""
    result = task_nlp.extract_task_entities(message, current_state.get("user_timezone", "UTC"))
    entities = result.get("entities", {})
    
    updates = {}
    if entities.get("notes"):
        updates["notes"] = entities["notes"]
    if entities.get("priority"):
        updates["priority"] = entities["priority"]
    
    if updates:
        await flow.update_draft_task(updates)
    
    # Move to confirmation
    draft_task = {**current_state["draft_task"], **updates}
    state = {
        "step": "awaiting_confirm",
        "draft_task": draft_task,
        "created_at": current_state["created_at"],
    }
    await flow.set_state(state)
    
    confirmation_msg = _generate_confirmation_message(draft_task, current_state.get("user_timezone", "UTC"))
    return {
        "message": confirmation_msg,
        "needs_response": True,
        "flow_state": state,
        "action": "confirm"
    }


async def _handle_confirmation_response(message: str, current_state: Dict[str, Any], flow: TaskFlowState, user_id: str) -> Dict[str, Any]:
    """Handle confirmation response."""
    low = message.lower().strip()
    
    if any(word in low for word in ["yes", "confirm", "correct", "right", "ok", "okay"]):
        # Create the task
        try:
            draft_task = current_state["draft_task"]
            # Convert to task_service format
            task_data = {
                "title": draft_task.get("title"),
                "description": draft_task.get("notes"),
                "priority": draft_task.get("priority", "medium"),
                "due_date": draft_task.get("due_date"),
                "tags": [],
                "recurrence": "none",
                "notify_channel": "email",
            }
            
            # Actually create the task using task_service
            from app.database import get_user_profile_collection
            
            # Get user email from profile
            profiles_collection = get_user_profile_collection()
            user_profile = await profiles_collection.find_one({"user_id": user_id})
            user_email = user_profile.get("email") if user_profile else None
            
            if not user_email:
                return {
                    "message": "I couldn't find your email address. Please update your profile to receive reminders.",
                    "needs_response": False,
                    "action": "error"
                }
            
            # Create task using task_service
            task_id = task_service.create_task(
                user={"user_id": user_id, "email": user_email},
                title=draft_task.get("title"),
                due_date_utc=draft_task.get("due_date"),
                description=draft_task.get("notes"),
                priority=draft_task.get("priority", "normal"),
                auto_complete=True
            )
            
            await flow.clear_state()
            
            return {
                "message": f"✅ Reminder created: '{draft_task.get('title')}' scheduled successfully!",
                "needs_response": False,
                "action": "created",
                "task_data": task_data,
                "task_id": task_id
            }
        except Exception as e:
            logger.exception(f"Failed to create task: {e}")
            return {
                "message": "Sorry, I had trouble creating that reminder. Let's try again.",
                "needs_response": True,
                "action": "retry"
            }
    
    elif any(word in low for word in ["no", "cancel", "stop", "abort"]):
        await flow.clear_state()
        return {
            "message": "No problem! Reminder cancelled.",
            "needs_response": False,
            "action": "cancelled"
        }
    
    else:
        return {
            "message": "Please say 'yes' to confirm or 'no' to cancel.",
            "needs_response": True,
            "action": "retry_confirm"
        }


def _generate_clarification_message(reason: str, result: Dict[str, Any]) -> str:
    """
    Enhanced clarification message generation covering all test cases.
    """
    ambiguities = result.get("ambiguities", {})
    validation_issues = result.get("validation_issues", [])
    
    if reason == "missing_time":
        return "At what time should I remind you?"
    
    elif reason == "vague_time":
        vague_phrases = ambiguities.get("vague_phrases_found", [])
        if vague_phrases:
            return f"I see you mentioned '{vague_phrases[0]}'. Could you be more specific about the time? For example, '8pm today' or 'in 2 hours'?"
        return "Could you be more specific about the time? For example, '8pm today' or 'in 2 hours'?"
    
    elif reason == "ambiguous_time":
        time_matches = ambiguities.get("time_matches", [])
        if time_matches:
            times = ", ".join(time_matches[:3])  # Show max 3 times
            return f"I found multiple times: {times}. Which one should I use?"
        return "I'm not sure which time you meant. Can you clarify?"
    
    elif reason == "conflicting_times":
        return "I noticed conflicting time references (like 'yesterday' and 'today'). Which date should I use?"
    
    elif reason == "incomplete_time":
        return "It looks like your message was cut off. What time should I schedule this for?"
    
    elif reason == "meal_context":
        context_phrases = ambiguities.get("context_phrases_found", [])
        if context_phrases:
            phrase = context_phrases[0]
            if "lunch" in phrase:
                return "What time do you usually have lunch? I can set the reminder for after that."
            elif "dinner" in phrase:
                return "What time do you usually have dinner? I can set the reminder for before that."
            elif "breakfast" in phrase:
                return "What time do you usually have breakfast? I can set the reminder for after that."
        return "What time should I schedule this for?"
    
    elif reason == "recurring_not_supported":
        return "Recurring reminders are not yet supported. Would you like to create a one-time reminder instead?"
    
    elif reason == "validation_issues":
        if validation_issues:
            issue = validation_issues[0]
            if issue["type"] == "past_time":
                return f"{issue['message']}"
            elif issue["type"] == "auto_bump":
                return f"{issue['message']}"
            elif issue["type"] == "missing_title":
                return f"{issue['message']}"
            elif issue["type"] == "title_too_short":
                return f"{issue['message']}"
            elif issue["type"] == "time_adjustment":
                return f"{issue['message']}"
        return "There seems to be an issue with the information provided. Can you try again?"
    
    return "I need a bit more information. Can you clarify?"


def _generate_confirmation_message(entities: Dict[str, Any], user_timezone: Optional[str]) -> str:
    """Generate confirmation message showing all detected details."""
    title = entities.get("title", "Reminder")
    due_date = entities.get("due_date")
    priority = entities.get("priority", "normal")
    notes = entities.get("notes")
    
    # Format time for display
    time_str = "No time set"
    if due_date:
        try:
            # Convert to user's timezone for display
            if user_timezone and user_timezone != "UTC":
                import pytz
                from zoneinfo import ZoneInfo
                try:
                    utc_aware = due_date.replace(tzinfo=pytz.UTC)
                    local_time = utc_aware.astimezone(ZoneInfo(user_timezone))
                    time_str = local_time.strftime("%I:%M %p on %B %d")
                except Exception:
                    time_str = due_date.strftime("%I:%M %p on %B %d")
            else:
                time_str = due_date.strftime("%I:%M %p on %B %d")
        except Exception:
            time_str = str(due_date)
    
    msg = f"🕗 Reminder summary:\n"
    msg += f"Task: {title}\n"
    msg += f"Time: {time_str}\n"
    msg += f"Priority: {priority.title()}\n"
    if notes:
        msg += f"Notes: {notes}\n"
    msg += f"\n✅ Confirm or 📝 Edit?"
    
    return msg
