#!/usr/bin/env python3
"""validate_pcf - check a PCF for a clean CAESAR II import before handing it over.

    python validate_pcf.py line.pcf [--skeys FLWN,ELBW,...] [--full-vocabulary] [--json]

Errors (exit 1): floating components (start attaches to no existing node), zero-length
elements, olets off the centreline, supports not on a node, record types outside the
CAESAR II safe set, missing or mismatched UNITS-BORE / UNITS-CO-ORDS, bores that look
like inches under UNITS-BORE MM. Warnings (exit 0): asymmetric bend tangents, bore
changes without a reducer, SKEYs outside the --skeys list, record types that are
accepted but not import-proven (GASKET, OLET), LF line endings.

It does NOT check that the SKEYs are what your site's Isogen emits, continuation
coordinates against adjoining sheets, or the axis declaration - do those by hand.

Works on any PCF (the builder's own or a third-party export). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, List, Optional, Tuple

INLINE = {"PIPE", "PIPE-FIXED", "ELBOW", "BEND", "FLANGE", "FLANGE-BLIND", "GASKET",
          "VALVE", "VALVE-ANGLE", "REDUCER-ECCENTRIC", "REDUCER-CONCENTRIC", "CAP",
          "MISC-COMPONENT", "TEE", "INSTRUMENT", "COUPLING", "UNION", "FILTER", "TRAP"}
POINT_ONLY = {"OLET", "SUPPORT", "WELD"}
# Seen in PCFs that import cleanly into CAESAR II, and reported-accepted but unproven.
PROVEN = {"PIPE", "PIPE-FIXED", "BEND", "TEE", "FLANGE", "VALVE", "VALVE-ANGLE",
          "REDUCER-CONCENTRIC", "SUPPORT"}
ACCEPTED = {"GASKET", "OLET"}
SAFE = PROVEN | ACCEPTED
# Nominal sizes written in inches. Under UNITS-BORE MM a real bore is size x 25.4
# (1/8 -> 3.175, 1/4 -> 6.35), so an exact inch value here is a unit error.
NPS_INCH = {0.125, 0.25, 0.375, 0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 8}
HEADER = ("ISOGEN-FILES", "UNITS-", "PIPELINE-REFERENCE", "PROJECT-IDENTIFIER", "AREA",
          "MATERIALS", "SPOOL", "DATE", "REVISION", "PIPING-SPEC", "MESSAGE")

Vec = Tuple[float, float, float]


def parse(text: str) -> Tuple[List[dict], Dict[str, str]]:
    comps: List[dict] = []
    header: Dict[str, str] = {}
    cur: Optional[dict] = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if not raw[0].isspace():
            tok = raw.split()
            kind = tok[0]
            if kind.startswith(HEADER) or (len(tok) > 1 and kind not in INLINE | POINT_ONLY):
                header[kind] = " ".join(tok[1:])
                cur = None
                continue
            cur = {"kind": kind, "ends": [], "branch": None, "centre": None, "co": None,
                   "desc": "", "skey": None, "line": len(comps)}
            comps.append(cur)
            continue
        if cur is None:
            continue
        t = raw.split()
        key = t[0]

        def pt(vals):
            xyz = tuple(float(x) for x in vals[:3])
            return xyz + ((float(vals[3]) if len(vals) > 3 else None),)
        if key == "END-POINT":
            cur["ends"].append(pt(t[1:]))
        elif key == "BRANCH1-POINT":
            cur["branch"] = pt(t[1:])
        elif key == "CENTRE-POINT":
            cur["centre"] = pt(t[1:])
        elif key == "CO-ORDS":
            cur["co"] = pt(t[1:])
        elif key == "ITEM-DESCRIPTION":
            cur["desc"] = " ".join(t[1:])
        elif key == "SKEY":
            cur["skey"] = t[1] if len(t) > 1 else ""
    return comps, header


def d3(a, b) -> float:
    return math.dist(a[:3], b[:3])


def seg_dist(p, a, b) -> float:
    ax, ay, az = a[:3]
    vx, vy, vz = b[0] - ax, b[1] - ay, b[2] - az
    L2 = vx * vx + vy * vy + vz * vz
    if L2 == 0:
        return d3(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy + (p[2] - az) * vz) / L2))
    return math.dist(p[:3], (ax + t * vx, ay + t * vy, az + t * vz))


def validate(text: str, skeys: Optional[set] = None, safe: bool = True,
             tol: Optional[float] = None) -> dict:
    comps, header = parse(text)
    errs: List[str] = []
    warns: List[str] = []
    unit = header.get("UNITS-CO-ORDS", "").upper()
    bunit = header.get("UNITS-BORE", "").upper()
    if not unit:
        errs.append("no UNITS-CO-ORDS header - the importer cannot scale the file")
    if not bunit:
        errs.append("no UNITS-BORE header")
    elif unit and bunit != unit:
        errs.append(f"UNITS-BORE {bunit} differs from UNITS-CO-ORDS {unit} - import-proven "
                    f"files use MM for both (bore = nominal size x 25.4)")
    if unit == "INCH":
        warns.append("INCH coordinates are not import-proven; MM is")
    tol = tol if tol is not None else (0.05 if unit != "INCH" else 0.002)   # 0.05 mm
    if "\r\n" not in text:
        warns.append("LF line endings - write CRLF for the Windows importer")

    def tag(c):
        return f"#{c['line']} {c['kind']} [{c['desc'][:45]}]"

    # 0. bore unit sanity: under UNITS-BORE MM a bore below 6 is an inch value written
    # into a mm field (the failure mode of writing NPS as the bore).
    if bunit == "MM":
        small = sorted({p[3] for c in comps for p in c["ends"] + [c["branch"], c["co"]]
                        if p and p[3] is not None and p[3] in NPS_INCH})
        if small:
            errs.append(f"bore value(s) {', '.join(f'{b:g}' for b in small[:5])} under UNITS-BORE MM "
                        f"look like inches - write nominal size x 25.4 (NPS 4 -> 101.6)")

    # 1. vocabulary
    for c in comps:
        if c["kind"] not in INLINE | POINT_ONLY:
            errs.append(f"unknown record type {tag(c)}")
        elif safe and c["kind"] not in SAFE:
            errs.append(f"record type outside the CAESAR II safe set {tag(c)} - map it "
                        f"(see references/caesar-import.md) or pass --full-vocabulary")
        elif safe and c["kind"] in ACCEPTED:
            warns.append(f"{c['kind']} is accepted but not yet seen in an import-proven file {tag(c)}")
        if skeys is not None and c["skey"] and c["skey"] not in skeys:
            warns.append(f"SKEY {c['skey']} not in the confirmed list {tag(c)}")

    # 2. connectivity as a tree, in file order. A component may start at ANY node already
    # placed (tee branch, olet branch, earlier run end). A tee is 3-legged, so the arriving
    # run may land on any leg. A start that matches nothing is a floating element: the
    # commonest cause of orphan nodes on import.
    placed: List[tuple] = []           # (point, owner kind)

    def hit(p):
        for q, k in placed:
            if d3(p, q) <= tol:
                return k, q
        return None

    first = True
    jumps = 0
    for c in comps:
        if c["kind"] == "OLET":
            for p in (c["centre"], c["branch"]):
                if p:
                    placed.append((p, "OLET"))
            continue
        if c["kind"] not in INLINE or not c["ends"]:
            continue
        legs = list(c["ends"]) + ([c["branch"]] if c["branch"] else [])
        att = [(p, hit(p)) for p in legs]
        joined = [(p, h) for p, h in att if h]
        if first:
            first = False
        elif not joined:
            s = c["ends"][0]
            errs.append(f"FLOATING {tag(c)} starts at ({s[0]:.1f}, {s[1]:.1f}, {s[2]:.1f}) - "
                        f"matches no existing node")
        else:
            if placed and d3(placed[-1][0], c["ends"][0]) > tol:
                jumps += 1
            # Bore continuity leg by leg: the attaching leg's bore must equal the bore of
            # the node it lands on (tee and olet branch nodes carry the branch bore). Only a
            # reducer changes bore, and it does so between its OWN two legs.
            p, (_owner, q) = joined[0]
            if p[3] is not None and q[3] is not None and abs(p[3] - q[3]) > 1e-6:
                warns.append(f"BORE CHANGE {q[3]:g} -> {p[3]:g} at {tag(c)} with no reducer")
        for e in c["ends"]:
            placed.append((e, c["kind"]))
        if c["branch"]:
            placed.append((c["branch"], c["kind"]))

    # 3. zero-length
    inline = [c for c in comps if c["kind"] in INLINE and len(c["ends"]) >= 2]
    for c in inline:
        if d3(c["ends"][0], c["ends"][1]) <= tol:
            errs.append(f"ZERO-LENGTH {tag(c)} - creates coincident nodes")

    # 4. olets and supports on the centreline
    segs = []
    for c in inline:
        a, b = c["ends"][0], c["ends"][1]
        if c["kind"] in ("ELBOW", "BEND") and c["centre"]:
            segs += [(a, c["centre"]), (c["centre"], b)]      # tangent legs: corner is on-line
        else:
            segs.append((a, b))
        if c["kind"] == "TEE" and c["branch"]:
            mid = c["centre"] or tuple((a[i] + b[i]) / 2 for i in range(3))
            segs.append((mid, c["branch"]))
    nodes = [p for c in comps if c["kind"] in INLINE for p in c["ends"] + [c["branch"]] if p]
    for c in comps:
        p = c["centre"] if c["kind"] == "OLET" else c["co"] if c["kind"] == "SUPPORT" else None
        if p and segs:
            off = min(seg_dist(p, a, b) for a, b in segs)
            if off > tol:
                errs.append(f"{c['kind']} OFF-LINE by {off:.2f} {unit.lower() or 'units'} {tag(c)}")
            elif c["kind"] == "SUPPORT" and not any(d3(p, q) <= tol for q in nodes):
                errs.append(f"SUPPORT not on a node {tag(c)} - split the element at the support")

    # 5. elbow tangent symmetry
    for c in comps:
        if c["kind"] in ("ELBOW", "BEND") and c["centre"] and len(c["ends"]) >= 2:
            r1, r2 = d3(c["centre"], c["ends"][0]), d3(c["centre"], c["ends"][1])
            if abs(r1 - r2) > max(10 * tol, 0.5 if unit != "INCH" else 0.02):
                warns.append(f"elbow tangents asymmetric {r1:.1f} vs {r2:.1f} {tag(c)} - "
                             f"corner or radius is wrong")

    ext = None
    if inline:
        ext = [[min(e[i] for c in inline for e in c["ends"]), max(e[i] for c in inline for e in c["ends"])]
               for i in range(3)]
    census: Dict[str, int] = {}
    for c in comps:
        census[c["kind"]] = census.get(c["kind"], 0) + 1
    return {"units": unit or "?", "census": census, "branch_jumps": jumps,
            "extents": ext, "centreline_length": sum(d3(c["ends"][0], c["ends"][1]) for c in inline),
            "errors": errs, "warnings": warns, "ok": not errs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pcf")
    ap.add_argument("--skeys", help="comma-separated SKEYs confirmed in your site's Isogen PCFs")
    ap.add_argument("--full-vocabulary", action="store_true",
                    help="allow record types outside the CAESAR II safe set")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        with open(a.pcf, encoding="ascii", errors="replace", newline="") as fh:
            text = fh.read()
    except OSError as e:
        print(f"cannot read {a.pcf}: {e}", file=sys.stderr)
        return 1
    r = validate(text, set(a.skeys.split(",")) if a.skeys else None, safe=not a.full_vocabulary)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0 if r["ok"] else 1
    u = r["units"].lower()
    print(f"File: {a.pcf}")
    print("Components: " + ", ".join(f"{k} {v}" for k, v in sorted(r["census"].items())))
    if r["extents"]:
        print("Extents ({}): ".format(u) + "   ".join(
            f"{ax} {lo:.0f}..{hi:.0f}" for ax, (lo, hi) in zip("XYZ", r["extents"])))
    print(f"Total inline centreline length: {r['centreline_length']:.0f} {u}")
    print(f"Branch starts (tee/olet legs): {r['branch_jumps']}")
    if r["errors"]:
        print(f"\n!! {len(r['errors'])} ERRORS - not deliverable")
        for e in r["errors"]:
            print("   " + e)
    else:
        print("\nOK - every component attaches to an existing node; no floating or zero-length")
        print("     elements; olets and supports lie on the centreline; record types are safe.")
    if r["warnings"]:
        print(f"\n{len(r['warnings'])} warnings:")
        for w in r["warnings"]:
            print("   " + w)
    print("\nNot checked here: SKEYs vs your site's Isogen output, continuation coordinates vs")
    print("adjoining sheets, the vertical-axis declaration. Check those by hand.")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
