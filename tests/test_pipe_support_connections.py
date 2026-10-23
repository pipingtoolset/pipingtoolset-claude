"""Parity tests for the pipe-support connection calculators (weld, baseplate, pier).

Standard library only. Two layers:
  1. calc-core fixtures (vendored under tests/fixtures/calc-core) via the shared harness.
  2. Goldens generated from the REAL TypeScript engine (tests/golden/pipe-support/*.json):
     the full output, warnings, status and structure must reproduce - numbers within
     1e-6 relative or 1e-9 absolute, everything else exactly. Non-finite numbers are
     stored as the strings "Infinity" / "-Infinity" / "NaN" (JSON has no encoding).

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
GOLDEN = os.path.join(ROOT, "tests", "golden", "pipe-support")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import parity  # noqa: E402
from pipe_support import baseplate, jsmath, pier, weld  # noqa: E402
from pipe_support.common import InputError  # noqa: E402

REGISTRY = {
    "structural.fillet-weld": weld.fillet_weld,
    "structural.baseplate-anchorage": baseplate.base_plate_anchorage,
    "structural.pier-soil": pier.pier_soil,
}
GOLDENS = {  # golden file -> (function, minimum case count)
    "weld": (weld.fillet_weld, 25),
    "baseplate": (baseplate.base_plate_anchorage, 25),
    "pier": (pier.pier_soil, 25),
}
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


class CalcCoreFixtures(unittest.TestCase):
    def _run(self, module):
        fails = parity.run_fixture(REGISTRY, module)
        self.assertEqual(fails, [], "\n".join(fails))

    def test_fillet_weld(self):
        self._run("structural.fillet-weld")

    def test_baseplate_anchorage(self):
        self._run("structural.baseplate-anchorage")

    def test_pier_soil(self):
        self._run("structural.pier-soil")

    def test_case_counts(self):
        for module, n in (("structural.fillet-weld", 4), ("structural.baseplate-anchorage", 4),
                          ("structural.pier-soil", 3)):
            self.assertEqual(len(parity.load(module)["cases"]), n)


class Goldens(unittest.TestCase):
    def _golden(self, name):
        with open(os.path.join(GOLDEN, f"{name}.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_goldens_reproduce_the_ts_engine(self):
        for name, (fn, minimum) in GOLDENS.items():
            g = self._golden(name)
            self.assertGreaterEqual(len(g["cases"]), minimum, name)
            for i, case in enumerate(g["cases"]):
                label = f"{name}[{i}]"
                inp = _decode(case["input"])
                if "error" in case:
                    with self.assertRaises(InputError, msg=label) as cm:
                        fn(dict(inp))
                    self.assertEqual(str(cm.exception), case["error"], label)
                    continue
                r = fn(dict(inp))
                diffs = []
                _diff("output", r["output"], _decode(case["output"]), diffs)
                _diff("warnings", r["warnings"], case["warnings"], diffs)
                if r["status"] != case["status"]:
                    diffs.append(f"status: expected {case['status']!r}, got {r['status']!r}")
                self.assertEqual(r["module"], g["module"], label)
                self.assertEqual(diffs, [], f"{label} input={json.dumps(inp)}\n" + "\n".join(diffs))

    def test_golden_coverage(self):
        """The goldens exercise every branch family the task calls for."""
        w = self._golden("weld")["cases"]
        pats = {c["input"]["pattern"] for c in w if "output" in c}
        self.assertEqual(pats, {"single", "two-parallel", "all-round"})
        self.assertEqual({c["input"]["method"] for c in w}, {"LRFD", "ASD"})
        outs = [c for c in w if "output" in c]
        self.assertTrue(any(c["output"]["directionalFactor"] == 1.5 for c in outs))
        self.assertTrue(any(c["output"]["directionalFactor"] == 1 for c in outs))
        self.assertTrue(any(c["output"]["baseMetalPerInch"] is not None for c in outs))
        self.assertTrue(any(c["status"] == "fail" for c in outs))
        joined = " ".join(x for c in outs for x in c["warnings"])
        for frag in ("below the Table J2.4", "exceeds the J2.2b", "Base-metal shear rupture", "eccentric", "4x the leg"):
            self.assertIn(frag, joined)

        b = [c for c in self._golden("baseplate")["cases"] if "output" in c]
        self.assertEqual({c["input"]["anchorType"] for c in b},
                         {"cast-in", "post-installed-adhesive", "post-installed-mechanical"})
        self.assertTrue(any(c["output"]["anchorsInTension"] for c in b))
        self.assertTrue(any(not c["output"]["anchorsInTension"] for c in b))
        labels = {k["label"] for c in b for k in c["output"]["checks"]}
        for lab in ("Concrete bearing", "Anchor pullout", "Concrete side-face blowout", "Concrete pryout (shear)",
                    "Concrete breakout (shear)", "Adhesive bond strength", "Tension-shear interaction",
                    "Base plate yield (tension interface)"):
            self.assertIn(lab, labels)
        self.assertTrue(any("anchorStressArea" in c["input"] for c in b))
        self.assertTrue(any("bondStrength" in c["input"] for c in b))
        joined = " ".join(x for c in b for x in c["warnings"])
        for frag in ("17.6.2.1.2", "cannot equilibrate", "no characteristic bond stress", "non-ductile"):
            self.assertIn(frag, joined)

        p = [c for c in self._golden("pier")["cases"] if "output" in c]
        self.assertTrue(any(c["output"]["partialBearing"] for c in p))
        self.assertTrue(any(c["input"].get("restraint") == "anchored" for c in p))
        labels = {k["label"] for c in p for k in c["output"]["checks"]}
        self.assertIn("Punching (two-way) shear", labels)
        self.assertIn("Pier concrete bearing", labels)
        self.assertTrue(any(c["input"].get("footingThickness", 1) == 0 for c in p))
        self.assertTrue(any(c["status"] == "fail" for c in p))


class Helpers(unittest.TestCase):
    def test_min_fillet_size_table_j24(self):
        self.assertEqual([weld.min_fillet_size(t) for t in (0.25, 0.3, 0.5, 0.6, 0.75, 0.8)],
                         [0.125, 0.1875, 0.1875, 0.25, 0.25, 0.3125])

    def test_thread_stress_area(self):
        self.assertAlmostEqual(baseplate.thread_stress_area(0.75), 0.3345, places=3)
        self.assertAlmostEqual(baseplate.thread_stress_area(1), 0.6057, places=3)
        # non-table diameter falls back to 8-UN
        self.assertAlmostEqual(baseplate.thread_stress_area(0.8), 0.7854 * (0.8 - 0.9743 / 8) ** 2)

    def test_js_num(self):
        f = jsmath.js_num
        self.assertEqual([f(6.0), f(0.25), f(1e-7), f(1e21), f(123456789.5), f(-0.0625), f(7)],
                         ["6", "0.25", "1e-7", "1e+21", "123456789.5", "-0.0625", "7"])
        self.assertEqual([f(math.inf), f(math.nan), f(0.0), f(0.000001)], ["Infinity", "NaN", "0", "0.000001"])

    def test_js_division(self):
        self.assertEqual(jsmath.div(1, 0), math.inf)
        self.assertEqual(jsmath.div(-1, 0), -math.inf)
        self.assertTrue(math.isnan(jsmath.div(0, 0)))
        self.assertTrue(math.isnan(jsmath.jmax(1, math.nan)))

    def test_missing_required_inputs_raise(self):
        for fn in (weld.fillet_weld, baseplate.base_plate_anchorage, pier.pier_soil):
            with self.assertRaises(InputError):
                fn({})


if __name__ == "__main__":
    unittest.main()
