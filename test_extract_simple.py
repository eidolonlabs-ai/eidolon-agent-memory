#!/usr/bin/env python3
"""Quick test of extract_session_facts tool."""
import asyncio
import sys
import json

sys.path.insert(0, "/Users/markcastillo/git/ember-benchmark")

async def test_extraction():
    from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
    
    print("Testing extract_session_facts...")
    print("=" * 80)
    
    try:
        adapter = EidolonAgentMemoryAdapter(server_url="http://localhost:3100", timeout=120.0)
        print("✓ Adapter created\n")
        
        # Setup
        print("Running setup...")
        await adapter.setup()
        print(f"✓ Setup complete. Companion ID: {adapter._companion_id}\n")
        
        # Simple conversation
        test_text = """User: Hi, I'm feeling really sad about my grandmother passing away last month.
Assistant: I'm so sorry to hear about your loss. It sounds like it's been a difficult time for you. Would you like to talk about her?
User: Yeah, she was 89 and lived in Portland. We were very close."""
        
        print(f"Testing extraction with conversation:\n{test_text[:200]}...\n")
        
        print("Calling extract_session_facts (timeout: 120s)...")
        import time
        start = time.time()
        
        try:
            result = await asyncio.wait_for(
                adapter._call_tool(
                    "extract_session_facts",
                    {
                        "api_key": adapter._api_key,
                        "companion_id": adapter._companion_id,
                        "conversation_text": test_text,
                    },
                ),
                timeout=120.0
            )
            
            elapsed = time.time() - start
            print(f"✓ Extraction completed in {elapsed:.1f}s")
            print(f"Result: {json.dumps(result, indent=2)[:500]}")
            
        except asyncio.TimeoutError:
            print("✗ TIMEOUT: extract_session_facts took > 120 seconds!")
            return False
        
        # Cleanup
        await adapter.teardown()
        return True
        
    except Exception as e:
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_extraction())
    sys.exit(0 if result else 1)
