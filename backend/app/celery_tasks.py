# backend/app/celery_tasks.py

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging
import uuid
import time

from app.celery_app import celery_app
from app.database import db_client
from app.utils import email_utils
from app.templates.email_templates import render_template
from app.services.redis_service import get_client as get_redis_client
from app.services import pinecone_service, neo4j_service, redis_service
from app.services.embedding_service import create_embedding
from app.services.pinecone_service import upsert_memory_vector
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(
    name="send_task_notification_email",
    bind=True,
    autoretry_for=(email_utils.EmailSendError,),
    retry_kwargs={"max_retries": 5, "countdown": 30},
    retry_backoff=True,
    retry_jitter=True
)
def send_task_notification_email(self, task_id: str, user_email: str, task_title: str, 
                                task_description: str = None, due_date: str = None, 
                                priority: str = "medium", task_type: str = "creation",
                                user_id: str | None = None):
    """
    Send comprehensive task notification emails with retry logic and error handling.
    
    Args:
        task_id: Unique task identifier
        user_email: Recipient email address
        task_title: Task title
        task_description: Optional task description
        due_date: Optional due date string
        priority: Task priority (low, medium, high, urgent)
        task_type: Type of notification (creation, reminder, completion, update)
    """
    trace_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    try:
        logger.info(f"[EmailTask] trace={trace_id} type={task_type} task_id={task_id} user_id={user_id or '-'} recipient={user_email}")
        
        # Generate email content based on task type
        if task_type == "creation":
            subject = f"New Task Created: {task_title}"
            html_content = render_template(
                "task_creation_email.html",
                title=task_title,
                description=task_description or "No description provided",
                due_date=due_date,
                priority=priority,
                task_id=task_id
            )
            text_content = f"New Task: {task_title}\n\nDescription: {task_description or 'No description'}\nDue: {due_date or 'No due date'}\nPriority: {priority}"
            
        elif task_type == "reminder":
            subject = f"Task Reminder: {task_title}"
            html_content = render_template(
                "task_reminder_email.html",
                title=task_title,
                due_date=due_date,
                description=task_description
            )
            text_content = f"Reminder: {task_title}\nDue: {due_date or 'Now'}\nDescription: {task_description or 'No description'}"
            
        elif task_type == "completion":
            subject = f"Task Completed: {task_title}"
            html_content = render_template(
                "task_completion_email.html",
                title=task_title,
                completed_at=datetime.utcnow()
            )
            text_content = f"Task Completed: {task_title}\nCompleted at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            
        else:  # update or other
            subject = f"Task Updated: {task_title}"
            html_content = render_template(
                "task_update_email.html",
                title=task_title,
                description=task_description,
                due_date=due_date,
                priority=priority
            )
            text_content = f"Task Updated: {task_title}\nDescription: {task_description or 'No description'}\nDue: {due_date or 'No due date'}"
        
        # Send email with retry logic
        email_utils.send_email(
            recipient=user_email,
            subject=subject,
            body=text_content,
            html=html_content,
            max_retries=3,
            retry_delay=10,
            trace_id=trace_id
        )
        
        duration = int((time.time() - start_time) * 1000)
        logger.info(f"[EmailTask] trace={trace_id} success duration={duration}ms")
        
        # Update task notification status in database
        try:
            tasks_col = db_client.get_tasks_collection()
            try:
                # Accept ObjectId or string ids
                from bson import ObjectId
                _id = ObjectId(task_id) if ObjectId.is_valid(task_id) else task_id
            except Exception:
                _id = task_id
            tasks_col.update_one({"_id": _id}, {"$set": {"last_notification_sent": datetime.utcnow()}, "$inc": {"notification_count": 1}})
        except Exception as e:
            logger.warning(f"[EmailTask] trace={trace_id} failed to update task status: {e}")

        # Activity log: email_sent
        try:
            act = db_client.get_activity_logs_collection()
            if act:
                act.insert_one({
                    "type": "email_sent",
                    "task_id": task_id,
                    "user_id": user_id,
                    "recipient": user_email,
                    "subject": subject,
                    "provider": "smtp",
                    "ok": True,
                    "timestamp": datetime.utcnow(),
                })
        except Exception:
            pass
            
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        logger.error(f"[EmailTask] trace={trace_id} failed duration={duration}ms error={e}")
        raise self.retry(exc=e)


@celery_app.task(
    name="send_bulk_task_notifications",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True
)
def send_bulk_task_notifications(self, notifications: List[Dict[str, Any]]):
    """
    Send multiple task notifications efficiently.
    
    Args:
        notifications: List of notification dictionaries with task details
    """
    trace_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    try:
        logger.info(f"[BulkEmailTask] trace={trace_id} processing {len(notifications)} notifications")
        
        success_count = 0
        failure_count = 0
        
        for notification in notifications:
            try:
                send_task_notification_email.delay(
                    task_id=notification.get("task_id"),
                    user_email=notification.get("user_email"),
                    task_title=notification.get("title"),
                    task_description=notification.get("description"),
                    due_date=notification.get("due_date"),
                    priority=notification.get("priority", "medium"),
                    task_type=notification.get("type", "creation")
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"[BulkEmailTask] trace={trace_id} failed to queue notification: {e}")
                failure_count += 1
        
        duration = int((time.time() - start_time) * 1000)
        logger.info(f"[BulkEmailTask] trace={trace_id} completed duration={duration}ms success={success_count} failures={failure_count}")
        
    except Exception as e:
        duration = int((time.time() - start_time) * 1000)
        logger.error(f"[BulkEmailTask] trace={trace_id} failed duration={duration}ms error={e}")
        raise self.retry(exc=e)


@celery_app.task(name="execute_scheduled_tasks")
def execute_scheduled_tasks() -> int:
    """Scan global tasks every minute, execute due tasks, mark user entries done, and delete global record.
    Returns number of tasks processed.
    """
    tasks_col = db_client.get_tasks_collection()
    prof_col = db_client.get_user_profile_collection()
    if not tasks_col:
        return 0
    now = datetime.now(timezone.utc)
    processed = 0
    try:
        due: List[Dict[str, Any]] = list(tasks_col.find({
            "status": "pending",
            "$or": [
                {"run_at": None},
                {"run_at": {"$lte": now.isoformat()}},
            ]
        }).limit(100))
        for doc in due:
            ok = False
            try:
                # Execute side-effect synchronously within Celery process
                ok = _execute_task_sync(doc)
            except Exception:
                ok = False

            # Update user profile entry to completed
            try:
                if prof_col and doc.get("user_id"):
                    prof_col.update_one(
                        {"_id": str(doc["user_id"])},
                        {"$set": {"tasks.$[t].status": "completed", "tasks.$[t].completed_at": datetime.utcnow()}},
                        array_filters=[{"t.task_id": str(doc.get("_id"))}],
                        upsert=True,
                    )
            except Exception:
                pass

            # Remove global task
            try:
                tasks_col.delete_one({"_id": doc.get("_id")})
            except Exception:
                pass

            processed += 1 if ok else 0
    except Exception:
        try:
            logger.debug("execute_scheduled_tasks failure", exc_info=True)
        except Exception:
            pass
    return processed


def _execute_task_sync(doc: Dict[str, Any]) -> bool:
    """Perform the task's side-effect: send notification email.
    This is the synchronous version for Celery worker.
    """
    try:
        task_id = str(doc.get("_id"))
        user_id = doc.get("user_id")
        title = doc.get("title", "Task Reminder")
        description = doc.get("description", "")
        due_date = doc.get("due_date")
        priority = doc.get("priority", "medium")
        
        # Get user email from profile
        try:
            prof_col = db_client.get_user_profile_collection()
            if prof_col and user_id:
                profile = prof_col.find_one({"_id": str(user_id)})
                if profile:
                    user_email = profile.get("email") or profile.get("user_email")
                    if user_email:
                        # Send notification email
                        send_task_notification_email.delay(
                            task_id=task_id,
                            user_email=user_email,
                            task_title=title,
                            task_description=description,
                            due_date=str(due_date) if due_date else None,
                            priority=priority,
                            task_type="reminder"
                        )
                        return True
        except Exception as e:
            logger.warning(f"Failed to send task notification: {e}")
        
        return False
    except Exception:
        return False


# =====================================================
# Memory pipeline task: embed -> pinecone upsert -> neo4j link -> notify
# =====================================================

@celery_app.task(bind=True, name="process_and_store_memory", max_retries=5, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True)
def process_and_store_memory(self, user_id: str, memory_id: str, text: str, source: str = "user"):
    trace_id = str(uuid.uuid4())[:8]
    start = time.time()
    logger.info(f"[MemoryTask] trace={trace_id} mem={memory_id} user={user_id} source={source}")
    # Ensure Neo4j sync driver is connected
    try:
        neo4j_service.neo4j_sync_service.connect(retries=3)
    except Exception as e:
        logger.warning(f"[MemoryTask] trace={trace_id} neo4j connect warning: {e}")
    try:
        # Create embedding with validation against configured Pinecone dimensions
        vector = create_embedding(text)
        required_dim = getattr(settings, "PINECONE_DIMENSIONS", 1024)
        if not vector or len(vector) != required_dim:
            raise ValueError(f"Embedding dimension mismatch: expected {required_dim}, got {len(vector) if vector else None}")
        # Upsert to Pinecone in user namespace
        metadata = {
            "user_id": user_id,
            "memory_id": memory_id,
            "source": source,
            "created_at": datetime.utcnow().isoformat(),
            "text": text,
            "snippet": (text[:200] if text else ""),
            "kind": "memory",
        }
        upsert_memory_vector(memory_id, user_id, vector, metadata)
        # Write Memory node into Neo4j and connect to user
        try:
            neo4j_service.neo4j_sync_service.create_memory_node(memory_id, text, memory_id, datetime.utcnow().isoformat(), snippet=text[:200])
            neo4j_service.neo4j_sync_service.connect_user_to_memory(user_id, memory_id)
        except Exception as e:
            logger.warning(f"[MemoryTask] trace={trace_id} neo4j write failed: {e}")
        # Notify frontend via Redis pubsub (best-effort)
        try:
            client = redis_service.get_client()
            if client:
                payload = {
                    "event": "memory_stored",
                    "user_id": user_id,
                    "memory_id": memory_id,
                    "source": source,
                    "ok": True,
                }
                channel = f"events:user:{user_id}"
                # aioredis client supports publish as async; using .publish if available else fallback
                try:
                    # prefer asyncio publish
                    import asyncio
                    if asyncio.iscoroutinefunction(client.publish):
                        asyncio.get_event_loop().create_task(client.publish(channel, __import__('json').dumps(payload)))
                    else:
                        client.publish(channel, __import__('json').dumps(payload))
                except Exception:
                    pass
        except Exception:
            pass
        dur = int((time.time() - start) * 1000)
        logger.info(f"[MemoryTask] trace={trace_id} success mem={memory_id} in {dur}ms")
        return {"ok": True, "memory_id": memory_id}
    except Exception as e:
        dur = int((time.time() - start) * 1000)
        logger.error(f"[MemoryTask] trace={trace_id} failed mem={memory_id} in {dur}ms err={e}")
        raise self.retry(exc=e, countdown=min(60, 2 ** max(1, self.request.retries)))


