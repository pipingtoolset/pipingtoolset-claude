"""iso-to-pcf: the output status taxonomy (B9) - envelope words, checks[], banner rule, parity.

Standard library only:  python -m unittest tests.test_iso_to_pcf_status -v
"""

from __future__ import annotations

import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "piping-toolset", "skills", "iso-to-pcf")
SCRIPTS = os.path.join(SKILL, "scripts")
EXAMPLES = os.path.join(SCRIPTS, "examples")
GOLDEN = os.path.join(ROOT, "tests", "golden", "demo-line.pcf")
sys.path.insert(0, SCRIPTS)

import build_pcf  # noqa: E402
import pcf_lib  # noqa: E402
import validate_pcf as V  # noqa: E402

WORDS = ("calculated", "screening", "manual check required", "pointer only", "not checked")


def example(name: str) -> dict:
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        return json.load(fh)


def demo() -> dict:
    return example("demo-line.json")


def run(spec: dict):
    b = build_pcf.Builder(copy.deepcopy(spec)).build()
    return b, build_pcf.report(b, b.bom_check())


def by_name(r: dict) -> dict:
    return {c["name"]: c for c in r["checks"]}


def clean() -> dict:
    """minimal-proven with explicit elbow radii and no ASSUMED item: nothing a script could flag."""
    spec = example("minimal-proven.json")
    spec.pop("assumed", None)
    for it in spec["items"]:
        if it["type"] in ("elbow", "bend"):
            it["radius"] = "9"
    return spec


def cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = build_pcf.main(argv)
    return code, out.getvalue(), err.getvalue()


DEMO_ASSUMED = ("confirm before issue: Gasket thickness 1/8 in (not dimensioned on the demo iso); LR elbow radius "
                "taken as 1.5 x NPS 6 (B16.9 convention); state it if the iso differs")


def banner_words(text: str):
    return re.findall(r"\b(PASS|OK|ISSUE|DELIVERABLE)\b", text)


class Envelope(unittest.TestCase):

    def test_every_example_carries_one_of_the_five_words_and_well_formed_checks(self):
        for name in ("demo-line.json", "minimal-proven.json"):
            _, r = run(example(name))
            self.assertIn(r["result_status"], WORDS, name)
            self.assertTrue(r["checks"], name)
            for c in r["checks"]:
                self.assertEqual(sorted(c), ["name", "note", "result_status", "status"], c)
                self.assertIn(c["result_status"], WORDS)
                self.assertIn(c["status"], ("pass", "fail", "na"))
            worst = max(r["checks"], key=lambda c: build_pcf.RESULT_STATUS_SEVERITY[c["result_status"]])
            self.assertEqual(r["result_status"], worst["result_status"])
            json.dumps(r)

    def test_calculated_is_reachable_at_check_level(self):
        _, r = run(example("demo-line.json"))
        c = by_name(r)
        self.assertEqual((c["closure checks"]["result_status"], c["closure checks"]["status"]), ("calculated", "pass"))
        self.assertEqual((c["BOM component counts"]["result_status"], c["BOM component counts"]["status"]),
                         ("calculated", "pass"))

    def test_assumed_inputs_are_one_manual_check_row_and_the_pipe_length_screen_is_screening(self):
        spec = demo()
        spec["bom"]["PIPE-LENGTH:6"] = "145'9"            # 1749 in against 1749.06 in of centreline
        _, r = run(spec)
        c = by_name(r)
        self.assertEqual(c["ASSUMED inputs"], {"name": "ASSUMED inputs", "result_status": "manual check required",
                                               "status": "na", "note": DEMO_ASSUMED})
        self.assertEqual(len([x for x in r["checks"] if x["name"] == "ASSUMED inputs"]), 1)
        self.assertEqual(c["BOM pipe length (+/-10% magnitude)"]["result_status"], "screening")
        self.assertEqual(r["result_status"], "manual check required")
        self.assertFalse(any(x.get("unresolved_factor") for x in r["checks"]))
        self.assertIn("ASSUMED inputs: " + DEMO_ASSUMED, r["result_status_why"])
        spec = clean()
        spec.setdefault("bom", {})["PIPE-LENGTH:6"] = "1"
        _, r = run(spec)
        self.assertNotIn("ASSUMED inputs", by_name(r))

    def test_not_checked_lists_the_validator_and_the_hand_checks_explicitly(self):
        spec = clean()
        spec["items"] = [it for it in spec["items"] if it["type"] != "check"]
        _, r = run(spec)
        self.assertEqual(r["result_status"], "calculated")        # listed limits never set the word
        nc = [c["name"] for c in r["checks"] if c["result_status"] == "not checked"]
        self.assertEqual(nc[0], "closure checks")                 # the spec states none
        self.assertIn("PCF connectivity validation", nc)
        for name, _note in pcf_lib.HAND_CHECKS:
            self.assertIn(name, nc)
            self.assertIn(name, r["result_status_why"])
        self.assertEqual(len(pcf_lib.HAND_CHECKS), 3)
        self.assertTrue(r["ok"])

    def test_hand_checks_match_the_validators_own_closing_paragraph(self):
        with open(os.path.join(SCRIPTS, "validate_pcf.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("SKEYs vs your site's Isogen output", src)
        self.assertIn("continuation coordinates vs", src)
        self.assertIn("vertical-axis declaration", src)
        names = " ".join(n for n, _ in pcf_lib.HAND_CHECKS)
        for key in ("SKEYs", "continuation coordinates", "vertical-axis declaration"):
            self.assertIn(key, names)

    def test_a_missing_bom_is_not_checked(self):
        spec = clean()
        del spec["bom"]
        _, r = run(spec)
        self.assertEqual(by_name(r)["BOM reconciliation"]["result_status"], "not checked")

    def test_manual_check_required_for_a_failed_closure_check(self):
        spec = demo()
        spec["items"][-1]["expect"] = {"E": "126'0"}
        b, r = run(spec)
        self.assertFalse(r["ok"])
        self.assertEqual(r["result_status"], "manual check required")
        c = by_name(r)["closure checks"]
        self.assertEqual((c["result_status"], c["status"]), ("manual check required", "fail"))
        self.assertRegex(c["note"], r"^1 of \d+ failed: ")

    def test_manual_check_required_for_a_bom_count_and_a_bom_length_failure(self):
        spec = demo()
        spec["bom"]["VALVE"] = 5
        _, r = run(spec)
        self.assertEqual(r["result_status"], "manual check required")
        self.assertEqual(by_name(r)["BOM component counts"]["status"], "fail")
        spec = demo()
        spec["bom"]["PIPE-LENGTH:6"] = "1"            # one inch against about 1749 in
        _, r = run(spec)
        self.assertEqual(r["result_status"], "manual check required")
        c = by_name(r)["BOM pipe length (+/-10% magnitude)"]
        self.assertEqual((c["result_status"], c["status"]), ("manual check required", "fail"))

    def test_pointer_only_is_not_reachable_by_this_builder(self):
        # no code-table input: code_values is refused, so no required value can arrive as a pointer
        for name in ("demo-line.json", "minimal-proven.json"):
            _, r = run(example(name))
            self.assertNotIn("pointer only", [c["result_status"] for c in r["checks"]])

    def test_status_and_exit_codes_are_unchanged(self):
        b, r = run(demo())
        self.assertTrue(r["ok"])
        self.assertEqual(sorted(k for k in r if k in ("ok", "closure_checks", "bom_checks")),
                         ["bom_checks", "closure_checks", "ok"])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.pcf")
            self.assertEqual(cli([os.path.join(EXAMPLES, "demo-line.json"), "-o", out])[0], 0)
            with open(out, encoding="ascii", newline="") as fh, open(GOLDEN, encoding="ascii", newline="") as g:
                self.assertEqual(fh.read(), g.read())
            spec = demo()
            spec["items"][-1]["expect"] = {"E": "126'0"}
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                json.dump(spec, fh)
            self.assertEqual(cli([bad, "-o", out])[0], 2)

    def test_json_output_carries_the_envelope(self):
        code, out, _ = cli([os.path.join(EXAMPLES, "demo-line.json"), "-o", os.devnull, "--json"])
        self.assertEqual(code, 0)
        r = json.loads(out)
        self.assertEqual(r["result_status"], "manual check required")      # the demo carries two ASSUMED items
        self.assertEqual(len(r["checks"]), len(by_name(r)))


class BannerRule(unittest.TestCase):

    def test_status_line_sits_under_the_title_and_is_ascii(self):
        b, r = run(demo())
        lines = build_pcf.render(r).splitlines()
        self.assertEqual(lines[0], "PCF build report - DEMO-6-P-1001")
        self.assertEqual(lines[1], "Result status: manual check required - ASSUMED inputs: " + DEMO_ASSUMED)
        self.assertTrue(all(ord(ch) < 128 for ch in lines[1]))

    def test_an_allowed_run_prints_pass_and_ok(self):
        _, r = run(clean())
        self.assertEqual(r["result_status"], "calculated")
        text = build_pcf.render(r)
        self.assertIn("[PASS] ", text)
        self.assertIn("RESULT: OK - run validate_pcf.py next", text)

    def test_an_assumed_item_holds_the_result_line(self):
        _, r = run(demo())
        text = build_pcf.render(r)
        self.assertIn("RESULT: MANUAL CHECK REQUIRED - confirm the ASSUMED items, then run validate_pcf.py", text)
        self.assertEqual(banner_words(text), [])
        self.assertNotIn("[PASS]", text)

    def test_a_failed_run_prints_fail_and_not_deliverable_and_no_positive_word(self):
        spec = demo()
        spec["items"][-1]["expect"] = {"E": "126'0"}
        _, r = run(spec)
        text = build_pcf.render(r)
        self.assertIn("[FAIL] ", text)
        self.assertIn("[MANUAL CHECK REQUIRED] ", text)     # the passing lines, where PASS would be
        self.assertIn("RESULT: NOT DELIVERABLE", text)
        self.assertEqual([w for w in banner_words(text) if w != "DELIVERABLE"], [])
        self.assertEqual(banner_words(text), ["DELIVERABLE"])   # only inside NOT DELIVERABLE
        self.assertIn("Result status: manual check required - closure checks: ", text)

    def test_pointer_only_and_screening_with_an_unresolved_factor_block_the_positive_words(self):
        _, r = run(clean())
        blocked = {
            "pointer only": dict(r, result_status="pointer only"),
            "screening with an unresolved factor": dict(
                r, result_status="screening", checks=r["checks"] + [{"name": "f", "result_status": "screening", "status": "na", "note": None,
                                          "unresolved_factor": True}]),
        }
        for label, doctored in blocked.items():
            text = build_pcf.render(doctored)
            self.assertEqual(banner_words(text), [], label)
            self.assertNotIn("[PASS]", text, label)
            self.assertIn("RESULT: ", text)
            self.assertIn("resolve the flagged checks", text, label)
        self.assertIn("RESULT: POINTER ONLY - ", build_pcf.render(blocked["pointer only"]))
        self.assertIn("RESULT: SCREENING - ", build_pcf.render(blocked["screening with an unresolved factor"]))

    def test_screening_without_a_factor_and_not_checked_do_not_block(self):
        for word in ("screening", "not checked", "calculated"):
            _, r = run(clean())
            self.assertIn("RESULT: OK - run validate_pcf.py next", build_pcf.render(dict(r, result_status=word)))


class Validator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        b, _ = run(demo())
        cls.text = b.pcf.text()

    def test_a_clean_pcf_is_calculated_and_lists_the_hand_checks(self):
        v = V.validate(self.text)
        self.assertTrue(v["ok"])
        self.assertEqual(v["result_status"], "calculated")
        by = {c["name"]: c for c in v["checks"]}
        self.assertEqual((by["PCF structure and connectivity"]["result_status"],
                          by["PCF structure and connectivity"]["status"]), ("calculated", "pass"))
        self.assertEqual(len([c for c in v["checks"] if c["result_status"] == "not checked"]), 3)
        json.dumps(v)

    def test_errors_are_manual_check_required(self):
        bad = self.text.replace("UNITS-BORE MM", "UNITS-BORE INCH")
        v = V.validate(bad)
        self.assertFalse(v["ok"])
        self.assertEqual(v["result_status"], "manual check required")
        self.assertEqual(v["checks"][0]["status"], "fail")

    def test_cli_banner_follows_the_status(self):
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, "g.pcf"), os.path.join(d, "b.pcf")
            with open(good, "w", encoding="ascii", newline="") as fh:
                fh.write(self.text)
            with open(bad, "w", encoding="ascii", newline="") as fh:
                fh.write(self.text.replace("UNITS-BORE MM", "UNITS-BORE INCH"))
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(V.main([good]), 0)
            self.assertIn("Result status: calculated - PCF structure and connectivity: every component attaches "
                          "to an existing node; not performed by this module: SKEYs", out.getvalue())
            self.assertIn("\nOK - every component attaches", out.getvalue())
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(V.main([bad]), 1)
            self.assertNotIn("\nOK - ", out.getvalue())
            self.assertIn("ERRORS - not deliverable", out.getvalue())
            self.assertIn("Result status: manual check required", out.getvalue())


if __name__ == "__main__":
    unittest.main()
