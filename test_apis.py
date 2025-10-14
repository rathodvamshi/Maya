import asyncio
import os
import sys
sys.path.append('backend')

from app.services import ai_service

async def test_providers():
    print("Testing AI providers...")
    
    # Test each provider individually
    test_prompt = "Say 'Hello from [provider]' in one sentence."
    
    # Test Gemini
    print("\n🔍 Testing Gemini...")
    try:
        result = await ai_service.generate_response_json(test_prompt)
        if result.get("response"):
            print(f"✅ Gemini: {result['response'][:100]}...")
            print(f"   Provider: {result.get('provider_used')}")
        else:
            print(f"❌ Gemini failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Gemini error: {e}")
    
    # Test Cohere
    print("\n🔍 Testing Cohere...")
    try:
        result = await ai_service.generate_response_json(test_prompt)
        if result.get("response"):
            print(f"✅ Cohere: {result['response'][:100]}...")
            print(f"   Provider: {result.get('provider_used')}")
        else:
            print(f"❌ Cohere failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Cohere error: {e}")
    
    # Test Anthropic
    print("\n🔍 Testing Anthropic...")
    try:
        result = await ai_service.generate_response_json(test_prompt)
        if result.get("response"):
            print(f"✅ Anthropic: {result['response'][:100]}...")
            print(f"   Provider: {result.get('provider_used')}")
        else:
            print(f"❌ Anthropic failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Anthropic error: {e}")

if __name__ == "__main__":
    asyncio.run(test_providers())