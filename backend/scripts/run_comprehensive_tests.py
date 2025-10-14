#!/usr/bin/env python3
"""
Comprehensive test runner for the task reminder system.
Runs all test suites as specified in requirements.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_command(command, description):
    """Run a command and return success status."""
    logger.info(f"Running: {description}")
    logger.info(f"Command: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"✅ {description} - PASSED")
            if result.stdout:
                logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"❌ {description} - FAILED")
            logger.error(f"Error: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"❌ {description} - ERROR: {e}")
        return False


def main():
    """Run comprehensive test suite."""
    logger.info("🚀 Starting Comprehensive Task System Test Suite")
    logger.info("=" * 60)
    
    # Change to backend directory
    os.chdir(backend_dir)
    
    test_results = []
    
    # Test Suite 1: Task NLP Parsing (30+ test cases)
    logger.info("\n📝 Test Suite 1: Task NLP Parsing")
    logger.info("-" * 40)
    result1 = run_command(
        "python -m pytest tests/test_task_nlp_comprehensive.py -v",
        "Task NLP Parsing Tests (30+ cases)"
    )
    test_results.append(("Task NLP Parsing", result1))
    
    # Test Suite 2: Task Service (10+ test cases)
    logger.info("\n🔧 Test Suite 2: Task Service")
    logger.info("-" * 40)
    result2 = run_command(
        "python -m pytest tests/test_task_service_comprehensive.py -v",
        "Task Service Tests (10+ cases)"
    )
    test_results.append(("Task Service", result2))
    
    # Test Suite 3: Celery Worker (10+ test cases)
    logger.info("\n⚡ Test Suite 3: Celery Worker")
    logger.info("-" * 40)
    result3 = run_command(
        "python -m pytest tests/test_celery_worker_comprehensive.py -v",
        "Celery Worker Tests (10+ cases)"
    )
    test_results.append(("Celery Worker", result3))
    
    # Test Suite 4: Integration E2E (4+ test cases)
    logger.info("\n🔗 Test Suite 4: Integration E2E")
    logger.info("-" * 40)
    result4 = run_command(
        "python -m pytest tests/test_task_integration_e2e.py -v",
        "Integration E2E Tests (4+ cases)"
    )
    test_results.append(("Integration E2E", result4))
    
    # Test Suite 5: API Endpoints
    logger.info("\n🌐 Test Suite 5: API Endpoints")
    logger.info("-" * 40)
    result5 = run_command(
        "python -m pytest tests/test_task_api_integration.py -v",
        "API Endpoint Tests"
    )
    test_results.append(("API Endpoints", result5))
    
    # Test Suite 6: Health Checks
    logger.info("\n🏥 Test Suite 6: Health Checks")
    logger.info("-" * 40)
    result6 = run_command(
        "python -m pytest tests/test_health_checks.py -v",
        "Health Check Tests"
    )
    test_results.append(("Health Checks", result6))
    
    # Test Suite 7: Email Templates
    logger.info("\n📧 Test Suite 7: Email Templates")
    logger.info("-" * 40)
    result7 = run_command(
        "python -m pytest tests/test_email_templates.py -v",
        "Email Template Tests"
    )
    test_results.append(("Email Templates", result7))
    
    # Test Suite 8: Task Flow Service
    logger.info("\n🔄 Test Suite 8: Task Flow Service")
    logger.info("-" * 40)
    result8 = run_command(
        "python -m pytest tests/test_task_flow_service.py -v",
        "Task Flow Service Tests"
    )
    test_results.append(("Task Flow Service", result8))
    
    # Test Suite 9: Database Integration
    logger.info("\n🗄️ Test Suite 9: Database Integration")
    logger.info("-" * 40)
    result9 = run_command(
        "python -m pytest tests/test_database_integration.py -v",
        "Database Integration Tests"
    )
    test_results.append(("Database Integration", result9))
    
    # Test Suite 10: Redis Integration
    logger.info("\n🔴 Test Suite 10: Redis Integration")
    logger.info("-" * 40)
    result10 = run_command(
        "python -m pytest tests/test_redis_integration.py -v",
        "Redis Integration Tests"
    )
    test_results.append(("Redis Integration", result10))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name:<25} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("-" * 60)
    logger.info(f"Total Test Suites: {len(test_results)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success Rate: {(passed/len(test_results)*100):.1f}%")
    
    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED! The task reminder system is working correctly.")
        return 0
    else:
        logger.error(f"\n💥 {failed} TEST SUITE(S) FAILED! Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)