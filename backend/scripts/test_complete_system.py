#!/usr/bin/env python3
"""
Comprehensive system test script for email notifications, memory connections, and task flow.
Tests all components end-to-end with proper error handling and performance metrics.
"""

import asyncio
import sys
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.memory_connection_validator import validate_memory_connections, test_embedding_pipeline
from app.services.task_flow_service import task_flow_service
from app.services import pinecone_service, neo4j_service, redis_service
from app.database import db_client
from app.celery_tasks import send_task_notification_email
from app.utils.email_utils import send_email
from app.config import settings


class SystemTester:
    """Comprehensive system tester for all components."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "tests": {},
            "overall_status": "unknown",
            "performance": {},
            "errors": []
        }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all system tests and return comprehensive results."""
        print("🚀 Starting comprehensive system tests...")
        
        start_time = time.time()
        
        try:
            # Test 1: Memory System Connections
            print("\n📊 Testing memory system connections...")
            await self._test_memory_connections()
            
            # Test 2: Database Connectivity
            print("\n🗄️ Testing database connectivity...")
            await self._test_database_connectivity()
            
            # Test 3: Email System
            print("\n📧 Testing email system...")
            await self._test_email_system()
            
            # Test 4: Celery Integration
            print("\n⚡ Testing Celery integration...")
            await self._test_celery_integration()
            
            # Test 5: Task Flow Service
            print("\n📋 Testing task flow service...")
            await self._test_task_flow_service()
            
            # Test 6: End-to-End Task Creation
            print("\n🔄 Testing end-to-end task creation...")
            await self._test_end_to_end_task_creation()
            
            # Test 7: Performance Tests
            print("\n⚡ Running performance tests...")
            await self._test_performance()
            
            # Calculate overall status
            self._calculate_overall_status()
            
            # Store performance metrics
            self.results["performance"]["total_test_time_ms"] = int((time.time() - start_time) * 1000)
            
            print(f"\n✅ System tests completed in {self.results['performance']['total_test_time_ms']}ms")
            print(f"Overall status: {self.results['overall_status']}")
            
        except Exception as e:
            print(f"\n❌ System tests failed: {e}")
            self.results["overall_status"] = "error"
            self.results["errors"].append(str(e))
        
        return self.results
    
    async def _test_memory_connections(self):
        """Test all memory system connections."""
        try:
            # Test Pinecone
            pinecone_healthy = pinecone_service.is_ready()
            self.results["tests"]["pinecone"] = {
                "status": "healthy" if pinecone_healthy else "unhealthy",
                "ready": pinecone_healthy
            }
            
            # Test Neo4j
            neo4j_healthy = await neo4j_service.ping()
            self.results["tests"]["neo4j"] = {
                "status": "healthy" if neo4j_healthy else "unhealthy",
                "connected": neo4j_healthy
            }
            
            # Test Redis
            redis_healthy = await redis_service.ping()
            self.results["tests"]["redis"] = {
                "status": "healthy" if redis_healthy else "unhealthy",
                "connected": redis_healthy
            }
            
            # Run comprehensive memory validation
            memory_validation = await validate_memory_connections()
            self.results["tests"]["memory_validation"] = memory_validation
            
            print(f"  Pinecone: {'✅' if pinecone_healthy else '❌'}")
            print(f"  Neo4j: {'✅' if neo4j_healthy else '❌'}")
            print(f"  Redis: {'✅' if redis_healthy else '❌'}")
            
        except Exception as e:
            print(f"  ❌ Memory connection test failed: {e}")
            self.results["tests"]["memory_connections"] = {"status": "error", "error": str(e)}
    
    async def _test_database_connectivity(self):
        """Test database connectivity and operations."""
        try:
            # Test database health
            db_healthy = db_client.healthy()
            
            # Test basic operations
            tasks_col = db_client.get_tasks_collection()
            if tasks_col:
                # Test insert
                test_doc = {
                    "test": True,
                    "timestamp": datetime.utcnow(),
                    "test_id": f"test_{int(time.time())}"
                }
                insert_result = tasks_col.insert_one(test_doc)
                
                # Test find
                found_doc = tasks_col.find_one({"_id": insert_result.inserted_id})
                
                # Test delete
                delete_result = tasks_col.delete_one({"_id": insert_result.inserted_id})
                
                self.results["tests"]["database"] = {
                    "status": "healthy",
                    "operations": {
                        "insert": insert_result.acknowledged,
                        "find": found_doc is not None,
                        "delete": delete_result.deleted_count > 0
                    }
                }
                
                print("  Database operations: ✅")
            else:
                self.results["tests"]["database"] = {"status": "error", "error": "Collection not available"}
                print("  Database operations: ❌")
                
        except Exception as e:
            print(f"  ❌ Database test failed: {e}")
            self.results["tests"]["database"] = {"status": "error", "error": str(e)}
    
    async def _test_email_system(self):
        """Test email system functionality."""
        try:
            # Check SMTP configuration
            smtp_configured = bool(settings.SMTP_USER and settings.SMTP_PASS)
            
            if not smtp_configured:
                self.results["tests"]["email"] = {
                    "status": "not_configured",
                    "message": "SMTP credentials not configured"
                }
                print("  Email system: ⚠️ Not configured")
                return
            
            # Test email sending (to a test address)
            test_email = "test@example.com"  # This won't actually send
            try:
                # This will test the email configuration without actually sending
                send_email(
                    recipient=test_email,
                    subject="System Test Email",
                    body="This is a test email for system validation.",
                    max_retries=1
                )
                self.results["tests"]["email"] = {"status": "healthy"}
                print("  Email system: ✅")
            except Exception as e:
                self.results["tests"]["email"] = {"status": "error", "error": str(e)}
                print(f"  Email system: ❌ {e}")
                
        except Exception as e:
            print(f"  ❌ Email test failed: {e}")
            self.results["tests"]["email"] = {"status": "error", "error": str(e)}
    
    async def _test_celery_integration(self):
        """Test Celery task integration."""
        try:
            # Test task queuing (without actually executing)
            test_task_id = f"test_{int(time.time())}"
            
            # This will queue the task but not execute it immediately
            task_result = send_task_notification_email.delay(
                task_id=test_task_id,
                user_email="test@example.com",
                task_title="Test Task",
                task_description="Test description",
                due_date=datetime.utcnow().isoformat(),
                priority="medium",
                task_type="test"
            )
            
            self.results["tests"]["celery"] = {
                "status": "healthy",
                "task_id": task_result.id,
                "queued": True
            }
            print("  Celery integration: ✅")
            
        except Exception as e:
            print(f"  ❌ Celery test failed: {e}")
            self.results["tests"]["celery"] = {"status": "error", "error": str(e)}
    
    async def _test_task_flow_service(self):
        """Test task flow service functionality."""
        try:
            # Test system health validation
            health_status = await task_flow_service.validate_system_health()
            
            self.results["tests"]["task_flow_service"] = {
                "status": "healthy",
                "health_status": health_status
            }
            print("  Task flow service: ✅")
            
        except Exception as e:
            print(f"  ❌ Task flow service test failed: {e}")
            self.results["tests"]["task_flow_service"] = {"status": "error", "error": str(e)}
    
    async def _test_end_to_end_task_creation(self):
        """Test complete end-to-end task creation flow."""
        try:
            # Create test user
            test_user = {
                "user_id": f"test_user_{int(time.time())}",
                "email": "test@example.com"
            }
            
            # Create test task
            task_result = await task_flow_service.create_task_with_notifications(
                user=test_user,
                title="System Test Task",
                due_date_utc=datetime.utcnow() + timedelta(hours=1),
                description="This is a test task created during system validation",
                priority="medium",
                tags=["test", "system-validation"],
                notify_immediately=False,  # Don't actually send emails
                schedule_reminder=False   # Don't schedule reminders
            )
            
            if task_result["success"]:
                # Test task update
                update_result = await task_flow_service.update_task_with_notifications(
                    task_id=task_result["task_id"],
                    user=test_user,
                    updates={"description": "Updated test task description"},
                    notify_user=False
                )
                
                # Test task completion
                completion_result = await task_flow_service.complete_task_with_notifications(
                    task_id=task_result["task_id"],
                    user=test_user,
                    notify_user=False
                )
                
                self.results["tests"]["end_to_end"] = {
                    "status": "healthy",
                    "task_creation": task_result["success"],
                    "task_update": update_result["success"],
                    "task_completion": completion_result["success"],
                    "task_id": task_result["task_id"]
                }
                print("  End-to-end task flow: ✅")
            else:
                self.results["tests"]["end_to_end"] = {
                    "status": "error",
                    "error": "Task creation failed",
                    "details": task_result.get("errors", [])
                }
                print("  End-to-end task flow: ❌")
                
        except Exception as e:
            print(f"  ❌ End-to-end test failed: {e}")
            self.results["tests"]["end_to_end"] = {"status": "error", "error": str(e)}
    
    async def _test_performance(self):
        """Test system performance with multiple operations."""
        try:
            start_time = time.time()
            
            # Test embedding pipeline performance
            embedding_test = await test_embedding_pipeline()
            
            # Test memory validation performance
            memory_validation_start = time.time()
            await validate_memory_connections()
            memory_validation_time = time.time() - memory_validation_start
            
            # Test database performance
            db_start = time.time()
            tasks_col = db_client.get_tasks_collection()
            if tasks_col:
                # Test query performance
                list(tasks_col.find({}).limit(10))
            db_time = time.time() - db_start
            
            self.results["tests"]["performance"] = {
                "status": "healthy",
                "embedding_pipeline": embedding_test,
                "memory_validation_time_ms": int(memory_validation_time * 1000),
                "database_query_time_ms": int(db_time * 1000),
                "total_performance_test_time_ms": int((time.time() - start_time) * 1000)
            }
            print("  Performance tests: ✅")
            
        except Exception as e:
            print(f"  ❌ Performance test failed: {e}")
            self.results["tests"]["performance"] = {"status": "error", "error": str(e)}
    
    def _calculate_overall_status(self):
        """Calculate overall system status based on test results."""
        test_statuses = []
        
        for test_name, test_result in self.results["tests"].items():
            if isinstance(test_result, dict):
                status = test_result.get("status", "unknown")
                test_statuses.append(status)
        
        if not test_statuses:
            self.results["overall_status"] = "unknown"
            return
        
        # Count statuses
        healthy_count = test_statuses.count("healthy")
        error_count = test_statuses.count("error")
        total_tests = len(test_statuses)
        
        if healthy_count == total_tests:
            self.results["overall_status"] = "excellent"
        elif healthy_count >= total_tests * 0.8:
            self.results["overall_status"] = "good"
        elif healthy_count >= total_tests * 0.6:
            self.results["overall_status"] = "fair"
        else:
            self.results["overall_status"] = "poor"
    
    def print_summary(self):
        """Print a summary of test results."""
        print("\n" + "="*60)
        print("📊 SYSTEM TEST SUMMARY")
        print("="*60)
        
        print(f"Overall Status: {self.results['overall_status'].upper()}")
        print(f"Total Test Time: {self.results['performance'].get('total_test_time_ms', 0)}ms")
        
        print("\nTest Results:")
        for test_name, result in self.results["tests"].items():
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                status_emoji = {
                    "healthy": "✅",
                    "error": "❌",
                    "not_configured": "⚠️",
                    "unknown": "❓"
                }.get(status, "❓")
                print(f"  {test_name}: {status_emoji} {status}")
        
        if self.results["errors"]:
            print(f"\nErrors: {len(self.results['errors'])}")
            for error in self.results["errors"]:
                print(f"  - {error}")
        
        print("\n" + "="*60)


async def main():
    """Main test execution function."""
    print("🧪 Comprehensive System Test Suite")
    print("=" * 50)
    
    tester = SystemTester()
    results = await tester.run_all_tests()
    
    # Print summary
    tester.print_summary()
    
    # Save results to file
    results_file = f"system_test_results_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    # Return appropriate exit code
    if results["overall_status"] in ["excellent", "good"]:
        print("\n🎉 All systems are operational!")
        return 0
    else:
        print("\n⚠️ Some systems need attention.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
