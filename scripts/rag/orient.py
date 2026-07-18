#!/usr/bin/env python3
"""Execution-context orientation compiler.

Give it the documents you are about to hand an execution agent — an execution plan, the
planning message, a set of VR/AUDIT ids, any mix — and it compiles ONE markdown artifact
answering: *where does everything these documents touch currently stand in the program's
state machine?* Per cited VR/AUDIT: its classified status + every correction edge in which
it is the LOSER (with the winning doc to read instead). Per touched canonical object: the
current seeded facts with stratum + provenance. Per numeric value the inputs assert near an
object: whether it matches or contradicts the seeded fact (stale-assumption candidates).
Plus the lifecycle state of every method the inputs name, the unmet monitors overlapping
the scope, and the correction arcs the cited docs sit in.

This is the plan-scoped sibling of synthesize_brief.py (which digests the WHOLE program):
pure distillation of the existing graph layers, stdlib only, NO LLM, NO new extraction
rules. Deterministic given fixed inputs — the as-of stamp is read from the graph's own
`generated` field, never the wall clock. Every flag is a candidate to READ, never a
verdict; the artifact adds no new claims.

Run (from repo root, after `rebuild.sh`):
    python3 scripts/rag/orient.py Plans/my_plan.md MESSAGE.md VR-1049 [--out my_slug]
    python3 scripts/rag/query.py orient <same args>     # via the query dispatcher
Writes data/rag/orient_<slug>.md and prints it.
"""
import json
import re
import sys
from pathlib import Path

import os
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
CORPUS = Path(os.environ.get("RAG_CORPUS_DIR", ROOT / "verification_ready"))
SEED_DIR = Path(os.environ.get("RAG_SEED_DIR", Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiers as tiers_mod  # noqa: E402  (P6 M2: versioned-doc verdicts)
from ontology import match_aliases, _alias_rx, _PROP_VALUE_RE, _WINDOW  # noqa: E402
from domain_ids import DOC_ID_RE  # noqa: E402 — doc-id scheme is config-driven
# Same self-referential determination query.py contradict uses (AUDIT-210 F2): a doc is
# retracted/corrected iff its OWN classified status says so.
RETRACTED_STATES = ("retracted", "deprecated", "corrected")
# Correction-edge loser semantics (README §6): the loser is the TARGET for verb relations
# (VR-A corrects VR-B => B lost) and the SOURCE for self-applied tags (VR-B corrected_by
# VR-A => B lost). Relation vocabulary comes from domain_config so a ported domain keeps
# working without edits here.
SELF_APPLIED = {"corrected_by", "corrected_by_audit"}
ACTIVE_CAP = 40
SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
_INT_RE = re.compile(r"\(?\s*(-?\d+)")

# Display-only denoising: the artifact orients an agent that has NOT lived inside the loop,
# so loop-internal shorthand is translated or dropped at render time (matching/graph logic
# is untouched). "banked" (loop jargon for settled-at-uniform-standard) reads as "settled";
# "FLAGSHIP" and "SLB Seq N" are loop bookkeeping with no orientation value.
_JARGON = [
    (re.compile(r"\bBANKED\b"), "settled"),
    (re.compile(r"\bbanked\b"), "settled"),
    (re.compile(r"\s*[—·,;:-]?\s*\bFLAGSHIP\b"), ""),
    (re.compile(r"\s*[—·,;:-]?\s*\bSLB Seq \d+\b"), ""),
]


def _clean(s):
    s = str(s)
    for rx, rep in _JARGON:
        s = rx.sub(rep, s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


def _load(name, default):
    try:
        return json.loads((DATA / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _stamp():
    for n in ("objects.json", "monitors.json"):
        d = _load(n, {})
        if isinstance(d, dict) and d.get("generated"):
            return d["generated"]
    return "unknown"


def _correction_relations():
    try:
        cfg = json.loads((SEED_DIR / "domain_config.json").read_text())
        return set(cfg.get("correction_relations", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"corrects", "refutes", "retracts", "supersedes", "downgrades",
                "amends", "correction_of"} | SELF_APPLIED


def resolve_inputs(args, fm_by_id):
    """Each arg is a VR/AUDIT id (resolved via file_meta) or a file path. Returns
    [(label, text)], plus the ids of input docs themselves (excluded from 'cited')."""
    inputs, self_ids, errors = [], set(), []
    for a in args:
        if DOC_ID_RE.fullmatch(a):
            meta = fm_by_id.get(a)
            if not meta:
                errors.append(f"{a}: not in the corpus (file_meta)")
                continue
            p = CORPUS / meta["file"]
            self_ids.add(a)
        else:
            p = Path(a) if Path(a).is_absolute() else ROOT / a
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as e:
            errors.append(f"{a}: unreadable ({e.__class__.__name__})")
            continue
        label = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else a
        m = DOC_ID_RE.match(p.name)
        if m:
            self_ids.add(m.group(1))
        inputs.append((label, text))
    return inputs, self_ids, errors


def cited_docs(inputs, self_ids):
    """id -> mention count across all inputs, excluding the input docs' own ids."""
    counts = {}
    for _label, text in inputs:
        for m in DOC_ID_RE.finditer(text):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    for sid in self_ids:
        counts.pop(sid, None)
    return counts


def build_losers(supersession, correction_rels):
    """loser id -> [(winner id, relation)] over correction-class edges only."""
    losers = {}
    for e in supersession.get("edges", []):
        rel = e.get("relation")
        if rel not in correction_rels:
            continue
        if rel in SELF_APPLIED:
            loser, winner = e["source"], e["target"]
        else:
            loser, winner = e["target"], e["source"]
        pair = (winner, rel)
        if pair not in losers.setdefault(loser, []):
            losers[loser].append(pair)
    return losers


def touched_objects(inputs, objects):
    """Canonical objects whose alias boundary-matches any input text. Returns
    [(obj, mention_count)] sorted by mentions desc."""
    joined = "\n".join(t for _l, t in inputs)
    out = []
    for obj in objects.values():
        n = 0
        for a in match_aliases(obj):
            if a in joined:  # cheap literal gate before the boundary regex
                n += len(_alias_rx(a).findall(joined))
        if n:
            out.append((obj, n))
    out.sort(key=lambda x: (-x[1], x[0]["id"]))
    return out


def _seed_values(obj, pairs, prop):
    """All seeded values of `prop` for this object: own properties + every (curve,field)
    pair it participates in. Returns [(where, value, stratum, vr_id)]."""
    vals = []
    p = (obj.get("properties") or {}).get(prop)
    if p:
        vals.append(("own", p.get("value", ""), p.get("stratum", "?"), p.get("vr_id", "?")))
    for pair in pairs.values():
        if obj["id"] not in (pair.get("curve"), pair.get("field")):
            continue
        pp = (pair.get("properties") or {}).get(prop)
        if pp:
            where = f"over {pair['field']}" if pair.get("curve") == obj["id"] \
                else f"{pair['curve']} over this field"
            vals.append((where, pp.get("value", ""), pp.get("stratum", "?"), pp.get("vr_id", "?")))
    return vals


def _lead_int(s):
    m = _INT_RE.match(str(s).strip())
    return m.group(1) if m else None


def assertion_check(inputs, touched, pairs):
    """Numeric values the inputs assert within ±_WINDOW of an object alias, compared to
    the seeded facts (drift-detector value patterns + window discipline). Each assertion
    is attributed ONLY to the NEAREST boundary-matched alias — when several objects
    co-occur in one window ("rank E(stem_2)=2 … cross-check E^5033") a naive any-alias
    join would charge the value to all of them. If the nearest object carries no seeded
    value for the property, the assertion is skipped rather than re-attributed to the
    2nd-nearest (precision over recall). Returns (mismatches, anchors); a mismatch is a
    stale-assumption CANDIDATE, not a verdict."""
    obj_rxs = [(obj, [_alias_rx(a) for a in match_aliases(obj)]) for obj, _n in touched]
    mismatches, anchors, seen = [], [], set()
    for prop, rx in _PROP_VALUE_RE.items():
        for label, text in inputs:
            for m in rx.finditer(text):
                lo, hi = max(0, m.start() - _WINDOW), m.end() + _WINDOW
                win = text[lo:hi]
                nearest, nearest_key = None, None
                for obj, rxs in obj_rxs:
                    for r in rxs:
                        for am in r.finditer(win):
                            a_start, a_end = lo + am.start(), lo + am.end()
                            # interval gap, not start-distance: 'A4' boundary-matches INSIDE
                            # 'K_A4' ('_' is not a boundary char) and would otherwise win by
                            # 2 chars; equal-gap ties go to the LONGER (more specific) alias.
                            gap = max(0, m.start() - a_end, a_start - m.end())
                            key = (gap, -(a_end - a_start))
                            if nearest_key is None or key < nearest_key:
                                nearest, nearest_key = obj, key
                if nearest is None:
                    continue
                expected = _seed_values(nearest, pairs, prop)
                if not expected:
                    continue
                val = m.group(1)
                key = (nearest["id"], prop, val)
                if key in seen:
                    continue
                seen.add(key)
                hits = [e for e in expected if _lead_int(e[1]) == val]
                if hits:
                    w, v, st, vr = hits[0]
                    anchors.append(f"- `{nearest['id']}` {prop} = {val} ({label}) — matches "
                                   f"seed **{_clean(v)}** ({w}) [{_clean(st)}, {vr}]")
                else:
                    exp = "; ".join(f"**{_clean(v)}** ({w}) [{_clean(st)}, {vr}]"
                                    for w, v, st, vr in expected[:4])
                    mismatches.append(f"- ⚠ `{nearest['id']}` {prop} = **{val}** asserted in "
                                      f"{label} — seed says {exp}. READ both; if the input "
                                      f"predates a correction, it is stale.")
    return mismatches, anchors


def methods_referenced(inputs, registry):
    joined = "\n".join(t for _l, t in inputs)
    out = []
    for mid, m in (registry or {}).items():
        forms = {mid, mid.replace("_", " ")}
        if any(_alias_rx(f).search(joined) for f in forms):
            out.append(m)
    out.sort(key=lambda m: (not m.get("has_produced_wrong_answer"),
                            m.get("current_state") != "failed", m.get("id", "")))
    return out


def relevant_monitors(monitors, touched, cited):
    aliases = [a for obj, _n in touched for a in match_aliases(obj)]
    rel, other_unmet = [], 0
    for m in monitors:
        if m.get("state") == "met":
            continue
        blob = " ".join((m.get("watch", ""), json.dumps(m.get("evidence", ""), ensure_ascii=False)))
        if any(_alias_rx(a).search(blob) for a in aliases) or any(c in blob for c in cited):
            rel.append(m)
        else:
            other_unmet += 1
    rel.sort(key=lambda m: (SEV_ORDER.get(m.get("severity"), 9), m.get("id", "")))
    return rel, other_unmet


def compile_orientation(args, out_slug=None):
    fm = _load("file_meta.json", [])
    fm_by_id = {r["id"]: r for r in fm if r.get("id")}
    inputs, self_ids, errors = resolve_inputs(args, fm_by_id)
    if not inputs:
        return None, errors or ["no readable inputs"]

    claim_status = _load("claim_status.json", {})
    supersession = _load("supersession.json", {"edges": []})
    arcs = _load("arcs.json", [])
    objdata = _load("objects.json", {})
    registry = _load("method_registry.json", {})
    mons = _load("monitors.json", {})
    monitors = mons.get("monitors") if isinstance(mons, dict) else (mons or [])

    losers = build_losers(supersession, _correction_relations())
    arc_by_member = {}
    for a in arcs:
        for mem in a.get("members", []):
            arc_by_member.setdefault(mem, a)

    cited = cited_docs(inputs, self_ids)
    corrected, dangling, active = [], [], []
    for cid in sorted(cited, key=lambda c: (-cited[c], c)):
        meta = fm_by_id.get(cid)
        if not meta:
            dangling.append(cid)
            continue
        status = meta.get("status_classified", "active")
        rec = (cid, meta, status, losers.get(cid, []), arc_by_member.get(cid))
        if status in RETRACTED_STATES or rec[3]:
            corrected.append(rec)
        else:
            active.append(rec)

    touched = touched_objects(inputs, objdata.get("objects", {}))
    pairs = objdata.get("pairs", {})
    mismatches, anchors = assertion_check(inputs, touched, pairs)
    methods = methods_referenced(inputs, registry)
    rel_mons, other_unmet = relevant_monitors(monitors, touched, list(cited))
    cited_arcs = []
    for a in arcs:
        hit = sorted(set(a.get("members", [])) & (set(cited) | self_ids))
        if hit:
            cited_arcs.append((a, hit))
    cited_arcs.sort(key=lambda x: (-(x[0].get("error_density") or 0.0), x[0].get("id", "")))

    # ---- render ------------------------------------------------------------
    L = []
    slug = out_slug or re.sub(r"[^A-Za-z0-9_-]+", "_", Path(args[0]).stem)[:60]
    L.append(f"# Execution-Context Orientation: {slug}\n")
    L.append(f"_Compiled from: {', '.join('`' + l + '`' for l, _t in inputs)}. "
             f"Graph state as of data/rag build `{_stamp()}`. Deterministic distillation of the "
             f"existing layers (scripts/rag/orient.py) — every flag is a candidate to READ, never "
             f"a verdict; this artifact adds no new claims._\n")
    if errors:
        L.append("**Input warnings:** " + "; ".join(errors) + "\n")
    L.append(f"**At a glance:** {len(cited)} docs cited "
             f"({len(corrected)} corrected/retracted ⚠, {len(dangling)} dangling) · "
             f"{len(touched)} canonical objects touched · {len(mismatches)} stale-assertion "
             f"candidate(s) · {len(methods)} methods referenced · {len(rel_mons)} unmet monitors "
             f"in scope.\n\n---\n")

    # P6 M5: thread citations — tier column with capture state (tiered deployments)
    _th = []
    try:
        _cl = json.loads((DATA / "capture_ledger.json").read_text())
        _captured = {(e["thread"], e["round"]) for e in _cl.get("captures", [])}
        _cap_whole = {e["thread"] for e in _cl.get("captures", []) if e["round"] is None}
        _cap_by = {}
        for e in _cl.get("captures", []):
            _cap_by.setdefault((e["thread"], e["round"]), e["vr"])
        import re as _re
        for th in _cl.get("threads", []):
            tid = th["thread_id"]
            for label, text in inputs:
                for m in _re.finditer(rf"\b{_re.escape(tid)}(?:\s+R(\d+))?\b", text):
                    rnd = int(m.group(1)) if m.group(1) else None
                    cap = _cap_by.get((tid, rnd)) if rnd else None
                    state = (f"captured by {cap}" if cap
                             else ("whole-thread captured" if tid in _cap_whole
                                   else "UNRECONCILED"))
                    _th.append((tid, rnd, state))
        _th = sorted(set(_th))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # P6 M2: versioned-tier citations (tiered deployments only; empty otherwise)
    _vd = []
    try:
        _vdj = json.loads((DATA / "versioned_docs.json").read_text())
        _vd = tiers_mod.classify_versioned_citations(inputs, _vdj.get("docs", []))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    L.append("## 1. Cited documents — standing in the correction graph\n")
    L.append("### ⚠ Corrected / refuted / retracted — READ the correction before relying\n")
    if corrected:
        for cid, meta, status, lost, arc in corrected:
            cs = claim_status.get(cid, {})
            sig = ", ".join(cs.get("body_signals", []))
            wins = "; ".join(f"**{w}** [{rel}]" for w, rel in lost[:6])
            wins_s = f" · loses to: {wins}" if wins else " (own classified status; no explicit loser edge)"
            arcs_s = f" · arc {arc['id']} (`{arc.get('state')}`)" if arc else ""
            L.append(f"- **{cid}** ({cited[cid]}×) — {_clean(meta.get('title', ''))[:90]} · own status "
                     f"`{status}` · {cs.get('primary', '?')}{(' → [' + sig + ']') if sig else ''}"
                     f"{wins_s}{arcs_s}")
    else:
        L.append("- _none — no cited doc is a correction loser_")
    if dangling:
        L.append("\n### Dangling references (cited but not in the corpus)\n")
        L.append("- " + ", ".join(dangling))

    if _th:
        L.append("\n### Thread citations in scope (thread tier: verification-weight, NEVER receipts)\n")
        for tid, rnd, state in _th:
            r = f" R{rnd}" if rnd else ""
            mark = "⚠ " if "UNRECONCILED" in state else ""
            L.append(f"- {mark}**{tid}{r}** — {state}")

    if _vd:
        L.append("\n### Versioned documents in scope (tier verdicts — version-number supersession)\n")
        for path, status, sup in _vd:
            arrow = f" → READ **{sup}**" if sup else ""
            mark = "⚠ " if status.startswith("superseded") else ""
            L.append(f"- {mark}`{path}` — **{status}**{arrow}")
    L.append("\n### Cited and currently active (no incoming correction)\n")
    for cid, meta, status, _lost, arc in active[:ACTIVE_CAP]:
        cs = claim_status.get(cid, {})
        arcs_s = f" · arc `{arc.get('state')}`" if arc else ""
        L.append(f"- **{cid}** ({cited[cid]}×) — {_clean(meta.get('title', ''))[:80]} · "
                 f"{cs.get('primary', '?')}{arcs_s}")
    if len(active) > ACTIVE_CAP:
        L.append(f"- _…{len(active) - ACTIVE_CAP} more active docs cited_")
    L.append("")

    L.append("## 2. Objects touched — current canonical facts\n")
    if touched:
        for obj, n in touched:
            L.append(f"### `{obj['id']}` ({n}×) — {_clean(obj.get('title', ''))[:100]}")
            if obj.get("note"):
                L.append(f"_{_clean(obj['note'])[:200]}_")
            own = [p for p in (obj.get("properties") or {}).values() if p.get("prop") != "provenance"]
            for p in own[:6]:
                L.append(f"- {p['prop']} = **{_clean(p.get('value', ''))}** "
                         f"[{_clean(p.get('stratum', '?'))}, {p.get('vr_id', '?')}]")
            for pair in pairs.values():
                if pair.get("curve") != obj["id"]:
                    continue
                fx = " · ".join(f"{p['prop']}=**{_clean(p.get('value',''))}** [{_clean(p.get('stratum','?'))}, "
                                f"{p.get('vr_id','?')}]" for p in (pair.get("properties") or {}).values()
                                if p.get("prop") != "provenance")
                if fx:
                    L.append(f"- over **{pair['field']}**: {fx}")
            L.append("")
    else:
        L.append("_no canonical objects matched — if the plan names domain objects, the seed may "
                 "be behind the corpus; run `query.py coverage` + `/ontology-reconcile`._\n")

    L.append("## 3. Assertion check — input values vs seeded facts\n")
    if mismatches:
        L.append("**Stale-assumption candidates (input asserts a value the seed contradicts):**\n")
        L.extend(mismatches)
        L.append("")
    if anchors:
        L.append("**Confirmed anchors (input value matches the seeded fact):**\n")
        L.extend(anchors[:15])
        if len(anchors) > 15:
            L.append(f"- _…{len(anchors) - 15} more matching assertions_")
    if not mismatches and not anchors:
        L.append("_no numeric assertions found near a touched object's alias "
                 f"(±{_WINDOW}-char window, drift-detector value patterns)_")
    L.append("")

    L.append("## 4. Methods referenced — lifecycle & reliability\n")
    if methods:
        for m in methods:
            from collections import Counter
            c = Counter(e.get("state") for e in (m.get("events") or []))
            roll = f"{c.get('validated', 0)}v / {c.get('calibrated', 0)}c / {c.get('failed', 0)}f"
            warn = " ⚠ has produced a wrong answer — verify before reuse" \
                if m.get("has_produced_wrong_answer") else ""
            L.append(f"- **{m.get('id')}** — `{m.get('current_state')}` · "
                     f"{m.get('event_count', '?')} events ({roll}){warn}")
    else:
        L.append("_no registered methods named in the inputs_")
    L.append("")

    L.append("## 5. Unmet monitors touching this scope\n")
    if rel_mons:
        for m in rel_mons:
            w = " ".join((m.get("watch") or "").split())
            L.append(f"- **[{m.get('severity')}]** `{m.get('id')}` ({m.get('state')}) — "
                     f"{w[:180]}{'…' if len(w) > 180 else ''}")
    else:
        L.append("_none of the unmet monitors mention this scope's objects or cited docs_")
    L.append(f"\n_{other_unmet} further unmet/error monitors outside this scope — "
             f"`query.py monitors` for all._\n")

    L.append("## 6. Correction arcs containing cited documents\n")
    if cited_arcs:
        for a, hit in cited_arcs[:10]:
            ed = a.get("error_density")
            eds = f"{ed:.3f}" if isinstance(ed, (int, float)) else "?"
            L.append(f"- **{a.get('id')}** ({a.get('span')}) — `{a.get('state')}` · "
                     f"err_density {eds} · {a.get('corrections', 0)}/{a.get('size', 0)} corr · "
                     f"cited members: {', '.join(hit[:8])}")
    else:
        L.append("_no cited doc sits in a detected correction arc_")
    L.append("\n---\n_Source layers: file_meta, claim_status, supersession, arcs, objects, "
             "method_registry, monitors (data/rag). Scope = the input documents only; for the "
             "program-wide picture read `query.py brief`. A doc absent from §1's ⚠ list is not "
             "thereby certified — a detector's 0 is not a proof._\n")

    out_path = DATA / f"orient_{slug}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(L))
    return out_path, errors


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out_slug = None
    if "--out" in argv:
        i = argv.index("--out")
        try:
            out_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", argv[i + 1])[:60]
        except IndexError:
            print("--out requires a name")
            return 1
        del argv[i:i + 2]
    if not argv:
        print("Usage: orient.py <plan.md | MESSAGE.md | VR-N | AUDIT-N> [...] [--out slug]")
        return 1
    if not (DATA / "file_meta.json").exists():
        print("data/rag not built — run: bash scripts/rag/rebuild.sh")
        return 1
    out_path, errors = compile_orientation(argv, out_slug)
    if out_path is None:
        for e in errors:
            print(f"error: {e}")
        return 1
    print(out_path.read_text())
    rel = out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path
    print(f"[orient: wrote {rel}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
