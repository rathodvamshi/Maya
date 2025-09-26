from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.collection import Collection
from datetime import datetime
from app.security import get_current_active_user
from app.database import get_user_collection
from app.services.neo4j_service import neo4j_service
from app.services import redis_service

router = APIRouter(prefix="/api/user", tags=["User"], dependencies=[Depends(get_current_active_user)])


class OnboardingBody(BaseModel):
    name: str | None = None
    region: str | None = None
    preferences: dict | None = None


@router.get("/onboarding-questions")
async def onboarding_questions():
    return {
        "questions": [
            {"id": "name", "q": "What's your preferred name?"},
            {"id": "region", "q": "Which region/country are you in?"},
            {"id": "cuisine", "q": "Any favorite cuisine?"},
        ]
    }


@router.post("/onboarding")
async def onboarding(
    body: OnboardingBody,
    current_user: dict = Depends(get_current_active_user),
    users: Collection = Depends(get_user_collection),
):
    # Update Mongo profile
    profile_update = {k: v for k, v in body.model_dump().items() if v is not None}
    users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"profile": profile_update, "last_seen": datetime.utcnow()}},
    )

    user_id = str(current_user["_id"])
    # Update Neo4j (best-effort), create preferences relations
    try:
        await neo4j_service.create_user_node(user_id)
        if body.name:
            await neo4j_service.run_query(
                "MERGE (u:User {id: $uid}) SET u.name=$name",
                {"uid": user_id, "name": body.name},
            )
        prefs = body.preferences or {}
        for k, v in prefs.items():
            if not v:
                continue
            await neo4j_service.run_query(
                "MERGE (u:User {id:$uid})\n MERGE (p:PREFERENCE {name:$val})\n MERGE (u)-[:LIKES {kind:$kind}]->(p)",
                {"uid": user_id, "val": str(v), "kind": k},
            )
    except Exception:
        pass

    # Cache small profile in Redis for quick personalization
    try:
        cache_key = f"user:{user_id}:recent_profile"
        await redis_service.set_prefetched_data(cache_key, profile_update or {}, ttl_seconds=300)
    except Exception:
        pass

    greeting = f"Welcome {body.name}!" if body.name else "Welcome!"
    return {"status": "ok", "greeting": greeting}
