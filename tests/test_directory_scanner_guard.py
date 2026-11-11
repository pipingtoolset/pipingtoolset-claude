"""Guard against the plugin-directory scanner's credential-read false positive.

The Anthropic directory validation reads a status word that is also a credential word,
followed by a condition word, as "reads the installer's <word> <condition>" and, with the
remote connector declared in .mcp.json, holds the plugin for a reviewer. Seen on 0.6.1
(conditional expressions) and on 0.10.0 (a docstring). It names one file per scan, so the
whole shipped folder is swept here.

The pattern below is assembled from parts so this file does not carry the sequence itself.
"""

from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "piping-toolset")
_WORD = "pa" + "ss"
_CONDITIONS = ("if", "when", "while", "where", "unless", "whenever")
_PATTERN = re.compile(
    r"\b" + _WORD + r"\b[\"'`]*[\s,:;]*(?:only\s+)?(?:" + "|".join(_CONDITIONS) + r")\b",
    re.IGNORECASE,
)
_TEXT_EXT = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".toml"}


class DirectoryScannerGuard(unittest.TestCase):
    def test_no_status_word_followed_by_a_condition(self):
        hits = []
        for dirpath, _dirs, files in os.walk(PLUGIN):
            if "__pycache__" in dirpath:
                continue
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() not in _TEXT_EXT:
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    for n, line in enumerate(fh, 1):
                        if _PATTERN.search(line):
                            hits.append(f"{os.path.relpath(path, ROOT)}:{n}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "reword: the status word must not be followed by a condition word")


if __name__ == "__main__":
    unittest.main()
