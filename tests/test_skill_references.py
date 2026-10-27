"""Every SKILL.md reference link resolves, and every references/*.md file is linked.

The Cowork trims (0.4.0) moved detail out of the skill bodies into ``references/``. A body
that links a file that does not exist, or a reference file nothing points at, is silent
content loss, so both directions are checked for all seven skills.
"""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = sorted(glob.glob(os.path.join(ROOT, "plugins", "piping-toolset", "skills", "*")))
LINK = re.compile(r"references/([A-Za-z0-9_.-]+\.md)(?:#[^)\s`]*)?")


class SkillReferences(unittest.TestCase):

    def test_seven_skills_present(self):
        self.assertEqual(len(SKILLS), 7, SKILLS)

    def test_links_resolve_and_files_are_linked(self):
        for skill in SKILLS:
            with open(os.path.join(skill, "SKILL.md"), encoding="utf-8") as fh:
                text = fh.read()
            linked = set(LINK.findall(text))
            on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(skill, "references", "*.md"))}
            name = os.path.basename(skill)
            self.assertFalse(linked - on_disk, f"{name}: linked but missing {sorted(linked - on_disk)}")
            self.assertFalse(on_disk - linked, f"{name}: on disk but never linked {sorted(on_disk - linked)}")

    def test_body_word_budget(self):
        """Cowork guidance: SKILL.md body under 3,000 words; detail belongs in references/."""
        for skill in SKILLS:
            with open(os.path.join(skill, "SKILL.md"), encoding="utf-8") as fh:
                words = len(fh.read().split())
            self.assertLess(words, 3000, f"{os.path.basename(skill)}: {words} words")


if __name__ == "__main__":
    unittest.main()
