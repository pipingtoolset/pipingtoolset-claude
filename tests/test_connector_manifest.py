"""The optional Engineering Data connector is declared once, for the Claude hosts only.

Claude hosts (Claude Code, Cowork) read ``plugins/piping-toolset/.mcp.json``. Since 0.7.1 there is
no Agent Plugins ``mcp.json``: the owner's install test of 0.7.0 in Codex showed a sign-in prompt at
install, so the "optional connector" copy was untrue there. With no server declared in the plugin
there is nothing for Codex or the ChatGPT desktop app to authenticate; those hosts add the server by
hand (``codex mcp add``, a developer-mode connector), which the README documents. The sign-in policy
in ``.agents/plugins/marketplace.json`` stays ``ON_INSTALL``, the only value the OpenAI docs list.
The one server is https://pipingtoolset.com/mcp.

The plugin stays free and every skill works without the connector, so the file declares a server
and nothing else: no headers, no environment variables, no stored credentials. Sign-in, where a
paid table needs it, happens in the host through pipingtoolset.com.

Also pinned here: ``mcp.json`` is absent and the packager puts only ``.mcp.json`` in the ``.plugin``
and ``.zip`` and keeps it out of the skills-only zip; the skill scripts import no network module
(the connector is the only network path); the listing copy obeys the board's wording rules of
2026-10-28; and the copy and nozzle-load instructions name the four API tables as cited values at
the Ultimate tier, with pointer mode still described as a possible state (0.7.1).
"""
from __future__ import annotations

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
RETIRED_AGENT_DECL = os.path.join(PLUGIN, "mcp.json")  # removed in 0.7.1; must stay absent
CODEX_MARKET = os.path.join(ROOT, ".agents", "plugins", "marketplace.json")
HOSTS_CHECKLIST = os.path.join(ROOT, "tests", "e2e", "HOSTS-CHECKLIST.md")
NOZZLE_SKILL = os.path.join(PLUGIN, "skills", "nozzle-load", "SKILL.md")
NOZZLE_TOOLREF = os.path.join(PLUGIN, "skills", "nozzle-load", "references", "tool-reference.md")
CLAUDE_MANIFEST = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
AGENT_MANIFEST = os.path.join(PLUGIN, "plugin.json")
CLAUDE_MARKET = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
README = os.path.join(ROOT, "README.md")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

SERVER_NAME = "pipingtoolset-data"
SERVER_URL = "https://pipingtoolset.com/mcp"
DOCS_URL = "https://pipingtoolset.com/docs/connector/"

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


def changelog_entries():
    """[(version, entry text)] in file order."""
    text = read(CHANGELOG)
    heads = list(re.finditer(r"^## \[(\d+\.\d+\.\d+)\][^\n]*$", text, re.MULTILINE))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((h.group(1), text[h.start():end]))
    return out


def top_changelog_entry():
    return changelog_entries()[0]


def changelog_entry(version):
    for v, entry in changelog_entries():
        if v == version:
            return entry
    raise AssertionError(f"no CHANGELOG entry for {version}")


class ConnectorDeclarations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claude = load(CLAUDE_DECL)

    def test_agent_plugins_declaration_is_absent(self):
        # 0.7.1: Codex prompted for sign-in at install while this file existed.
        self.assertFalse(os.path.exists(RETIRED_AGENT_DECL), RETIRED_AGENT_DECL)
        self.assertEqual(sorted(n for n in os.listdir(PLUGIN) if n.lower() in ("mcp.json", ".mcp.json")),
                         [".mcp.json"])

    def test_the_file_declares_exactly_one_server(self):
        self.assertIn("mcpServers", self.claude)
        self.assertEqual(list(self.claude["mcpServers"]), [SERVER_NAME])

    def test_url_is_plain_https_without_userinfo_query_or_fragment(self):
        parts = urlsplit(SERVER_URL)
        self.assertEqual((parts.scheme, parts.hostname, parts.path), ("https", "pipingtoolset.com", "/mcp"))
        self.assertIsNone(parts.username)
        self.assertIsNone(parts.password)
        self.assertEqual((parts.query, parts.fragment), ("", ""))
        url = self.claude["mcpServers"][SERVER_NAME]["url"]
        self.assertEqual(url, SERVER_URL)
        self.assertTrue(url.startswith("https://"), url)
        self.assertNotIn("@", url)
        self.assertNotIn("?", url)

    def test_claude_file_is_only_type_and_url(self):
        # Claude's .mcp.json names a Streamable HTTP server with type "http".
        self.assertEqual(set(self.claude), {"mcpServers"})
        self.assertEqual(set(self.claude["mcpServers"][SERVER_NAME]), {"type", "url"})
        self.assertEqual(self.claude["mcpServers"][SERVER_NAME]["type"], "http")

    def test_no_headers_or_credentials_anywhere(self):
        for key in walk_keys(self.claude):
            self.assertNotIn(re.sub(r"[-_]", "", key.lower()), FORBIDDEN_KEYS, key)
        self.assertIsNone(FORBIDDEN_TEXT.search(read(CLAUDE_DECL)))

    def test_manifests_do_not_redeclare_the_server(self):
        # Claude finds the declaration by its fixed file name at the plugin root; a second copy
        # inside a manifest would give a host two servers for one URL.
        for path in (CLAUDE_MANIFEST, AGENT_MANIFEST):
            self.assertNotIn("mcpServers", load(path), path)

    def test_declaration_is_a_small_lf_utf8_file(self):
        raw = read_bytes(CLAUDE_DECL)
        self.assertLess(len(raw), 4096)
        self.assertNotIn(b"\r", raw)
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "no BOM")

    def test_codex_sign_in_policy_stays_on_install_with_nothing_to_sign_in_to(self):
        # ON_INSTALL is the only documented value; with no server declared there is nothing to
        # authenticate at install. If Codex still prompts, the policy value is the next suspect.
        policy = load(CODEX_MARKET)["plugins"][0]["policy"]
        self.assertEqual(policy["authentication"], "ON_INSTALL")
        self.assertEqual(policy["installation"], "AVAILABLE")
        self.assertFalse(os.path.exists(RETIRED_AGENT_DECL))


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

    def test_plugin_archive_carries_only_the_claude_declaration_at_the_root(self):
        with zipfile.ZipFile(self.plugin_zip) as zf:
            names = zf.namelist()
            self.assertIn(".mcp.json", names)
            self.assertNotIn("mcp.json", names)
            self.assertEqual([n for n in names if n.lower().endswith("mcp.json")], [".mcp.json"])
            self.assertEqual(json.loads(zf.read(".mcp.json").decode("utf-8")), load(CLAUDE_DECL))

    def test_skills_archive_has_neither(self):
        with zipfile.ZipFile(self.skills_zip) as zf:
            for name in zf.namelist():
                self.assertTrue(name.startswith("skills/"), name)
                self.assertNotIn(name.rsplit("/", 1)[-1].lower(), (".mcp.json", "mcp.json"), name)

    def test_check_passes_on_the_real_archives(self):
        ok, out = self.quiet(self.pkg.check, self.plugin_zip)
        self.assertTrue(ok, out)
        ok, out = self.quiet(self.pkg.check_skills, self.skills_zip)
        self.assertTrue(ok, out)

    def test_check_fails_when_the_declaration_is_missing(self):
        target = os.path.join(self.tmp.name, "missing-mcp.plugin")
        self.rewrite(self.plugin_zip, target, drop=(".mcp.json",))
        ok, out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)
        self.assertIn(".mcp.json", out)

    def test_check_fails_when_the_retired_agent_declaration_returns(self):
        target = os.path.join(self.tmp.name, "retired-returns.plugin")
        self.rewrite(self.plugin_zip, target, add={"mcp.json": read(CLAUDE_DECL)})
        ok, out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)
        self.assertIn("mcp.json must not ship", out)

    def test_check_fails_when_the_declaration_has_two_servers(self):
        two = json.dumps({"mcpServers": {SERVER_NAME: {"type": "http", "url": SERVER_URL},
                                         "other": {"type": "http", "url": "https://example.org/mcp"}}})
        target = os.path.join(self.tmp.name, "two.plugin")
        self.rewrite(self.plugin_zip, target, drop=(".mcp.json",), add={".mcp.json": two})
        ok, out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)
        self.assertIn("exactly one server", out)

    def test_check_fails_on_a_plain_http_url(self):
        plain = json.dumps({"mcpServers": {SERVER_NAME: {"type": "http", "url": "http://pipingtoolset.com/mcp"}}})
        target = os.path.join(self.tmp.name, "plain.plugin")
        self.rewrite(self.plugin_zip, target, drop=(".mcp.json",), add={".mcp.json": plain})
        ok, _out = self.quiet(self.pkg.check, target)
        self.assertFalse(ok)

    def test_skills_check_fails_when_a_declaration_leaks_in(self):
        for leak in ("skills/mcp.json", "skills/.mcp.json"):
            target = os.path.join(self.tmp.name, "leak-skills-%s.zip" % leak.split("/")[1].strip("."))
            self.rewrite(self.skills_zip, target, add={leak: "{}"})
            ok, out = self.quiet(self.pkg.check_skills, target)
            self.assertFalse(ok, leak)
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

    def test_long_description_does_not_say_the_plugin_declares_the_server_everywhere(self):
        text = self.ui["longDescription"]
        self.assertNotIn("The plugin declares a remote MCP server", text)
        self.assertRegex(text, r"declared for Claude Code and Cowork and added by hand in Codex and ChatGPT")

    def test_listing_copy_names_the_four_api_tables_at_ultimate_and_keeps_pointer_mode(self):
        text = self.ui["longDescription"]
        self.assertRegex(text, r"Ultimate currently adds API 610 Tables 5a and 5b, API 560 Tables 7 to 10, "
                               r"API 660 Table 2 and API 661 Table 4")
        self.assertNotRegex(text, r"API 610, 560, 660 and 661 tables[^.]*pointer")
        # PVP2011, ASCE 7, AISC 360, ACI and NEMA SM-23 are still pointer-only, and said to be so now.
        self.assertRegex(text, r"PVP2011-57100 tables, ASCE 7-22, AISC 360, ACI and NEMA SM-23 currently return a pointer")
        self.assertIn("ASME and API", text)

    def test_capabilities_do_not_claim_the_whole_plugin_is_offline(self):
        caps = " | ".join(self.ui["capabilities"])
        self.assertNotIn("no network access", caps)
        self.assertIn("make no network calls", caps)
        self.assertRegex(caps, r"(?i)optional")

    def test_claude_description_names_the_connector_within_the_cap(self):
        self.assertIn("connector", self.claude["description"])
        self.assertLessEqual(len(self.claude["description"]), 500)
        self.assertIn("cited ASME and API table values", self.claude["description"])
        self.assertEqual(self.market["plugins"][0]["description"], self.claude["description"])
        self.assertEqual(self.agent["description"], self.claude["description"])

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

    def test_readme_says_codex_and_chatgpt_add_the_server_by_hand(self):
        text = read(README)
        for stale in ("Connector declaration read", "and in `mcp.json` for Agent Plugins hosts",
                      "(transport `streamable-http`)", "sign-in mode `mixed`"):
            self.assertNotIn(stale, text, stale)
        self.assertNotRegex(text, r"(?<![.\w])mcp\.json")
        self.assertIn("codex mcp add pipingtoolset-data --url https://pipingtoolset.com/mcp", self.section)
        self.assertRegex(self.section, r"(?is)installing the plugin[^.]*(?:does not|doesn't)[^.]*(?:contact|sign)")

    def test_readme_table_serves_the_four_api_tables_at_ultimate_and_keeps_the_kill_switch(self):
        sec = self.section
        self.assertRegex(sec, r"Ultimate[^\n]*API 610 Tables 5a and 5b[^\n]*API 560 Tables 7 to 10"
                              r"[^\n]*API 660 Table 2[^\n]*API 661 Table 4")
        row = [ln for ln in sec.splitlines() if ln.startswith("| Pointer only")]
        self.assertEqual(len(row), 1, row)
        self.assertNotRegex(row[0], r"API (?:610|560|660|661)")
        for needle in ("PVP2011-57100", "ASCE 7-22", "NEMA SM-23"):
            self.assertIn(needle, row[0], needle)
        self.assertIn("Currently", sec)
        self.assertRegex(sec, r"(?s)source can\s+move between served and pointer-only")

    def test_site_drafts_match_the_readme_on_the_declaration_and_the_api_tables(self):
        # The site pages are generated from the same copy; a stale file name or a pointer-only
        # row for the API tables there is the same drift the README test guards against.
        for name in ("claude-page.html", "openai-page.html"):
            text = read(os.path.join(ROOT, "docs", "site", name))
            self.assertNotRegex(text, r"(?<![.\w])mcp\.json", name)
            self.assertNotIn("for hosts that read it", text, name)
            self.assertNotIn("for hosts that read the declaration", text, name)
            rows = [ln for ln in text.splitlines() if ln.startswith("<tr><td>Pointer only")]
            self.assertEqual(len(rows), 1, name)
            self.assertNotRegex(rows[0], r"API (?:610|560|660|661)", name)
            self.assertRegex(text, r"<b>Ultimate</b> currently adds API 610 Tables 5a and 5b, API 560 Tables 7 to 10, "
                                   r"API 660 Table 2 and API 661 Table 4", name)
            self.assertNotIn("(API nozzle allowables, PVP2011-57100", text, name)

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
        version, _entry = top_changelog_entry()
        self.assertEqual(version, self.version)

    def test_changelog_records_the_codex_declaration_change(self):
        # 0.7.1 removed the Agent Plugins declaration so Codex has nothing to sign in to at install.
        entry = changelog_entry("0.7.1")
        for needle in (".mcp.json", "Codex", "sign-in", "connector"):
            self.assertIn(needle, entry, needle)

    def test_checklist_codex_connector_row_expects_no_sign_in_prompt(self):
        text = read(HOSTS_CHECKLIST)
        start = text.index("Connector row (Codex)")
        row = " ".join(text[start:text.index("Upgrade path", start)].split())
        for needle in ("NO sign-in prompt", "ON_INSTALL", "policy value", "codex mcp add"):
            self.assertIn(needle, row, needle)


class NozzleLoadApiTables(unittest.TestCase):
    """C3: the four API tables are lookup_value calls at Ultimate, one scalar per call."""

    @classmethod
    def setUpClass(cls):
        text = read(NOZZLE_SKILL)
        cls.skill = text[text.index("## With the Engineering Data connector"):]
        cls.ref = read(NOZZLE_TOOLREF)

    def test_slot_row_is_a_lookup_value_row_with_the_key_fields(self):
        row = [ln for ln in self.skill.splitlines() if ln.startswith("| `allowable`, `suctionAllowable`")]
        self.assertEqual(len(row), 1, row)
        row = row[0]
        for needle in ("lookup_value", "api610-nozzle-loads", "api660-nozzle-loads", "api661-nozzle-loads",
                       "api560-terminal-loads", "`table` (5a or 5b), `nozzle`, `nps`", "`sizeNps`, `flangeClass`",
                       "`sizeNps`", "`component`, `orientation`"):
            self.assertIn(needle, row, needle)
        self.assertNotIn("get_pointer", row)
        self.assertRegex(self.skill, r"(?s)first row below come back as cited values at the Ultimate tier")

    def test_one_call_per_value_and_six_citations(self):
        for needle in ("one `lookup_value` call per value", "six lookups for six components"):
            self.assertIn(needle, self.skill, needle)
        for needle in ("One `lookup_value` call per value", "each with its own citation", "twelve",
                       "`suctionAllowable.Fx` to `suctionAllowable.Mz`", "list_keys"):
            self.assertIn(needle, self.ref, needle)

    def test_pointer_fallback_is_unchanged(self):
        for needle in ("pointer", "use the interview and step 4 above, unchanged, and quote nothing new",
                       "Currently"):
            self.assertIn(needle, self.skill, needle)

    def test_tool_reference_lists_api_slots_as_connector_values_at_ultimate(self):
        self.assertIn("Ultimate", self.ref)
        self.assertIn("api610-nozzle-loads", self.ref)
        self.assertNotIn("Every table row, coefficient, constant and figure reading is pointer-only today", self.ref)


if __name__ == "__main__":
    unittest.main()
