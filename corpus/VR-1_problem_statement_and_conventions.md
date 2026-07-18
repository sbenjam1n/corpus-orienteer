# VR-1: Program charter — the Erdős distinct subset sums problem, conventions, and initial frontier survey

**Date:** 2026-07-16
**Status:** [V] verified — charter + source survey; frontier table corrected per VR-2
**Author:** planner (research workflow, adversarially verified where noted)

## §1 The problem

A set A of positive integers is **sum-distinct** if all 2^|A| subset sums are distinct
(the empty set counts, with sum 0). Erdős's "first serious problem" (erdosproblems.com
**#1**, $500 prize) asks: must the largest element of an n-element sum-distinct set be at
least c·2^n for an absolute constant c > 0?

The problem is OPEN and — per erdosproblems.com/1 (fetched 2026-07-16) — **"cannot be
resolved with a finite computation."** This program therefore never claims to attack the
conjecture itself. Its computational objects are:

- **The exact-optimum table** a(n) = the minimal possible largest element of an
  n-element sum-distinct set (OEIS A276661). Each exactly-determined a(n) is a permanent,
  independently checkable artifact.
- **Construction records** at larger n (Conway–Guy-type families and perturbations).
- **The empirical constant curve** a(n)/2^n against the Bohman and DFX bounds.

## §2 Conventions (binding for every VR in this corpus)

1. Elements are **distinct positive integers** (0 is excluded: {0} collides with {}).
2. All 2^n subsets count, including the empty set. Duplicate elements are excluded by
   "set" (two equal singletons collide).
3. Exact values are written `a(n) = v`; bounds are written `a(n) <= v` / `a(n) >= v`
   (ASCII, greppable; the drift detectors key on these forms).
4. **Asymmetric proof burden**: the positive side of `a(n) = v` is a witness set
   (trivially certifiable); the negative side ("no set with max <= v−1") rests on
   SEARCH COMPLETENESS — every exhaustion claim must name its prunes and argue each is
   conservative. An exact claim without an exhaustion receipt is not a result.
5. **Claim-inflation guard**: beating 0.22002·2^n at a single n does NOT improve the
   Bohman bound (an asymptotic family record). Single-n improvements are table entries.
6. **Overflow discipline**: subset-sum totals exceed int64 near n ≈ 57 and the Bohman
   bound value exceeds uint64 at n = 67. All arms use arbitrary-precision arithmetic
   (Python int); any future C port must justify its integer widths per-n.
7. **Certificate ceiling**: the bitset certificate (arms/verify_set.py) costs O(total
   sum) bits ≈ n·0.22·2^n — feasible only to n ≈ 30. Beyond that, sum-distinctness
   claims must cite a THEOREM (e.g. Bohman 1996 for Conway–Guy sets) and be labeled at
   that stratum, never presented as certificate-verified.

## §3 The classical ladder

The Conway–Guy sequence u(n) (OEIS A005318): u(0)=0, u(1)=1,
u(k+1) = 2u(k) − u(k − r(k)), r(k) = round(sqrt(2k)). The n-element **Conway–Guy set**
CG-n = {u(n) − u(j) : j < n} is sum-distinct for every n (conjectured by Conway–Guy
1968, **proved by Bohman 1996** — 28 years later; a standing reminder that long-lived
plausible claims in this literature have gone unproven for decades). First terms:

u(0..13) = 0, 1, 2, 4, 7, 13, 24, 44, 84, 161, 309, 594, 1164, 2284.

## §4 Bounds context

- Lower: a(n) >= binom(n, floor(n/2)) (Dubroff–Fox–Xu, arXiv:2006.12988) — the
  DFX bound; asymptotically ~ sqrt(2/pi)·2^n/sqrt(n) (constant first by Elkies–Gleason,
  unpublished). The program's own exhaustion floors use only the weaker self-contained
  doubling bound ceil((2^n − 1)/n), so our negative claims rest on our own arithmetic.
- Upper: max element <= 0.22002·2^n asymptotically (Bohman 1998) — unbeaten.

## §5 Initial frontier table (as first researched)

**[CORRECTED per VR-2 — this survey was stale on arrival; kept verbatim per the
append-only discipline]** Exact values of a(n) are known for n <= 9:
a(1)=1, a(2)=2, a(3)=4, a(4)=7, a(5)=13, a(6)=24, a(7)=44, a(8)=84 (Lunnon 1988),
a(9)=161 (Grossman). Conway–Guy sets match the optimum at every known n, and u(n) is
the natural upper-bound candidate for all larger n.

## §6 Sources

- https://www.erdosproblems.com/1 (OPEN, $500; fetched 2026-07-16)
- https://oeis.org/A276661 (a(n) table) · https://oeis.org/A005318 (Conway–Guy)
- Bohman 1996 (CG sets sum-distinct), Bohman 1998 (0.22002·2^n)
- Dubroff–Fox–Xu, arXiv:2006.12988
- Adversarial still-open sweep 2026-07-16: arXiv full-text 2022–2026, the
  teorth/erdosproblems AI-contributions tracker (no entry for #1), press/blog sweep —
  all corroborate OPEN. Details in VR-2 §5.
