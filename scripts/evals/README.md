# Evals Harness Scripts

These scripts provide a practical harness layer to run LOCOMO, LongMemEval, and EMBER and keep `docs/evals/BENCHMARK_RUN_TRACKER.md` updated.

## Files
- `scripts/evals/benchmark_harness.py`: shared external benchmark harness logic.
- `scripts/evals/run_locomo.py`: LOCOMO runner wrapper.
- `scripts/evals/run_longmemeval.py`: LongMemEval runner wrapper.
- `scripts/evals/run_memory_benchmarks.py`: orchestrates LOCOMO + LongMemEval + EMBER.

## Quick Start

From repo root:

```bash
# 1) Export model credentials (OpenAI key or OpenRouter mapped by wrappers)
export OPENAI_API_KEY="<key>"

# 2) Run everything (LOCOMO, LongMemEval, EMBER)
python scripts/evals/run_memory_benchmarks.py --server-url http://localhost:3100
```

## Individual Runs

```bash
python scripts/evals/run_locomo.py
python scripts/evals/run_longmemeval.py
python scripts/evals/run_memory_benchmarks.py --skip-locomo --skip-longmemeval
```

## Notes
- Defaults now target official benchmark repos:
	- LOCOMO: `snap-research/locomo` using `task_eval/evaluate_qa.py`
	- LongMemEval: `xiaowu0162/LongMemEval` using `src/evaluation/evaluate_qa.py`
- LOCOMO and LongMemEval now generate answers by ingesting benchmark conversations into the local MCP memory server and retrieving through MCP tools before answering.
- LongMemEval writes its generated hypothesis file automatically unless you override `LONGMEMEVAL_HYPOTHESIS_FILE`.
- Default limits are `LOCOMO_LIMIT=5` and `LONGMEMEVAL_LIMIT=25`; override them in the environment if you want a larger run.
- You can still override any default with `--repo-url`, `--setup-command`, and `--run-command`.
- The EMBER run uses your local `.venv` and writes an artifact in `docs/evals/artifacts`.
- Tracker updates are appended as new rows before `## Action Queue`.
