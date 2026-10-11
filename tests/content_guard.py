"""Shared content guard for the shipped skill files.

Scans every text file under a skill directory for banned material (personal paths and
names, employer or job identifiers, hand-offs to non-shipped skills, internal source
names). The banned list is stored ONLY as SHA-256 hashes of normalised, lower-cased
tokens, so this file itself carries none of the terms it forbids.

Matching: text is lower-cased and reduced to words (letters and digits, hyphenated
compounds kept whole) joined by single spaces. A hit is any banned entry that starts at
a word boundary of that stream, i.e. a banned word matches as a word prefix and a banned
phrase matches as a phrase. Windows absolute paths are caught by a separate regex.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Iterable, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = os.path.join(ROOT, "plugins")

# (normalised length, sha256 of the normalised lower-cased entry[, whole-word only])
_BANNED = (
    (5, "e790827938efc72efc985600838fa8bd9045dfef9f79fc3d45c8fb393faa0799"),
    (4, "99f7855eb789dfecf9ea66df3221a743f4ab8be59ae6b9c503499c1940a90fd5"),
    (7, "6c296fde55b852788be0818c74fc20be7554d5fede6bbd3d421965755dd3d0c1"),
    (6, "32efed5bc0664d9b3a1f3380099936ac2b87cae092be380339f1cd418f694e77"),
    (7, "78094dd1397fbcc660182aeb045c2884945a4950790b609fb04699c1ce63c6bb"),
    (6, "f4ae8da8d5faae028b13b0970a8a7890bb2ced123750fa748aec827ef2cad3eb"),
    (17, "99a2ba41f8b8f4acc46570848e2beed591f6b3f15ebdeda80fc9d63b4f823273"),
    (10, "595929c0cd05ed5e7d9ace0d21382ce7ae46df6351d647de5a018bf8c2043077"),
    (10, "2c03ea88094a0ea04f02a54f38c0d5a8f92d0b7cca977fbd396ddb89bbbef388", True),
    (9, "f3784e40c5b2b3f2347b6a689781d15a05ae971d1df1d4ff21108368df0e64f3"),
    (12, "b99a461435e39c19e791f4f60de482745e28bf6c82fd3a4b2642d4df9b7f7af3"),
    (13, "400248e0d497249579b94619f5a61fa6fe846818cee6c340951574cc192694e7"),
    (23, "056b67d4fc6791492758c00d4a1f6c6ff70801ae75c721262c829f2a6984a4ba"),
    (9, "cb367876888956689bdafa94e118184a2cdaedc8b2ff03319d2a522d63a04538"),
    (11, "b61d71a50c059752f32c2d789e08c289bdf0e7d9e6754a47c6d33171ab457a17"),
    (9, "525bb0a7be18bd54504c613a735155b9bd8d007f3d314e78f7096ba4d525b5ff"),
)
_HASHES = {e[1] for e in _BANNED}
_EXACT = {e[1] for e in _BANNED if len(e) > 2}   # must also end on a word boundary
_LENGTHS = sorted({e[0] for e in _BANNED})
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# A Windows absolute path such as a drive letter, colon, backslash. Safe to keep literal.
WINDOWS_PATH = re.compile(r"[A-Za-z]:\\")
_TEXT_EXT = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".toml", ".csv"}


def normalise(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def find_banned(text: str) -> List[str]:
    """Return the normalised spans of `text` that match a banned entry."""
    s = normalise(text)
    starts = [0] + [i + 1 for i, ch in enumerate(s) if ch == " "]
    hits: List[str] = []
    for i in starts:
        for n in _LENGTHS:
            span = s[i:i + n]
            if len(span) != n:
                continue
            digest = hashlib.sha256(span.encode()).hexdigest()
            if digest in _HASHES:
                if digest in _EXACT and i + n < len(s) and s[i + n] != " ":
                    continue
                hits.append(span)
    return hits


def skill_files(skill_dir: str) -> Iterable[str]:
    for dirpath, _dirs, files in os.walk(skill_dir):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in _TEXT_EXT:
                yield os.path.join(dirpath, name)


def scan(skill_dir: str) -> List[str]:
    """Problems found in every text file under skill_dir (empty list = clean)."""
    problems: List[str] = []
    for path in skill_files(skill_dir):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        rel = os.path.relpath(path, ROOT)
        for hit in find_banned(text):
            problems.append(f"{rel}: banned token {hit!r}")
        if WINDOWS_PATH.search(text):
            problems.append(f"{rel}: Windows absolute path")
    return problems


def assert_clean(testcase, skill_dir: str) -> None:
    testcase.assertEqual(scan(skill_dir), [])
