from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKER = REPO_ROOT / "docs/evals/BENCHMARK_RUN_TRACKER.md"
ARTIFACT_DIR = REPO_ROOT / "docs/evals/artifacts"


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )


def _append_tracker_row(
    *,
    benchmark: str,
    score_summary: str,
    status: str,
    artifact: str,
    notes: str,
) -> None:
    date_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = f"| {date_utc} | {benchmark} | Priority | {score_summary} | {status} | {artifact} | {notes} |\n"

    content = TRACKER.read_text(encoding="utf-8")
    marker = "\n## Action Queue\n"
    idx = content.find(marker)
    if idx == -1:
        TRACKER.write_text(content.rstrip() + "\n" + row, encoding="utf-8")
        return
    TRACKER.write_text(content[:idx].rstrip() + "\n" + row + content[idx:], encoding="utf-8")


def _ember_summary(results_path: Path) -> str:
    if not results_path.exists():
        return "No result json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    parts: list[str] = []
    for result in data.get("results", []):
        tier = str(result.get("tier", ""))
        score = result.get("score")
        passed = bool(result.get("passed", False))
        if isinstance(score, (int, float)):
            parts.append(f"{tier}={score:.3f} {'PASS' if passed else 'FAIL'}")
    return "; ".join(parts) if parts else "No scores"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LOCOMO, LongMemEval and EMBER in sequence")
    parser.add_argument("--skip-locomo", action="store_true", help="Skip LOCOMO")
    parser.add_argument("--skip-longmemeval", action="store_true", help="Skip LongMemEval")
    parser.add_argument("--skip-ember", action="store_true", help="Skip EMBER")
    parser.add_argument("--server-url", default="http://localhost:3100", help="MCP server URL for EMBER")
    parser.add_argument(
        "--ember-adapter",
        default="eidolon-agent-memory",
        help="EMBER adapter name",
    )
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_locomo:
        locomo = _run("python scripts/evals/run_locomo.py", REPO_ROOT)
        print(locomo.stdout)
        if locomo.returncode != 0:
            print(locomo.stderr)

    if not args.skip_longmemeval:
        longmemeval = _run("python scripts/evals/run_longmemeval.py", REPO_ROOT)
        print(longmemeval.stdout)
        if longmemeval.returncode != 0:
            print(longmemeval.stderr)

    if not args.skip_ember:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ember_path = ARTIFACT_DIR / f"ember_{ts}.json"
        ember_cmd = (
            f". .venv/bin/activate && python -m ember.cli run "
            f"--adapter {args.ember_adapter} --url {args.server_url} --json {ember_path}"
        )
        result = _run(ember_cmd, REPO_ROOT)
        # EMBER exits non-zero when tier(s) fail. We still treat this as a completed run if json exists.
        summary = _ember_summary(ember_path)
        status = "PASS" if "FAIL" not in summary else "PARTIAL"
        notes = "Full EMBER run completed"
        if not ember_path.exists():
            status = "FAIL"
            notes = "EMBER run did not produce artifact"

        _append_tracker_row(
            benchmark="EMBER (full)",
            score_summary=summary,
            status=status,
            artifact=str(ember_path if ember_path.exists() else "N/A"),
            notes=notes,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)


if __name__ == "__main__":
    main()
