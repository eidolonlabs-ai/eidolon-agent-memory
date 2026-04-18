#!/usr/bin/env python3
"""Test get_extracted_facts performance."""
import asyncio
import sys
import time

sys.path.insert(0, "/Users/markcastillo/git/ember-benchmark")

async def test_get_facts():
    from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
    
    print("Testing get_extracted_facts (12 parallel probes)...")
    print("=" * 80)
    
    try:
        adapter = EidolonAgentMemoryAdapter(server_url="http://localhost:3100", timeout=120.0)
        await adapter.setup()
        
        print(f"✓ Setup complete\n")
        print(f"Testing get_extracted_facts()...")
        
        start = time.time()
        facts = await asyncio.wait_for(
            adapter.get_extracted_facts(),
            timeout=120.0
        )
        elapsed = time.time() - start
        
        print(f"✓ Got facts in {elapsed:.1f}s")
        print(f"  Facts returned: {len(facts)}")
        if facts:
            for i, f in enumerate(facts[:5]):
                print(f"    {i+1}. {f.fact[:60]}...")
        
        await adapter.teardown()
        return True
        
    except asyncio.TimeoutError:
        print("✗ TIMEOUT: get_extracted_facts took > 120 seconds!")
        return False
    except Exception as e:
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_get_facts())
    sys.exit(0 if result else 1)
