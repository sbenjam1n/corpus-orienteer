# VR-6: The empirical constant curve c(n) = best-known-max/2^n (P4)

**Date:** 2026-07-17
**Status:** [V] verified — derived artifact from already-banked values; no new claims
**Arms:** arms/constants_curve.py
**Plan:** plans/P4_constants_curve.md

## §1 What it is

results/constant_curve.json + constant_curve.svg: c(n) for n = 1..40 against the two
rails (DFX floor binom(n, floor(n/2))/2^n below; Bohman 0.22002 above). Exact Fraction
arithmetic end-to-end; provenance three-way per row: `exact` own re-derivation
(n <= 9, VR-3/VR-4), `exact` external (n = 10 — Dyson's exhaustion, witness +
uniqueness cross-checked in VR-5; kept OUT of the arms' non-circular A_VERIFIED
table), `upper_bound` (verified witnesses n = 11..13 per VR-3/VR-5; calibrated
Conway–Guy u(n) beyond).

## §2 Receipts

- c(10) = 309/1024 = 0.30176; c(3) = 1/2 exactly (golden-tested).
- Overflow discipline (VR-1 §2.6) exercised: u(67) = 34808838084768972989 > 2^64,
  carried exactly (asserted in code + test). Matches Lunnon's value as quoted on
  OEIS A276661 ("a(67) < 34808838084768972989 = A005318(67)").
- Rails sane: DFX floor <= best-known at every n (tested).
- Deterministic: content-derived only; golden + overflow tests in tests/test_arms.py.

## §3 Reading

The curve visibly sags from c(1) = 0.5 toward the 0.22 rail as n grows (c(10) ≈ 0.302,
CG tail → ~0.235) — the gap between the best constructions and the DFX floor
(~0.7979/sqrt(n) at n = 40 ≈ 0.126) is the open territory of erdosproblems.com #1.
Each future exact value or record entry updates one row; the artifact regenerates
byte-identically otherwise.
