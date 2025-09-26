# backend/app/services/pinecone_service.py

import logging
from typing import Optional, Any, List, Dict, Tuple
from app.config import settings
from app.services.embedding_service import create_embedding

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Global Pinecone state
# =====================================================
pc: Optional[Any] = None
index = None
PINECONE_INDEX_NAME = settings.PINECONE_INDEX or "maya2-session-memory"
# This dimension MUST match your embedding model. Gemini's text-embedding-004 is 768.
REQUIRED_DIMENSION = 768

# =====================================================
# 🔹 Initialize Pinecone
# =====================================================
def initialize_pinecone():
    """
    Initializes the Pinecone client and index. Called once on app startup.
    It will automatically delete and recreate the index if the dimension is wrong.
    """
    global pc, index
    if not settings.PINECONE_API_KEY:
        logger.warning("⚠️ Pinecone API key not found. Pinecone service will be disabled.")
        return

    try:
        # Attempt modern v3 import first; if fails, inspect module for legacy shape
        try:
            from pinecone import Pinecone, ServerlessSpec  # type: ignore
            sdk_version = "v3"
            pc_obj = Pinecone(api_key=settings.PINECONE_API_KEY)
        except Exception as v3_err:  # noqa: BLE001
            import importlib
            try:
                pinecone_mod = importlib.import_module("pinecone")  # type: ignore
            except Exception as import_err:  # noqa: BLE001
                raise RuntimeError(
                    "Pinecone module import failed entirely. Install with 'pip install pinecone-client>=3'"
                    f" (v3 error: {v3_err}; import error: {import_err})"
                )

            # Identify legacy vs unexpected shapes
            has_init = hasattr(pinecone_mod, "init")
            has_index_attr = hasattr(pinecone_mod, "Index")
            if has_init and has_index_attr:
                try:
                    pinecone_mod.init(
                        api_key=settings.PINECONE_API_KEY,
                        environment=(settings.PINECONE_ENVIRONMENT or "us-east-1"),
                    )
                    sdk_version = "v2"
                    pc_obj = pinecone_mod
                except Exception as v2_err:  # noqa: BLE001
                    raise RuntimeError(
                        "Legacy Pinecone module present but initialization failed. Upgrade with 'pip install --upgrade pinecone-client'"
                        f" (v3 err: {v3_err}; v2 err: {v2_err})"
                    )
            else:
                exported = dir(pinecone_mod)
                raise RuntimeError(
                    "Unrecognized pinecone module shape. Expected v3 (Pinecone class) or v2 (init function). "
                    f"Found attributes: {exported[:25]}...  Install/upgrade with: pip install --upgrade 'pinecone-client>=3,<4'"
                )

        logger.info(f"Initializing Pinecone using {sdk_version} client path")
        create_new_index = False

        if sdk_version == "v3":
            existing = pc_obj.list_indexes()
            existing_names = existing.names() if hasattr(existing, "names") else [getattr(i, "name", None) for i in existing or []]
            if PINECONE_INDEX_NAME in existing_names:
                index_description = pc_obj.describe_index(PINECONE_INDEX_NAME)
                dim = getattr(index_description, "dimension", None) or (index_description.get("dimension") if isinstance(index_description, dict) else None)
                if dim != REQUIRED_DIMENSION:
                    logger.warning(f"Index '{PINECONE_INDEX_NAME}' wrong dimension {dim}; recreating")
                    pc_obj.delete_index(PINECONE_INDEX_NAME)
                    create_new_index = True
            else:
                create_new_index = True
            if create_new_index:
                pc_obj.create_index(
                    name=PINECONE_INDEX_NAME,
                    dimension=REQUIRED_DIMENSION,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region=(settings.PINECONE_ENVIRONMENT or "us-east-1")),
                )
            bound_index = pc_obj.Index(PINECONE_INDEX_NAME)
        else:  # v2
            # v2 uses list_indexes() -> list, describe_index(index_name) returns dict with 'dimension'
            existing = pc_obj.list_indexes() or []
            if PINECONE_INDEX_NAME in existing:
                desc = pc_obj.describe_index(PINECONE_INDEX_NAME) or {}
                dim = desc.get("dimension")
                if dim != REQUIRED_DIMENSION:
                    logger.warning(f"Index '{PINECONE_INDEX_NAME}' wrong dimension {dim}; recreating")
                    pc_obj.delete_index(PINECONE_INDEX_NAME)
                    create_new_index = True
            else:
                create_new_index = True
            if create_new_index:
                pc_obj.create_index(PINECONE_INDEX_NAME, dimension=REQUIRED_DIMENSION, metric="cosine")
            bound_index = pc_obj.Index(PINECONE_INDEX_NAME)

        # Assign globals
        pc = pc_obj
        index = bound_index
        logger.info(f"✅ Pinecone index ready: '{PINECONE_INDEX_NAME}' (sdk {sdk_version})")
    except Exception as e:  # noqa: BLE001
        logger.error(f"❌ Error initializing Pinecone: {e}")
        pc = None
        index = None

# =====================================================
# 🔹 Internal Helper: Ensure Index Ready
# =====================================================
def _ensure_index_ready():
    """Internal helper to re-attempt initialization if the index is not ready."""
    if index is None:
        logger.warning("⚠️ Pinecone index was not initialized on startup, attempting again...")
        initialize_pinecone()
    return index is not None

# =====================================================
# 🔹 Upsert Session Summary
# =====================================================
def upsert_session_summary(session_id: str, summary: str):
    """Upserts a session summary embedding into Pinecone."""
    if not _ensure_index_ready():
        logger.error("❌ Pinecone index unavailable. Skipping upsert.")
        return
    try:
        embedding = create_embedding(summary)
        if embedding:
            index.upsert(vectors=[(session_id, embedding, {"summary": summary})])
            logger.info(f"✅ Upserted summary for session {session_id}.")
    except Exception as e:
        logger.error(f"❌ Failed to upsert summary: {e}")

# =====================================================
# 🔹 Query Relevant Summary
# =====================================================
def query_relevant_summary(text: str, top_k: int = 1) -> str | None:
    """Finds the most relevant summary for a given text."""
    if not _ensure_index_ready():
        logger.error("❌ Pinecone index unavailable. Cannot query.")
        return None
    try:
        embedding = create_embedding(text)
        if not embedding:
            logger.warning("⚠️ Failed to create embedding for query.")
            return None
        
        results = index.query(vector=embedding, top_k=top_k, include_metadata=True)
        matches = (
            getattr(results, "matches", None)
            if not isinstance(results, dict)
            else results.get("matches", [])
        )
        if matches is None:
            matches = []
        if matches:
            best = matches[0]
            score = getattr(best, "score", None)
            md = getattr(best, "metadata", None)
            if score is None and isinstance(best, dict):
                score = best.get("score", 0)
                md = best.get("metadata")
            if (score or 0) > 0.75 and md:
                if isinstance(md, dict):
                    return md.get("summary")
                # Some SDKs may return metadata-like objects; fallback to str
                return str(md)
        return None
    except Exception as e:
        logger.error(f"❌ Query to Pinecone failed: {e}")
        return None

# =====================================================
# 🔹 Singleton-like Export for Compatibility
# =====================================================
class PineconeService:
    initialize_pinecone = staticmethod(initialize_pinecone)
    upsert_session_summary = staticmethod(upsert_session_summary)
    query_relevant_summary = staticmethod(query_relevant_summary)
    @staticmethod
    def is_ready() -> bool:
        return index is not None
    @staticmethod
    def get_index():
        return index

pinecone_service = PineconeService()

# =====================================================
# 🔹 New: Message-level Embeddings API
# =====================================================
def upsert_message_embedding(user_id: str, session_id: str, text: str, role: str, timestamp: str):
    """
    Upsert a single message embedding for later per-user semantic recall.
    - id format: f"{user_id}:{session_id}:{timestamp}:{role}"
    - metadata: includes user_id, session_id, role, timestamp, and text (for recall)
    """
    if not _ensure_index_ready():
        logger.debug("Pinecone index not ready; skipping message upsert.")
        return
    if not text:
        return

    try:
        emb = create_embedding(text)
        if not emb:
            return
        vid = f"{user_id}:{session_id}:{timestamp}:{role}"
        meta = {
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "timestamp": timestamp,
            "text": text,
            "kind": "message",
        }
        index.upsert(vectors=[(vid, emb, meta)])
    except Exception as e:
        logger.debug(f"Pinecone message upsert failed: {e}")


def upsert_user_fact_embedding(user_id: str, fact_text: str, timestamp: str, category: str = "generic"):
    """Upsert a semantic embedding representing a stable user fact/preference.

    ID format: user:{user_id}:fact:{hash_prefix}  (hash = deterministic over text)
    Metadata includes scope/kind to allow filtered queries distinct from messages.
    """
    if not _ensure_index_ready() or not fact_text:
        return
    try:
        import hashlib
        emb = create_embedding(fact_text)
        if not emb:
            return
        h = hashlib.sha1(fact_text.encode("utf-8")).hexdigest()[:12]
        vid = f"user:{user_id}:fact:{h}"
        meta = {
            "user_id": user_id,
            "session_id": "",  # not session-bound
            "role": "fact",
            "timestamp": timestamp,
            "text": fact_text,
            "kind": "user_fact",
            "category": category,
        }
        index.upsert(vectors=[(vid, emb, meta)])
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Pinecone user_fact upsert failed: {e}")


def bulk_upsert(payloads: List[Dict[str, Any]]):
    """Bulk upsert heterogeneous payloads from the embedding queue.

    Supports kinds: message, user_fact
    Each payload must contain: user_id, text, timestamp, kind.
    """
    if not _ensure_index_ready():
        return
    vectors: List[Tuple[str, List[float], Dict[str, Any]]] = []
    try:
        import hashlib
        for item in payloads:
            text = item.get("text")
            if not text:
                continue
            emb = create_embedding(text)
            if not emb:
                continue
            kind = item.get("kind") or item.get("role") or "message"
            user_id = item.get("user_id", "")
            ts = item.get("timestamp", "")
            if kind == "user_fact":
                h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
                vid = f"user:{user_id}:fact:{h}"
                meta = {
                    "user_id": user_id,
                    "session_id": "",
                    "role": "fact",
                    "timestamp": ts,
                    "text": text,
                    "kind": "user_fact",
                    "category": item.get("category", "generic"),
                }
            else:
                session_id = item.get("session_id", "")
                role = item.get("role", "user")
                vid = f"{user_id}:{session_id}:{ts}:{role}"
                meta = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": role,
                    "timestamp": ts,
                    "text": text,
                    "kind": "message",
                }
            vectors.append((vid, emb, meta))
        if vectors:
            # Pinecone v2 & v3 both accept list of (id, vector, metadata)
            index.upsert(vectors=vectors)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"bulk_upsert failed: {e}")

__all__ = [
    "pinecone_service",
    "upsert_message_embedding",
    "upsert_user_fact_embedding",
    "query_similar_texts",
    "query_user_facts",
    "bulk_upsert",
]


def query_similar_texts(user_id: str, text: str, top_k: int = 3) -> Optional[str]:
    """
    Query Pinecone for the most similar prior messages for this user and return
    a compact concatenated context string (limited to a few items).
    """
    if not _ensure_index_ready():
        return None


def query_user_facts(user_id: str, hint_text: str, top_k: int = 5) -> List[str]:
    """Return top semantic user_fact snippets (kind=user_fact) for a user.

    hint_text guides the embedding query (can be last user message). We filter by kind=user_fact
    in metadata using supported Pinecone filter syntax.
    """
    if not _ensure_index_ready():
        return []
    try:
        emb = create_embedding(hint_text or user_id)
        if not emb:
            return []
        # Filter: user_id match + kind=user_fact
        res = index.query(
            vector=emb,
            top_k=top_k,
            include_metadata=True,
            filter={"user_id": {"$eq": user_id}, "kind": {"$eq": "user_fact"}},
        )
        matches = (
            getattr(res, "matches", None)
            if not isinstance(res, dict)
            else res.get("matches", [])
        ) or []
        out: List[str] = []
        for m in matches:
            md = getattr(m, "metadata", None)
            if md is None and isinstance(m, dict):
                md = m.get("metadata")
            if isinstance(md, dict):
                txt = md.get("text")
                if txt and txt not in out:
                    out.append(txt)
        return out
    except Exception as e:  # noqa: BLE001
        logger.debug(f"query_user_facts failed: {e}")
        return []
    if not text:
        return None

    try:
        emb = create_embedding(text)
        if not emb:
            return None
        res = index.query(vector=emb, top_k=top_k, include_metadata=True, filter={"user_id": {"$eq": user_id}})
        matches = (
            getattr(res, "matches", None)
            if not isinstance(res, dict)
            else res.get("matches", [])
        )
        if matches is None:
            matches = []
        snippets: list[str] = []
        for m in matches:
            md = getattr(m, "metadata", None)
            if md is None and isinstance(m, dict):
                md = m.get("metadata")
            md = md or {}
            snippet = md.get("text") if isinstance(md, dict) else None
            if snippet:
                snippets.append(snippet)
        return "\n---\n".join(snippets) if snippets else None
    except Exception as e:
        logger.debug(f"Pinecone query_similar_texts failed: {e}")
        return None
