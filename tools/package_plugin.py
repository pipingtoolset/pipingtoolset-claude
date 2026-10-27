#!/usr/bin/env python3
"""Build the Cowork-installable ``piping-toolset.plugin`` archive.

A ``.plugin`` file is a ZIP whose root holds ``.claude-plugin/plugin.json`` directly
(no wrapping folder). This script zips the contents of ``plugins/piping-toolset``
reproducibly: sorted entries, a fixed 1980-01-01 timestamp, fixed permissions.

Usage:
    python tools/package_plugin.py [--out DIR] [--check]

Exit codes: 0 ok, 1 check failed, 2 manifest missing or name not kebab-case.
Python 3.9+, standard library only.
"""
import argparse
import fnmatch
import json
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "piping-toolset"
MANIFEST_REL = ".claude-plugin/plugin.json"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
EXCLUDE_DIRS = {"__pycache__"}
EXCLUDE_PATTERNS = ("*.pyc", ".DS_Store")
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _excluded(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    return any(fnmatch.fnmatch(path.name, pat) for pat in EXCLUDE_PATTERNS)


def read_name(plugin_dir: Path):
    """Return the plugin name from plugin.json, or None if missing/invalid."""
    manifest = plugin_dir / MANIFEST_REL
    if not manifest.is_file():
        print("error: %s not found" % manifest, file=sys.stderr)
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("error: cannot parse %s: %s" % (manifest, exc), file=sys.stderr)
        return None
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not KEBAB.match(name):
        print("error: plugin.json name %r is not kebab-case" % (name,), file=sys.stderr)
        return None
    return name


def build(plugin_dir: Path, out_file: Path) -> int:
    files = sorted(
        (p for p in plugin_dir.rglob("*") if p.is_file() and not _excluded(p, plugin_dir)),
        key=lambda p: p.relative_to(plugin_dir).as_posix(),
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(plugin_dir).as_posix(), date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # unix, so external_attr is honoured identically everywhere
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    return len(files)


def check(out_file: Path) -> bool:
    ok = True
    with zipfile.ZipFile(out_file) as zf:
        bad = zf.testzip()
        if bad is not None:
            print("check failed: corrupt entry %s" % bad, file=sys.stderr)
            ok = False
        names = zf.namelist()
    if MANIFEST_REL not in names:
        print("check failed: %s not at archive root" % MANIFEST_REL, file=sys.stderr)
        ok = False
    skills = [n for n in names if re.fullmatch(r"skills/[^/]+/SKILL\.md", n)]
    if not skills:
        print("check failed: no skills/*/SKILL.md at archive root", file=sys.stderr)
        ok = False
    if ok:
        print("check ok: %s and %d SKILL.md file(s) at root" % (MANIFEST_REL, len(skills)))
    return ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Package the piping-toolset Cowork .plugin file.")
    parser.add_argument("--out", default=str(REPO_ROOT), help="output directory (default: repo root)")
    parser.add_argument("--check", action="store_true", help="verify the produced archive layout")
    args = parser.parse_args(argv)

    name = read_name(PLUGIN_DIR)
    if name is None:
        return 2
    out_file = Path(args.out).resolve() / (name + ".plugin")
    count = build(PLUGIN_DIR, out_file)
    print("%s  entries=%d  size=%d bytes" % (out_file, count, out_file.stat().st_size))
    if args.check and not check(out_file):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
