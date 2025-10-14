"""
Redis Database Inspector
View all keys and data in Redis
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import redis_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def inspect_redis():
    """Inspect Redis data in detail."""
    print("🔍 REDIS DATABASE INSPECTION")
    print("=" * 50)
    
    try:
        # Get Redis client
        client = redis_service.get_client()
        if not client:
            print("❌ Redis client not available")
            return
        
        print("✅ Redis connected")
        
        # Get all keys
        print(f"\n🔍 Fetching all keys...")
        all_keys = await client.keys("*")
        print(f"   ✅ Found {len(all_keys)} keys")
        
        # Categorize keys
        key_categories = {
            "sessions": [],
            "users": [],
            "facts": [],
            "profiles": [],
            "states": [],
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
                key_categories["states"].append(key_str)
            elif key_str.startswith("embed:"):
                key_categories["other"].append(key_str)
            else:
                key_categories["other"].append(key_str)
        
        print(f"\n📁 Keys by Category:")
        for category, keys in key_categories.items():
            print(f"   {category}: {len(keys)} keys")
        
        # Inspect each category
        detailed_data = {}
        
        for category, keys in key_categories.items():
            if not keys:
                continue
                
            print(f"\n🔍 Inspecting {category.upper()} ({len(keys)} keys)")
            detailed_data[category] = []
            
            # Get detailed data for first 10 keys
            for key in keys[:10]:
                try:
                    key_type = await client.type(key)
                    key_ttl = await client.ttl(key)
                    
                    key_data = {
                        "key": key,
                        "type": key_type,
                        "ttl": key_ttl
                    }
                    
                    if key_type == "string":
                        value = await client.get(key)
                        key_data["value"] = value.decode('utf-8') if isinstance(value, bytes) else value
                        
                    elif key_type == "list":
                        length = await client.llen(key)
                        key_data["length"] = length
                        # Get all items if list is small, otherwise first 10
                        if length <= 20:
                            items = await client.lrange(key, 0, -1)
                        else:
                            items = await client.lrange(key, 0, 9)
                        key_data["items"] = [item.decode('utf-8') if isinstance(item, bytes) else item for item in items]
                        
                    elif key_type == "hash":
                        hash_data = await client.hgetall(key)
                        key_data["data"] = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in hash_data.items()}
                        
                    elif key_type == "set":
                        members = await client.smembers(key)
                        key_data["members"] = [member.decode('utf-8') if isinstance(member, bytes) else member for member in members]
                        
                    elif key_type == "zset":
                        # Get all members with scores
                        members = await client.zrange(key, 0, -1, withscores=True)
                        key_data["members"] = [(member.decode('utf-8') if isinstance(member, bytes) else member, score) for member, score in members]
                    
                    detailed_data[category].append(key_data)
                    
                except Exception as e:
                    print(f"   ⚠️ Error reading key {key}: {e}")
        
        # Special inspection for session data
        print(f"\n🔍 Inspecting Session Data...")
        session_data = {}
        
        for key in key_categories["sessions"]:
            try:
                # Get session messages
                messages = await client.lrange(key, 0, -1)
                session_data[key] = {
                    "message_count": len(messages),
                    "messages": [json.loads(msg.decode('utf-8')) for msg in messages if msg]
                }
            except Exception as e:
                print(f"   ⚠️ Error reading session {key}: {e}")
        
        # Special inspection for user profiles
        print(f"\n🔍 Inspecting User Profiles...")
        profile_data = {}
        
        for key in key_categories["users"]:
            try:
                if key.endswith(":profile"):
                    profile = await client.get(key)
                    if profile:
                        profile_data[key] = json.loads(profile.decode('utf-8'))
            except Exception as e:
                print(f"   ⚠️ Error reading profile {key}: {e}")
        
        # Summary
        print(f"\n📊 SUMMARY")
        print(f"   Total keys: {len(all_keys)}")
        for category, keys in key_categories.items():
            print(f"   {category}: {len(keys)} keys")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"redis_inspection_{timestamp}.json"
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_keys": len(all_keys),
            "key_categories": {k: len(v) for k, v in key_categories.items()},
            "detailed_data": detailed_data,
            "session_data": session_data,
            "profile_data": profile_data,
            "all_keys": [key.decode('utf-8') if isinstance(key, bytes) else key for key in all_keys]
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filename}")
        
        return results
        
    except Exception as e:
        print(f"❌ Redis inspection failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(inspect_redis())
