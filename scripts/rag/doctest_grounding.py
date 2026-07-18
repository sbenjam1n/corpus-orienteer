#!/usr/bin/env python3
"""Sphinx-doctest-style grounding (axis-5 borrow of docs/CONCEPT_COVERAGE_IMPLEMENTATION_INDEX).

grounding_check.py answers "does the cited reproducer EXIST?". This answers the next question —
"does it still PRODUCE the cited value?" — by RE-RUNNING a curated set of fast, self-checking
reproducers (scripts/rag/doctest_seed.json) and asserting each one's expected token appears in its
output. That is exactly Sphinx doctest's job: re-run + check output, so a reproducer that silently
stops producing the headline number (env rot, a refactor, a data change) is caught.

OPT-IN / on-demand ONLY — deliberately NOT wired into rebuild.sh: re-running PARI/GP is heavy and
environment-dependent (needs `gp`), and a coverage/rebuild pass must stay fast and hermetic. Run:

    python3 scripts/rag/doctest_grounding.py      # exit 0 if all produce, 1 if any fail/timeout
    python3 scripts/rag/query.py doctest          # same, via the query dispatcher

Stdlib only. If `gp` is absent it SKIPs (exit 0) rather than failing — absence of the interpreter
is not a grounding regression.
"""
import json, subprocess, sys, shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = Path(__file__).resolve().parent / "doctest_seed.json"
RESULTS = ROOT / "data" / "rag" / "doctest_results.json"


def _write_results(rows, skipped=False):
    """P1(b): persist a machine-readable results artifact (gitignored build output)."""
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "skipped": skipped,
        "summary": {"produced": sum(1 for r in rows if r["pass"]),
                    "failed": sum(1 for r in rows if not r["pass"]),
                    "total": len(rows)},
        "results": rows,
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def run(write_json=False):
    seed = json.loads(SEED.read_text()) if SEED.exists() else {"checks": []}
    checks = seed.get("checks", [])
    needs_gp = any("gp " in c.get("cmd", "") for c in checks)
    if needs_gp and not shutil.which("gp"):
        print("doctest-grounding: SKIP — gp (PARI/GP) not on PATH; cannot re-run reproducers.")
        if write_json:
            _write_results([], skipped=True)
        return 0
    n_ok = n_fail = 0
    rows = []
    print(f"Doctest-grounding: re-run {len(checks)} curated reproducer(s) — assert each PRODUCES its cited value")
    print("=" * 70)
    for c in checks:
        cmd, expect, claim = c.get("cmd", ""), c.get("expect", ""), c.get("claim", "")
        got, status = "", None
        try:
            r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                               timeout=c.get("timeout", 60))
            out = (r.stdout or "") + (r.stderr or "")
            got = out[-400:]
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT  {claim}\n           [{cmd}]"); n_fail += 1; status = "timeout"
            rows.append({"claim": claim, "cmd": cmd, "expect": expect, "got": "<timeout>", "pass": False})
            continue
        except Exception as e:                                          # pragma: no cover
            print(f"  ERROR    {claim}  ({e})"); n_fail += 1
            rows.append({"claim": claim, "cmd": cmd, "expect": expect, "got": f"<error: {e}>", "pass": False})
            continue
        ok = bool(expect and expect in out)
        if ok:
            print(f"  produces {claim}   («{expect}»)"); n_ok += 1
        else:
            print(f"  MISSING  {claim}\n           expected «{expect}» not in output  [{cmd}]"); n_fail += 1
        rows.append({"claim": claim, "cmd": cmd, "expect": expect, "got": got, "pass": ok})
    print("=" * 70)
    print(f"doctest-grounding: {n_ok} produce / {n_fail} fail "
          + ("— all curated reproducers produce their cited value." if not n_fail
             else "— a reproducer no longer produces its cited value (grounding regression)."))
    if write_json:
        _write_results(rows)
        print(f"doctest-grounding: wrote {RESULTS.relative_to(ROOT)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(run(write_json="--json" in sys.argv[1:]))
