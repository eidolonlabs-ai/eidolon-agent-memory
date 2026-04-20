from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKER = REPO_ROOT / "docs/evals/BENCHMARK_RUN_TRACKER.md"
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "docs/evals/artifacts"


@dataclass
class RunResult:
    benchmark: str
    status: str
    score_summary: str
    artifact: str
    notes: str
    run_meta_path: Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_summary(data: Any) -> str:
    if isinstance(data, dict):
        if "score" in data and isinstance(data["score"], (int, float)):
            return f"score={data['score']:.4f}"
        if "results" in data and isinstance(data["results"], list):
            pieces: list[str] = []
            for item in data["results"]:
                if not isinstance(item, dict):
                    continue
                tier = str(item.get("tier", "result"))
                score = item.get("score")
                passed = item.get("passed")
                if isinstance(score, (int, float)):
                    pieces.append(f"{tier}={score:.3f} {'PASS' if passed else 'FAIL'}")
            if pieces:
                return "; ".join(pieces)
    return "see artifact"


def _write_run_meta(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_tracker_row(
    tracker_path: Path,
    date_utc: str,
    benchmark: str,
    score_summary: str,
    status: str,
    artifact: str,
    notes: str,
) -> None:
    content = tracker_path.read_text(encoding="utf-8")
    row = f"| {date_utc} | {benchmark} | Baseline | {score_summary} | {status} | {artifact} | {notes} |\n"

    marker = "\n## Action Queue\n"
    idx = content.find(marker)
    if idx == -1:
        tracker_path.write_text(content.rstrip() + "\n" + row, encoding="utf-8")
        return

    updated = content[:idx].rstrip() + "\n" + row + content[idx:]
    tracker_path.write_text(updated, encoding="utf-8")


def record_tracker_entry(
    *,
    tracker_path: Path,
    benchmark: str,
    score_summary: str,
    status: str,
    artifact: str,
    notes: str,
) -> None:
    date_utc = _utc_now().strftime("%Y-%m-%d")
    _append_tracker_row(
        tracker_path=tracker_path,
        date_utc=date_utc,
        benchmark=benchmark,
        score_summary=score_summary,
        status=status,
        artifact=artifact,
        notes=notes,
    )


def _run_shell(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )


def _maybe_clone_repo(repo_url: str | None, repo_dir: Path) -> str:
    if repo_dir.exists():
        return "repo already present"
    if not repo_url:
        return "no repo_url provided"

    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        cwd=str(repo_dir.parent),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()}")
    return "repo cloned"


def run_external_benchmark(
    *,
    benchmark: str,
    run_command: str | None,
    repo_dir: Path,
    repo_url: str | None,
    setup_commands: list[str],
    artifact_path: Path,
    tracker_path: Path,
) -> RunResult:
    now = _utc_now()
    date_utc = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")

    run_meta_path = artifact_path.with_suffix(".run.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    clone_note = "clone not attempted"
    try:
        clone_note = _maybe_clone_repo(repo_url, repo_dir)
    except RuntimeError as exc:
        payload = {
            "benchmark": benchmark,
            "status": "BLOCKED",
            "timestamp": timestamp,
            "error": str(exc),
        }
        _write_run_meta(run_meta_path, payload)
        return RunResult(
            benchmark=benchmark,
            status="BLOCKED",
            score_summary="N/A",
            artifact="N/A",
            notes=f"{clone_note if 'clone_note' in locals() else 'clone failed'}: {exc}",
            run_meta_path=run_meta_path,
        )

    if not run_command:
        payload = {
            "benchmark": benchmark,
            "status": "BLOCKED",
            "timestamp": timestamp,
            "notes": "No run command provided.",
            "repo_dir": str(repo_dir),
            "repo_status": clone_note,
        }
        _write_run_meta(run_meta_path, payload)
        return RunResult(
            benchmark=benchmark,
            status="BLOCKED",
            score_summary="N/A",
            artifact="N/A",
            notes="No run command provided (set env var or --run-command).",
            run_meta_path=run_meta_path,
        )

    setup_logs: list[dict[str, Any]] = []
    for cmd in setup_commands:
        completed = _run_shell(cmd, repo_dir)
        setup_logs.append(
            {
                "command": cmd,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            payload = {
                "benchmark": benchmark,
                "status": "BLOCKED",
                "timestamp": timestamp,
                "repo_dir": str(repo_dir),
                "setup": setup_logs,
                "notes": "Setup command failed.",
            }
            _write_run_meta(run_meta_path, payload)
            return RunResult(
                benchmark=benchmark,
                status="BLOCKED",
                score_summary="N/A",
                artifact="N/A",
                notes=f"Setup failed: {cmd}",
                run_meta_path=run_meta_path,
            )

    completed = _run_shell(run_command, repo_dir)

    payload = {
        "benchmark": benchmark,
        "timestamp": timestamp,
        "repo_dir": str(repo_dir),
        "repo_status": clone_note,
        "run_command": run_command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "setup": setup_logs,
        "artifact_path": str(artifact_path),
    }

    status = "PASS" if completed.returncode == 0 else "FAIL"
    notes = "command completed"
    score_summary = "see artifact"
    artifact_ref = str(artifact_path)

    if artifact_path.exists():
        try:
            parsed = json.loads(artifact_path.read_text(encoding="utf-8"))
            score_summary = _safe_summary(parsed)
        except json.JSONDecodeError:
            score_summary = "non-json artifact"
    else:
        artifact_ref = str(run_meta_path)
        notes = "No benchmark artifact found; see run metadata."

    payload["status"] = status
    payload["score_summary"] = score_summary
    payload["notes"] = notes
    _write_run_meta(run_meta_path, payload)

    _append_tracker_row(
        tracker_path=tracker_path,
        date_utc=date_utc,
        benchmark=benchmark,
        score_summary=score_summary,
        status=status,
        artifact=artifact_ref,
        notes=notes,
    )

    return RunResult(
        benchmark=benchmark,
        status=status,
        score_summary=score_summary,
        artifact=artifact_ref,
        notes=notes,
        run_meta_path=run_meta_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generic external benchmark harness runner")
    parser.add_argument("--benchmark", required=True, help="Benchmark display name")
    parser.add_argument("--repo-dir", required=True, help="Path to external benchmark repo")
    parser.add_argument("--repo-url", default="", help="Optional git repo URL to clone")
    parser.add_argument("--run-command", default="", help="Command that runs the benchmark")
    parser.add_argument(
        "--setup-command",
        action="append",
        default=[],
        help="Optional setup command(s) executed before run-command",
    )
    parser.add_argument(
        "--artifact-path",
        required=True,
        help="Expected output artifact path written by benchmark command",
    )
    parser.add_argument(
        "--tracker-path",
        default=str(DEFAULT_TRACKER),
        help="Benchmark tracker markdown path",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    result = run_external_benchmark(
        benchmark=args.benchmark,
        run_command=args.run_command or None,
        repo_dir=Path(args.repo_dir).expanduser().resolve(),
        repo_url=args.repo_url or None,
        setup_commands=args.setup_command,
        artifact_path=Path(args.artifact_path).expanduser().resolve(),
        tracker_path=Path(args.tracker_path).expanduser().resolve(),
    )

    print(f"benchmark={result.benchmark}")
    print(f"status={result.status}")
    print(f"score_summary={result.score_summary}")
    print(f"artifact={result.artifact}")
    print(f"notes={result.notes}")
    print(f"run_meta={result.run_meta_path}")


if __name__ == "__main__":
    main()
