"""Plugin 0.8.0 (B9): the output status taxonomy in the pipe-support skill.

The envelope gains result_status (the worst word among the checks performed; "not checked" rows
are listed but never set it) and checks[]; the result document
repeats result_status. Every taxonomy word this skill can reach has a test, the banner rule
(no PASS under manual check required or pointer only) is pinned on the verdict line, the
report banner and the stage headings, and the existing envelope keys and status words are
unchanged. The constructed cases are the shipped examples with keys edited; every number is
an engine number from support_calc.run.

Standard library only:  python -m unittest discover -s tests -v
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts")
EX = os.path.join(SCRIPTS, "examples")
sys.path.insert(0, SCRIPTS)

import support_calc  # noqa: E402
from pipe_support import optimizer as OP  # noqa: E402
from pipe_support import report as R  # noqa: E402

WORDS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
NEW_ENVELOPE_KEYS = ("result_status", "checks")


def load(name):
    with open(os.path.join(EX, name), encoding="utf-8") as fh:
        s = json.load(fh)
    s["optimize"] = False
    return _esr_category(s, name)


def _esr_category(s, name):
    """ps-201 leaves the ACI 355.2/355.4 Anchor Category unset, so at the ACI CODE-318-25 default
    the engine takes Category 3 (psi_a 0.60) and the anchorage FAILS (1.1356 LRFD; 0.9.0). Tests whose
    subject is not the anchorage enter Category 1, as an engineer would from the anchor's ESR;
    PS201Category3 in test_pipe_support_skill.py runs the example as shipped."""
    if name == "ps-201-caesar.json":
        s.setdefault("design", {}).setdefault("baseplate", {})["anchorCategory"] = 1
    return s


def ps201(**edit):
    s = load("ps-201-caesar.json")
    for p in s["pipes"]:
        c = p["loads"]["cases"]
        if edit.get("moments"):
            c["SUS"] = c["SUS"] + [0, 0, 500]
        if edit.get("sds", 0.5) != 0.5:
            if edit["sds"] is None:
                p["loads"].pop("SDS")
            else:
                p["loads"]["SDS"] = edit["sds"]
    if edit.get("own_anchor") or edit.get("clean"):
        s["design"]["baseplate"] = {"bondStrength": 800, "anchorFuta": 58, "anchorType": "post-installed-adhesive",
                                    "anchorEmbedment": 8, "fc": 4000, "anchorCategory": 1}
    if edit.get("clean"):
        s.pop("assumed")                 # no ASSUMED item and no preset value: nothing to confirm
    return s


ASSUMED_NOTE = "confirm before issue: Loads from the CAESAR II restraint summary at node 1040; Y vertical."


def asd_wind(wind=1.5):
    """The 0.7.2 guard case: ps-201 in ASD, WIN x1.5, no EQ (anchorage held under ASD-5a-+T)."""
    s = load("ps-201-caesar.json")
    s["design"]["method"] = "ASD"
    s["design"]["baseplate"]["aciEdition"] = "318-19"   # the guard scenario lives on 318-19 numbers (0.9.0)
    for p in s["pipes"]:
        c = p["loads"]["cases"]
        c["WIN"] = [x * wind for x in c["WIN"]]
        del c["EQ"]
        p["loads"].pop("SDS")
    return s


def run(spec):
    return support_calc.run(spec, optimize=False)


def cli(spec):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = support_calc.main([path, "--quiet", "--no-optimize"])
    return code, out.getvalue().strip(), err.getvalue()


def by_name(doc, name):
    return [c for c in doc["envelope"]["checks"] if c["name"] == name][0]


def stage_check(doc, component):
    st = [s for s in doc["envelope"]["stages"] if s["component"] == component][0]
    return by_name(doc, st["stage"])


def banners(md):
    return [ln for ln in md.splitlines() if ln.startswith("> ")]


class Shape(unittest.TestCase):

    def test_every_run_emits_one_of_the_five_words(self):
        for spec in (ps201(), load("ps-101-factored.json"), asd_wind(), ps201(sds=None), ps201(sds="asce7-22-sds")):
            doc = run(spec)
            env = doc["envelope"]
            self.assertIn(env["result_status"], WORDS)
            self.assertEqual(doc["result_status"], env["result_status"])
            for c in env["checks"]:
                self.assertEqual(sorted(c), ["name", "note", "result_status", "status"])
                self.assertIn(c["result_status"], WORDS)
                self.assertIn(c["status"], ("pass", "fail", "na"))
            self.assertEqual(json.loads(R.to_json(doc))["envelope"]["checks"], env["checks"])

    def test_existing_envelope_keys_and_words_are_unchanged(self):
        """Parity: the envelope minus the two new keys is exactly the engine's own envelope."""
        spec = load("ps-101-factored.json")
        doc = run(spec)
        fs = support_calc.factored_spec(spec, doc["design"])
        engine = OP.envelope(doc["design"], fs["_factoredSets"], fs)
        self.assertEqual({k: v for k, v in doc["envelope"].items() if k not in NEW_ENVELOPE_KEYS}, engine)
        self.assertEqual((doc["envelope"]["status"], round(doc["envelope"]["governingRatio"], 4)), ("pass", 0.8314))
        g = run(asd_wind())
        self.assertEqual(g["envelope"]["status"], "manual check required")
        self.assertEqual([s["status"] for s in g["envelope"]["stages"]].count("manual check required"), 1)

    def test_status_line_sits_under_the_title(self):
        for spec in (ps201(), asd_wind(), ps201(sds="asce7-22-sds")):
            doc = run(spec)
            lines = R.markdown(doc).splitlines()
            self.assertTrue(lines[0].startswith("# Pipe Support Calculation - "))
            word = doc["result_status"]
            self.assertTrue(lines[2].startswith(f"Result status: {word} - "), lines[2])
            self.assertIn("## Result status by check", lines)


class Calculated(unittest.TestCase):
    """ps-101 (no preset, nothing ASSUMED): every stage calculated; the Known-limits items are listed
    as 'not checked' but the envelope reads 'calculated'."""

    @classmethod
    def setUpClass(cls):
        cls.doc = run(load("ps-101-factored.json"))

    def test_every_stage_is_calculated(self):
        st = [by_name(self.doc, s["stage"]) for s in self.doc["envelope"]["stages"]]
        self.assertEqual({c["result_status"] for c in st}, {"calculated"})
        self.assertEqual({c["status"] for c in st}, {"pass"})
        self.assertEqual(by_name(self.doc, "Loads as entered (factored mode)")["result_status"], "calculated")

    def test_envelope_is_calculated_and_the_banner_is_pass(self):
        self.assertEqual(self.doc["result_status"], "calculated")
        self.assertTrue(self.doc["_status"]["line"].startswith(
            "Result status: calculated - every check run is calculated from the given inputs; "
            "not performed by this module: "))
        self.assertTrue(self.doc["_status"]["banner_allowed"])
        self.assertEqual(cli(load("ps-101-factored.json"))[:2][0], 0)
        self.assertTrue(R.cli_verdict(self.doc).startswith("PASS - "))
        self.assertTrue(banners(R.markdown(self.doc))[0].startswith("> **PASS** - governing:"))


class NotChecked(unittest.TestCase):

    def test_known_limits_are_listed(self):
        doc = run(ps201())
        names = [c["name"] for c in doc["envelope"]["checks"] if c["result_status"] == "not checked"]
        self.assertEqual(names, ["Column torsion (AISC 360-22 H3)",
                                 "Seismic overstrength combinations (ASCE 7-22 Em with Omega0)",
                                 "Snow, rain, ice and flood loads (ASCE 7-22 Lr, S, R, Fa, Di, Wi)",
                                 "AWS D1.1 prequalified joints, WPS, filler metal, inspection"])
        self.assertTrue(all(by_name(doc, n)["status"] == "na" for n in names))

    def test_not_checked_never_blocks(self):
        doc = run(load("ps-101-factored.json"))
        self.assertEqual(doc["result_status"], "calculated")
        self.assertIn("not performed by this module: Column torsion (AISC 360-22 H3)", doc["_status"]["why"])
        self.assertEqual(cli(load("ps-101-factored.json"))[0], 0)

    def test_overstrength_is_listed_only_with_a_seismic_case(self):
        names = [c["name"] for c in run(asd_wind())["envelope"]["checks"]]
        self.assertNotIn("Seismic overstrength combinations (ASCE 7-22 Em with Omega0)", names)
        self.assertNotIn("Vertical seismic Ev = 0.2 SDS D (ASCE 7-22 12.4.2.2)", names)


class PresetAndAssumedInputs(unittest.TestCase):
    """ps-201 runs on CSA preset anchor values and carries one ASSUMED item: each gives one row graded
    manual check required, so the envelope follows and no PASS banner prints."""

    def test_preset_anchor_values_give_one_preset_inputs_row(self):
        doc = run(ps201())
        a = stage_check(doc, "anchorage")
        self.assertEqual((a["result_status"], a["status"]), ("calculated", "pass"))
        self.assertIn("bondStrength, anchorFuta, anchorType, anchorEmbedment, fc from the csa-type-1 preset", a["note"])
        self.assertEqual(stage_check(doc, "baseplate")["result_status"], "calculated")
        rows = [c for c in doc["envelope"]["checks"] if c["name"] == "preset inputs"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["result_status"], rows[0]["status"]), ("manual check required", "na"))
        self.assertTrue(rows[0]["note"].startswith(
            "confirm before issue: bondStrength = 800 from the csa-type-1 preset (replace with the anchor "
            "product's ESR value); anchorFuta = 58 from the csa-type-1 preset; "), rows[0]["note"])
        self.assertEqual(doc["result_status"], "manual check required")
        self.assertFalse([c for c in doc["envelope"]["checks"] if c["result_status"] == "screening"])

    def test_the_spec_assumed_item_gives_one_assumed_inputs_row(self):
        doc = run(ps201())
        rows = [c for c in doc["envelope"]["checks"] if c["name"] == "ASSUMED inputs"]
        self.assertEqual(rows, [{"name": "ASSUMED inputs", "result_status": "manual check required", "status": "na",
                                 "note": ASSUMED_NOTE}])

    def test_ps201_holds_the_banner_and_exits_3(self):
        doc = run(ps201())
        self.assertFalse(doc["_status"]["banner_allowed"])
        self.assertIn("ASSUMED inputs (" + ASSUMED_NOTE + ")", doc["_status"]["why"])
        self.assertIn("preset inputs (confirm before issue: bondStrength = 800", doc["_status"]["why"])
        code, line, _ = cli(ps201())
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith("MANUAL CHECK REQUIRED - "), line)
        self.assertNotIn("PASS", line)
        self.assertTrue(banners(R.markdown(doc))[0].startswith(
            "> **MANUAL CHECK REQUIRED (strength ratios within limits) - not issuable, held for a manual check: "
            "ASSUMED inputs"), banners(R.markdown(doc))[0])

    def test_user_anchor_values_clear_the_preset_row_and_confirming_clears_the_rest(self):
        doc = run(ps201(own_anchor=True))
        self.assertEqual(stage_check(doc, "anchorage")["result_status"], "calculated")
        self.assertNotIn("preset inputs", [c["name"] for c in doc["envelope"]["checks"]])
        self.assertEqual(doc["result_status"], "manual check required")            # the ASSUMED item remains
        clean = run(ps201(clean=True))
        self.assertEqual(clean["result_status"], "calculated")
        self.assertTrue(clean["_status"]["banner_allowed"])
        self.assertEqual(cli(ps201(clean=True))[0], 0)
        self.assertEqual(doc["envelope"]["governingRatio"], run(ps201())["envelope"]["governingRatio"])
        self.assertEqual(clean["envelope"]["governingRatio"], run(ps201())["envelope"]["governingRatio"])


class ManualCheckRequired(unittest.TestCase):

    def test_the_asd_wind_guard_maps_to_manual_check_required(self):
        doc = run(asd_wind())
        a = stage_check(doc, "anchorage")
        self.assertEqual((a["result_status"], a["status"]), ("manual check required", "pass"))
        self.assertIn("held by the ASD wind-anchorage guard (governing)", a["note"])
        self.assertEqual(doc["result_status"], "manual check required")
        self.assertFalse(doc["_status"]["banner_allowed"])
        code, line, _ = cli(asd_wind())
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith("NOT ISSUABLE - ASD anchorage governed by wind combination ASD-5a-+T"), line)

    def test_pipe_moments_map_to_manual_check_required(self):
        doc = run(ps201(moments=True, clean=True))
        held = [c for c in doc["envelope"]["checks"] if c["result_status"] == "manual check required"]
        self.assertEqual([c["name"] for c in held], ["Pipe moments at 6-P-1201 are not carried by the model",
                                                     "Pipe moments at 6-P-1202 are not carried by the model"])
        code, line, _ = cli(ps201(moments=True, clean=True))
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith("MANUAL CHECK REQUIRED WITH 2 CRITICAL FINDING(S) - "), line)
        self.assertTrue(banners(R.markdown(doc))[0].startswith(
            "> **MANUAL CHECK REQUIRED (strength ratios within limits) WITH 2 CRITICAL REVIEW FINDING(S) - "
            "not issuable until resolved**"))

    def test_a_seismic_case_without_sds_maps_to_manual_check_required(self):
        doc = run(ps201(sds=None))
        ev = by_name(doc, "Vertical seismic Ev = 0.2 SDS D (ASCE 7-22 12.4.2.2)")
        self.assertEqual(ev["result_status"], "manual check required")
        self.assertIn("SDS not given for 6-P-1201, 6-P-1202: Ev taken as zero", ev["note"])
        self.assertEqual(doc["envelope"]["status"], "pass")             # status word unchanged
        code, line, _ = cli(ps201(sds=None))
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith("MANUAL CHECK REQUIRED - "), line)

    def test_a_failure_still_prints_fail(self):
        doc = run(asd_wind(4.5))
        self.assertEqual(doc["envelope"]["status"], "fail")
        self.assertEqual(stage_check(doc, "anchorage")["status"], "fail")
        code, line, _ = cli(asd_wind(4.5))
        self.assertEqual(code, 2)
        self.assertTrue(line.startswith("FAIL - "), line)


class PointerOnly(unittest.TestCase):

    def test_an_sds_pointer_does_not_run_ev(self):
        doc = run(ps201(sds="asce7-22-sds", clean=True))
        ev = by_name(doc, "Vertical seismic Ev = 0.2 SDS D (ASCE 7-22 12.4.2.2)")
        self.assertEqual(ev["result_status"], "pointer only")
        self.assertIn("6-P-1201 (asce7-22-sds)", ev["note"])
        self.assertEqual(doc["result_status"], "pointer only")
        self.assertIn("Ev = 0.2 SDS D not applied", " ".join(doc["notes"]))
        no_sds = run(ps201(sds=None, clean=True))                         # the same numbers as a run without SDS
        strip = lambda e: {k: v for k, v in e.items() if k not in NEW_ENVELOPE_KEYS}  # noqa: E731
        self.assertEqual(strip(doc["envelope"]), strip(no_sds["envelope"]))
        self.assertNotEqual(strip(doc["envelope"]), strip(run(ps201(clean=True))["envelope"]))

    def test_pointer_only_blocks_the_banner_and_exits_3(self):
        code, line, _ = cli(ps201(sds="asce7-22-sds", clean=True))
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith("POINTER ONLY - "), line)
        self.assertIn("a required value is a pointer only (that check did not run)", line)

    def test_an_sds_pointer_through_code_values_is_recorded(self):
        spec = ps201(sds=None, clean=True)
        cit = {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
               "row": "Placeholder row"}
        spec["code_values"] = {"SDS": {"value": "asce7-22-sds", "unit": None, "citation": cit, "source": "connector"}}
        doc = run(spec)
        self.assertEqual(doc["result_status"], "pointer only")
        self.assertEqual(doc["code_value_applied"]["SDS"], {"value": "asce7-22-sds", "unit": "-"})
        self.assertNotIn("SDS", doc["spec"]["pipes"][0]["loads"])

    def test_any_other_pointer_value_exits_2(self):
        spec = ps201()
        del spec["design"]["material"]["Fy"]
        cit = {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table",
               "row": "Placeholder row"}
        spec["code_values"] = {"Fy": {"value": "aisc360-22-fy-fu", "unit": "ksi", "citation": cit, "source": "connector"}}
        code, out, err = cli(spec)
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("input error: code_values.Fy is a pointer only ('aisc360-22-fy-fu')"), err)


class BannerRule(unittest.TestCase):
    """No PASS wording anywhere in the verdict, the banner or a stage heading while the banner is held."""

    CASES = {"guard": asd_wind, "moments": lambda: ps201(moments=True), "no SDS": lambda: ps201(sds=None),
             "pointer": lambda: ps201(sds="asce7-22-sds"), "preset and ASSUMED": ps201}

    def test_no_pass_while_held(self):
        for name, make in self.CASES.items():
            with self.subTest(case=name):
                doc = run(make())
                self.assertFalse(doc["_status"]["banner_allowed"])
                self.assertNotIn("PASS", R.cli_verdict(doc))
                md = R.markdown(doc)
                self.assertFalse([b for b in banners(md) if "PASS" in b])
                heads = [ln for ln in md.splitlines() if ln.startswith("### ")]
                self.assertFalse([h for h in heads if " - PASS " in h], heads)
                self.assertTrue([h for h in heads if " - RATIO WITHIN LIMITS " in h], heads)
                self.assertEqual(cli(make())[0], 3)

    def test_pass_when_allowed(self):
        for spec in (ps201(clean=True), load("ps-101-factored.json")):
            doc = run(spec)
            self.assertTrue(doc["_status"]["banner_allowed"])
            self.assertTrue(R.cli_verdict(doc).startswith("PASS - "))
            self.assertFalse([ln for ln in R.markdown(doc).splitlines() if "RATIO WITHIN LIMITS" in ln])

    def test_the_optimizer_section_drops_pass_wording_while_held(self):
        with open(os.path.join(EX, "ps-201-caesar.json"), encoding="utf-8") as fh:
            settings = json.load(fh)["optimize"]
        for make, held in ((lambda: ps201(sds=None), True), (ps201, True), (lambda: ps201(clean=True), False)):
            spec = make()
            spec["optimize"] = settings
            doc = support_calc.run(spec, optimize=True)
            self.assertTrue(doc.get("optimizer"))
            lines = [ln for ln in R.markdown(doc).splitlines()
                     if ln.startswith("## Optimized alternatives") or "designs" in ln]
            if held:
                self.assertEqual(lines[0], "## Optimized alternatives (ratios within limits in every combination)")
                self.assertIn("designs within limits found.", lines[1])
                self.assertFalse([ln for ln in lines if "pass" in ln.lower()], lines)
            else:
                self.assertEqual(lines[0], "## Optimized alternatives (all pass every combination)")
                self.assertIn("passing designs found.", lines[1])


if __name__ == "__main__":
    unittest.main()
