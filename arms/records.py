#!/usr/bin/env python3
"""records — the n >= 14 record ladder (P3 §3): certified Conway–Guy baseline table
plus a bounded, deterministic perturbation search around the CG structure.

Calibration discipline (P1 §2): before any "improvement" may be reported, the arm must
reproduce the CG maxima as certified sum-distinct sets — that IS the baseline table.
Claim-inflation guard (VR-1 §2.5): a single-n improvement is a TABLE ENTRY; the Bohman
asymptotic record is untouchable by single-n results.

Baseline: for each n, the CG set {u(n) − u(j)} is certified by the exact bitset
(feasible up to n ≈ 28; the guard refuses beyond — the MITM design item covers 30+).

Perturbation search (bounded, deterministic — no randomness): for each n, candidate
sets are the CG set with ONE element lowered by delta ∈ {1..D} and the whole set
shifted down by s ∈ {0..S} (drop candidates with collisions/nonpositive/duplicate
elements). Any certified candidate with max < u(n) is an improvement (expected result
at these n: none — the CG structure is locally rigid; the negative result with counts
is the honest artifact).

Usage:
  python3 arms/records.py --baseline 14 25
  python3 arms/records.py --perturb 14 16 --delta 3 --shift 2
Outputs: results/records_baseline.json / results/records_perturb.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_set import is_sum_distinct  # noqa: E402
from conway_guy import conway_guy_set, u_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def baseline(lo, hi):
    rows = []
    u = u_sequence(hi)
    for n in range(lo, hi + 1):
        s = conway_guy_set(n)
        ok, info = is_sum_distinct(s)
        if not ok:
            raise SystemExit(f"CG-{n} FAILED certification: {info} — STOP (Bohman's "
                             f"theorem contradicted ⟹ our generator or verifier is wrong)")
        rows.append({"n": n, "max": u[n], "set": s, "certified": True})
        print(f"  CG-{n}: max {u[n]:,} certified ({len(s)} elements)", file=sys.stderr)
    return rows


def perturb(lo, hi, delta_max, shift_max):
    rows = []
    for n in range(lo, hi + 1):
        base = conway_guy_set(n)
        u_n = max(base)
        tried = 0
        improvements = []
        for s in range(0, shift_max + 1):
            shifted = [x - s for x in base]
            for i in range(len(base)):
                for d in range(1, delta_max + 1):
                    cand = sorted(shifted[:i] + [shifted[i] - d] + shifted[i + 1:])
                    tried += 1
                    if cand[0] <= 0 or len(set(cand)) != len(cand):
                        continue
                    if max(cand) >= u_n:
                        continue
                    ok, _ = is_sum_distinct(cand)
                    if ok:
                        improvements.append({"max": max(cand), "set": cand,
                                             "move": {"shift": s, "elem": i, "delta": d}})
        rows.append({"n": n, "cg_max": u_n, "candidates_tried": tried,
                     "improvements": improvements})
        print(f"  n={n}: {tried} candidates, {len(improvements)} improvements",
              file=sys.stderr)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--perturb", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--delta", type=int, default=3)
    ap.add_argument("--shift", type=int, default=2)
    args = ap.parse_args()
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    if args.baseline:
        rows = baseline(*args.baseline)
        (out / "records_baseline.json").write_text(json.dumps(
            {"arm": "records_baseline", "rows": rows}, indent=1) + "\n")
        print(f"baseline: {len(rows)} CG sets certified -> results/records_baseline.json")
    if args.perturb:
        rows = perturb(*args.perturb, args.delta, args.shift)
        (out / "records_perturb.json").write_text(json.dumps(
            {"arm": "records_perturb", "delta_max": args.delta, "shift_max": args.shift,
             "rows": rows}, indent=1) + "\n")
        total = sum(r["candidates_tried"] for r in rows)
        found = sum(len(r["improvements"]) for r in rows)
        print(f"perturb: {total} candidates, {found} improvements -> results/records_perturb.json")


if __name__ == "__main__":
    main()
