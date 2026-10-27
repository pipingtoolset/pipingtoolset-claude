"""Regression tests for the bolted-flange skill and its calculators.

Standard library only (unittest), so the gate runs anywhere Python 3.9+ runs:

    python -m unittest discover -s tests -v

Three layers:
  1. Parity - the two ported modules reproduce the vendored calculation-engine fixtures.
  2. Hand-derived cases - worked on paper from the published equations, using clearly
     fictitious round inputs (these are NOT code values), so the script is checked
     against arithmetic that did not come from the engine.
  3. CLI and SKILL.md guards.
"""

from __future__ import annotations

import ast
import copy
import glob
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "bolted-flange")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "bolted_flange.py")
EXAMPLE = os.path.join(SCRIPTS, "examples", "integral-weld-neck.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import bolted_flange as bf  # noqa: E402
import content_guard  # noqa: E402
import parity  # noqa: E402

ENGINE_MODULES = ["aux.app2-flange-integral", "connections.flange-equivalent-pressure"]
NEW_MODULES = ["connections.flange-derive"]

# A loose ring flange worked by hand (all fictitious round numbers).
#   A 16, B 8, C 14, G 10, t 1, N 1, P 100, m 2, y 5000, 8 bolts of 0.5 in^2, 1 in bolts, all S = 20000
#   b0 = N/2 = 0.5, b = 0.5 sqrt(0.5) = 0.353553
#   H  = pi/4 G^2 P = 7853.98     Hp = 2 b pi G m P = 4442.88     Wm1 = 12296.86
#   Wm2 = pi b G y = 55536.04     Am = max(Wm1/Sb, Wm2/Sa) = 2.7768   Ab = 4
#   Wg = (Am + Ab)/2 Sa = 67768.0
#   K = 2: Y = (0.66845 + 5.7169 K^2 log10(K)/(K^2 - 1))/(K - 1) = 2.96306, Z = (K^2+1)/(K^2-1) = 5/3
#   HD = pi/4 B^2 P = 5026.55   HT = H - HD = 2827.43   HG = Wm1 - H = 4442.88
#   hD = (C-B)/2 = 3   hG = (C-G)/2 = 2   hT = (hD + hG)/2 = 2.5
#   bolt spacing pi C/n = 5.49779   limit 2 d + t = 3   Bsc = sqrt(5.49779/3) = 1.35373
#   Mo = (HD hD + HT hT + HG hG) Bsc = 42011.77     Mg = Wg hG Bsc = 183479.74
#   ST = Y Mo/(t^2 B) = 15560.4 (operating)          67957.7 (seating)
LOOSE = dict(attachment="loose", P=100, A=16, B=8, C=14, t=1, G=10, N=1, m=2, y=5000, nBolts=8, aRoot=0.5,
             boltDia=1, Sa=20000, Sb=20000, Sf=20000, SfAmbient=20000, Edesign=10000000, Eambient=11000000)


def run(module: str, inputs: dict) -> dict:
    return bf.REGISTRY[module](dict(inputs))


class Rounding(unittest.TestCase):

    def test_half_up_on_exact_decimal_halves(self):
        self.assertEqual(bf.round_half_up(1.005, 2), 1.01)     # float-safe via repr
        self.assertEqual(bf.round_half_up(2.5, 0), 3.0)
        self.assertEqual(bf.round_half_up(-2.5, 0), -3.0)      # away from zero

    def test_non_finite_passes_through(self):
        self.assertTrue(math.isinf(bf.round_half_up(float("inf"), 3)))
        self.assertTrue(math.isnan(bf.round_half_up(float("nan"), 3)))


class Parity(unittest.TestCase):
    """Each ported function against the vendored fixtures (tests/parity.py)."""

    def _check(self, module: str):
        fails = parity.run_fixture(bf.REGISTRY, module)
        self.assertEqual(fails, [], "\n".join(fails))

    def test_manifest_lists_exactly_the_two_ported_modules(self):
        self.assertEqual(parity.modules_for("bolted-flange"), ENGINE_MODULES)

    def test_registry_is_the_ported_pair_plus_the_new_helper(self):
        self.assertEqual(sorted(bf.REGISTRY), sorted(ENGINE_MODULES + NEW_MODULES))
        self.assertEqual(sorted(bf.CITATIONS), sorted(bf.REGISTRY))
        self.assertEqual(sorted(bf.USER_SUPPLIED), sorted(bf.REGISTRY))
        self.assertEqual(sorted(bf.FIELDS), sorted(bf.REGISTRY))

    def test_flange_equivalent_pressure(self):
        self._check("connections.flange-equivalent-pressure")

    def test_app2_flange_integral(self):
        self._check("aux.app2-flange-integral")

    def test_every_manifest_module_is_registered(self):
        for module in parity.modules_for("bolted-flange"):
            self.assertIn(module, bf.REGISTRY)
            self.assertEqual(parity.load(module)["module"], module)

    def test_integral_fixture_matches_the_printed_reference_report(self):
        """Digits printed by the commercial program the engine was validated against."""
        case = parity.load("aux.app2-flange-integral")["cases"][0]
        out = run("aux.app2-flange-integral", case["input"])["output"]
        self.assertAlmostEqual(out["operating"]["SH"], 17116, delta=1.0)
        self.assertAlmostEqual(out["MoFtLb"], 35250.22, delta=0.5)
        self.assertAlmostEqual(out["Joperating"], 0.357, delta=0.001)
        self.assertAlmostEqual(out["Jseating"], 0.275, delta=0.001)

    def test_envelope_shape(self):
        for module in ENGINE_MODULES:
            res = run(module, parity.load(module)["cases"][0]["input"])
            self.assertEqual(set(res), {"module", "output", "status", "warnings"})
            self.assertEqual(res["module"], module)
            self.assertIn(res["status"], {"pass", "fail", "na"})
            self.assertIsInstance(res["warnings"], list)


class FlangeDerive(unittest.TestCase):
    """Round numbers worked on paper."""

    # flat, ID 10, OD 12:   N = (12 - 10)/2 = 1,  b0 = N/2 = 0.5 > 0.25
    #   b = 0.5 sqrt(0.5) = 0.353553,  G = OD - 2b = 12 - 0.707107 = 11.292893
    def test_flat_wide_gasket(self):
        out = run("connections.flange-derive", dict(facing="flat", gasket_ID=10, gasket_OD=12))["output"]
        self.assertEqual(out["N"], 1.0)
        self.assertEqual(out["b0"], 0.5)
        self.assertAlmostEqual(out["b"], 0.353553, delta=1e-6)
        self.assertAlmostEqual(out["G"], 11.292893, delta=1e-6)

    # ring joint, ID 10, OD 12:  N = 1, b0 = N/8 = 0.125 <= 0.25, b = b0, G = (10 + 12)/2 = 11
    def test_ring_joint(self):
        out = run("connections.flange-derive", dict(facing="ring-joint", gasket_ID=10, gasket_OD=12))["output"]
        self.assertEqual(out["b0"], 0.125)
        self.assertEqual(out["b"], 0.125)
        self.assertEqual(out["G"], 11.0)

    # ring joint, ID 10, OD 16: N = 3, b0 = 3/8 = 0.375 > 0.25, b = 0.5 sqrt(0.375) = 0.306186, G = 16 - 2b = 15.387628
    def test_wide_ring_joint_uses_od_minus_2b_and_the_warning_says_so(self):
        res = run("connections.flange-derive", dict(facing="ring-joint", gasket_ID=10, gasket_OD=16))
        self.assertEqual(res["output"]["b0"], 0.375)
        self.assertAlmostEqual(res["output"]["G"], 15.387628, delta=1e-6)
        ring = [w for w in res["warnings"] if w.startswith("Ring joint")]
        self.assertEqual(len(ring), 1)
        self.assertIn("OD - 2b", ring[0])
        self.assertNotIn("mean of the contact ID and OD", ring[0])
        narrow = run("connections.flange-derive", dict(facing="ring-joint", gasket_ID=10, gasket_OD=12))
        self.assertTrue(any("mean of the contact ID and OD" in w for w in narrow["warnings"] if w.startswith("Ring joint")))

    def test_hub_group_warns_that_g0_is_the_pipe_wall_only_when_bore_is_pipe_id(self):
        res = run("connections.flange-derive", dict(pipe_OD=10.75, B=10, X=12, Y=4, t=1.5))
        self.assertTrue(any("nominal" in w and "pipe inside diameter" in w for w in res["warnings"]))

    # flat, ID 10, OD 10.4: N = 0.2, b0 = 0.1, b = 0.1, G = 10.2 (mean diameter)
    # flat, ID 10, OD 11:   N = 0.5, b0 = 0.25 exactly, still the narrow branch: b = 0.25, G = 10.5
    def test_b0_boundary_at_one_quarter_inch(self):
        narrow = run("connections.flange-derive", dict(facing="flat", gasket_ID=10, gasket_OD=10.4))["output"]
        self.assertEqual((narrow["b0"], narrow["b"], narrow["G"]), (0.1, 0.1, 10.2))
        edge = run("connections.flange-derive", dict(facing="flat", gasket_ID=10, gasket_OD=11))["output"]
        self.assertEqual((edge["b0"], edge["b"], edge["G"]), (0.25, 0.25, 10.5))

    # 1 in - 8 UN: root diameter 1 - 1.299038/8 = 0.837620, area pi/4 x 0.837620^2 = 0.551041 in^2
    def test_un_root_area_one_inch_eight_tpi(self):
        out = run("connections.flange-derive", dict(bolt_D=1, bolt_tpi=8, nBolts=20))["output"]
        self.assertAlmostEqual(out["boltRootArea"], math.pi / 4 * (1 - 1.299038 / 8) ** 2, delta=1e-6)
        self.assertAlmostEqual(out["boltRootArea"], 0.551041, delta=1e-6)
        self.assertAlmostEqual(out["Ab"], 20 * 0.551041, delta=2e-4)

    def test_root_area_is_smaller_than_the_nominal_circle(self):
        out = run("connections.flange-derive", dict(bolt_D=1, bolt_tpi=8))["output"]
        self.assertLess(out["boltRootArea"], math.pi / 4)   # the "nominal diameter" error in the checklist

    # pipe OD 10.75, B 10, X 12, Y 4, t 1.5:  g0 = 0.375, g1 = (12 - 10)/2 = 1, h = 4 - 1.5 = 2.5
    def test_hub_geometry(self):
        out = run("connections.flange-derive", dict(pipe_OD=10.75, B=10, X=12, Y=4, t=1.5))["output"]
        self.assertEqual((out["g0"], out["g1"], out["h"]), (0.375, 1.0, 2.5))

    def test_status_is_na_and_groups_combine(self):
        res = run("connections.flange-derive", dict(facing="flat", gasket_ID=10, gasket_OD=12, bolt_D=1,
                                                    bolt_tpi=8, pipe_OD=10.75, B=10, X=12, Y=4, t=1.5))
        self.assertEqual(res["status"], "na")
        for key in ("N", "b0", "b", "G", "boltRootArea", "g0", "g1", "h"):
            self.assertIn(key, res["output"])

    def test_feeds_the_detailed_module(self):
        """The derived G, N, b and hub values are valid inputs to the analysis (fixture-style round trip)."""
        d = run("connections.flange-derive", dict(facing="flat", gasket_ID=16, gasket_OD=18, bolt_D=1, bolt_tpi=8,
                                                  nBolts=20, pipe_OD=15.8, B=15, X=17.4, Y=5, t=2))["output"]
        self.assertEqual((d["g0"], d["g1"], d["h"]), (0.4, 1.2, 3.0))
        with open(EXAMPLE, encoding="utf-8") as fh:
            ex = json.load(fh)
        self.assertAlmostEqual(ex["G"], d["G"], delta=1e-6)
        self.assertAlmostEqual(ex["aRoot"], d["boltRootArea"], delta=1e-6)
        self.assertEqual(ex["N"], d["N"])

    def test_errors(self):
        bad = [
            dict(),                                                           # no group
            dict(facing="flat", gasket_ID=12, gasket_OD=10),                  # OD not above ID
            dict(facing="flat", gasket_ID=0, gasket_OD=10),
            dict(facing="spiral", gasket_ID=10, gasket_OD=12),                # unknown facing
            dict(gasket_ID=10, gasket_OD=12),                                 # facing missing
            dict(bolt_D=1),                                                   # tpi missing
            dict(bolt_D=1, bolt_tpi=0),
            dict(bolt_D=0.5, bolt_tpi=0.5),                                   # root diameter not positive
            dict(pipe_OD=10, B=10, X=12, Y=4, t=1.5),                         # pipe OD not above bore
            dict(pipe_OD=10.75, B=10, X=9, Y=4, t=1.5),                       # hub base inside the bore
            dict(pipe_OD=10.75, B=10, X=12, Y=1, t=1.5),                      # no hub length
            dict(pipe_OD=10.75, B=10, X=12, Y=4),                             # t missing
        ]
        for inp in bad:
            with self.assertRaises(ValueError, msg=str(inp)):
                run("connections.flange-derive", inp)


class PressureEquivalentScreen(unittest.TestCase):
    # P 100, F 10000, M 50000 in-lbf, G 10:
    #   moment term = 16 x 50000 / (pi x 1000) = 254.648     force term = 4 x 10000 / (pi x 100) = 127.324
    #   Pe = 100 + 254.648 + 127.324 = 481.972
    BASE = dict(P=100, F=10000, M_in_lbf=50000, G=10, ratedPressure=500)

    def test_hand_case_in_lbf(self):
        res = run("connections.flange-equivalent-pressure", self.BASE)
        out = res["output"]
        self.assertAlmostEqual(out["momentTerm"], 16 * 50000 / (math.pi * 1000), delta=1e-3)
        self.assertAlmostEqual(out["momentTerm"], 254.648, delta=1e-3)
        self.assertAlmostEqual(out["forceTerm"], 127.324, delta=1e-3)
        self.assertAlmostEqual(out["Pe"], 481.972, delta=1e-3)
        self.assertAlmostEqual(out["utilization"], 481.972 / 500, delta=1e-4)
        self.assertEqual(res["status"], "pass")

    def test_fails_against_a_lower_rating(self):
        res = run("connections.flange-equivalent-pressure", dict(self.BASE, ratedPressure=450))
        self.assertEqual(res["status"], "fail")
        self.assertGreater(res["output"]["utilization"], 1)

    def test_engine_name_m_is_in_lbf(self):
        base = {k: v for k, v in self.BASE.items() if k != "M_in_lbf"}
        a = run("connections.flange-equivalent-pressure", dict(base, M=50000))["output"]
        b = run("connections.flange-equivalent-pressure", self.BASE)["output"]
        self.assertEqual(a, b)

    # The unit trap: 50000 in-lbf is 4166.67 ft-lbf. Same joint, same answer.
    def test_ft_lbf_is_converted_and_says_so(self):
        base = {k: v for k, v in self.BASE.items() if k != "M_in_lbf"}
        res = run("connections.flange-equivalent-pressure", dict(base, M_ft_lbf=50000 / 12))
        self.assertAlmostEqual(res["output"]["Pe"], 481.972, delta=1e-3)
        self.assertTrue(any("ft-lbf" in w or "M_ft_lbf" in w for w in res["warnings"]))

    def test_passing_ft_lbf_number_as_in_lbf_understates_the_screen(self):
        wrong = run("connections.flange-equivalent-pressure", dict(self.BASE, M_in_lbf=50000 / 12))["output"]["Pe"]
        right = run("connections.flange-equivalent-pressure", self.BASE)["output"]["Pe"]
        self.assertLess(wrong, right - 200)

    def test_exactly_one_moment_input(self):
        base = {k: v for k, v in self.BASE.items() if k != "M_in_lbf"}
        with self.assertRaises(ValueError):
            run("connections.flange-equivalent-pressure", base)
        with self.assertRaises(ValueError):
            run("connections.flange-equivalent-pressure", dict(base, M_in_lbf=1, M_ft_lbf=1))
        with self.assertRaises(ValueError):
            run("connections.flange-equivalent-pressure", dict(base, M=1, M_ft_lbf=1))

    def test_moment_sign_never_relieves(self):
        neg = run("connections.flange-equivalent-pressure", dict(self.BASE, M_in_lbf=-50000))["output"]
        self.assertAlmostEqual(neg["Pe"], 481.972, delta=1e-3)

    def test_compression_is_credited_only_with_a_warning(self):
        res = run("connections.flange-equivalent-pressure", dict(self.BASE, F=-10000))
        self.assertAlmostEqual(res["output"]["forceTerm"], -127.324, delta=1e-3)
        self.assertAlmostEqual(res["output"]["Pe"], 100 + 254.648 - 127.324, delta=1e-3)
        self.assertTrue(any("Compressive" in w for w in res["warnings"]))

    def test_engine_errors(self):
        for bad in (dict(G=0), dict(G=-1), dict(ratedPressure=0)):
            with self.assertRaises(ValueError, msg=str(bad)):
                run("connections.flange-equivalent-pressure", dict(self.BASE, **bad))


class DetailedAnalysisHandDerived(unittest.TestCase):

    def test_loose_ring_arithmetic(self):
        res = run("aux.app2-flange-integral", LOOSE)
        o = res["output"]
        self.assertEqual(o["Peq"], 100.0)
        self.assertAlmostEqual(o["b"], 0.35355, delta=1e-5)
        self.assertAlmostEqual(o["H"], 7853.98, delta=0.1)
        self.assertAlmostEqual(o["Hp"], 4442.88, delta=0.1)
        self.assertAlmostEqual(o["Wm1"], 12296.86, delta=0.1)
        self.assertAlmostEqual(o["Wm2"], 55536.04, delta=0.1)
        self.assertAlmostEqual(o["Am"], 2.7768, delta=1e-4)
        self.assertEqual(o["Ab"], 4.0)
        self.assertAlmostEqual(o["Wg"], 67768.0, delta=0.5)
        self.assertEqual(o["K"], 2.0)
        self.assertAlmostEqual(o["Y"], 2.9631, delta=1e-4)
        self.assertAlmostEqual(o["Z"], 1.6667, delta=1e-4)
        self.assertEqual((o["hD"], o["hT"], o["hG"]), (3.0, 2.5, 2.0))
        self.assertAlmostEqual(o["HD"], 5026.5, delta=0.1)
        self.assertAlmostEqual(o["HT"], 2827.4, delta=0.1)
        self.assertAlmostEqual(o["HG"], 4442.9, delta=0.1)
        self.assertAlmostEqual(o["boltSpacing"], 5.4978, delta=1e-4)
        self.assertEqual(o["boltSpacingMax"], 3.0)
        self.assertAlmostEqual(o["Bsc"], 1.3537, delta=1e-4)
        self.assertAlmostEqual(o["Mo"], 42011.8, delta=0.2)
        self.assertAlmostEqual(o["Mg"], 183479.7, delta=1.0)
        self.assertEqual(o["L"], 1.0)
        self.assertAlmostEqual(o["operating"]["ST"], 15560.4, delta=0.2)
        self.assertAlmostEqual(o["seating"]["ST"], 67957.7, delta=1.0)
        self.assertEqual((o["operating"]["SH"], o["operating"]["SR"]), (0.0, 0.0))   # no hub on a loose ring
        self.assertEqual(o["governing"], "gasket seating")
        self.assertEqual(res["status"], "fail")           # seating ST is far above Sf
        self.assertTrue(any("Loose-type" in w for w in res["warnings"]))

    # Rigidity (loose): J = 109.4 Mo_bare / (E t^3 KI ln K), Mo without Bsc = 42011.77/1.35373 = 31033.8
    #   J = 109.4 x 31033.8 / (1.0e7 x 1 x 0.2 x 0.693147) = 2.4491
    def test_loose_rigidity_uses_the_uncorrected_moment(self):
        o = run("aux.app2-flange-integral", LOOSE)["output"]
        self.assertAlmostEqual(o["Joperating"], 2.4491, delta=1e-4)
        with_bsc = 109.4 * o["Mo"] / (10e6 * 0.2 * math.log(2.0))
        self.assertGreater(with_bsc, o["Joperating"] * 1.3)     # applying Bsc to J would put it ~35 percent high

    def test_bolt_spacing_correction_can_be_switched_off(self):
        o = run("aux.app2-flange-integral", dict(LOOSE, applyBoltSpacing=False))["output"]
        self.assertEqual(o["Bsc"], 1.0)
        self.assertAlmostEqual(o["Mo"], 31033.8, delta=0.5)

    def test_wide_bolt_spacing_is_not_corrected_below_one(self):
        o = run("aux.app2-flange-integral", dict(LOOSE, nBolts=24, aRoot=0.2))["output"]    # 1.83 in spacing < 3 in limit
        self.assertEqual(o["Bsc"], 1.0)

    def test_external_loads_raise_peq(self):
        # Mext 5000 ft-lbf = 60000 in-lbf; Fax 2000 lbf; G 10:
        #   16 x 60000/(pi x 1000) = 305.577   4 x 2000/(pi x 100) = 25.465   Peq = 100 + 305.577 + 25.465 = 431.04
        o = run("aux.app2-flange-integral", dict(LOOSE, Mext=5000, Fax=2000))["output"]
        self.assertAlmostEqual(o["momentTerm"], 305.58, delta=0.01)
        self.assertAlmostEqual(o["forceTerm"], 25.46, delta=0.01)
        self.assertAlmostEqual(o["Peq"], 431.04, delta=0.01)

    def test_mext_in_lbf_alias_equals_ft_lbf_times_twelve(self):
        a = run("aux.app2-flange-integral", dict(LOOSE, Mext=5000))["output"]
        b = run("aux.app2-flange-integral", dict(LOOSE, Mext_in_lbf=60000))["output"]
        self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            run("aux.app2-flange-integral", dict(LOOSE, Mext=5000, Mext_in_lbf=60000))

    def test_negative_moment_never_relieves_but_compression_does(self):
        base = run("aux.app2-flange-integral", dict(LOOSE, Mext=5000))["output"]["Peq"]
        self.assertEqual(run("aux.app2-flange-integral", dict(LOOSE, Mext=-5000))["output"]["Peq"], base)
        res = run("aux.app2-flange-integral", dict(LOOSE, Fax=-2000))
        self.assertLess(res["output"]["Peq"], 100)
        self.assertTrue(any("Compressive" in w for w in res["warnings"]))

    def test_nonpositive_peq_is_an_error(self):
        with self.assertRaises(ValueError):
            run("aux.app2-flange-integral", dict(LOOSE, Fax=-1.0e6))

    def test_adequate_bolting_and_light_loads_pass(self):
        res = run("aux.app2-flange-integral", dict(LOOSE, y=100, m=0.5, nBolts=16, aRoot=0.8, Sa=40000, Sb=40000,
                                                   Sf=60000, SfAmbient=60000, P=50, t=3,
                                                   Edesign=1.0e8, Eambient=1.1e8))
        self.assertGreaterEqual(res["output"]["Ab"], res["output"]["Am"])
        self.assertEqual(res["status"], "pass")

    def test_inadequate_bolt_area_fails_with_a_warning(self):
        res = run("aux.app2-flange-integral", dict(LOOSE, nBolts=4, aRoot=0.05))
        self.assertEqual(res["status"], "fail")
        self.assertTrue(any("bolting is inadequate" in w for w in res["warnings"]))

    def test_2_5_sn_cap_governs_when_sn_is_low(self):
        case = parity.load("aux.app2-flange-integral")["cases"][0]["input"]
        high = run("aux.app2-flange-integral", case)["output"]["operating"]["allowSH"]
        self.assertEqual(high, min(1.5 * 19600, 2.5 * 17100))
        low = run("aux.app2-flange-integral", dict(case, Sn=10000, SnAmbient=10000))["output"]
        self.assertEqual(low["operating"]["allowSH"], 25000.0)
        self.assertEqual(low["seating"]["allowSH"], 25000.0)

    def test_missing_sn_leaves_the_cap_unchecked_and_says_so(self):
        case = dict(parity.load("aux.app2-flange-integral")["cases"][0]["input"])
        for k in ("Sn", "SnAmbient"):
            case.pop(k)
        res = run("aux.app2-flange-integral", case)
        self.assertEqual(res["output"]["operating"]["allowSH"], 1.5 * 19600)
        self.assertTrue(any("Sn not supplied" in w for w in res["warnings"]))

    def test_engine_errors(self):
        base = parity.load("aux.app2-flange-integral")["cases"][0]["input"]
        for bad in (dict(P=0), dict(G=0), dict(N=0), dict(m=-1), dict(y=-1), dict(Sa=0), dict(Sb=0), dict(Sf=0),
                    dict(nBolts=3), dict(aRoot=0), dict(C=16), dict(G=14), dict(G=21.3), dict(t=0),
                    dict(g0=0), dict(g1=0.2), dict(h=0)):
            with self.assertRaises(ValueError, msg=str(bad)):
                run("aux.app2-flange-integral", dict(base, **bad))

    def test_missing_required_field(self):
        base = dict(LOOSE)
        del base["Sb"]
        with self.assertRaises(ValueError):
            run("aux.app2-flange-integral", base)


class HubFactorOverrides(unittest.TestCase):
    CASE = parity.load("aux.app2-flange-integral")["cases"][0]["input"]

    def _series(self):
        g0, g1, h, B = self.CASE["g0"], self.CASE["g1"], self.CASE["h"], self.CASE["B"]
        return bf.hub_factors(g1 / g0, h / math.sqrt(B * g0))

    def test_overrides_equal_to_the_series_reproduce_the_fixture_output(self):
        s = self._series()
        base = run("aux.app2-flange-integral", self.CASE)
        over = run("aux.app2-flange-integral", dict(self.CASE, F_override=s["F"], V_override=s["V"], f_override=s["f"]))
        self.assertEqual(over["output"], base["output"])
        self.assertEqual(over["status"], base["status"])
        self.assertEqual(parity.run_case(lambda i: run("aux.app2-flange-integral", i),
                                         dict(parity.load("aux.app2-flange-integral")["cases"][0],
                                              input=dict(self.CASE, F_override=s["F"], V_override=s["V"], f_override=s["f"]))), [])

    def test_a_single_override_changes_only_what_it_feeds(self):
        s = self._series()
        base = run("aux.app2-flange-integral", self.CASE)["output"]
        one = run("aux.app2-flange-integral", dict(self.CASE, F_override=s["F"]))["output"]
        self.assertEqual(one, base)
        moved = run("aux.app2-flange-integral", dict(self.CASE, F_override=s["F"] * 1.2))["output"]
        self.assertAlmostEqual(moved["F"], round(s["F"] * 1.2, 4), delta=1e-4)
        self.assertNotEqual(moved["e"], base["e"])
        self.assertEqual(moved["V"], base["V"])

    def test_override_warning_names_the_factors(self):
        res = run("aux.app2-flange-integral", dict(self.CASE, V_override=0.05))
        self.assertTrue(any("override" in w and "V" in w for w in res["warnings"]))
        self.assertEqual(res["output"]["V"], 0.05)

    def test_full_override_does_not_evaluate_the_series(self):
        case = dict(self.CASE, h=20.0, F_override=0.6, V_override=0.04, f_override=1.0)
        res = run("aux.app2-flange-integral", case)
        self.assertEqual(res["output"]["F"], 0.6)
        self.assertEqual(res["output"]["V"], 0.04)

    def test_no_override_means_no_override_warning(self):
        res = run("aux.app2-flange-integral", self.CASE)
        self.assertFalse(any("override" in w for w in res["warnings"]))


class HubFactorMethods(unittest.TestCase):

    def test_straight_hub_series_matches_the_published_limit(self):
        # g1 = g0 and h/h0 = 0.25: the straight-hub values are F = 0.90892, V = 0.55010
        s = bf.hub_factors(1.0, 0.25)
        self.assertAlmostEqual(s["F"], 0.90892, delta=2e-5)
        self.assertAlmostEqual(s["V"], 0.55010, delta=2e-5)
        self.assertEqual(s["f"], 1.0)

    def test_series_guards(self):
        with self.assertRaises(ValueError):
            bf.hub_factors(0.9, 1.0)
        with self.assertRaises(ValueError):
            bf.hub_factors(1.5, 0.0)

    def test_curve_fit_is_not_shipped(self):
        self.assertFalse(hasattr(bf, "hub_factors_4165"))
        self.assertFalse(any(n.startswith("_fit_") for n in dir(bf)))

    def test_curve_fit_option_rejected_with_exit_2(self):
        case = parity.load("aux.app2-flange-integral")["cases"][0]["input"]
        for method in ("fit-4165", "chart"):
            with self.assertRaises(ValueError, msg=method) as cm:
                bf.validate("aux.app2-flange-integral", dict(case, hubFactorMethod=method))
            self.assertIn("not shipped", str(cm.exception))
            self.assertIn("F_override", str(cm.exception))
        r = subprocess.run([sys.executable, TOOL, "aux.app2-flange-integral", "--input",
                            json.dumps(dict(case, hubFactorMethod="fit-4165"))],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("not shipped", r.stderr)

    def test_series_method_named_explicitly_is_accepted(self):
        case = parity.load("aux.app2-flange-integral")["cases"][0]["input"]
        bf.validate("aux.app2-flange-integral", dict(case, hubFactorMethod="series"))


class Validate(unittest.TestCase):

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError) as cm:
            bf.validate("connections.flange-equivalent-pressure", dict(P=1, bad=2))
        self.assertIn("unknown input field", str(cm.exception))
        self.assertIn("valid:", str(cm.exception))

    def test_unknown_module_and_non_object(self):
        with self.assertRaises(ValueError):
            bf.validate("nope", {})
        with self.assertRaises(ValueError):
            bf.validate("aux.app2-flange-integral", [1])

    def test_screen_always_says_it_is_a_screen(self):
        w = bf.validate("connections.flange-equivalent-pressure", dict(P=100, F=0, M_in_lbf=1, G=10, ratedPressure=500))
        self.assertTrue(any("not a stress check" in x for x in w))

    def test_screen_design_pressure_above_rating_warns(self):
        w = bf.validate("connections.flange-equivalent-pressure", dict(P=600, F=0, M_in_lbf=1, G=10, ratedPressure=500))
        self.assertTrue(any("exceeds the supplied rating" in x for x in w))

    def test_screen_negative_pressure_rejected(self):
        with self.assertRaises(ValueError):
            bf.validate("connections.flange-equivalent-pressure", dict(P=-1, F=0, M_in_lbf=1, G=10, ratedPressure=500))

    def test_app2_refuses_silent_modulus_and_ambient_allowable_defaults(self):
        for k in ("Edesign", "Eambient", "SfAmbient"):
            inp = {a: b for a, b in LOOSE.items() if a != k}
            with self.assertRaises(ValueError, msg=k) as cm:
                bf.validate("aux.app2-flange-integral", inp)
            self.assertIn(k, str(cm.exception))

    def test_app2_attachment_and_method_enums(self):
        with self.assertRaises(ValueError):
            bf.validate("aux.app2-flange-integral", dict(LOOSE, attachment="slip-on"))
        with self.assertRaises(ValueError):
            bf.validate("aux.app2-flange-integral", dict(LOOSE, attachment="integral", hubFactorMethod="chart"))

    def test_app2_pressure_only_warns_when_no_loads_given(self):
        w = " ".join(bf.validate("aux.app2-flange-integral", LOOSE))
        self.assertIn("pressure-only", w)
        w2 = " ".join(bf.validate("aux.app2-flange-integral", dict(LOOSE, Fax=0)))
        self.assertNotIn("pressure-only", w2)
        w3 = " ".join(bf.validate("aux.app2-flange-integral", dict(LOOSE, Mext_in_lbf=100)))
        self.assertNotIn("pressure-only", w3)

    def test_screen_clamps_compression_unless_credited(self):
        base = dict(P=100, F=-10000, M_in_lbf=50000, G=10, ratedPressure=500)
        clamped = bf.run_module("connections.flange-equivalent-pressure", dict(base))
        zero = bf.run_module("connections.flange-equivalent-pressure", dict(base, F=0))
        self.assertEqual(clamped["output"], zero["output"])
        self.assertEqual(clamped["output"]["forceTerm"], 0.0)
        self.assertTrue(any("taken as F = 0" in x for x in clamped["warnings"]))
        self.assertEqual(clamped["inputs"]["F"], -10000)                       # the record keeps the user's value
        credited = bf.run_module("connections.flange-equivalent-pressure", dict(base, creditCompression=True))
        self.assertLess(credited["output"]["forceTerm"], 0)
        self.assertLess(credited["output"]["Pe"], clamped["output"]["Pe"])
        self.assertTrue(any("Compressive" in x for x in credited["warnings"]))
        self.assertFalse(any("taken as F = 0" in x for x in credited["warnings"]))
        tens = bf.run_module("connections.flange-equivalent-pressure", dict(base, F=4000))
        self.assertFalse(any("taken as F = 0" in x for x in tens["warnings"]))

    def test_credit_compression_must_be_boolean(self):
        with self.assertRaises(ValueError):
            bf.validate("connections.flange-equivalent-pressure",
                        dict(P=1, F=0, M_in_lbf=1, G=10, ratedPressure=500, creditCompression="yes"))

    def test_negative_zero_is_normalised_in_the_output_layer(self):
        self.assertEqual(repr(bf._clean_zero(-0.0)), "0.0")
        out = bf._clean_zero({"a": -0.0, "b": [-0.0, 1.5], "c": {"d": -0.0}, "e": "x"})
        self.assertEqual(json.dumps(out), '{"a": 0.0, "b": [0.0, 1.5], "c": {"d": 0.0}, "e": "x"}')

    def test_app2_override_rules(self):
        with self.assertRaises(ValueError):
            bf.validate("aux.app2-flange-integral", dict(LOOSE, F_override=0.6))        # loose
        integral = parity.load("aux.app2-flange-integral")["cases"][0]["input"]
        for bad in (dict(F_override=0), dict(V_override=-1), dict(f_override=0.9)):
            with self.assertRaises(ValueError, msg=str(bad)):
                bf.validate("aux.app2-flange-integral", dict(integral, **bad))

    def test_app2_reports_defaults_applied(self):
        w = bf.validate("aux.app2-flange-integral", LOOSE)
        joined = " ".join(w)
        self.assertIn("Defaults applied", joined)
        self.assertIn("rigidityFactor", joined)
        self.assertIn("b (derived from N", joined)

    def test_app2_one_moment_unit_only(self):
        with self.assertRaises(ValueError):
            bf.validate("aux.app2-flange-integral", dict(LOOSE, Mext=1, Mext_in_lbf=12))


class CommandLine(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")

    def test_list(self):
        r = self._run("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        ids = [ln for ln in r.stdout.splitlines() if ln and not ln[0].isspace() and len(ln.split()) == 1]
        self.assertEqual(sorted(ids), sorted(bf.REGISTRY))
        for module in bf.REGISTRY:
            for field in bf.FIELDS[module]:
                self.assertIn(field[0], r.stdout)
        self.assertIn("FT-LBF", r.stdout)
        self.assertIn("IN-LBF", r.stdout)

    def test_screen_through_the_cli_with_the_engine_names(self):
        case = parity.load("connections.flange-equivalent-pressure")["cases"][0]
        r = self._run("connections.flange-equivalent-pressure", "--input", json.dumps(case["input"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(set(env), {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied"})
        self.assertEqual(env["status"], "pass")
        self.assertAlmostEqual(env["output"]["Pe"], 1749.661, delta=1e-3)
        self.assertEqual(env["inputs"], case["input"])
        self.assertEqual(env["user_supplied"], ["ratedPressure"])
        self.assertIn("PNC00004", env["citation"])

    def test_screen_accepts_ft_lbf_and_in_lbf_alike(self):
        a = self._run("connections.flange-equivalent-pressure", "--input",
                      json.dumps(dict(P=500, F=2000, M_ft_lbf=50000 / 12, G=6, ratedPressure=1975)))
        b = self._run("connections.flange-equivalent-pressure", "--input",
                      json.dumps(dict(P=500, F=2000, M_in_lbf=50000, G=6, ratedPressure=1975)))
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(json.loads(a.stdout)["output"], json.loads(b.stdout)["output"])

    def test_screen_both_moments_exits_2(self):
        r = self._run("connections.flange-equivalent-pressure", "--input",
                      json.dumps(dict(P=500, F=2000, M_ft_lbf=1, M_in_lbf=12, G=6, ratedPressure=1975)))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_detailed_fixture_through_the_cli(self):
        case = parity.load("aux.app2-flange-integral")["cases"][0]
        r = self._run("aux.app2-flange-integral", "--input", json.dumps(case["input"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["status"], case["status"])
        for key, want in case["expect"].items():
            if isinstance(want, str):
                self.assertEqual(env["output"][key], want, key)
            else:
                self.assertAlmostEqual(env["output"][key], want, delta=case["tol"], msg=key)
        self.assertIn("m", env["user_supplied"])
        self.assertIn("Sn", env["user_supplied"])
        self.assertNotIn("P", env["user_supplied"])

    def test_loose_fixture_without_moduli_is_refused_by_the_cli(self):
        case = parity.load("aux.app2-flange-integral")["cases"][1]
        r = self._run("aux.app2-flange-integral", "--input", json.dumps(case["input"]))
        self.assertEqual(r.returncode, 2)
        self.assertIn("Edesign", r.stderr)

    def test_shipped_example_runs_and_passes(self):
        r = self._run("aux.app2-flange-integral", "--input-file", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["status"], "pass")
        self.assertGreaterEqual(env["output"]["Ab"], env["output"]["Am"])
        self.assertLessEqual(env["output"]["Joperating"], 1)

    def test_derive_through_the_cli(self):
        r = self._run("connections.flange-derive", "--input",
                      json.dumps(dict(facing="flat", gasket_ID=10, gasket_OD=12)))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["status"], "na")
        self.assertAlmostEqual(env["output"]["G"], 11.292893, delta=1e-6)
        self.assertEqual(env["user_supplied"], ["gasket_ID", "gasket_OD"])

    def test_input_file_with_bom(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.json")
            with open(path, "w", encoding="utf-8-sig") as fh:
                json.dump(dict(facing="ring-joint", gasket_ID=10, gasket_OD=12), fh)
            r = self._run("connections.flange-derive", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["output"]["G"], 11.0)

    def test_exit_2_on_bad_input_with_one_line(self):
        good = dict(P=500, F=2000, M_in_lbf=50000, G=6, ratedPressure=1975)
        cases = [
            ("connections.flange-equivalent-pressure", "--input", "{not json"),
            ("connections.flange-equivalent-pressure", "--input", "[1, 2]"),
            ("connections.flange-equivalent-pressure", "--input", json.dumps({"P": 1})),
            ("connections.flange-equivalent-pressure", "--input", json.dumps(dict(good, G=0))),
            ("connections.flange-equivalent-pressure", "--input", json.dumps(dict(good, bogus=1))),
            ("connections.flange-equivalent-pressure", "--input", json.dumps(dict(good, P="500"))),
            ("connections.flange-equivalent-pressure", "--input", json.dumps(dict(good, P=True))),
            ("connections.flange-equivalent-pressure",),
            ("connections.flange-equivalent-pressure", "--input", "{}", "--input-file", EXAMPLE),
            ("connections.flange-derive", "--input", "{}"),
            ("no.such-module", "--input", "{}"),
            ("aux.app2-flange-integral", "--input-file", os.path.join(ROOT, "tests", "does-not-exist.json")),
        ]
        for args in cases:
            r = self._run(*args)
            self.assertEqual(r.returncode, 2, f"{args}: rc={r.returncode} {r.stderr!r}")
            self.assertTrue(r.stderr.startswith("input error"), f"{args}: {r.stderr!r}")
            self.assertEqual(r.stdout, "", args)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, f"{args}: {r.stderr!r}")


class SkillContent(unittest.TestCase):
    """Guards on the shipped SKILL.md, references and script."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(TOOL, encoding="utf-8") as fh:
            cls.code = fh.read()
        cls.refs = {}
        for path in sorted(glob.glob(os.path.join(SKILL, "references", "*.md"))):
            with open(path, encoding="utf-8") as fh:
                cls.refs[os.path.basename(path)] = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: bolted-flange\ndescription: \""))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description", "compatibility"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 1024)
        for phrase in ("flange", "pressure-equivalent", "equivalent pressure", "Kellogg", "leakage", "nozzle load",
                       "Appendix 2", "4.16", "B16.5", "B31.3", "304.5.1", "flange rating", "gasket", "UG-44"):
            self.assertIn(phrase.lower(), desc.lower(), phrase)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)
        self.assertEqual(content_guard.scan(SKILL), [])

    def test_no_windows_paths_anywhere_under_the_skill(self):
        for path in content_guard.skill_files(SKILL):
            with open(path, encoding="utf-8") as fh:
                self.assertIsNone(re.search(r"[A-Za-z]:\\", fh.read()), path)

    def test_files_are_lf_utf8_without_bom(self):
        for path in content_guard.skill_files(SKILL):
            with open(path, "rb") as fh:
                raw = fh.read()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), path)
            self.assertNotIn(b"\r", raw, path)
            raw.decode("utf-8")

    def test_script_is_ascii_and_parses_as_python_39(self):
        self.assertTrue(all(ord(ch) < 128 for ch in self.code))
        ast.parse(self.code, TOOL, feature_version=(3, 9))
        self.assertIn("from __future__ import annotations", self.code)
        for banned in ("match ", "removeprefix", "slots=True"):
            self.assertNotIn(banned, self.code, banned)

    def test_script_uses_only_the_standard_library(self):
        tree = ast.parse(self.code)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        self.assertLessEqual(mods, {"__future__", "argparse", "json", "math", "sys", "decimal", "typing"})

    def test_script_header_states_the_hub_factor_provenance(self):
        header = " ".join(self.code.split('"""', 2)[1].split())
        self.assertIn("RECONSTRUCTION", header)
        self.assertIn("NOT transcribed from licensed Code text", header)

    def test_304_5_1_b_route_stated_in_the_body(self):
        body = " ".join(self.text.split("---", 2)[2].split())
        self.assertIn("304.5.1(b) permits either VIII-1 Appendix 2 or VIII-2 4.16", body)

    def test_compression_is_tied_to_the_4_16_13_fa_definition(self):
        blob = " ".join((self.text + " ".join(self.refs.values())).split())
        self.assertIn("FA = 0", blob)
        self.assertIn("max(F, 0)", self.refs["rejection-checklist.md"])
        self.assertIn("max(F, 0)", self.refs["app2-engine.md"])

    def test_pressure_design_hand_off_excludes_flange_rating_selection(self):
        self.assertNotIn("Flange rating selection", self.text)

    def test_related_tools_link_carries_utm(self):
        tail = self.text.split("## Related tools", 1)[1]
        self.assertIn("?utm_source=claude-plugin&utm_medium=skill", tail)

    def test_description_has_flange_leakage_and_api_610_phrases(self):
        desc = self.text.split("description:", 1)[1].split(chr(10), 1)[0]
        self.assertLess(len(desc), 1024)
        self.assertIn("flange leakage", desc)
        self.assertIn("API 610", desc)

    def test_curve_fit_is_documented_as_not_shipped(self):
        blob = " ".join((self.text + " ".join(self.refs.values()) + self.code).split())
        self.assertIn("not shipped", blob)
        self.assertNotIn("transcribed visually", blob)
        self.assertNotIn("coefficients are equation constants", blob)
        for phrase in ("image-only", "reading behind this skill", "source behind this skill"):
            self.assertNotIn(phrase, blob)

    def test_flange_derive_results_are_carried_into_the_detailed_module(self):
        self.assertIn("Carry b, G and N", self.text)
        self.assertIn("always for ring joints", self.text)

    def test_b31_1_citation_is_division_1_only(self):
        ladder = " ".join(self.refs["method-ladder.md"].split())
        self.assertIn("Section VIII, Division 1", ladder)
        self.assertIn("unlettered text that continues 104.5.1(a)", ladder)
        self.assertIn("104.5.1(c) | Bolting per 108.5", ladder)
        self.assertIn("Table A-10", ladder)

    def test_engine_default_moduli_are_labelled_parity_only(self):
        self.assertIn("PARITY ONLY", self.code)
        self.assertIn("ENGINE_DEFAULT_E_DESIGN", self.refs["tool-reference.md"])

    def test_hand_offs_name_only_pack_skills(self):
        self.assertIn("`pressure-design`", self.text)
        self.assertIn("`stress-screening`", self.text)
        self.assertIn("`nozzle-load`", self.text)
        self.assertIn("if it is installed", self.text)

    def test_required_sections_present(self):
        low = self.text.lower()
        for heading in ("## scope", "## step 0", "## running the tool", "## output format", "rejection checklist",
                        "## copyright boundary", "## hand-offs", "## related tools", "engineer of record verifies"):
            self.assertIn(heading, low, heading)
        for step in ("Step 1", "Step 2", "Step 3", "Step 4"):
            self.assertIn(step, self.text, step)
        self.assertIn("# Bolted Flange Evaluation", self.text)
        self.assertIn("ASSUMED", self.text)

    def test_every_registered_module_is_documented(self):
        for module in bf.REGISTRY:
            self.assertIn(f"`{module}`", self.text, module)

    def test_run_rules_stated(self):
        self.assertIn("run `list` first".lower(), self.text.lower())
        self.assertIn("every number you state comes from a script run", self.text.lower())
        self.assertIn("do not change into the skill folder", self.text.lower())
        self.assertIn("job.json", self.text)

    def test_ladder_order_screen_before_detailed(self):
        self.assertLess(self.text.index("Step 2"), self.text.index("Step 3"))
        self.assertIn("connections.flange-equivalent-pressure", self.text.split("Step 3", 1)[0])
        self.assertIn("a screen failure is not a joint failure", self.text.lower())

    def test_clause_path_is_stated(self):
        blob = self.text + " ".join(self.refs.values())
        for needle in ("4.16", "304.5.1(b)", "UG-44(b)", "NC-3658", "F312.1", "PCC-1", "PNC00004", "2.5.2",
                       "EN 1591-1"):
            self.assertIn(needle, blob, needle)

    def test_references_exist_and_are_linked(self):
        expected = {"method-ladder.md", "app2-engine.md", "inputs-from-tables.md", "tool-reference.md",
                    "rejection-checklist.md"}
        self.assertEqual(set(self.refs), expected)
        for name in expected:
            self.assertIn(f"references/{name}", self.text, name)

    def test_rejection_checklist_has_at_least_fourteen_items(self):
        items = re.findall(r"^\d+\. ", self.refs["rejection-checklist.md"], flags=re.M)
        self.assertGreaterEqual(len(items), 14)

    def test_body_word_budget(self):
        self.assertLess(len(self.text.split()), 3000)

    def test_hub_factor_limitation_documented(self):
        eng = self.refs["app2-engine.md"]
        self.assertIn("reconstruction", eng.lower())
        self.assertIn("F_override", eng)
        self.assertIn("not transcribed", eng.lower())

    def test_no_tabulated_values_or_material_stress_pairs(self):
        # A material designation and a stress figure on the same line is the failure mode.
        material = re.compile(r"\b(A\d{3}\b|SA-\d+|B7\b|L7\b|API ?5L|X\d{2}\b|Gr(ade)?\.? ?[A-Z0-9]+\b.*\d)", re.I)
        stress = re.compile(r"\b\d[\d,\.]*\s*(psi|ksi)\b", re.I)
        sources = [("SKILL.md", self.text)] + list(self.refs.items()) + [("bolted_flange.py", self.code)]
        for label, text in sources:
            for ln in text.splitlines():
                self.assertFalse(material.search(ln) and stress.search(ln), f"{label}: {ln.strip()}")

    def test_no_rating_class_dimension_or_gasket_factor_rows(self):
        # No B16.5 rating row (class / pressure pairs), gasket m/y table row, or flange dimension table.
        pattern = re.compile(r"(class\s*(150|300|600|900|1500|2500)[^.\n]*\b\d{3,4}\s*psi)", re.I)
        for label, text in [("SKILL.md", self.text)] + list(self.refs.items()):
            self.assertIsNone(pattern.search(text), label)
        for label, text in [("SKILL.md", self.text)] + list(self.refs.items()):
            for ln in text.splitlines():
                if ln.lstrip().startswith("|") and re.search(r"\|\s*\d+(\.\d+)?\s*\|\s*\d+(\.\d+)?\s*\|\s*\d+(\.\d+)?\s*\|", ln):
                    self.assertTrue(False, f"{label}: numeric table row {ln.strip()}")

    def test_example_inputs_are_declared_fields(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            ex = json.load(fh)
        declared = {f[0] for f in bf.FIELDS["aux.app2-flange-integral"]}
        self.assertTrue(set(ex) <= declared)


if __name__ == "__main__":
    unittest.main()
