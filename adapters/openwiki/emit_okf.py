#!/usr/bin/env python3
"""emit_okf — render the engine's deterministic surfaces as OpenWiki OKF pages
(P5 Layer A: the sidecar feeder).

Reads the current build (RAG_DATA_DIR, default data/rag) and writes markdown pages
whose YAML front matter uses EXACTLY the OKF keys OpenWiki's validator accepts
(`type` required; `title`, `description`, `resource`, `tags`) — nothing else, no
timestamps. Never writes `index.md` (OpenWiki regenerates those deterministically).
Page content is copied/derived from build outputs, so two emissions from the same
build are byte-identical; the corpus stamp in each description ties a page to the
build that produced it.

Pages (each skipped cleanly when its source is absent):
  brief.md     — the warm-start audit brief (verbatim body from audit_brief.md)
  monitors.md  — declared monitors, unmet first
  drift.md     — seed↔corpus drift report
  captures.md  — cross-tier capture state (tiered deployments with thread tiers)

Usage:
  python3 adapters/openwiki/emit_okf.py [--out wiki/corpus-orienteer]
Schedule it right after `./rag rebuild` and ahead of `openwiki … --update`
(see openwiki-update-prestep.yml in this directory).
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))

OKF_KEYS = ("type", "title", "description", "resource", "tags")


def _front_matter(**kv):
    assert all(k in OKF_KEYS for k in kv), f"non-OKF key in {list(kv)}"
    assert "type" in kv, "OKF requires `type`"
    lines = ["---"]
    for k in OKF_KEYS:
        if k not in kv:
            continue
        v = kv[k]
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---\n")
    return "\n".join(lines)


def _load(name):
    try:
        return json.loads((DATA / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _stamp():
    st = _load("index_stats.json") or {}
    return st.get("generated", "unbuilt")


def page_brief():
    src = DATA / "audit_brief.md"
    if not src.exists():
        return None
    return _front_matter(
        type="report", title="Corpus warm-start brief",
        description=f"Deterministic whole-program digest (build {_stamp()}): active "
                    "correction arcs, distrusted methods, unmet monitors, drift. "
                    "Read first when acting on the corpus.",
        tags=["corpus-orienteer", "brief", "orientation"],
    ) + src.read_text()


def page_monitors():
    md = _load("monitors.json")
    if not md:
        return None
    mons = md.get("monitors", [])
    unmet = [m for m in mons if m.get("state") == "unmet"]
    body = [f"# Monitors — {len(unmet)} unmet / {len(mons)} declared\n"]
    for m in sorted(mons, key=lambda m: (m.get("state") != "unmet", m.get("id", ""))):
        mark = "UNMET" if m.get("state") == "unmet" else m.get("state", "?")
        body.append(f"## {m.get('id')} — {mark} [{m.get('severity','?')}]\n")
        body.append(f"Watch: {m.get('watch','')}\n")
        body.append(f"Evidence: {m.get('evidence','')}\n")
    return _front_matter(
        type="report", title="Corpus monitors",
        description=f"Declared invariants evaluated deterministically each build "
                    f"(build {_stamp()}); {len(unmet)} unmet. Candidates to read, "
                    "never verdicts.",
        tags=["corpus-orienteer", "monitors"],
    ) + "\n".join(body)


def page_drift():
    d = _load("object_drift.json")
    if not d:
        return None
    st = d.get("stats", {})
    body = [f"# Seed↔corpus drift\n",
            f"confirmed {st.get('confirmed',0)} · unconfirmed {st.get('unconfirmed',0)} · "
            f"flagged {st.get('flagged',0)} · unverified {st.get('unverified',0)} · "
            f"no_detector {st.get('no_detector',0)}\n",
            "For `no_detector` facts, no flag does NOT mean verified.\n"]
    for fl in d.get("flags", []):
        body.append(f"- FLAG {fl.get('subject')}.{fl.get('prop')}: seed={fl.get('seed_value')} "
                    f"vs corpus={fl.get('corpus_value')} ({fl.get('corpus_vr_count')} docs)")
    return _front_matter(
        type="report", title="Corpus drift report",
        description=f"Authoritative-seed validation against the corpus (build {_stamp()}); "
                    f"{st.get('flagged',0)} high-precision flags.",
        tags=["corpus-orienteer", "drift", "seeds"],
    ) + "\n".join(body)


def page_captures():
    cl = _load("capture_ledger.json")
    if not cl:
        return None
    unrec, cands = cl.get("unreconciled_rounds", []), cl.get("receipt_candidates", [])
    body = [f"# Correspondence capture state\n",
            f"{len(cl.get('captures',[]))} captures · {len(unrec)} unreconciled rounds · "
            f"{len(cands)} receipt candidates\n"]
    for u in unrec:
        body.append(f"- UNRECONCILED {u['thread']} R{u['round']} ({u['path']})")
    for c in cands:
        body.append(f"- RECEIPT-CANDIDATE {c['vr']} cites {c['thread']} R{c['round']} — "
                    "read to certify (threads are verification-weight, never receipts)")
    return _front_matter(
        type="report", title="Correspondence capture state",
        description=f"Cross-tier reconciliation ledger (build {_stamp()}): thread rounds "
                    "not yet captured by a corpus doc, and receipt-like thread citations.",
        tags=["corpus-orienteer", "captures", "tiers"],
    ) + "\n".join(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "wiki" / "corpus-orienteer"),
                    help="target subtree (declare it externally generated in "
                         "openwiki/INSTRUCTIONS.md)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pages = {"brief.md": page_brief(), "monitors.md": page_monitors(),
             "drift.md": page_drift(), "captures.md": page_captures()}
    written = []
    for name, content in pages.items():
        assert name != "index.md"
        if content is None:
            continue
        (out / name).write_text(content)
        written.append(name)
    print(f"emit_okf: wrote {len(written)} page(s) to {out}: {', '.join(written)}")
    if not written:
        print("emit_okf: nothing to emit — run ./rag rebuild first", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
