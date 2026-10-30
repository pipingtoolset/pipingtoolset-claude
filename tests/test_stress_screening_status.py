"""stress-screening: output status taxonomy (plugin 0.8.0, B9).

One test per taxonomy word that this skill can reach, the banner rule, the five-word vocabulary,
and the guarantee that the existing status words and values do not move. Standard library only:

    python -m unittest tests.test_stress_screening_status -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-screening")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "stress_screening.py")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
import stress_screening as ss  # noqa: E402

WORDS = {"calculated", "screening", "manual check required", "pointer only", "not checked"}
DISP = dict(ii=2.0, io=1.5, Mi=1000, Mo=500, Mt=0, Z=8.0, Sc=20000, Sh=17000, f=1)
SUST = dict(method="sqrt", P=100, D=6.625, t=0.28, Sb=5000, St=100, Socc=2000, Sh=16000, k=1.33)
SPAN = dict(w=24, E=1.0e7, S_allow=3000, delta_allow=0.25, Z=10.0, I=40.0)
EXEMPT = dict(D=4.5, y=1.2, L=100, U=60, SA=30000, Ea=1.0e7, code="B31.3", edition=2022,
              fixation_points=2, intermediate_restraints=False, uniform_size=True)
SAMPLES = {
    "piping.displacement-stress": DISP,
    "piping.sustained-stress": SUST,
    "piping.fatigue-factor": dict(equation="b313-2022", fmax=1.0, N=7000),
    "supports.spring-variability": dict(hotLoad=1000, springRate=50, travel=0.2, limit=25),
    "supports.max-spring-rate": dict(hotLoad=1000, travel=0.5, variabilityLimit=0.25),
    "noncode.pipe-section": dict(OD=6.625, t=0.28),
    "screen.support-span": SPAN,
    "screen.flexibility-exemption": EXEMPT,
}


def names(env, word):
    return [c["name"] for c in env["checks"] if c["result_status"] == word]


class Vocabulary(unittest.TestCase):

    def test_the_words_are_exactly_the_five(self):
        self.assertEqual(set(ss.RESULT_STATUS), WORDS)
        self.assertEqual(len(ss.RESULT_STATUS), 5)

    def test_every_module_emits_status_fields_in_the_agreed_shape(self):
        self.assertEqual(set(SAMPLES), set(ss.REGISTRY))
        for module, inp in SAMPLES.items():
            env = ss.run_module(module, dict(inp))
            self.assertIn(env["result_status"], WORDS, module)
            self.assertTrue(env["checks"], module)
            for c in env["checks"]:
                self.assertEqual(set(c), {"name", "result_status", "status", "note"}, (module, c))
                self.assertIn(c["result_status"], WORDS, (module, c))
                self.assertIn(c["status"], ("pass", "fail", "na"), (module, c))
            self.assertEqual(env["result_status"], ss.envelope_status(env["checks"]), module)
            self.assertTrue(env["result_status_line"].startswith("Result status: " + env["result_status"]), module)

    def test_the_status_line_is_the_shared_renderer_output(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP))
        self.assertEqual(env["result_status_line"], ss.render_status_line(
            "calculated", "displacement stress range S_E against S_A calculated; not performed by this module: "
            "SIF source and tee orientation; liberal allowance, Eq. (1b)"))
        self.assertTrue(env["result_status_line"].startswith("Result status: calculated - "))
        self.assertTrue(env["result_status_line"].isascii())
        env = ss.run_module("noncode.pipe-section", dict(OD=6.625, t=0.28))
        self.assertEqual(env["result_status_line"], ss.render_status_line(
            "calculated", "every check this module performs was evaluated from the inputs given"))

    def test_the_cli_prints_the_same_fields(self):
        r = subprocess.run([sys.executable, TOOL, "piping.displacement-stress", "--input", json.dumps(DISP)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(env["checks"][0]["result_status"], "calculated")
        self.assertEqual(env["banner"], "PASS")

    def test_the_basis_command_reports_a_status_too(self):
        r = subprocess.run([sys.executable, TOOL, "basis", "--code", "B31.3", "--edition", "2022"],
                           capture_output=True, text=True, encoding="utf-8")
        out = json.loads(r.stdout)
        self.assertIn(out["result_status"], WORDS)
        self.assertEqual(out["fatigue_equation"], "b313-2022")      # the resolver fields are untouched


class Calculated(unittest.TestCase):

    def test_a_clean_run_is_calculated_when_the_module_lists_no_limit(self):
        env = ss.run_module("noncode.pipe-section", dict(SAMPLES["noncode.pipe-section"]))
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(len(env["checks"]), 1)

    def test_every_main_check_is_calculated_on_a_clean_run(self):
        for module in ("piping.displacement-stress", "piping.sustained-stress", "supports.spring-variability",
                       "supports.max-spring-rate", "noncode.pipe-section"):
            env = ss.run_module(module, dict(SAMPLES[module]))
            self.assertEqual(env["checks"][0]["result_status"], "calculated", module)

    def test_a_fail_is_still_calculated_and_still_prints_fail(self):
        env = ss.run_module("supports.spring-variability", dict(hotLoad=1000, springRate=50, travel=6, limit=25))
        self.assertEqual(env["status"], "fail")
        self.assertEqual(env["checks"][0]["result_status"], "calculated")
        self.assertEqual(env["checks"][0]["status"], "fail")
        self.assertEqual(env["banner"], "FAIL")


class Screening(unittest.TestCase):

    def test_the_span_screen_is_screening(self):
        env = ss.run_module("screen.support-span", dict(SPAN))
        self.assertEqual(env["result_status"], "screening")
        self.assertEqual(names(env, "screening"), ["support span, bending and deflection criteria"])
        self.assertIn("pressure stress in the span", names(env, "not checked"))
        self.assertIn("loads outside the screen", names(env, "not checked"))
        self.assertIsNone(env["banner"])           # no verdict without a proposed span

    def test_a_screening_pass_keeps_its_banner_because_no_factor_is_unresolved(self):
        env = ss.run_module("screen.support-span", dict(SPAN, L_actual_ft=5))
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["result_status"], "screening")
        self.assertFalse(any(c.get("unresolved_factor") for c in env["checks"]))
        self.assertEqual(env["banner"], "PASS")

    def test_pressure_stress_given_removes_that_not_checked_entry(self):
        env = ss.run_module("screen.support-span", dict(SPAN, S_pressure=500))
        self.assertNotIn("pressure stress in the span", names(env, "not checked"))

    def test_the_exemption_is_screening_when_everything_is_confirmed(self):
        env = ss.run_module("screen.flexibility-exemption", dict(EXEMPT))
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["result_status"], "screening")
        self.assertEqual(env["banner"], "PASS")
        self.assertEqual(names(env, "calculated"), ["disqualifier inputs"])

    def test_a_disqualifier_is_a_fail_and_still_screening(self):
        env = ss.run_module("screen.flexibility-exemption", dict(EXEMPT, fixation_points=3))
        self.assertEqual(env["status"], "fail")
        self.assertEqual(env["result_status"], "screening")
        self.assertEqual(env["banner"], "FAIL")
        dq = [c for c in env["checks"] if c["name"] == "disqualifier inputs"][0]
        self.assertEqual((dq["result_status"], dq["status"]), ("calculated", "fail"))


class ManualCheckRequired(unittest.TestCase):

    def test_unconfirmed_disqualifier_inputs(self):
        inp = {k: v for k, v in EXEMPT.items() if k != "uniform_size"}
        env = ss.run_module("screen.flexibility-exemption", inp)
        self.assertEqual(env["status"], "na")
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["disqualifier inputs"])

    def test_code_not_given_or_b311_before_2016(self):
        base = {k: v for k, v in EXEMPT.items() if k not in ("code", "edition")}
        env = ss.run_module("screen.flexibility-exemption", dict(base))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["D basis"])
        env = ss.run_module("screen.flexibility-exemption", dict(base, code="B31.1", edition=2012))
        self.assertEqual(names(env, "manual check required"), ["K1 form"])
        env = ss.run_module("screen.flexibility-exemption", dict(base, code="B31.1"))
        self.assertEqual(names(env, "manual check required"), ["K1 form"])

    def test_b311_from_2016_is_screening_with_the_d_basis_listed_as_not_checked(self):
        env = ss.run_module("screen.flexibility-exemption", dict(EXEMPT, code="B31.1", edition=2016))
        self.assertEqual(env["result_status"], "screening")
        self.assertIn("D basis", names(env, "not checked"))

    def test_f_above_one_in_the_displacement_check(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP, f=1.2))
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["f above 1.0 (fm = 1.2 conditions)"])

    def test_f_above_one_from_the_fatigue_factor(self):
        env = ss.run_module("piping.fatigue-factor", dict(equation="b313-2022", fmax=1.2, N=1000))
        self.assertGreater(env["output"]["f"], 1.0)
        self.assertEqual(env["result_status"], "manual check required")
        env = ss.run_module("piping.fatigue-factor", dict(equation="b313-2022", fmax=1.2, N=20000))
        self.assertLessEqual(env["output"]["f"], 1.0)
        self.assertNotEqual(env["result_status"], "manual check required")

    def test_an_unusual_occasional_factor(self):
        env = ss.run_module("piping.sustained-stress", dict(SUST, k=1.25))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["occasional factor k"])

    def test_a_spring_limit_that_looks_like_a_fraction(self):
        env = ss.run_module("supports.spring-variability", dict(hotLoad=1000, springRate=50, travel=0.2, limit=0.25))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["limit unit"])


class NotChecked(unittest.TestCase):

    def test_fatigue_without_a_code_and_edition_lists_the_equation_check(self):
        env = ss.run_module("piping.fatigue-factor", dict(SAMPLES["piping.fatigue-factor"]))
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(names(env, "not checked"),
                         ["equation generation against code edition", "load ranges behind N"])

    def test_fatigue_with_a_record_resolves_that_check(self):
        with open(os.path.join(SCRIPTS, "examples", "project-basis.example.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        rec.pop("assumptions", None)
        env = ss.run_module("piping.fatigue-factor", {"fmax": 1.0, "project_basis": rec})
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(names(env, "not checked"), ["load ranges behind N"])
        self.assertEqual(names(env, "calculated"), ["f factor and equivalent cycles N_E",
                                                    "equation generation against code edition"])

    def test_k_of_1_15_or_1_20_lists_the_duration_basis(self):
        for k in (1.15, 1.20):
            env = ss.run_module("piping.sustained-stress", dict(SUST, k=k))
            self.assertEqual(env["result_status"], "calculated", k)
            self.assertEqual(names(env, "not checked")[0], "k duration basis", k)
        env = ss.run_module("piping.sustained-stress", dict(SUST, k=1.33))
        self.assertNotIn("k duration basis", names(env, "not checked"))

    def test_not_checked_never_blocks_the_banner(self):
        env = ss.run_module("piping.sustained-stress", dict(SUST, k=1.15))
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["banner"], "PASS")


class PointerOnly(unittest.TestCase):
    """A pointer never reaches this script as a value, so the word is not reachable here."""

    def test_no_sample_or_variant_ever_produces_it(self):
        variants = [dict(DISP, f=1.2), dict(SUST, k=1.25), dict(SPAN, L_actual_ft=5)]
        seen = set()
        for module, inp in SAMPLES.items():
            seen.update(c["result_status"] for c in ss.run_module(module, dict(inp))["checks"])
        for module, inp in zip(("piping.displacement-stress", "piping.sustained-stress", "screen.support-span"), variants):
            seen.update(c["result_status"] for c in ss.run_module(module, dict(inp))["checks"])
        self.assertNotIn("pointer only", seen)
        self.assertTrue(seen <= WORDS)

    def test_a_pointer_text_passed_as_a_value_is_rejected_not_run(self):
        cv = {"Sh": {"value": "Table A-1, row for the material", "unit": "ksi",
                     "citation": {"standard": "s", "edition": "e", "table": "t", "row": "r"}, "source": "connector"}}
        inputs = {k: v for k, v in DISP.items() if k != "Sh"}
        inputs["code_values"] = cv
        r = subprocess.run([sys.executable, TOOL, "piping.displacement-stress", "--input", json.dumps(inputs)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Sh must be a number", r.stderr)


class BannerRule(unittest.TestCase):

    def test_pass_is_replaced_by_the_status_word_while_a_manual_check_is_open(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP, f=1.2))
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["banner"], "MANUAL CHECK REQUIRED")
        self.assertNotIn("PASS", env["banner"])

    def test_fail_still_prints_under_a_manual_check(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP, f=1.2, Mi=500000, Mo=500000))
        self.assertEqual(env["status"], "fail")
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(env["banner"], "FAIL")

    def test_the_banner_follows_the_shared_rule_for_every_word(self):
        self.assertEqual(ss.banner_word("PASS", "calculated"), "PASS")
        self.assertEqual(ss.banner_word("PASS", "not checked"), "PASS")
        self.assertEqual(ss.banner_word("PASS", "screening"), "PASS")
        self.assertEqual(ss.banner_word("PASS", "screening", True), "SCREENING")
        self.assertEqual(ss.banner_word("PASS", "pointer only"), "POINTER ONLY")
        self.assertEqual(ss.banner_word("PASS", "manual check required"), "MANUAL CHECK REQUIRED")
        # _banner is the wiring: PASS only when the checks allow it, FAIL always, nothing for na
        screening_open = [ss.make_check("x", "screening", "pass", None, True)]
        self.assertEqual(ss._banner("pass", screening_open), "SCREENING")
        self.assertEqual(ss._banner("fail", screening_open), "FAIL")
        self.assertIsNone(ss._banner("na", screening_open))

    def test_no_positive_banner_anywhere_in_the_output_under_a_blocked_status(self):
        env = ss.run_module("screen.flexibility-exemption",
                            {k: v for k, v in EXEMPT.items() if k != "intermediate_restraints"})
        self.assertEqual(env["status"], "na")
        self.assertEqual(env["result_status"], "manual check required")
        text = json.dumps({k: env[k] for k in ("banner", "result_status_line", "checks")})
        for word in ("PASS", "OK", "ISSUE", "DELIVERABLE"):
            self.assertNotIn(word, text)


class EngineUnchanged(unittest.TestCase):
    """B9 adds keys only: fixture parity and the engine outputs do not move."""

    def test_fixture_parity_for_the_six_ported_modules(self):
        for module in parity.modules_for("stress-screening"):
            self.assertEqual(parity.run_fixture(ss.REGISTRY, module), [], module)

    def test_the_envelope_status_and_output_equal_the_registry_result(self):
        for module, inp in SAMPLES.items():
            direct = ss.REGISTRY[module](dict(inp))
            env = ss.run_module(module, dict(inp))
            self.assertEqual(env["status"], direct["status"], module)
            self.assertEqual(env["output"], direct["output"], module)
            self.assertIn(env["status"], ("pass", "fail", "na"))

    def test_every_check_status_is_the_modules_own_or_na(self):
        for module, inp in SAMPLES.items():
            env = ss.run_module(module, dict(inp))
            first = env["checks"][0]
            self.assertEqual(first["status"], env["status"], module)


if __name__ == "__main__":
    unittest.main()


class PermanentLimitsAndAssumed(unittest.TestCase):
    """The known limits are listed on every run; an ASSUMED record item is an unconfirmed input."""

    def test_the_table_covers_every_module(self):
        self.assertEqual(set(ss.NOT_CHECKED), set(ss.REGISTRY))

    def test_every_listed_limit_is_a_not_checked_check_on_every_run(self):
        for module, inp in SAMPLES.items():
            env = ss.run_module(module, dict(inp))
            for name, note in ss.NOT_CHECKED[module]:
                hit = [c for c in env["checks"] if c["name"] == name]
                self.assertEqual(len(hit), 1, (module, name))
                self.assertEqual((hit[0]["result_status"], hit[0]["status"], hit[0]["note"]),
                                 ("not checked", "na", note), (module, name))

    def test_a_listed_limit_is_listed_not_checked_and_never_sets_the_word_or_blocks_the_banner(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP))
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(env["checks"][0]["result_status"], "calculated")
        self.assertEqual(names(env, "not checked"), ["SIF source and tee orientation", "liberal allowance, Eq. (1b)"])
        self.assertEqual((env["status"], env["banner"]), ("pass", "PASS"))

    def test_the_limits_do_not_hide_a_worse_word(self):
        env = ss.run_module("piping.displacement-stress", dict(DISP, f=1.2))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(env["banner"], "MANUAL CHECK REQUIRED")

    def _assumed_record(self):
        with open(os.path.join(SCRIPTS, "examples", "project-basis.example.json"), encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertTrue([a for a in rec["assumptions"] if a.get("status", "ASSUMED") == "ASSUMED"])
        return rec

    def test_an_assumed_record_item_is_one_manual_check_row_and_holds_the_banner(self):
        rec = self._assumed_record()
        items = [a["item"] for a in rec["assumptions"] if a.get("status", "ASSUMED") == "ASSUMED"]
        env = ss.run_module("noncode.pipe-section", dict(OD=6.625, t=0.28, project_basis=rec))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["ASSUMED inputs"])
        row = next(c for c in env["checks"] if c["name"] == "ASSUMED inputs")
        self.assertEqual(row["note"], "confirm before issue: " + "; ".join(items))
        self.assertIn("confirm before issue: " + items[0], env["result_status_line"])
        env = ss.run_module("piping.sustained-stress", dict(SUST, project_basis=rec))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual((env["status"], env["banner"]), ("pass", "MANUAL CHECK REQUIRED"))

    def test_an_assumed_item_leaves_a_worse_word_alone(self):
        rec = self._assumed_record()
        env = ss.run_module("piping.displacement-stress", dict(DISP, f=1.2, project_basis=rec))
        self.assertEqual(env["result_status"], "manual check required")

    def test_a_confirmed_assumption_does_not_demote(self):
        rec = self._assumed_record()
        for a in rec["assumptions"]:
            a["status"] = "confirmed"
        env = ss.run_module("noncode.pipe-section", dict(OD=6.625, t=0.28, project_basis=rec))
        self.assertEqual(env["result_status"], "calculated")

    def test_the_basis_command_with_an_assumed_item_is_a_manual_check(self):
        import tempfile
        rec = self._assumed_record()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "basis.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh)
            r = subprocess.run([sys.executable, TOOL, "basis", "--project-basis", path],
                               capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["result_status"], "manual check required")
