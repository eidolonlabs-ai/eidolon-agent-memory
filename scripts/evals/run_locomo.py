from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from benchmark_harness import REPO_ROOT, run_external_benchmark


def _default_artifact_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "docs/evals/artifacts" / f"locomo_{ts}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LOCOMO benchmark harness")
    parser.add_argument(
        "--repo-dir",
        default=str(REPO_ROOT / "external/evals/locomo"),
        help="Path to LOCOMO harness repository",
    )
    parser.add_argument(
        "--repo-url",
        default=os.getenv("LOCOMO_REPO_URL", "https://github.com/snap-research/locomo.git"),
        help="LOCOMO repository URL for first-time clone",
    )
    parser.add_argument(
        "--run-command",
        default=os.getenv("LOCOMO_RUN_COMMAND", ""),
        help="LOCOMO benchmark command (optional; defaults to official dataset/scoring with a local OpenAI-compatible model endpoint)",
    )
    parser.add_argument(
        "--setup-command",
        action="append",
        default=[],
        help="Optional setup command(s) executed before running LOCOMO (defaults are applied if omitted)",
    )
    parser.add_argument(
        "--artifact-path",
        default=str(_default_artifact_path()),
        help="Path to expected LOCOMO output artifact",
    )
    parser.add_argument(
        "--tracker-path",
        default=str(REPO_ROOT / "docs/evals/BENCHMARK_RUN_TRACKER.md"),
        help="Tracker markdown file",
    )
    return parser


def _default_setup_commands() -> list[str]:
    return [
        "mkdir -p datasets && curl -fsSL https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json -o datasets/locomo10.json",
        "mkdir -p data && cp datasets/locomo10.json data/locomo10.json",
        "mkdir -p outputs",
    ]


def _default_run_command(artifact_path: Path) -> str:
    repo_root = REPO_ROOT.resolve()
    repo_dir = REPO_ROOT / "external/evals/locomo"
    out_file = os.getenv("LOCOMO_OUT_FILE", "outputs/locomo10_qa.json")
    stats_file = out_file.replace(".json", "_stats.json")
    return (
        f"{json.dumps(str(repo_root / '.venv/bin/python'))} "
        f"{json.dumps(str(repo_root / 'scripts/evals/mcp_memory_eval.py'))} locomo "
        f"--repo-dir {json.dumps(str(repo_dir))} "
        "--data-file data/locomo10.json "
        f"--out-file {json.dumps(out_file)} "
        f"--summary-file {json.dumps(str(artifact_path))} "
        f"--stats-file {json.dumps(stats_file)} "
        f"--mcp-url {json.dumps(os.getenv('LOCOMO_MCP_URL', 'http://localhost:3100/mcp'))} "
        f"--answer-model {json.dumps(os.getenv('BENCHMARK_QA_MODEL', 'openai/gpt-4.1-mini'))} "
        f"--model-name {json.dumps(os.getenv('LOCOMO_MODEL_NAME', 'mcp-memory'))} "
        f"--limit {int(os.getenv('LOCOMO_LIMIT', '5'))} "
        + ("--extract-facts" if os.getenv("LOCOMO_EXTRACT_FACTS", "").strip().lower() in {"1", "true", "yes"} else "")
    )


def main() -> None:
    args = build_parser().parse_args()
    artifact_path = Path(args.artifact_path).expanduser().resolve()
    setup_commands = args.setup_command if args.setup_command else _default_setup_commands()
    run_command = args.run_command.strip() if args.run_command else _default_run_command(artifact_path)
    artifact_path = Path(args.artifact_path).expanduser().resolve()
    tracker_path = Path(args.tracker_path).expanduser().resolve()
    result = run_external_benchmark(
        benchmark="LOCOMO",
        run_command=run_command,
        repo_dir=Path(args.repo_dir).expanduser().resolve(),
        repo_url=args.repo_url or None,
        setup_commands=setup_commands,
        artifact_path=artifact_path,
        tracker_path=tracker_path,
    )
    print(f"LOCOMO -> {result.status} ({result.score_summary})")


if __name__ == "__main__":
    main()
