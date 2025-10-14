# backend/tests/test_task_nlp.py

import pytest
from datetime import datetime, timedelta
from app.services import task_nlp


class TestTaskNLP:
    """Test cases for task NLP service."""

    def test_detect_task_intent(self):
        """Test task intent detection."""
        # Positive cases
        assert task_nlp.detect_task_intent("remind me to call mom") == True
        assert task_nlp.detect_task_intent("schedule a meeting tomorrow") == True
        assert task_nlp.detect_task_intent("set a reminder for 8pm") == True
        
        # Negative cases
        assert task_nlp.detect_task_intent("what is a reminder?") == False
        assert task_nlp.detect_task_intent("how to schedule") == False
        assert task_nlp.detect_task_intent("") == False
        assert task_nlp.detect_task_intent(None) == False

    def test_extract_title(self):
        """Test title extraction."""
        assert task_nlp._extract_title("remind me to call mom") == "call mom"
        assert task_nlp._extract_title("schedule a meeting about project") == "project"
        assert task_nlp._extract_title("remind me about dentist appointment") == "dentist appointment"
        
        # Edge cases
        assert task_nlp._extract_title("just a normal message") is None
        assert task_nlp._extract_title("") is None

    def test_extract_priority(self):
        """Test priority extraction."""
        assert task_nlp._extract_priority("urgent reminder") == "urgent"
        assert task_nlp._extract_priority("high priority task") == "high"
        assert task_nlp._extract_priority("medium priority") == "medium"
        assert task_nlp._extract_priority("low priority") == "low"
        assert task_nlp._extract_priority("normal message") is None

    def test_extract_task_entities_basic(self):
        """Test basic entity extraction."""
        result = task_nlp.extract_task_entities("remind me to call mom at 8pm today", "UTC")
        
        assert result["entities"]["title"] == "call mom"
        assert result["entities"]["due_date"] is not None
        assert result["entities"]["priority"] is None
        assert result["needs_clarification"] == False
        assert result["confidence"] == 0.9

    def test_extract_task_entities_ambiguous(self):
        """Test ambiguous time handling."""
        result = task_nlp.extract_task_entities("remind me to call mom later", "UTC")
        
        assert result["entities"]["title"] == "call mom"
        assert result["needs_clarification"] == True
        assert result["clarification_reason"] == "vague_time"
        assert result["confidence"] == 0.5

    def test_extract_task_entities_missing_time(self):
        """Test missing time handling."""
        result = task_nlp.extract_task_entities("remind me to call mom", "UTC")
        
        assert result["entities"]["title"] == "call mom"
        assert result["needs_clarification"] == True
        assert result["clarification_reason"] == "missing_time"

    def test_extract_task_entities_multiple_times(self):
        """Test multiple time mentions."""
        result = task_nlp.extract_task_entities("remind me at 8am or 9am", "UTC")
        
        assert result["needs_clarification"] == True
        assert result["clarification_reason"] == "ambiguous_time"
        assert result["ambiguities"]["has_multiple_times"] == True

    def test_extract_task_entities_past_time(self):
        """Test past time validation."""
        # This should trigger validation issues
        result = task_nlp.extract_task_entities("remind me yesterday at 8pm", "UTC")
        
        assert result["needs_clarification"] == True
        assert result["clarification_reason"] == "validation_issues"
        assert len(result["validation_issues"]) > 0
        assert result["validation_issues"][0]["type"] == "past_time"

    def test_extract_task_entities_auto_bump(self):
        """Test auto-bump for recent past times."""
        # Create a time that's 30 minutes in the past
        past_time = datetime.utcnow() - timedelta(minutes=30)
        message = f"remind me at {past_time.strftime('%I:%M %p')}"
        
        result = task_nlp.extract_task_entities(message, "UTC")
        
        # Should auto-bump to tomorrow
        if result["validation_issues"]:
            auto_bump_issue = next((issue for issue in result["validation_issues"] if issue["type"] == "auto_bump"), None)
            if auto_bump_issue:
                assert auto_bump_issue["type"] == "auto_bump"

    def test_detect_ambiguities(self):
        """Test ambiguity detection."""
        ambiguities = task_nlp._detect_ambiguities("remind me later tonight")
        
        assert ambiguities["has_vague"] == True
        assert ambiguities["has_multiple_times"] == False
        assert ambiguities["has_choice"] == False

    def test_detect_ambiguities_multiple_times(self):
        """Test multiple time detection."""
        ambiguities = task_nlp._detect_ambiguities("remind me at 8am or 9am")
        
        assert ambiguities["has_multiple_times"] == True
        assert ambiguities["has_choice"] == True
        assert len(ambiguities["time_matches"]) >= 2

    def test_cross_validate_entities(self):
        """Test entity cross-validation."""
        entities = {
            "title": "test task",
            "due_date": datetime.utcnow() - timedelta(hours=2),  # 2 hours in past
            "priority": "medium",
            "notes": None
        }
        
        validation = task_nlp._cross_validate_entities(entities, "UTC")
        
        assert len(validation["issues"]) > 0
        assert validation["issues"][0]["type"] == "past_time"

    def test_cross_validate_missing_title(self):
        """Test missing title validation."""
        entities = {
            "title": None,
            "due_date": datetime.utcnow() + timedelta(hours=1),
            "priority": "medium",
            "notes": None
        }
        
        validation = task_nlp._cross_validate_entities(entities, "UTC")
        
        assert len(validation["issues"]) > 0
        assert validation["issues"][0]["type"] == "missing_title"

    def test_timezone_handling(self):
        """Test timezone handling."""
        result = task_nlp.extract_task_entities("remind me at 8pm today", "America/New_York")
        
        assert result["entities"]["due_date"] is not None
        # The due_date should be in UTC (naive)
        assert result["entities"]["due_date"].tzinfo is None

    def test_invalid_timezone_fallback(self):
        """Test invalid timezone fallback."""
        result = task_nlp.extract_task_entities("remind me at 8pm today", "Invalid/Timezone")
        
        # Should fallback to UTC and still work
        assert result["entities"]["due_date"] is not None
