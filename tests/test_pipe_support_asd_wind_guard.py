"""CODEX P1-5 (plugin 0.7.2): the ASD wind-anchorage guard.

Owner ruling 2026-10-30, superseding item 6 of the 2026-10-26 P.E. rulings ("documented
only"); P.E. confirmation pending at PR review. Code-basis item 10: in ASD the ACI 318-19
strength anchor capacity is converted with a fixed 1/1.5 (R17.5.3); under a 0.6W combination
the implied factor is 1/0.6 = 1.67, so ASD anchorage can be about 10 % unconservative. When
an ASD anchorage stage's governing combination carries wind, the envelope now holds the stage
at "manual check required", the verdict reads NOT ISSUABLE (never PASS), the CLI exits 3,
and the optimizer never ranks such a design as passing. The reviewer's major finding stays
as defence in depth.

The constructed cases are the shipped ps-201 CAESAR II example with the method switched and
the load cases edited; every number is an engine number from support_calc.run.

Standard library only:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support")
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

import support_calc  # noqa: E402
from pipe_support import loads as LD  # noqa: E402
from pipe_support import optimizer as OP  # noqa: E402
from pipe_support import report as R  # noqa: E402
from pipe_support import review as V  # noqa: E402

GUARD = "manual check required"
HEAD = ("NOT ISSUABLE - ASD anchorage governed by wind combination ASD-5a-+T: run anchorage in LRFD "
        "or resolve the ACI strength-to-ASD factor treatment (code-basis item 10)")


def example():
    with open(os.path.join(SCRIPTS, "examples", "ps-201-caesar.json"), encoding="utf-8") as fh:
        return json.load(fh)


def case(method, wind=1.5, eq=False, optimize=False, arm=None):
    """ps-201 with the method set, WIN scaled by `wind` (None drops it), EQ dropped (False),
    kept (True) or scaled (a number), and optionally the arm shape changed."""
    s = example()
    s["design"]["method"] = method
    if arm:
        for a in s["design"]["arms"]:
            a["shape"] = arm
    if not optimize:
        s["optimize"] = False
    for p in s["pipes"]:
        c = p["loads"]["cases"]
        if wind is None:
            del c["WIN"]
        else:
            c["WIN"] = [x * wind for x in c["WIN"]]
        if eq is False:
            del c["EQ"]
            p["loads"].pop("SDS", None)
        elif eq is not True:
            c["EQ"] = [x * eq for x in c["EQ"]]
    return s


def factored(method, **extra):
    with open(os.path.join(SCRIPTS, "examples", "ps-101-factored.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    spec["design"]["method"] = method
    spec.update(extra)
    return spec


def anchorage(doc):
    return [s for s in doc["envelope"]["stages"] if s["component"] == "anchorage"][0]


def cli(spec, *extra):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = support_calc.main([path, "--quiet", "--no-optimize", *extra])
        return code, out.getvalue().strip()


class GuardFires(unittest.TestCase):
    """ASD, every limit state within its ratio, anchorage governed by ASD-5a-+T (D + 0.6W + T)."""

    @classmethod
    def setUpClass(cls):
        cls.spec = case("ASD")
        cls.doc = support_calc.run(cls.spec, optimize=False)

    def test_stage_is_manual_check_required_with_the_engine_ratio_kept(self):
        st = anchorage(self.doc)
        self.assertEqual(st["combo"], "ASD-5a-+T")
        self.assertTrue(LD.asd_wind_combo(st["combo"]))
        self.assertEqual(st["status"], GUARD)
        self.assertEqual(st["engineStatus"], "pass")
        self.assertAlmostEqual(st["ratio"], 0.7653, places=4)          # engine number, not re-factored
        self.assertEqual(st["asdWindGuard"]["reason"], HEAD)

    def test_envelope_cannot_pass(self):
        env = self.doc["envelope"]
        self.assertEqual(env["status"], GUARD)
        self.assertEqual([g["stage"] for g in env["guards"]], ["Anchorage"])
        self.assertEqual(env["guards"][0]["check"], "Concrete breakout (tension)")
        others = [s for s in env["stages"] if s["component"] != "anchorage"]
        self.assertTrue(all(s["status"] == "pass" for s in others))   # only the guard holds it

    def test_cli_verdict_names_the_stage_and_exits_3_without_pass(self):
        code, line = cli(self.spec)
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith(HEAD + " - Anchorage / Concrete breakout (tension) = 0.7653 (ASD-5a-+T)"),
                        line)
        self.assertNotIn("PASS", line)
        self.assertEqual(R.cli_verdict(self.doc), line)

    def test_report_banner_and_stage_say_manual_check_required(self):
        md = R.markdown(self.doc)
        banners = [ln for ln in md.splitlines() if ln.startswith("> ")]
        self.assertTrue(banners[0].startswith(f"> **{HEAD}** - held: Anchorage / Concrete breakout (tension)"))
        self.assertFalse([b for b in banners if "PASS" in b], banners)
        self.assertIn("### Anchorage - MANUAL CHECK REQUIRED (max UR 0.765, combination ASD-5a-+T)", md)
        self.assertIn("**Validity guard - ASD anchorage under wind** (code-basis item 10; owner ruling 2026-10-30", md)
        self.assertIn("| ACI 318-19 Ch. 17 - anchorage | 17.6, 17.7, 17.8 | 0.765 | manual check required |", md)
        self.assertIn("manual check required", [r["status"] for r in self.doc["compliance"]])

    def test_major_finding_kept_and_says_the_guard_applied(self):
        f = [x for x in self.doc["findings"] if x["title"] == "ASD anchorage governed by a wind combination"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "major")
        self.assertIn("1/0.6 = 1.67", f[0]["detail"])
        self.assertIn("Guard applied: stage status 'manual check required' (engine status 'pass')", f[0]["detail"])
        self.assertIn("LRFD", f[0]["remedy"])

    def test_a_wind_governed_asd_failure_stays_a_failure(self):
        doc = support_calc.run(case("ASD", wind=4.5), optimize=False)
        st = anchorage(doc)
        self.assertTrue(LD.asd_wind_combo(st["combo"]), st["combo"])
        self.assertEqual(st["status"], "fail")
        self.assertEqual(st["asdWindGuard"]["engineStatus"], "fail")
        self.assertEqual(doc["envelope"]["status"], "fail")
        code, line = cli(case("ASD", wind=4.5))
        self.assertEqual(code, 2)
        self.assertTrue(line.startswith("FAIL - "), line)
        self.assertIn(f"> Also {HEAD}.", R.markdown(doc))


class GuardDoesNotFire(unittest.TestCase):

    def test_same_case_in_lrfd_passes_on_its_ratio(self):
        doc = support_calc.run(case("LRFD"), optimize=False)
        st = anchorage(doc)
        self.assertEqual((st["combo"], st["status"]), ("LRFD-4a-+T", "pass"))
        self.assertAlmostEqual(st["ratio"], 0.6276, places=4)
        self.assertEqual(doc["envelope"]["guards"], [])
        self.assertEqual(doc["envelope"]["status"], "pass")
        code, line = cli(case("LRFD"))
        self.assertEqual(code, 0)
        self.assertTrue(line.startswith("PASS - "), line)

    def test_lrfd_still_fails_on_its_ratio(self):
        doc = support_calc.run(case("LRFD", wind=9), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["status"], "fail")
        self.assertNotIn("asdWindGuard", st)
        self.assertEqual(doc["envelope"]["guards"], [])
        self.assertEqual(cli(case("LRFD", wind=9))[0], 2)

    def test_asd_dead_plus_thermal_governed_is_unchanged(self):
        doc = support_calc.run(case("ASD", wind=None), optimize=False)
        st = anchorage(doc)
        self.assertFalse(LD.asd_wind_combo(st["combo"]), st["combo"])
        self.assertTrue(st["combo"].startswith("ASD-1a"), st["combo"])
        self.assertEqual(st["status"], "pass")
        self.assertNotIn("engineStatus", st)
        self.assertEqual(doc["envelope"]["status"], "pass")
        self.assertEqual(doc["envelope"]["guards"], [])
        self.assertFalse([f for f in doc["findings"] if "ASD anchorage" in f["title"]])
        code, line = cli(case("ASD", wind=None))
        self.assertEqual(code, 0)
        self.assertTrue(line.startswith("PASS - "), line)

    def test_asd_seismic_governed_anchorage_is_not_guarded(self):
        doc = support_calc.run(case("ASD", wind=1.0, eq=True), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["combo"], "ASD-8-+T")                     # 0.7E: implied 1/0.7 < 1.5
        self.assertEqual(st["status"], "pass")
        self.assertEqual(doc["envelope"]["guards"], [])


class OptimizerHonoursTheGuard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = case("ASD", optimize=True)
        cls.spec["optimize"] = {"includeDesigns": True, "top": 30}
        cls.opt = support_calc.run(cls.spec)["optimizer"]

    def test_no_alternative_is_ranked_with_a_guarded_anchorage(self):
        sets, _ = OP.demand_sets(self.spec, "ASD")
        for a in self.opt["alternatives"]:
            env = OP.envelope(a["design"], sets, self.spec)
            self.assertEqual(env["status"], "pass", a["arms"])
            self.assertEqual(env["guards"], [], a["arms"])

    def test_the_log_says_why_and_the_as_drawn_design_is_not_offered(self):
        self.assertFalse(any(a["asDrawn"] for a in self.opt["alternatives"]))
        log = " ".join(self.opt["log"])
        self.assertIn("held by the ASD wind-anchorage guard (anchorage governed by ASD-5a-+T", log)
        self.assertIn("As-drawn design not offered: ASD anchorage governed by wind combination ASD-5a-+T", log)

    def test_a_guarded_stage_is_not_ok_for_the_tuner(self):
        st = {"stage": "Anchorage", "component": "anchorage", "status": GUARD, "ratio": 0.5}
        self.assertFalse(OP._stage_ok({"stages": [st]}, "anchorage"))
        self.assertTrue(OP._stage_ok({"stages": [dict(st, status="pass")]}, "anchorage"))

    def test_lrfd_alternatives_are_still_offered(self):
        spec = case("LRFD", optimize=True)
        self.assertTrue(support_calc.run(spec)["optimizer"]["alternatives"])


class OneSourceAndDefenceInDepth(unittest.TestCase):

    def test_one_predicate(self):
        self.assertIs(V.asd_wind_combo, LD.asd_wind_combo)

    def test_finding_without_the_envelope_guard_says_it_was_not_applied(self):
        st = {"stage": "Anchorage", "component": "anchorage", "status": "pass", "ratio": 0.93,
              "governing": "Concrete breakout (tension)", "combo": "ASD-5a+", "checks": []}
        env = {"stages": [st], "warnings": [], "governingRatio": 0.93, "governingStage": "Anchorage",
               "governingRun": {"warnings": []}}
        f = [x for x in V.review({"method": "ASD", "arms": []}, env, {"pipes": []})
             if x["title"] == "ASD anchorage governed by a wind combination"]
        self.assertEqual(len(f), 1)
        self.assertIn("Guard NOT applied to this envelope", f[0]["detail"])

    def test_factored_mode_lrfd_raises_no_factored_anchorage_finding(self):
        lrfd = support_calc.run(factored("LRFD"), optimize=False)
        self.assertEqual(lrfd["envelope"]["guards"], [])
        self.assertFalse([x for x in lrfd["findings"] if x["title"].startswith("ASD anchorage on factored")])

    def test_finding_detects_a_near_governing_wind_row_without_the_guard(self):
        st = {"stage": "Anchorage", "component": "anchorage", "status": "pass", "ratio": 0.95,
              "governing": "Tension-shear interaction", "combo": "ASD-8-+T", "checks": [],
              "asdWind": {"combo": "ASD-5a-+T", "ratio": 0.9, "governing": "Tension-shear interaction"}}
        env = {"stages": [st], "warnings": [], "governingRatio": 0.95, "governingStage": "Anchorage",
               "governingRun": {"warnings": []}}
        f = [x for x in V.review({"method": "ASD", "arms": []}, env, {"pipes": []})
             if x["title"] == "ASD anchorage governed by a wind combination"]
        self.assertEqual(len(f), 1)
        self.assertIn("wind combination ASD-5a-+T gives", f[0]["detail"])
        self.assertIn("Guard NOT applied to this envelope", f[0]["detail"])
        far = dict(st, asdWind=dict(st["asdWind"], ratio=0.8))     # 0.8 x 1.111 = 0.889 < 0.95
        env["stages"] = [far]
        self.assertFalse([x for x in V.review({"method": "ASD", "arms": []}, env, {"pipes": []})
                          if x["title"] == "ASD anchorage governed by a wind combination"])


class NearGoverningWind(unittest.TestCase):
    """Audit fix (B7 review): seismic ASD-8-+T governs the anchorage at 0.9494, but wind
    ASD-5a-+T gives 0.9249 and 0.9249 x (1/0.6)/1.5 = 1.028 reaches it. Before the fix this
    printed a plain PASS. ps-201 with WIN x2.2, EQ x1.6 and a W6X20 arm (so that only the
    anchorage is in question)."""

    @classmethod
    def setUpClass(cls):
        cls.spec = case("ASD", wind=2.2, eq=1.6, arm="W6X20")
        cls.doc = support_calc.run(cls.spec, optimize=False)

    def test_margin_is_the_equation_quotient(self):
        self.assertAlmostEqual(LD.asd_wind_margin(), (1 / 0.6) / 1.5, places=12)
        self.assertTrue(LD.asd_wind_could_govern(0.9249, 0.9494))
        self.assertTrue(LD.asd_wind_could_govern(0.9, 0.9))         # a tie the envelope broke
        self.assertFalse(LD.asd_wind_could_govern(0.6841, 0.9494))
        self.assertFalse(LD.asd_wind_could_govern("Infinity", 0.5))

    def test_stage_is_held_although_seismic_governs(self):
        st = anchorage(self.doc)
        self.assertEqual((st["combo"], st["ratio"]), ("ASD-8-+T", 0.9494))   # engine row unchanged
        self.assertEqual(st["status"], GUARD)
        self.assertEqual(st["engineStatus"], "pass")
        g = st["asdWindGuard"]
        self.assertEqual(g["trigger"], "near-governing")
        self.assertEqual((g["combo"], g["ratio"]), ("ASD-5a-+T", 0.9249))
        self.assertEqual((g["stageCombo"], g["stageRatio"]), ("ASD-8-+T", 0.9494))
        self.assertEqual(st["asdWind"]["combo"], "ASD-5a-+T")
        env = self.doc["envelope"]
        self.assertEqual(env["status"], GUARD)
        self.assertTrue(all(s["status"] == "pass" for s in env["stages"] if s["component"] != "anchorage"))

    def test_cli_and_report_say_not_issuable(self):
        code, line = cli(self.spec)
        self.assertEqual(code, 3)
        self.assertTrue(line.startswith(HEAD + " - Anchorage / Tension-shear interaction = 0.9249 (ASD-5a-+T)"),
                        line)
        self.assertNotIn("PASS", line)
        md = R.markdown(self.doc)
        banners = [ln for ln in md.splitlines() if ln.startswith("> ")]
        self.assertFalse([b for b in banners if "PASS" in b], banners)
        self.assertIn("the engine's governing row is Tension-shear interaction = 0.949 under ASD-8-+T", md)
        self.assertIn("[near-governing]", md)

    def test_major_finding_names_the_wind_row(self):
        f = [x for x in self.doc["findings"] if x["title"] == "ASD anchorage governed by a wind combination"]
        self.assertEqual(len(f), 1)
        self.assertIn("wind combination ASD-5a-+T gives Tension-shear interaction = 0.9249", f[0]["detail"])
        self.assertIn("Guard applied", f[0]["detail"])

    def test_same_case_in_lrfd_is_not_guarded(self):
        doc = support_calc.run(case("LRFD", wind=2.2, eq=1.6, arm="W6X20"), optimize=False)
        self.assertEqual(doc["envelope"]["guards"], [])
        self.assertEqual(anchorage(doc)["status"], "pass")
        self.assertNotIn("asdWind", anchorage(doc))

    def test_seismic_clear_of_the_margin_is_not_guarded(self):
        doc = support_calc.run(case("ASD", wind=1.0, eq=1.6, arm="W6X20"), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["combo"], "ASD-8-+T")
        self.assertEqual(st["asdWind"]["ratio"], 0.6841)            # 0.6841 x 1.111 = 0.760 < 0.9494
        self.assertEqual(st["status"], "pass")
        self.assertEqual(doc["envelope"]["guards"], [])


class FactoredModeAsd(unittest.TestCase):
    """Audit fix (B7 review): ASD anchorage on factored loads printed a plain PASS row because
    the guard could not see the combination. It is now held unless the spec declares the
    entered loads wind-free with factored_wind: false. ps-101 (factored) switched to ASD."""

    def test_undeclared_wind_content_holds_the_anchorage(self):
        doc = support_calc.run(factored("ASD"), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["combo"], "as entered")
        self.assertEqual(st["status"], GUARD)
        self.assertEqual(st["asdWindGuard"]["trigger"], "factored-undeclared")
        self.assertEqual([g["stage"] for g in doc["envelope"]["guards"]], ["Anchorage"])
        f = [x for x in doc["findings"] if x["title"].startswith("ASD anchorage on factored loads")]
        self.assertEqual([x["severity"] for x in f], ["major"])
        self.assertIn("Guard applied", f[0]["detail"])
        md = R.markdown(doc)
        self.assertIn("### Anchorage - MANUAL CHECK REQUIRED", md)
        self.assertIn("NOT ISSUABLE - ASD anchorage on factored loads with undeclared wind content", md)
        self.assertNotIn("### Anchorage - PASS", md)

    def test_declared_wind_free_is_unchanged(self):
        doc = support_calc.run(factored("ASD", factored_wind=False), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["status"], "pass")
        self.assertNotIn("engineStatus", st)
        self.assertEqual(doc["envelope"]["guards"], [])
        f = [x for x in doc["findings"] if x["title"].startswith("ASD anchorage on factored loads")]
        self.assertEqual([x["severity"] for x in f], ["info"])
        self.assertIn("factored_wind: false", f[0]["detail"])

    def test_declared_wind_holds_with_the_wind_headline(self):
        doc = support_calc.run(factored("ASD", factored_wind=True), optimize=False)
        st = anchorage(doc)
        self.assertEqual(st["asdWindGuard"]["trigger"], "factored-declared")
        self.assertEqual(st["asdWindGuard"]["reason"],
                         OP.asd_wind_guard_text("as entered (factored_wind: true)"))

    def test_lrfd_ignores_the_declaration(self):
        doc = support_calc.run(factored("LRFD", factored_wind=True), optimize=False)
        self.assertEqual(doc["envelope"]["guards"], [])

    def test_non_boolean_declaration_is_a_spec_error(self):
        with self.assertRaises(support_calc.InputError):
            support_calc.run(factored("ASD", factored_wind="no"), optimize=False)

    def test_factored_alternatives_honour_the_guard(self):
        spec = factored("ASD")
        spec["optimize"] = {"includeDesigns": True, "top": 30}
        opt = support_calc.run(spec)["optimizer"]
        fs = support_calc.factored_spec(spec, support_calc.resolve_design(spec))
        for a in opt["alternatives"]:
            env = OP.envelope(a["design"], fs["_factoredSets"], fs)
            self.assertEqual(env["guards"], [], a["arms"])
            self.assertEqual(env["status"], "pass", a["arms"])
        self.assertFalse(opt["alternatives"])                      # every anchorage is held
        wf = factored("ASD", factored_wind=False)
        wf["optimize"] = {"top": 3}
        self.assertTrue(support_calc.run(wf)["optimizer"]["alternatives"])


class Docs(unittest.TestCase):

    def read(self, *parts):
        with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_code_basis_item_10_names_the_ruling_and_what_it_supersedes(self):
        text = self.read("references", "code-basis.md")
        item = text.split("10. **", 1)[1].split("\n11. ", 1)[0]
        for needle in ("2026-10-30", "supersedes", "2026-10-26", "documented only", "manual check required",
                       "NOT ISSUABLE", "P.E.", "1/0.6 = 1.67", "loads.asd_wind_combo",
                       "loads.asd_wind_could_govern", "factored_wind", "P.E. confirmation points"):
            self.assertIn(needle, item)

    def test_skill_and_protocol_state_the_verdict_words(self):
        for parts in (("SKILL.md",), ("references", "review-protocol.md")):
            text = self.read(*parts)
            self.assertIn("manual check required", text, parts)
            self.assertIn("NOT ISSUABLE", text, parts)


if __name__ == "__main__":
    unittest.main()
