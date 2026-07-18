---
type: Operations
title: Port the engine to your corpus — the engine ↔ domain split
description: "How to port the corpus-orientation engine to a different corpus by swapping domains/<x>/{domain_config, *seed, tiers}.json and pointing the RAG_CORPUS_DIR / RAG_SEED_DIR / RAG_DATA_DIR env vars at your corpus. The engine code is untouched. Reference deployments: domains/erdos1/ (this demo) and domains/r14-bsd/ (the engine's origin math program; corpus not included)."
tags: [openwiki, operations, port, deployment, env-vars, domain-config, seeds]
---

# Port the engine to your corpus

The engine↔domain split is the point. Everything structural (chunking, supersession,
arcs, claim status, monitors, drift, coverage, orient) is engine code under `scripts/rag/`.
The vocabulary is `domain_config.json` + the four seeds + (optionally) `tiers.json` in
`domains/<yours>/`. To port the engine to a new corpus:

1. Swap `domains/<yours>/` with your five JSON files.
2. Point the env vars at your corpus / seeds / data directory.
3. Re-run `./rag rebuild`. The engine code is **untouched**.

The full operational reference is `scripts/rag/README.md` (install, build pipeline,
every runnable script, query CLI, concept glossary, data files, the
`domain_config.json` porting schema). This page is the porting playbook.

## The three env vars (or `ragconfig.json`)

The engine reads three directory locations, in this order of precedence:

```bash
RAG_CORPUS_DIR=/path/to/your/corpus
RAG_SEED_DIR=/path/to/your/seeds         # contains domain_config.json + the seeds
RAG_DATA_DIR=/path/to/your/build/output  # gitignored by convention
```

Env vars already set in the caller's environment take precedence over `ragconfig.json`
— the config file only fills in what is unset, so one-off overrides keep working:

```bash
RAG_CORPUS_DIR=scripts/rag/tests/fixture/corpus ./rag rebuild
```

The `./rag` bash wrapper resolves the locations from `ragconfig.json` (or the env
vars) and exports them for the engine scripts. Use `RAG_*` for tests and one-off
overrides; commit a `ragconfig.json` for the default deployment.

## What's in `domains/<yours>/`

The minimal port is one JSON file. The reference port is six.

| File | Required? | What it contains |
|---|---|---|
| `domain_config.json` | **yes** | doc-id scheme (`doc_id.primary` / `doc_id.audit`), entity-family patterns, supersession patterns (split into correction- vs reference-class), quantity patterns, type schema (with `match` + `valid`), drift value patterns, method indicators + lifecycle states |
| `canonical_objects.json` | optional but recommended | the hand-curated objects the engine should treat as authoritative facts (with `aliases`, `note`, `dropped` flag) |
| `object_properties_seed.json` | optional but recommended | per-object property bindings (subject / prop / value / vr_id / stratum / source) — the indexer *validates* these against the corpus (drift detection) |
| `domain_links_seed.json` | optional but recommended | typed object↔object links (`source`, `relation`, `target`, `vr_id`) |
| `monitors_seed.json` | optional | declared monitors with detector type + args (the `domains/erdos1/` instance has six; see below) |
| `tiers.json` | optional | heterogeneous population declaration; absent ⟹ byte-identical single-tier behavior (compatibility invariant) |

### The schema in one sentence

The contract is fully documented in `scripts/rag/README.md` §8. In one sentence:
`domain_config.json` declares how to recognise your entities, what counts as a correction
edge vs a reference, how to type and validate each entity, how to detect drift in your
seed values, and how to classify your methods' lifecycle states. The four seeds
provide the **authoritative facts** the indexer validates and the **typed links** /
**monitors** that close the gap from raw extraction to program-state estimation.

## Example — `domains/erdos1/` (this repo's demo)

- `domain_config.json` (~95 lines): doc-id `VR`/`AUDIT`; entity families for `VR-N`,
  `AUDIT-N`, `a(n)=v`, `u(n)`, `A\d{6}`, `CG-n`, `binom(…)`, `arms/<x>.py`,
  `plans/<x>.md`, `results/<x>.{json,log,txt}`, `§N`; 20 supersession patterns split
  correction vs reference; quantity `a_exact` and `nodes`; 11-entry type schema;
  drift-value patterns for `=`, `<=`, `>=`; 5 method indicators
  (`exhaustive_bnb`, `cg_generator`, `bitset_certificate`, `ilp_sat`, `local_search`)
  with 6 lifecycle states.
- `canonical_objects.json` (12 objects): the Erdős problem #1, A276661, A005318,
  `cg_family`, a(8)/a(9)/a(10)/a(11)/a(12)/a(13), `dfx_bound`, `bohman_bound`.
- `object_properties_seed.json` (15 properties): each bound carries `vr_id` +
  `stratum` + `source`.
- `domain_links_seed.json` (6 links): the A276661/A005318/cg_family/dfx_bound/bohman_bound
  graph.
- `monitors_seed.json` (6 monitors):
  - `settled_needs_independent_route` (`MEDIUM` · `settled_independent_route`)
  - `cg_optimality_forbidden` (`LOW` · `forbidden_predicate`)
  - `frontier_exact_claim_needs_exhaustion` (`MEDIUM` · `forbidden_predicate`)
  - `record_claim_inflation` (`LOW` · `forbidden_predicate`)
  - `corpus_completeness_overclaim` (`LOW` · `completeness_claim`)
  - `n11_frontier_open` (`LOW` · `claim_pending`)
- `tiers.json` (4 tiers): `vr` (corpus/), `plans` (plans/), `channels`
  (`QUEUE.md`, `README.md`), `derived` (`data/rag`, `wiki/corpus-orienteer`).

## Example — `domains/r14-bsd/` (the engine's origin)

The original mathematics research program this engine grew in (`r14-bsd` is the
legacy project name; the BSD conjecture). **Config only — the corpus is not in this
repo.** The seeds are much larger (the canonical-objects file is ~20KB, the property
seed ~28KB) — a heavier reference deployment. See the directory listing in
[Source map](../source-map.md).

## Porting checklist

1. **Write your corpus contract first.** Adapt `docs/rag_corpus_format.md` to your
   document class names + header fields (the engine handles `VR`/`AUDIT` by default;
   any other scheme is one config change).
2. **Pick your entity families.** What's a "thing" in your corpus? (curves, fields,
   theorems, scripts, parameters, files, modules — pick the families you want the
   engine to surface in `query.py object` / `query.py page`).
3. **Pick your supersession verbs.** What counts as a correction? A retraction? A
   reference? Fill in `supersession_patterns` and split them via `correction_relations`
   vs `reference_relations`.
4. **Pick your monitor set.** What are the standing invariants? Each monitor is a
   detector type + patterns + (where applicable) a `contradicts` seed fact. Start
   small; the engine's reporting surfaces scale.
5. **Write your seeds.** Hand-curate a small initial `canonical_objects.json` (one
   entry per "thing" the program should track), then add `object_properties_seed.json`
   entries for the values you want drift detection on.
6. **Run the engine.** `./rag rebuild`; check `./rag monitors`; check `./rag query stats`;
   check `./rag brief`.
7. **Validate end-to-end against the fixture.** `scripts/rag/tests/fixture/` is a
   self-contained fictional comet survey that exercises every feature; the engine
   suite passes against it (`./rag test`). If your port behaves the same way against
   the fixture, you have the contract right.

## What stays the same (the engine invariants)

- **Byte-determinism**: same corpus + same seeds ⟹ same `data/rag/` outputs.
- **Candidate, never verdict**: every new detector emits regions to READ.
- **Append-only**: conclusions change via new docs, never edits (the engine will
  surface unacknowledged corrections if you violate this).
- **Seeds authoritative**: the indexer *validates* your seeds against the corpus; it
  never extracts headline facts from prose.

## Two known deployment heuristics remain in engine code

`scripts/rag/README.md` §2.1 flags these explicitly so they don't surprise you:

1. `grounding_check.py`'s paper-outline checks (skip when `papers/` is absent).
2. Its `/tmp`-reproducer classification.

Both no-op on deployments without `papers/` or `/tmp` reproducers.

## Reference deployments

| Deployment | Domain | Use |
|---|---|---|
| `domains/erdos1/` | Erdős distinct subset sums | The demo in this repo; corpus present |
| `domains/r14-bsd/` | BSD conjecture (original program) | Reference configuration only; corpus not in this repo |
| `scripts/rag/tests/fixture/` | fictional comet survey | The fixture = the document contract's executable form |
| `scripts/rag/tests/fixture_tiered/` | comet survey + thread + versioned outline + archive + derived artifact | Tiered deployment freeze (P6 M5.2, 8 e2e asserts incl. byte-determinism) |
