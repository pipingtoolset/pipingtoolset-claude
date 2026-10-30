"""stress-screening: project basis record (plugin 0.8.0, B8).

The shared block (tools/shared/project_basis.py) is pinned elsewhere; these tests cover this skill's
fill map, the conflict rule through the CLI, the --project-basis file, the ASSUMED rendering and the
fixture-parity guarantee. Standard library only:

    python -m unittest tests.test_stress_screening_basis -v
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-screening")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "stress_screening.py")
EXAMPLE = os.path.join(SCRIPTS, "examples", "project-basis.example.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
import stress_screening as ss  # noqa: E402

SPAN = dict(w=24, E=1.0e7, S_allow=3000, delta_allow=0.25, Z=10.0, I=40.0)
EXEMPT = dict(D=4.5, y=1.2, L=100, U=60, SA=30000, Ea=1.0e7,
              fixation_points=2, intermediate_restraints=False, uniform_size=True)


def record(**changes):
    """The shipped example record, with top-level keys replaced (a None value removes the key)."""
    with open(EXAMPLE, encoding="utf-8") as fh:
        rec = json.load(fh)
    for key, value in changes.items():
        if value is None:
            rec.pop(key, None)
        else:
            rec[key] = value
    return rec


def cli(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")


def run(module, inputs, basis=None, **extra):
    """CLI run with the record as a top-level project_basis object; returns (completed process, envelope or None)."""
    body = dict(inputs, **extra)
    if basis is not None:
        body["project_basis"] = basis
    r = cli(module, "--input", json.dumps(body))
    return r, (json.loads(r.stdout) if r.returncode == 0 else None)


class FillMap(unittest.TestCase):

    def test_fatigue_equation_and_cycles_are_filled(self):
        r, env = run("piping.fatigue-factor", {"fmax": 1.0}, record())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env["inputs"], {"fmax": 1.0, "equation": "b313-2022", "N": 7000})
        used = {(u["input"], u["basis"], u["action"]) for u in env["project_basis_applied"]["fields_used"]}
        self.assertIn(("equation", "code.edition", "filled"), used)
        self.assertIn(("N", "states[0].cycles", "filled"), used)
        # the filled values drive the engine: the same run typed by hand gives the same output
        r2, env2 = run("piping.fatigue-factor", {"fmax": 1.0, "equation": "b313-2022", "N": 7000})
        self.assertEqual(env["output"], env2["output"])
        self.assertEqual(env["status"], env2["status"])

    def test_equation_follows_the_code_and_edition_of_the_record(self):
        legacy = record(code={"standard": "B31.1", "edition": "2024"})
        r, env = run("piping.fatigue-factor", {"fmax": 1.0}, legacy)
        self.assertEqual(env["inputs"]["equation"], "legacy")
        old = record(code={"standard": "B31.3", "edition": "2020"})
        self.assertEqual(run("piping.fatigue-factor", {"fmax": 1.0}, old)[1]["inputs"]["equation"], "legacy")

    def test_values_that_agree_are_marked_agreed(self):
        r, env = run("piping.fatigue-factor", {"fmax": 1.0, "equation": "b313-2022", "N": 7000}, record())
        self.assertEqual(r.returncode, 0, r.stderr)
        actions = {u["input"]: u["action"] for u in env["project_basis_applied"]["fields_used"] if u["input"]}
        self.assertEqual(actions, {"equation": "agreed", "N": "agreed"})

    def test_a_different_equation_exits_2(self):
        r, _ = run("piping.fatigue-factor", {"fmax": 1.0, "equation": "legacy", "N": 7000}, record())
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.edition conflicts with input equation", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_a_different_cycle_count_exits_2(self):
        r, _ = run("piping.fatigue-factor", {"fmax": 1.0, "N": 5000}, record())
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.states[0].cycles conflicts with input N", r.stderr)

    def test_sets_replace_n_so_n_is_not_filled(self):
        r, env = run("piping.fatigue-factor", {"fmax": 1.0, "sets": [{"N": 7000, "r": 1}]}, record())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("N", env["inputs"])

    def test_several_states_with_cycles_leave_n_to_the_caller(self):
        states = [{"key": "A", "cycles": 1000}, {"key": "B", "cycles": 200}]
        r, env = run("piping.fatigue-factor", {"fmax": 1.0, "N": 1200}, record(states=states))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env["inputs"]["N"], 1200)
        self.assertTrue(any("several states carry cycles" in w for w in env["warnings"]))
        r, _ = run("piping.fatigue-factor", {"fmax": 1.0}, record(states=states))
        self.assertEqual(r.returncode, 2)          # N is still required and nothing filled it
        self.assertIn("N is required", r.stderr)

    def test_a_standard_the_skill_does_not_cover_fills_nothing(self):
        r, _ = run("piping.fatigue-factor", {"fmax": 1.0, "N": 7000}, record(code={"standard": "B31.9", "edition": "2022"}))
        self.assertEqual(r.returncode, 2)
        self.assertIn("equation is required", r.stderr)

    def test_exemption_code_and_edition_are_filled(self):
        r, env = run("screen.flexibility-exemption", EXEMPT, record())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env["inputs"]["code"], "B31.3")
        self.assertEqual(env["inputs"]["edition"], "2022")
        used = {u["input"]: u["action"] for u in env["project_basis_applied"]["fields_used"] if u["input"]}
        self.assertEqual(used, {"code": "filled", "edition": "filled"})

    def test_an_edition_typed_as_a_number_agrees_with_the_record_string(self):
        r, env = run("screen.flexibility-exemption", EXEMPT, record(), code="B31.3", edition=2022)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(env["inputs"]["edition"], 2022)
        used = {u["input"]: u["action"] for u in env["project_basis_applied"]["fields_used"] if u["input"]}
        self.assertEqual(used, {"code": "agreed", "edition": "agreed"})

    def test_exemption_conflicts_exit_2(self):
        r, _ = run("screen.flexibility-exemption", EXEMPT, record(), code="B31.1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.standard conflicts with input code", r.stderr)
        r, _ = run("screen.flexibility-exemption", EXEMPT, record(), edition=2020)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.edition conflicts with input edition", r.stderr)

    def test_exemption_leaves_a_standard_it_does_not_cover_alone(self):
        r, env = run("screen.flexibility-exemption", EXEMPT, record(code={"standard": "B31.12", "edition": "2020"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("code", env["inputs"])

    def test_basis_command_resolves_from_the_record(self):
        r = cli("basis", "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["code"], "B31.3")
        self.assertEqual(out["edition"], "2022")               # the record's string, as given
        self.assertEqual(out["fatigue_equation"], "b313-2022")
        used = {u["input"]: u["action"] for u in out["project_basis_applied"]["fields_used"] if u["input"]}
        self.assertEqual(used, {"--code": "filled", "--edition": "filled"})

    def test_basis_command_conflict_and_agreement(self):
        r = cli("basis", "--code", "B31.1", "--edition", "2022", "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.standard conflicts with input --code", r.stderr)
        r = cli("basis", "--code", "B31.3", "--edition", "2020", "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.edition conflicts with input --edition", r.stderr)
        r = cli("basis", "--code", "B31.3", "--edition", "2022", "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["fatigue_equation"], "b313-2022")

    def test_basis_command_with_a_record_that_has_no_edition_still_asks_for_one(self):
        r = cli("basis", "--project-basis", self._file(record(code={"standard": "B31.3"})))
        self.assertEqual(r.returncode, 2)
        self.assertIn("basis needs --code and --edition", r.stderr)

    def test_state_install_owner_practice_and_units_are_recorded_as_noted(self):
        r, env = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, record())
        self.assertEqual(r.returncode, 0, r.stderr)
        noted = [u["basis"] for u in env["project_basis_applied"]["fields_used"] if u["action"] == "noted"]
        for path in ("code", "units.system", "installation_T_F", "states", "owner_practice[0]"):
            self.assertIn(path, noted)
        self.assertEqual(env["inputs"], {"OD": 6.625, "t": 0.28})     # nothing was filled

    def test_an_si_record_exits_2(self):
        r, _ = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, record(units={"system": "SI"}))
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.units.system is SI", r.stderr)

    def _file(self, rec):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(d, f)) for f in os.listdir(d)] and os.rmdir(d))
        path = os.path.join(d, "basis.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        return path


class RecordSources(unittest.TestCase):

    def _file(self, rec):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(d, f)) for f in os.listdir(d)] and os.rmdir(d))
        path = os.path.join(d, "basis.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        return path

    def test_the_cli_flag_alone_works(self):
        r = cli("piping.fatigue-factor", "--input", json.dumps({"fmax": 1.0}), "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inputs"]["equation"], "b313-2022")

    def test_key_and_file_that_are_the_same_record_are_accepted(self):
        r = cli("piping.fatigue-factor", "--input", json.dumps({"fmax": 1.0, "project_basis": record()}),
                "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_key_and_file_that_differ_exit_2(self):
        other = record(code={"standard": "B31.1", "edition": "2024"})
        r = cli("piping.fatigue-factor", "--input", json.dumps({"fmax": 1.0, "project_basis": other}),
                "--project-basis", EXAMPLE)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis conflicts with --project-basis file", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_an_invalid_record_exits_2_with_the_path(self):
        bad = record()
        bad["states"][0]["role"] = "sometimes"
        r, _ = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, bad)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.states[0].role", r.stderr)
        r, _ = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, dict(record(), colour="red"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.colour: unknown key", r.stderr)

    def test_a_missing_file_exits_2(self):
        r = cli("noncode.pipe-section", "--input", '{"OD": 6.625, "t": 0.28}', "--project-basis",
                os.path.join(ROOT, "tests", "no-such-basis.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read --project-basis file", r.stderr)

    def test_a_job_file_with_module_sections_takes_project_basis_beside_them(self):
        job = {"project_basis": record(), "piping.fatigue-factor": {"fmax": 1.0},
               "noncode.pipe-section": {"OD": 6.625, "t": 0.28}}
        path = self._file(job)
        r = cli("piping.fatigue-factor", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inputs"]["equation"], "b313-2022")
        r = cli("noncode.pipe-section", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_flat_job_file_takes_the_key(self):
        path = self._file({"_note": "comment", "project_basis": record(), "fmax": 1.0})
        r = cli("piping.fatigue-factor", "--input-file", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("project_basis_applied", json.loads(r.stdout))

    def test_run_module_takes_the_key_or_the_keyword(self):
        a = ss.run_module("piping.fatigue-factor", {"fmax": 1.0, "project_basis": record()})
        d = tempfile.mkdtemp()
        path = os.path.join(d, "b.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record(), fh)
        b = ss.run_module("piping.fatigue-factor", {"fmax": 1.0}, path)
        os.remove(path)
        os.rmdir(d)
        self.assertEqual(a, b)

    def test_the_callers_input_is_not_modified(self):
        inp = {"fmax": 1.0, "project_basis": record()}
        before = copy.deepcopy(inp)
        ss.run_module("piping.fatigue-factor", inp)
        self.assertEqual(inp, before)

    def test_a_code_value_and_the_record_that_disagree_exit_2(self):
        cv = {"N": {"value": 5000, "unit": None,
                    "citation": {"standard": "x", "edition": "y", "table": "t", "row": "r"}, "source": "user"}}
        r, _ = run("piping.fatigue-factor", {"fmax": 1.0, "code_values": cv}, record())
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.states[0].cycles conflicts with input N", r.stderr)


class AssumedAndSection(unittest.TestCase):

    def setUp(self):
        r, self.env = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, record())
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_assumed_items_are_copied_verbatim_and_confirmed_ones_are_not(self):
        applied = self.env["project_basis_applied"]
        self.assertEqual(sorted(applied), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(applied["schema"], "pipingtoolset.project-basis/1")
        self.assertEqual(applied["conflicts"], [])
        self.assertEqual(applied["assumptions"], [record()["assumptions"][0]])

    def test_section_1_lists_the_assumed_items_before_the_table(self):
        sec = self.env["basis_section"]
        self.assertTrue(sec.startswith("## 1. Basis\n"))
        self.assertIn("**ASSUMED - confirm before issue:**", sec)
        self.assertIn("Corrosion allowance per the line list", sec)
        self.assertNotIn("Design state governs pressure design;", sec.split("| Basis item")[0])
        self.assertLess(sec.index("ASSUMED"), sec.index("| Basis item"))
        self.assertIn("Taken from the record:", sec)

    def test_a_warning_and_the_status_line_count_the_assumed_items(self):
        self.assertTrue(any("1 ASSUMED item(s)" in w for w in self.env["warnings"]))
        self.assertIn("manual check required - confirm before issue: ", self.env["result_status_line"])

    def test_a_record_without_assumptions_says_so(self):
        r, env = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28}, record(assumptions=None))
        self.assertIn("No ASSUMED items in the project basis record.", env["basis_section"])
        self.assertEqual(env["project_basis_applied"]["assumptions"], [])
        self.assertFalse(any("ASSUMED" in w for w in env["warnings"]))

    def test_the_section_is_ascii(self):
        self.assertTrue(self.env["basis_section"].isascii())


class WithoutARecord(unittest.TestCase):
    """No record: nothing changes (fixture parity and the envelope)."""

    def test_no_basis_keys_in_the_envelope(self):
        r, env = run("noncode.pipe-section", {"OD": 6.625, "t": 0.28})
        for key in ("project_basis_applied", "basis_section"):
            self.assertNotIn(key, env)

    def test_the_registry_is_untouched_by_the_wiring(self):
        for module in ss.REGISTRY:
            if module in ("screen.support-span", "screen.flexibility-exemption"):
                continue
            fails = parity.run_fixture(ss.REGISTRY, module)
            self.assertEqual(fails, [], module)

    def test_a_record_never_changes_an_output_or_a_status(self):
        for module in ("piping.displacement-stress", "piping.sustained-stress", "supports.spring-variability",
                       "supports.max-spring-rate", "noncode.pipe-section"):
            base = dict(parity.load(module)["cases"][0]["input"])
            plain = ss.run_module(module, dict(base))
            with_record = ss.run_module(module, dict(base, project_basis=record(assumptions=None)))
            for key in ("status", "output", "citation", "inputs", "user_supplied", "result_status", "checks"):
                self.assertEqual(plain[key], with_record[key], (module, key))
        for module, base in (("screen.support-span", SPAN), ("screen.flexibility-exemption", dict(EXEMPT, code="B31.3", edition=2022))):
            plain = ss.run_module(module, dict(base))
            with_record = ss.run_module(module, dict(base, project_basis=record(assumptions=None)))
            for key in ("status", "output", "result_status", "checks"):
                self.assertEqual(plain[key], with_record[key], (module, key))


class Grammar(unittest.TestCase):

    def test_script_parses_as_python_3_9(self):
        with open(TOOL, encoding="utf-8") as fh:
            ast.parse(fh.read(), feature_version=(3, 9))

    def test_no_python_3_10_syntax_in_the_wiring(self):
        with open(TOOL, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), feature_version=(3, 9))
        self.assertFalse([n for n in ast.walk(tree) if type(n).__name__ == "Match"])

    def test_the_reference_is_the_shared_text(self):
        with open(os.path.join(ROOT, "tools", "shared", "project-basis.md"), "rb") as fh:
            canon = fh.read()
        with open(os.path.join(SKILL, "references", "project-basis.md"), "rb") as fh:
            self.assertEqual(fh.read(), canon)
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("references/project-basis.md", fh.read())

    def test_the_skill_text_states_the_interview_rule(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("reuse it: ask only for what is missing, never relabel a field", text)
        self.assertIn("--project-basis", text)


if __name__ == "__main__":
    unittest.main()
