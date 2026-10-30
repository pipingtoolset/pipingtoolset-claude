"""Regression tests for the pressure-design skill and its calculators.

Standard library only (unittest), so the gate runs anywhere Python 3.9+ runs:

    python -m unittest discover -s tests -v

Three layers:
  1. Parity - every module reproduces the vendored calc-core fixtures exactly.
  2. Hand-derived cases - worked on paper from the published equations, using clearly
     fictitious round inputs (these are NOT material allowables), so the script is
     checked against arithmetic that did not come from the engine.
  3. CLI and SKILL.md guards.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import unittest
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pressure-design")
SCRIPTS = os.path.join(SKILL, "scripts")
CLI = os.path.join(SCRIPTS, "pressure_design.py")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import content_guard  # noqa: E402
import parity  # noqa: E402
import pressure_design as pd  # noqa: E402

TOL = 1e-4


def run(module: str, inputs: dict) -> dict:
    return pd.REGISTRY[module](dict(inputs))


def with_basis(module: str, inputs: dict) -> dict:
    """A run_module / CLI job: a module whose equation carries W also gets a W_basis (0.7.2 W gate).
    The engine functions (run above) never see it."""
    return dict(inputs, W_basis="seamless") if module in pd.W_MODULES else dict(inputs)


class Parity(unittest.TestCase):
    """One method per module so a failure names the module."""

    def _check(self, module: str) -> None:
        self.assertIn(module, pd.REGISTRY)
        self.assertEqual(parity.run_fixture(pd.REGISTRY, module), [])

    def test_manifest_modules_are_exactly_the_registry(self):
        self.assertEqual(sorted(pd.REGISTRY), parity.modules_for("pressure-design"))

    def test_b313_wall_thickness(self):
        self._check("piping.b313-wall-thickness")

    def test_b311_wall_thickness(self):
        self._check("piping.b311-wall-thickness")

    def test_b31_allowable_pressure(self):
        self._check("piping.b31-allowable-pressure")

    def test_branch_reinforcement(self):
        self._check("piping.branch-reinforcement")

    def test_bend_thickness(self):
        self._check("piping.bend-thickness")

    def test_miter_allowable_pressure(self):
        self._check("piping.miter-allowable-pressure")

    def test_leak_test_pressure(self):
        self._check("piping.leak-test-pressure")


class Metadata(unittest.TestCase):

    def test_every_module_has_citation_and_field_table(self):
        for module in pd.REGISTRY:
            self.assertTrue(pd.CITATIONS.get(module), module)
            self.assertIn(module, pd.FIELDS)
            self.assertTrue(pd.user_supplied_names(module) or module == "piping.branch-reinforcement", module)

    def test_result_envelope_shape(self):
        for module in pd.REGISTRY:
            fx = parity.load(module)
            res = run(module, fx["cases"][0]["input"])
            self.assertEqual(set(res), {"module", "output", "status", "warnings"})
            self.assertEqual(res["module"], module)
            self.assertIn(res["status"], {"pass", "fail", "na"})
            self.assertIsInstance(res["warnings"], list)

    def test_round_half_up(self):
        self.assertEqual(pd.round_half_up(1.005, 2), 1.01)      # binary float would give 1.0
        self.assertEqual(pd.round_half_up(2.5, 0), 3.0)
        self.assertEqual(pd.round_half_up(-2.5, 0), -3.0)       # away from zero, not banker's
        self.assertTrue(math.isinf(pd.round_half_up(math.inf, 3)))


class HandDerived(unittest.TestCase):
    """Cases worked by hand. Inputs are fictitious round numbers - never allowables for
    a named material. Fractions are used so the reference value carries no rounding."""

    # --- B31.3 wall thickness, Eq. (3a) -------------------------------------------------
    # P=1000, D=10, S=24800, E=1, W=1, Y=0.4, c=0.1, mill tolerance 0.125
    #   S*E*W + P*Y = 24800 + 400 = 25200 ;  denominator 2*25200 = 50400
    #   t      = P*D/denom = 10000/50400 = 25/126            = 0.198413
    #   tm     = t + c = 25/126 + 1/10 = (125 + 63)/630 = 94/315 = 0.298413
    #   tOrder = tm/(1 - 0.125) = (94/315)*(8/7) = 752/2205  = 0.341043
    B313 = dict(P=1000, D=10, S=24800, E=1, W=1, Y=0.4, c=0.1, millTolerance=0.125)

    def test_b313_hand_case(self):
        out = run("piping.b313-wall-thickness", self.B313)["output"]
        self.assertAlmostEqual(out["t"], float(Fraction(25, 126)), delta=TOL)
        self.assertAlmostEqual(out["tm"], float(Fraction(94, 315)), delta=TOL)
        self.assertAlmostEqual(out["tOrder"], float(Fraction(752, 2205)), delta=TOL)

    # --- B31.1 wall thickness with W < 1 ------------------------------------------------
    # P=800, D=6, S=20000, E=0.8, W=0.5, y=0.4, A=0.05, mill tolerance 0.125
    #   S*E*W = 20000*0.8*0.5 = 8000 ; P*y = 320 ; sum 8320 ; denominator 16640
    #   t      = 800*6/16640 = 4800/16640 = 15/52              = 0.288462
    #   tm     = 15/52 + 1/20 = (75 + 13)/260 = 22/65          = 0.338462
    #   tOrder = (22/65)*(8/7) = 176/455                       = 0.386813
    # Halving W raises t: the same job with W = 1 must be thinner.
    def test_b311_hand_case_with_weld_factor(self):
        inp = dict(P=800, D=6, S=20000, E=0.8, W=0.5, y=0.4, A=0.05, millTolerance=0.125)
        out = run("piping.b311-wall-thickness", inp)["output"]
        self.assertAlmostEqual(out["t"], float(Fraction(15, 52)), delta=TOL)
        self.assertAlmostEqual(out["tm"], float(Fraction(22, 65)), delta=TOL)
        self.assertAlmostEqual(out["tOrder"], float(Fraction(176, 455)), delta=TOL)
        thinner = run("piping.b311-wall-thickness", dict(inp, W=1.0))["output"]["t"]
        self.assertLess(thinner, out["t"])

    def test_b311_omitted_w_equals_one(self):
        inp = dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125)
        self.assertEqual(run("piping.b311-wall-thickness", inp)["output"],
                         run("piping.b311-wall-thickness", dict(inp, W=1.0))["output"])

    # --- Allowable pressure is the inverse of the thickness equation --------------------
    # Take the B313 job above (Y = y = 0.4, c = A = 0.1) and order tOrder = 752/2205 in.
    #   tp = tOrder*(1 - 0.125) - A = 94/315 - 1/10 = 25/126
    #   P  = 2*S*E*tp/(D - 2*y*tp) = 2*24800*(25/126) / (10 - 0.8*25/126)
    #      = (1240000/126) / (1240/126) = 1000 psi        - the design pressure we started from
    def test_allowable_pressure_round_trip(self):
        inp = dict(D=10, t=752 / 2205, millTolerance=0.125, A=0.1, S=24800, E=1, y=0.4, Mf=1)
        out = run("piping.b31-allowable-pressure", inp)["output"]
        self.assertAlmostEqual(out["tp"], float(Fraction(25, 126)), delta=TOL)
        self.assertAlmostEqual(out["allowablePressure"], 1000.0, delta=TOL)

    def test_allowable_pressure_no_thickness_left_fails(self):
        res = run("piping.b31-allowable-pressure",
                  dict(D=10, t=0.2, millTolerance=0.125, A=0.2, S=20000, E=1, y=0.4, Mf=1))
        self.assertEqual((res["status"], res["output"]["allowablePressure"]), ("fail", 0))

    # --- Branch reinforcement, 90 degrees, with a pad ----------------------------------
    # Dh=10, Th=0.5, th=0.2, Db=4, Tb=0.25, tb=0.1, c=0.05, beta=90, Tr=0.25, Dp=7, A4welds=0.04
    #   sin(beta) = 1 ; Tb-c = 0.20 ; Th-c = 0.45
    #   d1 = 4 - 2*0.20 = 3.6
    #   d2 = max(3.6, 0.20 + 0.45 + 3.6/2 = 2.45) = 3.6
    #   L4 = min(2.5*0.45 = 1.125, 2.5*0.20 + 0.25 = 0.75) = 0.75
    #   A1 = th*d1*(2 - 1)          = 0.2*3.6                = 0.72
    #   A2 = (2*3.6 - 3.6)*(0.5 - 0.2 - 0.05) = 3.6*0.25     = 0.90
    #   A3 = 2*0.75*(0.25 - 0.1 - 0.05)/1     = 1.5*0.10     = 0.15
    #   pad inside zone: min(Dp=7, 2*d2=7.2) - Db/sin = 7 - 4 = 3 ; pad area 0.25*3 = 0.75
    #   A4 = 0.75 + 0.04 = 0.79
    #   margin = 0.90 + 0.15 + 0.79 - 0.72 = 1.12  -> pass
    def test_branch_90_degree_with_pad(self):
        inp = dict(Dh=10, Th=0.5, th=0.2, Db=4, Tb=0.25, tb=0.1, c=0.05,
                   betaDeg=90, Tr=0.25, Dp=7, A4welds=0.04)
        res = run("piping.branch-reinforcement", inp)
        o = res["output"]
        for key, want in dict(d1=3.6, d2=3.6, L4=0.75, A1=0.72, A2=0.9, A3=0.15, A4=0.79, margin=1.12).items():
            self.assertAlmostEqual(o[key], want, delta=TOL, msg=key)
        self.assertEqual(res["status"], "pass")
        self.assertEqual(res["warnings"], [])

    # --- Branch reinforcement, 45 degrees, no pad --------------------------------------
    # Dh=12, Th=0.4, th=0.15, Db=6, Tb=0.3, tb=0.1, c=0, beta=45, Tr=0, Dp=0, A4welds=0
    #   sin 45 = sqrt(2)/2
    #   d1 = (6 - 0.6)/(sqrt2/2) = 5.4*sqrt2 = 7.63675 ; d2 = max(d1, 0.3+0.4+d1/2 = 4.52) = d1
    #   L4 = min(2.5*0.4 = 1.0, 2.5*0.3 = 0.75) = 0.75
    #   A1 = 0.15*d1*(2 - sqrt2/2) = 0.81*sqrt2*(2 - sqrt2/2) = 1.62*sqrt2 - 0.81
    #   A2 = (2*d2 - d1)*(0.4 - 0.15) = d1*0.25 = 1.35*sqrt2
    #   A3 = 2*0.75*(0.3 - 0.1)/(sqrt2/2) = 0.6/sqrt2 = 0.3*sqrt2
    #   margin = A2 + A3 - A1 = (1.35 + 0.3 - 1.62)*sqrt2 + 0.81 = 0.03*sqrt2 + 0.81 = 0.85243
    #   2*d2 = 15.27 > Dh = 12 -> the zone-wider-than-header warning must appear.
    def test_branch_45_degree_no_pad(self):
        r2 = math.sqrt(2)
        inp = dict(Dh=12, Th=0.4, th=0.15, Db=6, Tb=0.3, tb=0.1, c=0,
                   betaDeg=45, Tr=0, Dp=0, A4welds=0)
        res = run("piping.branch-reinforcement", inp)
        o = res["output"]
        self.assertAlmostEqual(o["d1"], 5.4 * r2, delta=TOL)
        self.assertAlmostEqual(o["A1"], 1.62 * r2 - 0.81, delta=TOL)
        self.assertAlmostEqual(o["A2"], 1.35 * r2, delta=TOL)
        self.assertAlmostEqual(o["A3"], 0.3 * r2, delta=TOL)
        self.assertAlmostEqual(o["margin"], 0.03 * r2 + 0.81, delta=TOL)
        self.assertTrue(any("exceeds header OD" in w for w in res["warnings"]))

    def test_branch_shortfall_fails(self):
        # Same as the 90-degree case but a thin header: A2 collapses and the status flips.
        inp = dict(Dh=10, Th=0.25, th=0.2, Db=4, Tb=0.25, tb=0.1, c=0.05,
                   betaDeg=90, Tr=0, Dp=0, A4welds=0)
        res = run("piping.branch-reinforcement", inp)
        self.assertEqual(res["status"], "fail")
        self.assertLess(res["output"]["margin"], 0)

    # --- Bend I-factors, R/D = 3 --------------------------------------------------------
    # P=1000, D=10, R=30, S=20000, E=1, W=1, y=0.4, A=0
    #   I_in = (12 - 1)/(12 - 2) = 11/10 ; I_ex = (12 + 1)/(12 + 2) = 13/14
    #   tm(I) = P*D/(2*(S*E*W/I + P*y))
    #   intrados:  S/I = 200000/11 ; + 400 = 204400/11 ; *2 = 408800/11
    #              tm = 10000*11/408800 = 275/1022 = 0.269080
    #   extrados:  S/I = 280000/13 ; + 400 = 285200/13 ; *2 = 570400/13
    #              tm = 10000*13/570400 = 325/1426 = 0.227910
    #   centerline (I = 1): 10000/(2*20400) = 25/102 = 0.245098
    def test_bend_hand_case(self):
        out = run("piping.bend-thickness", dict(P=1000, D=10, R=30, S=20000, E=1, W=1, y=0.4, A=0))["output"]
        self.assertAlmostEqual(out["Iintrados"], 1.1, delta=TOL)
        self.assertAlmostEqual(out["Iextrados"], 13 / 14, delta=TOL)
        self.assertAlmostEqual(out["tmIntrados"], float(Fraction(275, 1022)), delta=TOL)
        self.assertAlmostEqual(out["tmExtrados"], float(Fraction(325, 1426)), delta=TOL)
        self.assertAlmostEqual(out["tmCenterline"], float(Fraction(25, 102)), delta=TOL)
        self.assertGreater(out["tmIntrados"], out["tmCenterline"])
        self.assertLess(out["tmExtrados"], out["tmCenterline"])

    # --- Mitered bends ------------------------------------------------------------------
    # S=18000, E=1, W=1, Tc=0.2, r2=5, R1=15 ; r2*Tc = 1 so sqrt(r2*Tc) = 1
    #   base = S*E*W*Tc/r2 = 18000*0.2/5 = 720
    # Three miters, theta = 15 deg, tan 15 = 2 - sqrt3 = 0.267949:
    #   Pm1 = 720 * 0.2/(0.2 + 0.643*0.267949) = 720 * 0.2/0.372291 = 386.78    (Eq. 4a)
    #   Pm2 = 720 * (15 - 5)/(15 - 2.5)        = 720 * 0.8          = 576       (Eq. 4b)
    #   allowable = min = Pm1, governing "Eq. 4a"
    # Single miter, theta = 30 deg, tan 30 = 1/sqrt3 = 0.577350:
    #   Pm = 720 * 0.2/(0.2 + 1.25*0.577350) = 720 * 0.2/0.921688           (Eq. 4c)
    def test_miter_multiple_and_single(self):
        base = dict(S=18000, E=1, W=1, Tc=0.2, r2=5, R1=15)
        multi = run("piping.miter-allowable-pressure", dict(base, thetaDeg=15, miters=3))["output"]
        pm1 = 720 * 0.2 / (0.2 + 0.643 * (2 - math.sqrt(3)))
        self.assertAlmostEqual(multi["Pm1"], pm1, delta=1e-3)
        self.assertAlmostEqual(multi["Pm2"], 576.0, delta=1e-3)
        self.assertAlmostEqual(multi["allowablePressure"], pm1, delta=1e-3)
        self.assertEqual(multi["governing"], "Eq. 4a")

        single = run("piping.miter-allowable-pressure", dict(base, thetaDeg=30, miters=1))["output"]
        pm = 720 * 0.2 / (0.2 + 1.25 * (1 / math.sqrt(3)))
        self.assertAlmostEqual(single["allowablePressure"], pm, delta=1e-3)
        self.assertEqual(single["governing"], "Eq. 4c (single miter)")
        self.assertEqual(single["Pm2"], 0)

    def test_miter_bend_radius_form_can_govern(self):
        # A tight R1 (R1 - r2 small) drives Eq. 4b below Eq. 4a: R1 = 6 -> 720*(1/3.5) = 205.71.
        out = run("piping.miter-allowable-pressure",
                  dict(S=18000, E=1, Tc=0.2, r2=5, R1=6, thetaDeg=15, miters=3))["output"]
        self.assertAlmostEqual(out["Pm2"], 720 * (6 - 5) / (6 - 2.5), delta=1e-3)
        self.assertEqual(out["governing"], "Eq. 4b")

    # --- Leak test ----------------------------------------------------------------------
    # P=450, ST=24000, S=16000, hydro factor 1.5, pneumatic factor 1.1
    #   ST/S = 1.5 ; hydro = 1.5*450*1.5 = 1012.5 ; pneumatic = 1.1*450 = 495
    # With an owner cap of 1.25 on ST/S:
    #   ratio = 1.25 ; hydro = 1.5*450*1.25 = 843.75 ; the warning must quote the
    #   uncapped code minimum (ratio 1.5, hydro 1012.5 psi).
    def test_leak_test_hand_case(self):
        inp = dict(P=450, ST=24000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1)
        res = run("piping.leak-test-pressure", inp)
        self.assertAlmostEqual(res["output"]["stressRatio"], 1.5, delta=TOL)
        self.assertAlmostEqual(res["output"]["hydroTest"], 1012.5, delta=TOL)
        self.assertAlmostEqual(res["output"]["pneumaticTest"], 495.0, delta=TOL)
        self.assertEqual(len(res["warnings"]), 1)

    def test_leak_test_owner_cap_reports_uncapped_minimum(self):
        inp = dict(P=450, ST=24000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1, stressRatioCap=1.25)
        res = run("piping.leak-test-pressure", inp)
        self.assertAlmostEqual(res["output"]["stressRatio"], 1.25, delta=TOL)
        self.assertAlmostEqual(res["output"]["hydroTest"], 843.75, delta=TOL)
        cap_warning = [w for w in res["warnings"] if w.startswith("Cap engaged")]
        self.assertEqual(len(cap_warning), 1)
        self.assertIn("ratio 1.5, hydro 1012.5 psi", cap_warning[0])

    def test_leak_test_no_cap_means_no_ceiling(self):
        res = run("piping.leak-test-pressure",
                  dict(P=100, ST=50000, S=1000, hydroFactor=1.5, pneumaticFactor=1.1))
        self.assertAlmostEqual(res["output"]["stressRatio"], 50.0, delta=TOL)

    def test_leak_test_pneumatic_bound_warning(self):
        res = run("piping.leak-test-pressure",
                  dict(P=100, ST=20000, S=20000, hydroFactor=1.5, pneumaticFactor=1.5, pneumaticMaxFactor=1.33))
        self.assertTrue(any("exceeds the code upper bound 1.33" in w for w in res["warnings"]))


class EngineErrors(unittest.TestCase):
    """Thrown-error conditions and messages match the calc-core engine."""

    def _raises(self, module: str, inputs: dict, message: str) -> None:
        with self.assertRaises(ValueError) as cm:
            run(module, inputs)
        self.assertEqual(str(cm.exception), message)

    def test_b313(self):
        self._raises("piping.b313-wall-thickness", dict(HandDerived.B313, D=0), "D must be > 0")
        self._raises("piping.b313-wall-thickness", dict(HandDerived.B313, W=0), "S, E, W must be > 0")
        self._raises("piping.b313-wall-thickness", dict(HandDerived.B313, millTolerance=1),
                     "millTolerance must be in [0, 1)")

    def test_b311(self):
        base = dict(P=100, D=6, S=20000, E=1, y=0.4, A=0, millTolerance=0.1)
        self._raises("piping.b311-wall-thickness", dict(base, W=1.2), "W must be in (0, 1]")
        self._raises("piping.b311-wall-thickness", dict(base, E=0), "S and E must be > 0")

    def test_other_modules(self):
        self._raises("piping.bend-thickness", dict(P=1, D=10, R=5, S=1, E=1, y=0.4, A=0),
                     "R must exceed D/2 (bend radius to centerline)")
        self._raises("piping.miter-allowable-pressure",
                     dict(S=1, E=1, Tc=0.2, r2=5, R1=2, thetaDeg=15, miters=3),
                     "R1 must exceed r2/2 for the multi-miter form")
        self._raises("piping.miter-allowable-pressure",
                     dict(S=1, E=1, Tc=0.2, r2=5, R1=9, thetaDeg=90, miters=1),
                     "thetaDeg must be in (0, 90)")
        self._raises("piping.branch-reinforcement",
                     dict(Dh=4, Th=0.5, th=0.1, Db=6, Tb=0.3, tb=0.1, c=0, betaDeg=90, Tr=0, Dp=0, A4welds=0),
                     "require 0 < Db <= Dh")
        self._raises("piping.branch-reinforcement",
                     dict(Dh=10, Th=0.5, th=0.1, Db=4, Tb=0.3, tb=0.1, c=0, betaDeg=30, Tr=0, Dp=0, A4welds=0),
                     "betaDeg must be 45\u201390 (code area method range)")
        self._raises("piping.leak-test-pressure",
                     dict(P=0, ST=1, S=1, hydroFactor=1.5, pneumaticFactor=1.1), "P must be > 0")

    def test_missing_and_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, "missing required input 'Y'"):
            run("piping.b313-wall-thickness", {k: v for k, v in HandDerived.B313.items() if k != "Y"})
        with self.assertRaisesRegex(ValueError, "unknown input field"):
            run("piping.b313-wall-thickness", dict(HandDerived.B313, y=0.4))   # B31.1 spelling
        with self.assertRaisesRegex(ValueError, "must be a number"):
            run("piping.b313-wall-thickness", dict(HandDerived.B313, S="24800"))


class Validate(unittest.TestCase):
    """Pre-flight layer: impossible inputs raise, implausible ones warn. The engine is not touched."""

    B311 = dict(P=100, D=6, S=20000, E=1, y=0.4, A=0.05, millTolerance=0.125)
    ALLOW = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1)
    BRANCH = dict(Dh=10, Th=0.5, th=0.2, Db=4, Tb=0.25, tb=0.1, c=0.05, betaDeg=90, Tr=0, Dp=0, A4welds=0)
    MITER = dict(S=18000, E=1, W=1, Tc=0.2, r2=5, R1=15, thetaDeg=15, miters=3)
    BEND = dict(P=1000, D=10, R=30, S=20000, E=1, W=1, y=0.4, A=0)
    LEAK = dict(P=450, ST=24000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1)

    def _bad(self, module, inputs, fragment):
        with self.assertRaises(ValueError, msg=fragment) as cm:
            pd.validate(module, inputs)
        self.assertIn(fragment, str(cm.exception))

    def test_valid_inputs_pass_without_warnings(self):
        self.assertEqual(pd.validate("piping.b313-wall-thickness", HandDerived.B313), [])
        self.assertEqual(pd.validate("piping.b311-wall-thickness", self.B311), [])
        self.assertEqual(pd.validate("piping.b31-allowable-pressure", self.ALLOW), [])
        self.assertEqual(pd.validate("piping.branch-reinforcement", self.BRANCH), [])
        self.assertEqual(pd.validate("piping.bend-thickness", self.BEND), [])
        self.assertEqual(pd.validate("piping.miter-allowable-pressure", self.MITER), [])
        self.assertEqual(pd.validate("piping.leak-test-pressure", self.LEAK), [])

    def test_zero_pressure_is_allowed(self):
        self.assertEqual(pd.validate("piping.b313-wall-thickness", dict(HandDerived.B313, P=0)), [])

    def test_negative_pressure(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, P=-1), "P must be >= 0")

    def test_negative_pressure_bend(self):
        self._bad("piping.bend-thickness", dict(self.BEND, P=-5), "P must be >= 0")

    def test_negative_corrosion_allowance_c(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, c=-0.1), "c must be >= 0")

    def test_negative_allowance_A(self):
        self._bad("piping.b311-wall-thickness", dict(self.B311, A=-0.1), "A must be >= 0")

    def test_quality_factor_above_one(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, E=1.2), "E must be <= 1")

    def test_weld_factor_above_one(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, W=1.1), "W must be <= 1")

    def test_quality_factor_not_positive(self):
        self._bad("piping.b311-wall-thickness", dict(self.B311, E=0), "E must be > 0")

    def test_negative_coefficient_Y(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, Y=-0.1), "Y must be in [0, 1)")

    def test_coefficient_y_one_or_more(self):
        self._bad("piping.b311-wall-thickness", dict(self.B311, y=1.0), "y must be in [0, 1)")

    def test_allowable_pressure_wall_at_or_above_half_od(self):
        self._bad("piping.b31-allowable-pressure", dict(self.ALLOW, t=5.0), "t must be less than D/2")

    def test_allowable_pressure_allowance_at_or_above_wall(self):
        self._bad("piping.b31-allowable-pressure", dict(self.ALLOW, A=0.5), "A must be less than the nominal wall")

    def test_b313_allowance_at_or_above_half_od(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, c=5.0), "allowance c must be less than D/2")

    def test_b311_required_thickness_at_or_above_half_od(self):
        self._bad("piping.b311-wall-thickness", dict(self.B311, P=1e6), "is not less than D/2")

    def test_branch_header_wall_vs_half_od(self):
        self._bad("piping.branch-reinforcement", dict(self.BRANCH, Th=5.0), "Th must be less than Dh/2")

    def test_branch_branch_wall_vs_half_od(self):
        self._bad("piping.branch-reinforcement", dict(self.BRANCH, Tb=2.0), "Tb must be less than Db/2")

    def test_branch_allowance_vs_walls(self):
        self._bad("piping.branch-reinforcement", dict(self.BRANCH, c=0.3), "c must be less than both Th and Tb")

    def test_miter_R1_must_exceed_r2(self):
        self._bad("piping.miter-allowable-pressure", dict(self.MITER, R1=5), "R1 must exceed r2")

    def test_miter_R1_below_r2_for_single_miter(self):
        self._bad("piping.miter-allowable-pressure", dict(self.MITER, R1=4, miters=1), "R1 must exceed r2")

    def test_leak_test_stress_ratio_warning(self):
        w = pd.validate("piping.leak-test-pressure", dict(self.LEAK, ST=40000))
        self.assertTrue(any("check S_T/S" in x for x in w))

    def test_leak_test_pneumatic_factor_warning(self):
        w = pd.validate("piping.leak-test-pressure", dict(self.LEAK, pneumaticFactor=1.5))
        self.assertTrue(any("above 1.33" in x for x in w))

    def test_negative_leak_test_pressure(self):
        self._bad("piping.leak-test-pressure", dict(self.LEAK, P=-1), "P must be >= 0")

    def test_unknown_field_still_rejected(self):
        self._bad("piping.b313-wall-thickness", dict(HandDerived.B313, bogus=1), "unknown input field")


class CommandLine(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8")

    def test_list_text(self):
        r = self._run("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        for module in pd.REGISTRY:
            self.assertIn(module, r.stdout)
        self.assertIn("[S]", r.stdout)
        self.assertIn("psi", r.stdout)

    def test_list_json_flags_user_supplied(self):
        r = self._run("list", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(set(data), set(pd.REGISTRY))
        b313 = {f["name"]: f for f in data["piping.b313-wall-thickness"]["fields"]}
        for name in ("S", "E", "W", "Y"):
            self.assertTrue(b313[name]["user_supplied"], name)
        for name in ("P", "D", "c", "millTolerance"):
            self.assertFalse(b313[name]["user_supplied"], name)
        self.assertEqual(b313["S"]["units"], "psi")

    def test_run_fixture_input(self):
        case = parity.load("piping.b313-wall-thickness")["cases"][0]
        job = with_basis("piping.b313-wall-thickness", case["input"])
        r = self._run("piping.b313-wall-thickness", "--input", json.dumps(job))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["module"], "piping.b313-wall-thickness")
        self.assertEqual(env["status"], "na")
        for key, want in case["expect"].items():
            self.assertAlmostEqual(env["output"][key], want, delta=case["tol"], msg=key)
        self.assertEqual(env["citation"], pd.CITATIONS["piping.b313-wall-thickness"])
        self.assertEqual(env["inputs"], job)
        self.assertEqual(env["user_supplied"], ["S", "E", "W", "Y"])
        self.assertIn("warnings", env)
        self.assertEqual(env["result_grade"], "calculated")

    def test_short_module_name_and_input_file(self):
        path = os.path.join(ROOT, "tests", "_pressure_design_cli_input.json")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(with_basis("piping.b313-wall-thickness", HandDerived.B313), fh)
            r = self._run("b313-wall-thickness", "--input-file", path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(json.loads(r.stdout)["output"]["tOrder"], 752 / 2205, delta=TOL)

    def test_omitted_w_is_never_a_silent_default(self):
        inp = dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125)
        r = self._run("piping.b311-wall-thickness", "--input", json.dumps(inp))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("Table 102.4.7-1", r.stderr)
        r = self._run("piping.b311-wall-thickness", "--input", json.dumps(dict(inp, W_basis="seamless")))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["defaults_applied"], {})
        self.assertEqual((env["weld_factor_basis"]["W"], env["weld_factor_basis"]["basis"]), (1.0, "seamless"))

    def test_single_miter_reports_pm2_as_null(self):
        inp = dict(S=18000, E=1, W=1, W_basis="seamless", Tc=0.2, r2=5, R1=15, thetaDeg=30, miters=1)
        r = self._run("piping.miter-allowable-pressure", "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(json.loads(r.stdout)["output"]["Pm2"])

    def test_multi_miter_keeps_numeric_pm2(self):
        inp = dict(S=18000, E=1, W=1, W_basis="seamless", Tc=0.2, r2=5, R1=15, thetaDeg=15, miters=3)
        r = self._run("piping.miter-allowable-pressure", "--input", json.dumps(inp))
        self.assertAlmostEqual(json.loads(r.stdout)["output"]["Pm2"], 576.0, delta=1e-3)

    def test_validation_warnings_reach_the_envelope(self):
        inp = dict(P=450, ST=40000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1)
        r = self._run("piping.leak-test-pressure", "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any("check S_T/S" in w for w in json.loads(r.stdout)["warnings"]))

    def test_physically_impossible_input_exits_2(self):
        r = self._run("piping.b313-wall-thickness", "--input", json.dumps(dict(HandDerived.B313, E=1.5)))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_bad_input_exits_2_with_one_line(self):
        bad = [
            ("piping.b313-wall-thickness", "--input", "{not json"),
            ("piping.b313-wall-thickness", "--input", "[1, 2]"),
            ("piping.b313-wall-thickness", "--input", json.dumps(dict(HandDerived.B313, D=0))),
            ("piping.b313-wall-thickness", "--input", json.dumps({"P": 1})),
            ("piping.b313-wall-thickness",),
            ("piping.no-such-module", "--input", "{}"),
            ("piping.b313-wall-thickness", "--input-file", os.path.join(ROOT, "tests", "does-not-exist.json")),
        ]
        for args in bad:
            r = self._run(*args)
            self.assertEqual(r.returncode, 2, f"{args}: {r.stdout!r} {r.stderr!r}")
            self.assertEqual(r.stdout, "", args)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, f"{args}: {r.stderr!r}")


class SkillContent(unittest.TestCase):
    """Guards on the shipped SKILL.md and script: frontmatter limits and the product rules."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(CLI, encoding="utf-8") as fh:
            cls.script = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: pressure-design\ndescription: "))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description", "compatibility"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 400)  # short slash-menu blurb
        for term in ("wall thickness", "304.1.2", "104.1.2", "MAWP", "branch reinforcement", "miter",
                     "leak test", "345.4.2", "B31.1", "B31.3", "schedule check"):
            self.assertIn(term.lower(), desc.lower(), term)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)

    def test_no_b31j_or_appendix_d_sif_content(self):
        for word in ("B31J", "Appendix D", "intensification"):
            self.assertNotIn(word, self.text, word)
            self.assertNotIn(word, self.script, word)

    def test_no_tabulated_values_or_material_stress_pairs(self):
        # A material designation and a stress figure on the same line is the failure mode.
        material = re.compile(r"\b(A\d{3}\b|SA-\d+|API ?5L|X\d{2}\b|Gr(ade)?\.? ?[A-Z0-9]+\b.*\d)", re.I)
        stress = re.compile(r"\b\d[\d,\.]*\s*(psi|ksi)\b", re.I)
        for label, text in (("SKILL.md", self.text), ("pressure_design.py", self.script)):
            for ln in text.splitlines():
                self.assertFalse(material.search(ln) and stress.search(ln), f"{label}: {ln.strip()}")

    def test_required_sections_present(self):
        for heading in ("## Step 0", "## Copyright-safe lookups", "## How to run the calculators",
                        "## Output format", "## Hand-offs", "## Related tools", "load-case-builder",
                        "stress-screening", "engineer of record"):
            self.assertIn(heading.lower(), self.text.lower(), heading)
        for module in pd.REGISTRY:
            self.assertIn(module, self.text, module)


# --------------------------------------------------------------------------- code_values

SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
HELPER_BEGIN = "# ===== BEGIN code_values helper"
HELPER_END = "# ===== END code_values helper ====="
# The five calculator scripts that carry the shared code_values helper block.
HELPER_SCRIPTS = (
    ("pressure-design", "pressure_design.py"),
    ("stress-screening", "stress_screening.py"),
    ("nozzle-load", "nozzle_load.py"),
    ("bolted-flange", "bolted_flange.py"),
    ("pipe-support", "support_calc.py"),
)


def cv(value, unit, source="connector", column="Placeholder column"):
    """A code_values entry with a placeholder citation."""
    citation = {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
                "row": "Placeholder row"}
    if column:
        citation["column"] = column
    return {"value": value, "unit": unit, "citation": citation, "source": source}


class CodeValues(unittest.TestCase):
    """The optional top-level code_values input, the contract shared by the calculator scripts."""

    MOD = "piping.b313-wall-thickness"
    B313 = dict(HandDerived.B313, W_basis="seamless")
    ENVELOPE_KEYS = {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied",
                     "defaults_applied"}

    def _keys(self, module):
        """The envelope keys of a valid run: W modules add weld_factor_basis, gated ones validity."""
        keys = set(self.ENVELOPE_KEYS)
        if module in pd.W_MODULES:
            keys.add("weld_factor_basis")
        if module in pd.GATED_MODULES:
            keys |= {"validity", "result_grade"}
        return keys

    def _cli(self, inputs: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, CLI, self.MOD, "--input", json.dumps(inputs)],
                              capture_output=True, text=True, encoding="utf-8")

    def _split(self, module, base, names, source="connector"):
        """(explicit inputs, the same inputs with `names` moved into code_values)."""
        units = {f[0]: f[1] for f in pd.FIELDS[module]}
        moved = {n: cv(base[n], None if units[n] == "-" else units[n], source) for n in names}
        return dict(base), dict({k: v for k, v in base.items() if k not in names}, code_values=moved)

    def test_every_module_filled_run_equals_the_explicit_run(self):
        for module in pd.REGISTRY:
            base = with_basis(module, parity.load(module)["cases"][0]["input"])
            names = [n for n in pd.user_supplied_names(module) or ["c", "Th"]     # branch-reinforcement has none
                     if isinstance(base.get(n), (int, float)) and not isinstance(base.get(n), bool)]
            self.assertTrue(names, module)
            explicit, filled = self._split(module, base, names)
            want = pd.run_module(module, explicit)
            got = pd.run_module(module, filled)
            self.assertEqual(sorted(got.pop("code_value_provenance")), sorted(names), module)
            self.assertEqual(got, want, module)

    def test_each_user_supplied_input_can_be_filled_on_its_own(self):
        for module in pd.REGISTRY:
            base = with_basis(module, parity.load(module)["cases"][0]["input"])
            want = pd.run_module(module, dict(base))
            for name in pd.user_supplied_names(module):
                if not isinstance(base.get(name), (int, float)) or isinstance(base.get(name), bool):
                    continue
                _, filled = self._split(module, base, [name], source="user")
                got = pd.run_module(module, filled)
                got.pop("code_value_provenance")
                self.assertEqual(got, want, f"{module} {name}")

    def test_provenance_is_echoed_with_unit_citation_and_source(self):
        base = {k: v for k, v in self.B313.items() if k not in ("S", "Y")}
        env = pd.run_module(self.MOD, dict(base, code_values={"S": cv(24800, "psi"), "Y": cv(0.4, None, "user")}))
        self.assertEqual(list(env["code_value_provenance"]), ["S", "Y"])
        self.assertEqual(env["code_value_provenance"]["S"],
                         {"unit": "psi", "source": "connector", "citation": cv(0, "psi")["citation"]})
        self.assertEqual(env["code_value_provenance"]["Y"]["source"], "user")
        self.assertIsNone(env["code_value_provenance"]["Y"]["unit"])
        self.assertEqual(env["user_supplied"], ["S", "E", "W", "Y"])
        self.assertNotIn("code_values", env["inputs"])
        self.assertEqual(env["inputs"]["S"], 24800)

    def test_an_input_present_in_both_places_and_equal_is_recorded(self):
        env = pd.run_module(self.MOD, dict(self.B313, code_values={"S": cv(24800, "psi")}))
        self.assertEqual(sorted(env["code_value_provenance"]), ["S"])
        want = pd.run_module(self.MOD, dict(self.B313))
        env.pop("code_value_provenance")
        self.assertEqual(env, want)

    def test_ksi_is_converted_exactly_and_noted(self):
        base = {k: v for k, v in self.B313.items() if k != "S"}
        env = pd.run_module(self.MOD, dict(base, code_values={"S": cv(24.8, "ksi")}))
        self.assertEqual(env["inputs"]["S"], 24800.0)
        self.assertEqual(env["code_value_provenance"]["S"]["unit"], "ksi")
        self.assertIn("code_values.S: 24.8 ksi applied as 24800 psi.", env["warnings"])
        self.assertEqual(env["output"], pd.run_module(self.MOD, dict(self.B313))["output"])

    def test_a_unit_that_cannot_be_used_is_rejected(self):
        base = {k: v for k, v in self.B313.items() if k != "S"}
        for unit in ("MPa", "bar", None, "in"):
            with self.assertRaisesRegex(ValueError, "code_values.S unit .* cannot be used for an input in 'psi'"):
                pd.run_module(self.MOD, dict(base, code_values={"S": cv(171, unit)}))
        base = {k: v for k, v in self.B313.items() if k != "c"}
        with self.assertRaisesRegex(ValueError, "code_values.c unit 'psi' cannot be used for an input in 'in'"):
            pd.run_module(self.MOD, dict(base, code_values={"c": cv(0.0625, "psi")}))

    def test_a_conflict_exits_2_with_the_exact_message(self):
        r = self._cli(dict(self.B313, code_values={"S": cv(24801, "psi")}))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertEqual(r.stderr, "input error: code_values.S conflicts with input S\n")
        # the same conflict reached through a unit conversion
        r = self._cli(dict(self.B313, code_values={"S": cv(24.9, "ksi")}))
        self.assertEqual(r.stderr, "input error: code_values.S conflicts with input S\n")

    def test_an_unknown_name_exits_2(self):
        for name in ("Q", "s", "y", "gasket.m", "S.value"):
            r = self._cli(dict(self.B313, code_values={name: cv(1, "psi")}))
            self.assertEqual((r.returncode, r.stdout), (2, ""), name)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, name)
            self.assertTrue(r.stderr.startswith(
                f"input error: code_values.{name} is not an input of {self.MOD} (valid: "), r.stderr)

    def test_a_malformed_block_or_entry_exits_2(self):
        bad = [
            ([1, 2], "code_values must be an object"),
            ({"S": 24800}, "code_values.S must be an object with value, unit, citation and source"),
            ({"S": {"value": 1, "unit": "psi", "source": "user"}}, "code_values.S.citation needs"),
            ({"S": dict(cv(1, "psi"), citation={"standard": "x", "edition": "y", "table": "z"})},
             "code_values.S.citation needs"),
            ({"S": dict(cv(1, "psi"), source="vendor")}, "code_values.S.source must be"),
            ({"S": {k: v for k, v in cv(1, "psi").items() if k != "unit"}}, "code_values.S.unit is required"),
            ({"S": cv(True, "psi")}, "code_values.S.value must be a number or a string"),
            ({"S": cv([1], "psi")}, "code_values.S.value must be a number or a string"),
        ]
        base = {k: v for k, v in self.B313.items() if k != "S"}
        for block, fragment in bad:
            r = self._cli(dict(base, code_values=block))
            self.assertEqual((r.returncode, r.stdout), (2, ""), fragment)
            self.assertIn(fragment, r.stderr)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, fragment)

    def test_an_edition_year_typed_as_a_number_is_echoed_as_text(self):
        base = {k: v for k, v in self.B313.items() if k != "S"}
        entry = cv(24800, "psi")
        entry["citation"]["edition"] = 2022
        env = pd.run_module(self.MOD, dict(base, code_values={"S": entry}))
        self.assertEqual(env["code_value_provenance"]["S"]["citation"]["edition"], "2022")
        self.assertIsInstance(entry["citation"]["edition"], int)        # the caller's entry is untouched

    def test_a_string_value_is_passed_through_for_the_engine_to_judge(self):
        base = {k: v for k, v in self.B313.items() if k != "S"}
        with self.assertRaisesRegex(ValueError, "input 'S' must be a number"):
            pd.run_module(self.MOD, dict(base, code_values={"S": cv("24800", "psi")}))

    def test_absent_code_values_changes_nothing(self):
        for module in pd.REGISTRY:
            base = with_basis(module, parity.load(module)["cases"][0]["input"])
            env = pd.run_module(module, dict(base))
            self.assertEqual(set(env), self._keys(module), module)
            self.assertNotIn("code_value_provenance", env, module)
            # inputs shows the values used: an omitted W stated by W_basis is echoed as 1.0
            used = dict(base, W=1.0) if module in pd.W_MODULES and "W" not in base else base
            self.assertEqual(env["inputs"], used, module)
            # a null block is treated as absent
            nulled = pd.run_module(module, dict(base, code_values=None))
            self.assertEqual(nulled, env, module)

    def test_an_empty_block_changes_nothing(self):
        for module in pd.REGISTRY:
            base = with_basis(module, parity.load(module)["cases"][0]["input"])
            self.assertEqual(pd.run_module(module, dict(base, code_values={})), pd.run_module(module, dict(base)), module)

    def test_the_caller_dict_is_not_modified(self):
        base = {k: v for k, v in self.B313.items() if k != "S"}
        job = dict(base, code_values={"S": cv(24.8, "ksi")})
        before = json.dumps(job, sort_keys=True)
        pd.run_module(self.MOD, job)
        self.assertEqual(json.dumps(job, sort_keys=True), before)

    def test_list_mentions_the_block(self):
        r = subprocess.run([sys.executable, CLI, "list"], capture_output=True, text=True, encoding="utf-8")
        self.assertIn("code_values", r.stdout)

    def test_helper_block_is_identical_in_every_calculator_script(self):
        blocks = {}
        for skill, name in HELPER_SCRIPTS:
            with open(os.path.join(SKILLS, skill, "scripts", name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertEqual(text.count(HELPER_BEGIN), 1, name)
            blocks[name] = text[text.index(HELPER_BEGIN):text.index(HELPER_END)]
        first = blocks["pressure_design.py"]
        for name, block in blocks.items():
            self.assertEqual(block, first, name)


class ExampleFile(unittest.TestCase):
    """examples/b313-wall-thickness.json: placeholder inputs that show the code_values contract."""

    PATH = os.path.join(SCRIPTS, "examples", "b313-wall-thickness.json")

    def test_runs_through_the_cli_with_input_file(self):
        r = subprocess.run([sys.executable, CLI, "b313-wall-thickness", "--input-file", self.PATH],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        with open(self.PATH, encoding="utf-8") as fh:
            job = json.load(fh)
        self.assertEqual(job["_note"], "placeholder inputs, not code values")
        self.assertNotIn("_note", env["inputs"])
        # P, D, c and the mill tolerance are the E1 prompt's own inputs
        self.assertEqual((job["P"], job["D"], job["c"], job["millTolerance"]), (750, 6.625, 0.0625, 0.125))
        S, E, W, Y = job["code_values"]["S"]["value"] * 1000, job["E"], job["W"], job["code_values"]["Y"]["value"]
        t = 750 * 6.625 / (2 * (S * E * W + 750 * Y))
        self.assertAlmostEqual(env["output"]["t"], t, delta=1e-5)
        self.assertAlmostEqual(env["output"]["tOrder"], (t + 0.0625) / 0.875, delta=1e-5)
        self.assertEqual(sorted(env["code_value_provenance"]), ["S", "Y"])
        self.assertEqual(env["inputs"]["S"], 12345.0)

    def test_every_code_values_entry_is_a_marked_placeholder(self):
        with open(self.PATH, encoding="utf-8") as fh:
            job = json.load(fh)
        for name, entry in job["code_values"].items():
            self.assertTrue(entry["citation"]["standard"].startswith("Placeholder"), name)
            self.assertEqual(entry["citation"]["edition"], "0000", name)
            self.assertIn(entry["source"], ("connector", "user"), name)

    def test_the_example_is_clean_under_the_content_guard(self):
        content_guard.assert_clean(self, SKILL)


if __name__ == "__main__":
    unittest.main()
