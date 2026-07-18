# Search engine v3 — design (the two promoted backlog items)

**Date:** 2026-07-17
**Status:** design (QUEUE Seq 12, promoted per the A3 stall trigger: the walk's first
four rungs each exceeded an hour of kernel time without exhausting)
**Scope:** (A) a stronger n=11 rung engine; (B) a MITM certificate arm for 30 < n <= 40.
Both are DESIGN-FIRST items; implementation enters the queue as its own gated plan.

## A. Stronger rung engine (the a(11) walk's bottleneck)

Measured: v2 (P1–P5 prunes, C kernel) does ~4–5M nodes/s but a single n=11 rung at the
DFX floor exceeds 10^9 nodes. Three upgrades, in expected-value order:

1. **Bidirectional / meet-in-the-middle feasibility**: **ANALYZED AND CORRECTED, VR-8.**
   The MITM difference-set characterization is correct (A=H∪L sum-distinct ⟺ H,L
   sum-distinct and D_H* ∩ D_L* = ∅; verified 71/71), BUT the join key is the
   difference set D_H (up to 2^h·(2^h-1) elements, exponential rather than a small hashable
   key), so the depth-n → 2·depth-(n/2) collapse does NOT hold, and MITM does not
   reduce the NODE COUNT for the infeasibility rungs the walk needs. This item is
   RETRACTED as "the lever." The genuine literature wins (Mucha–Nederlof–Pawlewicz–
   Węgrzycki, ESA 2019, representation method, linked from OEIS A276661) are
   research-grade and belong to a separate proof-gated plan. [was: optimistic
   depth-halving sketch]
2. **Dominance pruning with a correctness proof obligation**: if prefix P and P' cover
   the same element-count with P elementwise >= P' and equal partial sums... any such
   rule MUST ship with a conservativeness argument reviewed against the
   asymmetric-proof-burden rule (VR-1 §2.4), since dominance rules are where completeness
   bugs live. Design gate: each rule proved conservative in the plan doc BEFORE code.
3. **Per-rung parallelism** (intra-rung subtree splitting): partition the top-level
   element choices across workers with a shared ledger of exhausted subtrees, removing
   the current one-rung-per-core ceiling so 4 cores can burn down ONE hard rung.
   Mechanical; no correctness surface beyond subtree accounting.

Calibration gates (non-negotiable): v3 must reproduce, from scratch, (i) a(1..8)
exhaustive; (ii) the n=9 gate (a(9)=161, and node/verdict agreement per rung with the
v2 ledger where comparable); (iii) at least two v2-exhausted n=10 rungs from
results/gate_n10_ledger.json, all before any n=11 wall-clock counts.

## B. MITM certificate arm (30 < n <= 40)

The bitset certificate is O(total-sum) bits, approximately n*0.22*2^n, which is dead past n ~ 28-30. For
the records ladder to *certify* (not just construct) at 30 < n <= 40:

- Distinctness of all 2^n subset sums ⟺ the polynomial ∏(1 + x^{a_i}) has all
  coefficients <= 1. Split the set in halves A, B: coefficient vectors f_A, f_B of
  length S_A, S_B; the product's max coefficient is 1 iff (i) f_A, f_B individually
  flat (recurse/bitset, since halves are n/2 ~ 20, which is cheap) and (ii) the convolution
  f_A * f_B stays flat. Convolution via FFT is O(S log S) with S ~ 2^n*0.22*n, still
  too big at n = 40 (~10^13). The workable variant: **collision detection by sorted
  half-sums**: all 2^n sums are distinct iff the multiset {s_A + s_B} has no repeats,
  checkable by iterating the 2^{n/2} sorted half-sums of A against those of B with a
  two-pointer sweep over VALUE ORDER... which still enumerates 2^n pairs at n = 40.
- Honest conclusion (design finding): **full certificates at n = 40 cost >= 2^n
  operations no matter the encoding**; the arm's real deliverable is n <= ~34
  (2^34 ≈ 1.7·10^10 half-sum pair-events ≈ hours in C with sorted-merge early-exit),
  plus THEOREM-tier labeling beyond (Bohman structure), per VR-1 §2.7. Design
  gate: implementation targets n <= 34 and the epistemic-strata labels stay split
  (certified vs theorem-grounded), with no silent conflation.

## Queue placement

A.3 (intra-rung parallelism) is small and correctness-light: promote first, since it
directly serves the running walk. A.1 (MITM feasibility) is the big lever; its plan
carries the §A calibration gates. A.2 only with proofs. B rides after A.1 (shared
half-sum machinery).
