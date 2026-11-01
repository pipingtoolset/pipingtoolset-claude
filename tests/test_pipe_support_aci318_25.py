"""Plugin 0.9.0: ACI CODE-318-25 anchorage (ACI 318-19 selectable) and the AISC 360-22
conformance port from the PiperSTR engine (pipecalcpro main 4656183, PR #181, CHANGELOG-CALC 2026-11-01).

The parity goldens prove the port reproduces the engine case by case; these tests pin the
headline numbers the engine changelog states, the edition switch, and the reviewer finding
for an unset Anchor Category.

    python -m unittest tests.test_pipe_support_aci318_25 -v
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts")
sys.path.insert(0, SCRIPTS)

import support_calc  # noqa: E402
from pipe_support.assembly import CSA_PRESETS, analyze_assembly  # noqa: E402
from pipe_support.baseplate import anchor_phi, base_plate_anchorage, psi_a  # noqa: E402
from pipe_support.weld import fillet_weld  # noqa: E402

A36 = {"Fy": 36, "Fu": 58}
# The PiperSTR UI default loads: the two PS-101 pipes on arm 1 (1.2 / 1.5 kip vertical).
UI_PIPES = [{"tag": "6-P-1201", "offset": 8, "vertical": 1.2, "transverse": 0.2, "longitudinal": 0},
            {"tag": "6-P-1202", "offset": 18, "vertical": 1.5, "transverse": 0.25, "longitudinal": 0}]


def preset(name, verticals=None, **bp):
    p = copy.deepcopy(CSA_PRESETS[name])
    p["arms"][0]["pipes"] = copy.deepcopy(UI_PIPES)
    if verticals:
        for pipe, v in zip(p["arms"][0]["pipes"], verticals):
            pipe["vertical"] = v
    p["baseplate"].update(bp)
    return analyze_assembly({"method": "LRFD", "material": A36, **p})


def stage(r, prefix):
    return [s for s in r["output"]["stages"] if s["stage"].startswith(prefix)][0]


class PresetResults(unittest.TestCase):
    """CHANGELOG-CALC 2026-11-01 preset table (LRFD, A36, UI default loads)."""

    def test_csa_type_1(self):
        r = preset("csa-type-1")
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["output"]["governingRatio"], 0.8314)                     # arm weld J4-1, unchanged
        self.assertEqual(stage(r, "Arm 1 to column weld")["ratio"], 0.8314)
        base = stage(r, "Column to base plate weld")
        self.assertEqual((base["ratio"], base["governing"]), (0.2996, "Fillet weld stress"))  # 0.1997 x 1.5
        self.assertEqual(stage(r, "Anchorage")["ratio"], 0.4497)                    # 0.2506 x 0.70/0.65 / 0.60

    def test_csa_type_2_still_fails_at_its_default_loads(self):
        r = preset("csa-type-2")
        self.assertEqual(r["status"], "fail")
        self.assertEqual(r["output"]["governingRatio"], 1.2341)
        weld = stage(r, "Arm 1 to column weld")
        self.assertEqual((weld["ratio"], weld["governing"]), (1.2341, "Fillet weld stress"))
        self.assertEqual(stage(r, "Arm 1 @")["ratio"], 0.9436)                     # F10.2 principal-axis LTB
        self.assertEqual(stage(r, "Column to base plate weld")["ratio"], 0.2996)
        self.assertEqual(stage(r, "Anchorage")["ratio"], 0.4497)

    def test_318_19_reproduces_the_legacy_anchorage(self):
        self.assertEqual(stage(preset("csa-type-1", aciEdition="318-19"), "Anchorage")["ratio"], 0.2506)

    def test_heavy_8_10_kip_fails_at_category_3_and_passes_at_category_1(self):
        r = preset("csa-type-1", verticals=(8, 10))
        a = stage(r, "Anchorage")
        self.assertEqual((a["status"], a["ratio"], a["governing"]),
                         ("fail", 1.6101, "Tension-shear interaction (concrete)"))
        self.assertEqual(stage(r, "Column to base plate weld")["ratio"], 1.0783)
        self.assertEqual(stage(preset("csa-type-1", verticals=(8, 10), anchorCategory=1), "Anchorage")["status"],
                         "pass")


class EditionFactors(unittest.TestCase):

    def test_table_21_2_1_phi(self):
        self.assertEqual(anchor_phi("318-25", True, "nonredundant")["concreteTension"], 0.65)
        self.assertEqual(anchor_phi("318-25", True, "redundant")["concreteTension"], 0.75)
        self.assertEqual(anchor_phi("318-25", True, "nonredundant")["concreteShear"], 0.75)
        self.assertEqual(anchor_phi("318-19", True, "redundant")["concreteTension"], 0.70)
        self.assertEqual((anchor_phi("318-19", False, "nonredundant")["steelTension"],
                          anchor_phi("318-19", False, "nonredundant")["steelShear"]), (0.65, 0.60))

    def test_table_17_5_4_1_psi_a(self):
        self.assertEqual([psi_a("318-25", False, c, False, "tension") for c in (1, 2, 3)], [0.85, 0.75, 0.60])
        self.assertEqual([psi_a("318-25", False, c, True, "tension") for c in (1, 2, 3)], [1.0, 0.85, 0.75])
        self.assertEqual(psi_a("318-25", True, 3, False, "tension"), 0.95)
        self.assertEqual(psi_a("318-25", False, 3, False, "shear"), 0.95)
        self.assertEqual(psi_a("318-19", False, 3, False, "tension"), 1.0)

    BP = {"method": "LRFD", "columnDepth": 5.99, "columnWidth": 5.99, "plateLength": 12, "plateWidth": 12,
          "plateThickness": 0.75, "plateFy": 36, "fc": 4000, "pierLength": 16, "pierWidth": 16,
          "anchorType": "post-installed-adhesive", "anchorCount": 4, "anchorDiameter": 0.75,
          "anchorEmbedment": 4.25, "anchorFuta": 58, "anchorSpacingLength": 9, "anchorSpacingWidth": 9,
          "anchorEdgeDistance": 3.5, "P": 2.7, "M": 75, "V": 0.85}

    def test_unset_category_is_category_3_with_a_review_warning(self):
        r = base_plate_anchorage(dict(self.BP))
        self.assertTrue(any(w.startswith("REVIEW: post-installed anchor with no ACI 355.2/355.4 Anchor Category")
                            for w in r["warnings"]))
        clause = [c for c in r["output"]["checks"] if c["label"] == "Concrete breakout (tension)"][0]["clause"]
        self.assertIn("psi_a = 0.6 (Table 17.5.4.1)", clause)
        self.assertIn("ACI CODE-318-25", clause)
        entered = base_plate_anchorage(dict(self.BP, anchorCategory=3))
        self.assertFalse(any(w.startswith("REVIEW:") for w in entered["warnings"]))
        self.assertEqual(entered["output"]["checks"], r["output"]["checks"])

    def test_split_interaction_on_318_25_and_trilinear_on_318_19(self):
        new = {c["label"] for c in base_plate_anchorage(dict(self.BP))["output"]["checks"]}
        self.assertTrue({"Tension-shear interaction (concrete)", "Tension-shear interaction (steel)"} <= new)
        old = {c["label"] for c in base_plate_anchorage(dict(self.BP, aciEdition="318-19"))["output"]["checks"]}
        self.assertIn("Tension-shear interaction", old)
        self.assertNotIn("Tension-shear interaction (concrete)", old)

    def test_asd_divisor_is_the_project_basis_under_both_editions(self):
        for ed, label in (("318-25", "ACI CODE-318-25"), ("318-19", "ACI 318-19")):
            w = [x for x in base_plate_anchorage(dict(self.BP, method="ASD", aciEdition=ed))["warnings"]
                 if "strength-design (LRFD) chapter" in x][0]
            self.assertIn(f"{label} Chapter 17 is a strength-design (LRFD) chapter", w)
            self.assertIn("divided by 1.5", w)
            self.assertIn("project basis per the owner P.E. ruling of 2026-10-26, not an ACI provision", w)
            self.assertNotIn("R17.5.3", w)


class WeldKds(unittest.TestCase):

    W = {"method": "LRFD", "size": 0.25, "FEXX": 70, "pattern": "single", "depth": 10, "Vtransverse": 10}

    def test_kds_is_1_by_default_and_1_5_only_with_the_opt_in(self):
        self.assertEqual(fillet_weld(dict(self.W))["output"]["directionalFactor"], 1.0)
        self.assertEqual(fillet_weld(dict(self.W))["output"]["ratio"], 0.1796)
        opt = fillet_weld(dict(self.W, strainCompatibility="linear-through-cg"))["output"]
        self.assertEqual((opt["directionalFactor"], opt["ratio"]), (1.5, 0.1197))

    def test_opt_in_is_refused_with_moment_or_all_round(self):
        for over in ({"M": 10}, {"pattern": "all-round", "width": 6}):
            r = fillet_weld(dict(self.W, strainCompatibility="linear-through-cg", **over))
            self.assertEqual(r["output"]["directionalFactor"], 1.0)
            self.assertTrue(any("strainCompatibility 'linear-through-cg' ignored" in w for w in r["warnings"]))


def _ps201():
    with open(os.path.join(SCRIPTS, "examples", "ps-201-caesar.json"), encoding="utf-8") as fh:
        s = json.load(fh)
    s["optimize"] = False
    return s


def _category_findings(doc):
    return [f for f in doc["findings"] if f["title"].startswith("Anchor Category not entered")]


class AnchorCategoryFinding(unittest.TestCase):

    def test_shipped_ps201_fails_anchorage_and_raises_a_major_finding(self):
        doc = support_calc.run(_ps201(), optimize=False)
        st = [s for s in doc["envelope"]["stages"] if s["component"] == "anchorage"][0]
        self.assertEqual((st["status"], st["ratio"], st["governing"]),
                         ("fail", 1.1356, "Tension-shear interaction (concrete)"))
        f = _category_findings(doc)
        self.assertEqual([x["severity"] for x in f], ["major"])
        self.assertIn("Category 3", f[0]["detail"])
        self.assertIn("ESR", f[0]["detail"])
        self.assertIn("the verdict may change", f[0]["remedy"])
        self.assertIn("Table 17.5.4.1", f[0]["basis"])
        # the engine's REVIEW warning is not repeated as a second, info-level finding
        self.assertFalse([x for x in doc["findings"] if x["detail"].startswith("REVIEW: post-installed")])

    def test_category_entered_clears_the_finding(self):
        s = _ps201()
        s["design"]["baseplate"] = {"anchorCategory": 1}
        doc = support_calc.run(s, optimize=False)
        self.assertEqual(_category_findings(doc), [])
        st = [x for x in doc["envelope"]["stages"] if x["component"] == "anchorage"][0]
        self.assertEqual((st["status"], st["ratio"]), ("pass", 0.7423))

    def test_passing_anchorage_gives_an_info_finding(self):
        with open(os.path.join(SCRIPTS, "examples", "ps-101-factored.json"), encoding="utf-8") as fh:
            spec = json.load(fh)
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual([x["severity"] for x in _category_findings(doc)], ["info"])

    def test_no_finding_on_318_19_or_cast_in(self):
        for bp in ({"aciEdition": "318-19"}, {"anchorType": "cast-in", "bondStrength": None}):
            s = _ps201()
            s["design"]["baseplate"] = {k: v for k, v in bp.items() if v is not None}
            if bp.get("anchorType") == "cast-in":
                s["design"]["baseplate"].update({"anchorEmbedment": 12, "anchorEdgeDistance": 7.5,
                                                 "pierLength": 36, "pierWidth": 36})
            doc = support_calc.run(s, optimize=False)
            self.assertEqual(_category_findings(doc), [], bp)


class Docs(unittest.TestCase):

    def test_report_names_the_edition(self):
        doc = support_calc.run(_ps201(), optimize=False)
        from pipe_support import report as R
        md = R.markdown(doc)
        self.assertIn("AISC 360-22 / ACI CODE-318-25 / ASCE 7-22", md)
        self.assertIn("ACI CODE-318-25 Ch. 17 - anchorage", [r["area"] for r in doc["compliance"]])
        s = _ps201()
        s["design"]["baseplate"] = {"aciEdition": "318-19"}
        self.assertIn("AISC 360-22 / ACI 318-19 / ASCE 7-22", R.markdown(support_calc.run(s, optimize=False)))


if __name__ == "__main__":
    unittest.main()
