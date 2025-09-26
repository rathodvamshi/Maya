# backend/app/routers/health.py
from fastapi import APIRouter, HTTPException
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from app.services.neo4j_service import neo4j_service
from app.services.redis_service import redis_client
from app.services.pinecone_service import pinecone_service

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)

@router.get("/")
async def health_check():
    """
    Checks the status of critical services.
    """
    # Attempt to self-heal transient startup timing by initializing services if needed
    try:
        if not pinecone_service.is_ready():
            pinecone_service.initialize_pinecone()
    except Exception:
        pass

    try:
        if not neo4j_service._driver:
            await neo4j_service.connect()
    except Exception:
        pass

    services_status = {
        "neo4j": "operational",
        "redis": "operational",
        "pinecone": "operational" if pinecone_service.is_ready() else "down",
    }
    
    # Check Neo4j
    if not neo4j_service._driver:
        services_status["neo4j"] = "down"
    else:
        try:
            await neo4j_service._driver.verify_connectivity()
        except Exception:
            services_status["neo4j"] = "down"
    
    # Check Redis
    try:
        await redis_client.ping()
    except Exception:
        services_status["redis"] = "down"

    is_healthy = all(status == "operational" for status in services_status.values())

    if not is_healthy:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "One or more services are unavailable", "services": services_status},
        )

    return {"status": "All services are operational", "services": services_status}
