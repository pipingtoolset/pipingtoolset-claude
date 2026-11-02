"""Plugin 0.9.2: the 2026-11-02 adversarial-audit mirror (owner rulings R1-R3, audit N1, S1, S11b).

Engine references (the one-engine rule): the calculation engine's stress-range module after its
PR #187 (torsional SIF `it` in Eq. (17)) and its branch-reinforcement and miter modules after PR
#188 (minimum-wall basis, d2 cap, Sb/Sh on A3, header or branch wall FAIL, miter refusals and
eq. (5)). The hand numbers below are the engine fixtures' own derivations; every input is a
fictitious round value or a fixture input, never a code-table value.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PD_SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pressure-design", "scripts")
SS_SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "stress-screening", "scripts")
sys.path.insert(0, PD_SCRIPTS)
sys.path.insert(0, SS_SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
import pressure_design as pd  # noqa: E402
import stress_screening as ss  # noqa: E402

BRANCH = "piping.branch-reinforcement"
MITER = "piping.miter-allowable-pressure"
B311 = "piping.b311-wall-thickness"
MAWP = "piping.b31-allowable-pressure"
BEND = "piping.bend-thickness"
DISP = "piping.displacement-stress"


def check(env: dict, name: str) -> dict:
    rows = [c for c in env["checks"] if c["name"] == name]
    assert len(rows) == 1, [c["name"] for c in env["checks"]]
    return rows[0]


# --------------------------------------------------------------------------- N1: torsional SIF it


class TorsionalSif(unittest.TestCase):
    """St = it*|Mt|/(2Z). Hand case from the engine fixture: Mt 200,000 in-lb, Z 16.81 in^3."""

    TORSION = dict(ii=1, io=1, Mi=0, Mo=0, Mt=200000, Z=16.81, Sc=20000, Sh=17300, f=1)

    def test_it_scales_the_torsion_term(self):
        out = ss.displacement_stress(dict(self.TORSION, it=2.3))
        self.assertAlmostEqual(out["output"]["St"], 13682.332, delta=1e-3)     # 2.3 * 200000 / 33.62
        self.assertAlmostEqual(out["output"]["SE"], 27364.664, delta=1e-3)     # 2 * St with Sa = Sb = 0
        self.assertAlmostEqual(out["output"]["SA"], 29325, delta=1e-3)
        self.assertAlmostEqual(out["output"]["ratio"], 0.9332, delta=1e-4)
        self.assertEqual(out["status"], "pass")
        self.assertEqual(out["warnings"], [])

    def test_it_omitted_is_one_and_warned_when_mt_is_nonzero(self):
        out = ss.displacement_stress(dict(self.TORSION))
        self.assertAlmostEqual(out["output"]["St"], 5948.84, delta=1e-3)       # 200000 / 33.62: the 0.9.1 number
        self.assertAlmostEqual(out["output"]["SE"], 11897.68, delta=1e-3)
        self.assertAlmostEqual(out["output"]["ratio"], 0.4057, delta=1e-4)
        self.assertEqual(len(out["warnings"]), 1)
        self.assertIn("Torsional SIF it not supplied", out["warnings"][0])
        self.assertIn("B31J Table 1-1", out["warnings"][0])

    def test_no_warning_without_torsion(self):
        out = ss.displacement_stress(dict(self.TORSION, Mt=0))
        self.assertEqual(out["warnings"], [])
        self.assertEqual(out["output"]["St"], 0)

    def test_it_explicitly_one_is_not_warned(self):
        self.assertEqual(ss.displacement_stress(dict(self.TORSION, it=1))["warnings"], [])

    def test_the_fail_case(self):
        out = ss.displacement_stress(dict(self.TORSION, Mt=300000, it=2.3))
        self.assertAlmostEqual(out["output"]["SE"], 41046.996, delta=1e-3)
        self.assertEqual(out["status"], "fail")

    def test_it_below_one_is_rejected_like_the_other_sifs(self):
        with self.assertRaisesRegex(ValueError, "SIFs must be >= 1"):
            ss.displacement_stress(dict(self.TORSION, it=0.9))

    def test_it_is_a_declared_user_supplied_field(self):
        names = [f[0] for f in ss.FIELDS[DISP]]
        self.assertIn("it", names)
        self.assertFalse([f for f in ss.FIELDS[DISP] if f[0] == "it"][0][2])      # optional
        self.assertIn("it", ss.USER_SUPPLIED[DISP])
        env = ss.run_module(DISP, dict(self.TORSION, it=2.3))
        self.assertIn("it", env["user_supplied"])

    def test_envelope_lists_the_missing_it_as_not_checked(self):
        env = ss.run_module(DISP, dict(self.TORSION))
        row = check(env, "torsional SIF it (B31J Table 1-1)")
        self.assertEqual(row["result_status"], "not checked")
        self.assertIn("taken as 1.0", row["note"])
        given = ss.run_module(DISP, dict(self.TORSION, it=2.3))
        self.assertFalse([c for c in given["checks"] if c["name"].startswith("torsional SIF")])
        none = ss.run_module(DISP, dict(self.TORSION, Mt=0))
        self.assertFalse([c for c in none["checks"] if c["name"].startswith("torsional SIF")])

    def test_sustained_st_field_names_the_upstream_index(self):
        desc = [f[3] for f in ss.FIELDS["piping.sustained-stress"] if f[0] == "St"][0]
        self.assertIn("it*Mt/(2 Z)", desc)

    def test_cli_accepts_it(self):
        r = subprocess.run([sys.executable, os.path.join(SS_SCRIPTS, "stress_screening.py"), DISP,
                            "--input", json.dumps(dict(self.TORSION, it=2.3))],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertAlmostEqual(json.loads(r.stdout)["output"]["St"], 13682.332, delta=1e-3)


# --------------------------------------------------------------------------- S1 / S11b: B31.1 editions


class B311EditionResolver(unittest.TestCase):

    def test_2020_and_2022_name_b31j_table_1_1_for_the_104_8_indices(self):
        for yr in (2020, 2022):
            r = ss.resolve_basis("B31.1", yr)
            self.assertIn("B31J Table 1-1", r["sif_source"], yr)
            self.assertIn("ii, io, it", r["sif_source"], yr)
            self.assertIn("still printed", r["sif_source"], yr)
            self.assertEqual(r["sif_documents_permitted"], ["ASME B31J"], yr)
            self.assertTrue(any("finding from 2020 on" in n for n in r["notes"]), yr)

    def test_2018_and_earlier_keep_appendix_d(self):
        for yr in (2016, 2018):
            r = ss.resolve_basis("B31.1", yr)
            self.assertIn("Mandatory Appendix D", r["sif_source"])
            self.assertEqual(r["sif_documents_permitted"], ["ASME B31.1 Mandatory Appendix D"])

    def test_2024_and_2026_say_appendix_d_deleted(self):
        for yr in (2024, 2026):
            r = ss.resolve_basis("B31.1", yr)
            self.assertIn("deleted in 2024", r["sif_source"])
            self.assertEqual(r["sif_documents_permitted"], ["ASME B31J"])
            self.assertIn("without the ASD reduction", r["asd_reduction"])

    def test_2026_branch(self):
        r = ss.resolve_basis("B31.1", 2026)
        note = [n for n in r["notes"] if n.startswith("B31.1-2026")]
        self.assertEqual(len(note), 1)
        for token in ("104.8 equations and indices are unchanged", "102.3.3", "(c) test", "eq. (3)/(4)",
                      "eq. (5)/(6)", "104.2.1(c)", "Grade 91 Type 1"):
            self.assertIn(token, note[0])
        self.assertEqual(r["allowable_stress_dataset"], "b311-allowable-stresses-2026")
        self.assertEqual(r["fatigue_equation"], "legacy")
        self.assertFalse(any("B31.1-2026" in n for n in ss.resolve_basis("B31.1", 2024)["notes"]))

    def test_dataset_follows_the_edition(self):
        self.assertEqual(ss.resolve_basis("B31.1", 2024)["allowable_stress_dataset"], "b311-allowable-stresses-2024")
        self.assertEqual(ss.resolve_basis("B31.1", 2018)["allowable_stress_dataset"], "b311-allowable-stresses-2024")
        self.assertIsNone(ss.resolve_basis("B31.1", 2016)["allowable_stress_dataset"])
        self.assertEqual(ss.resolve_basis("B31.3", 2024)["allowable_stress_dataset"], "b313-allowable-stresses-2024")

    def test_resolver_still_carries_no_table_value(self):
        blob = json.dumps(ss.resolve_basis("B31.1", 2026))
        self.assertNotIn("ksi", blob)
        self.assertNotIn("psi", blob)


class PressureDesignEditionBasis(unittest.TestCase):
    B311_JOB = dict(P=800, D=6, S=20000, E=0.8, y=0.4, A=0.05, millTolerance=0.125, W_basis="seamless")

    def test_2026_equation_numbers_and_datasets(self):
        env = pd.run_module(B311, dict(self.B311_JOB, edition=2026))
        eb = env["edition_basis"]
        self.assertEqual(eb["generation"], "2026")
        self.assertIn("eq. (3)/(4)", eb["tm_equation"])
        self.assertIn("eq. (5)/(6)", eb["P_equation"])
        self.assertIn("104.2.1(c)", eb["bend_equation"])
        self.assertEqual(eb["y_table"], "Table 104.1.2-1")
        self.assertEqual(eb["datasets"], {"S": "b311-allowable-stresses-2026", "y": "b311-y-coefficients-2026"})
        self.assertTrue(any("Grade 91 Type 1" in n for n in eb["notes"]))
        self.assertIn("104.1.2-1", [f[4] for f in pd.FIELDS[B311] if f[0] == "y"][0])

    def test_2018_to_2024_numbers(self):
        for yr in (2018, 2022, "2024"):
            eb = pd.run_module(B311, dict(self.B311_JOB, edition=yr))["edition_basis"]
            self.assertEqual(eb["generation"], "2018-2024", yr)
            self.assertIn("eq. (7)/(8)", eb["tm_equation"])
            self.assertIn("102.4.5 eq. (3)", eb["bend_equation"])
            self.assertEqual(eb["datasets"]["S"], "b311-allowable-stresses-2024")

    def test_2016_and_no_edition(self):
        eb = pd.run_module(B311, dict(self.B311_JOB, edition="B31.1-2016",
                                      W_basis="below creep range per table note"))["edition_basis"]
        self.assertEqual(eb["generation"], "2016")
        self.assertEqual(eb["y_table"], "Table 104.1.2(A)")
        self.assertEqual(eb["datasets"], {})
        eb = pd.run_module(B311, dict(self.B311_JOB))["edition_basis"]
        self.assertEqual(eb["generation"], "edition not given")
        self.assertIn("by edition", eb["datasets"]["S"])

    def test_only_b31_1_runs_carry_it(self):
        mawp = dict(D=10, t=0.5, millTolerance=0.125, A=0.1, S=20000, E=1, y=0.4, Mf=1, W_basis="seamless")
        self.assertIn("edition_basis", pd.run_module(MAWP, dict(mawp, code="B31.1", edition=2026)))
        self.assertNotIn("edition_basis", pd.run_module(MAWP, dict(mawp, code="B31.3", edition=2024)))
        self.assertNotIn("edition_basis", pd.run_module(MAWP, dict(mawp)))
        self.assertNotIn("edition_basis", pd.run_module("piping.b313-wall-thickness",
                                                        dict(P=500, D=10, S=20000, E=1, W=1, W_basis="seamless",
                                                             Y=0.4, c=0.1, millTolerance=0.125, edition=2024)))

    def test_bend_gate_clause_follows_the_edition(self):
        bend = dict(P=9000, D=6, R=18, S=20000, E=1, y=0.4, A=0, code="B31.1", W_basis="seamless")
        new = pd.run_module(BEND, dict(bend, edition=2026))
        self.assertFalse(new["validity"]["thin_wall_valid"])
        self.assertIn("104.2.1(c)", new["validity"]["clause"])
        old = pd.run_module(BEND, dict(bend, edition=2024))
        self.assertIn("102.4.5", old["validity"]["clause"])
        self.assertNotIn("104.2.1(c)", old["validity"]["clause"])


# --------------------------------------------------------------------------- R1 / R2 / N6: branch reinforcement


class BranchReinforcement(unittest.TestCase):
    """Fixture geometry: 8 x 4 NPS, th 0.147, tb 0.077 (illustrative pressure-design thicknesses)."""

    def _case(self, i: int) -> dict:
        return dict(parity.load(BRANCH)["cases"][i]["input"])

    def test_fixture_has_the_nine_engine_cases(self):
        self.assertEqual(len(parity.load(BRANCH)["cases"]), 9)

    def test_header_below_th_fails_despite_a_positive_margin(self):
        inp = self._case(6)                                   # Th 0.2, c 0.0625 -> Th - c 0.1375 < th 0.147; pad 0.5 x 8
        out = pd.branch_reinforcement(inp)
        self.assertAlmostEqual(out["output"]["margin"], 1.13776, delta=1e-4)
        self.assertEqual(out["status"], "fail")
        self.assertTrue(any(w.startswith("FAIL — header wall net of allowance") for w in out["warnings"]))
        env = pd.run_module(BRANCH, inp)
        self.assertEqual(env["status"], "fail")
        row = check(env, pd.CHECK_BRANCH_WALLS)
        self.assertEqual((row["result_status"], row["status"]), ("calculated", "fail"))
        self.assertIn("Th - c = 0.1375 < th = 0.147", row["note"])

    def test_branch_below_tb_fails_too(self):
        inp = dict(self._case(0), Tb=0.1, tb=0.077, c=0.05)   # Tb - c 0.05 < tb
        out = pd.branch_reinforcement(inp)
        self.assertEqual(out["status"], "fail")
        self.assertTrue(any(w.startswith("FAIL — branch wall net of allowance") for w in out["warnings"]))

    def test_walls_at_their_design_thickness_pass_the_wall_row(self):
        env = pd.run_module(BRANCH, self._case(0))
        row = check(env, pd.CHECK_BRANCH_WALLS)
        self.assertEqual((row["result_status"], row["status"]), ("calculated", "pass"))

    def test_d2_is_capped_at_dh(self):
        out = pd.branch_reinforcement(self._case(8))          # 8 x 8 lateral at 45 deg: d1 11.40068 > Dh 8.625
        self.assertAlmostEqual(out["output"]["d1"], 11.40068, delta=1e-4)
        self.assertEqual(out["output"]["d2"], 8.625)
        self.assertAlmostEqual(out["output"]["margin"], -0.19908, delta=1e-4)   # uncapped would read +1.41360
        self.assertEqual(out["status"], "fail")
        self.assertTrue(any(w.startswith("d2 limited to Dh = 8.625 in") for w in out["warnings"]))

    def test_branch_allowable_below_run_reduces_a3(self):
        out = pd.branch_reinforcement(self._case(7))          # Sb 16000, Sh 20000 (illustrative)
        self.assertEqual(out["output"]["strengthRatio"], 0.8)
        self.assertAlmostEqual(out["output"]["A3"], 0.10815, delta=1e-4)        # 0.13518 x 0.8
        self.assertAlmostEqual(out["output"]["margin"], 0.0581, delta=1e-4)
        self.assertTrue(any("A3 reduced by Sb/Sh = 0.8" in w for w in out["warnings"]))
        equal = pd.branch_reinforcement(dict(self._case(7), Sb=20000))
        self.assertEqual(equal["output"]["strengthRatio"], 1)
        higher = pd.branch_reinforcement(dict(self._case(7), Sb=25000))         # never increases A3
        self.assertEqual(higher["output"]["strengthRatio"], 1)
        self.assertAlmostEqual(higher["output"]["A3"], 0.13518, delta=1e-4)

    def test_one_of_sb_sh_alone_is_warned_not_applied(self):
        out = pd.branch_reinforcement(dict(self._case(2), Sb=16000))
        self.assertEqual(out["output"]["strengthRatio"], 1)
        self.assertTrue(any("Enter both Sb and Sh" in w for w in out["warnings"]))
        with self.assertRaisesRegex(ValueError, "Sb and Sh must be > 0"):
            pd.branch_reinforcement(dict(self._case(2), Sb=0, Sh=20000))

    def test_sb_and_sh_are_user_supplied_and_fillable_from_code_values(self):
        self.assertEqual(pd.user_supplied_names(BRANCH), ["Sb", "Sh"])
        base = self._case(7)
        explicit = pd.run_module(BRANCH, dict(base))
        moved = {k: v for k, v in base.items() if k not in ("Sb", "Sh")}
        cit = {"standard": "Placeholder standard", "edition": "0000", "table": "Placeholder table", "row": "Placeholder row"}
        filled = pd.run_module(BRANCH, dict(moved, code_values={
            "Sb": {"value": 16, "unit": "ksi", "citation": cit, "source": "user"},
            "Sh": {"value": 20, "unit": "ksi", "citation": cit, "source": "user"}}))
        self.assertEqual(filled["output"], explicit["output"])
        self.assertEqual(sorted(filled["code_value_provenance"]), ["Sb", "Sh"])

    # ---- ruling R2: the wall basis -------------------------------------------------------------------
    def test_nominal_walls_are_reduced_by_the_default_mill_tolerance(self):
        job = dict(Dh=8.625, ThNominal=0.322, th=0.147, Db=4.5, TbNominal=0.237, tb=0.077, c=0, betaDeg=90,
                   Tr=0, Dp=0, A4welds=0)
        env = pd.run_module(BRANCH, job)
        self.assertAlmostEqual(env["inputs"]["Th"], 0.28175, delta=1e-9)
        self.assertAlmostEqual(env["inputs"]["Tb"], 0.207375, delta=1e-9)
        self.assertNotIn("ThNominal", env["inputs"])
        self.assertAlmostEqual(env["output"]["margin"], 0.08514, delta=1e-4)    # engine fixture case 2
        self.assertEqual(env["defaults_applied"], {"millTolerance": 0.125})
        self.assertIn("(default mill tolerance)", env["wall_basis"]["Th"]["basis"])
        self.assertIn("ThNominal 0.322 x (1 - 0.125 mill tolerance)", env["wall_basis"]["Th"]["basis"])
        self.assertIn("304.3.3(a)", env["wall_basis"]["clause"])
        self.assertTrue(any(w.startswith("millTolerance not given: 0.125 applied") for w in env["warnings"]))

    def test_zero_mill_tolerance_is_a_measured_wall(self):
        job = dict(Dh=8.625, ThNominal=0.322, th=0.147, Db=4.5, TbNominal=0.237, tb=0.077, c=0, betaDeg=90,
                   Tr=0, Dp=0, A4welds=0, millTolerance=0)
        env = pd.run_module(BRANCH, job)
        self.assertAlmostEqual(env["output"]["margin"], 0.30233, delta=1e-4)    # engine fixture case 0
        self.assertEqual(env["defaults_applied"], {})
        self.assertFalse(any(w.startswith("millTolerance not given") for w in env["warnings"]))
        self.assertNotIn("(default", env["wall_basis"]["Th"]["basis"])

    def test_entered_walls_are_taken_as_minimum_or_measured(self):
        env = pd.run_module(BRANCH, self._case(0))
        self.assertEqual(env["wall_basis"]["Th"], {"value": 0.322, "basis": "entered as the header minimum or measured wall"})
        self.assertEqual(env["defaults_applied"], {})

    def test_mixed_entry_is_allowed_per_wall(self):
        env = pd.run_module(BRANCH, dict(Dh=8.625, Th=0.28175, th=0.147, Db=4.5, TbNominal=0.237, tb=0.077, c=0,
                                         betaDeg=90, Tr=0, Dp=0, A4welds=0, millTolerance=0.125))
        self.assertAlmostEqual(env["output"]["margin"], 0.08514, delta=1e-4)

    def test_conflicts_and_omissions_exit_2(self):
        base = self._case(0)
        with self.assertRaisesRegex(ValueError, "give Th .* or ThNominal, not both"):
            pd.run_module(BRANCH, dict(base, ThNominal=0.322))
        with self.assertRaisesRegex(ValueError, "Th is required: the header minimum or measured wall"):
            pd.run_module(BRANCH, {k: v for k, v in base.items() if k != "Th"})
        with self.assertRaisesRegex(ValueError, "millTolerance must be in"):
            pd.run_module(BRANCH, dict({k: v for k, v in base.items() if k != "Tb"}, TbNominal=0.237, millTolerance=1))
        with self.assertRaisesRegex(ValueError, "Th and Tb .* are required"):
            pd.branch_reinforcement({k: v for k, v in base.items() if k != "Th"})

    def test_field_descriptions_name_the_minimum_wall_basis(self):
        desc = {f[0]: f[4] for f in pd.FIELDS[BRANCH]}
        self.assertIn("MINIMUM or measured wall", desc["Th"])
        self.assertIn("MINIMUM or measured wall", desc["Tb"])
        self.assertIn("304.3.3(c)(2)", desc["Sb"])
        self.assertNotIn("nominal (measured)", desc["Th"])


# --------------------------------------------------------------------------- R3 / N7: miters


class Miters(unittest.TestCase):
    BASE = dict(S=20000, E=1, Tc=0.25, r2=4.1515, R1=12, thetaDeg=15, miters=3)

    def test_fixture_has_the_five_engine_cases(self):
        self.assertEqual(len(parity.load(MITER)["cases"]), 5)

    def test_multiple_miters_above_22_5_deg_are_refused(self):
        with self.assertRaisesRegex(ValueError, r"θ > 22.5° with multiple miters is outside eqs. \(4a\)/\(4b\)"):
            pd.miter_allowable_pressure(dict(self.BASE, thetaDeg=30))
        r = subprocess.run([sys.executable, os.path.join(PD_SCRIPTS, "pressure_design.py"), MITER, "--input",
                            json.dumps(dict(self.BASE, thetaDeg=30, W_basis="seamless"))],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2)
        self.assertIn("eq. (4c)", r.stderr)

    def test_single_miter_above_22_5_deg_still_runs_eq_4c(self):
        out = pd.miter_allowable_pressure(dict(self.BASE, thetaDeg=30, miters=1))
        self.assertEqual(out["output"]["governing"], "Eq. 4c (single miter)")
        self.assertAlmostEqual(out["output"]["allowablePressure"], 305.611, delta=1e-3)
        self.assertEqual(out["output"]["Pm1"], 0)

    def test_r1_must_exceed_r2_for_the_multi_miter_form(self):
        with self.assertRaisesRegex(ValueError, "R1 = 4 in must exceed r2 = 4.1515 in for the multiple-miter form"):
            pd.miter_allowable_pressure(dict(self.BASE, R1=4))
        with self.assertRaisesRegex(ValueError, "R1 = 3 in must exceed r2 = 4.1515 in"):
            pd.miter_allowable_pressure(dict(self.BASE, R1=3))       # eq. (4b) would read -1500.512 psi
        self.assertEqual(pd.miter_allowable_pressure(dict(self.BASE, R1=4.2))["status"], "na")

    def test_eq_5_with_the_user_entered_a(self):
        ok = pd.miter_allowable_pressure(dict(self.BASE, A=0.8, D=8.625))        # A is a test input, not a Code value
        self.assertAlmostEqual(ok["output"]["R1min"], 7.2981, delta=1e-4)        # 0.8/tan15 + 4.3125
        self.assertEqual(ok["status"], "na")
        self.assertEqual(ok["warnings"], [])
        bad = pd.miter_allowable_pressure(dict(self.BASE, A=2.5, D=8.625))
        self.assertAlmostEqual(bad["output"]["R1min"], 13.6426, delta=1e-4)
        self.assertEqual(bad["status"], "fail")
        self.assertTrue(bad["warnings"][0].startswith("FAIL — R1 = 12 in is below the eq. (5) minimum"))
        self.assertAlmostEqual(bad["output"]["allowablePressure"], 707.589, delta=1e-3)   # pressures still reported

    def test_without_a_the_minimum_is_warned_and_listed_not_checked(self):
        out = pd.miter_allowable_pressure(dict(self.BASE))
        self.assertNotIn("R1min", out["output"])
        self.assertTrue(any(w.startswith("Eq. (5) minimum R1 not checked") for w in out["warnings"]))
        env = pd.run_module(MITER, dict(self.BASE, W_basis="seamless"))
        row = check(env, pd.CHECK_MITER_R1)
        self.assertEqual(row["result_status"], "not checked")
        self.assertNotIn("R1min", env["output"])

    def test_with_a_the_minimum_is_a_calculated_check(self):
        env = pd.run_module(MITER, dict(self.BASE, A=2.5, D=8.625, W_basis="seamless"))
        row = check(env, pd.CHECK_MITER_R1)
        self.assertEqual((row["result_status"], row["status"]), ("calculated", "fail"))
        self.assertEqual(env["status"], "fail")
        self.assertEqual(env["result_status"], "calculated")
        good = pd.run_module(MITER, dict(self.BASE, A=0.8, D=8.625, W_basis="seamless"))
        self.assertEqual(check(good, pd.CHECK_MITER_R1)["status"], "pass")
        self.assertIn("A", good["user_supplied"])

    def test_a_needs_d_and_a_single_miter_does_not_evaluate_it(self):
        with self.assertRaisesRegex(ValueError, "Pipe OD D \\(> 0\\) is required with A"):
            pd.miter_allowable_pressure(dict(self.BASE, A=0.8))
        with self.assertRaisesRegex(ValueError, "A must be > 0 when entered"):
            pd.miter_allowable_pressure(dict(self.BASE, A=0, D=8.625))
        single = pd.miter_allowable_pressure(dict(self.BASE, miters=1, A=0.8, D=8.625))
        self.assertNotIn("R1min", single["output"])
        self.assertTrue(any("not evaluated for a single miter" in w for w in single["warnings"]))
        env = pd.run_module(MITER, dict(self.BASE, miters=1, W_basis="seamless"))
        self.assertFalse([c for c in env["checks"] if c["name"] == pd.CHECK_MITER_R1])

    def test_no_static_not_checked_row_remains_for_miters(self):
        self.assertEqual(pd.NOT_CHECKED[MITER], [])


if __name__ == "__main__":
    unittest.main()
