"""load-case-builder: the project basis record (plugin 0.8.0, B8).

The generator takes a pipingtoolset.project-basis/1 record from the spec key ``project_basis`` or
``--project-basis <file>`` and fills code, edition, thermal_states and primary_state where the spec
leaves them out; a spec value that differs exits 2. Standard library only.
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
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "load-case-builder")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "loadcase_gen.py")
EXAMPLE_BASIS = os.path.join(SCRIPTS, "examples", "project-basis.example.json")
sys.path.insert(0, SCRIPTS)

import loadcase_gen as g  # noqa: E402


def basis() -> dict:
    with open(EXAMPLE_BASIS, encoding="utf-8") as fh:
        return json.load(fh)


# A spec that leaves code, edition, thermal_states and primary_state to the record.
BARE = {
    "frictions": [["w/ Friction", 1.0], ["w/o Friction", 0.0]],
    "hanger_friction": 1.0,
    "inter_state_expansion_ranges": False,
    "occasionals": [
        {"key": "seis_px", "name": "Seismic +X", "vector": "U1", "sign": "+", "base": "OPE1", "kind": "seismic"},
        {"key": "seis_v", "name": "Seismic -Y", "vector": "U2", "sign": "-", "base": "OPE1", "kind": "seismic"},
    ],
}

# The same job written out in full, as the record would fill it.
FULL = dict(copy.deepcopy(BARE), code="B31.3", edition="2022", primary_state="OPE1", thermal_states=[
    {"key": "OPE1", "name": "Normal operating", "T": "T1", "P": "P1", "D": "D1", "role": "operating", "cycles": 7000},
    {"key": "DES", "name": "Design", "T": "T2", "P": "P2", "role": "design"},
])


def build(spec: dict, path: str | None = None) -> g.LoadCaseSet:
    return g.LoadCaseSet(copy.deepcopy(spec), project_basis_file=path).build()


def with_basis(spec: dict, record: dict | None = None) -> dict:
    return dict(copy.deepcopy(spec), project_basis=record if record is not None else basis())


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")


class Fill(unittest.TestCase):

    def setUp(self):
        self.s = build(with_basis(BARE))

    def test_code_and_edition_from_the_record(self):
        self.assertEqual((self.s.code, self.s.edition), ("B31.3", "2022"))

    def test_thermal_states_from_the_slotted_states(self):
        got = [(t.key, t.name, t.T, t.P, t.D, t.role, t.cycles) for t in self.s.states]
        self.assertEqual(got, [("OPE1", "Normal operating", "T1", "P1", "D1", "operating", 7000),
                               ("DES", "Design", "T2", "P2", None, "design", None)])

    def test_primary_state_is_the_first_operating_state(self):
        self.assertEqual(self.s.primary.key, "OPE1")
        self.assertTrue(self.s.primary_state_declared)
        self.assertFalse(any(f.startswith("ASSUMED: primary state") for f in self.s.findings))

    def test_primary_state_falls_back_to_the_first_declared_state_not_the_design_state(self):
        rec = basis()
        rec["states"][0]["role"] = "upset"            # no operating state; DES is the design state
        self.assertEqual(build(with_basis(BARE, rec)).primary.key, "OPE1")

    def test_primary_state_is_an_operating_state_declared_after_the_design_state(self):
        rec = basis()
        rec["states"][0]["role"], rec["states"][1]["role"] = "design", "operating"
        self.assertEqual(build(with_basis(BARE, rec)).primary.key, "DES")

    def test_filled_set_equals_the_spec_written_in_full(self):
        self.assertEqual(self.s.rows(), build(FULL).rows())
        self.assertEqual(self.s.qc, build(FULL).qc)

    def test_applied_record_shape_and_fields_used(self):
        a = self.s.basis_applied
        self.assertEqual(sorted(a), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(a["schema"], "pipingtoolset.project-basis/1")
        self.assertEqual(a["conflicts"], [])
        used = [(u["input"], u["basis"], u["action"]) for u in a["fields_used"]]
        self.assertEqual(used, [
            ("code", "code.standard", "filled"), ("edition", "code.edition", "filled"),
            ("thermal_states", "states", "filled"), ("primary_state", "states[role=operating|first].key", "filled"),
            ("--format", "load_case_ids.software", "noted"), (None, "owner_practice[0]", "noted"),
            (None, "assumptions", "noted")])
        self.assertEqual(a["assumptions"], [basis()["assumptions"][0]])  # ASSUMED only, verbatim

    def test_agreeing_spec_values_are_agreed(self):
        s = build(with_basis(FULL))
        self.assertEqual({u["input"]: u["action"] for u in s.basis_applied["fields_used"] if u["input"]},
                         {"code": "agreed", "edition": "agreed", "thermal_states": "agreed",
                          "primary_state": "agreed", "--format": "noted"})
        self.assertEqual(s.rows(), build(FULL).rows())

    def test_omitted_defaults_and_a_numeric_edition_agree(self):
        spec = copy.deepcopy(FULL)
        spec["edition"] = 2022
        del spec["thermal_states"][0]["role"]   # default "operating" is the record's role
        s = build(with_basis(spec))
        self.assertEqual(s.edition, "2022")
        self.assertEqual(s.rows(), build(FULL).rows())

    def test_hydrotest_and_installed_states_are_not_thermal_states(self):
        rec = basis()
        rec["states"] += [{"key": "HT", "name": "Hydrotest", "role": "hydrotest", "slot": {"T": "T9", "P": "P9"}},
                          {"key": "INST", "role": "installed", "T_F": 70}]
        self.assertEqual([t.key for t in build(with_basis(BARE, rec)).states], ["OPE1", "DES"])

    def test_unslotted_state_without_spec_states_exits_2(self):
        rec = basis()
        del rec["states"][1]["slot"]
        with self.assertRaises(g.SpecError) as cm:
            build(with_basis(BARE, rec))
        self.assertIn("project_basis.states[key=DES].slot needs T and P", str(cm.exception))

    def test_unslotted_state_with_spec_states_uses_the_spec_and_says_so(self):
        rec = basis()
        del rec["states"][1]["slot"]
        spec = dict(copy.deepcopy(FULL), primary_state="DES")
        s = build(with_basis(spec, rec))
        self.assertEqual(s.primary.key, "DES")
        self.assertIn("NOTE: project basis state(s) DES carry no T/P slot", "\n".join(s.findings))

    def test_no_record_leaves_the_spec_object_alone(self):
        spec = copy.deepcopy(FULL)
        self.assertIs(g.LoadCaseSet(spec).spec, spec)
        s = build(dict(copy.deepcopy(FULL), project_basis=None))     # a null key is no record
        self.assertIsNone(s.basis)
        self.assertNotIn("project_basis_applied", json.loads(s.to_json()))
        self.assertEqual(g.render_report(s), g.render_report(build(FULL)))

    def test_software_and_owner_friction_notes(self):
        rec = basis()
        rec["load_case_ids"]["software"] = "AutoPIPE"
        spec = dict(copy.deepcopy(BARE), frictions=[["w/ Friction", 1.0]])
        s = build(with_basis(spec, rec))
        text = "\n".join(s.findings)
        self.assertIn("NOTE: project basis software is AutoPIPE", text)
        self.assertIn("NOTE: owner practice Owner piping stress practice carries a friction item", text)
        self.assertIn("AutoPIPE occasional construction", [c["name"] for c in s.checks])


class Conflicts(unittest.TestCase):

    def _conflict(self, spec: dict, message: str, record: dict | None = None):
        with self.assertRaises(g.SpecError) as cm:
            build(with_basis(spec, record))
        self.assertEqual(str(cm.exception), message)

    def test_code(self):
        self._conflict(dict(FULL, code="B31.1"), "project_basis.code.standard conflicts with input code")

    def test_edition(self):
        self._conflict(dict(FULL, edition="2020"), "project_basis.code.edition conflicts with input edition")

    def test_thermal_states(self):
        spec = copy.deepcopy(FULL)
        spec["thermal_states"][1]["T"] = "T3"
        self._conflict(spec, "project_basis.states conflicts with input thermal_states")

    def test_primary_state(self):
        self._conflict(dict(FULL, primary_state="DES"),
                       "project_basis.states[role=operating|first].key conflicts with input primary_state")

    def test_a_standard_the_generator_does_not_take(self):
        rec = basis()
        rec["code"]["standard"] = "B31.9"
        with self.assertRaises(g.SpecError) as cm:
            build(with_basis(BARE, rec))
        self.assertIn("code must be 'B31.1' or 'B31.3'", str(cm.exception))

    def test_invalid_record(self):
        rec = basis()
        rec["states"][0]["colour"] = "red"
        with self.assertRaises(g.SpecError) as cm:
            build(with_basis(BARE, rec))
        self.assertIn("project_basis is not a valid pipingtoolset.project-basis/1 record", str(cm.exception))
        self.assertIn("project_basis.states[0].colour: unknown key", str(cm.exception))


class CommandLine(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _write(self, name: str, obj) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_file_fills_and_json_carries_the_applied_record(self):
        r = run("--spec", self._write("spec.json", BARE), "--project-basis", EXAMPLE_BASIS, "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual((d["code"], d["edition"], d["primary_state"]), ("B31.3", "2022", "OPE1"))
        self.assertEqual(d["project_basis_applied"]["schema"], "pipingtoolset.project-basis/1")

    def test_spec_key_and_file_that_agree_run(self):
        r = run("--spec", self._write("spec.json", with_basis(BARE)), "--project-basis", EXAMPLE_BASIS)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_spec_key_against_a_different_file_exits_2(self):
        rec = basis()
        rec["code"]["edition"] = "2020"
        r = run("--spec", self._write("spec.json", with_basis(BARE, rec)), "--project-basis", EXAMPLE_BASIS)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("project_basis conflicts with --project-basis file", r.stderr)

    def test_input_conflict_exits_2(self):
        r = run("--spec", self._write("spec.json", dict(FULL, code="B31.1")), "--project-basis", EXAMPLE_BASIS)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.code.standard conflicts with input code", r.stderr)

    def test_example_against_the_example_record_conflicts_on_states(self):
        r = run("--example", "--project-basis", EXAMPLE_BASIS)
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.states conflicts with input thermal_states", r.stderr)

    def test_documented_fill_recipe_runs_the_example_against_the_record(self):
        """spec-format.md 'Project basis': drop code/edition/thermal_states/primary_state from the
        example spec and point every occasional base at a record state; the pair then runs."""
        with open(os.path.join(SCRIPTS, "examples", "two-state-b313.json"), encoding="utf-8") as fh:
            spec = json.load(fh)
        for k in ("code", "edition", "thermal_states", "primary_state"):
            spec.pop(k, None)
        for o in spec["occasionals"]:
            o["base"] = {"op": "OPE1", "des": "DES"}[o["base"]]
        r = run("--spec", self._write("filled.json", spec), "--project-basis", EXAMPLE_BASIS,
                "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual((out["code"], out["edition"], out["primary_state"]), ("B31.3", "2022", "OPE1"))
        self.assertIn({"input": "thermal_states", "basis": "states", "action": "filled"},
                      out["project_basis_applied"]["fields_used"])

    def test_missing_file_exits_2(self):
        r = run("--example", "--project-basis", os.path.join(self.tmp.name, "nope.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read --project-basis file", r.stderr)


class AssumedBlock(unittest.TestCase):

    def test_record_and_generator_assumed_items_are_at_the_top(self):
        spec = dict(copy.deepcopy(BARE))
        del spec["hanger_friction"]                       # a generator ASSUMED default as well
        report = g.render_report(build(with_basis(spec)))
        lines = report.splitlines()
        self.assertTrue(lines[0].startswith("## Load case set - B31.3 2022"))
        self.assertTrue(lines[1].startswith("Result status: manual check required - "))
        top = report.index("**ASSUMED - confirm before issue:**")
        self.assertLess(report.index("### 1 Basis"), top)
        self.assertLess(top, report.index("| L | Combination"))
        block = report[top:report.index("| L | Combination")]
        self.assertIn("- Corrosion allowance per the line list; note: line list not yet issued; owner: lead", block)
        self.assertIn("hanger design pair (W Rigid, W+T1 Ignore) runs at friction multiplier 1.0", block)
        self.assertNotIn("Design state governs pressure design", block.split("| Basis item")[0])  # confirmed
        self.assertIn("Taken from the record: code <- code.standard (filled)", block)

    def test_without_a_record_the_generator_assumptions_still_lead(self):
        report = g.render_report(build(g.EXAMPLE_SPEC))
        self.assertLess(report.index("**ASSUMED - confirm before issue:**"), report.index("| L | Combination"))
        self.assertIn("No project basis record was given", report)

    def test_nothing_assumed_and_no_record_prints_no_block(self):
        self.assertNotIn("### 1 Basis", g.render_report(build(FULL)))


class Grammar(unittest.TestCase):

    def test_script_parses_as_python_3_9(self):
        with open(TOOL, encoding="utf-8") as fh:
            ast.parse(fh.read(), filename=TOOL, feature_version=(3, 9))


if __name__ == "__main__":
    unittest.main()
