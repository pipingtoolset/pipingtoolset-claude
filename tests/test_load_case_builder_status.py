"""load-case-builder: the output status taxonomy (plugin 0.8.0, B9).

The generator's envelope carries result_status and checks[]; six QC items are evaluated, the
eleven that need the model are listed as "not checked" (they never set the envelope word), every
ASSUMED item goes into one "ASSUMED inputs" row, and QC findings keep their OK prefix (they are
check results, not a banner). Standard library only.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "load-case-builder", "scripts")
TOOL = os.path.join(SCRIPTS, "loadcase_gen.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "load-case-builder")
sys.path.insert(0, SCRIPTS)

import loadcase_gen as g  # noqa: E402

FIVE = ("calculated", "screening", "manual check required", "pointer only", "not checked")
MODEL_ITEMS = {1, 2, 3, 6, 8, 9, 12, 13, 14, 15, 16}


def fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


def declared() -> dict:
    """Three states, vertical seismic present, every generator input declared, no scale."""
    return dict(fixture("three-state-unscaled.json"), primary_state="max", hanger_friction=0.0)


def build(spec: dict) -> g.LoadCaseSet:
    return g.LoadCaseSet(copy.deepcopy(spec)).build()


def check(s: g.LoadCaseSet, name: str) -> dict:
    return next(c for c in s.checks if c["name"] == name)


def variants() -> dict:
    """Specs that between them reach every word this generator can emit."""
    b311 = dict(declared(), code="B31.1", edition="2024")
    scaled_b311_2024 = copy.deepcopy(b311)
    scaled_b311_2024["occasionals"][0]["scale"] = 0.7
    no_occ = dict(declared(), occasionals=[])
    unstated = copy.deepcopy(declared())
    del unstated["edition"]
    return {"example": g.EXAMPLE_SPEC, "declared": declared(), "unscaled": fixture("three-state-unscaled.json"),
            "scaled": fixture("three-state-scaled.json"), "b311": b311, "b311-2024-scaled": scaled_b311_2024,
            "no-occasionals": no_occ, "unstated-edition": unstated}


class Vocabulary(unittest.TestCase):

    def test_the_five_words(self):
        self.assertEqual(g.RESULT_STATUS, FIVE)

    def test_every_variant_emits_only_the_five_words_and_the_worst(self):
        for name, spec in variants().items():
            with self.subTest(name):
                s = build(spec)
                self.assertIn(s.result_status, FIVE)
                self.assertEqual(s.result_status, g.envelope_status(s.checks))
                for c in s.checks:
                    self.assertEqual(sorted(c), ["name", "note", "result_status", "status"])
                    self.assertIn(c["result_status"], FIVE)
                    self.assertIn(c["status"], ("pass", "fail", "na"))

    def test_screening_and_pointer_only_are_not_reachable(self):
        # No screening method and no code-table input (code_values is refused).
        for name, spec in variants().items():
            with self.subTest(name):
                words = {c["result_status"] for c in build(spec).checks}
                self.assertFalse(words & {"screening", "pointer only"}, words)


class Calculated(unittest.TestCase):

    def test_every_automated_item_is_calculated_when_everything_is_declared(self):
        s = build(declared())
        auto = [c for c in s.checks if c["result_status"] != "not checked"]
        self.assertEqual([c["name"] for c in auto],
                         ["code edition", "QC 4 vertical seismic and U2",
                          "QC 5 expansion completeness", "QC 7 forward references", "QC 10 occasional factor",
                          "QC 11 ASD position", "QC 17 resolved case set"])
        self.assertTrue(all(c["result_status"] == "calculated" for c in auto))
        self.assertEqual({c["status"] for c in auto}, {"pass", "na"})

    def test_a_definite_defect_is_calculated_and_fails(self):
        s = build(variants()["b311-2024-scaled"])
        self.assertEqual((check(s, "QC 11 ASD position")["result_status"], check(s, "QC 11 ASD position")["status"]),
                         ("calculated", "fail"))
        ex = build(g.EXAMPLE_SPEC)
        self.assertEqual(check(ex, "QC 4 vertical seismic and U2")["status"], "fail")
        self.assertIn("fails: QC 4 vertical seismic and U2", ex.status_line())

    def test_a_resolved_case_set_miss_fails_item_17(self):
        class Gap(g.LoadCaseSet):
            def _max_ope_members(self):
                return super()._max_ope_members()[:1]
        s = Gap(declared()).build()
        self.assertEqual(check(s, "QC 17 resolved case set")["status"], "fail")
        self.assertEqual(check(s, "QC 17 resolved case set")["result_status"], "calculated")

    def test_no_occasionals_makes_items_10_and_11_not_applicable(self):
        s = build(variants()["no-occasionals"])
        for name in ("QC 10 occasional factor", "QC 11 ASD position", "QC 4 vertical seismic and U2"):
            self.assertEqual((check(s, name)["result_status"], check(s, name)["status"]), ("calculated", "na"))


class NotChecked(unittest.TestCase):

    def test_the_eleven_model_items_are_listed(self):
        s = build(declared())
        items = {int(c["name"].split()[1]) for c in s.checks
                 if c["result_status"] == "not checked" and c["name"].startswith("QC ")}
        self.assertEqual(items, MODEL_ITEMS)

    def test_hydrotest_friction_item_only_with_a_hydrotest_and_two_frictions(self):
        name = "HYD friction multiplier in the software"
        self.assertIn(name, [c["name"] for c in build(declared()).checks])
        self.assertNotIn(name, [c["name"] for c in build(dict(declared(), hydrotest=False)).checks])

    def test_a_clean_declared_set_is_calculated_and_still_lists_the_model_items(self):
        s = build(declared())
        self.assertEqual(s.result_status, "calculated")
        self.assertTrue(g.checks_banner_allowed(s.checks))
        self.assertNotIn("ASSUMED inputs", [c["name"] for c in s.checks])
        self.assertIn("OK: Maximum Occasional envelope covers every occasional kind present.", s.findings)
        self.assertEqual(s.status_line(),
                         "Result status: calculated - QC items 4, 5, 7, 10, 11 and 17 calculated; "
                         "not performed by this module: 12 items that need the model")


class ManualCheckRequired(unittest.TestCase):

    CASES = {
        "unscaled": "ASSUMED inputs",                 # primary_state and hanger_friction defaulted
        "unstated-edition": "code edition",
        "b311": "QC 10 occasional factor",            # k = 1.15 / 1.20 needs the duration
        "scaled": "QC 11 ASD position",               # B31.3 reduction needs a written direction
    }

    def test_each_trigger(self):
        v = variants()
        for name, trigger in self.CASES.items():
            with self.subTest(name):
                s = build(v[name])
                self.assertEqual(s.result_status, "manual check required")
                self.assertEqual(check(s, trigger)["result_status"], "manual check required")
                self.assertIn(trigger, s.status_line())

    def test_an_assumed_item_in_the_record_is_a_manual_check(self):
        rec = {"schema": "pipingtoolset.project-basis/1",
               "assumptions": [{"item": "Seismic design category per the structural basis", "status": "ASSUMED"}]}
        s = build(dict(declared(), project_basis=rec))
        self.assertEqual(check(s, "ASSUMED inputs"), {
            "name": "ASSUMED inputs", "result_status": "manual check required", "status": "na",
            "note": "confirm before issue: Seismic design category per the structural basis"})
        self.assertEqual(s.result_status, "manual check required")
        rec["assumptions"][0]["status"] = "confirmed"
        s = build(dict(declared(), project_basis=rec))
        self.assertEqual(s.result_status, "calculated")
        self.assertNotIn("ASSUMED inputs", [c["name"] for c in s.checks])

    def test_generator_and_record_assumptions_share_one_row(self):
        rec = {"schema": "pipingtoolset.project-basis/1",
               "assumptions": [{"item": "Seismic design category per the structural basis"}]}
        s = build(dict(fixture("three-state-unscaled.json"), project_basis=rec))
        rows = [c for c in s.checks if c["name"] == "ASSUMED inputs"]
        self.assertEqual(len(rows), 1)
        note = rows[0]["note"]
        self.assertTrue(note.startswith("confirm before issue: primary state = "), note)
        self.assertIn("; hanger design pair (W Rigid, W+", note)
        self.assertTrue(note.endswith("; Seismic design category per the structural basis"), note)

    def test_chapter_ix_service_in_the_record_names_1_20(self):
        rec = {"schema": "pipingtoolset.project-basis/1", "service": {"fluid_category": "High Pressure"}}
        self.assertIn("K302.3.6(a) 1.20", check(build(dict(declared(), project_basis=rec)),
                                                "QC 10 occasional factor")["note"])


class BannerRule(unittest.TestCase):

    def test_qc_findings_keep_their_ok_prefix_under_every_word(self):
        # A QC finding prefix is a check result, not a banner: it is never rewritten.
        for name, spec in variants().items():
            with self.subTest(name):
                s = build(spec)
                report = g.render_report(s)
                self.assertFalse([x for x in s.findings if x.startswith("MANUAL CHECK REQUIRED: ")])
                self.assertNotIn("- MANUAL CHECK REQUIRED: ", report)
                if spec.get("occasionals"):
                    self.assertIn("OK: Maximum Occasional envelope covers every occasional kind present.",
                                  s.findings)

    def test_ok_line_under_manual_check_required(self):
        s = build(fixture("three-state-unscaled.json"))
        self.assertEqual(s.result_status, "manual check required")
        self.assertIn("OK: Maximum Occasional envelope covers every occasional kind present.", s.findings)

    def test_status_line_is_under_the_title(self):
        for name, spec in variants().items():
            with self.subTest(name):
                s = build(spec)
                lines = g.render_report(s).splitlines()
                self.assertTrue(lines[0].startswith("## Load case set - "))
                self.assertTrue(lines[1].startswith(f"Result status: {s.result_status} - "), lines[1])


class Envelope(unittest.TestCase):

    def test_cli_json_carries_result_status_and_checks(self):
        r = subprocess.run([sys.executable, TOOL, "--example", "--format", "json"], capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["result_status"], "manual check required")
        self.assertEqual(d["result_status"], g.envelope_status(d["checks"]))
        self.assertEqual(d["total_cases"], 88)              # existing keys and values unchanged
        self.assertTrue(d["qc"]["pass"])

    def test_cli_markdown_is_utf8_with_the_status_line(self):
        r = subprocess.run([sys.executable, TOOL, "--example"], capture_output=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Result status: manual check required - ".encode("utf-8"), r.stdout)

    def test_csv_carries_no_status_line(self):
        r = subprocess.run([sys.executable, TOOL, "--example", "--format", "csv"], capture_output=True,
                           text=True, encoding="utf-8")
        self.assertEqual(len(r.stdout.strip().splitlines()), 89)
        self.assertTrue(r.stdout.startswith("L,Combination,"))


if __name__ == "__main__":
    unittest.main()
