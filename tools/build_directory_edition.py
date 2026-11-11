"""Build the directory edition of the plugin: method and review guidance, no scripts.

The Anthropic plugin directory accepts, from an organization that is not Verified, only
Markdown, text, JSON, YAML and PNG / JPEG / GIF / WebP / ICO files, none of which may begin
with the two-character interpreter marker. The full plugin ships Python scripts, so it is
refused there (v0.10.1, 2026-11-11). This tool writes a second tree that meets the rule:

    <out>/README.md, LICENSE, NOTICE
    <out>/plugins/piping-toolset/        the plugin folder the directory reads
        .claude-plugin/plugin.json       edition description, same version as the full plugin
        .mcp.json, assets/icon.png, README.md, LICENSE
        skills/<name>/SKILL.md           with the edition notice after the frontmatter
        skills/<name>/references/*.md    unchanged

Every ``scripts/`` folder, the SVG icon and the Agent Plugins manifest are left out. The
tree is committed to the ``directory`` branch by the release job; ``main`` is never changed
by it. GitHub, Cowork and Codex installs keep the full plugin.

    python tools/build_directory_edition.py --out DIR      write the tree
    python tools/build_directory_edition.py --out DIR --check   write it, then verify it

Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_REL = Path("plugins") / "piping-toolset"
SOURCE = ROOT / PLUGIN_REL
REPO_URL = "https://github.com/pipingtoolset/pipingtoolset-claude"

ALLOWED_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
ALLOWED_BARE = {"LICENSE", "NOTICE"}
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml"}
MAX_BYTES = 256 * 1024
MAX_DESCRIPTION = 500
MARKER = "Directory edition"

DESCRIPTION = (
    "Directory edition: method, review and checklist guidance for six ASME B31.1 / B31.3 piping "
    "skills by pipingtoolset.com (pipe stress check, stress import, load cases, pipe supports, "
    "nozzle loads, bolted flanges). It includes no calculation scripts: Claude works each check by "
    "hand from the cited method and marks it not engine-verified. The full plugin with the "
    "fixture-verified engine is on GitHub. No ASME/API/PIP tables embedded; an optional connector "
    "serves cited table values to paid accounts."
)

NOTICE_LINES = [
    "> **" + MARKER + ": method and review guidance, no calculation scripts.**",
    "> This edition ships without the Python scripts of the full plugin, so nothing in it is run as a",
    "> program. Wherever the text below or a reference file names a script, a module id or a path under",
    "> `scripts/`, read that as a description of the method and not as a command.",
    ">",
    "> 1. Work each calculation by hand from the method in the reference files, and show every equation,",
    ">    input, unit and intermediate value.",
    "> 2. Head every numeric result `HAND CALCULATION, NOT ENGINE-VERIFIED` and give it the result status",
    ">    `screening`. Report each ratio as within or exceeds. Write no PASS, OK or issue-grade wording.",
    "> 3. The builders and converters named below (PCF, neutral file, load case tables) are not in this",
    ">    edition. Give the method and the checks; write such a file only as plain text the user can",
    ">    review line by line, and say it has not been through the validator.",
    "> 4. Tell the user once that the fixture-verified engine is in the full plugin on GitHub",
    ">    (pipingtoolset/pipingtoolset-claude) and in the calculators at pipingtoolset.com. Those scripts",
    ">    are not available from this edition.",
    "",
]

COMPATIBILITY = "compatibility: Method and review guidance only; this edition has no scripts"


def _skill_names() -> List[str]:
    return sorted(p.name for p in (SOURCE / "skills").iterdir() if (p / "SKILL.md").is_file())


def _with_notice(text: str) -> str:
    """SKILL.md with the edition notice after the frontmatter and the edition compatibility line."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md has no frontmatter block")
    end = lines.index("---", 1)
    head = [COMPATIBILITY if ln.startswith("compatibility:") else ln for ln in lines[: end + 1]]
    return "\n".join(head + [""] + NOTICE_LINES + lines[end + 1 :])


def _readme(version: str, skills: List[str]) -> str:
    rows = "\n".join("- `%s`" % s for s in skills)
    return "\n".join([
        "# PipingToolset (directory edition)",
        "",
        "Method, review and checklist guidance for ASME B31.1 / B31.3 piping stress work, by",
        "pipingtoolset.com. Version %s." % version,
        "",
        "## What this edition is",
        "",
        "Six skills that teach Claude how a piping stress engineer and a reviewer approach a job:",
        "",
        rows,
        "",
        "Each skill carries its procedure, its code paragraph references and its rejection checklists.",
        "",
        "## What it does not include",
        "",
        "This edition has **no calculation scripts**. The plugin directory accepts scripts only from",
        "Verified organizations, so the Python engine of the full plugin is left out here. Claude works",
        "each check by hand from the cited method, shows the steps, and marks every numeric result",
        "`HAND CALCULATION, NOT ENGINE-VERIFIED`. Nothing in this edition prints PASS or issue-grade",
        "wording, and it does not build PCF or neutral files through a validator.",
        "",
        "The full plugin, with the fixture-verified engine, the file builders and the validators, is at",
        "[%s](%s). The same engine runs the calculators at" % (REPO_URL.split("//")[1], REPO_URL),
        "[pipingtoolset.com](https://pipingtoolset.com).",
        "",
        "## Code tables",
        "",
        "No ASME, API or PIP table values are embedded. You read allowables, moduli, ratings and",
        "coefficients from your licensed copy. An optional connector (`pipingtoolset-data`) serves cited",
        "table values to signed-in paid accounts; the skills work without it.",
        "",
        "## Engineering responsibility",
        "",
        "Output is an aid to a qualified engineer and is not a sealed calculation. Check every value",
        "against the governing code edition before issue.",
        "",
        "## License and affiliation",
        "",
        "Apache-2.0. Flexible Piping Solutions LLC. Not affiliated with or endorsed by Anthropic, ASME,",
        "API or PIP.",
        "",
    ])


def build(out: Path) -> List[Path]:
    """Write the edition tree to ``out`` (emptied first, its ``.git`` kept). Returns the files written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    dest = out / PLUGIN_REL
    manifest = json.loads((SOURCE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    manifest["description"] = DESCRIPTION
    (dest / ".claude-plugin").mkdir(parents=True)
    (dest / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    shutil.copyfile(SOURCE / ".mcp.json", dest / ".mcp.json")
    (dest / "assets").mkdir()
    shutil.copyfile(SOURCE / "assets" / "icon.png", dest / "assets" / "icon.png")

    skills = _skill_names()
    for name in skills:
        src, dst = SOURCE / "skills" / name, dest / "skills" / name
        dst.mkdir(parents=True)
        (dst / "SKILL.md").write_text(
            _with_notice((src / "SKILL.md").read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        refs = src / "references"
        if refs.is_dir():
            (dst / "references").mkdir()
            for ref in sorted(refs.iterdir()):
                if ref.is_file() and ref.suffix.lower() == ".md":
                    shutil.copyfile(ref, dst / "references" / ref.name)

    readme = _readme(manifest["version"], skills)
    for folder in (out, dest):
        (folder / "README.md").write_text(readme, encoding="utf-8", newline="\n")
        shutil.copyfile(ROOT / "LICENSE", folder / "LICENSE")
    shutil.copyfile(ROOT / "NOTICE", out / "NOTICE")
    return sorted(p for p in out.rglob("*") if p.is_file() and ".git" not in p.relative_to(out).parts)


def violations(out: Path) -> List[str]:
    """Every way the tree at ``out`` breaks the directory's rule for a non-Verified organization."""
    out = Path(out)
    found: List[str] = []
    files = [p for p in out.rglob("*") if p.is_file() and ".git" not in p.relative_to(out).parts]
    for path in sorted(files):
        rel = path.relative_to(out).as_posix()
        ext = path.suffix.lower()
        data = path.read_bytes()
        if ext not in ALLOWED_EXT and not (ext == "" and path.name in ALLOWED_BARE) and path.name != ".mcp.json":
            found.append("%s: file type is outside the allowed list" % rel)
        if data[:2] == b"#!":
            found.append("%s: begins with the interpreter marker" % rel)
        if len(data) > MAX_BYTES and ext in TEXT_EXT:
            found.append("%s: %d bytes, over 256 KiB" % (rel, len(data)))
        if ext in TEXT_EXT or ext == "":
            if b"\x00" in data:
                found.append("%s: contains a NUL byte" % rel)
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                found.append("%s: is not UTF-8" % rel)
        if "scripts" in path.relative_to(out).parts:
            found.append("%s: is under a scripts folder" % rel)

    dest = out / PLUGIN_REL
    manifest_path = dest / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return found + ["%s: missing" % manifest_path.relative_to(out).as_posix()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    desc = manifest.get("description", "")
    if len(desc) > MAX_DESCRIPTION:
        found.append("plugin.json description is %d characters, over %d" % (len(desc), MAX_DESCRIPTION))
    if not desc.startswith(MARKER):
        found.append("plugin.json description does not open with the edition marker")
    icon = manifest.get("icon", "")
    if icon and not (dest / icon).is_file():
        found.append("plugin.json icon %s is not in the tree" % icon)
    skill_files = sorted((dest / "skills").glob("*/SKILL.md"))
    if not skill_files:
        found.append("no SKILL.md in the tree")
    for skill in skill_files:
        text = skill.read_text(encoding="utf-8")
        rel = skill.relative_to(out).as_posix()
        if MARKER not in text or "NOT ENGINE-VERIFIED" not in text:
            found.append("%s: the edition notice is missing" % rel)
        if "Requires Python" in text.split("---", 2)[1]:
            found.append("%s: frontmatter still says Python is required" % rel)
    for folder in (out, dest):
        if not (folder / "README.md").is_file() or not (folder / "LICENSE").is_file():
            found.append("%s: README.md or LICENSE missing" % (folder.relative_to(out).as_posix() or "."))
    return found


def main(argv: List[str] = None) -> int:
    ap = argparse.ArgumentParser(description="Build the directory edition of the plugin.")
    ap.add_argument("--out", required=True, help="directory to write the edition tree into")
    ap.add_argument("--check", action="store_true", help="verify the tree against the directory rule")
    args = ap.parse_args(argv)
    files = build(Path(args.out))
    print("directory edition: %d files -> %s" % (len(files), args.out))
    if args.check:
        bad = violations(Path(args.out))
        for line in bad:
            print("  violation: " + line)
        if bad:
            return 1
        print("check ok: allowed file types only, no scripts, notice in every SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
