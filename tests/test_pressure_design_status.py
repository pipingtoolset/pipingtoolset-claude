"""pressure-design wiring of the output status taxonomy (plugin 0.8.0, B9).

Every envelope of scripts/pressure_design.py carries result_status (the worst word of checks[]),
checks[] {name, result_status, status, note}, banner_allowed and result_status_line. The words
this skill reaches: calculated, screening (branch module on a B31.1 record), manual check required
(thin-wall gate, Category M / Chapter IX record), pointer only (a code_values pointer entry) and
not checked (each module's known limits). Envelope "status" words and values stay as before.

Inputs are the vendored fixture inputs or fictitious round numbers; none is a code-table value.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pressure-design")
SCRIPTS = os.path.join(SKILL, "scripts")
CLI = os.path.join(SCRIPTS, "pressure_design.py")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
import pressure_design as pd  # noqa: E402

B313 = "piping.b313-wall-thickness"
B311 = "piping.b311-wall-thickness"
MAWP = "piping.b31-allowable-pressure"
BRANCH = "piping.branch-reinforcement"
MITER = "piping.miter-allowable-pressure"
LEAK = "piping.leak-test-pressure"
WORDS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
POSITIVE = re.compile(r"\b(PASS|OK|ISSUE|DELIVERABLE)\b")
SCHEMA = "pipingtoolset.project-basis/1"


def fixture(module: str, i: int = 0) -> dict:
    job = dict(parity.load(module)["cases"][i]["input"])
    if module in pd.W_MODULES:
        job["W_basis"] = "seamless"
    return job


def record(**over) -> dict:
    return dict({"schema": SCHEMA, "code": {"standard": "B31.3", "edition": "2022"}}, **over)


def pointer(table: str = "the allowable stress table of record") -> dict:
    return {"mode": "pointer", "unit": "ksi", "source": "connector",
            "citation": {"standard": "ASME B31.3", "edition": "2024", "table": table, "row": "the user's line",
                         "column": "S"}}


def cli(module: str, inputs: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, CLI, module, "--input", json.dumps(inputs)],
                          capture_output=True, text=True, encoding="utf-8")


def words(env: dict) -> dict:
    return {c["name"]: c["result_status"] for c in env["checks"]}


class EnvelopeContract(unittest.TestCase):
    """Shape and invariants on every fixture run, plus the banner rule on every run in this file."""

    def assert_contract(self, env: dict) -> None:
        self.assertIn(env["result_status"], WORDS)
        self.assertTrue(env["checks"])
        for c in env["checks"]:
            self.assertIn(c["result_status"], WORDS)
            self.assertIn(c["status"], ("pass", "fail", "na"))
            self.assertTrue(c["name"])
        self.assertEqual(env["result_status"], pd.envelope_status(env["checks"]))
        self.assertEqual(env["banner_allowed"], pd.checks_banner_allowed(env["checks"]))
        self.assertTrue(env["result_status_line"].startswith(f"Result status: {env['result_status']} - "))
        if not env["banner_allowed"]:
            self.assertIsNone(POSITIVE.search(json.dumps(env, ensure_ascii=False)))

    def test_every_fixture_run_carries_the_taxonomy_and_unchanged_status(self):
        for module in pd.REGISTRY:
            for i, case in enumerate(parity.load(module)["cases"]):
                env = pd.run_module(module, fixture(module, i))
                engine = pd.REGISTRY[module](dict(case["input"]))
                self.assertEqual(env["status"], engine["status"], f"{module} {i}")
                self.assertEqual(env["checks"][0]["status"], engine["status"], f"{module} {i}")
                self.assert_contract(env)

    def test_parity_is_green(self):
        for module in pd.REGISTRY:
            self.assertEqual(parity.run_fixture(pd.REGISTRY, module), [], module)

    def test_the_cli_prints_the_keys(self):
        r = cli(B313, fixture(B313))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        for key in ("result_status", "checks", "banner_allowed", "result_status_line"):
            self.assertIn(key, env)
        self.assert_contract(env)


class EachWord(EnvelopeContract):

    def test_calculated(self):
        # MAWP has no listed limit once a design pressure is compared: every check calculated.
        allow = pd.run_module(MAWP, fixture(MAWP))["output"]["allowablePressure"]
        rec = record(states=[{"key": "DES", "role": "design", "P_psig": round(allow / 2)}])
        env = pd.run_module(MAWP, dict(fixture(MAWP), project_basis=rec))
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual({c["result_status"] for c in env["checks"]}, {"calculated"})
        check = [c for c in env["checks"] if c["name"] == pd.CHECK_DESIGN_P][0]
        self.assertEqual(check["status"], "pass")
        self.assertTrue(env["banner_allowed"])
        self.assert_contract(env)
        rec["states"][0]["P_psig"] = round(allow * 2)
        env = pd.run_module(MAWP, dict(fixture(MAWP), project_basis=rec))
        self.assertEqual([c for c in env["checks"] if c["name"] == pd.CHECK_DESIGN_P][0]["status"], "fail")
        self.assertEqual(env["status"], "na")                           # envelope status unchanged

    def test_not_checked_lists_each_modules_known_limits(self):
        # The limits are listed in checks[] but never set the envelope word: a clean run reads calculated.
        for module in pd.REGISTRY:
            env = pd.run_module(module, fixture(module))
            listed = {c["name"] for c in env["checks"] if c["result_status"] == "not checked"}
            self.assertTrue({n for n, _ in pd.NOT_CHECKED[module]} <= listed, module)
            self.assertEqual(env["result_status"], "calculated", module)
            self.assertTrue(env["result_status_line"].startswith("Result status: calculated - "), module)
            self.assertTrue(env["banner_allowed"], module)
            self.assertEqual(env["checks"][0]["result_status"], "calculated", module)
            self.assertIn("not performed by this module", env["result_status_line"], module)
            self.assert_contract(env)
        mawp = pd.run_module(MAWP, fixture(MAWP))
        self.assertEqual(words(mawp)[pd.CHECK_DESIGN_P], "not checked")

    def test_an_assumed_item_in_the_record_is_one_manual_check_row(self):
        rec = dict(schema=SCHEMA, assumptions=[{"item": "Corrosion allowance per the line list", "status": "ASSUMED"},
                                  {"item": "Mill tolerance 12.5%"},
                                  {"item": "Design pressure per the line list", "status": "confirmed"}])
        for module in pd.REGISTRY:
            env = pd.run_module(module, dict(fixture(module), project_basis=rec))
            rows = [c for c in env["checks"] if c["name"] == "ASSUMED inputs"]
            self.assertEqual(rows, [{"name": "ASSUMED inputs", "result_status": "manual check required",
                                     "status": "na", "note": "confirm before issue: Corrosion allowance per the "
                                     "line list; Mill tolerance 12.5%"}], module)
            self.assertEqual(env["result_status"], "manual check required", module)
            self.assertFalse(env["banner_allowed"], module)
            self.assertIn("confirm before issue: Corrosion allowance", env["result_status_line"], module)
            self.assertIsNone(POSITIVE.search(env["result_status_line"]), module)
        rec["assumptions"] = rec["assumptions"][2:]
        env = pd.run_module(MAWP, dict(fixture(MAWP), project_basis=rec))
        self.assertNotIn("ASSUMED inputs", words(env))

    def test_screening_branch_on_a_b31_1_record(self):
        for i in range(len(parity.load(BRANCH)["cases"])):
            env = pd.run_module(BRANCH, dict(fixture(BRANCH, i), project_basis=record(code={"standard": "B31.1"})))
            main = env["checks"][0]
            self.assertEqual(main["result_status"], "screening")
            self.assertNotIn("unresolved_factor", main)
            self.assertEqual(main["status"], pd.REGISTRY[BRANCH](dict(fixture(BRANCH, i)))["status"])
            self.assertEqual(env["result_status"], "screening")
            self.assertTrue(env["banner_allowed"])
            self.assertIn("screening check against the B31.3 form", env["result_status_line"])
            self.assert_contract(env)
        self.assertEqual(pd.run_module(BRANCH, dict(fixture(BRANCH), project_basis=record()))["checks"][0]
                         ["result_status"], "calculated")

    def test_manual_check_required_on_the_thin_wall_gate(self):
        job = dict(P=8000, D=10, S=20000, E=1, W=1, W_basis="seamless", Y=0.7, c=0, millTolerance=0.125)
        env = pd.run_module(B313, job)
        self.assertEqual(env["status"], "manual check required")       # the 0.7.2 word, unchanged
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(words(env)[pd.MAIN_CHECK[B313]], "manual check required")
        self.assertEqual(words(env)[pd.CHECK_VALIDITY], "manual check required")
        self.assertFalse(env["banner_allowed"])
        self.assertNotIn('"pass"', json.dumps(env))
        self.assertIn("equation value, not a design basis", env["result_status_line"])
        self.assert_contract(env)

    def test_manual_check_required_on_a_tripped_mawp_skips_the_design_pressure_comparison(self):
        job = dict(D=2, t=0.9, millTolerance=0, A=0, S=20000, E=1, W=1, W_basis="seamless", y=0.4, Mf=1)
        env = pd.run_module(MAWP, dict(job, project_basis=record(states=[{"key": "D", "role": "design",
                                                                           "P_psig": 100}])))
        self.assertEqual(env["result_status"], "manual check required")
        self.assertNotIn(pd.CHECK_DESIGN_P, words(env))
        self.assert_contract(env)

    def test_manual_check_required_for_category_m_or_chapter_ix(self):
        for rec in (record(service={"fluid_category": "Category M"}),
                    record(service={"fluid_category": "High Pressure"}),
                    record(code={"standard": "B31.3", "route": "Chapter IX"})):
            env = pd.run_module(B313, dict(fixture(B313), project_basis=rec))
            self.assertEqual(words(env)[pd.CHECK_SERVICE], "manual check required")
            self.assertEqual(env["result_status"], "manual check required")
            self.assertEqual(env["status"], "na")                       # status word unchanged
            self.assertFalse(env["banner_allowed"])
            self.assert_contract(env)
        for fc in ("Normal", "Category D"):
            env = pd.run_module(B313, dict(fixture(B313), project_basis=record(service={"fluid_category": fc})))
            self.assertNotIn(pd.CHECK_SERVICE, words(env), fc)

    def test_special_service_reaches_warnings_banner_and_result_grade(self):
        rec = record(service={"fluid_category": "Category M"})
        env = pd.run_module(B313, dict(fixture(B313), project_basis=rec))
        self.assertEqual(env["result_grade"], "manual check required")
        self.assertTrue(env["banner"].startswith("MANUAL CHECK REQUIRED: fluid service Category M"))
        self.assertEqual(env["warnings"][0], env["banner"])
        self.assertTrue(env["output"])                                  # engine numbers kept
        self.assertEqual(env["status"], "na")
        self.assertIsNone(POSITIVE.search(env["banner"]))
        # an ungated module: warning and banner, no result_grade key
        env = pd.run_module(LEAK, dict(fixture(LEAK), project_basis=rec))
        self.assertNotIn("result_grade", env)
        self.assertEqual(env["warnings"][0], env["banner"])
        self.assertTrue(env["banner"].startswith("MANUAL CHECK REQUIRED: fluid service"))
        # no flag: the 0.7.2 fields are as before
        env = pd.run_module(B313, dict(fixture(B313), project_basis=record(service={"fluid_category": "Normal"})))
        self.assertEqual(env["result_grade"], "calculated")
        self.assertNotIn("banner", env)

    def test_special_service_keeps_a_gate_or_pointer_banner_first(self):
        rec = record(service={"fluid_category": "High Pressure"})
        job = {k: v for k, v in fixture(B313).items() if k != "S"}
        env = pd.run_module(B313, dict(job, code_values={"S": pointer()}, project_basis=rec))
        self.assertTrue(env["banner"].startswith("POINTER ONLY: "))
        self.assertEqual(env["warnings"][0], env["banner"])
        self.assertTrue(env["warnings"][1].startswith("MANUAL CHECK REQUIRED: fluid service High Pressure"))
        self.assertEqual(env["result_grade"], "pointer only")
        job = dict(D=2, t=0.9, millTolerance=0, A=0, S=20000, E=1, W=1, W_basis="seamless", y=0.4, Mf=1)
        env = pd.run_module(MAWP, dict(job, project_basis=rec))
        self.assertTrue(env["banner"].startswith("MANUAL CHECK REQUIRED: ") and "D/6" in env["banner"])
        self.assertEqual(env["warnings"][0], env["banner"])
        self.assertTrue(env["warnings"][1].startswith("MANUAL CHECK REQUIRED: fluid service High Pressure"))
        self.assertEqual(env["result_grade"], "manual check required")

    def test_pointer_only(self):
        job = {k: v for k, v in fixture(B313).items() if k != "S"}
        env = pd.run_module(B313, dict(job, code_values={"S": pointer()}))
        self.assertEqual(env["status"], "pointer only")
        self.assertEqual(env["result_grade"], "pointer only")
        self.assertEqual(env["output"], {})
        self.assertEqual(env["result_status"], "pointer only")
        self.assertEqual(words(env)[pd.MAIN_CHECK[B313]], "pointer only")
        self.assertNotIn("validity", env)
        self.assertTrue(env["banner"].startswith("POINTER ONLY: S "))
        self.assertEqual(env["warnings"][0], env["banner"])
        self.assertEqual(env["value_pointers"]["S"]["citation"]["table"], "the allowable stress table of record")
        self.assertIn("the allowable stress table of record", env["result_status_line"])
        self.assertFalse(env["banner_allowed"])
        self.assert_contract(env)

    def test_pointer_only_by_cli_exits_0_and_mixes_with_cited_values(self):
        job = {k: v for k, v in fixture(LEAK).items() if k not in ("S", "ST")}
        cited = {"value": 20, "unit": "ksi", "source": "user",
                 "citation": {"standard": "s", "edition": "e", "table": "t", "row": "r"}}
        r = cli(LEAK, dict(job, code_values={"S": pointer(), "ST": cited}))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["result_status"], "pointer only")
        self.assertEqual(env["inputs"]["ST"], 20000.0)
        self.assertEqual(sorted(env["code_value_provenance"]), ["ST"])
        self.assert_contract(env)

    def test_pointer_errors_exit_2(self):
        job = {k: v for k, v in fixture(B313).items() if k != "S"}
        bad = (
            (dict(job, code_values={"S": dict(pointer(), value=12)}), "is a pointer and carries no value"),
            (dict(job, code_values={"Q": pointer()}), "code_values.Q is not an input of"),
            (dict(fixture(B313), code_values={"S": pointer()}), "code_values.S is a pointer but input S has a value"),
            (dict({k: v for k, v in job.items() if k != "D"}, code_values={"S": pointer()}),
             "missing required input 'D'"),
            (dict(job, code_values={"S": dict(pointer(), citation={"standard": "x"})}), "needs standard and table"),
            (dict(job, code_values={"S": dict(pointer(), source="web")}), "source must be"),
        )
        for inputs, msg in bad:
            r = cli(B313, inputs)
            self.assertEqual(r.returncode, 2, msg)
            self.assertIn(msg, r.stderr)

    def test_screening_is_reached_only_through_the_record(self):
        for module in pd.REGISTRY:
            for i in range(len(parity.load(module)["cases"])):
                self.assertNotEqual(pd.run_module(module, fixture(module, i))["result_status"], "screening")


class SkillText(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.skill = fh.read()
        with open(os.path.join(SKILL, "references", "modules.md"), encoding="utf-8") as fh:
            cls.modules = fh.read()

    def test_calc_sheet_has_the_status_line_under_the_title(self):
        title = "# Pressure Design Calculation — [line number / system]\n"
        self.assertIn(title + "Result status: [result_status_line from the run]\n", self.skill)

    def test_section_5_follows_the_banner_rule(self):
        self.assertIn("PASS or FAIL for each, with the margin, only where banner_allowed is true.", self.skill)
        self.assertIn('A "manual check required" or "pointer only" run shows', self.skill)
        self.assertNotIn('only where status is not "manual check required"', self.skill)

    def test_skill_names_the_five_words_and_the_pointer_route(self):
        for word in WORDS:
            self.assertIn(word, self.skill, word)
        self.assertIn('`"mode": "pointer"`', self.skill)
        self.assertIn("references/project-basis.md#result-status-words", self.skill)

    def test_modules_reference_lists_every_not_checked_item(self):
        self.assertIn("## Project basis and result status (0.8.0)", self.modules)
        for word in WORDS:
            self.assertIn(f"| {word} |", self.modules, word)


if __name__ == "__main__":
    unittest.main()
