"""
Neo4j Database Inspector
View all nodes, relationships, and data in Neo4j
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.enhanced_neo4j_service import enhanced_neo4j_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def inspect_neo4j():
    """Inspect Neo4j data in detail."""
    print("🔍 NEO4J DATABASE INSPECTION")
    print("=" * 50)
    
    try:
        # Connect to Neo4j
        await enhanced_neo4j_service.connect()
        
        if not await enhanced_neo4j_service.ping():
            print("❌ Neo4j not connected")
            return
        
        print("✅ Neo4j connected")
        
        # Get database info
        db_info = await enhanced_neo4j_service.get_database_info()
        print(f"\n📊 Database Information:")
        print(f"   Status: {db_info.get('status', 'Unknown')}")
        print(f"   Nodes: {db_info.get('nodes', 'Unknown')}")
        print(f"   Relationships: {db_info.get('relationships', 'Unknown')}")
        print(f"   Database: {db_info.get('database', 'Unknown')}")
        
        # Get all nodes with their labels
        print(f"\n🔍 Fetching all nodes...")
        nodes_query = """
        MATCH (n) 
        RETURN n, labels(n) as labels, id(n) as node_id
        ORDER BY labels(n)[0], n.name
        """
        nodes = await enhanced_neo4j_service.run_query(nodes_query)
        print(f"   ✅ Found {len(nodes)} nodes")
        
        # Group nodes by label
        nodes_by_label = {}
        for node in nodes:
            labels = node.get('labels', [])
            if labels:
                label = labels[0]
                if label not in nodes_by_label:
                    nodes_by_label[label] = []
                nodes_by_label[label].append(node)
        
        print(f"\n📁 Nodes by Label:")
        for label, node_list in nodes_by_label.items():
            print(f"   {label}: {len(node_list)} nodes")
            
            # Show sample nodes
            for i, node in enumerate(node_list[:3]):  # Show first 3
                node_data = node.get('n', {})
                print(f"      📄 {label} {i+1}: {node_data}")
        
        # Get all relationships
        print(f"\n🔍 Fetching all relationships...")
        rels_query = """
        MATCH ()-[r]->() 
        RETURN r, type(r) as rel_type, startNode(r) as start_node, endNode(r) as end_node
        ORDER BY type(r)
        """
        relationships = await enhanced_neo4j_service.run_query(rels_query)
        print(f"   ✅ Found {len(relationships)} relationships")
        
        # Group relationships by type
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel.get('rel_type', 'Unknown')
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append(rel)
        
        print(f"\n📁 Relationships by Type:")
        for rel_type, rel_list in rels_by_type.items():
            print(f"   {rel_type}: {len(rel_list)} relationships")
        
        # Get specific data types
        print(f"\n🔍 Fetching specific data...")
        
        # Users
        users_query = "MATCH (u:User) RETURN u, id(u) as user_id"
        users = await enhanced_neo4j_service.run_query(users_query)
        print(f"   👤 Users: {len(users)}")
        for user in users:
            user_data = user.get('u', {})
            print(f"      📄 User: {user_data}")
        
        # Concepts
        concepts_query = "MATCH (c:Concept) RETURN c, id(c) as concept_id"
        concepts = await enhanced_neo4j_service.run_query(concepts_query)
        print(f"   🧠 Concepts: {len(concepts)}")
        for concept in concepts:
            concept_data = concept.get('c', {})
            print(f"      📄 Concept: {concept_data}")
        
        # Facts
        facts_query = "MATCH (f:Fact) RETURN f, id(f) as fact_id"
        facts = await enhanced_neo4j_service.run_query(facts_query)
        print(f"   📚 Facts: {len(facts)}")
        for fact in facts:
            fact_data = fact.get('f', {})
            print(f"      📄 Fact: {fact_data}")
        
        # Get user networks
        print(f"\n🔍 Fetching user networks...")
        for user in users:
            user_id = user.get('u', {}).get('id')
            if user_id:
                network = await enhanced_neo4j_service.get_user_network(user_id, depth=2)
                print(f"   🌐 Network for user {user_id}: {network.get('total_connections', 0)} connections")
        
        # Summary
        print(f"\n📊 SUMMARY")
        print(f"   Total nodes: {len(nodes)}")
        print(f"   Total relationships: {len(relationships)}")
        print(f"   Node labels: {list(nodes_by_label.keys())}")
        print(f"   Relationship types: {list(rels_by_type.keys())}")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"neo4j_inspection_{timestamp}.json"
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "database_info": db_info,
            "nodes": nodes,
            "relationships": relationships,
            "nodes_by_label": nodes_by_label,
            "relationships_by_type": rels_by_type,
            "users": users,
            "concepts": concepts,
            "facts": facts,
            "summary": {
                "total_nodes": len(nodes),
                "total_relationships": len(relationships),
                "node_labels": list(nodes_by_label.keys()),
                "relationship_types": list(rels_by_type.keys())
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {filename}")
        
        return results
        
    except Exception as e:
        print(f"❌ Neo4j inspection failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(inspect_neo4j())
