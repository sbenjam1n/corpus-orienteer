#!/usr/bin/env python3
"""verify_set — sum-distinctness certificate checker (the shared verification core).

A set A of positive integers is sum-distinct iff all 2^|A| subset sums are distinct.
Incremental bitset method: represent the multiset of achievable subset sums as bits of a
Python int (bit s set ⟺ some subset sums to s). Adding element e maps the sum-set S to
S ∪ (S+e); the update is collision-free iff (sums << e) & sums == 0. Python ints are
arbitrary precision, so this is overflow-safe at any n (the record ladder overflows
int64 near n≈57 — see VR-1 §conventions).

Conventions (VR-1): elements are distinct POSITIVE integers (0 collides {0} with {});
the empty set counts (sum 0); checking pairs of DISJOINT subsets is equivalent (shared
elements cancel) — this checker needs no such optimization, the bitset covers all pairs.

Usage:
  python3 arms/verify_set.py --set "20,31,37,40,42,43,44"
  python3 arms/verify_set.py --set-file sets.txt        # one comma-separated set per line
Exit 0 = every set sum-distinct; 2 = a collision (first colliding sum reported); 1 = bad input.
"""

import argparse
import json
import sys


MAX_BITS_DEFAULT = 2_000_000_000  # ~250 MB bitset ceiling (certificate arm ceiling ≈ n=28–30)


def is_sum_distinct(elements, max_bits=MAX_BITS_DEFAULT):
    """Return (True, None) or (False, {'element': e, 'colliding_sum': s}).

    Cost is O(total sum) BITS — for an n-element set near the Bohman bound that is
    ≈ n·0.22·2^n bits, so certificates are feasible only to n ≈ 30. Beyond the
    `max_bits` guard we refuse loudly (ValueError) rather than thrash: large-n
    sum-distinctness claims must rest on a THEOREM (e.g. Bohman 1996 for Conway–Guy
    sets), not on a certificate — and must be labeled at that grounding (VR-1 §strata).
    """
    if len(set(elements)) != len(elements) or any(e <= 0 for e in elements):
        raise ValueError("elements must be distinct positive integers")
    total = sum(elements)
    if total + 1 > max_bits:
        raise ValueError(
            f"certificate infeasible: needs {total + 1} bits (> {max_bits}); "
            f"at this size distinctness must come from a theorem, not a certificate"
        )
    sums = 1  # bit 0: the empty set
    for e in sorted(elements):
        overlap = (sums << e) & sums
        if overlap:
            s = overlap.bit_length() - 1  # one witness sum reachable two ways
            return False, {"element": e, "colliding_sum": s}
        sums |= sums << e
    return True, None


def _parse(s):
    return [int(x) for x in s.replace(" ", "").split(",") if x]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", help="comma-separated elements")
    g.add_argument("--set-file", help="file with one comma-separated set per line")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    lines = [args.set] if args.set else [
        ln for ln in open(args.set_file).read().splitlines() if ln.strip() and not ln.startswith("#")
    ]
    ok_all = True
    results = []
    for ln in lines:
        try:
            elems = _parse(ln)
            ok, info = is_sum_distinct(elems)
        except ValueError as ex:
            print(f"INVALID {ln!r}: {ex}", file=sys.stderr)
            sys.exit(1)
        ok_all &= ok
        results.append({"set": elems, "n": len(elems), "max": max(elems) if elems else 0,
                        "sum_distinct": ok, "collision": info})
        if not args.json:
            tag = "SUM-DISTINCT" if ok else f"COLLISION at element {info['element']} (sum {info['colliding_sum']})"
            print(f"n={len(elems):>2} max={max(elems):>6}  {tag}  {elems}")
    if args.json:
        print(json.dumps(results, indent=1))
    sys.exit(0 if ok_all else 2)


if __name__ == "__main__":
    main()
