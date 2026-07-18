---
type: Reference
title: Compute arms — exhaustive, gate_parallel, conway_guy, verify_set, records, constants_curve
description: "The compute arms under arms/: each arm's purpose, the calibration discipline shared by all (canonical-source asserted in code before emission; no arm's output counts until it reproduces every cheaply reachable published result), what each arm's results land in, and the receipts each one carries. Plus arms/feasible.c — the exact DFS mirror of arms/exhaustive.py with per-M node-count equality."
tags: [openwiki, research, arms, compute, calibration, conway_guy, exhaustive, verify, records, constants]
---

# Compute arms

The arms under `arms/` are the demo program's **compute side** — every math artifact
that lives in `results/` comes from one of them. Every arm is governed by the same
calibration discipline (from `plans/P1_calibration.md` and `QUEUE.md` §0.5 P4.1):

> No arm's output counts for anything until the arm reproduces every cheaply reachable
> published result in its class.

That discipline is enforced two ways:

1. **In code** — each arm carries a `CALIBRATION` table (published values asserted
   in-code before any output) or an `A_VERIFIED` table (own-re-derived values used as
   non-circular subset-optimum floors) that fails loudly on a mismatch.
2. **In tests** — `tests/test_arms.py` runs the golden-value sweep + the certificate
   ceiling guard; CI runs it on every push and PR.

A failed calibration fails loudly (exit code ≠ 0) — the agent is never asked to
trust an uncalibrated number.

## The arms

### `arms/feasible.c` — exact DFS mirror (kernel)

C kernel answering one `(n, M)` feasibility question: "does an n-element
sum-distinct set with largest element EXACTLY M exist?" Built with
`gcc -O2 -o arms/feasible arms/feasible.c`.

- **Exact mirror** of `arms/exhaustive.py:feasible_with_max` (same DFS order, same
  prunes P1–P4, same non-circular `A_VERIFIED` table). The Python arm is the reference
  implementation; the C kernel exists because the n ≥ 9 gate runs are compute-bound.
- **Per-M node-count equality** with Python: n=8 M=83 = 9,388,500 in both engines
  pre-P5, 5,440,254 both post-P5 — re-verified after the live-word optimization (which
  changes speed, not traversal).
- **Driver sync check**: the Python driver (`exhaustive.py --engine c`) sync-checks the
  C kernel's `A_VERIFIED` table at startup via `--table`; mismatches exit non-zero.
- **Per-M runtime budget**: `feasible <n> <M> <budget_s>`; stdout `witness <nodes>
  <e1> ... <en>` / `infeasible <nodes>` / `budget <nodes>` (exit 2 = deadline hit, no
  claim).
- **Stride/offset partition** (P7 M1): the kernel's `--stride K --offset i` partition
  the depth-1 subtree choices across workers; every deeper node belongs to exactly one
  worker, so the workers' node-count sum equals the single-process count + (K−1)
  root increments (asserted by tests).

### `arms/exhaustive.py` — Python reference DFS

Branch-and-bound over descending elements with the incremental bitset collision test
and the conservative prune family:

| Prune | Rejection condition |
|---|---|
| **P1** element-supply | `cap < k` (need k more elements in [1..cap]) |
| **P2** doubling (remaining subset) | `2^k > k·cap + 1` (k elements must be sum-distinct in [1..cap]) |
| **P3** full-sum feasibility | partial_sum + best achievable remaining sum < 2ⁿ − 1 |
| **P4** subset-optimum floor | `cap < floor(k)` where `floor(k) = A_VERIFIED[k]` for `k ≤ 8`, else `binom(k, ⌊k/2⌋)` (DFX) |
| **P5** variance (second moment) | partial_sq + best achievable remaining Σ of squares < (4ⁿ − 1)/3 |

**Non-circularity rule** (pinned in the module docstring): the `floor(k)` table
contains **only values this repo has itself re-derived** — never the published value a
gate run is re-deriving. `A_VERIFIED = {1:1, 2:2, 3:4, 4:7, 5:13, 6:24, 7:44, 8:84,
9:161}`. a(9) was added after the n=9 gate (`VR-4` §4).

**Scan floors** (`--floor`): `dfx` (default, binom(n, n//2) — DFX 2021 theorem) or
`doubling` (ceil((2ⁿ − 1)/n), self-contained). The JSON records which floor the
negative side rests on.

**Ledger** (`--ledger FILE`): per-M checkpointing. Completed Ms are recorded and
skipped on restart; a killed run loses at most the current M's partial work. The
negative claim for a ledger M rests on the run that completed it.

**Outputs:** one JSON on stdout (`status`, `witness`, `nodes`, `elapsed`, `floor`
metadata). n=1..8 reproductions live in `results/exhaustive_n8.json` (8/8 published
agreement; the n=8 rung alone is 121.7M nodes / 285 s).

### `arms/gate_parallel.py` — rung-level parallel feasibility + ledger

Exhausts every rung `M ∈ [floor, witness_m − 1]` (one `feasible` process per rung, N
workers) and certifies the witness rung, establishing `a(n) = witness_m`.

- **Independent rungs**: any dispatch order is sound; runs **hardest-first** (descending
  M — cost grows toward the feasibility edge) so the long pole starts immediately.
  Also `--order asc` for **walk mode** — lowest rungs first, each exhausted M raises the
  proven lower bound immediately. The a(11) walk uses asc + intra.
- **Ceiling independence**: the witness ceiling may be chosen from published data (e.g.
  Conway–Guy value) — the PROOF does not depend on how the ceiling was picked. If a
  rung below the ceiling unexpectedly finds a witness, the ceiling drops (a discovery,
  recorded as such).
- **Ledger**: same schema as `exhaustive.py --ledger`; completed rungs skipped on
  restart; merged across sequential/parallel runs.
- **Budget**: overall wall-clock; in-flight rungs get the remaining budget; unfinished
  rungs stay off the ledger (no negative claim).
- **Intra-rung parallelism** (`--intra K`): K concurrent `feasible` processes partition
  the rung's depth-1 subtrees; rung infeasible iff ALL infeasible; any witness wins
  (others killed); any budget-kill → no claim. Node counts are summed (exact: workers
  cover every node once, + K−1 root increments — mirror-tested).

**n=9 gate receipts** (cleared, `VR-4` §4): all 35 rungs `M ∈ [126, 160]` exhausted
infeasible; witness at 161 = CG-9; **16,230,800,798 nodes** total across sequential +
parallel runs. The ledger survived a genuine mid-run container restart with 25 rungs
held, resumed, and completed — the resumability receipt.

### `arms/conway_guy.py` — Conway–Guy sequence + set builder

Generator for the Conway–Guy sequence `u(n)` (OEIS A005318):
`u(0)=0, u(1)=1, u(k+1) = 2·u(k) − u(k − round(√(2k)))`. The n-element Conway–Guy set
is `{u(n) − u(j) : j = 0..n−1}`.

- **Sum-distinctness is a THEOREM** (Bohman 1996, 28 years after the conjecture).
  Certificate-verified here only for n ≤ 30 (bitset ceiling, see `verify_set.py`).
- **Calibration**: `CALIBRATION = [0, 1, 2, 4, 7, 13, 24, 44, 84, 161, 309, 594, 1164,
  2284]` (14/14 OEIS terms) is asserted in-code before any output. A recurrence
  transcription bug therefore fails loudly instead of silently shipping wrong sets.
- The CG sets are optimal at every exactly-known n (n ≤ 10) and **NOT optimal in
  general** — refuted by posted n = 12, 13 constructions; see
  [Erdős frontier](erdos-frontier.md).

### `arms/verify_set.py` — bitset sum-distinctness certificate

The shared verification core used by `conway_guy.py --verify`, `records.py`, and
`VR-5` (posted-set verification).

- **Incremental bitset**: represent the multiset of achievable subset sums as bits of a
  Python int (bit s set ⟺ some subset sums to s). Adding element e maps the sum-set S to
  `S ∪ (S+e)`; collision-free iff `(sums << e) & sums == 0`. Python ints are arbitrary
  precision, so this is **overflow-safe at any n** (the record ladder overflows int64
  near n ≈ 57).
- **Certificate ceiling**: `MAX_BITS_DEFAULT = 2_000_000_000` (~250 MB bitset). The
  guard refuses with a cost estimate at > 2×10⁹ bits (n ≈ 28–30 ceiling). Large-n
  sum-distinctness claims must rest on a THEOREM (e.g. Bohman 1996 for Conway–Guy
  sets), not on a certificate — and must be labeled at that grounding (per the
  epistemic-strata labeling in `VR-1` §conventions).

### `arms/records.py` — n ≥ 14 record ladder

`plans/P3_records.md` §3:

- **Baseline** (`--baseline LO HI`): CG-n certified sum-distinct by the exact bitset
  for `n = 14..25` (12 sets; largest CG-25, max element 8,311,101; raw:
  `results/records_baseline.json`). A certification failure contradicts Bohman 1996 and
  **STOPS the arm as self-suspect** (coded in). n=26..28 remain within the bitset guard;
  n ≥ 29 needs the MITM certificate arm (design: `docs/SEARCH_ENGINE_V3_DESIGN.md`).
- **Perturbation scan** (`--perturb LO HI --delta D --shift S`): bounded deterministic
  neighborhood around the CG structure — one element lowered by `delta ≤ D`, whole set
  shifted down by `s ≤ S`. For `n = 14..18`, 1280 candidates, **0 improvements**
  (`results/records_perturb.json`). Consistent with CG local rigidity; recorded so the
  neighborhood is not silently re-searched. Any future improvement is a TABLE ENTRY,
  never a claim on Bohman's asymptotic record (`VR-1` §2.5; the
  `record_claim_inflation` monitor watches the phrasing).

### `arms/constants_curve.py` — the empirical constant curve

`plans/P4_constants_curve.md` (DONE, `VR-6`):

- The curve `c(n) = best-known-max(n) / 2ⁿ` against the two theoretical rails (DFX
  floor below; Bohman 0.22002 above), from the exact table where known and the best
  verified constructions elsewhere.
- **Three-way provenance per row**: `exact` own re-derivation (n ≤ 9, `VR-3`/`VR-4`),
  `exact` external (n = 10 — Dyson's exhaustion, witness + uniqueness cross-checked in
  `VR-5`; kept OUT of the arms' non-circular `A_VERIFIED`), `upper_bound` (verified
  witnesses n = 11..13 per `VR-3`/`VR-5`; calibrated Conway–Guy `u(n)` beyond).
- **Exact Fraction arithmetic end-to-end** (overflow discipline, `VR-1` §2.6):
  `u(67) > 2^64` carried exactly; asserted in code + test. A float-first implementation
  would quietly lose the tail.
- **Outputs** (deterministic, content-derived only): `results/constant_curve.json`
  (the table with exact numerator/denominator strings) + `results/constant_curve.svg`
  (a dependency-free polyline rendering n = 1..40).

## Where the receipts live

| Receipt | File | Linked from |
|---|---|---|
| n=1..8 exact optima | `results/exhaustive_n8.json` + `exhaustive_n8.log` | `VR-3` §2 |
| n=9 gate (cleared) | `results/gate_n9.json` + `gate_n9_ledger.json` + `gate_n9_par.log` | `VR-4` §4 |
| n=10 gate (running) | `results/gate_n10_ledger.json` + `gate_n10_par.log` | `VR-4` §5 |
| a(11) walk | `results/n11_walk.log` + `results/n11_ledger.json` | `plans/P2` §2.1 |
| CG-14..25 baseline | `results/records_baseline.json` | `VR-7` §1 |
| Records perturbation | `results/records_perturb.json` | `VR-7` §2 |
| Constant curve | `results/constant_curve.json` + `constant_curve.svg` | `VR-6` |

## Build the C kernel before running gates

The Python `exhaustive.py --engine c` requires `arms/feasible` to exist. To build:

```bash
gcc -O2 -o arms/feasible arms/feasible.c
```

Both engines (`py`, the reference; `c`, the kernel) coexist and are regression-tested
together.
