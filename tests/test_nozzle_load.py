"""Regression tests for the nozzle-load skill and its calculators.

Standard library only (unittest), so the gate runs anywhere Python 3.9+ runs:

    python -m unittest discover -s tests -v

Three layers:
  1. Parity - the three ported modules reproduce the vendored engine fixtures exactly.
  2. Hand-derived cases - worked on paper from the published equations and the paper's method,
     using clearly fictitious round inputs (these are NOT allowables for any equipment), so the
     script is checked against arithmetic that did not come from the engine. This layer also
     covers the three new modules, which have no engine fixtures.
  3. CLI and SKILL.md guards.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "nozzle-load")
SCRIPTS = os.path.join(SKILL, "scripts")
CLI = os.path.join(SCRIPTS, "nozzle_load.py")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import content_guard  # noqa: E402
import nozzle_load as nl  # noqa: E402
import parity  # noqa: E402

TOL = 1e-4
PORTED = ("connections.nozzle-load-check", "connections.nema-sm23", "connections.api610-annexf")
NEW = ("equipment.nozzle-load-sum", "equipment.api650-annexp-ordinates", "equipment.pvp2011-allowables")


# Test-side values for fixture parity; not shipped. The calc-core fixture cases for
# connections.api610-annexf were computed with these Annex F constants, but the fixture inputs do
# not carry them (the skill takes them as the user-supplied `annexF` block), so the tests inject them.
_ANNEXF_COMMON = dict(componentMultiple=2.0, resultantDenominator=1.5, interactionLimit=2.0,
                      centreForceFactor=1.5, centreMyFactor=2.0)
ANNEXF_TEST = {
    "USC": dict(_ANNEXF_COMMON, sigmaPLimit=5950.0, kSigma=122.0, kTau=61.0),
    "SI": dict(_ANNEXF_COMMON, sigmaPLimit=41.0, kSigma=10200.0, kTau=5100.0),
}
ANNEXF_MODULE = "connections.api610-annexf"


def annexf(units: str = "USC") -> dict:
    return dict(ANNEXF_TEST[units])


def fixture_input(module: str, case: dict) -> dict:
    """A fixture case's input, with the test-side annexF block added for the Annex F module."""
    inp = dict(case["input"])
    if module == ANNEXF_MODULE:
        inp["annexF"] = annexf(inp["units"])
    return inp


def six(fx=0, fy=0, fz=0, mx=0, my=0, mz=0) -> dict:
    return {"Fx": fx, "Fy": fy, "Fz": fz, "Mx": mx, "My": my, "Mz": mz}


def flat(v: float) -> dict:
    return six(v, v, v, v, v, v)


def run(module: str, inputs: dict) -> dict:
    return nl.REGISTRY[module](dict(inputs))


def cli_run(module: str, inputs: dict) -> dict:
    return nl.run_module(module, inputs)


class Parity(unittest.TestCase):
    """One method per ported module so a failure names the module."""

    def _check(self, module: str) -> None:
        self.assertIn(module, nl.REGISTRY)
        registry = dict(nl.REGISTRY)
        if module == ANNEXF_MODULE:
            # Per-module input hook: wrap the function so each fixture case gets the test-side annexF block.
            engine = nl.REGISTRY[module]
            registry[module] = lambda inp: engine(dict(inp, annexF=annexf(inp["units"])))
        self.assertEqual(parity.run_fixture(registry, module), [])

    def test_annexf_fixture_inputs_carry_no_constants(self):
        # The vendored inputs come from the engine and must stay untouched: the constants are not in them,
        # and without the injected block the module refuses to run.
        for case in parity.load(ANNEXF_MODULE)["cases"]:
            self.assertNotIn("annexF", case["input"])
            with self.assertRaisesRegex(ValueError, r"annexF\.(componentMultiple|sigmaPLimit) is required"):
                nl.REGISTRY[ANNEXF_MODULE](dict(case["input"]))

    def test_manifest_modules_are_registered(self):
        manifest = parity.modules_for("nozzle-load")
        self.assertEqual(sorted(manifest), sorted(PORTED))
        for module in manifest:
            self.assertIn(module, nl.REGISTRY)

    def test_registry_is_ported_plus_new(self):
        self.assertEqual(sorted(nl.REGISTRY), sorted(PORTED + NEW))

    def test_nozzle_load_check(self):
        self._check("connections.nozzle-load-check")

    def test_nema_sm23(self):
        self._check("connections.nema-sm23")

    def test_api610_annexf(self):
        self._check("connections.api610-annexf")


class Metadata(unittest.TestCase):

    def test_every_module_has_citation_fields_and_user_supplied(self):
        for module in nl.REGISTRY:
            self.assertTrue(nl.CITATIONS.get(module), module)
            self.assertIn(module, nl.FIELDS)
            self.assertIn(module, nl.USER_SUPPLIED)
            names = [f[0] for f in nl.FIELDS[module]]
            self.assertEqual(len(names), len(set(names)), module)
            for name in nl.USER_SUPPLIED[module]:
                self.assertIn(name, names, f"{module}: {name}")

    def test_result_envelope_shape_for_ported_modules(self):
        for module in PORTED:
            fx = parity.load(module)
            res = run(module, fixture_input(module, fx["cases"][0]))
            self.assertEqual(set(res), {"module", "output", "status", "warnings"})
            self.assertEqual(res["module"], module)
            self.assertIn(res["status"], {"pass", "fail", "na"})
            self.assertIsInstance(res["warnings"], list)

    def test_round_half_up(self):
        self.assertEqual(nl.round_half_up(1.005, 2), 1.01)      # binary float would give 1.0
        self.assertEqual(nl.round_half_up(2.5, 0), 3.0)
        self.assertEqual(nl.round_half_up(-2.5, 0), -3.0)       # away from zero, not banker's
        self.assertTrue(math.isinf(nl.round_half_up(math.inf, 3)))

    def test_round_sig(self):
        self.assertEqual(nl.round_sig(0.000123456789, 3), 0.000123)
        self.assertEqual(nl.round_sig(0, 3), 0)

    def test_named_constants_are_the_cited_numbers(self):
        self.assertEqual((nl.PVP_REF_STRESS_VESSEL, nl.PVP_REF_STRESS_NOZZLE), (18800.0, 17100.0))
        self.assertEqual(nl.PVP_TABLE_BASIS_THICKNESS, {"1A": 0.25, "1B": 0.375, "2": 0.375})
        self.assertFalse([n for n in dir(nl) if n.startswith("API610_") and n != "API610_UNIT_CONV"])
        self.assertEqual(nl.API610_UNIT_CONV, {"SI": 1000.0, "USC": 12.0})


class HandDerivedPorted(unittest.TestCase):
    """Cases for the ported modules worked by hand."""

    # --- per-component check ------------------------------------------------------------
    def test_check_ratios_and_governing(self):
        inp = dict(standard="datasheet", applied=six(400, -200, 100, 300, -900, 0), allowable=six(1000, 1000, 1000, 1000, 1000, 1000))
        res = run("connections.nozzle-load-check", inp)
        out = res["output"]
        self.assertEqual(out["ratios"], dict(Fx=0.4, Fy=0.2, Fz=0.1, Mx=0.3, My=0.9, Mz=0.0))   # |applied| / allowable
        self.assertEqual(out["governing"], "My")
        self.assertEqual(res["status"], "pass")
        self.assertAlmostEqual(out["FR"], math.sqrt(400 ** 2 + 200 ** 2 + 100 ** 2), delta=0.005)
        self.assertAlmostEqual(out["MR"], math.sqrt(300 ** 2 + 900 ** 2), delta=0.005)

    def test_check_over_one_fails(self):
        inp = dict(standard="datasheet", applied=six(0, 0, 0, 0, 0, -1500), allowable=flat(1000))
        res = run("connections.nozzle-load-check", inp)
        self.assertEqual((res["status"], res["output"]["governing"], res["output"]["maxRatio"]), ("fail", "Mz", 1.5))

    def test_check_recece_note_only_above_half(self):
        low = run("connections.nozzle-load-check", dict(standard="x", applied=flat(400), allowable=flat(1000)))
        high = run("connections.nozzle-load-check", dict(standard="x", applied=flat(600), allowable=flat(1000)))
        self.assertEqual(low["warnings"], [])
        self.assertEqual(len(high["warnings"]), 1)
        self.assertIn("RECE002", high["warnings"][0])
        self.assertEqual(high["status"], "pass")        # the note never changes the verdict

    # --- NEMA SM-23 combined form -------------------------------------------------------
    # NPS 6 -> De = 6.  Fr = sqrt(300^2 + 400^2) = 500, Mr = sqrt(600^2 + 800^2) = 1000.
    # index = 3*500 + 1000 = 2500;  a = 500 -> allowable 3000, ratio 5/6.
    SM23 = dict(NPS=6, applied=six(300, 400, 0, 0, 800, 600), coefficient=500)

    def test_sm23_hand_case(self):
        res = run("connections.nema-sm23", self.SM23)
        out = res["output"]
        self.assertEqual((out["De"], out["Fr"], out["Mr"], out["index"], out["allowable"]), (6.0, 500.0, 1000.0, 2500.0, 3000.0))
        self.assertAlmostEqual(out["ratio"], 5 / 6, delta=TOL)
        self.assertEqual(res["status"], "pass")

    def test_sm23_equivalent_diameter_break_at_nps_8(self):
        self.assertEqual(run("connections.nema-sm23", dict(self.SM23, NPS=8))["output"]["De"], 8.0)
        self.assertAlmostEqual(run("connections.nema-sm23", dict(self.SM23, NPS=10))["output"]["De"], 26 / 3, delta=1e-5)
        self.assertAlmostEqual(run("connections.nema-sm23", dict(self.SM23, NPS=24))["output"]["De"], 40 / 3, delta=1e-5)

    def test_sm23_coefficient_scales_the_allowable_and_can_fail_it(self):
        res = run("connections.nema-sm23", dict(self.SM23, coefficient=400))
        self.assertEqual((res["output"]["allowable"], res["status"]), (2400.0, "fail"))

    # --- Annex F ------------------------------------------------------------------------
    ZERO = six()

    def _f(self, **kw) -> dict:
        base = dict(pumpType="horizontal", units="USC", suctionApplied=self.ZERO, dischargeApplied=self.ZERO,
                    suctionAllowable=flat(1000), dischargeAllowable=flat(1000),
                    suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0),
                    annexF=annexf(kw.get("units", "USC")))
        base.update(kw)
        return run("connections.api610-annexf", base)

    def test_annexf_component_beyond_twice_table_fails_F12a(self):
        # Fy = 2500 on a 1000 allowable: ratio 2500 / 2000 = 1.25 > 1 on the F.1.2(a) screen
        res = self._f(suctionApplied=six(0, 2500, 0, 0, 0, 0))
        self.assertEqual(res["output"]["maxComponentRatio"], 1.25)
        self.assertEqual(res["output"]["governingComponent"], "suction.Fy")
        self.assertEqual(res["status"], "fail")
        self.assertTrue(any("F.1.3" in w for w in res["warnings"]))

    def test_annexf_pump_centre_unit_constant(self):
        # Suction Fy = 1000 at x = 120: MZCA = 0 + 500 - (0 - 1000*120)/k -> USC k=12 gives 10500, SI k=1000 gives 620
        inp = dict(suctionApplied=six(0, 1000, 0, 0, 0, 0), dischargeApplied=six(0, 0, 0, 0, 0, 500),
                   suctionPosition=dict(x=120, y=0, z=0))
        self.assertEqual(self._f(units="USC", **inp)["output"]["MZCA"], 10500.0)
        self.assertEqual(self._f(units="SI", **inp)["output"]["MZCA"], 620.0)

    def test_annexf_vertical_principal_stress_hand_case(self):
        # Suction Fy = 1000 tension on Do = 4, Di = 3 (placeholder bore): area term 1.27*1000/(16 - 9) = 181.4286;
        # no shear, so sigma_p = sigma_l/2 + sqrt(sigma_l^2/4) = sigma_l.  Ratio to the 5950 psi limit = 0.030494.
        res = self._f(pumpType="vertical-inline", suctionApplied=six(0, 1000, 0, 0, 0, 0),
                      suctionBore=dict(Do=4, Di=3), dischargeBore=dict(Do=4, Di=3))
        out = res["output"]
        self.assertAlmostEqual(out["suctionSigmaL"], 1270 / 7, delta=TOL)
        self.assertAlmostEqual(out["suctionSigmaP"], 1270 / 7, delta=TOL)
        self.assertAlmostEqual(out["suctionStressRatio"], (1270 / 7) / 5950, delta=1e-5)
        self.assertEqual(out["dischargeSigmaP"], 0.0)
        self.assertEqual(out["governingEquation"], "F.9")
        self.assertEqual(res["status"], "pass")

    def test_annexf_constants_drive_the_result(self):
        # Changing a user-supplied constant changes the verdict: nothing is baked in.
        loose = self._f(suctionApplied=six(0, 2500, 0, 0, 0, 0), annexF=dict(annexf(), componentMultiple=3.0))
        self.assertEqual(loose["output"]["maxComponentRatio"], round(2500 / 3000, 5))
        self.assertEqual(loose["output"]["checks"][0]["limit"], 3000.0)
        self.assertIn("3x Table 5", loose["output"]["checks"][0]["label"])

    def test_annexf_vertical_needs_only_its_three_constants(self):
        keys = ("sigmaPLimit", "kSigma", "kTau")
        res = self._f(pumpType="vertical-inline", suctionApplied=six(0, 1000, 0, 0, 0, 0),
                      suctionBore=dict(Do=4, Di=3), dischargeBore=dict(Do=4, Di=3),
                      annexF={k: annexf()[k] for k in keys})
        self.assertNotIn("maxComponentRatio", res["output"])
        self.assertEqual(res["status"], "pass")
        self.assertTrue(any("componentMultiple was not supplied" in w for w in res["warnings"]))

    def test_annexf_vertical_component_screen_is_advisory(self):
        # 3x the table range on Fy fails F.1.2(a) but F.2 permits it, so the verdict rests on the stress check
        res = self._f(pumpType="vertical-inline", suctionApplied=six(0, 3000, 0, 0, 0, 0),
                      suctionBore=dict(Do=4, Di=3), dischargeBore=dict(Do=4, Di=3))
        self.assertGreater(res["output"]["maxComponentRatio"], 1)
        self.assertEqual(res["status"], "pass")
        self.assertTrue(res["output"]["checks"][0]["advisory"])


class HandDerivedSum(unittest.TestCase):
    """equipment.nozzle-load-sum"""

    N1 = dict(tag="N1", **six(100, -50, 0, 200, 0, 300))
    N2 = dict(tag="N2", **six(300, 100, 50, -100, 400, 100))
    # sums: Fx 400, Fy 50, Fz 50, Mx 100, My 400, Mz 400
    LIMITS = six(500, 500, 500, 1000, 1000, 1000)

    def _sum(self, **kw) -> dict:
        inp = dict(standard="header limits", nozzles=[self.N1, self.N2], limits=self.LIMITS)
        inp.update(kw)
        return run("equipment.nozzle-load-sum", inp)

    def test_signed_sum_and_ratios(self):
        res = self._sum()
        out = res["output"]
        self.assertEqual(out["sum"], six(400, 50, 50, 100, 400, 400))
        self.assertEqual(out["absoluteSum"], six(400, 150, 50, 300, 400, 400))   # informational: signs aligned
        self.assertEqual(out["ratios"], dict(Fx=0.8, Fy=0.1, Fz=0.1, Mx=0.1, My=0.4, Mz=0.4))
        self.assertEqual((out["maxRatio"], out["governing"], res["status"]), (0.8, "Fx", "pass"))
        self.assertEqual(out["nozzleCount"], 2)
        self.assertAlmostEqual(out["FR"], math.sqrt(400 ** 2 + 50 ** 2 + 50 ** 2), delta=1e-3)

    def test_signs_cancel(self):
        res = self._sum(nozzles=[six(500, 0, 0, 0, 0, 0), six(-500, 0, 0, 0, 0, 0)])
        self.assertEqual(res["output"]["sum"]["Fx"], 0.0)
        self.assertEqual(res["output"]["absoluteSum"]["Fx"], 1000.0)
        self.assertEqual(res["output"]["perNozzle"][0]["tag"], "nozzle 1")       # untagged sets get a default label

    def test_bay_multiplier_of_three(self):
        # Fx limit 300: the sum 400 fails a single header (1.3333) and passes a bay at 3x (0.4444)
        limits = dict(self.LIMITS, Fx=300)
        single = self._sum(limits=limits)
        bay = self._sum(limits=limits, multiplier=3)
        self.assertEqual((single["status"], single["output"]["ratios"]["Fx"]), ("fail", 1.33333))
        self.assertEqual((bay["status"], bay["output"]["ratios"]["Fx"]), ("pass", 0.44444))
        self.assertEqual(bay["output"]["effectiveLimit"]["Fx"], 900.0)
        self.assertTrue(any("multiplier of 3" in w for w in bay["warnings"]))

    def test_one_nozzle_warns(self):
        res = self._sum(nozzles=[self.N1])
        self.assertTrue(any("Only one nozzle" in w for w in res["warnings"]))

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, "nozzles must be a non-empty list"):
            self._sum(nozzles=[])
        with self.assertRaisesRegex(ValueError, r"limits.Fz must be > 0"):
            self._sum(limits=dict(self.LIMITS, Fz=0))
        with self.assertRaisesRegex(ValueError, "multiplier must be > 0"):
            self._sum(multiplier=0)
        with self.assertRaisesRegex(ValueError, r"nozzles\[1\].Mz is required"):
            self._sum(nozzles=[self.N1, {k: v for k, v in self.N2.items() if k != "Mz"}])


class HandDerivedAnnexP(unittest.TestCase):
    """equipment.api650-annexp-ordinates, fictitious round inputs.

    a = 500, R = 10000, t = 25  ->  R*t = 250000, sqrt = 500, lambda = 1.0
    L = 1000                    ->  XA = 1500, XB = 500, XC = 1000  ->  3, 1, 2 over sqrt(R t)
    P = 0.1                     ->  FP = pi * 500^2 * 0.1 = 25000 pi
    YF = 2, YL = 4, YC = 5
    FR = 100000: (1/(2*2)) * 100000/(25000 pi)      = 1/pi
    ML = 1e8   : (1/(500*4)) * 1e8/(25000 pi)       = 2/pi
    MC = -2e8  : (1/(500*5)) * (-2e8)/(25000 pi)    = -3.2/pi
    """
    INP = dict(FR=100000, ML=1e8, MC=-2e8, a=500, R=10000, t=25, L=1000, P=0.1, YF=2, YL=4, YC=5)

    def test_ordinates(self):
        res = run("equipment.api650-annexp-ordinates", self.INP)
        out = res["output"]
        self.assertEqual(res["status"], "na")
        self.assertAlmostEqual(out["lambda"], 1.0, delta=1e-9)
        self.assertAlmostEqual(out["FP"], 25000 * math.pi, delta=0.1)
        self.assertEqual((out["XA_over_sqrtRt"], out["XB_over_sqrtRt"], out["XC_over_sqrtRt"]), (3.0, 1.0, 2.0))
        self.assertAlmostEqual(out["abscissa"], 1 / math.pi, delta=1e-5)
        self.assertAlmostEqual(out["ordinateP5a"], 2 / math.pi, delta=1e-5)
        self.assertAlmostEqual(out["ordinateP5b"], -3.2 / math.pi, delta=1e-5)

    def test_per_unit_load_scales_reproduce_the_ordinates(self):
        out = run("equipment.api650-annexp-ordinates", self.INP)["output"]
        self.assertAlmostEqual(out["abscissaPerFR"] * 100000, out["abscissa"], delta=1e-5)
        self.assertAlmostEqual(out["ordinateP5aPerML"] * 1e8, out["ordinateP5a"], delta=1e-5)
        self.assertAlmostEqual(out["ordinateP5bPerMC"] * -2e8, out["ordinateP5b"], delta=1e-5)

    def test_signs_are_kept(self):
        out = run("equipment.api650-annexp-ordinates", dict(self.INP, FR=-100000, ML=-1e8, MC=2e8))["output"]
        self.assertLess(out["abscissa"], 0)
        self.assertLess(out["ordinateP5a"], 0)
        self.assertGreater(out["ordinateP5b"], 0)

    def test_lambda_outside_plotted_range_warns(self):
        res = run("equipment.api650-annexp-ordinates", dict(self.INP, a=10))    # lambda = 0.02
        self.assertTrue(any("outside 0.1 to 30" in w for w in res["warnings"]))
        self.assertFalse(any("outside 0.1" in w for w in run("equipment.api650-annexp-ordinates", self.INP)["warnings"]))

    def test_errors(self):
        for name in ("a", "R", "t", "L", "P", "YF", "YL", "YC"):
            with self.assertRaisesRegex(ValueError, f"{name} must be > 0"):
                run("equipment.api650-annexp-ordinates", dict(self.INP, **{name: 0}))
        with self.assertRaisesRegex(ValueError, "FR is required"):
            run("equipment.api650-annexp-ordinates", {k: v for k, v in self.INP.items() if k != "FR"})


class HandDerivedPvp(unittest.TestCase):
    """equipment.pvp2011-allowables with a fictitious flat row: 1000 lbf and 1000 ft-lbf everywhere
    (these are NOT values of the paper's tables)."""

    BASE = dict(table="1A", NPS=6, row=flat(1000), T=0.25, S_vessel=18800, S_nozzle=17100)

    def _p(self, **kw) -> dict:
        d = dict(self.BASE)
        d.update(kw)
        return run("equipment.pvp2011-allowables", d)

    def _derived(self, res: dict) -> set:
        return set(res["output"]["derived"].values())

    def test_at_basis_with_reference_stresses_is_unchanged(self):
        res = self._p()
        self.assertEqual(res["status"], "na")
        self.assertEqual(self._derived(res), {1000.0})
        self.assertEqual(res["output"]["totalFactor"], 1.0)
        self.assertEqual(res["output"]["basisThickness"], 0.25)

    def test_thickness_scaling_eq4(self):
        # T = 0.125 on a 0.25 basis: (0.125/0.25)^2 = 0.25
        res = self._p(T=0.125)
        self.assertEqual(res["output"]["thicknessFactor"], 0.25)
        self.assertEqual(self._derived(res), {250.0})
        self.assertTrue(any("eq. (4)" in w and "below the Table 1A thickness basis" in w for w in res["warnings"]))

    def test_thickness_scaling_uses_the_tables_own_basis(self):
        # Table 1B and Table 2 both have a 0.375 basis; T = 0.1875 gives (0.5)^2 = 0.25
        for table in ("1B", "2"):
            res = self._p(table=table, T=0.1875)
            self.assertEqual(res["output"]["basisThickness"], 0.375)
            self.assertEqual(res["output"]["thicknessFactor"], 0.25)
            self.assertTrue(any("skill's extension" in w for w in res["warnings"]))

    def test_thickness_above_basis_earns_no_credit_and_no_warning(self):
        res = self._p(T=0.5)
        self.assertEqual(res["output"]["thicknessFactor"], 1.0)
        self.assertFalse(any("thickness basis" in w for w in res["warnings"]))

    def test_stress_ratio_lowest_governs(self):
        # S_vessel = 9400 -> 0.5 against 18,800; neck at 17,100 is 1.0
        res = self._p(S_vessel=9400)
        self.assertEqual(res["output"]["stressRatio"], 0.5)
        self.assertEqual(self._derived(res), {500.0})
        # neck governs: 8550 / 17,100 = 0.5 and shell above its reference
        res = self._p(S_vessel=20000, S_nozzle=8550)
        self.assertEqual((res["output"]["stressRatioVessel"] > 1, res["output"]["stressRatio"]), (True, 0.5))

    def test_stress_ratio_is_capped_at_one(self):
        res = self._p(S_vessel=25000, S_nozzle=25000)
        self.assertEqual(res["output"]["stressRatio"], 1.0)
        self.assertEqual(self._derived(res), {1000.0})
        self.assertTrue(any("capped at 1.0" in line for line in res["output"]["log"]))

    def test_owner_factor(self):
        res = self._p(ownerFactor=0.5, ownerFactorBasis="project spec")
        self.assertEqual(self._derived(res), {500.0})
        self.assertTrue(any("Owner factor x0.5 (project spec)" in line for line in res["output"]["log"]))

    def test_factors_compound_and_log_lists_each(self):
        # 0.25 (thickness) x 0.5 (stress) x 0.5 (owner) = 0.0625
        res = self._p(T=0.125, S_vessel=9400, ownerFactor=0.5)
        self.assertEqual(res["output"]["totalFactor"], 0.0625)
        self.assertEqual(self._derived(res), {62.5})
        log = " ".join(res["output"]["log"])
        for word in ("Thickness", "Stress ratio", "Owner factor", "Total factor"):
            self.assertIn(word, log)

    def test_interpolation_force_linear_in_d_moment_linear_in_d_squared(self):
        # rows at NPS 4 and 8, NPS 6: forces 1000 -> 2000 give 1500 (weight 2/4 = 1/2);
        # moments 2000 -> 6000 weight (36 - 16)/(64 - 16) = 5/12 -> 2000 + 4000*5/12 = 3666.667
        res = self._p(row=None, lowerNPS=4, upperNPS=8,
                      lowerRow=six(1000, 1000, 1000, 2000, 2000, 2000), upperRow=six(2000, 2000, 2000, 6000, 6000, 6000))
        out = res["output"]
        self.assertTrue(out["interpolated"])
        for k in ("Fx", "Fy", "Fz"):
            self.assertEqual(out["derived"][k], 1500.0)
        for k in ("Mx", "My", "Mz"):
            self.assertAlmostEqual(out["derived"][k], 2000 + 4000 * 5 / 12, delta=1e-3)

    def test_interpolation_log_does_not_credit_the_paper_with_the_affine_form(self):
        res = self._p(row=None, lowerNPS=4, upperNPS=8,
                      lowerRow=six(1000, 1000, 1000, 2000, 2000, 2000), upperRow=six(2000, 2000, 2000, 6000, 6000, 6000))
        line = [ln for ln in res["output"]["log"] if ln.startswith("Interpolated")][0]
        self.assertIn("affine in d", line)
        self.assertIn("skill's reading", line)
        self.assertNotIn("linear in d (eq. 1)", line)

    def test_interpolation_reports_the_proportional_bound(self):
        # NPS 6 between rows 4 and 8. Forces: 1000*6/4 = 1500 and 2000*6/8 = 1500 -> 1500, equal to the affine value.
        # Moments: 2000*36/16 = 4500 and 6000*36/64 = 3375 -> lower 3375, below the affine 3666.667.
        res = self._p(row=None, lowerNPS=4, upperNPS=8,
                      lowerRow=six(1000, 1000, 1000, 2000, 2000, 2000), upperRow=six(2000, 2000, 2000, 6000, 6000, 6000))
        bound = res["output"]["proportionalBound"]
        for k in ("Fx", "Fy", "Fz"):
            self.assertAlmostEqual(bound[k], 1500.0, delta=1e-3)
        for k in ("Mx", "My", "Mz"):
            self.assertAlmostEqual(bound[k], 3375.0, delta=1e-3)
        text = " | ".join(res["warnings"])
        self.assertIn("exceeds the proportional-through-origin bound", text)
        self.assertIn("Mx, My, Mz", text)
        self.assertIsNone(self._p()["output"]["proportionalBound"])

    def test_temperature_above_650_names_the_stress_ratio_as_the_only_adjustment(self):
        text = " | ".join(self._p(designTempF=800)["warnings"])
        self.assertIn("only adjustment is the stress ratio", text)
        self.assertIn("creep-range", text)

    def test_primary_loads_are_inside_the_papers_basis(self):
        text = " | ".join(self._p(loadsPrimary=True)["warnings"])
        self.assertIn("inside the paper's basis", text)
        self.assertNotIn("how wholly primary loads are treated", text)

    def test_scope_note_describes_the_pad_basis_accurately(self):
        text = " | ".join(self._p()["warnings"])
        self.assertIn("effective pad thickness", text)
        self.assertNotIn("full-thickness pads and", text)

    def test_interpolation_at_a_row_returns_that_row(self):
        r1, r2 = flat(1000), flat(2000)
        out = self._p(row=None, NPS=4, lowerNPS=4, upperNPS=8, lowerRow=r1, upperRow=r2)["output"]
        self.assertEqual(set(out["derived"].values()), {1000.0})
        out = self._p(row=None, NPS=8, lowerNPS=4, upperNPS=8, lowerRow=r1, upperRow=r2)["output"]
        self.assertEqual(set(out["derived"].values()), {2000.0})

    def test_scope_warnings(self):
        res = self._p(NPS=30, designTempF=700, material="aluminium", D=100, T=0.25, loadsPrimary=True)
        text = " | ".join(res["warnings"])
        self.assertIn("outside the paper's tabulated range", text)
        self.assertIn("above the paper's 650 F", text)
        self.assertIn("Aluminium", text)
        self.assertIn("D/T = 400.0 exceeds 320", text)
        self.assertIn("Loads declared primary", text)
        self.assertIn("individual analysis", text)

    def test_clean_basis_has_only_the_scope_note(self):
        res = self._p(designTempF=650, material="killed-carbon-steel", D=48, loadsPrimary=False)
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("Scope of the paper", res["warnings"][0])

    def test_unstated_basis_items_are_flagged(self):
        text = " | ".join(self._p()["warnings"])
        for fragment in ("Design temperature not stated", "Material not stated", "Vessel diameter not stated",
                         "not stated (loadsPrimary)"):
            self.assertIn(fragment, text)

    def test_other_materials_warn(self):
        self.assertTrue(any("not killed carbon steel" in w for w in self._p(material="other-ferrous")["warnings"]))

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, "table must be"):
            self._p(table="3")
        with self.assertRaisesRegex(ValueError, "T must be > 0"):
            self._p(T=0)
        with self.assertRaisesRegex(ValueError, "S_vessel must be > 0"):
            self._p(S_vessel=-1)
        with self.assertRaisesRegex(ValueError, r"ownerFactor must be in \(0, 1\]"):
            self._p(ownerFactor=1.2)
        with self.assertRaisesRegex(ValueError, r"row.Mz must be > 0"):
            self._p(row=dict(flat(1000), Mz=0))
        with self.assertRaisesRegex(ValueError, "either row"):
            self._p(row=None)
        with self.assertRaisesRegex(ValueError, "either row"):
            self._p(lowerNPS=4, upperNPS=8, lowerRow=flat(1), upperRow=flat(2))
        with self.assertRaisesRegex(ValueError, "no extrapolation"):
            self._p(row=None, NPS=10, lowerNPS=4, upperNPS=8, lowerRow=flat(1), upperRow=flat(2))
        with self.assertRaisesRegex(ValueError, "interpolation needs all"):
            self._p(row=None, lowerNPS=4, upperNPS=8, lowerRow=flat(1))

    def test_derived_set_feeds_the_per_component_check(self):
        derived = self._p(T=0.125)["output"]["derived"]                     # 250 everywhere
        res = run("connections.nozzle-load-check", dict(standard="PVP2011-57100 Table 1A, derived",
                                                         applied=six(200, 100, 0, 250, 0, 300), allowable=derived))
        self.assertEqual((res["status"], res["output"]["governing"], res["output"]["maxRatio"]), ("fail", "Mz", 1.2))


class OwnerFactorOnPortedModules(unittest.TestCase):
    """ownerFactor is applied by the CLI layer to the entered allowables; the ported functions are untouched."""

    def test_check_allowables_are_scaled(self):
        inp = dict(standard="datasheet", applied=six(400), allowable=flat(1000), ownerFactor=0.5)
        env = cli_run("connections.nozzle-load-check", inp)
        self.assertEqual(env["output"]["maxRatio"], 0.8)                     # 400 / (1000 * 0.5)
        self.assertEqual(env["inputs"]["ownerFactor"], 0.5)                  # input echoed unchanged
        self.assertEqual(env["inputs"]["allowable"], flat(1000))
        self.assertTrue(any("ownerFactor 0.5 applied" in w for w in env["warnings"]))
        plain = cli_run("connections.nozzle-load-check", dict(standard="datasheet", applied=six(400), allowable=flat(1000)))
        self.assertEqual(plain["output"]["maxRatio"], 0.4)

    def test_owner_factor_can_flip_a_pass(self):
        inp = dict(standard="datasheet", applied=six(600), allowable=flat(1000))
        self.assertEqual(cli_run("connections.nozzle-load-check", inp)["status"], "pass")
        self.assertEqual(cli_run("connections.nozzle-load-check", dict(inp, ownerFactor=0.5))["status"], "fail")

    def test_engine_recece002_note_is_not_double_counted_with_an_owner_factor(self):
        # raw ratio 0.6 is above 0.5, so the engine note fires without a factor; with ownerFactor 0.5 the
        # allowable is already factored (ratio 1.2) and the note about "the entered allowable" is dropped.
        inp = dict(standard="datasheet", applied=six(600), allowable=flat(1000))
        plain = cli_run("connections.nozzle-load-check", inp)
        self.assertTrue(any("maxRatio exceeds 0.5" in w for w in plain["warnings"]))
        env = cli_run("connections.nozzle-load-check", dict(inp, ownerFactor=0.5))
        self.assertEqual(env["output"]["maxRatio"], 1.2)
        self.assertFalse(any("maxRatio exceeds 0.5" in w for w in env["warnings"]))
        self.assertTrue(any("ownerFactor 0.5 applied" in w for w in env["warnings"]))

    def test_sm23_coefficient_is_scaled(self):
        env = cli_run("connections.nema-sm23", dict(HandDerivedPorted.SM23, ownerFactor=0.5))
        self.assertEqual(env["output"]["allowable"], 1500.0)
        self.assertEqual(env["status"], "fail")

    def test_annexf_table5_ranges_are_scaled(self):
        inp = dict(pumpType="horizontal", units="USC", suctionApplied=six(0, 1000, 0, 0, 0, 0), dischargeApplied=six(),
                   suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf(),
                   suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
        self.assertEqual(cli_run("connections.api610-annexf", inp)["output"]["maxComponentRatio"], 0.5)
        self.assertEqual(cli_run("connections.api610-annexf", dict(inp, ownerFactor=0.5))["output"]["maxComponentRatio"], 1.0)

    def test_sum_limits_are_scaled_before_the_multiplier(self):
        inp = dict(standard="x", nozzles=[six(300)], limits=flat(1000), multiplier=3, ownerFactor=0.5)
        self.assertEqual(cli_run("equipment.nozzle-load-sum", inp)["output"]["effectiveLimit"]["Fx"], 1500.0)

    def test_bad_owner_factor_is_rejected(self):
        for bad in (0, -0.5, 1.5, "half"):
            with self.assertRaises(ValueError, msg=str(bad)):
                cli_run("connections.nozzle-load-check",
                        dict(standard="x", applied=six(1), allowable=flat(1000), ownerFactor=bad))

    def test_pvp_takes_it_natively_and_api650_does_not_declare_it(self):
        names = [f[0] for f in nl.FIELDS["equipment.pvp2011-allowables"]]
        self.assertIn("ownerFactor", names)
        self.assertNotIn("ownerFactor", [f[0] for f in nl.FIELDS["equipment.api650-annexp-ordinates"]])
        self.assertNotIn("equipment.pvp2011-allowables", nl.OWNER_SCALED)


class EngineErrors(unittest.TestCase):
    """Thrown-error conditions and messages match the engine for the ported modules."""

    def _raises(self, module: str, inputs: dict, message: str) -> None:
        with self.assertRaises(ValueError) as cm:
            run(module, inputs)
        self.assertEqual(str(cm.exception), message)

    def test_nozzle_load_check(self):
        self._raises("connections.nozzle-load-check",
                     dict(standard="x", applied=flat(1), allowable=dict(flat(1), My=0)),
                     "allowable.My must be > 0 (supply it from the governing standard/vendor)")

    def test_nema_sm23(self):
        base = dict(NPS=6, applied=flat(1), coefficient=700)
        self._raises("connections.nema-sm23", dict(base, NPS=0), "NPS must be > 0")
        self._raises("connections.nema-sm23", dict(base, NPS=-12), "NPS must be > 0")
        self._raises("connections.nema-sm23", dict(base, coefficient=0), "coefficient must be > 0")

    def test_sm23_coefficient_has_no_default(self):
        with self.assertRaisesRegex(ValueError, "coefficient is required"):
            run("connections.nema-sm23", dict(NPS=6, applied=flat(1)))

    def test_annexf(self):
        base = dict(pumpType="horizontal", units="USC", suctionApplied=six(), dischargeApplied=six(),
                    suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf())
        self._raises("connections.api610-annexf", dict(base, suctionAllowable=dict(flat(1000), Fz=0)),
                     "suctionAllowable.Fz must be > 0 (supply the Table 5 base range for this nozzle/component)")
        self._raises("connections.api610-annexf", dict(base, pumpType="axial"),
                     'pumpType must be "horizontal" or "vertical-inline"')
        self._raises("connections.api610-annexf", dict(base, units="metric"), 'units must be "USC" or "SI"')
        self._raises("connections.api610-annexf", base,
                     'suctionPosition and dischargePosition are required for pumpType "horizontal" '
                     "(F.1.2 c / F.3-F.5 resolve loads to the pump center)")
        self._raises("connections.api610-annexf", dict(base, pumpType="vertical-inline"),
                     'suctionBore and dischargeBore ({Do, Di}) are required for pumpType "vertical-inline" '
                     "(F.2 / F.6-F.11 principal stress)")
        self._raises("connections.api610-annexf",
                     dict(base, pumpType="vertical-inline", suctionBore=dict(Do=3, Di=4), dischargeBore=dict(Do=4, Di=3)),
                     "nozzle bore requires Do > Di > 0 (Schedule 40 pipe OD/ID for the nozzle's nominal size)")

    HORIZONTAL_KEYS = ("componentMultiple", "resultantDenominator", "interactionLimit", "centreForceFactor", "centreMyFactor")
    VERTICAL_KEYS = ("sigmaPLimit", "kSigma", "kTau")

    def _annexf_base(self, pump_type: str) -> dict:
        base = dict(pumpType=pump_type, units="USC", suctionApplied=six(), dischargeApplied=six(),
                    suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf())
        if pump_type == "horizontal":
            base.update(suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
        else:
            base.update(suctionBore=dict(Do=4, Di=3), dischargeBore=dict(Do=4, Di=3))
        return base

    def test_annexf_missing_block_names_the_first_key(self):
        base = self._annexf_base("horizontal")
        del base["annexF"]
        self._raises(ANNEXF_MODULE, base, "annexF.componentMultiple is required (read it from F.1.2 a) of the "
                                          "edition of record; no default)")
        vbase = self._annexf_base("vertical-inline")
        del vbase["annexF"]
        self._raises(ANNEXF_MODULE, vbase, "annexF.sigmaPLimit is required (read it from Eq. F.6 (SI) or F.9 (USC) "
                                           "of the edition of record; no default)")

    def test_annexf_each_required_key_is_enforced_per_pump_type(self):
        for pump_type, keys in (("horizontal", self.HORIZONTAL_KEYS), ("vertical-inline", self.VERTICAL_KEYS)):
            for key in keys:
                base = self._annexf_base(pump_type)
                del base["annexF"][key]
                with self.assertRaises(ValueError, msg=f"{pump_type} {key}") as cm:
                    run(ANNEXF_MODULE, base)
                self.assertTrue(str(cm.exception).startswith(f"annexF.{key} is required"), str(cm.exception))
                self.assertTrue(str(cm.exception).endswith("no default)"), str(cm.exception))

    def test_annexf_keys_of_the_other_pump_type_are_not_required(self):
        base = self._annexf_base("horizontal")
        base["annexF"] = {k: annexf()[k] for k in self.HORIZONTAL_KEYS}
        run(ANNEXF_MODULE, base)
        vbase = self._annexf_base("vertical-inline")
        vbase["annexF"] = {k: annexf()[k] for k in self.VERTICAL_KEYS}
        run(ANNEXF_MODULE, vbase)

    def test_annexf_non_positive_or_non_numeric_constant_is_rejected(self):
        for pump_type, keys in (("horizontal", self.HORIZONTAL_KEYS), ("vertical-inline", self.VERTICAL_KEYS)):
            for key in keys:
                for bad in (0, -1.5):
                    base = self._annexf_base(pump_type)
                    base["annexF"][key] = bad
                    with self.assertRaises(ValueError, msg=f"{key}={bad}") as cm:
                        run(ANNEXF_MODULE, base)
                    self.assertTrue(str(cm.exception).startswith(f"annexF.{key} must be > 0"), str(cm.exception))
                base = self._annexf_base(pump_type)
                base["annexF"][key] = "2"
                self._raises(ANNEXF_MODULE, base, f"annexF.{key} must be a number")
        base = self._annexf_base("horizontal")
        base["annexF"] = [1, 2]
        self._raises(ANNEXF_MODULE, base, "annexF must be an object of the Annex F method constants read from the edition of record")

    def test_missing_and_non_numeric_components(self):
        with self.assertRaisesRegex(ValueError, r"applied.Fz is required"):
            run("connections.nozzle-load-check",
                dict(standard="x", applied={k: 1 for k in ("Fx", "Fy", "Mx", "My", "Mz")}, allowable=flat(1)))
        with self.assertRaisesRegex(ValueError, r"allowable.Mx must be a number"):
            run("connections.nozzle-load-check", dict(standard="x", applied=flat(1), allowable=dict(flat(1), Mx="1000")))


class Validate(unittest.TestCase):
    """Pre-flight layer: impossible inputs raise, implausible ones warn. The engine is not touched."""

    CHECK = dict(standard="datasheet", applied=flat(10), allowable=flat(100))

    def _bad(self, module, inputs, fragment):
        with self.assertRaises(ValueError, msg=fragment) as cm:
            nl.validate(module, inputs)
        self.assertIn(fragment, str(cm.exception))

    def test_valid_inputs_pass_without_warnings(self):
        self.assertEqual(nl.validate("connections.nozzle-load-check", self.CHECK), [])
        self.assertEqual(nl.validate("connections.nema-sm23", HandDerivedPorted.SM23), [])
        self.assertEqual(nl.validate("equipment.api650-annexp-ordinates", HandDerivedAnnexP.INP), [])

    def test_unknown_top_level_field(self):
        self._bad("connections.nozzle-load-check", dict(self.CHECK, alowable=flat(1)), "unknown input field(s) 'alowable'")
        self._bad("connections.nema-sm23", dict(HandDerivedPorted.SM23, Coefficient=700), "unknown input field(s) 'Coefficient'")
        self._bad("equipment.pvp2011-allowables", dict(HandDerivedPvp.BASE, t=0.25), "unknown input field(s) 't'")

    def test_unknown_key_inside_a_load_set(self):
        self._bad("connections.nozzle-load-check", dict(self.CHECK, applied=dict(flat(10), FX=1)), "unknown key(s) 'FX' in applied")
        self._bad("connections.api610-annexf", dict(pumpType="horizontal", units="USC", suctionPosition=dict(x=0, y=0, Z=0)),
                  "unknown key(s) 'Z' in suctionPosition")
        self._bad("equipment.nozzle-load-sum", dict(standard="x", nozzles=[dict(flat(1), Mq=2)], limits=flat(1)),
                  "unknown key(s) 'Mq' in nozzles[0]")
        self._bad(ANNEXF_MODULE, dict(pumpType="horizontal", units="USC", annexF=dict(annexf(), kSigmaa=1)),
                  "unknown key(s) 'kSigmaa' in annexF")

    def test_unknown_module(self):
        self._bad("connections.nozzle-load", {}, "unknown module")

    def test_standard_label_required_on_check_and_sum(self):
        self._bad("connections.nozzle-load-check", {k: v for k, v in self.CHECK.items() if k != "standard"}, "standard is required")
        self._bad("equipment.nozzle-load-sum", dict(nozzles=[flat(1)], limits=flat(1)), "standard is required")

    def test_negative_or_zero_size(self):
        self._bad("connections.nema-sm23", dict(HandDerivedPorted.SM23, NPS=-6), "NPS must be > 0")
        self._bad("connections.nema-sm23", dict(HandDerivedPorted.SM23, NPS=0), "NPS must be > 0")
        self._bad("connections.nema-sm23", dict(HandDerivedPorted.SM23, coefficient=-700), "coefficient must be > 0")
        self._bad("connections.nema-sm23", dict(HandDerivedPorted.SM23, coefficient=0), "coefficient must be > 0")

    def test_sm23_coefficient_is_not_judged_against_a_set_of_values(self):
        # The coefficient is whatever the user read from the governing equation; any positive value is accepted silently.
        for coef in (350, 700, 1234.5):
            self.assertEqual(nl.validate("connections.nema-sm23", dict(HandDerivedPorted.SM23, coefficient=coef)), [])

    def test_owner_factor_range(self):
        self._bad("connections.nozzle-load-check", dict(self.CHECK, ownerFactor=1.1), "ownerFactor must be in (0, 1]")
        self._bad("connections.nozzle-load-check", dict(self.CHECK, ownerFactor=0), "ownerFactor must be in (0, 1]")

    def test_api650_geometry(self):
        self._bad("equipment.api650-annexp-ordinates", dict(HandDerivedAnnexP.INP, L=400), "L must exceed a")
        self._bad("equipment.api650-annexp-ordinates", dict(HandDerivedAnnexP.INP, t=20000), "t must be less than R")
        self._bad("equipment.api650-annexp-ordinates", dict(HandDerivedAnnexP.INP, YF=-1), "YF must be > 0")

    def test_pvp_enums(self):
        self._bad("equipment.pvp2011-allowables", dict(HandDerivedPvp.BASE, table="3"), 'table must be "1A", "1B" or "2"')
        self._bad("equipment.pvp2011-allowables", dict(HandDerivedPvp.BASE, material="steel"), "material must be one of")
        self._bad("equipment.pvp2011-allowables", dict(HandDerivedPvp.BASE, loadsPrimary="yes"), "loadsPrimary must be true or false")

    def test_sum_multiplier_below_one_warns(self):
        w = nl.validate("equipment.nozzle-load-sum", dict(standard="x", nozzles=[flat(1)], limits=flat(1), multiplier=0.5))
        self.assertTrue(any("below 1" in x for x in w))


class CommandLine(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8")

    def test_unhashable_table_exits_2(self):
        for bad in (["1A"], {"a": 1}):
            r = self._run("equipment.pvp2011-allowables", "--input", json.dumps(dict(HandDerivedPvp.BASE, table=bad)))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertIn("table must be", r.stderr)

    def test_vertical_inline_rejects_owner_factor(self):
        inp = dict(pumpType="vertical-inline", units="USC", suctionApplied=six(), dischargeApplied=six(),
                   suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf(),
                   suctionBore=dict(Do=6.625, Di=6.065), dischargeBore=dict(Do=4.5, Di=4.026))
        r = self._run("connections.api610-annexf", "--input", json.dumps(dict(inp, ownerFactor=0.5)))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("principal-stress limit", r.stderr)
        r = self._run("connections.api610-annexf", "--input", json.dumps(dict(inp, ownerFactor=1)))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_annexf_exits_2_naming_the_key(self):
        inp = dict(pumpType="horizontal", units="USC", suctionApplied=six(), dischargeApplied=six(),
                   suctionAllowable=flat(1000), dischargeAllowable=flat(1000),
                   suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
        r = self._run(ANNEXF_MODULE, "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("annexF.componentMultiple is required", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1)
        bad = dict(inp, annexF=dict(annexf(), centreMyFactor=0))
        r = self._run(ANNEXF_MODULE, "--input", json.dumps(bad))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("annexF.centreMyFactor must be > 0", r.stderr)

    def test_sm23_zero_coefficient_exits_2(self):
        r = self._run("connections.nema-sm23", "--input", json.dumps(dict(HandDerivedPorted.SM23, coefficient=0)))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("coefficient must be > 0", r.stderr)

    def test_annexf_constants_are_echoed_as_user_supplied(self):
        inp = dict(pumpType="horizontal", units="USC", suctionApplied=six(), dischargeApplied=six(),
                   suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf(),
                   suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
        env = cli_run(ANNEXF_MODULE, inp)
        self.assertIn("annexF", env["user_supplied"])
        self.assertEqual(env["inputs"]["annexF"], annexf())
        self.assertIn("annexF", nl.USER_SUPPLIED[ANNEXF_MODULE])
        self.assertTrue(any("annexF" in w for w in env["warnings"]))

    def test_horizontal_factor_reword_of_base_range_note(self):
        inp = dict(pumpType="horizontal", units="USC", suctionApplied=six(0, 100, 0, 0, 0, 0), dischargeApplied=six(),
                   suctionAllowable=flat(1000), dischargeAllowable=flat(1000), annexF=annexf(),
                   suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0), ownerFactor=0.5)
        env = cli_run("connections.api610-annexf", inp)
        self.assertFalse(any("within the base Table 5 range" in w for w in env["warnings"]))
        self.assertTrue(any("factored Table 5 range" in w for w in env["warnings"]))

    def test_huge_magnitude_exits_2_not_a_traceback(self):
        inp = dict(standard="datasheet", applied=six(1e30), allowable=flat(1000))
        r = self._run("connections.nozzle-load-check", "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("input error", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_list_text(self):
        r = self._run("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        for module in nl.REGISTRY:
            self.assertIn(module, r.stdout)
        for name in ("coefficient", "ownerFactor", "multiplier", "S_vessel", "YF", "lowerRow"):
            self.assertIn(name, r.stdout)

    def test_run_each_fixture_case_through_the_cli(self):
        for module in PORTED:
            case = parity.load(module)["cases"][0]
            inp = fixture_input(module, case)
            if module == "connections.nozzle-load-check":
                self.assertIn("standard", inp)
            r = self._run(module, "--input", json.dumps(inp))
            self.assertEqual(r.returncode, 0, r.stderr)
            env = json.loads(r.stdout)
            self.assertEqual(env["module"], module)
            self.assertEqual(env["status"], case["status"])
            self.assertEqual(set(env), {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied"})
            self.assertEqual(env["citation"], nl.CITATIONS[module])
            self.assertEqual(env["inputs"], inp)
            for key, want in case["expect"].items():
                if isinstance(want, (int, float)):
                    self.assertAlmostEqual(env["output"][key], want, delta=case["tol"], msg=f"{module} {key}")
                else:
                    self.assertEqual(env["output"][key], want, f"{module} {key}")

    def test_user_supplied_is_listed(self):
        r = self._run("connections.nema-sm23", "--input", json.dumps(HandDerivedPorted.SM23))
        self.assertEqual(json.loads(r.stdout)["user_supplied"], ["coefficient"])

    def test_worked_example_runs(self):
        path = os.path.join(SCRIPTS, "examples", "vessel-nozzle-pvp2011.json")
        r = self._run("equipment.pvp2011-allowables", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["status"], "na")
        # T = 0.1875 on a 0.25 basis = 0.5625; S_vessel 14,100 / 18,800 = 0.75; owner 0.5 -> 0.2109375
        self.assertAlmostEqual(env["output"]["totalFactor"], 0.5625 * 0.75 * 0.5, delta=1e-5)
        self.assertEqual(env["output"]["derived"]["Fx"], round(1000 * 0.5625 * 0.75 * 0.5, 3))

    def test_input_file_with_bom(self):
        path = os.path.join(ROOT, "tests", "_nozzle_load_cli_input.json")
        try:
            with open(path, "w", encoding="utf-8-sig") as fh:
                json.dump(HandDerivedPorted.SM23, fh)
            r = self._run("connections.nema-sm23", "--input-file", path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_owner_factor_note_reaches_the_envelope(self):
        r = self._run("connections.nema-sm23", "--input", json.dumps(dict(HandDerivedPorted.SM23, ownerFactor=0.5)))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["output"]["allowable"], 1500.0)
        self.assertTrue(any("ownerFactor 0.5 applied" in w for w in env["warnings"]))

    def test_unknown_field_exits_2(self):
        bad = dict(HandDerivedPorted.SM23, Coefficient=700)
        r = self._run("connections.nema-sm23", "--input", json.dumps(bad))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("unknown input field", r.stderr)

    def test_negative_nps_or_de_exits_2(self):
        for nps in (-4, 0):
            r = self._run("connections.nema-sm23", "--input", json.dumps(dict(HandDerivedPorted.SM23, NPS=nps)))
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1)

    def test_missing_coefficient_exits_2(self):
        r = self._run("connections.nema-sm23", "--input", json.dumps(dict(NPS=6, applied=flat(1))))
        self.assertEqual(r.returncode, 2)
        self.assertIn("coefficient is required", r.stderr)

    def test_bad_input_exits_2_with_one_line(self):
        good = dict(standard="x", applied=flat(1), allowable=flat(10))
        bad = [
            ("connections.nozzle-load-check", "--input", "{not json"),
            ("connections.nozzle-load-check", "--input", "[1, 2]"),
            ("connections.nozzle-load-check", "--input", json.dumps(dict(good, allowable=dict(flat(10), Fz=0)))),
            ("connections.nozzle-load-check", "--input", json.dumps({"standard": "x"})),
            ("connections.nozzle-load-check",),
            ("connections.nozzle-load-check", "--input", "{}", "--input-file", "x.json"),
            ("connections.no-such-module", "--input", "{}"),
            ("connections.nozzle-load-check", "--input-file", os.path.join(ROOT, "tests", "does-not-exist.json")),
        ]
        for args in bad:
            r = self._run(*args)
            self.assertEqual(r.returncode, 2, f"{args}: {r.stdout!r} {r.stderr!r}")
            self.assertEqual(r.stdout, "", args)
            self.assertEqual(len(r.stderr.strip().splitlines()), 1, f"{args}: {r.stderr!r}")


class SkillContent(unittest.TestCase):
    """Guards on the shipped SKILL.md, references and script."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(CLI, encoding="utf-8") as fh:
            cls.script = fh.read()
        cls.refs = {}
        for path in glob.glob(os.path.join(SKILL, "references", "*.md")):
            with open(path, encoding="utf-8") as fh:
                cls.refs[os.path.basename(path)] = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: nozzle-load\ndescription: "))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description", "compatibility"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 1024)
        for term in ("nozzle load", "API 610", "API 617", "API 650", "API 660", "API 661", "API 560", "NEMA SM-23",
                     "PIP RECE002", "pressure vessel", "allowable"):
            self.assertIn(term.lower(), desc.lower(), term)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)

    def test_required_sections_present(self):
        for heading in ("## Scope", "## Step 0", "## Running the tool", "## Output format", "## Before you hand it over",
                        "## Copyright boundary", "## Hand-offs", "## Related tools", "engineer of record",
                        "ASSUMED", "run `python"):
            self.assertIn(heading.lower(), self.text.lower(), heading)
        for module in nl.REGISTRY:
            self.assertIn(module, self.text, module)
        for sibling in ("pressure-design", "stress-screening", "load-case-builder", "bolted-flange"):
            self.assertIn(sibling, self.text, sibling)

    def test_every_reference_is_linked_and_the_required_ones_exist(self):
        required = {"equipment-criteria.md", "pvp2011-method.md", "axes-and-load-cases.md", "owner-practices.md",
                    "tool-reference.md", "rejection-checklist.md"}
        self.assertEqual(required - set(self.refs), set())
        for name in self.refs:
            self.assertIn(f"references/{name}", self.text, name)

    def test_rejection_checklist_has_at_least_fourteen_numbered_items(self):
        items = re.findall(r"^\d+\.\s", self.refs["rejection-checklist.md"], flags=re.M)
        self.assertGreaterEqual(len(items), 14)

    def test_sm23_coefficients_are_named_with_their_equations(self):
        for fragment in ("E.1b", "I.1b", "D.1b", "API 617", "API 611", "API 612"):
            self.assertIn(fragment, self.text, fragment)
        self.assertIn("coefficient", self.text)

    def test_annexf_constants_are_documented_as_inputs(self):
        for key in ("componentMultiple", "resultantDenominator", "interactionLimit", "centreForceFactor",
                    "centreMyFactor", "sigmaPLimit", "kSigma", "kTau"):
            self.assertIn(key, self.text, key)
            self.assertIn(key, self.refs["tool-reference.md"], key)
        self.assertIn("User-supplied values table", self.text)

    def test_no_api_method_constant_ships_in_the_skill(self):
        # API 610 Annex F constants and the API 617 / 611 / 612 coefficients are user-supplied inputs.
        banned = re.compile(r"\b927\b|\b5950\b|\b10,?200\b|\b5,?100\b|API610_(?!UNIT_CONV)")
        for label, text in [("SKILL.md", self.text), ("nozzle_load.py", self.script)] + sorted(self.refs.items()):
            for ln in text.splitlines():
                self.assertIsNone(banned.search(ln), f"{label}: {ln.strip()[:120]}")

    def test_calc_sheet_template_and_run_rules(self):
        self.assertIn("# Nozzle Load Evaluation", self.text)
        self.assertIn("Every number you state comes from a script run", self.text)
        self.assertIn("scripts/nozzle_load.py", self.text)
        self.assertIn("do not change into the skill folder", self.text.lower())
        self.assertIn("job.json", self.text)

    def test_python_39_syntax_gate(self):
        import ast
        ast.parse(self.script, CLI, feature_version=(3, 9))
        self.assertIn("from __future__ import annotations", self.script)
        self.assertNotRegex(self.script, r"\bmatch\s+\w+\s*:")
        self.assertNotIn("removeprefix", self.script)

    def test_script_is_ascii(self):
        bad = [ln for ln in self.script.splitlines() if any(ord(c) > 127 for c in ln)]
        self.assertEqual(bad, [])

    def test_no_table_rows_in_the_skill_files(self):
        # Three or more comma-grouped thousands in one table cell run is the signature of a pasted table row.
        row = re.compile(r"(?:\b\d{1,2},\d{3}\b[\s|]+){3,}")
        for label, text in [("SKILL.md", self.text), ("nozzle_load.py", self.script)] + sorted(self.refs.items()):
            for ln in text.splitlines():
                self.assertIsNone(row.search(ln), f"{label}: {ln.strip()}")

    def test_no_nomogram_or_curve_values_and_no_pasted_equation_for_figure_data(self):
        for label, text in [("SKILL.md", self.text)] + sorted(self.refs.items()):
            self.assertNotRegex(text, r"\bY[FLC]\s*=\s*\d", f"{label}: a Y coefficient value")

    def test_api610_6_5_3_exception_is_stated_where_2x_is_discussed(self):
        for label, text in (("SKILL.md", self.text), ("equipment-criteria.md", self.refs["equipment-criteria.md"]),
                            ("rejection-checklist.md", self.refs["rejection-checklist.md"])):
            self.assertIn("6.5.3", text, label)
            self.assertIn("OH3 / OH6", text, label)

    def test_annexp_yl_yc_discrepancy_is_flagged(self):
        self.assertIn("some editions print YL in P.2.7.2.3", self.refs["equipment-criteria.md"])

    def test_owner_practices_routes_pnc00004_clauses(self):
        text = self.refs["owner-practices.md"]
        for clause in ("3.3.1", "3.3.2", "3.3.4", "3.3.5", "3.3.6", "3.2.14.3"):
            self.assertIn(clause, text, clause)
        self.assertIn("layout-stage estimate only", text)

    def test_pvp_reference_cites_the_papers_printed_equations_and_the_bound(self):
        text = self.refs["pvp2011-method.md"]
        self.assertIn("prints eq. (1)", text)
        self.assertIn("proportionalBound", text)
        self.assertIn("effective pad thickness", text)

    def test_references_say_what_is_image_only(self):
        self.assertIn("image", self.refs["equipment-criteria.md"].lower())
        self.assertIn("printed page", self.refs["equipment-criteria.md"].lower())

    def test_pvp_reference_states_the_limits(self):
        text = self.refs["pvp2011-method.md"]
        for fragment in ("Establishing Allowable Nozzle Loads", "PVP2011-57100", "650", "320", "(T / basis)", "18,800", "17,100",
                         "WRC 537", "4.5.15", "50%"):
            self.assertIn(fragment, text, fragment)


if __name__ == "__main__":
    unittest.main()
