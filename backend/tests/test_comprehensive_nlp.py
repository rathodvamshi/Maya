# backend/tests/test_comprehensive_nlp.py

import pytest
from datetime import datetime, timedelta
from app.services import task_nlp


class TestComprehensiveNLP:
    """
    Comprehensive test suite covering all intent detection, ambiguity handling,
    multilingual support, and edge cases as specified in the requirements.
    """

    # ========================
    # 1. Intent Detection Test Cases
    # ========================
    
    def test_intent_detection_create_task(self):
        """Test task creation intent detection."""
        test_cases = [
            ("Remind me to sleep at 10pm", True),
            ("I want to create a reminder for tomorrow morning", True),
            ("Schedule a task to finish report at 8am", True),
            ("Make a note for meeting at 3pm", True),
            ("Set an alarm for 7am", True),
            ("Wake me up at 6am", True),
            ("Create a reminder to call mom", True),
            ("Add a task for grocery shopping", True),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_intent_detection_modification(self):
        """Test task modification intent detection."""
        test_cases = [
            ("Cancel my meeting reminder", True),
            ("Delete the reminder for dentist", True),
            ("Remove the sleep reminder", True),
            ("Stop the alarm", True),
            ("Abort the task", True),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_intent_detection_listing(self):
        """Test task listing intent detection."""
        test_cases = [
            ("Show my upcoming tasks", True),
            ("What tasks do I have tomorrow?", True),
            ("List all my reminders", True),
            ("Display my tasks for today", True),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_intent_detection_reschedule(self):
        """Test reschedule intent detection."""
        test_cases = [
            ("Reschedule the sleep reminder to 9pm", True),
            ("Move the meeting to 3pm", True),
            ("Change the appointment to tomorrow", True),
            ("Postpone the task", True),
            ("Delay the reminder", True),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_intent_detection_verification(self):
        """Test OTP verification intent detection."""
        test_cases = [
            ("Verify my OTP for sleep reminder", True),
            ("Check the code for my task", True),
            ("Confirm the OTP", True),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_intent_detection_false_positives(self):
        """Test false positive prevention."""
        test_cases = [
            ("What is a reminder?", False),
            ("How to create a task?", False),
            ("Explain what a meeting is", False),
            ("Tell me about reminders", False),
            ("I don't want any reminders", False),
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    # ========================
    # 2. Multilingual Support
    # ========================
    
    def test_multilingual_intent_detection(self):
        """Test multilingual intent detection."""
        test_cases = [
            ("Kal 8 baje remind karna", True),  # Hindi-English mix
            ("Yaad dilana kal subah", True),  # Hindi
            ("Recordar mañana", True),  # Spanish
            ("Rappeler demain", True),  # French
        ]
        
        for input_text, expected in test_cases:
            assert task_nlp.detect_task_intent(input_text) == expected, f"Failed for: {input_text}"

    def test_multilingual_title_extraction(self):
        """Test multilingual title extraction."""
        test_cases = [
            ("Kal mom ko call ki yaad", "Mom ko call"),
            ("Yaad dilana doctor appointment", "Doctor appointment"),
            ("Aaj meeting ki yaad", "Meeting"),
        ]
        
        for input_text, expected_title in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["entities"]["title"] == expected_title, f"Failed for: {input_text}"

    # ========================
    # 3. Time Parsing & Ambiguity Tests
    # ========================
    
    def test_simple_valid_time_inputs(self):
        """Test simple valid time inputs."""
        test_cases = [
            ("Remind me to sleep at 8pm today", True),
            ("Remind me in 30 minutes", True),
            ("Remind me tomorrow at 7am", True),
            ("Remind me on 25th October at 9:30am", True),
        ]
        
        for input_text, should_pass in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            if should_pass:
                assert not result["needs_clarification"], f"Should not need clarification: {input_text}"
                assert result["entities"]["due_date"] is not None, f"Should have due date: {input_text}"

    def test_ambiguous_time_inputs(self):
        """Test ambiguous time inputs that should ask for clarification."""
        test_cases = [
            ("Remind me later", "vague_time"),
            ("Remind me soon", "vague_time"),
            ("Remind me tonight or tomorrow", "ambiguous_time"),
            ("Set a task for meeting", "missing_time"),
            ("Wake me up early", "vague_time"),
            ("Remind me after lunch", "meal_context"),
            ("Sleep reminder 8pm yesterday", "validation_issues"),
        ]
        
        for input_text, expected_reason in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["needs_clarification"], f"Should need clarification: {input_text}"
            assert result["clarification_reason"] == expected_reason, f"Wrong reason for: {input_text}"

    def test_edge_time_cases(self):
        """Test edge time cases."""
        # Test current time tolerance
        now = datetime.utcnow()
        test_cases = [
            # Within tolerance should be accepted
            (f"Remind me at {now.strftime('%I:%M %p')}", True),
            # Past time should be rejected
            (f"Remind me at {(now - timedelta(hours=2)).strftime('%I:%M %p')}", False),
        ]
        
        for input_text, should_pass in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            if should_pass:
                assert not result["needs_clarification"], f"Should pass: {input_text}"
            else:
                assert result["needs_clarification"], f"Should fail: {input_text}"

    def test_recurring_patterns(self):
        """Test recurring pattern detection."""
        test_cases = [
            ("Remind me every Monday at 8am", "recurring_not_supported"),
            ("Daily reminder at 9pm", "recurring_not_supported"),
            ("Repeat this task weekly", "recurring_not_supported"),
        ]
        
        for input_text, expected_reason in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["needs_clarification"], f"Should need clarification: {input_text}"
            assert result["clarification_reason"] == expected_reason, f"Wrong reason for: {input_text}"

    # ========================
    # 4. Title Extraction Tests
    # ========================
    
    def test_title_extraction_patterns(self):
        """Test various title extraction patterns."""
        test_cases = [
            ("Remind me to call mom at 8pm", "Call mom"),
            ("Schedule a meeting about project", "Project"),
            ("Create a reminder for dentist appointment", "Dentist appointment"),
            ("Set an alarm for gym", "Gym"),
            ("Wake me up for work", "Work"),
        ]
        
        for input_text, expected_title in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["entities"]["title"] == expected_title, f"Failed for: {input_text}"

    def test_title_extraction_edge_cases(self):
        """Test title extraction edge cases."""
        test_cases = [
            ("Remind me at 8pm", None),  # No title
            ("Schedule meeting", "Meeting"),  # Simple title
            ("Create task", "Task"),  # Generic title
        ]
        
        for input_text, expected_title in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["entities"]["title"] == expected_title, f"Failed for: {input_text}"

    # ========================
    # 5. Priority Extraction Tests
    # ========================
    
    def test_priority_extraction(self):
        """Test priority extraction."""
        test_cases = [
            ("Urgent reminder to call boss", "urgent"),
            ("High priority task for project", "high"),
            ("Medium priority meeting", "medium"),
            ("Low priority reminder", "low"),
            ("Normal reminder", None),
        ]
        
        for input_text, expected_priority in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["entities"]["priority"] == expected_priority, f"Failed for: {input_text}"

    # ========================
    # 6. Cross-Validation Tests
    # ========================
    
    def test_past_time_validation(self):
        """Test past time validation."""
        past_time = datetime.utcnow() - timedelta(hours=2)
        input_text = f"Remind me at {past_time.strftime('%I:%M %p')}"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        assert result["needs_clarification"], "Should need clarification for past time"
        assert result["clarification_reason"] == "validation_issues"
        
        validation_issues = result["validation_issues"]
        assert len(validation_issues) > 0
        assert validation_issues[0]["type"] == "past_time"

    def test_missing_title_validation(self):
        """Test missing title validation."""
        input_text = "Remind me at 8pm"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        assert result["needs_clarification"], "Should need clarification for missing title"
        
        validation_issues = result["validation_issues"]
        assert len(validation_issues) > 0
        assert validation_issues[0]["type"] == "missing_title"

    def test_title_too_short_validation(self):
        """Test title too short validation."""
        input_text = "Remind me to x at 8pm"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        assert result["needs_clarification"], "Should need clarification for short title"
        
        validation_issues = result["validation_issues"]
        assert len(validation_issues) > 0
        assert validation_issues[0]["type"] == "title_too_short"

    # ========================
    # 7. Timezone Handling Tests
    # ========================
    
    def test_timezone_handling(self):
        """Test timezone handling."""
        test_cases = [
            ("America/New_York", "EST"),
            ("Asia/Kolkata", "IST"),
            ("Europe/London", "GMT"),
            ("UTC", "UTC"),
        ]
        
        for timezone, expected_tz in test_cases:
            result = task_nlp.extract_task_entities("Remind me at 8pm today", timezone)
            if result["entities"]["due_date"]:
                # The due_date should be in UTC (naive)
                assert result["entities"]["due_date"].tzinfo is None, f"Should be naive UTC for {timezone}"

    def test_invalid_timezone_fallback(self):
        """Test invalid timezone fallback."""
        result = task_nlp.extract_task_entities("Remind me at 8pm today", "Invalid/Timezone")
        # Should fallback to UTC and still work
        assert result["entities"]["due_date"] is not None, "Should work with invalid timezone"

    # ========================
    # 8. Complex Ambiguity Tests
    # ========================
    
    def test_multiple_time_mentions(self):
        """Test multiple time mentions."""
        input_text = "Remind me at 8am or 9am tomorrow"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        assert result["needs_clarification"], "Should need clarification for multiple times"
        assert result["clarification_reason"] == "ambiguous_time"
        
        ambiguities = result["ambiguities"]
        assert ambiguities["has_multiple_times"], "Should detect multiple times"
        assert len(ambiguities["time_matches"]) >= 2, "Should find at least 2 time matches"

    def test_conflicting_time_references(self):
        """Test conflicting time references."""
        input_text = "Remind me yesterday at 8pm today"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        assert result["needs_clarification"], "Should need clarification for conflicting times"
        assert result["clarification_reason"] == "conflicting_times"

    def test_incomplete_time_references(self):
        """Test incomplete time references."""
        test_cases = [
            "Remind me at",
            "Schedule for",
            "Create reminder in",
            "Set alarm on",
        ]
        
        for input_text in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["needs_clarification"], f"Should need clarification: {input_text}"
            assert result["clarification_reason"] == "incomplete_time"

    # ========================
    # 9. Context-Aware Tests
    # ========================
    
    def test_meal_context_clarification(self):
        """Test meal context clarification."""
        test_cases = [
            ("Remind me after lunch", "meal_context"),
            ("Set reminder before dinner", "meal_context"),
            ("Wake me after breakfast", "meal_context"),
        ]
        
        for input_text, expected_reason in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["needs_clarification"], f"Should need clarification: {input_text}"
            assert result["clarification_reason"] == expected_reason, f"Wrong reason for: {input_text}"

    def test_choice_word_detection(self):
        """Test choice word detection."""
        test_cases = [
            ("Remind me at 8pm or 9pm", "ambiguous_time"),
            ("Schedule either morning or evening", "ambiguous_time"),
            ("Maybe remind me at 8pm", "ambiguous_time"),
        ]
        
        for input_text, expected_reason in test_cases:
            result = task_nlp.extract_task_entities(input_text, "UTC")
            assert result["needs_clarification"], f"Should need clarification: {input_text}"
            assert result["clarification_reason"] == expected_reason, f"Wrong reason for: {input_text}"

    # ========================
    # 10. Complete Flow Tests
    # ========================
    
    def test_complete_valid_flow(self):
        """Test complete valid flow without clarification."""
        input_text = "Remind me to call mom at 8pm today with high priority"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        
        assert not result["needs_clarification"], "Should not need clarification"
        assert result["entities"]["title"] == "Call mom"
        assert result["entities"]["priority"] == "high"
        assert result["entities"]["due_date"] is not None
        assert result["confidence"] == 0.9

    def test_clarification_flow(self):
        """Test clarification flow."""
        input_text = "Remind me to sleep"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        
        assert result["needs_clarification"], "Should need clarification"
        assert result["clarification_reason"] == "missing_time"
        assert result["confidence"] == 0.5

    def test_validation_flow(self):
        """Test validation flow."""
        input_text = "Remind me yesterday at 8pm"
        
        result = task_nlp.extract_task_entities(input_text, "UTC")
        
        assert result["needs_clarification"], "Should need clarification"
        assert result["clarification_reason"] == "validation_issues"
        assert len(result["validation_issues"]) > 0
