# VR-7: Records ladder opened — CG-14..25 certified baseline; bounded perturbation scan negative (P3 §3)

**Date:** 2026-07-17
**Status:** [V] verified — baseline certificates + a bounded negative result; no new values
**Arms:** arms/records.py (arms/conway_guy.py + arms/verify_set.py underneath)
**Plan:** plans/P3_records.md §3

## §1 Baseline table (calibration gate for any future record claim)

CG-n certified sum-distinct by the exact bitset for **n = 14..25** (twelve sets;
largest: CG-25, max element 8,311,101). Raw: results/records_baseline.json. A
certification FAILURE here would contradict Bohman 1996 and therefore STOP the arm as
self-suspect (coded in). n = 26..28 remain within the bitset guard if wanted;
n >= 29 needs the MITM certificate arm (design: docs/SEARCH_ENGINE_V3_DESIGN.md).

## §2 Perturbation scan — honest negative

Bounded deterministic neighborhood around the CG structure (one element lowered by
delta <= 4, whole set shifted down by <= 3): n = 14..18, 1280 candidates, **0
improvements** (results/records_perturb.json). Consistent with CG local rigidity;
recorded so the neighborhood is not silently re-searched. Any future improvement is a
TABLE ENTRY, never a claim on Bohman's asymptotic record (VR-1 §2.5; the
record_claim_inflation monitor watches the phrasing).

## §3 Next rungs for this ladder

Richer neighborhoods (multi-element moves, difference-structure edits à la Lunnon) are
open; they enter through the same calibration gate. The n = 12/13 posted sets (VR-5)
show non-CG structures win at small n — the interesting question is where that stops.
