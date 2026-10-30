"""Project basis tests for the bolted-flange skill (plugin 0.8.0, B8).

The skill takes `project_basis` (schema pipingtoolset.project-basis/1) as a top-level input or as
`--project-basis <file>`. It fills the design pressure P from the design state, checks an explicit
units.moment against the moment input given, reads the design temperature, code route and owner
acceptance for the sheet, and lists the ASSUMED items at the top of section 1. A different value in
the input and the record exits 2; the engine numbers never change.

    python -m unittest tests.test_bolted_flange_basis -v
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
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "bolted-flange")
SCRIPTS = os.path.join(SKILL, "scripts")
TOOL = os.path.join(SCRIPTS, "bolted_flange.py")
EXAMPLE_RECORD = os.path.join(SCRIPTS, "examples", "project-basis.example.json")
EXAMPLE_JOB = os.path.join(SCRIPTS, "examples", "integral-weld-neck.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import bolted_flange as bf  # noqa: E402
import parity  # noqa: E402

SCREEN = "connections.flange-equivalent-pressure"
APP2 = "aux.app2-flange-integral"
DERIVE = "connections.flange-derive"
SCHEMA = "pipingtoolset.project-basis/1"
FILL_PATH = "states[role=design|first].P_psig"


def record(**over):
    rec = {
        "schema": SCHEMA,
        "project": {"name": "Unit 4 tie-in", "line": "6-P-1001", "calcBy": "MN"},
        "code": {"standard": "B31.3", "edition": "2022"},
        "states": [
            {"key": "OPE", "name": "Normal operating", "role": "operating", "T_F": 300, "P_psig": 100},
            {"key": "DES", "name": "Design", "role": "design", "T_F": 350, "P_psig": 500},
        ],
        "units": {"system": "USC"},
        "assumptions": [
            {"item": "Rating at design temperature not yet read", "status": "ASSUMED", "owner": "lead"},
            {"item": "Gasket factors confirmed from the datasheet", "status": "confirmed"},
        ],
    }
    rec.update(over)
    return rec


def screen_job(**over):
    job = {"F": 2000, "M_in_lbf": 50000, "G": 6, "ratedPressure": 1975}
    job.update(over)
    return job


def app2_job(**over):
    with open(EXAMPLE_JOB, encoding="utf-8") as fh:
        job = json.load(fh)
    job["P"] = 500  # the design pressure of record()
    job.update(over)
    return job


def run_cli(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, encoding="utf-8")


class WithTempFiles(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)

    def write(self, name, obj):
        path = os.path.join(self._dir.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path


class FillFromTheDesignState(unittest.TestCase):
    def test_p_is_filled_on_both_pressure_modules(self):
        for module, job in ((SCREEN, screen_job()), (APP2, {k: v for k, v in app2_job().items() if k != "P"})):
            env = bf.run_module(module, dict(job, project_basis=record()))
            self.assertEqual(env["inputs"]["P"], 500, module)
            applied = env["project_basis_applied"]
            self.assertIn({"input": "P", "basis": FILL_PATH, "action": "filled"}, applied["fields_used"], module)

    def test_the_numbers_equal_the_run_with_p_typed(self):
        for module, job in ((SCREEN, screen_job()), (APP2, app2_job())):
            typed = bf.run_module(module, dict(job, P=500))
            filled = bf.run_module(module, dict({k: v for k, v in job.items() if k != "P"}, project_basis=record()))
            self.assertEqual(filled["output"], typed["output"], module)
            self.assertEqual(filled["status"], typed["status"], module)
            self.assertEqual(filled["inputs"], typed["inputs"], module)

    def test_first_state_is_used_when_no_state_has_the_design_role(self):
        rec = record(states=[{"key": "OPE", "role": "operating", "T_F": 300, "P_psig": 120}])
        env = bf.run_module(SCREEN, dict(screen_job(), project_basis=rec))
        self.assertEqual(env["inputs"]["P"], 120)

    def test_an_equal_p_is_agreed(self):
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=record()))
        self.assertIn({"input": "P", "basis": FILL_PATH, "action": "agreed"}, env["project_basis_applied"]["fields_used"])

    def test_a_different_p_is_a_conflict_with_the_exact_message(self):
        for module, job in ((SCREEN, screen_job(P=300)), (APP2, app2_job(P=300))):
            with self.assertRaises(ValueError) as cm:
                bf.run_module(module, dict(job, project_basis=record()))
            self.assertEqual(str(cm.exception), f"project_basis.{FILL_PATH} conflicts with input P", module)

    def test_the_conflict_exits_2_through_the_cli(self):
        r = run_cli(SCREEN, "--input", json.dumps(dict(screen_job(P=300), project_basis=record())))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertEqual(r.stderr, f"input error: project_basis.{FILL_PATH} conflicts with input P\n")

    def test_derive_has_nothing_to_fill_but_still_reports_the_record(self):
        job = {"facing": "flat", "gasket_ID": 10, "gasket_OD": 12}
        env = bf.run_module(DERIVE, dict(job, project_basis=record()))
        self.assertNotIn("P", env["inputs"])
        self.assertEqual(env["project_basis_applied"]["schema"], SCHEMA)
        self.assertEqual(env["project_basis_applied"]["conflicts"], [])

    def test_applied_has_the_pinned_shape_and_copies_the_assumed_items_verbatim(self):
        applied = bf.run_module(SCREEN, dict(screen_job(), project_basis=record()))["project_basis_applied"]
        self.assertEqual(sorted(applied), ["assumptions", "conflicts", "fields_used", "schema"])
        self.assertEqual(applied["assumptions"], [record()["assumptions"][0]])
        self.assertEqual(applied["conflicts"], [])
        for used in applied["fields_used"]:
            self.assertEqual(sorted(used), ["action", "basis", "input"])

    def test_the_effective_inputs_are_new_objects(self):
        job = dict(screen_job(), project_basis=record())
        before = copy.deepcopy(job)
        bf.run_module(SCREEN, job)
        self.assertEqual(job, before)

    def test_the_record_is_not_an_unknown_input_field(self):
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=record()))
        self.assertNotIn("project_basis", env["inputs"])


class WithoutARecordNothingChanges(unittest.TestCase):
    def test_no_applied_key_and_the_engine_output_is_the_registry_output(self):
        job = screen_job(P=500)
        env = bf.run_module(SCREEN, dict(job))
        self.assertNotIn("project_basis_applied", env)
        self.assertEqual(env["inputs"], job)
        want = bf.REGISTRY[SCREEN](dict(job))
        self.assertEqual(env["output"], bf._clean_zero(want["output"]))
        self.assertEqual(env["status"], want["status"])

    def test_a_null_record_is_no_record(self):
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=None))
        self.assertNotIn("project_basis_applied", env)


class UnitsCheck(unittest.TestCase):
    MOMENT_INPUTS = (("M", "in-lbf"), ("M_in_lbf", "in-lbf"), ("M_ft_lbf", "ft-lbf"))

    def test_si_system_exits_2(self):
        with self.assertRaisesRegex(ValueError, r"project_basis\.units\.system is SI: this skill's engine is USC"):
            bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=record(units={"system": "SI"})))

    def test_an_explicit_moment_unit_must_match_the_screen_input(self):
        for name, unit in self.MOMENT_INPUTS:
            job = {k: v for k, v in screen_job(P=500).items() if k != "M_in_lbf"}
            job[name] = 50000
            other = "ft-lbf" if unit == "in-lbf" else "in-lbf"
            ok = bf.run_module(SCREEN, dict(job, project_basis=record(units={"system": "USC", "moment": unit})))
            self.assertIn({"input": name, "basis": "units.moment", "action": "agreed"},
                          ok["project_basis_applied"]["fields_used"], name)
            with self.assertRaises(ValueError) as cm:
                bf.run_module(SCREEN, dict(job, project_basis=record(units={"system": "USC", "moment": other})))
            self.assertEqual(str(cm.exception), f"project_basis.units.moment conflicts with input {name}")

    def test_an_explicit_moment_unit_must_match_the_detailed_input(self):
        base = {k: v for k, v in app2_job().items() if k != "Mext_in_lbf"}
        for name, value, unit, other in (("Mext", 10000, "ft-lbf", "in-lbf"), ("Mext_in_lbf", 120000, "in-lbf", "ft-lbf")):
            job = dict(base, **{name: value})
            bf.run_module(APP2, dict(job, project_basis=record(units={"system": "USC", "moment": unit})))
            with self.assertRaisesRegex(ValueError, f"project_basis.units.moment conflicts with input {name}"):
                bf.run_module(APP2, dict(job, project_basis=record(units={"system": "USC", "moment": other})))

    def test_the_system_default_moment_unit_is_not_applied(self):
        # USC defaults to ft-lbf, but the screen is written in in-lbf: only an explicit unit is checked.
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=record()))
        self.assertNotIn("units.moment", [u["basis"] for u in env["project_basis_applied"]["fields_used"]])

    def test_a_moment_unit_the_skill_cannot_use_exits_2(self):
        for word in ("N-m", "kip-in", "kN-m"):
            with self.assertRaisesRegex(ValueError, "units.moment .* cannot be used"):
                bf.run_module(SCREEN, dict(screen_job(P=500),
                                           project_basis=record(units={"system": "USC", "moment": word})))

    def test_spelling_variants_of_a_unit_are_accepted(self):
        for word in ("ft-lb", "lb-ft", "FT-LBF"):
            job = {k: v for k, v in screen_job(P=500).items() if k != "M_in_lbf"}
            job["M_ft_lbf"] = 4000
            bf.run_module(SCREEN, dict(job, project_basis=record(units={"system": "USC", "moment": word})))


class RecordSources(WithTempFiles):
    def test_the_file_alone_is_used(self):
        path = self.write("pb.json", record())
        r = run_cli(SCREEN, "--input", json.dumps(screen_job()), "--project-basis", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["inputs"]["P"], 500)
        self.assertEqual(env["project_basis_applied"]["schema"], SCHEMA)

    def test_the_file_and_the_key_in_agreement_are_fine(self):
        path = self.write("pb.json", record())
        r = run_cli(SCREEN, "--input", json.dumps(dict(screen_job(), project_basis=record())), "--project-basis", path)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_file_and_the_key_in_disagreement_exit_2(self):
        path = self.write("pb.json", record())
        other = record(code={"standard": "B31.1", "edition": "2022"})
        r = run_cli(SCREEN, "--input", json.dumps(dict(screen_job(), project_basis=other)), "--project-basis", path)
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertEqual(r.stderr, "input error: project_basis conflicts with --project-basis file\n")

    def test_an_invalid_record_exits_2_with_the_path(self):
        bad = record(states=[{"key": "A", "role": "normal", "P_psig": 1}])
        r = run_cli(SCREEN, "--input", json.dumps(dict(screen_job(P=500), project_basis=bad)))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        self.assertIn("project_basis.states[0].role", r.stderr)
        r = run_cli(SCREEN, "--input", json.dumps(dict(screen_job(P=500), project_basis=dict(record(), bogus=1))))
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown key", r.stderr)

    def test_a_missing_file_exits_2(self):
        r = run_cli(SCREEN, "--input", json.dumps(screen_job(P=500)), "--project-basis", os.path.join(self._dir.name, "no.json"))
        self.assertEqual((r.returncode, r.stdout), (2, ""))

    def test_the_shipped_example_record_runs_both_modules(self):
        r = run_cli(SCREEN, "--input", json.dumps(screen_job(M_in_lbf=50000)), "--project-basis", EXAMPLE_RECORD)
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["inputs"]["P"], 150)
        self.assertEqual(env["project_basis_applied"]["assumptions"][0]["status"], "ASSUMED")
        job = {k: v for k, v in app2_job().items() if k != "P"}
        r = run_cli(APP2, "--input", json.dumps(job), "--project-basis", EXAMPLE_RECORD)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inputs"]["P"], 150)

    def test_list_mentions_the_record(self):
        r = run_cli("list")
        self.assertIn("project_basis", r.stdout)
        self.assertIn("--project-basis", r.stdout)


class SheetSectionOne(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rec = record()
        cls.env, cls.basis = bf.run_with_basis(SCREEN, dict(screen_job(), project_basis=rec))
        cls.sheet = bf.render_sheet(cls.env, cls.basis)

    def test_section_one_lists_the_assumed_items_first(self):
        i_head = self.sheet.index("## 1. Basis")
        i_assumed = self.sheet.index("**ASSUMED - confirm before issue:**")
        i_table = self.sheet.index("| Basis item")
        i_results = self.sheet.index("## Results")
        self.assertLess(i_head, i_assumed)
        self.assertLess(i_assumed, i_table)
        self.assertLess(i_table, i_results)
        self.assertIn("- Rating at design temperature not yet read; owner: lead", self.sheet)
        self.assertNotIn("Gasket factors confirmed", self.sheet.split("| Basis item")[0])

    def test_the_sheet_says_what_it_took_from_the_record(self):
        self.assertIn("Taken from the record: P <- " + FILL_PATH + " (filled)", self.sheet)

    def test_the_sheet_without_a_record_has_no_section_one(self):
        env = bf.run_module(SCREEN, screen_job(P=500))
        self.assertNotIn("## 1. Basis", bf.render_sheet(env))

    def test_cli_sheet_carries_section_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "pb.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(record(), fh)
            r = run_cli(SCREEN, "--input", json.dumps(screen_job()), "--project-basis", path, "--format", "sheet")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## 1. Basis", r.stdout)
        self.assertIn("**ASSUMED - confirm before issue:**", r.stdout)

    def test_a_record_with_no_assumed_items_says_so(self):
        rec = record(assumptions=[{"item": "x", "status": "confirmed"}])
        env, basis = bf.run_with_basis(SCREEN, dict(screen_job(), project_basis=rec))
        self.assertIn("No ASSUMED items in the project basis record.", bf.render_sheet(env, basis))


class OwnerAcceptance(unittest.TestCase):
    def _rec(self, item, document="PIP PNC00004"):
        return record(owner_practice=[{"document": document, "edition": "user to confirm", "items": [item]}],
                      assumptions=[])     # an ASSUMED item would grade every run manual check required

    def test_a_percent_becomes_a_calculated_check_that_can_fail(self):
        item = {"name": "flange acceptance", "value": 80, "unit": "%"}
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(item)))
        chk = [c for c in env["checks"] if c["name"].startswith("owner acceptance")][0]
        self.assertEqual((chk["result_status"], chk["status"]), ("calculated", "fail"))
        self.assertEqual(chk["name"], "owner acceptance (PIP PNC00004)")
        item["value"] = 95
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(item)))
        chk = [c for c in env["checks"] if c["name"].startswith("owner acceptance")][0]
        self.assertEqual(chk["status"], "pass")

    def test_a_fraction_without_a_unit_is_taken_as_a_fraction(self):
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec({"name": "Acceptance", "value": 0.9})))
        chk = [c for c in env["checks"] if c["name"].startswith("owner acceptance")][0]
        self.assertEqual(chk["status"], "pass")

    def test_the_screen_status_word_does_not_move(self):
        base = bf.run_module(SCREEN, screen_job(P=500))
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(
            {"name": "flange acceptance", "value": 10, "unit": "%"})))
        self.assertEqual(env["status"], base["status"])
        self.assertEqual(env["output"], base["output"])

    def test_a_text_value_is_a_pointer_and_the_check_does_not_run(self):
        item = {"name": "flange acceptance", "value": "from the owner document", "note": "not yet read"}
        env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(item)))
        chk = [c for c in env["checks"] if c["name"].startswith("owner acceptance")][0]
        self.assertEqual((chk["result_status"], chk["status"]), ("pointer only", "na"))
        self.assertIn("does not run", chk["note"])
        self.assertEqual(env["result_status"], "pointer only")

    def test_an_ambiguous_number_exits_2(self):
        for item in ({"name": "flange acceptance", "value": 80}, {"name": "flange acceptance", "value": 0},
                     {"name": "flange acceptance", "value": -5, "unit": "%"}):
            with self.assertRaisesRegex(ValueError, r"project_basis\.owner_practice\[0\]\.items\[0\]\.value .* cannot be used"):
                bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(item)))

    def test_other_owner_items_are_only_shown_on_the_sheet(self):
        for item in ("Run friction both ways", {"name": "nozzle load fraction", "value": 0.5}):
            env = bf.run_module(SCREEN, dict(screen_job(P=500), project_basis=self._rec(item)))
            self.assertFalse([c for c in env["checks"] if c["name"].startswith("owner acceptance")])

    def test_the_detailed_module_does_not_take_the_acceptance(self):
        item = {"name": "flange acceptance", "value": 10, "unit": "%"}
        env = bf.run_module(APP2, dict(app2_job(), project_basis=self._rec(item)))
        self.assertFalse([c for c in env["checks"] if c["name"].startswith("owner acceptance")])


class CodeRouteNotes(unittest.TestCase):
    def _checks(self, module, job, **rec):
        env = bf.run_module(module, dict(job, project_basis=record(**rec)))
        return {c["name"]: c for c in env["checks"]}

    def test_b313_is_the_304_5_1_b_route(self):
        chk = self._checks(SCREEN, screen_job())["code route"]
        self.assertEqual(chk["result_status"], "calculated")
        self.assertIn("304.5.1(b)", chk["note"])

    def test_b311_asks_for_the_viii_1_edition(self):
        chk = self._checks(SCREEN, screen_job(), code={"standard": "ASME B31.1", "edition": "2022"})["code route"]
        self.assertEqual(chk["result_status"], "not checked")
        self.assertIn("104.5.1", chk["note"])

    def test_another_standard_is_a_manual_check(self):
        for std in ("B31.9", "B31.12", "EN 13480"):
            chk = self._checks(APP2, app2_job(), code={"standard": std})["code route"]
            self.assertEqual(chk["result_status"], "manual check required", std)

    def test_high_pressure_service_is_a_manual_check(self):
        chk = self._checks(SCREEN, screen_job(), service={"fluid_category": "High Pressure"})
        self.assertEqual(chk["B31.3 Chapter IX"]["result_status"], "manual check required")
        chk = self._checks(SCREEN, screen_job(), code={"standard": "B31.3", "route": "Chapter IX"})
        self.assertEqual(chk["B31.3 Chapter IX"]["result_status"], "manual check required")

    def test_normal_service_has_no_chapter_ix_check(self):
        self.assertNotIn("B31.3 Chapter IX", self._checks(SCREEN, screen_job(), service={"fluid_category": "Normal"}))

    def test_the_b165_advisory_is_always_not_checked_and_carries_no_number_from_the_script(self):
        # rule 1: the 2.5.2 temperature threshold is not embedded; the design T only goes in the note
        for t in (300, 450, 800):
            states = [{"key": "DES", "role": "design", "T_F": t, "P_psig": 500}]
            env = bf.run_module(SCREEN, dict(screen_job(), project_basis=record(states=states)))
            self.assertNotIn("B16.5 2.5.2 advisory", [c["name"] for c in env["checks"]], t)
            item = [c for c in env["not_checked"] if c["name"] == "B16.5 2.5.2 advisory"]
            self.assertEqual(len(item), 1, t)
            self.assertIn(f"{t} F", item[0]["note"])
        env = bf.run_module(SCREEN, screen_job(P=500))
        item = [c for c in env["not_checked"] if c["name"] == "B16.5 2.5.2 advisory"]
        self.assertIn("no design temperature", item[0]["note"])

    def test_the_script_embeds_no_b165_threshold_constant(self):
        self.assertFalse([n for n in dir(bf) if n.startswith("B165_")])

    def test_a_design_temperature_never_lowers_the_envelope_word(self):
        base = bf.run_module(SCREEN, screen_job(P=500))["result_status"]
        states = [{"key": "DES", "role": "design", "T_F": 800, "P_psig": 500}]
        env = bf.run_module(SCREEN, dict(screen_job(), project_basis=record(states=states, assumptions=[])))
        self.assertEqual(env["result_status"], base)


class Python39Grammar(unittest.TestCase):
    def test_the_script_parses_as_python_3_9(self):
        with open(TOOL, encoding="utf-8") as fh:
            ast.parse(fh.read(), feature_version=(3, 9))

    def test_no_runtime_union_syntax_or_match_statements(self):
        with open(TOOL, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), feature_version=(3, 9))
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, getattr(ast, "Match", ()))])


class ParityStaysGreen(unittest.TestCase):
    def test_fixture_parity_for_the_ported_modules(self):
        for module in (APP2, SCREEN):
            self.assertEqual(parity.run_fixture(bf.REGISTRY, module), [], module)

    def test_a_record_changes_no_engine_output_key_or_value(self):
        for module, job in ((SCREEN, screen_job(P=500)), (APP2, app2_job())):
            plain = bf.run_module(module, dict(job))
            rec = bf.run_module(module, dict(job, project_basis=record()))
            self.assertEqual(rec["output"], plain["output"], module)
            self.assertEqual(rec["status"], plain["status"], module)
            self.assertEqual(rec["warnings"], plain["warnings"], module)


if __name__ == "__main__":
    unittest.main()
