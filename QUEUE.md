<!-- QUEUE.md — THE authoritative work-ordering for this program. PLANNER-WRITE-ONLY.
================================ WRITE RULE (PERMANENT) ================================
- Only the PLANNER (the human operator, or the seat they explicitly delegate) may set,
  add, remove, reorder, or re-prioritize items here. §1's ordering is the single source
  of truth for "what to work on next."
- The AGENT is READ-ONLY here: it executes the top UNBLOCKED item in its lane and NEVER
  edits this file. It reports progress and blockers via a VR/AUDIT in corpus/; the
  planner reconciles them into this queue. The agent MAY propose a reordering — in a VR,
  not here; a proposal is not a change until the planner makes it here.
- Every change to §1 increments **Queue Seq** and adds a one-line §6 history entry
  signed by the planner. An unsigned or non-planner edit is invalid by convention and
  reverted on sight.
- This file ORDERS; it does not DUPLICATE. Each item points to its plan + step and its
  tracking VR/AUDIT. Truth lives in the pointed-to doc; if they disagree, the doc wins
  and the planner fixes the pointer.
======================================================================================== -->

# QUEUE.md — Authoritative Work Queue

**Queue Seq:** 17
**Set by:** planner (program bootstrap)
**Date:** 2026-07-16
**Program:** the Erdős distinct-subset-sums ladder (erdosproblems.com #1, OEIS A276661)
run as a long-lived research program under the onto/audit RAG engine — the engine's own
`brief`/`orient`/`monitors` are this program's operating surfaces (dogfooding IS the demo).

---

## §0. STRATEGIC MAP

The conjecture itself is untouchable by computation ("cannot be resolved with a finite
computation" — VR-1 §1); the program's ladders are:

| Thread | Status | Queue loc | Pointer |
|---|---|---|---|
| **Exact ladder** — a(n) table (A276661): calibration n≤8 reproduced; a(9), a(10) witness-verified | calibration DONE (VR-3) | §1 A1 ✅ | plans/P1_calibration.md |
| — **a(11), the live frontier** (window [462, 594]) | ACTIVE, gated on engine upgrade | §1 A2 | plans/P2_frontier_n11.md |
| — a(12), a(13) posted third-party bounds: independent verification | ON-DECK | §2 | plans/P3_records.md §2 |
| **Record ladder** — constructions n ≥ 14 (CG perturbation, ILP, local search) | BACKLOG (after A2's engine work lands) | §4 | plans/P3_records.md |
| **Constant curve** — empirical a(n)/2^n vs Bohman/DFX | BACKLOG (cheap, fill-in) | §4 | plans/P4_constants_curve.md |
| **OpenWiki brain integration** — engine artifacts feeding a LangChain OpenWiki wiki | ON-DECK (independent lane) | §2 | plans/P5_openwiki_brain.md; adapters/openwiki/ |
| Modular side ladder (arXiv:2308.03748) | PARKED (different verification predicate — VR-1 sources) | — | — |
| **Engine: corpus tiers** | **COMPLETE (M1–M5, Seq 11)** — substrate; version supersession; capture ledger + receipt discipline; thread chunking/parties/detector scoping; authority-weighted search + orient tier blocks; fixture_tiered freeze (8 e2e asserts) | done | docs/CORPUS_TIERS_DESIGN.md; plans/P6_corpus_tiers.md v1.4 |

## §0.5 PINNED PROTOCOLS

### P1 — Index-document protocol
`corpus/` is the append-only truth (VR-N results, AUDIT-N findings; contract:
`docs/rag_corpus_format.md`). Conclusions change only via NEW documents carrying
correction verbs in metadata; corrected docs get inline `[CORRECTED per VR-N]` tags.
Standing documents (this file, README, plans) POINT into the corpus and never
restate its numbers without a VR citation; edits to standing docs that change a claim
carry a versioned bracket tag (`[vX: CORRECTED per VR-N]`). The engine's build
(`./rag rebuild`) is the index; `data/rag/` is derived, never authoritative.

### P2 — Working protocol (the loop)
One iteration = **orient → execute → record → reconcile**:
1. `./rag brief` (session warm start) and, before acting on any plan/VR set,
   `./rag orient <docs>` — its superseded-citation and stale-assertion findings are
   mandatory reads (a doc absent from its ⚠ list is not thereby certified).
2. Execute the top UNBLOCKED item in your lane (§1), inside its plan's step contract.
3. Record the result as a new VR (or finding as AUDIT-N) with receipts: the exact
   command, the raw artifact path under results/, and counts as returned — never
   summarized numbers without their source. Run `./rag rebuild`; check `./rag monitors`
   — a monitor you flipped (either way) is part of the result and named in the VR.
4. The planner reconciles: plan step boxes ticked with artifact paths, queue statuses
   updated (here), seeds re-seeded via the gated `/ontology-reconcile` path — never
   hand-edited silently.

### P3 — Authority chain
- **Planner** (human operator or explicit delegate): writes QUEUE.md and plans/;
  merges; adjudicates. The only seat that may promote backlog → active.
- **Agent**: executes queue items; writes VR-N into corpus/; read-only on QUEUE.md and
  on other documents' conclusions (corrections are new docs, per P1).
- **Auditor** (a role, not necessarily a separate person/session): writes AUDIT-N
  findings about existing docs — finds, never fixes; every claim carries the command it
  rests on and the count it returned. A zero-finding pass must attempt one adversarial
  refutation of the brief's highest-risk item and record the attempt.
- **Seeds** (domains/erdos1/): authoritative curated facts. The indexer VALIDATES them
  (drift), never extracts headline facts from prose. Seed edits are planner-gated.
- Third-party results (OEIS comments, posted constructions) enter at stratum
  `predicted` until independently verified here (e.g. a(12) <= 1157, VR-2 §2).

### P4 — Test strategy
Adapted from the source program's three standing checks (each guards a demonstrated
failure mode; docs/ontology_rag_assessment.md carries the lineage):
1. **Wrong value** → the calibration gate: no arm's output counts until the arm
   reproduces every cheaply reachable published value (VR-3 = the standing example;
   a(1..8) exhaustive 8/8, CG generator 14/14 OEIS terms). Canonical values are
   imported from seeds, never transcribed inline.
2. **Wrong binding** → conventions are pinned in VR-1 §2 (0 excluded, empty set counts,
   `=` vs `<=` vocabulary, A276661-vs-A005318 off-by-one); the seeds bind values to
   objects; drift + the orient assertion check catch stale/misbound numbers.
3. **Unnecessary/overclaimed computation** → the asymmetric-proof-burden rule (VR-1
   §2.4: exact claims need named, conservative prunes), the claim-inflation guard
   (VR-1 §2.5), and the `frontier_exact_claim_needs_exhaustion` +
   `record_claim_inflation` monitors, evaluated every build.
Cross-cutting: a detector's 0 is not a proof; candidates are regions to READ, never
verdicts; engine changes require the engine suite (43 tests) + the fixture
byte-determinism check; the corpus must rebuild with 0 errors + steady-state
byte-determinism (CI, .github/workflows/rag-tests.yml).

---

## §1. ACTIVE QUEUE (ordered; the agent runs the top UNBLOCKED item in its lane)

### AGENT lane

| # | Item | Status | Source (plan + step) | Gate / next checkpoint | Tracking |
|---|------|--------|----------------------|------------------------|----------|
| A4 | **Engine v3** (intra-rung parallelism → MITM feasibility → proof-gated dominance → MITM certificates) | **M1 DONE + VALIDATED** (intra-4 = identical verdicts, 3.3x); **M2 RESOLVED (VR-8): MITM analyzed → no node-count win → design corrected → redirected to the representation-method engine (separate proof-gated plan, P8 when promoted)**. Intra-4 walk RUNNING as the sound single-machine path | plans/P7_engine_v3.md v1.1 | M1 banked; M2 resolved. Real lever (representation method) is a future plan | VR-8 (M2); VR-9+ (walk rungs) |


| # | Item | Status | Source (plan + step) | Gate / next checkpoint | Tracking |
|---|------|--------|----------------------|------------------------|----------|
| A1 | Calibration: exhaustive a(1..8), witness certs a(9..11), CG generator 14/14 | **DONE (VR-3)** — 8/8 published-table agreement; n=8 = 121.7M nodes / 285s; certificate ceiling documented | plans/P1_calibration.md (all steps) | — | VR-3 |
| A2 | **a(11) campaign, phase M1: engine upgrade + gate** — admissible DFX-floor + stronger prunes; GATE = re-derive a(10)=309 exhaustively (cross-check vs Dyson's published code) BEFORE any n=11 wall-clock | ACTIVE — engine v2 BUILT (P3/P4/P5 prunes, DFX floor, M-ledger; C kernel = exact DFS mirror, per-M node-count equality verified, ~19× wall; n≤8 regression identical) — **n=9 gate CLEARED (a(9)=161 exact, 16.23B nodes)**; n=10 gate RUNNING as a standing campaign (ledger-checkpointed, projected tens of core-hours) | plans/P2_frontier_n11.md M1 (1.1–1.3, 1.5 ✅; 1.4 standing campaign) | the a(10) gate; STOP if it disagrees with 309 (that is a finding, not a nuisance) | VR-4 |
| A3 | a(11) window walk | **CLOSED (VR-9): beyond single-box compute** — floor rung M=462 ran ~42min at intra-4 without closing; 0 rungs proven; bound a(11)≥462 stands on the DFX THEOREM (free), not exhaustion. Window [462,594] unchanged. Re-open needs the representation-method engine (VR-8 §4) or multi-machine — out of demo scope | plans/P2_frontier_n11.md (closed); VR-8; VR-9 | — | VR-9 |

### PLANNER lane (runs in parallel; agent does not wait on these)

| # | Item | Status | Source | Tracking |
|---|------|--------|--------|----------|
| S1 | Independent verification of posted a(12)/a(13) upper-bound sets | **DONE (VR-5)** — both sets certified; seeds re-stratified predicted→verified; Dyson repo citation corrected (amends VR-2); doubling lemma spot-verified | plans/P3_records.md §2 | VR-5 |
| S2 | OpenWiki brain wiring | **COMPLETE (P5 v1.4, Seq 16)** — Layer A emitter+prestep+AGENTS.md; validator port; **live capture done (MiniMax-M3): generated wiki reflects the live corpus incl. both correction arcs**; Layer C PR sketch | plans/P5_openwiki_brain.md v1.4; adapters/openwiki/capture_example/ | — |

## §2. ON-DECK
S1, S2 (above); **P6 corpus tiers** (operator-raised 2026-07-16: correspondence threads,
versioned papers/outlines, and derived artifacts each need their own supersession/claim/
receipt semantics — design docs/CORPUS_TIERS_DESIGN.md, plan plans/P6_corpus_tiers.md;
becomes URGENT before P5's generated wiki lands, since that wiki is a derived tier that
must not be re-ingested as source); records ladder n≥14 kickoff after A2's engine work
exists (it reuses the same feasibility engine).

## §3. BLOCKED
A3 (on A2's gate). Nothing else.

## §4. BACKLOG (planner promotes; agent never self-serves from here)
Records n≥14 (P3); ~~constants curve (P4)~~ **P4 DONE (VR-6)**; MITM/FFT certificate arm for 30<n≤40 (extends
the §P4 ceiling — design first); **stronger n=11 rung engine** (MITM feasibility /
Dyson-style bidirectional search — promote if the A3 walk stalls on its first rungs);
**n=10 full exhaustion** (idle-window resumption of results/gate_n10_ledger.json —
evidence value only, gate already satisfied); modular side ladder (parked, see §0).

## §5. ID LEDGER
VR-1..3, AUDIT-1 minted (bootstrap). Next: VR-4 (A2 gate run), AUDIT-2, RF-stream not
yet started (single-operator program; referee seat activates when a second session joins).

## §6. HISTORY
| Seq | Date | Change | By |
|---|---|---|---|
| 1 | 2026-07-16 | Bootstrap: protocols pinned, A1 banked (VR-3), A2/A3 + S1/S2 seeded | planner |
| 2 | 2026-07-16 | Corpus-tiers gap raised by operator; design + P6 written; queued ON-DECK, flagged as a P5 prerequisite | planner |
| 3 | 2026-07-16 | A2 engine v2 built (prunes P3–P5, DFX floor, ledger, C mirror kernel); n=9 gate launched. P6 M1 executed (substrate + tests + demo tiers.json) | planner |
| 17 | 2026-07-17 | A3 CLOSED honestly (VR-9): a(11) frontier beyond single-box compute (42min floor-rung no-close + VR-8 analysis + Dyson 40-machine-week calibration); walk halted, orphan-reap bug fixed, durable trigger retired. Every queue item now resolved | planner |
| 16 | 2026-07-17 | P5 COMPLETE: live OpenWiki capture (funded MiniMax key) — generated wiki correctly reflects the live corpus state incl. correction arcs; the last externally-blocked item cleared | planner |
| 15 | 2026-07-17 | P7 M2 RESOLVED via analysis (VR-8): naive MITM gives no node-count win, design §A.1 corrected, redirected — no broken engine shipped. Walk = sound path | planner |
| 14 | 2026-07-17 | P7 M1 validated (intra-4 n=9 gate identical verdicts + 3.3x); broken-stderr hardening banked | planner |
| 13 | 2026-07-17 | Planner-seat correction (operator): tool-work needs no two-seat ceremony — P7 created + ACTIVATED directly; M1 built same turn | planner |
| 12 | 2026-07-17 | Queue cleared of all completables: records opened (VR-7), v3 engine designed (stall trigger), OKF pages validated against OpenWiki's own validator (2.4a). Remaining: A3 compute (standing), v3 impl (needs promotion), 2.4b + n=10 (operator/multi-machine) | planner |
| 11 | 2026-07-17 | Implementation queue worked through: P6 M4+M5 (thread parsing, scoping, weighting, fixture freeze) + P5 3.2 (upstream PR sketch). P6 COMPLETE | planner |
| 10 | 2026-07-17 | P4 done (VR-6: constant curve + rails + overflow receipts) | planner |
| 9 | 2026-07-17 | **Operator ACKED the A2 gate rescope** — A2 flipped DONE; A3 (a(11) walk) UNBLOCKED + launched (asc ledger walk); n=10 exhaustion demoted to §4 idle-window item (ledger preserved) | planner |
| 8 | 2026-07-17 | S1 done (VR-5: posted sets certified, seeds verified, VR-2 citation amended); A2 gate rescope PROPOSED on Dyson compute evidence — operator ack pending | planner |
| 7 | 2026-07-17 | P5 Layer A executed (OKF emitter + CI prestep + AGENTS.md contract; wiki registered as derived tier) | planner |
| 6 | 2026-07-17 | P6 M3 executed (capture ledger, receipt discipline, query/brief surfaces); arcs determinism bug found+fixed+backported | planner |
| 5 | 2026-07-16 | P6 M2 executed in parallel with the n=10 campaign (version-supersession synthesis + orient verdicts) | planner |
| 4 | 2026-07-16 | VR-4 banked: a(9)=161 re-derived (gate cleared); n=10 gate opened as a standing campaign; a9 seed provenance upgraded | planner |
