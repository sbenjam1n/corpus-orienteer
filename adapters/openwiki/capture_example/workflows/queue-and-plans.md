---
type: Workflow
title: Queue and plans — QUEUE.md governance, plans/P1..P7, current state
description: "How QUEUE.md and plans/P1..P7 govern the demo program: QUEUE.md is planner-write-only (agent is read-only there); plans are living documents with append-only history, version bumps, and a claims registry whose entries require artifacts. Plus the current state of A1..A4 (agent lane), S1..S2 (planner lane), and the §0 strategic map of ladders."
tags: [openwiki, workflow, queue, plans, governance]
---

# Queue and plans

The demo program is governed by two top-level coordination artifacts: **`QUEUE.md`**
(planner-write-only work queue) and **`plans/P1..P7.md`** (living plans with claims
registries). The working protocol that consumes them is in
[Working protocol](working-protocol.md).

## QUEUE.md — planner-write-only

`QUEUE.md` is the **authoritative work-ordering** for the program. It is
**planner-write-only** by permanent convention:

> Only the PLANNER (the human operator, or the seat they explicitly delegate) may set,
> add, remove, reorder, or re-prioritize items here. §1's ordering is the single source
> of truth for "what to work on next."
>
> The AGENT is READ-ONLY here: it executes the top UNBLOCKED item in its lane and
> NEVER edits this file. It reports progress and blockers via a VR/AUDIT in `corpus/`;
> the planner reconciles them into this queue. The agent MAY propose a reordering — in
> a VR, not here; a proposal is not a change until the planner makes it here.
>
> Every change to §1 increments **Queue Seq** and adds a one-line §6 history entry
> signed by the planner. An unsigned or non-planner edit is invalid by convention and
> reverted on sight.

§1 ordering ORDERS — it never DUPLICATES. Each item points to its plan + step and its
tracking VR/AUDIT. Truth lives in the pointed-to doc; if they disagree, the doc wins
and the planner fixes the pointer.

### Section map

- **§0 Strategic map** — the four ladders (exact / records / constant / OpenWiki) +
  parked items; pinned protocols cross-reference.
- **§0.5 Pinned protocols** — P1 index, P2 working loop, P3 authority chain, P4 test
  strategy.
- **§1 Active queue** — agent lane (`A1..A4`) and planner lane (`S1..S2`), ordered.
- **§2 On-deck** — promoted-but-not-yet-active.
- **§3 Blocked** — explicitly named blockers.
- **§4 Backlog** — planner promotes; agent never self-serves from here.
- **§5 ID ledger** — VR-N / AUDIT-N / RF-stream minting.
- **§6 History** — Seq-stamped, signed by the planner.

## Plans — `plans/P1..P7`

Plans are living documents with a pinned edit protocol (from `plans/P1_calibration.md`):

> Living document: never overwrite history; bump the version on substantive edits; log in
> §4. Claims enter §3 only with a verifying artifact; until then the slot reads
> `[PENDING: <artifact> -> <what it must show>]`.

Every plan has:

1. **§1 Objective** — what the plan produces and why.
2. **§2 Phases / stages** — each step checked off (`- [x]` vs `- [ ]`) with its
   artifact (file path or VR reference).
3. **§3 Claims registry** — `| # | Claim | Status | Artifact |` rows; claim only enters
   with a verifying artifact.
4. **§4 (or later) Version history** — append-only table of `| Date | Version | Change |`.

### The plan set

| Plan | Purpose | Status |
|---|---|---|
| [`P1_calibration.md`](../../plans/P1_calibration.md) | "Reproduce everything cheap before extending anything" — the calibration gate standing contract for any new arm | DONE (all steps, `VR-3`) |
| [`P2_frontier_n11.md`](../../plans/P2_frontier_n11.md) | The a(11) campaign — engine upgrade + n=10 gate (M1) and the a(11) walk (M2) | ACTIVE (M1 done except 1.4; M2 walk launched) |
| [`P3_records.md`](../../plans/P3_records.md) | Verify posted a(12)/a(13) sets (§2) + records ladder n ≥ 14 (§3) | §2 DONE (`VR-5`); §3 OPENED (`VR-7`: baseline + first neighborhood) |
| [`P4_constants_curve.md`](../../plans/P4_constants_curve.md) | The empirical constant curve `a(n)/2^n` against the DFX + Bohman rails | DONE (`VR-6`, Seq 10) |
| [`P5_openwiki_brain.md`](../../plans/P5_openwiki_brain.md) | OpenWiki brain integration (Layers A / B / C) | Layer A 2.1–2.3 DONE; 2.4 split: 2.4(a) DONE (validator port), 2.4(b) operator-gated; Layer B DONE; Layer C spec shipped |
| [`P6_corpus_tiers.md`](../../plans/P6_corpus_tiers.md) | Heterogeneous document populations under one orientation surface | COMPLETE (M1–M5, Seq 11) |
| [`P7_engine_v3.md`](../../plans/P7_engine_v3.md) | Search engine v3 — intra-rung parallelism, MITM feasibility, MITM certificates | ACTIVE (M1 DONE + VALIDATED; M2 RESOLVED via `VR-8` → redirected to representation-method plan; M3/M4 backlog) |

The design docs behind two plans are pinned in `docs/`:

- `docs/CORPUS_TIERS_DESIGN.md` — design behind `P6` (read first).
- `docs/SEARCH_ENGINE_V3_DESIGN.md` — design behind `P7` (read first). **§A.1 is
  corrected by `VR-8`**: naive MITM is not the lever.

## Current state (from `QUEUE.md` Seq 15, 2026-07-17)

### Agent lane

| # | Item | Status | Tracking |
|---|---|---|---|
| **A4** | Engine v3 — intra-rung parallelism + MITM feasibility + MITM certificates | **M1 DONE + VALIDATED** (intra-4 = identical verdicts, 3.3×); **M2 RESOLVED (`VR-8`)**: MITM analyzed → no node-count win → design `§A.1` corrected → redirected to representation-method engine (separate proof-gated plan, P8 when promoted). Intra-4 walk RUNNING as the sound single-machine path | `VR-8` (M2); `VR-9+` (walk rungs) |
| **A1** | Calibration: exhaustive a(1..8), witness certs a(9..11), CG generator 14/14 | **DONE** (`VR-3`) — 8/8 published-table agreement; n=8 = 121.7M nodes / 285s; certificate ceiling documented | `VR-3` |
| **A2** | a(11) campaign phase M1 — engine upgrade + n=10 gate | engine v2 BUILT (P3/P4/P5 prunes, DFX floor, M-ledger; C kernel = exact DFS mirror, per-M node-count equality verified, ~19× wall; n≤8 regression identical) — **n=9 gate CLEARED (a(9)=161 exact, 16.23B nodes)**; n=10 gate RUNNING as a standing campaign (ledger-checkpointed, projected tens of core-hours) | `VR-4` |
| **A3** | a(11) window walk — THE FRONTIER CAMPAIGN, ACTIVE (top of lane) — ascending ledger walk from DFX floor 462 toward 594; each contiguously exhausted rung raises the proven lower bound as a permanent artifact | RUNNING (`gate_parallel --order asc --intra 4`, 4 workers, 4h budget windows, ledger `results/n11_ledger.json`) | first artifact = first closed rung VR (`VR-6+`) |

### Planner lane

| # | Item | Status | Tracking |
|---|---|---|---|
| **S1** | Independent verification of posted a(12)/a(13) upper-bound sets | **DONE** (`VR-5`) — both sets certified; seeds re-stratified predicted → verified; Dyson repo citation corrected; doubling lemma spot-verified | `VR-5` |
| **S2** | OpenWiki brain wiring (Layer A sidecar on this repo) | **Layer A DONE** (`emit_okf` + prestep + `AGENTS.md`; wiki = derived tier); 2.4 live capture needs an OpenWiki install | — |

### On-deck / backlog / blocked

- **§2 On-deck**: S1, S2; **P6 corpus tiers** (`docs/CORPUS_TIERS_DESIGN.md`,
  `plans/P6_corpus_tiers.md`) — operator-raised 2026-07-16; **URGENT before P5's
  generated wiki lands**, since that wiki is a derived tier that must not be
  re-ingested as source; records ladder n ≥ 14 kickoff after A2's engine work exists
  (it reuses the same feasibility engine).
- **§3 Blocked**: A3 (on A2's gate). Nothing else.
- **§4 Backlog** (planner promotes; agent never self-serves): Records n ≥ 14 (`P3`);
  MITM/FFT certificate arm for 30 < n ≤ 40 (extends the `P4` ceiling — design first);
  stronger n=11 rung engine (MITM feasibility / Dyson-style bidirectional search —
  promote if the A3 walk stalls on its first rungs); n=10 full exhaustion (idle-window
  resumption of `results/gate_n10_ledger.json` — evidence value only, gate already
  satisfied); modular side ladder (parked, see §0).

## How an agent should use this page

1. Before each work block, read the top of `QUEUE.md` §1 to see what is currently top
   in your lane.
2. Read the relevant plan (`plans/P*.md`) to see the current state of its steps.
3. Use `./rag orient` to load the orientation artifact for the plan + any VR/AUDIT ids
   it cites ([working protocol](working-protocol.md)).
4. Execute the top UNBLOCKED step, record as a VR, and let the planner reconcile.

Do **not** edit `QUEUE.md` or reorder plan steps. Propose changes in a VR and let the
planner reconcile.
