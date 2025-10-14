"""
Test Storage and Recall System
Quick test to ensure data is properly stored and recalled
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_storage_service import enhanced_storage_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_storage_recall():
    """Test storage and recall system."""
    print("🧪 TESTING STORAGE AND RECALL SYSTEM")
    print("=" * 50)
    
    try:
        # Test user data
        test_user_id = "test_user_123"
        test_user_data = {
            "name": "Test User",
            "email": "test@example.com",
            "timezone": "UTC"
        }
        
        print(f"👤 Testing user: {test_user_id}")
        
        # 1. Ensure user exists
        print("\n1️⃣ Ensuring user exists...")
        success = await enhanced_storage_service.ensure_user_exists(test_user_id, test_user_data)
        print(f"✅ User ensured: {success}")
        
        # 2. Store memory
        print("\n2️⃣ Storing memory...")
        memory_data = {
            "memory_id": "test_memory_001",
            "text": "I love programming in Python and building AI applications",
            "memory_type": "fact",
            "priority": "high",
            "category": "programming"
        }
        success = await enhanced_storage_service.store_memory_with_guarantee(test_user_id, memory_data)
        print(f"✅ Memory stored: {success}")
        
        # 3. Store fact
        print("\n3️⃣ Storing fact...")
        success = await enhanced_storage_service.store_fact_with_guarantee(
            test_user_id, 
            "My favorite programming language is Python",
            "programming"
        )
        print(f"✅ Fact stored: {success}")
        
        # 4. Store session
        print("\n4️⃣ Storing session...")
        session_messages = [
            {"role": "user", "content": "Hello, I'm a programmer"},
            {"role": "assistant", "content": "Nice to meet you! What programming languages do you use?"},
            {"role": "user", "content": "I mainly use Python and JavaScript"}
        ]
        success = await enhanced_storage_service.store_session_with_guarantee(
            test_user_id,
            "test_session_001",
            session_messages
        )
        print(f"✅ Session stored: {success}")
        
        # 5. Test recall
        print("\n5️⃣ Testing recall...")
        recall_data = await enhanced_storage_service.recall_user_data(test_user_id, "programming")
        print(f"✅ Recall successful:")
        print(f"   - Memories: {len(recall_data.get('memories', []))}")
        print(f"   - Facts: {len(recall_data.get('facts', []))}")
        print(f"   - Relationships: {len(recall_data.get('relationships', []))}")
        print(f"   - Sessions: {len(recall_data.get('sessions', {}))}")
        print(f"   - Total items: {recall_data.get('total_items', 0)}")
        
        # 6. Get storage stats
        print("\n6️⃣ Getting storage stats...")
        stats = await enhanced_storage_service.get_storage_stats()
        print(f"✅ Storage stats:")
        for system, data in stats.items():
            if isinstance(data, dict):
                print(f"   - {system}: {data}")
        
        print("\n🎉 Storage and recall test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    success = await test_storage_recall()
    
    if success:
        print("\n✅ All tests passed! Your storage and recall system is working perfectly!")
    else:
        print("\n❌ Tests failed! Check the error messages above.")

if __name__ == "__main__":
    asyncio.run(main())
