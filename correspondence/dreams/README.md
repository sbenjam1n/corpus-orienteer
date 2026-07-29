# dreams/ — the model-correspondence channel (scaffold)

The divergent counterpart of an orientation pass: a scope's oriented artifacts
(`./rag clusters` sweep + `./rag orient`) are packaged into a packet under
`out/DREAM-N_<slug>/`, handed to a FRESH higher-model context, and the response
lands immutable under `in/DREAM-N_<slug>/RESPONSE.md`. Dream output is
idea-weight only (verification-weight zero) and enters a corpus only via a
reconciliation document: capture immutable, three-way-split every item (dream's
claim / our verification / our inference), re-verify independently at an
explicit grade, import the verification and never the dream.

`PROMPT.md` is the standing dreamer wrapper (v1.3), passed verbatim with slots
filled; the per-dream brief lives in each packet, never in the wrapper.
Reference implementation with live dreams: the r14-verify deployment
(`correspondence/dreams/` there, DREAM-0 onward).

Channel infrastructure ships in this repo too (mirrored byte-identical from the
r14 deployment, 2026-07-29): the `/dreams` and `/orient-scope` skills
(`.claude/skills/`), the restricted `dreamer` agent type (`.claude/agents/` —
Read/Write only, context-hygiene disclosure clause), and the dream-fence
PreToolUse hook (`.claude/hooks/dream_fence.py` + `.claude/settings.json` — W1:
in/ is write-once; W2: out/ packets freeze at handoff; calibrated nine of nine
on synthetic poles). Measured limitation (2026-07-29 probe): a custom agent type
does NOT remove harness-injected ambient context (project instructions, memory),
so in-session isolation is mitigated by the mandatory contamination disclosure,
not closed; full isolation requires out-of-session execution from a neutral
directory. Deployment note: where the r14 skill text says `tests/rag_smoke.sh`,
this repo's equivalent gate is `./rag test`.
