---
type: Architecture
title: Architecture overview — engine, demo program, OpenWiki adapter
description: "The three-hat structure of corpus-orienteer: the engine (scripts/rag/, MIT), the Erdős distinct-subset-sums demo program it operates, and the OpenWiki adapter that feeds the engine into LangChain's OpenWiki. Plus the build pipeline, determinism invariant, and the source-vs-derived boundary."
tags: [openwiki, architecture, overview, engine, demo, openwiki]
---

# Architecture overview

`corpus-orienteer` is structured around one stable split: an **engine** (domain-agnostic,
MIT-licensed) and a **deployment** (the Erdős distinct-subset-sums demo + a reference
deployment + an OpenWiki adapter). The engine is the asset; the demo is one of its
deployments and the engine's own dogfood.

## The three components

### 1. The engine — `scripts/rag/` (MIT)

Stdlib-only Python that ingests an append-only markdown corpus and produces a
byte-deterministic graph:

- **Entity registry** with declared types + value histories.
- **Supersession / correction graph** (reference-class benign edges vs correction-class
  edges extracted only from metadata).
- **Seeded ontology** of canonical objects with authoritative facts the indexer
  *validates* (drift detection) rather than extracts.
- **Declared monitors** evaluated every build (`forbidden_predicate`,
  `settled_independent_route`, `completeness_claim`, `claim_pending`,
  `json_field`/`json_count`/`text_present`/`text_absent`).
- **Self-coverage audit** — what the structured layers silently miss.
- Two agent-facing artifacts: **`brief`** (whole-program warm start) and
  **`orient <docs>`** (plan-scoped: superseded citations, stale numeric candidates,
  method reliability, in-scope unmet monitors — for exactly the documents you're about to
  touch).

The engine is ported to any corpus by swapping `domain_config.json` + the ontology seeds;
no engine code is touched. See [Port your corpus](../operations/port-your-corpus.md).

Full operational reference: `scripts/rag/README.md`. Concept glossary:
[Engine layers](engine-layers.md).

### 2. The demo program — `corpus/`, `arms/`, `domains/erdos1/`, `plans/`, `QUEUE.md`

A long-running research program that operates the engine while computing on
**erdosproblems.com #1, OEIS A276661** — the Erdős distinct-subset-sums problem. The
problem is provably not resolvable by finite computation, which makes it a safe endless
demo, and the program's three ladders (exact table `a(n)`, construction records
`n ≥ 14`, the empirical constant curve `a(n)/2^n`) produce a steady stream of `VR-N`
documents the engine indexes.

- **Corpus**: append-only `corpus/VR-*.md` (results) and `corpus/AUDIT-*.md` (findings
  about results). The header contract is pinned in `docs/rag_corpus_format.md`.
- **Compute arms**: `arms/exhaustive.py`, `arms/feasible.c`, `arms/gate_parallel.py`,
  `arms/conway_guy.py`, `arms/verify_set.py`, `arms/records.py`,
  `arms/constants_curve.py`. Each arm is independently calibrated — no arm's output
  counts until it reproduces every cheaply reachable published result in its class.
  See [Compute arms](../research-program/compute-arms.md).
- **Domain config + seeds**: `domains/erdos1/domain_config.json` (entity families,
  supersession patterns, method indicators, type schema) + four seed JSONs +
  `tiers.json` (heterogeneous population declaration).
- **Plans**: `plans/P1..P7.md` are living documents (append-only history; version
  bumps; claims registry entries that require an artifact).
- **Work queue**: `QUEUE.md` is planner-write-only (the agent is read-only here). §1
  ordering is the single source of truth for "what to work on next."

### 3. The OpenWiki adapter — `adapters/openwiki/`

Wires the engine into LangChain's OpenWiki as the deterministic half of a brain
(deterministic-fetch → LLM-synthesize). Three layers, cheapest first:

- **Layer A** — sidecar feeder (`emit_okf.py`): rebuild → emit OKF digest pages into
  `wiki/corpus-orienteer/` for the synthesis agent to read.
- **Layer B** — read-only stdio MCP server (`mcp_server.py`): six tools (brief, orient,
  search, page, timeline, monitors) usable from any MCP client.
- **Layer C** — connector spec (`upstream-generic-mcp-connector.md`): the upstream PR
  sketch for a generic `mcp` ConnectorId in `langchain-ai/openwiki`.

The adapter owns the bootstrap contract in this repo (`AGENTS.md` outside the managed
block; the skill `SKILL.md` installed into `~/.openwiki/skills/`). See
[OpenWiki integration](../integrations/openwiki-brain.md).

## The build pipeline

`scripts/rag/rebuild.sh` orchestrates four core stages (stdlib-only, ~5–10s steady state)
plus two optional flag-gated stages:

| Stage | Script | Produces |
|---|---|---|
| `[1/4]` index | `index_vrs.py` | chunks, entity/type registries, type violations, supersession, file_meta, claim_status, arcs, method_registry, concepts, index_stats |
| `[2/4]` ontology | `ontology.py` | objects, domain_links, object_drift, monitors |
| `[3/4]` coverage | `coverage.py` | coverage_report |
| `[4/4]` brief | `synthesize_brief.py` | `data/rag/audit_brief.md` (warm-start digest); rolls `file_meta_prev` snapshot |
| _(optional)_ | `embed.py` (`--embed`) | chroma_db, model (only if you opt into semantic search) |
| _(optional)_ | `doctest_grounding.py` (`--doctest`) | doctest_results.json (heavy; needs `gp`) |

Outputs land in `data/rag/` (gitignored, derived). The pipeline is reproducible from
`corpus/` + `domains/erdos1/` alone.

## The determinism invariant

Every `generated` stamp in the engine's outputs is **derived from the corpus** (max doc
date + doc count), never the wall clock. So rebuilding the same corpus twice produces
byte-identical `data/rag/` outputs and a clean `git status`. This is asserted by:

- `scripts/rag/tests/determinism_check.sh` — rebuilds twice; requires byte-identical
  `data/rag/` outputs.
- `.github/workflows/rag-tests.yml` — engine suite + demo arm tests + a corpus-conformance
  job whose second rebuild must match the first.

The invariant is why the engine is "evidence, never proof" without sliding into
indeterminism: every detector that ran, ran in the same way.

## Source vs derived (the binding line)

| Tier | Path | Status |
|---|---|---|
| Source — corpus | `corpus/` | append-only truth |
| Source — domain | `domains/<x>/{domain_config, *seed, tiers}.json` | hand-curated; planner-gated edits |
| Source — plans | `plans/P*.md` | living documents with version history |
| Source — channels | `QUEUE.md`, `README.md` | mutable; seq-stamped |
| **Derived** | `data/rag/` | engine outputs; gitignored; **never** cited as provenance |
| **Derived** | `wiki/corpus-orienteer/` | OpenWiki OKF pages emitted by `emit_okf.py`; **never** re-ingested (declared `indexed: false` in `tiers.json`) |

The boundary is enforced by the engine: `data/rag/` is gitignored; the wiki subtree is
declared as a `derived` tier in `domains/erdos1/tiers.json` so the indexer's
`indexed: false` rule excludes it from re-ingestion.

## Governance at a glance

`AGENTS.md` is binding for any agent. It mandates:

- Warm start from `./rag brief`; `./rag orient <docs>` before acting on any plan or VR set.
- `data/rag/` and `wiki/corpus-orienteer/` are derived — never sources.
- Corpus conclusions change only via new documents carrying correction verbs in metadata
  (`docs/rag_corpus_format.md`); corrected docs get inline `[CORRECTED per VR-N]` tags.
- The engine's outputs are evidence, never proof; candidates are regions to read.

The full authority chain (planner / agent / auditor / seeds / third-party) lives in
`QUEUE.md` §0.5 P3; the [working protocol](../workflows/working-protocol.md) page
distills it.

## CI

Two workflows in `.github/workflows/`:

- **`rag-tests.yml`** (push + PR): engine unit suite + fixture end-to-end with
  byte-determinism + demo arm tests (golden values + guards) + corpus-conformance
  rebuild on the live demo corpus.
- **`openwiki-update.yml`** (daily 08:00 UTC + manual dispatch): scheduled OpenWiki docs
  PR using `openwiki code --update --print`. The two pre-steps needed for the engine to
  feed it (rebuild + emit OKF pages + optional HIGH-monitor gate) live in
  `adapters/openwiki/openwiki-update-prestep.yml`.
