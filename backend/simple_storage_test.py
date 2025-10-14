"""
Simple Storage Test
Quick test to verify storage and recall is working
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_simple_storage():
    """Simple storage test."""
    print("🧪 SIMPLE STORAGE TEST")
    print("=" * 30)
    
    try:
        # Import services
        from app.services.enhanced_pinecone_service import enhanced_pinecone_service
        from app.services.enhanced_neo4j_service import enhanced_neo4j_service
        from app.services import redis_service
        
        print("🔧 Testing connections...")
        
        # Test Pinecone
        if enhanced_pinecone_service.is_ready():
            print("✅ Pinecone connected")
            stats = enhanced_pinecone_service.get_index_stats()
            print(f"   Vectors: {stats.get('total_vector_count', 0)}")
        else:
            print("❌ Pinecone not ready")
        
        # Test Neo4j
        if await enhanced_neo4j_service.ping():
            print("✅ Neo4j connected")
            db_info = await enhanced_neo4j_service.get_database_info()
            print(f"   Nodes: {db_info.get('nodes', 0)}")
        else:
            print("❌ Neo4j not ready")
        
        # Test Redis
        client = redis_service.get_client()
        if client:
            print("✅ Redis connected")
            keys = await client.keys("*")
            print(f"   Keys: {len(keys)}")
        else:
            print("❌ Redis not ready")
        
        print("\n🎉 All systems connected!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_simple_storage())
