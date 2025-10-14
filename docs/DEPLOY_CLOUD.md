Cloud-only deployment (no local Redis/Neo4j)

This app can run fully on managed services. Use docker-compose.cloud.yml for production-like deployments without local Redis/Neo4j.

Prereqs
- Docker and docker-compose
- Managed services provisioned:
  - Redis Cloud (TLS): get a rediss:// URL
  - Neo4j Aura (neo4j+s)
  - MongoDB Atlas
  - Pinecone index + API key

Setup backend/.env
Fill these minimal variables (do not commit secrets):
- MONGO_URI=mongodb+srv://USER:PASS@cluster.mongodb.net/DB
- MONGO_DB=assistant_db
- REDIS_URL=rediss://:PASSWORD@HOST:6380/0
- NEO4J_URI=neo4j+s://YOUR_INSTANCE.databases.neo4j.io
- NEO4J_USER=...
- NEO4J_PASSWORD=...
- NEO4J_DATABASE=neo4j
- PINECONE_API_KEY=...
- PINECONE_ENVIRONMENT=us-east-1
- COHERE_API_KEY=...
- GEMINI_API_KEYS=key1,key2

Run
- docker compose -f docker-compose.cloud.yml up --build -d
- Backend: http://localhost:8000 (swagger at /docs)
- Frontend: http://localhost:3000

Health and diagnostics
- GET /health/full for datastore status
- GET /health/ai-status for provider availability
- GET /health/cloud to see masked URLs and pings

Notes
- CORS: set CORS_ORIGINS to your frontend origin(s) in backend/.env
- SMTP is optional; without it, email features are disabled
- For rolling updates, both backend and workers auto-restart unless stopped
