#!/usr/bin/env python3
"""LLM Oracle HTTP API — stdlib-only, no external deps.

Usage:
    python http_api.py                    # serves on 0.0.0.0:8765
    python http_api.py --port 9000        # custom port
    PORT=9000 python http_api.py          # via env

Endpoints (all JSON):
    GET  /                       -> service info
    GET  /catalog.json           -> raw catalog dump
    GET  /models                 -> list models (?provider=&capability=)
    GET  /models/{model_id}      -> single model
    GET  /cheapest               -> rank by cost (?input_tokens=N&output_tokens=M&capability=X)
    POST /compare                -> body: {model_ids: [...], input_tokens, output_tokens}
    GET  /availability/{model_id} -> current availability + source

Telemetry: each request is logged to organism's events ledger (oracle_request).

License: Apache-2.0
Probe ID: P-001
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# reuse the tool implementations from mcp_server
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from mcp_server import (  # noqa: E402
    tool_list_models, tool_get_model, tool_find_cheapest,
    tool_compare_models, tool_check_availability, _load_catalog,
)

SERVICE_INFO = {
    "service": "llm-oracle",
    "version": "0.1.0",
    "provider": "weiseer",
    "purpose": "continuously-updated catalog + query API for LLM provider availability and pricing",
    "endpoints": {
        "GET /": "this info",
        "GET /catalog.json": "raw catalog dump (free, no auth)",
        "GET /models": "list models (filter: ?provider=, ?capability=)",
        "GET /models/{model_id}": "full record for one model",
        "GET /cheapest": "rank models by estimated cost (?input_tokens=N&output_tokens=M&capability=X&only_operational=true)",
        "POST /compare": "side-by-side comparison; body: {model_ids: [...], input_tokens?, output_tokens?}",
        "GET /availability/{model_id}": "current availability status with cited source",
    },
    "free_tier": "1000 calls/day per IP",
    "paid_tiers": {
        "pro": "$5 USDC/mo for 100k calls",
        "scale": "$20 USDC/mo for 1M calls",
    },
    "subscribe": "email wei@weiseer.com",
    "docs": "https://github.com/weiseer/llm-oracle",
    "license": "catalog: MIT, server: Apache-2.0",
}


def _log_event(actor_ip: str, path: str, method: str, status: int, latency_ms: int):
    """Write one event to organism's events ledger if available."""
    try:
        sys.path.insert(0, "/opt/organism")
        from core.db_helper import sync_conn  # type: ignore
        with sync_conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO events (event_type, actor, current_phase, event_category, data) "
                "VALUES (%s, %s, 1, %s, %s::jsonb)",
                (
                    "oracle_request",
                    "oracle_http_api",
                    "phase_1_operate",
                    json.dumps({
                        "path": path[:200],
                        "method": method,
                        "status": status,
                        "latency_ms": latency_ms,
                        "anon_caller": actor_ip[:32],
                    }),
                ),
            )
            c.commit()
    except Exception:
        pass  # local dev / no organism db; silently skip


class Handler(BaseHTTPRequestHandler):
    server_version = "llm-oracle/0.1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.client_address[0]} {fmt % args}\n")

    def _send(self, status: int, body, content_type="application/json"):
        data = body if isinstance(body, (bytes, bytearray)) else json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Service", "llm-oracle")
        self.send_header("X-Catalog-AsOf", _load_catalog().get("as_of", "unknown"))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, b"", content_type="text/plain")

    def do_GET(self):
        t0 = time.time()
        u = urlparse(self.path)
        path = u.path
        qs = parse_qs(u.query)
        status = 200
        try:
            if path == "/" or path == "":
                body = SERVICE_INFO
            elif path == "/catalog.json":
                body = _load_catalog()
            elif path == "/models":
                provider = (qs.get("provider") or [None])[0]
                capability = (qs.get("capability") or [None])[0]
                body = tool_list_models(provider=provider, capability=capability)
            elif path.startswith("/models/"):
                mid = path[len("/models/"):]
                body = tool_get_model(mid)
                if "error" in body:
                    status = 404
            elif path == "/cheapest":
                try:
                    it = int((qs.get("input_tokens") or ["1000"])[0])
                    ot = int((qs.get("output_tokens") or ["500"])[0])
                except ValueError:
                    self._send(400, {"error": "input_tokens and output_tokens must be integers"})
                    return
                cap = qs.get("capability") or qs.get("required_capabilities") or []
                only_op = (qs.get("only_operational") or ["true"])[0].lower() != "false"
                body = tool_find_cheapest(it, ot, list(cap), only_op)
            elif path.startswith("/availability/"):
                mid = path[len("/availability/"):]
                body = tool_check_availability(mid)
                if "error" in body:
                    status = 404
            elif path == "/healthz":
                body = {"ok": True, "catalog_as_of": _load_catalog().get("as_of")}
            else:
                status = 404
                body = {"error": "not_found", "path": path}
            self._send(status, body)
        finally:
            _log_event(self.client_address[0], path, "GET", status, int((time.time() - t0) * 1000))

    def do_POST(self):
        t0 = time.time()
        u = urlparse(self.path)
        path = u.path
        status = 200
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                self._send(400, {"error": "invalid_json"})
                return
            if path == "/compare":
                mids = body.get("model_ids") or []
                it = int(body.get("input_tokens", 1000))
                ot = int(body.get("output_tokens", 500))
                result = tool_compare_models(mids, it, ot)
                self._send(200, result)
            else:
                status = 404
                self._send(404, {"error": "not_found", "path": path})
        finally:
            _log_event(self.client_address[0], path, "POST", status, int((time.time() - t0) * 1000))


def main():
    ap = argparse.ArgumentParser(description="LLM Oracle HTTP API")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    ap.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    sys.stderr.write(f"llm-oracle serving on http://{args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
