"""Simple Neo4j connectivity smoke test.

Run inside the backend container:
    python scripts/neo4j_smoke.py
"""
import os
from neo4j import GraphDatabase

# Enforce secure Aura URI by default
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://bb2cd868.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

print(f"Connecting to {NEO4J_URI} as {NEO4J_USER}...")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()
print("Connected ✔")

with driver.session() as session:
    session.run("MERGE (t:Test {name: 'smoke'}) RETURN t").consume()
    result = session.run("MATCH (t:Test {name: 'smoke'}) RETURN count(t) AS c").single()
    print("Nodes with label Test and name smoke:", result["c"]) 

driver.close()
print("Done.")
