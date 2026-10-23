"""Regression tests for the iso-to-pcf skill (builder, library, validator).

Standard library only (unittest), so the gate runs anywhere Python 3.9+ runs:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "iso-to-pcf")
SCRIPTS = os.path.join(SKILL, "scripts")
DEMO = os.path.join(SCRIPTS, "examples", "demo-line.json")
GOLDEN = os.path.join(ROOT, "tests", "golden", "demo-line.pcf")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import build_pcf  # noqa: E402
import content_guard  # noqa: E402
import pcf_lib as L  # noqa: E402
import validate_pcf as V  # noqa: E402

SITE_SKEYS = {"FLWN", "FLBL", "BEBW", "TEBW", "WTBW", "VBSW", "RCBW", "ANCH", "SKID", "GUID"}


def demo() -> dict:
    with open(DEMO, encoding="utf-8") as fh:
        return json.load(fh)


def build(spec: dict) -> build_pcf.Builder:
    return build_pcf.Builder(copy.deepcopy(spec)).build()


def records(text: str):
    """[(kind, {attr: [values, ...]})] in file order, header lines skipped."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not line[0].isspace():
            tok = line.split()
            out.append((tok[0], {}) if len(tok) == 1 else ("HEADER", {}))
        elif out:
            t = line.split()
            out[-1][1].setdefault(t[0], []).append(t[1:])
    return [r for r in out if r[0] != "HEADER"]


def mm(inches) -> str:
    return f"{float(F(inches) * F(254, 10)):.4f}"


class Dimensions(unittest.TestCase):

    def test_iso_fraction_convention(self):
        cases = {"13.7/8": F(111, 8), "2635'0.7/16": F(2635 * 12) + F(7, 16), "5'4": F(64),
                 "4": F(4), "0.1/8": F(1, 8), "7/16": F(7, 16), "-1'2": F(-14),
                 "5' 4 1/2": F(129, 2), "3.1/2": F(7, 2)}
        for s, want in cases.items():
            self.assertEqual(L.ftin(s), want, s)

    def test_true_decimal_is_rejected(self):
        # 13.875 on an iso is a misread 13.7/8 or worse; never accept it silently.
        for bad in ("13.875", "5.5", "abc", "", "4.9/8"):
            with self.assertRaises(L.PCFError, msg=bad):
                L.ftin(bad)

    def test_fmt_in_round_trip(self):
        self.assertEqual(L.fmt_in(L.ftin("125'4.5/8")), "125'4.5/8")
        self.assertEqual(L.fmt_in(F(-14)), "-1'2")

    def test_profile_interpolates_exactly(self):
        p = L.Profile("N", [(L.ftin("215'0"), L.ftin("125'0")), (L.ftin("315'0"), L.ftin("124'0"))])
        self.assertEqual(p.el(L.ftin("265'0")), L.ftin("124'6"))
        with self.assertRaises(L.PCFError):
            p.el(L.ftin("400'0"))

    def test_tangent(self):
        self.assertEqual(L.tangent(F(9), 90.0), F(9))
        self.assertEqual(L.tangent(F(9), 45.0), L.frac_round(9 * 0.41421356237309503))


class DemoBuild(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.b = build(demo())
        cls.text = cls.b.pcf.text()
        cls.r = build_pcf.report(cls.b, cls.b.bom_check())

    def test_golden(self):
        with open(GOLDEN, encoding="ascii", newline="") as fh:
            self.assertEqual(self.text, fh.read())

    def test_crlf_and_header(self):
        self.assertTrue(self.text.startswith("ISOGEN-FILES"))
        self.assertEqual(self.text.count("\r\n"), self.text.count("\n"))
        # Import-proven header: mm for BOTH bore and coordinates, bare pipeline block.
        for line in ("UNITS-BORE MM", "UNITS-CO-ORDS MM", "UNITS-WEIGHT LBS", "UNITS-BOLT-DIA MM",
                     "PIPELINE-REFERENCE DEMO-6-P-1001", "    PROJECT-IDENTIFIER ", "    AREA "):
            self.assertIn(line + "\r\n", self.text)
        self.assertNotIn("ATTRIBUTE", self.text)
        self.assertNotIn("ITEM-CODE", self.text)

    def test_report_clean(self):
        self.assertTrue(self.r["ok"])
        self.assertTrue(all(c["pass"] for c in self.r["closure_checks"]))
        self.assertTrue(all(c["pass"] for c in self.r["bom_checks"]))

    def test_validator_passes_demo(self):
        v = V.validate(self.text, skeys=SITE_SKEYS)
        self.assertEqual(v["errors"], [])
        self.assertEqual(v["warnings"], [])

    def test_hand_computed_coordinates(self):
        recs = records(self.text)
        e1 = [a for k, a in recs if k == "BEND"][0]
        # Corner N 215'0 EL 110'0 at E 100'0; LR R = 1.5 x 6 = 9 in; 90 deg so T = 9 in.
        self.assertEqual(e1["END-POINT"][0][:3], [mm(1200), mm(214 * 12 + 3), mm(1320)])
        self.assertEqual(e1["END-POINT"][1][:3], [mm(1200), mm(2580), mm(1329)])
        self.assertEqual(e1["CENTRE-POINT"][0][:3], [mm(1200), mm(2580), mm(1320)])
        self.assertEqual(e1["ANGLE"][0], ["9000"])
        self.assertEqual(e1["BEND-RADIUS"][0], [mm(9)])
        self.assertEqual(e1["SKEY"][0], ["BEBW"])
        self.assertEqual(e1["END-POINT"][0][3], mm(6))   # bore in mm: NPS 6 -> 152.4000
        # Tee: centre E 110'0 EL 125'0, C = M = 5 5/8, branch DOWN.
        tee = [a for k, a in recs if k == "TEE"][0]
        self.assertEqual(tee["END-POINT"][0][0], mm(F(1320) - F(45, 8)))
        self.assertEqual(tee["END-POINT"][1][0], mm(F(1320) + F(45, 8)))
        self.assertEqual(tee["BRANCH1-POINT"][0][2], mm(F(1500) - F(45, 8)))
        self.assertEqual(tee["CENTRE-POINT"][0][:3], [mm(1320), mm(2580), mm(1500)])
        # Blind face: E 125'0 + 3 1/2 flange + 1/8 gasket + 1 blind (last FLANGE record).
        blind = [a for k, a in recs if k == "FLANGE"][-1]
        self.assertEqual(blind["END-POINT"][1][0], mm(F(1500) + F(37, 8)))
        self.assertEqual(blind["SKEY"][0], ["FLBL"])

    def test_safe_vocabulary_mapping(self):
        self.assertLessEqual({k for k, _ in records(self.text)}, set(L.SAFE_RECORDS))
        self.assertTrue(any("CAP written as a PIPE" in s for s in self.r["substitutions"]))

    def test_support_shape_and_placement(self):
        recs = records(self.text)
        sups = [a for k, a in recs if k == "SUPPORT"]
        # proven shape: CO-ORDS, SKEY, SUPPORT-DIRECTION (none on ANCH); guide -> two records
        self.assertEqual([a["SKEY"][0][0] for a in sups], ["ANCH", "SKID", "GUID", "GUID"])
        self.assertNotIn("SUPPORT-DIRECTION", sups[0])
        self.assertEqual([a["SUPPORT-DIRECTION"][0][0] for a in sups[2:]], ["EAST", "WEST"])
        body = self.text.split("SUPPORT\r\n")[2].split("\r\n")[:3]   # proven order first
        self.assertEqual([s.split()[0] for s in body], ["CO-ORDS", "SKEY", "SUPPORT-DIRECTION"])
        # every support sits on a node: the hanger at N 208'0 splits the pipe there
        ends = {tuple(e[:3]) for k, a in recs if k != "SUPPORT" for e in a.get("END-POINT", [])}
        for a in sups:
            self.assertIn(tuple(a["CO-ORDS"][0][:3]), ends)

    def test_branches_written_after_main_run(self):
        kinds = [k for k, _ in records(self.text)]
        last_main = max(i for i, k in enumerate(kinds) if k == "FLANGE")   # the blind
        self.assertEqual(kinds[last_main + 1:], ["PIPE", "PIPE", "VALVE"])  # drain, cap, vent

    def test_pipe_length_by_bore(self):
        # 13'10 7/8 + 13'6 + 2 x 8'9 3/8 + 1'6 3/8 + 98'6 sloped (x 1.00005) + 0'9 = 1749.06 in
        self.assertAlmostEqual(self.r["pipe_centreline_in"]["6"], 1749.06, delta=0.02)
        self.assertEqual(self.r["pipe_centreline_in"]["4"], 36.5)

    def test_assumptions_are_reported_once(self):
        self.assertEqual(len(self.r["assumed"]), len(set(self.r["assumed"])))
        self.assertTrue(any("1.5 x NPS" in a for a in self.r["assumed"]))


class MinimalProven(unittest.TestCase):

    def test_uses_only_import_proven_records_and_passes_clean(self):
        with open(os.path.join(SCRIPTS, "examples", "minimal-proven.json"), encoding="utf-8") as fh:
            b = build(json.load(fh))
        r = build_pcf.report(b, b.bom_check())
        self.assertTrue(r["ok"])
        text = b.pcf.text()
        self.assertLessEqual({k for k, _ in records(text)}, set(L.PROVEN_RECORDS))
        v = V.validate(text)
        self.assertEqual((v["errors"], v["warnings"]), ([], []))


class Variants(unittest.TestCase):

    def test_full_vocabulary_keeps_native_records(self):
        s = demo()
        s["full_vocabulary"] = True
        text = build(s).pcf.text()
        for k in ("FLANGE-BLIND", "CAP", "ELBOW"):
            self.assertIn(k, text)
        self.assertTrue(V.validate(text, safe=False)["ok"])
        self.assertFalse(V.validate(text, safe=True)["ok"])

    def test_y_up_axes(self):
        s = demo()
        s["axes"] = "Y-up"
        rec = records(build(s).pcf.text())[1][1]   # [0] is the nozzle ANCH
        # start E 100'0, N 200'0, EL 110'0 -> X=E, Y=EL, Z=-N
        self.assertEqual(rec["END-POINT"][0][:3], [mm(1200), mm(1320), mm(-2400)])

    def test_inch_coords(self):
        s = demo()
        s["units"] = "INCH"
        text = build(s).pcf.text()
        self.assertIn("UNITS-CO-ORDS INCH", text)
        self.assertIn("UNITS-BORE INCH", text)
        self.assertTrue(V.validate(text)["ok"])

    def test_failed_closure_check_flags_report(self):
        s = demo()
        s["items"][-1]["expect"] = {"E": "125'4.3/4"}      # 1/8 in off
        b = build(s)
        self.assertFalse(build_pcf.report(b, b.bom_check())["ok"])

    def test_bom_mismatch_flags_report(self):
        s = demo()
        s["bom"]["ELBOW"] = 5
        b = build(s)
        self.assertFalse(build_pcf.report(b, b.bom_check())["ok"])

    def test_off_line_corner_is_a_spec_error(self):
        s = demo()
        s["items"][5]["corner"] = {"EL": "125'0", "E": "100'1"}   # not plumb above the riser
        with self.assertRaises(L.PCFError):
            build(s)

    def test_tangent_overrun_is_a_spec_error(self):
        s = demo()
        s["items"][5]["corner"] = {"EL": "110'10"}   # 10 in riser cannot hold two 9 in tangents
        with self.assertRaises(L.PCFError):
            build(s)

    def test_fittings_make_up_gives_no_pipe(self):
        s = demo()
        s.pop("bom")
        s["items"] = [{"type": "elbow", "corner": {"len": "9"}, "out": "UP", "radius": "LR"},
                      {"type": "elbow", "corner": {"d": {"el": "1'6"}}, "out": "E", "radius": "LR"}]
        text = build(s).pcf.text()
        self.assertEqual([k for k, _ in records(text)], ["BEND", "BEND"])
        self.assertEqual(V.validate(text)["errors"], [])

    def test_stated_angle_must_match_geometry(self):
        s = demo()
        s["items"][4]["angle"] = "45"
        with self.assertRaises(L.PCFError):
            build(s)

    def test_unknown_type_rejected(self):
        s = demo()
        s["items"].insert(0, {"type": "widget"})
        with self.assertRaises(L.PCFError):
            build(s)

    def test_small_skew_on_long_run_is_rejected(self):
        # 1 in lateral slip over 100 ft: a direction-cosine test passes it, a distance test must not.
        s = {"start": {"at": {"E": "0", "N": "0", "EL": "0"}, "dir": "N", "bore": 6},
             "items": [{"type": "pipe", "to": {"E": "1", "N": "100'0"}}]}
        with self.assertRaises(L.PCFError):
            build(s)

    def test_large_bore_sloped_support_stays_on_line(self):
        # Snapped direction cosines once drifted tangent points ~0.06 mm off a sloped line at NPS 48.
        for n in (20, 23, 31, 35, 37, 43):
            s = {"start": {"at": {"E": "0", "N": "0", "EL": "1000'0"}, "dir": "E", "bore": 48},
                 "items": [
                     {"type": "elbow", "corner": {"E": "20'0"}, "out": {"n": str(n), "el": "-1"}, "radius": "LR"},
                     {"type": "support", "at": {"d": {"n": f"{n}'0", "el": "-1'0"}}, "name": "S1"},
                     {"type": "pipe", "to": {"d": {"n": f"{n}'0", "el": "-1'0"}}}]}
            self.assertEqual(V.validate(build(s).pcf.text())["errors"], [], n)

    def test_zero_denominator(self):
        for bad in ("1/0", "0.1/0"):
            with self.assertRaises(L.PCFError):
                L.ftin(bad)

    def test_missing_key_names_the_item(self):
        s = demo()
        del s["items"][4]["out"]
        with self.assertRaises(L.PCFError) as cm:
            build(s)
        self.assertIn("item 4", str(cm.exception))

    def test_tee_record_has_centre_point(self):
        # The import-proven Isogen TEE carries CENTRE-POINT before BRANCH1-POINT.
        tee = [a for k, a in records(build(demo()).pcf.text()) if k == "TEE"][0]
        self.assertEqual(list(tee)[:3], ["END-POINT", "CENTRE-POINT", "BRANCH1-POINT"])

    def test_support_behind_cursor_is_a_spec_error(self):
        s = demo()
        s["items"].insert(5, {"type": "support", "at": {"N": "201'0"}, "skey": "SKID"})
        with self.assertRaises(L.PCFError):
            build(s)

    def test_annotations_on_by_default_and_switchable(self):
        # Import-proven (live CAESAR II import of the T2 ladder file), so on by default.
        text = build(demo()).pcf.text()
        self.assertIn("ITEM-DESCRIPTION FLANGE WN CL150 RF 6IN STD", text)
        self.assertIn("WEIGHT 19.00", text)
        self.assertIn("NAME PS-01_HG", text)
        self.assertEqual(V.validate(text)["errors"], [])
        s = demo()
        s["annotate"] = False
        bare = build(s).pcf.text()
        for k in ("ITEM-DESCRIPTION ", "WEIGHT ", "NAME "):
            self.assertNotIn("\r\n    " + k, bare)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.pcf")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(build_pcf.main([DEMO, "-o", out]), 0)
                self.assertEqual(V.main([out]), 0)
            s = demo()
            s["items"][-1]["expect"] = {"E": "126'0"}
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(s, fh)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(build_pcf.main([bad, "-o", out]), 2)
            s["items"].insert(0, {"type": "widget"})
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(s, fh)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(build_pcf.main([bad, "-o", out]), 1)


class Validator(unittest.TestCase):
    HEAD = "UNITS-BORE MM\r\nUNITS-CO-ORDS MM\r\n"

    @staticmethod
    def pipe(a, b, bore=152.4, kind="PIPE"):
        return (f"{kind}\r\n    END-POINT {a} {bore}\r\n    END-POINT {b} {bore}\r\n"
                f"    ITEM-DESCRIPTION X\r\n")

    def test_floating_component(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1500 0 0", "2000 0 0")
        self.assertTrue(any(e.startswith("FLOATING") for e in V.validate(t)["errors"]))

    def test_branch_start_is_legal(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "TEE\r\n    END-POINT 1000 0 0 152.4\r\n    END-POINT 1300 0 0 152.4\r\n"
               "    CENTRE-POINT 1150 0 0\r\n    BRANCH1-POINT 1150 150 0 50.8\r\n"
             + self.pipe("1300 0 0", "2000 0 0") + self.pipe("1150 150 0", "1150 900 0", bore=50.8))
        r = V.validate(t)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["warnings"], [])

    def test_zero_length(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1000 0 0", "1000 0 0")
        self.assertTrue(any(e.startswith("ZERO-LENGTH") for e in V.validate(t)["errors"]))

    def test_support_off_line(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "SUPPORT\r\n    CO-ORDS 500 0 300 152.4\r\n    SKEY SKID\r\n")
        self.assertTrue(any("OFF-LINE" in e for e in V.validate(t)["errors"]))

    def test_bore_change_without_reducer_warns(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1000 0 0", "2000 0 0", bore=101.6)
        self.assertTrue(any("BORE CHANGE" in w for w in V.validate(t)["warnings"]))

    def test_support_must_sit_on_a_node(self):
        bend = ("BEND\r\n    END-POINT 1000 0 0 152.4\r\n    END-POINT 1228.6 228.6 0 152.4\r\n"
                "    CENTRE-POINT 1228.6 0 0\r\n    SKEY BEBW\r\n    ANGLE 9000\r\n"
                "    BEND-RADIUS 228.6\r\n")
        base = self.HEAD + self.pipe("0 0 0", "1000 0 0") + bend
        at_end = base + "SUPPORT\r\n    CO-ORDS 1228.6 228.6 0 152.4\r\n    SKEY SKID\r\n"
        self.assertEqual(V.validate(at_end)["errors"], [])
        for where in ("1228.6 0 0", "500 0 0"):        # bend corner, mid-pipe
            t = base + f"SUPPORT\r\n    CO-ORDS {where} 152.4\r\n    SKEY SKID\r\n"
            self.assertTrue(any("not on a node" in e for e in V.validate(t)["errors"]), where)

    def test_inch_bore_under_mm_units_is_an_error(self):
        # The first-release failure: NPS written as the bore under a mm header.
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0", bore=6)
        self.assertTrue(any("look like inches" in e for e in V.validate(t)["errors"]))
        t = "UNITS-BORE INCH\r\nUNITS-CO-ORDS MM\r\n" + self.pipe("0 0 0", "1000 0 0", bore=6)
        self.assertTrue(any("differs from UNITS-CO-ORDS" in e for e in V.validate(t)["errors"]))

    def test_elbow_record_is_outside_the_safe_set(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0", kind="ELBOW")
        self.assertTrue(any("safe set" in e for e in V.validate(t)["errors"]))

    def test_bore_mismatch_on_tee_branch_warns(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "TEE\r\n    END-POINT 1000 0 0 152.4\r\n    END-POINT 1300 0 0 152.4\r\n"
               "    BRANCH1-POINT 1150 150 0 101.6\r\n"
             + self.pipe("1150 150 0", "1150 900 0", bore=50.8))
        self.assertTrue(any("BORE CHANGE" in w for w in V.validate(t)["warnings"]))

    def test_unsafe_record_and_missing_units(self):
        errs = V.validate(self.pipe("0 0 0", "1000 0 0", kind="MISC-COMPONENT"))["errors"]
        self.assertTrue(any("UNITS-CO-ORDS" in e for e in errs))
        self.assertTrue(any("safe set" in e for e in errs))

    def test_lf_endings_warn(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")).replace("\r\n", "\n")
        self.assertTrue(any("CRLF" in w for w in V.validate(t)["warnings"]))


class SkillContent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: iso-to-pcf\ndescription: \""))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 400)  # short slash-menu blurb
        for trigger in ("PCF", "CAESAR II", "isometric", "PDF"):
            self.assertIn(trigger, desc)

    def test_shipped_files_referenced(self):
        for rel in ("scripts/build_pcf.py", "scripts/validate_pcf.py", "scripts/pcf_lib.py",
                    "scripts/examples/demo-line.json", "references/spec-format.md",
                    "references/reading-isos.md", "references/caesar-import.md"):
            self.assertTrue(os.path.exists(os.path.join(SKILL, *rel.split("/"))), rel)
            self.assertIn(rel.split("/")[-1], self.text)

    def test_hand_offs_name_only_pack_skills(self):
        self.assertIn("`load-case-builder`", self.text)
        self.assertIn("`stress-screening`", self.text)

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)


if __name__ == "__main__":
    unittest.main()
