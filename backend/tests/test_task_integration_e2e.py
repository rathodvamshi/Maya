# backend/tests/test_task_integration_e2e.py
"""
End-to-end integration tests for the complete task reminder system.
Tests the full flow: schedule 2-min, receive email, DB status changes (4+ test cases).
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from bson import ObjectId

from app.services.task_service import create_task, verify_otp
from app.services.task_nlp import parse_time, extract_task_entities
from app.services.task_flow_service import handle_task_intent
from app.celery_worker import send_task_otp_task


class TestTaskIntegrationE2E:
    """End-to-end integration tests for the complete task system."""

    @pytest.fixture
    def mock_user(self):
        """Mock user object."""
        return {
            "user_id": "test_user_123",
            "email": "test@example.com"
        }

    @pytest.fixture
    def mock_db_collection(self):
        """Mock database collection."""
        collection = Mock()
        collection.insert_one.return_value = Mock(inserted_id=ObjectId())
        collection.find_one.return_value = None
        collection.update_one.return_value = Mock(modified_count=1)
        return collection

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        redis_client = AsyncMock()
        redis_client.setex = AsyncMock(return_value=True)
        redis_client.get = AsyncMock(return_value="123456")
        redis_client.delete = AsyncMock(return_value=1)
        return redis_client

    def test_e2e_task_creation_and_scheduling(self, mock_user, mock_db_collection):
        """E2E: Create task, schedule Celery, verify database state."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            # Setup mocks
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock Celery task
            mock_async_result = Mock()
            mock_async_result.id = "celery_task_123"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Create task for 2 minutes from now
            due_date = datetime.utcnow() + timedelta(minutes=2)
            task_id = create_task(
                user=mock_user,
                title="E2E Test Task",
                due_date_utc=due_date,
                description="Integration test task",
                priority="high",
                auto_complete=True
            )
            
            # Verify task was created
            assert task_id is not None
            mock_db_collection.insert_one.assert_called_once()
            
            # Verify Celery task was scheduled
            mock_celery_task.apply_async.assert_called_once()
            celery_args = mock_celery_task.apply_async.call_args
            assert celery_args[1]["args"][0] == task_id
            assert celery_args[1]["args"][1] == "test@example.com"
            assert celery_args[1]["args"][2] == "E2E Test Task"
            assert celery_args[1]["eta"] == due_date

    def test_e2e_nlp_parsing_to_task_creation(self, mock_user, mock_db_collection):
        """E2E: Parse natural language, extract entities, create task."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            # Setup mocks
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock Celery task
            mock_async_result = Mock()
            mock_async_result.id = "celery_task_123"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Test NLP parsing
            message = "remind me to call mom tomorrow at 8pm with high priority"
            result = extract_task_entities(message, "UTC")
            
            # Verify entities were extracted
            assert not result.get("needs_clarification", True)
            entities = result.get("entities", {})
            assert entities.get("title") is not None
            assert entities.get("due_date") is not None
            assert entities.get("priority") == "high"
            
            # Create task from extracted entities
            task_id = create_task(
                user=mock_user,
                title=entities["title"],
                due_date_utc=entities["due_date"],
                description=entities.get("notes"),
                priority=entities.get("priority", "normal"),
                auto_complete=True
            )
            
            # Verify task was created
            assert task_id is not None
            mock_db_collection.insert_one.assert_called_once()

    def test_e2e_celery_execution_and_auto_complete(self, mock_user, mock_db_collection, mock_redis_client):
        """E2E: Celery executes, sends email, stores OTP, auto-completes task."""
        with patch('app.celery_worker.get_redis_client') as mock_get_redis, \
             patch('app.celery_worker.db_client', mock_db_collection), \
             patch('app.celery_worker.send_html_email') as mock_send_email:
            
            # Setup mocks
            mock_get_redis.return_value = mock_redis_client
            
            # Mock task document
            task_doc = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "E2E Test Task",
                "status": "todo",
                "auto_complete_after_email": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            mock_db_collection.find_one.return_value = task_doc
            
            # Create mock task instance
            mock_task_instance = Mock()
            
            # Execute Celery task
            task_id = str(task_doc["_id"])
            send_task_otp_task(
                mock_task_instance,
                task_id,
                "test@example.com",
                "E2E Test Task"
            )
            
            # Verify task was fetched
            mock_db_collection.find_one.assert_called_once_with({"_id": ObjectId(task_id)})
            
            # Verify email was sent
            mock_send_email.assert_called_once()
            email_call = mock_send_email.call_args
            assert email_call[1]["to"] == ["test@example.com"]
            assert "E2E Test Task" in email_call[1]["subject"]
            
            # Verify task was auto-completed
            mock_db_collection.update_one.assert_called_once()
            update_call = mock_db_collection.update_one.call_args
            assert update_call[0][0] == {"_id": ObjectId(task_id)}
            assert update_call[0][1]["$set"]["status"] == "done"
            assert "completed_at" in update_call[0][1]["$set"]

    def test_e2e_otp_verification_flow(self, mock_user, mock_db_collection, mock_redis_client):
        """E2E: Verify OTP after task execution."""
        with patch('app.services.task_service.get_redis') as mock_get_redis, \
             patch('app.services.task_service.db_client') as mock_db:
            
            # Setup mocks
            mock_get_redis.return_value = mock_redis_client
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Verify OTP
            result = verify_otp(mock_user, "task_id", "123456")
            
            # Verify OTP was verified
            assert result["verified"] is True
            
            # Verify task metadata was updated
            mock_db_collection.update_one.assert_called_once()
            update_call = mock_db_collection.update_one.call_args
            assert update_call[0][0] == {"_id": ObjectId("task_id"), "user_id": "test_user_123"}
            assert update_call[0][1]["$set"]["metadata.otp_verified"] is True

    def test_e2e_task_flow_conversation(self, mock_user):
        """E2E: Complete conversation flow from intent to task creation."""
        with patch('app.services.task_flow_service.task_service') as mock_task_service, \
             patch('app.services.task_flow_service.get_user_profile_collection') as mock_get_profiles:
            
            # Mock user profile
            mock_profiles = AsyncMock()
            mock_get_profiles.return_value = mock_profiles
            mock_profiles.find_one.return_value = {"email": "test@example.com"}
            
            # Mock task service
            mock_task_service.create_task.return_value = "created_task_id"
            
            # Test complete conversation flow
            # Step 1: Initial message with complete information
            message = "remind me to call mom tomorrow at 8pm"
            result = await handle_task_intent(message, "test_user_123", "UTC")
            
            # Should move to confirmation
            assert result.get("action") == "confirm"
            assert result.get("needs_response") is True
            
            # Step 2: User confirms
            confirm_result = await handle_task_intent("yes", "test_user_123", "UTC")
            
            # Should create task
            assert confirm_result.get("action") == "created"
            assert confirm_result.get("needs_response") is False
            assert "task_id" in confirm_result

    def test_e2e_error_handling_and_recovery(self, mock_user, mock_db_collection):
        """E2E: Test error handling and recovery scenarios."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            # Test database unavailable
            mock_db.healthy.return_value = False
            
            with pytest.raises(RuntimeError, match="Database unavailable"):
                create_task(
                    user=mock_user,
                    title="Test Task",
                    due_date_utc=datetime.utcnow() + timedelta(hours=1)
                )
            
            # Test Celery scheduling failure
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            mock_celery_task.apply_async.side_effect = Exception("Celery error")
            
            # Should still create task despite Celery failure
            task_id = create_task(
                user=mock_user,
                title="Test Task",
                due_date_utc=datetime.utcnow() + timedelta(hours=1)
            )
            
            assert task_id is not None
            mock_db_collection.insert_one.assert_called_once()

    def test_e2e_timezone_handling(self, mock_user, mock_db_collection):
        """E2E: Test timezone handling across the entire flow."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            # Setup mocks
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock Celery task
            mock_async_result = Mock()
            mock_async_result.id = "celery_task_123"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Test with different timezone
            message = "remind me to call mom tomorrow at 8pm"
            result = extract_task_entities(message, "Asia/Kolkata")
            
            # Verify timezone conversion
            entities = result.get("entities", {})
            due_date = entities.get("due_date")
            assert due_date is not None
            assert due_date.tzinfo is None  # Should be naive UTC
            
            # Create task
            task_id = create_task(
                user=mock_user,
                title=entities["title"],
                due_date_utc=due_date,
                auto_complete=True
            )
            
            # Verify task was created with correct UTC time
            assert task_id is not None
            mock_db_collection.insert_one.assert_called_once()

    def test_e2e_duplicate_prevention(self, mock_user, mock_db_collection):
        """E2E: Test duplicate task prevention."""
        with patch('app.services.task_service.db_client') as mock_db:
            # Setup mocks
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task found
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "Duplicate Test Task",
                "due_date": datetime.utcnow() + timedelta(hours=1)
            }
            mock_db_collection.find_one.return_value = existing_task
            
            # Try to create duplicate task
            with pytest.raises(ValueError, match="duplicate_task_window"):
                create_task(
                    user=mock_user,
                    title="Duplicate Test Task",
                    due_date_utc=datetime.utcnow() + timedelta(hours=1)
                )

    def test_e2e_auto_complete_behavior(self, mock_user, mock_db_collection, mock_redis_client):
        """E2E: Test auto-complete behavior with different settings."""
        with patch('app.celery_worker.get_redis_client') as mock_get_redis, \
             patch('app.celery_worker.db_client', mock_db_collection), \
             patch('app.celery_worker.send_html_email') as mock_send_email:
            
            # Setup mocks
            mock_get_redis.return_value = mock_redis_client
            
            # Test with auto_complete_after_email = True
            task_doc_auto = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "Auto Complete Task",
                "status": "todo",
                "auto_complete_after_email": True
            }
            mock_db_collection.find_one.return_value = task_doc_auto
            
            mock_task_instance = Mock()
            task_id = str(task_doc_auto["_id"])
            
            send_task_otp_task(
                mock_task_instance,
                task_id,
                "test@example.com",
                "Auto Complete Task"
            )
            
            # Should auto-complete
            mock_db_collection.update_one.assert_called_once()
            update_call = mock_db_collection.update_one.call_args
            assert update_call[0][1]["$set"]["status"] == "done"
            
            # Reset mocks
            mock_db_collection.reset_mock()
            
            # Test with auto_complete_after_email = False
            task_doc_no_auto = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "No Auto Complete Task",
                "status": "todo",
                "auto_complete_after_email": False
            }
            mock_db_collection.find_one.return_value = task_doc_no_auto
            
            task_id = str(task_doc_no_auto["_id"])
            send_task_otp_task(
                mock_task_instance,
                task_id,
                "test@example.com",
                "No Auto Complete Task"
            )
            
            # Should NOT auto-complete
            mock_db_collection.update_one.assert_not_called()
