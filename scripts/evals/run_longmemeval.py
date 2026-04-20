from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from benchmark_harness import REPO_ROOT, run_external_benchmark


def _default_artifact_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "docs/evals/artifacts" / f"longmemeval_{ts}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LongMemEval benchmark harness")
    parser.add_argument(
        "--repo-dir",
        default=str(REPO_ROOT / "external/evals/LongMemEval"),
        help="Path to LongMemEval harness repository",
    )
    parser.add_argument(
        "--repo-url",
        default=os.getenv("LONGMEMEVAL_REPO_URL", "https://github.com/xiaowu0162/LongMemEval.git"),
        help="LongMemEval repository URL for first-time clone",
    )
    parser.add_argument(
        "--run-command",
        default=os.getenv("LONGMEMEVAL_RUN_COMMAND", ""),
        help="LongMemEval benchmark command (optional; defaults to official evaluation flow)",
    )
    parser.add_argument(
        "--setup-command",
        action="append",
        default=[],
        help="Optional setup command(s) executed before running LongMemEval (defaults are applied if omitted)",
    )
    parser.add_argument(
        "--artifact-path",
        default=str(_default_artifact_path()),
        help="Path to expected LongMemEval output artifact",
    )
    parser.add_argument(
        "--tracker-path",
        default=str(REPO_ROOT / "docs/evals/BENCHMARK_RUN_TRACKER.md"),
        help="Tracker markdown file",
    )
    return parser


def _default_setup_commands() -> list[str]:
    return [
        "mkdir -p data",
        "curl -fsSL https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json -o data/longmemeval_oracle.json",
        "python3 -m venv .venv-eval",
        ".venv-eval/bin/python -m pip install -U pip",
        ".venv-eval/bin/python -m pip install packaging openai==1.35.1 'httpx<0.28' tqdm==4.66.4 backoff==2.2.1 numpy==1.26.3 nltk==3.9.1",
    ]


def _default_run_command(artifact_path: Path) -> str:
    artifact_literal = json.dumps(str(artifact_path))
    repo_root = REPO_ROOT.resolve()
    hypothesis_file = os.getenv(
        "LONGMEMEVAL_HYPOTHESIS_FILE",
        str(REPO_ROOT / "docs/evals/artifacts/longmemeval_hypothesis.jsonl"),
    )
    judge_model = os.getenv("LONGMEMEVAL_JUDGE_MODEL", "gpt-4o-mini")
    extract_flag = (
        "--extract-facts "
        if os.getenv("LONGMEMEVAL_EXTRACT_FACTS", "").strip().lower() in {"1", "true", "yes"}
        else ""
    )
    return (
        "set -a && [ -f ../../../.env ] && . ../../../.env || true; set +a; "
        "if [ -n \"${OPENROUTER_API_KEY:-}\" ] && [ -z \"${OPENAI_API_KEY:-}\" ]; then export OPENAI_API_KEY=\"$OPENROUTER_API_KEY\"; fi; "
        "if [ -n \"${OPENROUTER_BASE_URL:-}\" ] && [ -z \"${OPENAI_API_BASE:-}\" ]; then export OPENAI_API_BASE=\"$OPENROUTER_BASE_URL\"; fi; "
        "if [ -n \"${OPENAI_API_BASE:-}\" ] && [ -z \"${OPENAI_BASE_URL:-}\" ]; then export OPENAI_BASE_URL=\"$OPENAI_API_BASE\"; fi; "
        "if [ -z \"${OPENAI_BASE_URL:-}\" ] && [ -n \"${OPENAI_API_KEY:-}\" ]; then export OPENAI_BASE_URL=https://api.openai.com/v1; fi; "
        f"export LONGMEMEVAL_HYPOTHESIS_FILE={json.dumps(hypothesis_file)}; "
        "if [ -z \"${OPENAI_API_KEY:-}\" ]; then echo 'Missing OPENAI_API_KEY/OPENROUTER_API_KEY for LongMemEval run' >&2; exit 2; fi; "
        f"{json.dumps(str(repo_root / '.venv/bin/python'))} {json.dumps(str(repo_root / 'scripts/evals/mcp_memory_eval.py'))} longmemeval "
        "--data-file data/longmemeval_oracle.json "
        "--out-file \"$LONGMEMEVAL_HYPOTHESIS_FILE\" "
        f"--mcp-url {json.dumps(os.getenv('LONGMEMEVAL_MCP_URL', 'http://localhost:3100/mcp'))} "
        f"--answer-model {json.dumps(os.getenv('BENCHMARK_QA_MODEL', 'openai/gpt-4.1-mini'))} "
        f"--limit {int(os.getenv('LONGMEMEVAL_LIMIT', '25'))} "
        f"{extract_flag}"
        "&& "
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "import os\n"
        "hyp_raw = os.environ.get('LONGMEMEVAL_HYPOTHESIS_FILE', '').strip()\n"
        "hyp = Path(hyp_raw) if hyp_raw else None\n"
        "if hyp is None:\n"
        "    raise SystemExit('Set LONGMEMEVAL_HYPOTHESIS_FILE to a jsonl file containing question_id and hypothesis fields')\n"
        "if not hyp.exists():\n"
        "    raise SystemExit(f'Hypothesis file not found: {hyp}')\n"
        "PY\n"
        "cd src/evaluation && "
        f"../../.venv-eval/bin/python evaluate_qa.py {judge_model} \"$LONGMEMEVAL_HYPOTHESIS_FILE\" ../../data/longmemeval_oracle.json && "
        "python3 - <<'PY'\n"
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        f"result_path = Path(os.environ['LONGMEMEVAL_HYPOTHESIS_FILE'] + '.eval-results-{judge_model}')\n"
        "rows = [json.loads(line) for line in result_path.read_text(encoding='utf-8').splitlines() if line.strip()]\n"
        "correct = sum(1 for r in rows if bool(r.get('autoeval_label', {}).get('label')))\n"
        "total = len(rows)\n"
        "summary = {'benchmark':'LongMemEval','mode':'official_evaluation_mcp_memory','judge_model': os.environ.get('LONGMEMEVAL_JUDGE_MODEL', 'gpt-4o-mini'),'total':total,'correct':correct,'accuracy':(correct/total if total else 0.0),'hypothesis_file': os.environ['LONGMEMEVAL_HYPOTHESIS_FILE'],'result_file': str(result_path)}\n"
        f"Path({artifact_literal}).write_text(json.dumps(summary, indent=2), encoding='utf-8')\n"
        "PY"
    )


def main() -> None:
    args = build_parser().parse_args()
    artifact_path = Path(args.artifact_path).expanduser().resolve()
    setup_commands = args.setup_command if args.setup_command else _default_setup_commands()
    run_command = args.run_command.strip() if args.run_command else _default_run_command(artifact_path)
    artifact_path = Path(args.artifact_path).expanduser().resolve()
    tracker_path = Path(args.tracker_path).expanduser().resolve()
    result = run_external_benchmark(
        benchmark="LongMemEval",
        run_command=run_command,
        repo_dir=Path(args.repo_dir).expanduser().resolve(),
        repo_url=args.repo_url or None,
        setup_commands=setup_commands,
        artifact_path=artifact_path,
        tracker_path=tracker_path,
    )
    print(f"LongMemEval -> {result.status} ({result.score_summary})")


if __name__ == "__main__":
    main()
