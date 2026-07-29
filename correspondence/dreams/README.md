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
