from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import types
import uuid
from pathlib import Path
from typing import Any

import httpx


def _parse_sse_payload(raw: str) -> dict[str, Any]:
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue
    return {}


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _load_dotenv(repo_root: Path) -> None:
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


class McpHttpClient:
    def __init__(self, base_url: str, timeout_seconds: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session_id: str | None = None
        self._client = httpx.Client(timeout=self.timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        response = self._client.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]

        raw = response.text
        if not raw.strip():
            return {}
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return _parse_sse_payload(raw)
        return response.json()

    def initialize(self) -> None:
        self._post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-memory-eval", "version": "0.1"},
                },
            }
        )
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000) % 1_000_000_000,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = response.get("result", {})
        if isinstance(result, dict) and "content" in result:
            content = result.get("content") or []
            if content and isinstance(content[0], dict) and content[0].get("text"):
                text_payload = str(content[0]["text"])
                try:
                    return json.loads(text_payload)
                except json.JSONDecodeError:
                    return {"raw_text": text_payload, "_non_json": True}
        if isinstance(result, dict):
            return result
        raise RuntimeError(f"Unexpected MCP tool response for {name}: {response}")


class OpenAICompatibleResponder:
    def __init__(self, model: str) -> None:
        self.api_key = _env_first("BENCHMARK_LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY or OPENROUTER_API_KEY for benchmark answering")
        self.base_url = _env_first(
            "BENCHMARK_LLM_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_BASE_URL",
            "OPENROUTER_BASE_URL",
            default="https://api.openai.com/v1",
        ).rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=300.0)

    def close(self) -> None:
        self._client.close()

    def answer(self, *, system_prompt: str, user_prompt: str, max_tokens: int = 120) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in self.base_url:
            headers["HTTP-Referer"] = "https://github.com/eidolonlabs-ai/eidolon-agent-memory"
            headers["X-Title"] = "eidolon-agent-memory-benchmarks"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        response = self._client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        return (body["choices"][0]["message"]["content"] or "").strip()


def _question_intent(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in ("when", "first", "last", "how long", "ago", "latest", "recent")):
        return "recall"
    if any(token in lowered for token in ("feel", "emotion", "sad", "happy", "grief", "upset")):
        return "emotional"
    return "factual"


def _render_locomo_session(session_date: str, dialogs: list[dict[str, Any]]) -> tuple[str, str]:
    episodic_lines = [f"DATE: {session_date}", "CONVERSATION:"]
    extract_lines = [f"DATE: {session_date}"]
    for dialog in dialogs:
        speaker = dialog["speaker"].strip()
        text = dialog["text"].strip()
        episodic_lines.append(f"{speaker}: {text}")
        extract_lines.append(f"{speaker}: {text}")
        caption = dialog.get("blip_caption")
        if caption:
            episodic_lines.append(f"{speaker} shared: {caption}")
            extract_lines.append(f"{speaker} shared: {caption}")
    return "\n".join(episodic_lines), "\n".join(extract_lines)


def _render_longmemeval_session(session_date: str, messages: list[dict[str, Any]]) -> tuple[str, str]:
    episodic_lines = [f"DATE: {session_date}", "CONVERSATION:"]
    extract_lines = [f"DATE: {session_date}"]
    for message in messages:
        role = str(message.get("role", "user")).strip().title()
        content = str(message.get("content", "")).strip()
        episodic_lines.append(f"{role}: {content}")
        extract_lines.append(f"{role}: {content}")
    return "\n".join(episodic_lines), "\n".join(extract_lines)


def _collect_memory_context(mcp: McpHttpClient, api_key: str, companion_id: str, query: str) -> str:
    intent = _question_intent(query)
    sections: list[str] = []

    context = mcp.call_tool(
        "get_context",
        {
            "api_key": api_key,
            "companion_id": companion_id,
            "query": query,
            "intent": intent,
        },
    )
    context_text = str(context.get("context", "")).strip()
    if context_text:
        sections.append(context_text)

    facts = mcp.call_tool(
        "search_memory",
        {
            "api_key": api_key,
            "companion_id": companion_id,
            "query": query,
            "intent": intent,
            "limit": 8,
        },
    )
    fact_rows = facts.get("facts") or []
    if fact_rows:
        fact_lines = [f"- {row['fact_text']}" for row in fact_rows if row.get("fact_text")]
        if fact_lines:
            sections.append("Facts:\n" + "\n".join(fact_lines))

    episodic = mcp.call_tool(
        "get_episodic",
        {
            "api_key": api_key,
            "companion_id": companion_id,
            "query": query,
            "limit": 5,
        },
    )
    memories = episodic.get("memories") or []
    if memories:
        memory_lines = [f"- {row['text'][:500]}" for row in memories if row.get("text")]
        if memory_lines:
            sections.append("Memories:\n" + "\n".join(memory_lines))

    return "\n\n".join(section for section in sections if section.strip())


def _answer_question(
    responder: OpenAICompatibleResponder,
    *,
    benchmark: str,
    question: str,
    context: str,
) -> str:
    if not context.strip():
        return "No information available"

    if benchmark == "locomo":
        system_prompt = (
            "You answer memory benchmark questions using only retrieved memory. "
            "Return a short phrase. Prefer exact words from memory. "
            "If the memory does not contain the answer, reply exactly: No information available"
        )
        max_tokens = 48
    else:
        system_prompt = (
            "You answer memory benchmark questions using only retrieved memory. "
            "Be concise but include the necessary facts. "
            "If the answer is unavailable from memory, say that the information is not available."
        )
        max_tokens = 96

    user_prompt = f"Retrieved memory:\n{context}\n\nQuestion: {question}\nAnswer:"
    try:
        answer = responder.answer(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)
    except httpx.HTTPError:
        return "No information available"
    return answer or "No information available"


def _provision_eval_identity(mcp: McpHttpClient) -> tuple[str, str]:
    provisioned = mcp.call_tool(
        "provision_user",
        {
            "email": f"benchmark-{uuid.uuid4().hex[:12]}@example.com",
            "timezone": "UTC",
        },
    )
    api_key = provisioned["api_key"]
    companion = mcp.call_tool(
        "create_companion",
        {
            "api_key": api_key,
            "name": "Benchmark Companion",
            "persona": "Memory benchmark harness",
        },
    )
    return api_key, companion["companion_id"]


def _ingest_sessions(
    mcp: McpHttpClient,
    *,
    api_key: str,
    companion_id: str,
    sessions: list[tuple[str, str]],
    extract_facts: bool,
) -> None:
    for episodic_text, extract_text in sessions:
        mcp.call_tool(
            "store_episodic",
            {
                "api_key": api_key,
                "companion_id": companion_id,
                "text": episodic_text,
                "memory_type": "conversation",
                "importance": 0.7,
            },
        )
        if extract_facts:
            try:
                mcp.call_tool(
                    "extract_session_facts",
                    {
                        "api_key": api_key,
                        "companion_id": companion_id,
                        "conversation_text": extract_text,
                    },
                )
            except (RuntimeError, ValueError, TypeError, json.JSONDecodeError):
                # Extraction is best-effort for benchmark ingestion; retrieval still uses episodic memory.
                continue


def _install_locomo_scoring_stubs() -> None:
    bert_score = types.ModuleType("bert_score")

    def _unused_score(*args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("bert_score is not used in this LOCOMO scoring path")

    bert_score.score = _unused_score
    sys.modules.setdefault("bert_score", bert_score)


def run_locomo(args: argparse.Namespace) -> None:
    repo_dir = Path(args.repo_dir).resolve()
    data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
    out_file = Path(args.out_file).resolve()
    summary_file = Path(args.summary_file).resolve()
    stats_file = Path(args.stats_file).resolve()
    prediction_key = f"{args.model_name}_prediction"
    metric_key = f"{args.model_name}_f1"

    mcp = McpHttpClient(args.mcp_url)
    responder = OpenAICompatibleResponder(args.answer_model)
    mcp.initialize()

    try:
        selected: list[dict[str, Any]] = []
        remaining = args.limit
        for sample in data:
            if remaining <= 0:
                break
            qa = sample.get("qa", [])
            if not qa:
                continue
            take = min(remaining, len(qa))
            selected.append({**sample, "qa": qa[:take]})
            remaining -= take

        results: list[dict[str, Any]] = []
        for sample in selected:
            api_key, companion_id = _provision_eval_identity(mcp)
            sessions: list[tuple[str, str]] = []
            conversation = sample["conversation"]
            session_numbers = sorted(
                int(key.split("_")[-1])
                for key in conversation
                if key.startswith("session_") and not key.endswith("date_time")
            )
            for number in session_numbers:
                episodic_text, extract_text = _render_locomo_session(
                    conversation[f"session_{number}_date_time"],
                    conversation[f"session_{number}"],
                )
                sessions.append((episodic_text, extract_text))

            _ingest_sessions(
                mcp,
                api_key=api_key,
                companion_id=companion_id,
                sessions=sessions,
                extract_facts=args.extract_facts,
            )

            qa_rows: list[dict[str, Any]] = []
            for qa in sample["qa"]:
                row = dict(qa)
                context = _collect_memory_context(mcp, api_key, companion_id, qa["question"])
                row[prediction_key] = _answer_question(
                    responder,
                    benchmark="locomo",
                    question=qa["question"],
                    context=context,
                )
                qa_rows.append(row)
            results.append({"sample_id": sample["sample_id"], "qa": qa_rows})

        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

        _install_locomo_scoring_stubs()
        sys.path.insert(0, str(repo_dir))
        evaluation_mod = importlib.import_module("task_eval.evaluation")
        evaluation_stats_mod = importlib.import_module("task_eval.evaluation_stats")
        eval_question_answering = evaluation_mod.eval_question_answering
        analyze_aggr_acc = evaluation_stats_mod.analyze_aggr_acc

        for sample in results:
            exact_matches, _lengths, _recall = eval_question_answering(sample["qa"], prediction_key)
            for index, score in enumerate(exact_matches):
                sample["qa"][index][metric_key] = round(score, 3)

        out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        analyze_aggr_acc(
            str(Path(args.data_file).resolve()),
            str(out_file),
            str(stats_file),
            args.model_name,
            metric_key,
            rag=False,
        )

        flat_scores = [qa[metric_key] for sample in results for qa in sample["qa"]]
        summary = {
            "benchmark": "LOCOMO",
            "mode": "official_dataset_scoring_mcp_memory",
            "question_count": len(flat_scores),
            "mean_f1": (sum(flat_scores) / len(flat_scores)) if flat_scores else 0.0,
            "model": args.model_name,
            "answer_model": args.answer_model,
            "mcp_url": args.mcp_url,
            "extract_facts": args.extract_facts,
            "out_file": str(out_file),
            "stats_file": str(stats_file),
        }
        summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    finally:
        responder.close()
        mcp.close()


def run_longmemeval(args: argparse.Namespace) -> None:
    data = json.loads(Path(args.data_file).read_text(encoding="utf-8"))
    out_file = Path(args.out_file).resolve()
    mcp = McpHttpClient(args.mcp_url)
    responder = OpenAICompatibleResponder(args.answer_model)
    mcp.initialize()

    try:
        entries = data[: args.limit] if args.limit > 0 else data
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w", encoding="utf-8") as handle:
            for entry in entries:
                api_key, companion_id = _provision_eval_identity(mcp)
                sessions = [
                    _render_longmemeval_session(session_date, session_messages)
                    for session_date, session_messages in zip(
                        entry.get("haystack_dates", []),
                        entry.get("haystack_sessions", []),
                    )
                ]
                _ingest_sessions(
                    mcp,
                    api_key=api_key,
                    companion_id=companion_id,
                    sessions=sessions,
                    extract_facts=args.extract_facts,
                )
                context = _collect_memory_context(mcp, api_key, companion_id, entry["question"])
                hypothesis = _answer_question(
                    responder,
                    benchmark="longmemeval",
                    question=entry["question"],
                    context=context,
                )
                handle.write(
                    json.dumps(
                        {
                            "question_id": entry["question_id"],
                            "hypothesis": hypothesis,
                        }
                    )
                    + "\n"
                )
    finally:
        responder.close()
        mcp.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run benchmark QA generation against the MCP memory server")
    subparsers = parser.add_subparsers(dest="benchmark", required=True)

    locomo = subparsers.add_parser("locomo")
    locomo.add_argument("--repo-dir", required=True)
    locomo.add_argument("--data-file", required=True)
    locomo.add_argument("--out-file", required=True)
    locomo.add_argument("--summary-file", required=True)
    locomo.add_argument("--stats-file", required=True)
    locomo.add_argument("--mcp-url", default="http://localhost:3100/mcp")
    locomo.add_argument("--answer-model", default=_env_first("BENCHMARK_QA_MODEL", default="openai/gpt-4.1-mini"))
    locomo.add_argument("--model-name", default="mcp-memory")
    locomo.add_argument("--limit", type=int, default=int(os.getenv("LOCOMO_LIMIT", "5")))
    locomo.add_argument("--extract-facts", action="store_true")

    longmemeval = subparsers.add_parser("longmemeval")
    longmemeval.add_argument("--data-file", required=True)
    longmemeval.add_argument("--out-file", required=True)
    longmemeval.add_argument("--mcp-url", default="http://localhost:3100/mcp")
    longmemeval.add_argument("--answer-model", default=_env_first("BENCHMARK_QA_MODEL", default="openai/gpt-4.1-mini"))
    longmemeval.add_argument("--limit", type=int, default=int(os.getenv("LONGMEMEVAL_LIMIT", "25")))
    longmemeval.add_argument("--extract-facts", action="store_true")
    return parser


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    _load_dotenv(repo_root)
    args = build_parser().parse_args()
    if args.benchmark == "locomo":
        run_locomo(args)
        return
    if args.benchmark == "longmemeval":
        run_longmemeval(args)
        return
    raise ValueError(args.benchmark)


if __name__ == "__main__":
    main()