#!/usr/bin/env python3
"""gate_parallel — parallel exact-optimum gate: exhaust every rung M in
[floor, witness_m − 1] (one arms/feasible process per rung, N workers) and certify the
witness rung, establishing a(n) = witness_m.

Rungs are INDEPENDENT feasibility questions, so any dispatch order is sound; we run
hardest-first (descending M — cost grows toward the feasibility edge) so the long pole
starts immediately. The witness ceiling may be chosen from published data (e.g. the
Conway–Guy value): the PROOF does not depend on how the ceiling was picked — the
witness is certificate-verified and everything below is exhausted. If a rung below the
ceiling unexpectedly finds a witness, the ceiling drops and higher rungs become moot
(that would be a discovery, recorded as such).

Ledger: same schema as exhaustive.py --ledger (completed rungs skipped on restart,
merged across sequential/parallel runs). Budget: overall wall-clock; in-flight rungs
get the remaining budget; unfinished rungs stay off the ledger (no negative claim).

Usage:
  python3 arms/gate_parallel.py --n 9 --witness-m 161 --workers 4 \
      --budget 3600 --ledger results/gate_n9_ledger.json --out results/gate_n9.json
"""

import argparse
import json
import math
import subprocess
import sys
import time


def _p(msg):
    """Progress print that survives a closed stderr (a `| head` on a launcher once
    killed the main loop mid-campaign while queued rungs kept burning CPU unrecorded —
    the ledger, not the console, is the record; console loss must never abort a run)."""
    import sys as _s
    try:
        print(msg, file=_s.stderr, flush=True)
    except (BrokenPipeError, OSError):
        pass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exhaustive import A_VERIFIED, lower_bound, check_c_table_sync  # noqa: E402

BINARY = str(Path(__file__).resolve().parent / "feasible")

# P7 robustness: track live kernel children so a killed/exiting driver never leaks
# orphan `feasible` processes that keep burning cores under their own budget (observed:
# pkill on the driver once left 4 orphans running). A signal handler + atexit reap them.
import atexit
import signal
_LIVE = set()


def _reap(*_a):
    for pr in list(_LIVE):
        try:
            pr.kill()
        except Exception:
            pass
    if _a:
        sys.exit(143)


atexit.register(_reap)
for _sig in (signal.SIGTERM, signal.SIGINT):
    signal.signal(_sig, _reap)


def run_rung(n, M, budget_left, intra=1):
    """One rung. intra=K (P7 M1): K concurrent kernel processes partition the rung's
    depth-1 subtrees (stride/offset); rung infeasible iff ALL infeasible; any witness
    wins (others killed); any budget-kill ⟹ no claim. Node counts are summed (exact:
    workers cover every node once, + K−1 root increments — mirror-tested)."""
    t0 = time.monotonic()
    b = f"{max(1.0, budget_left):.1f}"
    procs = [subprocess.Popen([BINARY, str(n), str(M), b] +
                              ([str(intra), str(i)] if intra > 1 else []),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for i in range(intra)]
    _LIVE.update(procs)
    results = []
    for pr in procs:
        out, _err = pr.communicate()
        results.append(out.strip().split())
    for pr in procs:
        _LIVE.discard(pr)
    elapsed = round(time.monotonic() - t0, 3)
    if any(not r for r in results):
        return {"status": "error", "elapsed_s": elapsed, "stderr": "empty kernel output"}
    for r in results:
        if r[0] == "witness":
            return {"status": "witness", "nodes": sum(int(x[1]) for x in results if len(x) > 1),
                    "witness": sorted(int(v) for v in r[2:]), "elapsed_s": elapsed}
    nodes = sum(int(r[1]) for r in results)
    if all(r[0] == "infeasible" for r in results):
        return {"status": "infeasible", "nodes": nodes, "elapsed_s": elapsed,
                **({"intra": intra} if intra > 1 else {})}
    return {"status": "budget", "nodes": nodes, "elapsed_s": elapsed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--witness-m", type=int, required=True,
                    help="ceiling to certify (a witness must exist here)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget", type=float, default=3600.0)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--floor", choices=["dfx", "doubling"], default="dfx")
    ap.add_argument("--intra", type=int, default=1,
                    help="kernel processes PER RUNG (depth-1 subtree partition); "
                         "use with --workers 1 to put all cores on one rung at a time")
    ap.add_argument("--order", choices=["desc", "asc"], default="desc",
                    help="desc = gate mode (hardest rungs first, whole-window exhaustion); "
                         "asc = walk mode (lowest rungs first — each exhausted M raises the "
                         "proven lower bound immediately)")
    args = ap.parse_args()

    check_c_table_sync(BINARY)
    n, W = args.n, args.witness_m
    floor_val = lower_bound(n, args.floor)
    deadline = time.monotonic() + args.budget
    t0 = time.monotonic()

    ledger_path = Path(args.ledger)
    ledger = {"n": n, "completed": {}}
    if ledger_path.exists():
        try:
            prev = json.loads(ledger_path.read_text())
            if prev.get("n") == n:
                ledger = prev
        except json.JSONDecodeError:
            pass

    def save():
        ledger_path.write_text(json.dumps(ledger, indent=1))

    # 1. certify the ceiling (cheap: witnesses are found fast)
    wrec = ledger["completed"].get(str(W))
    if not (wrec and wrec.get("status") == "witness"):
        wrec = run_rung(n, W, deadline - time.monotonic())  # ceiling: witnesses are cheap, no intra
        if wrec["status"] != "witness":
            print(json.dumps({"status": "ceiling_failed", "n": n, "ceiling": W,
                              "detail": wrec}))
            sys.exit(1)
        ledger["completed"][str(W)] = wrec
        save()
    _p(f"ceiling M={W} witnessed: {wrec['witness']}")

    # 2. exhaust [floor, W-1] — desc: hardest first (gate); asc: lowest first (walk)
    rng = range(W - 1, floor_val - 1, -1) if args.order == "desc" \
        else range(floor_val, W)
    todo = [M for M in rng
            if ledger["completed"].get(str(M), {}).get("status") != "infeasible"]
    _p(f"rungs to exhaust: {len(todo)} of {W - floor_val} "
       f"(floor {floor_val}, {args.workers} workers, order {args.order}, intra {args.intra})")

    surprise_witness = None
    budget_hit = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_rung, n, M, deadline - time.monotonic(), args.intra): M
                for M in todo}
        for fut in as_completed(futs):
            M = futs[fut]
            rec = fut.result()
            if rec["status"] == "infeasible":
                ledger["completed"][str(M)] = rec
                save()
                _p(f"  M={M} infeasible ({rec['nodes']:,} nodes, {rec['elapsed_s']}s)")
            elif rec["status"] == "witness":
                ledger["completed"][str(M)] = rec
                save()
                surprise_witness = (M, rec["witness"])
                _p(f"  M={M} WITNESS (below ceiling!) {rec['witness']}")
            else:
                budget_hit.append(M)
                _p(f"  M={M} {rec['status']} — no claim")

    done = {int(k): v for k, v in ledger["completed"].items()}
    exhausted = sorted(M for M, v in done.items() if v["status"] == "infeasible")
    contiguous = all(M in done and done[M]["status"] == "infeasible"
                     for M in range(floor_val, W))
    total_nodes = sum(v.get("nodes", 0) for v in done.values())

    result = {"arm": "gate_parallel", "engine": "c", "n": n, "workers": args.workers,
              "intra": args.intra,
              "floor": {"kind": args.floor, "value": floor_val,
                        "provenance": "binom(n,n//2): Dubroff-Fox-Xu arXiv:2006.12988"},
              "prunes": ["P1", "P2", "P3", "P4", "P5"],
              "p4_verified_table": A_VERIFIED,
              "ceiling": W, "ceiling_witness": ledger["completed"][str(W)]["witness"],
              "rungs_exhausted": len(exhausted), "rungs_pending": sorted(budget_hit),
              "total_nodes": total_nodes,
              "elapsed_s": round(time.monotonic() - t0, 3)}
    if surprise_witness:
        result.update(status="witness_below_ceiling", at=surprise_witness[0],
                      witness=surprise_witness[1],
                      note="feasible below the assumed ceiling — a DISCOVERY; "
                           "re-run with the lower ceiling to establish exactness")
    elif contiguous:
        result.update(status="exact", a_n=W,
                      note=f"all M in [{floor_val},{W-1}] exhausted infeasible "
                           f"(floor = DFX theorem); witness at {W}")
    else:
        missing = [M for M in range(floor_val, W)
                   if done.get(M, {}).get("status") != "infeasible"]
        lb = floor_val
        while done.get(lb, {}).get("status") == "infeasible":
            lb += 1
        result.update(status="partial", missing_rungs=missing,
                      proven_lower_bound=lb,
                      note=f"{len(missing)} rungs unexhausted — no exactness claim; "
                           f"contiguous exhaustion [{floor_val},{lb-1}] ⟹ a({n}) >= {lb} "
                           f"(+ the DFX floor below); ledger holds {len(exhausted)} rungs")
    print(json.dumps(result))
    Path(args.out).write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
