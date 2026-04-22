# Eidolon Agent Memory

A companion cognitive memory platform implemented as an **MCP (Model Context Protocol) server** for conversational AI systems. Stores and retrieves facts, relationships, episodic memories, and preferences with emphasis on emotional salience awareness and graceful handling of sensitive content.

## Quick Start

### Docker (Recommended)
```bash
docker compose up -d --build
```

### Manual Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m eidolon_agent_memory
```

The MCP server will be available at `http://localhost:3100/mcp`

### Configuration
Create a `.env` file or set environment variables:
```env
# LLM Configuration
LLM_API_BASE=http://localhost:1234/v1           # Local LM Studio or OpenAI-compatible
LLM_MODEL=local-model                           # Model name to use
LLM_API_KEY=not-used                            # Required for cloud APIs

# Database
DATABASE_URL=postgresql://user:pass@localhost/eidolon_memory
POSTGRES_PASSWORD=password

# Embeddings
EMBEDDING_MODEL=nomic-embed-text                # All-MiniLM-L6-v2 or similar
EMBEDDING_API_BASE=http://localhost:8000        # Ollama or compatible

# Optional
DEBUG=false
REDIS_URL=redis://localhost:6379
```

## Architecture

See the end-to-end system diagram: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

### Data Model
- **MemoryNode**: Entities with embeddings, importance scores, confidence levels
- **MemoryEdge**: Facts (subject→predicate→object) with emotional metadata:
  - `emotional_salience`: HIGH (grief, loss, trauma) | MED (milestones) | LOW (preferences, trivia)
  - `scope`: user | shared | companion (determines visibility)
- **Semantic Search**: Context-aware retrieval with `SearchIntent` types (factual, emotional, casual, recall)

### Core Services
| Service | Purpose |
|---------|---------|
| `llm.py` | LLM completions with JSON parsing & corrective retry |
| `extraction.py` | Fact extraction from conversations with salience-weighted quality scoring |
| `search.py` | Vector + semantic search with emotional context filtering |
| `memory.py` | CRUD operations and relationship management |
| `embedding.py` | Text vectorization with fallback handling |

### 27+ MCP Tools
Grouped into four categories:
- **Memory Read**: `memory_search`, `memory_get_facts`, `memory_get_context`
- **Memory Write**: `memory_store_fact`, `memory_update_relationship`, `memory_delete_fact`
- **Cognitive**: `get_companion_values`, `get_user_profile`, `analyze_relationships`
- **Companion**: `get_companion_context`, `store_companion_perspective`

## Current Benchmark Performance

### Latest Run: April 20, 2026 @ 05:05:04 UTC

| Benchmark | Tier/Metric | Score | Threshold | Status |
|-----------|-------------|-------|-----------|--------|
| **EMBER** | Tier 1: Extraction Quality | 0.6429 | ≥0.80 | ✗ FAIL |
| | Tier 2: Retrieval Quality | 0.8562 | ≥0.75 | ✓ PASS |
| | Tier 2b: Graceful Omission | 1.0000 | ≥0.75 | ✓ PASS |
| | Tier 3: End-to-End Roundtrip | 0.4521 | ≥0.60 | ✗ FAIL |
| **LOCOMO** | Mean F1 Score | 0.3168 | — | — |
| **LongMemEval** | Accuracy | 0.4800 | — | — |

### Extraction Breakdown (Tier 1)
- **HIGH salience facts**: 18/29 (62%) — grief, loss, trauma
- **MED salience facts**: 16/24 (67%) — milestones, events
- **LOW salience facts**: 4/5 (80%) — preferences, trivia

**Key Insight**: Retrieval system is working well (0.856 PASS). Extraction bottleneck limits roundtrip performance. Graceful omission handling is perfect (never surfaces crisis content inappropriately).

## Benchmarks

Three benchmarks evaluate different aspects of memory quality:

### 1. EMBER (Emotionally-aware Memory Benchmark)
Tier 1-3 evaluation of extraction, retrieval, and roundtrip performance:
```bash
# Full run (all tiers)
. .venv/bin/activate && python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100

# Specific tier
python -m ember.cli run --adapter eidolon-agent-memory --url http://localhost:3100 --tiers 1,2
```

### 2. LOCOMO (Localized Compositional Memory)
Direct MCP-backed QA evaluation:
```bash
LOCOMO_EXTRACT_FACTS=1 python scripts/evals/run_locomo.py
```

### 3. LongMemEval (Long-context Memory)
Extended conversation retention with GPT-4o-mini judging:
```bash
LONGMEMEVAL_EXTRACT_FACTS=1 python scripts/evals/run_longmemeval.py
```

### Viewing Results
- **Artifacts**: `docs/evals/artifacts/` (JSON files timestamped with UTC execution time)
- **Tracker**: `docs/evals/BENCHMARK_RUN_TRACKER.md` (complete run history and trends)
- **Summaries**: See latest scores above or check `BENCHMARK_SCORE_SUMMARY.md`

## Development

### Testing
```bash
# Run extraction tests
python -m pytest test_extraction.py -v

# Integration test
python -m pytest test_full_integration.py -v

# Debug a specific component
python debug_extraction.py
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## Troubleshooting

### Connection Issues
- **Server not responding**: Check `docker compose logs server`
- **Database not starting**: Verify `POSTGRES_PASSWORD` in `.env` and check `docker compose logs postgres`
- **LLM timeout**: Increase `LLM_TIMEOUT_SECONDS` (default 120s)

### Extraction Quality Issues
- Check extraction quality with: `docker compose logs server | grep "extraction"`
- Review extraction prompt in `src/eidolon_agent_memory/services/extraction.py`
- Verify LLM is responding: `python test_single_search.py`

### Benchmark Failures
- Ensure Docker containers are healthy: `docker compose ps`
- Check server is responding: `curl http://localhost:3100/health`
- View benchmark logs: `tail -f docs/evals/artifacts/ember_*.json`

## Project Structure
```
src/eidolon_agent_memory/
├── services/          # Core business logic
│   ├── llm.py         # LLM completions with error handling
│   ├── extraction.py  # Fact extraction from conversations
│   ├── search.py      # Vector & semantic search
│   ├── memory.py      # Memory CRUD operations
│   └── embedding.py   # Text vectorization
├── tools/             # 27+ MCP tools
├── models/            # SQLAlchemy ORM
└── __init__.py        # MCP server entry point

scripts/evals/
├── run_memory_benchmarks.py    # Main orchestrator
├── run_locomo.py               # LOCOMO benchmark
├── run_longmemeval.py          # LongMemEval benchmark
└── mcp_memory_eval.py          # Shared evaluation logic

docs/evals/
├── BENCHMARK_RUN_TRACKER.md    # Complete run history
├── BENCHMARK_SCORE_SUMMARY.md  # Current score summary
└── artifacts/                  # JSON benchmark results
```

## Key Features

✅ **Emotional Salience Awareness**: Tracks HIGH/MED/LOW importance, weights extraction/retrieval accordingly

✅ **Graceful Omission**: Sensitive facts (crisis content) never surface in casual queries (Tier 2b: 1.0 PASS)

✅ **Semantic Search**: Context-aware retrieval with emotional filtering

✅ **MCP Integration**: Full Model Context Protocol support for seamless AI integration

✅ **Timeout Protection**: 120s LLM timeout prevents infinite hangs

✅ **PostgreSQL + pgvector**: Scalable vector search and relationship management

## Contributing

1. Branch from `main`
2. Run tests: `pytest -v`
3. Update BENCHMARK_RUN_TRACKER.md if changing extraction/retrieval logic
4. Submit PR with benchmark results

## License

See LICENSE file

## Support

- **Issues**: GitHub issues
- **Benchmark Questions**: See `docs/evals/BENCHMARK_RUN_TRACKER.md` for run history
- **Architecture**: Check EMBER benchmark instructions in `.github/copilot-instructions.md` (if in ember-benchmark repo)
