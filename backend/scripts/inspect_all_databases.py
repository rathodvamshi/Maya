"""
Comprehensive Database Inspector
View all data in Pinecone, Neo4j, and Redis
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service
from app.services import memory_store, redis_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseInspector:
    """Comprehensive database inspector for all systems."""
    
    def __init__(self):
        self.pinecone = enhanced_pinecone_service
        self.neo4j = enhanced_neo4j_service
        self.redis = redis_service
    
    async def inspect_pinecone(self) -> Dict[str, Any]:
        """Inspect Pinecone data."""
        print("\n🔍 INSPECTING PINECONE")
        print("=" * 50)
        
        try:
            # Get index stats
            stats = self.pinecone.get_index_stats()
            print(f"📊 Index Stats: {stats}")
            
            # Get all vectors (this might be expensive for large indexes)
            print("\n🔍 Fetching all vectors...")
            
            # Note: Pinecone doesn't have a direct "get all" method
            # We'll need to query with a dummy vector to get all results
            dummy_query = "test query for inspection"
            
            # Query all namespaces
            all_data = {}
            
            # Try to get data from default namespace
            try:
                vectors = self.pinecone.query_vectors(dummy_query, top_k=1000)
                all_data["default_namespace"] = vectors
                print(f"✅ Found {len(vectors)} vectors in default namespace")
            except Exception as e:
                print(f"⚠️ Could not query default namespace: {e}")
            
            # Try to get data from user namespaces
            # Note: This is a simplified approach - in production you'd want to track user namespaces
            user_namespaces = ["user:test_user", "user:demo_user"]  # Add your user namespaces here
            
            for namespace in user_namespaces:
                try:
                    vectors = self.pinecone.query_vectors(dummy_query, top_k=1000, namespace=namespace)
                    all_data[namespace] = vectors
                    print(f"✅ Found {len(vectors)} vectors in namespace: {namespace}")
                except Exception as e:
                    print(f"⚠️ Could not query namespace {namespace}: {e}")
            
            return {
                "stats": stats,
                "vectors": all_data,
                "total_vectors": sum(len(vectors) for vectors in all_data.values())
            }
            
        except Exception as e:
            print(f"❌ Pinecone inspection failed: {e}")
            return {"error": str(e)}
    
    async def inspect_neo4j(self) -> Dict[str, Any]:
        """Inspect Neo4j data."""
        print("\n🔍 INSPECTING NEO4J")
        print("=" * 50)
        
        try:
            # Get database info
            db_info = await self.neo4j.get_database_info()
            print(f"📊 Database Info: {db_info}")
            
            # Get all nodes
            print("\n🔍 Fetching all nodes...")
            nodes_query = "MATCH (n) RETURN n, labels(n) as labels LIMIT 1000"
            nodes = await self.neo4j.run_query(nodes_query)
            print(f"✅ Found {len(nodes)} nodes")
            
            # Get all relationships
            print("\n🔍 Fetching all relationships...")
            rels_query = "MATCH ()-[r]->() RETURN r, type(r) as rel_type LIMIT 1000"
            relationships = await self.neo4j.run_query(rels_query)
            print(f"✅ Found {len(relationships)} relationships")
            
            # Get users
            print("\n🔍 Fetching all users...")
            users_query = "MATCH (u:User) RETURN u"
            users = await self.neo4j.run_query(users_query)
            print(f"✅ Found {len(users)} users")
            
            # Get concepts
            print("\n🔍 Fetching all concepts...")
            concepts_query = "MATCH (c:Concept) RETURN c"
            concepts = await self.neo4j.run_query(concepts_query)
            print(f"✅ Found {len(concepts)} concepts")
            
            # Get facts
            print("\n🔍 Fetching all facts...")
            facts_query = "MATCH (f:Fact) RETURN f"
            facts = await self.neo4j.run_query(facts_query)
            print(f"✅ Found {len(facts)} facts")
            
            return {
                "database_info": db_info,
                "nodes": nodes,
                "relationships": relationships,
                "users": users,
                "concepts": concepts,
                "facts": facts,
                "summary": {
                    "total_nodes": len(nodes),
                    "total_relationships": len(relationships),
                    "total_users": len(users),
                    "total_concepts": len(concepts),
                    "total_facts": len(facts)
                }
            }
            
        except Exception as e:
            print(f"❌ Neo4j inspection failed: {e}")
            return {"error": str(e)}
    
    async def inspect_redis(self) -> Dict[str, Any]:
        """Inspect Redis data."""
        print("\n🔍 INSPECTING REDIS")
        print("=" * 50)
        
        try:
            client = self.redis.get_client()
            if not client:
                print("❌ Redis client not available")
                return {"error": "Redis client not available"}
            
            # Get all keys
            print("\n🔍 Fetching all keys...")
            all_keys = await client.keys("*")
            print(f"✅ Found {len(all_keys)} keys")
            
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
            
            # Get sample data from each category
            sample_data = {}
            
            for category, keys in key_categories.items():
                if keys:
                    print(f"\n📁 {category.upper()} ({len(keys)} keys)")
                    sample_data[category] = []
                    
                    # Get first 5 keys as samples
                    for key in keys[:5]:
                        try:
                            key_type = await client.type(key)
                            if key_type == "string":
                                value = await client.get(key)
                                sample_data[category].append({
                                    "key": key,
                                    "type": "string",
                                    "value": value.decode('utf-8') if isinstance(value, bytes) else value
                                })
                            elif key_type == "list":
                                length = await client.llen(key)
                                sample_items = await client.lrange(key, 0, 4)
                                sample_data[category].append({
                                    "key": key,
                                    "type": "list",
                                    "length": length,
                                    "sample_items": [item.decode('utf-8') if isinstance(item, bytes) else item for item in sample_items]
                                })
                            elif key_type == "hash":
                                hash_data = await client.hgetall(key)
                                sample_data[category].append({
                                    "key": key,
                                    "type": "hash",
                                    "data": {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in hash_data.items()}
                                })
                            else:
                                sample_data[category].append({
                                    "key": key,
                                    "type": key_type,
                                    "note": "Complex data type"
                                })
                        except Exception as e:
                            print(f"⚠️ Could not read key {key}: {e}")
            
            return {
                "total_keys": len(all_keys),
                "key_categories": {k: len(v) for k, v in key_categories.items()},
                "sample_data": sample_data,
                "all_keys": all_keys[:100]  # First 100 keys
            }
            
        except Exception as e:
            print(f"❌ Redis inspection failed: {e}")
            return {"error": str(e)}
    
    async def inspect_all(self):
        """Inspect all databases."""
        print("🚀 COMPREHENSIVE DATABASE INSPECTION")
        print("=" * 60)
        
        results = {}
        
        # Initialize services
        print("\n🔧 Initializing services...")
        try:
            self.pinecone.initialize()
            await self.neo4j.connect()
            print("✅ Services initialized")
        except Exception as e:
            print(f"⚠️ Service initialization warning: {e}")
        
        # Inspect each database
        results["pinecone"] = await self.inspect_pinecone()
        results["neo4j"] = await self.inspect_neo4j()
        results["redis"] = await self.inspect_redis()
        
        # Summary
        print("\n📊 INSPECTION SUMMARY")
        print("=" * 60)
        
        if "error" not in results["pinecone"]:
            print(f"🔍 Pinecone: {results['pinecone'].get('total_vectors', 0)} vectors")
        else:
            print(f"❌ Pinecone: {results['pinecone']['error']}")
        
        if "error" not in results["neo4j"]:
            summary = results["neo4j"].get("summary", {})
            print(f"🔍 Neo4j: {summary.get('total_nodes', 0)} nodes, {summary.get('total_relationships', 0)} relationships")
        else:
            print(f"❌ Neo4j: {results['neo4j']['error']}")
        
        if "error" not in results["redis"]:
            print(f"🔍 Redis: {results['redis'].get('total_keys', 0)} keys")
        else:
            print(f"❌ Redis: {results['redis']['error']}")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"database_inspection_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {filename}")
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")
        
        return results

async def main():
    """Main inspection function."""
    inspector = DatabaseInspector()
    results = await inspector.inspect_all()
    
    print("\n🎉 Database inspection complete!")
    return results

if __name__ == "__main__":
    asyncio.run(main())
