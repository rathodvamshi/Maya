"""Neo4j services: async (for FastAPI) and sync (for Celery worker)."""

import uuid
import logging
from typing import Optional, Dict, Any, List

from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase, Driver

from app.config import settings

logger = logging.getLogger(__name__)


class Neo4jService:
    _driver: Optional[AsyncDriver] = None

    async def connect(self):
        if self._driver:
            return
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            await self._driver.verify_connectivity()
        except Exception as e:
            logger.error(f"❌ Neo4j async connect failed: {e}")
            self._driver = None

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        if not self._driver:
            logger.error("Neo4j driver not available.")
            return None
        try:
            async with self._driver.session() as session:
                result = await session.run(query, parameters or {})
                return [record.data() async for record in result]
        except Exception as e:
            logger.error(f"Neo4j async query failed: {e}")
            return None

    async def create_user_node(self, user_id: str):
        if not self._driver:
            await self.connect()
        if not self._driver:
            return
        query = "MERGE (u:User {id: $user_id}) SET u.name = coalesce(u.name, $name)"
        await self.run_query(query, {"user_id": user_id, "name": f"User_{user_id}"})

    async def get_user_facts(self, user_id: str) -> str:
        if not self._driver:
            await self.connect()
        if not self._driver:
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

        async with self._driver.session() as session:
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

# --- New: synchronous service for Celery worker (no asyncio in worker) ---
class Neo4jSyncService:
    _driver: Optional[Driver] = None

    def connect(self):
        if self._driver:
            return
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            self._driver.verify_connectivity()
        except Exception as e:
            logger.error(f"❌ Neo4j sync connect failed: {e}")
            self._driver = None

    def close(self):
        if self._driver:
            self._driver.close()

    def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        if not self._driver:
            logger.error("Neo4j sync driver not available.")
            return None
        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [r.data() for r in result]
        except Exception as e:
            logger.error(f"Neo4j sync query failed: {e}")
            return None

    def add_entities_and_relationships_sync(self, facts: Dict[str, Any]):
        entities = facts.get("entities", [])
        relationships = facts.get("relationships", [])
        if not self._driver:
            logger.error("Neo4j sync driver not available. Cannot add entities.")
            return
        with self._driver.session() as session:
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
        with self._driver.session() as session:
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
        with self._driver.session() as session:
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
            with self._driver.session() as session:
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

neo4j_service = Neo4jService()
neo4j_sync_service = Neo4jSyncService()