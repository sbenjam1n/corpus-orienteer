# VR-2: Current frontier of the a(n) table — corrects VR-1, closes AUDIT-1

**Date:** 2026-07-16
**Status:** [V] verified — frontier restated against primary sources fetched 2026-07-16
**Supersession:** corrects VR-1 (§5 frontier table); closes AUDIT-1

## §1 The correction

VR-1 §5's "exact values known for n <= 9" is superseded. The current table
(OEIS A276661, fetched 2026-07-16):

| n | status | value / window | provenance |
|---|--------|----------------|------------|
| 1–7 | exact | 1, 2, 4, 7, 13, 24, 44 | classical (Lunnon 1988 a-table); reproduced exhaustively in VR-3 |
| 8 | exact | a(8) = 84 | Lunnon 1988; reproduced exhaustively in VR-3 |
| 9 | exact | a(9) = 161 | Grossman; CG-9 witness verified in VR-3 |
| 10 | exact | a(10) = 309 | **Dyson, Oct 21 2025** — exhaustive, published code **[CORRECTED per VR-5: the repository is github.com/pwdyson/erdos_1]**; CG-10 witness verified in VR-3 |
| 11 | **OPEN — the live frontier** | 462 <= a(11) <= 594 | lower: DFX binom(11,5); upper: CG-11 witness (u(11) = 594), verified in VR-3 |
| 12 | open | 924 <= a(12) <= 1157 | lower: DFX binom(12,6); upper: posted OEIS comment constructions (third-party, NOT independently verified here) |
| 13 | open | 1716 <= a(13) <= 2249 | lower: DFX binom(13,6); upper: posted (third-party, NOT independently verified here) |

## §2 Consequences for the program

- The exact-ladder target is **a(11)**: window [462, 594], exhaustion campaign in
  plans/P2_frontier_n11.md. Dyson's published a(10) code is the calibration
  counterpart for any exhaustion engine we run at n >= 10.
- **Do not rediscover n = 12, 13**: constructions beating Conway–Guy there are already
  posted. The honest next contributions are (a) independent verification of those
  posted sets (they are seeded at stratum `predicted` until then), and (b) records at
  n >= 14 (plans/P3_records.md).

## §3 Conway–Guy optimality is refuted as a general heuristic

u(12) = 1164 but a(12) <= 1157; u(13) = 2284 but a(13) <= 2249. CG sets are optimal at
every exactly-known n (n <= 10) and NOT optimal in general. The seeded fact
`cg_family.optimal_at = n<=10 only` and the `cg_optimality_forbidden` monitor guard
this corpus against re-asserting the refuted heuristic.

## §4 Historical caution imported with the table

Conway–Guy sets were only CONJECTURED sum-distinct for ~28 years until Bohman 1996.
A005318 values are upper-bound witnesses only where a verified witness set exists;
the sequence is not ground truth for the optimum (see n = 12).

## §5 Still-open verification (adversarial, 2026-07-16)

An adversarial sweep attempting to refute openness found: erdosproblems.com/1 OPEN,
$500, "cannot be resolved with a finite computation", page last edited 2026-04-06,
zero claimed proofs; arXiv full-text sweep 2022–2026 shows only variants (Zk
generalization 2510.06032, modular 2308.03748, few-subset-sums 2605.05498 — none touch
the 1D conjecture); the teorth/erdosproblems "AI contributions" tracker (through
2026-06-30) has NO entry for #1; no press/blog signal. Verdict: solidly open.

## §6 Sources

- https://oeis.org/A276661 · https://oeis.org/A005318 (fetched 2026-07-16)
- https://github.com/pwdyson/erdos_1 (a(10) search code) **[CORRECTED per VR-5 — was cited as pwdyson/distinct_subset_sum]**
- https://www.erdosproblems.com/1 · https://github.com/teorth/erdosproblems/wiki
- arXiv:2006.12988 (DFX) · arXiv:2510.06032 · arXiv:2308.03748 · arXiv:2605.05498
