# LLM Oracle — first organism probe

**Probe ID**: P-001
**Status**: shipping (first iteration)
**Started**: 2026-05-30 10:38 BJT
**Strategic role**: market sensor for [[project_organism_architecture_backlog]] v2 (Revenue-Coupled Architecture). Tests F (distribution), C (payment), B (verification), A (identity), G (decision log) simultaneously with minimum-viable architecture build per CRR rule.

## What it does

A continuously-updated catalog + query API for LLM provider availability and pricing.

Given a question like "for this prompt of N input tokens + expected M output tokens, which currently-available model offers the lowest cost?" — the oracle answers in milliseconds, with cited source for the pricing claim, with a confidence interval for the availability claim.

Targets two consumer profiles:
- **AI agents** that need to make routing decisions at inference time (the AgenticTrade-style buyer)
- **Developers** building multi-model applications who want a single up-to-date reference

## What it does NOT do

- Predict future pricing
- Recommend models for tasks (just answers the cost/availability question, doesn't decide for you)
- Cache or proxy actual model calls (this is a data oracle, not a routing layer)
- Track open-weights/self-hosted models initially (cost depends on hosting, harder to standardize)

## Initial scope

**Providers covered v0**: Anthropic, OpenAI, Google, DeepSeek, Mistral. ~15–20 models total.

**Data fields per model**:
- model_id, provider, family
- pricing: input USD per 1M tokens, output USD per 1M tokens, cached USD per 1M tokens (where applicable)
- context_window (tokens)
- max_output_tokens
- capabilities: tool_use, vision, audio, structured_output, prompt_caching
- availability_status: operational / degraded / outage (from provider status page or last-known)
- last_updated (UTC)
- pricing_source_url (citable)
- availability_source_url (citable)

**Update cadence**:
- Pricing: daily cron + manual on confirmed price change events
- Availability: 5-minute poll of provider status pages where available

## Access surfaces

1. **HTTP JSON API** at `https://oracle.weiseer.com`
   - `GET /models` — list all models (filter by provider, capability)
   - `GET /models/{model_id}` — full info for one model
   - `POST /compare` — compare a set of models for a token spec
   - `GET /cheapest?input_tokens=X&output_tokens=Y&capabilities=...` — query for lowest-cost match
   - `GET /availability/{model_id}` — current availability status
   - `GET /catalog.json` — raw dump (public)

2. **MCP server** (Python, stdio + HTTP/SSE later)
   - Tool: `list_models(provider?, capability?)`
   - Tool: `get_model(model_id)`
   - Tool: `find_cheapest(input_tokens, output_tokens, required_capabilities?)`
   - Tool: `compare_models(model_ids[], token_spec)`
   - Tool: `check_availability(model_id)`

3. **npm wrapper** `@weiseer/llm-oracle-mcp` — installs and runs the MCP server locally, talking to the public HTTP API.

## Pricing (probe phase)

Free tier:
- 1,000 calls/day per IP (HTTP) or per MCP client (anonymous)
- Raw catalog dump always free (it's the open reference)
- Citation requested but not enforced

Paid tier (probe — manual settlement):
- $5/month for 100,000 calls
- $20/month for 1,000,000 calls
- Payment: USDC to organism wallet (`BOUNTY_PAYOUT_ADDRESS`). Manual confirmation via email. Subscription tracked by API key issued on payment confirmation.
- x402 protocol integration deferred to v2 (per audit's security caveat — adopt with awareness, not blindly)

## Source data strategy

**Primary**: scrape each provider's official pricing documentation page; structured extraction + validation. Daily.
**Cross-check**: compare against LiteLLM's open-source `model_prices_and_context_window.json` (kept current by the community). Flag discrepancies for human review.
**Availability**: provider status pages where RSS/JSON feeds are published; otherwise daily smoke-test of a single API call per model.

## Verification (couples to layer B)

Every published claim is traceable:
- Each pricing row has `pricing_source_url` (the doc page we read it from)
- Each availability row has `availability_source_url` (status page or our smoke-test log)
- Every API response includes `data_version` and `as_of` timestamps
- Public `/catalog.json` lets anyone audit the entire dataset

## Distribution surfaces (couples to layer F)

- weiseer GitHub repo: `weiseer/llm-oracle` (public, MIT licensed for the catalog format + client code; Apache for the server)
- MCP registry submission (modelcontextprotocol/registry PR)
- AgenticTrade listing if/when API supports it
- npm: `@weiseer/llm-oracle-mcp` for easy MCP client install
- weiseer.com/oracle landing with docs + getting-started

## Telemetry (couples to layer G)

Every HTTP request + every MCP tool call writes one event to organism's events ledger:
- event_type: `oracle_request`
- data: { tool_or_path, anonymized_caller_id, query_summary, response_size, latency_ms, paid (bool), cited_source (bool — for paid subs that cite us back) }

Aggregations exposed at `/stats` (public dashboard) — for layer B's public correctness signal.

## Kill criteria (CRR-compliant)

- 4 weeks from public ship: if total cumulative real traffic < 100 calls AND zero inbound contact AND zero paid signups → sunset, write retrospective event, take learnings into P-002
- Architecture upgrades to support this probe are EARNED by ship-friction observation only, NOT pre-built

## What this probe deliberately tests

| Layer touched | Minimum slice built |
|---|---|
| A identity | weiseer.com/oracle landing only; no theatrical roadmap |
| B verification | every response includes citable source URL; no error-rate dashboard until traffic exists |
| C commercial | manual USDC + email-confirmed API key issue; no Coinbase Commerce, no x402 yet |
| F distribution | GitHub repo + MCP registry submission + npm publish + landing |
| G decision log | every request → event ledger; weekly review entry |
| D customer interaction | inbound email + GitHub issues only; no LLM tier-1 |
| E knowledge ingestion | provider-specific scrapers only; no generic crawler |
| H legal | apply existing template ToS/Privacy/Refund at /oracle/legal; no attorney review until first paid customer |

## Open risks (audit-aware)

- x402 vulnerabilities (arXiv 2605.11781) — deferring x402 entirely is the safer path for v1
- MCP registry commoditization (audit signal) — window is now; ship within days not weeks
- GitHub Marketplace verified-publisher requirement (audit signal) — Marketplace listing deferred; npm + MCP registry sufficient for v1
- AWS Marketplace AI-agent commoditization (audit signal) — AWS listing deferred to v3; first ship is GitHub-native

## Ship plan (work-items, no timelines)

- [ ] P-001.1 catalog.json v0 with 5 providers × 3 models each
- [ ] P-001.2 mcp_server.py functional + stdio runnable
- [ ] P-001.3 http_api.py functional (FastAPI or stdlib)
- [ ] P-001.4 README.md complete
- [ ] P-001.5 weiseer/llm-oracle GitHub repo created + initial push
- [ ] P-001.6 weiseer.com/oracle landing live (Cloudflare tunnel route)
- [ ] P-001.7 events ledger schema for oracle_request events
- [ ] P-001.8 daily update cron deployed on VPS
- [ ] P-001.9 npm package published
- [ ] P-001.10 MCP registry submission opened
- [ ] P-001.11 first public mention (weiseer X post / HN Show / dev.to writeup) — minimum 1 distribution attempt
- [ ] P-001.12 first paying customer or 4-week sunset checkpoint
