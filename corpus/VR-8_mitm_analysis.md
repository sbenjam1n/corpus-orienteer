# VR-8: MITM feasibility engine analyzed — does NOT accelerate the infeasibility proofs; design §A.1 corrected

**Date:** 2026-07-17
**Status:** [V] verified — rigorous negative + design correction; corrects docs/SEARCH_ENGINE_V3_DESIGN.md §A.1
**Arms:** analysis + arms/verify_set.py (characterization cross-check)
**Plan:** plans/P7_engine_v3.md M2

## §1 The question, honestly posed

P7 M2 proposed a meet-in-the-middle (MITM) feasibility engine as "THE big lever" to
turn the depth-n rung search into two depth-n/2 sweeps + a join (design §A.1). Before
building it — and risking a search-COMPLETENESS bug that would emit a FALSE negative
claim (a(11) ≥ X when false; the cardinal sin, VR-1 §2.4) — I analyzed whether the
speedup is real. It is not, for the case the walk actually needs.

## §2 The characterization (correct — verified)

Split A = {a_1 > … > a_n} into a high part H (top h) and low part L. A subset sum is
(H-subset-sum) + (L-subset-sum), so A is sum-distinct iff: H sum-distinct, L
sum-distinct, and the Minkowski sum S_H + S_L has no collision. A collision
s_H + s_L = s_H' + s_L' with (s_H,s_L)≠(s_H',s_L') forces a nonzero d with
d = s_H − s_H' = s_L' − s_L, i.e. **d ∈ D_H* ∩ D_L*** (nonzero difference sets). So:

> A = H ∪ L is sum-distinct ⟺ H, L each sum-distinct AND D_H* ∩ D_L* = ∅.

Cross-checked against the direct bitset test on 71 cases (Conway–Guy sets n=2..11 × all
splits, plus non-sum-distinct controls): **71/71 agree.** The characterization is sound.

## §3 Why it does NOT accelerate the walk (the decisive point)

MITM gives the classic √-speedup ONLY when the join key is small (sort one side,
binary-search the other in O(2^{n/2})). Here the join key is the **difference set
D_H**, whose size is up to 2^h·(2^h − 1) — exponential in the half-size, not a small
hashable key. The compatibility test is set-DISJOINTNESS of two large difference sets,
not equality of a scalar key. So the depth-n → 2·depth-(n/2) collapse **does not hold**.

For the INFEASIBILITY rungs the walk hits (prove no n-set with max ≤ M exists), MITM
must still show NO (H, L) pair works — it enumerates top halves H and, per H, searches
low halves. Illustrative measurement, n=7, M=43 (infeasible; a(7)=44): the v2
incremental-bitset DFS visits ~74,617 nodes; MITM enumerates ~1,608 sum-distinct top-4
candidates ALONE (bounded pool), each still needing a depth-3 low search against a
240-element difference set. The nested enumeration does not beat the DFS, and nothing
about it reduces the NODE COUNT — which is the actual barrier, since the v2 kernel
already amortizes the per-node collision test to near-O(1) via the bitset shift.

## §4 Consequences (design corrected, effort redirected)

1. **docs/SEARCH_ENGINE_V3_DESIGN.md §A.1 is corrected**: naive MITM is not the lever;
   the "big win" claim was over-optimistic. The genuine algorithmic wins in the
   literature (Mucha–Nederlof–Pawlewicz–Węgrzycki, *Equal-Subset-Sum Faster Than MITM*,
   ESA 2019 — LINKED from OEIS A276661) use the representation method, which is
   research-grade and carries its own completeness-proof burden; it is a proper
   separate plan, not a same-turn build.
2. **The sound single-machine path is the intra-4 walk** (P7 M1, 3.3× — banked, proven
   correct): it closes low a(11) rungs and each raises the proven lower bound as a
   permanent artifact (VR-9+). That the a(11) FRONTIER itself resists a single box is
   consistent with the problem's genuinely-open status (a(10) took Dyson ~40
   machine-weeks, VR-5 §3).
3. **No broken engine shipped.** The cardinal failure mode (a false infeasibility
   claim) is avoided by not deploying an unproven fast engine. M1's intra parallelism
   and the v2 prunes remain the certified basis for every negative claim.

## §5 What would change this

A representation-method engine with either (a) a written completeness proof, or (b)
exact agreement with the v2 kernel across the full n≤10 calibration suite (a(1..8) +
all 35 n=9 rungs + sampled n=10 rungs) as strong empirical evidence, could be adopted —
gated exactly as P7 M2's original gates specified. Until then its verdicts stay OUT of
the corpus. This VR closes M2 as "analyzed → redirected," not "pending."
