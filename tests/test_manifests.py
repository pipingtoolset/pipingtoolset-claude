"""The plugin's manifests agree with each other, and every skill declares its runtime.

Three hosts read three different files for the same plugin: Claude Code / Cowork read
``plugins/piping-toolset/.claude-plugin/plugin.json`` and ``.claude-plugin/marketplace.json``;
Agent Plugins 1.0 hosts (OpenAI Codex among them) read ``plugins/piping-toolset/plugin.json``
and ``.agents/plugins/marketplace.json``. Nothing links them, so a version bump or a
description edit in one file is silent drift in the others. This test is the link.

The OpenAI listing block (``extensions.com.openai.interface`` in the Agent Plugins manifest)
carries the limits the OpenAI submission portal enforces (developers.openai.com/plugins/deploy/
submission, read 2026-10-28): displayName and shortDescription 30 characters, longDescription
4000, developerName 80, up to 20 capabilities of 120, up to 3 unique defaultPrompt entries of
128, HTTPS URLs, ``#RRGGBB`` brandColor, square icons of at least 48 px under ``./assets``.
"""

import glob
import json
import os
import re
import struct
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "piping-toolset")
CLAUDE_MANIFEST = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
AGENT_MANIFEST = os.path.join(PLUGIN, "plugin.json")
CLAUDE_MARKET = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
CODEX_MARKET = os.path.join(ROOT, ".agents", "plugins", "marketplace.json")
HOSTS_CHECKLIST = os.path.join(ROOT, "tests", "e2e", "HOSTS-CHECKLIST.md")
# The optional Engineering Data connector: Claude hosts read .mcp.json, Agent Plugins hosts read
# mcp.json, both at the plugin root (tests/test_connector_manifest.py pins their contents).
CLAUDE_CONNECTOR = os.path.join(PLUGIN, ".mcp.json")
AGENT_CONNECTOR = os.path.join(PLUGIN, "mcp.json")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SKILLS = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md")))

AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
# Agent Plugins 1.0 name rule: a-z 0-9 - . ; alphanumeric at both ends; no -- or ..
AGENT_NAME = re.compile(r"^(?!.*(--|\.\.))[a-z0-9][a-z0-9.-]{0,62}[a-z0-9]$|^[a-z0-9]$")
AGENT_FIELDS = {"$schema", "name", "version", "description", "author", "homepage",
                "repository", "license", "keywords", "extensions"}
# Claude manifest: the fields Claude Code reads plus the five Anthropic-directory listing
# fields (icon, documentationUrl, supportUrl, privacyPolicyUrl, termsOfServiceUrl), which
# claude plugin validate accepts without a warning from v2.1.281.
CLAUDE_FIELDS = {"name", "displayName", "version", "description", "author", "homepage", "repository",
                 "license", "keywords", "icon", "documentationUrl", "supportUrl", "privacyPolicyUrl",
                 "termsOfServiceUrl"}
INTERFACE_FIELDS = {"displayName", "shortDescription", "longDescription", "developerName", "category",
                    "capabilities", "websiteURL", "privacyPolicyURL", "termsOfServiceURL", "supportURL",
                    "defaultPrompt", "brandColor", "composerIcon", "logo", "screenshots"}
HTTPS = re.compile(r"^https://[^\s@]+$")
HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
# OpenAI's submit-a-Claude-plugin guide asks for provider-neutral wording in anything the
# directory shows or the model reads. "Claude" may still name a host (Claude Code, Claude
# Cowork, "for Claude, ChatGPT and Codex"); it may not be the actor ("Claude interviews",
# "Claude never computes", "Claude's job").
CLAUDE_AS_ACTOR = re.compile(
    r"\bClaude(?:'s|\s+(?:never|does|did|interviews?|reads?|explains?|asks?|computes?|writes?|runs?|"
    r"follows?|will|can|should|must|is|has|then))\b")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head = text.split("\n---\n", 1)[0]
    return dict(ln.split(": ", 1) for ln in head.splitlines()[1:])


def image_square_px(path):
    """Edge length of a square PNG or SVG, or None if not square / not readable."""
    with open(path, "rb") as fh:
        head = fh.read(512)
    if head.startswith(b"\x89PNG"):
        w, h = struct.unpack(">II", head[16:24])
        return w if w == h else None
    text = head.decode("utf-8", "replace")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', text)
    if m and m.group(1) == m.group(2):
        return int(m.group(1))
    return None


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

    def test_version_is_semver_and_the_runbook_names_it(self):
        version = self.claude["version"]
        self.assertRegex(version, SEMVER)
        self.assertEqual(self.agent["version"], version)
        self.assertEqual(self.claude_market["plugins"][0]["version"], version)
        with open(HOSTS_CHECKLIST, encoding="utf-8") as fh:
            text = fh.read()
        # The Phase 2 runbook is copy-paste: its title and every release tag or download URL
        # must name the version being shipped, or a host run verifies the wrong archive.
        self.assertIn("(plugin %s)" % version, text.splitlines()[0])
        self.assertEqual(set(re.findall(r"\bv\d+\.\d+\.\d+\b", text)), {"v" + version})

    def test_connector_declarations_sit_next_to_the_manifests(self):
        for path in (CLAUDE_CONNECTOR, AGENT_CONNECTOR):
            self.assertTrue(os.path.isfile(path), path)
        # Each manifest is discovered by file name, so the Claude manifest keeps its field set
        # (no mcpServers key) and the Agent Plugins manifest points at nothing extra.
        self.assertNotIn("mcpServers", self.claude)
        self.assertNotIn("mcpServers", self.agent)

    def test_description_fits_the_cowork_upload_validator(self):
        # Cowork's Settings > Plugins > Upload rejects a plugin.json whose description
        # exceeds 500 characters ("Plugin description must be at most 500 characters",
        # observed on the 0.5.0 archive at 536 on 2026-10-27). The SKILL.md descriptions
        # already carry their own cap in test_skill_descriptions; this is the manifest's.
        self.assertLessEqual(len(self.claude["description"]), 500, len(self.claude["description"]))

    def test_claude_manifest_fields_and_listing_links(self):
        self.assertFalse(set(self.claude) - CLAUDE_FIELDS, set(self.claude) - CLAUDE_FIELDS)
        self.assertEqual(self.claude["displayName"], "PipingToolset")
        self.assertTrue(self.claude["icon"].startswith("./"), self.claude["icon"])
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, self.claude["icon"])), self.claude["icon"])
        for key in ("documentationUrl", "supportUrl", "privacyPolicyUrl", "termsOfServiceUrl"):
            self.assertRegex(self.claude[key], HTTPS, key)

    def test_claude_marketplace_entry_matches_manifest(self):
        (entry,) = self.claude_market["plugins"]
        self.assertEqual(entry["name"], self.claude["name"])
        self.assertEqual(entry["version"], self.claude["version"])
        self.assertEqual(entry["description"], self.claude["description"])
        self.assertEqual(entry["displayName"], self.claude["displayName"])
        self.assertEqual(entry["source"], "./plugins/piping-toolset")

    def test_codex_marketplace_entry_points_at_the_plugin(self):
        self.assertEqual(self.codex_market["name"], self.claude_market["name"])
        self.assertEqual(self.codex_market["interface"]["displayName"], self.claude["displayName"])
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

    def test_descriptions_are_provider_neutral(self):
        # The same archive goes to the Anthropic and OpenAI directories; the model reads the
        # description in both. "The assistant interviews", never "Claude interviews".
        for label, text in (("description", self.agent["description"]),
                            ("marketplace", self.claude_market["metadata"]["description"])):
            self.assertIsNone(CLAUDE_AS_ACTOR.search(text), (label, text))


class OpenAIListing(unittest.TestCase):
    """The ``extensions.com.openai.interface`` block, within the portal's limits."""

    @classmethod
    def setUpClass(cls):
        cls.agent = load(AGENT_MANIFEST)
        cls.claude = load(CLAUDE_MANIFEST)
        cls.codex_market = load(CODEX_MARKET)
        cls.ui = cls.agent["extensions"]["com.openai"]["interface"]

    def test_only_known_interface_fields(self):
        self.assertEqual(set(self.agent["extensions"]), {"com.openai"})
        self.assertEqual(set(self.agent["extensions"]["com.openai"]), {"interface"})
        self.assertFalse(set(self.ui) - INTERFACE_FIELDS, set(self.ui) - INTERFACE_FIELDS)

    def test_text_limits(self):
        self.assertEqual(self.ui["displayName"], self.claude["displayName"])
        self.assertLessEqual(len(self.ui["displayName"]), 30)
        self.assertLessEqual(len(self.ui["shortDescription"]), 30, self.ui["shortDescription"])
        self.assertTrue(self.ui["shortDescription"].strip())
        self.assertLessEqual(len(self.ui["longDescription"]), 4000)
        self.assertGreater(len(self.ui["longDescription"]), 200)
        self.assertNotIn("\t", self.ui["longDescription"])
        self.assertEqual(self.ui["developerName"], self.claude["author"]["name"])
        self.assertLessEqual(len(self.ui["developerName"]), 80)
        for text in (self.ui["shortDescription"], self.ui["longDescription"]):
            self.assertIsNone(CLAUDE_AS_ACTOR.search(text), text)

    def test_category_matches_the_codex_marketplace(self):
        (entry,) = self.codex_market["plugins"]
        self.assertEqual(self.ui["category"], entry["category"])

    def test_capabilities_and_prompts(self):
        caps = self.ui["capabilities"]
        self.assertIsInstance(caps, list)
        self.assertLessEqual(len(caps), 20)
        for cap in caps:
            self.assertTrue(cap.strip())
            self.assertLessEqual(len(cap), 120, cap)
        prompts = self.ui["defaultPrompt"]
        self.assertTrue(1 <= len(prompts) <= 3, prompts)
        self.assertEqual(len(set(prompts)), len(prompts), "defaultPrompt entries must be unique")
        for prompt in prompts:
            self.assertLessEqual(len(prompt), 128, prompt)
            self.assertNotIn("@", prompt, "no app @mentions in a default prompt")

    def test_urls_are_https_and_match_the_claude_manifest(self):
        for key in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL", "supportURL"):
            self.assertRegex(self.ui[key], HTTPS, key)
            self.assertLessEqual(len(self.ui[key]), 1024)
        self.assertEqual(self.ui["privacyPolicyURL"], self.claude["privacyPolicyUrl"])
        self.assertEqual(self.ui["termsOfServiceURL"], self.claude["termsOfServiceUrl"])
        self.assertEqual(self.ui["supportURL"], self.claude["supportUrl"])

    def test_brand_colour(self):
        self.assertRegex(self.ui["brandColor"], HEX_COLOUR)

    def test_logo_and_composer_icon_are_square_assets(self):
        for key in ("logo", "composerIcon"):
            rel = self.ui[key]
            self.assertTrue(rel.startswith("./assets/"), (key, rel))
            path = os.path.join(PLUGIN, rel)
            self.assertTrue(os.path.isfile(path), path)
            self.assertLessEqual(os.path.getsize(path), 5 * 1024 * 1024, path)
            edge = image_square_px(path)
            self.assertIsNotNone(edge, "%s is not a square PNG/SVG" % rel)
            self.assertGreaterEqual(edge, 48, (rel, edge))
            if rel.endswith(".png"):
                self.assertLessEqual(edge, 4096, (rel, edge))
        # The logo the OpenAI directory shows is the same file Cowork shows.
        self.assertEqual(self.ui["logo"], self.claude["icon"])
        for shot in self.ui.get("screenshots", []):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, shot)), shot)


class SkillCompatibility(unittest.TestCase):

    def test_every_skill_declares_the_python_floor(self):
        self.assertEqual(len(SKILLS), 7, SKILLS)
        for path in SKILLS:
            fm = frontmatter(path)
            self.assertEqual(list(fm), ["name", "description", "compatibility"], path)
            self.assertEqual(fm["compatibility"], "Requires Python 3.9+ (standard library only)", path)
            self.assertLessEqual(len(fm["compatibility"]), 500)

    def test_skill_bodies_name_no_single_provider_as_the_actor(self):
        # Host names (Claude Code, Claude Cowork, Codex CLI, the ChatGPT desktop app) are fine;
        # "Claude never computes" is not, because the same text runs under ChatGPT.
        for path in SKILLS:
            with open(path, encoding="utf-8") as fh:
                body = fh.read().split("\n---\n", 1)[1]
            body = re.sub(r"https?://\S+", "", body)
            self.assertIsNone(CLAUDE_AS_ACTOR.search(body), (path, CLAUDE_AS_ACTOR.search(body)))


if __name__ == "__main__":
    unittest.main()
