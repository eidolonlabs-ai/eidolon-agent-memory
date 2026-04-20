# Evals Benchmark Plan (LOCOMO, LongMemEval, EMBER)

## Objective
Run recognized memory benchmarks in this order:
1. LOCOMO baseline
2. LongMemEval baseline
3. EMBER improvement loop (priority benchmark for companion-memory behavior)

## Why This Order
- LOCOMO and LongMemEval provide external baseline confidence.
- EMBER focuses on emotionally-salient companion memory behaviors (graceful omission and two-way memory) and remains the optimization target after baseline validation.

## Canonical Sources
- Benchmark matrix: [ember-benchmark/docs/BENCHMARK_MATRIX.md](ember-benchmark/docs/BENCHMARK_MATRIX.md)
- Multi-benchmark plan: [ember-benchmark/docs/MULTI_BENCHMARK_TESTING_PLAN.md](ember-benchmark/docs/MULTI_BENCHMARK_TESTING_PLAN.md)
- Run tracker: [ember-benchmark/docs/BENCHMARK_TRACKER.md](ember-benchmark/docs/BENCHMARK_TRACKER.md)

These sources were added in commit af95fd454b2f68618c2d89c8c255cf87d6d8b7be and should be treated as benchmark-policy truth.

## Current State
- EMBER: integrated and runnable against local MCP server.
- LOCOMO: not yet wired into this repo.
- LongMemEval: not yet wired into this repo.

## Baseline Gate
Before deeper EMBER tuning, complete:
1. One successful LOCOMO run with stored artifact.
2. One successful LongMemEval run with stored artifact.
3. Tracker update in docs/evals/BENCHMARK_RUN_TRACKER.md.

## EMBER Priority Loop
After external baselines are captured:
1. Keep Tier 2 and Tier 2b in passing state.
2. Improve Tier 1 extraction weighted recall toward threshold.
3. Improve Tier 3 roundtrip by lifting extraction and retrieval alignment.
4. Log each run in tracker with artifact path and brief delta notes.

## Planned Commands

```bash
# LOCOMO harness wrapper
python scripts/evals/run_locomo.py

# LongMemEval harness wrapper
python scripts/evals/run_longmemeval.py

# Full sequence (LOCOMO + LongMemEval + EMBER)
python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100

# EMBER (active command)
. .venv/bin/activate && python -m ember.cli run \
  --adapter eidolon-agent-memory \
  --url http://localhost:3100 \
  --json /Users/markcastillo/git/eidolon-agent-memory/ember_results_latest.json
```

## Ownership and Updates
- Update this plan whenever benchmark execution method changes.
- Keep benchmark status snapshots in BENCHMARK_RUN_TRACKER.md.
- Script usage details: [scripts/evals/README.md](scripts/evals/README.md)
