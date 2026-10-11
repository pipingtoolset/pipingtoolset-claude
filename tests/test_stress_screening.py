"""Regression tests for the stress-screening skill.

Standard library only (unittest):

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-screening")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "stress_screening.py")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import content_guard  # noqa: E402
import parity  # noqa: E402
import stress_screening as ss  # noqa: E402

EXPECTED_CALC_CORE = [
    "noncode.pipe-section",
    "piping.displacement-stress",
    "piping.fatigue-factor",
    "piping.sustained-stress",
    "supports.max-spring-rate",
    "supports.spring-variability",
]
NEW_CHECKS = ["screen.flexibility-exemption", "screen.support-span"]


class Rounding(unittest.TestCase):

    def test_half_up_on_exact_decimal_halves(self):
        self.assertEqual(ss.round_half_up(1.005, 2), 1.01)     # float-safe via repr
        self.assertEqual(ss.round_half_up(2.5, 0), 3.0)
        self.assertEqual(ss.round_half_up(-2.5, 0), -3.0)      # away from zero
        self.assertEqual(ss.round_half_up(0.125, 2), 0.13)

    def test_non_finite_passes_through(self):
        self.assertTrue(math.isinf(ss.round_half_up(float("inf"), 3)))
        self.assertTrue(math.isnan(ss.round_half_up(float("nan"), 3)))


class CalcCoreParity(unittest.TestCase):
    """Each ported function against the vendored calc-core fixtures."""

    def _check(self, module: str):
        fails = parity.run_fixture(ss.REGISTRY, module)
        self.assertEqual(fails, [], "\n".join(fails))

    def test_manifest_lists_exactly_the_six_ported_modules(self):
        self.assertEqual(parity.modules_for("stress-screening"), EXPECTED_CALC_CORE)

    def test_registry_has_all_eight_ids(self):
        self.assertEqual(sorted(ss.REGISTRY), sorted(EXPECTED_CALC_CORE + NEW_CHECKS))
        self.assertEqual(sorted(ss.CITATIONS), sorted(ss.REGISTRY))
        self.assertEqual(sorted(ss.USER_SUPPLIED), sorted(ss.REGISTRY))
        for mid, fn in ss.REGISTRY.items():
            self.assertTrue(callable(fn), mid)

    def test_displacement_stress(self):
        self._check("piping.displacement-stress")

    def test_sustained_stress(self):
        self._check("piping.sustained-stress")

    def test_fatigue_factor(self):
        self._check("piping.fatigue-factor")

    def test_spring_variability(self):
        self._check("supports.spring-variability")

    def test_max_spring_rate(self):
        self._check("supports.max-spring-rate")

    def test_pipe_section(self):
        self._check("noncode.pipe-section")

    def test_every_manifest_module_is_registered(self):
        for module in parity.modules_for("stress-screening"):
            self.assertIn(module, ss.REGISTRY)
            self.assertEqual(parity.load(module)["module"], module)


class PortedBehaviour(unittest.TestCase):
    """Error conditions and warnings that mirror calc-core."""

    def test_displacement_stress_errors(self):
        base = dict(ii=2.0, io=1.5, Mi=1000, Mo=500, Mt=0, Z=8.0, Sc=20000, Sh=17000, f=1)
        for bad in ({"Z": 0}, {"ii": 0.9}, {"io": 0.5}, {"Sc": 0}, {"Sh": -1}, {"f": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                ss.displacement_stress({**base, **bad})

    def test_displacement_stress_axial_term_only_adds(self):
        base = dict(ii=2.0, io=1.5, Mi=1000, Mo=500, Mt=300, Z=8.0, Sc=20000, Sh=17000, f=1)
        a = ss.displacement_stress(base)["output"]["SE"]
        b = ss.displacement_stress({**base, "Sa": 500})["output"]["SE"]
        c = ss.displacement_stress({**base, "Sa": -500})["output"]["SE"]
        self.assertGreater(b, a)
        self.assertEqual(b, c)  # |Sa|

    def test_sustained_errors_and_unknown_method_warning(self):
        base = dict(method="sqrt", P=100, D=4.5, t=0.2, Sb=1000, St=100, Socc=500, Sh=15000, k=1.33)
        with self.assertRaises(ValueError):
            ss.sustained_stress({**base, "D": 0})
        with self.assertRaises(ValueError):
            ss.sustained_stress({**base, "k": 0})
        r = ss.sustained_stress({**base, "method": "sqroot"})
        self.assertTrue(r["warnings"])
        self.assertEqual(r["output"], ss.sustained_stress(base)["output"])  # treated as sqrt

    def test_additive_adds_occasional_directly(self):
        r = ss.sustained_stress(dict(method="additive", P=0, D=4.5, t=0.2, Sb=1000, St=200, Socc=300, Sh=15000, k=1.15))
        self.assertEqual(r["output"]["SL"], 1200)
        self.assertEqual(r["output"]["SLocc"], 1500)

    def test_fatigue_errors(self):
        with self.assertRaises(ValueError):
            ss.fatigue_factor({"N": 1000, "fmax": 1, "equation": "b31-1999"})
        with self.assertRaises(ValueError):
            ss.fatigue_factor({"N": 1000, "fmax": 0})
        with self.assertRaises(ValueError):
            ss.fatigue_factor({"N": 0, "fmax": 1})
        with self.assertRaises(ValueError):
            ss.fatigue_factor({"N": 1, "fmax": 1, "sets": [{"N": 10, "r": 1.5}]})
        with self.assertRaises(ValueError):
            ss.fatigue_factor({"N": 1, "fmax": 1, "sets": [{"N": 10, "r": 0}]})

    def test_fatigue_floor_warning_and_legacy_cap_warning(self):
        r = ss.fatigue_factor({"N": 1e12, "fmax": 1})
        self.assertEqual(r["output"]["f"], 0.15)
        self.assertTrue(any("floored" in w for w in r["warnings"]))
        r2 = ss.fatigue_factor({"N": 100, "fmax": 1.2})
        self.assertTrue(any("B31.1 caps f at 1.0" in w for w in r2["warnings"]))

    def test_spring_and_section_errors(self):
        with self.assertRaises(ValueError):
            ss.spring_variability({"hotLoad": 0, "springRate": 1, "travel": 1, "limit": 25})
        with self.assertRaises(ValueError):
            ss.spring_variability({"hotLoad": 100, "springRate": 1, "travel": 1, "limit": 0})
        with self.assertRaises(ValueError):
            ss.max_spring_rate({"hotLoad": 100, "travel": 0, "variabilityLimit": 0.25})
        with self.assertRaises(ValueError):
            ss.max_spring_rate({"hotLoad": 100, "travel": 1, "variabilityLimit": 1})
        with self.assertRaises(ValueError):
            ss.pipe_section({"OD": 4, "t": 2})

    def test_spring_limits_use_different_units(self):
        """Percent in spring-variability, fraction in max-spring-rate (a calc-core trait)."""
        m = ss.max_spring_rate({"hotLoad": 1000, "travel": 2, "variabilityLimit": 0.25})["output"]
        v = ss.spring_variability({"hotLoad": 1000, "springRate": m["maxRate"], "travel": 2, "limit": 25})
        self.assertEqual(v["output"]["variabilityPct"], 25.0)
        self.assertEqual(v["status"], "pass")

    def test_missing_and_non_numeric_inputs_raise_value_error(self):
        with self.assertRaises(ValueError):
            ss.pipe_section({"OD": 4})
        with self.assertRaises(ValueError):
            ss.pipe_section({"OD": "4", "t": 0.2})
        with self.assertRaises(ValueError):
            ss.pipe_section({"OD": True, "t": 0.2})


class FatigueEditionSwitch(unittest.TestCase):

    def test_forms_differ_at_high_cycles_and_are_labelled(self):
        old = ss.fatigue_factor({"N": 22500, "fmax": 1.2, "equation": "legacy"})
        new = ss.fatigue_factor({"N": 22500, "fmax": 1.2, "equation": "b313-2022"})
        self.assertAlmostEqual(old["output"]["f"], 6 * 22500 ** -0.2, places=5)
        self.assertAlmostEqual(new["output"]["f"], 20 * 22500 ** -0.333, places=5)
        self.assertLess(new["output"]["f"], old["output"]["f"])
        self.assertIn("6·N^(−0.2)", old["output"]["equation"])
        self.assertIn("20·N^(−0.333)", new["output"]["equation"])

    def test_default_is_legacy(self):
        """The ENGINE default (kept for parity); the CLI layer requires the equation explicitly."""
        self.assertEqual(ss.fatigue_factor({"N": 5000, "fmax": 1}), ss.fatigue_factor({"N": 5000, "fmax": 1, "equation": "legacy"}))

    def test_equivalent_cycle_exponent_follows_the_form(self):
        sets = [{"N": 1000, "r": 1}, {"N": 8000, "r": 0.5}]
        self.assertEqual(ss.fatigue_factor({"N": 1, "sets": sets, "fmax": 1})["output"]["NE"], 1000 + 8000 * 0.5 ** 5)
        self.assertEqual(ss.fatigue_factor({"N": 1, "sets": sets, "fmax": 1, "equation": "b313-2022"})["output"]["NE"], 1000 + 8000 * 0.5 ** 3)

    def test_cap_is_applied_before_the_floor(self):
        self.assertEqual(ss.fatigue_factor({"N": 50, "fmax": 1.2, "equation": "b313-2022"})["output"]["f"], 1.2)
        self.assertEqual(ss.fatigue_factor({"N": 50, "fmax": 1.0, "equation": "b313-2022"})["output"]["f"], 1.0)

    def test_resolver_selects_the_form_by_code_and_edition(self):
        self.assertEqual(ss.resolve_fatigue_equation("B31.3", 2020), "legacy")
        self.assertEqual(ss.resolve_fatigue_equation("B31.3", 2022), "b313-2022")
        self.assertEqual(ss.resolve_fatigue_equation("B31.3", "2024"), "b313-2022")
        for yr in (2016, 2022, 2024):
            self.assertEqual(ss.resolve_fatigue_equation("B31.1", yr), "legacy")


class SifSourceResolver(unittest.TestCase):

    def test_b313_editions(self):
        self.assertEqual(ss.resolve_sif_source("B31.3", 2018), "ASME B31.3 Appendix D")
        self.assertEqual(ss.resolve_sif_source("B31.3", 2016), "ASME B31.3 Appendix D")
        for yr in (2020, 2022, 2024):
            self.assertIn("B31J", ss.resolve_sif_source("B31.3", yr))
            self.assertIn("deleted", ss.resolve_sif_source("B31.3", yr))

    def test_b311_editions(self):
        self.assertEqual(ss.resolve_sif_source("B31.1", 2020), "ASME B31.1 Mandatory Appendix D")
        r22 = ss.resolve_basis("B31.1", 2022)
        self.assertIn("Appendix D", r22["sif_source"])
        self.assertEqual(r22["sif_documents_permitted"], ["ASME B31.1 Mandatory Appendix D", "ASME B31J"])
        r24 = ss.resolve_basis("B31.1", 2024)
        self.assertIn("B31J", r24["sif_source"])
        self.assertEqual(r24["sif_documents_permitted"], ["ASME B31J"])

    def test_tee_transposition_warning_always_present(self):
        for code, yr in (("B31.1", 2024), ("B31.3", 2018)):
            self.assertTrue(any("transposed" in n for n in ss.resolve_basis(code, yr)["notes"]))

    def test_occasional_and_asd_positions(self):
        b3 = ss.resolve_basis("B31.3", 2022)
        self.assertIn("1.33", b3["occasional_allowable"])
        self.assertIn("ASSUMED", b3["asd_reduction"])
        b1 = ss.resolve_basis("B31.1", 2024)
        self.assertIn("1.15", b1["occasional_allowable"])
        self.assertIn("1.20", b1["occasional_allowable"])
        self.assertIn("without the ASD reduction", b1["asd_reduction"])
        self.assertIn("1.0", b1["f_cap_rule"])

    def test_bad_input(self):
        for args in (("B31.4", 2020), ("B31.3", "abc"), ("B31.3", 1800), ("B31.3", True)):
            with self.assertRaises(ValueError, msg=str(args)):
                ss.resolve_basis(*args)

    def test_resolver_output_carries_running_text_limits_only(self):
        blob = json.dumps(ss.resolve_basis("B31.3", 2024))
        for token in ("1.33", "1.20", "700", "75"):   # limits the code states in running text
            self.assertIn(token, blob)


class HandFixtures(unittest.TestCase):
    """Checks with no calc-core module. Fixtures carry hand arithmetic in 'derivation'."""

    def _check(self, module: str):
        fails = parity.run_fixture(ss.REGISTRY, module, hand=True)
        self.assertEqual(fails, [], "\n".join(fails))

    def _shape(self, module: str):
        fx = parity.load(module, hand=True)
        self.assertEqual(fx["module"], module)
        self.assertGreaterEqual(len(fx["cases"]), 3)
        statuses = {c["status"] for c in fx["cases"]}
        self.assertIn("pass", statuses)
        self.assertIn("fail", statuses)
        for c in fx["cases"]:
            self.assertTrue(c.get("derivation"), "every hand case carries its arithmetic")
            self.assertIn("expect", c)
            self.assertIn("tol", c)

    def test_support_span_fixture(self):
        self._shape("screen.support-span")
        self._check("screen.support-span")

    def test_flexibility_exemption_fixture(self):
        self._shape("screen.flexibility-exemption")
        self._check("screen.flexibility-exemption")


class SupportSpan(unittest.TestCase):

    BASE = dict(w=24, E=1.0e7, S_allow=3000, delta_allow=0.25, Z=10.0, I=40.0)

    @staticmethod
    def _support_moments(n: int):
        """Hogging support moments / wL^2 for n equal spans (three-moment theorem)."""
        m = n - 1
        A = [[0.0] * m for _ in range(m)]
        b = [0.5] * m
        for i in range(m):
            A[i][i] = 4.0
            if i > 0:
                A[i][i - 1] = 1.0
            if i < m - 1:
                A[i][i + 1] = 1.0
        for i in range(1, m):                       # Thomas-style elimination
            f = A[i][i - 1] / A[i - 1][i - 1]
            A[i][i] -= f * A[i - 1][i]
            b[i] -= f * b[i - 1]
        M = [0.0] * m
        M[-1] = b[-1] / A[-1][-1]
        for i in range(m - 2, -1, -1):
            M[i] = (b[i] - A[i][i + 1] * M[i + 1]) / A[i][i]
        return [0.0] + M + [0.0]

    @classmethod
    def _numeric_beam(cls, n: int):
        """Independent check: n equal spans, UDL, rigid supports. Returns
        (max support moment / wL^2, max span deflection / (wL^4/EI))."""
        if n == 1:
            return 0.0, 5.0 / 384.0
        M = cls._support_moments(n)
        best = 0.0
        for s in range(n):
            Ma, Mb = M[s], M[s + 1]
            for k in range(1, 2000):
                x = k / 2000.0
                d = x * (1 - 2 * x * x + x ** 3) / 24 - Ma * x * (1 - x) * (2 - x) / 6 - Mb * x * (1 - x * x) / 6
                best = max(best, d)
        return max(M), best

    def test_coefficients_match_an_independent_numeric_beam_solution(self):
        c1_simple, c2_simple = self._numeric_beam(1)
        self.assertAlmostEqual(ss.SPAN_COEFFICIENTS["simple"][1], c2_simple, places=12)
        m2, d2 = self._numeric_beam(2)
        self.assertAlmostEqual(1 / ss.SPAN_COEFFICIENTS["two_span"][0], m2, places=12)
        self.assertAlmostEqual(ss.SPAN_COEFFICIENTS["two_span"][1], d2, places=6)
        m3, d3 = self._numeric_beam(3)
        self.assertAlmostEqual(1 / ss.SPAN_COEFFICIENTS["three_span"][0], m3, places=12)
        self.assertAlmostEqual(ss.SPAN_COEFFICIENTS["three_span"][1], d3, places=6)

    def test_continuous_is_the_envelope_over_two_to_eight_spans(self):
        c1, c2 = ss.SPAN_COEFFICIENTS["continuous"]
        for n in range(2, 9):
            m, d = self._numeric_beam(n)
            self.assertLessEqual(m, 1 / c1 + 1e-12, f"moment, n={n}")
            self.assertLessEqual(d, c2 + 1e-6, f"deflection, n={n}")

    def test_fixed_matches_interior_span_of_a_long_run(self):
        # Interior span of a long run: support moment -> wL^2/12 as n grows.
        M = self._support_moments(60)
        self.assertAlmostEqual(M[30], 1 / 12, places=6)

    def test_governing_is_the_smaller_span(self):
        for end in ss.SPAN_END_CONDITIONS:
            o = ss.support_span({**self.BASE, "end_condition": end})["output"]
            self.assertEqual(o["L_max_ft"], min(o["L_bending_ft"], o["L_deflection_ft"]))
            self.assertEqual(o["governing"], "bending" if o["L_bending_ft"] <= o["L_deflection_ft"] else "deflection")

    def test_default_end_condition_is_the_continuous_envelope_and_warns(self):
        r = ss.support_span(self.BASE)
        self.assertEqual(r["output"]["end_condition"], "continuous")
        self.assertTrue(any("envelope" in w for w in r["warnings"]))

    def test_actual_span_at_the_limit_passes_and_just_over_fails(self):
        lim = ss.support_span(self.BASE)["output"]["L_max_ft"]
        self.assertEqual(ss.support_span({**self.BASE, "L_actual_ft": lim})["status"], "pass")
        self.assertEqual(ss.support_span({**self.BASE, "L_actual_ft": lim + 0.5})["status"], "fail")

    def test_stress_and_sag_at_the_governing_span_hit_the_allowables(self):
        r = ss.support_span({**self.BASE, "end_condition": "simple"})["output"]
        at = ss.support_span({**self.BASE, "end_condition": "simple", "L_actual_ft": r["L_max_ft"]})["output"]
        self.assertAlmostEqual(at["sag_at_actual_in"], 0.25, delta=0.002)   # deflection governs
        self.assertLessEqual(at["bending_stress_at_actual_psi"], 3000)

    def test_section_from_od_and_t(self):
        a = ss.support_span({"w": 24, "E": 1.0e7, "S_allow": 3000, "delta_allow": 0.25, "OD": 6.625, "t": 0.28})["output"]
        sec = ss.pipe_section({"OD": 6.625, "t": 0.28})["output"]
        self.assertEqual((a["Z"], a["I"]), (sec["Z"], sec["I"]))

    def test_pressure_stress_shortens_the_bending_span(self):
        a = ss.support_span(self.BASE)["output"]["L_bending_ft"]
        b = ss.support_span({**self.BASE, "S_pressure": 1000})["output"]["L_bending_ft"]
        self.assertAlmostEqual(b / a, math.sqrt(2000 / 3000), places=3)

    def test_errors(self):
        for bad in ({"w": 0}, {"E": -1}, {"S_allow": 0}, {"delta_allow": 0}, {"end_condition": "pinned"},
                    {"S_pressure": 3000}, {"S_pressure": -1}, {"L_actual_ft": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                ss.support_span({**self.BASE, **bad})
        for key in ("Z", "I"):
            with self.assertRaises(ValueError):
                ss.support_span({k: v for k, v in self.BASE.items() if k != key})


class FlexibilityExemption(unittest.TestCase):

    BASE = dict(D=4.5, y=1.2, L=100, U=60, SA=30000, Ea=1.0e7,
                fixation_points=2, intermediate_restraints=False, uniform_size=True)

    def test_limitations_are_always_reported(self):
        w = " ".join(ss.flexibility_exemption(self.BASE)["warnings"])
        self.assertIn("no general proof", w)
        self.assertIn("terminal reactions", w)
        self.assertIn("two points of fixation", w)

    def test_each_disqualifier_defeats_a_passing_ratio(self):
        for bad in ({"fixation_points": 3}, {"intermediate_restraints": True}, {"uniform_size": False}):
            r = ss.flexibility_exemption({**self.BASE, **bad})
            self.assertLessEqual(r["output"]["ratio"], 1.0)
            self.assertEqual(r["status"], "fail", str(bad))
            self.assertFalse(r["output"]["exempt"])
            self.assertTrue(r["output"]["disqualifiers"])

    def test_unstated_disqualifiers_are_flagged_not_assumed(self):
        inp = {k: v for k, v in self.BASE.items() if k not in ("fixation_points", "intermediate_restraints", "uniform_size")}
        r = ss.flexibility_exemption(inp)
        w = " ".join(r["warnings"])
        for name in ("fixation_points", "intermediate_restraints", "uniform_size"):
            self.assertIn(name, w)
        self.assertEqual(r["status"], "na")
        self.assertIsNone(r["output"]["exempt"])
        self.assertFalse(r["output"]["disqualifier_inputs_confirmed"])
        self.assertIn("disqualifier inputs not confirmed - cannot conclude exempt", w)

    def test_each_single_omitted_disqualifier_input_gives_na(self):
        for name in ("fixation_points", "intermediate_restraints", "uniform_size"):
            r = ss.flexibility_exemption({k: v for k, v in self.BASE.items() if k != name})
            self.assertEqual((r["status"], r["output"]["exempt"]), ("na", None), name)

    def test_ratio_above_one_fails_even_when_disqualifiers_unconfirmed(self):
        inp = {k: v for k, v in self.BASE.items() if k != "uniform_size"}
        r = ss.flexibility_exemption({**inp, "y": 40.0})
        self.assertGreater(r["output"]["ratio"], 1.0)
        self.assertEqual((r["status"], r["output"]["exempt"]), ("fail", False))

    def test_all_three_confirmed_and_clear_passes(self):
        r = ss.flexibility_exemption(self.BASE)
        self.assertEqual((r["status"], r["output"]["exempt"]), ("pass", True))
        self.assertTrue(r["output"]["disqualifier_inputs_confirmed"])

    def test_k1_is_30_sa_over_ea(self):
        r = ss.flexibility_exemption({**self.BASE, "SA": 21000, "Ea": 2.0e7})
        self.assertAlmostEqual(r["output"]["K1"], 30 * 21000 / 2.0e7, places=6)

    def test_components_give_the_resultant(self):
        a = ss.flexibility_exemption({**self.BASE, "y": 1.0})["output"]
        b = {k: v for k, v in self.BASE.items() if k != "y"}
        b.update(dx=0.6, dy=0.0, dz=0.8)
        self.assertEqual(ss.flexibility_exemption(b)["output"], a)

    def test_errors(self):
        for bad in ({"D": 0}, {"y": 0}, {"L": 60}, {"L": 50}, {"U": 0}, {"SA": 0}, {"Ea": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                ss.flexibility_exemption({**self.BASE, **bad})
        with self.assertRaises(ValueError):
            ss.flexibility_exemption({k: v for k, v in self.BASE.items() if k != "y"})

    def test_pre_2016_b311_gets_a_form_warning(self):
        r = ss.flexibility_exemption({**self.BASE, "code": "B31.1", "edition": 2014})
        self.assertTrue(any("before the 2016" in w for w in r["warnings"]))


class Validate(unittest.TestCase):
    """Pre-flight layer: impossible inputs raise, implausible ones warn."""

    DISP = dict(ii=2.0, io=1.5, Mi=1000, Mo=500, Mt=0, Z=8.0, Sc=20000, Sh=17000, f=1)
    SUS = dict(method="sqrt", P=100, D=4.5, t=0.2, Sb=1000, St=100, Socc=500, Sh=15000, k=1.33)
    FAT = dict(N=5000, fmax=1, equation="legacy")

    def _bad(self, module, inputs, fragment):
        with self.assertRaises(ValueError, msg=fragment) as cm:
            ss.validate(module, inputs)
        self.assertIn(fragment, str(cm.exception))

    def test_valid_inputs_pass_cleanly(self):
        self.assertEqual(ss.validate("piping.displacement-stress", self.DISP), [])
        self.assertEqual(ss.validate("piping.sustained-stress", self.SUS), [])
        self.assertEqual(ss.validate("piping.fatigue-factor", self.FAT), [])

    def test_every_fixture_input_key_is_a_declared_field(self):
        import glob
        for folder in (parity.CALC_CORE, parity.HAND):
            for path in glob.glob(os.path.join(folder, "*.json")):
                if path.endswith("MANIFEST.json"):
                    continue
                with open(path, encoding="utf-8") as fh:
                    fx = json.load(fh)
                if fx["module"] not in ss.REGISTRY:
                    continue
                declared = {f[0] for f in ss.FIELDS[fx["module"]]}
                for case in fx["cases"]:
                    self.assertLessEqual(set(case["input"]), declared, fx["module"])

    def test_unknown_key_rejected(self):
        self._bad("piping.displacement-stress", {**self.DISP, "S_A": 1}, "unknown input field")

    def test_f_above_1_2_is_an_error(self):
        self._bad("piping.displacement-stress", {**self.DISP, "f": 1.3}, "f must be <= 1.2")

    def test_f_above_1_0_warns(self):
        w = ss.validate("piping.displacement-stress", {**self.DISP, "f": 1.1})
        self.assertTrue(any("fm = 1.2" in x for x in w))

    def test_sustained_negative_pressure(self):
        self._bad("piping.sustained-stress", {**self.SUS, "P": -1}, "P must be >= 0")

    def test_sustained_zero_pressure_allowed(self):
        self.assertEqual(ss.validate("piping.sustained-stress", {**self.SUS, "P": 0}), [])

    def test_sustained_wall_at_or_above_half_od(self):
        self._bad("piping.sustained-stress", {**self.SUS, "t": 2.5}, "t must be less than D/2")

    def test_sustained_k_below_range(self):
        self._bad("piping.sustained-stress", {**self.SUS, "k": 0.9}, "k must be in [1.0, 1.33]")

    def test_sustained_k_above_range(self):
        self._bad("piping.sustained-stress", {**self.SUS, "k": 1.5}, "k must be in [1.0, 1.33]")

    def test_sustained_unusual_k_warns(self):
        w = ss.validate("piping.sustained-stress", {**self.SUS, "k": 1.25})
        self.assertTrue(any("usual occasional factors" in x for x in w))

    def test_sustained_usual_k_does_not_warn(self):
        for k in (1.15, 1.20, 1.33):
            self.assertEqual(ss.validate("piping.sustained-stress", {**self.SUS, "k": k}), [], k)

    def test_sustained_negative_bending_warns(self):
        w = ss.validate("piping.sustained-stress", {**self.SUS, "Sb": -5})
        self.assertTrue(any(x.startswith("Sb is negative") for x in w))

    def test_sustained_negative_occasional_warns(self):
        w = ss.validate("piping.sustained-stress", {**self.SUS, "Socc": -5})
        self.assertTrue(any(x.startswith("Socc is negative") for x in w))

    def test_sustained_unrecognised_method_is_an_error(self):
        self._bad("piping.sustained-stress", {**self.SUS, "method": "sqroot"}, "method must be")

    def test_fatigue_equation_required(self):
        self._bad("piping.fatigue-factor", {"N": 5000, "fmax": 1}, "equation is required")

    def test_spring_limit_below_one_warns(self):
        w = ss.validate("supports.spring-variability", dict(hotLoad=1000, springRate=50, travel=6, limit=0.25))
        self.assertTrue(any("percent" in x for x in w))

    def test_spring_limit_in_percent_is_quiet(self):
        self.assertEqual(ss.validate("supports.spring-variability", dict(hotLoad=1000, springRate=50, travel=6, limit=25)), [])


class CommandLine(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")

    def test_list(self):
        r = self._run("list")
        self.assertEqual(r.returncode, 0, r.stderr)
        ids = [ln for ln in r.stdout.splitlines() if ln and not ln[0].isspace() and len(ln.split()) == 1]
        self.assertEqual(sorted(ids), sorted(ss.REGISTRY))

    def test_list_documents_exact_field_names_including_the_proposed_span_key(self):
        out = self._run("list").stdout
        self.assertIn("L_actual_ft", out)
        self.assertIn("PROPOSED span", out)
        self.assertRegex(out, r"\n\s+SA\s")
        for module in ss.REGISTRY:
            for field in ss.FIELDS[module]:
                self.assertIn(field[0], out)

    def test_run_inline_json_envelope(self):
        r = self._run("noncode.pipe-section", "--input", json.dumps({"OD": 6.625, "t": 0.28}))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(set(env), {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied"})
        self.assertEqual(env["module"], "noncode.pipe-section")
        self.assertEqual(env["output"]["Z"], 8.49575)
        self.assertEqual(env["inputs"], {"OD": 6.625, "t": 0.28})
        self.assertEqual(env["user_supplied"], [])

    def test_user_supplied_lists_only_inputs_present(self):
        inp = dict(ii=2.26557, io=1, Mi=44139.00255, Mo=0, Mt=0, Z=8.49575, Sc=20000, Sh=17300, f=1)
        r = self._run("piping.displacement-stress", "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["user_supplied"], ["ii", "io", "Sc", "Sh", "f"])
        self.assertIn("319.4.4", env["citation"])

    def test_input_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "in.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"hotLoad": 1000, "springRate": 50, "travel": 6, "limit": 6}, fh)
            r = self._run("supports.spring-variability", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["status"], "fail")

    def test_new_check_through_the_cli(self):
        inp = dict(D=4.5, y=1.2, L=100, U=60, SA=30000, Ea=1.0e7, fixation_points=2,
                   intermediate_restraints=False, uniform_size=True)
        r = self._run("screen.flexibility-exemption", "--input", json.dumps(inp))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["output"]["ratio"], 0.0375)
        self.assertIn("319.4.1(c)", env["citation"])

    def test_unknown_input_key_exits_2_listing_valid_fields(self):
        r = self._run("noncode.pipe-section", "--input", json.dumps({"OD": 4.5, "t": 0.2, "wall": 1}))
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown input field", r.stderr)
        self.assertIn("valid: OD, t", r.stderr)

    def test_fatigue_equation_omitted_exits_2(self):
        r = self._run("piping.fatigue-factor", "--input", json.dumps({"N": 5000, "fmax": 1}))
        self.assertEqual(r.returncode, 2)
        self.assertIn("equation is required", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_fatigue_equation_given_runs(self):
        r = self._run("piping.fatigue-factor", "--input", json.dumps({"N": 5000, "fmax": 1, "equation": "legacy"}))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_validation_warning_reaches_the_envelope(self):
        r = self._run("supports.spring-variability", "--input", json.dumps({"hotLoad": 1000, "springRate": 50, "travel": 6, "limit": 0.25}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any("percent" in w for w in json.loads(r.stdout)["warnings"]))

    def test_basis_subcommand(self):
        r = self._run("basis", "--code", "B31.3", "--edition", "2022")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["fatigue_equation"], "b313-2022")

    def test_exit_2_on_bad_input(self):
        cases = [
            ("piping.displacement-stress", "--input", "{not json"),
            ("piping.displacement-stress", "--input", json.dumps({"ii": 1})),          # missing fields
            ("piping.displacement-stress", "--input", json.dumps(dict(ii=0.5, io=1, Mi=1, Mo=0, Mt=0, Z=1, Sc=1, Sh=1, f=1))),
            ("no.such-module", "--input", "{}"),
            ("noncode.pipe-section",),                                                    # no input at all
            ("noncode.pipe-section", "--input", "[1, 2]"),                                # not an object
            ("noncode.pipe-section", "--input-file", os.path.join(ROOT, "tests", "does-not-exist.json")),
            ("basis", "--code", "B31.4", "--edition", "2022"),
            ("basis", "--code", "B31.3"),
        ]
        for args in cases:
            r = self._run(*args)
            self.assertEqual(r.returncode, 2, f"{args}: rc={r.returncode} {r.stderr}")
            self.assertIn("input error", r.stderr)
            self.assertEqual(r.stdout, "")


class SkillContent(unittest.TestCase):
    """Guards on the shipped SKILL.md: frontmatter limits and the product rules."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()
        with open(TOOL, encoding="utf-8") as fh:
            cls.code = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: stress-screening\ndescription: \""))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 1024)
        for trigger in ("sustained", "S_A", "f factor", "Eq. 17", "1.33 Sh", "formal analysis exemption",
                        "support span", "spring variability", "B31J", "B31.1", "B31.3"):
            self.assertIn(trigger, desc)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)

    def test_hand_offs_name_only_pack_skills(self):
        self.assertIn("`load-case-builder`", self.text)
        self.assertIn("`pressure-design`", self.text)
        self.assertIn("if it is installed", self.text)

    def test_copyright_boundary_and_disclaimer_present(self):
        self.assertIn("## Copyright boundary", self.text)
        self.assertIn("Do not ask the user to upload", self.text)
        self.assertIn("engineer of record verifies", self.text)

    def test_every_registered_module_is_documented(self):
        for mid in ss.REGISTRY:
            self.assertIn(f"`{mid}`", self.text, mid)

    def test_skill_never_computes_sifs(self):
        self.assertIn("never computes an i", self.text)
        lowered = self.code.lower()
        for forbidden in ("flexibility characteristic", "def sif", "def b31j", "appendix d table"):
            self.assertNotIn(forbidden, lowered)

    def test_code_and_skill_are_not_a_value_table(self):
        """No material designation is paired with a stress or modulus in the shipped text."""
        import re
        pat = re.compile(r"\b(A\s?106|A\s?53|A\s?312|A\s?333|SA-\d+|TP\s?304|TP\s?316|Gr\.?\s?B)\b[^\n]{0,60}\b\d{4,}\s?(psi|ksi)?", re.I)
        for label, blob in (("SKILL.md", self.text), ("stress_screening.py", self.code)):
            self.assertIsNone(pat.search(blob), label)


if __name__ == "__main__":
    unittest.main()
