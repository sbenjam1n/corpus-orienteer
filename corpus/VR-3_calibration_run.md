# VR-3: Calibration run — exhaustive a(1)..a(8), witness certificates a(9)..a(11), generator calibration

**Date:** 2026-07-16
**Status:** [V] verified — all outputs match VR-2's table (matches VR-2); no new claims
**Arms:** arms/exhaustive.py · arms/conway_guy.py · arms/verify_set.py

Calibrate-before-extend (QUEUE §P4): before the a(11) campaign consumes a single
CPU-hour, the engine must reproduce every cheaply reachable known result. All commands
run from the repo root; raw outputs in results/.

## §1 Conway–Guy generator calibration

`arms/conway_guy.py` computes u(n) from the recurrence u(k+1) = 2u(k) − u(k − round(sqrt(2k)))
and asserts its first 14 terms against the published OEIS A005318 values before emitting
anything. Result: 14/14 match (0, 1, 2, 4, 7, 13, 24, 44, 84, 161, 309, 594, 1164, 2284).
A recurrence transcription bug therefore fails loudly — the canonical-source discipline
applied to code.

## §2 Exhaustive exact optima, n = 1..8

`python3 arms/exhaustive.py --n {1..8}` — branch-and-bound over descending elements with
the incremental bitset collision test and two conservative prunes (P1 element-supply,
P2 doubling); scan floor = the self-contained doubling bound (NOT the stronger DFX bound,
so these negative claims rest only on this run's own arithmetic).

| n | a(n) | witness found | nodes | elapsed | published |
|---|------|---------------|-------|---------|-----------|
| 1 | 1  | [1] | 0 | ~0s | 1 ✓ |
| 2 | 2  | [1, 2] | 1 | ~0s | 2 ✓ |
| 3 | 4  | [2, 3, 4] | 5 | ~0s | 4 ✓ |
| 4 | 7  | [3, 5, 6, 7] | 29 | ~0s | 7 ✓ |
| 5 | 13 | [6, 9, 11, 12, 13] | 381 | ~0s | 13 ✓ |
| 6 | 24 | [11, 17, 20, 22, 23, 24] | 11,159 | 0.012s | 24 ✓ |
| 7 | 44 | [20, 31, 37, 40, 42, 43, 44] | 658,010 | 0.96s | 44 ✓ |
| 8 | 84 | [40, 60, 71, 77, 80, 82, 83, 84] | 121,754,429 | 284.8s | 84 ✓ |

8/8 agreement with the published table (raw: results/exhaustive_n8.json). The n=8
witness is exactly the CG-8 set. Node growth ×185 from n=7 to n=8 calibrates the
n = 9..11 cost model for plans/P2_frontier_n11.md: the current prunes will NOT reach
n=11 as-is; the campaign needs the stronger admissible floor and pruning family
(plan §M2) before spending compute.

## §3 Witness certificates at the frontier edge

`arms/conway_guy.py --n {9,10,11} --verify`: CG-9 (max 161), CG-10 (max 309), CG-11
(max 594) are certificate-verified sum-distinct. Consequences, per VR-2: a(9) <= 161 and
a(10) <= 309 (exactness of both rests on Grossman's and Dyson's exhaustions, cited in
VR-2 — not re-established here); a(11) <= 594 (our own verified witness for the open
frontier's upper edge).

## §4 Certificate ceiling (methods fact)

`arms/verify_set.py --n 40` on CG-40 fails by design: the bitset certificate costs
O(total sum) bits ≈ n·0.22·2^n — a CG-40 certificate would need ~10^13 bits. The guard
now refuses with a cost estimate at >2×10^9 bits (n ≈ 30 ceiling). Large-n
sum-distinctness of CG sets is Bohman's THEOREM (stratum: proved), not certificate
output; VR-1 §2.7 binds the labeling.

## §5 What this run does NOT establish

No new values. a(9), a(10) exactness imported from VR-2's provenance. a(11) remains
OPEN in [462, 594]; the n=11 negative side is untouched (P2's job, after its engine
gate). No statement about n >= 12.
