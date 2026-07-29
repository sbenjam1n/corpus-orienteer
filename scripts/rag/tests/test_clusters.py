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


if __name__ == "__main__":
    unittest.main()
