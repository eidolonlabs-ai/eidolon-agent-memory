#!/usr/bin/env python3
"""Smoke test for Eidolon Agent Memory MCP server."""
import urllib.request
import json

BASE = "http://localhost:3100/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_sse(raw: str) -> str:
    """Extract the first JSON value from an SSE stream."""
    for line in raw.splitlines():
        if line.startswith("data: "):
            return line[6:]
    return raw  # fallback for plain JSON responses


def post(payload, session_id=None):
    h = dict(HEADERS)
    if session_id:
        h["mcp-session-id"] = session_id
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode(), headers=h, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        new_sid = r.headers.get("mcp-session-id")
        raw = r.read().decode()
        body = parse_sse(raw) if raw.strip() else raw
        return new_sid or session_id, body


# 1. Initialize
sid, body = post({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.1"},
    },
})
print(f"Session ID: {sid}")
data = json.loads(body)
print(f"Server name: {data.get('result', {}).get('serverInfo', {})}")

# 2. Initialized notification
post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, sid)

# 3. Provision a user
sid, body = post({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "provision_user",
        "arguments": {"email": "test@example.com", "timezone": "UTC"},
    },
}, sid)
print(f"\nprovision_user response:")
data = json.loads(body)
result = data.get("result", {})
if "content" in result:
    inner = json.loads(result["content"][0]["text"])
    print(json.dumps(inner, indent=2))
    api_key = inner.get("api_key")
    print(f"\nAPI key: {api_key}")
else:
    print(json.dumps(data, indent=2))
    api_key = None

# 4. Call info with api_key
if api_key:
    sid, body = post({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "info",
            "arguments": {"api_key": api_key},
        },
    }, sid)
    print(f"\ninfo response:")
    data = json.loads(body)
    result = data.get("result", {})
    if "content" in result:
        inner = json.loads(result["content"][0]["text"])
        print(json.dumps(inner, indent=2))
    else:
        print(json.dumps(data, indent=2))
