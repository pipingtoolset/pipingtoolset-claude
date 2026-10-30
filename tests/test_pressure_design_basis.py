"""pressure-design wiring of the shared project basis record (plugin 0.8.0, B8).

scripts/pressure_design.py takes a pipingtoolset.project-basis/1 record as a top-level
"project_basis" object or as --project-basis <file>. This skill's fill map: code (MAWP and bend
modules) from code.standard, which must lie in the module's code family on every module; edition
from code.edition; P from the design state (role design, else the first state); W_basis "seamless"
from materials[use=pipe] when its form is seamless and W_basis is absent. units.system SI exits 2.

Inputs are the vendored fixture inputs or fictitious round numbers; none is a code-table value.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
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
BEND = "piping.bend-thickness"
MITER = "piping.miter-allowable-pressure"
LEAK = "piping.leak-test-pressure"
SCHEMA = "pipingtoolset.project-basis/1"
# SKILL.md word count (str.split) before 0.8.0: the B8/B9 text had to come with zero net growth.
SKILL_WORDS_0_7_2 = 2976


def fixture(module: str, i: int = 0) -> dict:
    """A fixture input made runnable through run_module (W_basis where the 0.7.2 W gate needs it)."""
    job = dict(parity.load(module)["cases"][i]["input"])
    if module in pd.W_MODULES:
        job["W_basis"] = "seamless"
    return job


def record(**over) -> dict:
    rec = {"schema": SCHEMA,
           "code": {"standard": "B31.3", "edition": "2022", "route": "Normal fluid service"},
           "states": [{"key": "OPE", "name": "Operating", "role": "operating", "T_F": 300, "P_psig": 900},
                      {"key": "DES", "name": "Design", "role": "design", "T_F": 350, "P_psig": 2000}],
           "assumptions": [{"item": "Corrosion allowance per the line list", "status": "ASSUMED",
                            "note": "line list not issued", "owner": "lead"},
                           {"item": "Design state governs", "status": "confirmed"}]}
    for k, v in over.items():
        if v is None:
            rec.pop(k, None)
        else:
            rec[k] = v
    return rec


def cli(module: str, inputs: dict, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, CLI, module, "--input", json.dumps(inputs), *extra],
                          capture_output=True, text=True, encoding="utf-8")


def used(env: dict) -> dict:
    """{basis path: (input, action)} from project_basis_applied.fields_used."""
    return {u["basis"]: (u["input"], u["action"]) for u in env["project_basis_applied"]["fields_used"]}


class FillMap(unittest.TestCase):

    def test_p_and_edition_fill_from_the_design_state_and_code(self):
        job = fixture(B313)
        del job["P"]
        env = pd.run_module(B313, dict(job, project_basis=record()))
        base = pd.run_module(B313, fixture(B313))
        self.assertEqual(env["inputs"]["P"], 2000)
        self.assertEqual(env["inputs"]["edition"], "2022")
        self.assertEqual(env["output"], base["output"])           # same P, same numbers
        self.assertEqual(env["status"], base["status"])
        u = used(env)
        self.assertEqual(u["states[role=design|first].P_psig"], ("P", "filled"))
        self.assertEqual(u["code.edition"], ("edition", "filled"))
        self.assertEqual(u["code.standard"], (None, "noted"))
        self.assertEqual(u["states[role=design|first].T_F"], (None, "noted"))

    def test_p_falls_back_to_the_first_state_without_a_design_role(self):
        rec = record(states=[{"key": "A", "role": "operating", "P_psig": 1500},
                             {"key": "B", "role": "upset", "P_psig": 2500}])
        job = fixture(B313)
        del job["P"]
        self.assertEqual(pd.run_module(B313, dict(job, project_basis=rec))["inputs"]["P"], 1500)

    def test_p_fills_every_module_that_takes_p(self):
        self.assertEqual(set(pd.P_MODULES), {B313, B311, BEND, LEAK})
        codes = {B311: "B31.1", BEND: "B31.3", LEAK: "B31.3", B313: "B31.3"}
        for module in pd.P_MODULES:
            job = fixture(module)
            want = job.pop("P")
            rec = record(code={"standard": codes[module], "edition": "2022"},
                         states=[{"key": "DES", "role": "design", "P_psig": want}])
            env = pd.run_module(module, dict(job, project_basis=rec))
            self.assertEqual(env["inputs"]["P"], want, module)
            self.assertEqual(used(env)["states[role=design|first].P_psig"], ("P", "filled"), module)
            self.assertEqual(env["output"], pd.run_module(module, fixture(module))["output"], module)

    def test_a_typed_p_that_agrees_is_kept(self):
        env = pd.run_module(B313, dict(fixture(B313), project_basis=record()))
        self.assertEqual(used(env)["states[role=design|first].P_psig"], ("P", "agreed"))

    def test_code_fills_the_mawp_and_bend_modules(self):
        for module, std, want in ((MAWP, "ASME B31.1", "B31.1"), (BEND, "B31.3", "B31.3"), (MAWP, "B31.12", "B31.12")):
            env = pd.run_module(module, dict(fixture(module), project_basis=record(code={"standard": std},
                                                                                    states=None)))
            self.assertEqual(env["inputs"]["code"], want, module)
            self.assertEqual(env["weld_factor_basis"]["code"], want, module)
            self.assertEqual(used(env)["code.standard"], ("code", "filled"), module)

    def test_a_typed_code_spelled_differently_agrees(self):
        env = pd.run_module(MAWP, dict(fixture(MAWP), code="asme b31.3", project_basis=record()))
        self.assertEqual(used(env)["code.standard"], ("code", "agreed"))
        self.assertEqual(env["inputs"]["code"], "B31.3")

    def test_an_edition_typed_as_a_number_agrees_with_the_string(self):
        env = pd.run_module(B313, dict(fixture(B313), edition=2022, project_basis=record()))
        self.assertEqual(used(env)["code.edition"], ("edition", "agreed"))
        self.assertEqual(env["inputs"]["edition"], 2022)

    def test_seamless_pipe_material_fills_w_basis(self):
        rec = record(materials=[{"id": "P1", "spec": "user spec", "form": "seamless", "use": "pipe"}])
        job = {k: v for k, v in fixture(B313).items() if k != "W_basis"}
        env = pd.run_module(B313, dict(job, project_basis=rec))
        self.assertEqual(env["inputs"]["W_basis"], "seamless")
        self.assertEqual(env["weld_factor_basis"]["basis"], "seamless")
        self.assertEqual(used(env)["materials[use=pipe].form"], ("W_basis", "filled"))
        self.assertEqual(used(env)["materials[use=pipe]"], (None, "noted"))
        # W omitted too: the W gate applies it as 1.0 on the filled basis
        job.pop("W")
        env = pd.run_module(B313, dict(job, project_basis=rec))
        self.assertEqual(env["inputs"]["W"], 1.0)
        self.assertEqual(env["weld_factor_basis"]["basis_source"], "W_basis (W omitted, applied as 1.0)")

    def test_w_basis_is_not_filled_for_welded_pipe_a_reduced_w_or_a_typed_basis(self):
        job = {k: v for k, v in fixture(B313).items() if k != "W_basis"}
        welded = record(materials=[{"id": "P1", "form": "welded", "use": "pipe"}])
        r = cli(B313, dict(job, project_basis=welded))
        self.assertEqual(r.returncode, 2)                       # the W gate still needs a basis
        self.assertIn("W = 1.0 needs W_basis", r.stderr)
        seamless = record(materials=[{"id": "P1", "form": "seamless", "use": "pipe"}])
        env = pd.run_module(B313, dict(job, W=0.9, project_basis=seamless))
        self.assertNotIn("W_basis", env["inputs"])
        typed = pd.run_module(B313, dict(job, W_basis="below creep range per table note", project_basis=seamless))
        self.assertEqual(typed["inputs"]["W_basis"], "below creep range per table note")   # no conflict
        self.assertNotIn("materials[use=pipe].form", used(typed))

    def test_modules_without_the_input_note_the_field(self):
        env = pd.run_module(BRANCH, dict(fixture(BRANCH), project_basis=record()))
        u = used(env)
        self.assertEqual(u["code.standard"], (None, "noted"))
        self.assertEqual(u["code.edition"], (None, "noted"))
        self.assertNotIn("states[role=design|first].P_psig", u)

    def test_mawp_and_miter_take_the_design_pressure_for_a_comparison(self):
        for module in (MAWP, MITER):
            env = pd.run_module(module, dict(fixture(module), project_basis=record()))
            self.assertEqual(used(env)["states[role=design|first].P_psig"], (None, "noted"), module)
            self.assertIn(pd.CHECK_DESIGN_P, [c["name"] for c in env["checks"]], module)


class Conflicts(unittest.TestCase):

    def _exit2(self, module, job, message, *extra):
        r = cli(module, job, *extra)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(r.stdout, "")
        self.assertIn(message, r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)

    def test_a_different_typed_p_exits_2(self):
        self._exit2(B313, dict(fixture(B313), P=1999, project_basis=record()),
                    "project_basis.states[role=design|first].P_psig conflicts with input P")

    def test_a_different_edition_exits_2(self):
        self._exit2(B313, dict(fixture(B313), edition="2024", project_basis=record()),
                    "project_basis.code.edition conflicts with input edition")

    def test_a_different_typed_code_exits_2(self):
        self._exit2(MAWP, dict(fixture(MAWP), code="B31.1", project_basis=record()),
                    "project_basis.code.standard conflicts with input code")

    def test_a_standard_outside_the_module_family_exits_2(self):
        for module, std in ((B311, "B31.3"), (B313, "B31.1"), (MITER, "B31.1"), (BEND, "B31.9"),
                            (LEAK, "B31.12"), (B313, "other")):
            job = dict(fixture(module), project_basis=record(code={"standard": std}))
            self._exit2(module, job, "project_basis.code.standard conflicts with input " + module)

    def test_b311_serves_b31_9(self):
        env = pd.run_module(B311, dict(fixture(B311), project_basis=record(code={"standard": "B31.9"}, states=None)))
        self.assertEqual(env["status"], "na")

    def test_si_units_exit_2(self):
        self._exit2(B313, dict(fixture(B313), project_basis=record(units={"system": "SI"})),
                    "project_basis.units.system is SI")

    def test_usc_units_are_accepted(self):
        env = pd.run_module(B313, dict(fixture(B313), project_basis=record(units={"system": "USC"})))
        self.assertEqual(env["status"], "na")

    def test_an_invalid_record_exits_2_with_the_path(self):
        rec = record()
        rec["states"][0]["role"] = "normal"
        self._exit2(B313, dict(fixture(B313), project_basis=rec), "project_basis.states[0].role")
        self._exit2(B313, dict(fixture(B313), project_basis=dict(record(), extra=1)),
                    "project_basis.extra: unknown key")


class FileRoute(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "project-basis.json")
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(record(), fh)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_file_fills_like_the_key(self):
        job = fixture(B313)
        del job["P"]
        r = cli(B313, job, "--project-basis", self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["inputs"]["P"], 2000)
        self.assertEqual(env["project_basis_applied"], pd.run_module(B313, dict(job, project_basis=record()))
                         ["project_basis_applied"])

    def test_file_and_a_different_key_exit_2(self):
        other = record(code={"standard": "B31.3", "edition": "2024"})
        r = cli(B313, dict(fixture(B313), project_basis=other), "--project-basis", self.path)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis conflicts with --project-basis file", r.stderr)

    def test_file_and_the_same_key_run(self):
        r = cli(B313, dict(fixture(B313), project_basis=record()), "--project-basis", self.path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_missing_file_exits_2(self):
        r = cli(B313, fixture(B313), "--project-basis", os.path.join(self.tmp.name, "none.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read --project-basis file", r.stderr)

    def test_the_shipped_example_record_runs(self):
        example = os.path.join(SCRIPTS, "examples", "project-basis.example.json")
        job = fixture(B313)
        del job["P"]
        r = cli(B313, job, "--project-basis", example)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inputs"]["P"], 150)


class AppliedAndSheet(unittest.TestCase):

    def test_applied_shape_and_assumed_items_copied_verbatim(self):
        rec = record()
        env = pd.run_module(B313, dict(fixture(B313), project_basis=rec))
        applied = env["project_basis_applied"]
        self.assertEqual(sorted(applied), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(applied["schema"], SCHEMA)
        self.assertEqual(applied["conflicts"], [])
        self.assertEqual(applied["assumptions"], [rec["assumptions"][0]])

    def test_basis_section_lists_every_assumed_item_first(self):
        rec = record(assumptions=[{"item": "Edition of record", "status": "ASSUMED"},
                                  {"item": "Mill tolerance from the purchase spec"},
                                  {"item": "Fluid service", "status": "confirmed"}])
        section = pd.run_module(B313, dict(fixture(B313), project_basis=rec))["basis_section"]
        lines = section.splitlines()
        self.assertEqual(lines[0], "**ASSUMED - confirm before issue:**")
        self.assertEqual(lines[1:3], ["- Edition of record", "- Mill tolerance from the purchase spec"])
        self.assertNotIn("- Fluid service", section)
        self.assertIn("| Code | standard=B31.3, edition=2022, route=Normal fluid service |", section)
        self.assertIn("P <- states[role=design|first].P_psig (agreed)", section)
        self.assertEqual(section, pd.render_basis_section(
            pd.run_module(B313, dict(fixture(B313), project_basis=rec))["project_basis_applied"], rec))

    def test_a_record_without_assumptions_says_so(self):
        section = pd.run_module(B313, dict(fixture(B313), project_basis=record(assumptions=None)))["basis_section"]
        self.assertTrue(section.startswith("No ASSUMED items in the project basis record."))

    def test_no_record_adds_nothing(self):
        for module in pd.REGISTRY:
            env = pd.run_module(module, fixture(module))
            self.assertNotIn("project_basis_applied", env, module)
            self.assertNotIn("basis_section", env, module)
            self.assertEqual(pd.run_module(module, dict(fixture(module), project_basis=None)), env, module)

    def test_the_callers_job_is_not_modified(self):
        job = dict(fixture(B313), project_basis=record())
        snapshot = json.loads(json.dumps(job))
        pd.run_module(B313, job)
        self.assertEqual(job, snapshot)


class SkillTextAndGrammar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.skill = fh.read()

    def test_skill_links_the_reference_and_states_the_reuse_rule(self):
        self.assertIn("[references/project-basis.md](references/project-basis.md)", self.skill)
        for phrase in ("--project-basis project-basis.json", "ask only for what it lacks", "never relabel a field",
                       "`basis_section` first"):
            self.assertIn(phrase, self.skill, phrase)

    def test_skill_md_did_not_grow(self):
        self.assertLessEqual(len(self.skill.split()), SKILL_WORDS_0_7_2)

    def test_reference_copy_is_the_canonical_file(self):
        with open(os.path.join(ROOT, "tools", "shared", "project-basis.md"), "rb") as fh:
            canon = fh.read()
        with open(os.path.join(SKILL, "references", "project-basis.md"), "rb") as fh:
            self.assertEqual(fh.read(), canon)

    def test_python_3_9_grammar(self):
        here = os.path.dirname(os.path.abspath(__file__))
        for path in (CLI, os.path.join(here, "test_pressure_design_basis.py"),
                     os.path.join(here, "test_pressure_design_status.py")):
            with open(path, encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=path, feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
