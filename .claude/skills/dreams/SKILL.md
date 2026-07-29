---
name: dreams
description: "Run a dreams pass over ONE VR range or ONE queue: refresh the scope's internal (derived) and external (seeded) vocabulary, build the oriented artifacts, compose a self-contained dream packet in correspondence/dreams/out/, hand it to a FRESH higher-model context (e.g. Agent model:fable), and land the response immutable in correspondence/dreams/in/. Use when asked to 'dream on' a range or queue, launch a dreams agent, or turn oriented OpenWiki outputs into speculative synthesis. Invoke to load the packet procedure + channel rules. Dreams are idea-weight, never receipts."
---

# dreams

The shape: refresh vocab → sweep/orient → packet → out/ → dreamer (fresh context) → in/ →
reconcile-to-enter. A dream is CORRESPONDENCE WITH A MODEL — the standing rule transfers
verbatim: replies are idea-weight, verification-weight ZERO, never cited as authority.
Corpus entry ONLY via a reconciliation VR: capture the response immutable, three-way-split
every item (dream's claim / our verification / our inference), re-verify each claim
independently at an explicit grade — import the verification, never the dream.

**Vocabulary refresh (the load-bearing prep):**
1. INTERNAL (derived — self-updates): `bash scripts/rag/rebuild.sh`, then
   `python3 scripts/rag/clusters.py <scope> --out <slug> [--seed-scope <name>]`. A thin or
   jargon-dominated derived list on new vocabulary = extractor lag, not absence.
2. EXTERNAL (seeded — updates by curation): extend `scripts/rag/cluster_seed.json` for the
   scope — CORPUS-tag corpus-present-but-unextracted terms (the stopgap pattern),
   MEMORY-tag genuinely-external neighborhood; set the curated date. The seed is committed;
   this is the durable half of "vocabulary is updated."
3. Re-sweep. The **ABSENT and ADJACENT-ONLY rows are the dream seeds**: what the corpus
   has not internalized is exactly what the dreamer should roam.

**Packet → `correspondence/dreams/out/DREAM-N_<slug>/`** (tracked; immutable once handed
off — outbox convention; N = next free across in/ and out/):
- `PACKET.md` — scope + HEAD sha + generating commands + sha256 of every attachment; the
  dream brief (open questions, drawn from ABSENT/ADJACENT-ONLY rows + unmet monitors +
  the queue's open-work items); the dreamer constraints below, verbatim.
- Frozen copies of `sweep_<slug>.md`, `orient_<slug>.md`, `clusters_<slug>.json`
  (byte-deterministic at that HEAD; attached anyway for self-containedness).

**Handoff.** A FRESH context, higher model class — `Agent(subagent_type: dreamer)`, the
restricted agent type (Read/Write only, no shell/search; model fable; context-hygiene
disclosure clause) — never same-context; same independence law as referees.
Message/output length at the class MAXIMUM (128k) — a dream is never truncated for
budget. Prompt = the standing wrapper `correspondence/dreams/PROMPT.md`, verbatim, slots
filled — never re-improvised. It reads the packet dir ONLY and writes ONLY
`correspondence/dreams/in/DREAM-N_<slug>/RESPONSE.md`, opening with a provenance header:
model id, date, packet sha256, plus disclosure of any ambient context visible beyond the
packet. Nothing else on disk. The channel's immutability is ALSO mechanical: the
dream-fence hook (`.claude/hooks/dream_fence.py`) blocks edits to landed in/ artifacts
(W1) and to handed-off out/ packets (W2).

**Dreamer constraints (paste into every PACKET.md):** no computations presented as
results; cite corpus documents by id, or mark ⚠MEMORY; speculation welcome and labeled;
questions outrank answers where uncertain; write only your own in/ dir.

**Return path.** in/ artifacts are immutable received documents; engage per the
reconciliation rule above. Landing a response ALSO mints an open-work row in the scope's
queue — or, where the queue is planner-write-only, in the scope's RESUME file (the live
cross-session surface; never a retired log) — an unqueued dream is the rot state. Anything
relayed onward carries the corrections-owed ledger; no dream content banked or relayed as
fact unverified.

**Git.** dreams/ is TRACKED — in/ is one-shot provenance (inbox class), out/ is
what-was-shown (outbox class). Nothing new is gitignored; `data/rag/` derived outputs stay
ignored, their packet copies are correspondence attachments. Dreams are never RAG-ingested
(corpus root is verification_ready/) and never land in verification_ready/ or docs/
directly — corpus entry is only via the reconciliation VR.
