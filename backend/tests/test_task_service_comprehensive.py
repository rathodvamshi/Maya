# backend/tests/test_task_service_comprehensive.py
"""
Comprehensive test suite for task service as specified in requirements.
Tests create, schedule, reschedule, delete, revoke (10+ test cases).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from bson import ObjectId

from app.services.task_service import create_task, reschedule_task, delete_task, verify_otp


class TestTaskServiceComprehensive:
    """Comprehensive test suite for task service."""

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
        collection.delete_one.return_value = Mock(deleted_count=1)
        return collection

    @pytest.fixture
    def mock_db_client(self, mock_db_collection):
        """Mock database client."""
        client = Mock()
        client.healthy.return_value = True
        client.get_tasks_collection.return_value = mock_db_collection
        return client

    def test_create_task_creates_doc_and_schedules(self, mock_user, mock_db_collection):
        """Test: create_task() returns task_id, DB record exists."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock Celery task
            mock_async_result = Mock()
            mock_async_result.id = "celery_task_123"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Create task
            due_date = datetime.utcnow() + timedelta(hours=1)
            task_id = create_task(
                user=mock_user,
                title="Test Task",
                due_date_utc=due_date,
                description="Test description",
                priority="high",
                auto_complete=True
            )
            
            # Verify task was created
            assert task_id is not None
            assert isinstance(task_id, str)
            
            # Verify database insert was called
            mock_db_collection.insert_one.assert_called_once()
            insert_call = mock_db_collection.insert_one.call_args[0][0]
            assert insert_call["title"] == "Test Task"
            assert insert_call["user_id"] == "test_user_123"
            assert insert_call["due_date"] == due_date
            assert insert_call["auto_complete_after_email"] is True
            
            # Verify Celery task was scheduled
            mock_celery_task.apply_async.assert_called_once()
            celery_args = mock_celery_task.apply_async.call_args
            assert celery_args[1]["args"][0] == task_id  # task_id
            assert celery_args[1]["args"][1] == "test@example.com"  # email
            assert celery_args[1]["args"][2] == "Test Task"  # title
            assert celery_args[1]["eta"] == due_date

    def test_create_task_without_email(self, mock_user, mock_db_collection):
        """Test create_task when user has no email."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # User without email
            user_no_email = {"user_id": "test_user_123"}
            
            due_date = datetime.utcnow() + timedelta(hours=1)
            task_id = create_task(
                user=user_no_email,
                title="Test Task",
                due_date_utc=due_date
            )
            
            # Task should still be created
            assert task_id is not None
            mock_db_collection.insert_one.assert_called_once()
            
            # But Celery task should not be scheduled
            mock_celery_task.apply_async.assert_not_called()

    def test_create_task_database_unavailable(self, mock_user):
        """Test create_task when database is unavailable."""
        with patch('app.services.task_service.db_client') as mock_db:
            mock_db.healthy.return_value = False
            
            due_date = datetime.utcnow() + timedelta(hours=1)
            
            with pytest.raises(RuntimeError, match="Database unavailable"):
                create_task(
                    user=mock_user,
                    title="Test Task",
                    due_date_utc=due_date
                )

    def test_reschedule_task_revokes_old_and_schedules_new(self, mock_user, mock_db_collection):
        """Test reschedule_task revokes old Celery task and schedules new one."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task, \
             patch('app.services.task_service.celery_app') as mock_celery_app:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "Test Task",
                "celery_task_id": "old_celery_id"
            }
            mock_db_collection.find_one.return_value = existing_task
            
            # Mock Celery control
            mock_celery_app.control.revoke.return_value = None
            
            # Mock new Celery task
            mock_async_result = Mock()
            mock_async_result.id = "new_celery_id"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Reschedule task
            new_due_date = datetime.utcnow() + timedelta(hours=2)
            result = reschedule_task(mock_user, str(existing_task["_id"]), new_due_date)
            
            # Verify old task was revoked
            mock_celery_app.control.revoke.assert_called_once_with("old_celery_id", terminate=False)
            
            # Verify task was updated
            mock_db_collection.update_one.assert_called()
            
            # Verify new Celery task was scheduled
            mock_celery_task.apply_async.assert_called_once()

    def test_reschedule_task_not_found(self, mock_user, mock_db_collection):
        """Test reschedule_task when task is not found."""
        with patch('app.services.task_service.db_client') as mock_db:
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            mock_db_collection.find_one.return_value = None
            
            with pytest.raises(ValueError, match="not_found"):
                reschedule_task(mock_user, "nonexistent_task_id", datetime.utcnow() + timedelta(hours=1))

    def test_delete_task_revokes_celery_and_deletes_doc(self, mock_user, mock_db_collection):
        """Test delete_task revokes Celery task and deletes document."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.celery_app') as mock_celery_app:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "celery_task_id": "celery_task_id"
            }
            mock_db_collection.find_one.return_value = existing_task
            
            # Mock Celery control
            mock_celery_app.control.revoke.return_value = None
            
            # Delete task
            result = delete_task(mock_user, str(existing_task["_id"]))
            
            # Verify Celery task was revoked
            mock_celery_app.control.revoke.assert_called_once_with("celery_task_id", terminate=False)
            
            # Verify document was deleted
            mock_db_collection.delete_one.assert_called_once()
            assert result is True

    def test_delete_task_not_found(self, mock_user, mock_db_collection):
        """Test delete_task when task is not found."""
        with patch('app.services.task_service.db_client') as mock_db:
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            mock_db_collection.find_one.return_value = None
            
            result = delete_task(mock_user, "nonexistent_task_id")
            assert result is False

    def test_verify_otp_correct_otp(self, mock_user, mock_db_collection):
        """Test verify_otp with correct OTP."""
        with patch('app.services.task_service.get_redis') as mock_get_redis, \
             patch('app.services.task_service.db_client') as mock_db:
            
            # Mock Redis client
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Redis get operation
            import asyncio
            async def mock_get(key):
                return "123456"
            mock_redis.get = mock_get
            
            # Mock Redis delete operation
            async def mock_delete(key):
                return 1
            mock_redis.delete = mock_delete
            
            # Mock database
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Verify OTP
            result = verify_otp(mock_user, "task_id", "123456")
            
            assert result["verified"] is True

    def test_verify_otp_incorrect_otp(self, mock_user):
        """Test verify_otp with incorrect OTP."""
        with patch('app.services.task_service.get_redis') as mock_get_redis:
            # Mock Redis client
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Redis get operation
            async def mock_get(key):
                return "123456"
            mock_redis.get = mock_get
            
            # Verify OTP with wrong code
            result = verify_otp(mock_user, "task_id", "654321")
            
            assert result["verified"] is False
            assert result["reason"] == "otp_mismatch"

    def test_verify_otp_expired_otp(self, mock_user):
        """Test verify_otp with expired OTP."""
        with patch('app.services.task_service.get_redis') as mock_get_redis:
            # Mock Redis client
            mock_redis = Mock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Redis get operation (returns None for expired)
            async def mock_get(key):
                return None
            mock_redis.get = mock_get
            
            # Verify OTP
            result = verify_otp(mock_user, "task_id", "123456")
            
            assert result["verified"] is False
            assert result["reason"] == "otp_expired_or_missing"

    def test_verify_otp_redis_unavailable(self, mock_user):
        """Test verify_otp when Redis is unavailable."""
        with patch('app.services.task_service.get_redis') as mock_get_redis:
            mock_get_redis.return_value = None
            
            with pytest.raises(RuntimeError, match="redis_unavailable"):
                verify_otp(mock_user, "task_id", "123456")

    def test_create_task_duplicate_prevention(self, mock_user, mock_db_collection):
        """Test that create_task prevents duplicates within ±5 minutes."""
        with patch('app.services.task_service.db_client') as mock_db:
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task found
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "Test Task",
                "due_date": datetime.utcnow() + timedelta(hours=1)
            }
            mock_db_collection.find_one.return_value = existing_task
            
            due_date = datetime.utcnow() + timedelta(hours=1)
            
            with pytest.raises(ValueError, match="duplicate_task_window"):
                create_task(
                    user=mock_user,
                    title="Test Task",
                    due_date_utc=due_date
                )

    def test_create_task_past_date_validation(self, mock_user, mock_db_collection):
        """Test that create_task validates due_date is in the future."""
        with patch('app.services.task_service.db_client') as mock_db:
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            mock_db_collection.find_one.return_value = None  # No duplicate
            
            # Past date
            past_date = datetime.utcnow() - timedelta(hours=1)
            
            with pytest.raises(ValueError, match="due_date must be in the future"):
                create_task(
                    user=mock_user,
                    title="Test Task",
                    due_date_utc=past_date
                )

    def test_create_task_logging(self, mock_user, mock_db_collection):
        """Test that create_task logs appropriate messages."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task, \
             patch('app.services.task_service.logger') as mock_logger:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock Celery task
            mock_async_result = Mock()
            mock_async_result.id = "celery_task_123"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            due_date = datetime.utcnow() + timedelta(hours=1)
            task_id = create_task(
                user=mock_user,
                title="Test Task",
                due_date_utc=due_date
            )
            
            # Verify logging calls
            assert mock_logger.info.call_count >= 2  # At least TASK_CREATED and OTP_SCHEDULED
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("[TASK_CREATED]" in call for call in log_calls)
            assert any("[OTP_SCHEDULED]" in call for call in log_calls)

    def test_reschedule_task_celery_revoke_failure(self, mock_user, mock_db_collection):
        """Test reschedule_task handles Celery revoke failure gracefully."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task, \
             patch('app.services.task_service.celery_app') as mock_celery_app:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "title": "Test Task",
                "celery_task_id": "old_celery_id"
            }
            mock_db_collection.find_one.return_value = existing_task
            
            # Mock Celery control to raise exception
            mock_celery_app.control.revoke.side_effect = Exception("Revoke failed")
            
            # Mock new Celery task
            mock_async_result = Mock()
            mock_async_result.id = "new_celery_id"
            mock_celery_task.apply_async.return_value = mock_async_result
            
            # Reschedule should still work despite revoke failure
            new_due_date = datetime.utcnow() + timedelta(hours=2)
            result = reschedule_task(mock_user, str(existing_task["_id"]), new_due_date)
            
            # Should still update the task and schedule new Celery task
            mock_db_collection.update_one.assert_called()
            mock_celery_task.apply_async.assert_called_once()

    def test_delete_task_celery_revoke_failure(self, mock_user, mock_db_collection):
        """Test delete_task handles Celery revoke failure gracefully."""
        with patch('app.services.task_service.db_client') as mock_db, \
             patch('app.services.task_service.celery_app') as mock_celery_app:
            
            mock_db.healthy.return_value = True
            mock_db.get_tasks_collection.return_value = mock_db_collection
            
            # Mock existing task
            existing_task = {
                "_id": ObjectId(),
                "user_id": "test_user_123",
                "celery_task_id": "celery_task_id"
            }
            mock_db_collection.find_one.return_value = existing_task
            
            # Mock Celery control to raise exception
            mock_celery_app.control.revoke.side_effect = Exception("Revoke failed")
            
            # Delete should still work despite revoke failure
            result = delete_task(mock_user, str(existing_task["_id"]))
            
            # Should still delete the document
            mock_db_collection.delete_one.assert_called_once()
            assert result is True
