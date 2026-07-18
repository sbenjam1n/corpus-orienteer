# VR-4: Search engine v2 + the exact-ladder gates — a(9) = 161 re-derived; n=10 campaign opened

**Date:** 2026-07-16
**Status:** [V] verified — engine receipts complete; n=9 gate CLEARED (matches VR-2); n=10 gate IN PROGRESS (ledger = live receipt); M2 remains BLOCKED on it
**Arms:** arms/exhaustive.py v2 · arms/feasible.c · arms/gate_parallel.py
**Plan:** plans/P2_frontier_n11.md M1 (steps 1.1–1.3, 1.5 complete; 1.4 partially — see §5)

## §1 Engine v2 — prunes, floors, checkpointing

Three prunes added to the v1 pair, each conservative (rejects only branches provably
containing no completion; arguments pinned in the module docstring):

- **P3 full-sum**: total ≥ 2^n − 1 (2^n distinct sums in [0, total]).
- **P4 subset-optimum floor**: the k remaining elements form a sum-distinct k-set, so
  their cap ≥ floor(k). **Non-circularity rule**: floor(k) uses ONLY own-re-derived
  values (VR-3's a(1..8); a(9) added by this VR's own gate, §4) else the DFX theorem
  binom(k, ⌊k/2⌋) — a gate run never imports the value it is re-deriving.
- **P5 variance** (the classical second-moment argument): the subset-sum distribution
  has variance Σa_i²/4 and 2^n distinct integers need variance ≥ (4^n−1)/12, so
  Σa_i² ≥ (4^n−1)/3.

Scan floors: `--floor dfx` (binom(n, ⌊n/2⌋), arXiv:2006.12988) default, doubling floor
as self-contained cross-check; the JSON records which floor the negative side rests on.
`--ledger` = per-M checkpointing (M-granularity resume). Regression: n = 1..8 values and
witnesses identical to VR-3; the a(8) rung count fell 121.7M → 30.9M nodes.

## §2 The C kernel and the mirror invariant

`arms/feasible.c` answers one (n, M) feasibility question; `exhaustive.py` stays the
reference implementation. The kernel is an **exact DFS mirror**, cross-validated the
strongest way available short of proof: **identical per-M node counts** —
n=8, M=83: 9,388,500 nodes in both engines pre-P5 and 5,440,254 post-P5 (re-verified
after the live-word optimization, which changes speed, not traversal). The driver
sync-checks the kernel's A_VERIFIED table at startup (`--table`). Wall-clock: the full
n=8 gate 285 s (v1 Python) → 8.0 s (v2 C).

## §3 Parallel gate driver

Rungs (fixed-M feasibility questions) are independent, so `gate_parallel.py` farms them
to N workers, hardest-first. The ceiling (e.g. the Conway–Guy value) is certified FIRST
by witness; **the choice of ceiling does not enter the proof** — exactness =
certificate at the ceiling + exhaustion of every rung below the theorem floor. A rung
finding a witness below the ceiling would be a discovery, recorded as such. The merged
per-rung ledger is the resumability mechanism and the receipt: the n=9 run survived a
genuine mid-run container restart with 25 rungs held, resumed, and completed.

## §4 GATE n=9 — CLEARED: a(9) = 161, exact

results/gate_n9.json + gate_n9_ledger.json: all 35 rungs M ∈ [126, 160] exhausted
infeasible (floor = DFX binom(9,4) = 126); witness at 161 = the CG-9 set
[77,117,137,148,154,157,159,160,161]. **16,230,800,798 nodes** total across the
sequential + parallel runs. Agrees with the published value (Grossman, per VR-2 §1).
Per the non-circularity rule, a(9) = 161 is now banked in A_VERIFIED in BOTH engines
(table sync re-checked; mirror re-verified post-edit).

## §5 GATE n=10 — OPENED, running; honest scale statement

results/gate_n10_ledger.json (live): ceiling 309 witnessed immediately (CG-10,
[148,225,265,285,296,302,305,307,308,309]); 57 rungs [252, 308] under exhaustion,
hardest-first, 4 workers. Measured scale: after ~10 minutes of 4-worker compute, zero
top rungs complete — single top rungs exceed 3×10⁹ nodes each and the full exhaustion
projects to **tens of core-hours** (consistent with a(10) having waited for Dyson's
2025 computation). This is a **standing campaign, not a session task**: it continues in
budgeted windows, the ledger accumulates permanent per-rung infeasibility receipts
across restarts, and completion (or any disagreement with 309 — a STOP finding) will be
recorded in a follow-up VR.

**Plan deviation, documented:** P2's step 1.4 asked for a cross-check "against Dyson's
published code"; his repository is outside this session's access scope, so the
cross-check is against his published RESULT (a(10) = 309, OEIS A276661) and our own
independently-witnessed CG-10 certificate. Running his code remains open under S1's
posted-sets verification item.

## §6 Gate discipline

Per QUEUE §1 A2/A3: **M2 (any n=11 wall-clock) remains BLOCKED** until the n=10 gate
completes and agrees. Nothing in this VR advances the frontier: a(10) here is still
VR-2's imported value (stratum verified via Dyson + our witness certificate); the
exhaustive re-derivation is what the open campaign will (or will not) deliver.

## §7 What this VR establishes

1. a(9) = 161 by our own exhaustive re-derivation (previously imported, VR-2).
2. The engine's negative claims now rest on five named conservative prunes, a theorem
   floor, an exact two-engine mirror, and restart-surviving per-rung receipts.
3. a(10) re-derivation: OPEN, in progress, honestly sized.
