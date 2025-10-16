# backend/app/routers/memory_health.py

"""
Memory system health check endpoints.
Provides comprehensive validation of Pinecone, Neo4j, and Redis connections.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
import logging

from app.services.memory_connection_validator import (
    validate_memory_connections,
    get_memory_health_status,
    test_embedding_pipeline
)
from app.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/memory",
    tags=["Memory Health"]
)


@router.get("/health")
async def memory_health_check():
    """
    Get current memory system health status without full validation.
    Returns quick status check for all memory systems.
    """
    try:
        status = await get_memory_health_status()
        return {
            "status": "success",
            "data": status
        }
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/full")
async def full_memory_validation():
    """
    Perform comprehensive memory system validation.
    Tests all connections, performance, and functionality.
    """
    try:
        results = await validate_memory_connections()
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"Full memory validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/health/embedding-pipeline")
async def test_embedding_pipeline_health():
    """
    Test the complete embedding pipeline from text to Pinecone storage.
    Validates embedding creation, storage, and retrieval.
    """
    try:
        results = await test_embedding_pipeline()
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logger.error(f"Embedding pipeline test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline test failed: {str(e)}")


@router.get("/health/pinecone")
async def pinecone_health_check():
    """
    Specific health check for Pinecone connection and functionality.
    """
    try:
        from app.services import pinecone_service
        from app.services.embedding_service import create_embedding
        from app.config import settings
        
        if not pinecone_service.is_ready():
            return {
                "status": "error",
                "message": "Pinecone service not initialized",
                "healthy": False
            }
        
        # Test embedding creation
        test_text = "Pinecone health check test"
        embedding = create_embedding(test_text)
        
        if not embedding or len(embedding) != settings.PINECONE_DIMENSIONS:
            return {
                "status": "error",
                "message": f"Embedding creation failed or wrong dimensions: {len(embedding) if embedding else 0}",
                "healthy": False
            }
        
        # Test Pinecone operations
        index = pinecone_service.get_index()
        if not index:
            return {
                "status": "error",
                "message": "Pinecone index not available",
                "healthy": False
            }
        
        return {
            "status": "success",
            "message": "Pinecone is healthy and operational",
            "healthy": True,
            "dimensions": len(embedding),
            "index_ready": True
        }
        
    except Exception as e:
        logger.error(f"Pinecone health check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "healthy": False
        }


@router.get("/health/neo4j")
async def neo4j_health_check():
    """
    Specific health check for Neo4j connection and functionality.
    """
    try:
        from app.services.neo4j_service import neo4j_service
        
        # Test connection
        is_connected = await neo4j_service.ping()
        if not is_connected:
            return {
                "status": "error",
                "message": "Neo4j connection failed",
                "healthy": False
            }
        
        # Test basic query
        test_query = "RETURN 1 as test"
        result = await neo4j_service.run_query(test_query)
        
        if result is None:
            return {
                "status": "error",
                "message": "Neo4j query failed",
                "healthy": False
            }
        
        return {
            "status": "success",
            "message": "Neo4j is healthy and operational",
            "healthy": True,
            "query_successful": True
        }
        
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "healthy": False
        }


@router.get("/health/redis")
async def redis_health_check():
    """
    Specific health check for Redis connection and functionality.
    """
    try:
        from app.services.redis_service import redis_service
        
        # Test ping
        is_connected = await redis_service.ping()
        if not is_connected:
            return {
                "status": "error",
                "message": "Redis connection failed",
                "healthy": False
            }
        
        # Test basic operations
        client = redis_service.get_client()
        if not client:
            return {
                "status": "error",
                "message": "Redis client not available",
                "healthy": False
            }
        
        # Test set/get operations
        test_key = f"health_check_{int(__import__('time').time())}"
        test_value = "health_check_value"
        
        await client.set(test_key, test_value, ex=60)
        retrieved_value = await client.get(test_key)
        await client.delete(test_key)
        
        if retrieved_value != test_value:
            return {
                "status": "error",
                "message": "Redis set/get operations failed",
                "healthy": False
            }
        
        return {
            "status": "success",
            "message": "Redis is healthy and operational",
            "healthy": True,
            "operations_tested": ["set", "get", "delete"]
        }
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "healthy": False
        }


@router.get("/health/summary")
async def memory_health_summary():
    """
    Get a summary of all memory system health checks.
    Returns quick status for all systems.
    """
    try:
        import asyncio
        
        # Run all health checks in parallel
        tasks = [
            pinecone_health_check(),
            neo4j_health_check(),
            redis_health_check()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        summary = {
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
            "systems": {
                "pinecone": results[0] if not isinstance(results[0], Exception) else {"status": "error", "message": str(results[0])},
                "neo4j": results[1] if not isinstance(results[1], Exception) else {"status": "error", "message": str(results[1])},
                "redis": results[2] if not isinstance(results[2], Exception) else {"status": "error", "message": str(results[2])}
            }
        }
        
        # Calculate overall health
        healthy_count = sum(1 for result in results if not isinstance(result, Exception) and result.get("healthy", False))
        total_systems = len(results)
        
        if healthy_count == total_systems:
            summary["overall_health"] = "excellent"
        elif healthy_count >= total_systems * 0.7:
            summary["overall_health"] = "good"
        elif healthy_count >= total_systems * 0.5:
            summary["overall_health"] = "fair"
        else:
            summary["overall_health"] = "poor"
        
        summary["healthy_systems"] = healthy_count
        summary["total_systems"] = total_systems
        
        return {
            "status": "success",
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Memory health summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health summary failed: {str(e)}")


@router.post("/health/validate")
async def validate_memory_systems():
    """
    Trigger comprehensive validation of all memory systems.
    This is a more intensive check that tests full functionality.
    """
    try:
        results = await validate_memory_connections()
        return {
            "status": "success",
            "message": "Memory systems validation completed",
            "data": results
        }
    except Exception as e:
        logger.error(f"Memory systems validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
