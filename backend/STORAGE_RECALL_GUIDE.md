# 🗄️ Storage and Recall Guide

This guide ensures your user data is properly stored and recalled across all systems.

## 🚀 **Quick Start - Ensure Data Storage**

### **1. Test Your System**
```bash
# Run the storage and recall test
python scripts/test_storage_recall.py

# This will:
# - Create a test user
# - Store memories, facts, and sessions
# - Test recall functionality
# - Show storage statistics
```

### **2. Seed Test Data**
```bash
# Populate your databases with sample data
python scripts/seed_test_data.py

# This creates:
# - 3 test users with profiles
# - 5 memories across users
# - 5 facts for each user
# - 2 conversation sessions
```

### **3. Verify Data Storage**
```bash
# Check all databases
python scripts/inspect_all_databases.py

# You should now see:
# - Pinecone: Multiple vectors
# - Neo4j: Users, concepts, relationships
# - Redis: User profiles, sessions, cached data
```

## 📊 **API Endpoints for Data Management**

### **User Management**
```bash
# Ensure user exists in all systems
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/ensure" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "name": "John Doe", "email": "john@example.com"}'

# Check if user exists
curl -X GET "http://127.0.0.1:8000/api/data/users/{user_id}/exists"
```

### **Guaranteed Storage**
```bash
# Store memory with guarantee
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/memories/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"memory_id": "mem001", "text": "I love programming", "memory_type": "fact"}'

# Store fact with guarantee
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/facts/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"fact_text": "My favorite color is blue", "category": "personal"}'

# Store session with guarantee
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/sessions/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess001", "messages": [{"role": "user", "content": "Hello"}]}'
```

### **Data Recall**
```bash
# Recall all user data
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/recall/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"query": "programming", "include_memories": true, "include_facts": true}'

# Simple recall
curl -X GET "http://127.0.0.1:8000/api/data/users/{user_id}/recall/simple?query=programming"
```

### **Data Verification**
```bash
# Verify user data exists
curl -X GET "http://127.0.0.1:8000/api/data/users/{user_id}/verify"

# Get storage statistics
curl -X GET "http://127.0.0.1:8000/api/data/storage/stats"
```

## 🔧 **Troubleshooting "No Records Found"**

### **Problem: Empty Databases**
If you see "no records found", your databases are empty. Here's how to fix:

1. **Seed Test Data**
```bash
python scripts/seed_test_data.py
```

2. **Create User Data via API**
```bash
# Create a user
curl -X POST "http://127.0.0.1:8000/api/data/users/user123/ensure" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "name": "Test User", "email": "test@example.com"}'

# Store some memories
curl -X POST "http://127.0.0.1:8000/api/data/users/user123/memories/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"memory_id": "mem001", "text": "I love programming in Python", "memory_type": "fact"}'
```

3. **Verify Data Was Stored**
```bash
# Check if data exists
curl -X GET "http://127.0.0.1:8000/api/data/users/user123/verify"
```

### **Problem: Data Not Persisting**
If data disappears, check:

1. **Database Connections**
```bash
# Check system health
curl -X GET "http://127.0.0.1:8000/api/inspector/health"
```

2. **Storage Statistics**
```bash
# Get storage stats
curl -X GET "http://127.0.0.1:8000/api/data/storage/stats"
```

3. **Ensure Data Persistence**
```bash
# Force data persistence
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/persist"
```

## 📈 **Data Storage Strategy**

### **Multi-System Storage**
Your data is stored in **3 systems** for redundancy:

1. **Pinecone** - Vector embeddings for semantic search
2. **Neo4j** - Knowledge graph for relationships
3. **Redis** - Fast access cache and sessions

### **Data Types Stored**

#### **User Profiles**
- Stored in: Neo4j + Redis
- Contains: Name, email, timezone, preferences
- Purpose: User identification and personalization

#### **Memories**
- Stored in: Pinecone + Neo4j + Redis
- Contains: Text, metadata, embeddings
- Purpose: Semantic search and recall

#### **Facts**
- Stored in: Pinecone + Neo4j + Redis
- Contains: Factual information about users
- Purpose: Knowledge base and context

#### **Sessions**
- Stored in: Neo4j + Redis
- Contains: Conversation history
- Purpose: Context and continuity

## 🎯 **Best Practices**

### **1. Always Use Guaranteed Storage**
```python
# Use these endpoints for guaranteed storage:
POST /api/data/users/{user_id}/memories/guaranteed
POST /api/data/users/{user_id}/facts/guaranteed
POST /api/data/users/{user_id}/sessions/guaranteed
```

### **2. Verify Data After Storage**
```python
# Always verify data was stored:
GET /api/data/users/{user_id}/verify
```

### **3. Use Bulk Operations for Efficiency**
```python
# Store multiple items at once:
POST /api/data/users/{user_id}/bulk-store
```

### **4. Regular Data Inspection**
```bash
# Check your data regularly:
python scripts/inspect_all_databases.py
```

## 🚨 **Common Issues and Solutions**

### **Issue: "User not found"**
**Solution:**
```bash
# Ensure user exists
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/ensure" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "name": "User Name"}'
```

### **Issue: "Memory not stored"**
**Solution:**
```bash
# Use guaranteed storage
curl -X POST "http://127.0.0.1:8000/api/data/users/{user_id}/memories/guaranteed" \
  -H "Content-Type: application/json" \
  -d '{"memory_id": "mem001", "text": "Your memory text", "memory_type": "fact"}'
```

### **Issue: "Recall returns empty"**
**Solution:**
```bash
# Check if data exists
curl -X GET "http://127.0.0.1:8000/api/data/users/{user_id}/verify"

# If empty, seed some data
python scripts/seed_test_data.py
```

## 📊 **Monitoring Your Data**

### **Web Interface**
Open `database_viewer.html` in your browser to:
- View all data in real-time
- Check system health
- Monitor storage statistics

### **Command Line Monitoring**
```bash
# Quick health check
curl http://127.0.0.1:8000/api/inspector/health

# Detailed inspection
python scripts/inspect_all_databases.py
```

### **API Monitoring**
```bash
# Get storage statistics
curl http://127.0.0.1:8000/api/data/storage/stats

# Verify specific user
curl http://127.0.0.1:8000/api/data/users/{user_id}/verify
```

## 🎉 **Success Indicators**

You'll know your system is working when:

1. **Storage Test Passes**
```bash
python scripts/test_storage_recall.py
# Should show: ✅ All tests passed!
```

2. **Data Inspection Shows Records**
```bash
python scripts/inspect_all_databases.py
# Should show: Multiple vectors, nodes, relationships, keys
```

3. **API Recall Returns Data**
```bash
curl -X GET "http://127.0.0.1:8000/api/data/users/{user_id}/recall/simple"
# Should return: memories, facts, relationships, sessions
```

4. **Web Interface Shows Data**
Open `database_viewer.html` and click "Inspect" - you should see data in all databases.

Your enhanced memory system now has **guaranteed storage and recall** across all databases! 🚀
