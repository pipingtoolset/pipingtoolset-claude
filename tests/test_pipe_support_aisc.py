"""Parity tests for the pipe-support AISC 360-22 member engine (pipe_support.aisc).

Standard library only. Two layers:
  1. The 14 calc-core `structural.aisc-member` fixture cases (vendored), via the shared harness.
  2. Goldens generated from the REAL TypeScript engine (tests/golden/pipe-support/aisc-member.json):
     the full CalcResult (output, warnings, status) must reproduce - numbers within 1e-6
     relative or 1e-9 absolute, everything else exactly. Non-finite numbers are stored as the
     strings "Infinity" / "-Infinity" / "NaN".

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "pipe-support", "scripts")
GOLDEN = os.path.join(ROOT, "tests", "golden", "pipe-support", "aisc-member.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
from pipe_support import aisc  # noqa: E402
from pipe_support.common import InputError  # noqa: E402

REGISTRY = {"structural.aisc-member": aisc.aisc_member_design}
_NONFINITE = {"Infinity": math.inf, "-Infinity": -math.inf, "NaN": math.nan}


def _decode(v):
    if isinstance(v, str) and v in _NONFINITE:
        return _NONFINITE[v]
    if isinstance(v, list):
        return [_decode(x) for x in v]
    if isinstance(v, dict):
        return {k: _decode(x) for k, x in v.items()}
    return v


def _diff(path, a, e, out):
    """Collect differences between actual `a` and expected `e` (golden)."""
    if isinstance(e, bool) or isinstance(a, bool):
        if a is not e:
            out.append(f"{path}: expected {e!r}, got {a!r}")
    elif isinstance(e, (int, float)):
        if not isinstance(a, (int, float)):
            out.append(f"{path}: expected {e!r}, got {a!r}")
        elif math.isnan(e) or math.isnan(a):
            if not (math.isnan(e) and math.isnan(a)):
                out.append(f"{path}: expected {e!r}, got {a!r}")
        elif math.isinf(e) or math.isinf(a):
            if a != e:
                out.append(f"{path}: expected {e!r}, got {a!r}")
        elif abs(a - e) > max(1e-9, 1e-6 * abs(e)):
            out.append(f"{path}: expected {e!r}, got {a!r}")
    elif isinstance(e, dict):
        if not isinstance(a, dict) or set(a) != set(e):
            out.append(f"{path}: key mismatch {sorted(a) if isinstance(a, dict) else a!r} vs {sorted(e)}")
        else:
            for k in e:
                _diff(f"{path}.{k}", a[k], e[k], out)
    elif isinstance(e, list):
        if not isinstance(a, list) or len(a) != len(e):
            out.append(f"{path}: list length {len(a) if isinstance(a, list) else a!r} vs {len(e)}")
        else:
            for i, (x, y) in enumerate(zip(a, e)):
                _diff(f"{path}[{i}]", x, y, out)
    elif a != e:
        out.append(f"{path}: expected {e!r}, got {a!r}")


def _golden():
    with open(GOLDEN, encoding="utf-8") as fh:
        return json.load(fh)


class CalcCoreFixture(unittest.TestCase):
    def test_piperstr_member_fixture(self):
        fails = parity.run_fixture(REGISTRY, "structural.aisc-member")
        self.assertEqual(fails, [], "\n".join(fails))

    def test_case_count(self):
        self.assertEqual(len(parity.load("structural.aisc-member")["cases"]), 16)  # +1 WT5X11 stem-in-compression (0.3.2), +1 L4X3X3/8 continuousLTR (0.9.0)


class Goldens(unittest.TestCase):
    def test_member_goldens_reproduce_the_ts_engine(self):
        member = _golden()["member"]
        self.assertGreaterEqual(len(member), 60)
        for i, case in enumerate(member):
            label = f"member[{i}] {case['name']}"
            inp = _decode(case["input"])
            if "error" in case:
                with self.assertRaises(InputError, msg=label) as cm:
                    aisc.aisc_member_design(json.loads(json.dumps(inp)))
                self.assertEqual(str(cm.exception), case["error"], label)
                continue
            r = aisc.aisc_member_design(json.loads(json.dumps(inp)))
            diffs = []
            _diff("result", r, _decode(case["output"]), diffs)
            self.assertEqual(diffs, [], f"{label}\n" + "\n".join(diffs))

    def test_cb_from_moments(self):
        for c in _golden()["cb"]:
            self.assertAlmostEqual(aisc.cb_from_moments(*c["args"]), c["output"], places=12)

    def test_deflection_helpers(self):
        g = _golden()
        for c in g["simpleSpan"]:
            self.assertAlmostEqual(aisc.simple_span_deflection(c["args"]), c["output"], places=12)
        for c in g["cantilever"]:
            self.assertAlmostEqual(aisc.cantilever_deflection(c["args"]), c["output"], places=12)
        fns = {"simple": aisc.simple_span_deflection, "cantilever": aisc.cantilever_deflection}
        for c in g["deflectionErrors"]:
            with self.assertRaises(InputError) as cm:
                fns[c["fn"]](c["args"])
            self.assertEqual(str(cm.exception), c["error"])

    def test_section_from_row(self):
        for c in _golden()["sectionFromRow"]:
            diffs = []
            _diff("section", aisc.section_from_row(c["row"]), c["output"], diffs)
            self.assertEqual(diffs, [], c["row"]["label"])

    def test_golden_coverage(self):
        """The goldens exercise every family, both methods and every F/E/G branch family."""
        ok = [c for c in _golden()["member"] if "output" in c]
        self.assertEqual({c["input"]["section"]["kind"] for c in ok},
                         {"I", "C", "T", "L", "HSS-RECT", "HSS-ROUND"})
        self.assertEqual({c["input"]["method"] for c in ok}, {"LRFD", "ASD"})
        clauses = " | ".join(ch["clause"] for c in ok for ch in c["output"]["output"]["checks"])
        for frag in ("F2-1 (yielding)", "F2-2 (inelastic LTB)", "F2-3 (elastic LTB)", "F3-1", "F3-2", "F4", "F5-1",
                     "F6-1", "F6-2", "F7-2", "F7-3", "F7-6", "F8-1", "F8-2", "F8-3", "F9", "F10-1", "F10-6",
                     "F10-7", "E3-2 inelastic", "E3-3 elastic", "E4-2", "E4-3", "E7 effective area", "E7-7",
                     "G2-1", "G2.1(a)", "G4", "G6-1", "D2-1", "D2-2", "H1-1a", "H1-1b",
                     # 360-22 conformance (0.9.0)
                     "F4-1", "F4-2", "F4-3", "F4-13", "F4-14", "F5-2", "F5-7", "F7-8", "F7-9", "F9-6", "F9-7",
                     "F9-14", "F9-15", "F9-16", "F10-2", "F10-3", "F10-5a", "F10 principal", "E4-4", "E5-1",
                     "E5-2", "E5-3", "E5-4", "Fex for a channel", "G3-1", "G5-1", "Case 8", "Case 2"):
            self.assertIn(frag, clauses, frag)
        outs = [c["output"]["output"] for c in ok]
        self.assertTrue(any(o["interactionEquation"] == "H1-1a" for o in outs))
        self.assertTrue(any(o["interactionEquation"] == "H1-1b" for o in outs))
        self.assertTrue(any(ch["ratio"] == "Infinity" for o in outs for ch in o["checks"]))
        self.assertTrue(any(c["output"]["status"] == "fail" for c in ok))
        self.assertTrue(any(ch["label"].startswith("Deflection") for o in outs for ch in o["checks"]))
        slender_adv = [ch for o in outs for ch in o["checks"] if ch.get("advisory") and ch["status"] == "fail"]
        self.assertTrue(slender_adv)


class Hand(unittest.TestCase):
    A992 = {"Fy": 50, "Fu": 65}

    def test_manual_flexure_values(self):
        s = aisc.section_from_row(aisc.find_shape("W12X40"))
        cls = aisc.classify_section(s, self.A992)
        self.assertEqual(cls["flexure"], "compact")
        mn = aisc.flexural_strength(s, self.A992, cls, {"Lb": 1000, "Cb": 1}, "major")
        self.assertAlmostEqual(mn["detail"]["Lp"], 1.76 * s["ry"] * math.sqrt(29000 / 50), places=9)
        mp = aisc.flexural_strength(s, self.A992, cls, {"Lb": 1, "Cb": 1}, "major")
        self.assertAlmostEqual(mp["value"], 50 * s["Zx"], places=9)

    def test_noncompact_flange_w_shapes_at_fy50(self):
        expected = sorted(["W21X48", "W14X99", "W14X90", "W12X65", "W10X12", "W8X31", "W8X10", "W6X15",
                           "W6X9", "W6X8.5"])
        found = sorted(r["label"] for r in aisc.shapes_by_family("W")
                       if aisc.classify_section(aisc.section_from_row(r), self.A992)["flange"]["flex"] != "compact")
        self.assertEqual(found, expected)

    def test_deflection_closed_form(self):
        d = aisc.simple_span_deflection({"w": 0.1, "L": 240, "I": 300, "E": 29000})
        self.assertAlmostEqual(d, 5 * 0.1 * 240 ** 4 / (384 * 29000 * 300), places=9)
        d = aisc.cantilever_deflection({"P": 2, "L": 48, "I": 29.1, "E": 29000})
        self.assertAlmostEqual(d, 2 * 48 ** 3 / (3 * 29000 * 29.1), places=9)

    def test_constants(self):
        self.assertEqual(aisc.PHI["flexure"], 0.9)
        self.assertEqual(aisc.OMEGA["shearRolled"], 1.5)
        self.assertEqual((aisc.DEFAULT_E, aisc.DEFAULT_G), (29000, 11200))
        self.assertEqual(aisc.SLENDERNESS_LIMIT, {"tension": 300, "compression": 200})
        self.assertAlmostEqual(aisc.design(100, "LRFD", 0.9, 1.67), 90.0)
        self.assertAlmostEqual(aisc.design(100, "ASD", 0.9, 1.67), 100 / 1.67)


class ShapeLookup(unittest.TestCase):
    def test_find_shape_normalises(self):
        a = aisc.find_shape("w12x40")
        self.assertIsNotNone(a)
        self.assertEqual(a["label"], "W12X40")
        self.assertIs(aisc.find_shape(" W12 X40 "), a)
        self.assertIsNone(aisc.find_shape("W99X99"))

    def test_shapes_by_family(self):
        cur = aisc.shapes_by_family("W")
        self.assertTrue(cur and all(r["family"] == "W" and r.get("current") is not False for r in cur))
        self.assertGreaterEqual(len(aisc.shapes_by_family("W", current_only=False)), len(cur))
        self.assertEqual(aisc.shapes_by_family("NOPE"), [])

    def test_js_number_formatting(self):
        self.assertEqual(aisc._js_num(6.0), "6")
        self.assertEqual(aisc._js_num(240), "240")
        self.assertEqual(aisc._js_num(0.0000001), "1e-7")
        self.assertEqual(aisc._js_num(0.00001), "0.00001")
        self.assertEqual(aisc._js_num(113.4), "113.4")
        self.assertEqual(aisc._js_num(1e21), "1e+21")


if __name__ == "__main__":
    unittest.main()
