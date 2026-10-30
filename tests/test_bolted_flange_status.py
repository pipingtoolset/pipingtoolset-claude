"""Result status taxonomy tests for the bolted-flange skill (plugin 0.8.0, B9).

Every envelope carries `result_status` (calculated / screening / manual check required / pointer only
/ not checked: the worst word of `checks`), `checks` [{name, result_status, status, note}] and
`not_checked` (methods the module never performs). The existing `status` words and every number are
unchanged. No positive banner wording is printed while the word is manual check required, pointer
only, or screening with an unresolved reconstructed hub factor.

    python -m unittest tests.test_bolted_flange_status -v
"""

from __future__ import annotations

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
EXAMPLE_JOB = os.path.join(SCRIPTS, "examples", "integral-weld-neck.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import bolted_flange as bf  # noqa: E402
import parity  # noqa: E402

SCREEN = "connections.flange-equivalent-pressure"
APP2 = "aux.app2-flange-integral"
DERIVE = "connections.flange-derive"
WORDS = {"calculated", "screening", "manual check required", "pointer only", "not checked"}
ACCEPT = re.compile(r"\b(pass|passes|passed|passing|ok|issued?|issue-grade|accepted|acceptable|deliverable)\b", re.I)


def load_example():
    with open(EXAMPLE_JOB, encoding="utf-8") as fh:
        return json.load(fh)


def factors(job):
    return bf.hub_factors(job["g1"] / job["g0"], job["h"] / (job["B"] * job["g0"]) ** 0.5)


def closed_job(**over):
    """Integral job with all three overrides, Sn and both loads: nothing left open."""
    job = load_example()
    s = factors(job)
    job.update(F_override=s["F"], V_override=s["V"], f_override=s["f"])
    job.update(over)
    return job


def loose_job(**over):
    job = {k: v for k, v in load_example().items() if k not in ("g0", "g1", "h")}
    job["attachment"] = "loose"
    job.update(over)
    return job


def screen_job(**over):
    job = {"P": 500, "F": 2000, "M_in_lbf": 50000, "G": 6, "ratedPressure": 1975}
    job.update(over)
    return job


def record(**over):
    rec = {"schema": "pipingtoolset.project-basis/1", "code": {"standard": "B31.3", "edition": "2022"},
           "states": [{"key": "DES", "role": "design", "T_F": 300, "P_psig": 500}], "units": {"system": "USC"}}
    rec.update(over)
    return rec


def by_name(env):
    return {c["name"]: c for c in env["checks"]}


class EveryEnvelopeCarriesTheStatus(unittest.TestCase):
    JOBS = (
        (DERIVE, {"facing": "flat", "gasket_ID": 10, "gasket_OD": 12}),
        (SCREEN, screen_job()),
        (APP2, load_example()),
        (APP2, closed_job()),
        (APP2, loose_job()),
    )

    def test_the_word_is_one_of_exactly_five(self):
        for module, job in self.JOBS:
            env = bf.run_module(module, dict(job))
            self.assertIn(env["result_status"], WORDS, module)
            self.assertEqual(set(bf.RESULT_STATUS), WORDS)

    def test_the_envelope_word_is_the_envelope_status_of_its_checks(self):
        for module, job in self.JOBS:
            env = bf.run_module(module, dict(job))
            self.assertEqual(env["result_status"], bf.envelope_status(env["checks"]), module)
            self.assertTrue(env["checks"], module)

    def test_check_shape(self):
        for module, job in self.JOBS:
            env = bf.run_module(module, dict(job))
            for c in list(env["checks"]) + list(env["not_checked"]):
                self.assertTrue({"name", "result_status", "status", "note"} <= set(c), c)
                self.assertIn(c["result_status"], WORDS, c)
                self.assertIn(c["status"], ("pass", "fail", "na"), c)

    def test_not_checked_entries_are_all_not_checked(self):
        env = bf.run_module(APP2, closed_job())
        self.assertTrue(env["not_checked"])
        for c in env["not_checked"]:
            self.assertEqual((c["result_status"], c["status"]), ("not checked", "na"))

    def test_the_existing_status_words_and_numbers_are_unchanged(self):
        for module, job in ((SCREEN, screen_job()), (APP2, load_example())):
            env = bf.run_module(module, dict(job))
            want = bf.REGISTRY[module](dict(job))
            self.assertEqual(env["status"], want["status"], module)
            self.assertEqual(env["output"], bf._clean_zero(want["output"]), module)

    def test_derive_is_calculated_and_lists_nothing_missing(self):
        env = bf.run_module(DERIVE, {"facing": "flat", "gasket_ID": 10, "gasket_OD": 12})
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(env["not_checked"], [])


class EachWordIsReachable(unittest.TestCase):
    def test_calculated(self):
        env = bf.run_module(APP2, closed_job())
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual({c["result_status"] for c in env["checks"]}, {"calculated"})
        self.assertFalse([c for c in env["checks"] if c.get("unresolved_factor")])

    def test_calculated_for_a_loose_flange_that_uses_no_hub_factor(self):
        env = bf.run_module(APP2, loose_job())
        self.assertEqual(env["output"]["result_grade"], "calculated")
        self.assertEqual(env["result_status"], "calculated")

    def test_screening_for_the_leakage_screen_always(self):
        env = bf.run_module(SCREEN, screen_job())
        self.assertEqual(env["result_status"], "screening")
        self.assertFalse([c for c in env["checks"] if c.get("unresolved_factor")])
        env = bf.run_module(SCREEN, screen_job(ratedPressure=100))
        self.assertEqual((env["status"], env["result_status"]), ("fail", "screening"))

    def test_screening_with_an_unresolved_factor_for_the_default_series(self):
        env = bf.run_module(APP2, load_example())
        self.assertEqual(env["result_status"], "screening")
        marked = [c["name"] for c in env["checks"] if c.get("unresolved_factor")]
        self.assertEqual(marked, ["flange stresses, operating and seating", "rigidity J <= 1"])
        self.assertEqual(by_name(env)["bolt area Ab >= Am"]["result_status"], "calculated")

    def test_a_partial_override_stays_screening_with_an_unresolved_factor(self):
        job = load_example()
        s = factors(job)
        env = bf.run_module(APP2, dict(job, F_override=s["F"], f_override=s["f"]))
        self.assertEqual(env["output"]["result_grade"], "screening")
        self.assertEqual(env["result_status"], "screening")
        self.assertIn("V", by_name(env)["rigidity J <= 1"]["note"])

    def test_result_grade_and_result_status_agree_on_screening(self):
        for job in (load_example(), closed_job(), loose_job()):
            env = bf.run_module(APP2, dict(job))
            self.assertEqual(env["output"]["result_grade"] == "screening", env["result_status"] == "screening")

    def test_manual_check_required_from_the_code_route(self):
        env = bf.run_module(APP2, dict(closed_job(), project_basis=record(code={"standard": "B31.9"}, states=[
            {"key": "DES", "role": "design", "T_F": 300, "P_psig": 300}])))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(by_name(env)["code route"]["result_status"], "manual check required")

    def test_manual_check_required_from_chapter_ix(self):
        rec = record(service={"fluid_category": "High Pressure"}, states=[
            {"key": "DES", "role": "design", "T_F": 300, "P_psig": 500}])
        env = bf.run_module(SCREEN, dict(screen_job(), project_basis=rec))
        self.assertEqual(env["result_status"], "manual check required")

    def test_pointer_only_from_an_owner_acceptance_pointer(self):
        rec = record(owner_practice=[{"document": "PNC00004", "items": [
            {"name": "flange acceptance", "value": "from the owner document"}]}])
        env = bf.run_module(SCREEN, dict(screen_job(), project_basis=rec))
        self.assertEqual(env["result_status"], "pointer only")
        self.assertEqual(env["status"], "pass")

    def test_a_missing_input_is_listed_not_checked_and_never_sets_the_word(self):
        job = {k: v for k, v in closed_job().items() if k not in ("Sn", "SnAmbient")}
        env = bf.run_module(APP2, job)
        self.assertEqual(env["result_status"], "calculated")
        self.assertIn("not performed by this module: hub stress cap 2.5 Sn", bf.status_why(env["checks"]))
        self.assertEqual(by_name(env)["hub stress cap 2.5 Sn"]["result_status"], "not checked")
        self.assertEqual(env["output"]["result_grade"], "calculated")

    def test_a_pressure_only_run_says_the_loads_were_not_evaluated(self):
        job = {k: v for k, v in closed_job().items() if k not in ("Fax", "Mext_in_lbf")}
        env = bf.run_module(APP2, job)
        self.assertEqual(by_name(env)["external loads"]["result_status"], "not checked")
        self.assertEqual(env["result_status"], "calculated")
        self.assertIn("not performed by this module: external loads", bf.status_why(env["checks"]))

    def test_severity_order_manual_over_pointer_over_screening(self):
        rec = record(code={"standard": "B31.9"}, owner_practice=[{"document": "PNC00004", "items": [
            {"name": "flange acceptance", "value": "tbd"}]}])
        env = bf.run_module(SCREEN, dict(screen_job(), project_basis=rec))
        self.assertTrue({"screening", "pointer only", "manual check required"}
                        <= {c["result_status"] for c in env["checks"]})
        self.assertEqual(env["result_status"], "manual check required")


class NotCheckedListIsExplicit(unittest.TestCase):
    NAMES = ("UG-44(b) / VIII-2 4.16.12 interaction", "ASME III NC-3658.3", "EN 1591-1",
             "PCC-1 Appendix O assembly bolt stress")

    def test_both_pressure_modules_name_the_interaction_methods(self):
        for module, job in ((SCREEN, screen_job()), (APP2, closed_job())):
            names = [c["name"] for c in bf.run_module(module, job)["not_checked"]]
            for want in self.NAMES:
                self.assertIn(want, names, module)

    def test_the_detailed_module_adds_the_shear_check_and_moe(self):
        names = [c["name"] for c in bf.run_module(APP2, closed_job())["not_checked"]]
        self.assertIn("VIII-2 4.16.7.2 Step 9(b) shear check", names)
        self.assertIn("Code external-moment term Moe", names)

    def test_the_screen_says_it_does_not_check_stress(self):
        names = [c["name"] for c in bf.run_module(SCREEN, screen_job())["not_checked"]]
        self.assertIn("bolt, gasket seating and flange stress", names)

    def test_a_listed_method_never_changes_the_envelope_word(self):
        self.assertEqual(bf.run_module(APP2, closed_job())["result_status"], "calculated")


class BannerRule(unittest.TestCase):
    def test_the_issue_grade_banner_is_kept_when_nothing_blocks_it(self):
        env = bf.run_module(APP2, closed_job())
        self.assertTrue(env["output"]["banner"].startswith("ISSUE-GRADE HUB FACTORS"))
        self.assertEqual(env["warnings"][0], env["output"]["banner"])

    def test_the_banner_is_withheld_under_manual_check_required(self):
        rec = record(code={"standard": "B31.9"}, states=[{"key": "DES", "role": "design", "T_F": 300, "P_psig": 300}])
        env = bf.run_module(APP2, dict(closed_job(), project_basis=rec))
        banner = env["output"]["banner"]
        self.assertTrue(banner.startswith("MANUAL CHECK REQUIRED:"), banner)
        self.assertNotIn("ISSUE-GRADE", banner)
        self.assertEqual(env["warnings"][0], banner)
        self.assertEqual(env["warnings"].count(banner), 1)
        self.assertEqual(env["output"]["result_grade"], "calculated")  # the grade keys are unchanged

    def test_no_acceptance_wording_on_a_blocked_sheet(self):
        rec = record(code={"standard": "B31.9"}, states=[{"key": "DES", "role": "design", "T_F": 300, "P_psig": 300}])
        env, basis = bf.run_with_basis(APP2, dict(closed_job(), project_basis=rec))
        text = bf.render_sheet(env, basis)
        self.assertIsNone(ACCEPT.search(text), ACCEPT.findall(text))
        self.assertIn("Result status: manual check required", text)

    def test_no_acceptance_wording_on_a_pointer_only_sheet(self):
        rec = record(owner_practice=[{"document": "PNC00004", "items": [{"name": "flange acceptance", "value": "tbd"}]}])
        env, basis = bf.run_with_basis(SCREEN, dict(screen_job(), project_basis=rec))
        text = bf.render_sheet(env, basis)
        self.assertIsNone(ACCEPT.search(text.replace("PNC00004", "")), ACCEPT.findall(text))
        self.assertIn("Result status: pointer only", text)

    def test_an_assumed_record_item_is_one_manual_check_row_and_withholds_the_banner(self):
        rec = record(assumptions=[{"item": "Rating at design temperature not yet read", "status": "ASSUMED"},
                                  {"item": "Gasket factors from the datasheet", "status": "confirmed"},
                                  {"item": "Bolt material per the line class"}],
                     states=[{"key": "DES", "role": "design", "T_F": 300, "P_psig": 300}])
        env, basis = bf.run_with_basis(APP2, dict(closed_job(), project_basis=rec))
        rows = [c for c in env["checks"] if c["name"] == "ASSUMED inputs"]
        self.assertEqual(rows, [{"name": "ASSUMED inputs", "result_status": "manual check required", "status": "na",
                                 "note": "confirm before issue: Rating at design temperature not yet read; "
                                         "Bolt material per the line class"}])
        self.assertEqual(env["result_status"], "manual check required")
        banner = env["output"]["banner"]
        self.assertTrue(banner.startswith("MANUAL CHECK REQUIRED: ASSUMED inputs (confirm before issue: "), banner)
        self.assertNotIn("ISSUE-GRADE", banner)
        text = bf.render_sheet(env, basis)
        bare = text.replace("confirm before issue", "")      # the mandated ASSUMED wording, not a banner
        self.assertIsNone(ACCEPT.search(bare), ACCEPT.findall(bare))
        self.assertIn("Result status: manual check required - ASSUMED inputs: confirm before issue: ", text)

    def test_the_banner_rule_follows_the_shared_helper(self):
        cases = (("calculated", False, True), ("not checked", False, True), ("screening", False, True),
                 ("screening", True, False), ("pointer only", False, False), ("manual check required", False, False))
        for word, unresolved, allowed in cases:
            self.assertEqual(bf.banner_allowed(word, unresolved), allowed, (word, unresolved))

    def test_a_screening_run_with_series_factors_prints_no_issue_grade_banner(self):
        env = bf.run_module(APP2, load_example())
        self.assertFalse(bf.checks_banner_allowed(env["checks"]))
        self.assertNotIn("ISSUE-GRADE", env["output"]["banner"])
        self.assertTrue(env["output"]["banner"].startswith("SCREENING / RECONSTRUCTED FACTORS"))


class SheetCarriesTheStatusLine(unittest.TestCase):
    def test_the_line_sits_under_the_title_block(self):
        for module, job, word in ((SCREEN, screen_job(), "screening"), (APP2, closed_job(), "calculated"),
                                  (APP2, load_example(), "screening")):
            lines = bf.render_sheet(bf.run_module(module, dict(job))).splitlines()
            self.assertEqual(lines[0], "# Bolted Flange Evaluation - " + module)
            hits = [i for i, ln in enumerate(lines) if ln.startswith("Result status: ")]
            self.assertEqual(len(hits), 1, module)
            self.assertLess(hits[0], 6, module)
            self.assertTrue(lines[hits[0]].startswith(f"Result status: {word} - "), lines[hits[0]])

    def test_derive_has_no_banner_so_the_line_follows_the_title(self):
        env = bf.run_module(DERIVE, {"facing": "flat", "gasket_ID": 10, "gasket_OD": 12})
        lines = bf.render_sheet(env).splitlines()
        self.assertTrue(lines[2].startswith("Result status: calculated - "), lines[:4])

    def test_the_sheet_lists_the_checks_and_the_methods_not_checked(self):
        text = bf.render_sheet(bf.run_module(APP2, closed_job()))
        self.assertIn("## Checks", text)
        self.assertIn("| bolt area Ab >= Am | calculated | met |", text)
        self.assertIn("## Not checked by this module", text)
        self.assertIn("- EN 1591-1:", text)

    def test_the_cli_sheet_is_utf_8_and_carries_the_em_dash(self):
        r = subprocess.run([sys.executable, TOOL, APP2, "--input-file", EXAMPLE_JOB, "--format", "sheet"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Result status: screening - ", r.stdout)

    def test_the_cli_json_carries_the_status_in_ascii(self):
        r = subprocess.run([sys.executable, TOOL, SCREEN, "--input", json.dumps(screen_job())],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["result_status"], "screening")
        self.assertTrue(r.stdout.isascii())


class ParityUnchanged(unittest.TestCase):
    def test_fixture_parity(self):
        for module in (APP2, SCREEN):
            self.assertEqual(parity.run_fixture(bf.REGISTRY, module), [], module)

    def test_registry_results_have_no_status_keys(self):
        for module in (APP2, SCREEN):
            res = bf.REGISTRY[module](dict(parity.load(module)["cases"][0]["input"]))
            self.assertEqual(set(res), {"module", "output", "status", "warnings"})
            self.assertNotIn("result_status", res["output"])


if __name__ == "__main__":
    unittest.main()
