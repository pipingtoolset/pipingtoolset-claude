"""nozzle-load 0.8.0: the output status taxonomy (B9).

Every envelope carries result_status (one of five words), checks[] (name, result_status, status, note),
a "Result status: <word> - <why>" line for the sheet and a banner word. Existing status words and
values are unchanged (fixture parity runs in test_nozzle_load.py). The banner rule: no PASS while the
result status is manual check required, pointer only, or screening with an unresolved factor.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "nozzle-load")
CLI = os.path.join(SKILL, "scripts", "nozzle_load.py")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import nozzle_load as nl  # noqa: E402

WORDS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
CHECK_KEYS = {"name", "result_status", "status", "note"}
DASH = "-"


def six(v=0.0):
    return {k: v for k in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}


def record(assumed=False):
    """The shipped example record; its ASSUMED items are dropped unless assumed=True (they would make
    every run "manual check required" through the one "ASSUMED inputs" row)."""
    with open(os.path.join(SKILL, "scripts", "examples", "project-basis.example.json"), encoding="utf-8") as fh:
        rec = json.load(fh)
    if not assumed:
        rec["assumptions"] = [a for a in rec.get("assumptions") or [] if a.get("status", "ASSUMED") != "ASSUMED"]
    return rec


ANNEXF_H = dict(pumpType="horizontal", units="USC", suctionApplied=six(10), dischargeApplied=six(10),
                suctionAllowable=six(1000), dischargeAllowable=six(1000),
                annexF=dict(componentMultiple=2.0, resultantDenominator=1.5, interactionLimit=2.0,
                            centreForceFactor=1.5, centreMyFactor=2.0),
                suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
ANNEXF_V = dict(pumpType="vertical-inline", units="USC", suctionApplied=six(10), dischargeApplied=six(10),
                suctionAllowable=six(1000), dischargeAllowable=six(1000),
                annexF=dict(sigmaPLimit=5000.0, kSigma=100.0, kTau=50.0),
                suctionBore=dict(Do=6.625, Di=6.065), dischargeBore=dict(Do=4.5, Di=4.026))
CHECK = dict(standard="datasheet", applied=six(100), allowable=six(1000))
SM23 = dict(NPS=6, applied=six(10), coefficient=500)
SUM = dict(standard="header", nozzles=[six(1), six(2)], limits=six(100))
ORD = dict(FR=1e5, ML=1e8, MC=-2e8, a=500, R=10000, t=25, L=1000, P=0.1, YF=2, YL=4, YC=5)
PVP = dict(table="1A", NPS=6, row=six(1000), T=0.25, S_vessel=18800, S_nozzle=17100, designTempF=400,
           material="killed-carbon-steel", D=48, loadsPrimary=True)
SAMPLES = (("connections.nozzle-load-check", CHECK), ("connections.nema-sm23", SM23),
           ("connections.api610-annexf", ANNEXF_H), ("connections.api610-annexf", ANNEXF_V),
           ("equipment.nozzle-load-sum", SUM), ("equipment.api650-annexp-ordinates", ORD),
           ("equipment.pvp2011-allowables", PVP))


def run(module, inp, **extra):
    return nl.run_module(module, dict(copy.deepcopy(inp), **extra))


def names(env, word):
    return [c["name"] for c in env["checks"] if c["result_status"] == word]


class Envelope(unittest.TestCase):

    def test_every_module_emits_one_of_the_five_words_and_well_formed_checks(self):
        self.assertEqual(nl.RESULT_STATUS, WORDS)
        seen = set()
        for module, inp in SAMPLES:
            env = run(module, inp)
            self.assertIn(env["result_status"], WORDS, module)
            seen.add(env["result_status"])
            self.assertTrue(env["checks"], module)
            for c in env["checks"]:
                self.assertEqual(set(c) - {"unresolved_factor"}, CHECK_KEYS, module)
                self.assertIn(c["result_status"], WORDS, module)
                self.assertIn(c["status"], ("pass", "fail", "na"), module)
            self.assertEqual(env["result_status"], nl.envelope_status(env["checks"]), module)
        self.assertTrue(seen <= set(WORDS))

    def test_the_five_words_are_all_reachable(self):
        # four as the envelope word; "not checked" as a listed row (it never sets the envelope word)
        got = {
            run("equipment.nozzle-load-sum", SUM)["result_status"],
            run("equipment.pvp2011-allowables", PVP)["result_status"],
            run("equipment.pvp2011-allowables", dict(PVP, material="aluminium"))["result_status"],
            run("connections.nozzle-load-check", CHECK, project_basis=record())["result_status"],
            run("connections.nema-sm23", SM23)["result_status"],
        }
        self.assertEqual(got, set(WORDS) - {"not checked"})
        self.assertIn("not checked", [c["result_status"] for c in run("connections.nema-sm23", SM23)["checks"]])

    def test_status_and_output_are_the_engines(self):
        for module, inp in SAMPLES:
            env = run(module, inp)
            res = nl.REGISTRY[module](dict(copy.deepcopy(inp)))
            self.assertEqual(env["status"], res["status"], module)
            self.assertEqual(env["output"], res["output"], module)

    def test_the_status_line_under_the_title(self):
        for module, inp in SAMPLES:
            env = run(module, inp)
            line = env["result_status_line"]
            self.assertTrue(line.startswith("Result status: %s %s " % (env["result_status"], DASH)), line)
            self.assertNotIn("\n", line)
        self.assertEqual(run("equipment.nozzle-load-sum", SUM)["result_status_line"],
                         "Result status: calculated %s six components against the allowables as entered; limits entered by "
                         "the user" % DASH)

    def test_no_check_carries_an_unresolved_factor(self):
        # every constant in this skill is a user input or a named constant of the paper
        for module, inp in SAMPLES:
            self.assertFalse([c for c in run(module, inp)["checks"] if c.get("unresolved_factor")], module)

    def test_json_cli_output_carries_the_keys(self):
        r = subprocess.run([sys.executable, CLI, "connections.nozzle-load-check", "--input", json.dumps(CHECK)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual((env["result_status"], env["banner"]), ("calculated", "PASS"))
        self.assertTrue(env["result_status_line"].startswith("Result status: calculated " + DASH))


class Calculated(unittest.TestCase):

    def test_check_and_sum_with_user_entered_allowables(self):
        for module, inp in (("connections.nozzle-load-check", CHECK), ("equipment.nozzle-load-sum", SUM)):
            env = run(module, inp)
            self.assertEqual(env["result_status"], "calculated", module)
            self.assertEqual(env["checks"][0]["status"], "pass", module)

    def test_a_failing_ratio_is_still_a_calculated_result(self):
        env = run("connections.nozzle-load-check", dict(CHECK, applied=six(2000)))
        self.assertEqual((env["status"], env["result_status"], env["banner"]), ("fail", "calculated", "FAIL"))
        self.assertEqual(env["checks"][0]["status"], "fail")

    def test_owner_factor_is_named_in_the_check(self):
        env = run("connections.nozzle-load-check", CHECK, ownerFactor=0.5)
        self.assertEqual(env["result_status"], "calculated")
        self.assertIn("factored by ownerFactor 0.5", env["checks"][0]["note"])


class Screening(unittest.TestCase):

    def test_pvp_derivation_inside_the_papers_basis_is_screening(self):
        env = run("equipment.pvp2011-allowables", PVP)
        self.assertEqual(env["result_status"], "screening")
        self.assertEqual(names(env, "screening"), ["derived allowable set (PVP2011-57100 method)"])
        self.assertEqual(env["status"], "na")

    def test_thickness_below_the_basis_of_table_1a_is_the_papers_own_eq4(self):
        env = run("equipment.pvp2011-allowables", dict(PVP, T=0.125, D=30))
        self.assertEqual(env["result_status"], "screening")

    def test_check_against_a_derived_set_is_at_least_screening(self):
        for given in ("screening", "calculated"):
            env = run("connections.nozzle-load-check", CHECK, derivedSetStatus=given)
            self.assertEqual(env["result_status"], "screening", given)
        env = run("equipment.nozzle-load-sum", SUM, derivedSetStatus="screening")
        self.assertEqual(env["result_status"], "screening")

    def test_screening_without_an_unresolved_factor_still_prints_the_verdict(self):
        env = run("connections.nozzle-load-check", CHECK, derivedSetStatus="screening")
        self.assertEqual((env["status"], env["banner"]), ("pass", "PASS"))


class ManualCheckRequired(unittest.TestCase):

    def _gate(self, **change):
        env = run("equipment.pvp2011-allowables", dict(PVP, **change))
        self.assertEqual(env["result_status"], "manual check required", change)
        return env

    def test_each_pvp_scope_limit(self):
        self.assertIn("material is killed carbon steel", names(self._gate(material="aluminium"), "manual check required"))
        self.assertIn("material is killed carbon steel", names(self._gate(material="other-ferrous"), "manual check required"))
        self.assertIn("design temperature at or below 650 F", names(self._gate(designTempF=700), "manual check required"))
        self.assertIn("NPS within the paper's range 2 to 24", names(self._gate(NPS=30), "manual check required"))
        self.assertIn("D/T at or below 320", names(self._gate(D=100), "manual check required"))

    def test_a_limit_the_run_cannot_evaluate_is_a_manual_check(self):
        for key, name in (("designTempF", "design temperature at or below 650 F"), ("material", "material is killed carbon steel"),
                          ("D", "D/T at or below 320"), ("loadsPrimary", "character of the loads stated (loadsPrimary)")):
            inp = {k: v for k, v in PVP.items() if k != key}
            env = nl.run_module("equipment.pvp2011-allowables", inp)
            self.assertEqual(env["result_status"], "manual check required", key)
            bad = [c for c in env["checks"] if c["name"] == name][0]
            self.assertEqual((bad["result_status"], bad["status"]), ("manual check required", "na"), key)

    def test_a_declared_secondary_load_is_assessed_not_unstated(self):
        self.assertEqual(run("equipment.pvp2011-allowables", dict(PVP, loadsPrimary=False))["result_status"], "screening")

    def test_eq4_on_tables_1b_and_2_is_the_skills_extension(self):
        for table in ("1B", "2"):
            env = self._gate(table=table, T=0.1875)
            self.assertIn("thickness below the table basis (eq. 4)", names(env, "manual check required"))

    def test_interpolation_above_the_proportional_bound(self):
        inp = {k: v for k, v in PVP.items() if k != "row"}
        inp.update(lowerNPS=4, upperNPS=8, lowerRow=dict(Fx=1000, Fy=1000, Fz=1000, Mx=2000, My=2000, Mz=2000),
                   upperRow=dict(Fx=2000, Fy=2000, Fz=2000, Mx=6000, My=6000, Mz=6000))
        env = nl.run_module("equipment.pvp2011-allowables", inp)
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(names(env, "manual check required"), ["interpolation between two user-read rows"])
        self.assertIn("Mx", env["checks"][-1]["note"])

    def test_annex_p_lambda_outside_the_plotted_range(self):
        env = run("equipment.api650-annexp-ordinates", ORD)
        self.assertEqual(env["result_status"], "calculated")
        far = run("equipment.api650-annexp-ordinates", dict(ORD, a=50000, R=1000, t=10, L=60000))
        self.assertEqual(far["result_status"], "manual check required")
        self.assertIn("lambda within the plotted range of Figures P.4a/P.4b", names(far, "manual check required"))

    def test_derived_set_with_a_tripped_gate_carries_into_the_check(self):
        env = run("connections.nozzle-load-check", CHECK, derivedSetStatus="manual check required")
        self.assertEqual(env["result_status"], "manual check required")
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["banner"], "MANUAL CHECK REQUIRED")

    def test_derived_label_without_derivedsetstatus_is_manual_check_required(self):
        for label in ("PVP2011-57100 Table 1A, derived", "derived set", "pvp2011 table 2"):
            for module, inp in (("connections.nozzle-load-check", CHECK), ("equipment.nozzle-load-sum", SUM)):
                env = run(module, dict(inp, standard=label))
                self.assertEqual(env["result_status"], "manual check required", (module, label))
                self.assertEqual(env["status"], "pass")
                self.assertEqual(env["banner"], "MANUAL CHECK REQUIRED")
                self.assertIn("derivedSetStatus was not supplied", env["result_status_line"])
        given = run("connections.nozzle-load-check", dict(CHECK, standard="PVP2011-57100 Table 1A, derived"),
                    derivedSetStatus="screening")
        self.assertEqual(given["result_status"], "screening")
        self.assertEqual(run("connections.nozzle-load-check", CHECK)["result_status"], "calculated")

    def test_bad_derived_status_exits_2(self):
        with self.assertRaisesRegex(ValueError, "derivedSetStatus must be one of"):
            run("connections.nozzle-load-check", CHECK, derivedSetStatus="fine")


class AssumedInputs(unittest.TestCase):

    def test_an_assumed_record_item_is_one_manual_check_row_and_holds_the_banner(self):
        rec = record(assumed=True)
        items = [a["item"] for a in rec["assumptions"] if a.get("status", "ASSUMED") == "ASSUMED"]
        self.assertTrue(items)
        for module, inp in SAMPLES:
            env = run(module, inp, project_basis=copy.deepcopy(rec))     # outranks the owner pointer row
            rows = [c for c in env["checks"] if c["name"] == "ASSUMED inputs"]
            self.assertEqual(rows, [{"name": "ASSUMED inputs", "result_status": "manual check required",
                                     "status": "na", "note": "confirm before issue: " + "; ".join(items)}], module)
            self.assertEqual(env["result_status"], "manual check required", module)
            self.assertNotEqual(env["banner"], "PASS", module)
        env = run("connections.nozzle-load-check", CHECK, project_basis=rec, ownerFactor=0.5)
        self.assertEqual((env["status"], env["banner"]), ("pass", "MANUAL CHECK REQUIRED"))
        self.assertIn("confirm before issue: " + items[0], env["result_status_line"])


class PointerOnly(unittest.TestCase):

    def test_owner_limit_recorded_as_a_pointer_does_not_run(self):
        env = run("connections.nozzle-load-check", CHECK, project_basis=record())
        self.assertEqual(env["result_status"], "pointer only")
        c = [c for c in env["checks"] if c["result_status"] == "pointer only"][0]
        self.assertEqual(c["name"], "owner practice design-stage limit")
        self.assertIn("recorded as a pointer", c["note"])
        self.assertIn("that check does not run", c["note"])
        self.assertIn("pointer only", env["result_status_line"])

    def test_supplying_the_factor_resolves_the_pointer(self):
        env = run("connections.nozzle-load-check", CHECK, project_basis=record(), ownerFactor=0.5)
        self.assertEqual(env["result_status"], "calculated")

    def test_the_other_owner_modules_follow(self):
        for module, inp in (("connections.nema-sm23", SM23), ("connections.api610-annexf", ANNEXF_H),
                            ("equipment.nozzle-load-sum", SUM), ("equipment.pvp2011-allowables", PVP)):
            self.assertEqual(run(module, inp, project_basis=record())["result_status"], "pointer only", module)
            self.assertNotIn("pointer only", [c["result_status"] for c in run(module, inp)["checks"]], module)

    def test_a_plain_text_pointer_item_is_pointer_only(self):
        rec = record()
        rec["owner_practice"] = [{"document": "RECE002", "items": ["design-stage factor per section 5 (pointer)"]}]
        env = run("connections.nozzle-load-check", CHECK, project_basis=rec)
        self.assertEqual(env["result_status"], "pointer only")
        self.assertIn("design-stage factor per section 5", env["checks"][-1]["note"])
        self.assertEqual(run("connections.nozzle-load-check", CHECK, project_basis=rec, ownerFactor=0.5)["result_status"],
                         "calculated")

    def test_a_plain_text_item_stating_a_value_only_warns(self):
        for text in ("design-stage factor 0.5", "acceptance limit 80 %"):
            rec = record()
            rec["owner_practice"] = [{"document": "RECE002", "items": [text]}]
            env = run("connections.nozzle-load-check", CHECK, project_basis=rec)
            self.assertEqual(env["result_status"], "calculated", text)
            self.assertTrue(any("no ownerFactor was supplied" in w for w in env["warnings"]), text)

    def test_a_record_without_a_pointer_item_is_not_pointer_only(self):
        rec = record()
        rec["owner_practice"][0]["items"] = ["Run support friction both with and without"]
        self.assertEqual(run("connections.nozzle-load-check", CHECK, project_basis=rec)["result_status"], "calculated")

    def test_ordinates_take_no_owner_factor(self):
        self.assertNotEqual(run("equipment.api650-annexp-ordinates", ORD, project_basis=record())["result_status"],
                            "pointer only")

    def test_severity_order_pointer_over_screening_and_below_manual(self):
        env = run("equipment.pvp2011-allowables", {k: v for k, v in PVP.items() if k != "ownerFactor"}, project_basis=record())
        self.assertEqual(env["result_status"], "pointer only")
        self.assertIn("screening", [c["result_status"] for c in env["checks"]])
        env = run("equipment.pvp2011-allowables", dict(PVP, material="aluminium"), project_basis=record())
        self.assertEqual(env["result_status"], "manual check required")


class NotChecked(unittest.TestCase):

    def test_sm23_vendor_sheet_items(self):
        env = run("connections.nema-sm23", SM23)
        self.assertEqual(env["result_status"], "calculated")
        self.assertIn("combined resultant", names(env, "not checked")[0])
        self.assertEqual(env["banner"], "PASS")

    def test_annexf_shaft_displacement_and_approval(self):
        for inp in (ANNEXF_H, ANNEXF_V):
            env = run("connections.api610-annexf", inp)
            self.assertEqual(env["result_status"], "calculated")
            self.assertTrue(any("shaft displacement limits" in n for n in names(env, "not checked")))

    def test_annexf_vertical_without_the_multiple_lists_the_skipped_screen(self):
        env = run("connections.api610-annexf", ANNEXF_V)
        self.assertIn("F.1.2 a) per-component screen", names(env, "not checked"))
        self.assertTrue(env["checks"][0]["name"].startswith("F.9 "), env["checks"][0]["name"])
        with_multiple = copy.deepcopy(ANNEXF_V)
        with_multiple["annexF"]["componentMultiple"] = 2.0
        env = nl.run_module("connections.api610-annexf", with_multiple)
        self.assertNotIn("F.1.2 a) per-component screen", names(env, "not checked"))

    def test_annexf_checks_mirror_the_engine_checks(self):
        env = run("connections.api610-annexf", ANNEXF_H)
        evaluated = [c for c in env["checks"] if c["result_status"] == "calculated"]
        self.assertEqual(len(evaluated), len(env["output"]["checks"]))
        self.assertEqual([c["status"] for c in evaluated], [c["status"] for c in env["output"]["checks"]])

    def test_api_560_movements(self):
        env = run("connections.nozzle-load-check", dict(CHECK, standard="API 560 Table 7"))
        self.assertEqual(env["result_status"], "calculated")
        self.assertIn("not performed by this module: heater terminal movements", env["result_status_line"])
        self.assertIn("heater terminal movements (API 560 section 9.2)", names(env, "not checked"))
        self.assertEqual(run("connections.nozzle-load-check", dict(CHECK, standard="API 5600 x"))["result_status"], "calculated")

    def test_annex_p_acceptance_is_not_evaluated(self):
        env = run("equipment.api650-annexp-ordinates", ORD)
        self.assertEqual(env["result_status"], "calculated")
        self.assertEqual(env["status"], "na")
        self.assertTrue(names(env, "not checked")[0].startswith("acceptance boundary"))


class BannerRule(unittest.TestCase):
    """No PASS while manual check required, pointer only, or screening with an unresolved factor."""

    def test_pass_is_withheld_under_pointer_only(self):
        env = run("connections.nozzle-load-check", CHECK, project_basis=record())
        self.assertEqual(env["status"], "pass")
        self.assertEqual(env["banner"], "POINTER ONLY")

    def test_pass_is_withheld_under_manual_check_required(self):
        env = run("connections.nozzle-load-check", CHECK, derivedSetStatus="manual check required")
        self.assertEqual(env["banner"], "MANUAL CHECK REQUIRED")

    def test_pass_is_kept_under_calculated_screening_and_not_checked(self):
        self.assertEqual(run("connections.nozzle-load-check", CHECK)["banner"], "PASS")
        self.assertEqual(run("connections.nozzle-load-check", CHECK, derivedSetStatus="screening")["banner"], "PASS")
        self.assertEqual(run("connections.nema-sm23", SM23)["banner"], "PASS")

    def test_fail_may_always_print(self):
        env = run("connections.nozzle-load-check", dict(CHECK, applied=six(5000)), project_basis=record())
        self.assertEqual((env["status"], env["result_status"], env["banner"]), ("fail", "pointer only", "FAIL"))

    def test_modules_with_no_verdict_say_so(self):
        self.assertEqual(run("equipment.pvp2011-allowables", PVP)["banner"], "NA")
        self.assertEqual(run("equipment.api650-annexp-ordinates", ORD)["banner"], "NA")

    def test_helper_table_for_the_rule(self):
        self.assertFalse(nl.banner_allowed("manual check required"))
        self.assertFalse(nl.banner_allowed("pointer only"))
        self.assertFalse(nl.banner_allowed("screening", True))
        self.assertTrue(nl.banner_allowed("screening"))
        self.assertTrue(nl.banner_allowed("not checked"))
        self.assertTrue(nl.banner_allowed("calculated"))


class SkillWording(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            self.text = fh.read()

    def test_skill_states_the_status_line_and_the_banner_rule(self):
        self.assertIn("Result status:", self.text)
        for word in ("manual check required", "pointer only"):
            self.assertIn(word, self.text)
        self.assertIn("banner", self.text.lower())

    def test_skill_is_inside_the_word_budget(self):
        self.assertLess(len(self.text.split()), 3000)


if __name__ == "__main__":
    unittest.main()
