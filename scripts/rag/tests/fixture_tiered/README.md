# fixture_tiered — the tier-semantics reference deployment

The executable freeze of docs/CORPUS_TIERS_DESIGN.md (P6 M4/M5), complementing
`../fixture/` (which stays single-tier as the backward-compatibility reference).
Exercised by `test_fixture_tiered_e2e.py`.

| Piece | Exercises |
|---|---|
| corpus/VR-1 (captures THREAD-1 R1; SETTLED **with** independent route) | capture edge (metadata-only); settled-monitor negative control |
| corpus/VR-2 ("confirmed per THREAD-1 R2"; cites papers/outline_v1.md) | receipt-laundering candidate; versioned-doc citation |
| threads/THREAD-1 (R1 Alice "SETTLED" no route · R2 Bob tail=7 · R3 Alice tail=8) | round chunking; party parsing; detector scoping (SETTLED must NOT fire — threads declare `detectors: []`); cross-party value attribution (7 vs 8 kept distinct by party); unreconciled rounds R2/R3 |
| papers/outline_v1 vs v2 + archive/v0 | version-number supersession (v2 current, v1 superseded, v0 archived) |
| derived/VR-99 | `indexed: false` exclusion (a vr-shaped doc in a derived root never indexed) |
| two full builds | byte-determinism modulo the temp-root path |
