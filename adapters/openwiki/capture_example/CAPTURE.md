# Captured OpenWiki run — the P5 2.4(b) before/after evidence

**Date:** 2026-07-17
**What this is:** the actual output of running LangChain's OpenWiki (`openwiki code
--init --print`) over this repository, with the corpus-orienteer integration in place
(the OKF digest pages emitted by `emit_okf.py` + the `AGENTS.md` orientation contract).
A one-time LLM-generated capture — **not maintained, not regenerated deterministically**;
it is frozen here as evidence that the integration works.

**Run configuration:** OpenWiki v0.2.0, provider `openai-compatible` → MiniMax-M3
(`api.minimax.io`), telemetry off, in a throwaway git copy of the repo (the real repo
was never touched). The `wiki/corpus-orienteer/` OKF pages were emitted first
(`./rag rebuild && emit_okf.py`), so the agent had the deterministic brief/monitors/
drift digests plus the AGENTS.md contract pointing it at `./rag orient`.

## What it demonstrates (the pitch, realized)

The agent's generated docs reflect the corpus's **actual current state**, with
provenance, rather than a plausible-but-stale synthesis:

- **The live frontier is correct.** `research-program/erdos-frontier.md` states
  **a(11) OPEN in [462, 594]** — the true frontier — with a(9)=161 and a(10)=309 marked
  exact. It did **not** regress to a stale "exact through n=9" or mislabel a(10) as the
  frontier. This is the exact defect class OpenWiki's own self-wiki exhibits (stale
  citations); the orientation layer prevented it here.
- **The correction arcs were picked up.** `workflows/working-protocol.md` narrates
  "OEIS had moved to a(10)=309 in Oct 2025; VR-2 then restated the frontier" (the
  AUDIT-1 → VR-2 arc), and `erdos-frontier.md` records "VR-2 §1 citation corrected in
  VR-5 (repository is github.com/pwdyson/erdos_1)" (the VR-5 → VR-2 arc). The agent
  read the supersession structure, not just the latest file.
- **Provenance-linked throughout.** Values cite the VR that establishes them
  (`VR-3` §2, `VR-4` §4, `VR-5` §2), and the n=9 gate receipts (35 rungs, 16.23B nodes)
  are quoted correctly.
- **Integration understood.** `integrations/openwiki-brain.md` reproduces the Layer
  A/B/C design and the "what OpenWiki lacks natively" list accurately.

## Honest caveats (this is an LLM run)

- **One conflation:** `testing/strategy.md` calls the tiered fixture a "comet survey" —
  that is the *single-tier* fixture (`scripts/rag/tests/fixture/`); the tiered fixture
  (`fixture_tiered/`) is a blob-mass survey. A minor mislabel, exactly the kind of thing
  the drift/orient layer would catch on a subsequent pass if these pages were fed back
  as a corpus.
- Content is model-dependent and would vary run to run; the deterministic half is the
  engine (brief/monitors/orient), not this synthesis.

## Reproducing

```bash
export OPENAI_COMPATIBLE_API_KEY=…  OPENAI_COMPATIBLE_BASE_URL=https://api.minimax.io/v1
export OPENWIKI_MODEL_ID=MiniMax-M3 OPENWIKI_PROVIDER=openai-compatible
./rag rebuild && python3 adapters/openwiki/emit_okf.py
openwiki code --init --print "Follow AGENTS.md; treat data/rag and wiki/ as derived."
```
