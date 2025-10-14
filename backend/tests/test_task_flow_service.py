# backend/tests/test_task_flow_service.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from app.services import task_flow_service


class TestTaskFlowService:
    """Test cases for task flow service."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        client = AsyncMock()
        client.get.return_value = None
        client.setex.return_value = True
        client.delete.return_value = True
        return client

    @pytest.fixture
    def mock_task_service(self):
        """Mock task service."""
        service = AsyncMock()
        service.create_task.return_value = MagicMock(id="test_task_id")
        return service

    @pytest.mark.asyncio
    async def test_start_new_task_flow_complete(self, mock_redis_client, mock_task_service):
        """Test starting a new task flow with complete information."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp, \
             patch('app.services.task_flow_service.task_service', mock_task_service):
            
            # Mock NLP to return complete entities
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": datetime.utcnow() + timedelta(hours=1),
                    "priority": "medium",
                    "notes": None
                },
                "needs_clarification": False,
                "confidence": 0.9
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me to call mom at 8pm", "user123", "UTC"
            )
            
            assert result["action"] == "confirm"
            assert result["needs_response"] == True
            assert "call mom" in result["message"]
            assert mock_redis_client.setex.called

    @pytest.mark.asyncio
    async def test_start_new_task_flow_needs_clarification(self, mock_redis_client):
        """Test starting a new task flow that needs clarification."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            # Mock NLP to return incomplete entities
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": None,
                    "priority": None,
                    "notes": None
                },
                "needs_clarification": True,
                "clarification_reason": "missing_time",
                "confidence": 0.5
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me to call mom", "user123", "UTC"
            )
            
            assert result["action"] == "clarify"
            assert result["needs_response"] == True
            assert "time" in result["message"].lower()
            assert mock_redis_client.setex.called

    @pytest.mark.asyncio
    async def test_handle_time_response(self, mock_redis_client):
        """Test handling time response."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            # Mock current state
            current_state = {
                "step": "awaiting_time",
                "draft_task": {"title": "call mom"},
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Mock NLP to return time
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "due_date": datetime.utcnow() + timedelta(hours=1)
                }
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_time_response(
                "8pm today", current_state, flow
            )
            
            assert result["action"] == "optional"
            assert result["needs_response"] == True
            assert "notes" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_time_response_invalid(self, mock_redis_client):
        """Test handling invalid time response."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            # Mock current state
            current_state = {
                "step": "awaiting_time",
                "draft_task": {"title": "call mom"},
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Mock NLP to return no time
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "due_date": None
                }
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_time_response(
                "invalid time", current_state, flow
            )
            
            assert result["action"] == "retry_time"
            assert result["needs_response"] == True
            assert "understand" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_confirmation_response_yes(self, mock_redis_client, mock_task_service):
        """Test handling confirmation with yes."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_service', mock_task_service), \
             patch('app.services.task_flow_service.get_user_profile_collection') as mock_profiles:
            
            # Mock current state
            current_state = {
                "step": "awaiting_confirm",
                "draft_task": {
                    "title": "call mom",
                    "due_date": datetime.utcnow() + timedelta(hours=1),
                    "priority": "medium",
                    "notes": None
                },
                "user_id": "user123",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Mock user profile
            mock_profile = {"email": "test@example.com"}
            mock_profiles.return_value.find_one.return_value = mock_profile
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_confirmation_response(
                "yes", current_state, flow, "user123"
            )
            
            assert result["action"] == "created"
            assert result["needs_response"] == False
            assert "created" in result["message"]
            assert mock_task_service.create_task.called
            assert mock_redis_client.delete.called

    @pytest.mark.asyncio
    async def test_handle_confirmation_response_no(self, mock_redis_client):
        """Test handling confirmation with no."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client):
            
            # Mock current state
            current_state = {
                "step": "awaiting_confirm",
                "draft_task": {"title": "call mom"},
                "created_at": datetime.utcnow().isoformat()
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_confirmation_response(
                "no", current_state, flow, "user123"
            )
            
            assert result["action"] == "cancelled"
            assert result["needs_response"] == False
            assert "cancelled" in result["message"]
            assert mock_redis_client.delete.called

    @pytest.mark.asyncio
    async def test_handle_confirmation_response_ambiguous(self, mock_redis_client):
        """Test handling ambiguous confirmation response."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client):
            
            # Mock current state
            current_state = {
                "step": "awaiting_confirm",
                "draft_task": {"title": "call mom"},
                "created_at": datetime.utcnow().isoformat()
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_confirmation_response(
                "maybe", current_state, flow, "user123"
            )
            
            assert result["action"] == "retry_confirm"
            assert result["needs_response"] == True
            assert "yes" in result["message"].lower()

    def test_generate_clarification_message(self):
        """Test clarification message generation."""
        result = {
            "clarification_reason": "missing_time",
            "ambiguities": {"time_matches": ["8am", "9am"]},
            "validation_issues": []
        }
        
        msg = task_flow_service._generate_clarification_message("missing_time", result)
        assert "time" in msg.lower()

    def test_generate_confirmation_message(self):
        """Test confirmation message generation."""
        entities = {
            "title": "call mom",
            "due_date": datetime.utcnow() + timedelta(hours=1),
            "priority": "medium",
            "notes": "check on her"
        }
        
        msg = task_flow_service._generate_confirmation_message(entities, "UTC")
        assert "call mom" in msg
        assert "medium" in msg.lower()
        assert "confirm" in msg.lower()

    @pytest.mark.asyncio
    async def test_task_flow_state_operations(self, mock_redis_client):
        """Test TaskFlowState operations."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client):
            
            flow = task_flow_service.TaskFlowState("user123")
            
            # Test set_state
            state = {"step": "awaiting_time", "draft_task": {}}
            result = await flow.set_state(state)
            assert result == True
            assert mock_redis_client.setex.called
            
            # Test get_state
            mock_redis_client.get.return_value = '{"step": "awaiting_time"}'
            state = await flow.get_state()
            assert state["step"] == "awaiting_time"
            
            # Test clear_state
            result = await flow.clear_state()
            assert result == True
            assert mock_redis_client.delete.called

    @pytest.mark.asyncio
    async def test_task_flow_state_no_redis(self):
        """Test TaskFlowState when Redis is unavailable."""
        with patch('app.services.task_flow_service.get_redis', return_value=None):
            
            flow = task_flow_service.TaskFlowState("user123")
            
            # All operations should return False when Redis is unavailable
            assert await flow.set_state({}) == False
            assert await flow.get_state() is None
            assert await flow.clear_state() == False
