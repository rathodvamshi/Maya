"""
Enhanced Neo4j Service with comprehensive CRUD operations
Supports the new Neo4j AuraDB configuration with proper error handling and global session persistence
"""

import uuid
import logging
import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from neo4j import AsyncGraphDatabase, AsyncDriver, GraphDatabase, Driver

from app.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# 🔹 Enhanced Neo4j Service
# =====================================================
class EnhancedNeo4jService:
    _driver: Optional[AsyncDriver] = None
    _database: Optional[str] = None
    _disabled: bool = False

    async def connect(self, retries: Optional[int] = None):
        """Establish async driver with retry/backoff."""
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
                self._driver = AsyncGraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
                await self._driver.verify_connectivity()
                self._database = getattr(settings, "NEO4J_DATABASE", None) or None
                
                if attempt > 0:
                    logger.info(f"Neo4j async connected after retry attempt={attempt}")
                return
            except Exception as e:
                last_err = e
                if self._driver:
                    try:
                        await self._driver.close()
                    except Exception:
                        pass
                    self._driver = None
                    
                if attempt < retries - 1:
                    delay = min(base_delay * (1.6 ** attempt), 5.0)
                    logger.warning(f"Neo4j async connect retry attempt={attempt+1}/{retries} in {delay:.2f}s: {e}")
                    try:
                        import asyncio
                        await asyncio.sleep(delay)
                    except Exception:
                        break
                        
        if last_err:
            logger.warning(f"⚠️ Neo4j async connect failed after {retries} attempts: {last_err}")
            self._disabled = True
        else:
            logger.warning("⚠️ Neo4j async connect failed: unknown error")
            self._disabled = True

    async def close(self):
        """Close the driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def run_query(self, query: str, parameters: Optional[Dict] = None) -> Optional[List[Dict]]:
        """Execute a Cypher query."""
        if self._disabled:
            return None
        if not self._driver:
            return None
        try:
            async with self._driver.session(database=self._database) as session:
                result = await session.run(query, parameters or {})
                return [record.data() async for record in result]
        except Exception as e:
            logger.error(f"Neo4j async query failed: {e}")
            return None

    # =====================================================
    # 🔹 CRUD Operations - Create
    # =====================================================
    async def create_user(self, user_id: str, name: Optional[str] = None, **properties) -> bool:
        """Create a user node."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            query = """
            MERGE (u:User {id: $user_id})
            SET u.name = coalesce($name, u.name, 'User_' + $user_id),
                u.created_at = coalesce(u.created_at, datetime()),
                u.updated_at = datetime()
            """
            
            # Add any additional properties
            for key, value in properties.items():
                query += f", u.{key} = ${key}"
                
            params = {"user_id": user_id, "name": name, **properties}
            await self.run_query(query, params)
            logger.info(f"✅ Created user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create user {user_id}: {e}")
            return False

    async def create_concept(self, concept_name: str, concept_type: str = "Concept", **properties) -> bool:
        """Create a concept node."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            query = f"""
            MERGE (c:{concept_type} {{name: $name}})
            SET c.created_at = coalesce(c.created_at, datetime()),
                c.updated_at = datetime()
            """
            
            # Add any additional properties
            for key, value in properties.items():
                query += f", c.{key} = ${key}"
                
            params = {"name": concept_name, **properties}
            await self.run_query(query, params)
            logger.info(f"✅ Created concept: {concept_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create concept {concept_name}: {e}")
            return False

    async def create_relationship(self, user_id: str, relationship_type: str, target_name: str, 
                                target_type: str = "Concept", **properties) -> bool:
        """Create a relationship between user and target."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            rel_type = "".join(filter(str.isalnum, relationship_type)).upper()
            query = f"""
            MATCH (u:User {{id: $user_id}})
            MERGE (t:{target_type} {{name: $target_name}})
            MERGE (u)-[r:{rel_type}]->(t)
            SET r.created_at = coalesce(r.created_at, datetime()),
                r.updated_at = datetime()
            """
            
            # Add any additional properties
            for key, value in properties.items():
                query += f", r.{key} = ${key}"
                
            params = {"user_id": user_id, "target_name": target_name, **properties}
            await self.run_query(query, params)
            logger.info(f"✅ Created relationship: {user_id}-[:{rel_type}]->{target_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create relationship: {e}")
            return False

    # =====================================================
    # 🔹 CRUD Operations - Read
    # =====================================================
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information."""
        if self._disabled:
            return None
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return None
            
        try:
            query = "MATCH (u:User {id: $user_id}) RETURN u"
            result = await self.run_query(query, {"user_id": user_id})
            if result:
                return result[0]["u"]
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get user {user_id}: {e}")
            return None

    async def get_user_relationships(self, user_id: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get user relationships."""
        if self._disabled:
            return []
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return []
            
        try:
            if relationship_type:
                rel_filter = f"type(r) = '{relationship_type}'"
            else:
                rel_filter = "true"
                
            query = f"""
            MATCH (u:User {{id: $user_id}})-[r]->(target)
            WHERE {rel_filter}
            RETURN type(r) as relationship_type, target.name as target_name, 
                   target as target_node, r as relationship
            ORDER BY target.name
            """
            
            result = await self.run_query(query, {"user_id": user_id})
            return result or []
        except Exception as e:
            logger.error(f"❌ Failed to get user relationships: {e}")
            return []

    async def get_user_facts(self, user_id: str) -> str:
        """Get user facts as formatted string."""
        if self._disabled:
            return ""
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return ""
            
        try:
            # Get relationship-based facts
            rel_query = """
            MATCH (u:User {id: $user_id})-[r]->(n)
            WHERE n.name IS NOT NULL
            RETURN type(r) AS rel, n.name AS name, n as node
            ORDER BY n.name
            LIMIT 50
            """
            rows = await self.run_query(rel_query, {"user_id": user_id}) or []

            # Include user's own stored name
            name_row = await self.run_query(
                "MATCH (u:User {id: $user_id}) RETURN u.name AS name LIMIT 1",
                {"user_id": user_id},
            ) or []
            if name_row and name_row[0].get("name"):
                rows = [{"rel": "IS_NAMED", "name": name_row[0]["name"]}] + rows

            if not rows:
                return ""
                
            facts = []
            for row in rows:
                if row.get("rel") and row.get("name"):
                    facts.append(f"{row['rel']} -> {row['name']}")
                    
            return "; ".join(facts)
        except Exception as e:
            logger.error(f"❌ Failed to get user facts: {e}")
            return ""

    async def search_concepts(self, search_term: str, concept_type: str = "Concept") -> List[Dict[str, Any]]:
        """Search for concepts by name."""
        if self._disabled:
            return []
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return []
            
        try:
            query = f"""
            MATCH (c:{concept_type})
            WHERE toLower(c.name) CONTAINS toLower($search_term)
            RETURN c.name as name, c as properties
            ORDER BY c.name
            LIMIT 20
            """
            result = await self.run_query(query, {"search_term": search_term})
            return result or []
        except Exception as e:
            logger.error(f"❌ Failed to search concepts: {e}")
            return []

    # =====================================================
    # 🔹 CRUD Operations - Update
    # =====================================================
    async def update_user(self, user_id: str, **properties) -> bool:
        """Update user properties."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            set_clauses = []
            params = {"user_id": user_id}
            
            for key, value in properties.items():
                set_clauses.append(f"u.{key} = ${key}")
                params[key] = value
                
            if not set_clauses:
                return True
                
            set_clauses.append("u.updated_at = datetime()")
            
            query = f"""
            MATCH (u:User {{id: $user_id}})
            SET {', '.join(set_clauses)}
            """
            
            await self.run_query(query, params)
            logger.info(f"✅ Updated user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update user {user_id}: {e}")
            return False

    async def update_concept(self, concept_name: str, concept_type: str = "Concept", **properties) -> bool:
        """Update concept properties."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            set_clauses = []
            params = {"name": concept_name}
            
            for key, value in properties.items():
                set_clauses.append(f"c.{key} = ${key}")
                params[key] = value
                
            if not set_clauses:
                return True
                
            set_clauses.append("c.updated_at = datetime()")
            
            query = f"""
            MATCH (c:{concept_type} {{name: $name}})
            SET {', '.join(set_clauses)}
            """
            
            await self.run_query(query, params)
            logger.info(f"✅ Updated concept: {concept_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update concept {concept_name}: {e}")
            return False

    async def update_relationship(self, user_id: str, relationship_type: str, target_name: str, **properties) -> bool:
        """Update relationship properties."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            rel_type = "".join(filter(str.isalnum, relationship_type)).upper()
            set_clauses = []
            params = {"user_id": user_id, "target_name": target_name}
            
            for key, value in properties.items():
                set_clauses.append(f"r.{key} = ${key}")
                params[key] = value
                
            if not set_clauses:
                return True
                
            set_clauses.append("r.updated_at = datetime()")
            
            query = f"""
            MATCH (u:User {{id: $user_id}})-[r:{rel_type}]->(target {{name: $target_name}})
            SET {', '.join(set_clauses)}
            """
            
            await self.run_query(query, params)
            logger.info(f"✅ Updated relationship: {user_id}-[:{rel_type}]->{target_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to update relationship: {e}")
            return False

    # =====================================================
    # 🔹 CRUD Operations - Delete
    # =====================================================
    async def delete_user(self, user_id: str) -> bool:
        """Delete user and all their relationships."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            query = """
            MATCH (u:User {id: $user_id})
            DETACH DELETE u
            """
            await self.run_query(query, {"user_id": user_id})
            logger.info(f"✅ Deleted user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete user {user_id}: {e}")
            return False

    async def delete_concept(self, concept_name: str, concept_type: str = "Concept") -> bool:
        """Delete concept and all relationships."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            query = f"""
            MATCH (c:{concept_type} {{name: $name}})
            DETACH DELETE c
            """
            await self.run_query(query, {"name": concept_name})
            logger.info(f"✅ Deleted concept: {concept_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete concept {concept_name}: {e}")
            return False

    async def delete_relationship(self, user_id: str, relationship_type: str, target_name: str) -> bool:
        """Delete a specific relationship."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            rel_type = "".join(filter(str.isalnum, relationship_type)).upper()
            query = f"""
            MATCH (u:User {{id: $user_id}})-[r:{rel_type}]->(target {{name: $target_name}})
            DELETE r
            """
            await self.run_query(query, {"user_id": user_id, "target_name": target_name})
            logger.info(f"✅ Deleted relationship: {user_id}-[:{rel_type}]->{target_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete relationship: {e}")
            return False

    # =====================================================
    # 🔹 Advanced Operations
    # =====================================================
    async def get_user_network(self, user_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get user's network up to specified depth."""
        if self._disabled:
            return {}
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return {}
            
        try:
            query = f"""
            MATCH path = (u:User {{id: $user_id}})-[*1..{depth}]-(connected)
            RETURN path
            LIMIT 100
            """
            result = await self.run_query(query, {"user_id": user_id})
            
            network = {
                "user_id": user_id,
                "depth": depth,
                "paths": result or [],
                "total_connections": len(result) if result else 0
            }
            
            return network
        except Exception as e:
            logger.error(f"❌ Failed to get user network: {e}")
            return {}

    async def get_concept_connections(self, concept_name: str, concept_type: str = "Concept") -> List[Dict[str, Any]]:
        """Get all connections to a concept."""
        if self._disabled:
            return []
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return []
            
        try:
            query = f"""
            MATCH (c:{concept_type} {{name: $name}})-[r]-(connected)
            RETURN type(r) as relationship_type, connected.name as connected_name, 
                   connected as connected_node, r as relationship
            ORDER BY connected.name
            """
            result = await self.run_query(query, {"name": concept_name})
            return result or []
        except Exception as e:
            logger.error(f"❌ Failed to get concept connections: {e}")
            return []

    async def add_entities_and_relationships(self, facts: Dict[str, Any]) -> bool:
        """Add structured facts to the knowledge graph."""
        if self._disabled:
            return False
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return False
            
        try:
            entities = facts.get("entities", [])
            relationships = facts.get("relationships", [])
            
            async with self._driver.session(database=self._database) as session:
                async with await session.begin_transaction() as tx:
                    # Create entities
                    for entity in entities:
                        label = "".join(filter(str.isalnum, entity.get("label", "Thing")))
                        name = entity.get("name")
                        if not name:
                            continue
                        await tx.run(f"MERGE (n:{label} {{name: $name}})", name=name)

                    # Create relationships
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
                            ON CREATE SET r.fact_id = $rid, r.created_at = datetime()
                            """,
                            source_name=source_name,
                            target_name=target_name,
                            rid=rid,
                        )
                        
            logger.info(f"✅ Added {len(entities)} entities and {len(relationships)} relationships")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to add entities and relationships: {e}")
            return False

    # =====================================================
    # 🔹 Utility Functions
    # =====================================================
    async def ping(self) -> bool:
        """Check if Neo4j is accessible."""
        try:
            if not self._driver:
                await self.connect(retries=1)
            if not self._driver:
                return False
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def get_database_info(self) -> Dict[str, Any]:
        """Get database information."""
        if self._disabled:
            return {"status": "disabled"}
        if not self._driver:
            await self.connect()
        if not self._driver or self._disabled:
            return {"status": "unavailable"}
            
        try:
            # Get basic database stats
            node_count = await self.run_query("MATCH (n) RETURN count(n) as count")
            rel_count = await self.run_query("MATCH ()-[r]->() RETURN count(r) as count")
            
            info = {
                "status": "connected",
                "database": self._database,
                "nodes": node_count[0]["count"] if node_count else 0,
                "relationships": rel_count[0]["count"] if rel_count else 0,
                "uri": settings.NEO4J_URI
            }
            
            return info
        except Exception as e:
            logger.error(f"❌ Failed to get database info: {e}")
            return {"status": "error", "error": str(e)}

    def is_ready(self) -> bool:
        """Check if service is ready."""
        return not self._disabled and self._driver is not None

# =====================================================
# 🔹 Legacy Compatibility
# =====================================================
class LegacyNeo4jService:
    """Legacy Neo4j service for backward compatibility."""
    
    def __init__(self):
        self.enhanced = EnhancedNeo4jService()
        
    async def connect(self, retries: Optional[int] = None):
        return await self.enhanced.connect(retries)
        
    async def close(self):
        return await self.enhanced.close()
        
    async def run_query(self, query: str, parameters: Optional[Dict] = None):
        return await self.enhanced.run_query(query, parameters)
        
    async def create_user_node(self, user_id: str):
        return await self.enhanced.create_user(user_id)
        
    async def get_user_facts(self, user_id: str):
        return await self.enhanced.get_user_facts(user_id)
        
    async def create_relation(self, user_id: str, rel_type: str, concept: str):
        return await self.enhanced.create_relationship(user_id, rel_type, concept)
        
    async def delete_relation(self, user_id: str, rel_type: str, concept: str):
        return await self.enhanced.delete_relationship(user_id, rel_type, concept)
        
    async def delete_concept(self, concept: str):
        return await self.enhanced.delete_concept(concept)
        
    async def add_entities_and_relationships(self, facts: Dict[str, Any]):
        return await self.enhanced.add_entities_and_relationships(facts)
        
    async def upsert_user_preference(self, user_id: str, label: str, pref_type: str = "HOBBY"):
        return await self.enhanced.create_relationship(user_id, "PREFERS", label, "Preference", pref_type=pref_type)
        
    async def update_fact(self, fact_id: str, correction: str, user_id: str):
        # This is a simplified implementation
        if not correction or correction.lower() == "delete":
            # Delete the fact
            return await self.enhanced.delete_relationship(user_id, "HAS_FACT", fact_id)
        else:
            # Update the fact
            return await self.enhanced.update_relationship(user_id, "HAS_FACT", fact_id, value=correction)

# Create service instances
enhanced_neo4j_service = EnhancedNeo4jService()
neo4j_service = LegacyNeo4jService()  # For backward compatibility
