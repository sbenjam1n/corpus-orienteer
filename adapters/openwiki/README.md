# OpenWiki Brains adapter

Drop this engine into [LangChain's OpenWiki](https://github.com/langchain-ai/openwiki)

**The integration model.** An OpenWiki "brain" is a wiki instance plus the mode that
maintains it (`code` | `personal`) — there is no brain-plugin API, and connectors are
deliberately built-in-only (see the bundled `skills/write-connector/SKILL.md`: no runtime
plugin loading). So **you don't write a brain, you feed one.** OpenWiki's architecture is
deterministic-fetch-then-LLM-synthesize; this engine slots into the deterministic half
and adds what OpenWiki lacks natively: a search index, an entity registry, seeded
authoritative facts with drift detection, a supersession/correction graph with
retraction down-weighting, claim strata, method reliability, declared monitors, and a
self-coverage audit — all byte-deterministic, no LLM in the build loop.

**Proven end-to-end.** A live run (OpenWiki v0.2.0 on MiniMax-M3) generated a full wiki
over this repo with Layer A in place. The agent's docs correctly state **a(11) OPEN
[462,594]** as the live frontier (not a stale synthesis) and picked up both of the
corpus's correction arcs — the exact defect class OpenWiki's *own* self-wiki exhibits.
The frozen output + writeup (including one honest caveat) is in
[`capture_example/`](capture_example/) → [`CAPTURE.md`](capture_example/CAPTURE.md).

Three layers, cheapest first:

## Layer A — sidecar feeder (zero OpenWiki changes; works today)

1. **Schedule `rebuild` ahead of OpenWiki's update.** In code mode, add a pre-step to
   OpenWiki's CI example (`examples/openwiki-update.yml`) before
   `openwiki code --update --print`:

   ```yaml
   - name: Rebuild corpus orientation graph
     run: ./rag rebuild   # RAG_* env vars or ragconfig.json point at the corpus
   ```

   In personal mode, run it from cron/LaunchAgents alongside `openwiki cron` schedules.

2. **Emit OKF-compliant digest pages** the synthesis agent can read: `brief`,
   unmet `monitors`, `drift`, and supersession summaries as markdown with YAML front
   matter restricted to OpenWiki's OKF keys (`type` required; `title`, `description`,
   `resource`, `tags`). Rules learned from source: never write `index.md` (OpenWiki
   regenerates it deterministically), no extra front-matter fields, and don't hand-write
   inside agent-owned generated pages — use a dedicated subtree declared in
   `openwiki/INSTRUCTIONS.md` as externally generated.

3. **Wire agent consumption through the instruction-file contract.** Outside the managed
   `<!-- OPENWIKI:START -->` block in `AGENTS.md` / `CLAUDE.md`:

   > Before acting on corpus documents (VR-N / AUDIT-N), run
   > `./rag orient <ids-or-paths>` and treat its superseded-citation and
   > stale-assertion findings as mandatory reads. Start sessions from `./rag brief`.

4. **Install the skill** (survives OpenWiki upgrades by design — `syncBundledSkills()`
   preserves third-party skill dirs):

   ```bash
   mkdir -p ~/.openwiki/skills/corpus-orienteer
   cp adapters/openwiki/SKILL.md ~/.openwiki/skills/corpus-orienteer/SKILL.md
   ```

   Compatibility note (verified on OpenWiki v0.2.2, 2026-07-22): newer OpenWiki
   versions require YAML frontmatter (`name` + `description`) on skill files and
   skip skills without it (`Skipping …/SKILL.md: no valid YAML frontmatter found`).
   The bundled `SKILL.md` now carries that frontmatter; if you maintain a local
   copy from an earlier checkout, re-copy it or prepend the frontmatter block.

## Layer B — read-only stdio MCP server (small engine-side addition)

`mcp_server.py` (this directory) wraps the query CLI as a read-only MCP server over
stdio: tools `brief`, `orient`, `search`, `page`, `timeline`, `monitors`. It matches
OpenWiki's `McpConnectorConfig` shape:

```jsonc
{
  "enabled": true,
  "mode": "mcp-stdio",
  "transport": {
    "type": "stdio",
    "command": "python3",
    "args": ["adapters/openwiki/mcp_server.py"],
    "env": { "RAG_CORPUS_DIR": "…", "RAG_SEED_DIR": "…", "RAG_DATA_DIR": "…" }
  },
  "allowedTools": ["brief", "orient", "search", "page", "timeline", "monitors"],
  "readOnlyOperations": [
    { "type": "tool", "name": "brief" },
    { "type": "tool", "name": "monitors" }
  ]
}
```

`readOnlyOperations` gives the per-ingestion deterministic dump into the connector's
`raw/<runId>/`; `openwiki_call_mcp_tool` lets the agent call `orient` mid-run for exactly
the documents it is about to touch. Caveat (verified at `d4e94ab`): OpenWiki wires only
the Notion connector id to `createMcpConnector()` today, so this layer needs a ~20-line
upstream PR exposing a generic MCP ConnectorId — or use Layer A until then. The server
is also useful standalone with any MCP client (Claude Code, etc.).

## Layer C — first-class connector (upstream PR)

`src/connectors/sources/corpus-orienteer.ts` exporting a `ConnectorRuntime`:
`id: "corpus-orienteer"`, `backend: "direct-api"` (local, no network, `requiredEnv: []` —
dirs come from `config.json`: `{ corpusDir, seedsDir, dataDir }`, mirroring `git-repo`'s
pattern), `supportsAgenticDiscovery: true`. `ingest()` = run `rebuild`, then
`writeRawJson()` of `brief`, `monitors`, supersession graph, `drift`, and the coverage
audit under `raw/<runId>/`; corpus content hash in `ConnectorState.latestIds` for no-op
detection; drift/coverage failures in `ConnectorIngestResult.warnings` (surfaced in run
summaries and `state.json` history). The synthesis agent reads these via
`openwiki_read_raw_item` and maintains `/sources/corpus-orienteer.md`.

## Lifecycle mapping

| Engine surface | OpenWiki home |
|---|---|
| `rebuild` | connector `ingest()` / CI pre-step / cron (snapshot-gated like OpenWiki's own update loop) |
| `brief` | regenerated OKF wiki page + session warm-start referenced from `AGENTS.md` |
| `orient <docs>` | on-demand agent tool at plan start (MCP tool or documented CLI; OpenWiki has no per-task pre-action hook, so this rides the instruction contract) |
| unmet `monitors` | connector `warnings` + `/open-questions.md` `Active` entries + a failing/annotating CI step so the scheduled docs PR carries the alert |
| method reliability / drift | `/themes.md` rows via the skill |

## The pitch, concretely

OpenWiki's staleness defense is "hope the next LLM update notices", and its **own
self-wiki** demonstrably carries stale citations (pages referencing repo files that no
longer exist at HEAD). That is exactly the defect class this
engine's supersession graph and self-coverage audit flag deterministically. The two
halves compose: deterministic state estimation (engine) under LLM synthesis (OpenWiki),
with the wiki as the shared medium.
