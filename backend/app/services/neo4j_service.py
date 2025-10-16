"""Neo4j services: async (for FastAPI) and sync (for Celery worker).

Enhancements:
 - Added configurable retry & backoff for initial connectivity to smooth over
    container cold starts (especially with Docker compose where app races DB).
    Configure with env vars:
        NEO4J_CONNECT_RETRIES (default 5)
        NEO4J_CONNECT_DELAY_SECS (initial delay, default 0.6)
    Exponential backoff (delay * 1.6 ** attempt) with cap 5s per attempt.
"""

import uuid
import logging
import os
import time
from typing import Optional, Dict, Any, List
import asyncio

from neo4j.exceptions import (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
    Neo4jError,
)

from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase, Driver

from app.config import settings

logger = logging.getLogger(__name__)


class Neo4jService:
    _driver: Optional[AsyncDriver] = None
    _database: Optional[str] = None
    _disabled: bool = False
    _offline: bool = False

    # NOTE: Avoid long-lived pooled sessions with Aura (they can go defunct on idle or re-balance)
    # We'll create short-lived sessions per query for stability.
    _rr_index: int = 0

    # Heartbeat task
    _hb_task: Optional[asyncio.Task] = None
    _hb_interval_secs: int = 60  # check every 60s to refresh connections proactively

    AURA_SECURE_URI: str = "neo4j+s://bb2cd868.databases.neo4j.io"

    def _ensure_secure_uri(self) -> str:
        """Always use the secure Aura URI for TLS as required."""
        # Even if settings overrides, enforce secure Aura endpoint per instruction
        return self.AURA_SECURE_URI

    def _is_transient_error(self, e: Exception) -> bool:
        msg = str(e) if e else ""
        if isinstance(e, (ServiceUnavailable, SessionExpired, TransientError, ConnectionResetError)):
            return True
        # Fallback on message patterns
        lowered = msg.lower()
        if any(s in lowered for s in [
            "defunct connection",
            "unable to retrieve routing information",
            "closed while sending",
            "connection reset",
            "host not available",
        ]):
            return True
        # Some Neo4jError subclasses can be transient (code starting with 'Neo.ClientError.Security' etc.)
        if isinstance(e, Neo4jError):
            # Treat some as transient just to be safe for reconnect logic
            if any(x in lowered for x in ["routing", "service unavailable", "session expired"]):
                return True
        return False

    async def _reinitialize_driver(self):
        """Close current driver and re-init along with session pool."""
        # Close previous
        if self._driver:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None
        # No pooled sessions to close (we use short-lived sessions now)
        # Reconnect
        try:
            uri = self._ensure_secure_uri()
            self._driver = AsyncGraphDatabase.driver(
                uri,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                # Tuning to avoid defunct connections lingering
                max_connection_pool_size=10,
                connection_acquisition_timeout=15,
                max_connection_lifetime=300,   # recycle connections every 5 minutes
                max_transaction_retry_time=30, # retry transactions up to 30s
                connection_timeout=10,
            )
            await self._driver.verify_connectivity()
            try:
                self._database = getattr(settings, "NEO4J_DATABASE", None) or None
            except Exception:
                self._database = None
            self._offline = False
            logger.info("✅ Neo4j reconnected successfully.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to reinitialize Neo4j driver: {e}")
            self._offline = True

    async def connect(self, retries: Optional[int] = None):
        """Attempt to establish async driver with retry/backoff.

        Called on FastAPI startup; non-blocking within a short bounded window.
        """
        if self._driver:
            return
        # Resolve retry settings
        if retries is None:
            try:
                retries = int(os.getenv("NEO4J_CONNECT_RETRIES", "5"))
            except ValueError:
                retries = 5
        base_delay = float(os.getenv("NEO4J_CONNECT_DELAY_SECS", "0.6"))

        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                uri = self._ensure_secure_uri()
                self._driver = AsyncGraphDatabase.driver(
                    uri,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                    max_connection_pool_size=10,
                    connection_acquisition_timeout=15,
                    max_connection_lifetime=300,
                    max_transaction_retry_time=30,
                    connection_timeout=10,
                )
                await self._driver.verify_connectivity()
                # Capture explicit database if provided
                try:
                    self._database = getattr(settings, "NEO4J_DATABASE", None) or None
                except Exception:
                    self._database = None
                self._offline = False
                if attempt > 0:
                    logger.info(f"Neo4j async connected after retry attempt={attempt}")
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
                # Ensure driver closed before retry
                if self._driver:
                    try:
                        await self._driver.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._driver = None
                # Compute backoff delay (skip sleep after final attempt)
                if attempt < retries - 1:
                    delay = min(base_delay * (1.6 ** attempt), 5.0)
                    logger.warning(
                        f"Neo4j async connect retry attempt={attempt+1}/{retries} in {delay:.2f}s: {e}"
                    )
                    try:
                        await asyncio.sleep(delay)
                    except Exception:  # noqa: BLE001
                        break
        # Exhausted retries
        if last_err:
            logger.warning(f"⚠️ Neo4j async connect failed after {retries} attempts: {last_err}")
            logger.warning("❌ Neo4j functionality disabled for this session")
            self._disabled = True
            self._offline = True
        else:
            logger.warning("⚠️ Neo4j async connect failed: unknown error")
            logger.warning("❌ Neo4j functionality disabled for this session")
            self._disabled = True
            self._offline = True
        
    

    async def close(self):
        # Stop heartbeat
        await self.stop_heartbeat()
        # No pooled sessions to close
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        if self._disabled:
            return None
        if not self._driver:
            return None
        attempts = 4
        backoffs = [0.5, 1, 2, 4]
        last_err: Optional[Exception] = None
        for i in range(attempts):
            try:
                # Always use a short-lived session to avoid defunct pooled sessions
                async with self._driver.session(database=self._database) as session2:
                    result = await session2.run(query, parameters or {})
                    return [record.data() async for record in result]
            except Exception as e:
                last_err = e
                is_transient = self._is_transient_error(e)
                if is_transient:
                    logger.warning("⚠️ Neo4j connection dropped, reinitializing driver...")
                    self._offline = True
                    # If routing table failed, explicitly verify connectivity before retry
                    try:
                        if self._driver:
                            await self._driver.verify_connectivity()
                        else:
                            await self._reinitialize_driver()
                    except Exception:
                        await self._reinitialize_driver()
                    # retry after backoff
                    if i < attempts - 1:
                        await asyncio.sleep(backoffs[i])
                        continue
                # Non-transient or exhausted
                logger.error(f"Neo4j async query failed: {e}")
                break
        return None

    async def create_user_node(self, user_id: str):
        if self._disabled:
            return
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return
        query = "MERGE (u:User {id: $user_id}) SET u.name = coalesce(u.name, $name)"
        await self.run_query(query, {"user_id": user_id, "name": f"User_{user_id}"})

    async def get_user_facts(self, user_id: str) -> str:
        if self._disabled:
            return ""
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return ""
        # Relationship-based facts
        rel_query = (
            "MATCH (u:User {id: $user_id})-[r]->(n) "
            "WHERE n.name IS NOT NULL "
            "RETURN type(r) AS rel, n.name AS name LIMIT 50"
        )
        rows = await self.run_query(rel_query, {"user_id": user_id}) or []

        # Also include the user's own stored name (if present) as a fact
        name_row = await self.run_query(
            "MATCH (u:User {id: $user_id}) RETURN u.name AS name LIMIT 1",
            {"user_id": user_id},
        ) or []
        if name_row and name_row[0].get("name"):
            rows = [{"rel": "IS_NAMED", "name": name_row[0]["name"]}] + rows

        if not rows:
            return ""
        return "; ".join(
            f"{row['rel']} -> {row['name']}" for row in rows if row.get("rel") and row.get("name")
        )

    async def update_fact(self, fact_id: str, correction: str, user_id: str):
        if not self._driver:
            logger.error("Neo4j driver not available.")
            return
        if not correction or correction.lower() == "delete":
            query = """
            MATCH (u:User {id: $user_id})-[r]->(n)
            WHERE r.fact_id = $fact_id
            DELETE r
            """
            await self.run_query(query, {"user_id": user_id, "fact_id": fact_id})
        else:
            query = """
            MATCH (u:User {id: $user_id})-[r]->(n)
            WHERE r.fact_id = $fact_id
            SET n.name = $correction
            """
            await self.run_query(query, {"user_id": user_id, "fact_id": fact_id, "correction": correction})

    async def add_entities_and_relationships(self, facts: Dict[str, Any]):
        """Adds structured facts to the knowledge graph (async version for FastAPI)."""
        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])
        if not self._driver:
            logger.error("Neo4j driver not available. Cannot add entities.")
            return

        async with self._driver.session(database=self._database) as session:
            async with await session.begin_transaction() as tx:
                # Entities
                for entity in entities:
                    label = "".join(filter(str.isalnum, entity.get("label", "Thing")))
                    name = entity.get("name")
                    if not name:
                        continue
                    await tx.run(f"MERGE (n:{label} {{name: $name}})", name=name)

                # Relationships (assign stable fact_id on create)
                for rel in relationships:
                    rel_type = "".join(filter(str.isalnum, rel.get("type", "RELATED_TO"))).upper()
                    source_name = rel.get("source")
                    target_name = rel.get("target")
                    if not source_name or not target_name:
                        continue
                    rid = str(uuid.uuid4())
                    await tx.run(
                        f"""
                        MATCH (source {{name: $source_name}}), (target {{name: $target_name}})
                        MERGE (source)-[r:{rel_type}]->(target)
                        ON CREATE SET r.fact_id = $rid
                        """,
                        source_name=source_name,
                        target_name=target_name,
                        rid=rid,
                    )

    async def upsert_user_preference(self, user_id: str, label: str, pref_type: str = "HOBBY"):
        """Create (User)-[:PREFERS {type: pref_type}]->(Preference {name: label}) edge (async)."""
        if not self._driver:
            await self.connect()
        if not self._driver or not label:
            return
        query = (
            "MERGE (u:User {id: $uid}) "
            "MERGE (p:Preference {name: $label}) "
            "MERGE (u)-[r:PREFERS]->(p) "
            "ON CREATE SET r.pref_type = $ptype, r.created_at = timestamp() "
            "ON MATCH SET r.pref_type = coalesce(r.pref_type, $ptype)"
        )
        try:
            await self.run_query(query, {"uid": user_id, "label": label, "ptype": pref_type})
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Async upsert_user_preference failed: {e}")

    async def ping(self) -> bool:
        try:
            if not self._driver:
                await self.connect(retries=1)
            if not self._driver:
                return False
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def _heartbeat_loop(self):
        while True:
            try:
                await asyncio.sleep(self._hb_interval_secs)
                if not self._driver:
                    continue
                # Use a tiny direct call to ensure driver+routing is OK
                try:
                    await self._driver.verify_connectivity()
                except Exception:
                    await self._reinitialize_driver()
                res = await self.run_query("RETURN 1 AS heartbeat")
                if res is None:
                    # run_query already attempted reinit; if still None, remain offline
                    continue
                if self._offline:
                    logger.info("✅ Neo4j reconnected successfully.")
                    self._offline = False
            except asyncio.CancelledError:
                break
            except Exception:
                # swallow to never crash app due to heartbeat
                pass

    async def start_heartbeat(self):
        if self._hb_task and not self._hb_task.done():
            return
        # Start periodic heartbeat
        self._hb_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self):
        if self._hb_task and not self._hb_task.done():
            self._hb_task.cancel()
            try:
                await self._hb_task
            except Exception:
                pass
        self._hb_task = None

# --- New: synchronous service for Celery worker (no asyncio in worker) ---
class Neo4jSyncService:
    _driver: Optional[Driver] = None
    _database: Optional[str] = None
    AURA_SECURE_URI: str = "neo4j+s://bb2cd868.databases.neo4j.io"

    def _ensure_secure_uri(self) -> str:
        return self.AURA_SECURE_URI

    def connect(self, retries: Optional[int] = None):
        if self._driver:
            return
        if retries is None:
            try:
                retries = int(os.getenv("NEO4J_CONNECT_RETRIES", "5"))
            except ValueError:
                retries = 5
        base_delay = float(os.getenv("NEO4J_CONNECT_DELAY_SECS", "0.6"))
        last_err: Optional[Exception] = None
        for attempt in range(retries):
            try:
                uri = self._ensure_secure_uri()
                self._driver = GraphDatabase.driver(
                    uri,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                    max_connection_pool_size=10,
                    connection_acquisition_timeout=15,
                    max_connection_lifetime=300,
                    max_transaction_retry_time=30,
                    connection_timeout=10,
                )
                self._driver.verify_connectivity()
                try:
                    self._database = getattr(settings, "NEO4J_DATABASE", None) or None
                except Exception:
                    self._database = None
                if attempt > 0:
                    logger.info(f"Neo4j async connected after retry attempt={attempt}")
                logger.info("✅ Connected to Neo4j successfully")
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
                if self._driver:
                    try:
                        self._driver.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._driver = None
                if attempt < retries - 1:
                    delay = min(base_delay * (1.6 ** attempt), 5.0)
                    logger.warning(
                        f"Neo4j sync connect retry attempt={attempt+1}/{retries} in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
        if last_err:
            logger.error(f"❌ Neo4j sync connect failed after {retries} attempts: {last_err}")
        else:
            logger.error("❌ Neo4j sync connect failed: unknown error")

    def close(self):
        if self._driver:
            self._driver.close()

    def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return None
        attempts = 3
        backoffs = [1, 2, 4]
        last_err: Optional[Exception] = None
        for i in range(attempts):
            try:
                with self._driver.session(database=self._database) as session:
                    result = session.run(query, parameters or {})
                    return [r.data() for r in result]
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                is_transient = isinstance(e, (ServiceUnavailable, SessionExpired, TransientError, ConnectionResetError)) or (
                    any(x in msg for x in ["defunct connection", "unable to retrieve routing information", "connection reset"]) )
                if is_transient:
                    logger.warning("⚠️ Neo4j connection dropped, reinitializing driver...")
                    # Re-init driver
                    try:
                        if self._driver:
                            self._driver.close()
                    except Exception:
                        pass
                    self._driver = None
                    self.connect(retries=1)
                    if i < attempts - 1:
                        time.sleep(backoffs[i])
                        continue
                logger.error(f"Neo4j sync query failed: {e}")
                break
        return None

    def add_entities_and_relationships_sync(self, facts: Dict[str, Any]):
        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])
        if not self._driver:
            logger.error("Neo4j sync driver not available. Cannot add entities.")
            return
        with self._driver.session(database=self._database) as session:
            with session.begin_transaction() as tx:
                for entity in entities:
                    label = "".join(filter(str.isalnum, entity.get("label", "Thing")))
                    name = entity.get("name")
                    if not name:
                        continue
                    tx.run(f"MERGE (n:{label} {{name: $name}})", name=name)

                for rel in relationships:
                    rel_type = "".join(filter(str.isalnum, rel.get("type", "RELATED_TO"))).upper()
                    source_name = rel.get("source")
                    target_name = rel.get("target")
                    if not source_name or not target_name:
                        continue
                    rid = str(uuid.uuid4())
                    tx.run(
                        f"""
                        MATCH (source {{name: $source_name}}), (target {{name: $target_name}})
                        MERGE (source)-[r:{rel_type}]->(target)
                        ON CREATE SET r.fact_id = $rid
                        """,
                        source_name=source_name,
                        target_name=target_name,
                        rid=rid,
                    )
                tx.commit()

    def upsert_user_preference_sync(self, user_id: str, label: str, pref_type: str = "HOBBY"):
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return
        if not label:
            return
        with self._driver.session(database=self._database) as session:
            try:
                session.run(
                    """
                    MERGE (u:User {id: $uid})
                    MERGE (p:Preference {name: $label})
                    MERGE (u)-[r:PREFERS]->(p)
                    ON CREATE SET r.pref_type = $ptype, r.created_at = timestamp()
                    ON MATCH SET r.pref_type = coalesce(r.pref_type, $ptype)
                    """,
                    uid=user_id,
                    label=label,
                    ptype=pref_type,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Sync upsert_user_preference failed: {e}")

    def update_fact_sync(self, fact_id: str, correction: str, user_id: str):
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return
        with self._driver.session(database=self._database) as session:
            if not correction or correction.lower() == "delete":
                session.run(
                    """
                    MATCH (u:User {id: $user_id})-[r]->(n)
                    WHERE r.fact_id = $fact_id
                    DELETE r
                    """,
                    user_id=user_id,
                    fact_id=fact_id,
                )
            else:
                session.run(
                    """
                    MATCH (u:User {id: $user_id})-[r]->(n)
                    WHERE r.fact_id = $fact_id
                    SET n.name = $correction
                    """,
                    user_id=user_id,
                    fact_id=fact_id,
                    correction=correction,
                )

    def get_user_facts_sync(self, user_id: str) -> str:
        """Return semi-colon separated relationship facts for a user (sync)."""
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return ""
        try:
            with self._driver.session(database=self._database) as session:
                rel_query = (
                    "MATCH (u:User {id: $user_id})-[r]->(n) "
                    "WHERE n.name IS NOT NULL "
                    "RETURN type(r) AS rel, n.name AS name LIMIT 50"
                )
                rows = session.run(rel_query, {"user_id": user_id})
                data = [r.data() for r in rows]
                # Include user name if set
                name_res = session.run(
                    "MATCH (u:User {id: $uid}) RETURN u.name AS name LIMIT 1", {"uid": user_id}
                )
                name_list = [r.get("name") for r in name_res if r.get("name")]
                if name_list:
                    data = [{"rel": "IS_NAMED", "name": name_list[0]}] + data
                if not data:
                    return ""
                return "; ".join(
                    f"{row['rel']} -> {row['name']}" for row in data if row.get("rel") and row.get("name")
                )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"get_user_facts_sync failed: {e}")
            return ""

    # --- Memory graph helpers for Celery pipeline ---
    def create_memory_node(self, memory_id: str, text: str, pinecone_id: str, created_at: str, snippet: str | None = None):
        """Create Memory node with minimal properties."""
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return
        with self._driver.session(database=self._database) as session:
            session.run(
                """
                MERGE (m:Memory {id: $mid})
                ON CREATE SET m.text=$text, m.pinecone_id=$pid, m.created_at=$cat, m.snippet=$snip
                ON MATCH SET m.text=coalesce($text, m.text), m.snippet=coalesce($snip, m.snippet), m.updated_at=datetime()
                """,
                mid=memory_id,
                text=text,
                pid=pinecone_id,
                cat=created_at,
                snip=snippet or (text[:200] if text else None),
            )

    def connect_user_to_memory(self, user_id: str, memory_id: str):
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return
        with self._driver.session(database=self._database) as session:
            session.run(
                """
                MERGE (u:User {id:$uid})
                MERGE (m:Memory {id:$mid})
                MERGE (u)-[r:HAS_MEMORY]->(m)
                ON CREATE SET r.created_at = datetime()
                ON MATCH SET r.updated_at = datetime()
                """,
                uid=user_id,
                mid=memory_id,
            )

    # --- CRUD helpers ---
    async def create_relation(self, user_id: str, rel_type: str, concept: str) -> None:
        if not self._driver:
            await self.connect()
        if not self._driver or not rel_type or not concept:
            return
        rel = "".join(filter(str.isalnum, rel_type)).upper()
        await self.run_query(
            """
            MERGE (u:User {id: $uid})
            MERGE (c:Concept {name: $name})
            MERGE (u)-[:%s]->(c)
            """ % rel,
            {"uid": user_id, "name": concept},
        )

    async def delete_relation(self, user_id: str, rel_type: str, concept: str) -> None:
        if not self._driver:
            await self.connect()
        if not self._driver or not rel_type or not concept:
            return
        rel = "".join(filter(str.isalnum, rel_type)).upper()
        await self.run_query(
            """
            MATCH (u:User {id: $uid})-[r:%s]->(c:Concept {name: $name})
            DELETE r
            """ % rel,
            {"uid": user_id, "name": concept},
        )

    async def get_relations(self, user_id: str, rel_type: str) -> List[str]:
        if not self._driver:
            await self.connect()
        if not self._driver or not rel_type:
            return []
        rel = "".join(filter(str.isalnum, rel_type)).upper()
        rows = await self.run_query(
            """
            MATCH (u:User {id: $uid})-[r:%s]->(c)
            RETURN c.name AS name
            ORDER BY c.name ASC
            """ % rel,
            {"uid": user_id},
        )
        return [r.get("name") for r in (rows or []) if r.get("name")]

    async def delete_concept(self, concept: str) -> None:
        if not self._driver:
            await self.connect()
        if not self._driver or not concept:
            return
        await self.run_query(
            """
            MATCH (c:Concept {name: $name})
            DETACH DELETE c
            """,
            {"name": concept},
        )

neo4j_service = Neo4jService()
neo4j_sync_service = Neo4jSyncService()