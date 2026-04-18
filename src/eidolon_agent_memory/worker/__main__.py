"""Entry point: python -m eidolon_agent_memory.worker"""
import asyncio
from eidolon_agent_memory.worker.autonomous import run

asyncio.run(run())
