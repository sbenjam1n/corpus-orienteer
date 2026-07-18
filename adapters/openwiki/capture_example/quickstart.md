---
type: Quickstart
title: corpus-orienteer — quickstart
description: One-page entrypoint for the corpus-orientation RAG engine + the Erdős distinct-subset-sums demo research program it operates, plus the OpenWiki integration. Start here.
tags: [openwiki, quickstart, orientation]
---

# corpus-orienteer — quickstart

`corpus-orienteer` is two things in one repo:

1. A **corpus-orientation engine** (`scripts/rag/`, MIT) — a stdlib-only, byte-deterministic
   tool that turns an append-only markdown corpus into a typed supersession/correction
   graph, a seeded ontology, declared monitors, drift detection, a self-coverage audit,
   and two agent-facing artifacts: a whole-program **brief** and a plan-scoped
   **orient** report. It is **not** a chat-RAG; it is the state estimator for an
   ongoing decision process.
2. A **live demo research program** (`domains/erdos1/`, `corpus/`, `arms/`) that operates
   the engine while computing on the **Erdős distinct subset sums problem**
   (erdosproblems.com #1, OEIS A276661, $500 prize) — a deliberately open problem whose
   live frontier at `a(11) ∈ [462, 594]` is exactly the kind of decision process the
   engine is built for. The engine is dogfooded as the demo: every program-level artifact
   is a corpus document the engine indexes.

Plus an **OpenWiki adapter** (`adapters/openwiki/`) that feeds the engine's deterministic
surfaces into LangChain's OpenWiki (the "brain" integration).

> **Source vs derived.** Per `AGENTS.md`: `data/rag/` and `wiki/corpus-orienteer/` are
> **derived** artifacts — never sources, never cited as provenance. The engine rebuild
> overwrites them deterministically.

## Orientation contract (binding for any agent)

Per `AGENTS.md`:

1. **Warm start.** Run `./rag brief` first — it prints the deterministic warm-start digest
   (active correction arcs, distrusted methods, unmet monitors, drift, changed-since-last-pass).
2. **Pre-action orientation.** Before summarizing, citing, or acting on specific corpus
   documents (ids like `VR-N` / `AUDIT-N`), run `./rag orient <ids-or-paths>`. Its report
   lists cited documents that have been corrected or superseded (with the winning document
   to read instead), stale numeric assertions (candidates to read, **never** verdicts),
   method reliability, and in-scope unmet monitors. **Never cite a document the orient
   report marks as a correction loser without also citing its corrector.**
3. **Search.** Prefer `./rag query search "<terms>"` over raw grep — results down-weight
   retracted and deprecated documents.
4. The engine's outputs are **evidence, never proof**: a detector's zero is not a
   certification; candidates are regions to read, not verdicts.

## 60-second tour

```bash
# 1. Engine sanity (unit + fixture end-to-end with byte-determinism assert)
./rag test

# 2. Build the corpus-orientation graph (stdlib-only, ~5–10s)
./rag rebuild

# 3. The two orientation surfaces
./rag brief                       # whole-program warm start
./rag orient AUDIT-1              # plan-scoped: AUDIT-1 cites VR-1 — orient flags VR-1 as a correction loser
./rag query search "certificate ceiling"
./rag query page "a(11)"          # the live frontier object
./rag query monitors              # 5 declared monitors + state
```

## Where things live

| What | Where | Notes |
|---|---|---|
| Demo corpus (the truth) | `corpus/VR-*.md`, `corpus/AUDIT-*.md` | append-only; corrections are new docs |
| Engine source (MIT) | `scripts/rag/` | stdlib-only; `README.md` is the operational reference |
| Engine entry | `./rag` | bash dispatcher; reads `ragconfig.json` |
| Compute arms (the demo's math) | `arms/` | each is independently calibrated; see [compute-arms](research-program/compute-arms.md) |
| Domain config + seeds | `domains/erdos1/` | `domain_config.json` + four seeds + `tiers.json` |
| Reference deployment | `domains/r14-bsd/` | engine's origin; corpus not included |
| OpenWiki adapter | `adapters/openwiki/` | Layer A OKF feeder, Layer B MCP server, Layer C spec |
| Plans (living) | `plans/P1..P7.md` | append-only history; each carries a claims registry |
| Work queue | `QUEUE.md` | planner-write-only; agent is read-only here |
| Design docs | `docs/` | corpus contract, corpus-tiers design, engine v3 design, ontology assessment |
| CI | `.github/workflows/rag-tests.yml`, `openwiki-update.yml` | engine conformance + scheduled OpenWiki PR |

## Major sections

- [Architecture overview](architecture/overview.md) — the engine↔demo split, the build
  pipeline, determinism, governance.
- [Engine layers](architecture/engine-layers.md) — the 5 layers (entity → vectors →
  grounding → ontology → robustness) and the query CLI.
- [Erdős frontier](research-program/erdos-frontier.md) — the problem, the current a(n)
  table, the CG-optimality refutation, the Bohman asymptotic record.
- [Compute arms](research-program/compute-arms.md) — `exhaustive`, `feasible.c`,
  `gate_parallel`, `conway_guy`, `verify_set`, `records`, `constants_curve`; what each
  does and the calibration discipline shared by all.
- [Working protocol](workflows/working-protocol.md) — the `orient → execute → record →
  reconcile` loop, header contract, supersession graph, authority chain.
- [Queue and plans](workflows/queue-and-plans.md) — `QUEUE.md` governance, the current
  state of `A2` / `A3` / `A4` / `S1` / `S2`, plan versioning discipline.
- [OpenWiki integration](integrations/openwiki-brain.md) — deterministic-fetch →
  LLM-synthesize split; Layers A / B / C.
- [Port your corpus](operations/port-your-corpus.md) — swap `domains/<yours>/` + point
  the env vars; reference deployments.
- [Testing strategy](testing/strategy.md) — three standing checks (wrong value / wrong
  binding / overclaim), byte-determinism, CI.
- [Source map](source-map.md) — one-line inventory of every top-level directory.

## Backlog

Areas deliberately not documented in detail on this initial run (note the area, source
anchor, and why deferred):

- **Detailed `domains/r14-bsd/` walk-through** — the engine's origin math program; corpus
  not present, so a one-line pointer in [source-map](source-map.md) suffices until the
  corpus lands.
- **`scripts/rag/coverage.py` and `grounding_check.py` internals** — covered at overview
  level in [engine layers](architecture/engine-layers.md); the engine README
  (`scripts/rag/README.md`) is the operational reference.
- **Layer C upstream OpenWiki PR details** — the PR is upstream
  (`langchain-ai/openwiki`), not in this repo; the spec sketch lives in
  `adapters/openwiki/upstream-generic-mcp-connector.md` and is referenced from
  [OpenWiki integration](integrations/openwiki-brain.md).
- **Detailed seed schema reference** — covered inline in
  [port your corpus](operations/port-your-corpus.md); a dedicated reference page is
  backlogged until the engine ships an external port beyond `erdos1` and `r14-bsd`.
