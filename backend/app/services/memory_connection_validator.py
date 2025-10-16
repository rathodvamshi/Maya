# backend/app/services/memory_connection_validator.py

"""
Comprehensive memory connection validation service.
Validates Pinecone, Neo4j, and Redis connections with health checks and performance metrics.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.services import pinecone_service, neo4j_service, redis_service
from app.services.embedding_service import create_embedding
from app.config import settings

logger = logging.getLogger(__name__)


class MemoryConnectionValidator:
    """
    Validates and monitors memory system connections (Pinecone, Neo4j, Redis).
    Provides health checks, performance metrics, and connection status.
    """
    
    def __init__(self):
        self.last_validation = None
        self.validation_results = {}
        self.performance_metrics = {}
    
    async def validate_all_connections(self) -> Dict[str, Any]:
        """
        Validate all memory system connections and return comprehensive status.
        
        Returns:
            Dict containing connection status, performance metrics, and health scores
        """
        start_time = time.time()
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "unknown",
            "connections": {},
            "performance": {},
            "recommendations": []
        }
        
        try:
            # Validate Pinecone connection
            pinecone_result = await self._validate_pinecone()
            results["connections"]["pinecone"] = pinecone_result
            
            # Validate Neo4j connection
            neo4j_result = await self._validate_neo4j()
            results["connections"]["neo4j"] = neo4j_result
            
            # Validate Redis connection
            redis_result = await self._validate_redis()
            results["connections"]["redis"] = redis_result
            
            # Calculate overall health
            health_scores = [conn.get("health_score", 0) for conn in results["connections"].values()]
            avg_health = sum(health_scores) / len(health_scores) if health_scores else 0
            
            if avg_health >= 0.9:
                results["overall_health"] = "excellent"
            elif avg_health >= 0.7:
                results["overall_health"] = "good"
            elif avg_health >= 0.5:
                results["overall_health"] = "fair"
            else:
                results["overall_health"] = "poor"
            
            # Generate recommendations
            results["recommendations"] = self._generate_recommendations(results["connections"])
            
            # Store performance metrics
            results["performance"] = {
                "validation_duration_ms": int((time.time() - start_time) * 1000),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.last_validation = results
            self.validation_results = results
            
            logger.info(f"Memory validation completed: {results['overall_health']} health")
            
        except Exception as e:
            logger.error(f"Memory validation failed: {e}")
            results["overall_health"] = "error"
            results["error"] = str(e)
        
        return results
    
    async def _validate_pinecone(self) -> Dict[str, Any]:
        """Validate Pinecone connection and performance."""
        result = {
            "status": "unknown",
            "health_score": 0.0,
            "details": {},
            "performance": {}
        }
        
        try:
            start_time = time.time()
            
            # Check if Pinecone is initialized
            if not pinecone_service.is_ready():
                result["status"] = "not_initialized"
                result["health_score"] = 0.0
                result["details"]["error"] = "Pinecone service not initialized"
                return result
            
            # Test embedding creation
            test_text = "Test embedding for connection validation"
            embedding_start = time.time()
            embedding = create_embedding(test_text)
            embedding_time = time.time() - embedding_start
            
            if not embedding or len(embedding) != settings.PINECONE_DIMENSIONS:
                result["status"] = "embedding_failed"
                result["health_score"] = 0.3
                result["details"]["error"] = f"Embedding creation failed or wrong dimensions: {len(embedding) if embedding else 0}"
                return result
            
            # Test Pinecone upsert
            test_id = f"validation_test_{int(time.time())}"
            upsert_start = time.time()
            
            try:
                index = pinecone_service.get_index()
                if index:
                    index.upsert(vectors=[(test_id, embedding, {"test": True, "timestamp": datetime.utcnow().isoformat()})])
                    upsert_time = time.time() - upsert_start
                    
                    # Test query
                    query_start = time.time()
                    query_result = index.query(vector=embedding, top_k=1, include_metadata=True)
                    query_time = time.time() - query_start
                    
                    # Clean up test vector
                    try:
                        index.delete(ids=[test_id])
                    except Exception:
                        pass
                    
                    result["status"] = "healthy"
                    result["health_score"] = 0.9
                    result["details"] = {
                        "dimensions": len(embedding),
                        "index_ready": True,
                        "upsert_successful": True,
                        "query_successful": True
                    }
                    result["performance"] = {
                        "embedding_time_ms": int(embedding_time * 1000),
                        "upsert_time_ms": int(upsert_time * 1000),
                        "query_time_ms": int(query_time * 1000)
                    }
                else:
                    result["status"] = "index_unavailable"
                    result["health_score"] = 0.5
                    result["details"]["error"] = "Pinecone index not available"
            except Exception as e:
                result["status"] = "operation_failed"
                result["health_score"] = 0.3
                result["details"]["error"] = str(e)
            
        except Exception as e:
            result["status"] = "connection_failed"
            result["health_score"] = 0.0
            result["details"]["error"] = str(e)
        
        return result
    
    async def _validate_neo4j(self) -> Dict[str, Any]:
        """Validate Neo4j connection and performance."""
        result = {
            "status": "unknown",
            "health_score": 0.0,
            "details": {},
            "performance": {}
        }
        
        try:
            start_time = time.time()
            
            # Test connection
            ping_start = time.time()
            is_connected = await neo4j_service.ping()
            ping_time = time.time() - ping_start
            
            if not is_connected:
                result["status"] = "connection_failed"
                result["health_score"] = 0.0
                result["details"]["error"] = "Neo4j ping failed"
                return result
            
            # Test basic query
            query_start = time.time()
            test_query = "RETURN 1 as test"
            query_result = await neo4j_service.run_query(test_query)
            query_time = time.time() - query_start
            
            if query_result is None:
                result["status"] = "query_failed"
                result["health_score"] = 0.5
                result["details"]["error"] = "Neo4j query returned None"
                return result
            
            # Test node creation and deletion
            create_start = time.time()
            test_node_id = f"validation_test_{int(time.time())}"
            create_query = f"CREATE (n:TestNode {{id: '{test_node_id}', created_at: datetime()}}) RETURN n"
            create_result = await neo4j_service.run_query(create_query)
            create_time = time.time() - create_start
            
            if create_result:
                # Clean up test node
                cleanup_query = f"MATCH (n:TestNode {{id: '{test_node_id}'}}) DELETE n"
                await neo4j_service.run_query(cleanup_query)
            
            result["status"] = "healthy"
            result["health_score"] = 0.9
            result["details"] = {
                "connection_verified": True,
                "query_successful": True,
                "node_operations": create_result is not None
            }
            result["performance"] = {
                "ping_time_ms": int(ping_time * 1000),
                "query_time_ms": int(query_time * 1000),
                "create_time_ms": int(create_time * 1000)
            }
            
        except Exception as e:
            result["status"] = "connection_failed"
            result["health_score"] = 0.0
            result["details"]["error"] = str(e)
        
        return result
    
    async def _validate_redis(self) -> Dict[str, Any]:
        """Validate Redis connection and performance."""
        result = {
            "status": "unknown",
            "health_score": 0.0,
            "details": {},
            "performance": {}
        }
        
        try:
            start_time = time.time()
            
            # Test ping
            ping_start = time.time()
            is_connected = await redis_service.ping()
            ping_time = time.time() - ping_start
            
            if not is_connected:
                result["status"] = "connection_failed"
                result["health_score"] = 0.0
                result["details"]["error"] = "Redis ping failed"
                return result
            
            # Test basic operations
            client = redis_service.get_client()
            if not client:
                result["status"] = "client_unavailable"
                result["health_score"] = 0.0
                result["details"]["error"] = "Redis client not available"
                return result
            
            # Test set/get operations
            test_key = f"validation_test_{int(time.time())}"
            test_value = "test_value"
            
            set_start = time.time()
            await client.set(test_key, test_value, ex=60)  # 60 second expiry
            set_time = time.time() - set_start
            
            get_start = time.time()
            retrieved_value = await client.get(test_key)
            get_time = time.time() - get_start
            
            # Clean up
            await client.delete(test_key)
            
            if retrieved_value != test_value:
                result["status"] = "operation_failed"
                result["health_score"] = 0.5
                result["details"]["error"] = "Redis set/get operation failed"
                return result
            
            result["status"] = "healthy"
            result["health_score"] = 0.9
            result["details"] = {
                "connection_verified": True,
                "set_operation": True,
                "get_operation": True,
                "delete_operation": True
            }
            result["performance"] = {
                "ping_time_ms": int(ping_time * 1000),
                "set_time_ms": int(set_time * 1000),
                "get_time_ms": int(get_time * 1000)
            }
            
        except Exception as e:
            result["status"] = "connection_failed"
            result["health_score"] = 0.0
            result["details"]["error"] = str(e)
        
        return result
    
    def _generate_recommendations(self, connections: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on connection status."""
        recommendations = []
        
        for service, status in connections.items():
            if status.get("health_score", 0) < 0.7:
                if service == "pinecone":
                    recommendations.append("Pinecone connection issues detected. Check API key and index configuration.")
                elif service == "neo4j":
                    recommendations.append("Neo4j connection issues detected. Verify URI and credentials.")
                elif service == "redis":
                    recommendations.append("Redis connection issues detected. Check Redis server status and configuration.")
        
        if not recommendations:
            recommendations.append("All memory systems are healthy and operational.")
        
        return recommendations
    
    async def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status without full validation."""
        if not self.last_validation:
            return {"status": "not_validated", "message": "No validation performed yet"}
        
        return {
            "last_validation": self.last_validation.get("timestamp"),
            "overall_health": self.last_validation.get("overall_health"),
            "connections": {
                service: {
                    "status": conn.get("status"),
                    "health_score": conn.get("health_score", 0)
                }
                for service, conn in self.last_validation.get("connections", {}).items()
            }
        }
    
    async def test_embedding_pipeline(self) -> Dict[str, Any]:
        """Test the complete embedding pipeline from text to Pinecone storage."""
        result = {
            "success": False,
            "steps": {},
            "performance": {},
            "error": None
        }
        
        try:
            start_time = time.time()
            
            # Step 1: Create embedding
            test_text = "Memory connection validation test"
            embedding_start = time.time()
            embedding = create_embedding(test_text)
            embedding_time = time.time() - embedding_start
            
            if not embedding:
                result["error"] = "Failed to create embedding"
                return result
            
            result["steps"]["embedding_creation"] = True
            
            # Step 2: Store in Pinecone
            if pinecone_service.is_ready():
                test_id = f"pipeline_test_{int(time.time())}"
                upsert_start = time.time()
                
                try:
                    index = pinecone_service.get_index()
                    index.upsert(vectors=[(test_id, embedding, {"test": True})])
                    upsert_time = time.time() - upsert_start
                    result["steps"]["pinecone_upsert"] = True
                    
                    # Step 3: Query from Pinecone
                    query_start = time.time()
                    query_result = index.query(vector=embedding, top_k=1)
                    query_time = time.time() - query_start
                    result["steps"]["pinecone_query"] = True
                    
                    # Clean up
                    index.delete(ids=[test_id])
                    
                    result["performance"] = {
                        "embedding_time_ms": int(embedding_time * 1000),
                        "upsert_time_ms": int(upsert_time * 1000),
                        "query_time_ms": int(query_time * 1000),
                        "total_time_ms": int((time.time() - start_time) * 1000)
                    }
                    result["success"] = True
                    
                except Exception as e:
                    result["error"] = f"Pinecone operation failed: {e}"
            else:
                result["error"] = "Pinecone not available"
                
        except Exception as e:
            result["error"] = f"Pipeline test failed: {e}"
        
        return result


# Global validator instance
memory_validator = MemoryConnectionValidator()


async def validate_memory_connections() -> Dict[str, Any]:
    """
    Convenience function to validate all memory connections.
    Returns comprehensive validation results.
    """
    return await memory_validator.validate_all_connections()


async def get_memory_health_status() -> Dict[str, Any]:
    """
    Get current memory system health status.
    Returns quick status without full validation.
    """
    return await memory_validator.get_connection_status()


async def test_embedding_pipeline() -> Dict[str, Any]:
    """
    Test the complete embedding pipeline.
    Returns detailed test results.
    """
    return await memory_validator.test_embedding_pipeline()
