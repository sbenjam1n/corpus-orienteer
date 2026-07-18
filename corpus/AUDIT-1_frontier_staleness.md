# AUDIT-1: Frontier staleness — VR-1 §5's a-table stops at n=9; OEIS moved in Oct 2025

**Date:** 2026-07-16
**Status:** [V] verified — finding confirmed against primary sources; disposition: correction required (executed as VR-2)

## Finding

VR-1 §5 states "Exact values of a(n) are known for n <= 9" and "Conway–Guy sets match
the optimum at every known n." Both claims were stale AT THE TIME OF WRITING:

1. **a(10) = 309 is exact** — determined exhaustively by Paul W. Dyson (OEIS A276661,
   Oct 21 2025), with published search code (github.com/pwdyson/distinct_subset_sum).
   Receipt: OEIS A276661 entry + code repository, fetched 2026-07-16.
2. **Conway–Guy is beaten at n = 12 and n = 13** — OEIS A276661 comments (Nov 2025 –
   Jan 2026, Popov / Branicky / Sungkawichai) post sum-distinct sets giving
   a(12) <= 1157 < 1164 = u(12) and a(13) <= 2249 < 2284 = u(13). These are
   third-party posted constructions, not yet independently verified in this corpus.
   Receipt: OEIS A276661 comment history, fetched 2026-07-16.

## Why the tool matters here

This is the exact defect class the engine's drift detector and orient assertion-check
exist for: a correctly-spelled object (a(10), the a-table) carrying a stale predicate.
The finding was surfaced by the program's own adversarial verification pass (the
pitfalls lens of the problem-selection workflow), BEFORE any plan consumed VR-1's table.

## Disposition

Correction required: a new VR must (a) restate the current frontier with receipts,
(b) mark VR-1 §5 with an inline correction tag, (c) re-seed the ontology's a-table
facts. Executed as VR-2 (which closes AUDIT-1).
