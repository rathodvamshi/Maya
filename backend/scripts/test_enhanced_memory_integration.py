"""
Comprehensive test script for enhanced memory integration
Tests Pinecone and Neo4j CRUD operations with session persistence
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_memory_service import enhanced_memory_service
from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MemoryIntegrationTester:
    """Comprehensive tester for memory integration."""
    
    def __init__(self):
        self.test_user_id = "test_user_123"
        self.test_session_id = "test_session_456"
        self.test_memory_id = "test_memory_789"
        
    async def run_all_tests(self):
        """Run all integration tests."""
        logger.info("🚀 Starting Enhanced Memory Integration Tests")
        
        try:
            # Initialize services
            await self.test_initialization()
            
            # Test health checks
            await self.test_health_checks()
            
            # Test user management
            await self.test_user_management()
            
            # Test memory CRUD operations
            await self.test_memory_crud()
            
            # Test fact management
            await self.test_fact_management()
            
            # Test session management
            await self.test_session_management()
            
            # Test global recall
            await self.test_global_recall()
            
            # Test persistence
            await self.test_persistence()
            
            # Test cleanup
            await self.test_cleanup()
            
            logger.info("✅ All tests completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Test suite failed: {e}")
            raise
    
    async def test_initialization(self):
        """Test service initialization."""
        logger.info("🔧 Testing service initialization...")
        
        # Initialize enhanced memory service
        success = await enhanced_memory_service.initialize()
        assert success, "Enhanced memory service initialization failed"
        
        logger.info("✅ Service initialization successful")
    
    async def test_health_checks(self):
        """Test health checks."""
        logger.info("🏥 Testing health checks...")
        
        health = await enhanced_memory_service.health_check()
        logger.info(f"Health status: {health}")
        
        assert health["overall"], "Overall health check failed"
        assert health["pinecone"]["ready"], "Pinecone not ready"
        assert health["neo4j"]["ready"], "Neo4j not ready"
        
        logger.info("✅ Health checks passed")
    
    async def test_user_management(self):
        """Test user management operations."""
        logger.info("👤 Testing user management...")
        
        # Create user profile
        success = await enhanced_memory_service.create_user_profile(
            self.test_user_id, 
            "Test User",
            email="test@example.com",
            timezone="UTC"
        )
        assert success, "User profile creation failed"
        
        # Get user profile
        profile = await enhanced_memory_service.get_user_profile(self.test_user_id)
        assert profile["user_id"] == self.test_user_id, "User profile retrieval failed"
        
        # Update user
        success = await enhanced_memory_service.update_user(
            self.test_user_id,
            last_seen=datetime.utcnow().isoformat()
        )
        assert success, "User update failed"
        
        logger.info("✅ User management tests passed")
    
    async def test_memory_crud(self):
        """Test memory CRUD operations."""
        logger.info("🧠 Testing memory CRUD operations...")
        
        # Create memory
        memory_text = "I love programming in Python and building AI applications"
        success = await enhanced_memory_service.create_memory(
            self.test_user_id,
            self.test_memory_id,
            memory_text,
            memory_type="fact",
            priority="high",
            category="programming"
        )
        assert success, "Memory creation failed"
        
        # Get memories
        memories = await enhanced_memory_service.get_memories(
            self.test_user_id,
            "programming",
            top_k=5
        )
        assert len(memories) > 0, "Memory retrieval failed"
        
        # Update memory
        updated_text = "I love programming in Python, building AI applications, and machine learning"
        success = await enhanced_memory_service.update_memory(
            self.test_user_id,
            self.test_memory_id,
            updated_text,
            category="ai_programming"
        )
        assert success, "Memory update failed"
        
        logger.info("✅ Memory CRUD tests passed")
    
    async def test_fact_management(self):
        """Test fact management operations."""
        logger.info("📚 Testing fact management...")
        
        # Create facts
        facts = [
            "My favorite programming language is Python",
            "I work as a software engineer",
            "I enjoy machine learning and AI",
            "My favorite framework is FastAPI"
        ]
        
        for fact in facts:
            success = await enhanced_memory_service.create_fact(
                self.test_user_id,
                fact,
                category="personal"
            )
            assert success, f"Fact creation failed: {fact}"
        
        # Get facts
        retrieved_facts = await enhanced_memory_service.get_facts(
            self.test_user_id,
            "programming",
            top_k=10
        )
        assert len(retrieved_facts) > 0, "Fact retrieval failed"
        
        logger.info("✅ Fact management tests passed")
    
    async def test_session_management(self):
        """Test session management."""
        logger.info("🔄 Testing session management...")
        
        # Create session
        success = await enhanced_memory_service.create_session(
            self.test_user_id,
            self.test_session_id
        )
        assert success, "Session creation failed"
        
        # Get session memories
        session_memories = await enhanced_memory_service.get_session_memories(
            self.test_user_id,
            self.test_session_id
        )
        assert session_memories["session_id"] == self.test_session_id, "Session memory retrieval failed"
        
        logger.info("✅ Session management tests passed")
    
    async def test_global_recall(self):
        """Test global recall functionality."""
        logger.info("🔍 Testing global recall...")
        
        # Perform global recall
        recall_results = await enhanced_memory_service.global_recall(
            self.test_user_id,
            "programming Python"
        )
        
        assert recall_results["user_id"] == self.test_user_id, "Global recall failed"
        assert "pinecone_memories" in recall_results, "Pinecone memories missing"
        assert "neo4j_relationships" in recall_results, "Neo4j relationships missing"
        
        logger.info(f"Global recall found {recall_results['total_recall_items']} items")
        logger.info("✅ Global recall tests passed")
    
    async def test_persistence(self):
        """Test data persistence."""
        logger.info("💾 Testing data persistence...")
        
        # Create session data
        session_data = {
            "messages": [
                {"role": "user", "content": "I'm working on a new AI project"},
                {"role": "assistant", "content": "That sounds exciting! What kind of AI project?"},
                {"role": "user", "content": "It's a natural language processing system for chatbots"}
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Persist session
        success = await enhanced_memory_service.persist_session(
            self.test_user_id,
            self.test_session_id,
            session_data
        )
        assert success, "Session persistence failed"
        
        logger.info("✅ Data persistence tests passed")
    
    async def test_cleanup(self):
        """Test cleanup operations."""
        logger.info("🧹 Testing cleanup operations...")
        
        # Delete memory
        success = await enhanced_memory_service.delete_memory(
            self.test_user_id,
            self.test_memory_id
        )
        assert success, "Memory deletion failed"
        
        # Delete facts
        facts_to_delete = [
            "My favorite programming language is Python",
            "I work as a software engineer"
        ]
        
        for fact in facts_to_delete:
            success = await enhanced_memory_service.delete_fact(
                self.test_user_id,
                fact
            )
            assert success, f"Fact deletion failed: {fact}"
        
        logger.info("✅ Cleanup tests passed")
    
    async def test_database_stats(self):
        """Test database statistics."""
        logger.info("📊 Testing database statistics...")
        
        stats = await enhanced_memory_service.get_database_stats()
        assert "pinecone" in stats, "Pinecone stats missing"
        assert "neo4j" in stats, "Neo4j stats missing"
        
        logger.info(f"Database stats: {stats}")
        logger.info("✅ Database statistics tests passed")

async def main():
    """Main test function."""
    tester = MemoryIntegrationTester()
    
    try:
        await tester.run_all_tests()
        await tester.test_database_stats()
        
        logger.info("🎉 All integration tests completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
