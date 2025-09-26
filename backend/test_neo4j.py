from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
user = "neo4j"
password = "password123"

driver = GraphDatabase.driver(uri, auth=(user, password))
try:
    driver.verify_connectivity()
    print("Connected to Neo4j!")
except Exception as e:
    print("Failed to connect:", e)
finally:
    driver.close()