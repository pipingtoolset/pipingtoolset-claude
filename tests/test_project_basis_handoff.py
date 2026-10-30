"""Cross-skill hand-off of one project basis record (plugin 0.8.0, B8 and B9).

One record, tests/fixtures/handoff/project-basis.json, is the load-case-builder Step 0 interview
of the shipped two-state example written down: B31.3-2022, two states (op operating, des design,
slots T1/P1/D1 and T2/P2/D2), USC, CAESAR II, a pipe and a support material, and one ASSUMED
item. Every one of the seven scripts runs on its own shipped example input with
`--project-basis <that file>`, the hand-off pattern of references/project-basis.md: the later
skill's input keeps only its own fields and leaves out what the record supplies.

What is pinned, per script:
- exit code as shipped, `project_basis_applied` present, `conflicts` empty, the record's ASSUMED
  item copied verbatim, and at least one input `filled` where the skill's fill map has a slot;
- no relabelling: each filled input carries the record's value, and the result is the same as
  the same value typed into the input without a record;
- `result_status` and every `checks[].result_status` are among the five words, and the calc
  sheet carries section 1 (ASSUMED items first) and a `Result status:` line under its title;
- the banner rule on the sheets this record holds (manual check required, or screening with an
  unresolved reconstructed factor): no PASS / OK wording.

The record is project data only: no code-table value is in it. Every number in the inputs is a
shipped example placeholder.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
RECORD = os.path.join(ROOT, "tests", "fixtures", "handoff", "project-basis.json")
sys.path.insert(0, os.path.join(ROOT, "tools", "shared"))

import project_basis as shared_pb  # noqa: E402

SCHEMA = "pipingtoolset.project-basis/1"
WORDS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
ASSUMED = {"item": "Corrosion allowance per the line list", "status": "ASSUMED",
           "note": "line list not yet issued", "owner": "lead"}
STATUS_LINE = re.compile(r"^Result status: (calculated|screening|manual check required|pointer only|not checked)"
                         r"( - .+)?$", re.M)


def script(skill: str, name: str) -> str:
    return os.path.join(SKILLS, skill, "scripts", name)


def example(skill: str, name: str) -> dict:
    with open(os.path.join(SKILLS, skill, "scripts", "examples", name), encoding="utf-8") as fh:
        return json.load(fh)


def record() -> dict:
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8", env=env)


def filled(applied: dict) -> dict:
    """{input: basis path} for every input the record filled."""
    return {u["input"]: u["basis"] for u in applied["fields_used"] if u["action"] == "filled"}


class Workdir:
    """One temp folder per test class: the derived inputs and the outputs of every run."""

    def __init__(self) -> None:
        self.path = tempfile.mkdtemp(prefix="pb-handoff-")

    def write(self, name: str, obj: dict) -> str:
        p = os.path.join(self.path, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=1)
        return p

    def read(self, name: str) -> str:
        with open(os.path.join(self.path, name), encoding="utf-8") as fh:
            return fh.read()

    def close(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class HandOffCase(unittest.TestCase):
    """Shared assertions on one run's result envelope."""

    def assert_consumed(self, applied: dict, expect_filled: dict) -> None:
        self.assertEqual(applied["schema"], SCHEMA)
        self.assertEqual(applied["conflicts"], [])
        self.assertEqual(applied["assumptions"], [ASSUMED])
        got = filled(applied)
        for name, path in expect_filled.items():
            self.assertEqual(got.get(name), path, f"{name} not filled from {path}: {applied['fields_used']}")

    def assert_words(self, env: dict, checks: list) -> None:
        self.assertIn(env["result_status"], WORDS)
        self.assertTrue(checks, "no checks[] in the envelope")
        for c in checks:
            self.assertIn(c["result_status"], WORDS, c)
        # the record's ASSUMED item: exactly one "ASSUMED inputs" row, manual check required, and the
        # envelope follows it (uniform in all seven skills)
        rows = [c for c in checks if c["name"] == "ASSUMED inputs"]
        self.assertEqual(len(rows), 1, [c["name"] for c in checks])
        self.assertEqual(rows[0]["result_status"], "manual check required")
        self.assertTrue(rows[0]["note"].startswith("confirm before issue: "), rows[0]["note"])
        self.assertIn(ASSUMED["item"], rows[0]["note"])
        self.assertEqual(env["result_status"], "manual check required")

    def assert_sheet(self, text: str, title_pattern: str, section_heading: str) -> None:
        """Title, then the Result status line within two lines, then section 1 with ASSUMED first."""
        lines = text.splitlines()
        title = [i for i, ln in enumerate(lines) if re.match(title_pattern, ln)]
        self.assertTrue(title, f"title {title_pattern!r} not found")
        status = [i for i, ln in enumerate(lines) if STATUS_LINE.match(ln)]
        self.assertTrue(status, "no Result status line")
        self.assertLessEqual(status[0] - title[0], 4, "Result status line is not under the title")
        start = text.find(section_heading) if section_heading else 0
        self.assertGreaterEqual(start, 0, f"section 1 {section_heading!r} not found")
        section = text[start:]
        assumed_at = section.find("**ASSUMED - confirm before issue:**")
        item_at = section.find(ASSUMED["item"])
        table_at = section.find("| Basis item (pipingtoolset.project-basis/1) | Value |")
        self.assertTrue(0 <= assumed_at < item_at < table_at, "ASSUMED items do not open section 1")


class TheRecord(unittest.TestCase):

    def test_it_is_a_valid_record_of_the_load_case_builder_interview(self):
        rec = record()
        self.assertEqual(shared_pb.validate_project_basis(rec), [])
        self.assertEqual(rec["schema"], SCHEMA)
        self.assertEqual((rec["code"]["standard"], rec["code"]["edition"]), ("B31.3", "2022"))
        self.assertEqual(rec["units"]["system"], "USC")
        self.assertEqual(rec["load_case_ids"]["software"], "CAESAR II")
        lcb = example("load-case-builder", "two-state-b313.json")
        self.assertEqual([(s["key"], s["name"], s["role"], s["slot"]["T"], s["slot"]["P"], s["slot"]["D"])
                          for s in rec["states"]],
                         [(s["key"], s["name"], s["role"], s["T"], s["P"], s["D"]) for s in lcb["thermal_states"]])
        self.assertEqual({m["use"] for m in rec["materials"]}, {"pipe", "support"})
        self.assertEqual([a for a in rec["assumptions"] if a.get("status", "ASSUMED") == "ASSUMED"], [ASSUMED])

    def test_it_carries_no_code_table_value(self):
        # Materials, citations and owner practice are text pointers; no S, E, W, Y, rating or allowable.
        rec = record()
        for m in rec["materials"]:
            self.assertFalse([v for v in m.values() if isinstance(v, (int, float))], m)
        for c in rec["citations"]:
            self.assertFalse([v for v in c.values() if isinstance(v, (int, float))], c)
        self.assertNotIn("code_values", rec)


class LoadCaseBuilder(HandOffCase):
    """The first skill: its spec drops code, edition, thermal_states and primary_state."""

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        spec = example("load-case-builder", "two-state-b313.json")
        typed = dict(copy.deepcopy(spec), primary_state="op")
        for k in ("code", "edition", "thermal_states", "primary_state"):
            spec.pop(k, None)
        gen = script("load-case-builder", "loadcase_gen.py")
        p = cls.wd.write("lcb.json", spec)
        cls.json = run(gen, "--spec", p, "--format", "json", "--project-basis", RECORD)
        cls.md = run(gen, "--spec", p, "--format", "md", "--project-basis", RECORD)
        cls.typed = run(gen, "--spec", cls.wd.write("lcb-typed.json", typed), "--format", "json")

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.json.returncode, 0, self.json.stderr)
        env = json.loads(self.json.stdout)
        self.assert_consumed(env["project_basis_applied"], {
            "code": "code.standard", "edition": "code.edition", "thermal_states": "states",
            "primary_state": "states[role=operating|first].key"})
        self.assert_words(env, env["checks"])

    def test_no_relabelling_the_case_set_equals_the_typed_spec(self):
        env, typed = json.loads(self.json.stdout), json.loads(self.typed.stdout)
        self.assertEqual((env["code"], env["edition"], env["primary_state"]), ("B31.3", "2022", "op"))
        self.assertEqual(env["cases"], typed["cases"])
        self.assertEqual(env["extraction_matrix"], typed["extraction_matrix"])
        descriptions = json.dumps(env["cases"])
        for s in record()["states"]:
            self.assertIn(s["name"], descriptions)

    def test_hanger_pair_is_w_plus_t_of_the_operating_state(self):
        env = json.loads(self.json.stdout)
        op = next(s for s in record()["states"] if s["role"] == "operating")
        hgr = [(c["Combination"], c["Hanger"]) for c in env["cases"] if c["Stress Type"] == "HGR"]
        self.assertEqual(hgr, [("W", "Rigid"), ("W+" + op["slot"]["T"], "Ignore")])

    def test_sheet_section_1_and_status_line(self):
        self.assertEqual(self.md.returncode, 0, self.md.stderr)
        self.assert_sheet(self.md.stdout, r"^## Load case set", "### 1 Basis")

    def test_banner_rule_while_manual_check_required(self):
        env = json.loads(self.json.stdout)
        self.assertEqual(env["result_status"], "manual check required")
        rows = [c for c in env["checks"] if c["name"] == "ASSUMED inputs"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["result_status"], "manual check required")
        self.assertIn(ASSUMED["item"], rows[0]["note"])
        # QC finding prefixes are check results, not banners: OK: lines keep their word.
        self.assertIsNotNone(re.search(r"^- OK:", self.md.stdout, re.M))
        self.assertIsNone(re.search(r"^- MANUAL CHECK REQUIRED:", self.md.stdout, re.M))


class PressureDesign(HandOffCase):
    """P and edition come from the record; W_basis stays the job file's (the pipe is welded)."""

    MODULE = "piping.b313-wall-thickness"

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        job = example("pressure-design", "b313-wall-thickness.json")
        cls.raw = run(script("pressure-design", "pressure_design.py"), cls.MODULE,
                      "--input-file", cls.wd.write("pd-raw.json", job), "--project-basis", RECORD)
        typed = dict(copy.deepcopy(job), P=300)
        for k in ("P", "edition"):
            job.pop(k)
        cls.res = run(script("pressure-design", "pressure_design.py"), cls.MODULE,
                      "--input-file", cls.wd.write("pd.json", job), "--project-basis", RECORD)
        cls.typed = run(script("pressure-design", "pressure_design.py"), cls.MODULE,
                        "--input-file", cls.wd.write("pd-typed.json", typed))

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        env = json.loads(self.res.stdout)
        self.assert_consumed(env["project_basis_applied"],
                             {"P": "states[role=design|first].P_psig", "edition": "code.edition"})
        self.assert_words(env, env["checks"])

    def test_no_relabelling_the_output_equals_the_typed_job(self):
        env, typed = json.loads(self.res.stdout), json.loads(self.typed.stdout)
        self.assertEqual(env["inputs"]["P"], 300)
        self.assertEqual(env["inputs"]["edition"], "2022")
        self.assertEqual(env["inputs"]["W_basis"], "longitudinal weld, confirmed")
        self.assertEqual(env["output"], typed["output"])
        self.assertEqual(env["status"], typed["status"])

    def test_sheet_section_1_and_status_line(self):
        env = json.loads(self.res.stdout)
        self.assertRegex(env["result_status_line"], STATUS_LINE)
        self.assert_sheet("# Pressure design\n" + env["result_status_line"] + "\n\n" + env["basis_section"],
                          r"^# Pressure design", "**ASSUMED - confirm before issue:**")
        # the record's ASSUMED item is the one "ASSUMED inputs" row, and the status line names it
        self.assertTrue(env["result_status_line"].startswith("Result status: manual check required - "))
        self.assertIn("confirm before issue: " + ASSUMED["item"], env["result_status_line"])

    def test_the_unstripped_example_conflicts_which_proves_the_record_is_read(self):
        self.assertEqual(self.raw.returncode, 2)
        self.assertIn("project_basis.states[role=design|first].P_psig conflicts with input P", self.raw.stderr)


class StressScreening(HandOffCase):
    """equation and N (fatigue), code and edition (flexibility exemption) come from the record."""

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        job = example("stress-screening", "sa-and-exemption.json")
        typed = cls.wd.write("ss-typed.json", job)
        job["piping.fatigue-factor"].pop("equation")
        job["piping.fatigue-factor"].pop("N")
        for k in ("code", "edition"):
            job["screen.flexibility-exemption"].pop(k)
        p = cls.wd.write("ss.json", job)
        cli = script("stress-screening", "stress_screening.py")
        cls.res, cls.typed = {}, {}
        for m in ("piping.fatigue-factor", "piping.displacement-stress", "screen.flexibility-exemption"):
            cls.res[m] = run(cli, m, "--input-file", p, "--project-basis", RECORD)
            cls.typed[m] = run(cli, m, "--input-file", typed)
        cls.basis = run(cli, "basis", "--project-basis", RECORD)

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        expect = {"piping.fatigue-factor": {"equation": "code.edition", "N": "states[0].cycles"},
                  "piping.displacement-stress": {},
                  "screen.flexibility-exemption": {"code": "code.standard", "edition": "code.edition"}}
        for m, want in expect.items():
            r = self.res[m]
            self.assertEqual(r.returncode, 0, (m, r.stderr))
            env = json.loads(r.stdout)
            self.assert_consumed(env["project_basis_applied"], want)
            self.assertTrue(env["project_basis_applied"]["fields_used"], m)
            self.assert_words(env, env["checks"])
        self.assertEqual(self.basis.returncode, 0, self.basis.stderr)
        self.assertIn(json.loads(self.basis.stdout)["result_status"], WORDS)

    def test_no_relabelling_the_outputs_equal_the_typed_job(self):
        fat = json.loads(self.res["piping.fatigue-factor"].stdout)
        self.assertEqual((fat["inputs"]["equation"], fat["inputs"]["N"]), ("b313-2022", 20000))
        for m in self.res:
            env, typed = json.loads(self.res[m].stdout), json.loads(self.typed[m].stdout)
            self.assertEqual(env["output"], typed["output"], m)
            self.assertEqual(env["status"], typed["status"], m)

    def test_sheet_section_1_and_status_line(self):
        env = json.loads(self.res["piping.fatigue-factor"].stdout)
        self.assert_sheet("# Stress screening\n" + env["result_status_line"] + "\n\n" + env["basis_section"],
                          r"^# Stress screening", "## 1. Basis")


class NozzleLoad(HandOffCase):
    """designTempF from the design state and the ownerFactorBasis label from owner_practice."""

    MODULE = "equipment.pvp2011-allowables"

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        job = example("nozzle-load", "vessel-nozzle-pvp2011.json")
        typed = dict(copy.deepcopy(job), ownerFactorBasis="Owner piping stress practice user to confirm")
        for k in ("designTempF", "ownerFactorBasis"):
            job.pop(k)
        cli = script("nozzle-load", "nozzle_load.py")
        cls.res = run(cli, cls.MODULE, "--input-file", cls.wd.write("nl.json", job), "--project-basis", RECORD)
        cls.typed = run(cli, cls.MODULE, "--input-file", cls.wd.write("nl-typed.json", typed))

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        env = json.loads(self.res.stdout)
        self.assert_consumed(env["project_basis_applied"], {
            "designTempF": "states[role=design|first].T_F", "ownerFactorBasis": "owner_practice"})
        self.assert_words(env, env["checks"])

    def test_no_relabelling_the_output_equals_the_typed_job(self):
        env, typed = json.loads(self.res.stdout), json.loads(self.typed.stdout)
        self.assertEqual(env["inputs"]["designTempF"], 400)
        self.assertEqual(env["inputs"]["ownerFactorBasis"], "Owner piping stress practice user to confirm")
        self.assertEqual(env["inputs"]["ownerFactor"], 0.5)     # never taken from the record
        self.assertEqual(env["output"], typed["output"])
        self.assertEqual(env["status"], typed["status"])

    def test_sheet_section_1_and_status_line(self):
        env = json.loads(self.res.stdout)
        self.assert_sheet("# Nozzle load\n" + env["result_status_line"] + "\n\n" + env["project_basis_section"],
                          r"^# Nozzle load", "## 1. Basis")


class BoltedFlange(HandOffCase):
    """P from the design state; the reconstructed hub factors hold the banner."""

    MODULE = "aux.app2-flange-integral"

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        job = example("bolted-flange", "integral-weld-neck.json")
        typed = cls.wd.write("bf-typed.json", job)
        job.pop("P")
        p = cls.wd.write("bf.json", job)
        cli = script("bolted-flange", "bolted_flange.py")
        cls.res = run(cli, cls.MODULE, "--input-file", p, "--project-basis", RECORD)
        cls.sheet = run(cli, cls.MODULE, "--input-file", p, "--project-basis", RECORD, "--format", "sheet")
        cls.typed = run(cli, cls.MODULE, "--input-file", typed)

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        env = json.loads(self.res.stdout)
        self.assert_consumed(env["project_basis_applied"], {"P": "states[role=design|first].P_psig"})
        self.assert_words(env, env["checks"] + env.get("not_checked", []))

    def test_no_relabelling_the_output_equals_the_typed_job(self):
        env, typed = json.loads(self.res.stdout), json.loads(self.typed.stdout)
        self.assertEqual(env["inputs"]["P"], 300)
        self.assertEqual(env["output"], typed["output"])
        self.assertEqual(env["status"], typed["status"])

    def test_sheet_section_1_and_status_line(self):
        self.assertEqual(self.sheet.returncode, 0, self.sheet.stderr)
        self.assert_sheet(self.sheet.stdout, r"^# Bolted Flange Evaluation", "## 1. Basis")

    def test_banner_rule_with_an_unresolved_reconstructed_factor(self):
        env = json.loads(self.res.stdout)
        self.assertEqual(env["result_status"], "manual check required")      # the ASSUMED item outranks it
        self.assertTrue(any(c.get("unresolved_factor") for c in env["checks"]))
        self.assertIsNone(re.search(r"\bPASS\b|\bOK\b|\bDELIVERABLE\b", self.sheet.stdout))


class PipeSupport(HandOffCase):
    """Title block, load units and axes come from the record; ASSUMED joins `assumed`."""

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        spec = example("pipe-support", "ps-201-caesar.json")
        cls.typed_spec = copy.deepcopy(spec)
        spec.pop("project")
        for pipe in spec["pipes"]:
            for k in ("units", "vertical_axis", "pipe_axis"):
                pipe["loads"].pop(k)
        cli = script("pipe-support", "support_calc.py")
        cls.res = run(cli, cls.wd.write("ps.json", spec), "--report", os.path.join(cls.wd.path, "ps.md"),
                      "--json", os.path.join(cls.wd.path, "ps-out.json"), "--project-basis", RECORD)
        cls.typed = run(cli, cls.wd.write("ps-typed.json", cls.typed_spec),
                        "--json", os.path.join(cls.wd.path, "ps-typed-out.json"))
        cls.out = json.loads(cls.wd.read("ps-out.json"))
        cls.typed_out = json.loads(cls.wd.read("ps-typed-out.json"))
        cls.report = cls.wd.read("ps.md")

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.res.returncode, self.typed.returncode, self.res.stderr)
        want = {"project": "project.name", "calcBy": "project.calcBy", "date": "project.date"}
        for n in range(len(self.typed_spec["pipes"])):
            want.update({f"pipes.{n}.loads.units": "units",
                         f"pipes.{n}.loads.vertical_axis": "equipment_axes.global_vertical",
                         f"pipes.{n}.loads.pipe_axis": "equipment_axes.pipe_axis"})
        self.assert_consumed(self.out["project_basis_applied"], want)
        self.assertIn(self.out["result_status"], WORDS)
        self.assert_words(self.out["envelope"], self.out["envelope"]["checks"])

    def test_no_relabelling_the_envelope_equals_the_typed_spec(self):
        for k in ("governingRatio", "governingStage", "governingCheck", "governingCombo", "combosRun", "status"):
            self.assertEqual(self.out["envelope"][k], self.typed_out["envelope"][k], k)
        self.assertEqual(self.out["result_status"], self.typed_out["result_status"])
        self.assertIn("| Project | Hand-off example unit |", self.report)
        self.assertIn("ASSUMED (project basis): " + ASSUMED["item"], " ".join(self.out["assumed"]))

    def test_sheet_section_1_and_status_line(self):
        self.assert_sheet(self.report, r"^# Pipe Support Calculation", "## Basis - project basis record")


class IsoToPcf(HandOffCase):
    """axes and pipeline.reference come from the record; the PCF equals the typed spec's."""

    @classmethod
    def setUpClass(cls):
        cls.wd = Workdir()
        spec = example("iso-to-pcf", "project-basis-line.json")
        typed = dict(copy.deepcopy(spec), axes="Y-up", pipeline={"reference": record()["project"]["line"]})
        cli = script("iso-to-pcf", "build_pcf.py")
        cls.res = run(cli, cls.wd.write("iso.json", spec), "-o", os.path.join(cls.wd.path, "iso.pcf"),
                      "--report", os.path.join(cls.wd.path, "iso.txt"), "--json", "--project-basis", RECORD)
        cls.typed = run(cli, cls.wd.write("iso-typed.json", typed), "-o", os.path.join(cls.wd.path, "typed.pcf"),
                        "--json")
        cls.env = json.loads(cls.res.stdout[cls.res.stdout.find("{"):])
        cls.report = cls.wd.read("iso.txt")

    @classmethod
    def tearDownClass(cls):
        cls.wd.close()

    def test_consumed_without_conflict(self):
        self.assertEqual(self.res.returncode, 0, self.res.stderr)
        self.assert_consumed(self.env["project_basis_applied"],
                             {"axes": "equipment_axes.global_vertical", "pipeline.reference": "project.line"})
        self.assert_words(self.env, self.env["checks"])

    def test_no_relabelling_the_pcf_equals_the_typed_spec(self):
        self.assertEqual(self.typed.returncode, 0, self.typed.stderr)
        self.assertEqual((self.env["axes"], self.env["pipeline"]), ("Y-up", "6-P-1201"))
        self.assertEqual(self.wd.read("iso.pcf"), self.wd.read("typed.pcf"))

    def test_sheet_section_1_and_status_line(self):
        self.assert_sheet(self.report, r"^PCF build report - 6-P-1201", "1. Basis")


class EveryScriptOnTheSameRecord(unittest.TestCase):
    """The seven scripts read one file and none of them rejects or rewrites it."""

    def test_the_record_file_is_unchanged_by_the_runs(self):
        before = record()
        wd = Workdir()
        try:
            job = example("bolted-flange", "integral-weld-neck.json")
            job.pop("P")
            r = run(script("bolted-flange", "bolted_flange.py"), "aux.app2-flange-integral",
                    "--input-file", wd.write("bf.json", job), "--project-basis", RECORD)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            wd.close()
        self.assertEqual(record(), before)

    def test_each_skill_ships_the_shared_reference_and_example(self):
        with open(os.path.join(ROOT, "tools", "shared", "project-basis.md"), encoding="utf-8") as fh:
            doc = fh.read()
        skills = ("load-case-builder", "pressure-design", "stress-screening", "pipe-support", "iso-to-pcf",
                  "nozzle-load", "bolted-flange")
        for s in skills:
            with open(os.path.join(SKILLS, s, "references", "project-basis.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), doc, s)
            self.assertTrue(os.path.isfile(os.path.join(SKILLS, s, "scripts", "examples",
                                                        "project-basis.example.json")), s)


if __name__ == "__main__":
    unittest.main()
