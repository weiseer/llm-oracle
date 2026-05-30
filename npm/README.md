# @weiseer/llm-oracle-mcp

MCP server for LLM provider availability and pricing. Self-contained — works offline with the bundled catalog, optionally fetches fresh data from `oracle.weiseer.com`.

## Install

```bash
npm install -g @weiseer/llm-oracle-mcp
```

## Use with Claude Desktop / Cursor / Cline / Continue / Windsurf

Add to your MCP client config:

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

- `list_models(provider?, capability?)` — list models
- `get_model(model_id)` — full record
- `find_cheapest(input_tokens, output_tokens, required_capabilities?)` — ranked by cost
- `compare_models(model_ids[], input_tokens?, output_tokens?)` — side-by-side
- `check_availability(model_id)` — current status with cited source

## Environment variables

- `LLM_ORACLE_URL` — override the remote catalog URL (default: `https://oracle.weiseer.com/catalog.json`)
- `LLM_ORACLE_LOCAL_ONLY=1` — skip remote fetch, use bundled catalog only

## Coverage (v0.1)

5 providers, 10 models: Anthropic (Claude Opus/Sonnet/Haiku 4.x), OpenAI (GPT-5, GPT-4o), Google (Gemini 2.5 Pro/Flash), DeepSeek (Reasoner, Chat), Mistral (Large). More coming as observed.

## Project

This is part of [weiseer/llm-oracle](https://github.com/weiseer/oracle) — weiseer's first probe (P-001). License: Apache-2.0. Source: [github.com/weiseer/llm-oracle](https://github.com/weiseer/llm-oracle).

Found a stale price? Open an issue with the source URL we should track.
