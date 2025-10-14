"""
Simple test script to verify enhanced memory system
"""

import asyncio
import logging
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_basic_functionality():
    """Test basic functionality of the enhanced memory system."""
    try:
        logger.info("🚀 Starting basic memory system test...")
        
        # Test imports
        from app.services.enhanced_memory_service import enhanced_memory_service
        from app.services.enhanced_pinecone_service import enhanced_pinecone_service
        from app.services.enhanced_neo4j_service import enhanced_neo4j_service
        
        logger.info("✅ All imports successful")
        
        # Test service initialization
        logger.info("🔧 Testing service initialization...")
        
        # Initialize Pinecone
        enhanced_pinecone_service.initialize()
        logger.info(f"Pinecone ready: {enhanced_pinecone_service.is_ready()}")
        
        # Initialize Neo4j
        await enhanced_neo4j_service.connect()
        logger.info(f"Neo4j ready: {await enhanced_neo4j_service.ping()}")
        
        # Initialize enhanced memory service
        success = await enhanced_memory_service.initialize()
        logger.info(f"Enhanced memory service initialized: {success}")
        
        # Test health check
        health = await enhanced_memory_service.health_check()
        logger.info(f"Health status: {health}")
        
        logger.info("✅ Basic functionality test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def main():
    """Main test function."""
    success = await test_basic_functionality()
    
    if success:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("💥 Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
