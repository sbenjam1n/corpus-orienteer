# RAG corpus format — the document contract

What a corpus must look like for the `scripts/rag/` engine to index it. This is the
engine's *input contract*, written domain-free; every example is from the shipped fixture
corpus (`scripts/rag/tests/fixture/`), which is the executable form of this spec. The
engine's *vocabulary* (entity families, relations, quantities, types) is separately
configurable via `domain_config.json` (see `scripts/rag/README.md` §8). This document
covers only what is structural.

## 1. Documents and namespaces

The corpus is a flat directory of markdown files (default `verification_ready/`,
override `RAG_CORPUS_DIR`). Two document namespaces:

- **Primary**: substantive results (default prefix `VR`).
- **Audit**: findings *about* existing documents (default prefix `AUDIT`).

Prefixes are configurable via `domain_config.json`:

```jsonc
"doc_id": { "primary": "VR", "audit": "AUDIT" }
```

Filenames MUST be `<PREFIX>-<N>_<slug>.md`, e.g. `VR-4_c1_period_correction.md`.
The id is parsed from the stem; everything after the first `_` is a human-readable slug.
Numbering within each namespace should be unique; the namespaces never collide.

The corpus is **append-only**: documents are never mutated to change a conclusion.
Corrections are NEW documents that point back (see §4). This is what makes the
longitudinal layers (arcs, supersession, claim timelines) meaningful.

## 2. Header contract

Each document opens with:

```markdown
# VR-4: C_1 period correction — corrects VR-3

**Date:** 2026-01-08
**Status:** [V] verified — correction; corrects VR-3
```

| Field | Required | Parsed as |
|---|---|---|
| `# <ID>: <title>` (first line) | yes | title; ALSO metadata for correction edges (§4) |
| `**Date:** YYYY-MM-DD` | yes | document date; drives timelines and the corpus stamp |
| `**Status:** [X] …` | yes | commitment marker + free text; metadata for correction edges |
| `**Version:**`, `**Author:**`, `**Supersession:**` | optional | version history; Supersession is a metadata line for correction edges |

Commitment markers in the Status line: `[V]` VERIFIED · `[P]` PROVED · `[C]` CONJECTURED
· `[O]` OPEN. Body signal tokens (anywhere in the text): `THEOREM`/`PROVED`/`SETTLED` →
FINALIZED · `RETRACTED`/`DEPRECATED` → SUPERSEDED · `TENTATIVE`/`PRELIMINARY` → TENTATIVE.
A document can be `[V]`-primary *and* carry a SUPERSEDED signal (verified then refuted);
the classifier keeps both.

## 3. Body structure

Bodies are chunked at `## ` headings; each section becomes one retrieval/scan unit with
the document's id, date, and status attached. Use one `## §N <name>` section per logical
unit. Detectors (monitors, drift) operate per-chunk, so a claim and its immediate context
should live in the same section.

## 4. Correction and reference conventions

Typed edges between documents are extracted from two pattern classes
(`domain_config.json`: `supersession_patterns`, split by `correction_relations` vs
`reference_relations`):

- **Correction-class** (`corrects`, `retracts`, `supersedes`, `corrected_by`, ...):
  extracted **only from metadata** (the title line, the `**Status:**` line, the
  `**Supersession:**` line). To DECLARE a correction, put the verb there:
  `# VR-4: … — corrects VR-3`. Body prose that merely *discusses* a correction does not
  create an edge. A negated verb (“does not supersede VR-3”) never creates an edge.
- **Reference-class** (`references`, ...): extracted from full text; benign pointers.

Loser semantics: for verb relations the **target** is the corrected/losing document
(`VR-4 corrects VR-3` ⟹ VR-3 lost); for self-applied bracket tags
(`[CORRECTED by VR-4]` inside VR-3) the **source** is the loser.

A corrected document should carry an inline acknowledgment tag (e.g.
`**[CORRECTED per VR-4]**` near the affected claim). A document that is a correction
loser but has no inline tag is surfaced by the grounding check as
`UNACKNOWLEDGED_CORRECTION`; that is a finding, not an error.

## 5. Retraction

A document retracts ITSELF with a `[RETRACTED]` marker plus a self-referencing sentence
(`**[RETRACTED]** this VR is retracted per VR-9 ...`), or via `[RETRACTED` in its own
Status line. The classifier distinguishes “this document IS retracted” from “this
document RETRACTS another” (which is a title/Status verb, §4). Retracted documents stay
in the corpus; their chunks are excluded from monitors/drift and down-weighted in search.

## 6. Values and quantities

Numeric claims the engine should track are written as `name = value` near the object they
describe (e.g. `C_1 period = 12 days`). Which names are tracked, their capture patterns,
and plausibility bounds come from `domain_config.json` (`quantities` for value-history;
`drift_value_patterns` for seed-vs-corpus drift and orient's assertion check). The
window discipline is ±70 chars: keep the value and its subject in the same sentence.

## 7. What the engine does NOT require

- No front-matter/YAML; the header is plain markdown.
- No registration step: drop a conforming file in the corpus dir and rebuild.
- No specific section names beyond the `## ` chunking convention.
- Seeds (`canonical_objects.json` etc.) are optional per-object curation on top; a corpus
  with no seeds still gets chunks, entities, supersession, arcs, and claim status.

## 8. Conformance check

The fixture corpus is the reference implementation of this contract. To validate a new
corpus quickly:

```bash
RAG_CORPUS_DIR=/path/to/corpus RAG_DATA_DIR=/tmp/ragtest RAG_SEED_DIR=/path/to/seeds \
  python3 scripts/rag/index_vrs.py
```

Zero `errors` in the final stats and non-empty `file_meta.json` means the structural
contract is met; everything else is vocabulary tuning in `domain_config.json`.
