#!/usr/bin/env python3
"""
Memory System Initialization Script
==================================

This script initializes and verifies all memory system components:
- Pinecone index setup and verification
- Neo4j database connection and schema
- MongoDB memory collections and indexes
- Gemini API configuration
- Redis connection for session storage

Usage:
    python scripts/initialize_memory_system.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config import settings
from app.services import pinecone_service, redis_service
from app.services.neo4j_service import neo4j_service
from app.services.gemini_service import create_embedding, generate
from app.database import db_client
from app.services import memory_service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MemorySystemInitializer:
    def __init__(self):
        self.initialization_results = {}
        
    async def initialize_all_systems(self):
        """Initialize all memory system components."""
        logger.info("🚀 Starting Memory System Initialization")
        logger.info("=" * 60)
        
        initializers = [
            ("MongoDB Connection", self.initialize_mongodb),
            ("Redis Connection", self.initialize_redis),
            ("Pinecone Index", self.initialize_pinecone),
            ("Neo4j Database", self.initialize_neo4j),
            ("Gemini API", self.initialize_gemini),
            ("Memory Collections", self.initialize_memory_collections),
            ("System Verification", self.verify_system),
        ]
        
        for init_name, init_func in initializers:
            logger.info(f"\n🔧 Initializing: {init_name}")
            try:
                result = await init_func()
                self.initialization_results[init_name] = {"status": "SUCCESS", "result": result}
                logger.info(f"✅ {init_name}: SUCCESS")
            except Exception as e:
                self.initialization_results[init_name] = {"status": "FAILED", "error": str(e)}
                logger.error(f"❌ {init_name}: FAILED - {e}")
        
        self.print_initialization_summary()
    
    async def initialize_mongodb(self):
        """Initialize MongoDB connection and create indexes."""
        # Connect to MongoDB
        connected = await asyncio.to_thread(db_client.connect)
        if not connected:
            raise Exception("Failed to connect to MongoDB")
        
        # Create indexes
        await asyncio.to_thread(db_client.ensure_indexes)
        
        # Test connection
        if not db_client.healthy():
            raise Exception("MongoDB connection not healthy")
        
        return {
            "connected": True,
            "indexes_created": True,
            "database_name": settings.MONGO_DB
        }
    
    async def initialize_redis(self):
        """Initialize Redis connection."""
        # Test Redis connection
        redis_ok = await redis_service.ping()
        if not redis_ok:
            raise Exception("Redis connection failed")
        
        # Test basic operations
        test_key = "memory_init_test"
        await redis_service.redis_client.set(test_key, "test_value", ex=60)
        value = await redis_service.redis_client.get(test_key)
        if value != "test_value":
            raise Exception("Redis read/write test failed")
        
        await redis_service.redis_client.delete(test_key)
        
        return {
            "connected": True,
            "read_write_test": True,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT
        }
    
    async def initialize_pinecone(self):
        """Initialize Pinecone index."""
        # Initialize Pinecone
        pinecone_service.initialize_pinecone()
        
        if not pinecone_service.is_ready():
            raise Exception("Pinecone initialization failed")
        
        index = pinecone_service.get_index()
        if not index:
            raise Exception("Pinecone index not available")
        
        # Test embedding creation and storage
        test_text = "Memory system initialization test"
        embedding = create_embedding(test_text)
        if not embedding or len(embedding) != 768:
            raise Exception(f"Embedding creation failed: expected 768 dimensions, got {len(embedding) if embedding else 0}")
        
        # Test vector upsert
        test_vector_id = "init_test_vector"
        try:
            index.upsert(vectors=[(test_vector_id, embedding, {"test": "initialization"})])
        except Exception as e:
            raise Exception(f"Vector upsert test failed: {e}")
        
        # Test vector query
        try:
            results = index.query(vector=embedding, top_k=1, include_metadata=True)
            if not results or not hasattr(results, 'matches'):
                raise Exception("Vector query test failed")
        except Exception as e:
            raise Exception(f"Vector query test failed: {e}")
        
        # Clean up test vector
        try:
            index.delete(ids=[test_vector_id])
        except Exception:
            pass  # Best effort cleanup
        
        return {
            "initialized": True,
            "index_ready": True,
            "index_name": settings.PINECONE_INDEX,
            "embedding_dimensions": 768,
            "vector_operations": True
        }
    
    async def initialize_neo4j(self):
        """Initialize Neo4j database and create schema."""
        # Connect to Neo4j
        await neo4j_service.connect()
        
        if not await neo4j_service.ping():
            raise Exception("Neo4j connection failed")
        
        # Create test user node
        test_user_id = "init_test_user"
        await neo4j_service.create_user_node(test_user_id)
        
        # Test relationship creation
        await neo4j_service.create_relation(
            user_id=test_user_id,
            rel_type="TESTING",
            concept="Memory System"
        )
        
        # Test fact retrieval
        facts = await neo4j_service.get_user_facts(test_user_id)
        if not facts:
            raise Exception("Neo4j fact retrieval test failed")
        
        # Clean up test data
        try:
            await neo4j_service.delete_relation(test_user_id, "TESTING", "Memory System")
        except Exception:
            pass  # Best effort cleanup
        
        return {
            "connected": True,
            "schema_created": True,
            "operations_tested": True,
            "uri": settings.NEO4J_URI
        }
    
    async def initialize_gemini(self):
        """Initialize and test Gemini API."""
        # Test text generation
        test_prompt = "This is a test for memory system initialization."
        try:
            response = generate(test_prompt)
            if not response or len(response.strip()) < 10:
                raise Exception("Gemini text generation test failed")
        except Exception as e:
            raise Exception(f"Gemini text generation failed: {e}")
        
        # Test embedding generation
        try:
            embedding = create_embedding(test_prompt)
            if not embedding or len(embedding) != 768:
                raise Exception(f"Gemini embedding test failed: expected 768 dimensions, got {len(embedding) if embedding else 0}")
        except Exception as e:
            raise Exception(f"Gemini embedding generation failed: {e}")
        
        return {
            "text_generation": True,
            "embedding_generation": True,
            "embedding_dimensions": len(embedding),
            "model": settings.GOOGLE_MODEL
        }
    
    async def initialize_memory_collections(self):
        """Initialize memory-related collections and test operations."""
        # Test memory service operations
        test_memory = {
            "user_id": "init_test_user",
            "title": "Initialization Test Memory",
            "value": "This is a test memory created during system initialization",
            "type": "test",
            "priority": "normal",
            "lifecycle_state": "active"
        }
        
        # Create test memory
        memory_doc = await memory_service.create_memory(test_memory)
        if not memory_doc or not memory_doc.get("_id"):
            raise Exception("Memory creation test failed")
        
        memory_id = memory_doc["_id"]
        
        # Test memory retrieval
        retrieved = await memory_service.get_memory("init_test_user", memory_id)
        if not retrieved:
            raise Exception("Memory retrieval test failed")
        
        # Test memory listing
        memories = await memory_service.list_memories("init_test_user", limit=10)
        if not memories:
            raise Exception("Memory listing test failed")
        
        # Clean up test memory
        try:
            await memory_service.update_memory(
                "init_test_user", 
                memory_id, 
                {"lifecycle_state": "archived"}, 
                reason="cleanup"
            )
        except Exception:
            pass  # Best effort cleanup
        
        return {
            "memory_creation": True,
            "memory_retrieval": True,
            "memory_listing": True,
            "test_memory_id": memory_id
        }
    
    async def verify_system(self):
        """Verify the complete memory system is working."""
        # Test end-to-end memory flow
        test_user_id = "system_verification_user"
        test_session_id = "verification_session"
        
        # Store a test message
        test_message = "This is a system verification message for memory testing."
        timestamp = datetime.utcnow().isoformat()
        
        # Store in Pinecone
        pinecone_service.upsert_message_embedding(
            user_id=test_user_id,
            session_id=test_session_id,
            text=test_message,
            role="user",
            timestamp=timestamp
        )
        
        # Store in Neo4j
        await neo4j_service.create_user_node(test_user_id)
        await neo4j_service.create_relation(
            user_id=test_user_id,
            rel_type="TESTING",
            concept="System Verification"
        )
        
        # Store in MongoDB
        memory_doc = await memory_service.create_memory({
            "user_id": test_user_id,
            "title": "System Verification Memory",
            "value": test_message,
            "type": "verification",
            "priority": "normal",
            "lifecycle_state": "active"
        })
        
        # Test retrieval
        similar_texts = pinecone_service.query_similar_texts(
            user_id=test_user_id,
            text="verification message",
            top_k=3
        )
        
        facts = await neo4j_service.get_user_facts(test_user_id)
        
        memories = await memory_service.list_memories(test_user_id, limit=5)
        
        # Verify all systems are working
        if not similar_texts:
            raise Exception("Pinecone retrieval verification failed")
        
        if not facts:
            raise Exception("Neo4j retrieval verification failed")
        
        if not memories:
            raise Exception("MongoDB retrieval verification failed")
        
        # Clean up verification data
        try:
            await neo4j_service.delete_relation(test_user_id, "TESTING", "System Verification")
            await memory_service.update_memory(
                test_user_id,
                memory_doc["_id"],
                {"lifecycle_state": "archived"},
                reason="cleanup"
            )
        except Exception:
            pass  # Best effort cleanup
        
        return {
            "pinecone_verification": True,
            "neo4j_verification": True,
            "mongodb_verification": True,
            "end_to_end_flow": True,
            "similar_texts_found": bool(similar_texts),
            "facts_found": bool(facts),
            "memories_found": len(memories) > 0
        }
    
    def print_initialization_summary(self):
        """Print initialization summary."""
        logger.info("\n" + "=" * 60)
        logger.info("🚀 MEMORY SYSTEM INITIALIZATION SUMMARY")
        logger.info("=" * 60)
        
        successful = sum(1 for result in self.initialization_results.values() if result["status"] == "SUCCESS")
        failed = sum(1 for result in self.initialization_results.values() if result["status"] == "FAILED")
        total = len(self.initialization_results)
        
        logger.info(f"Total Components: {total}")
        logger.info(f"Successfully Initialized: {successful} ✅")
        logger.info(f"Failed: {failed} ❌")
        logger.info(f"Success Rate: {(successful/total)*100:.1f}%")
        
        if failed > 0:
            logger.info("\n❌ FAILED INITIALIZATIONS:")
            for component, result in self.initialization_results.items():
                if result["status"] == "FAILED":
                    logger.info(f"  - {component}: {result['error']}")
        
        logger.info("\n✅ SUCCESSFULLY INITIALIZED:")
        for component, result in self.initialization_results.items():
            if result["status"] == "SUCCESS":
                logger.info(f"  - {component}")
        
        logger.info("\n" + "=" * 60)
        
        if failed == 0:
            logger.info("🎉 ALL COMPONENTS INITIALIZED SUCCESSFULLY!")
            logger.info("Memory system is ready for use.")
        else:
            logger.info("⚠️  Some components failed to initialize.")
            logger.info("Please check the configuration and try again.")
        
        return failed == 0

async def main():
    """Main initialization runner."""
    initializer = MemorySystemInitializer()
    success = await initializer.initialize_all_systems()
    
    if success:
        logger.info("\n🎯 Memory system initialization completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n💥 Memory system initialization failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
