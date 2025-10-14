# Comprehensive QA Checklist for Task Creation & Reminder Feature

## 🎯 **Test Coverage Overview**

This checklist covers all scenarios from the comprehensive test suite, organized by intent, language style, ambiguity type, and system behavior.

---

## 🧩 **1. Intent Detection Test Cases**

| # | User Input | Expected Intent | Expected Response | Status |
|---|------------|-----------------|------------------|---------|
| 1 | "Remind me to sleep at 10pm" | ✅ create_task | Ask confirmation / schedule at 22:00 | ⬜ |
| 2 | "I want to create a reminder for tomorrow morning" | ✅ create_task | Ask for title ("What should I remind you about?") | ⬜ |
| 3 | "Schedule a task to finish report at 8am" | ✅ create_task | Extract title="finish report", due=8am | ⬜ |
| 4 | "Make a note for meeting at 3pm" | ✅ create_task | Treat as task (meeting note) | ⬜ |
| 5 | "Cancel my meeting reminder" | ✅ cancel_task | Identify cancellation intent | ⬜ |
| 6 | "Show my upcoming tasks" | ✅ list_tasks | Return summary | ⬜ |
| 7 | "Reschedule the sleep reminder to 9pm" | ✅ reschedule_task | Update existing task | ⬜ |
| 8 | "Delete the reminder for dentist" | ✅ delete_task | Delete specified task | ⬜ |
| 9 | "Verify my OTP for sleep reminder" | ✅ verify_otp | Ask for OTP code / verify | ⬜ |
| 10 | "What tasks do I have tomorrow?" | ✅ list_tasks | Return tomorrow's list | ⬜ |

**✅ Pass Criteria:** All 10 cases correctly detect intent
**❌ Fail Criteria:** Any false positive or false negative

---

## ⏰ **2. Time Parsing & Ambiguity Tests**

### ✅ Simple Valid Inputs
| # | User Input | Expected Parsed Time | Should Pass | Status |
|---|------------|----------------------|-------------|---------|
| 1 | "Remind me to sleep at 8pm today" | today 20:00 local | ✅ | ⬜ |
| 2 | "Remind me in 30 minutes" | now + 30m | ✅ | ⬜ |
| 3 | "Remind me tomorrow at 7am" | tomorrow 07:00 | ✅ | ⬜ |
| 4 | "Remind me on 25th October at 9:30am" | 2025-10-25 09:30 local | ✅ | ⬜ |

### ⚠️ Ambiguous Inputs (Should Ask for Clarification)
| # | User Input | Detected Ambiguity | Expected Response | Status |
|---|------------|-------------------|------------------|---------|
| 1 | "Remind me later" | missing time | "When should I remind you?" | ⬜ |
| 2 | "Remind me soon" | vague time | "Can you specify a time like 'in 30 minutes'?" | ⬜ |
| 3 | "Remind me tonight or tomorrow" | multiple times | "Which one should I use?" | ⬜ |
| 4 | "Set a task for meeting" | missing time | "What time should I schedule it?" | ⬜ |
| 5 | "Wake me up early" | relative concept | "What time do you consider early?" | ⬜ |
| 6 | "Remind me after lunch" | context phrase | "What time do you usually have lunch?" | ⬜ |
| 7 | "Sleep reminder 8pm yesterday" | past time | "That time has passed. Should I set it for today instead?" | ⬜ |

### ⏱ Edge Time Cases
| # | Current Time | User Input | Expected Behavior | Status |
|---|--------------|------------|------------------|---------|
| 1 | 19:59 | "Remind me at 8pm" | Accept (within tolerance) | ⬜ |
| 2 | 20:00 | "Remind me at 8pm" | Bump +1 day | ⬜ |
| 3 | 23:59 | "Remind me at midnight" | Accept (today+1 minute) | ⬜ |
| 4 | 00:01 | "Remind me at 12am" | Accept next midnight | ⬜ |
| 5 | Any | "Remind me yesterday 9pm" | Reject as past | ⬜ |
| 6 | Any | "Remind me in 1 minute" | Accept and trigger after 60s | ⬜ |

**✅ Pass Criteria:** All time parsing works correctly with proper ambiguity detection
**❌ Fail Criteria:** Any incorrect time parsing or missing clarification

---

## 🌍 **3. Timezone Handling**

| # | Condition | Expected | Status |
|---|-----------|----------|---------|
| 1 | User in IST says "8pm" | Stored UTC = 14:30 | ⬜ |
| 2 | User in EST says "8pm" | Stored UTC = 01:00 next day | ⬜ |
| 3 | User timezone missing | Default to UTC | ⬜ |
| 4 | User changes timezone | Future tasks unaffected, new ones follow new TZ | ⬜ |
| 5 | RELATIVE_BASE honored (current local time) | All relative times correct | ⬜ |

**✅ Pass Criteria:** All timezone conversions work correctly
**❌ Fail Criteria:** Any incorrect timezone handling

---

## 🗣️ **4. Confirmation Flow (Redis State Machine)**

| Step | Input | Expected State | Expected Response | Status |
|------|-------|----------------|------------------|---------|
| 1 | "Remind me to sleep" | awaiting_time | Ask: "When should I remind you?" | ⬜ |
| 2 | "8pm today" | awaiting_optional | Ask: "Any notes or priority?" | ⬜ |
| 3 | "No" | awaiting_confirm | Show summary: "Confirm creating task Sleep at 8pm today?" | ⬜ |
| 4 | "Yes" | done | Create task, confirm success | ⬜ |
| 5 | "Cancel" | done | Clear Redis state, respond "Cancelled" | ⬜ |

**✅ Pass Criteria:** All state transitions work correctly
**❌ Fail Criteria:** Any state machine errors or lost context

---

## 📧 **5. Celery OTP Reminder Behavior**

| # | Case | Expected | Status |
|---|------|----------|---------|
| 1 | Task due in 2 minutes | OTP email sent ± few seconds | ⬜ |
| 2 | Email failure | Retries with backoff (up to 5) | ⬜ |
| 3 | OTP stored | Redis key otp:task:{id} expires after 600s | ⬜ |
| 4 | OTP expired | Verify API → "OTP expired" | ⬜ |
| 5 | OTP correct | Verify API → "OTP verified successfully" | ⬜ |
| 6 | OTP incorrect | Verify API → "Invalid OTP" | ⬜ |
| 7 | Email body | Uses HTML template, subject = "Reminder: {title} (OTP inside)" | ⬜ |

**✅ Pass Criteria:** All OTP flows work correctly
**❌ Fail Criteria:** Any OTP delivery or verification issues

---

## 🗂️ **6. Task CRUD + Reschedule Tests**

| # | Action | Input | Expected Result | Status |
|---|--------|-------|-----------------|---------|
| 1 | Create | "Remind me to meditate at 9am" | Added, OTP scheduled | ⬜ |
| 2 | Read | GET /tasks | Shows created task | ⬜ |
| 3 | Update | Change time to 10am | Old Celery revoked, new scheduled | ⬜ |
| 4 | Delete | Delete task | Removed from DB and Celery | ⬜ |
| 5 | Reschedule | POST /tasks/{id}/reschedule | Updates due_date and Celery ETA | ⬜ |
| 6 | Verify OTP | POST /tasks/{id}/verify-otp | Returns verified | ⬜ |
| 7 | Summary | GET /tasks/summary | Shows next 5 upcoming | ⬜ |

**✅ Pass Criteria:** All CRUD operations work correctly
**❌ Fail Criteria:** Any CRUD operation failures

---

## 🧭 **7. UI / Frontend Behavior**

| # | Feature | Expected | Status |
|---|---------|----------|---------|
| 1 | Tasks Page | CRUD operations work without refresh | ⬜ |
| 2 | Sidebar | Shows next 5 tasks, updates live | ⬜ |
| 3 | Chat Window | Shows confirmation buttons ("Confirm", "Edit", "Cancel") | ⬜ |
| 4 | OTP Modal | User can input OTP, verify | ⬜ |
| 5 | Error Handling | Graceful message on invalid OTP / server timeout | ⬜ |
| 6 | Validation | Prevent duplicate tasks (±5 min window) | ⬜ |

**✅ Pass Criteria:** All UI features work correctly
**❌ Fail Criteria:** Any UI functionality issues

---

## 🧱 **8. Stress & Edge Testing**

| # | Test | Expected | Status |
|---|------|----------|---------|
| 1 | 50 reminders same minute | All schedule correctly | ⬜ |
| 2 | Delete before trigger | No email sent | ⬜ |
| 3 | Restart worker before task | Still executes (persistent queue) | ⬜ |
| 4 | Redis restart | State resumes correctly | ⬜ |
| 5 | User rapid "create-cancel" | No duplicates, consistent state | ⬜ |
| 6 | Mixed language input ("Kal 8 baje remind karna") | Parsed correctly or ask for clarification | ⬜ |

**✅ Pass Criteria:** All stress tests pass
**❌ Fail Criteria:** Any system instability under load

---

## 🔐 **9. Security & Validation Tests**

| # | Case | Expected | Status |
|---|------|----------|---------|
| 1 | User tries to verify another user's OTP | Forbidden | ⬜ |
| 2 | Invalid JSON payload | 400 error | ⬜ |
| 3 | Missing required fields | Validation error | ⬜ |
| 4 | Database connection lost | Graceful fallback | ⬜ |
| 5 | Redis unavailable | Retry or store temp state in DB | ⬜ |

**✅ Pass Criteria:** All security measures work correctly
**❌ Fail Criteria:** Any security vulnerabilities

---

## 🔄 **10. Recovery & Consistency Checks**

| # | Scenario | Expected | Status |
|---|----------|----------|---------|
| 1 | Restart Celery mid-queue | Pending tasks recover | ⬜ |
| 2 | Mongo restart | Tasks persist | ⬜ |
| 3 | Redis flush | State resets, user can re-initiate | ⬜ |
| 4 | Duplicate task create | 409-style response | ⬜ |
| 5 | Server restart | Scheduled tasks remain (Celery beat consistency) | ⬜ |

**✅ Pass Criteria:** All recovery scenarios work correctly
**❌ Fail Criteria:** Any data loss or inconsistency

---

## 🧠 **11. Bonus: "Smart Behavior" Edge Tests**

| # | User Input | Expected | Status |
|---|------------|----------|---------|
| 1 | "Reschedule that one" | Context lookup of last task | ⬜ |
| 2 | "Same as yesterday" | Uses previous day's title/time | ⬜ |
| 3 | "Add it again tomorrow" | Clones existing task +1 day | ⬜ |
| 4 | "Make it daily" | Suggest recurring setup | ⬜ |
| 5 | "Remind me before dinner" | Ask: "What time do you usually have dinner?" | ⬜ |

**✅ Pass Criteria:** Smart behaviors work correctly
**❌ Fail Criteria:** Any context understanding failures

---

## 🌍 **12. Multilingual Support Tests**

| # | Language | Input | Expected Intent | Status |
|---|----------|-------|-----------------|---------|
| 1 | Hindi-English | "Kal 8 baje remind karna" | ✅ create_task | ⬜ |
| 2 | Hindi | "Yaad dilana kal subah" | ✅ create_task | ⬜ |
| 3 | Spanish | "Recordar mañana" | ✅ create_task | ⬜ |
| 4 | French | "Rappeler demain" | ✅ create_task | ⬜ |
| 5 | Hindi Title | "Kal mom ko call ki yaad" | Extract "Mom ko call" | ⬜ |

**✅ Pass Criteria:** All multilingual inputs work correctly
**❌ Fail Criteria:** Any language detection failures

---

## 📊 **Test Execution Instructions**

### **Automated Testing**
```bash
# Run comprehensive test suite
cd backend
python scripts/run_comprehensive_tests.py

# Run specific test categories
pytest tests/test_comprehensive_nlp.py -v
pytest tests/test_comprehensive_task_flow.py -v
pytest tests/test_task_api_integration.py -v
```

### **Manual Testing**
1. **Start the application** with all services running
2. **Go through each test case** in this checklist
3. **Mark status** as ✅ (Pass) or ❌ (Fail)
4. **Document any issues** found
5. **Verify edge cases** work as expected

### **Performance Testing**
```bash
# Test with multiple concurrent users
python scripts/stress_test.py --users 50 --duration 300

# Test Redis state management
python scripts/test_redis_state.py

# Test Celery task scheduling
python scripts/test_celery_scheduling.py
```

---

## ✅ **Final Sign-off**

### **QA Checklist Completion**
- [ ] All intent detection tests pass
- [ ] All time parsing tests pass
- [ ] All ambiguity detection tests pass
- [ ] All multilingual tests pass
- [ ] All flow scenario tests pass
- [ ] All edge case tests pass
- [ ] All stress tests pass
- [ ] All security tests pass
- [ ] All recovery tests pass
- [ ] All UI tests pass

### **Production Readiness**
- [ ] Code review completed
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Deployment plan ready

### **Sign-off**
- [ ] **QA Lead:** _________________ Date: _________
- [ ] **Dev Lead:** _________________ Date: _________
- [ ] **Product Owner:** _________________ Date: _________

---

## 📝 **Notes**

- **Test Environment:** Ensure all services (Redis, MongoDB, Celery, SMTP) are running
- **Test Data:** Use test user accounts and clean up after testing
- **Logging:** Check logs for any errors or warnings during testing
- **Performance:** Monitor system resources during stress testing
- **Documentation:** Update any discrepancies found during testing

**Last Updated:** {{ current_date }}
**Version:** 1.0
**Status:** Ready for Production Testing
