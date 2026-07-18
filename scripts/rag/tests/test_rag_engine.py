#!/usr/bin/env python3
"""Per-stage regression tests for the RAG engine.

Freezes as executable tests the detector behaviours that were previously only validated
ad hoc in VR prose ("control-validated, 0 FP") — so a future edit to a regex, a window,
or the loser semantics cannot silently regress them. Synthetic fixtures only: no
dependence on the live corpus, so these stay green as verification_ready/ evolves.

Run (from repo root):
    python3 -m unittest discover -s scripts/rag/tests -v
Full-pipeline byte-determinism is the separate, heavier check:
    bash scripts/rag/tests/determinism_check.sh
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ontology  # noqa: E402
import orient    # noqa: E402


class TestNormalizeToken(unittest.TestCase):
    def test_subscript_and_spelling_variants_fold(self):
        forms = ["stem_2", "stem2", "stem₂", "stem 2", "stem{2}"]
        keys = {ontology.normalize_token(f) for f in forms}
        self.assertEqual(len(keys), 1, f"variants did not fold: {keys}")

    def test_tilde_preserving(self):
        # K₁ and K̃₁ are DIFFERENT fields — the canonicalizer must not collapse them.
        self.assertNotEqual(ontology.normalize_token("K₁"),
                            ontology.normalize_token("K̃₁"))
        # but every tilde spelling converges to one key
        self.assertEqual(ontology.normalize_token("K~1"),
                         ontology.normalize_token("K̃₁"))


class TestAliasBoundary(unittest.TestCase):
    def test_short_alias_does_not_substring_match(self):
        self.assertIsNone(ontology._alias_rx("E^5").search("the twist E^5033 has"))
        self.assertIsNotNone(ontology._alias_rx("E^5").search("the twist E^5 has"))

    def test_underscore_is_not_a_boundary(self):
        # Documented hazard: 'A4' boundary-matches INSIDE 'K_A4' ('_' is not in the
        # boundary class). orient's interval-gap + longest-match tie-break exists
        # because of this; if this ever changes, revisit that tie-break.
        self.assertIsNotNone(ontology._alias_rx("A4").search("the field K_A4 here"))

    def test_match_aliases_drops_one_char_forms(self):
        obj = {"id": "Q", "primary": "Q", "aliases": ["Q", "rationals"]}
        self.assertNotIn("Q", ontology.match_aliases(obj))
        self.assertIn("rationals", ontology.match_aliases(obj))


class TestBuildLosers(unittest.TestCase):
    RELS = {"corrects", "refutes", "corrected_by", "supersedes"}

    def test_verb_relation_loser_is_target(self):
        sup = {"edges": [{"source": "VR-2", "relation": "corrects", "target": "VR-1"}]}
        self.assertEqual(orient.build_losers(sup, self.RELS), {"VR-1": [("VR-2", "corrects")]})

    def test_self_applied_loser_is_source(self):
        sup = {"edges": [{"source": "VR-1", "relation": "corrected_by", "target": "VR-2"}]}
        self.assertEqual(orient.build_losers(sup, self.RELS), {"VR-1": [("VR-2", "corrected_by")]})

    def test_reference_edges_ignored(self):
        sup = {"edges": [{"source": "VR-2", "relation": "references", "target": "VR-1"}]}
        self.assertEqual(orient.build_losers(sup, self.RELS), {})


class TestAssertionCheck(unittest.TestCase):
    """Nearest-alias attribution with interval-gap + longest-match tie-break."""

    OBJS = [
        ({"id": "E^161", "primary": "E^161", "aliases": ["E^{161}"],
          "properties": {}}, 1),
        ({"id": "E^5033", "primary": "E^5033", "aliases": [],
          "properties": {}}, 1),
        ({"id": "K_A4", "primary": "K_A4", "aliases": [],
          "properties": {}}, 1),
        ({"id": "A_4", "primary": "A_4", "aliases": ["A4"],
          "properties": {}}, 1),
    ]
    PAIRS = {
        "E^161@Q": {"curve": "E^161", "field": "Q", "properties": {
            "sha_order": {"prop": "sha_order", "value": "16", "vr_id": "VR-982",
                          "stratum": "verified"}}},
        "E^5033@Q": {"curve": "E^5033", "field": "Q", "properties": {
            "sha_order": {"prop": "sha_order", "value": "64", "vr_id": "VR-994",
                          "stratum": "verified"}}},
        "E@K_A4": {"curve": "E", "field": "K_A4", "properties": {
            "sha_order": {"prop": "sha_order", "value": "1", "vr_id": "VR-558",
                          "stratum": "verified"}}},
    }

    def check(self, text):
        return orient.assertion_check([("t.md", text)], self.OBJS, self.PAIRS)

    def test_stale_value_flagged(self):
        mism, anch = self.check("Per the old analysis, E^161 has sha = 64 here.")
        self.assertEqual(len(mism), 1)
        self.assertIn("E^161", mism[0])
        self.assertEqual(anch, [])

    def test_matching_value_is_anchor(self):
        mism, anch = self.check("E^5033 gives sha = 64 as calibration.")
        self.assertEqual(mism, [])
        self.assertEqual(len(anch), 1)
        self.assertIn("E^5033", anch[0])

    def test_nearest_alias_wins_over_cooccurring_object(self):
        # E^161 is inside the window but E^5033 is nearer to the value.
        mism, anch = self.check("unlike E^161, the twist E^5033 has sha = 64.")
        self.assertEqual(mism, [])
        self.assertEqual(len(anch), 1)
        self.assertIn("E^5033", anch[0])

    def test_overlapping_alias_tiebreak_prefers_longer_match(self):
        # 'A4' matches inside 'K_A4' with the same interval gap; the longer K_A4
        # match must win so the (seeded) K_A4 fact is checked, not skipped via A_4.
        mism, anch = self.check("The E/K_A4 instance has |Sha| = 4 (old value).")
        self.assertEqual(len(mism), 1)
        self.assertIn("K_A4", mism[0])

    def test_no_seeded_prop_means_skip_not_reattribute(self):
        # A_4 (nearest) has no sha_order seeded -> skip entirely; do NOT charge the
        # 2nd-nearest object.
        mism, anch = self.check("blah blah for A4 we get sha = 7 conjecturally, "
                                "and separately E^161 is fine.")
        self.assertEqual((mism, anch), ([], []))


def _mon(det, mid="test_monitor", **args):
    return {"id": mid, "watch": "w", "severity": "LOW", "detector_type": det,
            "detector_args": args}


def _chunk(content, vr="VR-1", status="active"):
    return {"vr_id": vr, "content": content, "status": status, "entities": []}


class TestForbiddenPredicate(unittest.TestCase):
    ARGS = dict(patterns=[r"stem_k\s*=\s*the splitting field"],
                exclude=[r"\bNOT\b", r"mislabel"], window=40, scan_files=[],
                contradicts="stem_k is the root field")

    def run_mon(self, chunks, mid="fp_test"):
        return ontology.evaluate_monitor(_mon("forbidden_predicate", mid, **self.ARGS),
                                         {}, chunks)

    def test_assertion_flagged(self):
        r = self.run_mon([_chunk("we recall stem_k = the splitting field of G_k")])
        self.assertEqual(r["state"], "unmet")
        self.assertIn("VR-1", r["evidence"])

    def test_negation_window_excluded(self):
        r = self.run_mon([_chunk("stem_k = the splitting field is the mislabel; it is NOT")])
        self.assertEqual(r["state"], "met")

    def test_retracted_chunk_skipped(self):
        r = self.run_mon([_chunk("stem_k = the splitting field", status="retracted")])
        self.assertEqual(r["state"], "met")

    def test_self_consumption_guard(self):
        # A chunk QUOTING the monitor's definition (it names the monitor id) must not
        # be a candidate — the guard vocabulary itself is not an assertion.
        r = self.run_mon([_chunk("the fp_test monitor watches for the phrase "
                                 "stem_k = the splitting field appearing anywhere")])
        self.assertEqual(r["state"], "met")

    def test_self_consumption_guard_is_doc_level(self):
        # A doc that names the monitor in ONE section is exempt in ALL its sections
        # (sub-chunks quoting the span without repeating the id must not re-flag).
        r = self.run_mon([
            _chunk("this doc dispositions fp_test candidates", vr="AUDIT-9"),
            _chunk("the flagged span, verbatim: stem_k = the splitting field", vr="AUDIT-9"),
        ])
        self.assertEqual(r["state"], "met")

    def test_other_docs_still_flagged(self):
        r = self.run_mon([
            _chunk("this doc dispositions fp_test candidates", vr="AUDIT-9"),
            _chunk("we recall stem_k = the splitting field of G_k", vr="VR-7"),
        ])
        self.assertEqual(r["state"], "unmet")
        self.assertIn("VR-7", r["evidence"])


class TestCompletenessClaim(unittest.TestCase):
    def run_mon(self, chunks, mid="cc_test"):
        return ontology.evaluate_monitor(
            _mon("completeness_claim", mid, exclude=[r"\bnot\b"], window=30), {}, chunks)

    def test_overclaim_flagged(self):
        r = self.run_mon([_chunk("after the sweep the corpus is corpus-clean now")])
        self.assertEqual(r["state"], "unmet")

    def test_self_consumption_guard(self):
        r = self.run_mon([_chunk("the cc_test monitor flags corpus-clean overclaims")])
        self.assertEqual(r["state"], "met")


class TestSettledIndependentRoute(unittest.TestCase):
    def run_mon(self, chunks, mid="sir_test"):
        return ontology.evaluate_monitor(_mon("settled_independent_route", mid), {}, chunks)

    def test_settled_without_route_flagged(self):
        r = self.run_mon([_chunk("the value is SETTLED at 384.")])
        self.assertEqual(r["state"], "unmet")

    def test_settled_with_route_ok(self):
        r = self.run_mon([_chunk("SETTLED at 384 via an independent route (PARI).")])
        self.assertEqual(r["state"], "met")

    def test_self_consumption_guard(self):
        r = self.run_mon([_chunk("per the sir_test rule, nothing is SETTLED on one method")])
        self.assertEqual(r["state"], "met")


class TestOrientDenoise(unittest.TestCase):
    def test_jargon_translated(self):
        self.assertEqual(orient._clean("rank 0, BANKED 2026, FLAGSHIP"), "rank 0, settled 2026")
        self.assertEqual(orient._clean("banked SLB Seq 65"), "settled")

    def test_plain_text_untouched(self):
        self.assertEqual(orient._clean("|Sha|=16, verified VR-982"),
                         "|Sha|=16, verified VR-982")


if __name__ == "__main__":
    unittest.main()


class TestSupersessionTargetNamespace(unittest.TestCase):
    """An edge pattern that matched an AUDIT-namespace id must target AUDIT-N, not
    fabricate PRIMARY-N (which pointed the edge at an unrelated primary doc that
    happened to share the number)."""

    def _edges(self, text):
        import index_vrs
        return index_vrs.extract_supersession("VR-99", text)

    def test_audit_target_keeps_namespace(self):
        text = ("# VR-99: t\n\n**Date:** 2026-01-01\n"
                "**Status:** [V] verified [CORRECTED by AUDIT-3]\n\nbody\n")
        edges = self._edges(text)
        self.assertIn(("corrected_by_audit", "AUDIT-3"), edges)
        self.assertNotIn(("corrected_by_audit", "VR-3"), edges)

    def test_primary_target_unchanged(self):
        text = ("# VR-99: t — corrects VR-3\n\n**Date:** 2026-01-01\n"
                "**Status:** [V] verified — corrects VR-3\n\nbody\n")
        edges = self._edges(text)
        self.assertIn(("corrects", "VR-3"), edges)


class TestCorpusTiersM1(unittest.TestCase):
    """P6 M1 substrate: tiers.json absent => no tier stamps (C1 compatibility);
    present => chunk stamps, extra contract-vr roots walked, derived roots excluded."""

    def _build(self, with_tiers):
        import json as _json
        import shutil
        import subprocess
        import sys as _sys
        import tempfile
        rag = Path(__file__).resolve().parents[1]
        root = rag.parents[1]
        fixture = rag / "tests" / "fixture"
        tmp = Path(tempfile.mkdtemp(prefix="tiers_m1_"))
        try:
            corpus = tmp / "corpus"
            shutil.copytree(fixture / "corpus", corpus)
            seeds = tmp / "seeds"
            shutil.copytree(fixture / "seeds", seeds)
            extra = tmp / "extra_corpus"          # second contract-vr root
            extra.mkdir()
            (extra / "VR-99_extra_tier_doc.md").write_text(
                "# VR-99: extra-root doc\n\n**Date:** 2026-02-01\n"
                "**Status:** [V] verified\n\n## §1 body\ntext\n")
            derived = tmp / "derived"             # indexed:false tier
            derived.mkdir()
            (derived / "VR-500_derived_never_indexed.md").write_text(
                "# VR-500: derived artifact\n\n**Date:** 2026-02-02\n"
                "**Status:** [V] verified\n\n## §1 body\nquotes monitors\n")
            if with_tiers:
                rel = lambda p: str(p.relative_to(root)) if str(p).startswith(str(root)) else str(p)
                (seeds / "tiers.json").write_text(_json.dumps({"tiers": [
                    {"id": "vr", "roots": [rel(corpus)], "contract": "vr",
                     "authority": 3, "citable_as_receipt": True},
                    {"id": "vr_extra", "roots": [rel(extra)], "contract": "vr",
                     "authority": 3, "citable_as_receipt": True},
                    {"id": "derived", "roots": [rel(derived)], "contract": "vr",
                     "indexed": False, "authority": 0},
                ]}))
            data = tmp / "data"
            env = dict(**__import__("os").environ,
                       RAG_CORPUS_DIR=str(corpus), RAG_SEED_DIR=str(seeds),
                       RAG_DATA_DIR=str(data))
            r = subprocess.run([_sys.executable, str(rag / "index_vrs.py")],
                               capture_output=True, text=True, env=env, cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            chunks = [_json.loads(l) for l in
                      (data / "chunks.jsonl").read_text().splitlines()]
            return chunks
        finally:
            shutil.rmtree(tmp)

    def test_no_tiers_json_means_no_stamps(self):
        chunks = self._build(with_tiers=False)
        self.assertTrue(chunks)
        self.assertTrue(all("tier" not in ch for ch in chunks))
        self.assertFalse(any(ch["vr_id"] == "VR-99" for ch in chunks))

    def test_tiered_build_stamps_walks_and_excludes(self):
        chunks = self._build(with_tiers=True)
        self.assertTrue(all(ch.get("tier") for ch in chunks))
        by_vr = {ch["vr_id"]: ch.get("tier") for ch in chunks}
        self.assertEqual(by_vr.get("VR-99"), "vr_extra")       # extra root walked
        self.assertEqual(by_vr.get("VR-1"), "vr")              # main corpus stamped
        self.assertNotIn("VR-500", by_vr)                      # derived excluded


class TestVersionedTiersM2(unittest.TestCase):
    """P6 M2: version-number supersession synthesis + the orient citation verdicts."""

    def _tiers(self, tmp):
        return [{"id": "papers", "roots": [str(tmp / "papers")],
                 "contract": "versioned", "version_pattern": r"_v(\d+)(?:_(\d+))?",
                 "archive_roots": [str(tmp / "papers" / "archive")],
                 "authority": 1, "citable_as_receipt": False}]

    def _mkdocs(self, tmp):
        papers = tmp / "papers"
        (papers / "archive").mkdir(parents=True)
        (papers / "outline_v1.md").write_text("# outline v1\n")
        (papers / "outline_v2_3.md").write_text("# outline v2.3\n")
        (papers / "archive" / "outline_v0.md").write_text("# outline v0\n")
        (papers / "notes.md").write_text("# unversioned — ignored\n")

    def test_synthesis_and_verdicts(self):
        import tempfile
        import shutil
        import tiers as tiers_mod
        tmp = Path(tempfile.mkdtemp(prefix="tiers_m2_"))
        try:
            self._mkdocs(tmp)
            docs = tiers_mod.build_versioned_docs(self._tiers(tmp))
            by_path = {d["path"]: d for d in docs}
            self.assertEqual(len(docs), 3)  # notes.md ignored (no version match)
            v2 = next(d for d in docs if d["path"].endswith("outline_v2_3.md"))
            v1 = next(d for d in docs if d["path"].endswith("outline_v1.md"))
            v0 = next(d for d in docs if d["path"].endswith("outline_v0.md"))
            self.assertEqual(v2["status"], "current")
            self.assertEqual(v1["status"], "superseded")
            self.assertTrue(v1["superseded_by"].endswith("outline_v2_3.md"))
            self.assertTrue(v0["archived"])
            self.assertEqual(v0["status"], "superseded")
            # orient hook: a plan citing v1 gets the ⚠ + the current doc to read
            plan_text = f"see {v1['path']} for the layout"
            hits = tiers_mod.classify_versioned_citations(
                [("plans/p.md", plan_text)], docs)
            self.assertEqual(len(hits), 1)
            path, status, sup = hits[0]
            self.assertEqual(status, "superseded")
            self.assertTrue(sup.endswith("outline_v2_3.md"))
            # citing the current version yields a non-superseded verdict
            hits2 = tiers_mod.classify_versioned_citations(
                [("plans/p.md", f"see {v2['path']}")], docs)
            self.assertEqual(hits2[0][1], "current")
        finally:
            shutil.rmtree(tmp)

    def test_archive_only_family_has_no_current(self):
        import tempfile
        import shutil
        import tiers as tiers_mod
        tmp = Path(tempfile.mkdtemp(prefix="tiers_m2b_"))
        try:
            (tmp / "papers" / "archive").mkdir(parents=True)
            (tmp / "papers" / "archive" / "dead_v1.md").write_text("x\n")
            docs = tiers_mod.build_versioned_docs(self._tiers(tmp))
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["status"], "superseded")
            self.assertIsNone(docs[0]["superseded_by"])
        finally:
            shutil.rmtree(tmp)


class TestCaptureLedgerM3(unittest.TestCase):
    """P6 M3: captures edges (metadata-only), unreconciled rounds, receipt-laundering
    candidates (windowed, softener-excluded, candidates-never-verdicts)."""

    def test_ledger(self):
        import json as _json
        import os
        import shutil
        import subprocess
        import sys as _sys
        import tempfile
        rag = Path(__file__).resolve().parents[1]
        root = rag.parents[1]
        tmp = Path(tempfile.mkdtemp(prefix="tiers_m3_"))
        try:
            corpus = tmp / "corpus"
            corpus.mkdir()
            (corpus / "VR-1_capture.md").write_text(
                "# VR-1: reconciles round one — captures THREAD-1 R1\n\n"
                "**Date:** 2026-03-01\n**Status:** [V] verified — captures THREAD-1 R1\n\n"
                "## §1 capture\nRound one's claim re-derived here with our own receipts.\n")
            (corpus / "VR-2_launder.md").write_text(
                "# VR-2: uses round two\n\n**Date:** 2026-03-02\n"
                "**Status:** [V] verified\n\n"
                "## §1 body\nThe value 42 is confirmed per THREAD-1 R2 and needs no rerun.\n")
            threads = tmp / "threads"
            threads.mkdir()
            (threads / "THREAD-1_topic.md").write_text(
                "# THREAD-1: external correspondence\n\n## R1 first round\nclaim A\n\n"
                "## R2 second round\nclaim B (value 42)\n")
            seeds = tmp / "seeds"
            shutil.copytree(rag / "tests" / "fixture" / "seeds", seeds)
            rel = lambda p: str(p)
            (seeds / "tiers.json").write_text(_json.dumps({"tiers": [
                {"id": "vr", "roots": [rel(corpus)], "contract": "vr",
                 "authority": 3, "citable_as_receipt": True},
                {"id": "threads", "roots": [rel(threads)], "contract": "rounds",
                 "doc_id": {"primary": "THREAD"},
                 "authority": 2, "citable_as_receipt": False},
            ]}))
            data = tmp / "data"
            env = dict(os.environ, RAG_CORPUS_DIR=str(corpus),
                       RAG_SEED_DIR=str(seeds), RAG_DATA_DIR=str(data))
            r = subprocess.run([_sys.executable, str(rag / "index_vrs.py")],
                               capture_output=True, text=True, env=env, cwd=root)
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            cl = _json.loads((data / "capture_ledger.json").read_text())
            self.assertEqual(cl["threads"][0]["rounds"], [1, 2])
            self.assertEqual(cl["captures"],
                             [{"vr": "VR-1", "thread": "THREAD-1", "round": 1}])
            self.assertEqual(cl["unreconciled_rounds"],
                             [{"thread": "THREAD-1", "round": 2,
                               "path": cl["threads"][0]["path"]}])
            cands = cl["receipt_candidates"]
            self.assertEqual(len(cands), 1)
            self.assertEqual((cands[0]["vr"], cands[0]["round"]), ("VR-2", 2))
            # the capturing VR's own R1 citation is NOT a candidate
            self.assertFalse(any(c["round"] == 1 for c in cands))
        finally:
            shutil.rmtree(tmp)
