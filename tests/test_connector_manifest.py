"""The optional Engineering Data connector is declared once per host family, the same way.

Claude hosts (Claude Code, Cowork) read ``plugins/piping-toolset/.mcp.json``. Agent Plugins 1.0
hosts (OpenAI Codex, the ChatGPT desktop app) read ``plugins/piping-toolset/mcp.json``, the
portable form that names a transport ``type`` for each server and carries the OpenAI sign-in
setting under ``extensions["com.openai"].auth`` (developers.openai.com/plugins/build/plugins,
read 2026-10-28). Both name the one remote server at https://pipingtoolset.com/mcp.

The plugin stays free and every skill works without the connector, so these files declare a
server and nothing else: no headers, no environment variables, no stored credentials. Sign-in,
where a paid table needs it, happens in the host through pipingtoolset.com.

Also pinned here: the packager puts both declarations in the ``.plugin`` and ``.zip`` and keeps
them out of the skills-only zip; the skill scripts import no network module (the connector is
the only network path); and the listing copy obeys the board's wording rules of 2026-10-28.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "piping-toolset")
CLAUDE_DECL = os.path.join(PLUGIN, ".mcp.json")
AGENT_DECL = os.path.join(PLUGIN, "mcp.json")
CLAUDE_MANIFEST = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
AGENT_MANIFEST = os.path.join(PLUGIN, "plugin.json")
CLAUDE_MARKET = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
README = os.path.join(ROOT, "README.md")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

SERVER_NAME = "pipingtoolset-data"
SERVER_URL = "https://pipingtoolset.com/mcp"
DOCS_URL = "https://pipingtoolset.com/docs/connector/"
AGENT_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"

# Key names (compared lower-case with - and _ removed) that would put a header, an environment
# variable or a stored credential into a declaration.
FORBIDDEN_KEYS = {"headers", "header", "env", "envvars", "envfile", "bearertokenenvvar", "httpheaders",
                  "apikey", "clientsecret", "secret", "password", "token", "accesstoken", "authorization",
                  "headerscheme", "clientid"}
FORBIDDEN_TEXT = re.compile(r"bearer\s|authorization:|api[_-]?key|client[_-]?secret", re.IGNORECASE)

# Board ruling of 2026-10-28 on listing and connector wording (binding): never these words, and
# no upsell verbs in tool or connector text.
BANNED_COPY = [
    r"\bapproved\b", r"\bauthori[sz]ed\b", r"\blicensed\s+(?:data|tables?|content)\b", r"\bnamed-table\b",
    r"\bfree\s+ASME\s+data\b", r"\bZDR\b", r"\bzero-data\s+retention\b", r"\bnever\s+trained\b",
    r"\ball\s+API\s+standards\b", r"\bsame\s+engine\b", r"\blicensed\s+piping\s+engineer\b",
    r"\blicensing\s+firewall\b", r"\bupgrade\s+now\b", r"\bunlock",
]
BANNED_COPY_RE = re.compile("|".join(BANNED_COPY), re.IGNORECASE)
NETWORK_MODULES = re.compile(r"urllib|http\.client|\bsocket\b|\brequests\b|\bhttpx\b")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def walk_keys(node):
    """Every dict key anywhere in a parsed JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            for sub in walk_keys(value):
                yield sub
    elif isinstance(node, list):
        for value in node:
            for sub in walk_keys(value):
                yield sub


def load_packager():
    spec = importlib.util.spec_from_file_location("package_plugin", os.path.join(ROOT, "tools", "package_plugin.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readme_section(title):
    text = read(README)
    match = re.search(r"^## %s\s*$" % re.escape(title), text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def top_changelog_entry():
    text = read(CHANGELOG)
    heads = list(re.finditer(r"^## \[(\d+\.\d+\.\d+)\][^\n]*$", text, re.MULTILINE))
    first = heads[0]
    end = heads[1].start() if len(heads) > 1 else len(text)
    return first.group(1), text[first.start():end]


class ConnectorDeclarations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claude = load(CLAUDE_DECL)
        cls.agent = load(AGENT_DECL)

    def test_each_file_declares_exactly_one_server(self):
        for label, doc in (("claude", self.claude), ("agent", self.agent)):
            self.assertIn("mcpServers", doc, label)
            self.assertEqual(list(doc["mcpServers"]), [SERVER_NAME], label)

    def test_both_files_name_the_same_url(self):
        urls = {doc["mcpServers"][SERVER_NAME]["url"] for doc in (self.claude, self.agent)}
        self.assertEqual(urls, {SERVER_URL})

    def test_url_is_plain_https_without_userinfo_query_or_fragment(self):
        parts = urlsplit(SERVER_URL)
        self.assertEqual((parts.scheme, parts.hostname, parts.path), ("https", "pipingtoolset.com", "/mcp"))
        self.assertIsNone(parts.username)
        self.assertIsNone(parts.password)
        self.assertEqual((parts.query, parts.fragment), ("", ""))
        for doc in (self.claude, self.agent):
            url = doc["mcpServers"][SERVER_NAME]["url"]
            self.assertTrue(url.startswith("https://"), url)
            self.assertNotIn("@", url)
            self.assertNotIn("?", url)

    def test_transport_type_per_host_family(self):
        # Claude's .mcp.json uses "http" for a Streamable HTTP server; the portable Agent
        # Plugins file names the same transport "streamable-http".
        self.assertEqual(self.claude["mcpServers"][SERVER_NAME]["type"], "http")
        self.assertEqual(self.agent["mcpServers"][SERVER_NAME]["type"], "streamable-http")

    def test_claude_file_is_only_type_and_url(self):
        self.assertEqual(set(self.claude), {"mcpServers"})
        self.assertEqual(set(self.claude["mcpServers"][SERVER_NAME]), {"type", "url"})

    def test_agent_file_uses_the_portable_schema_and_site_sign_in(self):
        self.assertEqual(self.agent["$schema"], AGENT_SCHEMA)
        self.assertEqual(set(self.agent), {"$schema", "mcpServers"})
        server = self.agent["mcpServers"][SERVER_NAME]
        self.assertEqual(set(server), {"type", "url", "extensions"})
        self.assertEqual(set(server["extensions"]), {"com.openai"})
        auth = server["extensions"]["com.openai"]["auth"]
        # Some tools are open and some need a signed-in paid account, which is the "mixed" mode.
        self.assertEqual(auth["type"], "mixed")
        self.assertEqual(auth["client"], {"mode": "dcr"})
        self.assertEqual(set(auth), {"type", "client"})

    def test_no_headers_or_credentials_anywhere(self):
        for path in (CLAUDE_DECL, AGENT_DECL):
            doc = load(path)
            for key in walk_keys(doc):
                self.assertNotIn(re.sub(r"[-_]", "", key.lower()), FORBIDDEN_KEYS, (path, key))
            self.assertIsNone(FORBIDDEN_TEXT.search(read(path)), path)

    def test_manifests_do_not_redeclare_the_server(self):
        # Both hosts find the declaration by its fixed file name at the plugin root; a second copy
        # inside a manifest would give a host two servers for one URL.
        for path in (CLAUDE_MANIFEST, AGENT_MANIFEST):
            self.assertNotIn("mcpServers", load(path), path)

    def test_declarations_are_small_lf_utf8_files(self):
        for path in (CLAUDE_DECL, AGENT_DECL):
            raw = read_bytes(path)
            self.assertLess(len(raw), 4096, path)
            self.assertNotIn(b"\r", raw, path)
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "no BOM: " + path)


class ConnectorPackaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pkg = load_packager()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.plugin_zip = os.path.join(cls.tmp.name, "piping-toolset.plugin")
        cls.skills_zip = os.path.join(cls.tmp.name, "piping-toolset-skills.zip")
        cls.pkg.build(Path(PLUGIN), Path(cls.plugin_zip))
        cls.pkg.build_skills(Path(PLUGIN), Path(cls.skills_zip))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def quiet(self, func, path):
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = func(Path(path))
        return result, sink.getvalue()

    def rewrite(self, source, target, drop=(), add=None):
        with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename in drop:
                    continue
                zout.writestr(info, zin.read(info.filename))
            for name, data in (add or {}).items():
                zout.writestr(name, data)

    def test_plugin_archive_carries_both_declarations_at_the_root(self):
        with zipfile.ZipFile(self.plugin_zip) as zf:
            names = zf.namelist()
            self.assertIn(".mcp.json", names)
            self.assertIn("mcp.json", names)
            self.assertEqual(json.loads(zf.read(".mcp.json").decode("utf-8")), load(CLAUDE_DECL))
            self.assertEqual(json.loads(zf.read("mcp.json").decode("utf-8")), load(AGENT_DECL))

    def test_skills_archive_has_neither(self):
        with zipfile.ZipFile(self.skills_zip) as zf:
            for name in zf.namelist():
                self.assertTrue(name.startswith("skills/"), name)
                self.assertNotIn(name.rsplit("/", 1)[-1], (".mcp.json", "mcp.json"), name)

    def test_check_passes_on_the_real_archives(self):
        ok, out = self.quiet(self.pkg.check, self.plugin_zip)
        self.assertTrue(ok, out)
        ok, out = self.quiet(self.pkg.check_skills, self.skills_zip)
        self.assertTrue(ok, out)

    def test_check_fails_when_a_declaration_is_missing(self):
        for missing in (".mcp.json", "mcp.json"):
            target = os.path.join(self.tmp.name, "missing-%s.plugin" % missing.strip("."))
            self.rewrite(self.plugin_zip, target, drop=(missing,))
            ok, out = self.quiet(self.pkg.check, target)
            self.assertFalse(ok, missing)
            self.assertIn(missing, out)

    def test_check_fails_when_the_two_declarations_name_different_urls(self):
        other = json.dumps({"mcpServers": {SERVER_NAME: {"type": "http", "url": "https://example.org/mcp"}}})
        target = os.path.join(self.tmp.name, "mismatch.plugin")
        self.rewrite(self.plugin_zip, target, drop=(".mcp.json",), add={".mcp.json": other})
        ok, out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)
        self.assertIn("different URLs", out)

    def test_check_fails_on_a_plain_http_url(self):
        plain = json.dumps({"mcpServers": {SERVER_NAME: {"type": "http", "url": "http://pipingtoolset.com/mcp"}}})
        target = os.path.join(self.tmp.name, "plain.plugin")
        self.rewrite(self.plugin_zip, target, drop=(".mcp.json",), add={".mcp.json": plain})
        ok, _out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)

    def test_skills_check_fails_when_a_declaration_leaks_in(self):
        target = os.path.join(self.tmp.name, "leak-skills.zip")
        self.rewrite(self.skills_zip, target, add={"skills/mcp.json": "{}"})
        ok, out = self.quiet(self.pkg.check_skills, target)
        self.assertFalse(ok)
        self.assertIn("connector declaration", out)

    def test_archives_stay_reproducible(self):
        again = os.path.join(self.tmp.name, "again.plugin")
        self.pkg.build(Path(PLUGIN), Path(again))
        self.assertEqual(read_bytes(again), read_bytes(self.plugin_zip))


class SkillsMakeNoNetworkCalls(unittest.TestCase):

    def test_no_skill_script_mentions_a_network_module(self):
        offenders = []
        base = os.path.join(PLUGIN, "skills")
        for skill in sorted(os.listdir(base)):
            scripts = os.path.join(base, skill, "scripts")
            for dirpath, _dirs, files in os.walk(scripts):
                for name in sorted(files):
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, name)
                    for lineno, line in enumerate(read(path).splitlines(), 1):
                        if NETWORK_MODULES.search(line):
                            offenders.append("%s:%d" % (os.path.relpath(path, ROOT), lineno))
        self.assertEqual(offenders, [])


class ListingCopy(unittest.TestCase):
    """Wording the board fixed on 2026-10-28, and what the listing must say about the connector."""

    @classmethod
    def setUpClass(cls):
        cls.claude = load(CLAUDE_MANIFEST)
        cls.agent = load(AGENT_MANIFEST)
        cls.market = load(CLAUDE_MARKET)
        cls.ui = cls.agent["extensions"]["com.openai"]["interface"]

    def listing_texts(self):
        yield "claude description", self.claude["description"]
        yield "agent description", self.agent["description"]
        yield "marketplace description", self.market["plugins"][0]["description"]
        yield "marketplace metadata", self.market["metadata"]["description"]
        yield "shortDescription", self.ui["shortDescription"]
        yield "longDescription", self.ui["longDescription"]
        for cap in self.ui["capabilities"]:
            yield "capability", cap
        for prompt in self.ui["defaultPrompt"]:
            yield "defaultPrompt", prompt
        yield "README", read(README)
        yield "CHANGELOG top entry", top_changelog_entry()[1]

    def test_banned_words_and_upsell_verbs_are_absent(self):
        for label, text in self.listing_texts():
            self.assertIsNone(BANNED_COPY_RE.search(text), (label, BANNED_COPY_RE.search(text)))

    def test_long_description_scopes_the_connector(self):
        text = self.ui["longDescription"]
        for needle in (SERVER_URL, DOCS_URL, "make no network calls", "Currently", "Pro Plus", "pointer",
                       "not to train", "verified against your own copy"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("Nothing you enter reaches PipingToolset or Flexible Piping Solutions.", text)

    def test_capabilities_do_not_claim_the_whole_plugin_is_offline(self):
        caps = " | ".join(self.ui["capabilities"])
        self.assertNotIn("no network access", caps)
        self.assertIn("make no network calls", caps)
        self.assertRegex(caps, r"(?i)optional")

    def test_claude_description_names_the_connector_within_the_cap(self):
        self.assertIn("connector", self.claude["description"])
        self.assertLessEqual(len(self.claude["description"]), 500)

    def test_the_plugin_stays_free_in_the_copy(self):
        self.assertIn("needs no account", self.ui["longDescription"])


class ReadmeAndChangelog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.section = readme_section("Engineering Data connector")
        cls.version = load(CLAUDE_MANIFEST)["version"]

    def test_section_exists_and_gives_the_endpoint_and_docs(self):
        self.assertTrue(self.section, "README needs a '## Engineering Data connector' section")
        for needle in (SERVER_URL, DOCS_URL, SERVER_NAME):
            self.assertIn(needle, self.section, needle)

    def test_section_states_what_is_sent_and_what_is_free_or_paid(self):
        for needle in ("make no network calls", "only", "Currently", "Pro Plus", "pointer", "pricing",
                       "not to train", "own copy"):
            self.assertIn(needle, self.section, needle)

    def test_section_has_the_four_install_lines(self):
        for needle in ("claude mcp add --transport http %s %s" % (SERVER_NAME, SERVER_URL),
                       "Register automatically", "Sign in", "developer mode", "streamable"):
            self.assertIn(needle, self.section, needle)

    def test_how_it_works_no_longer_says_nothing_is_ever_sent(self):
        text = read(README)
        self.assertNotIn("Nothing you enter is sent to PipingToolset or Flexible Piping Solutions.", text)
        self.assertNotIn("and nothing is sent to PipingToolset.", text)
        self.assertIn("make no network calls", text)

    def test_refusal_prompt_in_try_it_is_qualified_by_the_connector(self):
        text = read(README)
        start = text.index("Then ask for what it will not give you")
        window = text[start:start + 1500]
        self.assertRegex(window, r"(?i)connector")

    def test_changelog_top_entry_is_this_version(self):
        version, entry = top_changelog_entry()
        self.assertEqual(version, self.version)
        for needle in (".mcp.json", "mcp.json", "code_values", "connector"):
            self.assertIn(needle, entry, needle)


if __name__ == "__main__":
    unittest.main()
