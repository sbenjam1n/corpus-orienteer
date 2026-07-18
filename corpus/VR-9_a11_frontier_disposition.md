# VR-9: a(11) exact frontier is beyond single-box compute — A3 closed honestly (0 rungs proven)

**Date:** 2026-07-17
**Status:** [V] verified — negative/disposition; NO new bound proven (states what was and was NOT established)
**Arms:** arms/gate_parallel.py (--intra 4 walk); arms/feasible.c
**Plan:** plans/P2_frontier_n11.md M2 (closed); confirms VR-8

## §1 What the walk did — and did not — establish

The a(11) window walk ran under intra-4 (P7 M1, 3.3×) ascending from the DFX floor 462.
**It closed ZERO rungs.** The first rung, M=462, ran **~42 minutes of 4-core wall-clock
without exhausting** (results/n11_ledger.json holds only the ceiling witness at 594; no
infeasible rung). Therefore this VR proves **no new lower bound**.

The standing bound **a(11) ≥ 462 rests on the Dubroff–Fox–Xu THEOREM** (binom(11,5)=462,
arXiv:2006.12988) — cited for free, NOT on any exhaustion performed here. The walk would
only have pushed it to 463 by exhausting M=462; that single +1 improvement did not
complete in practical single-box time.

## §2 Why — and why this is the expected, correct outcome

VR-8 established that the engine cannot be asymptotically accelerated for infeasibility
rungs (naive MITM gives no node-count win; the representation-method engine is
research-grade). The empirical stall confirms it: an a(11) rung near the DFX floor is
large enough that 4 cores do not exhaust it in tens of minutes. Calibration: a(10) = 309
took Dyson ~17 machines × 2.5 weeks + 4 weeks revalidation (~40 machine-weeks, VR-5 §3);
a(11) is strictly harder. A single 4-core box advancing the EXACT frontier was never in
reach — which is precisely why erdosproblems.com #1 is open.

## §3 Disposition (A3 closed)

- **A3 (a(11) exact-ladder walk) is CLOSED as "beyond single-box compute."** Not
  abandoned in error — closed with a receipt (42-min no-close on the floor rung) and the
  VR-8 analysis behind it. Re-opening requires either the representation-method engine
  (VR-8 §4 — a future proof-gated plan) or genuine multi-machine compute; both are out of
  this demo's scope.
- **The exact-ladder demo value stands on what IS certified**: a(1..8) re-derived
  exhaustively here (VR-3/VR-4), a(9)=161 gate cleared (VR-4), a(10)=309 cross-checked
  (VR-5), and the verified upper bounds a(11) ≤ 594 / a(12) ≤ 1157 / a(13) ≤ 2249
  (VR-3/VR-5). That is a complete, honest, provenance-linked table — the demo does not
  need a new a(11) rung to be a real research program.
- **The proven window for a(11) is unchanged: [462, 594]** (both endpoints from prior
  results — DFX theorem below, our CG-11 certificate above).

## §4 Engineering note (banked)

Stopping the walk surfaced an orphan-process bug: killing the driver left its per-rung
`feasible` children running under their own budget. Fixed — `gate_parallel.py` now reaps
live kernel children on SIGTERM/SIGINT/atexit, so a stopped or restarted driver never
leaks compute. The durable self-heal trigger is retired (the walk is deliberately halted,
not failed).
