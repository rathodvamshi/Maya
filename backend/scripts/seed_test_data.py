"""
Seed Test Data Script
Creates sample user data in all databases to test storage and recall
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
import json

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_memory_service import enhanced_memory_service
from app.services.enhanced_pinecone_service import enhanced_pinecone_service
from app.services.enhanced_neo4j_service import enhanced_neo4j_service
from app.services import memory_store

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataSeeder:
    """Seed test data into all databases."""
    
    def __init__(self):
        self.test_users = [
            {
                "user_id": "user_001",
                "name": "John Doe",
                "email": "john@example.com",
                "timezone": "UTC"
            },
            {
                "user_id": "user_002", 
                "name": "Jane Smith",
                "email": "jane@example.com",
                "timezone": "America/New_York"
            },
            {
                "user_id": "user_003",
                "name": "Bob Wilson", 
                "email": "bob@example.com",
                "timezone": "Europe/London"
            }
        ]
        
        self.test_memories = [
            {
                "user_id": "user_001",
                "memory_id": "mem_001",
                "text": "I love programming in Python and building AI applications",
                "memory_type": "fact",
                "priority": "high",
                "category": "programming"
            },
            {
                "user_id": "user_001", 
                "memory_id": "mem_002",
                "text": "My favorite programming language is Python because it's easy to learn",
                "memory_type": "preference",
                "priority": "medium",
                "category": "programming"
            },
            {
                "user_id": "user_002",
                "memory_id": "mem_003", 
                "text": "I work as a data scientist and specialize in machine learning",
                "memory_type": "fact",
                "priority": "high",
                "category": "career"
            },
            {
                "user_id": "user_002",
                "memory_id": "mem_004",
                "text": "I enjoy reading science fiction books in my free time",
                "memory_type": "hobby",
                "priority": "low",
                "category": "personal"
            },
            {
                "user_id": "user_003",
                "memory_id": "mem_005",
                "text": "I'm learning web development with React and Node.js",
                "memory_type": "learning",
                "priority": "high",
                "category": "programming"
            }
        ]
        
        self.test_facts = [
            {
                "user_id": "user_001",
                "fact_text": "John's favorite color is blue",
                "category": "personal"
            },
            {
                "user_id": "user_001",
                "fact_text": "John has 5 years of programming experience",
                "category": "career"
            },
            {
                "user_id": "user_002",
                "fact_text": "Jane has a PhD in Computer Science",
                "category": "education"
            },
            {
                "user_id": "user_002",
                "fact_text": "Jane lives in New York City",
                "category": "location"
            },
            {
                "user_id": "user_003",
                "fact_text": "Bob is a beginner programmer",
                "category": "skill_level"
            }
        ]
        
        self.test_sessions = [
            {
                "user_id": "user_001",
                "session_id": "session_001",
                "messages": [
                    {"role": "user", "content": "Hello, I'm John. I love programming!"},
                    {"role": "assistant", "content": "Nice to meet you John! What programming languages do you work with?"},
                    {"role": "user", "content": "I mainly work with Python and JavaScript"},
                    {"role": "assistant", "content": "That's great! Python is excellent for AI and data science."}
                ]
            },
            {
                "user_id": "user_002",
                "session_id": "session_002", 
                "messages": [
                    {"role": "user", "content": "Hi, I'm Jane. I'm a data scientist."},
                    {"role": "assistant", "content": "Hello Jane! Data science is fascinating. What's your specialty?"},
                    {"role": "user", "content": "I specialize in machine learning and deep learning"},
                    {"role": "assistant", "content": "Excellent! ML and DL are cutting-edge fields."}
                ]
            }
        ]
    
    async def seed_all_data(self):
        """Seed all test data into the databases."""
        print("🌱 SEEDING TEST DATA")
        print("=" * 50)
        
        try:
            # Initialize services
            print("🔧 Initializing services...")
            enhanced_pinecone_service.initialize()
            await enhanced_neo4j_service.connect()
            await enhanced_memory_service.initialize()
            print("✅ Services initialized")
            
            # Seed user profiles
            print("\n👤 Seeding user profiles...")
            for user in self.test_users:
                success = await enhanced_memory_service.create_user_profile(
                    user["user_id"],
                    user["name"],
                    email=user["email"],
                    timezone=user["timezone"]
                )
                if success:
                    print(f"✅ Created user: {user['name']} ({user['user_id']})")
                else:
                    print(f"❌ Failed to create user: {user['name']}")
            
            # Seed memories
            print("\n🧠 Seeding memories...")
            for memory in self.test_memories:
                success = await enhanced_memory_service.create_memory(
                    memory["user_id"],
                    memory["memory_id"],
                    memory["text"],
                    memory["memory_type"],
                    memory["priority"],
                    category=memory["category"]
                )
                if success:
                    print(f"✅ Created memory: {memory['memory_id']} for {memory['user_id']}")
                else:
                    print(f"❌ Failed to create memory: {memory['memory_id']}")
            
            # Seed facts
            print("\n📚 Seeding facts...")
            for fact in self.test_facts:
                success = await enhanced_memory_service.create_fact(
                    fact["user_id"],
                    fact["fact_text"],
                    fact["category"]
                )
                if success:
                    print(f"✅ Created fact for {fact['user_id']}: {fact['fact_text'][:50]}...")
                else:
                    print(f"❌ Failed to create fact for {fact['user_id']}")
            
            # Seed sessions
            print("\n💬 Seeding sessions...")
            for session in self.test_sessions:
                # Create session
                success = await enhanced_memory_service.create_session(
                    session["user_id"],
                    session["session_id"]
                )
                if success:
                    print(f"✅ Created session: {session['session_id']} for {session['user_id']}")
                
                # Store session messages in Redis
                for message in session["messages"]:
                    await memory_store.append_session_messages(
                        session["session_id"],
                        [message],
                        max_items=50
                    )
                print(f"✅ Stored {len(session['messages'])} messages for session {session['session_id']}")
            
            # Test recall
            print("\n🔍 Testing recall...")
            for user in self.test_users:
                user_id = user["user_id"]
                
                # Test memory recall
                memories = await enhanced_memory_service.get_memories(user_id, "", top_k=10)
                print(f"✅ User {user_id}: {len(memories)} memories")
                
                # Test fact recall
                facts = await enhanced_memory_service.get_facts(user_id, "", top_k=5)
                print(f"✅ User {user_id}: {len(facts)} facts")
                
                # Test global recall
                recall_results = await enhanced_memory_service.global_recall(user_id, "programming")
                print(f"✅ User {user_id}: {recall_results.get('total_recall_items', 0)} recall items")
            
            print("\n🎉 Data seeding completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Data seeding failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def verify_data(self):
        """Verify that data was stored correctly."""
        print("\n🔍 VERIFYING STORED DATA")
        print("=" * 50)
        
        try:
            # Check Pinecone
            if enhanced_pinecone_service.is_ready():
                stats = enhanced_pinecone_service.get_index_stats()
                print(f"📊 Pinecone: {stats.get('total_vector_count', 0)} vectors")
            else:
                print("❌ Pinecone not ready")
            
            # Check Neo4j
            if await enhanced_neo4j_service.ping():
                db_info = await enhanced_neo4j_service.get_database_info()
                print(f"📊 Neo4j: {db_info.get('nodes', 0)} nodes, {db_info.get('relationships', 0)} relationships")
            else:
                print("❌ Neo4j not ready")
            
            # Check Redis
            from app.services import redis_service
            client = redis_service.get_client()
            if client:
                keys = await client.keys("*")
                print(f"📊 Redis: {len(keys)} keys")
            else:
                print("❌ Redis not ready")
            
            return True
            
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False

async def main():
    """Main seeding function."""
    seeder = DataSeeder()
    
    # Seed data
    success = await seeder.seed_all_data()
    
    if success:
        # Verify data
        await seeder.verify_data()
        print("\n🎉 All data seeded and verified successfully!")
    else:
        print("\n💥 Data seeding failed!")

if __name__ == "__main__":
    asyncio.run(main())
