---
type: Integration
title: OpenWiki brain integration — Layer A sidecar feeder, Layer B MCP server, Layer C connector spec
description: "How the corpus-orientation engine slots into LangChain's OpenWiki as the deterministic half of a brain (deterministic-fetch → LLM-synthesize). Layer A: rebuild + OKF digest emission (zero OpenWiki changes; works today). Layer B: read-only stdio MCP server (works with any MCP client; needs a generic ConnectorId in OpenWiki). Layer C: upstream PR sketch for a generic mcp ConnectorId. Plus the AGENTS.md contract, the skill installed into ~/.openwiki/skills/, and the tier declaration that prevents derived pages from being re-ingested."
tags: [openwiki, integration, openwiki, brain, mcp, okf, layer-a, layer-b, layer-c]
---

# OpenWiki brain integration

The repo feeds LangChain's OpenWiki ("OpenWiki Brains", v0.1.0 2026-07-10; design
verified against `d4e94ab` / v0.2.0) as the **deterministic half** of a brain.
OpenWiki's architecture is *deterministic-fetch-then-LLM-synthesize*; this engine slots
into the deterministic half and adds what OpenWiki lacks natively:

- a search index (TF-IDF + optional ONNX/ChromaDB),
- an entity registry with declared types + value histories,
- seeded authoritative facts with **drift detection**,
- a **supersession/correction graph** with retraction down-weighting,
- **claim strata** (proved / verified / predicted / open / retracted),
- **method reliability** lifecycles,
- **declared monitors** evaluated every build,
- a **self-coverage audit**.

All byte-deterministic, no LLM in the build loop.

> **Brains, not plugins.** An OpenWiki brain is a wiki instance plus the mode that
> maintains it (`code` | `personal`) — there is no brain-plugin API, and connectors are
> deliberately built-in-only (see `skills/write-connector/SKILL.md`: no runtime plugin
> loading). So **you don't write a brain, you feed one**.

## Layer A — sidecar feeder (zero OpenWiki changes; works today)

The cheapest layer and the one already shipped. Three pieces:

### A.1 OKF digest emitter — `adapters/openwiki/emit_okf.py`

Renders the engine's deterministic surfaces (`brief`, `monitors`, `drift`, `captures`)
as OpenWiki OKF pages in `wiki/corpus-orienteer/`. Constraints verified the hard way
(documented in `adapters/openwiki/README.md` §Layer A):

- YAML front matter uses **exactly** the five OKF keys OpenWiki accepts
  (`type` required; `title`, `description`, `resource`, `tags`) — nothing else.
- **Never writes `index.md`** (OpenWiki regenerates index files deterministically).
- Two emissions from the same build are **byte-identical** (regression-tested in
  `tests/test_arms.py::TestEmitOkf`).

Pages emitted (each skipped cleanly when its source is absent):

| Page | Source | Content |
|---|---|---|
| `brief.md` | `data/rag/audit_brief.md` | warm-start digest (active arcs, distrusted methods, unmet monitors, drift, changed-since-last-pass) |
| `monitors.md` | `data/rag/monitors.json` | declared monitors, unmet first, with watch text + evidence |
| `drift.md` | `data/rag/object_drift.json` | seed↔corpus drift report (confirmed/unconfirmed/flagged/unverified/no_detector counts + per-flag rows) |
| `captures.md` | `data/rag/capture_ledger.json` | cross-tier capture state for tiered deployments with thread tiers (reconciliation receipts) |

Each `description` field carries the corpus stamp (`<date>+<N>docs`) so the page ties
to the build that produced it.

### A.2 CI pre-step drop-in — `adapters/openwiki/openwiki-update-prestep.yml`

Insert ahead of the `openwiki code --update --print` step in OpenWiki's scheduled
update workflow (`examples/openwiki-update.yml`):

```yaml
- name: Rebuild corpus orientation graph
  run: ./rag rebuild
- name: Emit OKF digest pages (brief, monitors, drift, captures)
  run: python3 adapters/openwiki/emit_okf.py --out wiki/corpus-orienteer
- name: Fail loudly on unmet HIGH monitors (optional gate)
  # … see the prestep file …
```

This repo's `.github/workflows/openwiki-update.yml` runs the OpenWiki update daily at
08:00 UTC + on `workflow_dispatch`. The pre-step is the only thing that has to land
in OpenWiki's example workflow; the rest of the adapter stays in this repo.

### A.3 Instruction contract — `AGENTS.md`

Outside the managed `<!-- OPENWIKI:START -->` block, the agent contract reads:

> Before acting on corpus documents (VR-N / AUDIT-N), run `./rag orient <ids-or-paths>`
> and treat its superseded-citation and stale-assertion findings as mandatory reads.
> Start sessions from `./rag brief`.

The skill `adapters/openwiki/SKILL.md` is installed into `~/.openwiki/skills/corpus-orienteer/`
to make this contract available to the synthesis agent across sessions. Per
OpenWiki's `syncBundledSkills()`, third-party skill dirs survive upgrades by design.

### A.4 Tier declaration — `domains/erdos1/tiers.json`

The wiki subtree is declared a **`derived` tier** so the indexer's `indexed: false`
rule excludes it from re-ingestion. Without this, the next `./rag rebuild` would
chunk-index the OKF pages and the self-consumption guard would have to defend against
its own output.

```jsonc
{ "id": "derived", "roots": ["data/rag", "wiki/corpus-orienteer"],
  "contract": "vr", "indexed": false, "authority": 0, "citable_as_receipt": false }
```

### A.5 Validator port — `adapters/openwiki/okf_validator_port.mjs`

Verbatim JS port of OpenWiki's `validateOkfFrontmatter` (from `src/agent/frontmatter-validator.ts
@ d4e94ab`) — types stripped, logic identical. Validates every emitted page without
needing the OpenWiki install. Asserts: `brief.md`, `monitors.md`, `drift.md` are
all VALID. (The plan tracked 2.4(a) as DONE with this port; 2.4(b) — the live agent
before/after capture — needs an actual OpenWiki install with provider keys.)

## Layer B — read-only stdio MCP server — `adapters/openwiki/mcp_server.py`

Stdlib-only, newline-delimited JSON-RPC 2.0 on stdio (the MCP stdio transport). Exposes
six read-only tools that wrap the engine's orientation surfaces:

| Tool | What it returns |
|---|---|
| `brief` | Warm-start digest of the whole research corpus |
| `orient` | Plan-scoped orientation: superseded citations, stale-assertion candidates, method reliability, in-scope monitors, correction arcs |
| `search` | Corpus search (semantic if vectors built, else TF-IDF; retracted/down-weighted) |
| `page` | Consolidated object record (type, aliases, properties, per-(curve,field) pair facts, links, claims, drift) |
| `timeline` | Value/concept evolution of an entity across the corpus |
| `monitors` | Declared object monitors + evaluated state (unmet first) |

Designed to match OpenWiki's `McpConnectorConfig` shape (`mode: "mcp-stdio"`,
`transport.command`, `transport.args`, `transport.env`, `allowedTools`,
`readOnlyOperations`):

```jsonc
{
  "enabled": true,
  "mode": "mcp-stdio",
  "transport": {
    "type": "stdio",
    "command": "python3",
    "args": ["adapters/openwiki/mcp_server.py"],
    "env": { "RAG_CORPUS_DIR": "...", "RAG_SEED_DIR": "...", "RAG_DATA_DIR": "..." }
  },
  "allowedTools": ["brief", "orient", "search", "page", "timeline", "monitors"],
  "readOnlyOperations": [
    { "type": "tool", "name": "brief" },
    { "type": "tool", "name": "monitors" }
  ]
}
```

`readOnlyOperations` gives the per-ingestion deterministic dump into the connector's
`raw/<runId>/`; `openwiki_call_mcp_tool` lets the agent call `orient` mid-run for
exactly the documents it is about to touch.

**Caveat (verified at `d4e94ab`)**: OpenWiki wires only the Notion connector id to
`createMcpConnector()` today, so this layer needs a ~20-line upstream PR exposing a
generic `mcp` ConnectorId — or use Layer A until then. The server is also useful
standalone with any MCP client (Claude Code, etc.).

## Layer C — first-class connector (upstream PR)

`adapters/openwiki/upstream-generic-mcp-connector.md` is the upstream PR sketch.
**Not verified against current HEAD** — rebase before submitting. The change is:

1. `src/connectors/types.ts` — add `"mcp"` to the `ConnectorId` union.
2. `src/connectors/registry.ts` — register the generic runtime (`backend: "mcp-stdio"`,
   `requiredEnv: []`, `supportsAgenticDiscovery: true`); instances follow the
   existing multi-instance convention (`mcp-1`, `mcp-2`, …).
3. `src/connectors/mcp-runtime.ts` — no changes; the read-only policy
   (`allowedTools` / `readOnlyHint` / read-only-name heuristic) already generalizes.
4. Onboarding (`--init`) — add "MCP server" to the connector picker.

The sketch's pitch: OpenWiki's deliberate no-runtime-plugin policy stays intact — no
plugin loading is added; MCP is already OpenWiki's sanctioned boundary for external
tools, and the runtime already enforces read-only. It converts every read-only MCP
server into a brain source with zero further code — including deterministic corpus
engines like this one.

## Surface-to-home mapping (from `adapters/openwiki/README.md`)

| Engine surface | OpenWiki home |
|---|---|
| `rebuild` | connector `ingest()` / CI pre-step / cron (snapshot-gated like OpenWiki's own update loop) |
| `brief` | regenerated OKF wiki page + session warm-start referenced from `AGENTS.md` |
| `orient <docs>` | on-demand agent tool at plan start (MCP tool or documented CLI; OpenWiki has no per-task pre-action hook, so this rides the instruction contract) |
| unmet `monitors` | connector `warnings` + `/open-questions.md` `Active` entries + a failing/annotating CI step so the scheduled docs PR carries the alert |
| method reliability / drift | `/themes.md` rows via the skill |

## The pitch, concretely

OpenWiki's staleness defense is "hope the next LLM update notices" — and its **own
self-wiki demonstrably carries stale citations** (pages referencing repo files that no
longer exist at HEAD, verified 2026-07-16). That is exactly the defect class this
engine's supersession graph and self-coverage audit flag deterministically. The two
halves compose: deterministic state estimation (engine) under LLM synthesis (OpenWiki),
with the wiki as the shared medium.
