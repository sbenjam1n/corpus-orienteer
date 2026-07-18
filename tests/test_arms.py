#!/usr/bin/env python3
"""Demo-program arm tests: golden values + guards.

Run (from repo root): python3 -m unittest discover -s tests
Fast by design (< ~5s): the exhaustive golden set stops at n=7 (n=8 takes minutes and
is banked as a corpus artifact, results/exhaustive_n8.json / VR-3).
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "arms"))

from verify_set import is_sum_distinct  # noqa: E402
from conway_guy import u_sequence, conway_guy_set, CALIBRATION  # noqa: E402

# Published values (OEIS A276661 / A005318; VR-2).
GOLDEN_A = {1: 1, 2: 2, 3: 4, 4: 7, 5: 13, 6: 24, 7: 44}


class TestVerifySet(unittest.TestCase):
    def test_known_sum_distinct(self):
        ok, info = is_sum_distinct([20, 31, 37, 40, 42, 43, 44])  # the a(7) witness
        self.assertTrue(ok, info)

    def test_collision_detected(self):
        ok, info = is_sum_distinct([1, 2, 3])  # 1+2 = 3
        self.assertFalse(ok)
        self.assertEqual(info["colliding_sum"], 3)

    def test_rejects_nonpositive_and_duplicates(self):
        with self.assertRaises(ValueError):
            is_sum_distinct([0, 1, 2])
        with self.assertRaises(ValueError):
            is_sum_distinct([2, 2, 3])

    def test_certificate_ceiling_guard(self):
        # A CG-40-sized set must be REFUSED (theorem territory), not attempted.
        big = conway_guy_set(40)
        with self.assertRaises(ValueError):
            is_sum_distinct(big)


class TestConwayGuy(unittest.TestCase):
    def test_generator_matches_oeis(self):
        self.assertEqual(u_sequence(13), CALIBRATION)

    def test_cg_sets_certify_up_to_20(self):
        for n in range(1, 21):
            s = conway_guy_set(n)
            ok, info = is_sum_distinct(s)
            self.assertTrue(ok, f"CG-{n} failed: {info}")
            self.assertEqual(max(s), u_sequence(n)[n])


class TestExhaustiveGolden(unittest.TestCase):
    def test_exact_optima_n1_to_7(self):
        for n, expected in GOLDEN_A.items():
            proc = subprocess.run(
                [sys.executable, str(ROOT / "arms" / "exhaustive.py"),
                 "--n", str(n), "--budget", "120"],
                capture_output=True, text=True, cwd=ROOT, timeout=150)
            self.assertEqual(proc.returncode, 0, proc.stderr[-300:])
            out = json.loads(proc.stdout)
            self.assertEqual(out["status"], "exact", out)
            self.assertEqual(out["a_n"], expected, f"n={n}: {out}")
            ok, _ = is_sum_distinct(out["witness"])
            self.assertTrue(ok, f"witness for n={n} not sum-distinct")
            self.assertEqual(max(out["witness"]), expected)


if __name__ == "__main__":
    unittest.main()


class TestEmitOkf(unittest.TestCase):
    """P5 Layer A: OKF pages carry only the five OKF keys, never index.md, and two
    emissions from the same build are byte-identical."""

    def test_pages_okf_clean_and_deterministic(self):
        import subprocess
        import tempfile
        import hashlib
        for _ in range(2):
            outs = []
            for run in range(2):
                out = Path(tempfile.mkdtemp(prefix=f"okf{run}_"))
                r = subprocess.run(
                    [sys.executable, str(ROOT / "adapters" / "openwiki" / "emit_okf.py"),
                     "--out", str(out)], capture_output=True, text=True, cwd=ROOT)
                self.assertEqual(r.returncode, 0, r.stderr)
                outs.append(out)
            files0 = sorted(p.name for p in outs[0].glob("*.md"))
            self.assertNotIn("index.md", files0)
            self.assertIn("brief.md", files0)
            for name in files0:
                a = (outs[0] / name).read_text()
                b = (outs[1] / name).read_text()
                self.assertEqual(hashlib.sha256(a.encode()).hexdigest(),
                                 hashlib.sha256(b.encode()).hexdigest(),
                                 f"{name} not deterministic")
                fm = a.split("---")[1]
                keys = {ln.split(":")[0].strip() for ln in fm.strip().splitlines()}
                self.assertTrue(keys <= {"type", "title", "description", "resource", "tags"},
                                f"non-OKF keys in {name}: {keys}")
                self.assertIn("type", keys)
            break


class TestConstantsCurve(unittest.TestCase):
    """P4: exact arithmetic, golden values, overflow discipline."""

    def test_golden_and_overflow(self):
        sys.path.insert(0, str(ROOT / "arms"))
        from constants_curve import build
        rows = {r["n"]: r for r in build(67)}
        self.assertEqual(rows[10]["best_known_max"], "309")
        self.assertEqual(rows[10]["kind"], "exact")
        self.assertEqual(rows[12]["best_known_max"], "1157")
        self.assertEqual(rows[12]["kind"], "upper_bound")
        # c(3) = 4/8 exactly
        self.assertEqual((rows[3]["c_num"], rows[3]["c_den"]), ("1", "2"))
        # overflow: u(67) beyond uint64, exact string intact
        self.assertGreater(int(rows[67]["best_known_max"]), 2 ** 64)
        # rails sane: DFX floor <= best everywhere
        for r in rows.values():
            self.assertLessEqual(r["dfx_floor_float"], r["c_float"] + 1e-12, r)
