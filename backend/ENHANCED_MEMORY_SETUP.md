# Enhanced Memory System Setup Guide

This guide explains how to set up and use the enhanced memory system with Pinecone and Neo4j integration.

## 🚀 Overview

The enhanced memory system provides comprehensive CRUD operations across:
- **Pinecone**: Vector database for semantic search and similarity matching
- **Neo4j**: Knowledge graph for relationship management
- **Redis**: Session management and caching
- **MongoDB**: Structured data storage

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the backend directory with the following variables:

```bash
# Pinecone Configuration
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX=maya2-session-memory
PINECONE_HOST=https://maya-ityq2wh.svc.aped-4627-b74a.pinecone.io
PINECONE_DIMENSIONS=1536
PINECONE_METRIC=cosine
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Neo4j Configuration
NEO4J_URI=neo4j+s://bb2cd868.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
NEO4J_DATABASE=neo4j
NEO4J_QUERY_API_URL=https://bb2cd868.databases.neo4j.io/db/{databaseName}/query/v2

# MongoDB Configuration
MONGO_URI=mongodb+s://username:password@cluster.mongodb.net/
MONGO_DB=MAYA

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_TLS=false

# AI Providers
GEMINI_API_KEY=your-gemini-api-key
COHERE_API_KEY=your-cohere-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

## 🏗️ Architecture

### Enhanced Memory Service

The `EnhancedMemoryService` provides a unified interface for:

1. **User Management**
   - Create/update/delete user profiles
   - Global user recall across all systems

2. **Memory Operations**
   - Create/read/update/delete memories
   - Semantic search and similarity matching
   - Fact extraction and storage

3. **Session Management**
   - Session creation and persistence
   - Cross-session memory recall
   - Global session state management

4. **Knowledge Graph Operations**
   - Relationship management
   - Concept search and discovery
   - Network analysis

## 📡 API Endpoints

### Health and Status
- `GET /api/enhanced-memory/health` - Service health check
- `GET /api/enhanced-memory/stats` - Database statistics

### User Management
- `POST /api/enhanced-memory/users/{user_id}/profile` - Create user profile
- `GET /api/enhanced-memory/users/{user_id}/profile` - Get user profile
- `PUT /api/enhanced-memory/users/{user_id}/profile` - Update user profile
- `DELETE /api/enhanced-memory/users/{user_id}` - Delete user

### Memory Operations
- `POST /api/enhanced-memory/users/{user_id}/memories` - Create memory
- `GET /api/enhanced-memory/users/{user_id}/memories` - Get memories
- `PUT /api/enhanced-memory/users/{user_id}/memories/{memory_id}` - Update memory
- `DELETE /api/enhanced-memory/users/{user_id}/memories/{memory_id}` - Delete memory

### Fact Management
- `POST /api/enhanced-memory/users/{user_id}/facts` - Create fact
- `GET /api/enhanced-memory/users/{user_id}/facts` - Get facts
- `DELETE /api/enhanced-memory/users/{user_id}/facts` - Delete fact

### Session Management
- `POST /api/enhanced-memory/users/{user_id}/sessions/{session_id}` - Create session
- `GET /api/enhanced-memory/users/{user_id}/sessions/{session_id}` - Get session memories
- `POST /api/enhanced-memory/users/{user_id}/sessions/{session_id}/persist` - Persist session

### Global Recall
- `POST /api/enhanced-memory/users/{user_id}/recall` - Global recall
- `GET /api/enhanced-memory/users/{user_id}/search` - Search memories

### Relationship Management
- `GET /api/enhanced-memory/users/{user_id}/relationships` - Get relationships
- `GET /api/enhanced-memory/users/{user_id}/network` - Get user network
- `GET /api/enhanced-memory/concepts/search` - Search concepts

## 🧪 Testing

### Run Integration Tests

```bash
cd backend
python scripts/test_enhanced_memory_integration.py
```

### Test Individual Components

```bash
# Test Pinecone connection
python -c "from app.services.enhanced_pinecone_service import enhanced_pinecone_service; enhanced_pinecone_service.initialize(); print('Pinecone ready:', enhanced_pinecone_service.is_ready())"

# Test Neo4j connection
python -c "import asyncio; from app.services.enhanced_neo4j_service import enhanced_neo4j_service; print('Neo4j ready:', asyncio.run(enhanced_neo4j_service.ping()))"
```

## 🔄 Usage Examples

### Create User Profile

```python
from app.services.enhanced_memory_service import enhanced_memory_service

# Create user profile
await enhanced_memory_service.create_user_profile(
    user_id="user123",
    name="John Doe",
    email="john@example.com",
    timezone="UTC"
)
```

### Create Memory

```python
# Create a memory
await enhanced_memory_service.create_memory(
    user_id="user123",
    memory_id="mem001",
    text="I love programming in Python",
    memory_type="fact",
    priority="high",
    category="programming"
)
```

### Global Recall

```python
# Perform global recall
results = await enhanced_memory_service.global_recall(
    user_id="user123",
    query="programming Python"
)

print(f"Found {results['total_recall_items']} items")
```

### Session Persistence

```python
# Persist session data
session_data = {
    "messages": [
        {"role": "user", "content": "I'm working on a new project"},
        {"role": "assistant", "content": "That sounds exciting!"}
    ],
    "timestamp": "2024-01-01T00:00:00Z"
}

await enhanced_memory_service.persist_session(
    user_id="user123",
    session_id="session456",
    session_data
)
```

## 🚨 Troubleshooting

### Common Issues

1. **Pinecone Connection Failed**
   - Check API key and index configuration
   - Verify dimensions match (1536)
   - Ensure index exists and is accessible

2. **Neo4j Connection Failed**
   - Check URI format and credentials
   - Verify AuraDB instance is running
   - Check network connectivity

3. **Memory Operations Failing**
   - Verify user exists in both systems
   - Check memory ID format
   - Ensure proper authentication

### Debug Commands

```bash
# Check service health
curl -X GET "http://localhost:8000/api/enhanced-memory/health"

# Get database stats
curl -X GET "http://localhost:8000/api/enhanced-memory/stats"

# Test user profile
curl -X GET "http://localhost:8000/api/enhanced-memory/users/test_user/profile"
```

## 📊 Monitoring

### Health Checks

The system provides comprehensive health monitoring:

- **Pinecone**: Connection status, index stats
- **Neo4j**: Database connectivity, node/relationship counts
- **Redis**: Cache performance, session management
- **MongoDB**: Collection health, query performance

### Metrics

Key metrics to monitor:

- Memory creation/retrieval latency
- Vector similarity scores
- Knowledge graph relationship counts
- Session persistence success rates
- Global recall accuracy

## 🔒 Security

### Authentication

All endpoints require authentication via JWT tokens:

```python
# Include in request headers
Authorization: Bearer <your-jwt-token>
```

### Data Privacy

- User data is isolated by user ID
- Pinecone namespaces prevent cross-user access
- Neo4j relationships are user-scoped
- All operations are logged for audit

## 🚀 Performance

### Optimization Tips

1. **Batch Operations**: Use batch upsert for multiple vectors
2. **Caching**: Leverage Redis for frequently accessed data
3. **Indexing**: Ensure proper database indexes
4. **Connection Pooling**: Configure connection limits

### Scaling

- **Pinecone**: Serverless scaling based on usage
- **Neo4j**: AuraDB auto-scaling
- **Redis**: Cluster mode for high availability
- **MongoDB**: Atlas auto-scaling

## 📚 Additional Resources

- [Pinecone Documentation](https://docs.pinecone.io/)
- [Neo4j AuraDB Documentation](https://neo4j.com/cloud/aura/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/docs/)

## 🤝 Support

For issues or questions:

1. Check the troubleshooting section
2. Review the test scripts
3. Check service health endpoints
4. Review application logs

The enhanced memory system is designed to be robust, scalable, and easy to use. With proper configuration, it provides powerful memory management capabilities across all your applications.
