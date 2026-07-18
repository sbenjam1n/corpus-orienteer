#!/usr/bin/env python3
"""conway_guy — Conway–Guy sequence generator + calibrated sum-distinct set builder.

The Conway–Guy sequence u (OEIS A005318): u(0)=0, u(1)=1,
u(k+1) = 2·u(k) − u(k − r(k)) with r(k) = nearest integer to sqrt(2k).
The n-element Conway–Guy set is {u(n) − u(j) : j = 0..n−1}; Bohman (1996) proved these
are sum-distinct for all n. Their maxima u(n) give the classical upper-bound ladder for
a(n) (minimal possible max element of an n-element sum-distinct set, OEIS A276661):
optimal at every exactly-known n ≤ 10, and REFUTED as optimal at n = 12, 13
(posted constructions beat u(12)=1164 and u(13)=2284 — see VR-2).

CALIBRATION: the generator asserts its first 14 terms against the published OEIS values
embedded below before emitting anything. A recurrence bug therefore fails loudly instead
of silently shipping wrong sets (canonical-source discipline, QUEUE §P4).

Usage:
  python3 arms/conway_guy.py --n 13            # print u(0..13) + the 13-element set
  python3 arms/conway_guy.py --n 20 --verify   # also certify the set via verify_set
  python3 arms/conway_guy.py --n 60 --json
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_set import is_sum_distinct  # noqa: E402

# A005318(0..13), quoted from OEIS / the frontier survey (VR-1, VR-2).
CALIBRATION = [0, 1, 2, 4, 7, 13, 24, 44, 84, 161, 309, 594, 1164, 2284]


def u_sequence(n):
    u = [0, 1]
    for k in range(1, n):
        r = int(math.floor(math.sqrt(2 * k) + 0.5))
        u.append(2 * u[k] - u[k - r])
    return u[: n + 1]


def conway_guy_set(n):
    u = u_sequence(n)
    return sorted(u[n] - u[j] for j in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--verify", action="store_true", help="certify sum-distinctness of the set")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    u = u_sequence(max(args.n, len(CALIBRATION) - 1))
    if u[: len(CALIBRATION)] != CALIBRATION:
        print(f"CALIBRATION FAILURE: generator {u[:len(CALIBRATION)]} != OEIS {CALIBRATION}",
              file=sys.stderr)
        sys.exit(3)

    s = conway_guy_set(args.n)
    verified = None
    if args.verify:
        ok, info = is_sum_distinct(s)
        verified = ok
        if not ok:
            print(f"VERIFY FAILURE at n={args.n}: {info}", file=sys.stderr)
            sys.exit(2)
    out = {"n": args.n, "u_n": u[args.n], "set": s, "calibrated_terms": len(CALIBRATION),
           "sum_distinct_verified": verified}
    if args.json:
        print(json.dumps(out))
    else:
        print(f"u(0..{args.n}) = {u[: args.n + 1]}")
        print(f"CG set (n={args.n}, max={u[args.n]}): {s}"
              + ("" if verified is None else f"  [sum-distinct: {verified}]"))
    sys.exit(0)


if __name__ == "__main__":
    main()
