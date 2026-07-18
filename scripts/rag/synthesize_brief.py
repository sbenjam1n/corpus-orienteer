#!/usr/bin/env python3
"""Warm-start audit brief — P0 of the Perplexity-Brain integration.
Deterministic warm-start digest generator.

Brain's move: scheduled synthesis -> a compact context layer -> auto-loaded into the agent
before the next task, so it starts warm instead of from scratch. Our analogue: distill the
EXISTING graph layers (arcs / methods / monitors / drift) into ONE deterministic, bounded
markdown digest that the /vr-audit and /r14-loop skills read at pass start — so each pass
opens knowing what is currently broken, which methods to distrust, which monitors fire, and
what drifted, instead of re-deriving it cold by re-querying.

Pure distillation: stdlib only, NO LLM, NO new extraction. Deterministic given fixed inputs —
it reads the inputs' own `generated` stamp rather than the wall clock, so two runs over the
same data/rag produce byte-identical output. Every line cites its source id, and the digest
reuses the disciplined epistemics already baked into the graph (candidate-emitting, never a
verdict), so it cannot fabricate a PROVED state.

Run:
    python3 scripts/rag/synthesize_brief.py     # writes data/rag/audit_brief.md, prints path
    python3 scripts/rag/query.py brief          # same, via the query dispatcher
Wired as the final rebuild stage (rebuild.sh) after coverage.py.
"""
import json
from collections import Counter
from pathlib import Path

import os
ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag"))
OUT = DATA / "audit_brief.md"

# Arc states that mean "still open". 'converged' is resolved and is omitted (there is NO
# 'closed' state in the arc state machine: {converged, stalled, diagnosed, exploring, oscillating}).
ACTIVE_ARC_STATES = {"stalled", "oscillating", "exploring", "diagnosed"}
STUCK_ARC_STATES = {"stalled", "oscillating"}        # the worrying ones -> flagged with a marker
ARC_CAP = 15                                          # bound the digest; note the total
WATCH_TRUNC = 150
SEV_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
# P3(a) hot-arc -> monitor candidate. Threshold calibrated from the live distribution
# (mean error_density 0.291, median 0.250); 0.40 + size>=10 selects sustained error regions.
HOT_ED = 0.40
HOT_MIN_SIZE = 10


def _load(name):
    p = DATA / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _load_sessions():
    """P2: read the append-only per-pass session log (JSONL); [] if absent/empty. Read-only here
    (only record_session.py writes it), so the brief stays deterministic across repeated runs."""
    p = DATA / "audit_sessions.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _dismissed_by_monitor(sessions):
    """P3b: monitor_id -> {candidate -> 'disposition (audit)'} aggregated across all prior passes."""
    by = {}
    for s in sessions:
        for d in (s.get("dismissed_candidates") or []):
            mon = d.get("monitor")
            cand = d.get("candidate")
            if not mon or not cand:
                continue
            disp = d.get("disposition", "dismissed")
            audit = d.get("audit") or s.get("audit_id", "")
            by.setdefault(mon, {})[cand] = f"{disp}" + (f" ({audit})" if audit else "")
    return by


def _src_stamp():
    """A stable 'as-of' stamp pulled from the inputs (never wall-clock -> deterministic)."""
    for n in ("monitors.json", "object_drift.json"):
        d = _load(n)
        if isinstance(d, dict) and d.get("generated"):
            return d["generated"]
    return "unknown"


def _reliability(method):
    """P1(a): per-method reliability rollup from the EXISTING events[] (validated/calibrated/failed)."""
    c = Counter(e.get("state") for e in (method.get("events") or []))
    return c, f"{c.get('validated', 0)}v / {c.get('calibrated', 0)}c / {c.get('failed', 0)}f"


def section_arcs(arcs):
    if not arcs:
        return "_arcs.json missing or empty_\n"
    active = [a for a in arcs if a.get("state") in ACTIVE_ARC_STATES]
    active.sort(key=lambda a: (-(a.get("error_density") or 0.0), a.get("id", "")))
    shown = active[:ARC_CAP]
    lines = []
    for a in shown:
        st = a.get("state", "?")
        mark = "⚠️" if st in STUCK_ARC_STATES else "·"
        ed = a.get("error_density")
        eds = f"{ed:.3f}" if isinstance(ed, (int, float)) else "?"
        ces = a.get("correction_edges") or []
        last = ces[-1] if ces else None
        lasts = f"{last['source']} {last['relation']} {last['target']}" if last else "—"
        kes = ", ".join(e.get("entity", "") for e in (a.get("key_entities") or [])[:4])
        lines.append(
            f"- {mark} **{a.get('id')}** ({a.get('span')}) — `{st}` · "
            f"err_density {eds} · {a.get('corrections', 0)}/{a.get('size', 0)} corr · "
            f"last: {lasts}" + (f" · _{kes}_" if kes else "")
        )
    body = "\n".join(lines) if lines else "- _no active arcs_"
    note = (f"\n\n_{len(active)} active arcs (state ∈ stalled/oscillating/exploring/diagnosed); "
            f"showing top {len(shown)} by error_density. 'converged' arcs omitted (resolved)._")
    return body + note + "\n"


def section_methods(reg):
    if not reg:
        return "_method_registry.json missing or empty_\n"
    methods = list(reg.values()) if isinstance(reg, dict) else reg
    failed = [m for m in methods if m.get("current_state") == "failed"]
    wrong = [m for m in methods if m.get("has_produced_wrong_answer")]

    out = ["**(2a) Lifecycle state = `failed`** — structural dead-ends:"]
    if failed:
        for m in sorted(failed, key=lambda x: x.get("id", "")):
            _c, roll = _reliability(m)
            out.append(f"- **{m.get('id')}** — `failed` · {m.get('event_count', '?')} events "
                       f"({roll}) · wrong_answer={m.get('has_produced_wrong_answer')}")
    else:
        out.append("- _none_")

    out += ["", "**(2b) Has produced a wrong answer** — verify before reuse "
            "(lifecycle state may be calibrated/validated):"]
    if wrong:
        def fails(m):
            return _reliability(m)[0].get("failed", 0)
        for m in sorted(wrong, key=lambda x: (-fails(x), x.get("id", ""))):
            _c, roll = _reliability(m)
            out.append(f"- **{m.get('id')}** — `{m.get('current_state')}` · "
                       f"{m.get('event_count', '?')} events ({roll})")
    else:
        out.append("- _none_")

    out += ["", "_Note: (2a) and (2b) are ORTHOGONAL — a failed-state method need not have a "
            "wrong numeric answer (e.g. it failed structurally), and a validated method may carry "
            "historical wrong answers. Surfacing only one set would drop real signal, so both are shown._"]
    return "\n".join(out) + "\n"


def section_captures():
    """P6 M3: unreconciled thread rounds + receipt-laundering candidates, from
    capture_ledger.json. Empty string when the file is absent (single-tier mode or no
    thread tiers) so non-tiered deployments' briefs are byte-identical."""
    try:
        cl = json.loads((DATA / "capture_ledger.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    unrec, cands = cl.get("unreconciled_rounds", []), cl.get("receipt_candidates", [])
    if not unrec and not cands:
        return ""
    lines = ["\n## 3b. Correspondence capture state (cross-tier)\n"]
    for u in unrec[:10]:
        lines.append(f"- ✗ **{u['thread']} R{u['round']}** unreconciled — no capturing doc yet ({u['path']})")
    if len(unrec) > 10:
        lines.append(f"- _… {len(unrec) - 10} more unreconciled rounds_")
    for c in cands[:10]:
        lines.append(f"- ⚠ {c['vr']} cites {c['thread']} R{c['round']} in a receipt-like context — "
                     f"READ to certify (thread tiers are verification-weight, never receipts)")
    return "\n".join(lines) + "\n"


def section_monitors(mon, dismissed=None):
    dismissed = dismissed or {}
    monitors = mon.get("monitors") if isinstance(mon, dict) else mon
    if not monitors:
        return "_monitors.json missing or empty_\n"
    unmet = [m for m in monitors if m.get("state") == "unmet"]
    unmet.sort(key=lambda m: (SEV_ORDER.get(m.get("severity"), 9), m.get("id", "")))
    lines = []
    for m in unmet:
        w = " ".join((m.get("watch") or "").split())
        if len(w) > WATCH_TRUNC:
            w = w[:WATCH_TRUNC - 1] + "…"
        lines.append(f"- **[{m.get('severity')}]** `{m.get('id')}` — {w}")
        # P3b: if a prior pass already triaged candidates under this monitor, surface that so
        # the auditor does not re-investigate certified-historical items as if fresh.
        prior = dismissed.get(m.get("id"))
        if prior:
            items = ", ".join(f"{c} → {disp}" for c, disp in sorted(prior.items()))
            lines.append(f"  - _already triaged (do not re-investigate): {items}_")
    met = sum(1 for m in monitors if m.get("state") == "met")
    body = "\n".join(lines) if lines else "- _none unmet_"
    return body + f"\n\n_{len(unmet)} unmet / {met} met._\n"


def section_recent_passes(sessions):
    """P2: the last few audit passes from the session log (warm longitudinal context)."""
    if not sessions:
        return ("- _no session log yet (data/rag/audit_sessions.jsonl). Populated once the "
                "/vr-audit and /r14-loop skills call record_session.py at pass-end — see the "
                "plan's deferred-skill-wiring section._\n")
    recent = sessions[-5:]
    lines = []
    for s in reversed(recent):
        f = s.get("findings") or []
        um = s.get("monitors_unmet")
        ums = f" · {um} unmet monitors" if um is not None else ""
        diss = len(s.get("dismissed_candidates") or [])
        disss = f" · {diss} triaged" if diss else ""
        lines.append(f"- **{s.get('audit_id')}** ({s.get('date')}) — {len(f)} findings{ums}{disss}")
    return "\n".join(lines) + f"\n\n_{len(sessions)} passes recorded; showing last {len(recent)}._\n"


def section_drift(drift):
    if not drift:
        return "_object_drift.json missing or empty_\n"
    stats = drift.get("stats", {}) or {}
    flags = drift.get("flags", []) or []
    if flags:
        lines = [f"- {json.dumps(f, ensure_ascii=False)[:220]}" for f in flags[:20]]
        if len(flags) > 20:
            lines.append(f"- _…{len(flags) - 20} more_")
    else:
        lines = ["- _no active drift flags_"]
    nd = stats.get("no_detector", 0)
    caveat = (f"\n\n⚠️ _CAVEAT: {nd} structural facts (degree / defining_poly / disc) have NO drift "
              f"detector by design — for those, 'no flag' ≠ 'verified'. "
              f"stats: confirmed {stats.get('confirmed', 0)}, unconfirmed {stats.get('unconfirmed', 0)}, "
              f"flagged {stats.get('flagged', 0)}, unverified {stats.get('unverified', 0)}, no_detector {nd}._")
    return "\n".join(lines) + caveat + "\n"


def _fm_index(lst):
    """Index a file_meta list by id (fallback: file path) -> (version, file)."""
    idx = {}
    for r in (lst or []):
        k = r.get("id") or r.get("file")
        if k:
            idx[k] = (r.get("version"), r.get("file"))
    return idx


def section_changes(curr, prev):
    """P4: document-level delta since the previous rebuild snapshot (file_meta_prev.json)."""
    if curr is None:
        return "_file_meta.json missing_\n"
    cur = _fm_index(curr)
    if prev is None:
        return ("- _baseline — no previous snapshot to diff against "
                "(file_meta_prev.json is written after this rebuild; the delta appears next pass)._\n")
    old = _fm_index(prev)
    added = sorted(set(cur) - set(old))
    removed = sorted(set(old) - set(cur))
    bumped = [(k, old[k][0], cur[k][0]) for k in sorted(set(cur) & set(old)) if cur[k][0] != old[k][0]]
    lines = []
    if added:
        lines.append(f"- **added ({len(added)}):** " + ", ".join(added[:25]) + (" …" if len(added) > 25 else ""))
    if removed:
        lines.append(f"- **removed ({len(removed)}):** " + ", ".join(removed[:25]) + (" …" if len(removed) > 25 else ""))
    for k, ov, cv in bumped[:25]:
        lines.append(f"- **version bump:** {k}  {ov} → {cv}")
    if len(bumped) > 25:
        lines.append(f"- _…{len(bumped) - 25} more version bumps_")
    if not lines:
        lines = ["- _no document add/remove/version-bump since last rebuild_"]
    caveat = ("\n\n⚠️ _CAVEAT: this delta tracks document add/remove/version, NOT prose content. "
              "A change touching only a structural fact (degree / defining_poly / disc — 77 no_detector) "
              "can appear here (or not at all) with NO drift signal; 'changed, no drift' ≠ 'safe'. Verify manually._")
    return "\n".join(lines) + caveat + "\n"


def section_hot_arcs(arcs):
    """P3(a): active arcs above the hot threshold — candidates to promote to a standing monitor."""
    if not arcs:
        return "_arcs.json missing_\n"
    hot = [a for a in arcs if a.get("state") in ACTIVE_ARC_STATES
           and (a.get("error_density") or 0.0) >= HOT_ED and a.get("size", 0) >= HOT_MIN_SIZE]
    hot.sort(key=lambda a: (-(a.get("error_density") or 0.0), a.get("id", "")))
    if not hot:
        return f"- _no active arc exceeds the hot threshold (error_density ≥ {HOT_ED}, size ≥ {HOT_MIN_SIZE})_\n"
    out = [f"_Active arcs with error_density ≥ {HOT_ED} and size ≥ {HOT_MIN_SIZE} — sustained error regions. "
           "If no standing monitor already covers one, consider promoting it via /ontology-reconcile "
           "(propose-not-apply; the auditor decides):_", ""]
    for a in hot:
        ed = a.get("error_density") or 0.0
        out.append(f"- **{a.get('id')}** ({a.get('span')}) — `{a.get('state')}` · err_density {ed:.3f} · "
                   f"{a.get('corrections', 0)}/{a.get('size', 0)} corr · stub id "
                   f"`monitor_{str(a.get('id', '')).replace('-', '_')}`")
    return "\n".join(out) + "\n"


def build_brief():
    arcs = _load("arcs.json")
    reg = _load("method_registry.json")
    mon = _load("monitors.json")
    drift = _load("object_drift.json")
    fm_cur = _load("file_meta.json")
    fm_prev = _load("file_meta_prev.json")
    sessions = _load_sessions()
    dismissed = _dismissed_by_monitor(sessions)

    n_active = len([a for a in (arcs or []) if a.get("state") in ACTIVE_ARC_STATES])
    methods = list(reg.values()) if isinstance(reg, dict) else (reg or [])
    n_failed = len([m for m in methods if m.get("current_state") == "failed"])
    n_wrong = len([m for m in methods if m.get("has_produced_wrong_answer")])
    mons = mon.get("monitors") if isinstance(mon, dict) else (mon or [])
    n_unmet = len([m for m in mons if m.get("state") == "unmet"])

    return (
        "# Audit Warm-Start Brief\n\n"
        f"_Deterministic digest of data/rag as of `{_src_stamp()}`. Generated by "
        "`scripts/rag/synthesize_brief.py`. "
        "Read this FIRST at the start of a /vr-audit or /r14-loop pass — it is a warm start, not a "
        "verdict: every item is a candidate to READ, never a settled finding._\n\n"
        f"**At a glance:** {n_active} active correction arcs · {n_failed} failed-state methods · "
        f"{n_wrong} methods with a historical wrong answer · {n_unmet} unmet monitors.\n\n"
        "---\n\n"
        "## 1. Active correction arcs (unresolved)\n\n" + section_arcs(arcs) + "\n"
        "## 2. Methods to distrust\n\n" + section_methods(reg) + "\n"
        "## 3. Unmet monitors (by severity)\n\n" + section_monitors(mon, dismissed) + "\n"
        + section_captures() +
        "## 4. Drift\n\n" + section_drift(drift) + "\n"
        "## 5. Changed since last pass\n\n" + section_changes(fm_cur, fm_prev) + "\n"
        "## 6. Hot arcs → consider a standing monitor\n\n" + section_hot_arcs(arcs) + "\n"
        "## 7. Recent passes\n\n" + section_recent_passes(sessions) +
        "\n---\n_End of brief. Source layers: arcs.json, method_registry.json, monitors.json, "
        "object_drift.json, file_meta.json, audit_sessions.jsonl. This digest distills them; it "
        "adds no new claims._\n"
    )


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_brief())
    out = OUT.relative_to(ROOT) if OUT.is_relative_to(ROOT) else OUT
    print(f"audit-brief: wrote {out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
