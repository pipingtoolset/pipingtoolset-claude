"""Shared project_basis block (plugin 0.8.0, B8): schema, load and conflict rule, fill semantics, copies.

The canonical text is tools/shared/project_basis.py; each of the seven skill scripts carries a
byte-identical copy between its BEGIN/END markers (written by tools/sync_shared_blocks.py), the way
the 0.7.0 code_values block is pinned. Standard library only:

    python -m unittest tests.test_project_basis_shared -v
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
SHARED = os.path.join(ROOT, "tools", "shared")
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
sys.path.insert(0, SHARED)

import project_basis as pb  # noqa: E402

SCRIPTS = {
    "load-case-builder": "loadcase_gen.py",
    "pressure-design": "pressure_design.py",
    "stress-screening": "stress_screening.py",
    "pipe-support": "support_calc.py",
    "iso-to-pcf": "build_pcf.py",
    "nozzle-load": "nozzle_load.py",
    "bolted-flange": "bolted_flange.py",
}
BEGIN = "# BEGIN shared {0} (do not edit here; source tools/shared/{0}.py)"
END = "# END shared {0}"


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def block_of(text, name):
    begin, end = BEGIN.format(name), END.format(name)
    if text.count(begin + "\n") != 1 or text.count(end + "\n") != 1:
        raise AssertionError(f"need exactly one {name} block")
    return text[text.index(begin):text.index(end) + len(end)]


def example():
    with open(os.path.join(SHARED, "project-basis.example.json"), encoding="utf-8") as fh:
        return json.load(fh)


class Schema(unittest.TestCase):

    def test_the_example_is_valid(self):
        self.assertEqual(pb.validate_project_basis(example()), [])

    def test_the_minimal_record_is_the_schema_id_alone(self):
        self.assertEqual(pb.validate_project_basis({"schema": "pipingtoolset.project-basis/1"}), [])
        self.assertEqual(pb.PROJECT_BASIS_SCHEMA_ID, "pipingtoolset.project-basis/1")

    def test_schema_is_required_and_exact(self):
        self.assertIn("project_basis.schema: required", pb.validate_project_basis({}))
        errs = pb.validate_project_basis({"schema": "pipingtoolset.project-basis/2"})
        self.assertTrue(errs and errs[0].startswith("project_basis.schema: 'pipingtoolset.project-basis/2' is not one of"))
        self.assertEqual(pb.validate_project_basis([]), ["project_basis: must be an object"])

    def test_unknown_keys_are_rejected_at_every_level(self):
        for path, mutate in (
                ("project_basis.extra", lambda b: b.update(extra=1)),
                ("project_basis.code.year", lambda b: b["code"].update(year="2022")),
                ("project_basis.states[1].temp", lambda b: b["states"][1].update(temp=1)),
                ("project_basis.states[0].slot.X", lambda b: b["states"][0]["slot"].update(X="X1")),
                ("project_basis.load_case_ids.cases.WIN", lambda b: b["load_case_ids"]["cases"].update(WIN="L9")),
                ("project_basis.equipment_axes.nozzle_axis_map.Fr", lambda b: b["equipment_axes"]["nozzle_axis_map"].update(Fr="+X"))):
            rec = example()
            mutate(rec)
            errs = pb.validate_project_basis(rec)
            self.assertEqual(len(errs), 1, errs)
            self.assertTrue(errs[0].startswith(path + ": unknown key"), errs)

    def test_bad_enum_words_are_rejected(self):
        for path, mutate in (
                ("project_basis.states[0].role", lambda b: b["states"][0].update(role="normal")),
                ("project_basis.service.fluid_category", lambda b: b["service"].update(fluid_category="Category X")),
                ("project_basis.units.system", lambda b: b["units"].update(system="MKS")),
                ("project_basis.load_case_ids.software", lambda b: b["load_case_ids"].update(software="ROHR2")),
                ("project_basis.equipment_axes.global_vertical", lambda b: b["equipment_axes"].update(global_vertical="X")),
                ("project_basis.equipment_axes.nozzle_axis_map.Fx", lambda b: b["equipment_axes"]["nozzle_axis_map"].update(Fx="up")),
                ("project_basis.materials[0].form", lambda b: b["materials"][0].update(form="spiral")),
                ("project_basis.materials[0].use", lambda b: b["materials"][0].update(use="valve")),
                ("project_basis.assumptions[0].status", lambda b: b["assumptions"][0].update(status="assumed")),
                ("project_basis.states[0].slot.T", lambda b: b["states"][0]["slot"].update(T="P1"))):
            rec = example()
            mutate(rec)
            errs = pb.validate_project_basis(rec)
            self.assertEqual(len(errs), 1, errs)
            self.assertTrue(errs[0].startswith(path + ": "), errs)

    def test_bad_types_are_rejected(self):
        rec = example()
        rec["code"]["edition"] = 2022
        rec["service"]["corroded"] = "yes"
        rec["states"][0]["T_F"] = "350"
        rec["states"][1]["P_psig"] = True
        rec["load_case_ids"]["cases"]["OCC"] = ["L5", 6.5]
        rec["owner_practice"][0]["items"].append(7)
        errs = pb.validate_project_basis(rec)
        self.assertIn("project_basis.code.edition: must be a string (write an edition year or an id in quotes)", errs)
        self.assertIn("project_basis.service.corroded: must be a true or false", errs)
        self.assertIn("project_basis.states[0].T_F: must be a number", errs)
        self.assertIn("project_basis.states[1].P_psig: must be a number", errs)
        self.assertIn("project_basis.load_case_ids.cases.OCC: ['L5', 6.5] has the wrong type", errs)
        self.assertIn("project_basis.owner_practice[0].items[2]: 7 has the wrong type", errs)
        self.assertEqual(len(errs), 6, errs)

    def test_required_keys_inside_lists_and_unique_state_keys(self):
        rec = example()
        del rec["states"][1]["key"]
        rec["assumptions"].append({"status": "ASSUMED"})
        rec["owner_practice"].append({"items": []})
        errs = pb.validate_project_basis(rec)
        self.assertIn("project_basis.states[1].key: required", errs)
        self.assertIn("project_basis.assumptions[2].item: required", errs)
        self.assertIn("project_basis.owner_practice[1].document: required", errs)
        rec = example()
        rec["states"][1]["key"] = "OPE1"
        self.assertEqual(pb.validate_project_basis(rec), ["project_basis.states: key 'OPE1' is used more than once"])


class Load(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text, encoding="utf-8"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding=encoding) as fh:
            fh.write(text)
        return path

    def test_neither_given_is_none(self):
        self.assertIsNone(pb.load_project_basis(None, None))
        self.assertIsNone(pb.load_project_basis("", None))

    def test_top_level_only_returns_a_validated_copy(self):
        rec = example()
        got = pb.load_project_basis(None, rec)
        self.assertEqual(got, rec)
        got["code"]["edition"] = "1999"
        self.assertEqual(rec["code"]["edition"], "2022")

    def test_file_only_and_a_bom_file(self):
        rec = example()
        self.assertEqual(pb.load_project_basis(self.write("a.json", json.dumps(rec)), None), rec)
        self.assertEqual(pb.load_project_basis(self.write("b.json", json.dumps(rec), "utf-8-sig"), None), rec)

    def test_both_equal_is_fine_and_both_different_conflicts(self):
        rec = example()
        path = self.write("a.json", json.dumps(rec))
        self.assertEqual(pb.load_project_basis(path, copy.deepcopy(rec)), rec)
        other = example()
        other["code"]["edition"] = "2020"
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.load_project_basis(path, other)
        self.assertEqual(str(cm.exception), "project_basis conflicts with --project-basis file")
        self.assertIsInstance(cm.exception, ValueError)

    def test_invalid_records_and_files_raise(self):
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.load_project_basis(None, {"schema": "pipingtoolset.project-basis/1", "colour": "red"})
        self.assertEqual(str(cm.exception), "project_basis is not a valid pipingtoolset.project-basis/1 record: "
                                            "project_basis.colour: unknown key (valid: " +
                         ", ".join(pb.PROJECT_BASIS_SCHEMA[1]) + ")")
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.load_project_basis(self.write("bad.json", "{not json"), None)
        self.assertIn("is not valid JSON", str(cm.exception))
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.load_project_basis(os.path.join(self.tmp.name, "missing.json"), None)
        self.assertIn("cannot read --project-basis file", str(cm.exception))
        with self.assertRaises(pb.ProjectBasisError):
            pb.load_project_basis(self.write("null.json", "null"), None)


class Fill(unittest.TestCase):

    MAP = [
        ("edition", "code.edition", None),
        ("P", "states[role=design|first].P_psig", None),
        ("T", "states[role=design|first].T_F", None),
        ("W_basis", "materials[use=pipe].form", lambda f: "seamless" if f == "seamless" else pb.PROJECT_BASIS_SKIP),
        ("design.vertical_axis", "equipment_axes.global_vertical", None),
        ("software", "load_case_ids.software", None),
        ("absent", "materials[use=bolt].grade", None),
    ]

    def setUp(self):
        self.basis = pb.load_project_basis(None, example())

    def test_absent_inputs_are_filled_and_the_input_is_not_modified(self):
        inputs = {"D": 6.625, "design": {"method": "ASD"}}
        before = copy.deepcopy(inputs)
        eff, applied = pb.fill_from_basis(inputs, self.basis, self.MAP)
        self.assertEqual(inputs, before)
        self.assertEqual(eff, {"D": 6.625, "design": {"method": "ASD", "vertical_axis": "Y"}, "edition": "2022",
                               "P": 150, "T": 400, "W_basis": "seamless", "software": "CAESAR II"})
        self.assertEqual(applied["fields_used"][:3], [
            {"input": "edition", "basis": "code.edition", "action": "filled"},
            {"input": "P", "basis": "states[role=design|first].P_psig", "action": "filled"},
            {"input": "T", "basis": "states[role=design|first].T_F", "action": "filled"}])
        self.assertEqual([u["input"] for u in applied["fields_used"]],
                         ["edition", "P", "T", "W_basis", "design.vertical_axis", "software"])

    def test_applied_shape(self):
        _, applied = pb.fill_from_basis({}, self.basis, self.MAP)
        self.assertEqual(sorted(applied), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(applied["schema"], "pipingtoolset.project-basis/1")
        self.assertEqual(applied["conflicts"], [])
        self.assertEqual(applied["assumptions"], [example()["assumptions"][0]])

    def test_present_and_equal_agrees_null_is_absent(self):
        eff, applied = pb.fill_from_basis({"edition": "2022", "P": 150.0, "T": None}, self.basis, self.MAP[:3])
        self.assertEqual([u["action"] for u in applied["fields_used"]], ["agreed", "agreed", "filled"])
        self.assertEqual(eff["T"], 400)

    def test_present_and_different_conflicts(self):
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.fill_from_basis({"edition": "2020"}, self.basis, self.MAP)
        self.assertEqual(str(cm.exception), "project_basis.code.edition conflicts with input edition")
        with self.assertRaises(pb.ProjectBasisError) as cm:
            pb.fill_from_basis({"P": 151}, self.basis, self.MAP)
        self.assertEqual(str(cm.exception), "project_basis.states[role=design|first].P_psig conflicts with input P")

    def test_selectors_fall_back_to_the_first_state_and_skip_cleanly(self):
        rec = example()
        del rec["states"][1]
        rec["materials"][0]["form"] = "welded"
        eff, applied = pb.fill_from_basis({}, rec, self.MAP)
        self.assertEqual((eff["P"], eff["T"]), (120, 350))
        self.assertNotIn("W_basis", eff)
        self.assertNotIn("absent", eff)
        self.assertEqual(pb.basis_get(rec, "states[role=design].T_F", "none"), "none")
        self.assertEqual(pb.basis_get(rec, "states[0].key"), "OPE1")
        self.assertIsNone(pb.basis_get(rec, "states[5].key"))
        self.assertEqual(pb.basis_get(rec, "load_case_ids.cases.OCC"), ["L5", "L6"])

    def test_a_transform_may_stop_the_run(self):
        def usc_only(system):
            if system != "USC":
                raise pb.ProjectBasisError("project_basis.units.system SI: this engine is USC only")
            return pb.PROJECT_BASIS_SKIP
        rec = example()
        rec["units"]["system"] = "SI"
        with self.assertRaises(pb.ProjectBasisError):
            pb.fill_from_basis({}, rec, [("units", "units.system", usc_only)])
        self.assertEqual(pb.fill_from_basis({}, example(), [("units", "units.system", usc_only)])[0], {})

    def test_no_basis_returns_the_same_inputs_and_none(self):
        inputs = {"a": 1}
        eff, applied = pb.fill_from_basis(inputs, None, self.MAP)
        self.assertIs(eff, inputs)
        self.assertIsNone(applied)

    def test_a_non_object_parent_input_is_an_error(self):
        with self.assertRaises(pb.ProjectBasisError):
            pb.fill_from_basis({"design": "ASD"}, self.basis, self.MAP)

    def test_mark_used_units_and_assumptions(self):
        _, applied = pb.fill_from_basis({}, self.basis, [])
        pb.mark_basis_used(applied, "owner_practice")
        self.assertEqual(applied["fields_used"], [{"input": None, "basis": "owner_practice", "action": "noted"}])
        self.assertIsNone(pb.mark_basis_used(None, "owner_practice"))
        self.assertEqual(pb.basis_units(self.basis)["moment"], "ft-lbf")
        self.assertEqual(pb.basis_units({"units": {"system": "SI", "pressure": "bar"}})["pressure"], "bar")
        self.assertEqual(pb.basis_units({}), {})
        rec = {"assumptions": [{"item": "a"}, {"item": "b", "status": "confirmed"}, {"item": "c", "status": "ASSUMED"}]}
        self.assertEqual(pb.basis_assumptions(rec), [{"item": "a"}, {"item": "c", "status": "ASSUMED"}])


class Render(unittest.TestCase):

    def test_assumed_items_come_first_then_the_record_then_fields_used(self):
        basis = example()
        _, applied = pb.fill_from_basis({}, basis, [("edition", "code.edition", None)])
        md = pb.render_basis_section(applied, basis, heading="## 1. Basis")
        lines = md.splitlines()
        self.assertEqual(lines[0], "## 1. Basis")
        self.assertEqual(lines[2], "**ASSUMED - confirm before issue:**")
        self.assertEqual(lines[3], "- Corrosion allowance per the line list; note: line list not yet issued; owner: lead")
        self.assertNotIn("Design state governs", md.split("| Basis item")[0])
        self.assertIn("| State OPE1 | name=Normal operating, role=operating, T_F=350, P_psig=120, cycles=7000, "
                      "slot=T=T1, P=P1, D=D1 |", lines)
        self.assertIn("| Service | fluid_category=Normal, fluid=hydrocarbon liquid, corroded=yes, cyclic=no |", lines)
        self.assertEqual(lines[-1], "Taken from the record: edition <- code.edition (filled)")
        self.assertTrue(md.isascii() if hasattr(md, "isascii") else all(ord(c) < 128 for c in md))

    def test_no_assumptions_and_no_basis(self):
        md = pb.render_basis_section(None, {"schema": pb.PROJECT_BASIS_SCHEMA_ID})
        self.assertTrue(md.startswith("No ASSUMED items in the project basis record.\n"))
        self.assertEqual(pb.render_basis_section(None, None), "")


class Copies(unittest.TestCase):
    """The seven scripts carry the canonical block byte for byte; the shipped example and reference too."""

    def test_canonical_block_hygiene(self):
        block = block_of(read_bytes(os.path.join(SHARED, "project_basis.py")).decode("utf-8"), "project_basis")
        tree = ast.parse(block, feature_version=(3, 9))
        kinds = {type(n).__name__ for n in tree.body}
        self.assertLessEqual(kinds, {"Assign", "FunctionDef", "ClassDef"})  # names only, no top-level import
        self.assertTrue(all(ord(c) < 128 for c in block))
        for word in ("urllib", "http.client", "socket", "requests", "httpx", "importlib", "__import__", "print("):
            self.assertNotIn(word, block)
        self.assertEqual(block.count("open("), 1)  # the --project-basis file read only
        exec(compile(block, "project_basis block", "exec"), {})  # runs standalone, nothing else needed

    def test_seven_scripts_carry_the_canonical_block(self):
        canonical = block_of(read_bytes(os.path.join(SHARED, "project_basis.py")).decode("utf-8"), "project_basis")
        for skill, script in SCRIPTS.items():
            text = read_bytes(os.path.join(SKILLS, skill, "scripts", script)).decode("utf-8")
            self.assertEqual(block_of(text, "project_basis"), canonical, skill)
            self.assertLess(text.index(END.format("project_basis")), text.index(BEGIN.format("result_status")), skill)

    def test_example_copies_are_identical(self):
        canonical = read_bytes(os.path.join(SHARED, "project-basis.example.json"))
        for skill in SCRIPTS:
            path = os.path.join(SKILLS, skill, "scripts", "examples", "project-basis.example.json")
            self.assertEqual(read_bytes(path), canonical, skill)

    def test_reference_copies_are_identical_wherever_present_or_linked(self):
        canonical = read_bytes(os.path.join(SHARED, "project-basis.md"))
        for skill in SCRIPTS:
            path = os.path.join(SKILLS, skill, "references", "project-basis.md")
            with open(os.path.join(SKILLS, skill, "SKILL.md"), encoding="utf-8") as fh:
                linked = "references/project-basis.md" in fh.read()
            if linked or os.path.exists(path):
                self.assertEqual(read_bytes(path), canonical, skill)

    def test_sync_check_is_green(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sync_shared_blocks.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sync check ok", r.stdout)

    def test_sync_check_reports_drift(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import sync_shared_blocks as sync  # noqa: E402
        text = read_bytes(os.path.join(SKILLS, "pressure-design", "scripts", "pressure_design.py")).decode("utf-8")
        block = block_of(text, "project_basis")
        drifted = text.replace(block, block.replace("PROJECT_BASIS_SKIP = object()", "PROJECT_BASIS_SKIP = None"))
        self.assertNotEqual(drifted, text)
        self.assertEqual(sync.apply_block(drifted, "project_basis", sync.canonical_block("project_basis")), text)
        bare = text.replace(block_of(text, "result_status") + "\n\n\n", "").replace(block + "\n\n\n", "")
        self.assertNotIn("# BEGIN shared", bare)
        again = bare
        for name in sync.BLOCKS:
            again = sync.apply_block(again, name, sync.canonical_block(name))
        self.assertEqual(again, text)


if __name__ == "__main__":
    unittest.main()
