"""
Enhanced Memory Router
Provides comprehensive CRUD operations for Pinecone and Neo4j integration
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

from app.services.enhanced_memory_service import enhanced_memory_service
from app.security import get_current_active_user

router = APIRouter(prefix="/api/enhanced-memory", tags=["Enhanced Memory"])

# =====================================================
# 🔹 Pydantic Models
# =====================================================
class UserProfileCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = "UTC"
    properties: Optional[Dict[str, Any]] = {}

class MemoryCreate(BaseModel):
    memory_id: str
    text: str
    memory_type: str = "fact"
    priority: str = "normal"
    metadata: Optional[Dict[str, Any]] = {}

class MemoryUpdate(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = {}

class FactCreate(BaseModel):
    fact_text: str
    category: str = "generic"

class SessionData(BaseModel):
    messages: List[Dict[str, str]]
    timestamp: str
    metadata: Optional[Dict[str, Any]] = {}

class GlobalRecallRequest(BaseModel):
    query: str
    top_k: int = 10

# =====================================================
# 🔹 Health and Status Endpoints
# =====================================================
@router.get("/health")
async def get_health_status():
    """Get health status of enhanced memory services."""
    try:
        health = await enhanced_memory_service.health_check()
        return {
            "status": "healthy" if health["overall"] else "unhealthy",
            "services": health,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/stats")
async def get_database_stats():
    """Get comprehensive database statistics."""
    try:
        stats = await enhanced_memory_service.get_database_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")

# =====================================================
# 🔹 User Management Endpoints
# =====================================================
@router.post("/users/{user_id}/profile")
async def create_user_profile(
    user_id: str,
    profile: UserProfileCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create user profile in both systems."""
    try:
        success = await enhanced_memory_service.create_user_profile(
            user_id,
            profile.name,
            **profile.properties
        )
        
        if success:
            return {"message": "User profile created successfully", "user_id": user_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to create user profile")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user profile: {str(e)}")

@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get comprehensive user profile."""
    try:
        profile = await enhanced_memory_service.get_user_profile(user_id)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")

@router.put("/users/{user_id}/profile")
async def update_user_profile(
    user_id: str,
    properties: Dict[str, Any],
    current_user: dict = Depends(get_current_active_user)
):
    """Update user profile."""
    try:
        success = await enhanced_memory_service.update_user(user_id, **properties)
        
        if success:
            return {"message": "User profile updated successfully", "user_id": user_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to update user profile")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user profile: {str(e)}")

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete user from both systems."""
    try:
        success = await enhanced_memory_service.delete_user(user_id)
        
        if success:
            return {"message": "User deleted successfully", "user_id": user_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete user")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

# =====================================================
# 🔹 Memory Management Endpoints
# =====================================================
@router.post("/users/{user_id}/memories")
async def create_memory(
    user_id: str,
    memory: MemoryCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new memory."""
    try:
        success = await enhanced_memory_service.create_memory(
            user_id,
            memory.memory_id,
            memory.text,
            memory.memory_type,
            memory.priority,
            **memory.metadata
        )
        
        if success:
            return {"message": "Memory created successfully", "memory_id": memory.memory_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to create memory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create memory: {str(e)}")

@router.get("/users/{user_id}/memories")
async def get_memories(
    user_id: str,
    query: str = "",
    top_k: int = 10,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user memories."""
    try:
        memories = await enhanced_memory_service.get_memories(user_id, query, top_k)
        return {
            "user_id": user_id,
            "query": query,
            "memories": memories,
            "total": len(memories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get memories: {str(e)}")

@router.put("/users/{user_id}/memories/{memory_id}")
async def update_memory(
    user_id: str,
    memory_id: str,
    memory_update: MemoryUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update a memory."""
    try:
        success = await enhanced_memory_service.update_memory(
            user_id,
            memory_id,
            memory_update.text,
            **memory_update.metadata
        )
        
        if success:
            return {"message": "Memory updated successfully", "memory_id": memory_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to update memory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update memory: {str(e)}")

@router.delete("/users/{user_id}/memories/{memory_id}")
async def delete_memory(
    user_id: str,
    memory_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a memory."""
    try:
        success = await enhanced_memory_service.delete_memory(user_id, memory_id)
        
        if success:
            return {"message": "Memory deleted successfully", "memory_id": memory_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete memory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")

# =====================================================
# 🔹 Fact Management Endpoints
# =====================================================
@router.post("/users/{user_id}/facts")
async def create_fact(
    user_id: str,
    fact: FactCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a user fact."""
    try:
        success = await enhanced_memory_service.create_fact(
            user_id,
            fact.fact_text,
            fact.category
        )
        
        if success:
            return {"message": "Fact created successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create fact")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create fact: {str(e)}")

@router.get("/users/{user_id}/facts")
async def get_facts(
    user_id: str,
    query: str = "",
    top_k: int = 5,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user facts."""
    try:
        facts = await enhanced_memory_service.get_facts(user_id, query, top_k)
        return {
            "user_id": user_id,
            "query": query,
            "facts": facts,
            "total": len(facts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get facts: {str(e)}")

@router.delete("/users/{user_id}/facts")
async def delete_fact(
    user_id: str,
    fact_text: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete a user fact."""
    try:
        success = await enhanced_memory_service.delete_fact(user_id, fact_text)
        
        if success:
            return {"message": "Fact deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete fact")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete fact: {str(e)}")

# =====================================================
# 🔹 Session Management Endpoints
# =====================================================
@router.post("/users/{user_id}/sessions/{session_id}")
async def create_session(
    user_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Create a new session."""
    try:
        success = await enhanced_memory_service.create_session(user_id, session_id)
        
        if success:
            return {"message": "Session created successfully", "session_id": session_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to create session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

@router.get("/users/{user_id}/sessions/{session_id}")
async def get_session_memories(
    user_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Get session memories."""
    try:
        session_memories = await enhanced_memory_service.get_session_memories(user_id, session_id)
        return session_memories
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session memories: {str(e)}")

@router.post("/users/{user_id}/sessions/{session_id}/persist")
async def persist_session(
    user_id: str,
    session_id: str,
    session_data: SessionData,
    current_user: dict = Depends(get_current_active_user)
):
    """Persist session data."""
    try:
        success = await enhanced_memory_service.persist_session(
            user_id,
            session_id,
            session_data.dict()
        )
        
        if success:
            return {"message": "Session persisted successfully", "session_id": session_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to persist session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to persist session: {str(e)}")

# =====================================================
# 🔹 Global Recall Endpoints
# =====================================================
@router.post("/users/{user_id}/recall")
async def global_recall(
    user_id: str,
    recall_request: GlobalRecallRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Perform global recall across all memory systems."""
    try:
        recall_results = await enhanced_memory_service.global_recall(
            user_id,
            recall_request.query
        )
        return recall_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Global recall failed: {str(e)}")

@router.get("/users/{user_id}/search")
async def search_memories(
    user_id: str,
    query: str,
    top_k: int = 10,
    current_user: dict = Depends(get_current_active_user)
):
    """Search memories across all systems."""
    try:
        search_results = await enhanced_memory_service.search_memories(user_id, query, top_k)
        return search_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")

# =====================================================
# 🔹 Relationship Management Endpoints
# =====================================================
@router.get("/users/{user_id}/relationships")
async def get_relationships(
    user_id: str,
    relationship_type: Optional[str] = None,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user relationships from Neo4j."""
    try:
        relationships = await enhanced_memory_service.get_relationships(user_id, relationship_type)
        return {
            "user_id": user_id,
            "relationship_type": relationship_type,
            "relationships": relationships,
            "total": len(relationships)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get relationships: {str(e)}")

# =====================================================
# 🔹 Utility Endpoints
# =====================================================
@router.get("/users/{user_id}/network")
async def get_user_network(
    user_id: str,
    depth: int = 2,
    current_user: dict = Depends(get_current_active_user)
):
    """Get user's network from Neo4j."""
    try:
        network = await enhanced_memory_service.neo4j.get_user_network(user_id, depth)
        return network
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user network: {str(e)}")

@router.get("/concepts/search")
async def search_concepts(
    search_term: str,
    concept_type: str = "Concept",
    current_user: dict = Depends(get_current_active_user)
):
    """Search for concepts in Neo4j."""
    try:
        concepts = await enhanced_memory_service.neo4j.search_concepts(search_term, concept_type)
        return {
            "search_term": search_term,
            "concept_type": concept_type,
            "concepts": concepts,
            "total": len(concepts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search concepts: {str(e)}")
