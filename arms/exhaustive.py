#!/usr/bin/env python3
"""exhaustive — exact-optimum search for a(n) = minimal largest element of an
n-element sum-distinct set (OEIS A276661).

Decision procedure: feasible(n, M) = "does an n-element sum-distinct set with largest
element EXACTLY M exist?" (a(n) = min M with feasible; feasibility with max ≤ M is
monotone in M, so we scan M upward from a lower bound). DFS chooses elements in
DESCENDING order below M, maintaining the subset-sum bitset incrementally
(collision ⟺ (sums << e) & sums ≠ 0 — exact, overflow-safe, Python bigint).

Prunes (all conservative — completeness of the negative side is the load-bearing
claim, see VR-1 §asymmetric-proof-burden). Each rejects only branches that PROVABLY
contain no completion; no heuristic cutoffs, so an exhausted scan is a proof of
infeasibility for that (n, M):
  P1 element-supply: need k more elements, all distinct in [1..cap] ⟹ cap ≥ k.
  P2 doubling (remaining subset): the k remaining elements alone must be sum-distinct
     within [1..cap], so 2^k ≤ k·cap + 1.
  P3 full-sum feasibility: ALL 2^n subset sums of the full set are distinct in
     [0, total], so total ≥ 2^n − 1; prune when partial_sum + (best achievable
     remaining sum = k·cap − k(k−1)/2) < 2^n − 1.
  P4 subset-optimum floor: the k remaining elements form a sum-distinct k-set (subsets
     of sum-distinct sets are sum-distinct), whose max element is their largest, ≤ cap;
     so cap ≥ floor(k) where floor(k) = OWN-REPRODUCED a(k) for k ≤ 8 (VR-3 exhaustive,
     8/8 published agreement) else binom(k, ⌊k/2⌋) (Dubroff–Fox–Xu theorem,
     arXiv:2006.12988). NON-CIRCULARITY RULE: the floor table contains only values this
     repo has itself re-derived — never the published value a gate run is re-deriving.
# a(9)=161 added after the n=9 gate (results/gate_n9.json: 35 rungs exhausted, VR-4).
  P5 variance (second moment, the classical Erdős–Moser argument): the 2^n subset sums
     are distinct integers, and the subset-sum distribution has variance Σa_i²/4, while
     any 2^n distinct integers have variance ≥ ((2^n)²−1)/12; hence Σa_i² ≥ (4^n−1)/3.
     Prune when partial_sq + (best achievable remaining Σ of squares =
     Σ_{i=0..k−1}(cap−i)²) < (4^n−1)/3.

Scan floors (--floor): "dfx" (default) starts the M-scan at binom(n, ⌊n/2⌋) (theorem);
"doubling" at ceil((2^n − 1)/n) (self-contained cross-check). The JSON records which
floor the negative side rests on.

Ledger (--ledger FILE): per-M checkpointing. Completed Ms are recorded and skipped on
restart; a killed run loses at most the current M's partial work (M-granularity
resumability; the negative claim for a ledger M rests on the run that completed it).

Usage:
  python3 arms/exhaustive.py --n 7                       # determine a(7) exactly
  python3 arms/exhaustive.py --n 9 --budget 900          # gate run (dfx floor)
  python3 arms/exhaustive.py --n 11 --from-m 462 --to-m 500 --budget 3600 \
      --ledger results/n11_ledger.json                   # frontier window slice
Output: one JSON object (result, witness, nodes, elapsed) on stdout; progress on stderr.
"""

import argparse
import json
import math
import sys
import time


class Budget(Exception):
    pass


def feasible_with_max_c(n, M, deadline, stats, binary):
    """Dispatch one (n, M) question to the C kernel (arms/feasible.c) — an exact DFS
    mirror of feasible_with_max, cross-validated by identical per-M node counts
    (n=8, M=83: 9,388,500 nodes in both engines). The kernel's A_VERIFIED table is
    sync-checked at driver startup (--table)."""
    import subprocess
    budget_left = max(1.0, deadline - time.monotonic())
    proc = subprocess.run([binary, str(n), str(M), f"{budget_left:.1f}"],
                          capture_output=True, text=True)
    out = proc.stdout.strip().split()
    if not out:
        raise RuntimeError(f"C kernel produced no output (exit {proc.returncode}): {proc.stderr}")
    if out[0] == "witness":
        stats["nodes"] += int(out[1])
        return sorted(int(x) for x in out[2:])
    if out[0] == "infeasible":
        stats["nodes"] += int(out[1])
        return None
    if out[0] == "budget":
        stats["nodes"] += int(out[1])
        raise Budget()
    raise RuntimeError(f"C kernel unexpected output: {proc.stdout!r}")


def check_c_table_sync(binary):
    """The kernel's own-reproduced table must equal A_VERIFIED (wrong-binding guard)."""
    import subprocess
    out = subprocess.run([binary, "--table"], capture_output=True, text=True).stdout.split()
    c_table = {i + 1: int(v) for i, v in enumerate(out)}
    if c_table != A_VERIFIED:
        raise SystemExit(f"C kernel A_VERIFIED out of sync: {c_table} != {A_VERIFIED}")


# OWN-REPRODUCED exact optima (VR-3: exhaustive n=1..8, 8/8 published agreement).
# Extend ONLY after a gate run in this repo re-derives the next value (see VR-4+);
# never seed from the published table alone (non-circularity rule above).
A_VERIFIED = {1: 1, 2: 2, 3: 4, 4: 7, 5: 13, 6: 24, 7: 44, 8: 84, 9: 161}


def subset_floor(k):
    """Conservative lower bound on the max element of ANY k-element sum-distinct set."""
    if k <= 0:
        return 0
    v = A_VERIFIED.get(k)
    return v if v is not None else math.comb(k, k // 2)


def feasible_with_max(n, M, deadline, stats, stride=1, offset=0):
    """Sum-distinct set of size n with largest element exactly M? Returns witness or None.
    Raises Budget if the deadline passes (search state NOT exhausted). stride/offset
    partition the depth-1 element choices across workers (P7 M1); defaults = the
    whole tree."""
    sums = 1 | (1 << M)  # {} and {M}
    need = (1 << n) - 1        # total sum must reach this (P3)
    need_sq = ((1 << (2 * n)) - 1) // 3  # Σa_i² must reach this (P5, variance bound)

    def max_sq(k, cap):
        # largest achievable Σ of squares of k distinct elements ≤ cap
        return sum((cap - i) * (cap - i) for i in range(k))

    def dfs(k, cap, sums, chosen, partial, partial_sq, depth=1):
        # k elements still to choose, all in [1..cap]; partial(_sq) = Σ chosen (Σ squares)
        if k == 0:
            return chosen
        stats["nodes"] += 1
        if stats["nodes"] % 500000 == 0:
            if time.monotonic() > deadline:
                raise Budget()
            print(f"    …n={n} M={M} nodes={stats['nodes']:,}", file=sys.stderr, flush=True)
        if cap < k:                                          # P1
            return None
        fl = subset_floor(k)
        if cap < fl:                                         # P4
            return None
        if partial + k * cap - k * (k - 1) // 2 < need:      # P3
            return None
        if partial_sq + max_sq(k, cap) < need_sq:            # P5
            return None
        if (1 << k) > k * cap + 1:                           # P2
            return None
        for e in range(cap, fl - 1, -1):                     # e = largest remaining ⟹ e ≥ floor(k)
            if depth == 1 and (cap - e) % stride != offset:  # P7 M1 partition
                continue
            overlap = (sums << e) & sums
            if overlap == 0:
                w = dfs(k - 1, e - 1, sums | (sums << e), chosen + [e],
                        partial + e, partial_sq + e * e, depth + 1)
                if w:
                    return w
        return None

    w = dfs(n - 1, M - 1, sums, [M], M, M * M)
    return sorted(w) if w else None


def lower_bound(n, floor_kind="dfx"):
    """Starting M for the scan. "dfx": binom(n, n//2) (Dubroff–Fox–Xu 2021 theorem,
    arXiv:2006.12988). "doubling": ceil((2^n − 1)/n), self-contained. The negative side
    of an exact result is "no set with max < a(n)" DOWN TO this floor plus the cited
    theorem below it."""
    doubling = max(n, -(-((1 << n) - 1) // n))
    if floor_kind == "doubling":
        return doubling
    return max(doubling, math.comb(n, n // 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--from-m", type=int, help="start of M scan (default: the chosen floor)")
    ap.add_argument("--to-m", type=int, help="inclusive end of M scan (default: unbounded)")
    ap.add_argument("--budget", type=float, default=300.0, help="wall-clock seconds (default 300)")
    ap.add_argument("--floor", choices=["dfx", "doubling"], default="dfx",
                    help="scan floor: dfx = binom(n,n//2) (theorem); doubling = self-contained")
    ap.add_argument("--ledger", help="per-M checkpoint file (completed Ms skipped on restart)")
    ap.add_argument("--engine", choices=["py", "c"], default="py",
                    help="feasibility kernel: py (reference) or c (arms/feasible, exact mirror)")
    args = ap.parse_args()

    c_binary = None
    if args.engine == "c":
        from pathlib import Path as _P
        c_binary = str(_P(__file__).resolve().parent / "feasible")
        if not _P(c_binary).exists():
            raise SystemExit("C engine requested but arms/feasible not built "
                             "(gcc -O2 -o arms/feasible arms/feasible.c)")
        check_c_table_sync(c_binary)

    n = args.n
    floor_val = lower_bound(n, args.floor)
    m0 = args.from_m if args.from_m else floor_val
    deadline = time.monotonic() + args.budget
    t0 = time.monotonic()
    stats = {"nodes": 0}
    ledger_path = args.ledger
    ledger = {"n": n, "completed": {}}
    if ledger_path:
        try:
            prev = json.load(open(ledger_path))
            if prev.get("n") == n:
                ledger = prev
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_ledger():
        if ledger_path:
            with open(ledger_path, "w") as f:
                json.dump(ledger, f, indent=1)

    result = {"arm": "exhaustive", "version": 2, "engine": args.engine,
              "n": n, "scan_from": m0,
              "floor": {"kind": args.floor, "value": floor_val,
                        "provenance": "binom(n,n//2): Dubroff-Fox-Xu arXiv:2006.12988"
                                      if args.floor == "dfx" else "ceil((2^n-1)/n), self-contained"},
              "prunes": ["P1", "P2", "P3", "P4", "P5"],
              "p4_verified_table": A_VERIFIED,
              "budget_s": args.budget}

    M = m0
    skipped = 0
    try:
        while args.to_m is None or M <= args.to_m:
            done = ledger["completed"].get(str(M))
            if done and done.get("status") == "infeasible":
                skipped += 1
                M += 1
                continue
            print(f"  n={n}: testing M={M}", file=sys.stderr, flush=True)
            nodes_before = stats["nodes"]
            t_m = time.monotonic()
            w = (feasible_with_max_c(n, M, deadline, stats, c_binary) if c_binary
                 else feasible_with_max(n, M, deadline, stats))
            m_rec = {"nodes": stats["nodes"] - nodes_before,
                     "elapsed_s": round(time.monotonic() - t_m, 3)}
            if w:
                m_rec.update(status="witness", witness=w)
                ledger["completed"][str(M)] = m_rec
                save_ledger()
                result.update(status="exact", a_n=M, witness=w,
                              note=f"infeasible exhaustively for all max in [{m0},{M-1}]"
                                   f"{f' ({skipped} from ledger)' if skipped else ''}; witness at {M}")
                if args.from_m and args.from_m > floor_val:
                    result["status"] = "witness_upper_bound"
                    result["note"] = (f"scan started at {m0} > floor {floor_val}: result is an "
                                      f"upper bound + a [{m0},{M-1}] infeasibility certificate only")
                break
            m_rec.update(status="infeasible")
            ledger["completed"][str(M)] = m_rec
            save_ledger()
            M += 1
        else:
            result.update(status="window_infeasible", window=[m0, args.to_m],
                          note=f"no n={n} sum-distinct set with max in [{m0},{args.to_m}] "
                               f"(exhaustive{f', {skipped} Ms from ledger' if skipped else ''})")
    except Budget:
        result.update(status="budget_exhausted", reached_m=M,
                      note=f"M in [{m0},{M-1}] exhausted infeasible"
                           f"{f' ({skipped} from ledger)' if skipped else ''}; "
                           f"M={M} INCOMPLETE — no negative claim at {M}")

    result.update(nodes=stats["nodes"], elapsed_s=round(time.monotonic() - t0, 3))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
