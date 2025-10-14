# backend/tests/test_comprehensive_task_flow.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from app.services import task_flow_service


class TestComprehensiveTaskFlow:
    """
    Comprehensive test suite for task flow service covering all conversation
    scenarios, Redis state management, and edge cases.
    """

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

    # ========================
    # 1. Intent Detection & Flow Initiation
    # ========================
    
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
    async def test_start_new_task_flow_missing_time(self, mock_redis_client):
        """Test starting a new task flow with missing time."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
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

    @pytest.mark.asyncio
    async def test_start_new_task_flow_vague_time(self, mock_redis_client):
        """Test starting a new task flow with vague time."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": None,
                    "priority": None,
                    "notes": None
                },
                "needs_clarification": True,
                "clarification_reason": "vague_time",
                "ambiguities": {"vague_phrases_found": ["later"]},
                "confidence": 0.5
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me to call mom later", "user123", "UTC"
            )
            
            assert result["action"] == "clarify"
            assert result["needs_response"] == True
            assert "later" in result["message"]

    @pytest.mark.asyncio
    async def test_start_new_task_flow_ambiguous_time(self, mock_redis_client):
        """Test starting a new task flow with ambiguous time."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": None,
                    "priority": None,
                    "notes": None
                },
                "needs_clarification": True,
                "clarification_reason": "ambiguous_time",
                "ambiguities": {"time_matches": ["8am", "9am"]},
                "confidence": 0.5
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me at 8am or 9am", "user123", "UTC"
            )
            
            assert result["action"] == "clarify"
            assert result["needs_response"] == True
            assert "8am" in result["message"] and "9am" in result["message"]

    @pytest.mark.asyncio
    async def test_start_new_task_flow_meal_context(self, mock_redis_client):
        """Test starting a new task flow with meal context."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": None,
                    "priority": None,
                    "notes": None
                },
                "needs_clarification": True,
                "clarification_reason": "meal_context",
                "ambiguities": {"context_phrases_found": ["after lunch"]},
                "confidence": 0.5
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me to call mom after lunch", "user123", "UTC"
            )
            
            assert result["action"] == "clarify"
            assert result["needs_response"] == True
            assert "lunch" in result["message"]

    @pytest.mark.asyncio
    async def test_start_new_task_flow_recurring_not_supported(self, mock_redis_client):
        """Test starting a new task flow with recurring pattern."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "title": "call mom",
                    "due_date": None,
                    "priority": None,
                    "notes": None
                },
                "needs_clarification": True,
                "clarification_reason": "recurring_not_supported",
                "confidence": 0.5
            }
            
            result = await task_flow_service.handle_task_intent(
                "remind me every Monday to call mom", "user123", "UTC"
            )
            
            assert result["action"] == "clarify"
            assert result["needs_response"] == True
            assert "recurring" in result["message"].lower()

    # ========================
    # 2. Time Response Handling
    # ========================
    
    @pytest.mark.asyncio
    async def test_handle_time_response_valid(self, mock_redis_client):
        """Test handling valid time response."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            current_state = {
                "step": "awaiting_time",
                "draft_task": {"title": "call mom"},
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
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
            
            current_state = {
                "step": "awaiting_time",
                "draft_task": {"title": "call mom"},
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
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

    # ========================
    # 3. Optional Details Handling
    # ========================
    
    @pytest.mark.asyncio
    async def test_handle_optional_response_with_details(self, mock_redis_client):
        """Test handling optional response with details."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            current_state = {
                "step": "awaiting_optional",
                "draft_task": {
                    "title": "call mom",
                    "due_date": datetime.utcnow() + timedelta(hours=1)
                },
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {
                    "notes": "check on her health",
                    "priority": "high"
                }
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_optional_response(
                "high priority, check on her health", current_state, flow
            )
            
            assert result["action"] == "confirm"
            assert result["needs_response"] == True
            assert "call mom" in result["message"]

    @pytest.mark.asyncio
    async def test_handle_optional_response_no_details(self, mock_redis_client):
        """Test handling optional response without details."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            current_state = {
                "step": "awaiting_optional",
                "draft_task": {
                    "title": "call mom",
                    "due_date": datetime.utcnow() + timedelta(hours=1)
                },
                "user_timezone": "UTC",
                "created_at": datetime.utcnow().isoformat()
            }
            
            mock_nlp.extract_task_entities.return_value = {
                "entities": {}
            }
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_optional_response(
                "no", current_state, flow
            )
            
            assert result["action"] == "confirm"
            assert result["needs_response"] == True

    # ========================
    # 4. Confirmation Handling
    # ========================
    
    @pytest.mark.asyncio
    async def test_handle_confirmation_response_yes(self, mock_redis_client, mock_task_service):
        """Test handling confirmation with yes."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_service', mock_task_service), \
             patch('app.services.task_flow_service.get_user_profile_collection') as mock_profiles:
            
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

    # ========================
    # 5. Error Handling
    # ========================
    
    @pytest.mark.asyncio
    async def test_task_creation_error_handling(self, mock_redis_client, mock_task_service):
        """Test error handling during task creation."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_service', mock_task_service), \
             patch('app.services.task_flow_service.get_user_profile_collection') as mock_profiles:
            
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
            
            mock_profile = {"email": "test@example.com"}
            mock_profiles.return_value.find_one.return_value = mock_profile
            
            # Mock task creation failure
            mock_task_service.create_task.side_effect = Exception("Database error")
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_confirmation_response(
                "yes", current_state, flow, "user123"
            )
            
            assert result["action"] == "retry"
            assert result["needs_response"] == True
            assert "trouble" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_missing_email_handling(self, mock_redis_client, mock_task_service):
        """Test handling missing user email."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_service', mock_task_service), \
             patch('app.services.task_flow_service.get_user_profile_collection') as mock_profiles:
            
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
            
            # Mock missing email
            mock_profiles.return_value.find_one.return_value = None
            
            flow = task_flow_service.TaskFlowState("user123")
            
            result = await task_flow_service._handle_confirmation_response(
                "yes", current_state, flow, "user123"
            )
            
            assert result["action"] == "error"
            assert result["needs_response"] == False
            assert "email" in result["message"].lower()

    # ========================
    # 6. Redis State Management
    # ========================
    
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

    # ========================
    # 7. Message Generation Tests
    # ========================
    
    def test_generate_clarification_message_comprehensive(self):
        """Test comprehensive clarification message generation."""
        test_cases = [
            ("missing_time", "At what time should I remind you?"),
            ("vague_time", "Could you be more specific about the time?"),
            ("ambiguous_time", "I found multiple times:"),
            ("conflicting_times", "I noticed conflicting time references"),
            ("incomplete_time", "It looks like your message was cut off"),
            ("meal_context", "What time do you usually have"),
            ("recurring_not_supported", "Recurring reminders are not yet supported"),
            ("validation_issues", "There seems to be an issue"),
        ]
        
        for reason, expected_content in test_cases:
            result = {
                "ambiguities": {
                    "vague_phrases_found": ["later"],
                    "time_matches": ["8am", "9am"],
                    "context_phrases_found": ["after lunch"]
                },
                "validation_issues": [
                    {"type": "past_time", "message": "That time has already passed"}
                ]
            }
            
            message = task_flow_service._generate_clarification_message(reason, result)
            assert expected_content.lower() in message.lower(), f"Failed for reason: {reason}"

    def test_generate_confirmation_message(self):
        """Test confirmation message generation."""
        entities = {
            "title": "call mom",
            "due_date": datetime.utcnow() + timedelta(hours=1),
            "priority": "high",
            "notes": "check on her health"
        }
        
        message = task_flow_service._generate_confirmation_message(entities, "UTC")
        
        assert "call mom" in message
        assert "high" in message.lower()
        assert "confirm" in message.lower()

    # ========================
    # 8. Edge Cases and Stress Tests
    # ========================
    
    @pytest.mark.asyncio
    async def test_rapid_create_cancel_flow(self, mock_redis_client):
        """Test rapid create-cancel flow."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client), \
             patch('app.services.task_flow_service.task_nlp') as mock_nlp:
            
            # Start flow
            mock_nlp.extract_task_entities.return_value = {
                "entities": {"title": "test", "due_date": None},
                "needs_clarification": True,
                "clarification_reason": "missing_time"
            }
            
            result1 = await task_flow_service.handle_task_intent(
                "remind me to test", "user123", "UTC"
            )
            assert result1["action"] == "clarify"
            
            # Cancel flow
            flow = task_flow_service.TaskFlowState("user123")
            current_state = await flow.get_state()
            
            if current_state:
                result2 = await task_flow_service._handle_confirmation_response(
                    "cancel", current_state, flow, "user123"
                )
                assert result2["action"] == "cancelled"

    @pytest.mark.asyncio
    async def test_multiple_user_isolation(self, mock_redis_client):
        """Test that multiple users don't interfere with each other."""
        with patch('app.services.task_flow_service.get_redis', return_value=mock_redis_client):
            
            flow1 = task_flow_service.TaskFlowState("user1")
            flow2 = task_flow_service.TaskFlowState("user2")
            
            # Set different states for different users
            await flow1.set_state({"step": "awaiting_time", "user_id": "user1"})
            await flow2.set_state({"step": "awaiting_confirm", "user_id": "user2"})
            
            # Verify isolation
            state1 = await flow1.get_state()
            state2 = await flow2.get_state()
            
            assert state1["step"] == "awaiting_time"
            assert state2["step"] == "awaiting_confirm"
            assert state1["user_id"] == "user1"
            assert state2["user_id"] == "user2"
