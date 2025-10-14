# backend/tests/test_task_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from bson import ObjectId
from app.services.task_service import TaskService
from app.models import TaskCreate, TaskUpdate, TaskStatus, TaskPriority, TaskRecurrence, NotifyChannel


class TestTaskService:
    """Test cases for task service."""

    @pytest.fixture
    def task_service(self):
        """Create task service instance with mocked dependencies."""
        service = TaskService()
        service.tasks_collection = AsyncMock()
        service.profiles_collection = AsyncMock()
        service.redis_client = AsyncMock()
        return service

    @pytest.fixture
    def sample_task_data(self):
        """Sample task data for testing."""
        return {
            "title": "Test Task",
            "description": "Test description",
            "status": TaskStatus.TODO,
            "priority": TaskPriority.MEDIUM,
            "due_date": datetime.utcnow() + timedelta(hours=1),
            "tags": ["test"],
            "recurrence": TaskRecurrence.NONE,
            "notify_channel": NotifyChannel.EMAIL,
        }

    @pytest.mark.asyncio
    async def test_create_task_success(self, task_service, sample_task_data):
        """Test successful task creation."""
        # Mock database operations
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = ObjectId()
        task_service.tasks_collection.insert_one.return_value = mock_insert_result
        
        mock_task_doc = {
            "_id": mock_insert_result.inserted_id,
            "user_id": "user123",
            **sample_task_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "celery_task_id": None,
            "metadata": {}
        }
        task_service.tasks_collection.find_one.return_value = mock_task_doc
        
        # Mock Celery task
        with patch('app.services.task_service.send_task_otp_task') as mock_celery:
            mock_celery_result = MagicMock()
            mock_celery_result.id = "celery_task_123"
            mock_celery.apply_async.return_value = mock_celery_result
            
            task_create = TaskCreate(**sample_task_data)
            result = await task_service.create_task("user123", "test@example.com", task_create)
            
            assert result.id == mock_insert_result.inserted_id
            assert result.title == sample_task_data["title"]
            assert mock_celery.apply_async.called
            assert task_service.tasks_collection.update_one.called

    @pytest.mark.asyncio
    async def test_create_task_duplicate_check(self, task_service, sample_task_data):
        """Test duplicate task detection."""
        # Mock existing task
        existing_task = {
            "_id": ObjectId(),
            "user_id": "user123",
            "title": sample_task_data["title"],
            "due_date": sample_task_data["due_date"],
            "status": TaskStatus.TODO
        }
        task_service.tasks_collection.find_one.return_value = existing_task
        
        task_create = TaskCreate(**sample_task_data)
        
        with pytest.raises(ValueError, match="similar task"):
            await task_service.create_task("user123", "test@example.com", task_create)

    @pytest.mark.asyncio
    async def test_create_task_past_time_rejection(self, task_service):
        """Test rejection of past due dates."""
        past_time_data = {
            "title": "Test Task",
            "description": "Test description",
            "status": TaskStatus.TODO,
            "priority": TaskPriority.MEDIUM,
            "due_date": datetime.utcnow() - timedelta(hours=1),  # Past time
            "tags": [],
            "recurrence": TaskRecurrence.NONE,
            "notify_channel": NotifyChannel.EMAIL,
            "allow_past": False
        }
        
        task_create = TaskCreate(**past_time_data)
        
        with pytest.raises(ValueError, match="future"):
            await task_service.create_task("user123", "test@example.com", task_create)

    @pytest.mark.asyncio
    async def test_list_tasks(self, task_service):
        """Test task listing."""
        mock_tasks = [
            {
                "_id": ObjectId(),
                "user_id": "user123",
                "title": "Task 1",
                "status": TaskStatus.TODO,
                "due_date": datetime.utcnow() + timedelta(hours=1)
            },
            {
                "_id": ObjectId(),
                "user_id": "user123", 
                "title": "Task 2",
                "status": TaskStatus.DONE,
                "due_date": datetime.utcnow() + timedelta(hours=2)
            }
        ]
        
        task_service.tasks_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value = mock_tasks
        
        result = await task_service.list_tasks("user123")
        
        assert len(result) == 2
        assert result[0].title == "Task 1"
        assert result[1].title == "Task 2"

    @pytest.mark.asyncio
    async def test_get_task(self, task_service):
        """Test getting a single task."""
        mock_task = {
            "_id": ObjectId(),
            "user_id": "user123",
            "title": "Test Task",
            "status": TaskStatus.TODO
        }
        
        task_service.tasks_collection.find_one.return_value = mock_task
        
        result = await task_service.get_task("user123", str(mock_task["_id"]))
        
        assert result.title == "Test Task"
        assert result.status == TaskStatus.TODO

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, task_service):
        """Test getting non-existent task."""
        task_service.tasks_collection.find_one.return_value = None
        
        result = await task_service.get_task("user123", "nonexistent_id")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_task(self, task_service):
        """Test task update."""
        existing_task = MagicMock()
        existing_task.id = ObjectId()
        existing_task.due_date = datetime.utcnow() + timedelta(hours=1)
        existing_task.celery_task_id = None
        existing_task.notify_channel = NotifyChannel.EMAIL
        
        task_service.get_task.return_value = existing_task
        task_service.tasks_collection.update_one.return_value.matched_count = 1
        
        # Mock updated task
        updated_task = {
            "_id": existing_task.id,
            "user_id": "user123",
            "title": "Updated Task",
            "status": TaskStatus.TODO
        }
        task_service.tasks_collection.find_one.return_value = updated_task
        
        updates = TaskUpdate(title="Updated Task")
        result = await task_service.update_task("user123", str(existing_task.id), updates)
        
        assert result.title == "Updated Task"
        assert task_service.tasks_collection.update_one.called

    @pytest.mark.asyncio
    async def test_update_task_due_date_change(self, task_service):
        """Test task update with due date change."""
        existing_task = MagicMock()
        existing_task.id = ObjectId()
        existing_task.due_date = datetime.utcnow() + timedelta(hours=1)
        existing_task.celery_task_id = "old_celery_id"
        existing_task.notify_channel = NotifyChannel.EMAIL
        existing_task.title = "Test Task"
        
        task_service.get_task.return_value = existing_task
        task_service.tasks_collection.update_one.return_value.matched_count = 1
        
        # Mock user profile
        task_service.profiles_collection.find_one.return_value = {"email": "test@example.com"}
        
        # Mock Celery operations
        with patch('app.services.task_service.celery_app') as mock_celery_app, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            mock_celery_result = MagicMock()
            mock_celery_result.id = "new_celery_id"
            mock_celery_task.apply_async.return_value = mock_celery_result
            
            # Mock updated task
            updated_task = {
                "_id": existing_task.id,
                "user_id": "user123",
                "title": "Test Task",
                "status": TaskStatus.TODO,
                "celery_task_id": "new_celery_id"
            }
            task_service.tasks_collection.find_one.return_value = updated_task
            
            new_due_date = datetime.utcnow() + timedelta(hours=2)
            updates = TaskUpdate(due_date=new_due_date)
            result = await task_service.update_task("user123", str(existing_task.id), updates)
            
            # Verify Celery task was revoked and rescheduled
            assert mock_celery_app.control.revoke.called
            assert mock_celery_task.apply_async.called
            assert result.celery_task_id == "new_celery_id"

    @pytest.mark.asyncio
    async def test_delete_task(self, task_service):
        """Test task deletion."""
        existing_task = MagicMock()
        existing_task.id = ObjectId()
        existing_task.celery_task_id = "celery_task_123"
        
        task_service.get_task.return_value = existing_task
        task_service.tasks_collection.delete_one.return_value.deleted_count = 1
        
        # Mock Celery operations
        with patch('app.services.task_service.celery_app') as mock_celery_app:
            
            result = await task_service.delete_task("user123", str(existing_task.id))
            
            assert result == True
            assert mock_celery_app.control.revoke.called
            assert task_service.tasks_collection.delete_one.called

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, task_service):
        """Test deleting non-existent task."""
        task_service.get_task.return_value = None
        
        result = await task_service.delete_task("user123", "nonexistent_id")
        
        assert result == False

    @pytest.mark.asyncio
    async def test_reschedule_task(self, task_service):
        """Test task rescheduling."""
        existing_task = MagicMock()
        existing_task.id = ObjectId()
        existing_task.due_date = datetime.utcnow() + timedelta(hours=1)
        existing_task.celery_task_id = "old_celery_id"
        existing_task.notify_channel = NotifyChannel.EMAIL
        existing_task.title = "Test Task"
        
        task_service.get_task.return_value = existing_task
        task_service.tasks_collection.update_one.return_value.matched_count = 1
        
        # Mock user profile
        task_service.profiles_collection.find_one.return_value = {"email": "test@example.com"}
        
        # Mock Celery operations
        with patch('app.services.task_service.celery_app') as mock_celery_app, \
             patch('app.services.task_service.send_task_otp_task') as mock_celery_task:
            
            mock_celery_result = MagicMock()
            mock_celery_result.id = "new_celery_id"
            mock_celery_task.apply_async.return_value = mock_celery_result
            
            # Mock updated task
            updated_task = {
                "_id": existing_task.id,
                "user_id": "user123",
                "title": "Test Task",
                "status": TaskStatus.TODO,
                "celery_task_id": "new_celery_id"
            }
            task_service.tasks_collection.find_one.return_value = updated_task
            
            new_due_date = datetime.utcnow() + timedelta(hours=3)
            result = await task_service.reschedule_task("user123", str(existing_task.id), new_due_date)
            
            assert result.title == "Test Task"
            assert result.celery_task_id == "new_celery_id"

    @pytest.mark.asyncio
    async def test_verify_otp_success(self, task_service):
        """Test successful OTP verification."""
        task_service.redis_client.get.return_value = "123456"
        task_service.tasks_collection.update_one.return_value = True
        
        result = await task_service.verify_otp("user123", "task123", "123456")
        
        assert result == True
        assert task_service.redis_client.delete.called
        assert task_service.tasks_collection.update_one.called

    @pytest.mark.asyncio
    async def test_verify_otp_failure(self, task_service):
        """Test failed OTP verification."""
        task_service.redis_client.get.return_value = "123456"
        
        result = await task_service.verify_otp("user123", "task123", "654321")
        
        assert result == False
        assert not task_service.redis_client.delete.called

    @pytest.mark.asyncio
    async def test_verify_otp_no_redis(self, task_service):
        """Test OTP verification when Redis is unavailable."""
        task_service.redis_client = None
        
        result = await task_service.verify_otp("user123", "task123", "123456")
        
        assert result == False

    @pytest.mark.asyncio
    async def test_get_upcoming_tasks_summary(self, task_service):
        """Test getting upcoming tasks summary."""
        mock_tasks = [
            {
                "_id": ObjectId(),
                "user_id": "user123",
                "title": "Upcoming Task 1",
                "status": TaskStatus.TODO,
                "due_date": datetime.utcnow() + timedelta(hours=1)
            },
            {
                "_id": ObjectId(),
                "user_id": "user123",
                "title": "Upcoming Task 2", 
                "status": TaskStatus.TODO,
                "due_date": datetime.utcnow() + timedelta(hours=2)
            }
        ]
        
        task_service.tasks_collection.find.return_value.sort.return_value.limit.return_value = mock_tasks
        
        result = await task_service.get_upcoming_tasks_summary("user123", limit=5)
        
        assert len(result) == 2
        assert result[0].title == "Upcoming Task 1"
        assert result[1].title == "Upcoming Task 2"
