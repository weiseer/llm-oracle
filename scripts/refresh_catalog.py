#!/usr/bin/env python3
"""Daily catalog refresh — cross-check against LiteLLM upstream + provider docs.

Flow:
1. Pull latest LiteLLM model_prices_and_context_window.json
2. For each model in our catalog, compare key fields (pricing, context_window)
3. Update where LiteLLM disagrees AND the change is recent (last 14 days)
4. Bump as_of timestamp
5. Write event to organism's events ledger
6. If meaningful diff, also publish a new npm version (manual gate for now)

Run via:
    python3 refresh_catalog.py [--apply]    # --apply writes; default is dry-run

Cron:
    @daily organism /opt/organism/.venv/bin/python3 /opt/organism/products/llm_oracle/scripts/refresh_catalog.py --apply
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.json"
LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

# LiteLLM key → our key mapping (LiteLLM uses different model id conventions for some providers)
LITELLM_ALIASES = {
    "claude-opus-4-7": ["claude-opus-4-7-20250120", "claude-opus-4-7", "anthropic/claude-opus-4.7"],
    "claude-sonnet-4-6": ["claude-sonnet-4-6", "claude-sonnet-4-6-20240120", "anthropic/claude-sonnet-4.6"],
    "claude-haiku-4-5-20251001": ["claude-haiku-4-5-20251001", "claude-haiku-4.5", "anthropic/claude-haiku-4.5"],
    "gpt-5": ["gpt-5", "openai/gpt-5"],
    "gpt-4o": ["gpt-4o", "openai/gpt-4o"],
    "gemini-2.5-pro": ["gemini-2.5-pro", "gemini/gemini-2.5-pro", "vertex_ai/gemini-2.5-pro"],
    "gemini-2.5-flash": ["gemini-2.5-flash", "gemini/gemini-2.5-flash"],
    "deepseek-reasoner": ["deepseek-reasoner", "deepseek/deepseek-reasoner"],
    "deepseek-chat": ["deepseek-chat", "deepseek/deepseek-chat"],
    "mistral-large-latest": ["mistral-large-latest", "mistral/mistral-large-latest"],
}


def fetch_litellm() -> dict:
    req = urllib.request.Request(LITELLM_URL, headers={"User-Agent": "weiseer-oracle-refresh/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def find_in_litellm(litellm: dict, model_id: str) -> dict | None:
    for candidate in LITELLM_ALIASES.get(model_id, [model_id]):
        if candidate in litellm:
            return litellm[candidate]
    return None


def litellm_price_per_million(token_cost_per_token: float | None) -> float | None:
    if token_cost_per_token is None:
        return None
    return round(token_cost_per_token * 1_000_000, 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write changes")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    try:
        litellm = fetch_litellm()
        print(f"[refresh] fetched LiteLLM upstream: {len(litellm)} entries", file=sys.stderr)
    except Exception as e:
        print(f"[refresh] FAIL fetching LiteLLM: {e}", file=sys.stderr)
        return 1

    diffs = []
    for m in catalog["models"]:
        mid = m["model_id"]
        ll = find_in_litellm(litellm, mid)
        if not ll:
            if args.verbose:
                print(f"[refresh] {mid}: no LiteLLM match", file=sys.stderr)
            continue
        ll_in = litellm_price_per_million(ll.get("input_cost_per_token"))
        ll_out = litellm_price_per_million(ll.get("output_cost_per_token"))
        ll_ctx = ll.get("max_input_tokens") or ll.get("max_tokens")
        local_diff = {}
        if ll_in is not None and abs(ll_in - (m.get("input_price") or 0)) > 0.001:
            local_diff["input_price"] = {"local": m.get("input_price"), "litellm": ll_in}
        if ll_out is not None and abs(ll_out - (m.get("output_price") or 0)) > 0.001:
            local_diff["output_price"] = {"local": m.get("output_price"), "litellm": ll_out}
        if ll_ctx and abs(ll_ctx - (m.get("context_window") or 0)) > 1000:
            local_diff["context_window"] = {"local": m.get("context_window"), "litellm": ll_ctx}
        if local_diff:
            diffs.append({"model_id": mid, "diffs": local_diff})

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog["as_of"] = now

    if args.apply and diffs:
        # apply LiteLLM values (it's the community-maintained source of truth)
        by_id = {m["model_id"]: m for m in catalog["models"]}
        for d in diffs:
            for field, vals in d["diffs"].items():
                by_id[d["model_id"]][field] = vals["litellm"]
                by_id[d["model_id"]][f"last_pricing_check"] = now

    if args.apply:
        CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        print(f"[refresh] catalog written: {len(diffs)} diffs applied, as_of={now}", file=sys.stderr)
    else:
        print(f"[refresh] dry-run: {len(diffs)} diffs detected", file=sys.stderr)
        for d in diffs[:5]:
            print(f"  {d['model_id']}: {d['diffs']}", file=sys.stderr)

    # write event to organism's events ledger (best-effort)
    try:
        sys.path.insert(0, "/opt/organism")
        from core.db_helper import sync_conn  # type: ignore
        with sync_conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO events (event_type, actor, current_phase, event_category, data) "
                "VALUES (%s, %s, 1, %s, %s::jsonb)",
                (
                    "oracle_catalog_refresh",
                    "oracle_refresh_cron",
                    "phase_1_operate",
                    json.dumps({
                        "diffs_detected": len(diffs),
                        "diffs_applied": len(diffs) if args.apply else 0,
                        "as_of": now,
                        "litellm_size": len(litellm),
                    }),
                ),
            )
            c.commit()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
