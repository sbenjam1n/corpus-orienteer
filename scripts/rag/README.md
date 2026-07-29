# RAG + Ontology + Audit Toolchain

Longitudinal, corpus-wide retrieval, structured-ontology, and self-audit layer over the
`verification_ready/` VR/AUDIT corpus. Five conceptual layers (entity registry → vector
search → grounding/contradiction → ontology objects → robustness), a stdlib-only core, an
optional ONNX/ChromaDB semantic-search layer, and a clean **engine ↔ domain-config split**
so the engine ports to any corpus by swapping `domain_config.json` + the ontology seeds.

The engine is **MIT-licensed** ([`LICENSE`](LICENSE); it travels with `scripts/rag/` on
extraction and covers the engine + fixture, not the research corpus).

This file is the complete operational reference. Design rationale lives in
[`docs/ontology_rag_assessment.md`](../../docs/ontology_rag_assessment.md).
The **concept-coverage upgrade roadmap** (token-coverage → claim-coverage) + the
borrow-from-analogues matrix lives in
[`docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX.md`](../../docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX.md).

---

## 1. Install

```bash
pip3 install --user chromadb tokenizers onnxruntime numpy   # ONLY for semantic search
```

The core (indexer, ontology, coverage, grounding, query, TF-IDF search) is **stdlib-only**.
ChromaDB/ONNX are optional; without them, `search` falls back to TF-IDF.

## 2. Quick start

```bash
bash scripts/rag/rebuild.sh --embed        # first run: downloads ~90MB ONNX model, full build (~60s)
bash scripts/rag/rebuild.sh                 # subsequent: index → ontology → coverage, no embed (~5–10s)
python3 scripts/rag/query.py page E^161     # try it
```

All commands are run from the repo root, and outputs land in `data/rag/` (gitignored).

### 2.1 Try the engine in 60 seconds (no corpus needed)

The engine ships with a self-contained fixture corpus (a fictional comet survey,
`tests/fixture/`) that exercises every feature. Run the whole pipeline against it:

```bash
export RAG_CORPUS_DIR=scripts/rag/tests/fixture/corpus \
       RAG_SEED_DIR=scripts/rag/tests/fixture/seeds \
       RAG_DATA_DIR=/tmp/rag_fixture
for s in index_vrs ontology coverage grounding_check synthesize_brief; do python3 scripts/rag/$s.py; done
python3 scripts/rag/query.py monitors                       # 3 live candidates
python3 scripts/rag/orient.py scripts/rag/tests/fixture/plan_stale.md   # catches the stale period
unset RAG_CORPUS_DIR RAG_SEED_DIR RAG_DATA_DIR
```

The same three env vars are the **porting mechanism**: point them at any corpus that
meets the document contract in [`docs/rag_corpus_format.md`](../../docs/rag_corpus_format.md)
(the fixture is that contract's executable form). `python3 -m unittest discover -s
scripts/rag/tests` runs the engine's full test suite: unit controls plus the fixture
end-to-end with a byte-determinism assert (also run by CI, `.github/workflows/rag-tests.yml`).

**Engine vs deployment.** Everything structural (chunking, supersession, arcs, claim
status, monitors, drift, coverage, orient) is the engine; the r14-specific layer is
`domain_config.json` + the four seeds + the monitor examples in this README. Two known
deployment heuristics remain in engine code and no-op elsewhere: `grounding_check.py`'s
paper-outline checks (skip when `papers/` is absent) and its `/tmp`-reproducer
classification.

## 3. The build pipeline (`rebuild.sh`)

```
bash scripts/rag/rebuild.sh [--embed]
```

Four core stages (stdlib-only, fast); two optional flag-gated extras (`--embed`, `--doctest`, order-independent):

| Stage | Script | Produces |
|---|---|---|
| `[1/4]` index | `index_vrs.py` | chunks, entity_registry, type_registry, type_violations, supersession, file_meta, claim_status, arcs, method_registry, concepts, index_stats |
| `[2/4]` ontology | `ontology.py` | objects, domain_links, object_drift, monitors |
| `[3/4]` coverage | `coverage.py` | coverage_report |
| `[4/4]` brief | `synthesize_brief.py` | audit_brief.md (warm-start digest), rolls file_meta_prev snapshot |
| _(optional)_ embed | `embed.py` (`--embed`, ~60s) | chroma_db, model |
| _(optional)_ doctest | `doctest_grounding.py --json` (`--doctest`, needs gp; heavy) | doctest_results.json |

## 4. Runnable scripts

Each runs standalone (from repo root) as well as via `rebuild.sh`. **Engine** scripts are
domain-agnostic; the **domain** is `domain_config.json` + the seeds (§8).

| Script | Run standalone | Reads | Writes |
|---|---|---|---|
| `index_vrs.py` | `python3 scripts/rag/index_vrs.py` | `verification_ready/*.md`, `domain_config.json` | chunks, entity/type registries, supersession, arcs, methods, concepts, claim_status |
| `ontology.py` | `python3 scripts/rag/ontology.py` | the seeds + index outputs | objects, domain_links, object_drift, monitors |
| `coverage.py` | `python3 scripts/rag/coverage.py` | corpus + config + seeds + entity_registry | coverage_report |
| `grounding_check.py` | `python3 scripts/rag/grounding_check.py` | file_meta, supersession, VR headers | grounding_report (+ prints `Total findings: N`) |
| `embed.py` | `python3 scripts/rag/embed.py` | chunks.jsonl | chroma_db, model |
| `query.py` | `python3 scripts/rag/query.py <mode> [arg] [--flags]` | data/rag/* | stdout (read-only) |
| `viz.py` | `python3 scripts/rag/viz.py <links\|graph\|arc> [VR-N]` | objects, domain_links, supersession, arcs | `data/rag/viz/*.{mmd,dot,svg,png}` |
| `reconcile_workflow.js` | via the Workflow tool, `{scriptPath: "scripts/rag/reconcile_workflow.js"}` | coverage_report + corpus | a gated proposal (stdout) |
| `synthesize_brief.py` | `python3 scripts/rag/synthesize_brief.py` | arcs, method_registry, monitors, object_drift, file_meta(+prev) | `data/rag/audit_brief.md` (deterministic warm-start digest) |
| `orient.py` | `python3 scripts/rag/orient.py <plan.md \| VR-N> […] [--out slug]` | the given docs + file_meta, claim_status, supersession, arcs, objects, method_registry, monitors | `data/rag/orient_<slug>.md` (plan-scoped orientation artifact) |
| `clusters.py` | `python3 scripts/rag/clusters.py <scope docs/ids…> --out <slug> [--seed-scope name] [--dirs …] [--top N]` | scope docs + concepts, objects, file_meta, chunks; `cluster_seed.json` (seed) + domain_config `sweep_dirs` | `data/rag/clusters_<slug>.json` (pinned sweep plan) + `sweep_<slug>.md` (per-term literal/adjacency table — deterministic steps 2–3 of a scope orientation) |
| `rebuild.sh` | `bash scripts/rag/rebuild.sh [--embed]` | — | orchestrates the five stages; prints a per-stage timing breakdown |
| `tests/test_rag_engine.py` | `python3 -m unittest discover -s scripts/rag/tests` | — | per-stage regression tests (synthetic fixtures; detector controls frozen as tests) |
| `tests/determinism_check.sh` | `bash scripts/rag/tests/determinism_check.sh` | — | rebuilds twice; requires byte-identical `data/rag/` outputs + clean `git status` |

## 5. Query CLI — complete reference

```
python3 scripts/rag/query.py <mode> [argument] [--flagged]
```

Modes marked **no-arg** run without an argument; only `type` takes `--flagged`.

| Mode | Invocation | Returns |
|---|---|---|
| `search` | `query.py search "epsilon convergence k=3"` | semantic (ChromaDB) or TF-IDF top chunks; retracted/deprecated down-weighted |
| `object` | `query.py object eps_k3` | entity record: type, value-history, mention timeline (substring match) |
| `related` | `query.py related VR-534` | VRs sharing entities + supersession neighbours |
| `timeline` | `query.py timeline sha` | value/concept evolution of an entity across VRs |
| `graph` | `query.py graph VR-550` | supersession edges in/out of a VR, each annotated with its W3C-PROV interop term (`≈` = local verb is richer than PROV) |
| `arc` | `query.py arc VR-812` | the research arc containing VR-N: members, state, error density, correction edges |
| `method` | `query.py method descent_engine` | a method's lifecycle (states, defining VRs, has-produced-wrong-answer) |
| `stratum` | `query.py stratum "Sha E^161"` | per-VR epistemic-stratum timeline of a claim (proved/verified/predicted/open/retracted) |
| `concept` | `query.py concept "uniform false-zero"` | concept introduction point, propagation, continuity |
| `type` | `query.py type field` · `query.py type group --flagged` | entities of a declared type; `--flagged` = validator suspects only |
| `type` **no-arg** | `query.py type` | type summary (counts + flagged per type) |
| `page` | `query.py page E^161` | **consolidated object record**: type, aliases, interfaces, properties, per-(curve,field) pair facts, links, claims, mention stats, drift flags |
| `locate` | `query.py locate E^161` | **concept-LOCATE** (grep-to-LOCATE / read-to-CERTIFY): every chunk mentioning any boundary-matched alias of the object, providing regions to READ, makes **no** predicate verdict. On-demand (~0.4s), not a build precompute |
| `links` | `query.py links K_A4` · `query.py links twist_of` | domain links for an object, or all links of a relation |
| `drift` **no-arg** | `query.py drift` | seed↔corpus property-drift report (high-precision flags + coverage counts) |
| `monitor`/`monitors` **no-arg** | `query.py monitors` | declared object monitors + evaluated state (unmet first) |
| `interface` | `query.py interface Twistable` | objects implementing an interface |
| `coverage` **no-arg** | `query.py coverage` | self-coverage audit: uncaptured tokens/relations, unseeded objects, alias drift |
| `viz` **no-arg→links** | `query.py viz links` · `query.py viz graph VR-558` · `query.py viz arc VR-812` | render a graph (see §5.1); writes to `data/rag/viz/` |
| `contradict` | `query.py contradict VR-408` | contradiction check: claim status, refutation edges, entity value-changes, retracted refs |
| `deprecated` **no-arg** | `query.py deprecated` | all retracted/deprecated VRs |
| `brief` **no-arg** | `query.py brief` | **warm-start audit brief**: regenerates + prints `data/rag/audit_brief.md`: active arcs, distrusted methods (failed-state + wrong-answer, with reliability rollup), unmet monitors, drift, changed-since-last-pass, hot-arc monitor candidates. Deterministic distillation, no new claims |
| `orient` | `query.py orient Plans/plan.md MESSAGE.md VR-1049` | **execution-context orientation** (§5.2): where the *given* documents stand in the state machine: cited-doc correction status, touched-object facts, stale-assertion candidates, method reliability, in-scope monitors, arcs |
| `stats` **no-arg** | `query.py stats` | `index_stats.json` (counts) |

Flags elsewhere: `rebuild.sh --embed` (rebuild vectors); `viz … --png`/`--svg`/`--dot`. The
`/rag` skill also exposes `grounding` (runs `grounding_check.py`), `doctest` (runs
`doctest_grounding.py`, opt-in, re-runs curated reproducers; see §6 grounding), and
`rebuild [--embed]`.

### 5.1 Visualization (`viz`)

Renders the relationship graphs that already exist as edge lists. Three targets:
`links` (the domain-object graph, showing canonical objects + typed links: twist_of / defined_over /
has_galois_group / …), `graph VR-N` (the supersession neighbourhood of a VR, with correction edges
bold, reference edges plain, superseded edges dashed), `arc VR-N` (the correction graph of a
VR's arc). Nodes are coloured/shaped by type; the focus node is highlighted.

Output formats:
- **Mermaid** (default): **printed to the terminal** (and written to `.mmd`); renders
  natively in **GitHub markdown** and at mermaid.live, pure text, zero install. Read/copy/
  paste it anywhere.
- **Terminal diagram** (`--text` Unicode boxes/arrows, `--ascii` ASCII-only): drawn in the
  terminal via the `mmdflux` CLI if present (`brew install mmdflux` / cargo). Best for
  neighbourhoods and arcs; the full `links` graph is wide, so use `--png` for that.
- **Interactive HTML** (`--html`): a self-contained d3 force-directed graph: drag nodes,
  zoom/pan, hover tooltips, type legend, and a per-relation filter. Best for the dense full
  `links` graph (too big for static/terminal). Open the written `.html` in a browser (d3 loads
  from CDN). `query.py viz links --html` → `data/rag/viz/domain_links.html`.
- **Graphviz DOT** (`--dot`): printed to the terminal (and written to `.dot`).
- **PNG / SVG** (`--png` / `--svg`): rendered via the mermaid CLI `mmdc` *if* a headless Chrome
  is available. One-time setup: `npm i -g @mermaid-js/mermaid-cli && npx puppeteer browsers
  install chrome-headless-shell` (viz.py auto-detects it + applies `--no-sandbox`). Without it,
  the `.mmd`/`.dot` is still written.

```bash
python3 scripts/rag/query.py viz links --html        # interactive d3 graph (open in browser)
python3 scripts/rag/query.py viz graph VR-819 --text # terminal diagram (mmdflux)
python3 scripts/rag/query.py viz links --png         # the ontology, as an image
python3 scripts/rag/query.py viz graph VR-631        # Mermaid you can paste into a VR/AUDIT
python3 scripts/rag/query.py viz arc VR-812 --svg    # an arc's correction graph
```

### 5.2 Execution-context orientation (`orient`)

The plan-scoped sibling of `brief`. `brief` digests the WHOLE program; `orient` takes the
specific documents you are about to hand an execution agent (an execution plan, the
planning message, VR/AUDIT ids, any mix) and compiles ONE markdown artifact answering:
*where does everything these documents touch currently stand in the state machine?*

```bash
python3 scripts/rag/orient.py Plans/my_plan.md MESSAGE.md VR-1049 [--out my_slug]
python3 scripts/rag/query.py orient <same args>        # via the dispatcher
# → data/rag/orient_<slug>.md (also printed)
```

Six sections, all distilled from the existing graph layers (no LLM, no new extraction,
deterministic, byte-identical across runs on the same build):

1. **Cited documents:** every VR/AUDIT the inputs reference: classified status, and every
   correction edge in which it is the **loser**, with the winning doc to READ instead;
   dangling refs listed.
2. **Objects touched:** canonical objects boundary-matched in the inputs, with current
   seeded facts (value + stratum + VR) incl. per-(curve,field) pairs.
3. **Assertion check:** numeric values the inputs assert near an object alias vs the
   seeded facts. A mismatch (e.g. a plan still assuming `|Sha(E^161)|=64`) is a
   **stale-assumption candidate to READ, never a verdict**. Attribution is
   nearest-alias-only (precision over recall).
4. **Methods referenced:** lifecycle state + reliability rollup + wrong-answer history.
5. **Unmet monitors** overlapping the scope's objects/docs.
6. **Correction arcs** containing the cited documents.

Give the artifact to the execution agent alongside the plan (or read it as the auditor
before dispatch): it is the "you are here" map of the decision process. A doc absent from
§1's ⚠ list is not thereby certified; a detector's 0 is not a proof.

## 6. Concepts

**Extraction layer**
- **Entity / entity registry:** named tokens (curves, fields, groups, theorems, params,
  scripts, Lean modules) with mention timelines + value-history; `entity_registry.json`.
- **Declared type + validator:** each entity carries a `type`; a *loose* `match` pattern
  assigns it, a *tight* `valid` pattern checks well-formedness. Typed-but-invalid keys →
  `type_violations.json` (extraction suspects like `G_`, `K_`, `688a923`).
- **Quantities:** tracked numeric value-histories on bare-name buckets (`rank`, `sha`,
  `eps_k`, `val2`) with plausibility bounds.
- **Supersession graph:** directed typed edges. **Reference-class** (benign: `references`,
  `script_ref`, `corroborates`, `closes`) scanned in full text; **correction-class**
  (`corrects`/`refutes`/`retracts`/`supersedes`/`downgrades`/`corrected_by`/…) scanned in
  metadata only (avoids body-prose false edges). The *loser* end is target for verb
  relations, source for self-applied bracket tags.
- **Arcs:** connected correction components + entity-overlap, classified
  converged/oscillating/stalled/exploring/diagnosed, with error density + correction latency.
- **Method registry:** methods/instruments as lifecycle objects
  (proposed→…→validated→failed→diagnosed→rebuilt), `has_produced_wrong_answer`.
- **Claim status (VR-level):** primary commitment from the status line (`[V]`→VERIFIED,
  `[P]`→PROVED, `[C]`→CONJECTURED, `[O]`→OPEN) plus body signals (FINALIZED / TENTATIVE /
  SUPERSEDED / DEAD); a VR can be VERIFIED-primary + DEAD-signal (verified then refuted). The
  classifier distinguishes "this VR IS retracted" from "this VR retracts something else".
- **Claim strata (per-claim):** epistemic level of each assertion within a VR
  (proved/verified/predicted/open/retracted); powers `query.py stratum`.
- **Concept emergence:** multi-word terms with introduction point + propagation + continuity.

**Ontology layer**
- **Canonical object:** a real domain object (curve/field/group/…) with a stable id and an
  alias list. `normalize_token` folds subscripts/ASCII/tilde spellings, **tilde-preserving**
  so `K₁` ≠ `K̃₁`.
- **(curve,field)-bound property:** rank/|Sha|/digits live on a **pair id** `curve@field`
  (the same curve has different rank over different fields); conductor/CM/root-number on the
  curve, degree/Galois-group on the field. Each fact carries value + VR + stratum.
- **Domain link:** typed object↔object edge (`defined_over`, `has_galois_group`, `twist_of`,
  …), **supersession-aware** (tagged `superseded` if its source VR is a correction loser).
- **Interface:** shared contract an object satisfies: `Citable`, `Provenanced`, `Statused`,
  `Computed`, `Twistable`, `Extension`.
- **Object monitor:** a declared watch condition evaluated each build. Detector types:
  `text_present` (+optional `also_absent`), `text_absent` (`patterns` list), `json_field`
  (`field`/`unmet_if`; missing witness = `error`, not a pass), `json_count` (`field`/`max`),
  `claim_pending` (`entity`), `settled_independent_route` (flags SETTLED without an
  independent-route citation), **`forbidden_predicate`** (CLAIM-level: a wrong predicate on a
  correctly-spelled, correctly-seeded object (e.g. "stem_k = the splitting field"); scans chunks
  **and** `scan_files` canonical docs, catches any stem level seeded or not, each candidate
  carries the matched span + the contradicted seed fact; **candidate-emitting, never a verdict**),
  **`completeness_claim`** (flags narrow `corpus-clean`/`grep-clean`/`mislabel-clean` overclaims to
  label at their grounding). The latter two are the **concept-coverage** layer (claim-coverage,
  not token-coverage); design in `docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX.md`.
- **Drift:** the indexer *validating the seed*: high-precision, windowed, word-boundary,
  only **flags** when a single alternative value dominates ≥3 distinct VRs; otherwise reports
  `confirmed` / `unconfirmed` / `unverified` / `no_detector`. Refuses to cry wolf.

**Robustness layer**
- **Self-coverage audit:** corpus content the structured layers miss: uncaptured recurring
  tokens, unknown relation verbs near VR-refs, unseeded object-shaped entities, alias drift.
  Turns silent degradation into a visible report.
- **Determinism invariant:** every `generated` stamp is derived from the corpus (max doc
  date + doc count), never the wall clock, so rebuilding the same corpus twice produces
  byte-identical `data/rag/` outputs and a clean `git status`. Tested by
  `tests/determinism_check.sh`.
- **Self-consumption guard:** a chunk that names a monitor's id is quoting/discussing its
  definition, not asserting the watched predicate, and is excluded from that monitor's
  candidates (the "linter counts its own generated sections" bug class). Applied to every
  corpus-scanning detector (`settled_independent_route`, `forbidden_predicate`,
  `completeness_claim`); regression-tested in `tests/test_rag_engine.py`.
- **Semantic reconciliation:** `/ontology-reconcile`: an LLM reads the coverage gaps *by
  meaning* and proposes `domain_config.json`/seed updates, validated vs CLAUDE.md, **gated,
  not auto-applied**.

## 7. Data files

**Git-tracked (the domain layer; swap to port):** `domain_config.json`,
`canonical_objects.json`, `object_properties_seed.json`, `domain_links_seed.json`,
`monitors_seed.json`.

**Gitignored outputs (`data/rag/`):**

| File | Contents |
|---|---|
| `chunks.jsonl` | section chunks (status, entities, supersession metadata) |
| `entity_registry.json` | entities + declared `type` + mention timeline + value-history |
| `type_registry.json` | declared type vocabulary: per-type counts, validator pattern, flagged count |
| `type_violations.json` | typed-but-malformed keys (extraction suspects) |
| `supersession.json` | correction/reference edges + `relation_prov` (W3C-PROV/nanopub vocab map for interop) |
| `arcs.json` | detected research arcs + states |
| `method_registry.json` | method lifecycle objects |
| `claim_status.json` | per-VR commitment + claim strata |
| `concepts.json` | concept emergence records |
| `file_meta.json` | per-file parsed metadata |
| `objects.json` | canonical objects: properties, pair facts, interfaces, links, claims, mentions |
| `domain_links.json` | typed object↔object links, supersession-tagged |
| `object_drift.json` | seed↔corpus drift report |
| `monitors.json` | monitors evaluated to met/unmet + evidence |
| `coverage_report.json` | what the structured layers miss |
| `grounding_report.json` | reproducer existence · dangling VR-N **and AUDIT-N** refs · file-citation resolution (`DANGLING_FILE_REF`, `.lean`→`proofs/`; outline-version churn→INFO) · retraction propagation |
| `index_stats.json` | counts (tracked, regenerated each build) |
| `chroma_db/`, `model/` | ONNX vector store + cached model |

## 8. Domain config — the porting surface

`domain_config.json` is the program's entire vocabulary. `index_vrs.py` loads it (with an
embedded fallback if absent). To run the toolchain on a different corpus, replace this file
and the seeds; the engine code is untouched.

```jsonc
{
  "entity_families":      [ { "pattern": "<regex>", "template": "<{n} = group n>" }, … ],
  "supersession_patterns":[ { "pattern": "<regex w/ VR-(\\d+)>", "relation": "<name>" }, … ],
  "reference_relations":  [ "references", "script_ref", "corroborates", "closes", … ],  // benign, full-text
  "correction_relations": [ "corrects", "refutes", "retracts", … ],                     // metadata-only
  "quantities":           [ { "name", "value_pattern", "key_group"|null, "key_literal"|null,
                              "val_group", "bound": [min,max]|null }, … ],
  "type_schema": { "<type>": { "display", "match": "<loose>", "valid": "<tight>" }, … },
  // optional — defaults preserve this deployment:
  "doc_id":               { "primary": "VR", "audit": "AUDIT" },   // document namespaces (domain_ids.py)
  "drift_value_patterns": { "<prop>": "<regex w/ one value group>" },  // drift + orient assertion checks
  "method_indicators":    [ { "pattern": "<regex>", "id": "<method_id>" }, … ],
  "method_lifecycle":     [ { "pattern": "<regex>", "state": "<state>" }, … ],
  "grounding":            { "source_root": "proofs" }              // bare-module citation resolution
}
```

Path overrides (porting/tests): `RAG_CORPUS_DIR` (corpus), `RAG_DATA_DIR` (outputs),
`RAG_SEED_DIR` (domain_config + seeds). The document contract a corpus must meet is
specified in `docs/rag_corpus_format.md`; the fixture (`tests/fixture/`) is its
executable reference.

Seed schemas: `canonical_objects.json` `{id,type,title,primary,aliases,dropped,note}` ·
`object_properties_seed.json` `{subject (id or "curve@field"),prop,value,vr_id,stratum,source}` ·
`domain_links_seed.json` `{source,relation,target,vr_id}` ·
`monitors_seed.json` `{id,watch,severity,detector_type,detector_args}`.

## 9. Keeping it operative + porting

The structured layers are pattern/seed-driven, precise but liable to miss what they don't
anticipate. Two mechanisms keep the tool honest:

Every rebuild runs `coverage.py`, so `query.py coverage` shows what is slipping (new
notation, relations, objects, alias drift), making the failure mode visible rather than
silent. When coverage shows drift, running `/ontology-reconcile` reads the flagged VRs by
meaning and proposes `domain_config.json`/seed edits (gated; you review, apply, then
rebuild; see the procedure in `.claude/commands/ontology-reconcile.md`).

To **port to another program**: write a new `domain_config.json` (entity families, relations,
quantities, type schema) and new ontology seeds; run `rebuild.sh`. The engine
(`index_vrs`/`ontology`/`coverage`/`query`) needs no changes.

## 10. Skills

| Skill | Use |
|---|---|
| `/rag <mode> …` | interactive query dispatch (all modes above) |
| `/ontology-reconcile` | semantic reconciliation when coverage shows drift |
| `/vr-audit` | full audit pass (uses `coverage`/`drift`/`monitor`/`type`/`graph`/`timeline`) |
| `/r14-loop` | substantive iteration (queries RAG for prior art) |
| `/audit-request <type> <target>` | dispatched single-purpose audit |

## 11. Architecture & history

The five layers (entity registry → vector search → grounding/contradiction → ontology →
robustness) are detailed, with rationale and the adversarial-review history, in
[`docs/ontology_rag_assessment.md`](../../docs/ontology_rag_assessment.md) (Builds 1–3) and
the reconciliation proposal log [`docs/ontology_reconcile_proposal.md`](../../docs/ontology_reconcile_proposal.md).

Design principles: stdlib-only core; build on existing data (each layer reuses the prior);
post-hoc longitudinal (audits the whole corpus, not a single trajectory); seeds are
authoritative (the indexer *validates* them, never extracts headline facts from prose).
