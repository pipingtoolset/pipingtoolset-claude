"""Plugin 0.8.0 (B8): the shared project basis record in the pipe-support skill.

support_calc.py reads the optional top-level `project_basis` object or `--project-basis
<file>` (pipingtoolset.project-basis/1, references/project-basis.md) and fills, or checks
against, the spec keys of this skill's fill map: project / calcBy / date, and in CAESAR II
mode every pipe's loads.units, vertical_axis and pipe_axis. ASSUMED items join `assumed` and
are listed first in the report's basis section; support material and load case ids are
carried to the sheet. Every number here is an engine number from support_calc.run.

Standard library only:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import copy
import glob
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support")
SCRIPTS = os.path.join(SKILL, "scripts")
EX = os.path.join(SCRIPTS, "examples")
sys.path.insert(0, SCRIPTS)

import support_calc  # noqa: E402
from pipe_support import report as R  # noqa: E402

SCHEMA = "pipingtoolset.project-basis/1"


def load(name):
    with open(os.path.join(EX, name), encoding="utf-8") as fh:
        return json.load(fh)


def caesar():
    """ps-201 without the optimizer."""
    s = load("ps-201-caesar.json")
    s["optimize"] = False
    return s


def bare():
    """ps-201 with every key of the fill map removed from the spec."""
    s = caesar()
    s.pop("project")
    for p in s["pipes"]:
        for k in ("units", "vertical_axis", "pipe_axis"):
            p["loads"].pop(k)
    return s


def record(**extra):
    b = {"schema": SCHEMA,
         "project": {"name": "Example - CAESAR II restraint loads", "calcBy": "initials", "date": "2026-10-30"},
         "units": {"system": "USC"},
         "equipment_axes": {"global_vertical": "Y", "pipe_axis": "X"}}
    b.update(extra)
    return b


def main(spec, *extra):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh)
        args = [path, "--no-optimize", "--quiet"]
        for x in extra:
            if isinstance(x, dict):                  # a record to pass as --project-basis <file>
                bp = os.path.join(d, "basis.json")
                with open(bp, "w", encoding="utf-8") as fh:
                    json.dump(x, fh)
                args += ["--project-basis", bp]
            else:
                args.append(x)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = support_calc.main(args)
    return code, out.getvalue(), err.getvalue()


class Fill(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.want = support_calc.run(caesar(), optimize=False)
        spec = bare()
        spec["project_basis"] = record()
        cls.doc = support_calc.run(spec, optimize=False)

    def test_every_mapped_field_is_filled(self):
        sp = self.doc["spec"]
        self.assertEqual((sp["project"], sp["calcBy"], sp["date"]),
                         ("Example - CAESAR II restraint loads", "initials", "2026-10-30"))
        for p in sp["pipes"]:
            self.assertEqual((p["loads"]["units"], p["loads"]["vertical_axis"], p["loads"]["pipe_axis"]),
                             ("lb-ft", "Y", "X"))
        self.assertNotIn("project_basis", sp)

    def test_the_filled_run_equals_the_explicit_run(self):
        self.assertEqual(self.doc["envelope"], self.want["envelope"])
        self.assertEqual(self.doc["findings"], self.want["findings"])
        self.assertEqual(self.doc["combinations"], self.want["combinations"])

    def test_fields_used_and_applied_shape(self):
        ap = self.doc["project_basis_applied"]
        self.assertEqual(sorted(ap), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual((ap["schema"], ap["assumptions"], ap["conflicts"]), (SCHEMA, [], []))
        want = [{"input": "project", "basis": "project.name", "action": "filled"},
                {"input": "calcBy", "basis": "project.calcBy", "action": "filled"},
                {"input": "date", "basis": "project.date", "action": "filled"}]
        for i in (0, 1):
            want += [{"input": f"pipes.{i}.loads.units", "basis": "units", "action": "filled"},
                     {"input": f"pipes.{i}.loads.vertical_axis", "basis": "equipment_axes.global_vertical",
                      "action": "filled"},
                     {"input": f"pipes.{i}.loads.pipe_axis", "basis": "equipment_axes.pipe_axis",
                      "action": "filled"}]
        self.assertEqual(ap["fields_used"], want)
        self.assertIn("project_basis_applied", json.loads(R.to_json(self.doc)))

    def test_present_and_equal_values_agree(self):
        spec = caesar()
        spec["project_basis"] = record()
        ap = support_calc.run(spec, optimize=False)["project_basis_applied"]
        actions = {u["input"]: u["action"] for u in ap["fields_used"]}
        self.assertEqual(actions["project"], "agreed")
        self.assertEqual(actions["pipes.1.loads.vertical_axis"], "agreed")
        self.assertEqual(actions["calcBy"], "filled")

    def test_kip_in_units_fill_kip_in(self):
        spec = bare()
        spec["project_basis"] = record(units={"system": "USC", "force": "kip", "moment": "kip-in"})
        for p in spec["pipes"]:                       # the same loads in kip / kip-in
            p["loads"]["cases"] = {k: [x / 1000 for x in v] for k, v in p["loads"]["cases"].items()}
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual([p["loads"]["units"] for p in doc["spec"]["pipes"]], ["kip-in", "kip-in"])
        self.assertAlmostEqual(doc["envelope"]["governingRatio"], self.want["envelope"]["governingRatio"], places=9)

    def test_a_record_without_the_slots_fills_nothing(self):
        spec = caesar()
        spec["project_basis"] = {"schema": SCHEMA}
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(doc["project_basis_applied"]["fields_used"], [])
        self.assertEqual(doc["envelope"], self.want["envelope"])

    def test_factored_mode_notes_units_and_fills_the_title_block(self):
        spec = load("ps-101-factored.json")
        spec.pop("project", None)
        spec["project_basis"] = record()
        doc = support_calc.run(spec, optimize=False)
        used = doc["project_basis_applied"]["fields_used"]
        self.assertIn({"input": None, "basis": "units", "action": "noted"}, used)
        self.assertFalse([u for u in used if "pipes" in (u["input"] or "")])
        self.assertEqual(doc["spec"]["project"], "Example - CAESAR II restraint loads")
        self.assertAlmostEqual(doc["envelope"]["governingRatio"], 0.8314, places=4)

    def test_support_material_and_load_case_ids_reach_the_sheet_only(self):
        spec = caesar()
        spec["project_basis"] = record(
            materials=[{"id": "SUP-1", "spec": "user structural spec", "grade": "user grade", "use": "support"}],
            load_case_ids={"software": "AutoPIPE", "cases": {"SUS": "L3", "OPE": "L2", "OCC": ["L5", "L6"]}})
        doc = support_calc.run(spec, optimize=False)
        used = doc["project_basis_applied"]["fields_used"]
        self.assertIn({"input": "design.material", "basis": "materials[use=support]", "action": "noted"}, used)
        self.assertIn({"input": None, "basis": "load_case_ids", "action": "noted"}, used)
        notes = " ".join(doc["notes"])
        self.assertIn("Support material from the project basis: id SUP-1, spec user structural spec", notes)
        self.assertIn("SUS = L3; OPE = L2; OCC = L5, L6", notes)
        self.assertIn("AutoPIPE", notes)
        self.assertEqual(doc["design"]["material"], self.want["design"]["material"])
        self.assertEqual(doc["envelope"], self.want["envelope"])

    def test_the_shipped_example_record_runs_with_ps201(self):
        with open(os.path.join(EX, "project-basis.example.json"), encoding="utf-8") as fh:
            basis = json.load(fh)
        spec = caesar()
        spec.pop("project")
        spec["project_basis"] = basis
        doc = support_calc.run(spec, optimize=False)
        # the record's ASSUMED item joins the one "ASSUMED inputs" row; everything else is unchanged
        strip = lambda e: dict(e, checks=[c for c in e["checks"] if c["name"] != "ASSUMED inputs"])  # noqa: E731
        self.assertEqual(strip(doc["envelope"]), strip(self.want["envelope"]))
        row = [c for c in doc["envelope"]["checks"] if c["name"] == "ASSUMED inputs"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0]["result_status"], "manual check required")
        self.assertIn("Loads from the CAESAR II restraint summary at node 1040", row[0]["note"])
        self.assertIn("Corrosion allowance per the line list", row[0]["note"])
        self.assertEqual(doc["spec"]["project"], "Example unit tie-in")

    def test_the_caller_spec_is_not_modified(self):
        spec = bare()
        spec["project_basis"] = record()
        before = copy.deepcopy(spec)
        support_calc.run(spec, optimize=False)
        self.assertEqual(spec, before)

    def test_no_record_no_basis_keys(self):
        self.assertNotIn("project_basis_applied", self.want)
        self.assertNotIn("Basis - project basis record", R.markdown(self.want))
        self.assertFalse([k for k in json.loads(R.to_json(self.doc)) if k.startswith("_")])


class Conflicts(unittest.TestCase):

    def test_a_conflict_exits_2_with_the_shared_message(self):
        spec = caesar()
        spec["project_basis"] = record(equipment_axes={"global_vertical": "Z", "pipe_axis": "X"})
        code, out, err = main(spec)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, "input error: project_basis.equipment_axes.global_vertical conflicts with "
                              "input pipes.0.loads.vertical_axis\n")

    def test_a_title_block_conflict_exits_2(self):
        spec = caesar()
        spec["project_basis"] = record(project={"name": "Another project"})
        code, _, err = main(spec)
        self.assertEqual((code, err), (2, "input error: project_basis.project.name conflicts with input project\n"))

    def test_units_conflict_names_the_pipe(self):
        spec = caesar()
        spec["pipes"][1]["loads"]["units"] = "kip-in"
        spec["project_basis"] = record()
        code, _, err = main(spec)
        self.assertEqual((code, err), (2, "input error: project_basis.units conflicts with input "
                                          "pipes.1.loads.units\n"))

    def test_si_units_exit_2(self):
        spec = bare()
        spec["project_basis"] = record(units={"system": "SI"})
        code, _, err = main(spec)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("input error: project_basis.units.system SI cannot be used"), err)

    def test_a_force_moment_pair_the_engine_cannot_read_exits_2(self):
        spec = bare()
        spec["project_basis"] = record(units={"system": "USC", "force": "lbf", "moment": "in-lbf"})
        code, _, err = main(spec)
        self.assertEqual(code, 2)
        self.assertIn("project_basis.units force 'lbf' with moment 'in-lbf' cannot be used", err)

    def test_file_and_key_with_different_content_exit_2(self):
        spec = caesar()
        spec["project_basis"] = record()
        code, _, err = main(spec, record(project={"name": "Another project"}))
        self.assertEqual((code, err), (2, "input error: project_basis conflicts with --project-basis file\n"))

    def test_file_and_key_with_equal_content_run(self):
        spec = caesar()
        spec["project_basis"] = record()
        code, out, err = main(spec, record())
        self.assertEqual((code, err), (3, ""))               # ps-201's ASSUMED item and preset values hold it
        self.assertTrue(out.startswith("MANUAL CHECK REQUIRED - "), out)

    def test_the_file_alone_fills_like_the_key(self):
        spec = bare()
        code, out, _ = main(spec, record())
        self.assertEqual(code, 3)
        self.assertEqual(out, main(caesar())[1])

    def test_an_invalid_record_exits_2_with_the_path(self):
        spec = caesar()
        spec["project_basis"] = record(equipment_axes={"global_vertical": "Up"}, extra=1)
        code, _, err = main(spec)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith(f"input error: project_basis is not a valid {SCHEMA} record: "), err)
        self.assertIn("project_basis.extra: unknown key", err)
        self.assertIn("project_basis.equipment_axes.global_vertical: 'Up' is not one of Y, Z", err)


class Assumed(unittest.TestCase):

    BASIS = record(assumptions=[
        {"item": "Restraint loads from the issued CAESAR II model", "status": "ASSUMED",
         "note": "model rev B not yet checked", "owner": "lead"},
        {"item": "Concrete pier existing and sound", "status": "confirmed"},
        {"item": "Anchor product to be confirmed"}])

    @classmethod
    def setUpClass(cls):
        spec = caesar()
        spec["project_basis"] = cls.BASIS
        cls.doc = support_calc.run(spec, optimize=False)
        cls.md = R.markdown(cls.doc)

    def test_assumed_items_are_copied_verbatim(self):
        self.assertEqual(self.doc["project_basis_applied"]["assumptions"],
                         [self.BASIS["assumptions"][0], self.BASIS["assumptions"][2]])

    def test_assumed_items_join_the_spec_assumptions(self):
        self.assertEqual(self.doc["spec"]["assumed"][0], "Loads from the CAESAR II restraint summary at node 1040; Y vertical.")
        self.assertIn("ASSUMED (project basis): Restraint loads from the issued CAESAR II model; model rev B not "
                      "yet checked (owner: lead)", self.doc["assumed"])
        self.assertIn("ASSUMED (project basis): Anchor product to be confirmed", self.doc["assumed"])
        self.assertFalse([a for a in self.doc["assumed"] if "pier existing" in a])
        self.assertIn({"input": "assumed", "basis": "assumptions", "action": "filled"},
                      self.doc["project_basis_applied"]["fields_used"])

    def test_every_assumed_item_is_in_the_one_assumed_inputs_row(self):
        rows = [c for c in self.doc["envelope"]["checks"] if c["name"] == "ASSUMED inputs"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["note"], "confirm before issue: Loads from the CAESAR II restraint summary at "
                         "node 1040; Y vertical.; Restraint loads from the issued CAESAR II model; model rev B "
                         "not yet checked (owner: lead); Anchor product to be confirmed")
        self.assertEqual(self.doc["result_status"], "manual check required")

    def test_assumed_fills_an_absent_list(self):
        spec = caesar()
        spec.pop("assumed")
        spec["project_basis"] = self.BASIS
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(len(doc["spec"]["assumed"]), 2)
        self.assertIn({"input": "assumed", "basis": "assumptions", "action": "filled"},
                      doc["project_basis_applied"]["fields_used"])

    def test_section_1_lists_every_assumed_item_first(self):
        lines = self.md.splitlines()
        i = lines.index("## Basis - project basis record")
        self.assertLess(i, lines.index("## Design basis"))
        self.assertEqual(lines[i + 1:i + 5], [
            "",
            "**ASSUMED - confirm before issue:**",
            "- Restraint loads from the issued CAESAR II model; note: model rev B not yet checked; owner: lead",
            "- Anchor product to be confirmed"])
        section = "\n".join(lines[i:lines.index("## Design basis")])
        self.assertIn(f"| Basis item ({SCHEMA}) | Value |", section)
        self.assertIn("Taken from the record: project <- project.name (agreed)", section)

    def test_a_record_without_assumptions_says_so(self):
        spec = caesar()
        spec["project_basis"] = record()
        md = R.markdown(support_calc.run(spec, optimize=False))
        self.assertIn("## Basis - project basis record\n\nNo ASSUMED items in the project basis record.", md)


class Grammar(unittest.TestCase):

    def test_python_3_9_grammar(self):
        files = [os.path.join(SCRIPTS, "support_calc.py")] + sorted(glob.glob(os.path.join(SCRIPTS, "pipe_support", "*.py")))
        files += [os.path.join(ROOT, "tests", n) for n in ("test_pipe_support_basis.py", "test_pipe_support_status.py")]
        for path in files:
            with open(path, encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=path, feature_version=(3, 9))

    def test_the_skill_links_and_ships_the_reference(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("references/project-basis.md", text)
        self.assertIn("--project-basis", text)
        with open(os.path.join(SKILL, "references", "project-basis.md"), encoding="utf-8") as fh, \
                open(os.path.join(ROOT, "tools", "shared", "project-basis.md"), encoding="utf-8") as gh:
            self.assertEqual(fh.read(), gh.read())


if __name__ == "__main__":
    unittest.main()
