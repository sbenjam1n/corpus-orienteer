#!/usr/bin/env python3
"""constants_curve — the empirical constant c(n) = best-known-max(n)/2^n against the
two theoretical rails (P4).

Canonical-import discipline (QUEUE §P4.1): values come from the same sources the rest
of the program trusts — A_VERIFIED (own-re-derived exact optima) from arms/exhaustive,
the seeded verified upper bounds (a(11)..a(13), VR-3/VR-5), and the calibrated
Conway–Guy generator for n beyond the table. Nothing is re-derived inline.

Rails: DFX floor binom(n, ⌊n/2⌋)/2^n (theorem, arXiv:2006.12988) below; Bohman's
asymptotic 0.22002 above (VR-1 §2.5: single-n values never touch the family record).

Arithmetic is EXACT (Fraction over Python ints) until final rendering — the overflow
discipline (VR-1 §2.6): u(67) exceeds uint64 and 2^n dwarfs int64 well before the
record ladder's range; a float-first implementation would quietly lose the tail.

Outputs (deterministic; content-derived only):
  results/constant_curve.json   — the table with exact numerator/denominator strings
  results/constant_curve.svg    — a dependency-free polyline rendering (n = 1..40)

Usage: python3 arms/constants_curve.py [--max-n 40]
"""

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exhaustive import A_VERIFIED  # noqa: E402
from conway_guy import u_sequence  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Exact by EXTERNAL exhaustion (not own-re-derived — A_VERIFIED stays non-circular;
# the curve may still label it exact, with the provenance in `source`)
EXACT_EXTERNAL = {10: (309, "Dyson 2025 exhaustive (external); witness + uniqueness cross-checked, VR-5")}
# Verified non-exact upper bounds (seed provenance; see domains/erdos1 seeds)
VERIFIED_UPPER = {11: (594, "CG-11 witness, VR-3"),
                  12: (1157, "posted set certified, VR-5"),
                  13: (2249, "posted set certified, VR-5")}
BOHMAN = 0.22002


def build(max_n):
    u = u_sequence(max_n)
    rows = []
    for n in range(1, max_n + 1):
        if n in A_VERIFIED:
            best, kind, src = A_VERIFIED[n], "exact", "own re-derivation (VR-3/VR-4)"
        elif n in EXACT_EXTERNAL:
            best, (kind, src) = EXACT_EXTERNAL[n][0], ("exact", EXACT_EXTERNAL[n][1])
        elif n in VERIFIED_UPPER:
            best, (kind, src) = VERIFIED_UPPER[n][0], ("upper_bound", VERIFIED_UPPER[n][1])
        else:
            best, kind, src = u[n], "upper_bound", "Conway–Guy u(n) (calibrated generator; sum-distinct by Bohman 1996)"
        c = Fraction(best, 2 ** n)
        dfx = Fraction(math.comb(n, n // 2), 2 ** n)
        rows.append({"n": n, "best_known_max": str(best), "kind": kind, "source": src,
                     "c_num": str(c.numerator), "c_den": str(c.denominator),
                     "c_float": float(c), "dfx_floor_float": float(dfx)})
    return rows


def svg(rows):
    W, H, PAD = 640, 360, 44
    xs = [r["n"] for r in rows]

    def pt(n, c):
        x = PAD + (n - xs[0]) / (xs[-1] - xs[0]) * (W - 2 * PAD)
        y = H - PAD - min(c, 0.6) / 0.6 * (H - 2 * PAD)
        return f"{x:.1f},{y:.1f}"

    best = " ".join(pt(r["n"], r["c_float"]) for r in rows)
    dfx = " ".join(pt(r["n"], r["dfx_floor_float"]) for r in rows)
    boh = f"{pt(xs[0], BOHMAN)} {pt(xs[-1], BOHMAN)}"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="11">
<rect width="{W}" height="{H}" fill="white"/>
<text x="{W/2:.0f}" y="18" text-anchor="middle" font-size="13">c(n) = best-known-max / 2^n — exact to n=10, verified bounds 11–13, Conway–Guy beyond</text>
<polyline points="{dfx}" fill="none" stroke="#888" stroke-dasharray="4 3"/>
<polyline points="{boh}" fill="none" stroke="#b00" stroke-dasharray="6 3"/>
<polyline points="{best}" fill="none" stroke="#036" stroke-width="1.6"/>
<text x="{W-PAD}" y="{H-PAD-BOHMAN/0.6*(H-2*PAD)-6:.0f}" text-anchor="end" fill="#b00">Bohman 0.22002 (asymptotic family record)</text>
<text x="{W-PAD}" y="{H-PAD+14}" text-anchor="end" fill="#888">DFX floor binom(n,n/2)/2^n</text>
<text x="{PAD}" y="{H-8}" fill="#036">n = {xs[0]}..{xs[-1]}; blue = best known</text>
</svg>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-n", type=int, default=40)
    args = ap.parse_args()
    rows = build(args.max_n)
    # overflow discipline receipts: the exact path must hold beyond machine words
    r67 = build(67)[-1]
    assert int(r67["best_known_max"]) > 2 ** 64, "u(67) must exceed uint64 (VR-1 §2.6)"
    out = ROOT / "results" / "constant_curve.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"rows": rows, "bohman_rail": BOHMAN,
                               "overflow_receipt_n67_max": r67["best_known_max"]},
                              indent=1) + "\n")
    (ROOT / "results" / "constant_curve.svg").write_text(svg(rows))
    print(f"constants_curve: {len(rows)} rows -> results/constant_curve.json + .svg "
          f"(c(10)={rows[9]['c_float']:.5f}, overflow receipt u(67)={r67['best_known_max']})")


if __name__ == "__main__":
    main()
