# llm-oracle

> Continuously-updated catalog + query API for LLM provider availability and pricing.

Built by [weiseer](https://weiseer.com).

## What it does

Given a question like *"for this prompt of N input tokens plus M expected output tokens, which currently-available model offers the lowest cost?"* the oracle answers in milliseconds, with the source URL it used for the pricing claim.

Use it as:
- an MCP server for AI agents that need to make routing decisions at inference time
- an HTTP JSON API for any tool that wants up-to-date LLM pricing/availability
- a raw `catalog.json` you can audit, vendor, or contribute fixes to

## Why

LLM pricing changes monthly. Every multi-model app rebuilds the same lookup table. We maintain it so you don't.

- **Cited**: every pricing row links to the provider's official documentation
- **Versioned**: `as_of` timestamp on every response so you know how fresh the data is
- **Open**: catalog is public JSON, MIT licensed; client/server code is Apache-2.0
- **Cross-checked**: source data verified against the open-source [LiteLLM price file](https://github.com/BerriAI/litellm) where overlap exists

## Coverage (v0)

5 providers, ~10 models. Growing as we observe demand.

- Anthropic: Claude Opus 4.7, Sonnet 4.6, Haiku 4.5
- OpenAI: GPT-5, GPT-4o
- Google: Gemini 2.5 Pro, Gemini 2.5 Flash
- DeepSeek: Reasoner, Chat
- Mistral: Large

## Quickstart

### As an MCP server (Claude Desktop, Cursor, Continue, Cline, etc.)

```bash
git clone https://github.com/weiseer/llm-oracle
cd llm-oracle
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "llm-oracle": {
      "command": "python",
      "args": ["/absolute/path/to/llm-oracle/mcp_server.py"]
    }
  }
}
```

The agent now has tools:

- `list_models(provider?, capability?)` → list models, optionally filtered
- `get_model(model_id)` → full record for one model
- `find_cheapest(input_tokens, output_tokens, required_capabilities?)` → ranked by estimated cost
- `compare_models(model_ids[], input_tokens?, output_tokens?)` → side-by-side
- `check_availability(model_id)` → current status with cited source

### As an HTTP API

```bash
# Free tier: 1,000 calls/day per IP, no key
curl https://oracle.weiseer.com/catalog.json
curl 'https://oracle.weiseer.com/cheapest?input_tokens=2000&output_tokens=500'
curl https://oracle.weiseer.com/models/claude-sonnet-4-6
```

### As raw JSON

```bash
curl https://oracle.weiseer.com/catalog.json > my-local-catalog.json
```

## Pricing

| Tier | Calls | Cost |
|------|-------|------|
| Free | 1,000/day | $0 |
| Pro | 100,000/month | $5 USDC/mo |
| Scale | 1,000,000/month | $20 USDC/mo |
| Raw catalog | unlimited | $0 (always free) |

Paid tiers settle in USDC. Email `wei@weiseer.com` to subscribe; we issue an API key and confirm receipt. (We'll automate this when the first three paid customers exist.)

## Schema

See `catalog.json` for the canonical schema. Per-model fields include `model_id`, `provider`, `family`, `context_window`, `max_output_tokens`, `input_price`, `output_price`, `cached_input_price`, `capabilities`, `availability_status`, source URLs, and timestamps.

## Update cadence

- Pricing: daily cron + manual when a price change is publicly announced
- Availability: 5-minute poll of provider status pages where available; daily smoke-test otherwise

## Errors and disagreements

Found a stale price? An incorrect capability flag? A missing model? [Open an issue](https://github.com/weiseer/llm-oracle/issues) — please include the source URL we should be tracking.

## Telemetry

The hosted service logs each request as a single event (caller, query summary, latency, paid status) to weiseer's append-only audit ledger. The MCP server you self-host logs nothing.

## Building on this

The catalog format is MIT licensed. Vendor it, mirror it, build on top of it. We ask only that you cite `weiseer/llm-oracle` somewhere visible if you redistribute the data.

The server and MCP code are Apache-2.0.

## Roadmap (probe-pulled, not pre-planned)

This is **P-001 in weiseer's strategic backlog** — a market sensor for organism's architecture v2. We expand it where users ask, kill it if 4 weeks of public availability brings under 100 calls. Don't expect a polished commercial product; expect honest experimentation with daily updates.

What we might add (in observed-demand order):
- More providers (Cohere, xAI, AI21, Together, Replicate hosted, Bedrock, Azure pricing variants)
- x402 micropayments for high-volume agent buyers (deferred — see [arXiv 2605.11781](https://arxiv.org/abs/2605.11781) on protocol security)
- Historical pricing time-series
- SLA + uptime aggregates per provider
- Per-region availability where providers vary
- Self-hosted model cost estimators (with caveats)

## Contact

`wei@weiseer.com` · [github.com/weiseer](https://github.com/weiseer) · [weiseer.com](https://weiseer.com)
