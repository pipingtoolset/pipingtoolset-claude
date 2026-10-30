#!/usr/bin/env python3
"""Copy the shared helper blocks and the project-basis files into the seven skills.

Skills stay standalone (an Agent Skills host loads one skill folder, so no skill imports another),
so shared code is shared by byte-identical copy. The canonical text lives in tools/shared/:

  project_basis.py, result_status.py   the text between
      '# BEGIN shared <name> (do not edit here; source tools/shared/<name>.py)' and
      '# END shared <name>' (markers included) is copied into each main script; a script that has
      no block yet gets it right after its imports (result_status right after project_basis).
  project-basis.example.json           -> skills/<skill>/scripts/examples/project-basis.example.json
  project-basis.md                     -> skills/<skill>/references/project-basis.md, for each skill
      whose SKILL.md links references/project-basis.md (test_skill_references requires every
      reference file to be linked); an unlinked skill is reported as pending.

    python tools/sync_shared_blocks.py            # write the copies
    python tools/sync_shared_blocks.py --check    # exit 1 on drift, naming each file
    python tools/sync_shared_blocks.py --check --strict   # also fail while a skill is pending

The 0.7.0 code_values block is a separate, older copy and is not touched here.
Repo tooling only; not shipped with the plugin.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "tools", "shared")
SKILLS = os.path.join(ROOT, "plugins", "piping-toolset", "skills")
BLOCKS = ("project_basis", "result_status")  # insertion order
SCRIPTS = {
    "load-case-builder": "loadcase_gen.py",
    "pressure-design": "pressure_design.py",
    "stress-screening": "stress_screening.py",
    "pipe-support": "support_calc.py",
    "iso-to-pcf": "build_pcf.py",
    "nozzle-load": "nozzle_load.py",
    "bolted-flange": "bolted_flange.py",
}
REFERENCE = "project-basis.md"
EXAMPLE = "project-basis.example.json"
LINK = "references/" + REFERENCE


def begin_marker(name: str) -> str:
    return f"# BEGIN shared {name} (do not edit here; source tools/shared/{name}.py)"


def end_marker(name: str) -> str:
    return f"# END shared {name}"


def script_path(skill: str) -> str:
    return os.path.join(SKILLS, skill, "scripts", SCRIPTS[skill])


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def find_block(text: str, name: str):
    """(start, end) character offsets of the marked block, markers included; None when absent."""
    lines = text.split("\n")
    begin = [i for i, ln in enumerate(lines) if ln == begin_marker(name)]
    end = [i for i, ln in enumerate(lines) if ln == end_marker(name)]
    if not begin and not end:
        return None
    if len(begin) != 1 or len(end) != 1 or end[0] < begin[0]:
        raise SystemExit(f"malformed '{name}' markers (need one BEGIN line, then one END line)")
    start = sum(len(ln) + 1 for ln in lines[:begin[0]])
    stop = sum(len(ln) + 1 for ln in lines[:end[0]]) + len(lines[end[0]])
    return start, stop


def canonical_block(name: str) -> str:
    text = read_text(os.path.join(SHARED, name + ".py"))
    span = find_block(text, name)
    if span is None:
        raise SystemExit(f"tools/shared/{name}.py has no BEGIN/END markers")
    return text[span[0]:span[1]]


def _after_imports(text: str) -> int:
    """Line index just past the last top-level import that precedes the first def or class."""
    last = None
    for node in ast.parse(text).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = node.end_lineno
    if last is None:
        raise SystemExit("no top-level import to anchor the shared blocks after")
    return last


def apply_block(text: str, name: str, block: str) -> str:
    span = find_block(text, name)
    if span is not None:
        return text[:span[0]] + block + text[span[1]:]
    lines = text.split("\n")
    prev = BLOCKS[:BLOCKS.index(name)]
    anchors = [find_block(text, p) for p in prev]
    anchors = [a for a in anchors if a is not None]
    if anchors:
        cut = text[:anchors[-1][1]].count("\n") + 1
    else:
        cut = _after_imports(text)
    head, tail = lines[:cut], lines[cut:]
    while head and head[-1] == "":
        head.pop()
    while tail and tail[0] == "":
        tail.pop(0)
    return "\n".join(head + ["", ""] + block.split("\n") + ["", ""] + tail)


def links_reference(skill: str) -> bool:
    return LINK in read_text(os.path.join(SKILLS, skill, "SKILL.md"))


def plan():
    """[(target path, wanted text)] plus the skills whose SKILL.md does not link the reference yet."""
    blocks = {name: canonical_block(name) for name in BLOCKS}
    reference = read_text(os.path.join(SHARED, REFERENCE))
    example = read_text(os.path.join(SHARED, EXAMPLE))
    targets, pending = [], []
    for skill in SCRIPTS:
        text = read_text(script_path(skill))
        for name in BLOCKS:
            text = apply_block(text, name, blocks[name])
        targets.append((script_path(skill), text))
        targets.append((os.path.join(SKILLS, skill, "scripts", "examples", EXAMPLE), example))
        if links_reference(skill):
            targets.append((os.path.join(SKILLS, skill, "references", REFERENCE), reference))
        else:
            pending.append(skill)
    return targets, pending


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true", help="report drift and exit 1 instead of writing")
    ap.add_argument("--strict", action="store_true", help="with --check: a skill not linking the reference fails")
    args = ap.parse_args(argv)
    targets, pending = plan()
    drift = [path for path, want in targets if not os.path.exists(path) or read_text(path) != want]
    for skill in pending:
        print(f"pending: {skill}/SKILL.md does not link {LINK} yet (reference not copied)")
    if args.check:
        for path in drift:
            print(f"drift: {os.path.relpath(path, ROOT)}")
        failed = bool(drift) or (args.strict and bool(pending))
        print("sync check failed" if failed else f"sync check ok: {len(targets)} file(s) match tools/shared")
        return 1 if failed else 0
    for path, want in targets:
        if path in drift:
            write_text(path, want)
            print(f"wrote {os.path.relpath(path, ROOT)}")
    print(f"sync done: {len(drift)} file(s) written, {len(targets) - len(drift)} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
