---
type: Workflow
title: Working protocol — orient, execute, record, reconcile
description: "The orient → execute → record → reconcile loop from QUEUE.md §0.5 P2; the header contract for new VR/AUDIT documents (docs/rag_corpus_format.md); how the supersession graph extracts correction vs reference edges from metadata; the authority chain (planner, agent, auditor, seeds, third-party); and the discipline that a detector's zero is not a certification."
tags: [openwiki, workflow, protocol, corpus, vr, audit, supersession]
---

# Working protocol

The demo program operates under `QUEUE.md` §0.5 — four pinned protocols (P1–P4) plus
the §0 strategic map and §1 active queue. This page distills the parts an agent must
internalize to act on the corpus; the queue and plans themselves are tracked in
[Queue and plans](queue-and-plans.md).

## The orient → execute → record → reconcile loop (P2)

One iteration of the program is exactly four steps:

1. **Orient.** Run `./rag brief` (session warm start) and, before acting on any plan or
   VR set, `./rag orient <docs>` — its superseded-citation and stale-assertion findings
   are **mandatory reads**. A doc absent from the ⚠ list is not thereby certified.
2. **Execute.** Execute the top UNBLOCKED item in your lane (`QUEUE.md` §1), inside
   its plan's step contract.
3. **Record.** Record the result as a new `VR-N` (or finding as `AUDIT-N`) **with
   receipts**: the exact command, the raw artifact path under `results/`, and counts as
   returned — never summarized numbers without their source. Run `./rag rebuild`; check
   `./rag monitors` — a monitor you flipped (either way) is part of the result and
   named in the VR.
4. **Reconcile.** The planner reconciles: plan step boxes ticked with artifact paths,
   queue statuses updated, seeds re-seeded via the gated `/ontology-reconcile` path —
   **never hand-edited silently**.

## The header contract for new VR / AUDIT documents

Every new corpus document opens with a structured header. The contract is pinned in
`docs/rag_corpus_format.md` §2; deviations break the engine's parsing.

```markdown
# VR-4: C_1 period correction — corrects VR-3

**Date:** 2026-01-08
**Status:** [V] verified — correction; corrects VR-3
```

| Field | Required | Parsed as |
|---|---|---|
| `# <ID>: <title>` (first line) | yes | title; ALSO metadata for correction edges |
| `**Date:** YYYY-MM-DD` | yes | document date; drives timelines and the corpus stamp |
| `**Status:** [X] …` | yes | commitment marker + free text; metadata for correction edges |
| `**Version:**`, `**Author:**`, `**Supersession:**` | optional | version history; Supersession is a metadata line for correction edges |

**Commitment markers**: `[V]` VERIFIED · `[P]` PROVED · `[C]` CONJECTURED · `[O]` OPEN.
**Body signal tokens**: `THEOREM`/`PROVED`/`SETTLED` → FINALIZED ·
`RETRACTED`/`DEPRECATED` → SUPERSEDED · `TENTATIVE`/`PRELIMINARY` → TENTATIVE. A
document can be `[V]`-primary + carry a SUPERSEDED signal (verified then refuted) —
the classifier keeps both.

Bodies are chunked at `## ` headings; each section becomes one retrieval/scan unit with
the document's id, date, and status attached. **A claim and its immediate context
should live in the same section** — detectors (monitors, drift) operate per-chunk.

## The supersession graph — correction vs reference

Typed edges between documents are extracted from two pattern classes (`domain_config.json`:
`supersession_patterns`, split by `correction_relations` vs `reference_relations`):

- **Correction-class** (`corrects`, `retracts`, `supersedes`, `corrected_by`, …) —
  extracted **only from metadata** (the title line, the `**Status:**` line, the
  `**Supersession:**` line). To DECLARE a correction, put the verb there:
  `# VR-4: … — corrects VR-3`. Body prose that merely *discusses* a correction does not
  create an edge. A negated verb ("does not supersede VR-3") never creates an edge.
- **Reference-class** (`references`, `corroborates`, `closes`, …) — extracted from
  full text; benign pointers.

**Loser semantics**: for verb relations the **target** is the corrected/losing document
(`VR-4 corrects VR-3` ⟹ VR-3 lost); for self-applied bracket tags
(`[CORRECTED by VR-4]` inside VR-3) the **source** is the loser.

A corrected document should carry an inline acknowledgment tag (e.g.
`**[CORRECTED per VR-4]**` near the affected claim). A document that is a correction
loser but has no inline tag is surfaced by the grounding check as
`UNACKNOWLEDGED_CORRECTION` — that is a finding, not an error.

**Retraction**: a document retracts ITSELF with a `[RETRACTED]` marker plus a
self-referencing sentence. Retracted documents stay in the corpus; their chunks are
excluded from monitors/drift and **down-weighted in search**.

The canonical example of the graph in action is the `VR-1` → `AUDIT-1` → `VR-2` chain:
AUDIT-1 found that VR-1 §5's "exact values known for n ≤ 9" was stale at the time of
writing (OEIS had moved to a(10) = 309 in Oct 2025); VR-2 then restated the frontier
table against primary sources fetched 2026-07-16. The engine's graph carries the whole
story.

## The authority chain (P3)

| Seat | Writes | Reads | Notes |
|---|---|---|---|
| **Planner** (human operator or explicit delegate) | `QUEUE.md`, `plans/P*.md`; merges; adjudicates | everything | The **only** seat that may promote backlog → active. |
| **Agent** | `corpus/VR-N.md`, `corpus/AUDIT-N.md`; receipts with raw artifact paths | `QUEUE.md` (read-only), `plans/`, the corpus | Executes the top UNBLOCKED item in its lane. Corrections are new docs, never edits. |
| **Auditor** (a role, not necessarily a separate person/session) | `corpus/AUDIT-N.md` (findings about existing docs) | the corpus | **Finds, never fixes.** Every claim carries the command it rests on and the count it returned. A zero-finding pass must attempt one adversarial refutation of the brief's highest-risk item and record the attempt. |
| **Seeds** (`domains/<x>/*seed.json`) | authoritative curated facts (planner-gated) | engine outputs (drift reports) | The indexer VALIDATES them (drift), never extracts headline facts from prose. |
| **Third-party results** (OEIS comments, posted constructions) | enter at stratum `predicted` until independently verified | the corpus | e.g. a(12) ≤ 1157 entered at `predicted` in `VR-2` §1, promoted to `verified` in `VR-5` §2 after certificate verification. |

## Anti-discipline reminders (binding)

From `AGENTS.md` and the standing queue protocols:

- **A detector's zero is not a certification.** Candidates are regions to read, never
  verdicts.
- **Single-n results never touch the Bohman record.** The `record_claim_inflation`
  monitor enforces the labeling.
- **Exhaustion claims without prunes are not exhaustion.** Every negative claim names
  the prunes and argues each is conservative. `arms/exhaustive.py` documents its prunes
  (P1–P5) in the module docstring.
- **CG optimality is refuted as a general heuristic.** The `cg_optimality_forbidden`
  monitor enforces the labeling.
- **No exact frontier claim without an exhaustion receipt.** The
  `frontier_exact_claim_needs_exhaustion` monitor flags any `a(n)=v` at n ≥ 11 that
  doesn't have an exhaustion receipt in the same window.
- **No `SETTLED` without an independent route.** The `settled_needs_independent_route`
  monitor catches this.

## Receipt-bearing claims — the practice

Every claim in a VR that rests on a numeric result carries the receipt:

- The exact command line (copy-pastable, reproducible).
- The raw artifact path under `results/`.
- Counts as returned (nodes visited, elapsed seconds, rungs exhausted) — not
  summarized.
- The exact comparator (e.g. "matches Dyson 2025 (OEIS A276661 Oct 21 2025,
  `github.com/pwdyson/erdos_1` — citation corrected in `VR-5`)").
- For an exact claim, both sides: the positive side (a witness set, certificate-
  verified via `arms/verify_set.py`) AND the negative side (every M below the witness
  exhausted infeasible under the named prunes).

A VR without receipts is not a VR — it's a draft.
