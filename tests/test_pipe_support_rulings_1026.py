"""P.E. rulings of 2026-10-26, ported in plugin 0.3.2 — each pinned by the hand number the
engine repo's fixtures carry, plus the two reviewer findings the engine does not make.

  1. "Base metal governs" (J4) warning only at a base-metal ratio >= 0.5
  2. J10.1 keeps tw + 2w as the loaded width and says so; the reviewer adds the flange-weld note
  3. psi_cp,N (ACI 17.6.2.6) for post-installed anchors in uncracked concrete, cac from the ESR
  4. WT flexure honours the stem orientation (F9: Mp = My, B < 0, stem local buckling)
  5. goalpost / trapeze headers are checked as simple spans
  6. ASD anchorage governed by a wind combination -> reviewer recommends LRFD.
     SUPERSEDED 2026-10-30 (owner ruling, plugin 0.7.2, P.E. confirmation pending): the
     "documented only" treatment is replaced by an automatic envelope guard ("manual check
     required", NOT ISSUABLE verdict, exit 3) - pinned in test_pipe_support_asd_wind_guard.py.
     The reviewer finding pinned below stays as defence in depth.

Standard library only:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts"))

from pipe_support import review as V  # noqa: E402
from pipe_support.aisc import aisc_member_design, find_shape, section_from_row  # noqa: E402
from pipe_support.assembly import analyze_assembly, csa_preset, simple_span_point_loads  # noqa: E402
from pipe_support.baseplate import base_plate_anchorage  # noqa: E402

A36 = {"Fy": 36, "Fu": 58}


def csa1(**over):
    d = csa_preset("csa-type-1")
    d.update({"method": "LRFD", "tag": "PS-101", "material": A36,
              "arms": [{"shape": "W6X15", "elevation": 96, "projection": 24,
                        "pipes": [{"tag": "6-P-1201", "offset": 8, "vertical": 1.2, "transverse": 0.2},
                                  {"tag": "6-P-1202", "offset": 18, "vertical": 1.5, "transverse": 0.25}]}]})
    d.update(over)
    return d


def stage(r, needle):
    for s in r["output"]["stages"]:
        if needle in s["stage"]:
            return s
    raise AssertionError(f"no stage containing {needle!r}: {[s['stage'] for s in r['output']['stages']]}")


def check(st, needle):
    for c in st["checks"]:
        if needle in c["label"]:
            return c
    raise AssertionError(f"no check containing {needle!r}: {[c['label'] for c in st['checks']]}")


class J4Warning(unittest.TestCase):
    def test_fires_once_on_ps101(self):
        r = analyze_assembly(csa1())
        hits = [w for w in r["warnings"] if w.startswith("Base metal governs over the weld metal")]
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(check(stage(r, "Arm 1 to column weld"), "tension yielding")["ratio"], 0.831, places=3)
        self.assertLess(check(stage(r, "Column to base plate weld"), "shear rupture")["ratio"], 0.5)


class J10LoadedWidth(unittest.TestCase):
    def test_clause_states_tw_plus_2w_and_the_flange_caveat(self):
        r = analyze_assembly(csa1(weldSize=0.375))                 # 0.23 + 0.75 = 0.98 > 0.15*5.99
        c = check(stage(r, "Arm 1 to column weld"), "flange local bending")
        self.assertIn("tw + 2w = 0.98 in", c["clause"])
        self.assertIn("bf if the arm flanges are also welded", c["clause"])

    def test_reviewer_notes_the_assumption_when_the_row_is_present(self):
        r = analyze_assembly(csa1(weldSize=0.375))
        env = _env(r)
        f = [x for x in V.review(csa1(weldSize=0.375), env, {"pipes": []}) if x["title"].startswith("J10.1 loaded width")]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "info")
        self.assertIn("re-run the check with that detail", f[0]["detail"])

    def test_reviewer_flags_the_exemption_when_j10_was_not_required(self):
        r = analyze_assembly(csa1())                                # 0.73 < 0.8985: not required
        f = [x for x in V.review(csa1(), _env(r), {"pipes": []}) if x["title"].startswith("J10.1 exemption")]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "minor")


class PsiCpN(unittest.TestCase):
    base = {"method": "LRFD", "columnDepth": 5.99, "columnWidth": 5.99,
            "plateLength": 12, "plateWidth": 12, "plateThickness": 0.75, "plateFy": 36,
            "fc": 4000, "pierLength": 16, "pierWidth": 16, "anchorType": "post-installed-adhesive",
            "anchorCount": 4, "anchorDiameter": 0.75, "anchorEmbedment": 4.25, "anchorFuta": 58,
            "anchorSpacingLength": 9, "anchorSpacingWidth": 9, "anchorEdgeDistance": 3.5,
            "P": 2.7, "M": 75, "V": 0.85}

    def breakout(self, **over):
        r = base_plate_anchorage({**self.base, **over})
        c = [x for x in r["output"]["checks"] if x["label"] == "Concrete breakout (tension)"][0]
        return c["capacity"], c["clause"], r["warnings"]

    def test_cracked_default_is_untouched(self):
        cap, clause, warns = self.breakout()
        self.assertNotIn("psi_cp,N", clause)
        self.assertFalse(any("cac" in w for w in warns))

    def test_default_cac_two_hef_with_warning(self):
        # hand: cac = 8.5; psi_cp,N = max(3.5/8.5, 6.375/8.5) = 0.75; psi_c,N = 1.25 -> x0.9375
        cracked = self.breakout()[0]
        cap, clause, warns = self.breakout(cracked=False)
        self.assertAlmostEqual(cap / cracked, 1.25 * 0.75, places=4)
        self.assertIn("psi_cp,N = 0.75 (17.6.2.6, cac = 8.5 in)", clause)
        self.assertTrue(any("Table 17.9.5 default cac = 2·hef = 8.5 in" in w for w in warns))

    def test_esr_cac(self):
        cracked = self.breakout()[0]
        cap, clause, warns = self.breakout(cracked=False, cac=7)
        self.assertAlmostEqual(cap / cracked, 1.25 * 6.375 / 7, places=4)
        self.assertIn("psi_cp,N = 0.9107", clause)
        self.assertFalse(any("Table 17.9.5" in w for w in warns))

    def test_unity_cases(self):
        cracked = self.breakout()[0]
        self.assertAlmostEqual(self.breakout(cracked=False, cac=3)[0] / cracked, 1.25, places=4)
        ci = self.breakout(anchorType="cast-in")[0]
        cap, clause, _ = self.breakout(anchorType="cast-in", cracked=False)
        self.assertAlmostEqual(cap / ci, 1.25, places=4)
        self.assertNotIn("psi_cp,N", clause)
        self.assertIn("cac = 17 in", self.breakout(anchorType="post-installed-mechanical", cracked=False)[1])


class WTStemOrientation(unittest.TestCase):
    WT = section_from_row(find_shape("WT5X11"))

    def member(self, sic):
        i = {"section": self.WT, "material": A36, "method": "LRFD", "Lx": 24, "Ly": 24, "Lb": 24,
             "Kx": 2.1, "Ky": 2.1, "demand": {"Mx": 40, "Vx": 2}}
        if sic is not None:
            i["stemInCompression"] = sic
        return aisc_member_design(i)

    def test_tension_branch(self):
        self.assertAlmostEqual(self.member(False)["output"]["capacity"]["momentX"], 0.9 * 99.072, places=3)

    def test_compression_branch_mp_equals_my(self):
        r = self.member(True)
        self.assertAlmostEqual(r["output"]["capacity"]["momentX"], 0.9 * 61.92, places=3)
        self.assertAlmostEqual(r["output"]["governingRatio"], 40 / 55.728, places=4)
        self.assertTrue(any("stem in flexural compression" in w for w in r["warnings"]))

    def test_no_orientation_keeps_tension_and_asks(self):
        r = self.member(None)
        self.assertAlmostEqual(r["output"]["capacity"]["momentX"], 0.9 * 99.072, places=3)
        self.assertTrue(any("supply stemInCompression" in w for w in r["warnings"]))

    def test_arm_default_is_stem_down_compression(self):
        arm = {"shape": "WT5X11", "elevation": 96, "projection": 24, "pipes": [{"offset": 20, "vertical": 1.5}]}
        d = analyze_assembly(csa1(arms=[arm]))
        self.assertAlmostEqual(check(stage(d, "Arm 1 @"), "Flexure, major")["capacity"], 55.728, places=3)
        self.assertTrue(any("WT stem orientation not given" in w for w in d["warnings"]))
        u = analyze_assembly(csa1(arms=[dict(arm, stemOrientation="up")]))
        self.assertAlmostEqual(check(stage(u, "Arm 1 @"), "Flexure, major")["capacity"], 89.1648, places=3)
        self.assertFalse(any("WT stem orientation not given" in w for w in u["warnings"]))


class Header(unittest.TestCase):
    # hand: L = 60, 3 kip at 20 + 1 kip at 40 -> RB 1.6667, RA 2.3333, Mmax 46.667 at 20,
    # W6X15 EI = 29000*29.1, delta(30) = 0.018170 in (max of the three stations).
    EI = 29000 * 29.1

    def test_simple_span_statics(self):
        s = simple_span_point_loads([{"a": 20, "P": 3}, {"a": 40, "P": 1}], 60, self.EI)
        self.assertAlmostEqual(s["RA"], 2.3333, places=4)
        self.assertAlmostEqual(s["RB"], 1.6667, places=4)
        self.assertAlmostEqual(s["Mmax"], 46.6667, places=4)
        self.assertEqual(s["xM"], 20)
        self.assertAlmostEqual(s["delta"], 0.018170, places=6)
        c = simple_span_point_loads([{"a": 30, "P": 2}], 60, self.EI)
        self.assertAlmostEqual(c["delta"], 2 * 60 ** 3 / (48 * self.EI), places=10)

    def goalpost(self, spacing):
        o = {"type": "goalpost", "arms": [{"shape": "W6X15", "elevation": 96, "projection": 24,
                                            "pipes": [{"offset": 20, "vertical": 3}, {"offset": 40, "vertical": 1}]}]}
        if spacing is not None:
            o["columnSpacing"] = spacing
        return analyze_assembly(csa1(**o))

    def test_header_stage(self):
        r = self.goalpost(60)
        h = stage(r, 'Header @ EL 96" — W6X15, 60" span')
        self.assertEqual(h["component"], "header")
        self.assertAlmostEqual(check(h, "Flexure, major")["demand"], 46.6667, places=3)
        self.assertAlmostEqual(check(h, "Deflection")["demand"], 0.0182, places=4)
        self.assertAlmostEqual(check(h, "Deflection")["capacity"], 60 / 240, places=6)
        self.assertTrue(any("reactions A = 2.333 kip / B = 1.667 kip" in w for w in r["warnings"]))
        self.assertTrue(any("column A receives 58.3 %" in w for w in r["warnings"]))
        self.assertEqual(len([s for s in r["output"]["stages"] if s["component"] == "arm"]), 1)

    def test_long_span_is_weaker(self):
        short = check(stage(self.goalpost(60), "Header"), "Flexure, major")["capacity"]
        long = check(stage(self.goalpost(240), "Header"), "Flexure, major")["capacity"]
        self.assertLess(long, short)

    def test_no_spacing_no_header(self):
        r = self.goalpost(None)
        self.assertFalse(any(s["component"] == "header" for s in r["output"]["stages"]))
        self.assertTrue(any("header span could not be checked" in w for w in r["warnings"]))

    def test_wt_header_reverses_the_stem_rule(self):
        r = analyze_assembly(csa1(type="goalpost", columnSpacing=24,
                                  arms=[{"shape": "WT5X11", "elevation": 96, "projection": 24,
                                         "stemOrientation": "down", "pipes": [{"offset": 12, "vertical": 1}]}]))
        self.assertAlmostEqual(check(stage(r, "Arm 1 @"), "Flexure, major")["capacity"], 55.728, places=3)
        self.assertAlmostEqual(check(stage(r, "Header"), "Flexure, major")["capacity"], 89.1648, places=3)


class ASDWindAnchorage(unittest.TestCase):
    def test_combo_id_decoding(self):
        for cid, want in (("ASD-5a+", True), ("ASD-5a-+T", True), ("ASD-7a+", True), ("ASD-6a-", True),
                          ("ASD-1a", False), ("ASD-2a+T", False), ("ASD-0.6D+T", False), ("ASD-HYD", False),
                          ("LRFD-5a+", False), ("LRFD-4a+", False), ("ASD-5a+ (service)", True), ("", False)):
            self.assertEqual(V.asd_wind_combo(cid), want, cid)

    def test_finding_only_for_asd_wind_governed_anchorage(self):
        st = {"stage": "Anchorage", "component": "anchorage", "status": "pass", "ratio": 0.93,
              "governing": "Concrete breakout (tension)", "combo": "ASD-5a+", "checks": []}
        env = {"stages": [st], "warnings": [], "governingRatio": 0.93, "governingStage": "Anchorage",
               "governingRun": {"warnings": []}}
        design = {"method": "ASD", "arms": [], "columnShape": None}
        f = [x for x in V.review(design, env, {"pipes": []}) if x["title"].startswith("ASD anchorage governed")]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "major")
        self.assertIn("1/0.6 = 1.67", f[0]["detail"])
        self.assertIn("LRFD", f[0]["remedy"])
        for combo in ("ASD-1a", "LRFD-5a+"):
            env2 = copy.deepcopy(env)
            env2["stages"][0]["combo"] = combo
            self.assertEqual([x for x in V.review(design, env2, {"pipes": []})
                              if x["title"].startswith("ASD anchorage governed")], [], combo)


def _env(r):
    """Minimal envelope from one engine run, the shape review() reads."""
    stages = [dict(s, combo="LRFD-1a") for s in r["output"]["stages"]]
    return {"stages": stages, "warnings": r["warnings"], "governingRatio": r["output"]["governingRatio"],
            "governingStage": r["output"]["governingStage"], "governingRun": {"warnings": r["warnings"]}}


if __name__ == "__main__":
    unittest.main()
