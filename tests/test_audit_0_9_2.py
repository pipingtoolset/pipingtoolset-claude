"""Plugin 0.9.2: the 2026-11-02 adversarial-audit mirror (audit N1, S1, S11b).

The pressure-design half of that audit (branch reinforcement, miters, the B31.1 edition basis for
wall thickness) left the plugin in 0.10.0 with the pressure-design skill; this file keeps the
stress-range half.

Engine reference (the one-engine rule): the calculation engine's stress-range module after its
PR #187 (torsional SIF `it` in Eq. (17)). The hand numbers below are the engine fixtures' own
derivations; every input is a fictitious round value or a fixture input, never a code-table value.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SS_SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-stress-check", "scripts")
sys.path.insert(0, SS_SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pipe_stress_check as ss  # noqa: E402

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
        r = subprocess.run([sys.executable, os.path.join(SS_SCRIPTS, "pipe_stress_check.py"), DISP,
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
