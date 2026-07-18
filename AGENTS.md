# Agent instructions — corpus-orienteer

This repository is a research program run under `QUEUE.md` (the planner-write-only
work queue; read its §0.5 pinned protocols before changing anything).

## Orientation contract (binding for any agent, human or LLM)

- **Start sessions from `./rag brief`** — the deterministic warm start: active
  correction arcs, distrusted methods, unmet monitors, drift, changed-since-last-pass.
- **Before acting on corpus documents** (ids `VR-N` / `AUDIT-N`, files under
  `corpus/`), run `./rag orient <ids-or-paths>` and treat its superseded-citation and
  stale-assertion findings as mandatory reads. Never cite a document the report marks
  as a correction loser without also citing its corrector.
- Prefer `./rag query search "<terms>"` over raw grep — retracted/deprecated documents
  are down-weighted.
- The engine's outputs are **evidence, never proof**: a detector's zero is not a
  certification; candidates are regions to read, not verdicts.
- `data/rag/` and `wiki/corpus-orienteer/` are **derived artifacts** — never sources,
  never edited by hand, never cited as provenance.
- Corpus conclusions change only via NEW documents with correction verbs in metadata
  (`docs/rag_corpus_format.md`); corrected docs get inline `[CORRECTED per VR-N]` tags.
- Correspondence threads (when present) are verification-weight, **never receipts**;
  reconciling a round into the corpus is a `captures THREAD-N R<k>` declaration in the
  capturing doc's metadata (`./rag query captures` shows the ledger).

<!-- OpenWiki manages its own block below this line; keep this section above it. -->
