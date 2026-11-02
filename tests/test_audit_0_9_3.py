"""Plugin 0.9.3: the second 2026-11-02 adversarial-audit mirror (owner rulings R5; audit items N5, N9, S5c).

Engine references (the one-engine rule): the calculation engine's leak-test, flange-equivalent-pressure
and api610-annexf modules after its PR #187 (the 1.5 x P hydrotest floor of B31.3 345.4.2(a), no
compression credit in the Kellogg screen, |Fy| in the Annex F vertical in-line stress) and its nema-sm23
module after PR #186 (the coefficient basis is a required input; 927 defaults only under API 617 Annex E
eq. (E.1b)). The hand numbers below are the engine fixtures' own derivations; every input is a fictitious
round value or a fixture input. The 927 is the coefficient printed in eq. (E.1b), not a table value.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
PD_SCRIPTS = os.path.join(SKILLS, "pressure-design", "scripts")
NL_SCRIPTS = os.path.join(SKILLS, "nozzle-load", "scripts")
BF_SCRIPTS = os.path.join(SKILLS, "bolted-flange", "scripts")
for p in (PD_SCRIPTS, NL_SCRIPTS, BF_SCRIPTS, os.path.join(ROOT, "tests")):
    sys.path.insert(0, p)

import parity  # noqa: E402
import pressure_design as pd  # noqa: E402
import nozzle_load as nl  # noqa: E402
import bolted_flange as bf  # noqa: E402

LEAK = "piping.leak-test-pressure"
NEMA = "connections.nema-sm23"
SCREEN = "connections.flange-equivalent-pressure"
ANNEXF = "connections.api610-annexf"
NL_CLI = os.path.join(NL_SCRIPTS, "nozzle_load.py")
PD_CLI = os.path.join(PD_SCRIPTS, "pressure_design.py")


def six(fx=0, fy=0, fz=0, mx=0, my=0, mz=0) -> dict:
    return {"Fx": fx, "Fy": fy, "Fz": fz, "Mx": mx, "My": my, "Mz": mz}


def cli(tool: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, tool, *args], capture_output=True, text=True, encoding="utf-8")


# --------------------------------------------------------------------------- N5: the 1.5 x P hydrotest floor


class HydrotestFloor(unittest.TestCase):
    """B31.3 345.4.2(a): never below 1.5 x P; (b) Eq. (24) only raises it. B31.1 137.4.5 is the same floor."""

    def test_fixture_parity_including_the_floor_case(self):
        self.assertEqual(parity.run_fixture(pd.REGISTRY, LEAK), [])
        self.assertEqual(len(parity.load(LEAK)["cases"]), 4)

    def test_engine_case_3_reads_450_not_337_5(self):
        out = pd.leak_test_pressure(dict(P=300, ST=15000, S=20000, hydroFactor=1.5, pneumaticFactor=1.1))
        self.assertEqual(out["output"]["stressRatio"], 1.0)
        self.assertEqual(out["output"]["hydroTest"], 450.0)          # 0.9.2 printed 337.5
        self.assertEqual(out["output"]["pneumaticTest"], 330.0)
        floor = [w for w in out["warnings"] if "< 1" in w]
        self.assertEqual(len(floor), 1)
        self.assertIn("ST/S = 0.75 < 1", floor[0])
        self.assertIn("450 psi floor", floor[0])
        self.assertIn("345.4.2(a)", floor[0])
        self.assertIn("137.4.5", floor[0])

    def test_hand_case_floor_is_factor_times_p(self):
        # P 450, ST 12,000 / S 16,000 -> raw 0.75 -> applied 1.0 -> hydro 1.5 x 450 = 675
        out = pd.leak_test_pressure(dict(P=450, ST=12000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1))
        self.assertEqual(out["output"]["hydroTest"], 675.0)
        self.assertEqual(out["output"]["stressRatio"], 1.0)

    def test_ratio_above_one_is_unchanged_and_not_warned(self):
        out = pd.leak_test_pressure(dict(P=450, ST=24000, S=16000, hydroFactor=1.5, pneumaticFactor=1.1))
        self.assertEqual(out["output"]["hydroTest"], 1012.5)          # the 0.9.2 hand case, unchanged
        self.assertFalse(any("< 1" in w for w in out["warnings"]))

    def test_owner_cap_never_lowers_the_floor(self):
        out = pd.leak_test_pressure(dict(P=300, ST=15000, S=20000, hydroFactor=1.5, pneumaticFactor=1.1,
                                         stressRatioCap=6.5))
        self.assertEqual(out["output"]["hydroTest"], 450.0)
        self.assertFalse(any("Cap engaged" in w for w in out["warnings"]))

    def test_no_ceiling_on_the_ratio(self):
        # The refuted "6.5 cap": Eq. (24) carries no ceiling, so ST/S 8 stays 8 without a cap.
        out = pd.leak_test_pressure(dict(P=300, ST=20000, S=2500, hydroFactor=1.5, pneumaticFactor=1.1))
        self.assertEqual((out["output"]["stressRatio"], out["output"]["hydroTest"]), (8.0, 3600.0))

    def test_cli_carries_the_floor(self):
        r = cli(PD_CLI, LEAK, "--input", json.dumps(dict(P=300, ST=15000, S=20000, hydroFactor=1.5, pneumaticFactor=1.1)))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["output"]["hydroTest"], 450.0)
        self.assertTrue(any("450 psi floor" in w for w in env["warnings"]))

    def test_citation_names_the_floor(self):
        self.assertIn("345.4.2(a)", pd.CITATIONS[LEAK])


# --------------------------------------------------------------------------- R5: the coefficient basis


class NemaBasis(unittest.TestCase):
    L12 = six(600, 600, 600, 1000, 1000, 300)

    def test_fixture_parity_three_cases(self):
        self.assertEqual(parity.run_fixture(nl.REGISTRY, NEMA), [])
        self.assertEqual(len(parity.load(NEMA)["cases"]), 3)

    def test_api617_with_927_entered_is_the_0_9_2_number_labelled(self):
        out = nl.nema_sm23(dict(NPS=12, basis="api617", applied=self.L12, coefficient=927))["output"]
        self.assertEqual((out["De"], out["allowable"], out["ratio"]), (9.33333, 8652.0, 0.5274))
        self.assertEqual(out["coefficientSource"], "API 617 eq. (E.1b) 927")
        self.assertIn("API 617 9th Ed. Annex E eq. (E.1b)", out["basis"])

    def test_api617_default_is_the_e1b_coefficient_and_says_so(self):
        res = nl.nema_sm23(dict(NPS=6, basis="api617", applied=six(1000, 1000, 1000, 1500, 1500, 0)))
        out = res["output"]
        self.assertEqual(nl.API617_E1B_COEFFICIENT, 927)
        self.assertEqual((out["coefficient"], out["De"], out["allowable"]), (927.0, 6.0, 5562.0))
        self.assertAlmostEqual(out["index"], 7317.47277, delta=1e-4)
        self.assertEqual((out["ratio"], res["status"]), (1.3156, "fail"))
        self.assertEqual(out["coefficientSource"], "API 617 eq. (E.1b) 927 (default)")
        self.assertTrue(any("coefficient not entered" in w and "eq. (E.1b)" in w for w in res["warnings"]))

    def test_api617_other_coefficient_is_marked_as_differing(self):
        out = nl.nema_sm23(dict(NPS=6, basis="api617", applied=self.L12, coefficient=500))["output"]
        self.assertEqual(out["coefficientSource"], "user-entered (differs from API 617 eq. (E.1b) 927)")
        self.assertEqual(out["allowable"], 3000.0)

    def test_nema_sm23_basis_needs_the_coefficient(self):
        with self.assertRaisesRegex(ValueError, "coefficient is required"):
            nl.nema_sm23(dict(NPS=8, basis="nema-sm23", applied=self.L12))
        res = nl.nema_sm23(dict(NPS=8, basis="nema-sm23", coefficient=400, applied=six(200, 300, 600, 300, 400, 0)))
        self.assertEqual((res["output"]["allowable"], res["output"]["ratio"], res["status"]), (3200.0, 0.8125, "pass"))
        self.assertEqual(res["output"]["coefficientSource"], "user-entered")
        self.assertFalse(any("coefficient not entered" in w for w in res["warnings"]))

    def test_api611_and_api612_need_the_coefficient_and_keep_their_label(self):
        for basis, label in (("api611", "API 611 Annex I eq. (I.1b)"), ("api612", "API 612 Annex D eq. (D.1b)")):
            with self.assertRaisesRegex(ValueError, "coefficient is required"):
                nl.nema_sm23(dict(NPS=6, basis=basis, applied=self.L12))
            out = nl.nema_sm23(dict(NPS=6, basis=basis, applied=self.L12, coefficient=500))["output"]
            self.assertIn(label, out["basis"])
            self.assertEqual(out["coefficientSource"], "user-entered")

    def test_no_basis_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Select the basis"):
            nl.nema_sm23(dict(NPS=6, applied=self.L12, coefficient=927))
        with self.assertRaisesRegex(ValueError, "Select the basis"):
            nl.nema_sm23(dict(NPS=6, basis="api-617", applied=self.L12))

    def test_validate_mirrors_the_rules(self):
        with self.assertRaisesRegex(ValueError, "basis is required"):
            nl.validate(NEMA, dict(NPS=6, applied=self.L12, coefficient=927))
        with self.assertRaisesRegex(ValueError, 'coefficient is required for basis "nema-sm23"'):
            nl.validate(NEMA, dict(NPS=6, basis="nema-sm23", applied=self.L12))
        self.assertEqual(nl.validate(NEMA, dict(NPS=6, basis="api617", applied=self.L12)), [])
        with self.assertRaisesRegex(ValueError, "coefficient must be > 0"):
            nl.validate(NEMA, dict(NPS=6, basis="api617", applied=self.L12, coefficient=0))

    def test_envelope_lists_the_coefficient_as_user_supplied_only_when_entered(self):
        env = nl.run_module(NEMA, dict(NPS=6, basis="api617", applied=self.L12))
        self.assertEqual(env["user_supplied"], [])
        self.assertEqual(env["result_status"], "calculated")
        row = [c for c in env["checks"] if c["name"] == "3*Fr + Mr against a*De"][0]
        self.assertIn("927 (default)", row["note"])
        env = nl.run_module(NEMA, dict(NPS=6, basis="api617", applied=self.L12, coefficient=927))
        self.assertEqual(env["user_supplied"], ["coefficient"])

    def test_owner_factor_scales_the_default_too(self):
        env = nl.run_module(NEMA, dict(NPS=6, basis="api617", applied=self.L12, ownerFactor=0.5))
        self.assertEqual(env["output"]["coefficient"], 463.5)
        self.assertEqual(env["output"]["allowable"], 2781.0)
        self.assertEqual(env["output"]["coefficientSource"], "API 617 eq. (E.1b) 927 (default) x ownerFactor 0.5")
        self.assertTrue(any("scaled by ownerFactor" in w for w in env["warnings"]))
        self.assertTrue(any("ownerFactor 0.5 applied" in w for w in env["warnings"]))

    def test_cli_exit_2_without_a_basis_or_a_required_coefficient(self):
        r = cli(NL_CLI, NEMA, "--input", json.dumps(dict(NPS=6, applied=self.L12, coefficient=927)))
        self.assertEqual(r.returncode, 2)
        self.assertIn("basis is required", r.stderr)
        r = cli(NL_CLI, NEMA, "--input", json.dumps(dict(NPS=6, basis="api612", applied=self.L12)))
        self.assertEqual(r.returncode, 2)
        self.assertIn('coefficient is required for basis "api612"', r.stderr)
        r = cli(NL_CLI, NEMA, "--input", json.dumps(dict(NPS=6, basis="api617", applied=self.L12)))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["output"]["coefficientSource"], "API 617 eq. (E.1b) 927 (default)")

    def test_fields_and_citation(self):
        names = {f[0]: f for f in nl.FIELDS[NEMA]}
        self.assertTrue(names["basis"][2])            # required
        self.assertFalse(names["coefficient"][2])     # optional (api617 only)
        self.assertIn("no default basis", nl.CITATIONS[NEMA])
        self.assertIn("eq. (E.1b)", nl.CITATIONS[NEMA])


# --------------------------------------------------------------------------- S5c: |Fy| in the Annex F vertical in-line stress


class AnnexFAbsoluteFy(unittest.TestCase):

    def _si_case(self) -> dict:
        from test_nozzle_load import fixture_input  # the test-side annexF constants, not shipped
        fx = parity.load(ANNEXF)
        cases = [c for c in fx["cases"] if c["input"].get("pumpType") == "vertical-inline"]
        self.assertEqual(len(cases), 1)
        return fixture_input(ANNEXF, cases[0])

    def test_engine_re_derived_case(self):
        inp = self._si_case()
        self.assertLess(inp["suctionApplied"]["Fy"], 0)              # the compressive suction case
        out = nl.REGISTRY[ANNEXF](inp)["output"]
        self.assertAlmostEqual(out["suctionSigmaL"], 3.4673, delta=1e-4)     # 0.9.2: 2.7618
        self.assertAlmostEqual(out["suctionSigmaP"], 5.7136, delta=1e-4)     # 0.9.2: 5.2203
        self.assertAlmostEqual(out["suctionStressRatio"], 0.13936, delta=1e-5)
        self.assertAlmostEqual(out["governingRatio"], 0.20268, delta=1e-5)  # discharge F.6, unchanged

    def test_sign_of_fy_does_not_change_the_stress(self):
        inp = self._si_case()
        flipped = json.loads(json.dumps(inp))
        flipped["suctionApplied"]["Fy"] = -flipped["suctionApplied"]["Fy"]
        a = nl.REGISTRY[ANNEXF](inp)["output"]
        b = nl.REGISTRY[ANNEXF](flipped)["output"]
        self.assertEqual(a["suctionSigmaL"], b["suctionSigmaL"])
        self.assertEqual(a["suctionSigmaP"], b["suctionSigmaP"])


# --------------------------------------------------------------------------- N9: no compression credit in the screen


class ScreenCompression(unittest.TestCase):
    BASE = dict(P=500, F=-2000, M=50000, G=6, ratedPressure=1975)

    def test_fixture_parity_four_cases(self):
        self.assertEqual(parity.run_fixture(bf.REGISTRY, SCREEN), [])
        self.assertEqual(len(parity.load(SCREEN)["cases"]), 4)

    def test_default_takes_no_credit(self):
        res = bf.flange_equivalent_pressure(dict(self.BASE))
        out = res["output"]
        self.assertEqual((out["Fapplied"], out["forceTerm"]), (0.0, 0.0))
        self.assertAlmostEqual(out["Pe"], 1678.926, delta=1e-3)
        self.assertAlmostEqual(out["utilization"], 0.8501, delta=1e-4)
        self.assertEqual([w for w in res["warnings"] if "taken as zero" in w],
                         ["Compressive axial force F = -2000 taken as zero — compression is not credited against Pe "
                          "unless creditCompression is set per the owner specification."])

    def test_credit_on_request_is_warned(self):
        res = bf.flange_equivalent_pressure(dict(self.BASE, creditCompression=True))
        out = res["output"]
        self.assertEqual(out["Fapplied"], -2000.0)
        self.assertAlmostEqual(out["forceTerm"], -70.736, delta=1e-3)
        self.assertAlmostEqual(out["Pe"], 1608.19, delta=1e-3)
        self.assertAlmostEqual(out["utilization"], 0.8143, delta=1e-4)
        self.assertTrue(any(w.startswith("Compressive axial force CREDITED") for w in res["warnings"]))
        self.assertFalse(any("taken as zero" in w for w in res["warnings"]))

    def test_tension_is_unchanged(self):
        out = bf.flange_equivalent_pressure(dict(self.BASE, F=2000))["output"]
        self.assertEqual(out["Fapplied"], 2000.0)
        self.assertAlmostEqual(out["Pe"], 1749.661, delta=1e-3)

    def test_cli_layer_no_longer_pre_clamps_and_warns_once(self):
        env = bf.run_module(SCREEN, dict(self.BASE))
        self.assertEqual(env["output"]["Fapplied"], 0.0)
        self.assertEqual(env["inputs"]["F"], -2000)
        self.assertEqual(len([w for w in env["warnings"] if "ompressive" in w]), 1)
        self.assertAlmostEqual(env["output"]["Pe"], 1678.926, delta=1e-3)
        env = bf.run_module(SCREEN, dict(self.BASE, creditCompression=True))
        self.assertEqual(env["output"]["Fapplied"], -2000.0)
        self.assertEqual(len([w for w in env["warnings"] if "ompressive" in w]), 1)

    def test_output_order_follows_the_engine(self):
        out = bf.flange_equivalent_pressure(dict(self.BASE))["output"]
        self.assertEqual(list(out)[:5], ["momentTerm", "Fapplied", "forceTerm", "Pe", "utilization"])


# --------------------------------------------------------------------------- release mechanics


class ReleaseMechanics(unittest.TestCase):

    def test_fixture_snapshot_is_whole(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "calc-core", "MANIFEST.json"), encoding="utf-8") as fh:
            man = json.load(fh)
        self.assertEqual(man["modules"][LEAK]["cases"], 4)
        self.assertEqual(man["modules"][NEMA]["cases"], 3)
        self.assertEqual(man["modules"][SCREEN]["cases"], 4)
        self.assertEqual(man["modules"][ANNEXF]["cases"], 4)

    def test_result_words_unchanged(self):
        for mod in (pd, nl, bf):
            self.assertEqual(tuple(mod.RESULT_STATUS),
                             ("calculated", "screening", "manual check required", "assumed", "pointer only", "not checked"))


if __name__ == "__main__":
    unittest.main()
