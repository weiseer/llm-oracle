#!/usr/bin/env node
/**
 * @weiseer/llm-oracle-mcp
 *
 * Stdio MCP server exposing the llm-oracle catalog.
 * Self-contained: ships bundled catalog.json; optionally fetches fresh data
 * from oracle.weiseer.com when reachable.
 *
 * License: Apache-2.0
 * Probe ID: P-001 (organism strategic backlog v2)
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BUNDLED_CATALOG_PATH = join(__dirname, "catalog.json");
const REMOTE_URL =
  process.env.LLM_ORACLE_URL || "https://oracle.weiseer.com/catalog.json";
const LOCAL_ONLY = !!process.env.LLM_ORACLE_LOCAL_ONLY;
const CACHE_TTL_MS = 10 * 60 * 1000;

let _cached = null;
let _cachedAt = 0;

async function loadCatalog() {
  const now = Date.now();
  if (_cached && now - _cachedAt < CACHE_TTL_MS) return _cached;
  if (!LOCAL_ONLY) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 5000);
      const res = await fetch(REMOTE_URL, { signal: ctrl.signal });
      clearTimeout(timer);
      if (res.ok) {
        _cached = await res.json();
        _cachedAt = now;
        _cached._source = "remote";
        return _cached;
      }
    } catch {
      // fall through to bundled
    }
  }
  _cached = JSON.parse(readFileSync(BUNDLED_CATALOG_PATH, "utf-8"));
  _cached._source = "bundled";
  _cachedAt = now;
  return _cached;
}

function allModels(cat) {
  return cat.models || [];
}

// ---- tool handlers ----

async function listModels({ provider, capability } = {}) {
  const cat = await loadCatalog();
  let models = allModels(cat);
  if (provider) models = models.filter((m) => m.provider?.toLowerCase() === provider.toLowerCase());
  if (capability) models = models.filter((m) => m.capabilities?.[capability] === true);
  return {
    as_of: cat.as_of,
    source: cat._source,
    count: models.length,
    models: models.map((m) => ({
      model_id: m.model_id,
      provider: m.provider,
      display_name: m.display_name,
      context_window: m.context_window,
      input_price: m.input_price,
      output_price: m.output_price,
      availability_status: m.availability_status,
    })),
  };
}

async function getModel({ model_id }) {
  if (!model_id) return { error: "model_id required" };
  const cat = await loadCatalog();
  const m = allModels(cat).find((x) => x.model_id === model_id);
  if (!m) return { error: `model_id '${model_id}' not found`, as_of: cat.as_of };
  return { ...m, _source: cat._source };
}

async function findCheapest({
  input_tokens,
  output_tokens,
  required_capabilities = [],
  only_operational = true,
}) {
  if (typeof input_tokens !== "number" || typeof output_tokens !== "number") {
    return { error: "input_tokens and output_tokens are required numbers" };
  }
  const cat = await loadCatalog();
  const ranked = allModels(cat)
    .filter((m) => {
      if (only_operational && m.availability_status !== "operational") return false;
      const caps = m.capabilities || {};
      return required_capabilities.every((c) => caps[c] === true);
    })
    .filter((m) => m.input_price != null && m.output_price != null)
    .map((m) => ({
      model_id: m.model_id,
      provider: m.provider,
      estimated_cost_usd: +(
        (input_tokens / 1_000_000) * m.input_price +
        (output_tokens / 1_000_000) * m.output_price
      ).toFixed(6),
      context_window: m.context_window,
      availability_status: m.availability_status,
    }))
    .sort((a, b) => a.estimated_cost_usd - b.estimated_cost_usd);
  return {
    as_of: cat.as_of,
    source: cat._source,
    query: { input_tokens, output_tokens, required_capabilities, only_operational },
    count: ranked.length,
    ranked,
  };
}

async function compareModels({ model_ids = [], input_tokens = 1000, output_tokens = 500 }) {
  const cat = await loadCatalog();
  const byId = Object.fromEntries(allModels(cat).map((m) => [m.model_id, m]));
  const rows = model_ids.map((mid) => {
    const m = byId[mid];
    if (!m) return { model_id: mid, error: "not_found" };
    const ip = m.input_price || 0;
    const op = m.output_price || 0;
    return {
      model_id: mid,
      provider: m.provider,
      input_price: ip,
      output_price: op,
      context_window: m.context_window,
      max_output_tokens: m.max_output_tokens,
      capabilities: m.capabilities || {},
      availability_status: m.availability_status,
      estimated_cost_usd: +(
        (input_tokens / 1_000_000) * ip +
        (output_tokens / 1_000_000) * op
      ).toFixed(6),
    };
  });
  return { as_of: cat.as_of, source: cat._source, query: { input_tokens, output_tokens }, rows };
}

async function checkAvailability({ model_id }) {
  if (!model_id) return { error: "model_id required" };
  const cat = await loadCatalog();
  const m = allModels(cat).find((x) => x.model_id === model_id);
  if (!m) return { error: `model_id '${model_id}' not found` };
  return {
    model_id,
    availability_status: m.availability_status,
    source_url: m.availability_source_url,
    last_checked: m.last_availability_check,
    as_of: cat.as_of,
    source: cat._source,
  };
}

const TOOLS = [
  {
    name: "list_models",
    description:
      "List LLM models, optionally filtered by provider or required capability. Returns brief records.",
    inputSchema: {
      type: "object",
      properties: {
        provider: {
          type: "string",
          description: "filter by provider id (anthropic / openai / google / deepseek / mistral)",
        },
        capability: {
          type: "string",
          description:
            "filter by required capability (tool_use / vision / audio / structured_output / prompt_caching)",
        },
      },
    },
  },
  {
    name: "get_model",
    description: "Full record for one model id, including cited pricing/availability source URLs.",
    inputSchema: {
      type: "object",
      properties: { model_id: { type: "string" } },
      required: ["model_id"],
    },
  },
  {
    name: "find_cheapest",
    description:
      "Rank models by estimated cost for a given token spec; returns cheapest first. Skip non-operational by default.",
    inputSchema: {
      type: "object",
      properties: {
        input_tokens: { type: "number" },
        output_tokens: { type: "number" },
        required_capabilities: { type: "array", items: { type: "string" } },
        only_operational: { type: "boolean", default: true },
      },
      required: ["input_tokens", "output_tokens"],
    },
  },
  {
    name: "compare_models",
    description: "Side-by-side comparison of a set of models for a token spec.",
    inputSchema: {
      type: "object",
      properties: {
        model_ids: { type: "array", items: { type: "string" } },
        input_tokens: { type: "number", default: 1000 },
        output_tokens: { type: "number", default: 500 },
      },
      required: ["model_ids"],
    },
  },
  {
    name: "check_availability",
    description: "Current availability status for a model with cited source URL.",
    inputSchema: {
      type: "object",
      properties: { model_id: { type: "string" } },
      required: ["model_id"],
    },
  },
];

const HANDLERS = {
  list_models: listModels,
  get_model: getModel,
  find_cheapest: findCheapest,
  compare_models: compareModels,
  check_availability: checkAvailability,
};

const server = new Server(
  { name: "llm-oracle", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  const handler = HANDLERS[name];
  if (!handler) {
    return {
      content: [{ type: "text", text: JSON.stringify({ error: `unknown tool: ${name}` }) }],
      isError: true,
    };
  }
  try {
    const result = await handler(args || {});
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  } catch (e) {
    return {
      content: [{ type: "text", text: JSON.stringify({ error: e.message }) }],
      isError: true,
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
process.stderr.write("llm-oracle-mcp connected via stdio\n");
