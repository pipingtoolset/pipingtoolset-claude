"""Smoke tests for the stress-import import-preparation toolkit (standard library only).

Covers the scripts that prepare Revit / Fabrication PCF exports and Navisworks NWC support data
for AutoPIPE or CAESAR II: pcf_prep.py, nwc_supports.py, ap_bendcheck.py (+ ap_pcf.py),
ntl_closures.py, fix_closures.py, pcf2caesar.py (+ pcf_union.py, pcf_split.py, pcf_graph.py,
pcf_pieces.py) and the example job files.

Every test builds its own tiny synthetic input in a temporary directory. The inputs are
SYNTHETIC: they exercise the scripts' code paths and documented exit codes, not a real Revit
export, a real Navisworks cache or a real AutoPIPE .ntl.

    python -m unittest tests.test_stress_import_toolkit -v
"""

from __future__ import annotations

import ast
import copy
import csv
import importlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-import")
SCRIPTS = os.path.join(SKILL, "scripts")
EXAMPLES = os.path.join(SCRIPTS, "examples")

NEW_SCRIPTS = (
    "nwc_supports.py", "pcf_prep.py", "ap_bendcheck.py", "ap_pcf.py", "ntl_closures.py", "fix_closures.py",
    "pcf2caesar.py", "pcf_union.py", "pcf_split.py", "pcf_graph.py", "pcf_pieces.py",
)
NEW_EXAMPLES = ("revit-to-autopipe.job.json", "revit-to-caesar.job.json", "nwc-families.example.json")
# command-line tools: name -> exit code when run with no arguments (the documented usage exit)
CLIS = {
    "nwc_supports.py": 2, "pcf_prep.py": 2, "ap_bendcheck.py": 2, "ntl_closures.py": 2,
    "fix_closures.py": 2, "pcf2caesar.py": 2, "pcf_pieces.py": 2,
}
HEAVY = {"numpy", "scipy", "matplotlib", "openpyxl", "pandas"}


def run(script, *args, cwd=None):
    """Run a shipped script isolated (-I), from any working directory."""
    return subprocess.run([sys.executable, "-I", os.path.join(SCRIPTS, script), *args], capture_output=True,
                          text=True, cwd=cwd, timeout=180)


def write(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="latin-1", newline="") as fh:
        fh.write(text.replace("\n", newline))
    return path


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1)
    return path


# --------------------------------------------------------------------------- synthetic PCF builders
HDR = "ISOGEN-FILES ISOGEN.FLS\nUNITS-BORE INCH\nUNITS-CO-ORDS INCH\nUNITS-WEIGHT LBS\nPIPELINE-REFERENCE SRC\n"


def _pt(key, p, bore=4.0):
    return "    %s  %s  %s  %s  %.4f" % (key, p[0], p[1], p[2], bore)


def rec(kind, pts, extra=(), centre=None, rid=None):
    out = [kind] + [_pt("END-POINT", p) for p in pts]
    if centre is not None:
        out.append("    CENTRE-POINT  %s  %s  %s" % centre)
    out += ["    " + e for e in extra]
    if rid is not None:
        out.append("    REVIT-ID %d" % rid)
    return out


def revit_style_pcf():
    """Two 4 in PIPEs 0.05 in apart, a 1/8 in 'Shop Weld' COUPLING, a FLANGE and a SUPPORT."""
    b = []
    b += rec("PIPE", [(0, 0, 0), (100, 0, 0)], ["ITEM-DESCRIPTION Pipe - CS SCH40"], rid=1)
    b += rec("PIPE", [(100.05, 0, 0), (200, 0, 0)], ["ITEM-DESCRIPTION Pipe - CS SCH40"], rid=2)
    b += rec("COUPLING", [(200, 0, 0), (200.125, 0, 0)], ["ITEM-DESCRIPTION Shop Weld - .125"], rid=3)
    b += rec("FLANGE", [(200.125, 0, 0), (202.125, 0, 0)], ["SKEY FLWN", "ITEM-DESCRIPTION Weld Neck Flange 4in"], rid=4)
    b += ["SUPPORT", "    CO-ORDS  50  0  -2  4.0000", "    SKEY HANG", "    NAME SRC-HNG1"]
    return HDR + "\n".join(b) + "\n"


def caesar_supply_pcf():
    """PIPE, shop-weld COUPLING, 90 degree ELBOW, PIPE: every record type pcf2caesar converts."""
    b = []
    b += rec("PIPE", [(0, 0, 0), (100, 0, 0)], ["ITEM-DESCRIPTION Pipe"], rid=11)
    b += rec("COUPLING", [(100, 0, 0), (100.125, 0, 0)], ["ITEM-DESCRIPTION Shop Weld - .125"], rid=12)
    b += rec("ELBOW", [(100.125, 0, 0), (112.125, 12, 0)], ["ITEM-DESCRIPTION Elbow 90"], centre=(112.125, 0, 0), rid=13)
    b += rec("PIPE", [(112.125, 12, 0), (112.125, 300, 0)], ["ITEM-DESCRIPTION Pipe"], rid=14)
    return HDR + "\n".join(b) + "\n"


def caesar_return_pcf():
    return HDR + "\n".join(rec("PIPE", [(0, 36, 0), (100, 36, 0)], ["ITEM-DESCRIPTION Pipe"], rid=21)) + "\n"


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)


# --------------------------------------------------------------------------- 1. files and imports
class ShippedFiles(unittest.TestCase):

    def test_every_new_file_is_shipped(self):
        for name in NEW_SCRIPTS:
            self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, name)), name)
        for name in NEW_EXAMPLES:
            self.assertTrue(os.path.isfile(os.path.join(EXAMPLES, name)), name)

    def test_files_are_ascii_lf_with_trailing_newline(self):
        names = [os.path.join(SCRIPTS, n) for n in NEW_SCRIPTS] + [os.path.join(EXAMPLES, n) for n in NEW_EXAMPLES]
        for path in names:
            with open(path, "rb") as fh:
                data = fh.read()
            self.assertTrue(all(c < 128 for c in data), path)
            self.assertNotIn(b"\r", data, path)
            self.assertTrue(data.endswith(b"\n") and not data.endswith(b"\n\n"), path)

    def test_python_39_grammar(self):
        for name in NEW_SCRIPTS:
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=name, feature_version=(3, 9))

    def test_no_script_imports_a_heavy_library(self):
        seen = 0
        for name in sorted(os.listdir(SCRIPTS)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=name)
            seen += 1
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module or ""]
                else:
                    continue
                for mod in mods:
                    self.assertNotIn(mod.split(".")[0], HEAVY, f"{name} imports {mod}")
        self.assertGreaterEqual(seen, len(NEW_SCRIPTS))

    def test_every_sibling_import_is_preceded_by_a_path_insert(self):
        siblings = {os.path.splitext(n)[0] for n in os.listdir(SCRIPTS) if n.endswith(".py")}
        for name in NEW_SCRIPTS:
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                text = fh.read()
            tree = ast.parse(text)
            top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            uses = [n for n in top if any((a.name if isinstance(n, ast.Import) else n.module).split(".")[0] in siblings
                                          for a in (n.names if isinstance(n, ast.Import) else [n]))]
            if uses:
                self.assertIn("sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))", text, name)
                self.assertLess(text.index("sys.path.insert(0, os.path.dirname"), text.index(f"\n{ast.get_source_segment(text, uses[0])}"), name)

    def test_each_module_imports_from_the_skill_folder(self):
        old_flag = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        sys.path.insert(0, SCRIPTS)
        try:
            for name in NEW_SCRIPTS:
                mod = importlib.import_module(os.path.splitext(name)[0])
                self.assertTrue(os.path.samefile(mod.__file__, os.path.join(SCRIPTS, name)), name)
        finally:
            sys.path.remove(SCRIPTS)
            sys.dont_write_bytecode = old_flag


# --------------------------------------------------------------------------- 2. command lines
class CommandLines(TmpCase):

    def test_help_exits_zero_and_prints_a_docstring(self):
        for name in CLIS:
            r = run(name, "--help", cwd=self.tmp)
            self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
            self.assertIn(os.path.splitext(name)[0], r.stdout + r.stderr, name)

    def test_no_arguments_is_the_documented_usage_exit(self):
        for name, code in CLIS.items():
            r = run(name, cwd=self.tmp)
            self.assertEqual(r.returncode, code, f"{name}: {r.stdout} {r.stderr}")
            self.assertIn("usage", (r.stdout + r.stderr).lower(), name)

    def test_missing_input_files_exit_one(self):
        gone = self.p("gone.x")
        for name, args in (("pcf_prep.py", [self.p("gone.json")]), ("pcf2caesar.py", [self.p("gone.json")]),
                           ("ap_bendcheck.py", [gone]), ("pcf_pieces.py", [gone]),
                           ("nwc_supports.py", [gone, "-o", self.p("o.csv")])):
            r = run(name, *args, cwd=self.tmp)
            self.assertEqual(r.returncode, 1, f"{name}: {r.stdout} {r.stderr}")


# --------------------------------------------------------------------------- 3a. pcf_prep.py
class PcfPrep(TmpCase):

    def minimal_job(self):
        write(self.p("exports", "model.pcf"), revit_style_pcf())
        return dump_json(self.p("min.job.json"), {"pcf_globs": ["exports/model.pcf"], "output_dir": "out",
                                                  "output_stem": "m"})

    def test_minimal_job_runs_clean_and_heals_the_model(self):
        r = run("pcf_prep.py", self.minimal_job(), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = self.p("out", "m.pcf")
        with open(out, "rb") as fh:
            raw = fh.read()
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"), "CRLF line endings")
        text = raw.decode("latin-1")
        self.assertNotIn("Shop Weld", text)
        self.assertIn("PIPELINE-REFERENCE m", text)
        rep = load_json(self.p("out", "m_report.json"))
        self.assertEqual(rep["heal"]["weld_couplings_removed"], 1)
        self.assertGreaterEqual(rep["heal"]["joints_closed"], 1)
        self.assertGreaterEqual(rep["connectivity_before"]["near_miss_pairs"], 1)
        self.assertEqual(rep["connectivity_after"]["near_miss_pairs"], 0)
        self.assertEqual(rep["connectivity_after"]["networks"], 1)
        self.assertEqual(rep["output"]["records"].get("FLANGE"), 1)

    def test_missing_pcf_matches_exit_one(self):
        dump_json(self.p("job.json"), {"pcf_globs": ["exports/none*.pcf"], "output_dir": "out"})
        r = run("pcf_prep.py", self.p("job.json"), cwd=self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def example_run(self, extra_rule):
        job = load_json(os.path.join(EXAMPLES, "revit-to-autopipe.job.json"))
        write(self.p("exports", "SUPPLY.pcf"), revit_style_pcf())
        write(self.p("sup.csv"), "cls,family,system,guid,level,x_ft,y_ft,z_ft,has_xyz\n"
                                 "CLEVIS,Clevis X,SUPPLY,ABCDEFGHIJKLMNOPQRSTUV,L1,2.0,0.0,0.05,True\n")
        write(self.p("items.csv"), "name,name2,system,x_ft,y_ft,z_ft\n")
        job.update(pcf_globs=["exports/SUPPLY.pcf"], supports_csv="sup.csv", nwc_items_csv="items.csv")
        if extra_rule:
            job["boundary_rules"].append({"name": "Open pipe end", "match": {"rtype": "PIPE"}, "action": "FREE",
                                          "note": "VFY"})
        return run("pcf_prep.py", dump_json(self.p("ex.job.json"), job), cwd=self.tmp)

    def test_shipped_example_job_is_accepted_and_reports_the_unmatched_free_end(self):
        r = self.example_run(False)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)          # built, review items: documented exit 2
        self.assertIn("free ends not matched by a boundary rule", r.stdout)
        rep = load_json(self.p("out", "model_A_report.json"))
        self.assertEqual(rep["supports"]["placed"], 1)
        self.assertEqual(rep["supports"]["by_class"], {"CLEVIS": 1})
        for suffix in ("_supports.csv", "_free_ends.csv", "_report.json"):
            self.assertTrue(os.path.isfile(self.p("out", "model_A" + suffix)), suffix)
        with open(self.p("out", "model_A.pcf"), encoding="latin-1") as fh:
            text = fh.read()
        self.assertIn("COMPONENT-ATTRIBUTE1 SET-ME", text)              # placeholder system data is carried
        self.assertIn("NAME CLV-QRSTUV", text)                          # tag_prefix from support_rules

    def test_shipped_example_job_exits_zero_once_every_free_end_has_a_rule(self):
        r = self.example_run(True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_shipped_example_without_its_exports_fails_cleanly(self):
        r = run("pcf_prep.py", os.path.join(EXAMPLES, "revit-to-autopipe.job.json"), cwd=self.tmp)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no PCF files matched", r.stdout + r.stderr)

    def test_no_project_defaults_are_left_in_the_module(self):
        sys.path.insert(0, SCRIPTS)
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            pcf_prep = importlib.import_module("pcf_prep")
        finally:
            sys.path.remove(SCRIPTS)
            sys.dont_write_bytecode = old
        pat = pcf_prep.not_inline_re()
        self.assertTrue(pat.match("Pipe-CS"))
        self.assertIsNone(pat.match("Y-Strainer 4in"))
        self.assertTrue(pcf_prep.not_inline_re("Pump Skid").match("pump skid base"))


# --------------------------------------------------------------------------- 3b. pcf2caesar.py
class Pcf2Caesar(TmpCase):

    def minimal_job(self, **more):
        write(self.p("SUPPLY.pcf"), caesar_supply_pcf())
        write(self.p("RETURN.pcf"), caesar_return_pcf())
        job = {"outdir": "out", "name": "m", "model": "MA",
               "pcf_files": {"SUP": "SUPPLY.pcf", "RET": "RETURN.pcf"},
               "models": {"MA": ["SUP", "RET"]},
               "lines": {"LNS": {"files": ["SUP"]}, "LNR": {"files": ["RET"]}},
               "span_table_ft": [[2, 10], [30, 10]]}
        job.update(more)
        return dump_json(self.p("min.job.json"), job)

    def test_minimal_job_converts_and_places_supports(self):
        r = run("pcf2caesar.py", self.minimal_job(), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in ("m_LNS.pcf", "m_LNR.pcf", "m_combined.pcf", "m_supports.csv", "m_report.json", "m.log"):
            self.assertTrue(os.path.isfile(self.p("out", name)), name)
        with open(self.p("out", "m_combined.pcf"), "rb") as fh:
            raw = fh.read()
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
        text = raw.decode("latin-1")
        self.assertIn("BEND\r\n", text)                                  # ELBOW -> BEND
        self.assertIn("COUPLING (as PIPE)", text)                       # COUPLING -> PIPE
        self.assertIn("NAME PTS-", text)                                # default support_prefix
        self.assertNotIn("PROJECT-IDENTIFIER", text)                    # defaults are empty
        self.assertNotIn("AREA ", text)
        rep = load_json(self.p("out", "m_report.json"))
        self.assertEqual(rep.get("errors", []), [])
        self.assertEqual(rep["component_counts"].get("BEND"), 1)
        self.assertGreaterEqual(rep["support_counts"].get("HGR", 0), 1)

    def test_job_keys_replace_the_old_hard_coded_names(self):
        job = self.minimal_job(support_prefix="ZZ", project_identifier="PID-1", area="AREA-1")
        r = run("pcf2caesar.py", job, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(self.p("out", "m_LNS.pcf"), encoding="latin-1") as fh:
            text = fh.read()
        self.assertIn("    PROJECT-IDENTIFIER PID-1", text)
        self.assertIn("    AREA AREA-1", text)
        self.assertIn("NAME ZZ-", text)
        self.assertNotIn("NAME PTS-", text)

    def test_shipped_example_job_runs_on_synthetic_exports(self):
        job = load_json(os.path.join(EXAMPLES, "revit-to-caesar.job.json"))
        write(self.p("exports", "SUPPLY.pcf"), caesar_supply_pcf())
        write(self.p("exports", "RETURN.pcf"), caesar_return_pcf())
        r = run("pcf2caesar.py", dump_json(self.p("ex.job.json"), job), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(self.p("out", "example_model_a_combined.pcf"), encoding="latin-1") as fh:
            text = fh.read()
        self.assertIn("PROJECT-IDENTIFIER EXAMPLE-PROJECT-ID", text)
        rep = load_json(self.p("out", "example_model_a_report.json"))
        self.assertTrue(any(e["kind"] == "EQUIP" and "EXAMPLE equipment nozzle" in e["tag"] for e in rep["ends"]))

    def test_pcf_pieces_reads_the_output(self):
        run("pcf2caesar.py", self.minimal_job(), cwd=self.tmp)
        r = run("pcf_pieces.py", self.p("out", "m_combined.pcf"), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("piece 0:", r.stdout)
        self.assertIn("PTS-HGR", r.stdout)

    def test_unhandled_record_types_are_reported_with_exit_two(self):
        # pcf2caesar converts PIPE, COUPLING, ELBOW/BEND, TEE, REDUCER-CONCENTRIC and VALVE only (Revit writes
        # flanges as COUPLING). A FLANGE record is listed under report errors and the run exits 2; a SUPPORT
        # record has no end points and is skipped with a warning.
        job = self.minimal_job()
        write(self.p("SUPPLY.pcf"), revit_style_pcf())        # the file with FLANGE and SUPPORT records
        r = run("pcf2caesar.py", job, cwd=self.tmp)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        errors = load_json(self.p("out", "m_report.json"))["errors"]
        self.assertTrue(any("unhandled record FLANGE" in e for e in errors), errors)
        self.assertIn("skipped 1 record(s) without connection points", r.stderr)

    def test_bad_jobs_exit_one_with_the_failing_key_named(self):
        job = load_json(self.minimal_job())
        del job["span_table_ft"]
        r = run("pcf2caesar.py", dump_json(self.p("nospan.json"), job), cwd=self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("span_table_ft", r.stderr)
        job["span_table_ft"] = [[2, 10]]
        job["pcf_files"] = {"SUP": "does-not-exist.pcf"}
        r = run("pcf2caesar.py", dump_json(self.p("nofile.json"), job), cwd=self.tmp)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FileNotFoundError", r.stderr)

    def test_model_box_drops_outside_records_and_cuts_straddling_ones(self):
        job = load_json(self.minimal_job())
        job["box_ft"] = [-1.0, 10.0, -1.0, 1.0]                  # list form: xmin, xmax, ymin, ymax
        r = run("pcf2caesar.py", dump_json(self.p("box.json"), job), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rep = load_json(self.p("out", "m_report.json"))
        self.assertEqual(rep["revit_elements_in"], 3)             # pipe, coupling, elbow; the rest is outside or crosses
        self.assertTrue(any(e["kind"] == "CUT" for e in rep["ends"]), rep["ends"])
        job["box_ft"] = {"xmin": -1.0, "xmax": 10.0, "ymin": -1.0, "ymax": 1.0}      # dict form
        run("pcf2caesar.py", dump_json(self.p("box2.json"), job), cwd=self.tmp)
        self.assertEqual(load_json(self.p("out", "m_report.json"))["revit_elements_in"], 3)
        del job["box_ft"]                                          # no box: everything is in
        run("pcf2caesar.py", dump_json(self.p("box3.json"), job), cwd=self.tmp)
        self.assertEqual(load_json(self.p("out", "m_report.json"))["revit_elements_in"], 5)

    def test_two_models_split_by_exclusive_tags(self):
        job = load_json(self.minimal_job())
        job["models"] = {"MA": ["SUP"], "MB": ["RET"]}
        job["model"] = "MB"
        r = run("pcf2caesar.py", dump_json(self.p("two.json"), job), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(load_json(self.p("out", "m_report.json"))["revit_elements_in"], 1)


# --------------------------------------------------------------------------- 4. NTL closures
def ntl(lines):
    return "\r\n".join(lines) + "\r\n"


def card(key, name, dx, dy, dz, extra=""):
    return f"{key:<5}{name:<15}{dx:10.3f}{dy:10.3f}{dz:10.3f}{extra}"


def looped_ntl():
    """A square loop P1 -> P2 -> P3 -> P4 -> P1 whose closing point P1 carries a flange."""
    return ntl([
        "RVER 2.3",
        card("SEG", "P1", 0.0, 0.0, 0.0),
        "PIPE 4.000",
        card("RUN", "P2", 10.0, 0.0, 0.0),
        card("RUN", "P3", 0.0, 10.0, 0.0),
        card("RUN", "P4", -10.0, 0.0, 0.0),
        card("RUN", "P1", 0.0, -10.0, 0.0),
        card("FLA", "P1", 0.0, 0.0, 0.0),
        "***",
    ])


class NtlClosures(TmpCase):

    def test_lists_the_closure_on_the_flange_point(self):
        path = self.p("loop.ntl")
        with open(path, "wb") as fh:
            fh.write(looped_ntl().encode("latin-1"))
        r = run("ntl_closures.py", path, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("loop.ntl closures: 1", r.stdout)
        self.assertIn("point P1", r.stdout)
        self.assertIn("closed by RUN", r.stdout)
        self.assertIn("'FLA'", r.stdout)

    def test_fix_closures_moves_the_closure_to_a_plain_pipe_point(self):
        src = self.p("loop.ntl")
        with open(src, "wb") as fh:
            fh.write(looped_ntl().encode("latin-1"))
        dst = self.p("fixed.ntl")
        r = run("fix_closures.py", src, dst, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("closure moved: P1 -> P4", r.stdout)
        self.assertIn("fixed 1", r.stdout)
        with open(dst, "rb") as fh:
            out = fh.read().decode("latin-1")
        lines = out.split("\r\n")
        seg = [ln for ln in lines if ln.startswith("SEG ")]
        self.assertEqual(len(seg), 1)
        self.assertEqual(seg[0].split()[1], "P4")                   # the loop now starts (and closes) at P4
        coords = [float(v) for v in seg[0].split()[2:5]]
        self.assertEqual(coords, [0.0, 10.0, 0.0])                  # P1 (0,0,0) minus the closing delta (0,-10,0)
        i_flange = next(i for i, ln in enumerate(lines) if ln.startswith("FLA "))
        i_p2 = next(i for i, ln in enumerate(lines) if ln.startswith("RUN  P2"))
        self.assertLess(i_flange, i_p2)                              # RUN P1 + FLA P1 moved to the start of the segment
        # the corrected file has no closure left on a flange: ntl_closures lists P4 with no FLA
        r2 = run("ntl_closures.py", dst, cwd=self.tmp)
        self.assertIn("closures: 1", r2.stdout)
        self.assertIn("point P4", r2.stdout)
        self.assertNotIn("'FLA'", r2.stdout)
        # and a second pass changes nothing
        r3 = run("fix_closures.py", dst, self.p("fixed2.ntl"), cwd=self.tmp)
        self.assertIn("fixed 0", r3.stdout)


# --------------------------------------------------------------------------- 5. bend check
class BendCheck(TmpCase):

    def elbow_pcf(self, t2):
        b = []
        b += rec("PIPE", [(0, 0, 0), (100, 0, 0)], ["ITEM-DESCRIPTION Pipe"], rid=1)
        b += rec("ELBOW", [(100, 0, 0), (106, t2, 0)], ["ITEM-DESCRIPTION Elbow"], centre=(106, 0, 0), rid=2)
        b += rec("PIPE", [(106, t2, 0), (106, 100, 0)], ["ITEM-DESCRIPTION Pipe"], rid=3)
        return write(self.p("b.pcf"), HDR + "\n".join(b) + "\n")

    def test_long_radius_elbow_with_equal_legs_is_clean(self):
        r = run("ap_bendcheck.py", self.elbow_pcf(6), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 elbows written L, 0 explicit R", r.stdout)
        self.assertIn("E726-15 undefined bends: 0", r.stdout)
        self.assertIn("W726-8 kinks > 1.00 deg: 0", r.stdout)

    def test_unequal_legs_are_flagged_as_an_undefined_bend(self):
        # legs 6 and 4 in: the translator writes R = 5 in, whose 5 in tangent overshoots the 4 in leg by 1 in
        r = run("ap_bendcheck.py", self.elbow_pcf(4), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 elbows written L, 1 explicit R", r.stdout)
        self.assertIn("E726-15 undefined bends: 1", r.stdout)
        self.assertIn("short by 1.000 in", r.stdout)

    def test_ntl_mode(self):
        def bend_ntl(radius):
            return ntl(["RVER 2.3", card("SEG", "A", 0.0, 0.0, 0.0), "PIPE 4.000",
                        card("RUN", "B", 5.0, 0.0, 0.0), card("BEND", "C", 0.5, 0.0, 0.0, f"{radius:<10}"),
                        card("RUN", "D", 0.0, 5.0, 0.0), "***"])
        with open(self.p("l.ntl"), "wb") as fh:
            fh.write(bend_ntl("L").encode("latin-1"))
        r = run("ap_bendcheck.py", self.p("l.ntl"), cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("E726-15 undefined bends: 0", r.stdout)
        with open(self.p("l.ntl"), "wb") as fh:
            fh.write(bend_ntl("30.0").encode("latin-1"))
        r = run("ap_bendcheck.py", self.p("l.ntl"), "--verbose", cwd=self.tmp)
        self.assertIn("E726-15 undefined bends: 1", r.stdout)
        self.assertIn("bend margins", r.stdout)


# --------------------------------------------------------------------------- 6. NWC support miner
def synthetic_nwc(path):
    """A '#LcUStream' file holding one zlib chunk laid out the way nwc_supports.py documents:
    strings, the marker 'By Type', more strings, and a little-endian float64 XYZ triple (ft)."""
    def s(txt):
        return txt.encode("ascii") + b"\x00"
    rec_ = (s("Revit Family") + s("Adjustable Trapeze Hanger A") + s("MEP Fabrication Hangers") + s("By Type")
            + s("Piping Systems: Example Water Supply") + s("Level : L1") + s("AbCdEfGhIjKlMnOpQrStUv")
            + b"\x00" * 3 + struct.pack("<ddd", 10.5, 20.25, 30.125) + b"\x00" * 16)
    blob = b"\x00" * 64 + rec_ + b"\x00" * 64
    with open(path, "wb") as fh:
        fh.write(b"#LcUStream" + b"\x00" * 6 + zlib.compress(blob))
    return path


class NwcSupports(TmpCase):

    def setUp(self):
        super().setUp()
        sys.path.insert(0, SCRIPTS)
        self.addCleanup(lambda: sys.path.remove(SCRIPTS))
        old = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        self.addCleanup(lambda: setattr(sys, "dont_write_bytecode", old))
        self.nwc = importlib.import_module("nwc_supports")

    def test_classifier_uses_the_generic_defaults_and_the_category_rule(self):
        fam = dict(self.nwc.DEFAULT_FAMILIES)
        self.assertEqual(self.nwc.classify(["Revit Family", "Clevis Hanger 4in"], fam), ("Clevis Hanger 4in", "CLEVIS"))
        self.assertEqual(self.nwc.classify(["x", "Trapeze A", "MEP Fabrication Hangers"], fam), ("Trapeze", "TRAPEZE"))
        self.assertIsNone(self.nwc.classify(["Pump", "Skid"], fam))
        key, cls = self.nwc.classify(["x", "unnamed", "MEP Fabrication Hangers"], fam)
        self.assertEqual(cls, "TRAPEZE")                            # category only: inferred, flagged in the name
        self.assertIn("inferred", key)
        fam["Floor Stand"] = "STAND"
        self.assertEqual(self.nwc.classify(["Floor Stand 3"], fam)[1], "STAND")

    def test_first_xyz_honours_the_elevation_window(self):
        buf = b"\x00" * 8 + struct.pack("<ddd", 1.5, 2.5, 3.5) + b"\x00" * 8
        self.assertEqual(self.nwc.first_xyz(buf, 0, len(buf), 0.0, 10.0, 100.0), (1.5, 2.5, 3.5))
        self.assertIsNone(self.nwc.first_xyz(buf, 0, len(buf), 50.0, 60.0, 100.0))

    def test_end_to_end_on_a_synthetic_stream(self):
        # NOT a real NWC: a stream built from the layout the script documents, to exercise inflate, mine and the CSV.
        nwc = synthetic_nwc(self.p("m.nwc"))
        fam = self.p("fam.json")
        with open(os.path.join(EXAMPLES, "nwc-families.example.json"), encoding="utf-8") as fh, \
                open(fam, "w", encoding="utf-8") as out:
            out.write(fh.read())
        r = run("nwc_supports.py", nwc, "-o", self.p("s.csv"), "--items-out", self.p("i.csv"),
                "--families", fam, "--zmin", "29", "--zmax", "31", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(self.p("s.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cls"], "TRAPEZE")
        self.assertEqual((rows[0]["x_ft"], rows[0]["y_ft"], rows[0]["z_ft"]), ("10.5", "20.25", "30.125"))
        self.assertEqual(rows[0]["guid"], "AbCdEfGhIjKlMnOpQrStUv")
        self.assertEqual(rows[0]["level"], "L1")
        with open(self.p("i.csv"), newline="", encoding="utf-8") as fh:
            items = list(csv.DictReader(fh))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["z_ft"], "30.125")
        self.assertEqual(list(items[0].keys()), ["name", "name2", "system", "x_ft", "y_ft", "z_ft"])

    def test_the_csv_feeds_pcf_prep(self):
        # nwc_supports.py output -> pcf_prep.py supports_csv: the column names must line up
        nwc = synthetic_nwc(self.p("m.nwc"))
        r = run("nwc_supports.py", nwc, "-o", self.p("s.csv"), "--zmin", "29", "--zmax", "31", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # the synthetic support sits at x = 10.5 ft, y = 20.25 ft (243 in), z = 30.125 ft: put a pipe under it
        b = rec("PIPE", [(0, 243, 360.0), (240, 243, 360.0)], ["ITEM-DESCRIPTION Pipe"], rid=1)
        write(self.p("exports", "line.pcf"), HDR + "\n".join(b) + "\n")
        dump_json(self.p("job.json"), {
            "pcf_globs": ["exports/line.pcf"], "output_dir": "out", "output_stem": "n", "supports_csv": "s.csv",
            "support_rules": {"TRAPEZE": {"max_horiz_in": 2.0, "min_dz_in": -2.0, "max_dz_in": 2.0,
                                          "multi_pipe": False, "tag_prefix": "TRP"}}})
        r = run("pcf_prep.py", self.p("job.json"), cwd=self.tmp)
        self.assertIn(r.returncode, (0, 2), r.stdout + r.stderr)
        rep = load_json(self.p("out", "n_report.json"))
        self.assertEqual(rep["supports"]["placed"], 1, rep["supports"])
        self.assertEqual(rep["supports"]["by_class"], {"TRAPEZE": 1})


# --------------------------------------------------------------------------- 7. example files
class Examples(unittest.TestCase):

    AUTOPIPE_KEYS = (
        "name", "pcf_globs", "output_dir", "output_stem", "pipeline_reference", "assumed", "box_ft", "clip_mode",
        "heal_tol_in", "min_segment_in", "weld_match", "fuse_rtypes", "retype", "flange_map", "normalize_elbows",
        "elbow_margin_in", "straighten_max_dev_in", "valve_weights", "systems", "desc_schedule_tag", "nwc_items_csv",
        "bridge", "not_inline_extra_regex", "three_way", "supports_csv", "support_system_match", "support_rules",
        "support_desc_max", "support_skey_override", "infill", "boundary_rules", "drop_fragments_max_components",
        "expected_collapse_match", "pcf_pipe_match", "nwc_pipe_name_prefix",
    )
    CAESAR_KEYS = (
        "name", "outdir", "pcf_dir", "pcf_files", "box_ft", "models", "model", "unassigned_by_bore", "lines",
        "small_bore_max", "chiller_body_bore_in", "chiller_tag_prefix", "chiller_port_lines", "end_overrides",
        "equipment_ff_ft", "base_bend_max_above_ff_ft", "base_walk_max_ft", "near_support_max_ft", "near_nozzle_in",
        "riser_floors_ft", "riser_clamp_above_floor_ft", "riser_max_ft", "span_table_ft", "merge_in",
        "tee_carry_ratio", "near_tee_in", "no_support_below_ft", "support_prefix", "project_identifier", "area",
    )

    def test_examples_are_valid_json_with_every_documented_key_and_a_comment_for_each(self):
        for fname, keys in (("revit-to-autopipe.job.json", self.AUTOPIPE_KEYS), ("revit-to-caesar.job.json", self.CAESAR_KEYS)):
            job = load_json(os.path.join(EXAMPLES, fname))
            for k in keys:
                self.assertIn(k, job, f"{fname}: {k}")
                self.assertIn("_comment_" + k, job, f"{fname}: no comment for {k}")
                self.assertIsInstance(job["_comment_" + k], str)
            self.assertIn("_comment", job)

    def test_every_documented_key_is_read_by_the_script(self):
        for script, keys in (("pcf_prep.py", self.AUTOPIPE_KEYS), ("pcf2caesar.py", self.CAESAR_KEYS)):
            with open(os.path.join(SCRIPTS, script), encoding="utf-8") as fh:
                text = fh.read()
            # the keys are read from the job dict, directly or by a helper module of the same tool
            for helper in ("pcf_union.py", "pcf_split.py"):
                if script == "pcf2caesar.py":
                    with open(os.path.join(SCRIPTS, helper), encoding="utf-8") as fh:
                        text += fh.read()
            for k in keys:
                self.assertTrue(f"'{k}'" in text or f'"{k}"' in text, f"{script} never reads {k}")

    def test_no_example_carries_a_real_looking_value(self):
        for fname in NEW_EXAMPLES:
            with open(os.path.join(EXAMPLES, fname), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotRegex(text, r"[A-Za-z]:\\")
            self.assertIn("PLACEHOLDER", text, fname)

    def test_families_example_loads_through_the_script_option(self):
        data = load_json(os.path.join(EXAMPLES, "nwc-families.example.json"))
        classes = {v for k, v in data.items() if not k.startswith("_")}
        self.assertTrue({"STAND", "ROLLER", "RISER"} <= classes)


if __name__ == "__main__":
    unittest.main()
