"""The plugin's manifests agree with each other, and every skill declares its runtime.

Three hosts read three different files for the same plugin: Claude Code / Cowork read
``plugins/piping-toolset/.claude-plugin/plugin.json`` and ``.claude-plugin/marketplace.json``;
Agent Plugins 1.0 hosts (OpenAI Codex among them) read ``plugins/piping-toolset/plugin.json``
and ``.agents/plugins/marketplace.json``. Nothing links them, so a version bump or a
description edit in one file is silent drift in the others. This test is the link.
"""

import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "piping-toolset")
CLAUDE_MANIFEST = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
AGENT_MANIFEST = os.path.join(PLUGIN, "plugin.json")
CLAUDE_MARKET = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
CODEX_MARKET = os.path.join(ROOT, ".agents", "plugins", "marketplace.json")
SKILLS = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))

AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
# Agent Plugins 1.0 name rule: a-z 0-9 - . ; alphanumeric at both ends; no -- or ..
AGENT_NAME = re.compile(r"^(?!.*(--|\.\.))[a-z0-9][a-z0-9.-]{0,62}[a-z0-9]$|^[a-z0-9]$")
AGENT_FIELDS = {"$schema", "name", "version", "description", "author", "homepage",
                "repository", "license", "keywords", "extensions"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head = text.split("\n---\n", 1)[0]
    return dict(ln.split(": ", 1) for ln in head.splitlines()[1:])


class ManifestParity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claude = load(CLAUDE_MANIFEST)
        cls.agent = load(AGENT_MANIFEST)
        cls.claude_market = load(CLAUDE_MARKET)
        cls.codex_market = load(CODEX_MARKET)

    def test_name_version_description_agree(self):
        for key in ("name", "version", "description"):
            self.assertEqual(self.claude[key], self.agent[key], key)

    def test_description_fits_the_cowork_upload_validator(self):
        # Cowork's Settings > Plugins > Upload rejects a plugin.json whose description
        # exceeds 500 characters ("Plugin description must be at most 500 characters",
        # observed on the 0.5.0 archive at 536 on 2026-10-27). The SKILL.md descriptions
        # already carry their own cap in test_skill_descriptions; this is the manifest's.
        self.assertLessEqual(len(self.claude["description"]), 500, len(self.claude["description"]))

    def test_claude_marketplace_entry_matches_manifest(self):
        (entry,) = self.claude_market["plugins"]
        self.assertEqual(entry["name"], self.claude["name"])
        self.assertEqual(entry["version"], self.claude["version"])
        self.assertEqual(entry["description"], self.claude["description"])
        self.assertEqual(entry["source"], "./plugins/piping-toolset")

    def test_codex_marketplace_entry_points_at_the_plugin(self):
        self.assertEqual(self.codex_market["name"], self.claude_market["name"])
        (entry,) = self.codex_market["plugins"]
        self.assertEqual(entry["name"], self.agent["name"])
        self.assertEqual(entry["source"], {"source": "local", "path": "./plugins/piping-toolset"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertTrue(entry["category"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, entry["source"]["path"], "plugin.json")))

    def test_agent_manifest_is_spec_shaped(self):
        self.assertEqual(self.agent["$schema"], AGENT_PLUGINS_SCHEMA)
        self.assertRegex(self.agent["name"], AGENT_NAME)
        self.assertFalse(set(self.agent) - AGENT_FIELDS, set(self.agent) - AGENT_FIELDS)
        self.assertEqual(self.agent["license"], "Apache-2.0")
        self.assertEqual(self.agent["author"], self.claude["author"])
        self.assertEqual(self.agent["homepage"], self.claude["homepage"])
        self.assertEqual(self.agent["keywords"], self.claude["keywords"])
        self.assertEqual(self.agent["repository"], "https://github.com/pipingtoolset/pipingtoolset-claude")


class SkillCompatibility(unittest.TestCase):

    def test_every_skill_declares_the_python_floor(self):
        self.assertEqual(len(SKILLS), 7, SKILLS)
        for path in SKILLS:
            fm = frontmatter(path)
            self.assertEqual(list(fm), ["name", "description", "compatibility"], path)
            self.assertEqual(fm["compatibility"], "Requires Python 3.9+ (standard library only)", path)
            self.assertLessEqual(len(fm["compatibility"]), 500)


if __name__ == "__main__":
    unittest.main()
