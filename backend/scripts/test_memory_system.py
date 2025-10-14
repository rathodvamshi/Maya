#!/usr/bin/env python3
"""
Comprehensive Memory System Test Script
======================================

This script tests the complete memory system including:
- Pinecone long-term memory storage and retrieval
- Neo4j semantic memory storage and retrieval  
- MongoDB structured memory storage
- Cross-session memory persistence
- Gemini API integration for embeddings and text generation

Usage:
    python scripts/test_memory_system.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any, List

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services import pinecone_service, memory_service, memory_store
from app.services.neo4j_service import neo4j_service
from app.services.gemini_service import create_embedding, generate
from app.memory.manager import memory_manager
from app.services.memory_coordinator import gather_memory_context, post_message_update_async

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MemorySystemTester:
    def __init__(self):
        self.test_user_id = "test_user_memory_system"
        self.test_session_id = "test_session_001"
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run all memory system tests."""
        logger.info("🧠 Starting Comprehensive Memory System Tests")
        logger.info("=" * 60)
        
        tests = [
            ("Pinecone Connection", self.test_pinecone_connection),
            ("Neo4j Connection", self.test_neo4j_connection),
            ("Gemini API", self.test_gemini_api),
            ("MongoDB Memory Storage", self.test_mongodb_memory_storage),
            ("Pinecone Embedding Storage", self.test_pinecone_embedding_storage),
            ("Neo4j Semantic Storage", self.test_neo4j_semantic_storage),
            ("Memory Coordinator", self.test_memory_coordinator),
            ("Cross-Session Persistence", self.test_cross_session_persistence),
            ("Memory Retrieval", self.test_memory_retrieval),
            ("End-to-End Memory Flow", self.test_end_to_end_flow),
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n🔍 Running: {test_name}")
            try:
                result = await test_func()
                self.test_results[test_name] = {"status": "PASS", "result": result}
                logger.info(f"✅ {test_name}: PASSED")
            except Exception as e:
                self.test_results[test_name] = {"status": "FAIL", "error": str(e)}
                logger.error(f"❌ {test_name}: FAILED - {e}")
        
        self.print_summary()
    
    async def test_pinecone_connection(self):
        """Test Pinecone connection and index availability."""
        if not pinecone_service.is_ready():
            raise Exception("Pinecone service not ready")
        
        index = pinecone_service.get_index()
        if not index:
            raise Exception("Pinecone index not available")
        
        return {"index_ready": True, "index_name": settings.PINECONE_INDEX}
    
    async def test_neo4j_connection(self):
        """Test Neo4j connection."""
        if not await neo4j_service.ping():
            raise Exception("Neo4j service not available")
        
        return {"neo4j_connected": True}
    
    async def test_gemini_api(self):
        """Test Gemini API for text generation and embeddings."""
        # Test text generation
        test_prompt = "Hello, this is a test message for memory system validation."
        try:
            response = generate(test_prompt)
            if not response or len(response.strip()) < 10:
                raise Exception("Gemini text generation returned empty or too short response")
        except Exception as e:
            raise Exception(f"Gemini text generation failed: {e}")
        
        # Test embedding generation
        try:
            embedding = create_embedding(test_prompt)
            if not embedding or len(embedding) != 768:
                raise Exception(f"Gemini embedding generation failed: expected 768 dimensions, got {len(embedding) if embedding else 0}")
        except Exception as e:
            raise Exception(f"Gemini embedding generation failed: {e}")
        
        return {
            "text_generation": True,
            "embedding_generation": True,
            "embedding_dimensions": len(embedding)
        }
    
    async def test_mongodb_memory_storage(self):
        """Test MongoDB memory storage."""
        test_memory = {
            "user_id": self.test_user_id,
            "title": "Test Memory",
            "value": "This is a test memory for system validation",
            "type": "test",
            "priority": "normal",
            "lifecycle_state": "active"
        }
        
        # Create memory
        memory_doc = await memory_service.create_memory(test_memory)
        if not memory_doc or not memory_doc.get("_id"):
            raise Exception("Failed to create memory in MongoDB")
        
        memory_id = memory_doc["_id"]
        
        # Retrieve memory
        retrieved = await memory_service.get_memory(self.test_user_id, memory_id)
        if not retrieved:
            raise Exception("Failed to retrieve memory from MongoDB")
        
        # List memories
        memories = await memory_service.list_memories(self.test_user_id, limit=10)
        if not memories:
            raise Exception("Failed to list memories from MongoDB")
        
        return {
            "memory_created": True,
            "memory_retrieved": True,
            "memory_listed": True,
            "memory_id": memory_id,
            "total_memories": len(memories)
        }
    
    async def test_pinecone_embedding_storage(self):
        """Test Pinecone embedding storage and retrieval."""
        test_text = "This is a test message for Pinecone embedding storage validation."
        
        # Store embedding
        timestamp = datetime.utcnow().isoformat()
        pinecone_service.upsert_message_embedding(
            user_id=self.test_user_id,
            session_id=self.test_session_id,
            text=test_text,
            role="user",
            timestamp=timestamp
        )
        
        # Store user fact embedding
        pinecone_service.upsert_user_fact_embedding(
            user_id=self.test_user_id,
            fact_text="User likes testing memory systems",
            timestamp=timestamp,
            category="preference"
        )
        
        # Query similar texts
        similar_texts = pinecone_service.query_similar_texts(
            user_id=self.test_user_id,
            text="test message",
            top_k=3
        )
        
        # Query user facts
        user_facts = pinecone_service.query_user_facts(
            user_id=self.test_user_id,
            hint_text="user preferences",
            top_k=3
        )
        
        return {
            "message_embedding_stored": True,
            "user_fact_embedding_stored": True,
            "similar_texts_found": bool(similar_texts),
            "user_facts_found": len(user_facts) > 0,
            "similar_texts_count": len(similar_texts.split('\n---\n')) if similar_texts else 0,
            "user_facts_count": len(user_facts)
        }
    
    async def test_neo4j_semantic_storage(self):
        """Test Neo4j semantic storage and retrieval."""
        # Create user node
        await neo4j_service.create_user_node(self.test_user_id)
        
        # Add user preference
        await neo4j_service.upsert_user_preference(
            user_id=self.test_user_id,
            label="Memory Testing",
            pref_type="HOBBY"
        )
        
        # Create relation
        await neo4j_service.create_relation(
            user_id=self.test_user_id,
            rel_type="LIKES",
            concept="Testing"
        )
        
        # Retrieve user facts
        facts = await neo4j_service.get_user_facts(self.test_user_id)
        
        return {
            "user_node_created": True,
            "preference_added": True,
            "relation_created": True,
            "facts_retrieved": bool(facts),
            "facts_text": facts
        }
    
    async def test_memory_coordinator(self):
        """Test memory coordinator functionality."""
        # Test memory context gathering
        context = await gather_memory_context(
            user_id=self.test_user_id,
            user_key=self.test_user_id,
            session_id=self.test_session_id,
            latest_user_message="What do you remember about me?",
            top_k_semantic=3,
            top_k_user_facts=3
        )
        
        if not context:
            raise Exception("Memory coordinator returned empty context")
        
        # Test post message update
        await post_message_update_async(
            user_id=self.test_user_id,
            user_key=self.test_user_id,
            session_id=self.test_session_id,
            user_message="I love testing memory systems and want to remember this conversation.",
            ai_message="I'll remember that you love testing memory systems and this conversation.",
            state="testing"
        )
        
        return {
            "context_gathered": True,
            "context_keys": list(context.keys()),
            "post_update_completed": True,
            "has_pinecone_context": bool(context.get("pinecone_context")),
            "has_neo4j_facts": bool(context.get("neo4j_facts")),
            "has_profile": bool(context.get("profile"))
        }
    
    async def test_cross_session_persistence(self):
        """Test memory persistence across different sessions."""
        new_session_id = "test_session_002"
        
        # Store memory in first session
        await memory_store.append_session_messages(
            self.test_session_id,
            [
                {"role": "user", "content": "My name is Test User and I love memory systems"},
                {"role": "assistant", "content": "I'll remember that your name is Test User and you love memory systems"}
            ]
        )
        
        # Test retrieval in new session
        context = await gather_memory_context(
            user_id=self.test_user_id,
            user_key=self.test_user_id,
            session_id=new_session_id,
            latest_user_message="What is my name?",
            top_k_semantic=5,
            top_k_user_facts=5
        )
        
        # Check if previous session data is accessible
        has_cross_session_memory = (
            context.get("pinecone_context") and "Test User" in context.get("pinecone_context", "") or
            context.get("user_facts_semantic") and any("Test User" in fact for fact in context.get("user_facts_semantic", []))
        )
        
        return {
            "cross_session_retrieval": has_cross_session_memory,
            "context_available": bool(context),
            "pinecone_context_length": len(context.get("pinecone_context", "")),
            "user_facts_count": len(context.get("user_facts_semantic", []))
        }
    
    async def test_memory_retrieval(self):
        """Test comprehensive memory retrieval."""
        # Test unified memory manager
        memory_result = await memory_manager.get_memory(
            user_id=self.test_user_id,
            query="What do you know about me?",
            memory_type=None,
            session_id=self.test_session_id
        )
        
        if not memory_result:
            raise Exception("Memory manager returned empty result")
        
        return {
            "memory_manager_working": True,
            "has_history": len(memory_result.get("history", [])) > 0,
            "has_pinecone": len(memory_result.get("pinecone", [])) > 0,
            "has_neo4j": bool(memory_result.get("neo4j")),
            "total_pinecone_memories": len(memory_result.get("pinecone", []))
        }
    
    async def test_end_to_end_flow(self):
        """Test complete end-to-end memory flow."""
        # Simulate a conversation flow
        user_messages = [
            "Hi, my name is Test User",
            "I work as a software engineer",
            "I love testing memory systems",
            "What do you remember about me?"
        ]
        
        ai_responses = []
        for i, user_msg in enumerate(user_messages):
            # Gather context
            context = await gather_memory_context(
                user_id=self.test_user_id,
                user_key=self.test_user_id,
                session_id=f"e2e_session_{i}",
                latest_user_message=user_msg,
                top_k_semantic=3,
                top_k_user_facts=3
            )
            
            # Simulate AI response (using Gemini)
            try:
                ai_response = generate(f"User said: {user_msg}. Context: {context.get('pinecone_context', '')[:200]}...")
                ai_responses.append(ai_response)
            except Exception as e:
                ai_response = f"Simulated response to: {user_msg}"
                ai_responses.append(ai_response)
            
            # Post message update
            await post_message_update_async(
                user_id=self.test_user_id,
                user_key=self.test_user_id,
                session_id=f"e2e_session_{i}",
                user_message=user_msg,
                ai_message=ai_response,
                state="conversation"
            )
        
        # Test final memory retrieval
        final_context = await gather_memory_context(
            user_id=self.test_user_id,
            user_key=self.test_user_id,
            session_id="e2e_final",
            latest_user_message="Tell me everything you know about me",
            top_k_semantic=10,
            top_k_user_facts=10
        )
        
        return {
            "conversation_flow_completed": True,
            "messages_processed": len(user_messages),
            "ai_responses_generated": len(ai_responses),
            "final_context_available": bool(final_context),
            "final_pinecone_context": bool(final_context.get("pinecone_context")),
            "final_neo4j_facts": bool(final_context.get("neo4j_facts"))
        }
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "=" * 60)
        logger.info("🧠 MEMORY SYSTEM TEST SUMMARY")
        logger.info("=" * 60)
        
        passed = sum(1 for result in self.test_results.values() if result["status"] == "PASS")
        failed = sum(1 for result in self.test_results.values() if result["status"] == "FAIL")
        total = len(self.test_results)
        
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed} ✅")
        logger.info(f"Failed: {failed} ❌")
        logger.info(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            logger.info("\n❌ FAILED TESTS:")
            for test_name, result in self.test_results.items():
                if result["status"] == "FAIL":
                    logger.info(f"  - {test_name}: {result['error']}")
        
        logger.info("\n✅ PASSED TESTS:")
        for test_name, result in self.test_results.items():
            if result["status"] == "PASS":
                logger.info(f"  - {test_name}")
        
        logger.info("\n" + "=" * 60)
        
        if failed == 0:
            logger.info("🎉 ALL TESTS PASSED! Memory system is working correctly.")
        else:
            logger.info("⚠️  Some tests failed. Please check the configuration and connections.")
        
        return failed == 0

async def main():
    """Main test runner."""
    tester = MemorySystemTester()
    success = await tester.run_all_tests()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
