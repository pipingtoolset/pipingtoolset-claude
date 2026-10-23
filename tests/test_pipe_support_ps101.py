"""PS-101 verification: the skill reproduces a pipingtoolset.com PiperSTR Design Summary
Report value for value (every stage, every limit-state row, base reactions, verdict and
the assumptions list). The report is transcribed in tests/fixtures/ps-101-design-summary.json.

Standard library only:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts"))

from pipe_support.assembly import analyze_assembly  # noqa: E402

with open(os.path.join(ROOT, "tests", "fixtures", "ps-101-design-summary.json"), encoding="utf-8") as fh:
    FX = json.load(fh)


class PS101(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.r = analyze_assembly(FX["input"])
        cls.o = cls.r["output"]
        cls.e = FX["expect"]
        cls.tol = FX["tol"]

    def near(self, got, want, what):
        self.assertLessEqual(abs(float(got) - float(want)), self.tol + 1e-9, what)

    def test_verdict(self):
        self.assertEqual(self.r["status"], self.e["status"])
        self.near(self.o["governingRatio"], self.e["governingRatio"], "governing ratio")
        self.assertEqual(self.o["governingCheck"], self.e["governingCheck"])
        self.assertIn(self.e["governingStageContains"], self.o["governingStage"])

    def test_base_reactions_and_lateral(self):
        for k, v in self.e["baseReactions"].items():
            self.near(self.o["baseReactions"][k], v, k)
        for k, v in self.e["lateral"].items():
            self.near(self.o["lateral"][k], v, k)

    def test_every_stage_and_row(self):
        self.assertEqual(len(self.o["stages"]), len(self.e["stages"]))
        for est, st in zip(self.e["stages"], self.o["stages"]):
            self.assertEqual(st["component"], est["component"], st["stage"])
            self.near(st["ratio"], est["ratio"], st["stage"])
            rows = {c["label"]: c for c in st["checks"]}
            for label, dem, cap, rat, clause in est["checks"]:
                with self.subTest(stage=st["stage"], row=label):
                    self.assertIn(label, rows)
                    c = rows[label]
                    self.near(c["demand"], dem, "demand")
                    self.near(c["capacity"], cap, "capacity")
                    self.near(c["ratio"], rat, "ratio")
                    self.assertIn(clause, c["clause"])

    def test_assumptions_and_warnings(self):
        text = " || ".join(self.r["warnings"])
        for w in self.e["warningsContain"]:
            with self.subTest(warning=w):
                self.assertIn(w, text)
        for w in self.e.get("warningsAbsent", []):        # the false J2.4 / J2.2b warnings are gone
            with self.subTest(absent=w):
                self.assertNotIn(w, text)


if __name__ == "__main__":
    unittest.main()
