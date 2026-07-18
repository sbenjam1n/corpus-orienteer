#!/usr/bin/env python3
"""Per-pass session recorder — P2 of the Perplexity-Brain integration.
See Plans/perplexity_brain_integration_execution.md.

Brain adds a node to its context graph after every task (what was used, what held up, what was
corrected) — a point-in-time SESSION record, distinct from the durable AUDIT-### documents the
corpus already carries (199 AUDIT-sourced supersession edges). This appends one such ephemeral
record per /vr-audit (or /r14-loop) pass to data/rag/audit_sessions.jsonl, so the warm-start
brief can show "recent passes" (P2) and annotate monitor candidates a prior pass already
triaged/dismissed (P3b) — "remember corrections, don't re-walk dead ends".

Append-only + flock-serialized: VR-1029 flags a parallel-write hazard on scripts/rag/ outputs,
so each append takes an exclusive lock (one atomic line write), making concurrent writers safe.

Usage (the deferred skill call-site appends a JSON object; see the plan's "deferred skill
wiring" section):
    echo '{"audit_id":"AUDIT-222","date":"2026-06-21","findings":[...]}' | \
        python3 scripts/rag/record_session.py
    python3 scripts/rag/record_session.py --json '{"audit_id":"AUDIT-222","date":"2026-06-21"}'

Record schema (only audit_id + date are required; the rest are optional and free-form):
    {
      "audit_id": "AUDIT-222",          # the pass's AUDIT-### (or a pass tag)
      "date": "2026-06-21",
      "briefs_read": true,              # did the pass open the warm-start brief?
      "findings": [{"vr_id": "VR-1040", "severity": "MEDIUM", "fix_state": "proposed"}],
      "monitors_unmet": 7,             # monitor state at the pass
      "dismissed_candidates": [        # P3b: candidates triaged-and-dismissed this pass
        {"candidate": "VR-66", "monitor": "tower_object_forbidden_predicate",
         "disposition": "certified-historical", "audit": "AUDIT-221"}
      ]
    }
Stdlib only. Never raises on a malformed record beyond a clear error + exit 2.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = Path(os.environ.get("RAG_DATA_DIR", ROOT / "data" / "rag")) / "audit_sessions.jsonl"


def record(obj):
    """Append one validated session record as a single JSON line, serialized by an exclusive lock."""
    if not isinstance(obj, dict):
        raise ValueError("session record must be a JSON object")
    if not obj.get("audit_id") or not obj.get("date"):
        raise ValueError("session record requires 'audit_id' and 'date'")
    line = json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)   # VR-1029: serialize concurrent appenders
        except (ImportError, OSError):
            pass                                     # non-POSIX / no-flock: single small append is still ~atomic
        f.write(line)
        f.flush()
    return obj["audit_id"]


def _read_arg():
    rest = sys.argv[1:]
    if rest and rest[0] == "--json" and len(rest) > 1:
        return rest[1]
    if rest and rest[0] not in ("--json",):
        return rest[0]
    return sys.stdin.read()


def main():
    raw = _read_arg()
    if not raw or not raw.strip():
        print("record_session: no record provided (pass JSON via stdin or --json).", file=sys.stderr)
        return 2
    try:
        obj = json.loads(raw)
        aid = record(obj)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"record_session: invalid record — {e}", file=sys.stderr)
        return 2
    print(f"record_session: appended pass {aid} to {LOG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
