# P-002 SPEC — Bounty Market Intelligence MCP

**Probe ID**: P-002
**Status**: design draft
**Started**: 2026-05-30 11:17 BJT (per RER: shipped after P-001 architecture items)
**Strategic role**: second probe under [[project_organism_micro_saas_portfolio_frame]] v2. Tests whether an AI-agent surface different from "data oracle" (i.e. "live operational intelligence") draws different usage signal. Uses organism's already-running axis-2 bounty monitor as the data source.

## What it does

A continuously-updated MCP server + HTTP API for live coding-bounty deal-flow across funded GitHub bounty platforms (Algora, future: Opire/Polar/IssueHunt).

Given a query like *"unassigned Python bounties with bounty ≥ $500 posted in the last 7 days where no /claim PR exists yet"* — returns the matching live bounties with full metadata in milliseconds, structured for AI-agent consumption.

Targets:
- **AI agents acting on behalf of developers** looking for paid coding work
- **AI agents acting on behalf of OSS funders** looking to track competitive landscape
- **Developers + organism's own ACH harness** as the dogfooding consumer

## What it does NOT do

- Solve the bounty for you (out of scope — that's the ACH harness, which is on hold pending v2)
- Submit /claim on your behalf
- Predict bounty success
- Cover non-escrow-backed bounties (scam filter from axis-2 still applies)

## Reuse of existing organism capability

This probe ships fast because axis-2 monitor already does the hard work:
- Already runs every minute scanning verified Algora escrow-bot bounties
- Already filters scam farms (SecureBananaLabs / ClankerNation / UnsafeLabs)
- Already classifies bug-fix vs feature
- Already tracks attempts + assignment status
- Already writes events to ledger

P-002 only adds:
- Persistent storage of normalized bounty records (currently axis-2 only writes seen-set + events)
- Query layer + MCP/HTTP surfaces
- Public catalog snapshot (similar to llm-oracle pattern)

## Initial scope

**Data schema** per bounty (per the existing axis-2 candidate structure):
- key (repo + issue#), repo, issue_number, title, html_url
- dollars (parsed integer USD)
- language
- attempts (existing /claim or /attempt comment count)
- has_open_pr (true if cross-referenced PR exists in open state)
- trust ("whitelist" or "escrow-bot")
- is_bug_fix (bug-fix classification)
- assignee (if assigned)
- created_at, updated_at, seen_at
- algora_url (deep link to algora.io listing where applicable)

**Update cadence**:
- Tracks the existing 1-minute axis-2 cron (no new infrastructure needed)
- Snapshot exposed at `/bounties.json` updated each cron tick

## Access surfaces

1. **HTTP JSON API** at `https://bounties.weiseer.com` (deferred — same hosted-endpoint dependency as oracle.weiseer.com)
   - `GET /bounties` — list (filter by ?lang=, ?min_dollars=, ?bug_fix=, ?max_attempts=, ?has_open_pr=)
   - `GET /bounties/{repo}/{num}` — single bounty
   - `GET /bounties.json` — raw catalog dump
   - `GET /stats` — aggregates (total open, by language, by bug-fix vs feature)

2. **MCP server** (Python + JS variants, npm package `@weiseer/bounty-mcp`):
   - `list_bounties(filter?)` — query the live snapshot
   - `find_matching(skills[], min_dollars, max_attempts, require_open_pr_absent)` — agent-friendly query
   - `get_bounty(repo, num)` — full record
   - `check_status(repo, num)` — fresh check (is it still open, claimed, completed)

## Pricing (probe phase)

- **Free**: catalog dump + listing (data is public on Algora; we add structure + filter + freshness)
- **Pro tier** (deferred until hosted endpoint exists):
  - $10 USDC/mo — high-freq polling + custom filter persistence
  - per-call x402 once protocol matured

## Source data strategy

- **Primary**: axis-2 bounty_monitor cron (already running)
- **Storage**: add a Postgres table `bounty_snapshot` populated by axis-2 each tick
- **Catalog dump**: hourly dump from `bounty_snapshot` → `bounties.json` (committed to npm package on schedule)

## Verification (couples to layer B)

- Each bounty record has its `algora_url` and `github_url` — auditable at source
- Snapshot timestamp `as_of` always present
- Stats publish per-snapshot count + per-trust-tier counts

## Distribution

- weiseer GitHub repo: `weiseer/bounty-mcp` (public)
- npm: `@weiseer/bounty-mcp`
- MCP registry submission via mcp-publisher CLI
- Smithery + mcp.so + Glama + PulseMCP listings

## Telemetry (couples to layer G)

Every HTTP request + MCP tool call writes one `bounty_query` event to the ledger.
Match outcomes (did the queried bounty get claimed / completed) tracked by axis-2 reading the same data, closing the learning loop.

## Kill criteria (CRR-compliant)

- 4 weeks from public ship: if total cumulative real traffic < 200 calls AND zero inbound contact AND zero downstream agents using the catalog → sunset, retrospective event, P-003.

## What this probe deliberately tests vs P-001

- **Different consumer profile**: developer-routing-agent (P-002) vs LLM-routing-agent (P-001)
- **Different data freshness signal**: minute-level operational (P-002) vs daily catalog (P-001)
- **Same npm + MCP distribution path**: validates the distribution layer for second product without rebuild
- **Tests cross-probe inbound**: does someone discovering one finds and uses the other?

## Ship plan (work-items, no timelines)

- [ ] P-002.1 add `bounty_snapshot` table migration
- [ ] P-002.2 modify axis-2 to write snapshot rows per tick (additive — does not break existing seen-set behavior)
- [ ] P-002.3 Python query layer + stdio MCP server (`bounty_mcp_server.py`)
- [ ] P-002.4 JS/npm wrapper (`@weiseer/bounty-mcp` mirror of llm-oracle pattern)
- [ ] P-002.5 `weiseer/bounty-mcp` GitHub repo create + push
- [ ] P-002.6 README + dist drafts
- [ ] P-002.7 hourly bounties.json snapshot dump to repo
- [ ] P-002.8 events ledger schema `bounty_query`
- [ ] P-002.9 MCP registry submission via mcp-publisher
- [ ] P-002.10 npm publish
- [ ] P-002.11 first public mention (weiseer X tweet + dev.to short post)
- [ ] P-002.12 4-week sunset checkpoint

## Open risks (audit-aware)

- Bounty data is public; competitive moat is **freshness + structure**, not data scarcity
- If Algora API stabilizes + opens, they may publish this themselves (commoditization risk)
- TAM for "AI agents that find coding bounties for developers" is uncertain — this probe IS the TAM sensor
