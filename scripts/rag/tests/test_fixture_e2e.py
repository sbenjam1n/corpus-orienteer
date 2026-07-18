#!/usr/bin/env python3
"""End-to-end pipeline test on the shipped fixture corpus (Stage 1 of
Plans/rag_standalone_extraction_execution.md).

Runs the real pipeline (index → ontology → coverage → grounding → brief) as
subprocesses with RAG_CORPUS_DIR / RAG_DATA_DIR / RAG_SEED_DIR pointed at
scripts/rag/tests/fixture/, into a temp data dir — zero dependence on the live
corpus or data/rag. Asserts one receipt per feature class (S2 of the plan) and
byte-determinism across two runs (S3). Subprocesses, not in-process imports:
the engine reads the env at module import (plan §9 R1).
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAG = Path(__file__).resolve().parents[1]          # scripts/rag
FIXTURE = Path(__file__).resolve().parent / "fixture"
PIPELINE = ["index_vrs.py", "ontology.py", "coverage.py", "grounding_check.py",
            "synthesize_brief.py"]


def run_pipeline(data_dir):
    env = {**os.environ,
           "RAG_CORPUS_DIR": str(FIXTURE / "corpus"),
           "RAG_DATA_DIR": str(data_dir),
           "RAG_SEED_DIR": str(FIXTURE / "seeds")}
    for script in PIPELINE:
        r = subprocess.run([sys.executable, str(RAG / script)], env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise AssertionError(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return env


def hash_outputs(data_dir):
    out = {}
    for p in sorted(Path(data_dir).glob("*")):
        if p.is_file() and p.suffix in (".json", ".jsonl", ".md"):
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class TestFixtureE2E(unittest.TestCase):
    """One pipeline run shared across asserts (class fixture — it's ~2s but no need to repeat)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        cls.env = run_pipeline(cls.data)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def load(self, name):
        return json.loads((self.data / name).read_text())

    # ---- indexing -----------------------------------------------------------
    def test_corpus_indexed(self):
        meta = self.load("file_meta.json")
        self.assertEqual(len(meta), 13)
        reg = self.load("entity_registry.json")
        for e in ("C_1", "C_2", "OBS_A"):
            self.assertIn(e, reg, f"entity {e} not extracted")
        self.assertEqual(reg["C_1"]["type"], "comet")
        # doc refs are deliberately chunk-level, not registry entries
        chunks = [json.loads(l) for l in (self.data / "chunks.jsonl").read_text().splitlines() if l]
        self.assertTrue(any("VR-3" in c["entities"] for c in chunks),
                        "VR-3 ref not extracted into any chunk's entities")

    def test_corpus_stamp_is_corpus_derived(self):
        stats = self.load("index_stats.json")
        self.assertEqual(stats["generated"], "2026-01-17+13docs")

    # ---- supersession & status ---------------------------------------------
    def test_correction_and_reference_edges(self):
        edges = {(e["source"], e["relation"], e["target"])
                 for e in self.load("supersession.json")["edges"]}
        self.assertIn(("VR-4", "corrects", "VR-3"), edges)
        self.assertIn(("VR-9", "retracts", "VR-8"), edges)
        self.assertIn(("VR-2", "references", "VR-1"), edges)
        self.assertIn(("AUDIT-1", "references", "VR-3"), edges)

    def test_retracted_status_classified(self):
        meta = {m["id"]: m for m in self.load("file_meta.json")}
        self.assertEqual(meta["VR-8"]["status_classified"], "retracted")
        self.assertEqual(meta["VR-1"]["status_classified"], "active")

    def test_arc_contains_correction_pair(self):
        arcs = self.load("arcs.json")
        self.assertTrue(any({"VR-3", "VR-4"} <= set(a.get("members", [])) for a in arcs),
                        f"no arc contains the VR-3/VR-4 correction pair: {arcs}")

    # ---- ontology: objects, drift ------------------------------------------
    def test_objects_and_seeded_fact(self):
        objs = self.load("objects.json")["objects"]
        self.assertEqual(set(objs), {"C_1", "C_2", "OBS_A"})
        self.assertEqual(objs["C_1"]["properties"]["period"]["value"], "12")

    def test_drift_flag_and_confirm(self):
        drift = self.load("object_drift.json")
        flagged = [(f["subject"], f["prop"], f["corpus_value"]) for f in drift["flags"]]
        self.assertIn(("C_2", "period", "21"), flagged,
                      f"C_2 period drift (seed 20, corpus 21×3) not flagged: {drift}")
        self.assertGreaterEqual(drift["stats"]["confirmed"], 1,
                                "C_1 period=12 should confirm against the corpus")

    # ---- monitors -----------------------------------------------------------
    def monitor(self, mid):
        mons = {m["id"]: m for m in self.load("monitors.json")["monitors"]}
        return mons[mid]

    def test_forbidden_predicate_candidate(self):
        m = self.monitor("c1_forbidden_class")
        self.assertEqual(m["state"], "unmet")
        self.assertIn("VR-6", m["evidence"])
        self.assertNotIn("VR-8", m["evidence"], "retracted doc must be excluded")

    def test_completeness_claim_candidate(self):
        m = self.monitor("catalog_completeness_overclaim")
        self.assertEqual(m["state"], "unmet")
        self.assertIn("VR-7", m["evidence"])

    def test_settled_without_route_candidate(self):
        m = self.monitor("settled_needs_independent_route")
        self.assertEqual(m["state"], "unmet")
        self.assertIn("VR-5", m["evidence"])

    def test_method_registry_config_driven(self):
        reg = self.load("method_registry.json")
        self.assertIn("period_fit", reg, "config-declared method not extracted")
        self.assertGreaterEqual(reg["period_fit"]["event_count"], 1)

    # ---- grounding ----------------------------------------------------------
    def test_grounding_findings(self):
        rep = self.load("grounding_report.json")
        dangling = [f["detail"] for f in rep["findings"] if f["type"] == "DANGLING_REF"]
        self.assertTrue(any("VR-99" in d for d in dangling),
                        f"dangling VR-99 not found: {rep['summary']}")
        unack = [f["vr_id"] for f in rep["findings"]
                 if f["type"] == "UNACKNOWLEDGED_CORRECTION"]
        self.assertIn("VR-3", unack, "VR-3 (corrected, no inline tag) not surfaced")

    # ---- brief + orient ------------------------------------------------------
    def test_brief_written(self):
        brief = (self.data / "audit_brief.md").read_text()
        self.assertIn("settled_needs_independent_route", brief)

    def test_orient_catches_stale_plan(self):
        r = subprocess.run([sys.executable, str(RAG / "orient.py"),
                            str(FIXTURE / "plan_stale.md"), "--out", "fixture_plan"],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertIn("VR-99", out)                                  # dangling citation
        self.assertIn("loses to: **VR-4** [corrects]", out)          # VR-3 cited, corrected
        self.assertIn("⚠ `C_1` period = **15**", out)                # stale assertion vs seed 12
        self.assertIn("⚠ `C_2` period = **21**", out)                # stale vs (itself drifted) seed 20
        self.assertIn("`C_1` period = 12", out)                      # matching-anchor path exercised

    # ---- determinism ---------------------------------------------------------
    def test_byte_determinism(self):
        with tempfile.TemporaryDirectory() as second:
            run_pipeline(second)
            h1, h2 = hash_outputs(self.data), hash_outputs(second)
            h1.pop("orient_fixture_plan.md", None)   # written by the orient test, run once
            self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()
