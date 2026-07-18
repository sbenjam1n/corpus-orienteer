# Upstream PR sketch: generic MCP connector id for OpenWiki (P5 Layer B → C bridge)

**Target:** `langchain-ai/openwiki` (sketch written against `d4e94ab` / v0.2.0 source
reads, 2026-07-16; **not verified against current HEAD** — rebase before submitting).
**Problem:** `createMcpConnector()` + `McpConnectorConfig` exist and enforce a read-only
tool policy, but only the `notion` ConnectorId is wired to them — a user cannot
configure an arbitrary MCP server (like `corpus-orienteer`'s stdio server) as a source
without forking.

## The change (~20 lines + registry entry)

1. `src/connectors/types.ts` — add a generic id:

```ts
export type ConnectorId =
  | "gmail" | "notion" | "slack" | "git-repo" | "web-search" | "hackernews" | "x"
  | "mcp";                       // NEW: user-configured MCP server (stdio or http)
```

2. `src/connectors/registry.ts` — register the generic runtime; instances follow the
existing multi-instance convention (`mcp-1`, `mcp-2`, …):

```ts
import { createMcpConnector } from "./sources/mcp";

// in createConnectorRegistry():
mcp: createMcpConnector({
  id: "mcp",
  displayName: "MCP server",
  description: "A user-configured Model Context Protocol server (read-only).",
  backend: "mcp-stdio",           // overridden per-instance by config.json `mode`
  requiredEnv: [],                // credentials, if any, ride transport.env
  supportsAgenticDiscovery: true, // gated by allowedTools/readOnlyOperations anyway
}),
```

3. No changes to `src/connectors/mcp-runtime.ts` — the read-only policy
(`allowedTools` / server `readOnlyHint` / read-only-name heuristic) already generalizes;
the Notion-specific heuristic stays scoped to the `notion` id.

4. Onboarding (`--init`): add "MCP server" to the connector picker; its config step
writes `~/.openwiki/connectors/mcp-<n>/config.json` in the existing
`McpConnectorConfig` shape (`mode`, `transport{command,args,env,url,headers}`,
`allowedTools`, `readOnlyOperations`).

## Why upstream should want it

- The deliberate no-runtime-plugin policy (`skills/write-connector/SKILL.md`) stays
  intact: this adds no plugin loading — MCP is already OpenWiki's sanctioned boundary
  for external tools, and the runtime already enforces read-only.
- It converts every read-only MCP server into a brain source with zero further code —
  including deterministic corpus engines like this one (see `mcp_server.py`: tools
  `brief`/`orient`/`search`/`page`/`timeline`/`monitors`, per-ingestion dumps via
  `readOnlyOperations`).

## Example instance config (this engine)

```jsonc
// ~/.openwiki/connectors/mcp-1/config.json
{
  "enabled": true,
  "mode": "mcp-stdio",
  "transport": {
    "type": "stdio",
    "command": "python3",
    "args": ["/path/to/corpus-orienteer/adapters/openwiki/mcp_server.py"],
    "env": { "RAG_CORPUS_DIR": "...", "RAG_SEED_DIR": "...", "RAG_DATA_DIR": "..." }
  },
  "allowedTools": ["brief", "orient", "search", "page", "timeline", "monitors"],
  "readOnlyOperations": [
    { "type": "tool", "name": "brief" },
    { "type": "tool", "name": "monitors" }
  ]
}
```

## Submission checklist

- [ ] Rebase the sketch against HEAD (`src/connectors/*` moves fast; v0.2.0 shipped OKF)
- [ ] `openwiki ingest mcp-1` end-to-end against `mcp_server.py`
- [ ] Docs: connectors page + `--init` copy
- [ ] Tests mirroring the notion-connector suite for the generic id
