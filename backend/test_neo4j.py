import os
from neo4j import GraphDatabase

uri = os.getenv("NEO4J_URI", "neo4j+s://bb2cd868.databases.neo4j.io")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

if not user or not password:
    print("Skipping Neo4j test: NEO4J_USER/NEO4J_PASSWORD not set")
else:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        print("Connected to Neo4j!")
    except Exception as e:
        print("Failed to connect:", e)
    finally:
        driver.close()