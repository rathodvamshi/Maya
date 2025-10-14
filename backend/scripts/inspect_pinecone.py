"""
Pinecone Database Inspector
View all vectors and metadata in Pinecone
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_pinecone_service import enhanced_pinecone_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def inspect_pinecone():
    """Inspect Pinecone data in detail."""
    print("🔍 PINECONE DATABASE INSPECTION")
    print("=" * 50)
    
    try:
        # Initialize Pinecone
        enhanced_pinecone_service.initialize()
        
        if not enhanced_pinecone_service.is_ready():
            print("❌ Pinecone not ready")
            return
        
        print("✅ Pinecone connected")
        
        # Get index stats
        stats = enhanced_pinecone_service.get_index_stats()
        print(f"\n📊 Index Statistics:")
        print(f"   Total vectors: {stats.get('total_vector_count', 'Unknown')}")
        print(f"   Dimension: {stats.get('dimension', 'Unknown')}")
        print(f"   Index fullness: {stats.get('index_fullness', 'Unknown')}")
        
        # Query all vectors (this might be expensive for large indexes)
        print(f"\n🔍 Fetching all vectors...")
        
        # Try to get vectors from different namespaces
        namespaces_to_check = [
            None,  # Default namespace
            "user:test_user",
            "user:demo_user",
            "user:admin"
        ]
        
        all_vectors = {}
        
        for namespace in namespaces_to_check:
            try:
                print(f"\n📁 Checking namespace: {namespace or 'default'}")
                
                # Query with a broad search
                vectors = enhanced_pinecone_service.query_vectors(
                    "test query for inspection",
                    top_k=1000,
                    namespace=namespace
                )
                
                if vectors:
                    all_vectors[namespace or "default"] = vectors
                    print(f"   ✅ Found {len(vectors)} vectors")
                    
                    # Show sample vectors
                    for i, vector in enumerate(vectors[:3]):  # Show first 3
                        print(f"   📄 Vector {i+1}:")
                        print(f"      ID: {vector.get('id', 'Unknown')}")
                        print(f"      Score: {vector.get('score', 'N/A')}")
                        metadata = vector.get('metadata', {})
                        print(f"      Metadata: {json.dumps(metadata, indent=6)}")
                else:
                    print(f"   📭 No vectors found")
                    
            except Exception as e:
                print(f"   ⚠️ Error querying namespace {namespace}: {e}")
        
        # Summary
        total_vectors = sum(len(vectors) for vectors in all_vectors.values())
        print(f"\n📊 SUMMARY")
        print(f"   Total vectors found: {total_vectors}")
        print(f"   Namespaces with data: {len(all_vectors)}")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pinecone_inspection_{timestamp}.json"
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "stats": stats,
            "vectors": all_vectors,
            "total_vectors": total_vectors
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filename}")
        
        return results
        
    except Exception as e:
        print(f"❌ Pinecone inspection failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(inspect_pinecone())
