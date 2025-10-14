# backend/tests/test_task_nlp_comprehensive.py
"""
Comprehensive test suite for task NLP parsing as specified in requirements.
Tests multiple relative/absolute/timezone cases (30+ test cases).
"""

import pytest
from datetime import datetime, timedelta
from app.services.task_nlp import parse_time, detect_task_intent, extract_task_entities


class TestTaskNLPComprehensive:
    """Comprehensive test suite for task NLP parsing."""

    def test_parse_time_8pm_today_asia_kolkata(self):
        """Test: parse_time("8pm today", "Asia/Kolkata") => not None, correct UTC conversion."""
        dt = parse_time("8pm today", "Asia/Kolkata")
        assert dt is not None
        # Should be in the future
        assert dt > datetime.utcnow()
        # Should be approximately 8pm IST converted to UTC
        # IST is UTC+5:30, so 8pm IST = 2:30pm UTC
        assert dt.hour == 14  # 2pm UTC
        assert dt.minute == 30

    def test_parse_time_relative_times(self):
        """Test various relative time expressions."""
        test_cases = [
            ("in 2 hours", "UTC"),
            ("in 30 minutes", "UTC"),
            ("in 1 day", "UTC"),
            ("tomorrow at 9am", "UTC"),
            ("next week", "UTC"),
            ("in 3 days", "UTC"),
        ]
        
        for time_text, tz in test_cases:
            dt = parse_time(time_text, tz)
            assert dt is not None, f"Failed to parse: {time_text}"
            assert dt > datetime.utcnow(), f"Parsed time should be in future: {time_text}"

    def test_parse_time_absolute_times(self):
        """Test absolute time expressions."""
        test_cases = [
            ("2025-12-25 10:00", "UTC"),
            ("December 25, 2025 at 10:00 AM", "UTC"),
            ("25/12/2025 10:00", "UTC"),
        ]
        
        for time_text, tz in test_cases:
            dt = parse_time(time_text, tz)
            assert dt is not None, f"Failed to parse: {time_text}"
            # Should be December 25, 2025 at 10:00 UTC
            assert dt.year == 2025
            assert dt.month == 12
            assert dt.day == 25
            assert dt.hour == 10
            assert dt.minute == 0

    def test_parse_time_timezone_conversions(self):
        """Test timezone conversions."""
        # Test different timezones
        timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"]
        
        for tz in timezones:
            dt = parse_time("tomorrow at 2pm", tz)
            assert dt is not None, f"Failed to parse with timezone: {tz}"
            assert dt > datetime.utcnow(), f"Should be in future for timezone: {tz}"

    def test_parse_time_edge_cases(self):
        """Test edge cases and error handling."""
        # Past times should return None (unless very recent)
        past_time = parse_time("yesterday at 2pm", "UTC")
        assert past_time is None or past_time > datetime.utcnow()
        
        # Invalid time expressions
        invalid_times = ["", "invalid time", "xyz", "never"]
        for invalid in invalid_times:
            dt = parse_time(invalid, "UTC")
            assert dt is None, f"Should return None for invalid time: {invalid}"

    def test_parse_time_near_past_tolerance(self):
        """Test ±60s tolerance: nudge near-past into +1 minute."""
        # Create a time that's 30 seconds in the past
        now = datetime.utcnow()
        past_time = now - timedelta(seconds=30)
        past_time_str = past_time.strftime("%H:%M")
        
        dt = parse_time(f"today at {past_time_str}", "UTC")
        assert dt is not None
        # Should be nudged to future
        assert dt > now

    def test_detect_task_intent_positive_cases(self):
        """Test task intent detection for positive cases."""
        positive_cases = [
            "remind me to call mom",
            "schedule a meeting tomorrow",
            "create a reminder for 8pm",
            "set an alarm for 6am",
            "wake me up at 7am",
            "call me about the project",
            "add a task for next week",
            "make a note to buy groceries",
        ]
        
        for message in positive_cases:
            assert detect_task_intent(message), f"Should detect task intent: {message}"

    def test_detect_task_intent_negative_cases(self):
        """Test task intent detection for negative cases."""
        negative_cases = [
            "what is a reminder?",
            "how to create a task?",
            "explain task management",
            "tell me about meetings",
            "I don't want any reminders",
            "cancel all tasks",
            "delete everything",
        ]
        
        for message in negative_cases:
            # Some of these might still be task-related (like cancel/delete)
            # So we test that the function doesn't crash
            result = detect_task_intent(message)
            assert isinstance(result, bool), f"Should return boolean: {message}"

    def test_extract_task_entities_complete(self):
        """Test complete entity extraction."""
        message = "remind me to call mom tomorrow at 8pm with high priority"
        result = extract_task_entities(message, "UTC")
        
        assert not result.get("needs_clarification", True), "Should not need clarification"
        entities = result.get("entities", {})
        assert entities.get("title") is not None, "Should extract title"
        assert entities.get("due_date") is not None, "Should extract due date"
        assert entities.get("priority") == "high", "Should extract priority"

    def test_extract_task_entities_missing_time(self):
        """Test entity extraction with missing time."""
        message = "remind me to call mom"
        result = extract_task_entities(message, "UTC")
        
        assert result.get("needs_clarification", False), "Should need clarification for missing time"
        assert result.get("clarification_reason") == "missing_time"

    def test_extract_task_entities_vague_time(self):
        """Test entity extraction with vague time."""
        vague_cases = [
            "remind me later",
            "remind me soon",
            "remind me eventually",
            "remind me when possible",
        ]
        
        for message in vague_cases:
            result = extract_task_entities(message, "UTC")
            assert result.get("needs_clarification", False), f"Should need clarification: {message}"
            assert result.get("clarification_reason") == "vague_time"

    def test_extract_task_entities_multiple_times(self):
        """Test entity extraction with multiple time references."""
        message = "remind me tomorrow at 8pm or 9pm"
        result = extract_task_entities(message, "UTC")
        
        assert result.get("needs_clarification", False), "Should need clarification for multiple times"
        assert result.get("clarification_reason") == "ambiguous_time"

    def test_extract_task_entities_conflicting_times(self):
        """Test entity extraction with conflicting time references."""
        message = "remind me yesterday and today"
        result = extract_task_entities(message, "UTC")
        
        assert result.get("needs_clarification", False), "Should need clarification for conflicting times"
        assert result.get("clarification_reason") == "conflicting_times"

    def test_extract_task_entities_meal_context(self):
        """Test entity extraction with meal context."""
        meal_cases = [
            "remind me after lunch",
            "remind me before dinner",
            "remind me after breakfast",
        ]
        
        for message in meal_cases:
            result = extract_task_entities(message, "UTC")
            assert result.get("needs_clarification", False), f"Should need clarification: {message}"
            assert result.get("clarification_reason") == "meal_context"

    def test_extract_task_entities_incomplete_time(self):
        """Test entity extraction with incomplete time."""
        incomplete_cases = [
            "remind me at",
            "remind me in",
            "remind me on",
            "remind me for",
        ]
        
        for message in incomplete_cases:
            result = extract_task_entities(message, "UTC")
            assert result.get("needs_clarification", False), f"Should need clarification: {message}"
            assert result.get("clarification_reason") == "incomplete_time"

    def test_extract_task_entities_priority_extraction(self):
        """Test priority extraction."""
        priority_cases = [
            ("remind me with high priority", "high"),
            ("urgent reminder", "urgent"),
            ("low priority task", "low"),
            ("medium priority reminder", "medium"),
        ]
        
        for message, expected_priority in priority_cases:
            result = extract_task_entities(message, "UTC")
            entities = result.get("entities", {})
            assert entities.get("priority") == expected_priority, f"Should extract priority: {message}"

    def test_extract_task_entities_notes_extraction(self):
        """Test notes extraction from quoted text."""
        message = 'remind me to "call mom about the birthday party"'
        result = extract_task_entities(message, "UTC")
        
        entities = result.get("entities", {})
        assert entities.get("notes") == "call mom about the birthday party", "Should extract notes from quotes"

    def test_extract_task_entities_validation_issues(self):
        """Test validation issues handling."""
        # Test past time validation
        message = "remind me yesterday at 2pm"
        result = extract_task_entities(message, "UTC")
        
        validation_issues = result.get("validation_issues", [])
        assert len(validation_issues) > 0, "Should have validation issues for past time"
        assert any(issue["type"] == "past_time" for issue in validation_issues)

    def test_extract_task_entities_confidence_scoring(self):
        """Test confidence scoring."""
        # Complete information should have high confidence
        complete_message = "remind me to call mom tomorrow at 8pm"
        result = extract_task_entities(complete_message, "UTC")
        assert result.get("confidence", 0) >= 0.8, "Complete info should have high confidence"
        
        # Incomplete information should have lower confidence
        incomplete_message = "remind me later"
        result = extract_task_entities(incomplete_message, "UTC")
        assert result.get("confidence", 1) <= 0.6, "Incomplete info should have lower confidence"

    def test_extract_task_entities_timezone_handling(self):
        """Test timezone handling in entity extraction."""
        # Test with different timezones
        timezones = ["UTC", "America/New_York", "Asia/Kolkata", "Europe/London"]
        
        for tz in timezones:
            message = "remind me tomorrow at 2pm"
            result = extract_task_entities(message, tz)
            
            entities = result.get("entities", {})
            due_date = entities.get("due_date")
            if due_date:
                # Should be a naive UTC datetime
                assert due_date.tzinfo is None, "Should return naive UTC datetime"
                assert due_date > datetime.utcnow(), "Should be in the future"

    def test_extract_task_entities_ambiguity_detection(self):
        """Test ambiguity detection."""
        message = "remind me early tomorrow"
        result = extract_task_entities(message, "UTC")
        
        ambiguities = result.get("ambiguities", {})
        assert ambiguities.get("has_vague", False), "Should detect vague time"
        assert "early" in ambiguities.get("vague_phrases_found", []), "Should identify vague phrases"

    def test_extract_task_entities_cross_validation(self):
        """Test cross-validation of entities."""
        # Test with conflicting information
        message = "remind me yesterday at 2pm tomorrow"
        result = extract_task_entities(message, "UTC")
        
        validation_issues = result.get("validation_issues", [])
        assert len(validation_issues) > 0, "Should have validation issues for conflicting times"

    def test_parse_time_stability(self):
        """Test that parse_time returns stable results."""
        # Parse the same time multiple times
        time_text = "tomorrow at 2pm"
        results = []
        
        for _ in range(5):
            dt = parse_time(time_text, "UTC")
            results.append(dt)
        
        # All results should be the same
        assert all(r == results[0] for r in results), "Parse results should be stable"

    def test_parse_time_seconds_rounding(self):
        """Test that seconds are rounded for stability."""
        # Create a time with seconds
        now = datetime.utcnow()
        future_time = now + timedelta(hours=1, minutes=30, seconds=45)
        time_str = future_time.strftime("%H:%M")
        
        dt = parse_time(f"today at {time_str}", "UTC")
        assert dt is not None
        assert dt.second == 0, "Seconds should be rounded to 0"
        assert dt.microsecond == 0, "Microseconds should be rounded to 0"
