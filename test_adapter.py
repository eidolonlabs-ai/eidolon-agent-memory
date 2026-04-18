#!/usr/bin/env python3
import asyncio
from pathlib import Path
import sys
sys.path.insert(0, '/Users/markcastillo/git/ember-benchmark')
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter

async def test():
    print("Testing EidolonAgentMemoryAdapter connectivity...")
    
    try:
        adapter = EidolonAgentMemoryAdapter(
            api_url="http://localhost:3100/mcp",
            api_key="test",
            companion_id="test"
        )
        print("✓ Adapter initialized")
        
        # Try to get extracted facts (should work quickly with empty/minimal data)
        print("Testing get_extracted_facts()...")
        facts = await adapter.get_extracted_facts()
        print(f"✓ Got response: {len(facts)} facts")
        
        print("\n✓ EidolonAgentMemoryAdapter is working!")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test())
    sys.exit(0 if result else 1)
