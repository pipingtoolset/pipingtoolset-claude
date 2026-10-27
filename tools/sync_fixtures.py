#!/usr/bin/env python3
"""Vendor a sanitized snapshot of pipingtoolset calc-core fixtures into this repo.

The skill scripts must reproduce the web engine's fixture cases exactly ("one engine").
This copies only what the parity tests need - module, inputs, expected outputs,
status and tolerance - and DROPS every case name and description, so no material
or table annotation from the private repo lands in this (eventually public) one.

    python tools/sync_fixtures.py --src C:\\dev\\projects\\pipecalcpro          # write snapshot
    python tools/sync_fixtures.py --src C:\\dev\\projects\\pipecalcpro --check  # drift check

Not shipped with the plugin (repo tooling only).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "tests", "fixtures", "calc-core")
MANIFEST = os.path.join(DEST, "MANIFEST.json")

# module id -> owning skill. Only data-free modules: every code-table value is an input.
MODULES = {
    "piping.b313-wall-thickness": "pressure-design",
    "piping.b311-wall-thickness": "pressure-design",
    "piping.b31-allowable-pressure": "pressure-design",
    "piping.branch-reinforcement": "pressure-design",
    "piping.bend-thickness": "pressure-design",
    "piping.miter-allowable-pressure": "pressure-design",
    "piping.leak-test-pressure": "pressure-design",
    "piping.displacement-stress": "stress-screening",
    "piping.sustained-stress": "stress-screening",
    "piping.fatigue-factor": "stress-screening",
    "supports.spring-variability": "stress-screening",
    "supports.max-spring-rate": "stress-screening",
    "noncode.pipe-section": "stress-screening",
    "structural.aisc-member": "pipe-support",
    "structural.fillet-weld": "pipe-support",
    "structural.baseplate-anchorage": "pipe-support",
    "structural.pier-soil": "pipe-support",
    "connections.nozzle-load-check": "nozzle-load",
    "connections.nema-sm23": "nozzle-load",
    "connections.api610-annexf": "nozzle-load",
    "connections.flange-equivalent-pressure": "bolted-flange",
    "aux.app2-flange-integral": "bolted-flange",
}


def sanitize(fx: dict) -> dict:
    cases = []
    for c in fx["cases"]:
        keep = {"input": c["input"]}
        for k in ("expect", "status", "tol"):
            if k in c:
                keep[k] = c[k]
        cases.append(keep)
    return {"module": fx["module"], "cases": cases}


def load_source(src: str) -> dict[str, tuple[str, dict, str]]:
    out = {}
    for path in glob.glob(os.path.join(src, "packages", "calc-core", "fixtures", "*.json")):
        raw = open(path, "rb").read()
        fx = json.loads(raw)
        if fx.get("module") in MODULES:
            out[fx["module"]] = (os.path.basename(path), fx, hashlib.sha256(raw).hexdigest())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="pipecalcpro checkout")
    ap.add_argument("--check", action="store_true", help="fail if the snapshot is stale")
    a = ap.parse_args()

    found = load_source(a.src)
    missing = sorted(set(MODULES) - set(found))
    if missing:
        print(f"missing fixtures in source: {missing}", file=sys.stderr)
        return 2

    if a.check:
        man = json.load(open(MANIFEST, encoding="utf-8"))
        stale = [m for m, (_, _, h) in found.items() if man["modules"][m]["source_sha256"] != h]
        if stale:
            print(f"STALE vs calc-core: {stale} - rerun without --check and re-run parity tests",
                  file=sys.stderr)
            return 1
        print(f"snapshot current ({len(found)} modules)")
        return 0

    try:
        commit = subprocess.run(["git", "-C", a.src, "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from parity import fixture_filename  # one Windows-safe naming rule for writer and reader

    os.makedirs(DEST, exist_ok=True)
    manifest = {"source": "pipecalcpro packages/calc-core/fixtures", "calc_core_commit": commit,
                "modules": {}}
    for module, (fname, fx, h) in sorted(found.items()):
        clean = sanitize(fx)
        with open(os.path.join(DEST, fixture_filename(module)), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(clean, fh, indent=2)
            fh.write("\n")
        manifest["modules"][module] = {"skill": MODULES[module], "source_file": fname,
                                       "source_sha256": h, "cases": len(clean["cases"])}
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    total = sum(m["cases"] for m in manifest["modules"].values())
    print(f"vendored {len(found)} modules, {total} cases @ {commit[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
