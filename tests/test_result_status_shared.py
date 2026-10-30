"""Shared result_status block (plugin 0.8.0, B9): the five words, worst_of order, banner rule, copies.

The canonical text is tools/shared/result_status.py; each of the seven skill scripts carries a
byte-identical copy between its BEGIN/END markers (written by tools/sync_shared_blocks.py).

    python -m unittest tests.test_result_status_shared -v
"""

from __future__ import annotations

import ast
import itertools
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "tools", "shared")
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
sys.path.insert(0, SHARED)

import result_status as rs  # noqa: E402

SCRIPTS = {
    "load-case-builder": "loadcase_gen.py",
    "pressure-design": "pressure_design.py",
    "stress-screening": "stress_screening.py",
    "pipe-support": "support_calc.py",
    "iso-to-pcf": "build_pcf.py",
    "nozzle-load": "nozzle_load.py",
    "bolted-flange": "bolted_flange.py",
}
BEGIN = "# BEGIN shared result_status (do not edit here; source tools/shared/result_status.py)"
END = "# END shared result_status"
WORST_FIRST = ("manual check required", "pointer only", "screening", "not checked", "calculated")


def read(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def block_of(text):
    if text.count(BEGIN + "\n") != 1 or text.count(END + "\n") != 1:
        raise AssertionError("need exactly one result_status block")
    return text[text.index(BEGIN):text.index(END) + len(END)]


class Words(unittest.TestCase):

    def test_exactly_five_words(self):
        self.assertEqual(rs.RESULT_STATUS, ("calculated", "screening", "manual check required", "pointer only",
                                            "not checked"))
        self.assertEqual(set(rs.RESULT_STATUS_SEVERITY), set(rs.RESULT_STATUS))
        self.assertEqual(rs.CHECK_STATUS, ("pass", "fail", "na"))

    def test_worst_of_follows_the_severity_order(self):
        for i, j in itertools.combinations(range(5), 2):
            hi, lo = WORST_FIRST[i], WORST_FIRST[j]
            self.assertEqual(rs.worst_of([lo, hi]), hi)
            self.assertEqual(rs.worst_of([hi, lo]), hi)
        self.assertEqual(rs.worst_of(list(WORST_FIRST[::-1])), "manual check required")
        self.assertEqual(rs.worst_of(["calculated"]), "calculated")
        self.assertEqual(rs.worst_of([]), "not checked")
        self.assertEqual(rs.worst_of(iter(["calculated", "not checked"])), "not checked")

    def test_worst_of_reads_check_dicts_and_rejects_other_words(self):
        checks = [rs.make_check("a", "calculated", "pass"), rs.make_check("b", "screening", "pass")]
        self.assertEqual(rs.worst_of(checks), "screening")
        for bad in ("PASS", "ok", "Calculated", None, "manual-check-required"):
            with self.assertRaises(ValueError):
                rs.worst_of(["calculated", bad])

    def test_envelope_status_ignores_not_checked_rows(self):
        calc = rs.make_check("a", "calculated", "pass")
        gap = rs.make_check("b", "not checked", note="module does not perform it")
        scr = rs.make_check("c", "screening", "pass")
        self.assertEqual(rs.envelope_status([calc, gap]), "calculated")
        self.assertEqual(rs.envelope_status([gap, scr, calc]), "screening")
        self.assertEqual(rs.envelope_status([gap, gap]), "not checked")
        self.assertEqual(rs.envelope_status([]), "not checked")
        self.assertEqual(rs.envelope_status(iter(["not checked", "calculated"])), "calculated")
        for i, j in itertools.combinations(range(5), 2):
            hi, lo = WORST_FIRST[i], WORST_FIRST[j]
            self.assertEqual(rs.envelope_status([lo, hi, "not checked"]), lo if hi == "not checked" else hi)
        with self.assertRaises(ValueError):
            rs.envelope_status(["calculated", "PASS"])

    def test_assumed_inputs_check_is_one_manual_check_row(self):
        row = rs.assumed_inputs_check(["Corrosion allowance per the line list",
                                       {"item": "Seismic design category", "note": "structural basis"},
                                       "Corrosion allowance per the line list", "  "])
        self.assertEqual(row, {"name": "ASSUMED inputs", "result_status": "manual check required", "status": "na",
                               "note": "confirm before issue: Corrosion allowance per the line list; "
                                       "Seismic design category"})
        self.assertEqual(rs.ASSUMED_CHECK_NAME, "ASSUMED inputs")
        self.assertIsNone(rs.assumed_inputs_check([]))
        self.assertIsNone(rs.assumed_inputs_check(None))
        calc = rs.make_check("a", "calculated", "pass")
        self.assertEqual(rs.envelope_status([calc, row]), "manual check required")
        self.assertFalse(rs.checks_banner_allowed([calc, row]))

    def test_not_performed_summary(self):
        calc = rs.make_check("a", "calculated", "pass")
        self.assertEqual(rs.not_performed([calc]), "")
        self.assertEqual(rs.not_performed([calc, rs.make_check("SIF source", "not checked"),
                                           rs.make_check("tee orientation", "not checked")]),
                         "not performed by this module: SIF source; tee orientation")

    def test_make_check_shape(self):
        self.assertEqual(rs.make_check("Eq. 3a wall", "calculated", "pass", "t >= tm"),
                         {"name": "Eq. 3a wall", "result_status": "calculated", "status": "pass", "note": "t >= tm"})
        self.assertEqual(rs.make_check("Sn cap", "not checked")["status"], "na")
        self.assertEqual(rs.make_check("hub F", "screening", "pass", unresolved_factor=True)["unresolved_factor"], True)
        self.assertNotIn("unresolved_factor", rs.make_check("hub F", "screening", "pass"))
        with self.assertRaises(ValueError):
            rs.make_check("x", "calculated", "PASS")
        with self.assertRaises(ValueError):
            rs.make_check("x", "calculated", "pass", unresolved_factor=True)
        with self.assertRaises(ValueError):
            rs.make_check("x", "done")


class BannerRule(unittest.TestCase):

    TABLE = (  # (result_status, unresolved_factor, banner allowed)
        ("calculated", False, True),
        ("not checked", False, True),
        ("screening", False, True),
        ("screening", True, False),
        ("pointer only", False, False),
        ("pointer only", True, False),
        ("manual check required", False, False),
        ("manual check required", True, False),
    )

    def test_banner_allowed_table(self):
        for word, unresolved, allowed in self.TABLE:
            self.assertIs(rs.banner_allowed(word, unresolved), allowed, (word, unresolved))
        with self.assertRaises(ValueError):
            rs.banner_allowed("PASS")

    def test_banner_word(self):
        self.assertEqual(rs.banner_word("PASS", "calculated"), "PASS")
        self.assertEqual(rs.banner_word("OK", "screening"), "OK")
        self.assertEqual(rs.banner_word("PASS", "screening", True), "SCREENING")
        self.assertEqual(rs.banner_word("DELIVERABLE", "pointer only"), "POINTER ONLY")
        self.assertEqual(rs.banner_word("ISSUE", "manual check required"), "MANUAL CHECK REQUIRED")

    def test_checks_banner_allowed_and_status_fields(self):
        calc = rs.make_check("a", "calculated", "pass")
        gap = rs.make_check("b", "not checked", note="module does not perform it")
        rec = rs.make_check("c", "screening", "pass", unresolved_factor=True)
        gate = rs.make_check("d", "manual check required", "na")
        self.assertTrue(rs.checks_banner_allowed([calc, gap]))
        self.assertFalse(rs.checks_banner_allowed([calc, rec]))
        self.assertFalse(rs.checks_banner_allowed([calc, gate]))
        self.assertEqual(rs.status_fields([calc, gap]), {"result_status": "calculated", "checks": [calc, gap]})
        self.assertEqual(rs.status_fields([gap])["result_status"], "not checked")
        self.assertEqual(rs.status_fields([gap, rec])["result_status"], "screening")
        self.assertEqual(rs.status_fields(iter([calc]))["result_status"], "calculated")

    def test_status_line(self):
        self.assertEqual(rs.render_status_line("screening", "flange equivalent-pressure screen"),
                         "Result status: screening - flange equivalent-pressure screen")
        self.assertEqual(rs.render_status_line("calculated", ""), "Result status: calculated")
        with self.assertRaises(ValueError):
            rs.render_status_line("PASS", "x")


class Copies(unittest.TestCase):

    def test_canonical_block_hygiene(self):
        block = block_of(read(os.path.join(SHARED, "result_status.py")))
        tree = ast.parse(block, feature_version=(3, 9))
        self.assertLessEqual({type(n).__name__ for n in tree.body}, {"Assign", "FunctionDef"})
        self.assertTrue(all(ord(c) < 128 for c in block))
        for word in ("import ", "open(", "print("):
            self.assertNotIn(word, block)
        exec(compile(block, "result_status block", "exec"), {})

    def test_seven_scripts_carry_the_canonical_block(self):
        canonical = block_of(read(os.path.join(SHARED, "result_status.py")))
        for skill, script in SCRIPTS.items():
            self.assertEqual(block_of(read(os.path.join(SKILLS, skill, "scripts", script))), canonical, skill)


if __name__ == "__main__":
    unittest.main()
