#!/usr/bin/env python3
"""Tiered-fixture end-to-end (P6 M4/M5 freeze): every tier semantic exercised over the
checked-in fixture_tiered/ corpus — thread-round chunking with parties, detector
scoping (SETTLED in a thread does NOT fire vr-semantics monitors), capture ledger,
version-number supersession, derived exclusion, cross-party value attribution — plus
byte-determinism across two runs.

The fixture is copied to a temp dir and tiers.json is written there with absolute
roots (tier roots are repo-root-relative in production; tests pin them absolutely)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAG = Path(__file__).resolve().parents[1]
ROOT = RAG.parents[1]
FIXTURE = RAG / "tests" / "fixture_tiered"


def build(tmp):
    for d in ("corpus", "threads", "papers", "seeds", "derived"):
        shutil.copytree(FIXTURE / d, tmp / d)
    (tmp / "seeds" / "tiers.json").write_text(json.dumps({"tiers": [
        {"id": "vr", "roots": [str(tmp / "corpus")], "contract": "vr",
         "authority": 3, "citable_as_receipt": True},
        {"id": "threads", "roots": [str(tmp / "threads")], "contract": "rounds",
         "doc_id": {"primary": "THREAD"}, "party_headers": True,
         "party_pattern": r"R\d+\s*\(([^)]+)\)",
         "authority": 2, "citable_as_receipt": False, "detectors": []},
        {"id": "papers", "roots": [str(tmp / "papers")], "contract": "versioned",
         "version_pattern": r"_v(\d+)", "archive_roots": [str(tmp / "papers" / "archive")],
         "authority": 1, "citable_as_receipt": False},
        {"id": "derived", "roots": [str(tmp / "derived")], "contract": "vr",
         "indexed": False, "authority": 0},
    ]}))
    data = tmp / "data"
    env = dict(os.environ, RAG_CORPUS_DIR=str(tmp / "corpus"),
               RAG_SEED_DIR=str(tmp / "seeds"), RAG_DATA_DIR=str(data))
    for script in ("index_vrs.py", "ontology.py"):
        r = subprocess.run([sys.executable, str(RAG / script)],
                           capture_output=True, text=True, env=env, cwd=ROOT)
        assert r.returncode == 0, f"{script}: {r.stderr[-500:]}"
    return data


class TestTieredFixtureE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tiered_e2e_"))
        cls.data = build(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def _chunks(self):
        return [json.loads(l) for l in (self.data / "chunks.jsonl").read_text().splitlines()]

    def test_thread_rounds_chunked_with_parties(self):
        th = [c for c in self._chunks() if c["vr_id"] == "THREAD-1"]
        self.assertEqual([c["section"] for c in th], ["R1", "R2", "R3"])
        self.assertEqual([c.get("party") for c in th], ["Alice", "Bob", "Alice"])
        self.assertTrue(all(c["tier"] == "threads" for c in th))

    def test_settled_in_thread_does_not_fire_monitor(self):
        mons = json.loads((self.data / "monitors.json").read_text())["monitors"]
        m = next(m for m in mons if m["id"] == "settled_needs_independent_route")
        # VR-1 says SETTLED WITH an independent route; THREAD-1 R1 says SETTLED with
        # none — but threads declare detectors: [], so the monitor stays met.
        self.assertEqual(m["state"], "met", m)

    def test_capture_ledger(self):
        cl = json.loads((self.data / "capture_ledger.json").read_text())
        self.assertEqual(cl["captures"], [{"vr": "VR-1", "thread": "THREAD-1", "round": 1}])
        self.assertEqual([u["round"] for u in cl["unreconciled_rounds"]], [2, 3])
        self.assertEqual([(c["vr"], c["round"]) for c in cl["receipt_candidates"]],
                         [("VR-2", 2)])

    def test_versioned_supersession(self):
        vd = json.loads((self.data / "versioned_docs.json").read_text())["docs"]
        by = {d["path"]: d for d in vd}
        v1 = next(d for d in vd if d["path"].endswith("outline_v1.md"))
        v2 = next(d for d in vd if d["path"].endswith("outline_v2.md"))
        v0 = next(d for d in vd if d["path"].endswith("outline_v0.md"))
        self.assertEqual(v2["status"], "current")
        self.assertEqual(v1["status"], "superseded")
        self.assertTrue(v0["archived"])

    def test_derived_excluded(self):
        self.assertFalse(any(c["vr_id"] == "VR-99" for c in self._chunks()))

    def test_cross_party_value_attribution(self):
        reg = json.loads((self.data / "entity_registry.json").read_text())
        tail = reg.get("tail length") or {}
        vals = tail.get("values", [])
        # Bob asserts 7 (R2), Alice asserts 8 (R3) — both present, party-attributed
        got = {(v.get("party"), v["value"]) for v in vals if v["vr_id"] == "THREAD-1"}
        self.assertEqual(got, {("Bob", "7"), ("Alice", "8")})

    def test_arcs_exclude_threads(self):
        arcs = json.loads((self.data / "arcs.json").read_text())
        for a in arcs:
            self.assertFalse(any(m.startswith("THREAD") for m in a["members"]), a)

    def test_byte_determinism(self):
        import hashlib
        tmp2 = Path(tempfile.mkdtemp(prefix="tiered_e2e_b_"))
        try:
            data2 = build(tmp2)
            for f in sorted(self.data.glob("*.json*")):
                a = f.read_bytes()
                b = (data2 / f.name).read_bytes()
                # tier roots are absolute tmp paths — normalize before comparing
                a = a.replace(str(self.tmp).encode(), b"TMP")
                b = b.replace(str(tmp2).encode(), b"TMP")
                self.assertEqual(hashlib.sha256(a).hexdigest(),
                                 hashlib.sha256(b).hexdigest(), f.name)
        finally:
            shutil.rmtree(tmp2)


if __name__ == "__main__":
    unittest.main()
