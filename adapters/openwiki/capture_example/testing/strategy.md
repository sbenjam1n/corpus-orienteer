---
type: Testing
title: Testing strategy — engine suite, arm tests, determinism, fixtures, monitors as tests
description: "How the engine + demo arm tests are organised: the engine suite under scripts/rag/tests/ (unit controls + two fixture end-to-end runs with byte-determinism asserts), the demo arm tests under tests/test_arms.py (golden values + certificate ceiling guard + OKF determinism + constants-curve overflow), and how monitor semantics get frozen as regression tests. Plus the .github/workflows/rag-tests.yml CI job structure and the rules a new arm must satisfy before its output counts."
tags: [openwiki, testing, determinism, fixtures, monitors, ci, regression]
---

# Testing strategy

The demo program stands on four testing surfaces, each guarding a demonstrated failure
mode (the lineage is in `docs/ontology_rag_assessment.md`):

1. **Wrong value** → the calibration gate.
2. **Wrong binding** → conventions + drift + the orient assertion check.
3. **Unnecessary / overclaimed computation** → the asymmetric-proof-burden rule + the
   claim-inflation guard + claim-level monitors.
4. **Silent drift** → the determinism invariant + the self-consumption guard + the
   self-coverage audit.

This page distills the test layout and the rules a new arm must satisfy.

## The engine suite — `scripts/rag/tests/`

| File | Purpose |
|---|---|
| `test_rag_engine.py` | Engine unit controls — detector behaviour, parsers, indexing, ontology, drift, monitors, orient, query modes. **Detector controls are frozen as tests**, so a detector rewrite that changes behaviour is a deliberate, reviewable diff. |
| `test_fixture_e2e.py` | End-to-end run on the single-tier fixture corpus (a fictional comet survey). Exercises every engine surface against a known corpus. |
| `test_fixture_tiered_e2e.py` | End-to-end run on the tiered fixture (comet survey + thread + versioned outline + archive + derived artifact). **8 e2e asserts** including byte-determinism. The tier-semantics freeze per P6 M5.2. |
| `determinism_check.sh` | Rebuilds the engine twice; requires byte-identical `data/rag/` outputs and a clean `git status`. The determinism-invariant belt. |

The fixture corpus is the **executable form** of the document contract
(`docs/rag_corpus_format.md`) — `RAG_CORPUS_DIR=scripts/rag/tests/fixture/corpus ./rag rebuild`
should work without any other setup. The tiered fixture is the equivalent for
multi-population deployments.

## The demo arm tests — `tests/test_arms.py`

Four test classes, ~5s total:

| Class | What it asserts |
|---|---|
| `TestVerifySet` | Known sum-distinct set certifies; collision detected (and the colliding sum is the correct one); nonpositive/duplicate elements rejected; **`arms/verify_set` refuses CG-40-sized sets** with a cost estimate (theorem territory, not certificate) |
| `TestConwayGuy` | Generator matches OEIS A005318 first 14 terms exactly; CG sets certificate-verify up to n=20 |
| `TestExhaustiveGolden` | `arms/exhaustive.py` re-derives a(1)..a(7) exactly (8 stops at minutes-scale and is banked as a corpus artifact in `results/exhaustive_n8.json` / `VR-3`) |
| `TestEmitOkf` | OKF pages carry only the five OKF front-matter keys (`type`, `title`, `description`, `resource`, `tags`); `index.md` is never written; two emissions from the same build are byte-identical (SHA-256 match) |
| `TestConstantsCurve` | Golden values for the empirical constant curve; c(3) = 1/2 exactly; u(67) overflows uint64 and is carried exactly; DFX floor ≤ best-known everywhere |

## The CI workflow — `.github/workflows/rag-tests.yml`

Two jobs run on every push and PR:

### `engine` job

```yaml
- name: Unit + fixture end-to-end suite
  run: python -m unittest discover -s scripts/rag/tests -v
- name: Demo arm tests (golden values + guards)
  run: python -m unittest discover -s tests -v
```

Stdlib-only, runs in seconds.

### `corpus-conformance` job

```yaml
- name: Corpus conforms + full pipeline builds
  run: |
    ./rag rebuild
    ./rag query stats
- name: Determinism — repeat builds are byte-identical
  run: |
    ./rag rebuild
    find data/rag -type f | sort | xargs sha256sum > /tmp/build1.sha
    ./rag rebuild
    find data/rag -type f | sort | xargs sha256sum > /tmp/build2.sha
    diff /tmp/build1.sha /tmp/build2.sha
```

The determinism job primes once (`build 1` / `build 2`), then asserts that two
further rebuilds are byte-identical (the "steady-state rebuilds" invariant — the
first-ever build has no `file_meta_prev.json` snapshot, so the brief's
"changed since last pass" section legitimately differs between build 1 and build 2).
The invariant must hold on the live demo corpus, not just on the fixture.

## The OpenWiki docs workflow — `.github/workflows/openwiki-update.yml`

Daily at 08:00 UTC + on `workflow_dispatch`. Installs OpenWiki, runs
`openwiki code --update --print`, and opens a PR with the generated docs. The pre-steps
needed for the corpus engine to feed it (`rebuild` + `emit_okf`) live in
`adapters/openwiki/openwiki-update-prestep.yml` and must be inserted into OpenWiki's
example workflow. The scheduled PR carries the alerts (unmet HIGH monitors via the
optional failing-gate step).

## Rules a new arm must satisfy

From `plans/P1_calibration.md` §2 (the standing rule for future arms):

1. **Calibration gate first**: a new arm enters the queue with its own §1-style
   calibration block. The calibration set for exact-ladder arms is frozen:
   {a(1)..a(8) exhaustive, CG-9/10/11 certificates}; for record-ladder arms:
   {reproduce CG-n maxima for n = 14..20 before reporting any "improvement"}.
2. **In-code calibration assertion**: each arm carries a `CALIBRATION` table or
   `A_VERIFIED` table that fails loudly (exit code ≠ 0) on a mismatch. A recurrence
   transcription bug must never silently ship wrong sets.
3. **Asymmetric proof burden**: every exhaustion claim names its prunes and argues
   each is conservative (`arms/exhaustive.py` documents P1–P5 in the module docstring;
   the same shape is expected of any future arm).
4. **Certificate ceiling**: `arms/verify_set.py`'s `MAX_BITS_DEFAULT = 2_000_000_000`
   guard refuses with a cost estimate at > 2×10⁹ bits. Large-n sum-distinctness claims
   must rest on a THEOREM (e.g. Bohman 1996 for Conway–Guy sets), and must be labeled
   at that grounding. A new arm that produces certificates must mirror this discipline.
5. **Non-circularity**: subset-optimum floors (P4) use **only** values the repo has
   itself re-derived — never the published value a gate run is re-deriving.
6. **Monitor semantics as tests**: any new monitor added to `monitors_seed.json`
   should have a corresponding test in `scripts/rag/tests/test_rag_engine.py` so its
   semantics are frozen. The engine already does this for the existing detectors.

## How to add a test for a new detector

1. Implement the detector in `scripts/rag/ontology.py:evaluate_monitor` (or in the
   appropriate module per the engine's existing layout).
2. Declare it in `monitors_seed.json` (or in a `domains/<x>/monitors_seed.json` for a
   ported deployment).
3. Add a test in `scripts/rag/tests/test_rag_engine.py` that exercises:
   - the detector firing on a synthetic positive case (the candidate row carries the
     matched span + the contradicted seed fact),
   - the detector NOT firing on a negative control (a chunk that uses the same words
     in a non-asserting context — quoting, negation, corrected status).
4. Add the monitor to `rebuild.sh`'s post-coverage stage (it's already wired — just
   declared and exercised).
5. Run `python -m unittest discover -s scripts/rag/tests -v` to confirm green.

The same shape applies to a new arm under `arms/`: calibration table + golden test +
recipt test (`is_sum_distinct` for sums; `a(n) = expected` for the value; and a
**certificate ceiling guard** for any arm that produces certificates).
