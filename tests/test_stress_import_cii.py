"""stress-import: the CAESAR II neutral-file repair (fix_cii.py, verify_cii.py, cii.py), the
pre-import checker (pcf_check.py) and the SVG plotter (plot_pcf.py), on synthetic files.

The neutral-file scripts were proven on a real APCF import; this test rebuilds the format they
rely on (15-line element records of %13.6E reals, 24-line restraint records, COORDS seeds in ft,
the SIF&TEES slots) small enough to reason about: two elements on two lines sharing one node,
one '+ANC' restraint imported as code 6. Standard library only; no Python beyond 3.9 is needed.
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-import", "scripts")
sys.path.insert(0, SCRIPTS)

import cii  # noqa: E402
import fix_cii  # noqa: E402

FMT = fix_cii.fmt


def element(frm, to, dx, dy, dz, od=6.625, wall=0.28, ins=0.0, t1=70.0, p1=0.0, fluid=0.0):
    r = [0.0] * 53
    r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7] = float(frm), float(to), dx, dy, dz, od, wall, ins
    r[9], r[18], r[31], r[46], r[47] = t1, p1, fluid, 9999.99, 9999.99
    chunks = [r[0:6], r[6:12], r[12:18], r[18:24], r[24:30], r[30:36], r[36:42], r[42:48], r[48:53]]
    lines = [FMT(c) for c in chunks]
    lines += ["", "", "   -1   -1", "    0    0    0    0    0", "    0    0    0    0    0", "    0    0    0    0    0"]
    return lines


def restraint(node, rtype, tag="PTS-ANC_A001"):
    lines = []
    for k in range(6):
        if k == 0:
            lines += [FMT([float(node), float(rtype), 1e12, 0.0, 0.0, 0.0]), FMT([0.0, 1.0, 0.0]), tag, ""]
        else:
            lines += [FMT([0.0] * 6), FMT([0.0] * 3), "", ""]
    return lines


def synthetic_cii():
    L = ["#$ VERSION", "  5.00", "#$ CONTROL", "  2  0  0  1", "#$ ELEMENTS"]
    L += element(10, 20, 120.0, 0.0, 0.0)          # +X, line A
    L += element(20, 30, 0.0, 120.0, 0.0)          # +Y (up), line B
    L += ["#$ BEND", "#$ RIGID", "#$ RESTRANT"] + restraint(10, 6)
    sif = [0.0] * (2 * 42 * 2)
    sif[0] = 10.0
    L += ["#$ SIF&TEES"] + [FMT(sif[i:i + 6]) for i in range(0, len(sif), 6)]
    L += ["#$ REDUCERS", "#$ COORDS", "  1", "%15d" % 10 + "".join("%13.6E" % v for v in (0.0, 0.0, 0.0))]
    L += ["#$ ALLOWBLS", "  0.0", "#$ MISCEL_1", "  x", "#$ DISPLMNT", "#$ FORCMNT", "#$ EQUIPMNT", "#$ FLANGES",
          "#$ EXPJT", "#$ UNIFORM", "#$ WIND", "#$ OFFSETS", "#$ UNITS", "  INCH  LB  F  PSI", ""]
    return "\r\n".join(L)


def pcf(points, bore=6.0):
    out = ["ISOGEN-FILES ISOGEN.FLS", "UNITS-BORE INCH", "UNITS-CO-ORDS INCH", "PIPELINE-REFERENCE X"]
    for a, b in zip(points, points[1:]):
        out += ["PIPE", "    END-POINT %.4f %.4f %.4f %.1f" % (*a, bore), "    END-POINT %.4f %.4f %.4f %.1f" % (*b, bore)]
    return "\r\n".join(out) + "\r\n"


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


class NeutralFileRepair(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.src = os.path.join(cls.tmp, "in.CII")
        with open(cls.src, "w", encoding="latin-1", newline="") as fh:
            fh.write(synthetic_cii())
        # CAESAR II frame (X, Y up, Z) -> PCF frame (X, Y, Z up): node 20 is (120, 0, 0), node 30 (120, 0, 120)
        with open(os.path.join(cls.tmp, "A.pcf"), "w", newline="") as fh:
            fh.write(pcf([(0, 0, 0), (120, 0, 0)]))
        with open(os.path.join(cls.tmp, "B.pcf"), "w", newline="") as fh:
            fh.write(pcf([(120, 0, 0), (120, 0, 120)]))
        cls.cfg = os.path.join(cls.tmp, "lines.json")
        with open(cls.cfg, "w") as fh:
            fh.write('{"inc": 5, "p1": 150.0, "insul_in": 1.0, "fluid_den_lb_in3": 0.0361111, "tol_in": 0.05,\n'
                     ' "lines": {"A": {"pcf": "%s", "start": 100, "band_end": 495, "t1": 40.0},\n'
                     '           "B": {"pcf": "%s", "start": 500, "band_end": 995, "t1": 58.0}}}'
                     % (os.path.join(cls.tmp, "A.pcf").replace("\\", "/"), os.path.join(cls.tmp, "B.pcf").replace("\\", "/")))
        cls.dst = os.path.join(cls.tmp, "out.CII")
        cls.map = os.path.join(cls.tmp, "map.csv")
        cls.fix = run(os.path.join(SCRIPTS, "fix_cii.py"), cls.src, cls.dst, cls.map, cls.cfg)

    def test_the_synthetic_file_parses_like_a_real_one(self):
        secs = cii.sections(self.src)
        els = cii.elements(secs)
        self.assertEqual([(e["frm"], e["to"]) for e in els], [(10.0, 20.0), (20.0, 30.0)])
        self.assertEqual(els[0]["dx"], 120.0)
        (slots,) = cii.restraints(secs)
        self.assertEqual((slots[0]["node"], slots[0]["type"], slots[0]["tag"]), (10.0, 6.0, "PTS-ANC_A001"))

    def test_fixer_runs_and_renumbers_in_element_order_per_line(self):
        self.assertEqual(self.fix.returncode, 0, self.fix.stdout + self.fix.stderr)
        with open(self.map, newline="") as fh:
            rows = {int(r["old_node"]): r for r in csv.DictReader(fh)}
        self.assertEqual({k: int(v["new_node"]) for k, v in rows.items()}, {10: 100, 20: 105, 30: 500})
        self.assertEqual(rows[20]["line"], "A/B")           # the shared node belongs to both PCFs
        self.assertEqual(float(rows[30]["Z_in"]), 120.0)    # Y-up -> Z-up mapping
        self.assertIn("anchors fixed 1", self.fix.stdout)

    def test_anchor_code_6_becomes_1_and_line_data_lands(self):
        els = cii.elements(cii.sections(self.dst))
        self.assertEqual([(e["frm"], e["to"], e["t1"], e["p1"], e["ins"]) for e in els],
                         [(100.0, 105.0, 40.0, 150.0, 1.0), (105.0, 500.0, 58.0, 150.0, 1.0)])
        self.assertAlmostEqual(els[0]["r"][31], 0.0361111)
        (slots,) = cii.restraints(cii.sections(self.dst))
        self.assertEqual((slots[0]["node"], slots[0]["type"], slots[0]["dir"]), (100.0, 1.0, [0.0, 0.0, 0.0]))
        with open(self.dst, "rb") as fh:
            raw = fh.read()
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))   # CAESAR II wants CRLF

    def test_verifier_passes_the_repair_and_fails_a_tampered_one(self):
        v = run(os.path.join(SCRIPTS, "verify_cii.py"), self.src, self.dst, self.map, self.cfg)
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertTrue(v.stdout.strip().endswith("PASS"), v.stdout)
        with open(self.dst, encoding="latin-1") as fh:
            text = fh.read()
        bad = os.path.join(self.tmp, "bad.CII")
        with open(bad, "w", encoding="latin-1", newline="") as fh:
            fh.write(text.replace("#$ MISCEL_1\n  x", "#$ MISCEL_1\n  y"))   # text mode read: LF
        v = run(os.path.join(SCRIPTS, "verify_cii.py"), self.src, bad, self.map, self.cfg)
        self.assertEqual(v.returncode, 1)
        self.assertIn("MISCEL_1 changed", v.stdout)

    def test_a_node_on_no_pcf_is_refused_not_guessed(self):
        cfg = os.path.join(self.tmp, "lines-a-only.json")
        with open(self.cfg) as fh:
            text = fh.read()
        with open(cfg, "w") as fh:
            fh.write(text.replace('"B": {"pcf": "%s"' % os.path.join(self.tmp, "B.pcf").replace("\\", "/"),
                                  '"B": {"pcf": "%s"' % os.path.join(self.tmp, "A.pcf").replace("\\", "/")))
        r = run(os.path.join(SCRIPTS, "fix_cii.py"), self.src, os.path.join(self.tmp, "x.CII"),
                os.path.join(self.tmp, "x.csv"), cfg)
        self.assertEqual(r.returncode, 2)
        self.assertIn("nodes on no PCF", r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "x.CII")))

    def test_usage_without_arguments_exits_2(self):
        self.assertEqual(run(os.path.join(SCRIPTS, "fix_cii.py")).returncode, 2)

    def test_point_index_matches_brute_force(self):
        pts = [(0, 0, 0), (120, 0, 0), (120, 0, 120), (0.03, 0.0, 0.0)]
        idx = fix_cii.PointIndex(pts, 0.05)
        for q in [(0.0, 0.0, 0.0), (120.0, 0.0, 0.04), (60.0, 0.0, 0.0), (0.02, 0.0, 0.0)]:
            brute = min(fix_cii.math.dist(q, p) for p in pts)
            got = idx.nearest_dist(q, 0.05)
            if brute <= 0.05:
                self.assertAlmostEqual(got, brute)
            else:
                self.assertGreater(got, 0.05)


class PreImportCheckAndPlot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.pcf = os.path.join(cls.tmp, "line.pcf")
        body = pcf([(0, 0, 0), (120, 0, 0), (240, 0, 0)])
        body += "SUPPORT\r\n    CO-ORDS 120.0000 0.0000 0.0000\r\n    SKEY ANCH\r\n    NAME PTS-ANC_A001\r\n"
        with open(cls.pcf, "w", newline="") as fh:
            fh.write(body)

    def test_pcf_check_reports_pieces_free_ends_and_skips_spans_without_a_table(self):
        r = run(os.path.join(SCRIPTS, "pcf_check.py"), self.pcf)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("== pieces (1)", r.stdout)
        self.assertIn("== free ends (2)", r.stdout)
        self.assertIn("spans not checked", r.stdout)
        self.assertIn("HARD FAILURES: 0", r.stdout)

    def test_pcf_check_flags_a_support_off_the_centreline(self):
        bad = os.path.join(self.tmp, "off.pcf")
        with open(self.pcf) as fh:
            text = fh.read()
        with open(bad, "w", newline="") as fh:
            fh.write(text.replace("CO-ORDS 120.0000 0.0000 0.0000", "CO-ORDS 120.0000 3.0000 0.0000"))
        r = run(os.path.join(SCRIPTS, "pcf_check.py"), bad, "--span-table", "6:12")
        self.assertEqual(r.returncode, 1)
        self.assertIn("supports off node (1)", r.stdout)
        self.assertIn("<-- NO ANCHOR", r.stdout)

    def test_plot_writes_an_svg_with_three_views_and_the_anchor_marker(self):
        svg = os.path.join(self.tmp, "line.svg")
        r = run(os.path.join(SCRIPTS, "plot_pcf.py"), self.pcf, svg, "test line", "--floors", "0,10")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(svg, encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(text.startswith("<svg"))
        for label in ("plan X-Y", "elevation Y-Z", "elevation X-Z"):
            self.assertIn(label, text)
        self.assertIn('fill="red"', text)                    # the anchor
        self.assertIn("stroke-dasharray", text)              # the floors


if __name__ == "__main__":
    unittest.main()
