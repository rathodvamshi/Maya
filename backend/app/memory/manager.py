from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.services import memory_store
from app.services import pinecone_service
from app.services.neo4j_service import neo4j_service
from app.services import memory_service


logger = logging.getLogger(__name__)


class MemoryManager:
    """Unified CRUD over multi-layer memory: Redis, Pinecone, Neo4j, and structured Mongo memories.

    memory_type values:
      - "short-term" => Redis session history/state
      - "long-term"  => Pinecone structured memory vectors + Mongo record
      - "semantic"   => Neo4j node/relations
    """

    # -------- Short-term (Redis) --------
    async def add_memory(self, user_id: str, content: Dict[str, Any], memory_type: str = "short-term", session_id: Optional[str] = None) -> Dict[str, Any]:
        ts = datetime.utcnow().isoformat()
        try:
            if memory_type == "short-term":
                if not session_id:
                    raise ValueError("session_id required for short-term memory")
                msg = content if isinstance(content, dict) else {"role": "user", "content": str(content)}
                await memory_store.append_session_messages(session_id, [msg], max_items=50)
                logger.info(f"[Redis] Added message for user={user_id} session={session_id}")
                return {"ok": True, "ts": ts}

            if memory_type == "long-term":
                title = content.get("title") or content.get("key") or (content.get("value") or "").split(" ")[0][:50]
                doc = await memory_service.create_memory({
                    "user_id": user_id,
                    "title": title or "memory",
                    "value": content.get("value", ""),
                    "type": content.get("type", "fact"),
                    "priority": content.get("priority", "normal"),
                })
                logger.info(f"[Pinecone] Upserted memory '{doc.get('title')}' id={doc.get('_id')}")
                return {"ok": True, "id": doc.get("_id"), "ts": ts}

            if memory_type == "semantic":
                rel = content.get("relation") or content.get("rel") or "REMEMBERS"
                concept = content.get("concept") or content.get("name")
                if not concept:
                    raise ValueError("concept required for semantic memory")
                await neo4j_service.create_relation(user_id, rel, concept)
                logger.info(f"[Neo4j] Created relation (User)-[:{rel}]->(Concept {{name:'{concept}'}})")
                return {"ok": True, "ts": ts}

            raise ValueError("unknown memory_type")
        except Exception as e:
            logger.error(f"add_memory failed: {e}")
            return {"ok": False, "error": str(e)}

    async def get_memory(self, user_id: str, query: Optional[str] = None, memory_type: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if memory_type in (None, "short-term"):
                if session_id:
                    hist = await memory_store.get_session_history(session_id, limit=50)
                else:
                    hist = []
            else:
                hist = []

            pine = []
            if memory_type in (None, "long-term"):
                if query:
                    # Enhanced query with multiple memory types
                    pine = pinecone_service.query_user_memories(user_id, query, top_k=8)
                    
                    # Also get user facts for better context
                    try:
                        user_facts = pinecone_service.query_user_facts(user_id, query, top_k=5)
                        for fact in user_facts:
                            pine.append({
                                "memory_id": f"fact_{hash(fact)}",
                                "similarity": 0.8,  # Default similarity for facts
                                "text": fact,
                                "lifecycle_state": "active",
                                "type": "user_fact"
                            })
                    except Exception as e:
                        logger.debug(f"Failed to get user facts: {e}")
                else:
                    # No query provided -> fall back to latest memories from Mongo for context
                    try:
                        raw = await memory_service.list_memories(user_id, limit=20, lifecycle=["active", "candidate", "distilled"])
                        # Map to a shape similar to query_user_memories entries
                        pine = [
                            {
                                "memory_id": m.get("_id"),
                                "similarity": None,
                                "text": f"{m.get('title')}: {m.get('value','')}",
                                "lifecycle_state": m.get("lifecycle_state"),
                                "type": "structured_memory"
                            }
                            for m in raw
                        ]
                    except Exception:
                        pine = []

            graph = ""
            if memory_type in (None, "semantic"):
                graph = await neo4j_service.get_user_facts(user_id)

            merged: Dict[str, Any] = {
                "history": hist,
                "pinecone": pine,
                "neo4j": graph,
            }
            
            # Log successful memory retrieval
            if pine or graph:
                logger.info(f"Retrieved memories for user {user_id}: "
                           f"pinecone={len(pine)}, neo4j={bool(graph)}, session={session_id}")
            
            return merged
        except Exception as e:
            logger.error(f"get_memory failed: {e}")
            return {"history": [], "pinecone": [], "neo4j": "", "error": str(e)}

    # ---------------- Convenience APIs (KV-style) ----------------
    async def add_kv_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        *,
        memory_type: str = "long-term",
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """Add a simple key/value fact for the user.

        long-term -> stored via memory_service + embedded to Pinecone (user namespace)
        semantic  -> optional mapping to a simple Neo4j relation (User)-[:HAS_{KEY}]->(Value)
        short-term-> no-op here; use add_memory(..., memory_type="short-term") for messages.
        """
        try:
            if not key or not value:
                return {"ok": False, "error": "key and value required"}
            k = str(key).strip()
            v = str(value).strip()
            if memory_type == "long-term":
                doc = await memory_service.create_memory({
                    "user_id": user_id,
                    "title": k,
                    "value": v,
                    "type": "fact",
                    "priority": priority,
                })
                return {"ok": True, "id": doc.get("_id")}
            elif memory_type == "semantic":
                rel = f"HAS_{k.upper()}"
                await neo4j_service.create_relation(user_id, rel, v)
                return {"ok": True}
            elif memory_type == "short-term":
                # For short-term, we store a synthetic assistant note
                await memory_store.append_session_messages(
                    session_id=f"user:{user_id}:kv",
                    messages=[{"role": "assistant", "content": f"{k} = {v}"}],
                    max_items=10,
                )
                return {"ok": True}
            return {"ok": False, "error": "unknown memory_type"}
        except Exception as e:
            logger.error(f"add_kv_memory failed: {e}")
            return {"ok": False, "error": str(e)}

    async def get_profile_value(self, user_id: str, key: str) -> Optional[str]:
        """Fetch a deterministic profile field (e.g., name, timezone)."""
        try:
            from app.services import profile_service
            prof = profile_service.get_profile(user_id)
            val = prof.get(key)
            if isinstance(val, (str, int, float)):
                return str(val)
            return None
        except Exception:
            return None

    async def delete_memory_by_title(self, user_id: str, title: str) -> Dict[str, Any]:
        """Archive memory records with a given title and delete vectors.

        Safe (no hard delete): sets lifecycle_state to archived and removes Pinecone vector.
        """
        try:
            from app.database import get_memories_collection
            coll = get_memories_collection()
            cur = coll.find({"user_id": user_id, "title": title})
            ids = []
            for d in cur:
                mid = str(d.get("_id"))
                ids.append(mid)
                await memory_service.update_memory(user_id, mid, {"lifecycle_state": "archived"}, reason="delete_by_title")
                pinecone_service.delete_user_memory_vectors(user_id, mid)
            return {"ok": True, "count": len(ids), "ids": ids}
        except Exception as e:
            logger.error(f"delete_memory_by_title failed: {e}")
            return {"ok": False, "error": str(e)}

    async def update_memory(self, user_id: str, content: Dict[str, Any], memory_type: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if memory_type == "short-term":
                if not session_id:
                    raise ValueError("session_id required")
                msgs = content.get("messages") or []
                await memory_store.set_session_history(session_id, msgs)
                logger.info(f"[Redis] Updated session history for session={session_id}")
                return {"ok": True}

            if memory_type == "long-term":
                memory_id = content.get("id") or content.get("memory_id")
                if not memory_id:
                    raise ValueError("memory id required")
                updated = await memory_service.update_memory(user_id, memory_id, content)
                ok = bool(updated)
                logger.info(f"[Pinecone] Upserted memory id={memory_id}")
                return {"ok": ok}

            if memory_type == "semantic":
                # For simplicity: allow updating relation target name
                rel = content.get("relation")
                old = content.get("old_concept")
                new = content.get("concept")
                if rel and old and new and old != new:
                    await neo4j_service.delete_relation(user_id, rel, old)
                    await neo4j_service.create_relation(user_id, rel, new)
                    logger.info(f"[Neo4j] Updated relation {rel}: {old} -> {new}")
                    return {"ok": True}
                return {"ok": False, "error": "no-op"}

            raise ValueError("unknown memory_type")
        except Exception as e:
            logger.error(f"update_memory failed: {e}")
            return {"ok": False, "error": str(e)}

    async def delete_memory(self, user_id: str, memory_type: str, identifier: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            if memory_type == "short-term":
                if not session_id:
                    raise ValueError("session_id required")
                await memory_store.delete_session(session_id)
                await memory_store.delete_session_state(session_id)
                logger.info(f"[Redis] Deleted session {session_id}")
                return {"ok": True}

            if memory_type == "long-term":
                if not identifier:
                    raise ValueError("memory id required")
                # Soft delete via lifecycle_state
                await memory_service.update_memory(user_id, identifier, {"lifecycle_state": "archived"}, reason="delete")
                pinecone_service.delete_user_memory_vectors(user_id, identifier)
                logger.info(f"[Pinecone] Deleted vectors for memory id={identifier}")
                return {"ok": True}

            if memory_type == "semantic":
                if not identifier:
                    raise ValueError("concept or rel:concept required")
                if ":" in identifier:
                    rel, concept = identifier.split(":", 1)
                    await neo4j_service.delete_relation(user_id, rel, concept)
                    logger.info(f"[Neo4j] Deleted relation {rel} -> {concept}")
                else:
                    await neo4j_service.delete_concept(identifier)
                    logger.info(f"[Neo4j] Deleted concept {identifier}")
                return {"ok": True}

            raise ValueError("unknown memory_type")
        except Exception as e:
            logger.error(f"delete_memory failed: {e}")
            return {"ok": False, "error": str(e)}


memory_manager = MemoryManager()


