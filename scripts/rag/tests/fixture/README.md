# Fixture corpus — feature coverage map

A tiny fictional comet-survey research program exercising every engine feature,
so the pipeline can be run and tested with zero dependence on the live corpus.
Used by `test_fixture_e2e.py` via `RAG_CORPUS_DIR` / `RAG_DATA_DIR` / `RAG_SEED_DIR`.

| Doc | Exercises |
|---|---|
| VR-1 | entity extraction, quantities (period/magnitude), seed confirm (C_1 period=12) |
| VR-2 | reference edge (references VR-1) |
| VR-3 | wrong value (period=15) — correction TARGET; UNACKNOWLEDGED_CORRECTION (no inline tag) |
| VR-4 | correction edge (corrects VR-3, metadata-scoped) — arc with VR-3 |
| VR-5 | `settled_independent_route` monitor candidate (SETTLED, no independent route) |
| VR-6 | `forbidden_predicate` candidate ("C_1 is an asteroid" vs seeded body_class=comet) |
| VR-7 | `completeness_claim` candidate ("corpus-clean") |
| VR-8 | retracted doc (classify_status) — its forbidden phrase must NOT be flagged |
| VR-9 | retraction edge (retracts VR-8); dangling ref (VR-99); dangling file citation |
| VR-10..12 | drift flag: C_2 seeded period=20, corpus says 21 across 3 distinct VRs |
| AUDIT-1 | audit namespace; reference edge from an AUDIT doc |
| VR-1, VR-4 | method registry: `period_fit` lifecycle (implemented → failed → validated) |
| plan_stale.md | `orient` input: stale assertion (C_1 period=15), corrected citation (VR-3), dangling VR-99 |
