"""
Database Inspector API
Web interface to view all data in Pinecone, Neo4j, and Redis
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service
from app.services import redis_service
from app.security import get_current_active_user

router = APIRouter(prefix="/api/inspector", tags=["Database Inspector"])

@router.get("/health")
async def get_system_health():
    """Get health status of all databases."""
    try:
        # Check Pinecone
        pinecone_ready = enhanced_pinecone_service.is_ready()
        pinecone_stats = enhanced_pinecone_service.get_index_stats() if pinecone_ready else None
        
        # Check Neo4j
        neo4j_ready = await enhanced_neo4j_service.ping()
        neo4j_info = await enhanced_neo4j_service.get_database_info() if neo4j_ready else None
        
        # Check Redis
        redis_client = redis_service.get_client()
        redis_ready = redis_client is not None
        redis_keys = len(await redis_client.keys("*")) if redis_ready else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "pinecone": {
                "ready": pinecone_ready,
                "stats": pinecone_stats
            },
            "neo4j": {
                "ready": neo4j_ready,
                "info": neo4j_info
            },
            "redis": {
                "ready": redis_ready,
                "key_count": redis_keys
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/pinecone")
async def inspect_pinecone(
    namespace: Optional[str] = None,
    top_k: int = 100,
    current_user: dict = Depends(get_current_active_user)
):
    """Inspect Pinecone data."""
    try:
        if not enhanced_pinecone_service.is_ready():
            raise HTTPException(status_code=503, detail="Pinecone not available")
        
        # Get index stats
        stats = enhanced_pinecone_service.get_index_stats()
        
        # Query vectors
        vectors = enhanced_pinecone_service.query_vectors(
            "inspection query",
            top_k=top_k,
            namespace=namespace
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "namespace": namespace,
            "stats": stats,
            "vectors": vectors,
            "total_vectors": len(vectors)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone inspection failed: {str(e)}")

@router.get("/neo4j")
async def inspect_neo4j(
    current_user: dict = Depends(get_current_active_user)
):
    """Inspect Neo4j data."""
    try:
        if not await enhanced_neo4j_service.ping():
            raise HTTPException(status_code=503, detail="Neo4j not available")
        
        # Get database info
        db_info = await enhanced_neo4j_service.get_database_info()
        
        # Get all nodes
        nodes_query = "MATCH (n) RETURN n, labels(n) as labels LIMIT 1000"
        nodes = await enhanced_neo4j_service.run_query(nodes_query)
        
        # Get all relationships
        rels_query = "MATCH ()-[r]->() RETURN r, type(r) as rel_type LIMIT 1000"
        relationships = await enhanced_neo4j_service.run_query(rels_query)
        
        # Get users
        users_query = "MATCH (u:User) RETURN u"
        users = await enhanced_neo4j_service.run_query(users_query)
        
        # Get concepts
        concepts_query = "MATCH (c:Concept) RETURN c"
        concepts = await enhanced_neo4j_service.run_query(concepts_query)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "database_info": db_info,
            "nodes": nodes,
            "relationships": relationships,
            "users": users,
            "concepts": concepts,
            "summary": {
                "total_nodes": len(nodes),
                "total_relationships": len(relationships),
                "total_users": len(users),
                "total_concepts": len(concepts)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j inspection failed: {str(e)}")

@router.get("/redis")
async def inspect_redis(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_active_user)
):
    """Inspect Redis data."""
    try:
        client = redis_service.get_client()
        if not client:
            raise HTTPException(status_code=503, detail="Redis not available")
        
        # Get all keys
        all_keys = await client.keys("*")
        
        # Categorize keys
        key_categories = {
            "sessions": [],
            "users": [],
            "facts": [],
            "profiles": [],
            "other": []
        }
        
        for key in all_keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            if key_str.startswith("sess:"):
                key_categories["sessions"].append(key_str)
            elif key_str.startswith("user:"):
                key_categories["users"].append(key_str)
            elif key_str.startswith("facts_cache:"):
                key_categories["facts"].append(key_str)
            elif key_str.startswith("session:state:"):
                key_categories["profiles"].append(key_str)
            else:
                key_categories["other"].append(key_str)
        
        # Get detailed data for requested category or all
        detailed_data = {}
        categories_to_inspect = [category] if category else key_categories.keys()
        
        for cat in categories_to_inspect:
            if cat in key_categories and key_categories[cat]:
                detailed_data[cat] = []
                
                for key in key_categories[cat][:20]:  # Limit to 20 keys per category
                    try:
                        key_type = await client.type(key)
                        key_data = {"key": key, "type": key_type}
                        
                        if key_type == "string":
                            value = await client.get(key)
                            key_data["value"] = value.decode('utf-8') if isinstance(value, bytes) else value
                        elif key_type == "list":
                            length = await client.llen(key)
                            items = await client.lrange(key, 0, 9)  # First 10 items
                            key_data["length"] = length
                            key_data["items"] = [item.decode('utf-8') if isinstance(item, bytes) else item for item in items]
                        elif key_type == "hash":
                            hash_data = await client.hgetall(key)
                            key_data["data"] = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in hash_data.items()}
                        
                        detailed_data[cat].append(key_data)
                    except Exception as e:
                        key_data = {"key": key, "error": str(e)}
                        detailed_data[cat].append(key_data)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_keys": len(all_keys),
            "key_categories": {k: len(v) for k, v in key_categories.items()},
            "detailed_data": detailed_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis inspection failed: {str(e)}")

@router.get("/all")
async def inspect_all_databases(
    current_user: dict = Depends(get_current_active_user)
):
    """Inspect all databases at once."""
    try:
        results = {}
        
        # Pinecone
        try:
            if enhanced_pinecone_service.is_ready():
                results["pinecone"] = {
                    "ready": True,
                    "stats": enhanced_pinecone_service.get_index_stats(),
                    "sample_vectors": enhanced_pinecone_service.query_vectors("inspection", top_k=10)
                }
            else:
                results["pinecone"] = {"ready": False, "error": "Not initialized"}
        except Exception as e:
            results["pinecone"] = {"ready": False, "error": str(e)}
        
        # Neo4j
        try:
            if await enhanced_neo4j_service.ping():
                db_info = await enhanced_neo4j_service.get_database_info()
                nodes = await enhanced_neo4j_service.run_query("MATCH (n) RETURN n, labels(n) as labels LIMIT 100")
                relationships = await enhanced_neo4j_service.run_query("MATCH ()-[r]->() RETURN r, type(r) as rel_type LIMIT 100")
                
                results["neo4j"] = {
                    "ready": True,
                    "database_info": db_info,
                    "sample_nodes": nodes,
                    "sample_relationships": relationships
                }
            else:
                results["neo4j"] = {"ready": False, "error": "Not connected"}
        except Exception as e:
            results["neo4j"] = {"ready": False, "error": str(e)}
        
        # Redis
        try:
            client = redis_service.get_client()
            if client:
                all_keys = await client.keys("*")
                key_categories = {
                    "sessions": len([k for k in all_keys if k.decode('utf-8').startswith("sess:")]),
                    "users": len([k for k in all_keys if k.decode('utf-8').startswith("user:")]),
                    "facts": len([k for k in all_keys if k.decode('utf-8').startswith("facts_cache:")]),
                    "other": len([k for k in all_keys if not k.decode('utf-8').startswith(("sess:", "user:", "facts_cache:"))])
                }
                
                results["redis"] = {
                    "ready": True,
                    "total_keys": len(all_keys),
                    "key_categories": key_categories
                }
            else:
                results["redis"] = {"ready": False, "error": "Client not available"}
        except Exception as e:
            results["redis"] = {"ready": False, "error": str(e)}
        
        return {
            "timestamp": datetime.now().isoformat(),
            "databases": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database inspection failed: {str(e)}")
