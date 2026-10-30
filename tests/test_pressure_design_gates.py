"""Regression tests for the pressure-design validity gates (plugin 0.7.2, CODEX P1-3).

Two gates sit in the CLI / envelope layer of scripts/pressure_design.py, around the engine:

  1. Thin-wall validity: P/(S*E) against 0.385 and the thickness against D/6, reported as a
     "validity" object; a trip makes the run "manual check required" with the numbers only as
     an "equation value, not a design basis".
  2. W basis: where the code and edition's equation carries W, W omitted or W = 1.0 needs a
     W_basis (exit 2 otherwise, naming the table and edition).

Inputs below are fictitious round numbers chosen to hit each branch; none is a code-table value.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pressure-design")
SCRIPTS = os.path.join(SKILL, "scripts")
CLI = os.path.join(SCRIPTS, "pressure_design.py")
EXAMPLES = os.path.join(SCRIPTS, "examples")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
import pressure_design as pd  # noqa: E402

B313 = "piping.b313-wall-thickness"
B311 = "piping.b311-wall-thickness"
MAWP = "piping.b31-allowable-pressure"
BEND = "piping.bend-thickness"
MITER = "piping.miter-allowable-pressure"


def cli(module: str, inputs: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, CLI, module, "--input", json.dumps(inputs)],
                          capture_output=True, text=True, encoding="utf-8")


def engine_inputs(module: str, job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in {f[0] for f in pd.BASIS_FIELDS.get(module, [])}}


def assert_no_design_basis(tc: unittest.TestCase, env: dict) -> None:
    """A tripped gate: status word, empty output, numbers only as an equation value, no PASS."""
    tc.assertEqual(env["status"], "manual check required")
    tc.assertEqual(env["result_grade"], "manual check required")
    tc.assertEqual(env["output"], {})
    tc.assertEqual(env["equation_value"]["label"], "equation value, not a design basis")
    tc.assertFalse(env["validity"]["thin_wall_valid"])
    tc.assertEqual(env["warnings"][0], env["banner"])
    tc.assertTrue(env["banner"].startswith("MANUAL CHECK REQUIRED: "))
    tc.assertIn("equation value, not a design basis", env["banner"])
    text = json.dumps(env)
    tc.assertNotIn("PASS", text)
    tc.assertNotIn('"pass"', text)


class ThinWallGateB313(unittest.TestCase):
    # P=8000, D=10, S=20000, E=1, W=1, Y=0.7: P/(S*E) = 0.4 > 0.385 while
    # t = 80000 / (2*(20000 + 5600)) = 1.5625 < D/6 = 1.66667 (the ratio trips alone).
    RATIO_ONLY = dict(P=8000, D=10, S=20000, E=1, W=1, W_basis="seamless", Y=0.7, c=0, millTolerance=0.125)
    # P=6000, D=10, S=20000, E=1, W=0.5, Y=0.4: P/(S*E) = 0.3 while
    # t = 60000 / (2*(10000 + 2400)) = 2.41935 >= D/6 (the thickness trips alone).
    THICK_ONLY = dict(P=6000, D=10, S=20000, E=1, W=0.5, Y=0.4, c=0, millTolerance=0.125)

    def test_the_example_reports_the_ratio_and_stays_calculated(self):
        path = os.path.join(EXAMPLES, "b313-wall-thickness.json")
        r = subprocess.run([sys.executable, CLI, B313, "--input-file", path], capture_output=True, text=True,
                           encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        with open(path, encoding="utf-8") as fh:
            job = json.load(fh)
        S = job["code_values"]["S"]["value"] * 1000
        v = env["validity"]
        self.assertEqual(v["P_over_SE"], pd.round_half_up(job["P"] / (S * job["E"]), 5))
        self.assertAlmostEqual(v["P_over_SE"], 750 / (12345 * 0.77), delta=1e-5)
        self.assertEqual(v["P_over_SE_limit"], 0.385)
        self.assertFalse(v["P_over_SE_exceeds"])
        self.assertFalse(v["t_over_D6"])
        self.assertTrue(v["thin_wall_valid"])
        self.assertEqual(v["D_over_6"], pd.round_half_up(6.625 / 6, 5))
        self.assertEqual(env["result_grade"], "calculated")
        self.assertEqual(env["status"], "na")
        self.assertIn("304.1.2(b)", v["clause"])
        self.assertEqual(env["weld_factor_basis"]["basis"], "longitudinal weld, confirmed")
        self.assertEqual(env["weld_factor_basis"]["edition"], "2022")
        self.assertEqual(env["weld_factor_basis"]["table"], "B31.3 Table 302.3.5 (para. 302.3.5(e))")

    def test_ratio_trigger_alone_stops_the_design_basis(self):
        env = pd.run_module(B313, self.RATIO_ONLY)
        assert_no_design_basis(self, env)
        v = env["validity"]
        self.assertEqual(v["P_over_SE"], 0.4)
        self.assertTrue(v["P_over_SE_exceeds"])
        self.assertFalse(v["t_over_D6"])
        self.assertIn("P/(S*E) = 0.4 > 0.385", env["banner"])
        self.assertIn("B31.3 para. 304.1.2(b)", env["banner"])
        self.assertEqual(env["equation_value"]["values"], pd.REGISTRY[B313](engine_inputs(B313, self.RATIO_ONLY))["output"])
        self.assertAlmostEqual(env["equation_value"]["values"]["t"], 1.5625, delta=1e-5)

    def test_thickness_trigger_alone_stops_the_design_basis(self):
        env = pd.run_module(B313, self.THICK_ONLY)
        assert_no_design_basis(self, env)
        v = env["validity"]
        self.assertFalse(v["P_over_SE_exceeds"])
        self.assertTrue(v["t_over_D6"])
        self.assertEqual(v["thickness"], pd.round_half_up(60000 / 24800, 5))
        self.assertIn("t >= D/6", env["banner"])

    def test_the_limit_itself_is_not_a_trip(self):
        # P/(S*E) = 7700/20000 = 0.385 exactly; the clause trips on "> 0.385"
        env = pd.run_module(B313, dict(self.RATIO_ONLY, P=7700))
        self.assertEqual(env["validity"]["P_over_SE"], 0.385)
        self.assertFalse(env["validity"]["P_over_SE_exceeds"])
        self.assertEqual(env["result_grade"], "calculated")

    def test_the_banner_points_at_equation_value(self):
        env = pd.run_module(B313, self.RATIO_ONLY)
        self.assertIn("the thickness under equation_value is an equation value", env["banner"])
        self.assertNotIn("below is", env["banner"])

    def test_b311_clause_names_the_pack_rule_not_a_status_word(self):
        env = pd.run_module(B311, dict(P=9000, D=6, S=20000, E=1, W=1, W_basis="seamless", y=0.4, A=0,
                                       millTolerance=0.125, edition="2022"))
        assert_no_design_basis(self, env)
        clause = env["validity"]["clause"]
        self.assertIn("confirmed by the P.E. 2026-10-30", clause)
        self.assertNotIn("screening", clause)

    def test_the_header_says_exit_0_does_not_mean_a_design_basis(self):
        self.assertIn("a tripped validity gate also exits 0", pd.__doc__)

    def test_cli_exit_is_0_and_prints_no_design_thickness(self):
        r = cli(B313, self.RATIO_ONLY)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        assert_no_design_basis(self, env)
        self.assertNotIn("t", env["output"])


class ThinWallGateOtherModules(unittest.TestCase):

    def test_b311_checks_tm_against_d_over_6(self):
        # D=6, P=3000, S=20000, E=1, y=0.4, A=0.6: t = 18000/42400 = 0.42453, tm = 1.02453 >= 1.0
        job = dict(P=3000, D=6, S=20000, E=1, W=1, W_basis="seamless", y=0.4, A=0.6, millTolerance=0.125, edition="2022")
        env = pd.run_module(B311, job)
        assert_no_design_basis(self, env)
        v = env["validity"]
        self.assertTrue(v["thickness_checked"].startswith("tm"))
        self.assertFalse(v["P_over_SE_exceeds"])
        self.assertIn("Do/tm < 6", v["clause"])
        self.assertIn("104.1.2", v["clause"])
        # the same job with no allowance is inside the basis
        ok = pd.run_module(B311, dict(job, A=0))
        self.assertEqual(ok["result_grade"], "calculated")
        self.assertEqual(ok["output"], pd.REGISTRY[B311](engine_inputs(B311, dict(job, A=0)))["output"])

    def test_mawp_uses_the_computed_allowable_pressure(self):
        job = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1, W=1, W_basis="seamless", code="B31.3")
        env = pd.run_module(MAWP, job)
        P = env["output"]["allowablePressure"]
        self.assertEqual(env["validity"]["P_basis"], "computed allowable pressure")
        self.assertEqual(env["validity"]["P_over_SE"], pd.round_half_up(P / 20000, 5))
        self.assertEqual(env["result_grade"], "calculated")

    def test_mawp_thick_wall_trips(self):
        # D=4, t=1.0 >= D/6; P = 2*20000*1/(4 - 0.8) = 12500, P/(S*E) = 0.625
        job = dict(D=4, t=1.0, millTolerance=0, A=0, S=20000, E=1, y=0.4, Mf=1, W=1, W_basis="seamless", code="B31.3")
        env = pd.run_module(MAWP, job)
        assert_no_design_basis(self, env)
        self.assertEqual(env["equation_value"]["values"]["allowablePressure"], 12500)
        self.assertEqual(env["validity"]["P_over_SE"], 0.625)
        self.assertTrue(env["validity"]["t_over_D6"])
        self.assertIn("pressure under equation_value is an equation value", env["banner"])

    def test_mawp_b31_12_includes_mf_and_needs_no_w(self):
        job = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=0.8, code="B31.12")
        env = pd.run_module(MAWP, job)
        P = env["output"]["allowablePressure"]
        self.assertTrue(env["validity"]["SE_includes_Mf"])
        self.assertEqual(env["validity"]["P_over_SE"], pd.round_half_up(P / (20000 * 0.8), 5))
        self.assertFalse(env["weld_factor_basis"]["W_in_equation"])
        self.assertEqual(env["defaults_applied"], {})

    def test_mawp_no_thickness_left_keeps_the_engine_fail(self):
        job = dict(D=10, t=0.2, millTolerance=0.5, A=0.1, S=20000, E=1, y=0.4, Mf=1, W=0.9)
        env = pd.run_module(MAWP, job)
        self.assertEqual(env["status"], "fail")
        self.assertNotIn("validity", env)

    def test_bend_checks_the_intrados_pressure_thickness(self):
        job = dict(P=1000, D=10, R=30, S=20000, E=1, W=1, W_basis="seamless", y=0.4, A=0, code="B31.3")
        env = pd.run_module(BEND, job)
        self.assertEqual(env["validity"]["thickness"], env["output"]["tmIntrados"])
        self.assertEqual(env["result_grade"], "calculated")
        tripped = pd.run_module(BEND, dict(job, P=8000))          # P/(S*E) = 0.4
        assert_no_design_basis(self, tripped)
        self.assertIn("304.2.1", tripped["banner"])

    def test_miter_and_other_modules_carry_no_validity_gate(self):
        job = dict(S=18000, E=1, W=1, W_basis="seamless", Tc=0.2, r2=5, R1=15, thetaDeg=15, miters=3)
        env = pd.run_module(MITER, job)
        self.assertNotIn("validity", env)
        self.assertIn("weld_factor_basis", env)
        for module in ("piping.branch-reinforcement", "piping.leak-test-pressure"):
            env = pd.run_module(module, parity.load(module)["cases"][0]["input"])
            self.assertNotIn("validity", env, module)
            self.assertNotIn("weld_factor_basis", env, module)


class FixtureNumbersUnchanged(unittest.TestCase):
    """Computed numbers for valid inputs are unchanged: no fixture case trips a gate."""

    def test_parity_is_green_for_every_module(self):
        for module in pd.REGISTRY:
            self.assertEqual(parity.run_fixture(pd.REGISTRY, module), [], module)

    def test_every_fixture_case_runs_calculated_with_the_engine_numbers(self):
        for module in pd.GATED_MODULES + (MITER,):
            for i, case in enumerate(parity.load(module)["cases"]):
                job = dict(case["input"], W_basis="seamless")
                env = pd.run_module(module, job)
                engine = pd.REGISTRY[module](dict(case["input"]))
                self.assertEqual(env["status"], engine["status"], f"{module} {i}")
                want = dict(engine["output"])
                if module == MITER and case["input"].get("miters") == 1:
                    want["Pm2"] = None
                self.assertEqual(env["output"], want, f"{module} {i}")
                if module in pd.GATED_MODULES:
                    self.assertEqual(env["result_grade"], "calculated", f"{module} {i}")
                    self.assertTrue(env["validity"]["thin_wall_valid"], f"{module} {i}")


class WGate(unittest.TestCase):
    BASE = dict(P=1000, D=10, S=24800, E=1, Y=0.4, c=0.1, millTolerance=0.125)

    def _exit2(self, module, job, *fragments):
        r = cli(module, job)
        self.assertEqual((r.returncode, r.stdout), (2, ""), r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        for f in fragments:
            self.assertIn(f, r.stderr)
        return r.stderr

    def test_w_absent_without_basis_exits_2_naming_table_and_edition(self):
        self._exit2(B313, dict(self.BASE, edition="2022"), "W is required", "B31.3 Table 302.3.5 ", "B31.3-2022")
        self._exit2(B313, dict(self.BASE, edition=2024), "B31.3 Table 302.3.5-1", "B31.3-2024")
        self._exit2(B313, self.BASE, "Table 302.3.5", "edition of record")
        b311 = dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125, edition="2022")
        self._exit2(B311, b311, "B31.1 Table 102.4.7-1", "B31.1-2022")
        mawp = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1)
        self._exit2(MAWP, mawp, "B31.3 Table 302.3.5", "B31.1 Table 102.4.7-1")
        self._exit2(BEND, dict(P=1000, D=10, R=30, S=20000, E=1, y=0.4, A=0), "W is required")
        self._exit2(MITER, dict(S=18000, E=1, Tc=0.2, r2=5, R1=15, thetaDeg=15, miters=3), "W is required")

    def test_w_one_without_basis_exits_2(self):
        self._exit2(B313, dict(self.BASE, W=1), "W = 1.0 needs W_basis", "Table 302.3.5")

    def test_w_basis_alone_is_accepted_and_applied_as_one(self):
        env = pd.run_module(B313, dict(self.BASE, W_basis="below creep range per table note"))
        rec = env["weld_factor_basis"]
        self.assertEqual((rec["W"], rec["basis"]), (1.0, "below creep range per table note"))
        self.assertTrue(rec["basis_source"].startswith("W_basis"))
        self.assertEqual(env["inputs"]["W"], 1.0)
        self.assertEqual(env["defaults_applied"], {})
        self.assertEqual(env["output"], pd.REGISTRY[B313](dict(self.BASE, W=1))["output"])

    def test_w_one_with_basis_is_recorded(self):
        env = pd.run_module(B313, dict(self.BASE, W=1, W_basis="seamless", edition="2022"))
        rec = env["weld_factor_basis"]
        self.assertEqual((rec["W"], rec["basis"], rec["basis_source"]), (1, "seamless", "W_basis"))
        self.assertEqual(rec["table"], "B31.3 Table 302.3.5 (para. 302.3.5(e))")
        self.assertEqual(env["inputs"]["W_basis"], "seamless")
        self.assertEqual(env["inputs"]["edition"], "2022")

    def test_free_text_basis_is_recorded_verbatim(self):
        text = "ERW pipe; design temperature below the table's first column (my copy, note 3)"
        env = pd.run_module(B313, dict(self.BASE, W=1, W_basis=text))
        self.assertEqual(env["weld_factor_basis"]["basis"], text)

    def test_a_reduced_w_needs_no_basis(self):
        env = pd.run_module(B313, dict(self.BASE, W=0.9))
        self.assertIsNone(env["weld_factor_basis"]["basis"])
        self.assertIn("cite its table line", env["weld_factor_basis"]["basis_source"])

    def test_a_cited_code_values_entry_for_w_is_a_basis(self):
        entry = {"value": 1, "unit": None, "source": "user",
                 "citation": {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
                              "row": "Placeholder row", "column": "Placeholder column"}}
        env = pd.run_module(B313, dict(self.BASE, code_values={"W": entry}))
        self.assertEqual(env["weld_factor_basis"]["basis_source"], "code_values citation")
        self.assertIn("Placeholder table", env["weld_factor_basis"]["basis"])

    B311_2016 = dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125, edition="B31.1-2016")

    def test_b311_2016_route_needs_w_or_a_basis(self):
        # para. 104.1.1: Eq. (7) (no W) only for seamless pipe or pipe below the creep range;
        # welded pipe in the creep range is para. 104.1.4 Eq. (11) with W, so the route can require W.
        self._exit2(B311, self.B311_2016, "W or W_basis is required", "B31.1-2016", "104.1.1", "104.1.4",
                    "B31.1 Table 102.4.7 ")
        self._exit2(B311, dict(self.B311_2016, W=1), "W = 1.0 needs W_basis", "B31.1-2016", "104.1.4")
        mawp = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1, code="B31.1", edition=2016)
        self._exit2(MAWP, mawp, "W or W_basis is required", "104.1.1")
        self._exit2(B311, dict(self.B311_2016, edition="2018"), "W is required", "B31.1-2018")

    def test_b311_2016_basis_records_eq7_and_warns_the_creep_range_limit(self):
        env = pd.run_module(B311, dict(self.B311_2016, W_basis="below creep range per table note"))
        rec = env["weld_factor_basis"]
        self.assertFalse(rec["W_in_equation"])
        self.assertIn("para. 104.1.2 Eq. (7)", rec["route"])
        self.assertIn("104.1.4", rec["note"])
        self.assertEqual(rec["W"], 1.0)
        self.assertEqual(env["defaults_applied"], {})
        self.assertEqual(env["result_grade"], "calculated")
        warned = [w for w in env["warnings"] if w.startswith("B31.1-2016:")]
        self.assertEqual(len(warned), 1, env["warnings"])
        self.assertIn("para. 104.1.4", warned[0])
        self.assertIn("below creep range per table note", warned[0])
        # Eq. (7) with no W gives the same numbers as the engine at W = 1
        self.assertEqual(env["output"], pd.REGISTRY[B311](engine_inputs(B311, dict(self.B311_2016, W=1)))["output"])

    def test_b311_2016_reduced_w_is_the_104_1_4_route(self):
        env = pd.run_module(B311, dict(self.B311_2016, W=0.5))
        rec = env["weld_factor_basis"]
        self.assertTrue(rec["W_in_equation"])
        self.assertIn("104.1.4 Eq. (11)", rec["route"])
        self.assertFalse(any(w.startswith("B31.1-2016:") for w in env["warnings"]))
        self.assertFalse(any("result is conservative" in w for w in env["warnings"]))
        self.assertEqual(env["output"], pd.REGISTRY[B311](engine_inputs(B311, dict(self.B311_2016, W=0.5)))["output"])

    def test_b311_2016_bend_equation_still_has_no_w(self):
        job = dict(P=1000, D=10, R=30, S=20000, E=1, y=0.4, A=0, code="B31.1", edition="2016")
        env = pd.run_module(BEND, job)
        self.assertFalse(env["weld_factor_basis"]["W_in_equation"])
        self.assertIn("102.4.5", env["weld_factor_basis"]["note"])

    def test_seamless_basis_with_a_joint_factor_below_one_is_warned(self):
        env = pd.run_module(B313, dict(self.BASE, E=0.85, W=1, W_basis="seamless"))
        self.assertTrue(any(w.startswith("W_basis says seamless but E = 0.85") for w in env["warnings"]),
                        env["warnings"])
        clean = pd.run_module(B313, dict(self.BASE, W=1, W_basis="seamless"))
        self.assertFalse(any("W_basis says seamless" in w for w in clean["warnings"]))
        self.assertEqual(env["output"], pd.REGISTRY[B313](engine_inputs(B313, dict(self.BASE, E=0.85, W=1)))["output"])

    def test_mawp_b31_9_needs_no_w_and_unknown_code_exits_2(self):
        job = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1, code="b31.9")
        env = pd.run_module(MAWP, job)
        self.assertFalse(env["weld_factor_basis"]["W_in_equation"])
        self.assertEqual(env["inputs"]["code"], "B31.9")
        self._exit2(MAWP, dict(job, code="B31.4"), "code must be one of B31.3, B31.1, B31.9, B31.12")
        self._exit2(BEND, dict(P=1000, D=10, R=30, S=20000, E=1, W=1, W_basis="seamless", y=0.4, A=0, code="B31.9"),
                    "code must be one of B31.3, B31.1")

    def test_a_w_in_an_equation_without_w_is_warned(self):
        job = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1, W=0.8, code="B31.12")
        env = pd.run_module(MAWP, job)
        self.assertTrue(any("has no W term; the result is conservative" in w for w in env["warnings"]))

    def test_malformed_basis_inputs_exit_2(self):
        self._exit2(B313, dict(self.BASE, W=1, W_basis=""), "W_basis must be a non-empty string")
        self._exit2(B313, dict(self.BASE, W=1, W_basis=1), "W_basis must be a non-empty string")
        self._exit2(B313, dict(self.BASE, W=1, W_basis="seamless", edition=True), "edition must be")
        self._exit2(B313, dict(self.BASE, W=1, W_basis="seamless", code="B31.3"), "unknown input field(s) 'code'")
        self._exit2("piping.leak-test-pressure",
                    dict(P=450, ST=20000, S=20000, hydroFactor=1.5, pneumaticFactor=1.1, W_basis="seamless"),
                    "unknown input field(s) 'W_basis'")

    def test_defaults_applied_never_holds_w(self):
        jobs = {
            B313: dict(self.BASE),
            B311: dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125),
            MAWP: dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1),
            BEND: dict(P=1000, D=10, R=30, S=20000, E=1, y=0.4, A=0),
            MITER: dict(S=18000, E=1, Tc=0.2, r2=5, R1=15, thetaDeg=15, miters=3),
        }
        self.assertEqual(set(jobs), set(pd.W_MODULES))
        for module, job in jobs.items():
            env = pd.run_module(module, dict(job, W_basis="seamless"))
            self.assertNotIn("W", env["defaults_applied"], module)
            self.assertEqual(env["weld_factor_basis"]["W"], 1.0, module)

    def test_list_json_shows_basis_fields_and_gates(self):
        r = subprocess.run([sys.executable, CLI, "list", "--json"], capture_output=True, text=True, encoding="utf-8")
        data = json.loads(r.stdout)
        for module in pd.W_MODULES:
            names = [f["name"] for f in data[module]["basis_fields"]]
            self.assertIn("W_basis", names, module)
            self.assertIn("edition", names, module)
        self.assertIn("code", [f["name"] for f in data[MAWP]["basis_fields"]])
        self.assertEqual({m for m in data if data[m]["validity_gate"]}, set(pd.GATED_MODULES))


class SkillTextStatesTheGates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.skill = fh.read()
        with open(os.path.join(SKILL, "references", "modules.md"), encoding="utf-8") as fh:
            cls.modules = fh.read()

    def test_no_text_still_says_the_ratio_is_untested(self):
        for label, text in (("SKILL.md", self.skill), ("modules.md", self.modules)):
            self.assertNotIn("not tested by the script", text, label)
            self.assertNotIn("does **not** test that", text, label)
            self.assertNotIn("applies silently", text, label)

    def test_skill_names_the_gate_words_and_the_w_basis(self):
        for phrase in ("manual check required", "equation value, not a design basis", "W_basis", "P_over_SE",
                       "weld_factor_basis", "302.3.5", "102.4.7"):
            self.assertIn(phrase, self.skill, phrase)

    def test_modules_reference_describes_the_validity_object(self):
        for phrase in ("validity", "P_over_SE", "manual check required", "W_basis", "B31.1-2016"):
            self.assertIn(phrase, self.modules, phrase)


if __name__ == "__main__":
    unittest.main()
