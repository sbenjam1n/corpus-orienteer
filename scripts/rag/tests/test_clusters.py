#!/usr/bin/env python3
"""Unit tests for clusters.py's normalization core (fold / term_rx).

Freezes the sweep-normalization lessons as executable tests, per this suite's
philosophy (validations previously ad hoc in VR prose become regressions-proof):
  - dash family: "Zilber–Pink" (en-dash) must match seed "Zilber-Pink"
  - accents: "André–Oort" / "Wüstholz" fold to ASCII (NFKD + strip combining)
  - stroke letters: "Łoś" has NO NFKD decomposition — needs the explicit stroke
    map (found as a live false-ADJACENT-ONLY on "Los engine", 2026-07-29)
  - word boundary: "abc" must not count "abcd…" (the exact-count upgrade over grep)

Synthetic only: no corpus, no data/rag build needed.
Run (from repo root): python3 -m unittest discover -s scripts/rag/tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clusters  # noqa: E402


class TestFold(unittest.TestCase):
    def test_dash_family_folds(self):
        self.assertEqual(clusters.fold("Zilber–Pink"), clusters.fold("Zilber-Pink"))
        self.assertEqual(clusters.fold("Manin—Mumford"), "manin-mumford")

    def test_accents_fold(self):
        self.assertEqual(clusters.fold("André–Oort"), "andre-oort")
        self.assertEqual(clusters.fold("Wüstholz"), "wustholz")

    def test_stroke_letters_fold(self):
        self.assertEqual(clusters.fold("Łoś engine"), "los engine")
        self.assertEqual(clusters.fold("Øystein"), "oystein")

    def test_whitespace_collapse(self):
        self.assertEqual(clusters.fold("a  b\n c"), "a b c")


class TestTermRx(unittest.TestCase):
    def test_word_bounded(self):
        rx = clusters.term_rx("abc")
        self.assertIsNotNone(rx.search(clusters.fold("the abc conjecture")))
        # hyphen compounds DO count ("abc-conditional" mentions abc)…
        self.assertIsNotNone(rx.search(clusters.fold("abc-conditional regime")))
        # …but word-internal runs do not (the exact-count upgrade over raw grep)
        self.assertIsNone(rx.search(clusters.fold("abcd")))
        self.assertIsNone(rx.search(clusters.fold("xabc")))

    def test_multiword_matches_folded_haystack(self):
        rx = clusters.term_rx("Manin-Mumford")
        self.assertIsNotNone(rx.search(clusters.fold("relative Manin–Mumford problem")))


class TestInstrumentSlice(unittest.TestCase):
    DRIFT = {"flags": [{"object": "E", "prop": "rank", "seed": 0, "corpus": 1},
                       {"object": "X_far", "prop": "deg", "seed": 2, "corpus": 3}]}
    COV = {"alias_drift": [{"object": "E", "seed_primary": "E", "recent_dominant": "64a1"},
                           {"object": "X_far", "seed_primary": "X", "recent_dominant": "Y"}],
           "uncaptured_tokens": [
               {"token": "jelonek_set", "vrs": 9, "examples": ["VR-1098"]},
               {"token": "elsewhere_token", "vrs": 5, "examples": ["VR-7"]}],
           "unseeded_objects": [{"entity": "K_new", "type": "field", "mentions": 4},
                                {"entity": "Z_absent", "type": "field", "mentions": 2}]}

    def test_filters_to_scope(self):
        sl = clusters.instrument_slice(
            touched_ids={"E"}, scope_ids={"VR-1098"},
            scope_folded=clusters.fold("the K_new field and jelonek_set appear here"),
            drift=self.DRIFT, coverage=self.COV)
        self.assertEqual([f["object"] for f in sl["drift_flags"]], ["E"])
        self.assertEqual([a["object"] for a in sl["alias_drift"]], ["E"])
        self.assertEqual([t["token"] for t in sl["uncaptured_tokens"]], ["jelonek_set"])
        self.assertEqual([o["entity"] for o in sl["unseeded_objects"]], ["K_new"])

    def test_empty_scope_yields_empty_sections(self):
        sl = clusters.instrument_slice(set(), set(), "", self.DRIFT, self.COV)
        self.assertTrue(all(v == [] for v in sl.values()))


if __name__ == "__main__":
    unittest.main()
