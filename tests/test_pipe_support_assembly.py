"""Parity + behaviour tests for the pipe-support assembly cascade (assembly.py).

Standard library only. Two layers:
  1. Goldens generated from the REAL TypeScript engine (tests/golden/pipe-support/assembly.json):
     the full output, warnings, status and structure must reproduce - numbers within
     1e-6 relative or 1e-9 absolute, everything else exactly. Non-finite numbers are
     stored as the strings "Infinity" / "-Infinity" / "NaN".
  2. The behaviours of calc-core's support-assembly.test.ts, restated.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import copy
import json
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts")
GOLDEN = os.path.join(ROOT, "tests", "golden", "pipe-support", "assembly.json")
sys.path.insert(0, SCRIPTS)

from pipe_support.assembly import CSA_PRESETS, analyze_assembly  # noqa: E402
from pipe_support.common import InputError  # noqa: E402

_NONFINITE = {"Infinity": math.inf, "-Infinity": -math.inf, "NaN": math.nan}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def compare(exp, act, path="$"):
    """Return a list of mismatch descriptions (empty == equal)."""
    if isinstance(exp, str) and exp in _NONFINITE and _num(act):
        e = _NONFINITE[exp]
        if math.isnan(e):
            return [] if math.isnan(act) else [f"{path}: expected NaN, got {act!r}"]
        return [] if act == e else [f"{path}: expected {exp}, got {act!r}"]
    if _num(exp):
        if not _num(act):
            return [f"{path}: expected number {exp!r}, got {act!r}"]
        if math.isnan(act) or math.isinf(act):
            return [f"{path}: expected {exp!r}, got {act!r}"]
        if abs(act - exp) <= 1e-9 or abs(act - exp) <= 1e-6 * abs(exp):
            return []
        return [f"{path}: expected {exp!r}, got {act!r}"]
    if isinstance(exp, dict):
        if not isinstance(act, dict):
            return [f"{path}: expected object, got {act!r}"]
        out = []
        if set(exp) != set(act):
            out.append(f"{path}: keys differ: missing {sorted(set(exp) - set(act))} extra {sorted(set(act) - set(exp))}")
        for k in exp:
            if k in act:
                out += compare(exp[k], act[k], f"{path}.{k}")
        return out
    if isinstance(exp, list):
        if not isinstance(act, list) or len(exp) != len(act):
            return [f"{path}: list mismatch (expected {len(exp)} items, got {act if not isinstance(act, list) else len(act)})"]
        out = []
        for i, (e, a) in enumerate(zip(exp, act)):
            out += compare(e, a, f"{path}[{i}]")
        return out
    return [] if exp == act else [f"{path}: expected {exp!r}, got {act!r}"]


def _load():
    with open(GOLDEN, encoding="utf-8") as fh:
        return json.load(fh)


class GoldenParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _load()

    def test_golden_file_shape(self):
        self.assertEqual(self.data["module"], "structural.support-assembly")
        cases = self.data["cases"]
        self.assertGreaterEqual(len(cases), 40)
        types = {c["input"].get("type") for c in cases}
        self.assertTrue({"t-post", "multi-tier", "cantilever", "goalpost", "trapeze"} <= types)
        self.assertGreaterEqual(sum(1 for c in cases if "error" in c), 3)

    def test_golden_covers_pr138_branches(self):
        """The goldens exercise the J4 split rows, J10.1 (required / not required / near top) and the t/2 rule."""
        clauses, labels, warns = [], set(), []
        for c in self.data["cases"]:
            if "output" not in c:
                continue
            warns.extend(c["warnings"])
            for st in c["output"]["stages"]:
                for ck in st["checks"]:
                    labels.add(ck["label"])
                    clauses.append(ck["clause"])
        self.assertTrue({"Base-metal tension yielding", "Base-metal tension rupture", "Base-metal shear rupture",
                         "Column flange local bending"} <= labels)
        joined = " | ".join(clauses)
        for frag in ("(both faces of the arm element)", "in per line", "×0.5 within 10·tf of the column top"):
            self.assertIn(frag, joined)
        self.assertTrue(any("J10-1 (6.25·Fy·tf², tf = " in x and "×0.5" not in x for x in clauses))
        self.assertTrue(any("J10.1 column-flange local bending not required" in w for w in warns))
        self.assertTrue(any(ck["label"] == "Column flange local bending" and ck["status"] == "fail"
                            for c in self.data["cases"] if "output" in c
                            for st in c["output"]["stages"] for ck in st["checks"]))
        self.assertTrue(any(c["input"]["arms"][0]["shape"].startswith(("HSS", "PIPE")) for c in self.data["cases"]
                            if "output" in c))

    def test_every_golden_reproduces_in_full(self):
        failures = []
        for i, case in enumerate(self.data["cases"]):
            inp = copy.deepcopy(case["input"])
            if "error" in case:
                try:
                    analyze_assembly(inp)
                except InputError as exc:
                    if str(exc) != case["error"]:
                        failures.append(f"case {i}: error text {str(exc)!r} != {case['error']!r}")
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"case {i}: raised {type(exc).__name__}: {exc}")
                else:
                    failures.append(f"case {i}: expected error {case['error']!r}, got a result")
                continue
            try:
                got = analyze_assembly(inp)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"case {i}: raised {type(exc).__name__}: {exc}")
                continue
            for m in compare(case["output"], got["output"], "output"):
                failures.append(f"case {i}: {m}")
            if got["status"] != case["status"]:
                failures.append(f"case {i}: status {got['status']!r} != {case['status']!r}")
            for m in compare(case["warnings"], got["warnings"], "warnings"):
                failures.append(f"case {i}: {m}")
            if got["module"] != "structural.support-assembly":
                failures.append(f"case {i}: module {got['module']!r}")
        self.assertEqual(failures, [], "\n" + "\n".join(failures[:60]))

    def test_input_is_not_mutated(self):
        case = self.data["cases"][1]
        inp = copy.deepcopy(case["input"])
        before = copy.deepcopy(inp)
        analyze_assembly(inp)
        self.assertEqual(inp, before)


# --------------------------------------------------------------------------- #
# Behaviour tests (support-assembly.test.ts)
# --------------------------------------------------------------------------- #
A36 = {"Fy": 36, "Fu": 58}


def csa1(**over):
    preset = copy.deepcopy(CSA_PRESETS["csa-type-1"])
    inp = {"method": "LRFD", "tag": "PS-101", "material": A36, **preset}
    inp["arms"] = [{"shape": "W6X15", "elevation": 96, "projection": 24, "pipes": [
        {"tag": "6-P-1201", "offset": 8, "vertical": 1.2, "transverse": 0.2},
        {"tag": "6-P-1202", "offset": 18, "vertical": 1.5, "transverse": 0.25}]}]
    inp["pier"] = {"pierLength": 16, "pierWidth": 16, "pierHeight": 24, "fc": 4000, "footingLength": 36,
                   "footingWidth": 36, "footingThickness": 12, "allowableBearing": 3, "frictionCoefficient": 0.35}
    inp.update(over)
    return inp


def one_pipe(**p):
    return csa1(arms=[{"shape": "W6X15", "elevation": 96, "projection": 24,
                       "pipes": [{"offset": 8, "vertical": 1.2, **p}]}])


def stage(r, component):
    return next(s for s in r["output"]["stages"] if s["component"] == component)


class CascadeBehaviour(unittest.TestCase):
    def test_runs_every_stage(self):
        r = analyze_assembly(csa1())
        comps = [s["component"] for s in r["output"]["stages"]]
        for c in ("arm", "weld", "column", "baseplate", "anchorage", "pier"):
            self.assertIn(c, comps)

    def test_base_reactions(self):
        r = analyze_assembly(csa1())
        b = r["output"]["baseReactions"]
        self.assertAlmostEqual(b["axial"], 2.7, 4)
        self.assertAlmostEqual(b["moment"], 79.8, 4)
        self.assertAlmostEqual(b["momentY"], 0, 4)
        self.assertAlmostEqual(b["torsion"], 0, 4)
        self.assertAlmostEqual(b["shear"], 0.45, 4)
        self.assertEqual(r["output"]["lateral"], {"transverse": 0.45, "longitudinal": 0})

    def test_increased_load_propagates_to_foundation(self):
        footing = {"pier": {**csa1()["pier"], "footingLength": 84, "footingWidth": 84, "footingThickness": 18}}
        light = analyze_assembly(csa1(**footing))
        heavy = analyze_assembly(csa1(**footing, arms=[{"shape": "W6X15", "elevation": 96, "projection": 24,
                                                         "pipes": [{"offset": 18, "vertical": 15, "transverse": 2}]}]))

        def soil(r):
            return next(c for c in stage(r, "pier")["checks"] if c["label"].startswith("Soil bearing"))["demand"]
        self.assertGreater(soil(heavy), soil(light))
        self.assertGreater(heavy["output"]["governingRatio"], light["output"]["governingRatio"])

    def test_legacy_lateral_load(self):
        no_wind = analyze_assembly(csa1())
        wind = analyze_assembly(csa1(lateralLoad=1.0))
        self.assertAlmostEqual(wind["output"]["baseReactions"]["moment"] - no_wind["output"]["baseReactions"]["moment"], 96, 4)
        self.assertAlmostEqual(wind["output"]["baseReactions"]["shear"] - no_wind["output"]["baseReactions"]["shear"], 1.0, 4)
        self.assertEqual(wind["output"]["lateral"], no_wind["output"]["lateral"])

    def test_governing_names_and_summary(self):
        r = analyze_assembly(csa1())
        o = r["output"]
        self.assertTrue(o["governingStage"])
        self.assertTrue(o["governingCheck"])
        s = o["summary"]
        self.assertEqual(s["pass"] + s["fail"] + s["na"], len(o["stages"]))

    def test_arm_deflection_is_its_own_check(self):
        arm = stage(analyze_assembly(csa1()), "arm")
        self.assertTrue(any(c["label"].startswith("Deflection") for c in arm["checks"]))

    def test_grossly_overloaded_arm_fails(self):
        r = analyze_assembly(csa1(arms=[{"shape": "L3X3X1/4", "elevation": 96, "projection": 48,
                                         "pipes": [{"offset": 48, "vertical": 40}]}]))
        self.assertEqual(r["status"], "fail")
        self.assertGreater(r["output"]["governingRatio"], 1)

    def test_infinity_wins_the_rollup(self):
        # A 3 ft footing under 79.8 kip*in / 2.7 kip loses the resultant: soil bearing = Infinity.
        r = analyze_assembly(csa1())
        pier = stage(r, "pier")
        self.assertEqual(pier["ratio"], math.inf)
        self.assertEqual(r["output"]["governingRatio"], math.inf)
        self.assertEqual(r["output"]["governingStage"], "Pier and soil")
        self.assertEqual(r["status"], "fail")


class PipeFrameLoads(unittest.TestCase):
    def test_transverse_acts_along_arm(self):
        r = analyze_assembly(one_pipe(transverse=1.0))
        b = r["output"]["baseReactions"]
        self.assertAlmostEqual(b["moment"], 105.6, 4)
        self.assertAlmostEqual(b["momentY"], 0, 4)
        self.assertAlmostEqual(b["torsion"], 0, 4)
        self.assertAlmostEqual(b["shear"], 1.0, 4)
        self.assertEqual(r["output"]["lateral"], {"transverse": 1.0, "longitudinal": 0})
        arm = stage(r, "arm")
        self.assertTrue(any(("compression" in c["label"].lower() or "axial" in c["label"].lower()) and c["demand"] > 0
                            for c in arm["checks"]))

    def test_longitudinal_acts_across_arm(self):
        r = analyze_assembly(one_pipe(longitudinal=0.5))
        b = r["output"]["baseReactions"]
        self.assertAlmostEqual(b["moment"], 9.6, 4)
        self.assertAlmostEqual(b["momentY"], 48, 4)
        self.assertAlmostEqual(b["torsion"], 4, 4)
        self.assertAlmostEqual(b["shear"], 0.5, 4)
        self.assertEqual(r["output"]["lateral"], {"transverse": 0, "longitudinal": 0.5})
        arm = stage(r, "arm")
        self.assertTrue(any("minor" in c["label"].lower() and c["demand"] > 0 for c in arm["checks"]))
        self.assertTrue(any("torsion" in w and "not checked" in w for w in r["warnings"]))

    def test_out_of_plane_moment_reaches_base_stages(self):
        without = analyze_assembly(one_pipe())
        with_l = analyze_assembly(one_pipe(longitudinal=0.5))
        self.assertGreater(stage(with_l, "anchorage")["ratio"], stage(without, "anchorage")["ratio"])
        self.assertGreater(stage(with_l, "baseplate")["ratio"], stage(without, "baseplate")["ratio"])
        self.assertTrue(any("M_eq" in w for w in with_l["warnings"]))

    def test_horizontal_loads_combine_as_magnitudes(self):
        r = analyze_assembly(csa1(arms=[{"shape": "W6X15", "elevation": 96, "projection": 24, "pipes": [
            {"offset": 8, "vertical": 1.2, "longitudinal": 0.5, "transverse": 0.3},
            {"offset": 18, "vertical": 1.5, "longitudinal": -0.5, "transverse": -0.3}]}]))
        self.assertEqual(r["output"]["lateral"], {"transverse": 0.6, "longitudinal": 1.0})
        self.assertAlmostEqual(r["output"]["baseReactions"]["momentY"], 96, 4)
        self.assertAlmostEqual(r["output"]["baseReactions"]["torsion"], 0.5 * 8 + 0.5 * 18, 4)

    def test_two_tiers_each_at_own_elevation(self):
        preset = copy.deepcopy(CSA_PRESETS["csa-type-2"])
        r = analyze_assembly({"method": "LRFD", "material": A36, **preset, "arms": [
            {"shape": "L4X3X3/8", "elevation": 96, "projection": 36, "pipes": [{"offset": 24, "vertical": 0.8, "longitudinal": 0.2}]},
            {"shape": "L4X3X3/8", "elevation": 66, "projection": 36, "pipes": [{"offset": 24, "vertical": 0.6, "longitudinal": 0.4}]}]})
        self.assertAlmostEqual(r["output"]["baseReactions"]["momentY"], 0.2 * 96 + 0.4 * 66, 4)
        self.assertAlmostEqual(r["output"]["baseReactions"]["shear"], 0.6, 4)


class Configurations(unittest.TestCase):
    def test_multi_tier_accumulates(self):
        preset = copy.deepcopy(CSA_PRESETS["csa-type-2"])
        r = analyze_assembly({"method": "LRFD", "tag": "PS-202", "material": A36, **preset, "arms": [
            {"shape": "L4X3X3/8", "elevation": 96, "projection": 36, "pipes": [{"offset": 24, "vertical": 0.8}]},
            {"shape": "L4X3X3/8", "elevation": 66, "projection": 36, "pipes": [{"offset": 24, "vertical": 0.6}]}]})
        self.assertEqual(len([s for s in r["output"]["stages"] if s["component"] == "arm"]), 2)
        self.assertAlmostEqual(r["output"]["baseReactions"]["axial"], 1.4, 4)
        self.assertAlmostEqual(r["output"]["baseReactions"]["moment"], 1.4 * 24, 4)

    def test_goalpost_halves_the_column_demand(self):
        single = analyze_assembly(csa1())
        goal = analyze_assembly(csa1(type="goalpost", columnSpacing=60))
        self.assertAlmostEqual(goal["output"]["baseReactions"]["axial"], single["output"]["baseReactions"]["axial"] / 2, 4)

    def test_goalpost_without_spacing_warns(self):
        r = analyze_assembly(csa1(type="goalpost"))
        self.assertTrue(any("without a column spacing" in w for w in r["warnings"]))

    def test_cantilever_stops_at_arm(self):
        r = analyze_assembly(csa1(type="cantilever"))
        comps = [s["component"] for s in r["output"]["stages"]]
        self.assertNotIn("column", comps)
        self.assertIn("arm", comps)

    def test_missing_base_plate_warns(self):
        r = analyze_assembly(csa1(baseplate=None, pier=None))
        self.assertTrue(any("No base plate" in w for w in r["warnings"]))

    def test_missing_pier_warns(self):
        r = analyze_assembly(csa1(pier=None))
        self.assertTrue(any("No pier or soil data" in w for w in r["warnings"]))

    def test_assumed_column_k_flagged(self):
        r = analyze_assembly(csa1())
        self.assertTrue(any("K = 2.1" in w for w in r["warnings"]))
        r2 = analyze_assembly(csa1(columnK=1.2))
        self.assertFalse(any("K = 2.1" in w for w in r2["warnings"]))

    def test_asd_ratios_higher_than_lrfd(self):
        lrfd = analyze_assembly(csa1(method="LRFD"))
        asd = analyze_assembly(csa1(method="ASD"))
        self.assertGreater(stage(asd, "column")["ratio"], stage(lrfd, "column")["ratio"])

    def test_uplift_reported_on_net_negative_axial(self):
        r = analyze_assembly(csa1(columnSelfWeight=-4.0))
        b = r["output"]["baseReactions"]
        self.assertAlmostEqual(b["axial"], -1.3, 4)
        self.assertAlmostEqual(b["uplift"], 1.3, 4)

    def test_errors(self):
        with self.assertRaisesRegex(InputError, "at least one arm"):
            analyze_assembly(csa1(arms=[]))
        with self.assertRaisesRegex(InputError, "columnHeight must be positive"):
            analyze_assembly(csa1(columnHeight=0))
        with self.assertRaisesRegex(InputError, "columnShape is required"):
            analyze_assembly(csa1(columnShape=None))
        with self.assertRaisesRegex(InputError, "shape not in dataset"):
            analyze_assembly(csa1(columnShape="W99X999"))

    def test_custom_resolver_is_used(self):
        calls = []

        def resolver(label):
            from pipe_support.aisc import find_shape, section_from_row
            calls.append(label)
            return section_from_row(find_shape(label))
        analyze_assembly(csa1(), resolve_shape=resolver)
        self.assertEqual(calls, ["W6X15", "W6X15"])

    def test_presets_shape(self):
        self.assertEqual(set(CSA_PRESETS), {"csa-type-1", "csa-type-2"})
        self.assertEqual(CSA_PRESETS["csa-type-1"]["type"], "t-post")
        self.assertEqual(CSA_PRESETS["csa-type-2"]["type"], "multi-tier")
        self.assertEqual(len(CSA_PRESETS["csa-type-2"]["arms"]), 2)


if __name__ == "__main__":
    unittest.main()
