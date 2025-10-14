"""
Test script to verify all imports work correctly
"""

def test_imports():
    """Test all critical imports."""
    try:
        print("Testing imports...")
        
        # Test basic imports
        print("1. Testing basic imports...")
        from app.config import settings
        print("✅ Config import successful")
        
        # Test service imports
        print("2. Testing service imports...")
        from app.services.enhanced_pinecone_service import enhanced_pinecone_service
        print("✅ Enhanced Pinecone service import successful")
        
        from app.services.enhanced_neo4j_service import enhanced_neo4j_service
        print("✅ Enhanced Neo4j service import successful")
        
        from app.services.enhanced_memory_service import enhanced_memory_service
        print("✅ Enhanced memory service import successful")
        
        # Test router imports
        print("3. Testing router imports...")
        from app.routers.enhanced_memory import router
        print("✅ Enhanced memory router import successful")
        
        # Test main app import
        print("4. Testing main app import...")
        from app.main import app
        print("✅ Main app import successful")
        
        print("🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()
