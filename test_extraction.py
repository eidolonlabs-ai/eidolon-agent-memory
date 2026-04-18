#!/usr/bin/env python3
"""Quick extraction test - extract one small conversation to verify everything works."""
import asyncio
import sys
import json

sys.path.insert(0, "/Users/markcastillo/git/ember-benchmark")

async def test():
    from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
    
    adapter = EidolonAgentMemoryAdapter(server_url="http://localhost:3100", timeout=600.0)
    
    try:
        print("Setting up adapter...")
        await adapter.setup()
        print(f"✓ Setup complete. Companion ID: {adapter._companion_id}\n")
        
        # Simple test conversation
        from ember.types import Message
        messages = [
            Message(role="user", content="Hi there!"),
            Message(role="assistant", content="Hello! How can I help?"),
            Message(role="user", content="I live in Seattle."),
            Message(role="assistant", content="Seattle is great! Do you like it there?"),
        ]
        
        print("Ingesting test conversation...")
        print(f"  Messages: {len(messages)}")
        
        import time
        start = time.time()
        await adapter.ingest_conversation(messages)
        elapsed = time.time() - start
        print(f"✓ Ingestion complete in {elapsed:.1f}s\n")
        
        print("Extracting facts...")
        facts = await adapter.get_extracted_facts()
        print(f"✓ Extracted {len(facts)} facts:")
        for i, fact in enumerate(facts[:5], 1):
            print(f"  {i}. {fact.predicate}: {fact.fact}")
        
        if len(facts) > 5:
            print(f"  ... and {len(facts) - 5} more")
        
        print(f"\n✅ TEST PASSED - System works!")
        
        await adapter.teardown()
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED")
        print(f"Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test()))
