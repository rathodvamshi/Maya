"""
Enhanced Pinecone Service with comprehensive CRUD operations
Supports the new Pinecone configuration with 1536 dimensions and proper error handling
"""

import logging
from typing import Optional, Any, List, Dict, Tuple
from datetime import datetime
import hashlib
import json

from app.config import settings
from app.services.embedding_service import create_embedding

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Global Pinecone state
# =====================================================
pc: Optional[Any] = None
index = None
PINECONE_INDEX_NAME = settings.PINECONE_INDEX or "maya2-session-memory"
REQUIRED_DIMENSION = settings.PINECONE_DIMENSIONS or 1536

# =====================================================
# 🔹 Initialize Pinecone
# =====================================================
def initialize_pinecone():
    """
    Initializes the Pinecone client and index with the new configuration.
    """
    global pc, index
    if not settings.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Pinecone service will be disabled.")
        return

    try:
        from pinecone import Pinecone, ServerlessSpec
        pc_obj = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        logger.info("Initializing Pinecone using v3 client")
        create_new_index = False

        # Check if index exists and has correct dimensions
        existing = pc_obj.list_indexes()
        existing_names = existing.names() if hasattr(existing, "names") else [getattr(i, "name", None) for i in existing or []]
        
        if PINECONE_INDEX_NAME in existing_names:
            index_description = pc_obj.describe_index(PINECONE_INDEX_NAME)
            dim = getattr(index_description, "dimension", None) or (index_description.get("dimension") if isinstance(index_description, dict) else None)
            if dim != REQUIRED_DIMENSION:
                logger.warning(f"Index '{PINECONE_INDEX_NAME}' wrong dimension {dim}; recreating")
                pc_obj.delete_index(PINECONE_INDEX_NAME)
                create_new_index = True
        else:
            create_new_index = True
            
        if create_new_index:
            pc_obj.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=REQUIRED_DIMENSION,
                metric=settings.PINECONE_METRIC or "cosine",
                spec=ServerlessSpec(cloud=settings.PINECONE_CLOUD or "aws", region=settings.PINECONE_REGION or "us-east-1"),
            )
            
        bound_index = pc_obj.Index(PINECONE_INDEX_NAME)

        # Assign globals
        pc = pc_obj
        index = bound_index
        logger.info(f"✅ Pinecone index ready: '{PINECONE_INDEX_NAME}' (dimensions: {REQUIRED_DIMENSION})")
    except Exception as e:
        logger.error(f"❌ Error initializing Pinecone: {e}")
        pc = None
        index = None

# =====================================================
# 🔹 Internal Helper: Ensure Index Ready
# =====================================================
def _ensure_index_ready():
    """Internal helper to re-attempt initialization if the index is not ready."""
    if index is None:
        logger.warning("⚠️ Pinecone index was not initialized on startup, attempting again...")
        initialize_pinecone()
    return index is not None

# =====================================================
# 🔹 CRUD Operations - Create
# =====================================================
def create_vector(vector_id: str, text: str, metadata: Dict[str, Any], namespace: Optional[str] = None) -> bool:
    """Create a new vector in Pinecone."""
    if not _ensure_index_ready():
        logger.error("❌ Pinecone index unavailable. Cannot create vector.")
        return False
    
    try:
        embedding = create_embedding(text)
        if not embedding:
            logger.error("❌ Failed to create embedding for vector")
            return False
            
        vector_data = {
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
        }
        
        if namespace:
            index.upsert(vectors=[vector_data], namespace=namespace)
        else:
            index.upsert(vectors=[vector_data])
            
        logger.info(f"✅ Created vector: {vector_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create vector {vector_id}: {e}")
        return False

def create_user_memory(user_id: str, memory_id: str, text: str, metadata: Dict[str, Any]) -> bool:
    """Create a user memory vector."""
    namespace = f"user:{user_id}"
    vector_id = f"memory:{memory_id}"
    
    memory_metadata = {
        "user_id": user_id,
        "memory_id": memory_id,
        "text": text,
        "kind": "memory",
        "created_at": datetime.utcnow().isoformat(),
        **metadata
    }
    
    return create_vector(vector_id, text, memory_metadata, namespace)

def create_user_fact(user_id: str, fact_text: str, category: str = "generic") -> bool:
    """Create a user fact vector."""
    namespace = f"user:{user_id}"
    fact_hash = hashlib.sha1(fact_text.encode("utf-8")).hexdigest()[:12]
    vector_id = f"fact:{fact_hash}"
    
    fact_metadata = {
        "user_id": user_id,
        "text": fact_text,
        "kind": "fact",
        "category": category,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return create_vector(vector_id, fact_text, fact_metadata, namespace)

# =====================================================
# 🔹 CRUD Operations - Read
# =====================================================
def read_vector(vector_id: str, namespace: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Read a specific vector by ID."""
    if not _ensure_index_ready():
        return None
    
    try:
        if namespace:
            result = index.fetch(ids=[vector_id], namespace=namespace)
        else:
            result = index.fetch(ids=[vector_id])
            
        vectors = result.get("vectors", {})
        if vector_id in vectors:
            return vectors[vector_id]
        return None
    except Exception as e:
        logger.error(f"❌ Failed to read vector {vector_id}: {e}")
        return None

def query_vectors(query_text: str, top_k: int = 10, namespace: Optional[str] = None, 
                 filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Query vectors by similarity."""
    if not _ensure_index_ready():
        return []
    
    try:
        embedding = create_embedding(query_text)
        if not embedding:
            return []
            
        query_params = {
            "vector": embedding,
            "top_k": top_k,
            "include_metadata": True
        }
        
        if filter_dict:
            query_params["filter"] = filter_dict
            
        if namespace:
            result = index.query(namespace=namespace, **query_params)
        else:
            result = index.query(**query_params)
            
        matches = result.get("matches", [])
        return [
            {
                "id": match.get("id"),
                "score": match.get("score"),
                "metadata": match.get("metadata", {})
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f"❌ Failed to query vectors: {e}")
        return []

def get_user_memories(user_id: str, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Get user memories by query."""
    namespace = f"user:{user_id}"
    filter_dict = {
        "user_id": {"$eq": user_id},
        "kind": {"$eq": "memory"}
    }
    return query_vectors(query_text, top_k, namespace, filter_dict)

def get_user_facts(user_id: str, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Get user facts by query."""
    namespace = f"user:{user_id}"
    filter_dict = {
        "user_id": {"$eq": user_id},
        "kind": {"$eq": "fact"}
    }
    return query_vectors(query_text, top_k, namespace, filter_dict)

# =====================================================
# 🔹 CRUD Operations - Update
# =====================================================
def update_vector(vector_id: str, text: str, metadata: Dict[str, Any], namespace: Optional[str] = None) -> bool:
    """Update an existing vector."""
    if not _ensure_index_ready():
        return False
    
    try:
        embedding = create_embedding(text)
        if not embedding:
            return False
            
        vector_data = {
            "id": vector_id,
            "values": embedding,
            "metadata": {**metadata, "updated_at": datetime.utcnow().isoformat()}
        }
        
        if namespace:
            index.upsert(vectors=[vector_data], namespace=namespace)
        else:
            index.upsert(vectors=[vector_data])
            
        logger.info(f"✅ Updated vector: {vector_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to update vector {vector_id}: {e}")
        return False

def update_user_memory(user_id: str, memory_id: str, text: str, metadata: Dict[str, Any]) -> bool:
    """Update a user memory vector."""
    namespace = f"user:{user_id}"
    vector_id = f"memory:{memory_id}"
    
    memory_metadata = {
        "user_id": user_id,
        "memory_id": memory_id,
        "text": text,
        "kind": "memory",
        "updated_at": datetime.utcnow().isoformat(),
        **metadata
    }
    
    return update_vector(vector_id, text, memory_metadata, namespace)

# =====================================================
# 🔹 CRUD Operations - Delete
# =====================================================
def delete_vector(vector_id: str, namespace: Optional[str] = None) -> bool:
    """Delete a specific vector."""
    if not _ensure_index_ready():
        return False
    
    try:
        if namespace:
            index.delete(ids=[vector_id], namespace=namespace)
        else:
            index.delete(ids=[vector_id])
            
        logger.info(f"✅ Deleted vector: {vector_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete vector {vector_id}: {e}")
        return False

def delete_user_memory(user_id: str, memory_id: str) -> bool:
    """Delete a user memory vector."""
    namespace = f"user:{user_id}"
    vector_id = f"memory:{memory_id}"
    return delete_vector(vector_id, namespace)

def delete_user_fact(user_id: str, fact_text: str) -> bool:
    """Delete a user fact vector."""
    namespace = f"user:{user_id}"
    fact_hash = hashlib.sha1(fact_text.encode("utf-8")).hexdigest()[:12]
    vector_id = f"fact:{fact_hash}"
    return delete_vector(vector_id, namespace)

def delete_user_namespace(user_id: str) -> bool:
    """Delete all vectors in a user's namespace."""
    if not _ensure_index_ready():
        return False
    
    try:
        namespace = f"user:{user_id}"
        index.delete(delete_all=True, namespace=namespace)
        logger.info(f"✅ Deleted namespace: {namespace}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete namespace {namespace}: {e}")
        return False

# =====================================================
# 🔹 Batch Operations
# =====================================================
def batch_upsert(vectors: List[Dict[str, Any]], namespace: Optional[str] = None) -> bool:
    """Batch upsert multiple vectors."""
    if not _ensure_index_ready():
        return False
    
    try:
        if namespace:
            index.upsert(vectors=vectors, namespace=namespace)
        else:
            index.upsert(vectors=vectors)
            
        logger.info(f"✅ Batch upserted {len(vectors)} vectors")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to batch upsert: {e}")
        return False

def batch_delete(vector_ids: List[str], namespace: Optional[str] = None) -> bool:
    """Batch delete multiple vectors."""
    if not _ensure_index_ready():
        return False
    
    try:
        if namespace:
            index.delete(ids=vector_ids, namespace=namespace)
        else:
            index.delete(ids=vector_ids)
            
        logger.info(f"✅ Batch deleted {len(vector_ids)} vectors")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to batch delete: {e}")
        return False

# =====================================================
# 🔹 Utility Functions
# =====================================================
def get_index_stats() -> Optional[Dict[str, Any]]:
    """Get index statistics."""
    if not _ensure_index_ready():
        return None
    
    try:
        stats = index.describe_index_stats()
        return stats
    except Exception as e:
        logger.error(f"❌ Failed to get index stats: {e}")
        return None

def is_ready() -> bool:
    """Check if Pinecone service is ready."""
    return index is not None

def get_index():
    """Get the Pinecone index object."""
    return index

# =====================================================
# 🔹 Legacy Compatibility
# =====================================================
def upsert_session_summary(session_id: str, summary: str):
    """Legacy function for session summaries."""
    metadata = {
        "session_id": session_id,
        "kind": "session_summary",
        "created_at": datetime.utcnow().isoformat()
    }
    create_vector(session_id, summary, metadata)

def query_relevant_summary(text: str, top_k: int = 1) -> str | None:
    """Legacy function for querying summaries."""
    results = query_vectors(text, top_k)
    if results and results[0]["score"] > 0.75:
        return results[0]["metadata"].get("text")
    return None

# =====================================================
# 🔹 Service Class for Compatibility
# =====================================================
class EnhancedPineconeService:
    """Enhanced Pinecone service with comprehensive CRUD operations."""
    
    def __init__(self):
        self.initialize = initialize_pinecone
        self.is_ready = is_ready
        self.get_index = get_index
        
        # CRUD operations
        self.create_vector = create_vector
        self.read_vector = read_vector
        self.update_vector = update_vector
        self.delete_vector = delete_vector
        
        # User-specific operations
        self.create_user_memory = create_user_memory
        self.create_user_fact = create_user_fact
        self.get_user_memories = get_user_memories
        self.get_user_facts = get_user_facts
        self.update_user_memory = update_user_memory
        self.delete_user_memory = delete_user_memory
        self.delete_user_fact = delete_user_fact
        self.delete_user_namespace = delete_user_namespace
        
        # Batch operations
        self.batch_upsert = batch_upsert
        self.batch_delete = batch_delete
        
        # Utility functions
        self.get_index_stats = get_index_stats
        self.query_vectors = query_vectors
        
        # Legacy compatibility
        self.upsert_session_summary = upsert_session_summary
        self.query_relevant_summary = query_relevant_summary

# Create service instance
enhanced_pinecone_service = EnhancedPineconeService()
