---
type: Architecture
title: Engine layers — the five conceptual layers + the query CLI
description: "The five conceptual layers of the corpus-orientation engine (entity registry, vector search, grounding/contradiction, ontology, robustness), the runnable scripts that produce each layer's data, and the full query CLI surface (brief, orient, search, page, monitors, graph, arc, method, stratum, deprecated, contradict, drift, coverage, viz)."
tags: [openwiki, architecture, engine, query, cli]
---

# Engine layers

The engine (`scripts/rag/`) is organised as five conceptual layers stacked from raw text
to program-state distillation. Each layer's output is JSON under `data/rag/` (derived,
gitignored, **never** a source per `AGENTS.md`).

## Layer 1 — Extraction: entities, types, quantities, supersession

**Script:** `scripts/rag/index_vrs.py` (run standalone or via `rebuild.sh [1/4]`).
**Outputs:** `chunks.jsonl`, `entity_registry.json`, `type_registry.json`,
`type_violations.json`, `supersession.json`, `claim_status.json`, `arcs.json`,
`method_registry.json`, `concepts.json`, `file_meta.json`, `index_stats.json`.

Key design points:

- **Section-chunking** at `## ` headings (per `docs/rag_corpus_format.md` §3).
- **Entity families** declared in `domains/<x>/domain_config.json` (`entity_families`)
  — every captured token has a template, e.g. `a(n)=v`, `u(n)`, `CG-n`, `arms/foo.py`,
  `plans/foo.md`, `results/foo.json`.
- **Declared type + validator**: each entity carries a `type`; a *loose* `match` assigns
  it, a *tight* `valid` pattern checks well-formedness. Typed-but-invalid keys →
  `type_violations.json` (extraction suspects).
- **Supersession graph**: **reference-class** (`references`, `script_ref`,
  `corroborates`, `closes`) scanned in full text; **correction-class**
  (`corrects`/`refutes`/`retracts`/`supersedes`/`corrected_by`/…) scanned in
  **metadata only** (avoids body-prose false edges).
- **Arcs**: connected correction components + entity-overlap, classified
  `converged` / `oscillating` / `stalled` / `exploring` / `diagnosed`, with error
  density + correction latency.
- **Method registry**: methods/instruments as lifecycle objects
  (`proposed → implemented → calibrated → validated → failed → diagnosed → rebuilt`),
  with `has_produced_wrong_answer`.
- **Claim status (VR-level)**: primary commitment from the `[V]/[P]/[C]/[O]` status
  marker + body signals (`FINALIZED`/`TENTATIVE`/`SUPERSEDED`/`DEAD`). A VR can be
  `[V]`-primary + DEAD-signal (verified then refuted).
- **Claim strata (per-claim)**: epistemic level of each assertion within a VR
  (`proved`/`verified`/`predicted`/`open`/`retracted`); powers `query.py stratum`.
- **Concept emergence**: multi-word terms with introduction point + propagation +
  continuity.

## Layer 2 — Vector search (optional)

**Script:** `scripts/rag/embed.py` (`--embed` flag; off by default; needs `chromadb` +
`onnxruntime` + `tokenizers` + ~90MB ONNX model download on first run).
**Outputs:** `chroma_db/`, `model/` (gitignored).

When built, `query.py search` uses semantic vectors; without it, search falls back to
TF-IDF (authority-weighted when `tiers.json` declares heterogeneous populations). The
engine's headline surfaces (`brief`, `orient`, `monitors`) do **not** depend on vectors.

## Layer 3 — Grounding + contradiction

**Script:** `scripts/rag/grounding_check.py`. **Output:** `grounding_report.json` (printed
in summary; not part of the deterministic rebuild pipeline).

Checks: cited reproducer exists, `/tmp`-reproducer flag, dangling file refs, retraction
propagation. In tiered deployments, `papers/` outline-version checks apply when that tier
is declared.

## Layer 4 — Ontology layer

**Script:** `scripts/rag/ontology.py` (run via `rebuild.sh [2/4]`).
**Inputs:** the five seed JSONs in `domains/<x>/` + the indexer outputs.
**Outputs:** `objects.json`, `domain_links.json`, `object_drift.json`, `monitors.json`.

Design points:

- **Canonical object** — a real domain object (curve/field/group/…) with a stable id and
  alias list. `normalize_token` folds subscripts/ASCII/tilde spellings,
  **tilde-preserving** so `K₁` ≠ `K̃₁`.
- **(curve, field)-bound property** — rank/|Sha|/digits live on a **pair id**
  `curve@field` (the same curve has different rank over different fields); conductor /
  CM / root-number on the curve, degree / Galois-group on the field. Each fact carries
  value + VR + stratum.
- **Domain link** — typed object↔object edge (`defined_over`, `has_galois_group`,
  `twist_of`, …), **supersession-aware** (tagged `superseded` if its source VR is a
  correction loser).
- **Interface** — shared contract an object satisfies: `Citable`, `Provenanced`,
  `Statused`, `Computed`, `Twistable`, `Extension`.
- **Object monitor** — a declared watch condition evaluated each build. Detector types:
  `text_present` (+optional `also_absent`), `text_absent` (`patterns` list),
  `json_field` (missing witness = `error`, not a pass), `json_count`, `claim_pending`,
  `settled_independent_route`,
  **`forbidden_predicate`** (claim-level: a wrong predicate on a correctly-spelled,
  correctly-seeded object — candidate-emitting, never a verdict),
  **`completeness_claim`** (flags narrow `corpus-clean`/`grep-clean`/`mislabel-clean`
  overclaims). The latter two are the **concept-coverage** layer — claim-coverage, not
  token-coverage; design in `docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX.md`.
- **Drift** — the indexer *validating the seed*: high-precision, windowed, word-boundary
  — only **flags** when a single alternative value dominates ≥3 distinct VRs; otherwise
  reports `confirmed` / `unconfirmed` / `unverified` / `no_detector`. Refuses to cry wolf.

## Layer 5 — Robustness: coverage + determinism + self-consumption

- **`coverage.py`** (`rebuild.sh [3/4]`): the **self-coverage audit** — uncaptured
  recurring tokens, unknown relation verbs near VR-refs, unseeded object-shaped
  entities, alias drift. Turns silent degradation into a visible report.
- **Determinism invariant**: every `generated` stamp is derived from the corpus (max doc
  date + doc count), never the wall clock. Tested by
  `tests/determinism_check.sh` and `.github/workflows/rag-tests.yml`.
- **Self-consumption guard**: a chunk that names a monitor's id is quoting/discussing its
  definition, not asserting the watched predicate, and is excluded from that monitor's
  candidates. Applied to every corpus-scanning detector
  (`settled_independent_route`, `forbidden_predicate`, `completeness_claim`);
  regression-tested.
- **Semantic reconciliation** (`/ontology-reconcile`): an LLM reads the coverage gaps
  *by meaning* and proposes `domain_config.json`/seed updates, validated vs
  `CLAUDE.md`, **gated, not auto-applied**.

## The query CLI — `scripts/rag/query.py <mode> [arg] [--flagged]`

Modes marked **no-arg** run without an argument. Only `type` takes `--flagged`.

| Mode | Invocation | What it returns |
|---|---|---|
| `search` | `query.py search "epsilon convergence k=3"` | semantic (ChromaDB) or TF-IDF top chunks; retracted/deprecated down-weighted |
| `object` | `query.py object eps_k3` | entity record: type, value-history, mention timeline (substring match) |
| `related` | `query.py related VR-534` | VRs sharing entities + supersession neighbours |
| `timeline` | `query.py timeline sha` | value/concept evolution of an entity across VRs |
| `graph` | `query.py graph VR-550` | supersession edges in/out of a VR, each annotated with its W3C-PROV interop term |
| `arc` | `query.py arc VR-812` | the research arc containing VR-N: members, state, error density, correction edges |
| `method` | `query.py method descent_engine` | a method's lifecycle (states, defining VRs, has-produced-wrong-answer) |
| `stratum` | `query.py stratum "Sha E^161"` | per-VR epistemic-stratum timeline of a claim |
| `concept` | `query.py concept "uniform false-zero"` | concept introduction point, propagation, continuity |
| `type` | `query.py type field` · `query.py type group --flagged` | entities of a declared type; `--flagged` = validator suspects only |
| `page` | `query.py page E^161` | **consolidated object record**: type, aliases, interfaces, properties, per-(curve,field) pair facts, links, claims, mention stats, drift flags |
| `locate` | `query.py locate E^161` | concept-LOCATE: every chunk mentioning any boundary-matched alias of the object — regions to READ, no verdict |
| `links` | `query.py links K_A4` · `query.py links twist_of` | domain links for an object, or all links of a relation |
| `drift` | `query.py drift` | seed↔corpus property-drift report |
| `monitor`/`monitors` | `query.py monitors` | declared object monitors + evaluated state (unmet first) |
| `interface` | `query.py interface Twistable` | objects implementing an interface |
| `coverage` | `query.py coverage` | self-coverage audit |
| `viz` | `query.py viz links` · `query.py viz graph VR-558` · `query.py viz arc VR-812` | render a relationship graph (Mermaid / DOT / HTML d3 / PNG / SVG / terminal) |
| `contradict` | `query.py contradict VR-408` | contradiction check: claim status, refutation edges, entity value-changes, retracted refs |
| `deprecated` | `query.py deprecated` | all retracted/deprecated VRs |
| `brief` | `query.py brief` | **warm-start audit brief**: regenerates + prints `data/rag/audit_brief.md` — active arcs, distrusted methods, unmet monitors, drift, changed-since-last-pass. **The first thing to read in a session.** |
| `orient` | `query.py orient Plans/my_plan.md MESSAGE.md VR-1049` | **execution-context orientation**: where the *given* documents stand in the state machine — cited-doc correction status, touched-object facts, stale-assertion candidates, method reliability, in-scope monitors, arcs |
| `stats` | `query.py stats` | `index_stats.json` (counts) |

`./rag` is a bash wrapper that resolves `ragconfig.json` (or the `RAG_*` env vars) and
dispatches to these scripts; `./rag brief` is an alias for `query.py brief`;
`./rag orient` runs `orient.py` directly.

## Operational references

- **Engine operational reference**: `scripts/rag/README.md` (install, full pipeline,
  every runnable script, every mode with --flags, concept glossary, data files, the
  `domain_config.json` porting schema).
- **Domain-config porting schema**: `scripts/rag/README.md` §8.
- **Concept-coverage design history**: `docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX.md`,
  `docs/ontology_rag_assessment.md`.
- **Document contract**: `docs/rag_corpus_format.md`.
