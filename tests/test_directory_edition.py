"""The directory edition meets the plugin directory's rule for a non-Verified organization.

The directory refused v0.10.1 on 2026-11-11: from an organization that is not Verified it
accepts only Markdown, text, JSON, YAML and PNG / JPEG / GIF / WebP / ICO files, none
beginning with the interpreter marker. tools/build_directory_edition.py writes a second tree
without the scripts; the release job commits it to the ``directory`` branch. These tests
build that tree and hold it to the rule, so a new file type in the plugin cannot reach the
directory branch unnoticed.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import build_directory_edition as edition  # noqa: E402
import test_directory_scanner_guard as guard  # noqa: E402


class DirectoryEdition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "edition"
        cls.files = edition.build(cls.out)
        cls.plugin = cls.out / edition.PLUGIN_REL

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_tree_meets_the_directory_rule(self):
        self.assertEqual(edition.violations(self.out), [])

    def test_no_script_or_vector_file_is_shipped(self):
        suffixes = {p.suffix.lower() for p in self.files}
        self.assertFalse(suffixes & {".py", ".svg", ".sh", ".ps1", ".js"}, suffixes)
        self.assertFalse([p for p in self.files if "scripts" in p.parts])

    def test_all_six_skills_keep_their_method_text(self):
        full = sorted(p.parent.name for p in (ROOT / edition.PLUGIN_REL / "skills").glob("*/SKILL.md"))
        here = sorted(p.parent.name for p in (self.plugin / "skills").glob("*/SKILL.md"))
        self.assertEqual(here, full)
        self.assertEqual(len(here), 6)
        for name in here:
            src = ROOT / edition.PLUGIN_REL / "skills" / name / "references"
            dst = self.plugin / "skills" / name / "references"
            self.assertEqual(sorted(p.name for p in dst.iterdir()), sorted(p.name for p in src.glob("*.md")))

    def test_every_skill_opens_with_the_edition_notice(self):
        for skill in (self.plugin / "skills").glob("*/SKILL.md"):
            text = skill.read_text(encoding="utf-8")
            front, body = text.split("---", 2)[1:]
            self.assertIn("this edition has no scripts", front, skill)
            self.assertTrue(body.lstrip().startswith("> **" + edition.MARKER), skill)
            for phrase in ("HAND CALCULATION, NOT ENGINE-VERIFIED", "`screening`", "Write no PASS"):
                self.assertIn(phrase, body, skill)

    def test_manifest_keeps_the_version_and_states_the_edition(self):
        full = json.loads((ROOT / edition.PLUGIN_REL / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        here = json.loads((self.plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(here["version"], full["version"])
        self.assertEqual(here["name"], full["name"])
        self.assertTrue(here["description"].startswith(edition.MARKER))
        self.assertIn("no calculation scripts", here["description"])
        self.assertLessEqual(len(here["description"]), 500)
        self.assertTrue((self.plugin / here["icon"]).is_file())

    def test_readme_says_what_is_left_out(self):
        for folder in (self.out, self.plugin):
            text = (folder / "README.md").read_text(encoding="utf-8")
            self.assertIn("no calculation scripts", text)
            self.assertIn(edition.REPO_URL, text)
            self.assertGreaterEqual(len(text.split()), 40)

    def test_edition_text_clears_the_scanner_guard(self):
        hits = []
        for path in self.files:
            if path.suffix.lower() not in guard._TEXT_EXT:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if guard._PATTERN.search(line) or guard._COMMAND_POSITION.search(line):
                    hits.append("%s:%d: %s" % (os.path.relpath(path, self.out), n, line.strip()[:100]))
        self.assertEqual(hits, [])

    def test_violations_catches_a_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "e"
            edition.build(out)
            bad = out / edition.PLUGIN_REL / "skills" / "nozzle-load" / "scripts"
            bad.mkdir()
            (bad / "x.py").write_bytes(b"#!" + b"/usr/bin/env python3\n")
            found = "\n".join(edition.violations(out))
            self.assertIn("file type is outside the allowed list", found)
            self.assertIn("begins with the interpreter marker", found)
            self.assertIn("is under a scripts folder", found)


if __name__ == "__main__":
    unittest.main()
