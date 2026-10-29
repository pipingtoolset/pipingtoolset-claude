"""The shipped calculator scripts make no network calls.

The Engineering Data connector is reached by the assistant through its own tools. The scripts
only receive its answers, as a `code_values` block in their inputs, so none of them may import
a networking library. This test reads every Python file under the skills directory:

  1. a plain text search for the library names urllib, http.client, socket, requests and httpx
     (it also catches a name in a comment, on purpose);
  2. an import check of the parsed source against a longer list of networking modules;
  3. a check that nothing imports by computed name, which would slip past 1 and 2.

Standard library only (unittest):

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")

NAMES = ("urllib", "http.client", "socket", "requests", "httpx")
NETWORK_MODULES = {
    "urllib", "urllib2", "urllib3", "http", "httplib", "socket", "socketserver", "ssl", "select", "selectors",
    "asyncio", "ftplib", "smtplib", "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc", "webbrowser",
    "requests", "httpx", "aiohttp", "websocket", "websockets", "paramiko", "pycurl",
}
DYNAMIC_IMPORT = re.compile(r"__import__|importlib")


def shipped_python_files():
    for dirpath, dirs, files in os.walk(SKILLS):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class NoNetwork(unittest.TestCase):

    def test_the_scan_sees_every_script(self):
        files = [os.path.basename(p) for p in shipped_python_files()]
        # a scan of nothing would pass: pin the scripts that must be inside it
        for expected in ("pressure_design.py", "stress_screening.py", "nozzle_load.py", "bolted_flange.py",
                         "support_calc.py", "loadcase_gen.py", "build_pcf.py", "pcf_lib.py", "validate_pcf.py",
                         "baseplate.py", "report.py"):
            self.assertIn(expected, files)
        self.assertGreaterEqual(len(files), 20)

    def test_no_script_names_a_network_library(self):
        hits = []
        for path in shipped_python_files():
            text = read(path)
            for name in NAMES:
                if name in text:
                    hits.append(f"{os.path.relpath(path, ROOT)}: {name}")
        self.assertEqual(hits, [])

    def test_no_script_imports_a_networking_module(self):
        hits = []
        for path in shipped_python_files():
            tree = ast.parse(read(path), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    mods = [node.module or ""]
                else:
                    continue
                for mod in mods:
                    if mod.split(".")[0] in NETWORK_MODULES:
                        hits.append(f"{os.path.relpath(path, ROOT)}: import {mod}")
        self.assertEqual(hits, [])

    def test_no_script_imports_by_computed_name(self):
        hits = [os.path.relpath(p, ROOT) for p in shipped_python_files() if DYNAMIC_IMPORT.search(read(p))]
        self.assertEqual(hits, [])

    def test_the_code_values_helper_only_reads_its_input(self):
        # the helper block that carries cited values into the calculators is plain data handling
        with open(os.path.join(SKILLS, "pressure-design", "scripts", "pressure_design.py"), encoding="utf-8") as fh:
            text = fh.read()
        block = text[text.index("# ===== BEGIN code_values helper"):text.index("# ===== END code_values helper =====")]
        self.assertNotIn("open(", block)
        self.assertNotIn("import ", block)


if __name__ == "__main__":
    unittest.main()
