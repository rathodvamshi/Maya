"""
Data Management API
Ensures proper storage and recall of user data
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.enhanced_storage_service import enhanced_storage_service
from app.security import get_current_active_user

router = APIRouter(prefix="/api/data", tags=["Data Management"])

# =====================================================
# 🔹 Pydantic Models
# =====================================================
class UserCreate(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
    timezone: str = "UTC"
    metadata: Optional[Dict[str, Any]] = {}

class MemoryCreate(BaseModel):
    memory_id: str
    text: str
    memory_type: str = "fact"
    priority: str = "normal"
    category: str = "general"
    metadata: Optional[Dict[str, Any]] = {}

class FactCreate(BaseModel):
    fact_text: str
    category: str = "generic"

class SessionCreate(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]

class RecallRequest(BaseModel):
    query: str = ""
    include_memories: bool = True
    include_facts: bool = True
    include_relationships: bool = True
    include_sessions: bool = True

# =====================================================
# 🔹 User Management
# =====================================================
@router.post("/users/{user_id}/ensure")
async def ensure_user_exists(
    user_id: str,
    user_data: UserCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Ensure user exists in all systems."""
    try:
        success = await enhanced_storage_service.ensure_user_exists(
            user_id,
            user_data.dict()
        )
        
        if success:
            return {
                "message": "User ensured in all systems",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to ensure user exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ensure user: {str(e)}")

@router.get("/users/{user_id}/exists")
async def check_user_exists(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Check if user exists in all systems."""
    try:
        # Check Neo4j
        neo4j_user = await enhanced_storage_service.neo4j.get_user(user_id)
        neo4j_exists = neo4j_user is not None
        
        # Check Redis
        from app.services import redis_service
        client = redis_service.get_client()
        redis_exists = False
        if client:
            profile_key = f"user:{user_id}:profile"
            redis_exists = await client.exists(profile_key)
        
        # Check Pinecone (by querying for user data)
        pinecone_exists = False
        if enhanced_storage_service.pinecone.is_ready():
            memories = enhanced_storage_service.pinecone.get_user_memories(user_id, "", top_k=1)
            pinecone_exists = len(memories) > 0
        
        return {
            "user_id": user_id,
            "exists_in": {
                "neo4j": neo4j_exists,
                "redis": redis_exists,
                "pinecone": pinecone_exists
            },
            "exists_in_all": neo4j_exists and redis_exists and pinecone_exists
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check user existence: {str(e)}")

# =====================================================
# 🔹 Memory Management
# =====================================================
@router.post("/users/{user_id}/memories/guaranteed")
async def store_memory_guaranteed(
    user_id: str,
    memory: MemoryCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Store memory with guarantee across all systems."""
    try:
        success = await enhanced_storage_service.store_memory_with_guarantee(
            user_id,
            memory.dict()
        )
        
        if success:
            return {
                "message": "Memory stored with guarantee",
                "user_id": user_id,
                "memory_id": memory.memory_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store memory with guarantee")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")

@router.post("/users/{user_id}/facts/guaranteed")
async def store_fact_guaranteed(
    user_id: str,
    fact: FactCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Store fact with guarantee across all systems."""
    try:
        success = await enhanced_storage_service.store_fact_with_guarantee(
            user_id,
            fact.fact_text,
            fact.category
        )
        
        if success:
            return {
                "message": "Fact stored with guarantee",
                "user_id": user_id,
                "fact_text": fact.fact_text,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store fact with guarantee")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store fact: {str(e)}")

@router.post("/users/{user_id}/sessions/guaranteed")
async def store_session_guaranteed(
    user_id: str,
    session: SessionCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Store session with guarantee across all systems."""
    try:
        success = await enhanced_storage_service.store_session_with_guarantee(
            user_id,
            session.session_id,
            session.messages
        )
        
        if success:
            return {
                "message": "Session stored with guarantee",
                "user_id": user_id,
                "session_id": session.session_id,
                "message_count": len(session.messages),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to store session with guarantee")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store session: {str(e)}")

# =====================================================
# 🔹 Data Recall
# =====================================================
@router.post("/users/{user_id}/recall/guaranteed")
async def recall_user_data_guaranteed(
    user_id: str,
    recall_request: RecallRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """Recall all user data with guarantee."""
    try:
        # Ensure user exists first
        await enhanced_storage_service.ensure_data_persistence(user_id)
        
        # Recall data
        data = await enhanced_storage_service.recall_user_data(
            user_id,
            recall_request.query
        )
        
        return {
            "user_id": user_id,
            "query": recall_request.query,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recall user data: {str(e)}")

@router.get("/users/{user_id}/recall/simple")
async def recall_user_data_simple(
    user_id: str,
    query: str = "",
    current_user: dict = Depends(get_current_active_user)
):
    """Simple recall of user data."""
    try:
        data = await enhanced_storage_service.recall_user_data(user_id, query)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recall user data: {str(e)}")

# =====================================================
# 🔹 Data Persistence
# =====================================================
@router.post("/users/{user_id}/persist")
async def ensure_data_persistence(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Ensure all user data is properly persisted."""
    try:
        success = await enhanced_storage_service.ensure_data_persistence(user_id)
        
        if success:
            return {
                "message": "Data persistence ensured",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to ensure data persistence")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ensure data persistence: {str(e)}")

# =====================================================
# 🔹 Storage Statistics
# =====================================================
@router.get("/storage/stats")
async def get_storage_stats(
    current_user: dict = Depends(get_current_active_user)
):
    """Get comprehensive storage statistics."""
    try:
        stats = await enhanced_storage_service.get_storage_stats()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "storage_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get storage stats: {str(e)}")

# =====================================================
# 🔹 Bulk Operations
# =====================================================
@router.post("/users/{user_id}/bulk-store")
async def bulk_store_user_data(
    user_id: str,
    data: Dict[str, Any],
    current_user: dict = Depends(get_current_active_user)
):
    """Bulk store user data across all systems."""
    try:
        results = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "results": {}
        }
        
        # Ensure user exists
        user_data = data.get("user", {})
        if user_data:
            results["results"]["user"] = await enhanced_storage_service.ensure_user_exists(user_id, user_data)
        
        # Store memories
        memories = data.get("memories", [])
        memory_results = []
        for memory in memories:
            success = await enhanced_storage_service.store_memory_with_guarantee(user_id, memory)
            memory_results.append({"memory_id": memory.get("memory_id"), "success": success})
        results["results"]["memories"] = memory_results
        
        # Store facts
        facts = data.get("facts", [])
        fact_results = []
        for fact in facts:
            success = await enhanced_storage_service.store_fact_with_guarantee(
                user_id, 
                fact.get("fact_text", ""), 
                fact.get("category", "generic")
            )
            fact_results.append({"fact_text": fact.get("fact_text"), "success": success})
        results["results"]["facts"] = fact_results
        
        # Store sessions
        sessions = data.get("sessions", [])
        session_results = []
        for session in sessions:
            success = await enhanced_storage_service.store_session_with_guarantee(
                user_id,
                session.get("session_id", ""),
                session.get("messages", [])
            )
            session_results.append({"session_id": session.get("session_id"), "success": success})
        results["results"]["sessions"] = session_results
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk store data: {str(e)}")

# =====================================================
# 🔹 Data Verification
# =====================================================
@router.get("/users/{user_id}/verify")
async def verify_user_data(
    user_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """Verify user data exists in all systems."""
    try:
        # Check each system
        verification = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "systems": {}
        }
        
        # Check Neo4j
        neo4j_user = await enhanced_storage_service.neo4j.get_user(user_id)
        verification["systems"]["neo4j"] = {
            "exists": neo4j_user is not None,
            "data": neo4j_user
        }
        
        # Check Redis
        from app.services import redis_service
        client = redis_service.get_client()
        if client:
            profile_key = f"user:{user_id}:profile"
            profile_exists = await client.exists(profile_key)
            profile_data = None
            if profile_exists:
                profile_data = await client.get(profile_key)
                if profile_data:
                    import json
                    profile_data = json.loads(profile_data.decode('utf-8'))
            
            verification["systems"]["redis"] = {
                "exists": profile_exists,
                "data": profile_data
            }
        else:
            verification["systems"]["redis"] = {"exists": False, "error": "Redis not available"}
        
        # Check Pinecone
        if enhanced_storage_service.pinecone.is_ready():
            memories = enhanced_storage_service.pinecone.get_user_memories(user_id, "", top_k=5)
            facts = enhanced_storage_service.pinecone.get_user_facts(user_id, "", top_k=5)
            
            verification["systems"]["pinecone"] = {
                "exists": len(memories) > 0 or len(facts) > 0,
                "memories_count": len(memories),
                "facts_count": len(facts),
                "sample_memories": memories[:3],
                "sample_facts": facts[:3]
            }
        else:
            verification["systems"]["pinecone"] = {"exists": False, "error": "Pinecone not available"}
        
        return verification
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify user data: {str(e)}")
