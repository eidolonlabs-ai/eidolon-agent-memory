# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Eidolon Agent Memory** is an MCP (Model Context Protocol) server that provides a cognitive memory platform for conversational AI. It stores and retrieves facts, relationships, episodic memories, and preferences with emphasis on:

- **Emotional salience awareness**: Differentiates between HIGH (grief, trauma), MED (milestones), and LOW (preferences, trivia) importance
- **Graceful omission**: Ensures sensitive/crisis content never surfaces in casual queries
- **Semantic search**: Vector + context-aware retrieval with emotional filtering
- **27+ MCP tools**: Organized into memory read/write, cognitive, companion, and scheduler categories

Core stack: **FastAPI + SQLAlchemy + PostgreSQL + pgvector + OpenAI-compatible LLM + MCP**

## Development Setup

### Initial Setup
```bash
# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copy env template
cp .env.example .env
```

### Docker Quick Start (Recommended)
```bash
docker compose up -d --build
# Server available at http://localhost:3100
# Database at localhost:25433
```

### Manual Setup (without Docker)
```bash
# Ensure PostgreSQL + pgvector is running locally
# Configure .env with DATABASE_URL, LLM_API_BASE, EMBEDDING_API_BASE

alembic upgrade head  # Apply migrations
python -m eidolon_agent_memory  # Start MCP server
```

## Common Commands

### Development
```bash
# Run all tests
pytest -v

# Run specific test file
pytest test_extraction.py -v

# Run single test
pytest test_extraction.py::test_function_name -v

# Start local dev server (non-Docker)
python -m eidolon_agent_memory

# Check server health
curl http://localhost:3100/health
```

### Database
```bash
# Create a new migration after changing models
alembic revision --autogenerate -m "Description of changes"

# Apply pending migrations
alembic upgrade head

# View migration status
alembic current
```

### Benchmarking
```bash
# Full EMBER benchmark (all tiers)
python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100

# Specific EMBER tier
python -m ember.cli run --adapter eidolon-agent-memory --url http://localhost:3100 --tiers 1,2

# LOCOMO benchmark
LOCOMO_EXTRACT_FACTS=1 python scripts/evals/run_locomo.py

# LongMemEval benchmark
LONGMEMEVAL_EXTRACT_FACTS=1 python scripts/evals/run_longmemeval.py
```

## Architecture

### Service Layer (`src/eidolon_agent_memory/services/`)
Core business logic with clear separation of concerns:

- **`llm.py`**: LLM completions with JSON parsing, corrective retry on parse errors, timeout handling (120s default)
- **`extraction.py`**: Fact extraction from conversations with salience-weighted quality scoring, 3-tier emotional salience tagging
- **`search.py`**: Vector + semantic search combining embeddings with emotional context filtering and `SearchIntent` types (factual, emotional, casual, recall)
- **`memory.py`**: CRUD operations on MemoryNode/MemoryEdge, relationship management
- **`embedding.py`**: Text vectorization with OpenAI-compatible API fallback handling
- **`cognitive.py`**: Higher-level reasoning (companion values, user insights, relationship analysis)
- **`decay.py`**: Time-weighted memory decay calculation (memories fade over time)
- **`relationship.py`**: Social graph operations and path finding

### Data Model
- **MemoryNode**: Entities with embeddings, importance scores, confidence, timestamps
- **MemoryEdge**: Facts (subject→predicate→object) with:
  - `emotional_salience`: HIGH | MED | LOW (weighting for extraction/retrieval)
  - `scope`: user | shared | companion (visibility control)
  - `confidence`: 0-1 extraction confidence score
- **SearchIntent**: Semantic intent for contextual retrieval (factual vs. emotional vs. casual)

### Tools Layer (`src/eidolon_agent_memory/tools/`)
MCP tool implementations grouped functionally:

- **`memory_read.py`**: `memory_search`, `memory_get_facts`, `memory_get_context` — retrieve with emotional filtering
- **`memory_write.py`**: `memory_store_fact`, `memory_update_relationship`, `memory_delete_fact` — persist facts and relationships
- **`cognitive.py`**: `get_companion_values`, `get_user_profile`, `analyze_relationships` — introspection and inference
- **`companion.py`**: `get_companion_context`, `store_companion_perspective` — AI companion specific operations
- **`scheduler.py`**: Reminder and task scheduling with cron support
- **`utility.py`**: Health checks, session management

### Data Layer (`src/eidolon_agent_memory/models/`)
SQLAlchemy ORM models:

- **`memory.py`**: MemoryNode and MemoryEdge (pgvector embeddings)
- **`relationship.py`**: Relationship tracking with emotional metadata
- **`user.py`**: User accounts with API key authentication
- **`companion.py`**: AI companion profiles and perspective data
- **`session.py`**: Conversation sessions and message history
- **`task.py`**: Scheduled tasks and reminders
- **`preference.py`**: User preferences and settings
- **`insight.py`**: Derived insights and cognitive summaries

### Configuration (`src/eidolon_agent_memory/core/`)
- **`config.py`**: Pydantic settings loading from `.env` (LLM endpoints, database URL, embedding model, MCP transport)
- **`auth.py`**: API key verification and user resolution with fast path caching

## Key Development Patterns

### Fact Extraction Quality
The bottleneck is in **Tier 1 extraction** (currently 64% PASS). When improving:

- Check extraction prompts in `extraction.py` — quality directly correlates with final performance
- Salience scoring must differentiate crisis (HIGH) from routine (LOW) facts
- Review `extraction.py:_score_extraction_quality()` for quality thresholds
- Test with small conversations first: `python test_single_search.py`

### Emotional Salience Levels
- **HIGH**: Grief, loss, trauma, crisis events — never surface casually, use in recall queries only
- **MED**: Milestones, important events, decisions — surface contextually
- **LOW**: Preferences, trivia, casual facts — always safe to surface

When extracting facts, classify correctly or retrieval will fail to respect emotional boundaries.

### Graceful Omission
Tier 2b benchmark (graceful omission) **passes 100%** — crisis content never surfaces in casual queries. This is enforced in `search.py:_filter_by_emotional_context()`. Do not modify emotional filtering logic without re-running benchmarks.

### Search Intent
Query intent should guide retrieval strategy:

- **factual**: Straightforward information lookup
- **emotional**: Deep emotional context matters
- **casual**: Lightweight, preference-based
- **recall**: Broad memory retrieval, full context

In `search.py`, intent affects query embedding and result filtering.

## Testing

### Test Files
- **`test_extraction.py`**: Fact extraction quality on small conversations
- **`test_search.py`**: Vector search and retrieval ranking
- **`test_full_integration.py`**: End-to-end flow (ingest → extract → search → recall)
- **`test_adapter.py`**: Benchmark adapter compatibility
- Root-level test files test specific components directly; migrate failing tests to `tests/` directory structure as codebase grows

### Running Tests
```bash
pytest -v              # All tests
pytest test_extraction.py -v --tb=short  # Single file with compact tracebacks
```

### Benchmark Results
- **Latest run**: April 20, 2026
- **EMBER Tier 1 (Extraction)**: 0.6429 (FAIL, needs improvement)
- **EMBER Tier 2 (Retrieval)**: 0.8562 (PASS)
- **EMBER Tier 2b (Graceful Omission)**: 1.0000 (PASS)
- **EMBER Tier 3 (End-to-End)**: 0.4521 (FAIL, limited by Tier 1)

Results tracked in `docs/evals/BENCHMARK_RUN_TRACKER.md`. When changing extraction/retrieval, re-run benchmarks and update tracker with absolute UTC timestamp (e.g., "April 20, 2026 @ 05:05:04 UTC").

## Database Migrations

Using Alembic for schema management:

```bash
# Auto-generate migration after model changes
alembic revision --autogenerate -m "Add field to memory table"

# Review generated migration in alembic/versions/
alembic upgrade head
```

**Important**: Migrations run automatically on `docker compose up` (via `migrate` service). For manual setups, run `alembic upgrade head` before starting the server.

## Environment Variables

Key settings in `.env`:

```env
# LLM (OpenAI-compatible endpoint — LM Studio by default)
LLM_API_BASE=http://localhost:1234/v1
LLM_COGNITIVE_MODEL=lmstudio-community/gemma-3-12b-it-GGUF
LLM_EXTRACTION_MODEL=lmstudio-community/gemma-3-12b-it-GGUF

# Embeddings (OpenAI-compatible)
EMBEDDING_API_BASE=http://localhost:1234/v1
EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
EMBEDDING_DIMENSIONS=768

# Database
DATABASE_URL=postgresql+asyncpg://eidolon_agent_memory:eidolon_agent_memory@localhost:25433/eidolon_agent_memory

# MCP
MCP_TRANSPORT=http
MCP_PORT=3100
```

For Ollama, Docker internal networking uses `http://host.docker.internal:8000` from containers.

## Troubleshooting

### Extraction Quality Low
1. Check LLM is responding: `python test_single_search.py`
2. Review extraction prompt in `extraction.py:_extract_facts_with_salience()`
3. Verify emotional salience classification in `_classify_salience()`
4. Run `pytest test_extraction.py -v` for detailed feedback

### Server Won't Start
```bash
# Check database connectivity
curl http://localhost:3100/health

# View logs
docker compose logs server

# Verify migrations ran
alembic current
```

### Benchmark Failures
1. Ensure containers are healthy: `docker compose ps`
2. Server responding: `curl http://localhost:3100/health`
3. Check LLM/embedding endpoints in `.env`
4. View detailed benchmark logs: `tail -f docs/evals/artifacts/ember_*.json`

## Project Structure

```
src/eidolon_agent_memory/
├── __init__.py               # Package init, version info
├── __main__.py               # Entry point: python -m eidolon_agent_memory
├── server.py                 # FastMCP server + tool registration
├── core/                     # Configuration & auth
│   ├── config.py            # Pydantic settings
│   └── auth.py              # API key verification
├── services/                 # Core business logic
│   ├── llm.py               # LLM completions + JSON parsing
│   ├── extraction.py        # Fact extraction with salience scoring
│   ├── search.py            # Vector + semantic search
│   ├── memory.py            # CRUD operations
│   ├── embedding.py         # Vectorization
│   ├── cognitive.py         # Higher-level reasoning
│   ├── decay.py             # Time-weighted decay
│   └── relationship.py      # Social graph operations
├── tools/                    # 27+ MCP tool implementations
│   ├── memory_read.py       # Search, get_facts, get_context
│   ├── memory_write.py      # Store, update, delete
│   ├── cognitive.py         # User profile, companion values, analysis
│   ├── companion.py         # Companion-specific tools
│   ├── scheduler.py         # Reminders and task scheduling
│   └── utility.py           # Health, sessions
├── models/                   # SQLAlchemy ORM
│   ├── base.py              # Base model with created_at, updated_at
│   ├── memory.py            # MemoryNode, MemoryEdge (pgvector)
│   ├── relationship.py      # Relationships + emotional metadata
│   ├── user.py              # Users, API keys
│   ├── companion.py         # Companion profiles
│   ├── session.py           # Conversation sessions
│   ├── task.py              # Scheduled tasks
│   ├── preference.py        # User preferences
│   └── insight.py           # Derived insights
├── db/                       # Database initialization
│   └── session.py           # AsyncSessionLocal setup
└── worker/                   # Background task processing

alembic/
├── versions/                 # Migration files (auto-generated)
└── env.py                    # Alembic configuration

scripts/evals/
├── run_memory_benchmarks.py  # EMBER orchestrator
├── run_locomo.py             # LOCOMO benchmark
├── run_longmemeval.py        # LongMemEval benchmark
└── mcp_memory_eval.py        # Shared eval utilities

docs/
├── ARCHITECTURE.md           # System design diagrams and flow
├── evals/
│   ├── BENCHMARK_RUN_TRACKER.md   # Complete run history
│   ├── BENCHMARK_SCORE_SUMMARY.md # Current scores
│   └── artifacts/                 # JSON results (timestamped)
```

## Notes on Memory System Design

The system uses three dimensions for memory management:

1. **Salience** (HIGH/MED/LOW): Emotional importance, affects extraction weighting and retrieval ranking
2. **Scope** (user/shared/companion): Visibility control, determines who can access the memory
3. **Confidence** (0-1): Extraction quality, used for filtering and ranking results

When modifying extraction, search, or retrieval logic, consider all three dimensions — they interact. For example, HIGH salience facts should be extracted with higher confidence thresholds but retrieved eagerly in emotional queries.
