"""
Minimal test to isolate import issues
"""

def test_minimal_imports():
    """Test minimal imports to isolate issues."""
    try:
        print("Testing minimal imports...")
        
        # Test 1: Basic config
        print("1. Testing config...")
        from app.config import settings
        print("✅ Config OK")
        
        # Test 2: Enhanced services
        print("2. Testing enhanced services...")
        from app.services.enhanced_pinecone_service import enhanced_pinecone_service
        print("✅ Enhanced Pinecone OK")
        
        from app.services.enhanced_neo4j_service import enhanced_neo4j_service
        print("✅ Enhanced Neo4j OK")
        
        from app.services.enhanced_memory_service import enhanced_memory_service
        print("✅ Enhanced Memory OK")
        
        # Test 3: Router
        print("3. Testing router...")
        from app.routers.enhanced_memory import router
        print("✅ Enhanced Memory Router OK")
        
        # Test 4: Main app (this might fail)
        print("4. Testing main app...")
        try:
            from app.main import app
            print("✅ Main app OK")
        except Exception as e:
            print(f"❌ Main app failed: {e}")
            return False
        
        print("🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_minimal_imports()
