#!/usr/bin/env python3
"""
nwc_supports.py - mine pipe-support items (hangers, trapezes, stands, riser clamps)
out of an Autodesk Navisworks cache (.nwc) exported from Revit, without Navisworks.

What it does
------------
An .nwc is a chain of zlib-deflated chunks ("LcUStream" format). Inflated, each
Revit element carries its property strings (family, type, category, system,
IFC GUID, workset) in a record that starts with the marker "By Type\\0", and an
insertion point stored as three little-endian float64 values (Revit internal
feet, project coordinates - the same frame Revit PCF exports use, x12 for inches).

The record layout is undocumented. This script therefore:
  * classifies records by the strings found before each "By Type" marker,
  * takes the FIRST plausible XYZ triple inside the record (z inside a window you
    give it), and
  * reports what it found so the result can be checked against the PCF
    (pcf_prep.py, job key "supports_csv", does the snapping and reports snap distances).

Treat the output as a model-derived support LAYOUT, not a support DESIGN.
Verify a sample against Navisworks Manage (select element > Properties) before issue.

Standard library only. Python 3.9+.

Usage
-----
  python nwc_supports.py MODEL.nwc -o supports.csv [--zmin 780 --zmax 1000]
         [--items-out items.csv] [--families families.json] [--log run.log]

  --zmin/--zmax  window for the elevation (ft, Revit project Z) of a plausible insertion
                 point; it filters garbage float triples. Choose it from the level you are
                 mining; the defaults accept any value.
  --xyabs        largest plausible |x| and |y| in ft (default 1e5).
  --families     JSON object {"substring of family or type name": "CLASS"} that is merged
                 over the built-in map (see examples/nwc-families.example.json; keys that
                 start with an underscore are comments and ignored). Classes
                 CLEVIS, TRAPEZE, RISER and ROLLER are what a "Fabrication hanger" category
                 record can take; any other class name is carried through to the CSV and
                 ignored by pcf_prep.py unless its job lists that class in "support_rules".
  --items-out    also write EVERY element record that has a coordinate (name, system, xyz),
                 which pcf_prep.py uses to name in-line items the PCF export left out.

Output CSV columns: cls, family, system, guid, level, x_ft, y_ft, z_ft, has_xyz
(coordinates are Revit feet in project coordinates, the frame of the PCF export).

Exit codes: 0 ok, 1 bad input / unreadable file, 2 nothing found.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

LOG = logging.getLogger("nwc_supports")

# Default family -> support class map.  Keys are case-insensitive substrings of the
# Revit family/type name.  Classes are interpreted by pcf_prep.py.  These are generic
# names only: project-specific family names (floor stands, equipment frames ...) belong in
# a --families file.
DEFAULT_FAMILIES: Dict[str, str] = {
    "Trapeze": "TRAPEZE",
    "Clevis": "CLEVIS",
    "Pipe_Roll": "ROLLER",
    "Roller": "ROLLER",
    "Riser Clamp": "RISER",
}
HANGER_CATEGORY = "MEP Fabrication Hangers"

STR_RE = re.compile(rb"([\x20-\x7e]{3,})\x00")
GUID_RE = re.compile(r"[0-9A-Za-z_$]{22}")
MARK = b"By Type\x00"


def inflate_nwc(path: Path) -> bytes:
    """Inflate every zlib chunk in order and concatenate them."""
    raw = path.read_bytes()
    if not raw.startswith(b"#LcUStream"):
        LOG.warning("File does not start with #LcUStream - may not be an .nwc; trying anyway")
    out = bytearray()
    pos = 0
    chunks = 0
    for m in re.finditer(rb"\x78[\x01\x5e\x9c\xda]", raw):
        start = m.start()
        if start < pos:
            continue
        d = zlib.decompressobj()
        try:
            data = d.decompress(raw[start:])
        except zlib.error:
            continue
        if len(data) < 64:
            continue
        consumed = len(raw) - start - len(d.unused_data)
        out += data
        pos = start + consumed
        chunks += 1
    LOG.info("inflated %d chunks, %d bytes -> %d bytes", chunks, len(raw), len(out))
    if not out:
        raise ValueError("no zlib streams found - unsupported .nwc variant")
    return bytes(out)


def first_xyz(buf: bytes, start: int, end: int, zmin: float, zmax: float,
              xyabs: float) -> Optional[Tuple[float, float, float]]:
    """First float64 triple in [start,end) with z in window and |x|,|y| < xyabs."""
    end = min(end, len(buf) - 24)
    for off in range(start, end):
        x, y, z = struct.unpack_from("<ddd", buf, off)
        if zmin < z < zmax and abs(x) < xyabs and abs(y) < xyabs and abs(x) > 1e-3 and abs(y) > 1e-3:
            return x, y, z
    return None


def classify(tail: List[str], families: Dict[str, str]) -> Optional[Tuple[str, str]]:
    joined = " | ".join(tail).lower()
    if tail and tail[-1] == HANGER_CATEGORY:
        for key, cls in families.items():
            if key.lower() in joined and cls in ("CLEVIS", "TRAPEZE", "RISER", "ROLLER"):
                return key, cls
        # Fabrication hanger whose family name was string-pooled away (seen in real
        # exports: the record carries only the category).  Treated as a TRAPEZE and
        # flagged as inferred in the family column.
        return "MEP Fabrication Hanger (family not in record - inferred TRAPEZE)", "TRAPEZE"
    for key, cls in families.items():
        if key.lower() in joined:
            fam = next((s for s in reversed(tail) if key.lower() in s.lower()), key)
            return fam, cls
    return None


def mine(blob: bytes, families: Dict[str, str], zmin: float, zmax: float,
         xyabs: float) -> List[dict]:
    marks = [m.start() for m in re.finditer(re.escape(MARK), blob)]
    LOG.info("%d element records", len(marks))
    rows: List[dict] = []
    for i, a in enumerate(marks):
        back = blob[max(0, a - 500):a]
        tail = [s.decode() for s in STR_RE.findall(back)][-6:]
        hit = classify(tail, families)
        if not hit:
            continue
        family, cls = hit
        nxt = marks[i + 1] if i + 1 < len(marks) else a + 2000
        end = min(nxt, a + 1500)
        fwd = [s.decode() for s in STR_RE.findall(blob[a:end])]
        system = next((s for s in fwd if ": " in s and re.search(r"water|piping|pipe", s, re.I)), "")
        guid = next((s for s in fwd if GUID_RE.fullmatch(s)), "")
        level = next((s for s in fwd if s.startswith("Level : ")), "").replace("Level : ", "")
        xyz = first_xyz(blob, a, end, zmin, zmax, xyabs)
        rows.append(dict(cls=cls, family=family, system=system, guid=guid, level=level,
                         x_ft=round(xyz[0], 5) if xyz else "", y_ft=round(xyz[1], 5) if xyz else "",
                         z_ft=round(xyz[2], 5) if xyz else "", has_xyz=bool(xyz)))
    return rows


SKIP_ITEM_NAMES = {"Default", "Center Line", "By Type", "Workset1", "LcRevitComposite", "LcRevitInstance"}


def mine_items(blob: bytes, zmin: float, zmax: float, xyabs: float) -> List[dict]:
    """Every element record that carries an insertion point: name, system, xyz (ft)."""
    marks = [m.start() for m in re.finditer(re.escape(MARK), blob)]
    rows: List[dict] = []
    for i, a in enumerate(marks):
        back = [s.decode() for s in STR_RE.findall(blob[max(0, a - 500):a])]
        names = [s for s in back if s not in SKIP_ITEM_NAMES and re.search("[A-Za-z]{2}", s)]
        nxt = marks[i + 1] if i + 1 < len(marks) else a + 2000
        end = min(nxt, a + 1500)
        xyz = first_xyz(blob, a, end, zmin, zmax, xyabs)
        if not xyz:
            continue
        fwd = [s.decode() for s in STR_RE.findall(blob[a:end])]
        system = next((s for s in fwd if ": " in s and re.search(r"water|piping", s, re.I)), "")
        rows.append(dict(name=names[-1] if names else "", name2=names[-2] if len(names) > 1 else "",
                         system=system, x_ft=round(xyz[0], 5), y_ft=round(xyz[1], 5), z_ft=round(xyz[2], 5)))
    return rows


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("nwc", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True, help="output CSV")
    ap.add_argument("--zmin", type=float, default=-1e5, help="lowest plausible elevation, ft (filters garbage triples)")
    ap.add_argument("--zmax", type=float, default=1e5)
    ap.add_argument("--xyabs", type=float, default=1e5, help="max |x|,|y| in ft")
    ap.add_argument("--families", type=Path, help="JSON {substring: CLASS} to extend/override the family map")
    ap.add_argument("--items-out", type=Path,
                    help="also write EVERY element record with coordinates (used by pcf_prep.py to "
                         "name in-line items the PCF export left out, e.g. strainers, control valves)")
    ap.add_argument("--log", type=Path)
    a = ap.parse_args(argv)

    handlers = [logging.StreamHandler(sys.stdout)]
    if a.log:
        handlers.append(logging.FileHandler(a.log, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)

    if not a.nwc.is_file():
        LOG.error("not found: %s", a.nwc)
        return 1
    fams = dict(DEFAULT_FAMILIES)
    if a.families:
        try:
            extra = json.loads(a.families.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            LOG.error("cannot read families file %s: %s", a.families, e)
            return 1
        fams.update({k: v for k, v in extra.items() if not k.startswith("_")})   # _comment keys
    try:
        blob = inflate_nwc(a.nwc)
    except (OSError, ValueError) as e:
        LOG.error("cannot read %s: %s", a.nwc, e)
        return 1
    if a.items_out:
        items = mine_items(blob, a.zmin, a.zmax, a.xyabs)
        a.items_out.parent.mkdir(parents=True, exist_ok=True)
        with a.items_out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name", "name2", "system", "x_ft", "y_ft", "z_ft"])
            w.writeheader()
            w.writerows(items)
        LOG.info("wrote %d element records with coordinates -> %s", len(items), a.items_out)
    rows = mine(blob, fams, a.zmin, a.zmax, a.xyabs)
    if not rows:
        LOG.error("no support records found")
        return 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[(r["cls"], r["system"] or "-")] = by.get((r["cls"], r["system"] or "-"), 0) + 1
    for (c, s), n in sorted(by.items()):
        LOG.info("%-16s %-48s %5d", c, s[:48], n)
    LOG.info("wrote %d records (%d with coordinates) -> %s", len(rows), sum(r["has_xyz"] for r in rows), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
