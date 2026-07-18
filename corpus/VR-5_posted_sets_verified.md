# VR-5: Posted a(12)/a(13) witness sets independently certified; Dyson provenance corrected — amends VR-2

**Date:** 2026-07-17
**Status:** [V] verified — certificates in hand; amends VR-2 (Dyson repository citation)
**Arms:** arms/verify_set.py (bitset certificate)
**Plan:** plans/P3_records.md §2 (QUEUE S1)

## §1 The posted sets, retrieved with full provenance

OEIS A276661 (fetched via the OEIS JSON API, 2026-07-17) carries the third-party upper
bounds VR-2 imported at stratum `predicted`, WITH explicit witness sets:

- **a(12) <= 1157** — set {1157, 1152, 1149, 1147, 1145, 1141, 1130, 1108, 1069, 993,
  845, 554}. Provenance: Ven Popov, Nov 27 2025, edited Michael S. Branicky,
  Jan 25 2026 ("a potential optimal solution").
- **a(13) <= 2249** — set {2249, 2243, 2240, 2237, 2230, 2225, 2220, 2197, 2154, 2078,
  1931, 1637, 1077}. Same provenance chain.
- a(11) <= 594 via CG-11 (Branicky, Jan 24 2026) — already certified by our own
  generator in VR-3 §3.

## §2 Certificates

`arms/verify_set.py` (exact bitset, overflow-safe): **both sets are sum-distinct** —
n=12/max 1157 and n=13/max 2249. The bounds a(12) <= 1157 < 1164 = u(12) and
a(13) <= 2249 < 2284 = u(13) are therefore now **verified here**, not merely posted
(seeds re-stratified predicted → verified, this VR). Their OPTIMALITY remains open —
these are upper-bound witnesses; the exact windows (VR-2 §1) are unchanged:
924 <= a(12), 1716 <= a(13) (DFX floors).

Supplementary: Sungkawichai's doubling lemma (OEIS comment, Jan 24 2026 — if S solves
a(n) then {1} ∪ 2S witnesses a(n+1) <= 2·max(S)) verified on a live instance:
{1} ∪ 2·S12 is sum-distinct with n=13, max 2314 (weaker than the posted 2249, as
expected — the lemma is a general ladder, not a record).

## §3 Dyson provenance — correction to VR-2

VR-2 §1 cites Dyson's a(10) code as `github.com/pwdyson/distinct_subset_sum`. The
OEIS-curated link is **`github.com/pwdyson/erdos_1`** ("Distinct Subset Sum Search:
Computation of 10th term of OEIS A276661"), fetched and confirmed 2026-07-17; the URL
VR-2 carried came from the problem-selection research and could not be confirmed
(GitHub returns bot-403s to this environment's plain HTTP checks; the OEIS-linked repo
is confirmed by content). VR-2 carries an inline tag pointing here.

Two facts from the confirmed repository, both load-bearing:

1. **a(10)'s optimal set is UNIQUE and equals CG-10** ({148, 225, 265, 285, 296, 302,
   305, 307, 308, 309}) — exactly the witness our generator produced and certified in
   VR-3 §3.
2. **Dyson's compute scale: ~17 machines for ~2.5 weeks, plus ~4 weeks of revalidation
   with a second algorithm** — roughly 40+ machine-weeks. This externally calibrates
   our n=10 gate campaign (VR-4 §5): full single-machine re-derivation on 4 cores is
   out of reasonable reach, consistent with our measured rung costs.

## §4 Consequence for the A2 gate (planner decision required)

Given §3.2, the plan's original gate ("re-derive a(10)=309 exhaustively before any
n=11 wall-clock") is a multi-machine campaign, not a single-box task. A RESCOPE is
proposed at QUEUE Seq 8: gate = n=9 full re-derivation (DONE, VR-4) + n=10 partial
rung receipts (ledger, ongoing) + the value/witness/uniqueness cross-check against
Dyson (this VR). **M2 stays BLOCKED pending operator acknowledgment of the rescope** —
the discipline that a gate change is a planner/operator act, not an agent convenience.
