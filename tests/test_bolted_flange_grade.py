"""Result-grade tests for the bolted-flange skill (CODEX P1-4).

The detailed VIII-2 4.16 result is graded `screening` ("screening / reconstructed factors")
while any hub factor the flange type uses came from the open-source series, and `calculated`
only when F_override, V_override and f_override were all supplied (or the flange is loose and
uses no hub factor). The grade adds result keys; every engine number and status word stays.

    python -m unittest tests.test_bolted_flange_grade -v
"""

from __future__ import annotations

import itertools
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "bolted-flange")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "bolted_flange.py")
EXAMPLE = os.path.join(SCRIPTS, "examples", "integral-weld-neck.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import bolted_flange as bf  # noqa: E402
import parity  # noqa: E402

APP2 = "aux.app2-flange-integral"
SCREEN = "connections.flange-equivalent-pressure"
FIXTURE_CASES = parity.load(APP2)["cases"]
CASE = FIXTURE_CASES[0]["input"]
LOOSE_CASE = FIXTURE_CASES[1]["input"]
SCREEN_CASE = parity.load(SCREEN)["cases"][0]["input"]
BANNER = ("SCREENING / RECONSTRUCTED FACTORS: F, V, f from the open-source series reconstruction; "
          "supply F_override, V_override, f_override read from VIII-2 Table 4.16.5 for an issue-grade result")
TAXONOMY = "calculated / screening / manual check required / pointer only / not checked"
# Acceptance wording that must not appear on a screening run. The required banner line itself
# contains "issue-grade" (it tells the user what to supply), so it is cut out before the scan.
ACCEPT = re.compile(r"\b(pass|passes|passed|passing|issued?|issue-grade|accepted|acceptable)\b", re.I)


def run(module, inputs):
    return bf.REGISTRY[module](dict(inputs))


def series_factors(case):
    return bf.hub_factors(case["g1"] / case["g0"], case["h"] / (case["B"] * case["g0"]) ** 0.5)


def full_override(case=CASE):
    s = series_factors(case)
    return dict(case, F_override=s["F"], V_override=s["V"], f_override=s["f"])


def with_pre_flight(case):
    """The fixture inputs plus the values the run_module pre-flight refuses to default."""
    return dict(case, Edesign=bf.ENGINE_DEFAULT_E_DESIGN, Eambient=bf.ENGINE_DEFAULT_E_AMBIENT,
                SfAmbient=case.get("SfAmbient", case["Sf"]))


def strip_banner(text):
    return text.replace(BANNER, "")


class DefaultRunIsScreening(unittest.TestCase):
    def test_default_integral_run_is_screening_with_all_factors_on_the_series(self):
        out = run(APP2, CASE)["output"]
        self.assertEqual(out["result_grade"], "screening")
        self.assertEqual(out["grade_label"], "screening / reconstructed factors")
        self.assertEqual(out["factor_basis"], {"F": "series", "V": "series", "f": "series"})
        self.assertEqual(out["banner"], BANNER)
        self.assertIn("Series factor(s) in use: F, V, f", out["grade_note"])
        self.assertIn("Override(s) supplied: none", out["grade_note"])

    def test_every_integral_fixture_case_without_overrides_is_screening(self):
        seen = 0
        for i, case in enumerate(FIXTURE_CASES):
            if case["input"]["attachment"] != "integral":
                continue
            seen += 1
            out = run(APP2, case["input"])["output"]
            self.assertEqual(out["result_grade"], "screening", i)
            self.assertEqual(set(out["factor_basis"].values()), {"series"}, i)
        self.assertGreaterEqual(seen, 1)

    def test_banner_is_the_first_finding_in_the_engine_result_and_the_envelope(self):
        self.assertEqual(run(APP2, CASE)["warnings"][0], BANNER)
        env = bf.run_module(APP2, with_pre_flight(CASE))
        self.assertEqual(env["warnings"][0], BANNER)
        self.assertEqual(env["warnings"].count(BANNER), 1)
        self.assertEqual(env["output"]["result_grade"], "screening")

    def test_envelope_keys_are_unchanged(self):
        env = bf.run_module(APP2, with_pre_flight(CASE))
        self.assertEqual(set(env), {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied"})

    def test_example_job_is_screening(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            ex = json.load(fh)
        self.assertEqual(run(APP2, ex)["output"]["result_grade"], "screening")


class OverridesCloseTheGrade(unittest.TestCase):
    def test_all_three_overrides_give_calculated_and_the_issue_grade_banner(self):
        res = run(APP2, full_override())
        out = res["output"]
        self.assertEqual(out["result_grade"], "calculated")
        self.assertEqual(out["grade_label"], "calculated")
        self.assertEqual(out["factor_basis"], {"F": "override", "V": "override", "f": "override"})
        self.assertTrue(out["banner"].startswith("ISSUE-GRADE HUB FACTORS"))
        self.assertNotIn("SCREENING", out["banner"])
        self.assertEqual(res["warnings"][0], out["banner"])
        self.assertNotIn(BANNER, res["warnings"])

    def test_calculated_run_changes_no_engine_number_or_status(self):
        base = run(APP2, CASE)
        over = run(APP2, full_override())

        def keep(o):
            return {k: v for k, v in o.items() if k not in bf.GRADE_KEYS}

        self.assertEqual(keep(over["output"]), keep(base["output"]))
        self.assertEqual(over["status"], base["status"])

    def test_partial_overrides_stay_screening_and_name_the_missing_factors(self):
        s = series_factors(CASE)
        values = {"F": s["F"], "V": s["V"], "f": s["f"]}
        for r in (1, 2):
            for given in itertools.combinations("FVf", r):
                case = dict(CASE, **{k + "_override": values[k] for k in given})
                res = run(APP2, case)
                out = res["output"]
                missing = [k for k in "FVf" if k not in given]
                prefix = "Series factor(s) in use: " + ", ".join(missing)
                self.assertEqual(out["result_grade"], "screening", given)
                self.assertEqual(out["banner"], BANNER, given)
                self.assertEqual(out["factor_basis"], {k: ("override" if k in given else "series") for k in "FVf"}, given)
                self.assertIn(prefix, out["grade_note"], given)
                for k in missing:
                    self.assertIn(k + "_override", out["grade_note"], given)
                self.assertTrue(any(w.startswith("Result grade screening: " + prefix) for w in res["warnings"]), given)
                self.assertEqual(res["warnings"][0], BANNER)

    def test_loose_flange_uses_no_hub_factor_and_is_calculated(self):
        out = run(APP2, LOOSE_CASE)["output"]
        self.assertEqual(out["result_grade"], "calculated")
        self.assertEqual(out["factor_basis"], {"F": "not used", "V": "not used", "f": "not used"})
        self.assertIn("no hub factor", out["grade_note"])
        self.assertTrue(out["banner"].startswith("ISSUE-GRADE FACTOR BASIS: loose-type flange"))


class ScreenIsAlwaysScreening(unittest.TestCase):
    def test_screen_grade_is_screening_and_carries_its_banner(self):
        out = run(SCREEN, SCREEN_CASE)["output"]
        self.assertEqual(out["result_grade"], "screening")
        self.assertIn("leakage screen, not a stress check", out["grade_label"])
        self.assertTrue(out["banner"].startswith("SCREENING:"))

    def test_screen_grade_does_not_depend_on_the_outcome(self):
        within = run(SCREEN, dict(SCREEN_CASE, ratedPressure=1.0e6))
        exceeds = run(SCREEN, dict(SCREEN_CASE, ratedPressure=1.0))
        self.assertEqual((within["status"], exceeds["status"]), ("pass", "fail"))
        self.assertEqual(within["output"]["result_grade"], "screening")
        self.assertEqual(exceeds["output"]["result_grade"], "screening")


class NoAcceptanceWordingOnAScreeningRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = with_pre_flight(CASE)
        cls.env = bf.run_module(APP2, cls.job)
        cls.sheet = bf.render_sheet(cls.env)

    def test_sheet_leads_with_the_banner(self):
        lines = self.sheet.splitlines()
        self.assertEqual(lines[0], "# Bolted Flange Evaluation - " + APP2)
        self.assertEqual(lines[2], "**" + BANNER + "**")
        self.assertIn("Result grade: screening / reconstructed factors", self.sheet)
        self.assertIn("Hub factor basis: F series; V series; f series", self.sheet)

    def test_sheet_has_no_pass_or_issue_wording(self):
        text = strip_banner(self.sheet)
        self.assertIsNone(ACCEPT.search(text), ACCEPT.findall(text))

    def test_no_acceptance_wording_whether_the_tool_rule_is_met_or_missed(self):
        # Sweep the design pressure of the shipped example so the tool status runs both ways.
        with open(EXAMPLE, encoding="utf-8") as fh:
            ex = json.load(fh)
        statuses = set()
        for n in (300, 1500, 3000):
            env = bf.run_module(APP2, dict(ex, P=n))
            statuses.add(env["status"])
            text = strip_banner(bf.render_sheet(env))
            self.assertIsNone(ACCEPT.search(text), (n, env["status"], ACCEPT.findall(text)))
            self.assertIn("Tool status:", text)
        self.assertEqual(statuses, {"pass", "fail"}, "the sweep should exercise both tool statuses")

    def test_findings_and_output_strings_have_no_acceptance_wording(self):
        for w in self.env["warnings"]:
            self.assertIsNone(ACCEPT.search(strip_banner(w)), w)
        for k, v in self.env["output"].items():
            if isinstance(v, str) and k != "banner":
                self.assertIsNone(ACCEPT.search(v), (k, v))
        self.assertIsNone(ACCEPT.search(self.env["citation"]))

    def test_screening_sheet_never_prints_the_issue_grade_banner(self):
        self.assertNotIn("ISSUE-GRADE", self.sheet)

    def test_calculated_sheet_prints_the_issue_grade_banner_and_not_the_screening_one(self):
        env = bf.run_module(APP2, with_pre_flight(full_override()))
        sheet = bf.render_sheet(env)
        self.assertEqual(env["output"]["result_grade"], "calculated")
        self.assertEqual(sheet.splitlines()[2], "**" + env["output"]["banner"] + "**")
        self.assertIn("ISSUE-GRADE HUB FACTORS", sheet)
        self.assertNotIn("SCREENING / RECONSTRUCTED FACTORS", sheet)
        self.assertIn("Hub factor basis: F override; V override; f override", sheet)

    def test_partial_override_sheet_is_screening_and_names_the_missing_factor(self):
        s = series_factors(CASE)
        env = bf.run_module(APP2, with_pre_flight(dict(CASE, F_override=s["F"], f_override=s["f"])))
        sheet = bf.render_sheet(env)
        self.assertEqual(sheet.splitlines()[2], "**" + BANNER + "**")
        self.assertIn("Series factor(s) in use: V", sheet)
        self.assertIn("V_override", sheet)
        self.assertNotIn("ISSUE-GRADE", sheet)


class EngineNumbersUnchanged(unittest.TestCase):
    def test_fixture_parity_for_both_ported_modules(self):
        for module in (APP2, SCREEN):
            self.assertEqual(parity.run_fixture(bf.REGISTRY, module), [], module)

    def test_registry_result_shape_is_unchanged(self):
        for module in (APP2, SCREEN):
            res = run(module, parity.load(module)["cases"][0]["input"])
            self.assertEqual(set(res), {"module", "output", "status", "warnings"})

    def test_grade_keys_are_appended_after_the_engine_keys(self):
        out = run(APP2, CASE)["output"]
        self.assertEqual(list(out)[-len(bf.GRADE_KEYS):-1], list(bf.GRADE_KEYS[:-1]))
        self.assertEqual(list(out)[-1], "report_word")
        self.assertEqual(list(out)[-len(bf.GRADE_KEYS) - 1], "governing")
        screen = run(SCREEN, SCREEN_CASE)["output"]
        self.assertEqual(list(screen)[:4], ["momentTerm", "forceTerm", "Pe", "utilization"])
        self.assertEqual(list(screen)[4:], ["result_grade", "grade_label", "banner", "report_word"])


class CommandLineSheet(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")

    def test_default_format_is_the_json_envelope_with_the_grade(self):
        r = self._run(APP2, "--input-file", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(set(env), {"module", "status", "output", "warnings", "citation", "inputs", "user_supplied"})
        self.assertEqual(env["output"]["result_grade"], "screening")
        self.assertEqual(env["warnings"][0], BANNER)

    def test_sheet_format_prints_the_banner_first(self):
        r = self._run(APP2, "--input-file", EXAMPLE, "--format", "sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[2], "**" + BANNER + "**")
        self.assertIsNone(ACCEPT.search(strip_banner(r.stdout)))

    def test_sheet_format_with_all_overrides_prints_the_issue_grade_banner(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            ex = json.load(fh)
        job = full_override(ex)
        r = self._run(APP2, "--input", json.dumps(job), "--format", "sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ISSUE-GRADE HUB FACTORS", r.stdout)
        self.assertNotIn("SCREENING / RECONSTRUCTED FACTORS", r.stdout)

    def test_sheet_format_for_the_screen_and_derive(self):
        good = dict(P=500, F=2000, M_in_lbf=50000, G=6, ratedPressure=1975)
        r = self._run(SCREEN, "--input", json.dumps(good), "--format", "sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("**SCREENING:", r.stdout)
        self.assertIn("within the supplied rating", r.stdout)
        r = self._run("connections.flange-derive", "--input",
                      json.dumps(dict(facing="flat", gasket_ID=10, gasket_OD=12)), "--format", "sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("SCREENING", r.stdout)

    def test_bad_format_exits_2(self):
        r = self._run(APP2, "--input-file", EXAMPLE, "--format", "pdf")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")


class DocsStateTheGradeRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def read(*parts):
            with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
                return " ".join(fh.read().split())

        cls.skill = read("SKILL.md")
        cls.refs = {n: read("references", n) for n in ("app2-engine.md", "method-ladder.md", "rejection-checklist.md",
                                                       "tool-reference.md")}
        with open(TOOL, encoding="utf-8") as fh:
            cls.code = " ".join(fh.read().split())

    def test_every_document_states_the_label_and_the_taxonomy(self):
        for name, text in list(self.refs.items()) + [("SKILL.md", self.skill)]:
            self.assertIn("screening / reconstructed factors", text.lower(), name)
            self.assertIn("calculated", text, name)
            self.assertIn(TAXONOMY, text, name)
        self.assertIn(TAXONOMY, self.code)

    def test_skill_and_engine_doc_carry_the_banner_text_and_the_rule(self):
        self.assertIn("SCREENING / RECONSTRUCTED FACTORS", self.skill)
        self.assertIn(BANNER, self.refs["app2-engine.md"])
        self.assertIn("all three of `F_override`, `V_override`, `f_override`", self.skill)
        self.assertIn("partial override", self.skill)

    def test_ladder_says_the_screen_is_screening_always(self):
        self.assertIn("`screening` always", self.refs["method-ladder.md"])

    def test_script_banner_constants_match_the_documented_text(self):
        self.assertEqual(bf.BANNER_RECON, BANNER)
        self.assertEqual(bf.GRADE_LABEL_RECON, "screening / reconstructed factors")


class ReportWordAndBannerScope(unittest.TestCase):
    """Fix-pass additions: a report word beside the machine status, and a banner that does not over-claim."""

    def test_report_word_for_both_modules(self):
        self.assertIn(run(APP2, CASE)["output"]["report_word"], ("tool rule met", "tool rule not met"))
        for p, word in ((300, "within"), (3000, "exceeds")):
            inp = dict(SCREEN_CASE)
            inp["P"] = p
            res = run(SCREEN, inp)
            self.assertEqual(res["output"]["report_word"], "within" if res["status"] == "pass" else "exceeds")
        self.assertEqual(bf.GRADE_KEYS[-1], "report_word")

    def test_report_word_has_no_acceptance_wording(self):
        word = run(APP2, CASE)["output"]["report_word"]
        self.assertIsNone(re.search(r"pass|issue|accept", word, re.I))

    def test_calculated_and_loose_banners_state_the_scope(self):
        for banner in (bf.BANNER_CALCULATED, bf.BANNER_LOOSE):
            self.assertIn("Peq external-load treatment", banner)
            self.assertIn("defaulted inputs", banner)
            self.assertIn("rejection checklist", banner)

    def test_skill_guidance_no_longer_says_the_joint_passes_the_screen(self):
        skill = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "piping-toolset", "skills", "bolted-flange")
        for rel in ("SKILL.md", os.path.join("references", "method-ladder.md")):
            with open(os.path.join(skill, rel), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("passes the screen", text)
            self.assertNotIn("passing the screen", text)


if __name__ == "__main__":
    unittest.main()
