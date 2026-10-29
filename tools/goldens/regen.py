#!/usr/bin/env python3
"""Regenerate tests/golden/pipe-support/*.json from the pipingtoolset calc-core engine.

The pipe-support skill is a Python port of the PiperSTR TypeScript engine in the private
pipecalcpro repository. Its parity tests compare the port against goldens produced by the
REAL engine. The three generators beside this script produce those goldens:

    gen-goldens.mts              -> weld.json, baseplate.json, pier.json
    gen-assembly-goldens.mts     -> assembly.json
    gen-aisc-member-goldens.mts  -> aisc-member.json

Each generator imports the engine by the relative path ``../packages/...``, so it must run
from a directory that is a direct child of a pipecalcpro checkout. This script copies the
three files into ``<src>/.golden-gen-tmp/``, runs each with that checkout's own ``tsx``
(``npx tsx``), collects the output, and removes the temporary folder again. The goldens are
written byte for byte as the generators emit them (LF line endings, no trailing edits).

Usage (from this repository's root; ``--src`` is a pipecalcpro checkout with node_modules):

    python tools/goldens/regen.py --src C:\\dev\\projects\\pipecalcpro          # rewrite the goldens
    python tools/goldens/regen.py --src C:\\dev\\projects\\pipecalcpro --check  # exit 1 on drift

After a rewrite, run the parity tests and commit the goldens with the engine change that
motivated them (CHANGELOG entries say "parity goldens regenerated from the fixed engine").
SOURCE.json records which engine commit produced the committed goldens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEST = ROOT / "tests" / "golden" / "pipe-support"
TMP_DIR_NAME = ".golden-gen-tmp"
GENERATORS = ("gen-goldens.mts", "gen-assembly-goldens.mts", "gen-aisc-member-goldens.mts")
GOLDENS = ("weld.json", "baseplate.json", "pier.json", "assembly.json", "aisc-member.json")


VERBOSE = False


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"generator failed ({proc.returncode}): {' '.join(cmd)}")
    lines = proc.stdout.splitlines()
    # The generators print one numbered line per case between their summary lines; only
    # the summaries (first, last, and anything unnumbered) are repeated unless --verbose.
    shown = lines if VERBOSE else [
        ln for i, ln in enumerate(lines) if i in (0, len(lines) - 1) or not ln[:1].isdigit()
    ]
    for line in shown:
        print("  " + line)


def _git(src: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(src), *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def generate(src: Path, out: Path) -> None:
    """Run the three generators inside ``src`` and leave the five goldens in ``out``."""
    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("npx not found on PATH (Node.js is needed to run the TypeScript generators)")
    if not (src / "packages" / "calc-core" / "src" / "structural").is_dir():
        raise SystemExit(f"{src} is not a pipecalcpro checkout (no packages/calc-core/src/structural)")
    tmp = src / TMP_DIR_NAME
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        for name in GENERATORS:
            shutil.copyfile(HERE / name, tmp / name)
        out.mkdir(parents=True, exist_ok=True)
        print("gen-goldens.mts (weld, baseplate, pier)")
        _run([npx, "tsx", str(tmp / "gen-goldens.mts"), str(out)], src)
        print("gen-assembly-goldens.mts (assembly)")
        _run([npx, "tsx", str(tmp / "gen-assembly-goldens.mts"), str(out / "assembly.json")], src)
        print("gen-aisc-member-goldens.mts (aisc-member)")
        _run([npx, "tsx", str(tmp / "gen-aisc-member-goldens.mts"), str(out / "aisc-member.json")], src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    missing = [g for g in GOLDENS if not (out / g).is_file()]
    if missing:
        raise SystemExit(f"generators did not produce: {', '.join(missing)}")


def _read(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True, help="pipecalcpro checkout (with node_modules)")
    ap.add_argument("--check", action="store_true", help="compare only; exit 1 if any golden would change")
    ap.add_argument("--verbose", action="store_true", help="echo every per-case line the generators print")
    args = ap.parse_args(argv)
    global VERBOSE
    VERBOSE = args.verbose
    src = Path(args.src).resolve()

    with tempfile.TemporaryDirectory(prefix="pipe-support-goldens-") as td:
        out = Path(td)
        generate(src, out)
        changed = []
        for g in GOLDENS:
            new = _read(out / g)
            old = _read(DEST / g) if (DEST / g).is_file() else None
            if old != new:
                changed.append(g)
            if not args.check:
                (DEST / g).write_bytes(new)

        commit = _git(src, "rev-parse", "HEAD")
        branch = _git(src, "rev-parse", "--abbrev-ref", "HEAD")
        if args.check:
            if changed:
                print(f"STALE vs calc-core {commit[:12]} ({branch}): {', '.join(changed)}", file=sys.stderr)
                print("re-run without --check, run the parity tests, and commit the goldens", file=sys.stderr)
                return 1
            print(f"check ok: {len(GOLDENS)} goldens match calc-core {commit[:12]} ({branch})")
            return 0

        manifest = {
            "source": "pipecalcpro packages/calc-core/src/structural (PiperSTR engine)",
            "calc_core_commit": commit,
            "calc_core_branch": branch,
            "generators": list(GENERATORS),
            "goldens": {g: hashlib.sha256(_read(DEST / g)).hexdigest() for g in GOLDENS},
        }
        (DEST / "SOURCE.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
        print(f"wrote {len(GOLDENS)} goldens ({', '.join(changed) if changed else 'no change'}) and SOURCE.json "
              f"from calc-core {commit[:12]} ({branch})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
