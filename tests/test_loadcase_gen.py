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
    kinds = {x.get("kind", "other") for x in occ}
    hangers = 2 if spec.get("hangers", True) else 0
    hyd = 1 if spec.get("hydrotest", True) else 0
    ranges = s * (s - 1) // 2 if spec.get("inter_state_expansion_ranges", True) and s > 1 else 0
    envelopes = 1 + len(kinds) + (1 if kinds else 0)  # max:ope, one per kind, max:occ
    # HGR + HYD + OPE + OPE+OCC + SUS + EXP + ranges + pure + code-occ + envelopes
    return hangers + hyd + s * f + o * f + s * f + s * f + ranges + o * f + o * f + envelopes


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
        self.assertEqual(len(build(g.EXAMPLE_SPEC).cases), 87)

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
        self.assertIn(f"| Flange / nozzle loads - Operating | {idx['ope:op:1.0']}, {idx['ope:op:0.0']} |",
                      matrix)

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
        self.assertIn("Total cases: 87", r.stdout)

    def test_json_format(self):
        r = self._run("--example", "--format", "json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["total_cases"], 87)

    def test_csv_format(self):
        r = self._run("--example", "--format", "csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 88)  # header + 87

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
        self.assertLessEqual(len(desc), 1024)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)


if __name__ == "__main__":
    unittest.main()
