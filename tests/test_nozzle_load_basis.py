"""nozzle-load 0.8.0: the shared project basis record (B8).

The fill map of this skill: api610-annexf `units` <- units.system; pvp2011-allowables
`designTempF` <- the design state and `ownerFactorBasis` <- owner_practice; the equipment axes map,
the unit system and the owner practice are carried to the sheet. Conflicts exit 2 with the shared
message. The record never reaches the engine, so fixture parity is untouched.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "nozzle-load")
CLI = os.path.join(SKILL, "scripts", "nozzle_load.py")
EXAMPLE = os.path.join(SKILL, "scripts", "examples", "project-basis.example.json")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import nozzle_load as nl  # noqa: E402
import parity  # noqa: E402


def six(v=0.0):
    return {k: v for k in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")}


def record():
    with open(EXAMPLE, encoding="utf-8") as fh:
        return json.load(fh)


def annexf_usc():
    return dict(componentMultiple=2.0, resultantDenominator=1.5, interactionLimit=2.0, centreForceFactor=1.5,
                centreMyFactor=2.0)


ANNEXF = dict(pumpType="horizontal", suctionApplied=six(10), dischargeApplied=six(10),
              suctionAllowable=six(1000), dischargeAllowable=six(1000), annexF=annexf_usc(),
              suctionPosition=dict(x=0, y=0, z=0), dischargePosition=dict(x=0, y=0, z=0))
PVP = dict(table="1A", NPS=6, row=six(1000), T=0.25, S_vessel=18800, S_nozzle=17100)
CHECK = dict(standard="datasheet", applied=six(100), allowable=six(1000))


def cli(*args):
    return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, encoding="utf-8")


class Fill(unittest.TestCase):

    def test_annexf_units_are_filled_from_the_record(self):
        env = nl.run_module("connections.api610-annexf", dict(ANNEXF, project_basis=record()))
        self.assertEqual(env["inputs"]["units"], "USC")
        self.assertEqual(env["output"]["units"], "USC")
        used = {u["input"]: u for u in env["project_basis_applied"]["fields_used"] if u["input"]}
        self.assertEqual(used["units"], {"input": "units", "basis": "units.system", "action": "filled"})

    def test_annexf_si_record_fills_si(self):
        rec = record()
        rec["units"] = {"system": "SI"}
        inp = dict(ANNEXF, annexF=dict(annexf_usc(), sigmaPLimit=1.0, kSigma=1.0, kTau=1.0), project_basis=rec)
        self.assertEqual(nl.run_module("connections.api610-annexf", inp)["inputs"]["units"], "SI")

    def test_annexf_units_present_and_equal_is_agreed(self):
        env = nl.run_module("connections.api610-annexf", dict(ANNEXF, units="USC", project_basis=record()))
        used = [u for u in env["project_basis_applied"]["fields_used"] if u["input"] == "units"]
        self.assertEqual(used[0]["action"], "agreed")

    def test_annexf_units_conflict_exits_2(self):
        with self.assertRaisesRegex(ValueError, r"^project_basis\.units\.system conflicts with input units$"):
            nl.run_module("connections.api610-annexf", dict(ANNEXF, units="SI", project_basis=record()))

    def test_pvp_design_temperature_is_filled_from_the_design_state(self):
        env = nl.run_module("equipment.pvp2011-allowables", dict(PVP, project_basis=record()))
        self.assertEqual(env["inputs"]["designTempF"], 400)
        self.assertIn({"input": "designTempF", "basis": "states[role=design|first].T_F", "action": "filled"},
                      env["project_basis_applied"]["fields_used"])

    def test_pvp_design_temperature_falls_back_to_the_first_state(self):
        rec = record()
        rec["states"] = [rec["states"][0]]
        env = nl.run_module("equipment.pvp2011-allowables", dict(PVP, project_basis=rec))
        self.assertEqual(env["inputs"]["designTempF"], 350)

    def test_pvp_design_temperature_conflict_exits_2(self):
        with self.assertRaisesRegex(ValueError, r"^project_basis\.states\[role=design\|first\]\.T_F conflicts with "
                                                r"input designTempF$"):
            nl.run_module("equipment.pvp2011-allowables", dict(PVP, designTempF=350, project_basis=record()))

    def test_pvp_design_temperature_agreed(self):
        env = nl.run_module("equipment.pvp2011-allowables", dict(PVP, designTempF=400, project_basis=record()))
        used = [u for u in env["project_basis_applied"]["fields_used"] if u["input"] == "designTempF"]
        self.assertEqual(used[0]["action"], "agreed")

    def test_pvp_owner_factor_basis_label_comes_from_owner_practice(self):
        env = nl.run_module("equipment.pvp2011-allowables", dict(PVP, ownerFactor=0.5, project_basis=record()))
        self.assertEqual(env["inputs"]["ownerFactorBasis"], "Owner piping stress practice user to confirm")
        self.assertTrue(any("Owner factor x0.5 (Owner piping stress practice user to confirm)" in ln
                            for ln in env["output"]["log"]))

    def test_a_label_the_user_wrote_is_kept_and_is_never_a_conflict(self):
        env = nl.run_module("equipment.pvp2011-allowables",
                            dict(PVP, ownerFactor=0.5, ownerFactorBasis="project spec", project_basis=record()))
        self.assertEqual(env["inputs"]["ownerFactorBasis"], "project spec")
        self.assertFalse([u for u in env["project_basis_applied"]["fields_used"] if u["input"] == "ownerFactorBasis"])

    def test_the_owner_factor_value_is_never_taken_from_the_record(self):
        rec = record()
        rec["owner_practice"][0]["items"] = [{"name": "nozzle load design-stage fraction", "value": 0.5}]
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=rec))
        self.assertNotIn("ownerFactor", env["inputs"])
        self.assertEqual(env["output"]["ratios"]["Fx"], 0.1)
        self.assertTrue(any("'nozzle load design-stage fraction' = 0.5" in w and "no ownerFactor was supplied" in w
                            for w in env["warnings"]))

    def test_modules_with_no_slot_still_carry_the_record_to_the_sheet(self):
        for module, inp in (("connections.nozzle-load-check", CHECK),
                            ("connections.nema-sm23", dict(NPS=6, applied=six(10), coefficient=500)),
                            ("equipment.nozzle-load-sum", dict(standard="s", nozzles=[six(1), six(2)], limits=six(100))),
                            ("equipment.api650-annexp-ordinates",
                             dict(FR=1e5, ML=1e8, MC=-2e8, a=500, R=10000, t=25, L=1000, P=0.1, YF=2, YL=4, YC=5))):
            env = nl.run_module(module, dict(inp, project_basis=record()))
            used = {(u["basis"], u["action"]) for u in env["project_basis_applied"]["fields_used"]}
            self.assertEqual(used, {("units.system", "noted"), ("equipment_axes.nozzle_axis_map", "noted"),
                                    ("owner_practice", "noted")}, module)
            self.assertIn("equipment axes", env["project_basis_section"].lower(), module)
            self.assertIn("nozzle_axis_map=Fx=+X", env["project_basis_section"], module)

    def test_no_record_no_basis_keys(self):
        env = nl.run_module("connections.nozzle-load-check", CHECK)
        self.assertNotIn("project_basis_applied", env)
        self.assertNotIn("project_basis_section", env)

    def test_the_record_is_not_an_unknown_input_and_is_not_echoed_as_one(self):
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=record()))
        self.assertNotIn("project_basis", env["inputs"])
        with self.assertRaisesRegex(ValueError, "unknown input field"):
            nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis_typo=record()))

    def test_the_callers_dict_is_not_modified(self):
        inp = dict(PVP, project_basis=record())
        snapshot = copy.deepcopy(inp)
        nl.run_module("equipment.pvp2011-allowables", inp)
        self.assertEqual(inp, snapshot)

    def test_the_record_changes_no_engine_output(self):
        for module, inp in (("connections.nozzle-load-check", CHECK), ("equipment.pvp2011-allowables", dict(PVP, designTempF=400))):
            plain = nl.run_module(module, inp)
            with_basis = nl.run_module(module, dict(inp, project_basis=record()))
            self.assertEqual(plain["output"], with_basis["output"], module)
            self.assertEqual(plain["status"], with_basis["status"], module)

    def test_parity_registry_is_untouched(self):
        # the fill and the status layers live in run_module; the engine functions never see the record
        registry = dict(nl.REGISTRY)
        for module in ("connections.nozzle-load-check", "connections.nema-sm23"):
            self.assertEqual(parity.run_fixture(registry, module), [], module)


class SiRecord(unittest.TestCase):

    def test_si_record_stops_the_usc_only_modules(self):
        rec = record()
        rec["units"] = {"system": "SI"}
        for module, inp in (("connections.nema-sm23", dict(NPS=6, applied=six(10), coefficient=500)),
                            ("equipment.pvp2011-allowables", PVP)):
            with self.assertRaisesRegex(ValueError, r"project_basis\.units\.system is SI but %s takes USC inputs only"
                                        % module.replace(".", r"\.")):
                nl.run_module(module, dict(inp, project_basis=rec))

    def test_si_record_is_noted_for_the_unit_agnostic_modules(self):
        rec = record()
        rec["units"] = {"system": "SI"}
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=rec))
        self.assertIn("system=SI", env["project_basis_section"])


class Assumed(unittest.TestCase):

    def test_assumed_items_are_copied_verbatim_and_listed_first(self):
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=record()))
        self.assertEqual(env["project_basis_applied"]["assumptions"],
                         [{"item": "Corrosion allowance per the line list", "status": "ASSUMED",
                           "note": "line list not yet issued", "owner": "lead"}])
        section = env["project_basis_section"]
        self.assertTrue(section.startswith("## 1. Basis\n\n**ASSUMED - confirm before issue:**\n- Corrosion allowance"))
        self.assertLess(section.index("**ASSUMED"), section.index("| Basis item"))
        self.assertEqual(env["project_basis_applied"]["conflicts"], [])
        self.assertEqual(env["project_basis_applied"]["schema"], "pipingtoolset.project-basis/1")

    def test_a_confirmed_item_is_not_listed_as_assumed(self):
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=record()))
        self.assertNotIn("Design state governs pressure design", env["project_basis_section"].split("| Basis item")[0])

    def test_no_assumed_item_says_so(self):
        rec = record()
        rec["assumptions"] = [{"item": "x", "status": "confirmed"}]
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=rec))
        self.assertIn("No ASSUMED items in the project basis record.", env["project_basis_section"])

    def test_the_section_is_ascii(self):
        env = nl.run_module("connections.nozzle-load-check", dict(CHECK, project_basis=record()))
        self.assertTrue(all(ord(c) < 128 for c in env["project_basis_section"]))


class CommandLine(unittest.TestCase):

    def _write(self, tmp, name, obj):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return path

    def test_file_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = cli("equipment.pvp2011-allowables", "--input", json.dumps(PVP),
                    "--project-basis", self._write(tmp, "pb.json", record()))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = json.loads(r.stdout)
        self.assertEqual(env["inputs"]["designTempF"], 400)
        self.assertIn("project_basis_applied", env)

    def test_key_only(self):
        r = cli("equipment.pvp2011-allowables", "--input", json.dumps(dict(PVP, project_basis=record())))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["inputs"]["designTempF"], 400)

    def test_file_and_key_equal_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = cli("equipment.pvp2011-allowables", "--input", json.dumps(dict(PVP, project_basis=record())),
                    "--project-basis", self._write(tmp, "pb.json", record()))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_file_and_key_different_exits_2(self):
        other = record()
        other["code"]["edition"] = "2020"
        with tempfile.TemporaryDirectory() as tmp:
            r = cli("equipment.pvp2011-allowables", "--input", json.dumps(dict(PVP, project_basis=record())),
                    "--project-basis", self._write(tmp, "pb.json", other))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stderr.strip(), "input error: project_basis conflicts with --project-basis file")
        self.assertNotIn("Traceback", r.stderr)

    def test_conflict_with_an_input_exits_2(self):
        r = cli("equipment.pvp2011-allowables", "--input", json.dumps(dict(PVP, designTempF=300, project_basis=record())))
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.states[role=design|first].T_F conflicts with input designTempF", r.stderr)

    def test_unknown_key_and_missing_file_exit_2(self):
        bad = record()
        bad["surprise"] = 1
        r = cli("connections.nozzle-load-check", "--input", json.dumps(dict(CHECK, project_basis=bad)))
        self.assertEqual(r.returncode, 2)
        self.assertIn("project_basis.surprise: unknown key", r.stderr)
        r = cli("connections.nozzle-load-check", "--input", json.dumps(CHECK), "--project-basis", "no-such-file.json")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_list_names_the_record(self):
        r = cli("list")
        self.assertEqual(r.returncode, 0)
        self.assertIn("project_basis", r.stdout)
        self.assertIn("--project-basis", r.stdout)


class SkillFiles(unittest.TestCase):

    def test_python_39_grammar(self):
        with open(CLI, encoding="utf-8") as fh:
            src = fh.read()
        ast.parse(src, CLI, feature_version=(3, 9))
        self.assertTrue(all(ord(c) < 128 for c in src))

    def test_skill_links_the_reference_and_says_reuse_never_relabel(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("references/project-basis.md", text)
        self.assertIn("project_basis", text)
        low = text.lower()
        self.assertIn("never relabel", low)
        self.assertIn("ask only for what is missing", low)

    def test_the_example_record_ships_in_the_skill(self):
        self.assertTrue(os.path.isfile(EXAMPLE))
        self.assertEqual(nl.validate_project_basis(record()), [])


if __name__ == "__main__":
    unittest.main()
