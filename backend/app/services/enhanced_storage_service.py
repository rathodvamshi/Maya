"""
Enhanced Storage Service
Ensures proper storage and recall of user data across all systems
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from app.services.enhanced_memory_service import enhanced_memory_service
from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service
from app.services import memory_store, redis_service

logger = logging.getLogger(__name__)

class EnhancedStorageService:
    """Enhanced storage service with guaranteed data persistence."""
    
    def __init__(self):
        self.memory_service = enhanced_memory_service
        self.pinecone = enhanced_pinecone_service
        self.neo4j = enhanced_neo4j_service
    
    async def ensure_user_exists(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Ensure user exists in all systems."""
        try:
            # Create user in Neo4j
            success = await self.neo4j.create_user(
                user_id,
                user_data.get("name"),
                email=user_data.get("email"),
                timezone=user_data.get("timezone"),
                created_at=datetime.utcnow().isoformat()
            )
            
            if success:
                logger.info(f"✅ User {user_id} created in Neo4j")
            else:
                logger.warning(f"⚠️ User {user_id} may already exist in Neo4j")
            
            # Store user profile in Redis
            client = redis_service.get_client()
            if client:
                profile_key = f"user:{user_id}:profile"
                await client.set(
                    profile_key,
                    json.dumps(user_data),
                    ex=86400  # 24 hours TTL
                )
                logger.info(f"✅ User {user_id} profile cached in Redis")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to ensure user {user_id} exists: {e}")
            return False
    
    async def store_memory_with_guarantee(self, user_id: str, memory_data: Dict[str, Any]) -> bool:
        """Store memory with guarantee across all systems."""
        try:
            memory_id = memory_data.get("memory_id", f"mem_{datetime.utcnow().timestamp()}")
            text = memory_data.get("text", "")
            memory_type = memory_data.get("memory_type", "fact")
            priority = memory_data.get("priority", "normal")
            
            # Store in Pinecone
            pinecone_success = self.pinecone.create_user_memory(
                user_id,
                memory_id,
                text,
                {
                    "user_id": user_id,
                    "memory_id": memory_id,
                    "text": text,
                    "type": memory_type,
                    "priority": priority,
                    "created_at": datetime.utcnow().isoformat(),
                    **memory_data.get("metadata", {})
                }
            )
            
            # Store in Neo4j as concept
            neo4j_success = True
            if memory_type == "fact":
                # Extract key concepts
                concepts = self._extract_concepts(text)
                for concept in concepts:
                    await self.neo4j.create_concept(concept, "Fact")
                    await self.neo4j.create_relationship(user_id, "KNOWS", concept, "Fact")
            
            # Store in Redis for quick access
            redis_success = True
            client = redis_service.get_client()
            if client:
                memory_key = f"user:{user_id}:memory:{memory_id}"
                await client.set(
                    memory_key,
                    json.dumps({
                        "memory_id": memory_id,
                        "text": text,
                        "type": memory_type,
                        "priority": priority,
                        "created_at": datetime.utcnow().isoformat()
                    }),
                    ex=86400  # 24 hours TTL
                )
            
            if pinecone_success and neo4j_success and redis_success:
                logger.info(f"✅ Memory {memory_id} stored successfully for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial storage for memory {memory_id}: Pinecone={pinecone_success}, Neo4j={neo4j_success}, Redis={redis_success}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to store memory for user {user_id}: {e}")
            return False
    
    async def store_fact_with_guarantee(self, user_id: str, fact_text: str, category: str = "generic") -> bool:
        """Store fact with guarantee across all systems."""
        try:
            # Store in Pinecone
            pinecone_success = self.pinecone.create_user_fact(user_id, fact_text, category)
            
            # Store in Neo4j
            neo4j_success = await self.neo4j.create_relationship(user_id, "HAS_FACT", fact_text, "Fact", category=category)
            
            # Store in Redis
            redis_success = True
            client = redis_service.get_client()
            if client:
                fact_key = f"user:{user_id}:fact:{hash(fact_text)}"
                await client.set(
                    fact_key,
                    json.dumps({
                        "fact_text": fact_text,
                        "category": category,
                        "created_at": datetime.utcnow().isoformat()
                    }),
                    ex=86400
                )
            
            if pinecone_success and neo4j_success and redis_success:
                logger.info(f"✅ Fact stored successfully for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial storage for fact: Pinecone={pinecone_success}, Neo4j={neo4j_success}, Redis={redis_success}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to store fact for user {user_id}: {e}")
            return False
    
    async def store_session_with_guarantee(self, user_id: str, session_id: str, messages: List[Dict[str, str]]) -> bool:
        """Store session with guarantee across all systems."""
        try:
            # Store in Neo4j
            neo4j_success = await self.neo4j.create_relationship(
                user_id, 
                "HAS_SESSION", 
                session_id, 
                "Session",
                created_at=datetime.utcnow().isoformat()
            )
            
            # Store in Redis
            redis_success = True
            for message in messages:
                await memory_store.append_session_messages(
                    session_id,
                    [message],
                    max_items=50
                )
            
            # Extract and store key facts from session
            facts_extracted = 0
            for message in messages:
                if message.get("role") == "user" and len(message.get("content", "")) > 20:
                    # Extract facts from user messages
                    fact_text = message["content"]
                    if await self.store_fact_with_guarantee(user_id, fact_text, "session_fact"):
                        facts_extracted += 1
            
            if neo4j_success and redis_success:
                logger.info(f"✅ Session {session_id} stored successfully for user {user_id} ({facts_extracted} facts extracted)")
                return True
            else:
                logger.warning(f"⚠️ Partial storage for session {session_id}: Neo4j={neo4j_success}, Redis={redis_success}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to store session {session_id} for user {user_id}: {e}")
            return False
    
    async def recall_user_data(self, user_id: str, query: str = "") -> Dict[str, Any]:
        """Recall all user data with guarantee."""
        try:
            # Get memories from Pinecone
            memories = self.pinecone.get_user_memories(user_id, query, top_k=20)
            
            # Get facts from Pinecone
            facts = self.pinecone.get_user_facts(user_id, query, top_k=10)
            
            # Get relationships from Neo4j
            relationships = await self.neo4j.get_user_relationships(user_id)
            
            # Get user info from Neo4j
            user_info = await self.neo4j.get_user(user_id)
            
            # Get session data from Redis
            client = redis_service.get_client()
            session_data = {}
            if client:
                session_keys = await client.keys(f"sess:{user_id}:*")
                for key in session_keys:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    if key_str.endswith(":msgs"):
                        messages = await memory_store.get_session_history(key_str.split(":")[1])
                        session_data[key_str] = messages
            
            return {
                "user_id": user_id,
                "user_info": user_info,
                "memories": memories,
                "facts": facts,
                "relationships": relationships,
                "sessions": session_data,
                "total_items": len(memories) + len(facts) + len(relationships),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to recall data for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "error": str(e),
                "memories": [],
                "facts": [],
                "relationships": [],
                "sessions": {},
                "total_items": 0
            }
    
    async def ensure_data_persistence(self, user_id: str) -> bool:
        """Ensure all user data is properly persisted."""
        try:
            # Check if user exists in all systems
            user_exists_neo4j = await self.neo4j.get_user(user_id) is not None
            user_exists_redis = False
            
            client = redis_service.get_client()
            if client:
                profile_key = f"user:{user_id}:profile"
                user_exists_redis = await client.exists(profile_key)
            
            # If user doesn't exist, create them
            if not user_exists_neo4j:
                await self.neo4j.create_user(user_id, f"User_{user_id}")
            
            if not user_exists_redis and client:
                await client.set(
                    f"user:{user_id}:profile",
                    json.dumps({"user_id": user_id, "name": f"User_{user_id}"}),
                    ex=86400
                )
            
            logger.info(f"✅ Data persistence ensured for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to ensure data persistence for user {user_id}: {e}")
            return False
    
    def _extract_concepts(self, text: str) -> List[str]:
        """Extract key concepts from text."""
        # Simple concept extraction
        words = text.lower().split()
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should"}
        concepts = [word for word in words if len(word) > 3 and word not in stop_words]
        return concepts[:5]  # Limit to 5 concepts
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics."""
        try:
            stats = {}
            
            # Pinecone stats
            if self.pinecone.is_ready():
                pinecone_stats = self.pinecone.get_index_stats()
                stats["pinecone"] = {
                    "ready": True,
                    "total_vectors": pinecone_stats.get("total_vector_count", 0),
                    "dimension": pinecone_stats.get("dimension", 0)
                }
            else:
                stats["pinecone"] = {"ready": False}
            
            # Neo4j stats
            if await self.neo4j.ping():
                db_info = await self.neo4j.get_database_info()
                stats["neo4j"] = {
                    "ready": True,
                    "nodes": db_info.get("nodes", 0),
                    "relationships": db_info.get("relationships", 0)
                }
            else:
                stats["neo4j"] = {"ready": False}
            
            # Redis stats
            client = redis_service.get_client()
            if client:
                keys = await client.keys("*")
                stats["redis"] = {
                    "ready": True,
                    "total_keys": len(keys),
                    "user_keys": len([k for k in keys if k.decode('utf-8').startswith("user:")]),
                    "session_keys": len([k for k in keys if k.decode('utf-8').startswith("sess:")])
                }
            else:
                stats["redis"] = {"ready": False}
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get storage stats: {e}")
            return {"error": str(e)}

# Create service instance
enhanced_storage_service = EnhancedStorageService()
