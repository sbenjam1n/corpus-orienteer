# corpus-orienteer: an ontology/audit RAG engine for long-running research programs

A deterministic, stdlib-only **corpus-orientation engine** (`scripts/rag/`, MIT) plus a
**live demo research program** it operates: computing on the Erdős distinct subset sums
problem (erdosproblems.com **#1**, $500 prize, open since the 1930s and provably not
resolvable by finite computation, which is exactly why it makes a safe, endless demo).

The engine answers the question every long-lived agent program hits: *"I'm about to act:
what does this program currently believe, which of my inputs are stale, and which methods
can I trust?"* It is not a chat-RAG: it is the **state estimator** for an ongoing
decision process. Everything it builds is byte-deterministic (no LLM in the build loop),
derived from an **append-only markdown corpus** where corrections are new documents that
point back, never edits.

This engine aims to **orient agents in a long-running program**, with retrieval being just one surface among
many and **differs from other ontology-aware RAG projects in some key ways**. This isn't **LLM-derived ontologies** from unstructured text; the ontology here is **hand-curated seed truth that the indexer validates and refuses to extract**;  auto-extraction-as-authoritative is a failure mode this tool's design
explicitly rejects. Our build is **byte-deterministic** and CI-asserted, and runs without an LLM in the loop. The intended corpus is an **append-only corrective log**, the output of an ongoing research program or descision process, with supersession semantics, claim strata, method reliability, monitors, and drift.

**Contents:** [What it builds](#what-the-engine-builds) · [Quick start](#try-it-in-5-minutes) ·
[Command reference](#command-reference-the-operational-surface) ·
[The demo program](#the-demo-program) · [Compute arms](#compute-arms) ·
[Corpus tiers](#corpus-tiers-heterogeneous-document-populations) ·
[OpenWiki integration](#langchain--openwiki-brains-integration) ·
[Porting](#porting-the-engine-to-your-program) · [Repository map](#repository-map) ·
[Testing & CI](#testing--ci)

## What the engine builds

From a flat directory of dated, statused markdown docs (`VR-N` results, `AUDIT-N`
findings (contract in `docs/rag_corpus_format.md`):

- typed **entity registry** with per-value history; **supersession/correction graph**
  (retracted docs down-weighted in search); research **arcs** with convergence states;
  **method-reliability** lifecycles; per-claim **epistemic strata**
- a seeded **ontology** of canonical objects with authoritative facts the indexer
  *validates* (drift detection) rather than extracts; typed links; **declared monitors**
  evaluated every build (including claim-level detectors: forbidden predicates,
  completeness overclaims, settled-without-independent-route)
- **corpus tiers** ([P6](#corpus-tiers-heterogeneous-document-populations)): index
  threads, versioned papers, plans, and derived artifacts each under their own metamodel
- **self-coverage audits**: the tool reports what it is silently missing
- two agent-facing artifacts: **`brief`** (whole-program warm start) and
  **`orient <docs>`** (plan-scoped: superseded citations, stale numeric assertions,
  method reliability, unmet monitors, for exactly the documents you're about to act on)

## Try it in 5 minutes

```bash
git clone <this repo> && cd corpus-orienteer

./rag test        # engine suite: 56 tests + fixtures + byte-determinism; ./rag test  (arms: python3 -m unittest discover -s tests → 9)
./rag rebuild     # index the demo program's corpus (corpus/, config in ragconfig.json)
./rag brief       # "you are here": arcs, distrusted methods, unmet monitors, drift
./rag monitors    # the program's standing invariants, evaluated deterministically
./rag orient AUDIT-1   # about to act on AUDIT-1? it cites VR-1 — orient flags VR-1
                       # as a correction loser: "⚠ VR-1 … loses to VR-2 [corrects]"
./rag query search "certificate ceiling"
./rag query page "a(11)"     # the live frontier object: window [462,594], provenance
```

The demo corpus is real, not staged: VR-1's frontier table shipped stale (the research
that selected this problem reported "exact optima known to n=9"; adversarial
verification found OEIS had moved to a(10)=309 in Oct 2025), and AUDIT-1 records the
finding, VR-2 corrects it, and the engine's graph carries the whole story. It now spans
**9 VRs + 1 AUDIT** with several genuine correction arcs (e.g. VR-5 correcting VR-2's
citation, VR-8 correcting an over-optimistic engine design).

## Command reference / Operational surface

Everything is driven by the root `./rag` wrapper, which resolves `ragconfig.json`
(corpus/seed/data dirs) into the engine's env vars and dispatches. **Env vars win over
the config file**, so `RAG_CORPUS_DIR=… ./rag rebuild` is a one-off override.

### `./rag` subcommands

| Command | Does |
|---|---|
| `./rag rebuild [--embed] [--doctest]` | Full build: index → ontology → coverage → brief. `--embed` adds the optional ONNX/ChromaDB vector layer; `--doctest` re-runs cited reproducers. |
| `./rag query <mode> [args]` | Any query mode (below). |
| `./rag orient <doc…> [--out slug]` | Plan-scoped orientation artifact for the given docs/ids. |
| `./rag brief` | Warm-start whole-program digest. |
| `./rag grounding` | Dangling-ref / reproducer / retraction-propagation check. |
| `./rag coverage` | Self-coverage audit (what the extractor is missing). |
| `./rag monitors` | Declared monitors, evaluated (unmet first). |
| `./rag viz <links\|graph\|arc> [VR-N]` | Render relationship graphs (Mermaid/DOT/d3-HTML/PNG). |
| `./rag test` | Engine unit + fixture e2e suite (56 tests). |
| `./rag doctor` | Corpus conformance check + `index_stats`. |
| `./rag config` | Print the resolved corpus/seed/data dirs. |
| `./rag record-session …` | Append an audit-pass record (warm-start history). |

### `./rag query <mode>` — the ~25 read surfaces

`search` · `page` · `object` · `related` · `timeline` · `graph` · `arc` · `method` ·
`stratum` · `concept` · `type` · `locate` · `links` · `drift` · `monitors` ·
`interface` · `coverage` · `contradict` · `deprecated` · `captures` (cross-tier capture
ledger) · `viz` · `brief` · `orient` · `stats`. Full per-mode reference:
[`scripts/rag/README.md`](scripts/rag/README.md) §5.

## The demo program

The underlying problem asks whether a set of positive integers can be *sum-distinct*
(all subset sums differing) while keeping the largest element small: how small can the
largest element of an n-element sum-distinct set be (OEIS A276661)? Erdős conjectured
it grows like c·2^n; the constant-factor question is wide open.

The program is run under `QUEUE.md`, the planner-write-only work queue whose §0.5
pins the four protocols (index-document, working protocol, authority chain, test
strategy). Plans live in `plans/`; results are VRs in `corpus/`; the engine's own
`brief`/`orient`/`monitors` are the operating surfaces (the program dogfoods the tool).

| Ladder | State | Plan / VR |
|---|---|---|
| Exact table a(n), n ≤ 10 | **certified/cross-checked**: a(1..8) re-derived exhaustively here, a(9)=161 gate cleared, a(10)=309 cross-checked | `plans/P1,P2`; VR-3/4/5 |
| a(11), the live frontier | **window [462, 594] stands; exact value beyond single-box compute** (VR-9: floor rung ran 42 min without closing, as expected for an open problem) | `plans/P2`; VR-8/9 |
| a(12), a(13) posted bounds | **certified here** (≤ 1157 / ≤ 2249), CG-optimality refuted at n=12/13 | `plans/P3`; VR-5 |
| Records n ≥ 14 | CG-14..25 certified baseline + first perturbation neighborhood (0 improvements) | `plans/P3`; VR-7 |
| Constant curve a(n)/2^n | done: exact-arithmetic table + SVG, overflow receipts | `plans/P4`; VR-6 |
| Search engine v3 | intra-rung parallelism done (3.3×); MITM analyzed → no win (VR-8); representation-method engine deferred | `plans/P7`; VR-8 |

## Compute arms

The demo's computation lives in `arms/`, each **calibrated against published values
before its output counts** (the non-circularity discipline: a gate never imports the
value it is re-deriving).

| Arm | What it is |
|---|---|
| `verify_set.py` | Sum-distinctness certificate (incremental bitset, overflow-safe; refuses beyond the ~2×10⁹-bit ceiling, which is theorem territory). |
| `conway_guy.py` | Conway–Guy sequence generator + sets; self-asserts 14 published OEIS terms before emitting. |
| `exhaustive.py` | Exact-optimum branch-and-bound (5 conservative prunes P1–P5, DFX theorem floor, per-M ledger; `--engine c` dispatches to the kernel). |
| `feasible.c` | C kernel: exact DFS mirror of `exhaustive.py`, cross-validated by identical per-M node counts; ~19x wall-clock. |
| `gate_parallel.py` | Parallel/rung-independent driver: gate mode (exhaust a window) or walk mode (`--order asc`, raise the lower bound), with `--intra K` (K cores on one rung) and orphan-safe process reaping. |
| `records.py` | Records ladder: CG-n baseline certification + bounded perturbation search. |
| `constants_curve.py` | The empirical c(n)=best/2ⁿ curve vs the DFX and Bohman rails; exact `Fraction` arithmetic, JSON + SVG. |

Design of the (deferred) stronger engine: `docs/SEARCH_ENGINE_V3_DESIGN.md`.

## Corpus tiers (heterogeneous document populations)

A real program is not one document class. Threads, versioned papers/outlines, living
plans, channels, and derived artifacts each carry a *different metamodel* (mutability,
supersession semantics, claim semantics, evidence weight). An optional `tiers.json`
(next to the seeds; **absent ⟹ byte-identical single-tier behavior**) declares them:

First, version-number supersession: versioned tiers get synthesized `superseded` verdicts
from filename patterns, so a stale outline is visible to `orient` with zero authoring
discipline. Second, a capture ledger (`./rag query captures`) tracks `captures THREAD-N
R<k>` edges alongside an unreconciled-rounds report and receipt-laundering candidates
(a VR citing a thread round as if it were a receipt). Third, detector scoping ensures
that a "SETTLED" in an external thread does not fire vr-corpus monitors, so metamodel
misapplication is prevented rather than hand-waved. Fourth, derived-tier exclusion
guarantees that engine outputs and generated wikis are never re-ingested as source,
serving as the generalized self-consumption guard. Finally, cross-party attribution keys
thread values by speaker, making conflation machine-visible.

Design: `docs/CORPUS_TIERS_DESIGN.md`; plan: `plans/P6_corpus_tiers.md`; frozen semantics:
`scripts/rag/tests/fixture_tiered/`.

## LangChain / OpenWiki Brains integration

`adapters/openwiki/` feeds this engine into
[LangChain's OpenWiki](https://github.com/langchain-ai/openwiki) as a brain's
**deterministic half** (OpenWiki is deterministic-fetch-then-LLM-synthesize; this engine
is the deterministic fetch). Three layers, cheapest first:

- **Layer A (sidecar feeder)** (zero OpenWiki changes): `emit_okf.py` renders
  brief/monitors/drift/captures as OKF-compliant wiki pages (validated against OpenWiki's
  *own* front-matter validator, ported verbatim in `okf_validator_port.mjs`);
  `openwiki-update-prestep.yml` is the CI drop-in; `AGENTS.md` + `SKILL.md` carry the
  orientation contract. The generated wiki is registered as a **derived tier** so it is
  never re-ingested.
- **Layer B, read-only stdio MCP server** (`mcp_server.py`): exposes
  `brief`/`orient`/`search`/`page`/`timeline`/`monitors` to any MCP client, matching
  OpenWiki's `McpConnectorConfig`.
- **Layer C, first-class connector**: upstream PR sketch in
  `upstream-generic-mcp-connector.md`.

The demo used this integration (OpenWiki v0.2.0 on MiniMax-M3) to generate a full wiki
with the orientation in place; the agent's docs correctly state
**a(11) OPEN [462,594]** as the live frontier (not a stale synthesis) and picked up both
correction arcs.. The frozen output + writeup is in `adapters/openwiki/capture_example/` (see `CAPTURE.md`). Full design:
`adapters/openwiki/README.md`; plan: `plans/P5_openwiki_brain.md`.

## Porting the engine to another program

The engine/domain split is the point: write `domains/<yours>/` (one `domain_config.json`
vocabulary file + four seed JSONs, optional `tiers.json`) and point `ragconfig.json`
(or the `RAG_CORPUS_DIR` / `RAG_SEED_DIR` / `RAG_DATA_DIR` env vars, which take precedence) at your
corpus. The engine code is untouched. Reference deployments: `domains/erdos1/` (this
demo) and `domains/r14-bsd/` (the mathematics research program this engine grew in;
config only, corpus not included). Corpus contract: `docs/rag_corpus_format.md`; the
shipped fixtures (`scripts/rag/tests/fixture/` single-tier, `fixture_tiered/` tiered) are
its executable form.

## Repository map

Everything maintained, and where it lives:

```
rag                        root CLI wrapper (ragconfig.json → env → dispatch)
ragconfig.json             this deployment's corpus/seed/data dirs
QUEUE.md                   planner-write-only work queue + the four pinned protocols
AGENTS.md                  agent orientation contract (brief-first, orient-before-acting)
LICENSE                    MIT (engine + fixtures)

scripts/rag/               THE ENGINE (domain-agnostic; MIT)
  index_vrs.py             stage 1 — chunks, entities, supersession, arcs, methods, strata
  ontology.py              stage 2 — canonical objects, links, monitors, drift
  coverage.py              stage 3 — self-coverage audit
  synthesize_brief.py      stage 4 — the warm-start brief
  orient.py                plan-scoped orientation artifacts
  query.py                 the ~25 read modes
  grounding_check.py       dangling refs / reproducers / retraction propagation
  tiers.py                 corpus-tier substrate (P6)
  embed.py                 optional ONNX/ChromaDB vector layer
  viz.py                   relationship-graph rendering
  domain_ids.py · record_session.py · doctest_grounding.py   supporting
  README.md · SETUP.md     full engine reference
  tests/                   fixture/ (single-tier) + fixture_tiered/ (P6) + unit suites

domains/erdos1/            demo domain: domain_config.json + 4 seeds + tiers.json
domains/r14-bsd/           reference domain (the origin program; config only)

corpus/                    the demo program's append-only VR/AUDIT corpus (9 VR + 1 AUDIT)
plans/                     P1..P7 execution plans (edit protocol + claims registry each)
arms/                      compute arms (see Compute arms)
results/                   compute artifacts (ledgers, JSON, SVG)
adapters/openwiki/         the OpenWiki integration (3 layers + live capture example)
docs/                      corpus contract + design docs + design history
.github/workflows/         rag-tests.yml (engine + arm + conformance + determinism CI)
data/rag/                  build outputs (gitignored; regenerated by ./rag rebuild)
```

## Testing & CI

- `./rag test`: 56 engine tests, covering unit detector controls and two fixture
  end-to-end runs (single-tier and tiered) with **byte-determinism asserts**.
- `python3 -m unittest discover -s tests`: 9 arm tests, covering golden a(n) values, the
  certificate ceiling guard, OKF-emission determinism, and constants-curve overflow.
- `.github/workflows/rag-tests.yml`: runs the above plus **live-corpus conformance**
  (`./rag rebuild` with 0 errors) and **steady-state byte-determinism** (repeat builds
  hash identical).
- Discipline the demo itself enforces (QUEUE §P4): every arm calibrates against published
  values before its output counts; exact claims name their prunes; a detector's zero is
  evidence, never proof.


## License

Engine + fixtures: MIT (`LICENSE`). The demo corpus documents record facts about a
public mathematical problem with cited sources.
