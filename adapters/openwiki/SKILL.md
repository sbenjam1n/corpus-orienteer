# corpus-orienteer

Use the deterministic corpus-orientation engine when updating this wiki, and route its
findings into the wiki's canonical pages. The engine lives in the corpus repository
(root `./rag` CLI; configuration in `ragconfig.json`).

## When updating from the corpus source

1. **Warm start.** Run `./rag brief` first and read the digest: active arcs, distrusted
   methods (with wrong-answer history), unmet monitors, drift flags, and
   changed-since-last-pass documents. Treat it as the current state of the research
   program — it is deterministic and regenerated from the corpus, never synthesized.
2. **Pre-action orientation.** Before summarizing, citing, or acting on specific corpus
   documents (ids like VR-N / AUDIT-N), run `./rag orient <ids-or-paths>`. Its report
   lists: cited documents that have been corrected or superseded (with the winning
   document to read instead), stale numeric assertions (candidates to READ, never
   verdicts), method reliability, and in-scope unmet monitors. Never cite a document the
   orient report marks as a correction loser without also citing its corrector.
3. **Search.** Prefer `./rag query search "<terms>"` over raw grep — results down-weight
   retracted and deprecated documents.

## Routing findings into wiki pages

- Each **unmet monitor** becomes (or refreshes) an `Active` entry in
  `/open-questions.md` with `Owner`, `Seen` (the build date from the brief), and
  `Evidence` (the monitor id + its evidence line). When a monitor turns met, move the
  entry to `Answered` with the resolving document id.
- **Method reliability** changes (a method entering `failed`/`diagnosed`, or carrying
  `has_produced_wrong_answer`) become rows/updates in `/themes.md` with the defining
  document ids as Evidence.
- **Drift flags** (seed↔corpus disagreement on an authoritative value) are surfaced in
  the relevant topic page with both values and their document provenance — flag, don't
  adjudicate.

## Discipline

- The engine's outputs are **evidence, never proof**: a detector's zero is not a
  certification, and a candidate is a region to read, not a verdict.
- Do not edit the corpus itself; corrections there are new documents, written by the
  research loop, not by wiki maintenance.
- Do not write `index.md` files or non-OKF front-matter fields.
