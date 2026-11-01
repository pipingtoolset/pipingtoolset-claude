"""Tests for the pipe-support modules that are new in the plugin (not ports): ASCE 7-22
load combinations, AISC J3/J4 bolts, J2 / D1.1 detailing, the optimizer, the reviewer,
the report and the CLI.

Standard library only:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support")
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import content_guard  # noqa: E402
import support_calc  # noqa: E402
from pipe_support import bolts as B  # noqa: E402
from pipe_support import detailing as DT  # noqa: E402
from pipe_support import loads as LD  # noqa: E402
from pipe_support import optimizer as OP  # noqa: E402
from pipe_support.common import InputError  # noqa: E402

EX = os.path.join(SCRIPTS, "examples")


def load(name):
    with open(os.path.join(EX, name), encoding="utf-8") as fh:
        return _esr_category(json.load(fh), name)


def _esr_category(s, name):
    """ps-201 leaves the ACI 355.2/355.4 Anchor Category unset, so at the ACI CODE-318-25 default
    the engine takes Category 3 (psi_a 0.60) and the anchorage FAILS (1.1356 LRFD; 0.9.0). Tests whose
    subject is not the anchorage enter Category 1, as an engineer would from the anchor's ESR;
    PS201Category3 in test_pipe_support_skill.py runs the example as shipped."""
    if name == "ps-201-caesar.json":
        s.setdefault("design", {}).setdefault("baseplate", {})["anchorCategory"] = 1
    return s


# ------------------------------------------------------------------ loads

class Loads(unittest.TestCase):
    SPEC = {"units": "kip-in", "cases": {"SUS": [0, -2, 0], "OPE": [0.5, -2.2, -0.3],
                                         "WIN": [0, 0, 0.4], "EQ": [0, 0, 0.6]}, "SDS": 0.5}

    def combos(self, method, **kw):
        c, n, cats = LD.combinations({**self.SPEC, **kw}, method)
        return {x["id"]: x for x in c}, n, cats

    def test_categories_and_units(self):
        cats, _ = LD.categories({"cases": {"SUS": [0, -1000, 0, 0, 0, 1200], "OPE": [200, -1100, 0]}})
        self.assertEqual(cats["D"][:3], [0.0, -1.0, 0.0])            # lb -> kip
        self.assertAlmostEqual(cats["D"][5], 14.4)                    # 1200 ft-lb -> 14.4 kip-in
        self.assertEqual([round(x, 9) for x in cats["T"][:3]], [0.2, -0.1, 0.0])   # OPE - SUS

    def test_asce_7_22_lrfd_factors(self):
        c, _, _ = self.combos("LRFD")
        self.assertEqual(c["LRFD-1a"]["factors"], {"D": 1.4})
        self.assertEqual(c["LRFD-5a+"]["factors"], {"D": 0.9, "W": 1.0})
        self.assertEqual(c["LRFD-5a-"]["factors"], {"D": 0.9, "W": -1.0})
        self.assertEqual(c["LRFD-6+"]["factors"], {"D": 1.2, "Ev": 1.0, "Eh": 1.0, "L": 1.0})
        self.assertEqual(c["LRFD-7-"]["factors"], {"D": 0.9, "Ev": -1.0, "Eh": -1.0})
        self.assertIn("LRFD-1a+T", c)                                 # T variants present
        self.assertIn("LRFD-1a", c)                                   # and T-absent variants

    def test_asce_7_22_asd_factors(self):
        c, _, _ = self.combos("ASD")
        self.assertEqual(c["ASD-6a+"]["factors"]["W"], 0.45)          # 0.75 x 0.6W
        self.assertEqual(c["ASD-7a+"]["factors"], {"D": 0.6, "W": 0.6})
        self.assertEqual(c["ASD-9+"]["factors"]["Eh"], 0.525)
        self.assertEqual(c["ASD-10+"]["factors"]["Ev"], -0.7)

    def test_ev_from_sds(self):
        _, _, cats = self.combos("LRFD")
        self.assertAlmostEqual(cats["Ev"][1], 0.2 * 0.5 * -2)

    def test_t_factor_floors(self):
        with self.assertRaises(InputError):
            LD.combinations({**self.SPEC, "T_factor": 0.9}, "LRFD")
        with self.assertRaises(InputError):
            LD.combinations({**self.SPEC, "T_factor": 0.7}, "ASD")
        LD.combinations({**self.SPEC, "T_factor": 0.75}, "ASD")

    def test_support_demand_sign_convention(self):
        d = LD.support_demands([0.3, -2.0, -0.4, 0, 0, 0], "Y", "X")
        self.assertEqual(d["vertical"], 2.0)          # CAESAR -Y on the restraint = down
        self.assertEqual(d["longitudinal"], 0.3)      # along the pipe (X)
        self.assertEqual(d["transverse"], 0.4)        # across the pipe -> along the arm
        self.assertLess(LD.support_demands([0, 1.5, 0], "Y", "X")["vertical"], 0)   # uplift

    def test_minimum_dead_with_thermal_governs_uplift(self):
        # T opposing D: 0.9D + T (LRFD) and 0.6D + T (ASD) must exist (2.3.1 / 2.4.1 "not acting")
        spec = {"cases": {"SUS": [0, -1000, 0], "OPE": [0, 500, 0]}}
        for m, want in (("LRFD", 0.6), ("ASD", 0.9)):
            c, _, _ = LD.combinations(spec, m)
            up = -min(LD.support_demands(x["vector"])["vertical"] for x in c)
            self.assertAlmostEqual(up, want, places=9, msg=m)

    def test_ev_is_vertical_only_and_sign_checks(self):
        cats, notes = LD.categories({"units": "kip-in", "cases": {"SUS": [0.5, -2, 0.3], "EQ": [0, -2, 1]}, "SDS": 1.0})
        self.assertEqual(cats["Ev"], [0.0, -0.4, 0.0, 0.0, 0.0, 0.0])
        self.assertTrue(any("combined OCC case" in n for n in notes))
        _, notes = LD.categories({"cases": {"SUS": [0, 900, 0]}})
        self.assertTrue(any("sign convention" in n for n in notes))

    def test_hydrotest_and_missing_sus(self):
        c, _, _ = LD.combinations({"units": "kip-in", "cases": {"SUS": [0, -1, 0], "HYD": [0, -3, 0]}}, "LRFD")
        hyd = [x for x in c if x["id"] == "LRFD-HYD"][0]
        self.assertAlmostEqual(hyd["vector"][1], -4.2)
        with self.assertRaises(InputError):
            LD.categories({"cases": {"OPE": [0, -1, 0]}})


# ------------------------------------------------------------------ bolts

class Bolts(unittest.TestCase):
    BASE = {"method": "LRFD", "grade": "A325", "d": 0.75, "nBolts": 1, "rows": 1, "cols": 1,
            "edgeLoaded": 2.0, "edgeSide": 2.0,
            "plies": [{"t": 1.0, "Fy": 50, "Fu": 65}], "V": 1.0}

    def single(self, **kw):
        r = B.bolt_group({**self.BASE, **kw})
        return {c["check"]: c for c in r["output"]["checks"]}

    def test_manual_table_7_1_single_shear(self):
        # AISC Manual Table 7-1: 3/4 in Group A-N 17.9 kip, -X 22.5 kip; Group B-N 22.5 kip
        self.assertAlmostEqual(self.single()["Bolt shear"]["capacity"], 17.9, delta=0.05)
        self.assertAlmostEqual(self.single(threads="X")["Bolt shear"]["capacity"], 22.5, delta=0.05)
        self.assertAlmostEqual(self.single(grade="A490")["Bolt shear"]["capacity"], 22.5, delta=0.05)
        self.assertAlmostEqual(self.single(shearPlanes=2)["Bolt shear"]["capacity"], 35.8, delta=0.05)

    def test_bearing_and_tearout(self):
        c = self.single()["Bearing / tear-out (ply)"]
        # lc = 2.0 - 13/32 = 1.59375 -> 1.2 lc t Fu = 124.3 > 2.4 d t Fu = 117 -> bearing governs
        self.assertAlmostEqual(c["capacity"], 0.75 * 2.4 * 0.75 * 1.0 * 65, places=3)

    def test_tension_shear_interaction_reduces_tension(self):
        free = B.bolt_group({**self.BASE, "V": 0.001, "T": 10})["output"]["checks"]
        loaded = B.bolt_group({**self.BASE, "V": 15, "T": 10})["output"]["checks"]
        cap = lambda rows: [c for c in rows if c["check"].startswith("Bolt tension")][0]["capacity"]  # noqa: E731
        self.assertAlmostEqual(cap(free), 0.75 * 90 * math.pi * 0.75 ** 2 / 4, places=2)   # Fnt' capped at Fnt
        self.assertLess(cap(loaded), cap(free))

    def test_edge_and_spacing_detailing(self):
        r = B.bolt_group({**self.BASE, "nBolts": 2, "rows": 2, "spacing": 1.9, "edgeLoaded": 0.875})
        msgs = " ".join(d["message"] for d in r["output"]["detailing"])
        self.assertIn("2 2/3 d", msgs)
        self.assertIn("Table J3.4 minimum 1", msgs)
        self.assertEqual(r["status"], "fail")
        self.assertEqual(B.min_edge_distance(0.875), 1.125)
        self.assertEqual(B.hole_diameter(1.0), 1.125)

    def test_fillet_length_and_beta_cap(self):
        f = DT.fillet_detailing({"size": 0.25, "tThinner": 0.5, "length": 0.75})
        self.assertEqual(f[0]["severity"], "advisory")                     # L < 4w -> effective size L/4
        f = DT.fillet_detailing({"size": 0.25, "tThinner": 0.5, "length": 100, "endLoaded": True})
        self.assertIn("180w = 45 in", f[0]["message"])                    # L/w = 400 > 300

    def test_end_plate_no_prying(self):
        r = B.end_plate_no_prying({"method": "LRFD", "T": 15, "b": 1.75, "d": 0.75, "p": 3, "Fu": 58, "t": 0.75})
        self.assertAlmostEqual(r["output"]["tmin"], math.sqrt(4 * 15 * 1.375 / (0.9 * 3 * 58)), places=4)


# ------------------------------------------------------------------ detailing

class Detailing(unittest.TestCase):

    def test_table_j2_4_and_j2_3(self):
        self.assertEqual([DT.min_fillet(t) for t in (0.25, 0.375, 0.625, 1.25)], [1 / 8, 3 / 16, 1 / 4, 5 / 16])
        self.assertEqual(DT.min_pjp_throat(1.0), 5 / 16)
        self.assertEqual(DT.min_pjp_throat(3.0), 1 / 2)

    def test_fillet_findings(self):
        f = DT.fillet_detailing({"size": 0.125, "tThinner": 0.5, "tEdge": 0.5, "length": 0.4,
                                 "FEXX": 60, "baseGrade": "A992", "field": True, "position": "overhead"})
        sev = [x["severity"] for x in f]
        self.assertGreaterEqual(sev.count("violation"), 2)          # min size, filler (short length = advisory)
        self.assertIn("constructability", sev)
        self.assertEqual(DT.fillet_detailing({"size": 0.25, "tThinner": 0.375, "length": 6}), [])

    def test_pjp_groove(self):
        r = DT.groove_weld({"method": "LRFD", "type": "PJP", "throat": 0.25, "length": 6, "tThinner": 1.0,
                            "FEXX": 70, "baseFy": 50, "baseFu": 65, "Tn": 30})
        self.assertEqual(r["status"], "fail")                        # throat below Table J2.3 5/16
        self.assertAlmostEqual(r["output"]["checks"][0]["capacity"], 0.8 * 0.6 * 70 * 1.5, places=4)


# ------------------------------------------------------------------ optimizer, review, CLI

class EndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = load("ps-201-caesar.json")
        cls.doc = support_calc.run(cls.spec)

    def test_envelope_is_the_worst_combination(self):
        env = self.doc["envelope"]
        sets, _ = OP.demand_sets(self.spec, "LRFD")
        design = support_calc.resolve_design(self.spec)
        singles = [OP.envelope(design, [s], self.spec)["governingRatio"] for s in sets]
        self.assertAlmostEqual(env["governingRatio"], max(singles))
        self.assertEqual(env["combosRun"], len(sets))

    def test_every_alternative_passes_and_is_ranked(self):
        alts = self.doc["optimizer"]["alternatives"]
        self.assertGreaterEqual(len(alts), 3)
        for a in alts:
            self.assertLessEqual(a["governingRatio"], 1.0)
        self.assertEqual([a["rank"] for a in alts], list(range(1, len(alts) + 1)))
        self.assertEqual(sorted(a["score"] for a in alts), [a["score"] for a in alts])

    def test_optimizer_max_ratio_is_respected(self):
        spec = copy.deepcopy(self.spec)
        spec["optimize"] = {**spec["optimize"], "maxRatio": 0.8}
        alts = support_calc.run(spec)["optimizer"]["alternatives"]
        self.assertTrue(alts)
        self.assertTrue(all(a["governingRatio"] <= 0.8 for a in alts))

    def test_alternatives_respect_weld_limits_and_seed_as_drawn(self):
        alts = self.doc["optimizer"]["alternatives"]
        for a in alts:
            self.assertNotIn("as drawn", a["governingStage"])
        # as drawn (1/4 in fillet on a 0.23 in web) breaks J2.2b, so it must NOT be offered...
        self.assertFalse(any(a["asDrawn"] for a in alts))
        # ...but a compliant as-drawn design competes with the searched alternatives
        spec = copy.deepcopy(self.spec)
        spec["design"]["weldSize"] = 0.1875
        spec["optimize"] = {"includeDesigns": True, "top": 30}
        out = support_calc.run(spec)["optimizer"]["alternatives"]
        self.assertTrue(any(a["asDrawn"] for a in out))
        for a in out:
            env = OP.envelope(a["design"], OP.demand_sets(spec, "LRFD")[0], spec)
            self.assertFalse([w for w in env["warnings"] if "exceeds the J2.2b maximum" in w], a["arms"])

    def test_bolted_alternative_checks_the_tension_row(self):
        from pipe_support import review as RV
        env = {"stages": [{"component": "arm", "checks": [{"label": "Flexure, major axis", "demand": 600},
                                                          {"label": "Shear, major axis", "demand": 5},
                                                          {"label": "Axial compression", "demand": 0}]}]}
        alt = RV.bolted_arm_alternative({"arms": [{"shape": "W6X15"}]}, env, "LRFD")
        self.assertAlmostEqual(alt["boltTension"], 600 / (5.99 - 0.26 / 2 + 1.5) / 2, places=2)
        cap = 0.75 * 90 * math.pi / 4                                       # 1 in A325, no shear reduction
        self.assertLessEqual(alt["boltTension"] / cap, 1.0)
        self.assertTrue(alt["bolts"].startswith("4 - 1 in"))

    def test_preset_values_are_never_silent(self):
        text = " ".join(self.doc["assumed"])
        self.assertIn("bondStrength = 800 taken from the csa-type-1 preset", text)

    def test_critical_finding_gives_exit_3(self):
        spec = copy.deepcopy(self.spec)
        spec["optimize"] = False
        for p in spec["pipes"]:
            p["loads"]["cases"]["SUS"] = p["loads"]["cases"]["SUS"] + [0, 0, 500]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.json")
            with open(path, "w") as fh:
                json.dump(spec, fh)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(support_calc.main([path, "--quiet"]), 3)

    def test_factored_mode_optimizes_too(self):
        doc = support_calc.run(load("ps-101-factored.json"))
        self.assertTrue(doc["optimizer"]["alternatives"])

    def test_engine_checks_weld_base_metal_on_the_column(self):
        # pipecalcpro #138 / plugin 0.3.1: the engine checks J4 on the thinner (column) element
        # itself, so the 0.3.0 [cross-check] row is retired.
        st = [x for x in self.doc["envelope"]["stages"] if x["component"] == "weld" and "base" in x["stage"].lower()][0]
        rows = {c["label"]: c for c in st["checks"]}
        self.assertIn("Base-metal shear", rows)
        # 0.9.0: the lower of J4-3 yielding (1.00 x 0.6 Fy t) and J4-4 rupture (0.75 x 0.6 Fu t)
        self.assertAlmostEqual(rows["Base-metal shear"]["capacity"], min(1.00 * 0.6 * 36, 0.75 * 0.6 * 58) * 0.23, places=3)
        labels = [c["label"] for s in self.doc["envelope"]["stages"] for c in s["checks"]]
        self.assertFalse([l for l in labels if "cross-check" in l])
        self.assertFalse([f for f in self.doc["findings"] if f.get("source") == "cross-check"])

    def test_pipe_moments_are_a_critical_finding(self):
        spec = copy.deepcopy(self.spec)
        spec["optimize"] = False
        for p in spec["pipes"]:
            p["loads"]["cases"]["SUS"] = p["loads"]["cases"]["SUS"] + [0, 0, 500]
        f = support_calc.run(spec, optimize=False)["findings"]
        self.assertEqual(f[0]["severity"], "critical")
        self.assertIn("moments", f[0]["title"])

    def test_report_sections(self):
        from pipe_support import report as R
        md = R.markdown(self.doc)
        for h in ("## Design basis", "## Loads", "## Reactions at the base plate", "## Limit-state results",
                  "## Compliance matrix", "## Engineering review findings", "## Optimized alternatives",
                  "## Assumptions", "AWS D1.1", "| Unit |"):
            self.assertIn(h, md)
        json.loads(R.to_json(self.doc))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(support_calc.main([os.path.join(EX, "ps-101-factored.json"),
                                                    "--no-optimize", "--quiet"]), 0)
                bad = load("ps-101-factored.json")
                bad["design"]["arms"][0]["pipes"][0]["vertical"] = 60
                p = os.path.join(d, "bad.json")
                with open(p, "w") as fh:
                    json.dump(bad, fh)
                self.assertEqual(support_calc.main([p, "--no-optimize", "--quiet"]), 2)
                del bad["design"]["columnHeight"]
                with open(p, "w") as fh:
                    json.dump(bad, fh)
                self.assertEqual(support_calc.main([p, "--no-optimize", "--quiet"]), 1)

    def test_factored_mode_reproduces_ps101_verdict(self):
        doc = support_calc.run(load("ps-101-factored.json"), optimize=False)
        self.assertAlmostEqual(doc["envelope"]["governingRatio"], 0.8314, places=4)


class SkillContent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\nname: pipe-support\ndescription: \""))
        head = self.text.split("\n---\n", 1)[0]
        self.assertEqual([ln.split(":", 1)[0] for ln in head.splitlines()[1:]], ["name", "description", "compatibility"])
        desc = self.text.split("description: ", 1)[1].split("\n", 1)[0].strip('"')
        self.assertLessEqual(len(desc), 400)
        for t in ("CAESAR II", "ASCE 7-22", "AISC 360-22", "ACI CODE-318-25", "AWS D1.1", "optimized"):
            self.assertIn(t, desc)

    def test_shipped_files_referenced(self):
        for rel in ("scripts/support_calc.py", "references/spec-format.md", "references/review-protocol.md",
                    "references/code-basis.md", "scripts/examples/ps-201-caesar.json",
                    "scripts/examples/ps-101-factored.json", "scripts/pipe_support/data/aisc_shapes.json"):
            self.assertTrue(os.path.exists(os.path.join(SKILL, *rel.split("/"))), rel)
            self.assertIn(rel.split("/")[-1], self.text)

    def test_hand_offs_name_only_pack_skills(self):
        for s in ("`load-case-builder`", "`stress-screening`", "`iso-to-pcf`"):
            self.assertIn(s, self.text)

    def test_shapes_attribution(self):
        # The dataset is an index plus family-group parts, each under 256 KiB: the Anthropic
        # plugin directory inspects a file only up to that size and held 0.5.1 for review
        # because the single 454 KB file exceeded it (pre-submission report, 2026-10-28).
        data = os.path.join(SCRIPTS, "pipe_support", "data")
        with open(os.path.join(data, "aisc_shapes.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertIn("AISC Shapes Database v16.0", d["attribution"])
        self.assertNotIn("rows", d, "rows belong in the parts, not the index")
        total = 0
        for rel in d["parts"]:
            path = os.path.join(data, *rel.split("/"))
            self.assertLess(os.path.getsize(path), 256 * 1024, rel)
            with open(path, encoding="utf-8") as fh:
                part = json.load(fh)
            self.assertIn("AISC Shapes Database v16.0", part["attribution"], rel)
            self.assertTrue(all(r["family"] in part["families"] for r in part["rows"]), rel)
            total += len(part["rows"])
        self.assertEqual(total, d["row_count"])
        self.assertGreater(total, 1000)
        for name in os.listdir(os.path.join(data, "aisc_shapes")):
            self.assertIn("aisc_shapes/" + name, d["parts"], "a part file the index does not list")

    def test_shapes_load_in_original_order(self):
        from pipe_support import aisc
        rows = aisc.load_shapes()
        self.assertEqual(len(rows), 1506)
        self.assertEqual(rows[0]["label"], "W44X408")
        self.assertEqual([r["family"] for r in rows[:1]] + [rows[-1]["family"]], ["W", "BJ"])
        self.assertEqual(aisc.find_shape("w6x15")["label"], "W6X15")

    def test_no_personal_or_employer_material(self):
        content_guard.assert_clean(self, SKILL)


# ------------------------------------------------------------------ code_values

def cv(value, unit, source="connector", column="Placeholder column"):
    """A code_values entry with a placeholder citation."""
    citation = {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
                "row": "Placeholder row"}
    if column:
        citation["column"] = column
    return {"value": value, "unit": unit, "citation": citation, "source": source}


class CodeValues(unittest.TestCase):
    """The optional code_values block of the spec (the spelling codeValues is accepted too)."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load("ps-201-caesar.json")
        cls.want = support_calc.run(copy.deepcopy(cls.spec), optimize=False)

    def _without(self, *paths):
        spec = copy.deepcopy(self.spec)
        for path in paths:
            node = spec
            for seg in path[:-1]:
                node = node[seg]
            del node[path[-1]]
        return spec

    def _same_as_explicit(self, doc, ignore=("spec", "notes")):
        for key in self.want:
            if key in ignore:
                continue
            self.assertEqual(doc[key], self.want[key], key)

    def _main(self, spec, *extra):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "spec.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(spec, fh)
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = support_calc.main([path, "--no-optimize", *extra])
        return code, out.getvalue(), err.getvalue()

    def test_full_paths_fill_the_spec_and_the_result_equals_the_explicit_run(self):
        spec = self._without(("design", "material", "Fy"), ("design", "material", "Fu"),
                             ("pipes", 0, "loads", "SDS"), ("pipes", 1, "loads", "SDS"))
        spec["code_values"] = {
            "design.material.Fy": cv(36, "ksi"), "design.material.Fu": cv(58, "ksi", "user"),
            "pipes.0.loads.SDS": cv(0.5, "g", "user"), "pipes.1.loads.SDS": cv(0.5, "g", "user")}
        doc = support_calc.run(spec, optimize=False)
        self._same_as_explicit(doc, ignore=("spec", "notes", "code_value_provenance", "code_value_applied"))
        self.assertEqual(list(doc["code_value_provenance"]),
                         ["design.material.Fy", "design.material.Fu", "pipes.0.loads.SDS", "pipes.1.loads.SDS"])
        self.assertEqual(doc["code_value_provenance"]["design.material.Fu"],
                         {"unit": "ksi", "source": "user", "citation": cv(0, "ksi")["citation"]})
        self.assertEqual(doc["code_value_applied"]["pipes.1.loads.SDS"], {"value": 0.5, "unit": "-"})
        self.assertNotIn("code_values", doc["spec"])

    def test_short_names_fill_every_pipe_and_both_spellings_of_the_key_work(self):
        for key in ("code_values", "codeValues"):
            spec = self._without(("design", "material", "Fy"), ("pipes", 0, "loads", "SDS"),
                                 ("pipes", 1, "loads", "SDS"))
            spec[key] = {"Fy": cv(36, "ksi"), "SDS": cv(0.5, None, "user")}
            doc = support_calc.run(spec, optimize=False)
            self._same_as_explicit(doc, ignore=("spec", "notes", "code_value_provenance", "code_value_applied"))
            self.assertEqual(list(doc["code_value_provenance"]), ["Fy", "SDS"], key)
            self.assertEqual([p["loads"]["SDS"] for p in doc["spec"]["pipes"]], [0.5, 0.5], key)
            self.assertEqual(doc["code_value_applied"]["Fy"], {"value": 36, "unit": "ksi"}, key)

    def test_a_value_replaces_the_preset_and_the_preset_note_goes_away(self):
        spec = copy.deepcopy(self.spec)
        self.assertIn("bondStrength = 800 taken from the csa-type-1 preset", " ".join(self.want["assumed"]))
        spec["code_values"] = {"bondStrength": cv(0.9, "ksi", "user")}
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(doc["design"]["baseplate"]["bondStrength"], 900.0)
        self.assertNotIn("bondStrength = 800", " ".join(doc["assumed"]))
        self.assertIn("code_values.bondStrength: 0.9 ksi applied as 900 psi.", doc["notes"])
        self.assertEqual(doc["code_value_applied"]["bondStrength"], {"value": 900.0, "unit": "psi"})

    def test_anchor_values_by_their_full_and_short_names(self):
        for name in ("design.baseplate.bondStrength", "baseplate.bondStrength", "bondStrength"):
            spec = copy.deepcopy(self.spec)
            spec["code_values"] = {name: cv(800, "psi", "user")}
            doc = support_calc.run(spec, optimize=False)
            self.assertEqual(doc["design"]["baseplate"]["bondStrength"], 800, name)
            # the preset note goes away, so the anchorage check's screening note no longer names
            # bondStrength (0.8.0 result status); every other envelope key equals the explicit run
            self._same_as_explicit(doc, ignore=("spec", "notes", "assumed", "code_value_provenance",
                                                "code_value_applied", "envelope", "_status"))
            strip = ("checks", "result_status")
            self.assertEqual({k: v for k, v in doc["envelope"].items() if k not in strip},
                             {k: v for k, v in self.want["envelope"].items() if k not in strip}, name)
            note = [c for c in doc["envelope"]["checks"] if c["name"] == "Anchorage"][0]["note"]
            self.assertNotIn("bondStrength", note, name)
        spec = copy.deepcopy(self.spec)
        spec["code_values"] = {"anchorFuta": cv(58, "ksi"), "plateFy": cv(36, "ksi"), "cac": cv(12, "in", "user")}
        doc = support_calc.run(spec, optimize=False)
        bp = doc["design"]["baseplate"]
        self.assertEqual((bp["anchorFuta"], bp["plateFy"], bp["cac"]), (58, 36, 12))

    def test_a_conflict_exits_2_with_the_exact_message_and_no_verdict(self):
        spec = copy.deepcopy(self.spec)
        spec["code_values"] = {"design.material.Fy": cv(50, "ksi")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "input error: code_values.design.material.Fy conflicts with input design.material.Fy\n")
        spec["code_values"] = {"Fy": cv(50, "ksi")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out, err), (2, "", "input error: code_values.Fy conflicts with input Fy\n"))

    def test_a_conflict_on_one_pipe_names_that_pipe(self):
        spec = copy.deepcopy(self.spec)
        spec["pipes"][1]["loads"]["SDS"] = 0.6
        spec["code_values"] = {"SDS": cv(0.5, None, "user")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "input error: code_values.SDS conflicts with input SDS (pipes[1].loads.SDS)\n")

    def test_an_equal_value_is_recorded_as_matching(self):
        spec = copy.deepcopy(self.spec)
        spec["code_values"] = {"Fy": cv(36, "ksi"), "Fu": cv(58, "ksi")}
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(list(doc["code_value_provenance"]), ["Fy", "Fu"])
        self._same_as_explicit(doc, ignore=("spec", "notes", "code_value_provenance", "code_value_applied"))

    def test_an_unknown_name_exits_2(self):
        for name in ("fy", "Q", "design.material.Q", "pipes.0.loads.D", "arms.0.shape", "design"):
            spec = copy.deepcopy(self.spec)
            spec["code_values"] = {name: cv(1, "ksi")}
            code, out, err = self._main(spec, "--quiet")
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
            self.assertTrue(err.startswith(f"input error: code_values.{name} is not an input of the support spec (valid: "),
                            err)

    def test_a_unit_that_cannot_be_used_exits_2(self):
        spec = self._without(("design", "material", "Fy"))
        spec["code_values"] = {"Fy": cv(248, "MPa")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "input error: code_values.Fy unit 'MPa' cannot be used for an input in 'ksi'\n")

    def test_a_malformed_block_exits_2(self):
        for block, fragment in (([1], "code_values must be an object"),
                                ({"Fy": 36}, "code_values.Fy must be an object"),
                                ({"Fy": dict(cv(36, "ksi"), source="x")}, "code_values.Fy.source must be")):
            spec = self._without(("design", "material", "Fy"))
            spec["code_values"] = block
            code, out, err = self._main(spec, "--quiet")
            self.assertEqual((code, out), (2, ""), fragment)
            self.assertIn(fragment, err)

    def test_the_key_given_in_both_spellings_exits_2(self):
        spec = copy.deepcopy(self.spec)
        spec["code_values"] = {"Fy": cv(36, "ksi")}
        spec["codeValues"] = {"Fu": cv(58, "ksi")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("give code_values once, not as both code_values and codeValues", err)

    def test_sds_needs_caesar_mode(self):
        spec = load("ps-101-factored.json")
        spec["code_values"] = {"SDS": cv(0.5, None, "user")}
        code, out, err = self._main(spec, "--quiet")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("code_values.SDS: nothing to fill, pipes is not a non-empty list", err)

    def test_the_factored_example_with_its_material_moved_into_the_block(self):
        base = load("ps-101-factored.json")
        want = support_calc.run(copy.deepcopy(base), optimize=False)
        spec = copy.deepcopy(base)
        del spec["design"]["material"]
        spec["code_values"] = {"Fy": cv(36, "ksi"), "Fu": cv(58, "ksi")}
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(doc["envelope"]["governingRatio"], want["envelope"]["governingRatio"])
        self.assertAlmostEqual(doc["envelope"]["governingRatio"], 0.8314, places=4)

    def test_absent_block_changes_nothing(self):
        for doc in (self.want, support_calc.run(load("ps-101-factored.json"), optimize=False)):
            self.assertNotIn("code_value_provenance", doc)
            self.assertNotIn("code_value_applied", doc)
            self.assertNotIn("Code-table values", support_calc.R.markdown(doc))
            self.assertNotIn("code_value", support_calc.R.to_json(doc))
        spec = copy.deepcopy(self.spec)
        spec["code_values"] = None
        doc = support_calc.run(spec, optimize=False)
        self.assertNotIn("code_value_provenance", doc)
        self._same_as_explicit(doc)
        spec["code_values"] = {}                               # an empty block is the same as none
        doc = support_calc.run(spec, optimize=False)
        self.assertNotIn("code_value_provenance", doc)
        self.assertNotIn("code_value_applied", doc)
        self._same_as_explicit(doc)

    def test_provenance_reaches_the_json_and_the_markdown_report(self):
        spec = self._without(("design", "material", "Fy"), ("design", "material", "Fu"))
        spec["code_values"] = {"Fy": cv(36, "ksi"), "Fu": cv(58, "ksi", "user")}
        with tempfile.TemporaryDirectory() as d:
            path, jpath, mpath = (os.path.join(d, n) for n in ("spec.json", "out.json", "calc.md"))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(spec, fh)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = support_calc.main([path, "--no-optimize", "--json", jpath, "--report", mpath, "--quiet"])
            with open(jpath, encoding="utf-8") as fh:
                data = json.load(fh)
            with open(mpath, encoding="utf-8") as fh:
                md = fh.read()
        self.assertEqual(code, 3)          # ps-201's ASSUMED item and CSA preset anchor values hold the banner
        self.assertEqual(list(data["code_value_provenance"]), ["Fy", "Fu"])
        self.assertEqual(data["code_value_provenance"]["Fy"]["source"], "connector")
        self.assertEqual(data["code_value_applied"]["Fu"], {"value": 58, "unit": "ksi"})
        self.assertIn("## Code-table values (user-supplied or connector-supplied, cited)", md)
        self.assertIn("| Input | Value | Unit | Source | Citation |", md)
        self.assertIn("| Fy | 36 | ksi | connector | Placeholder standard 0000, Placeholder table, Placeholder row, "
                      "Placeholder column |", md)
        self.assertIn("| Fu | 58 | ksi | user |", md)

    def test_the_caller_spec_is_not_modified(self):
        spec = self._without(("design", "material", "Fy"))
        spec["code_values"] = {"Fy": cv(0.036, "Msi")}
        before = json.dumps(spec, sort_keys=True)
        doc = support_calc.run(spec, optimize=False)
        self.assertEqual(json.dumps(spec, sort_keys=True), before)
        self.assertEqual(doc["design"]["material"]["Fy"], 36.0)


if __name__ == "__main__":
    unittest.main()
