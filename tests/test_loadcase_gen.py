"""Regression tests for the load-case-builder generator.

Standard library only (unittest), so the gate runs anywhere Python 3.9+ runs:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "load-case-builder")
SCRIPTS = os.path.join(SKILL, "scripts")
GOLDEN = os.path.join(ROOT, "tests", "golden", "two-state-b313.md")
GOLDEN_SCALED = os.path.join(ROOT, "tests", "golden", "three-state-scaled-b313.md")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "load-case-builder")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import content_guard  # noqa: E402
import loadcase_gen as g  # noqa: E402


def build(spec: dict) -> g.LoadCaseSet:
    return g.LoadCaseSet(copy.deepcopy(spec)).build()


def expected_count(spec: dict) -> int:
    """Case count derived from the block structure, independent of the generator."""
    s = len(spec["thermal_states"])
    f = len(spec.get("frictions", [[0, 1.0], [0, 0.0]]))
    occ = spec.get("occasionals", [])
    o = len(occ)
    u = sum(1 for x in occ if x.get("scale"))  # scaled occasionals get unreduced companions
    kinds = {x.get("kind", "other") for x in occ}
    hangers = 2 if spec.get("hangers", True) else 0
    hyd = 1 if spec.get("hydrotest", True) else 0
    ranges = s * (s - 1) // 2 if spec.get("inter_state_expansion_ranges", True) and s > 1 else 0
    envelopes = 1 + len(kinds) + (1 if kinds else 0)  # max:ope, one per kind, max:occ
    # HGR + HYD/friction + OPE + OPE+OCC + OPE+OCC-UNRED + SUS + EXP + ranges/friction
    # + pure + code-occ + envelopes
    return (hangers + hyd * f + s * f + o * f + u * f + s * f + s * f + ranges * f + o * f + o * f
            + envelopes)


class GoldenOutput(unittest.TestCase):
    """The example's full report is locked. Any change to case order, combination
    strings or QC text must be a deliberate golden update, reviewed by the P.E."""

    def test_example_matches_golden(self):
        with open(GOLDEN, encoding="utf-8") as fh:
            golden = fh.read()
        self.assertEqual(g.render_report(build(g.EXAMPLE_SPEC)), golden)

    def test_example_json_file_matches_builtin(self):
        path = os.path.join(SCRIPTS, "examples", "two-state-b313.json")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), g.EXAMPLE_SPEC)


class Structure(unittest.TestCase):

    def test_case_count_follows_block_structure(self):
        self.assertEqual(len(build(g.EXAMPLE_SPEC).cases), expected_count(g.EXAMPLE_SPEC))
        self.assertEqual(len(build(g.EXAMPLE_SPEC).cases), 88)  # 0.7.0 had 87: HYD per friction

    def test_every_reference_points_backward(self):
        s = build(g.EXAMPLE_SPEC)
        index = {c.key: c.number for c in s.cases}
        for c in s.cases:
            for _, ref in c.refs:
                self.assertLess(index[ref], c.number, f"L{c.number} -> {ref}")

    def test_block_order(self):
        order = ["HGR", "HYD", "OPE", "OPE+OCC", "SUS", "EXP", "OCC-PURE", "OCC-CODE", "MAX"]
        blocks = [c.block for c in build(g.EXAMPLE_SPEC).cases]
        seen = [b for i, b in enumerate(blocks) if i == 0 or blocks[i - 1] != b]
        self.assertEqual(seen, order)

    def test_combination_methods(self):
        for c in build(g.EXAMPLE_SPEC).cases:
            if c.block in ("EXP", "OCC-PURE"):
                self.assertEqual(c.method, "Algebraic", c.desc)
            if c.block == "OCC-CODE":
                self.assertEqual(c.method, "Scalar", c.desc)
            if c.block == "OCC-PURE":
                self.assertTrue(c.suppress, c.desc)
            if c.block == "MAX":
                self.assertEqual(c.method, "Max", c.desc)

    def test_hanger_design_cases_follow_caesar_recommended_set(self):
        """W (Rigid) sizes the load, W+T1 (Ignore) sizes the travel; H is their output,
        so it must not appear until the As-Designed cases."""
        s = build(g.EXAMPLE_SPEC)
        rigid, travel = s.cases[0], s.cases[1]
        self.assertEqual((rigid.terms, rigid.hanger), (["W"], "Rigid"))
        self.assertEqual((travel.terms, travel.hanger), (["W", "T1"], "Ignore"))
        self.assertEqual(s.combo_string(travel), "W+T1")
        first_h = next(c for c in s.cases if "H" in c.terms)
        self.assertNotEqual(first_h.block, "HGR")
        for c in s.cases:
            if c.block in ("OPE", "OPE+OCC", "SUS"):
                self.assertIn("H", c.terms, c.desc)
                self.assertEqual(c.hanger, "As Designed", c.desc)

    def test_sustained_drops_thermal_and_displacement(self):
        for c in build(g.EXAMPLE_SPEC).cases:
            if c.block == "SUS":
                self.assertFalse(any(t.startswith(("T", "D")) for t in c.terms), c.terms)
                self.assertIn("H", c.terms)

    def test_inserting_a_state_keeps_references_semantic(self):
        """The whole point: add a state at the front and every combination still
        points at the case its key names."""
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["thermal_states"].insert(1, {"key": "upset", "name": "UPSET CONDITION",
                                          "T": "T3", "P": "P3"})
        spec["inter_state_expansion_ranges"] = True
        s = build(spec)
        self.assertEqual(len(s.cases), expected_count(spec))
        by_num = {c.number: c for c in s.cases}
        index = {c.key: c for c in s.cases}
        for c in s.cases:
            if c.block == "EXP" and c.key.startswith("exp:"):
                _, state, fric = c.key.split(":")
                plus, minus = [index[r] for _, r in c.refs]
                self.assertEqual(plus.key, f"ope:{state}:{fric}")
                self.assertEqual(minus.key, f"sus:{state}:{fric}")
                # and the rendered string names those same numbers
                self.assertEqual(s.combo_string(c), f"L{plus.number}-L{minus.number}")
                self.assertIs(by_num[plus.number], plus)

    def test_max_operating_covers_every_friction_variant(self):
        """Found by the E6 end-to-end run: the envelope used to hold only the
        with-friction cases, so a frictionless-governed reaction never reached it."""
        s = build(g.EXAMPLE_SPEC)
        env = next(c for c in s.cases if c.key == "max:ope")
        refs = {r for _, r in env.refs}
        for _, fv in g.EXAMPLE_SPEC["frictions"]:
            self.assertIn(f"ope:op:{fv}", refs)
            for o in g.EXAMPLE_SPEC["occasionals"]:
                if o["base"] == "op":
                    self.assertIn(f"opeocc:{o['key']}:{fv}", refs)
        matrix = s.report_matrix()
        idx = {c.key: c.number for c in s.cases}
        self.assertIn(f"| Flange / nozzle loads - Operating | {idx['ope:op:1.0']}, {idx['ope:op:0.0']}, "
                      f"{idx['ope:des:1.0']}, {idx['ope:des:0.0']} |", matrix)

    def test_envelope_covers_every_kind(self):
        s = build(g.EXAMPLE_SPEC)
        env = next(c for c in s.cases if c.key == "max:occ")
        self.assertEqual({r.split(":")[1] for _, r in env.refs},
                         {o["kind"] for o in g.EXAMPLE_SPEC["occasionals"]})


class QCFindings(unittest.TestCase):

    def _findings(self, spec: dict) -> str:
        return "\n".join(build(spec).findings)

    def test_example_flags_missing_vertical_seismic_and_u2_conflict(self):
        f = self._findings(g.EXAMPLE_SPEC)
        self.assertIn("GAP: no vertical seismic", f)
        self.assertIn("CONFLICT: U2 carries snow", f)

    def test_vertical_seismic_clears_gap(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["occasionals"] = [o for o in spec["occasionals"] if o["kind"] != "snow"]
        spec["occasionals"].append({"key": "seis_v", "name": "Seismic -Y", "vector": "U2",
                                    "sign": "-", "kind": "seismic"})
        f = self._findings(spec)
        self.assertNotIn("GAP: no vertical seismic", f)
        self.assertNotIn("CONFLICT", f)

    def test_unstated_edition_is_a_finding(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        del spec["edition"]
        self.assertIn("BASIS: code edition not stated", self._findings(spec))

    def _b311_scaled(self, edition: str) -> str:
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["code"], spec["edition"] = "B31.1", edition
        for o in spec["occasionals"]:
            if o["kind"] == "wind":
                o["scale"] = 0.6
        return self._findings(spec)

    def test_b311_2024_asd_reduction_is_an_error(self):
        self.assertIn("ERROR: B31.1-2024", self._b311_scaled("2024"))

    def test_b311_pre_2024_asd_reduction_is_a_check_not_an_error(self):
        f = self._b311_scaled("2022")
        self.assertNotIn("ERROR: B31.1-2024", f)
        self.assertIn("CHECK: occasional terms carry an ASD scale factor", f)

    def test_b311_allowable_text(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["code"] = "B31.1"
        self.assertIn("k = 1.15", self._findings(spec))

    def test_single_friction_note(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["frictions"] = [["w/ Friction", 1.0]]
        self.assertIn("NOTE: only one friction multiplier", self._findings(spec))


class SpecErrors(unittest.TestCase):

    def test_unknown_base_state(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["occasionals"][0]["base"] = "nope"
        with self.assertRaises(g.SpecError):
            g.LoadCaseSet(spec)

    def test_unknown_kind(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["occasionals"][0]["kind"] = "tornado"
        with self.assertRaises(g.SpecError):
            g.LoadCaseSet(spec)

    def test_bad_code(self):
        spec = copy.deepcopy(g.EXAMPLE_SPEC)
        spec["code"] = "B31.4"
        with self.assertRaises(g.SpecError):
            g.LoadCaseSet(spec)

    def test_forward_reference_is_rejected(self):
        s = g.LoadCaseSet(copy.deepcopy(g.EXAMPLE_SPEC))
        s.cases = [g.Case(key="a", block="EXP", stress="EXP", desc="A", method="Algebraic",
                          refs=[(+1, "b")]),
                   g.Case(key="b", block="OPE", stress="OPE", desc="B", terms=["W"])]
        with self.assertRaises(g.SpecError):
            s._resolve()


class CommandLine(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "loadcase_gen.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_example_spec_file(self):
        r = self._run("--spec", os.path.join(SCRIPTS, "examples", "two-state-b313.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Total cases: 88", r.stdout)

    def test_json_format(self):
        r = self._run("--example", "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["total_cases"], 88)

    def test_csv_format(self):
        r = self._run("--example", "--format", "csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 89)  # header + 88

    def test_bad_spec_exits_2(self):
        r = self._run("--spec", os.path.join(ROOT, "tests", "does-not-exist.json"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("spec error", r.stderr)


class SkillContent(unittest.TestCase):
    """Guards on the shipped SKILL.md: frontmatter limits and the product rules."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: load-case-builder\n"))
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 400)  # short slash-menu blurb

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)


# ------------------------------------------------------------------ code_values

class CodeValuesAreRefused(unittest.TestCase):
    """The generator has no code-table inputs: an empty block changes nothing, an entry is refused."""

    BLOCK = {
        "Sh": {"value": 20.0, "unit": "ksi",
               "citation": {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
                            "row": "Placeholder row"},
               "source": "connector"},
    }

    def test_null_and_empty_blocks_change_nothing(self):
        for block in (None, {}):
            spec = dict(copy.deepcopy(g.EXAMPLE_SPEC), code_values=block)
            self.assertEqual(g.render_report(build(spec)), g.render_report(build(g.EXAMPLE_SPEC)))

    def test_an_entry_is_a_spec_error_naming_the_entry(self):
        with self.assertRaises(g.SpecError) as cm:
            build(dict(copy.deepcopy(g.EXAMPLE_SPEC), code_values=self.BLOCK))
        self.assertIn("code_values.Sh is not an input of loadcase_gen.py", str(cm.exception))

    def test_a_block_that_is_not_an_object_is_a_spec_error(self):
        for block in ([1], "Sh", 5):
            with self.assertRaises(g.SpecError) as cm:
                build(dict(copy.deepcopy(g.EXAMPLE_SPEC), code_values=block))
            self.assertIn("code_values must be an object", str(cm.exception))

    def test_cli_exits_2_with_an_entry_and_is_identical_without_one(self):
        import tempfile
        tool = os.path.join(SCRIPTS, "loadcase_gen.py")
        with tempfile.TemporaryDirectory() as d:
            def run(block):
                path = os.path.join(d, "job.json")
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(dict(copy.deepcopy(g.EXAMPLE_SPEC), code_values=block), fh)
                return subprocess.run([sys.executable, tool, "--spec", path], capture_output=True, text=True,
                                      encoding="utf-8")
            refused, empty = run(self.BLOCK), run({})
            plain = subprocess.run([sys.executable, tool, "--example"], capture_output=True, text=True,
                                   encoding="utf-8")
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(refused.stdout, "")
        self.assertIn("code_values.Sh is not an input of loadcase_gen.py", refused.stderr)
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(empty.stdout, plain.stdout)



# ------------------------------------------------------------------ 0.7.1 completeness gates
# CODEX P1-1 (coverage of every state and friction variant in the envelopes and the
# extraction matrix) and P1-2 (unreduced companions for ASD-scaled occasionals).

def load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


def matrix(s: g.LoadCaseSet) -> dict:
    """Extraction matrix as {purpose: [case keys]}."""
    return {purpose: keys for purpose, keys, _ in s.matrix_rows()}


def refs(s: g.LoadCaseSet, key: str) -> set:
    return {r for _, r in next(c for c in s.cases if c.key == key).refs}


def matrix_numbers(s: g.LoadCaseSet, purpose: str) -> list:
    """L-numbers printed in one row of the rendered markdown matrix."""
    line = next(x for x in s.report_matrix().splitlines() if x.startswith(f"| {purpose} |"))
    return [int(t) for t in line.split("|")[2].split(",")]


class MultiStateCoverage(unittest.TestCase):
    """Three states, three friction multipliers, occasionals riding non-primary states,
    inter-state ranges on, nothing scaled."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load_fixture("three-state-unscaled.json")
        cls.s = build(cls.spec)
        cls.F = [str(fv) for _, fv in cls.spec["frictions"]]
        cls.states = [st["key"] for st in cls.spec["thermal_states"]]
        cls.n = {c.key: c.number for c in cls.s.cases}

    def test_count_and_qc_pass(self):
        self.assertEqual(len(self.s.cases), expected_count(self.spec))
        self.assertTrue(self.s.qc["pass"], self.s.qc["misses"])
        self.assertEqual(self.s.qc["counts"]["expected_cases"], len(self.s.cases))
        self.assertIn("QC: resolved case set complete", "\n".join(self.s.findings))

    def test_max_ope_holds_every_state_and_friction(self):
        env = refs(self.s, "max:ope")
        for st in self.states:
            for fv in self.F:
                self.assertIn(f"ope:{st}:{fv}", env)
        for o in self.spec["occasionals"]:
            for fv in self.F:
                self.assertIn(f"opeocc:{o['key']}:{fv}", env)   # incl. wind on 'max', PSV on 'cold'

    def test_non_primary_sus_case_is_in_every_sustained_row(self):
        """A state-2 SUS case at a non-first friction is where the matrix points."""
        m = matrix(self.s)
        for row in ("Code stress - Sustained", "Support loads - Sustained", "Displacements - Sustained"):
            for st in self.states:
                for fv in self.F:
                    self.assertIn(f"sus:{st}:{fv}", m[row], row)
            self.assertIn(self.n["sus:max:0.5"], matrix_numbers(self.s, row))

    def test_inter_state_ranges_per_friction(self):
        m = matrix(self.s)["Code stress - Expansion range between states"]
        for i, a in enumerate(self.states):
            for b in self.states[i + 1:]:
                for fv in self.F:
                    key = f"exprange:{a}:{b}:{fv}"
                    c = next(x for x in self.s.cases if x.key == key)
                    self.assertEqual(c.refs, [(+1, f"ope:{a}:{fv}"), (-1, f"ope:{b}:{fv}")])
                    self.assertEqual(c.method, "Algebraic")
                    self.assertIn(key, m)
        # the frictionless range exists and the printed row carries its number
        self.assertIn(self.n["exprange:op:cold:0.0"],
                      matrix_numbers(self.s, "Code stress - Expansion range between states"))

    def test_hydrotest_per_friction_in_stress_and_support_rows(self):
        m = matrix(self.s)
        hyd = [c for c in self.s.cases if c.block == "HYD"]
        self.assertEqual([c.friction for c in hyd], [fv for _, fv in self.spec["frictions"]])
        for c in hyd:
            self.assertIn(c.key, m["Code stress - Hydrotest"])
            self.assertIn(c.key, m["Support loads - Hydrotest"])
            self.assertTrue(c.desc.startswith("HYDRO TEST CASE ("), c.desc)

    def test_hanger_pair_listed_and_friction_explicit(self):
        m = matrix(self.s)
        self.assertEqual(m["Hanger design - Rigid load / Ignore travel"], ["hgr:rigid", "hgr:travel"])
        f = "\n".join(self.s.findings)
        self.assertIn("ASSUMED: hanger design pair (W Rigid, W+T1 Ignore) runs at friction multiplier 1.0", f)
        self.assertIn("ASSUMED: primary state = op (first declared)", f)

    def test_occasionals_on_non_primary_states_subtract_their_own_base(self):
        self.assertEqual(refs(self.s, "pure:win_px:0.0"), {"opeocc:win_px:0.0", "ope:max:0.0"})
        self.assertEqual(refs(self.s, "occ:psv_cold:0.5"), {"sus:cold:0.5", "pure:psv_cold:0.5"})


class PrimaryStateAndHangerFriction(unittest.TestCase):

    def setUp(self):
        self.spec = load_fixture("three-state-unscaled.json")

    def test_primary_state_never_changes_coverage(self):
        base = build(self.spec)
        for key in ("op", "max", "cold"):
            s = build(dict(copy.deepcopy(self.spec), primary_state=key))
            self.assertEqual([c.key for c in s.cases], [c.key for c in base.cases])
            self.assertEqual(refs(s, "max:ope"), refs(base, "max:ope"))
            self.assertTrue(s.qc["pass"], s.qc["misses"])
            for purpose, keys in matrix(base).items():
                self.assertEqual(set(matrix(s)[purpose]), set(keys), purpose)
            self.assertNotIn("ASSUMED: primary state", "\n".join(s.findings))

    def test_primary_state_drives_hanger_travel_and_labels(self):
        s = build(dict(copy.deepcopy(self.spec), primary_state="max"))
        travel = next(c for c in s.cases if c.key == "hgr:travel")
        self.assertEqual(travel.terms, ["W", "T2"])
        self.assertIn("primary state max", s.report_matrix())
        self.assertEqual(matrix(s)["Flange / nozzle loads - Operating"][0], "ope:max:1.0")

    def test_hanger_friction_field(self):
        s = build(dict(copy.deepcopy(self.spec), hanger_friction=0.0))
        for key in ("hgr:rigid", "hgr:travel"):
            self.assertEqual(next(c for c in s.cases if c.key == key).friction, 0.0)
        self.assertNotIn("ASSUMED: hanger design pair", "\n".join(s.findings))
        self.assertIn("friction 0.0", s.report_matrix())

    def test_single_state_needs_no_primary_assumption(self):
        spec = copy.deepcopy(self.spec)
        spec["thermal_states"] = spec["thermal_states"][:1]
        spec["occasionals"] = [o for o in spec["occasionals"] if o["base"] == "op"]
        s = build(spec)
        self.assertNotIn("ASSUMED: primary state", "\n".join(s.findings))
        self.assertTrue(s.qc["pass"], s.qc["misses"])

    def test_no_hangers_no_hanger_assumption(self):
        s = build(dict(copy.deepcopy(self.spec), hangers=False))
        self.assertNotIn("ASSUMED: hanger design pair", "\n".join(s.findings))
        self.assertNotIn("Hanger design", s.report_matrix())
        self.assertTrue(s.qc["pass"], s.qc["misses"])

    def test_no_hydrotest_no_occasionals_still_passes(self):
        spec = dict(copy.deepcopy(self.spec), hydrotest=False, occasionals=[])
        s = build(spec)
        self.assertEqual(len(s.cases), expected_count(spec))
        self.assertTrue(s.qc["pass"], s.qc["misses"])
        self.assertNotIn("Hydrotest", s.report_matrix())

    def test_spec_errors(self):
        bad = [dict(copy.deepcopy(self.spec), primary_state="nope"),
               dict(copy.deepcopy(self.spec), hanger_friction=-1),
               dict(copy.deepcopy(self.spec), hanger_friction="1.0"),
               dict(copy.deepcopy(self.spec), hanger_friction=True),
               dict(copy.deepcopy(self.spec), frictions=[]),
               dict(copy.deepcopy(self.spec), frictions=[["a", 1.0], ["b", 1.0]]),
               dict(copy.deepcopy(self.spec), frictions=[["a", 1], ["b", 1.0]]),
               dict(copy.deepcopy(self.spec), frictions=[["a", -0.5]]),
               dict(copy.deepcopy(self.spec), frictions=[["a", "1.0"]]),
               dict(copy.deepcopy(self.spec), frictions=[["a", True]])]
        for bad_scale in (0, 1.0, 1.3, "0.6", True, -0.6):
            spec = copy.deepcopy(self.spec)
            spec["occasionals"][0]["scale"] = bad_scale
            bad.append(spec)
        dup_state = copy.deepcopy(self.spec)
        dup_state["thermal_states"].append(dict(dup_state["thermal_states"][0]))
        dup_occ = copy.deepcopy(self.spec)
        dup_occ["occasionals"].append(dict(dup_occ["occasionals"][0]))
        for spec in bad + [dup_state, dup_occ]:
            with self.assertRaises(g.SpecError):
                g.LoadCaseSet(spec)


class ScaledOccasionals(unittest.TestCase):
    """P1-2: the reduced OPE+OCC case keeps the scale for the code-stress path; an
    unreduced companion feeds Maximum Operating, support loads and displacements."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load_fixture("three-state-scaled.json")
        cls.s = build(cls.spec)
        cls.F = [str(fv) for _, fv in cls.spec["frictions"]]
        cls.by_key = {c.key: c for c in cls.s.cases}

    def test_golden(self):
        with open(GOLDEN_SCALED, encoding="utf-8") as fh:
            self.assertEqual(g.render_report(self.s), fh.read())

    def test_count_block_order_and_backward_refs(self):
        self.assertEqual(len(self.s.cases), expected_count(self.spec))
        blocks = [c.block for c in self.s.cases]
        seen = [b for i, b in enumerate(blocks) if i == 0 or blocks[i - 1] != b]
        self.assertEqual(seen, ["HGR", "HYD", "OPE", "OPE+OCC", "OPE+OCC-UNRED", "SUS", "EXP",
                                "OCC-PURE", "OCC-CODE", "MAX"])
        index = {c.key: c.number for c in self.s.cases}
        for c in self.s.cases:
            for _, r in c.refs:
                self.assertLess(index[r], c.number, c.key)
        self.assertTrue(self.s.qc["pass"], self.s.qc["misses"])

    def test_companion_pairs(self):
        env = refs(self.s, "max:ope")
        m = matrix(self.s)
        for o in self.spec["occasionals"]:
            sign = o.get("sign", "+")
            for fv in self.F:
                red = self.by_key[f"opeocc:{o['key']}:{fv}"]
                if o.get("scale"):
                    unred = self.by_key[f"opeoccu:{o['key']}:{fv}"]
                    self.assertEqual(red.terms[-1], f"{sign}{o['scale']}{o['vector']}")
                    self.assertEqual(unred.terms[:-1], red.terms[:-1])
                    self.assertEqual(unred.terms[-1], f"{sign}{o['vector']}")
                    self.assertEqual((unred.friction, unred.stress), (red.friction, "OPE"))
                    self.assertIn("UNREDUCED", unred.desc)
                    self.assertIn(" REDUCED", red.desc)
                    self.assertIn(unred.key, env)                 # loads read full magnitude
                    self.assertNotIn(red.key, env)                # never the reduced case
                    self.assertIn(unred.key, m["Support loads / displacements - Occasional UNREDUCED"])
                else:
                    self.assertIn(red.key, env)
                    self.assertNotIn(f"opeoccu:{o['key']}:{fv}", self.by_key)
                # the code-stress path stays on the reduced case
                self.assertEqual(refs(self.s, f"pure:{o['key']}:{fv}"),
                                 {red.key, f"ope:{o['base']}:{fv}"})

    def test_findings_and_matrix_say_which_is_which(self):
        f = "\n".join(self.s.findings)
        self.assertIn("Unreduced companions (12 OPE+OCC-UNRED cases) are generated", f)
        r = self.s.report_matrix()
        self.assertIn("ASD-scaled terms are REDUCED here (stress path only)", r)
        self.assertIn("scaled occasionals enter UNREDUCED", r)

    def test_json_carries_qc_and_matrix(self):
        d = json.loads(self.s.to_json())
        self.assertTrue(d["qc"]["pass"])
        self.assertEqual(d["qc"]["misses"], [])
        self.assertEqual(d["qc"]["counts"]["scaled_occasionals"], 4)
        self.assertEqual(d["qc"]["counts"]["generated_cases"], d["total_cases"])
        self.assertEqual((d["primary_state"], d["hanger_friction"]), ("max", 0.0))
        purposes = [row["purpose"] for row in d["extraction_matrix"]]
        self.assertIn("Support loads / displacements - Occasional UNREDUCED", purposes)
        self.assertTrue(all(isinstance(n, int) for row in d["extraction_matrix"] for n in row["cases"]))

    def test_removing_the_scale_removes_only_the_companions(self):
        plain = load_fixture("three-state-unscaled.json")
        unscaled = copy.deepcopy(self.spec)
        for o in unscaled["occasionals"]:
            o.pop("scale", None)
        a, b = build(unscaled), build(dict(plain, primary_state="max", hanger_friction=0.0))
        self.assertEqual(g.render_report(a), g.render_report(b))
        self.assertFalse(any(c.block == "OPE+OCC-UNRED" for c in a.cases))

    def test_b311_scaled_still_gets_companions(self):
        s = build(dict(copy.deepcopy(self.spec), code="B31.1", edition="2024"))
        self.assertIn("ERROR: B31.1-2024", "\n".join(s.findings))
        self.assertTrue(any(c.block == "OPE+OCC-UNRED" for c in s.cases))
        self.assertTrue(s.qc["pass"], s.qc["misses"])


class UnscaledEqualsBaseline(unittest.TestCase):
    """With no scaled occasional, 0.7.1 reproduces the 0.7.0 case set (recorded symbolically
    in tests/fixtures/load-case-builder/baseline-0.7.0-unscaled.json) except the P1-1
    coverage changes: HYD and inter-state ranges per friction, Maximum Operating over every
    state. Every other case keeps its key, content and relative order."""

    SPECS = {"two-state-b313 (built-in example)": lambda: g.EXAMPLE_SPEC,
             "three-state-unscaled": lambda: load_fixture("three-state-unscaled.json")}

    @staticmethod
    def _rec(c: g.Case) -> dict:
        return {"key": c.key, "block": c.block, "stress": c.stress, "desc": c.desc,
                "terms": c.terms, "refs": [[sg, r] for sg, r in c.refs], "method": c.method,
                "friction": c.friction, "hanger": c.hanger, "suppress": c.suppress}

    def test_every_old_case_survives_unchanged_or_as_a_documented_coverage_change(self):
        baseline = load_fixture("baseline-0.7.0-unscaled.json")["sets"]
        self.assertEqual(set(baseline), set(self.SPECS))
        for name, spec_fn in self.SPECS.items():
            with self.subTest(name):
                spec = spec_fn()
                s = build(spec)
                new = {c.key: self._rec(c) for c in s.cases}
                order = [c.key for c in s.cases]
                f0name, f0 = spec["frictions"][0][0], str(spec["frictions"][0][1])
                mapped = []
                for old in baseline[name]:
                    k = old["key"]
                    if k == "hyd":
                        nk = f"hyd:{f0}"
                        self.assertEqual(new[nk], dict(old, key=nk, desc=f"HYDRO TEST CASE ({f0name})"))
                    elif k.startswith("exprange:"):
                        nk = f"{k}:{f0}"
                        self.assertEqual(new[nk], dict(old, key=nk, desc=f"{old['desc']} ({f0name})"))
                    elif k == "max:ope":
                        nk = k
                        self.assertTrue({r for _, r in old["refs"]} <= {r for _, r in new[k]["refs"]})
                        self.assertEqual(dict(new[k], refs=None), dict(old, refs=None))
                    else:
                        nk = k
                        self.assertEqual(new[k], old, k)
                    mapped.append(nk)
                # relative order of the surviving cases is unchanged
                kept = set(mapped)
                self.assertEqual([k for k in order if k in kept], mapped)
                # the only additions are the per-friction HYD and range cases
                for k in set(order) - kept:
                    self.assertTrue(k.startswith(("hyd:", "exprange:")), k)
                    self.assertFalse(k.endswith(":" + f0), k)


class CaseSetQCDetectsDefects(unittest.TestCase):
    """The resolved-case-set check is independent of the block builders: re-introduce each
    0.7.0 defect and it fails."""

    def setUp(self):
        self.spec = load_fixture("three-state-scaled.json")

    def _misses(self, cls) -> str:
        s = cls(copy.deepcopy(self.spec)).build()
        self.assertFalse(s.qc["pass"])
        self.assertEqual(s.qc["counts"]["misses"], len(s.qc["misses"]))
        self.assertIn("ERROR: resolved case set has", "\n".join(s.findings))
        return "\n".join(s.qc["misses"])

    def test_primary_only_envelope_is_caught(self):
        class PrimaryOnly(g.LoadCaseSet):
            def _max_ope_members(self):
                p = self.states[0].key
                return [k for k in super()._max_ope_members()
                        if k.startswith(f"ope:{p}:")
                        or any(k.split(":")[1] == o.key for o in self.occ if o.base == p)]
        misses = self._misses(PrimaryOnly)
        self.assertIn("[ope:max:0.0] is not in max:ope", misses)
        self.assertIn("[opeoccu:win_px:0.5] is not in max:ope", misses)

    def test_reduced_case_in_envelope_is_caught(self):
        class Reduced(g.LoadCaseSet):
            def _load_occ_key(self, o, fval):
                return self._k("opeocc", o.key, str(fval))
        self.assertIn("REDUCED case [opeocc:win_px:1.0] is in max:ope", self._misses(Reduced))

    def test_first_friction_only_ranges_are_caught(self):
        class FirstFrictionRanges(g.LoadCaseSet):
            def _block_expansion(self):
                super()._block_expansion()
                f0 = str(self.frictions[0][1])
                self.cases = [c for c in self.cases
                              if not (c.key.startswith("exprange:") and not c.key.endswith(":" + f0))]
        self.assertIn("missing inter-state range op-cold x friction 0.0",
                      self._misses(FirstFrictionRanges))

    def test_matrix_row_gap_is_caught(self):
        class FirstStateSag(g.LoadCaseSet):
            def matrix_rows(self):
                return [(p, k[:1] if p == "Displacements - Sustained" else k, b)
                        for p, k, b in super().matrix_rows()]
        self.assertIn("matrix row 'Displacements - Sustained' does not list [sus:op:0.5]",
                      self._misses(FirstStateSag))

    def test_cli_json_reports_the_qc_block(self):
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "loadcase_gen.py"), "--spec",
                            os.path.join(FIXTURES, "three-state-unscaled.json"), "--format", "json"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertTrue(d["qc"]["pass"])
        self.assertEqual(d["qc"]["counts"]["state_pairs_ranged"], 3)

if __name__ == "__main__":
    unittest.main()
