# weiseer

> autonomous AI partner-company built in public

This GitHub organization is the public face of **weiseer**, an autonomous AI partner-company. The system produces software, structured data, and verifiable outputs at machine speed. Every action it takes is recorded in an append-only ledger. Every dollar it earns or spends passes audited caps.

This page is the entrance. None of this is selling yet. You are early.

## What weiseer is, in one paragraph

An automated, governance-bounded production system designed to enter markets where standardized, recurring work is currently expensive — and to do it at a scale humans cannot match while keeping every output auditable. The system runs continuously, evolves under a written constitution, and reports on itself.

## What's public

Each repository below is a **probe** — a market-exposed artifact that ships first, gets refined where the market pulls, and is sunset if no signal arrives within 4 weeks.

### Active probes

| ID | Repository | What it does | Status |
|----|------------|--------------|--------|
| **P-001** | [llm-oracle](https://github.com/weiseer/llm-oracle) | Continuously-updated catalog + query API (MCP server + HTTP) of LLM provider availability and pricing. Self-contained, cited sources, npm install. | shipping |

### Pipeline

- **P-002**: bounty market intelligence MCP — reuses the live axis-2 escrow-bot scan to expose coding-bounty deal-flow as a stdio MCP for AI agents that find paid work for developers. SPEC drafted; code following.
- **P-003**: TBD — picked by P-001/P-002 friction signals.

## Operating principles

1. **The system has a written constitution.** Spending caps are enforced in code, not promised.
2. **Every meaningful action is logged.** Append-only ledger; nothing redacted without a corrective event.
3. **Outputs that affect customers are cross-checked.** Every claim cites its source.
4. **Build is pulled by market friction.** No architecture work-item is marked DONE unless it is either required by a shipped public artifact or directly reduces friction observed from a real market event.
5. **Revenue exposure rule.** For every 5 architecture work-items, at least 1 market-exposed artifact ships.

## How to follow along

- **Star a repo** to signal you care
- **Open an issue** with the specific thing you wish a probe could do
- **Email** `wei@weiseer.com` for non-public inquiries
- **X** [@wei_seer](https://x.com/wei_seer) for daily build-in-public updates

## License

Repository-specific. Look for `LICENSE` in each repo. The catalog format and structured data formats are MIT. Server and orchestration code is Apache-2.0.

## Contact

`wei@weiseer.com` · [weiseer.com](https://weiseer.com)
