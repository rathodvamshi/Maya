# backend/tests/test_task_api_integration.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from bson import ObjectId
from app.main import app
from app.models import TaskStatus, TaskPriority


class TestTaskAPI:
    """Integration tests for task API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "user_id": "test_user_123",
            "email": "test@example.com",
            "username": "testuser"
        }

    @pytest.fixture
    def sample_task(self):
        """Sample task data."""
        return {
            "_id": ObjectId(),
            "user_id": "test_user_123",
            "title": "Test Task",
            "description": "Test description",
            "status": TaskStatus.TODO.value,
            "priority": TaskPriority.MEDIUM.value,
            "due_date": datetime.utcnow() + timedelta(hours=1),
            "tags": ["test"],
            "recurrence": "none",
            "notify_channel": "email",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "celery_task_id": None,
            "metadata": {}
        }

    def test_create_task_success(self, client, mock_user, sample_task):
        """Test successful task creation."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.create_task.return_value = MagicMock(**sample_task)
            
            task_data = {
                "title": "Test Task",
                "description": "Test description",
                "priority": "medium",
                "due_date": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "tags": ["test"],
                "recurrence": "none",
                "notify_channel": "email"
            }
            
            response = client.post("/api/tasks", json=task_data)
            
            assert response.status_code == 201
            assert response.json()["title"] == "Test Task"
            assert mock_service.create_task.called

    def test_create_task_validation_error(self, client, mock_user):
        """Test task creation with validation error."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user):
            
            # Missing required title
            task_data = {
                "description": "Test description",
                "priority": "medium"
            }
            
            response = client.post("/api/tasks", json=task_data)
            
            assert response.status_code == 422  # Validation error

    def test_get_tasks(self, client, mock_user, sample_task):
        """Test getting tasks."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.list_tasks.return_value = [MagicMock(**sample_task)]
            
            response = client.get("/api/tasks")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["title"] == "Test Task"

    def test_get_task_by_id(self, client, mock_user, sample_task):
        """Test getting a specific task."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.get_task.return_value = MagicMock(**sample_task)
            
            task_id = str(sample_task["_id"])
            response = client.get(f"/api/tasks/{task_id}")
            
            assert response.status_code == 200
            assert response.json()["title"] == "Test Task"

    def test_get_task_not_found(self, client, mock_user):
        """Test getting non-existent task."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.get_task.return_value = None
            
            response = client.get("/api/tasks/nonexistent_id")
            
            assert response.status_code == 404

    def test_update_task(self, client, mock_user, sample_task):
        """Test updating a task."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            updated_task = {**sample_task, "title": "Updated Task"}
            mock_service.update_task.return_value = MagicMock(**updated_task)
            
            task_id = str(sample_task["_id"])
            update_data = {"title": "Updated Task"}
            
            response = client.put(f"/api/tasks/{task_id}", json=update_data)
            
            assert response.status_code == 200
            assert response.json()["title"] == "Updated Task"

    def test_delete_task(self, client, mock_user, sample_task):
        """Test deleting a task."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.delete_task.return_value = True
            
            task_id = str(sample_task["_id"])
            response = client.delete(f"/api/tasks/{task_id}")
            
            assert response.status_code == 200
            assert response.json()["message"] == "Task deleted successfully"

    def test_delete_task_not_found(self, client, mock_user):
        """Test deleting non-existent task."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.delete_task.return_value = False
            
            response = client.delete("/api/tasks/nonexistent_id")
            
            assert response.status_code == 404

    def test_verify_otp_success(self, client, mock_user, sample_task):
        """Test successful OTP verification."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.verify_otp.return_value = True
            
            task_id = str(sample_task["_id"])
            otp_data = {"otp": "123456"}
            
            response = client.post(f"/api/tasks/{task_id}/verify-otp", json=otp_data)
            
            assert response.status_code == 200
            assert response.json()["verified"] == True

    def test_verify_otp_failure(self, client, mock_user, sample_task):
        """Test failed OTP verification."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.verify_otp.return_value = False
            
            task_id = str(sample_task["_id"])
            otp_data = {"otp": "654321"}
            
            response = client.post(f"/api/tasks/{task_id}/verify-otp", json=otp_data)
            
            assert response.status_code == 400
            assert response.json()["detail"] == "Invalid OTP"

    def test_reschedule_task(self, client, mock_user, sample_task):
        """Test task rescheduling."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            updated_task = {**sample_task, "due_date": datetime.utcnow() + timedelta(hours=2)}
            mock_service.reschedule_task.return_value = MagicMock(**updated_task)
            
            task_id = str(sample_task["_id"])
            reschedule_data = {
                "due_date": (datetime.utcnow() + timedelta(hours=2)).isoformat()
            }
            
            response = client.post(f"/api/tasks/{task_id}/reschedule", json=reschedule_data)
            
            assert response.status_code == 200
            assert mock_service.reschedule_task.called

    def test_get_tasks_summary(self, client, mock_user, sample_task):
        """Test getting tasks summary."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.get_upcoming_tasks_summary.return_value = [MagicMock(**sample_task)]
            
            response = client.get("/api/tasks/summary")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["title"] == "Test Task"

    def test_get_task_stats(self, client, mock_user):
        """Test getting task statistics."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_stats = {
                "total": 10,
                "pending": 7,
                "completed": 3,
                "overdue": 1
            }
            mock_service.get_task_stats.return_value = mock_stats
            
            response = client.get("/api/tasks/stats")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 10
            assert data["pending"] == 7

    def test_get_task_tags(self, client, mock_user):
        """Test getting task tags."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_tags = ["work", "personal", "urgent"]
            mock_service.get_task_tags.return_value = mock_tags
            
            response = client.get("/api/tasks/tags")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            assert "work" in data
            assert "personal" in data

    def test_unauthorized_access(self, client):
        """Test unauthorized access to task endpoints."""
        # Test without authentication
        response = client.get("/api/tasks")
        assert response.status_code == 401  # Unauthorized

    def test_task_creation_with_invalid_date(self, client, mock_user):
        """Test task creation with invalid date format."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user):
            
            task_data = {
                "title": "Test Task",
                "due_date": "invalid-date-format"
            }
            
            response = client.post("/api/tasks", json=task_data)
            
            assert response.status_code == 422  # Validation error

    def test_task_update_with_past_date(self, client, mock_user, sample_task):
        """Test task update with past date."""
        with patch('app.routers.tasks.get_current_active_user', return_value=mock_user), \
             patch('app.routers.tasks.task_service') as mock_service:
            
            mock_service.update_task.side_effect = ValueError("Due date must be in the future")
            
            task_id = str(sample_task["_id"])
            update_data = {
                "due_date": (datetime.utcnow() - timedelta(hours=1)).isoformat()
            }
            
            response = client.put(f"/api/tasks/{task_id}", json=update_data)
            
            assert response.status_code == 400
            assert "future" in response.json()["detail"]
