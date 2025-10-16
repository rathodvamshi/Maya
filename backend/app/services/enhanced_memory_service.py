"""
Enhanced Memory Service integrating Pinecone and Neo4j
Provides comprehensive CRUD operations with session persistence and global recall
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import json

from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service
from app.services import memory_store

logger = logging.getLogger(__name__)

class EnhancedMemoryService:
    """Enhanced memory service with comprehensive CRUD operations."""
    
    def __init__(self):
        self.pinecone = enhanced_pinecone_service
        self.neo4j = enhanced_neo4j_service
        
    # =====================================================
    # 🔹 Initialization and Health Checks
    # =====================================================
    async def initialize(self):
        """Initialize both Pinecone and Neo4j services."""
        try:
            # Initialize Pinecone
            self.pinecone.initialize()
            
            # Initialize Neo4j
            await self.neo4j.connect()
            try:
                await self.neo4j.start_heartbeat()
            except Exception:
                pass
            
            logger.info("✅ Enhanced memory service initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize enhanced memory service: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of both services."""
        pinecone_ready = self.pinecone.is_ready()
        neo4j_ready = await self.neo4j.ping()
        
        return {
            "pinecone": {
                "ready": pinecone_ready,
                "status": "connected" if pinecone_ready else "disconnected"
            },
            "neo4j": {
                "ready": neo4j_ready,
                "status": "connected" if neo4j_ready else "disconnected"
            },
            "overall": pinecone_ready and neo4j_ready
        }
    
    # =====================================================
    # 🔹 User Management
    # =====================================================
    async def create_user_profile(self, user_id: str, name: Optional[str] = None, **properties) -> bool:
        """Create user profile in both systems."""
        try:
            # Create user in Neo4j
            neo4j_success = await self.neo4j.create_user(user_id, name, **properties)
            
            # Create user namespace in Pinecone (implicit)
            pinecone_success = True  # Namespace is created on first vector insert
            
            if neo4j_success and pinecone_success:
                logger.info(f"✅ Created user profile: {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial user creation: Neo4j={neo4j_success}, Pinecone={pinecone_success}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to create user profile {user_id}: {e}")
            return False
    
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user profile."""
        try:
            # Get Neo4j user data
            neo4j_user = await self.neo4j.get_user(user_id)
            
            # Get Pinecone user memories
            pinecone_memories = self.pinecone.get_user_memories(user_id, "", top_k=50)
            
            # Get Neo4j relationships
            relationships = await self.neo4j.get_user_relationships(user_id)
            
            profile = {
                "user_id": user_id,
                "neo4j_data": neo4j_user or {},
                "pinecone_memories": pinecone_memories,
                "relationships": relationships,
                "total_memories": len(pinecone_memories),
                "total_relationships": len(relationships)
            }
            
            return profile
        except Exception as e:
            logger.error(f"❌ Failed to get user profile {user_id}: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    # =====================================================
    # 🔹 Memory Operations - Create
    # =====================================================
    async def create_memory(self, user_id: str, memory_id: str, text: str, 
                           memory_type: str = "fact", priority: str = "normal", 
                           **metadata) -> bool:
        """Create a memory in both systems."""
        try:
            # Create in Pinecone
            pinecone_metadata = {
                "user_id": user_id,
                "memory_id": memory_id,
                "type": memory_type,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                **metadata
            }
            pinecone_success = self.pinecone.create_user_memory(user_id, memory_id, text, pinecone_metadata)
            
            # Create concept in Neo4j if it's a fact
            neo4j_success = True
            if memory_type == "fact":
                # Extract key concepts from text
                concepts = self._extract_concepts(text)
                for concept in concepts:
                    await self.neo4j.create_concept(concept, "Fact")
                    await self.neo4j.create_relationship(user_id, "KNOWS", concept, "Fact")
            
            if pinecone_success and neo4j_success:
                logger.info(f"✅ Created memory: {memory_id} for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial memory creation: Pinecone={pinecone_success}, Neo4j={neo4j_success}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to create memory {memory_id}: {e}")
            return False
    
    async def create_fact(self, user_id: str, fact_text: str, category: str = "generic") -> bool:
        """Create a user fact."""
        try:
            # Create in Pinecone
            pinecone_success = self.pinecone.create_user_fact(user_id, fact_text, category)
            
            # Create in Neo4j
            neo4j_success = await self.neo4j.create_relationship(user_id, "HAS_FACT", fact_text, "Fact", category=category)
            
            if pinecone_success and neo4j_success:
                logger.info(f"✅ Created fact for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial fact creation: Pinecone={pinecone_success}, Neo4j={neo4j_success}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to create fact: {e}")
            return False
    
    # =====================================================
    # 🔹 Memory Operations - Read
    # =====================================================
    async def get_memories(self, user_id: str, query: str = "", top_k: int = 10) -> List[Dict[str, Any]]:
        """Get user memories from Pinecone."""
        try:
            if query:
                memories = self.pinecone.get_user_memories(user_id, query, top_k)
            else:
                # Get all memories if no query
                memories = self.pinecone.get_user_memories(user_id, "", top_k)
            
            return memories
        except Exception as e:
            logger.error(f"❌ Failed to get memories for user {user_id}: {e}")
            return []
    
    async def get_facts(self, user_id: str, query: str = "", top_k: int = 5) -> List[Dict[str, Any]]:
        """Get user facts from Pinecone."""
        try:
            if query:
                facts = self.pinecone.get_user_facts(user_id, query, top_k)
            else:
                facts = self.pinecone.get_user_facts(user_id, "", top_k)
            
            return facts
        except Exception as e:
            logger.error(f"❌ Failed to get facts for user {user_id}: {e}")
            return []
    
    async def get_relationships(self, user_id: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user relationships from Neo4j."""
        try:
            relationships = await self.neo4j.get_user_relationships(user_id, relationship_type)
            return relationships
        except Exception as e:
            logger.error(f"❌ Failed to get relationships for user {user_id}: {e}")
            return []
    
    async def search_memories(self, user_id: str, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Comprehensive memory search across both systems."""
        try:
            # Search Pinecone memories
            pinecone_memories = self.pinecone.get_user_memories(user_id, query, top_k)
            pinecone_facts = self.pinecone.get_user_facts(user_id, query, top_k)
            
            # Search Neo4j concepts
            neo4j_concepts = await self.neo4j.search_concepts(query)
            
            # Get Neo4j facts
            neo4j_facts = await self.neo4j.get_user_facts(user_id)
            
            return {
                "query": query,
                "pinecone_memories": pinecone_memories,
                "pinecone_facts": pinecone_facts,
                "neo4j_concepts": neo4j_concepts,
                "neo4j_facts": neo4j_facts,
                "total_results": len(pinecone_memories) + len(pinecone_facts) + len(neo4j_concepts)
            }
        except Exception as e:
            logger.error(f"❌ Failed to search memories: {e}")
            return {"query": query, "error": str(e)}
    
    # =====================================================
    # 🔹 Memory Operations - Update
    # =====================================================
    async def update_memory(self, user_id: str, memory_id: str, text: str, **metadata) -> bool:
        """Update a memory in Pinecone."""
        try:
            updated_metadata = {
                "user_id": user_id,
                "memory_id": memory_id,
                "text": text,
                "updated_at": datetime.utcnow().isoformat(),
                **metadata
            }
            
            success = self.pinecone.update_user_memory(user_id, memory_id, text, updated_metadata)
            
            if success:
                logger.info(f"✅ Updated memory: {memory_id}")
            else:
                logger.error(f"❌ Failed to update memory: {memory_id}")
            
            return success
        except Exception as e:
            logger.error(f"❌ Failed to update memory {memory_id}: {e}")
            return False
    
    async def update_user(self, user_id: str, **properties) -> bool:
        """Update user properties in Neo4j."""
        try:
            success = await self.neo4j.update_user(user_id, **properties)
            
            if success:
                logger.info(f"✅ Updated user: {user_id}")
            else:
                logger.error(f"❌ Failed to update user: {user_id}")
            
            return success
        except Exception as e:
            logger.error(f"❌ Failed to update user {user_id}: {e}")
            return False
    
    # =====================================================
    # 🔹 Memory Operations - Delete
    # =====================================================
    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """Delete a memory from Pinecone."""
        try:
            success = self.pinecone.delete_user_memory(user_id, memory_id)
            
            if success:
                logger.info(f"✅ Deleted memory: {memory_id}")
            else:
                logger.error(f"❌ Failed to delete memory: {memory_id}")
            
            return success
        except Exception as e:
            logger.error(f"❌ Failed to delete memory {memory_id}: {e}")
            return False
    
    async def delete_fact(self, user_id: str, fact_text: str) -> bool:
        """Delete a fact from both systems."""
        try:
            # Delete from Pinecone
            pinecone_success = self.pinecone.delete_user_fact(user_id, fact_text)
            
            # Delete from Neo4j
            neo4j_success = await self.neo4j.delete_relationship(user_id, "HAS_FACT", fact_text)
            
            if pinecone_success and neo4j_success:
                logger.info(f"✅ Deleted fact for user {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial fact deletion: Pinecone={pinecone_success}, Neo4j={neo4j_success}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to delete fact: {e}")
            return False
    
    async def delete_user(self, user_id: str) -> bool:
        """Delete user from both systems."""
        try:
            # Delete from Neo4j
            neo4j_success = await self.neo4j.delete_user(user_id)
            
            # Delete from Pinecone
            pinecone_success = self.pinecone.delete_user_namespace(user_id)
            
            if neo4j_success and pinecone_success:
                logger.info(f"✅ Deleted user: {user_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial user deletion: Neo4j={neo4j_success}, Pinecone={pinecone_success}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to delete user {user_id}: {e}")
            return False
    
    # =====================================================
    # 🔹 Session Management
    # =====================================================
    async def create_session(self, user_id: str, session_id: str) -> bool:
        """Create a new session."""
        try:
            # Create session in Neo4j
            await self.neo4j.create_relationship(user_id, "HAS_SESSION", session_id, "Session")
            
            # Session data is managed by Redis through memory_store
            logger.info(f"✅ Created session: {session_id} for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create session {session_id}: {e}")
            return False
    
    async def get_session_memories(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """Get session-specific memories."""
        try:
            # Get session history from Redis
            session_history = await memory_store.get_session_history(session_id)
            
            # Get related memories from Pinecone
            related_memories = self.pinecone.get_user_memories(user_id, "", top_k=20)
            
            # Get user facts
            user_facts = self.pinecone.get_user_facts(user_id, "", top_k=10)
            
            return {
                "session_id": session_id,
                "user_id": user_id,
                "session_history": session_history,
                "related_memories": related_memories,
                "user_facts": user_facts
            }
        except Exception as e:
            logger.error(f"❌ Failed to get session memories: {e}")
            return {"session_id": session_id, "user_id": user_id, "error": str(e)}
    
    # =====================================================
    # 🔹 Global Recall and Persistence
    # =====================================================
    async def global_recall(self, user_id: str, query: str) -> Dict[str, Any]:
        """Global recall across all memory systems."""
        try:
            # Get memories from Pinecone
            pinecone_memories = self.pinecone.get_user_memories(user_id, query, top_k=10)
            pinecone_facts = self.pinecone.get_user_facts(user_id, query, top_k=5)
            
            # Get relationships from Neo4j
            relationships = await self.neo4j.get_user_relationships(user_id)
            
            # Get Neo4j facts
            neo4j_facts = await self.neo4j.get_user_facts(user_id)
            
            # Get user network
            user_network = await self.neo4j.get_user_network(user_id)
            
            return {
                "query": query,
                "user_id": user_id,
                "pinecone_memories": pinecone_memories,
                "pinecone_facts": pinecone_facts,
                "neo4j_relationships": relationships,
                "neo4j_facts": neo4j_facts,
                "user_network": user_network,
                "total_recall_items": len(pinecone_memories) + len(pinecone_facts) + len(relationships)
            }
        except Exception as e:
            logger.error(f"❌ Failed to perform global recall: {e}")
            return {"query": query, "user_id": user_id, "error": str(e)}
    
    async def persist_session(self, user_id: str, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Persist session data across systems."""
        try:
            # Extract key information from session
            key_facts = self._extract_facts_from_session(session_data)
            
            # Store facts in both systems
            for fact in key_facts:
                await self.create_fact(user_id, fact)
            
            # Update session relationship in Neo4j
            await self.neo4j.update_relationship(user_id, "HAS_SESSION", session_id, 
                                               last_activity=datetime.utcnow().isoformat())
            
            logger.info(f"✅ Persisted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to persist session {session_id}: {e}")
            return False
    
    # =====================================================
    # 🔹 Utility Functions
    # =====================================================
    def _extract_concepts(self, text: str) -> List[str]:
        """Extract key concepts from text."""
        # Simple concept extraction - can be enhanced with NLP
        words = text.lower().split()
        # Filter out common words and extract meaningful terms
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        concepts = [word for word in words if len(word) > 3 and word not in stop_words]
        return concepts[:5]  # Limit to 5 concepts
    
    def _extract_facts_from_session(self, session_data: Dict[str, Any]) -> List[str]:
        """Extract facts from session data."""
        facts = []
        
        # Extract facts from messages
        messages = session_data.get("messages", [])
        for message in messages:
            content = message.get("content", "")
            if len(content) > 20:  # Only consider substantial messages
                facts.append(content)
        
        return facts[:10]  # Limit to 10 facts per session
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            # Get Pinecone stats
            pinecone_stats = self.pinecone.get_index_stats()
            
            # Get Neo4j stats
            neo4j_stats = await self.neo4j.get_database_info()
            
            return {
                "pinecone": pinecone_stats,
                "neo4j": neo4j_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Failed to get database stats: {e}")
            return {"error": str(e)}

# Create service instance
enhanced_memory_service = EnhancedMemoryService()
