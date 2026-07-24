---
name: program-protocol
description: "Run a long-lived research program the verified way: append-only VR/RF corpus with independent-context referees, a planner-write-only QUEUE pinning the four protocols, a six-level authority chain, and the corpus-orienteer/OpenWiki audit loop. Use when starting, extending, or reconciling a multi-session verification program (math, audits, experiments), when the user says \"mint a VR\", \"referee this\", \"set up the queue\", \"reconcile the collaborator's work\", or when results need to survive sessions, referees, and collaborators. Invoke to load the operating rules."
---

# program-protocol

The shape: QUEUE → plan → script → VR → independent RF → fold → index row → rebuild.

**QUEUE** (`*_QUEUE.md`, planner-write-only; agents read, propose changes via VR (Verification Ready) open-work
items). It pins four protocols at §0, in this order:

1. **Index registry** — the related indexes in authority order; highest version-numbered
   filename is authoritative.
2. **Authority chain** — committed reproducers with passing runs > graded VRs (grade is
   part of the claim: [V] > [D] > [C] > [UL]; version-history-latest wins) > independent
   RF verdicts > indexes (pointers, never overriding) > collaborator artifacts (enter
   only via a reconciliation VR) > chat (never authoritative; re-derive in-corpus).
3. **Testing strategy** — two independent systems for anything a referee will doubt
   (disagreement = STOP, never average); exact arithmetic; every [V] traces to a
   chk-assertion in a committed script (print-only claims are a defect class); predictions
   preregistered before compute, intactness sweeps over ALL run logs; every instrument
   calibrated at both poles (a known-positive and a known-negative control).
4. **Working protocol** — every deliverable = VR + committed reproducer + RF slot + index
   row. Corrections are new documents pointing back, or vN+1 folds with a version-history
   row — never silent edits. Scratchpad-only artifacts are never citable.

**VR/RF cycle.** VRs are append-only, edit-protocol'd, every claim graded. RFs are
advisory, documents-only, and MUST come from a fresh context (agent or session) — a
same-context review is self-review, labeled as such, and never closes a referee slot.
Fold every RF finding as a vN+1 with the referee line updated; a refuted sub-claim is
retracted inline ([RETRACTED as of vN]), repaired, never deleted.

**Audit tooling.** After each work batch: rebuild the corpus-orienteer index, re-emit the
OKF orientation pages (brief/monitors/drift), and `orient` any documents you are about to
act on. Generated wikis/pages are derived artifacts — gitignored, never re-ingested.
OpenWiki (when installed) consumes the emitted pages; run it only on a throwaway copy.

**Collaborators.** Received artifacts land immutable in `correspondence/inbox/<TAG>/`;
engage via a reconciliation VR with the three-way split (their claim / our verification /
our inference); re-verify before importing, at an explicit grade; keep a corrections-owed
ledger for the next outbound memo; no from-memory citation relayed as fact in either
direction; no public release without explicit operator permission.
