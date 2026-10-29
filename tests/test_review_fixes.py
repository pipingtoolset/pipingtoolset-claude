"""Regression tests for the 2026-10-28 review findings on the 0.7.0 connector work."""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_connector_manifest import BANNED_COPY_RE  # noqa: E402

CONTRACT_TITLE = "Code-table values (user-supplied or connector-supplied, cited)"
CALC_SHEET_SKILLS = ("pressure-design", "bolted-flange", "nozzle-load", "stress-screening")
CONNECTOR_SKILLS = ("pressure-design", "bolted-flange", "nozzle-load")


def _shipped_text_files():
    for base, dirs, files in os.walk(os.path.join(ROOT, "plugins")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith((".md", ".py", ".json", ".txt")):
                yield os.path.join(base, name)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class CopyRulesInShippedText(unittest.TestCase):
    def test_no_banned_copy_token_anywhere_in_the_plugin(self):
        hits = []
        for path in _shipped_text_files():
            for n, line in enumerate(_read(path).splitlines(), 1):
                m = BANNED_COPY_RE.search(line)
                if m:
                    hits.append(f"{os.path.relpath(path, ROOT)}:{n}: {m.group(0)}")
        self.assertEqual(hits, [])

    def test_golden_outputs_carry_no_banned_token(self):
        gold = os.path.join(ROOT, "tests", "golden")
        hits = [f for f in os.listdir(gold) if f.endswith(".md") and BANNED_COPY_RE.search(_read(os.path.join(gold, f)))]
        self.assertEqual(hits, [])


class SkillText(unittest.TestCase):
    def test_calc_sheet_section_3_has_the_contract_title(self):
        for skill in CALC_SHEET_SKILLS:
            self.assertIn("## 3. " + CONTRACT_TITLE, _read(os.path.join(SKILLS, skill, "SKILL.md")), skill)

    def test_descriptions_mention_the_optional_connector_where_values_can_come_from_it(self):
        for skill in CONNECTOR_SKILLS:
            head = _read(os.path.join(SKILLS, skill, "SKILL.md")).split("---")[1]
            desc = re.search(r'^description:\s*"(.*)"\s*$', head, re.M).group(1)
            self.assertIn("optional connector", desc, skill)
            self.assertLessEqual(len(desc), 1024, skill)

    def test_get_pointer_is_described_by_its_arguments(self):
        for skill in ("nozzle-load", "pipe-support"):
            text = _read(os.path.join(SKILLS, skill, "SKILL.md"))
            self.assertRegex(text, r"`get_pointer` takes `standard` .*and `quantity`; the table's id is the `id` its result returns", skill)

    def test_get_skey_map_arguments_are_named(self):
        text = _read(os.path.join(SKILLS, "iso-to-pcf", "SKILL.md"))
        self.assertIn("sends only `scope` and `component`", text)
        self.assertNotIn("group name, never", text)

    def test_allowable_stress_key_fields_are_split_by_code(self):
        text = _read(os.path.join(SKILLS, "pressure-design", "SKILL.md"))
        self.assertIn("B31.3 `grade`, `classCond`, `size`, `productForm`, `lineNo`, `uns`", text)
        self.assertIn("B31.1 `grade`, `typeClass`, `sizeOrDia`, `productForm`, `table`, `notes`", text)


if __name__ == "__main__":
    unittest.main()
