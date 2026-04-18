#!/usr/bin/env python3
"""Test a single search_memory call."""
import asyncio
import sys
import time

sys.path.insert(0, "/Users/markcastillo/git/ember-benchmark")

async def test():
    from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
    from ember.data import load_golden_conversations
    
    print("Creating adapter...")
    adapter = EidolonAgentMemoryAdapter(server_url="http://localhost:3100")
    
    print("Setup...")
    await adapter.setup()
    print(f"✓ Setup complete")
    
    conversations = load_golden_conversations()
    conv = conversations[0]
    
    print(f"Testing single search_memory call...")
    print("Reset...")
    await adapter.reset()
    print("✓ Reset")
    
    print("Ingest...")
    await adapter.ingest_conversation(conv.messages)
    print("✓ Ingest")
    
    print("Wait...")
    await adapter.wait_for_extraction()
    print("✓ Wait")
    
    print("\nMaking single search_memory call (60s timeout)...")
    try:
        start = time.time()
        result = await asyncio.wait_for(
            adapter._call_tool("search_memory", {
                "api_key": adapter._api_key,
                "companion_id": adapter._companion_id,
                "query": "user life personal history",
                "intent": "recall",
                "limit": 50,
            }),
            timeout=60.0
        )
        elapsed = time.time() - start
        print(f"✓ Got result in {elapsed:.1f}s")
        print(f"  Response type: {type(result)}")
        if isinstance(result, dict):
            print(f"  Keys: {result.keys()}")
            if 'facts' in result:
                print(f"  Facts count: {len(result['facts'])}")
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"✗ TIMEOUT after {elapsed:.1f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ ERROR after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
    
    await adapter.teardown()

if __name__ == "__main__":
    asyncio.run(test())
