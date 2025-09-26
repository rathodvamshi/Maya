from fastapi import APIRouter, Depends, HTTPException
from pymongo.collection import Collection
from bson import ObjectId
from datetime import datetime
import io, json, zipfile

from app.security import get_current_active_user
from app.database import get_sessions_collection
from app.services.neo4j_service import neo4j_service
from app.services import pinecone_service, redis_service

router = APIRouter(prefix="/api/memories", tags=["Memories"], dependencies=[Depends(get_current_active_user)])


@router.post("/export")
async def export_memories(current_user: dict = Depends(get_current_active_user), sessions: Collection = Depends(get_sessions_collection)):
    user_id = str(current_user["_id"])

    # Gather Mongo sessions
    cur = sessions.find({"userId": current_user["_id"]})
    sessions_data = [{"_id": str(s["_id"]), "title": s.get("title"), "messages": s.get("messages", [])} for s in cur]

    # Neo4j facts (as text bullets)
    facts = await neo4j_service.get_user_facts(user_id)

    # Pinecone metadata cannot be exported without listing; we export a placeholder
    pinecone_meta_note = "Pinecone vectors exist keyed by user_id; raw text may be omitted for privacy."

    blob = {
        "exported_at": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "sessions": sessions_data,
        "neo4j_facts": facts,
        "pinecone": pinecone_meta_note,
    }

    # Zip the JSON for delivery
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("memories.json", json.dumps(blob, ensure_ascii=False, indent=2))
    mem.seek(0)

    from fastapi.responses import StreamingResponse
    headers = {"Content-Disposition": "attachment; filename=memories.zip"}
    return StreamingResponse(mem, media_type="application/zip", headers=headers)


@router.delete("/{user_id}")
async def delete_memories(user_id: str, current_user: dict = Depends(get_current_active_user), sessions: Collection = Depends(get_sessions_collection)):
    # Only allow self-delete unless you have an admin flag (omitted for brevity)
    if user_id != str(current_user.get("_id")):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Delete Mongo sessions
    sessions.delete_many({"userId": current_user["_id"]})

    # Delete Redis keys (best-effort)
    try:
        if redis_service.redis_client:
            await redis_service.redis_client.delete(f"user:{user_id}:recent_profile")
    except Exception:
        pass

    # Delete Pinecone vectors by user prefix: not directly supported via prefix; require filter delete
    try:
        if pinecone_service.is_ready():
            idx = pinecone_service.get_index()
            if idx:
                idx.delete(filter={"user_id": {"$eq": user_id}})
    except Exception:
        pass

    # Delete Neo4j user node and relationships
    try:
        await neo4j_service.run_query("MATCH (u:User {id:$uid}) DETACH DELETE u", {"uid": user_id})
    except Exception:
        pass

    return {"status": "deleted"}
