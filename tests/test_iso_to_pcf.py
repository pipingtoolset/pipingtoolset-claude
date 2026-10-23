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

SITE_SKEYS = {"FLWN", "FLBL", "ELBW", "TEBW", "WTBW", "VBSW", "RCBW", "01HG", "01GU"}


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
        self.assertIn("UNITS-CO-ORDS           MM", self.text)
        self.assertIn("X=E, Y=N, Z=EL (Z vertical)", self.text)

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
        e1 = [a for k, a in recs if k == "ELBOW"][0]
        # Corner N 215'0 EL 110'0 at E 100'0; LR R = 1.5 x 6 = 9 in; 90 deg so T = 9 in.
        self.assertEqual(e1["END-POINT"][0][:3], [mm(1200), mm(214 * 12 + 3), mm(1320)])
        self.assertEqual(e1["END-POINT"][1][:3], [mm(1200), mm(2580), mm(1329)])
        self.assertEqual(e1["CENTRE-POINT"][0][:3], [mm(1200), mm(2580), mm(1320)])
        self.assertEqual(e1["ANGLE"][0], ["9000.0000"])
        self.assertNotIn("BEND-RADIUS", e1)            # safe vocabulary drops it
        # Tee: centre E 110'0 EL 125'0, C = M = 5 5/8, branch DOWN.
        tee = [a for k, a in recs if k == "TEE"][0]
        self.assertEqual(tee["END-POINT"][0][0], mm(F(1320) - F(45, 8)))
        self.assertEqual(tee["END-POINT"][1][0], mm(F(1320) + F(45, 8)))
        self.assertEqual(tee["BRANCH1-POINT"][0][2], mm(F(1500) - F(45, 8)))
        # Blind face: E 125'0 + 3 1/2 flange + 1/8 gasket + 1 blind.
        self.assertEqual(recs[-1][1]["END-POINT"][1][0], mm(F(1500) + F(37, 8)))

    def test_safe_vocabulary_mapping(self):
        self.assertLessEqual({k for k, _ in records(self.text)}, set(L.SAFE_RECORDS))
        self.assertTrue(any("CAP written as a PIPE" in s for s in self.r["substitutions"]))

    def test_support_attribute_order(self):
        sup = self.text.split("SUPPORT\r\n", 1)[1].split("\r\n")[:6]
        self.assertEqual([s.split()[0] for s in sup],
                         ["CO-ORDS", "SUPPORT-DIRECTION", "SKEY", "ITEM-CODE", "ITEM-DESCRIPTION", "NAME"])

    def test_pipe_length_by_bore(self):
        # 13'10 7/8 + 13'6 + 2 x 8'9 3/8 + 1'6 3/8 + 98'6 sloped (x 1.00005) + 0'9 = 1749.06 in
        self.assertAlmostEqual(self.r["pipe_centreline_in"]["6"], 1749.06, delta=0.02)
        self.assertEqual(self.r["pipe_centreline_in"]["4"], 36.5)

    def test_assumptions_are_reported_once(self):
        self.assertEqual(len(self.r["assumed"]), len(set(self.r["assumed"])))
        self.assertTrue(any("1.5 x NPS" in a for a in self.r["assumed"]))


class Variants(unittest.TestCase):

    def test_full_vocabulary_keeps_native_records(self):
        s = demo()
        s["full_vocabulary"] = True
        text = build(s).pcf.text()
        for k in ("FLANGE-BLIND", "CAP", "BEND-RADIUS"):
            self.assertIn(k, text)
        self.assertTrue(V.validate(text, safe=False)["ok"])
        self.assertFalse(V.validate(text, safe=True)["ok"])

    def test_y_up_axes(self):
        s = demo()
        s["axes"] = "Y-up"
        rec = records(build(s).pcf.text())[0][1]
        # start E 100'0, N 200'0, EL 110'0 -> X=E, Y=EL, Z=-N
        self.assertEqual(rec["END-POINT"][0][:3], [mm(1200), mm(1320), mm(-2400)])

    def test_inch_coords(self):
        s = demo()
        s["units"] = "INCH"
        text = build(s).pcf.text()
        self.assertIn("UNITS-CO-ORDS           INCH", text)
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
        s["items"][4]["corner"] = {"EL": "125'0", "E": "100'1"}   # not plumb above the riser
        with self.assertRaises(L.PCFError):
            build(s)

    def test_tangent_overrun_is_a_spec_error(self):
        s = demo()
        s["items"][4]["corner"] = {"EL": "110'10"}   # 10 in riser cannot hold two 9 in tangents
        with self.assertRaises(L.PCFError):
            build(s)

    def test_fittings_make_up_gives_no_pipe(self):
        s = demo()
        s.pop("bom")
        s["items"] = [{"type": "elbow", "corner": {"len": "9"}, "out": "UP", "radius": "LR"},
                      {"type": "elbow", "corner": {"d": {"el": "1'6"}}, "out": "E", "radius": "LR"}]
        text = build(s).pcf.text()
        self.assertEqual([k for k, _ in records(text)], ["ELBOW", "ELBOW"])
        self.assertEqual(V.validate(text)["errors"], [])

    def test_stated_angle_must_match_geometry(self):
        s = demo()
        s["items"][3]["angle"] = "45"
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
        del s["items"][3]["out"]
        with self.assertRaises(L.PCFError) as cm:
            build(s)
        self.assertIn("item 3", str(cm.exception))

    def test_tee_record_has_no_centre_point(self):
        tee = [a for k, a in records(build(demo()).pcf.text()) if k == "TEE"][0]
        self.assertNotIn("CENTRE-POINT", tee)

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
    HEAD = "UNITS-BORE INCH\r\nUNITS-CO-ORDS MM\r\n"

    @staticmethod
    def pipe(a, b, bore=6, kind="PIPE"):
        return (f"{kind}\r\n    END-POINT {a} {bore}\r\n    END-POINT {b} {bore}\r\n"
                f"    ITEM-DESCRIPTION X\r\n")

    def test_floating_component(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1500 0 0", "2000 0 0")
        self.assertTrue(any(e.startswith("FLOATING") for e in V.validate(t)["errors"]))

    def test_branch_start_is_legal(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "TEE\r\n    END-POINT 1000 0 0 6\r\n    END-POINT 1300 0 0 6\r\n"
               "    CENTRE-POINT 1150 0 0\r\n    BRANCH1-POINT 1150 150 0 2\r\n"
             + self.pipe("1300 0 0", "2000 0 0") + self.pipe("1150 150 0", "1150 900 0", bore=2))
        r = V.validate(t)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["warnings"], [])

    def test_zero_length(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1000 0 0", "1000 0 0")
        self.assertTrue(any(e.startswith("ZERO-LENGTH") for e in V.validate(t)["errors"]))

    def test_support_off_line(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "SUPPORT\r\n    CO-ORDS 500 0 300 6\r\n    NAME S1\r\n")
        self.assertTrue(any("OFF-LINE" in e for e in V.validate(t)["errors"]))

    def test_bore_change_without_reducer_warns(self):
        t = self.HEAD + self.pipe("0 0 0", "1000 0 0") + self.pipe("1000 0 0", "2000 0 0", bore=4)
        self.assertTrue(any("BORE CHANGE" in w for w in V.validate(t)["warnings"]))

    def test_support_at_elbow_corner_is_on_line(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "ELBOW\r\n    END-POINT 1000 0 0 6\r\n    END-POINT 1228.6 228.6 0 6\r\n"
               "    CENTRE-POINT 1228.6 0 0\r\n"
             + "SUPPORT\r\n    CO-ORDS 1228.6 0 0 6\r\n    NAME S1\r\n")
        self.assertEqual(V.validate(t)["errors"], [])

    def test_bore_mismatch_on_tee_branch_warns(self):
        t = (self.HEAD + self.pipe("0 0 0", "1000 0 0")
             + "TEE\r\n    END-POINT 1000 0 0 6\r\n    END-POINT 1300 0 0 6\r\n"
               "    BRANCH1-POINT 1150 150 0 4\r\n"
             + self.pipe("1150 150 0", "1150 900 0", bore=2))
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
