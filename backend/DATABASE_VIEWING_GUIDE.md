# 🔍 Database Viewing Guide

This guide shows you how to view all data in your Pinecone, Neo4j, and Redis databases.

## 🚀 **Quick Start - View All Data**

### **Method 1: Web Interface (Recommended)**
1. Open `database_viewer.html` in your browser
2. Click "Check Health" to see system status
3. Click "Inspect" for each database to view data
4. Use "Inspect All" to see everything at once

### **Method 2: Command Line Scripts**
```bash
# View all databases
python scripts/inspect_all_databases.py

# View individual databases
python scripts/inspect_pinecone.py
python scripts/inspect_neo4j.py
python scripts/inspect_redis.py
```

### **Method 3: API Endpoints**
```bash
# Health check
curl http://127.0.0.1:8000/api/inspector/health

# View Pinecone data
curl http://127.0.0.1:8000/api/inspector/pinecone

# View Neo4j data
curl http://127.0.0.1:8000/api/inspector/neo4j

# View Redis data
curl http://127.0.0.1:8000/api/inspector/redis

# View all databases
curl http://127.0.0.1:8000/api/inspector/all
```

## 📊 **What You Can View**

### **🔍 Pinecone (Vector Database)**
- **Total vectors** in your index
- **Vector dimensions** (1536 for your setup)
- **Sample vectors** with metadata
- **Namespace data** (user-specific vectors)
- **Similarity scores** and embeddings

### **🧠 Neo4j (Knowledge Graph)**
- **All nodes** (Users, Concepts, Facts)
- **All relationships** between nodes
- **User networks** and connections
- **Knowledge graph structure**
- **Node properties** and labels

### **⚡ Redis (Cache & Sessions)**
- **All keys** in Redis
- **Session data** (conversation history)
- **User profiles** and preferences
- **Cached facts** and data
- **Key categories** and types

## 🛠️ **Detailed Usage**

### **1. Web Interface Usage**

Open `database_viewer.html` in your browser and:

1. **Check System Health**
   - Click "Check Health" to see if all databases are connected
   - View total counts for each database
   - See connection status

2. **Inspect Pinecone**
   - Click "Inspect" under Pinecone section
   - View vector statistics and sample data
   - See metadata for each vector

3. **Inspect Neo4j**
   - Click "Inspect" under Neo4j section
   - View nodes, relationships, and users
   - See knowledge graph structure

4. **Inspect Redis**
   - Click "Inspect" under Redis section
   - View all keys and their categories
   - See session data and user profiles

### **2. Command Line Usage**

```bash
# Navigate to backend directory
cd backend

# Run comprehensive inspection
python scripts/inspect_all_databases.py

# This will:
# - Check all database connections
# - Display statistics for each database
# - Show sample data from each system
# - Save detailed results to JSON file
```

### **3. API Usage**

You can also use the API endpoints directly:

```bash
# Get system health
curl -X GET "http://127.0.0.1:8000/api/inspector/health"

# Get Pinecone data with specific parameters
curl -X GET "http://127.0.0.1:8000/api/inspector/pinecone?namespace=user:test_user&top_k=100"

# Get Redis data for specific category
curl -X GET "http://127.0.0.1:8000/api/inspector/redis?category=sessions"
```

## 📈 **Understanding Your Data**

### **Pinecone Data Structure**
```json
{
  "id": "memory:12345",
  "score": 0.95,
  "metadata": {
    "user_id": "user123",
    "memory_id": "12345",
    "text": "I love programming",
    "kind": "memory",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

### **Neo4j Data Structure**
```json
{
  "nodes": [
    {
      "n": {"id": "user123", "name": "John Doe"},
      "labels": ["User"]
    }
  ],
  "relationships": [
    {
      "r": {"created_at": "2024-01-01T00:00:00Z"},
      "rel_type": "HAS_FACT"
    }
  ]
}
```

### **Redis Data Structure**
```json
{
  "sessions": [
    {
      "key": "sess:session123:msgs",
      "type": "list",
      "items": ["user message", "assistant response"]
    }
  ],
  "users": [
    {
      "key": "user:user123:profile",
      "type": "string",
      "value": "{\"name\": \"John Doe\", \"email\": \"john@example.com\"}"
    }
  ]
}
```

## 🔧 **Troubleshooting**

### **Common Issues**

1. **"Database not connected"**
   - Check if your application is running
   - Verify environment variables are set
   - Check database credentials

2. **"No data found"**
   - Your databases might be empty
   - Check if you've created any memories or users
   - Try creating some test data first

3. **"Permission denied"**
   - Make sure you're authenticated
   - Check if you have proper API keys
   - Verify database permissions

### **Debug Commands**

```bash
# Check if services are running
curl http://127.0.0.1:8000/api/inspector/health

# Test individual database connections
python -c "from app.services.enhanced_pinecone_service import enhanced_pinecone_service; enhanced_pinecone_service.initialize(); print('Pinecone ready:', enhanced_pinecone_service.is_ready())"

python -c "import asyncio; from app.services.enhanced_neo4j_service import enhanced_neo4j_service; print('Neo4j ready:', asyncio.run(enhanced_neo4j_service.ping()))"
```

## 📊 **Data Export**

All inspection scripts save detailed results to JSON files:

- `database_inspection_YYYYMMDD_HHMMSS.json` - Complete inspection
- `pinecone_inspection_YYYYMMDD_HHMMSS.json` - Pinecone data only
- `neo4j_inspection_YYYYMMDD_HHMMSS.json` - Neo4j data only
- `redis_inspection_YYYYMMDD_HHMMSS.json` - Redis data only

## 🎯 **Quick Commands Summary**

```bash
# View all data (recommended)
python scripts/inspect_all_databases.py

# View specific databases
python scripts/inspect_pinecone.py
python scripts/inspect_neo4j.py
python scripts/inspect_redis.py

# Web interface
open database_viewer.html

# API endpoints
curl http://127.0.0.1:8000/api/inspector/health
curl http://127.0.0.1:8000/api/inspector/all
```

## 🚀 **Next Steps**

1. **Run the inspection** to see your current data
2. **Create some test data** using the enhanced memory API
3. **Monitor your databases** regularly using the web interface
4. **Export data** for backup or analysis
5. **Set up monitoring** for production use

Your enhanced memory system is now fully inspectable and monitorable! 🎉
