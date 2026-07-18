---
type: Research
title: "Erdős distinct-subset-sums frontier — the demo program's a(n) table"
description: "The Erdős distinct subset sums problem (erdosproblems.com #1, OEIS A276661, $500 prize) as operated by corpus-orienteer: the exact a(n) table with provenance, the live frontier a(11) in [462, 594], the posted-vs-verified status of a(12) and a(13) constructions, the Conway–Guy optimality refutation at n=12/13, and the Bohman asymptotic record that single-n improvements never touch."
tags: [openwiki, research, erdos, frontier, a-table]
---

# Erdős distinct-subset-sums frontier

The demo program in this repo operates on **OEIS A276661** — the minimal largest element
of an n-element sum-distinct set — which corresponds to **erdosproblems.com #1**, the
Erdős "$500 first serious problem." The conjecture itself is provably not resolvable by
finite computation (see `corpus/VR-1` §1, fetched from erdosproblems.com 2026-07-16), so
the program never claims to attack the conjecture — its computational objects are the
exact-optimum table `a(n)`, construction records at larger `n`, and the empirical
constant curve `a(n)/2^n`.

> **Conventions** (binding for every VR; see `corpus/VR-1` §2):
> elements are distinct positive integers, the empty set counts, exact values are
> written `a(n) = v`, bounds as `a(n) <= v` / `a(n) >= v`. The asymmetric proof burden
> is pinned: the positive side of `a(n) = v` is a witness (trivially certifiable); the
> negative side ("no set with max ≤ v−1") rests on **search completeness** — every
> exhaustion claim must name its prunes and argue each is conservative. An exact claim
> without an exhaustion receipt is not a result.

## The current a(n) table

Source of truth: `corpus/VR-2` §1 (frontier restated against primary sources, fetched
2026-07-16) + `corpus/VR-5` (posted-set verification) + `corpus/VR-3` (calibration run
that reproduces a(1)..a(8) exhaustively and witnesses CG-9/10/11).

| n | status | value / window | provenance |
|---|---|---|---|
| 1..7 | exact | 1, 2, 4, 7, 13, 24, 44 | classical (Lunnon 1988); reproduced exhaustively in `VR-3` |
| 8 | exact | **a(8) = 84** | Lunnon 1988; reproduced exhaustively in `VR-3` (121.7M nodes / 285s) |
| 9 | exact | **a(9) = 161** | Grossman; **re-derived exhaustively in `VR-4` §4** (35 rungs, 16.23B nodes) — the n=9 gate, cleared |
| 10 | exact | **a(10) = 309** | **Dyson, Oct 21 2025** (exhaustive, published code) — CG-10 witness verified in `VR-3` §3; VR-2 §1 citation corrected in `VR-5` (repository is `github.com/pwdyson/erdos_1`) |
| **11** | **OPEN — live frontier** | **462 ≤ a(11) ≤ 594** | lower: DFX binom(11, 5) (arXiv:2006.12988); upper: CG-11 witness (u(11) = 594), verified in `VR-3` §3 |
| 12 | open | 924 ≤ a(12) ≤ 1157 | lower: DFX binom(12, 6); upper: **posted OEIS-comment set (Popov Nov 2025 / Branicky Jan 2026), certificate-verified here in `VR-5` §2** — proves a(12) ≤ 1157 < u(12) = 1164 |
| 13 | open | 1716 ≤ a(13) ≤ 2249 | lower: DFX binom(13, 6); upper: **posted OEIS-comment set (same provenance), certificate-verified in `VR-5` §2** — proves a(13) ≤ 2249 < u(13) = 2284 |

The CG-9/10/11 witnesses are identical to the optimum at those n — the optimality
ceiling holds for n ≤ 10. At n = 12, 13 the ceiling is **beaten** by posted constructions,
which is exactly what flipped the program's heuristic about CG optimality from
"unbeaten-in-small-cases" to "refuted-as-general" (`VR-2` §3).

## Bounds context (from `VR-1` §4)

- **Lower (DFX)**: `a(n) ≥ binom(n, ⌊n/2⌋)` (Dubroff–Fox–Xu, arXiv:2006.12988);
  asymptotically ~ √(2/π) · 2ⁿ / √n.
- **Upper (Bohman)**: max element ≤ 0.22002 · 2ⁿ asymptotically (Bohman 1998) —
  unbeaten.
- The program's own exhaustion floors use only the weaker **self-contained doubling
  bound** `⌈(2ⁿ − 1) / n⌉`, so the negative claims in `VR-3` / `VR-4` rest on the run's
  own arithmetic — not on the DFX theorem. DFX is cited context, not part of the proof.

## The CG-optimality refutation (and why it's pinned as a monitor)

`u(12) = 1164` but `a(12) ≤ 1157`; `u(13) = 2284` but `a(13) ≤ 2249`. Conway–Guy sets
were optimal at every exactly-known n (n ≤ 10) and **NOT optimal in general** — a
refuted heuristic. The seeded fact `cg_family.optimal_at = "n<=10 only"` (in
`domains/erdos1/canonical_objects.json` and `object_properties_seed.json`) and the
`cg_optimality_forbidden` monitor (`domains/erdos1/monitors_seed.json`) guard this corpus
against re-asserting the refuted heuristic in any future doc.

## The Bohman record (untouched by single-n)

Bohman's 0.22002 · 2ⁿ is an **asymptotic family record**, not a single-n value. The
`record_claim_inflation` monitor (`monitors_seed.json`) prevents any doc from claiming
that a single-n improvement beats the Bohman bound. Per `VR-1` §2.5: **beating
0.22002 · 2ⁿ at a single n does NOT improve the asymptotic family record** — single-n
results are table entries, not record claims.

## Anti-rediscovery discipline (from `VR-2` §2)

Do not rediscover n = 12, 13: the constructions beating Conway–Guy there are already
posted. The honest next contributions are:

1. Independent verification of those posted sets — **done** (`VR-5`).
2. Records at n ≥ 14 — **opened** (`VR-7`: CG-14..25 certified baseline + a bounded
   perturbation scan that found 0 improvements — recorded honestly as a negative so the
   neighborhood is not silently re-searched).
3. The empirical constant curve `a(n)/2ⁿ` — **done** (`VR-6`: results in
   `results/constant_curve.{json,svg}` with three-way provenance per row).

## The frontier campaign — `plans/P2_frontier_n11.md`

The current agent lane is the **a(11) walk**: an ascending ledger walk from the DFX
floor 462 toward the 594 ceiling. Each contiguously exhausted rung raises the proven
lower bound (`a(11) ≥ lb`) as a permanent artifact, even if the window never fully
closes. Probe receipt: `M=462` alone exceeded 131M nodes in 5 minutes — rungs are
hours-scale. The walk runs under `arms/gate_parallel.py --order asc --intra 4` after
the n=10 gate (which itself is a standing campaign; see
[Compute arms](compute-arms.md)).

The walk's design lever — a meet-in-the-middle feasibility engine — was **analyzed
before being built** (`VR-8`): the difference-set characterization is sound
(verified 71/71 against the direct bitset), but the join key (the difference set) is
**exponential in the half-size**, so the depth-n → 2·depth-(n/2) collapse does not
hold for the infeasibility rungs the walk hits. Naive MITM does NOT reduce the node
count, so `docs/SEARCH_ENGINE_V3_DESIGN.md` §A.1 was corrected, and the algorithmic
lever (the representation method, Mucha et al. ESA 2019 — research-grade, proof-gated)
is redirected to its own future plan. The sound single-machine path remains the
intra-4 walk (P7 M1, 3.3× speedup banked, identical verdicts on the n=9 gate).
