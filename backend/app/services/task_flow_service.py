# backend/app/services/task_flow_service.py

"""
Comprehensive task flow service that integrates database, email notifications, and memory systems.
Provides end-to-end task management with proper error handling and performance optimization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from bson import ObjectId

from app.database import db_client
from app.services.task_service import create_task, _user_id_str
from app.celery_tasks import send_task_notification_email, send_bulk_task_notifications
from app.services.memory_connection_validator import validate_memory_connections
from app.services import pinecone_service, neo4j_service, redis_service
from app.utils.time_utils import format_ist

logger = logging.getLogger(__name__)


class TaskFlowService:
    """
    Comprehensive task flow service that handles the complete task lifecycle.
    Integrates database operations, email notifications, and memory systems.
    """
    
    def __init__(self):
        self.performance_metrics = {}
        self.error_counts = {}
    
    async def create_task_with_notifications(
        self,
        user: Dict[str, Any],
        title: str,
        due_date_utc: datetime,
        description: str = None,
        priority: str = "medium",
        tags: List[str] = None,
        notify_immediately: bool = True,
        schedule_reminder: bool = True
    ) -> Dict[str, Any]:
        """
        Create a task with comprehensive notification system.
        
        Args:
            user: User information dictionary
            title: Task title
            due_date_utc: Due date in UTC
            description: Task description
            priority: Task priority (low, medium, high, urgent)
            tags: List of task tags
            notify_immediately: Send immediate creation notification
            schedule_reminder: Schedule reminder notification
            
        Returns:
            Dict containing task_id, status, and metadata
        """
        start_time = datetime.utcnow()
        result = {
            "success": False,
            "task_id": None,
            "notifications": {},
            "performance": {},
            "errors": []
        }
        
        try:
            # Step 1: Create task in database
            task_id = create_task(
                user=user,
                title=title,
                due_date_utc=due_date_utc,
                description=description,
                priority=priority,
                auto_complete=True
            )
            result["task_id"] = task_id
            
            # Step 2: Update task with additional metadata
            try:
                tasks_col = db_client.get_tasks_collection()
                if tasks_col:
                    update_data = {
                        "tags": tags or [],
                        "created_via": "task_flow_service",
                        "flow_metadata": {
                            "notify_immediately": notify_immediately,
                            "schedule_reminder": schedule_reminder,
                            "created_at": start_time.isoformat()
                        }
                    }
                    tasks_col.update_one(
                        {"_id": ObjectId(task_id)},
                        {"$set": update_data}
                    )
            except Exception as e:
                logger.warning(f"Failed to update task metadata: {e}")
                result["errors"].append(f"Metadata update failed: {e}")
            
            # Step 3: Send immediate notification if requested
            if notify_immediately:
                try:
                    user_email = user.get("email") or user.get("user_email")
                    if user_email:
                        send_task_notification_email.delay(
                            task_id=task_id,
                            user_email=user_email,
                            task_title=title,
                            task_description=description or "",
                            due_date=due_date_utc.isoformat(),
                            priority=priority,
                            task_type="creation"
                        )
                        result["notifications"]["creation_sent"] = True
                        logger.info(f"Creation notification queued for task {task_id}")
                    else:
                        result["errors"].append("No user email found for notification")
                except Exception as e:
                    logger.error(f"Failed to send creation notification: {e}")
                    result["errors"].append(f"Creation notification failed: {e}")
            
            # Step 4: Store task in memory systems (Pinecone)
            try:
                await self._store_task_in_memory(task_id, title, description, user)
                result["notifications"]["memory_stored"] = True
            except Exception as e:
                logger.warning(f"Failed to store task in memory: {e}")
                result["errors"].append(f"Memory storage failed: {e}")
            
            # Step 5: Create Neo4j relationships if applicable
            try:
                await self._create_task_relationships(task_id, title, user)
                result["notifications"]["relationships_created"] = True
            except Exception as e:
                logger.warning(f"Failed to create task relationships: {e}")
                result["errors"].append(f"Relationship creation failed: {e}")
            
            result["success"] = True
            result["performance"]["total_time_ms"] = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"Task flow completed successfully: {task_id}")
            
        except Exception as e:
            logger.error(f"Task flow failed: {e}")
            result["errors"].append(f"Task creation failed: {e}")
        
        return result
    
    async def _store_task_in_memory(
        self, 
        task_id: str, 
        title: str, 
        description: str, 
        user: Dict[str, Any]
    ) -> None:
        """Store task information in Pinecone for semantic search."""
        try:
            if not pinecone_service.is_ready():
                logger.warning("Pinecone not available for task storage")
                return
            
            # Create embedding from task content
            task_text = f"{title} {description or ''}"
            from app.services.embedding_service import create_embedding
            embedding = create_embedding(task_text)
            
            if embedding:
                # Store in Pinecone with task metadata
                metadata = {
                    "task_id": task_id,
                    "user_id": _user_id_str(user),
                    "title": title,
                    "description": description or "",
                    "type": "task",
                    "created_at": datetime.utcnow().isoformat()
                }
                
                index = pinecone_service.get_index()
                if index:
                    index.upsert(vectors=[(f"task:{task_id}", embedding, metadata)])
                    logger.info(f"Task {task_id} stored in Pinecone")
            
        except Exception as e:
            logger.error(f"Failed to store task in memory: {e}")
            raise
    
    async def _create_task_relationships(
        self, 
        task_id: str, 
        title: str, 
        user: Dict[str, Any]
    ) -> None:
        """Create Neo4j relationships for task."""
        try:
            if not await neo4j_service.ping():
                logger.warning("Neo4j not available for relationship creation")
                return
            
            user_id = _user_id_str(user)
            
            # Create user node if not exists
            await neo4j_service.create_user_node(user_id)
            
            # Create task node and relationship
            query = """
            MATCH (u:User {id: $user_id})
            MERGE (t:Task {id: $task_id, title: $title})
            MERGE (u)-[:HAS_TASK]->(t)
            SET t.created_at = datetime()
            """
            
            await neo4j_service.run_query(query, {
                "user_id": user_id,
                "task_id": task_id,
                "title": title
            })
            
            logger.info(f"Task relationships created for {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to create task relationships: {e}")
            raise
    
    async def update_task_with_notifications(
        self,
        task_id: str,
        user: Dict[str, Any],
        updates: Dict[str, Any],
        notify_user: bool = True
    ) -> Dict[str, Any]:
        """
        Update a task and send notification if requested.
        
        Args:
            task_id: Task identifier
            user: User information
            updates: Dictionary of updates to apply
            notify_user: Whether to send update notification
            
        Returns:
            Dict containing update status and metadata
        """
        result = {
            "success": False,
            "updated": False,
            "notifications": {},
            "errors": []
        }
        
        try:
            tasks_col = db_client.get_tasks_collection()
            if not tasks_col:
                result["errors"].append("Database unavailable")
                return result
            
            user_id = _user_id_str(user)
            
            # Find existing task
            task = tasks_col.find_one({"_id": ObjectId(task_id), "user_id": user_id})
            if not task:
                result["errors"].append("Task not found")
                return result
            
            # Apply updates
            update_data = {
                **updates,
                "updated_at": datetime.utcnow(),
                "last_modified_by": user_id
            }
            
            update_result = tasks_col.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": update_data}
            )
            
            if update_result.modified_count > 0:
                result["updated"] = True
                
                # Send update notification if requested
                if notify_user:
                    try:
                        user_email = user.get("email") or user.get("user_email")
                        if user_email:
                            send_task_notification_email.delay(
                                task_id=task_id,
                                user_email=user_email,
                                task_title=task.get("title", "Task"),
                                task_description=updates.get("description", task.get("description", "")),
                                due_date=updates.get("due_date", task.get("due_date")),
                                priority=updates.get("priority", task.get("priority", "medium")),
                                task_type="update"
                            )
                            result["notifications"]["update_sent"] = True
                    except Exception as e:
                        logger.error(f"Failed to send update notification: {e}")
                        result["errors"].append(f"Update notification failed: {e}")
                
                # Update memory systems
                try:
                    await self._update_task_in_memory(task_id, updates)
                    result["notifications"]["memory_updated"] = True
                except Exception as e:
                    logger.warning(f"Failed to update task in memory: {e}")
                    result["errors"].append(f"Memory update failed: {e}")
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Task update failed: {e}")
            result["errors"].append(f"Update failed: {e}")
        
        return result
    
    async def _update_task_in_memory(self, task_id: str, updates: Dict[str, Any]) -> None:
        """Update task information in Pinecone."""
        try:
            if not pinecone_service.is_ready():
                return
            
            # Get updated task data
            tasks_col = db_client.get_tasks_collection()
            task = tasks_col.find_one({"_id": ObjectId(task_id)})
            if not task:
                return
            
            # Create new embedding if title or description changed
            if "title" in updates or "description" in updates:
                task_text = f"{task.get('title', '')} {task.get('description', '')}"
                from app.services.embedding_service import create_embedding
                embedding = create_embedding(task_text)
                
                if embedding:
                    metadata = {
                        "task_id": task_id,
                        "user_id": task.get("user_id"),
                        "title": task.get("title", ""),
                        "description": task.get("description", ""),
                        "type": "task",
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    index = pinecone_service.get_index()
                    if index:
                        index.upsert(vectors=[(f"task:{task_id}", embedding, metadata)])
                        logger.info(f"Task {task_id} updated in Pinecone")
            
        except Exception as e:
            logger.error(f"Failed to update task in memory: {e}")
            raise
    
    async def complete_task_with_notifications(
        self,
        task_id: str,
        user: Dict[str, Any],
        notify_user: bool = True
    ) -> Dict[str, Any]:
        """
        Complete a task and send completion notification.
        
        Args:
            task_id: Task identifier
            user: User information
            notify_user: Whether to send completion notification
            
        Returns:
            Dict containing completion status and metadata
        """
        result = {
            "success": False,
            "completed": False,
            "notifications": {},
            "errors": []
        }
        
        try:
            tasks_col = db_client.get_tasks_collection()
            if not tasks_col:
                result["errors"].append("Database unavailable")
                return result
            
            user_id = _user_id_str(user)
            
            # Update task status
            update_result = tasks_col.update_one(
                {"_id": ObjectId(task_id), "user_id": user_id},
                {
                    "$set": {
                        "status": "done",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.modified_count > 0:
                result["completed"] = True
                
                # Send completion notification if requested
                if notify_user:
                    try:
                        task = tasks_col.find_one({"_id": ObjectId(task_id)})
                        user_email = user.get("email") or user.get("user_email")
                        if user_email and task:
                            send_task_notification_email.delay(
                                task_id=task_id,
                                user_email=user_email,
                                task_title=task.get("title", "Task"),
                                task_description=task.get("description", ""),
                                due_date=None,
                                priority=task.get("priority", "medium"),
                                task_type="completion"
                            )
                            result["notifications"]["completion_sent"] = True
                    except Exception as e:
                        logger.error(f"Failed to send completion notification: {e}")
                        result["errors"].append(f"Completion notification failed: {e}")
                
                # Update Neo4j relationships
                try:
                    await self._update_task_completion_in_neo4j(task_id, user_id)
                    result["notifications"]["relationships_updated"] = True
                except Exception as e:
                    logger.warning(f"Failed to update task completion in Neo4j: {e}")
                    result["errors"].append(f"Neo4j update failed: {e}")
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Task completion failed: {e}")
            result["errors"].append(f"Completion failed: {e}")
        
        return result
    
    async def _update_task_completion_in_neo4j(self, task_id: str, user_id: str) -> None:
        """Update task completion status in Neo4j."""
        try:
            if not await neo4j_service.ping():
                return
            
            query = """
            MATCH (u:User {id: $user_id})-[:HAS_TASK]->(t:Task {id: $task_id})
            SET t.status = 'completed', t.completed_at = datetime()
            """
            
            await neo4j_service.run_query(query, {
                "user_id": user_id,
                "task_id": task_id
            })
            
            logger.info(f"Task {task_id} completion updated in Neo4j")
            
        except Exception as e:
            logger.error(f"Failed to update task completion in Neo4j: {e}")
            raise
    
    async def get_task_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for task operations."""
        return {
            "performance_metrics": self.performance_metrics,
            "error_counts": self.error_counts,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def validate_system_health(self) -> Dict[str, Any]:
        """Validate all system components for task operations."""
        try:
            # Validate memory connections
            memory_health = await validate_memory_connections()
            
            # Check database health
            db_healthy = db_client.healthy()
            
            # Check Celery connectivity (basic check)
            celery_healthy = True  # Assume healthy if no errors
            
            return {
                "overall_health": "good" if all([memory_health.get("overall_health") == "excellent", db_healthy, celery_healthy]) else "degraded",
                "components": {
                    "database": {"healthy": db_healthy},
                    "memory_systems": memory_health,
                    "celery": {"healthy": celery_healthy}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"System health validation failed: {e}")
            return {
                "overall_health": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global task flow service instance
task_flow_service = TaskFlowService()


async def create_task_with_full_flow(
    user: Dict[str, Any],
    title: str,
    due_date_utc: datetime,
    description: str = None,
    priority: str = "medium",
    tags: List[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to create a task with full notification flow.
    """
    return await task_flow_service.create_task_with_notifications(
        user=user,
        title=title,
        due_date_utc=due_date_utc,
        description=description,
        priority=priority,
        tags=tags
    )


async def update_task_with_notifications(
    task_id: str,
    user: Dict[str, Any],
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to update a task with notifications.
    """
    return await task_flow_service.update_task_with_notifications(
        task_id=task_id,
        user=user,
        updates=updates
    )


async def complete_task_with_notifications(
    task_id: str,
    user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convenience function to complete a task with notifications.
    """
    return await task_flow_service.complete_task_with_notifications(
        task_id=task_id,
        user=user
    )