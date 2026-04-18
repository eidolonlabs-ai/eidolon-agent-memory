#!/usr/bin/env python3
"""Full integration test: reset, ingest, extract."""
import asyncio
import sys
import json
import time

sys.path.insert(0, "/Users/markcastillo/git/ember-benchmark")

async def full_test():
    from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
    from ember.data import load_golden_conversations
    
    print("Full integration test (reset + ingest + extract)...")
    print("=" * 80)
    
    try:
        adapter = EidolonAgentMemoryAdapter(server_url="http://localhost:3100", timeout=120.0)
        
        # Get first conversation
        convs = load_golden_conversations()
        conv = convs[0]
        
        print(f"\nLoaded {len(convs)} conversations from golden dataset")
        print(f"Testing first conversation ({len(conv.messages)} messages)\n")
        
        # Setup (needed once before reset loop)
        print("0. Setup adapter...")
        start = time.time()
        await adapter.setup()
        print(f"   ✓ Setup took {time.time() - start:.1f}s")
        
        # Reset
        print("\n1. Reset adapter...")
        start = time.time()
        await adapter.reset()
        print(f"   ✓ Reset took {time.time() - start:.1f}s")
        
        # Ingest
        print("\n2. Ingest conversation...")
        start = time.time()
        await adapter.ingest_conversation(conv.messages)
        print(f"   ✓ Ingest took {time.time() - start:.1f}s")
        
        # Wait
        print("\n3. Wait for extraction (no-op)...")
        await adapter.wait_for_extraction()
        print("   ✓ Wait done")
        
        # Get facts
        print("\n4. Get extracted facts (12 parallel probes)...")
        start = time.time()
        facts = await asyncio.wait_for(
            adapter.get_extracted_facts(),
            timeout=60.0
        )
        elapsed = time.time() - start
        print(f"   ✓ Got {len(facts)} facts in {elapsed:.1f}s")
        
        # Score
        from ember.scoring import extraction_recall
        result = extraction_recall(facts, conv.expected_facts)
        print(f"\n5. Score:")
        print(f"   Recall: {result['recall']:.4f}")
        print(f"   Salience-weighted recall: {result['salience_weighted_recall']:.4f}")
        
        await adapter.teardown()
        return True
        
    except Exception as e:
        import traceback
        print(f"✗ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(full_test())
    sys.exit(0 if result else 1)
