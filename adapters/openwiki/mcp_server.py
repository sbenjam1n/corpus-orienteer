#!/usr/bin/env python3
"""Read-only MCP (Model Context Protocol) server over stdio for the onto/audit RAG engine.

Exposes the engine's orientation surfaces as MCP tools: brief, orient, search, page,
timeline, monitors. Every tool is a read-only dispatch into scripts/rag/query.py or
orient.py — the server never mutates the corpus, seeds, or build outputs (run
`./rag rebuild` separately/on a schedule to refresh the graph).

Stdlib-only, newline-delimited JSON-RPC 2.0 on stdio (the MCP stdio transport). Designed
for OpenWiki's `McpConnectorConfig` (`mode: "mcp-stdio"`) but works with any MCP client.

Configuration: the standard engine env vars (RAG_CORPUS_DIR / RAG_SEED_DIR /
RAG_DATA_DIR), passed through to the engine subprocesses; defaults resolve exactly as
the engine's own defaults do. Set them in the MCP client's `transport.env`.

Usage:  python3 adapters/openwiki/mcp_server.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "corpus-orienteer", "version": "1.0.0"}

TOOLS = [
    {
        "name": "brief",
        "description": (
            "Warm-start digest of the whole research corpus: active arcs, distrusted "
            "methods, unmet monitors, drift flags, changed-since-last-pass documents. "
            "Deterministic distillation of the current build; read this first in a session."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "orient",
        "description": (
            "Plan-scoped orientation for specific corpus documents you are about to act "
            "on: superseded/corrected citations (with the winning document to read "
            "instead), stale numeric-assertion candidates, method reliability, in-scope "
            "unmet monitors, correction arcs. Pass document ids (e.g. 'VR-12') and/or "
            "repo-relative markdown paths."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "documents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Document ids (VR-N / AUDIT-N) or markdown file paths",
                }
            },
            "required": ["documents"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search",
        "description": (
            "Search the corpus (semantic if the vector layer is built, else TF-IDF). "
            "Retracted/deprecated documents are down-weighted."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "page",
        "description": (
            "Consolidated record of a canonical domain object (by id or any alias): "
            "type, aliases, seeded authoritative facts with provenance and epistemic "
            "stratum, typed links, claims, mention stats, drift flags."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"object": {"type": "string"}},
            "required": ["object"],
            "additionalProperties": False,
        },
    },
    {
        "name": "timeline",
        "description": "Value/concept evolution of an entity across the corpus, in document order.",
        "inputSchema": {
            "type": "object",
            "properties": {"entity": {"type": "string"}},
            "required": ["entity"],
            "additionalProperties": False,
        },
    },
    {
        "name": "monitors",
        "description": (
            "Declared object monitors with their evaluated state from the current build "
            "(unmet first). Candidates are regions to read, never verdicts."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

# tool name -> argv builder (read-only query dispatches only)
def _tool_argv(name, args):
    q = [sys.executable, str(ROOT / "scripts" / "rag" / "query.py")]
    if name == "brief":
        return q + ["brief"]
    if name == "orient":
        return [sys.executable, str(ROOT / "scripts" / "rag" / "orient.py")] + list(args["documents"])
    if name == "search":
        return q + ["search", args["query"]]
    if name == "page":
        return q + ["page", args["object"]]
    if name == "timeline":
        return q + ["timeline", args["entity"]]
    if name == "monitors":
        return q + ["monitors"]
    return None


def _run_tool(name, args):
    argv = _tool_argv(name, args or {})
    if argv is None:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    try:
        proc = subprocess.run(
            argv, cwd=ROOT, capture_output=True, text=True, timeout=120, env=os.environ.copy()
        )
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": f"{name}: timed out after 120s"}], "isError": True}
    out = proc.stdout.strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        tail = "\n".join(err[-8:]) if err else "(no stderr)"
        return {
            "content": [{"type": "text", "text": f"{name} failed (exit {proc.returncode}):\n{tail}"}],
            "isError": True,
        }
    return {"content": [{"type": "text", "text": out or "(empty result)"}]}


def _handle(req):
    """Return a response dict for a request, or None for a notification."""
    method = req.get("method")
    req_id = req.get("id")
    is_notification = "id" not in req

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = req.get("params") or {}
        result = _run_tool(params.get("name"), params.get("arguments") or {})
    elif method == "ping":
        result = {}
    elif is_notification:  # notifications/initialized etc.
        return None
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            print(json.dumps(resp), flush=True)
            continue
        resp = _handle(req)
        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
