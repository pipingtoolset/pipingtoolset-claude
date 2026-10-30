"""iso-to-pcf: the project basis record (B8) - fill map, conflicts, ASSUMED rendering, CLI.

Standard library only:  python -m unittest tests.test_iso_to_pcf_basis -v
"""

from __future__ import annotations

import ast
import copy
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "iso-to-pcf")
SCRIPTS = os.path.join(SKILL, "scripts")
DEMO = os.path.join(SCRIPTS, "examples", "demo-line.json")
EXAMPLE = os.path.join(SCRIPTS, "examples", "project-basis.example.json")
TOOL = os.path.join(SCRIPTS, "build_pcf.py")
sys.path.insert(0, SCRIPTS)

import build_pcf  # noqa: E402


def demo() -> dict:
    with open(DEMO, encoding="utf-8") as fh:
        return json.load(fh)


def basis(**parts) -> dict:
    rec = {"schema": "pipingtoolset.project-basis/1"}
    rec.update(parts)
    return rec


def build(spec: dict, cli_path=None) -> build_pcf.Builder:
    return build_pcf.Builder(copy.deepcopy(spec), cli_path).build()


def text_of(spec: dict, cli_path=None) -> str:
    return build(spec, cli_path).pcf.text()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = build_pcf.main(argv)
    return code, out.getvalue(), err.getvalue()


def used(applied, name):
    return [u for u in applied["fields_used"] if u["input"] == name]


class FillMap(unittest.TestCase):

    def test_axes_filled_from_global_vertical(self):
        base = demo()
        base["axes"] = "Y-up"
        want = text_of(base)
        for vertical, axes in (("Y", "Y-up"), ("Z", "Z-up")):
            spec = demo()
            del spec["axes"]
            spec["project_basis"] = basis(equipment_axes={"global_vertical": vertical})
            b = build(spec)
            self.assertEqual(b.spec["axes"], axes)
            self.assertEqual(used(b.basis_applied, "axes")[0]["action"], "filled")
            self.assertEqual(b.pcf.axes, axes)
        spec = demo()
        del spec["axes"]
        spec["project_basis"] = basis(equipment_axes={"global_vertical": "Y"})
        self.assertEqual(text_of(spec), want)

    def test_axes_agreed(self):
        spec = demo()
        spec["project_basis"] = basis(equipment_axes={"global_vertical": "Z"})
        b = build(spec)
        self.assertEqual(used(b.basis_applied, "axes")[0]["action"], "agreed")

    def test_axes_conflict(self):
        spec = demo()
        spec["project_basis"] = basis(equipment_axes={"global_vertical": "Y"})
        with self.assertRaisesRegex(build_pcf.ProjectBasisError,
                                    r"^project_basis\.equipment_axes\.global_vertical conflicts with input axes$"):
            build(spec)

    def test_units_filled_from_an_explicit_mm(self):
        spec = demo()
        del spec["units"]
        spec["project_basis"] = basis(units={"length": "mm"})
        b = build(spec)
        self.assertEqual(b.spec["units"], "MM")
        self.assertEqual(used(b.basis_applied, "units")[0]["action"], "filled")
        self.assertIn("UNITS-CO-ORDS MM", b.pcf.text())

    def test_units_conflict_when_the_spec_asks_for_inches(self):
        spec = demo()
        spec["units"] = "INCH"
        spec["project_basis"] = basis(units={"length": "mm"})
        with self.assertRaisesRegex(build_pcf.ProjectBasisError,
                                    r"^project_basis\.units\.length conflicts with input units$"):
            build(spec)

    def test_units_other_than_mm_is_the_models_own_and_never_changes_the_pcf(self):
        # The record is shared by seven skills; a CAESAR II model in inches is legitimate, and
        # the PCF is written in mm regardless. It is noted, not filled and not a conflict.
        want = text_of(demo())
        for given in ({"length": "in"}, {"system": "USC"}):
            spec = demo()
            spec["project_basis"] = basis(units=given)
            b = build(spec)
            self.assertEqual(b.pcf.text(), want)
            self.assertEqual(b.spec["units"], "MM")
            if "length" in given:
                self.assertEqual(used(b.basis_applied, "units")[0]["action"], "noted")
            else:
                self.assertEqual(used(b.basis_applied, "units"), [])

    def test_pipeline_reference_filled_and_checked(self):
        spec = demo()
        del spec["pipeline"]
        spec["project_basis"] = basis(project={"line": "6-P-2002-A1"})
        b = build(spec)
        self.assertIn("PIPELINE-REFERENCE 6-P-2002-A1\r\n", b.pcf.text())
        self.assertEqual(used(b.basis_applied, "pipeline.reference")[0]["action"], "filled")
        spec = demo()
        spec["project_basis"] = basis(project={"line": "DEMO-6-P-1001"})
        self.assertEqual(used(build(spec).basis_applied, "pipeline.reference")[0]["action"], "agreed")
        spec["project_basis"] = basis(project={"line": "OTHER"})
        with self.assertRaisesRegex(build_pcf.ProjectBasisError,
                                    r"^project_basis\.project\.line conflicts with input pipeline\.reference$"):
            build(spec)

    def test_pipeline_attributes_survive_the_fill(self):
        spec = demo()
        spec["pipeline"] = {"attributes": [["PIPING-SPEC", "A1"]]}
        spec["project_basis"] = basis(project={"line": "L-1"})
        text = text_of(spec)
        self.assertIn("PIPELINE-REFERENCE L-1\r\n", text)
        self.assertIn("    PIPING-SPEC A1\r\n", text)

    def test_other_fields_are_reported_not_used(self):
        spec = demo()
        spec["project_basis"] = basis(code={"standard": "B31.3", "edition": "2022"}, service={"fluid": "water"},
                                      states=[{"key": "A", "role": "design", "T_F": 100}])
        b = build(spec)
        self.assertEqual(b.basis_applied["fields_used"], [])
        self.assertEqual(b.pcf.text(), text_of(demo()))

    def test_the_example_record_builds_a_y_up_line(self):
        spec = demo()
        del spec["axes"], spec["pipeline"]
        with open(EXAMPLE, encoding="utf-8") as fh:
            spec["project_basis"] = json.load(fh)
        b = build(spec)
        self.assertEqual(b.pcf.axes, "Y-up")
        self.assertIn('PIPELINE-REFERENCE 6"-P-1001-A1\r\n', b.pcf.text())
        names = [u["input"] for u in b.basis_applied["fields_used"]]
        self.assertEqual(names, ["axes", "pipeline.reference", "assumed"])


class Assumptions(unittest.TestCase):

    REC = basis(assumptions=[
        {"item": "Corrosion allowance per the line list", "status": "ASSUMED", "note": "list not issued", "owner": "lead"},
        {"item": "Design state governs", "status": "confirmed"},
        {"item": "Bare ASSUMED item"}])

    def test_assumed_items_join_the_assumed_list_verbatim(self):
        spec = demo()
        spec["project_basis"] = copy.deepcopy(self.REC)
        b = build(spec)
        r = build_pcf.report(b, b.bom_check())
        self.assertEqual(r["assumed"][0], "Gasket thickness 1/8 in (not dimensioned on the demo iso)")
        self.assertIn("project basis: Corrosion allowance per the line list - list not issued (lead)", r["assumed"])
        self.assertIn("project basis: Bare ASSUMED item", r["assumed"])
        self.assertFalse([a for a in r["assumed"] if "Design state governs" in a])
        # the record's own items are copied verbatim into the applied block
        self.assertEqual(r["project_basis_applied"]["assumptions"],
                         [self.REC["assumptions"][0], self.REC["assumptions"][2]])
        self.assertEqual(used(r["project_basis_applied"], "assumed")[0]["action"], "filled")

    def test_assumed_list_is_created_when_the_spec_has_none(self):
        spec = demo()
        del spec["assumed"]
        spec["project_basis"] = copy.deepcopy(self.REC)
        b = build(spec)
        self.assertEqual(used(b.basis_applied, "assumed")[0]["action"], "filled")
        self.assertEqual(b.spec["assumed"][0], "project basis: Corrosion allowance per the line list - list not issued (lead)")

    def test_no_assumed_items_leaves_the_assumed_list_alone(self):
        spec = demo()
        spec["project_basis"] = basis(assumptions=[{"item": "x", "status": "confirmed"}])
        b = build(spec)
        self.assertEqual(b.spec["assumed"], demo()["assumed"])
        self.assertEqual(used(b.basis_applied, "assumed"), [])

    def test_assumed_items_head_the_basis_section_of_the_report(self):
        spec = demo()
        spec["project_basis"] = copy.deepcopy(self.REC)
        b = build(spec)
        text = build_pcf.render(build_pcf.report(b, b.bom_check()), b.basis)
        lines = text.splitlines()
        self.assertEqual(lines[0], "PCF build report - DEMO-6-P-1001")
        self.assertTrue(lines[1].startswith("Result status: "))
        head = lines.index("1. Basis")
        self.assertEqual(lines[head + 2], "**ASSUMED - confirm before issue:**")
        self.assertEqual(lines[head + 3], "- Corrosion allowance per the line list; note: list not issued; owner: lead")
        self.assertEqual(lines[head + 4], "- Bare ASSUMED item")
        self.assertLess(text.index("1. Basis"), text.index("Axes: "))
        self.assertLess(text.index("**ASSUMED"), text.index("Component census"))
        self.assertIn("Taken from the record: assumed <- assumptions (filled)", text)

    def test_no_assumed_sentence_when_the_record_has_none(self):
        spec = demo()
        spec["project_basis"] = basis(project={"name": "N"})
        b = build(spec)
        text = build_pcf.render(build_pcf.report(b, b.bom_check()), b.basis)
        self.assertIn("No ASSUMED items in the project basis record.", text)

    def test_no_record_no_section_and_no_applied_block(self):
        b = build(demo())
        r = build_pcf.report(b, b.bom_check())
        self.assertNotIn("project_basis_applied", r)
        self.assertNotIn("1. Basis", build_pcf.render(r))
        self.assertNotIn("project basis:", " ".join(r["assumed"]))


class Applied(unittest.TestCase):

    def test_shape_of_project_basis_applied(self):
        spec = demo()
        del spec["axes"]
        spec["project_basis"] = basis(equipment_axes={"global_vertical": "Z"})
        b = build(spec)
        r = build_pcf.report(b, b.bom_check())
        applied = r["project_basis_applied"]
        self.assertEqual(sorted(applied), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(applied["schema"], "pipingtoolset.project-basis/1")
        self.assertEqual(applied["conflicts"], [])
        self.assertEqual(applied["fields_used"],
                         [{"input": "axes", "basis": "equipment_axes.global_vertical", "action": "filled"}])
        json.dumps(r)

    def test_the_caller_spec_is_not_modified(self):
        spec = demo()
        del spec["axes"]
        spec["project_basis"] = basis(equipment_axes={"global_vertical": "Y"})
        before = copy.deepcopy(spec)
        build_pcf.Builder(spec).build()
        self.assertEqual(spec, before)


class FileAndKey(unittest.TestCase):

    def write(self, d, name, obj):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_cli_flag_fills(self):
        with tempfile.TemporaryDirectory() as d:
            spec = demo()
            del spec["axes"]
            sp = self.write(d, "s.json", spec)
            bp = self.write(d, "b.json", basis(equipment_axes={"global_vertical": "Y"}))
            out = os.path.join(d, "o.pcf")
            code, stdout, _ = run_main([sp, "-o", out, "--project-basis", bp])
            self.assertEqual(code, 0)
            self.assertIn("Axes: Y-up", stdout)
            self.assertIn("1. Basis", stdout)
            code, stdout, _ = run_main([sp, "-o", out, "--project-basis", bp, "--json"])
            self.assertEqual(json.loads(stdout)["project_basis_applied"]["fields_used"][0]["input"], "axes")

    def test_file_and_key_equal_is_fine_and_different_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            rec = basis(equipment_axes={"global_vertical": "Z"})
            spec = demo()
            spec["project_basis"] = rec
            sp = self.write(d, "s.json", spec)
            out = os.path.join(d, "o.pcf")
            same = self.write(d, "same.json", rec)
            self.assertEqual(run_main([sp, "-o", out, "--project-basis", same])[0], 0)
            other = self.write(d, "other.json", basis(equipment_axes={"global_vertical": "Y"}))
            os.remove(out)
            code, _, err = run_main([sp, "-o", out, "--project-basis", other])
            self.assertEqual(code, 2)
            self.assertIn("project_basis conflicts with --project-basis file", err)
            self.assertFalse(os.path.exists(out))

    def test_conflict_exit_code_message_and_no_pcf_through_the_real_cli(self):
        with tempfile.TemporaryDirectory() as d:
            spec = demo()
            spec["project_basis"] = basis(equipment_axes={"global_vertical": "Y"})
            sp = self.write(d, "s.json", spec)
            out = os.path.join(d, "o.pcf")
            r = subprocess.run([sys.executable, TOOL, sp, "-o", out], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 2)
            self.assertIn("project_basis.equipment_axes.global_vertical conflicts with input axes", r.stderr)
            self.assertFalse(os.path.exists(out))

    def test_invalid_record_and_missing_file_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            sp = self.write(d, "s.json", demo())
            out = os.path.join(d, "o.pcf")
            bad = self.write(d, "bad.json", basis(equipment_axes={"global_vertical": "Q"}))
            code, _, err = run_main([sp, "-o", out, "--project-basis", bad])
            self.assertEqual((code, "global_vertical" in err), (2, True))
            unknown = self.write(d, "unk.json", basis(colour="red"))
            self.assertEqual(run_main([sp, "-o", out, "--project-basis", unknown])[0], 2)
            code, _, err = run_main([sp, "-o", out, "--project-basis", os.path.join(d, "nope.json")])
            self.assertEqual(code, 2)
            self.assertFalse(os.path.exists(out))

    def test_a_spec_defect_still_exits_1_with_a_valid_record(self):
        with tempfile.TemporaryDirectory() as d:
            spec = demo()
            spec["items"].insert(0, {"type": "widget"})
            spec["project_basis"] = basis(project={"name": "N"})
            sp = self.write(d, "s.json", spec)
            self.assertEqual(run_main([sp, "-o", os.path.join(d, "o.pcf")])[0], 1)

    def test_code_values_is_still_refused_with_a_record(self):
        spec = demo()
        spec["code_values"] = {"S": {"value": 1, "unit": "psi", "source": "user"}}
        spec["project_basis"] = basis(project={"name": "N"})
        with self.assertRaises(build_pcf.CodeValuesError):
            build(spec)


class Grammar(unittest.TestCase):

    def test_python_39_grammar(self):
        for name in ("build_pcf.py", "validate_pcf.py", "pcf_lib.py"):
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=name, feature_version=(3, 9))

    def test_scripts_stay_ascii(self):
        for name in ("build_pcf.py", "validate_pcf.py", "pcf_lib.py"):
            with open(os.path.join(SCRIPTS, name), "rb") as fh:
                self.assertTrue(all(b < 128 for b in fh.read()), name)

    def test_skill_links_the_shipped_reference_and_example(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertRegex(body, r"references/project-basis\.md")
        self.assertTrue(os.path.exists(os.path.join(SKILL, "references", "project-basis.md")))
        self.assertTrue(re.search(r"never relabel", body))
        self.assertLessEqual(len(body.split()), 1970)   # the 0.7.2 body had 1970 words: net growth stays at or below zero


class BundledPairing(unittest.TestCase):
    """The shipped record is Y-vertical: it must work with a shipped spec, and conflict with the Z-up ones."""

    def test_example_record_builds_with_its_paired_spec(self):
        pair = os.path.join(SCRIPTS, "examples", "project-basis-line.json")
        with open(pair, encoding="utf-8") as fh:
            spec = json.load(fh)
        with open(EXAMPLE, encoding="utf-8") as fh:
            spec["project_basis"] = json.load(fh)
        b = build(spec)
        self.assertEqual(b.pcf.axes, "Y-up")
        self.assertIn('PIPELINE-REFERENCE 6"-P-1001-A1\r\n', b.pcf.text())

    def test_example_record_conflicts_with_the_z_up_examples(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            rec = json.load(fh)
        for name in ("demo-line.json", "minimal-proven.json"):
            with open(os.path.join(SCRIPTS, "examples", name), encoding="utf-8") as fh:
                spec = json.load(fh)
            spec["project_basis"] = rec
            with self.assertRaisesRegex(Exception, r"equipment_axes\.global_vertical conflicts with input axes"):
                build(spec)

    def test_spec_format_names_the_pairing(self):
        with open(os.path.join(SKILL, "references", "spec-format.md"), encoding="utf-8") as fh:
            self.assertIn("project-basis-line.json", fh.read())


if __name__ == "__main__":
    unittest.main()
