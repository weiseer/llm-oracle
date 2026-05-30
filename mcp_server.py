#!/usr/bin/env python3
"""LLM Oracle MCP server — exposes the catalog as MCP tools.

Run via:
    python mcp_server.py             # stdio mode for local MCP clients (Claude Desktop, Cursor, etc.)
    python mcp_server.py --http PORT  # HTTP/SSE mode for remote agents (default 8765)

Catalog source: data/catalog.json (local) or env LLM_ORACLE_URL (remote fetch).

License: Apache-2.0
Probe ID: P-001 (organism strategic backlog v2)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.request
from typing import Any

CATALOG_LOCAL = pathlib.Path(__file__).parent / "catalog.json"
CATALOG_URL_ENV = "LLM_ORACLE_URL"
DEFAULT_REMOTE = "https://oracle.weiseer.com/catalog.json"

_CACHED: dict[str, Any] = {}
_CACHED_AT: float = 0.0
_CACHE_TTL = 600  # 10 min


def _load_catalog() -> dict[str, Any]:
    global _CACHED, _CACHED_AT
    if _CACHED and (time.time() - _CACHED_AT) < _CACHE_TTL:
        return _CACHED
    url = os.environ.get(CATALOG_URL_ENV)
    if url:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                _CACHED = json.loads(r.read().decode())
                _CACHED_AT = time.time()
                return _CACHED
        except Exception:
            pass
    if CATALOG_LOCAL.exists():
        _CACHED = json.loads(CATALOG_LOCAL.read_text(encoding="utf-8"))
        _CACHED_AT = time.time()
        return _CACHED
    return {"models": [], "as_of": "unknown", "schema_version": "0.0.0"}


def _all_models() -> list[dict]:
    return _load_catalog().get("models", [])


# ---- tool implementations ----

def tool_list_models(provider: str | None = None, capability: str | None = None) -> dict:
    """List models, optionally filtered by provider or required capability."""
    models = _all_models()
    if provider:
        models = [m for m in models if m.get("provider", "").lower() == provider.lower()]
    if capability:
        models = [m for m in models if m.get("capabilities", {}).get(capability) is True]
    return {
        "as_of": _load_catalog().get("as_of"),
        "count": len(models),
        "models": [
            {
                "model_id": m["model_id"],
                "provider": m["provider"],
                "display_name": m.get("display_name"),
                "context_window": m.get("context_window"),
                "input_price": m.get("input_price"),
                "output_price": m.get("output_price"),
                "availability_status": m.get("availability_status"),
            }
            for m in models
        ],
    }


def tool_get_model(model_id: str) -> dict:
    """Return full record for one model."""
    for m in _all_models():
        if m["model_id"] == model_id:
            return m
    return {"error": f"model_id '{model_id}' not found", "as_of": _load_catalog().get("as_of")}


def tool_find_cheapest(input_tokens: int, output_tokens: int,
                       required_capabilities: list[str] | None = None,
                       only_operational: bool = True) -> dict:
    """Return models ranked by estimated cost for a given token spec, lowest first.

    Cost = (input_tokens/1M * input_price) + (output_tokens/1M * output_price)
    Skips models missing required_capabilities or not operational (when only_operational=True).
    """
    candidates = []
    for m in _all_models():
        if only_operational and m.get("availability_status") != "operational":
            continue
        caps = m.get("capabilities", {})
        if required_capabilities and not all(caps.get(c) for c in required_capabilities):
            continue
        ip = m.get("input_price")
        op = m.get("output_price")
        if ip is None or op is None:
            continue
        cost = (input_tokens / 1_000_000.0) * ip + (output_tokens / 1_000_000.0) * op
        candidates.append({
            "model_id": m["model_id"],
            "provider": m["provider"],
            "estimated_cost_usd": round(cost, 6),
            "context_window": m.get("context_window"),
            "availability_status": m.get("availability_status"),
        })
    candidates.sort(key=lambda x: x["estimated_cost_usd"])
    return {
        "as_of": _load_catalog().get("as_of"),
        "query": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                  "required_capabilities": required_capabilities or [],
                  "only_operational": only_operational},
        "count": len(candidates),
        "ranked": candidates,
    }


def tool_compare_models(model_ids: list[str], input_tokens: int = 1000,
                        output_tokens: int = 500) -> dict:
    """Side-by-side comparison of a set of models for a token spec."""
    by_id = {m["model_id"]: m for m in _all_models()}
    rows = []
    for mid in model_ids:
        m = by_id.get(mid)
        if not m:
            rows.append({"model_id": mid, "error": "not_found"})
            continue
        ip = m.get("input_price") or 0
        op = m.get("output_price") or 0
        cost = (input_tokens / 1_000_000.0) * ip + (output_tokens / 1_000_000.0) * op
        rows.append({
            "model_id": mid,
            "provider": m.get("provider"),
            "input_price": ip,
            "output_price": op,
            "context_window": m.get("context_window"),
            "max_output_tokens": m.get("max_output_tokens"),
            "capabilities": m.get("capabilities", {}),
            "availability_status": m.get("availability_status"),
            "estimated_cost_usd": round(cost, 6),
        })
    return {"as_of": _load_catalog().get("as_of"),
            "query": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "rows": rows}


def tool_check_availability(model_id: str) -> dict:
    """Return current availability status for a model with source citation."""
    for m in _all_models():
        if m["model_id"] == model_id:
            return {
                "model_id": model_id,
                "availability_status": m.get("availability_status"),
                "source_url": m.get("availability_source_url"),
                "last_checked": m.get("last_availability_check"),
                "as_of": _load_catalog().get("as_of"),
            }
    return {"error": f"model_id '{model_id}' not found"}


# ---- MCP protocol (minimal manual stdio implementation) ----

TOOLS = [
    {
        "name": "list_models",
        "description": "List available LLM models, optionally filtered by provider or required capability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "filter by provider id (anthropic/openai/google/deepseek/mistral)"},
                "capability": {"type": "string", "description": "filter by required capability (tool_use/vision/audio/structured_output/prompt_caching)"},
            },
        },
    },
    {
        "name": "get_model",
        "description": "Full record for a single model id.",
        "inputSchema": {"type": "object", "properties": {"model_id": {"type": "string"}}, "required": ["model_id"]},
    },
    {
        "name": "find_cheapest",
        "description": "Rank models by estimated cost for a given token spec; returns cheapest first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "input_tokens": {"type": "integer"},
                "output_tokens": {"type": "integer"},
                "required_capabilities": {"type": "array", "items": {"type": "string"}},
                "only_operational": {"type": "boolean", "default": True},
            },
            "required": ["input_tokens", "output_tokens"],
        },
    },
    {
        "name": "compare_models",
        "description": "Side-by-side comparison of a set of models for a token spec.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_ids": {"type": "array", "items": {"type": "string"}},
                "input_tokens": {"type": "integer", "default": 1000},
                "output_tokens": {"type": "integer", "default": 500},
            },
            "required": ["model_ids"],
        },
    },
    {
        "name": "check_availability",
        "description": "Current availability status for a model with cited source URL.",
        "inputSchema": {"type": "object", "properties": {"model_id": {"type": "string"}}, "required": ["model_id"]},
    },
]

TOOL_HANDLERS = {
    "list_models": tool_list_models,
    "get_model": tool_get_model,
    "find_cheapest": tool_find_cheapest,
    "compare_models": tool_compare_models,
    "check_availability": tool_check_availability,
}


def _reply(req_id, result=None, error=None):
    msg: dict = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _serve_stdio():
    """Minimal MCP stdio loop. Handles initialize, tools/list, tools/call."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            continue
        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params") or {}
        if method == "initialize":
            _reply(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "llm-oracle", "version": "0.1.0"},
            })
        elif method == "tools/list":
            _reply(req_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            handler = TOOL_HANDLERS.get(name)
            if not handler:
                _reply(req_id, error={"code": -32601, "message": f"unknown tool {name}"})
                continue
            try:
                result = handler(**args)
                _reply(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
            except TypeError as e:
                _reply(req_id, error={"code": -32602, "message": f"invalid params for {name}: {e}"})
            except Exception as e:
                _reply(req_id, error={"code": -32000, "message": str(e)})
        elif method == "notifications/initialized":
            pass  # acknowledged
        elif method == "ping":
            _reply(req_id, {})
        else:
            _reply(req_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="LLM Oracle MCP server")
    ap.add_argument("--http", type=int, metavar="PORT", help="serve HTTP/SSE on PORT instead of stdio")
    args = ap.parse_args()
    if args.http:
        # HTTP/SSE mode left as v2 work-item; stdio is sufficient for first ship
        print(f"http mode not yet implemented; use http_api.py for v0 HTTP serving on port {args.http}", file=sys.stderr)
        sys.exit(2)
    _serve_stdio()
