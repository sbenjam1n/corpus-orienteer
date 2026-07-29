---
name: orient-scope
description: "Produce a scope-oriented OpenWiki output for ONE queue or ONE VR range: rebuild + emit the deterministic OKF pages, run a scoped orient artifact, and widen it with a concept-cluster corpus sweep (✓CORPUS/⚠MEMORY-tagged) before any LLM synthesis. Use when asked to 'orient the queue', 'orient a VR range', for an 'oriented OpenWiki output', or to warm-start a session against a specific plan/VR set. Invoke to load the pipeline. Reference implementation: r14-verify (JC_QUEUE.md + VR-1088–1125)."
---

# orient-scope

The shape: rebuild → emit OKF → derive/pin clusters → sweep → scoped orient → tag → (funded) synth.
OpenWiki is *fed, not written* (deterministic-fetch-then-LLM-synthesize); this drives the
deterministic half. Local calls are `python3 scripts/rag/{query,orient}.py` (there is no
`./rag` wrapper). `emit_okf.py` is whole-program; **scope is set by `orient.py`, never emit.**

**Prelude — whole-program, once per pass.**
```bash
bash scripts/rag/rebuild.sh
python3 adapters/openwiki/emit_okf.py     # → wiki/corpus-orienteer/{brief,monitors,drift}.md
bash tests/rag_smoke.sh                    # gate: index + OKF pages valid before feeding
```

**Per scope (a queue, or a VR range):**
1. **SCOPE** — pin the exact input docs/ids.
2. **CLUSTERS** — `clusters.py <scope> --out <slug> [--seed-scope <name>]`: internal heads
   are DERIVED (concepts.json VR-trail ∩ scope + touched objects, zero-LLM); external
   heads come from the committed `cluster_seed.json` — curated ONCE, CORPUS/MEMORY-tagged,
   then pinned (generation is a curation event, the canonical_objects precedent). A thin
   derived list on new vocabulary = extractor lag → seed a CORPUS-tagged stopgap + flag
   for ontology-reconcile.
3. **HARDER** — same invocation emits `data/rag/sweep_<slug>.md`: per-term literal hits
   (case/dash/accent-folded, word-bounded, exact counts) + TF-IDF adjacency (retracted
   down-weighted; stdlib tier PINNED for claims). Literal-vs-adjacency stays split:
   0 literal ≠ absent — read the ADJACENT-ONLY rows; adjacency ≠ presence.
4. **ORIENT** — `orient.py <scope> --out <slug>` → `data/rag/orient_<slug>.md`: corrected/
   superseded citations, stale-assertion candidates, method reliability, in-scope monitors, arcs.
5. **TRAVERSE** — `query.py page/timeline` on touched objects for cross-scope links grep misses.
6. **TAG + REGISTER** — mark every line ✓CORPUS vs ⚠MEMORY; a stale-assertion flag is a READ,
   never a verdict; unmet monitors → open-questions. Nothing banked; no ⚠MEMORY relayed as fact.
7. **SYNTH** *(only with a funded model)* — OpenWiki on a throwaway rsync copy, instructed to
   read brief/monitors/drift + `orient_<slug>` FIRST; freeze under `adapters/openwiki/capture_r14/`.

**Queue scope** — `orient.py <QUEUE> <highest-version index> <plan> --out <q>`: orients on
planner **intent** (the four pins, reserved/earmarked numbers, open-work).
**VR-range scope** — enumerate existing ids (`seq`+`ls`, gaps auto-skip), `orient.py $IDS
--out <v>`: orients on **evidence** (banked / corrected / superseded). `diff` the two =
planned-but-unbanked.

**Guards.** Throwaway copy only (OpenWiki writes files). `wiki/`, `data/rag/`, `orient_*.md`
are derived — gitignored, never re-ingested. A detector's zero is not a certification. Synth
is blocked without a funded `OPENAI_COMPATIBLE` endpoint; steps 1–6 are the useful output without it.
