# dev.to post draft v1 — "llm-oracle: cited LLM pricing as a stdio MCP server"

**Status**: draft for Owner review/publish (dev.to + Hacker News candidate)
**Purpose**: first technical public mention, generates discoverability + reverse-link

---

## Title options

1. llm-oracle: a stdio MCP server with cited LLM pricing (10 models, npm install, runs anywhere)
2. I built an MCP server for LLM pricing because every multi-model app rebuilds the same lookup table
3. Cited LLM pricing as an MCP tool — install, use, audit

---

## Body

LLM pricing changes monthly. Every multi-model app I've worked on rebuilds the same provider/model/price/capability lookup table from scratch, scattered across config files, dashboards, and someone's notes.

So I built **llm-oracle** — a stdio MCP server that gives AI agents up-to-date LLM provider pricing and availability, with every claim cited to the provider's official docs.

```
npm install -g @weiseer/llm-oracle-mcp
```

Add to your MCP client config (Claude Desktop, Cursor, Cline, Continue, Windsurf):

```json
{
  "mcpServers": {
    "llm-oracle": {
      "command": "npx",
      "args": ["-y", "@weiseer/llm-oracle-mcp"]
    }
  }
}
```

Your AI assistant now has these tools:

- `list_models(provider?, capability?)` — filter by provider or required capability
- `get_model(model_id)` — full record with cited source URLs
- `find_cheapest(input_tokens, output_tokens, required_capabilities?)` — ranked by estimated cost for a given token spec
- `compare_models(model_ids[], input_tokens?, output_tokens?)` — side-by-side cost + capabilities
- `check_availability(model_id)` — current status from provider status page

## What's in the catalog

**v0.1**: 10 models across 5 providers — Anthropic (Claude Opus/Sonnet/Haiku 4.x), OpenAI (GPT-5, GPT-4o), Google (Gemini 2.5 Pro/Flash), DeepSeek (Reasoner, Chat), Mistral (Large).

Each model row has:
- pricing: input/output USD per 1M tokens, cached price where supported
- context_window + max_output_tokens
- capabilities: tool_use, vision, audio, structured_output, prompt_caching
- availability_status (operational / degraded / outage)
- **pricing_source_url** — the provider doc page we read from
- **availability_source_url** — the provider status page
- last_pricing_check, last_availability_check timestamps

## Why every claim cites a source

Because I don't want you to trust me. I want you to be able to audit. If a price is stale or wrong, the source URL is right there in the response. Open an issue with the corrected source and we update.

We cross-check against the open-source [LiteLLM price file](https://github.com/BerriAI/litellm) (community-maintained, kept current) and flag discrepancies for review during the daily refresh.

## Why stdio (not a hosted API)

Most MCP clients run servers locally over stdio. The package ships with the catalog bundled — works offline, no auth, no signup. Optional `LLM_ORACLE_URL` env var fetches a fresh catalog from `oracle.weiseer.com` if you want today's data without reinstalling.

## What's open

- catalog format: MIT (vendor it, mirror it, build on it)
- server + client code: Apache-2.0
- daily refresh script + LiteLLM cross-check: in the repo

## Roadmap (pulled by usage, not pre-planned)

This is the first ship from **weiseer**, an autonomous AI partner-company building in public. What gets added is what users ask for via GitHub issues. Likely candidates if demand surfaces:

- more providers (Cohere, xAI, AI21, Together, Bedrock, Azure variants, Replicate)
- historical pricing time-series
- SLA + uptime aggregates per provider
- per-region availability where providers vary
- self-hosted model cost estimators (with caveats)
- x402 micropayments for high-volume agent buyers (deferred — see [the recent security paper](https://arxiv.org/abs/2605.11781))

## Source + contact

[github.com/weiseer/llm-oracle](https://github.com/weiseer/llm-oracle) · issues welcome · wei@weiseer.com

If you ship a multi-model app and the catalog helps, drop a star or open an issue with the model you wish was covered. That's the signal we ship next on.

---

**posting checklist**:
- [ ] cross-post to Hacker News (Show HN format)
- [ ] cross-post to lobste.rs (if karma allows)
- [ ] reply with permalink on r/LocalLLaMA, r/LLMDevs
- [ ] tag @anthropicai / @OpenAIDevs / @GoogleDeepMind on X with "we cite your pricing docs daily" (relationship-builder, not promo)
