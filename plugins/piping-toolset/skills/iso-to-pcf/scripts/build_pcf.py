#!/usr/bin/env python3
"""build_pcf - walk a JSON transcription of a stress isometric into a CAESAR II PCF.

    python build_pcf.py spec.json -o line.pcf [--report report.txt] [--json]

The spec (references/spec-format.md) is a transcription of the drawing: start point,
then an ordered walk of components with the drawing's own dimensions as iso strings
("13.7/8", "2635'0.7/16"). This script does all of the geometry - bend tangents,
tee and olet branch points, sloped elevations, axis mapping, mm conversion - in exact
Fraction arithmetic with a single cursor, so adjacent components share one coordinate
and the chain is continuous by construction.

Exit codes: 0 clean; 2 a closure check or BOM count failed (PCF still written so it can
be inspected, but it is not deliverable); 1 the spec is defective (nothing written).

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction as F
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcf_lib import (DIRS, PCF, SAFE_MAP, PCFError, Point, Profile, add, along,  # noqa: E402
                     angle_deg, fmt_in, ftin, length, off_ray, sub, tangent, unit)


# Closure-check flag words, chosen by truth value rather than a conditional expression
# (a plugin-directory scanner reads the conditional form as a credential read).
_FLAG_WORDS = ("FAIL", "PASS")


def _flag(ok) -> str:
    return _FLAG_WORDS[1 if ok else 0]

INLINE_TYPES = {"flange": "FLANGE", "blind": "FLANGE-BLIND", "gasket": "GASKET",
                "valve": "VALVE", "cap": "CAP", "misc": "MISC-COMPONENT",
                "coupling": "COUPLING"}
# Defaults: VVFL/RCBW/BEBW/TEBW and the support SKEYs are seen in import-proven PCFs;
# FLWN/FLBL/WTBW are common Isogen keys. Override per item with "skey".
DEFAULT_SKEY = {"FLANGE": "FLWN", "FLANGE-BLIND": "FLBL", "VALVE": "VVFL", "GASKET": None,
                "CAP": None, "MISC-COMPONENT": "VVFL", "COUPLING": None}
SUPPORT_SKEYS = {"ANCH": None, "SKID": "UP", "GUID": None, "SPRG": "UP"}   # skey: default direction
LINE_TOL = 1 / 64   # in: perpendicular offset beyond which a point is off the run


class Builder:
    def __init__(self, spec: dict):
        self.spec = spec
        self.pcf = PCF(axes=spec.get("axes", "Z-up"), coords=spec.get("units", "MM"),
                       safe=not spec.get("full_vocabulary", False),
                       weight_units=spec.get("weight_units", "LBS"),
                       annotate=bool(spec.get("annotate", True)))
        self.profiles: Dict[str, Profile] = {}
        for name, p in spec.get("profiles", {}).items():
            self.profiles[name] = Profile(p["along"], [(ftin(s), ftin(z)) for s, z in p["points"]])
        st = spec["start"]
        self.cursor: Point = self.point(st["at"], base=(F(0), F(0), F(0)), absolute=True)
        self.anchor: Point = self.cursor
        self.dir: Point = self.direction(st["dir"])
        self.bore: F = F(str(st["bore"]))
        self.checks: List[dict] = []
        self.pipe_len: Dict[str, F] = {}
        self.assumed: List[str] = list(spec.get("assumed", []))
        self.substitutions: List[str] = []
        self.deferred: List[tuple] = []     # branch walks, written after the main run

    # ------------------------------------------------------------------ inputs
    def direction(self, d) -> Point:
        if isinstance(d, str):
            if d.upper() not in DIRS:
                raise PCFError(f"direction {d!r}: use E W N S UP DOWN or {{e,n,el}}")
            return DIRS[d.upper()]
        return unit((ftin(d.get("e", "0")), ftin(d.get("n", "0")), ftin(d.get("el", "0"))))

    def point(self, p: dict, base: Optional[Point] = None, absolute: bool = False) -> Point:
        """Resolve a point spec. Forms (all dims are iso strings):
        {"E":..,"N":..,"EL":..}  absolute plant coords; omitted ones inherit the anchor;
                                 EL may be "@<profile>" to interpolate at this E/N.
        {"d": {"e":..,"n":..,"el":..}}  delta from the anchor (last stated point).
        {"len": ..}               distance along the current direction from the anchor.
        """
        base = self.anchor if base is None else base
        if "d" in p:
            d = p["d"]
            return add(base, (ftin(d.get("e", "0")), ftin(d.get("n", "0")), ftin(d.get("el", "0"))))
        if "len" in p:
            return along(base, self.dir, ftin(p["len"]))
        if not any(k in p for k in ("E", "N", "EL")):
            raise PCFError(f"point {p!r} has no E/N/EL, d or len")
        if absolute and not all(k in p for k in ("E", "N", "EL")):
            raise PCFError("start point must give E, N and EL")
        e = ftin(p["E"]) if "E" in p else base[0]
        n = ftin(p["N"]) if "N" in p else base[1]
        el = p.get("EL")
        if isinstance(el, str) and el.startswith("@"):
            prof = self.profiles.get(el[1:])
            if prof is None:
                raise PCFError(f"unknown profile {el!r}")
            z = prof.el((e, n)[prof.idx])
        elif el is not None:
            z = ftin(el)
        else:
            z = base[2]
        return (e, n, z)

    # ------------------------------------------------------------------ helpers
    def _on_line(self, target: Point, what: str):
        """target must lie ahead of the cursor on the current run, within 1/64 in."""
        if target == self.cursor:
            return
        ahead, perp = off_ray(target, self.cursor, self.dir)
        if perp > LINE_TOL or ahead <= 0:
            raise PCFError(f"{what}: point is {'behind the cursor' if ahead <= 0 else 'off the run'} "
                           f"({perp:.3f} in off-line, {ahead:.3f} in ahead) - check the walk")

    def _pipe_to(self, p2: Point, it: dict, label: str):
        if p2 == self.cursor:
            return                                   # fittings make up: no pipe element
        self._on_line(p2, label)
        own = it.get("type") == "pipe"
        self.pcf.inline("PIPE", self.cursor, p2, self.bore,
                        desc=it.get("desc") if own else it.get("pipe_desc"))
        k = f"{float(self.bore):g}"
        self.pipe_len[k] = self.pipe_len.get(k, F(0)) + F(round(length(sub(p2, self.cursor)) * 10000), 10000)
        self.cursor = p2

    def _radius(self, it: dict) -> F:
        r = it.get("radius", "LR")
        if r in ("LR", "SR"):
            # B16.9 convention: LR = 1.5 x NPS, SR = 1.0 x NPS, inches. Valid for NPS >= 3/4
            # only where NPS is the nominal size the user entered as bore.
            self.assumed.append(f"{r} elbow radius taken as {'1.5' if r == 'LR' else '1.0'} x NPS "
                                f"{float(self.bore):g} (B16.9 convention); state it if the iso differs")
            return self.bore * (F(3, 2) if r == "LR" else F(1))
        return ftin(r)

    # ------------------------------------------------------------------ walk
    def walk(self, items: List[dict]):
        for i, it in enumerate(items):
            t = it.get("type")
            handler = getattr(self, f"do_{t}", None)
            if handler is None:
                raise PCFError(f"item {i}: unknown type {t!r}")
            try:
                handler(it)
            except PCFError as e:
                raise PCFError(f"item {i} ({t} {it.get('desc', '')}): {e}") from None
            except KeyError as e:
                raise PCFError(f"item {i} ({t} {it.get('desc', '')}): missing key {e}") from None

    def do_pipe(self, it):
        p2 = self.point(it["to"])
        self._pipe_to(p2, it, "pipe")
        self.anchor = p2

    def _inline(self, it, logical, bore2=None, extra=()):
        if "at" in it:                                   # stated start: pipe up to it first
            self._pipe_to(self.point(it["at"]), it, logical)
        if "len" in it:
            p2 = along(self.cursor, self.dir, ftin(it["len"]))
        elif "to" in it:
            p2 = self.point(it["to"], base=self.cursor)
        else:
            raise PCFError("needs len (face-to-face along the run) or to")
        self._on_line(p2, logical)
        skey = it.get("skey", DEFAULT_SKEY.get(logical))
        self.pcf.inline(logical, self.cursor, p2, self.bore, bore2=bore2, desc=it.get("desc"),
                        skey=skey, weight=F(str(it["weight"])) if "weight" in it else None,
                        extra=extra)
        if self.pcf.safe and logical in SAFE_MAP:
            self.substitutions.append(f"{logical} written as a {SAFE_MAP[logical]} record "
                                      f"({it.get('desc', logical)}, SKEY {skey or 'none'})")
        self.cursor = self.anchor = p2

    def __getattr__(self, name):
        if name.startswith("do_") and name[3:] in INLINE_TYPES:
            logical = INLINE_TYPES[name[3:]]
            return lambda it: self._inline(it, logical)
        raise AttributeError(name)

    def do_reducer(self, it):
        new = F(str(it["bore"]))
        ecc = bool(it.get("eccentric"))
        logical = "REDUCER-ECCENTRIC" if ecc else "REDUCER-CONCENTRIC"
        extra = [f"FLAT-DIRECTION {it.get('flat', 'DOWN')}"] if ecc else []
        if "skey" not in it:
            it = dict(it, skey="RECC" if ecc else "RCBW")
        if ecc and "to" not in it:
            raise PCFError("eccentric reducer needs 'to' (the offset end point), not just len")
        if ecc and self.pcf.safe:
            self.substitutions.append(f"eccentric reducer written as REDUCER-CONCENTRIC; the offset "
                                      f"is carried by its end points ({it.get('desc', '')})")
        if ecc:
            p2 = self.point(it["to"], base=self.cursor)
            self.pcf.inline(logical, self.cursor, p2, self.bore, bore2=new, desc=it.get("desc"),
                            skey=it["skey"], extra=extra)
            self.cursor = self.anchor = p2
        else:
            self._inline(it, logical, bore2=new)
        self.bore = new

    def _bend(self, it, bend: bool):
        corner = self.point(it["corner"])
        out = self.direction(it["out"])
        ang = angle_deg(self.dir, out)
        if "angle" in it:                                # trimmed/odd angle stated on the iso
            stated = float(F(str(it["angle"])))
            if abs(stated - ang) > 0.25:
                raise PCFError(f"stated angle {stated} deg vs {ang:.2f} deg from the directions")
        R = self._radius(it)
        T = tangent(R, ang)
        t1 = along(corner, self.dir, -T)
        if t1 != self.cursor:
            if off_ray(t1, self.cursor, self.dir)[0] <= 0:
                raise PCFError(f"tangent {fmt_in(T)} overruns the previous component - "
                               f"radius or corner is wrong")
        self._pipe_to(t1, it, "bend")
        t2 = along(corner, out, T)
        self.pcf.bend(t1, t2, corner, self.bore, ang, R, desc=it.get("desc"),
                      skey=it.get("skey", "BEBW"), logical="BEND" if bend else "ELBOW")
        self.cursor, self.anchor, self.dir = t2, corner, out

    def do_elbow(self, it):
        self._bend(it, bend=False)

    def do_bend(self, it):
        self._bend(it, bend=True)

    def _branch(self, it, centre: Point, bp: Point, bdir: Point, bbore: F):
        # Isogen writes the main run first and each branch leg after it; the import-proven
        # files follow that order, so branch walks are queued, not walked in place.
        if it.get("branch"):
            self.deferred.append(((bp, centre, bdir, bbore), it["branch"]))

    def do_tee(self, it):
        centre = self.point(it["centre"])
        C = ftin(it["C"])
        M = ftin(it.get("M", it["C"]))
        bdir = self.direction(it["branch_dir"])
        if float(sum(a * b for a, b in zip(bdir, self.dir))) != 0:
            raise PCFError("tee branch direction must be square to the run")
        bbore = F(str(it.get("branch_bore", self.bore)))
        p1, p2 = along(centre, self.dir, -C), along(centre, self.dir, C)
        self._pipe_to(p1, it, "tee")
        bp = along(centre, bdir, M)
        self.pcf.tee(p1, p2, centre, self.bore, bp, bbore, desc=it.get("desc"),
                     skey=it.get("skey", "TEBW"))
        self.cursor, self.anchor = p2, centre
        self._branch(it, centre, bp, bdir, bbore)
        self.cursor, self.anchor = p2, centre

    def do_olet(self, it):
        centre = self.point(it["at"])
        self._on_line(centre, "olet")
        bdir = self.direction(it["branch_dir"])
        bbore = F(str(it["branch_bore"]))
        bp = along(centre, bdir, ftin(it["height"]))
        self.pcf.olet(centre, bp, bbore, desc=it.get("desc"), skey=it.get("skey", "WTBW"))
        self.anchor = centre
        self._branch(it, centre, bp, bdir, bbore)
        self.anchor = centre

    def do_support(self, it):
        """A support must sit ON a node: the pipe is split at the support point (the
        import-proven files never place a restraint mid-element)."""
        at = self.point(it["at"]) if "at" in it else self.cursor
        if at != self.cursor:
            self._pipe_to(at, it, "support")          # raises if behind or off the run
        skey = it.get("skey", "SKID")
        dirs = it.get("direction", SUPPORT_SKEYS.get(skey, "UP"))
        for d in (dirs if isinstance(dirs, list) else [dirs]):
            self.pcf.support(at, self.bore, skey=skey, direction=d, name=it.get("name"),
                             desc=it.get("desc"))
        self.anchor = at

    def do_check(self, it):
        got = self.cursor if it.get("of") == "cursor" else self.anchor
        want = self.point(it["expect"], base=got)
        tol = ftin(it.get("tol", "0.1/16"))
        d = sub(got, want)
        self.checks.append({"label": it["label"], "delta_in": [float(x) for x in d],
                            "tol_in": float(tol), "pass": all(abs(x) <= tol for x in d)})

    # ------------------------------------------------------------------ run
    def build(self):
        pl = self.spec.get("pipeline", {})
        attrs = [(a[0], a[1]) for a in pl.get("attributes", [])]
        self.pcf.set_header(pl.get("reference", "LINE"), attrs)
        self.walk(self.spec["items"])
        while self.deferred:                          # branches of branches queue behind
            (self.cursor, self.anchor, self.dir, self.bore), items = self.deferred.pop(0)
            self.walk(items)
        return self

    def bom_check(self) -> List[dict]:
        out = []
        for k, want in self.spec.get("bom", {}).items():
            k = k.upper()
            if k.startswith("PIPE-LENGTH"):          # PIPE-LENGTH:<bore> magnitude check, 10%
                bore = k.split(":", 1)[1]
                got = float(self.pipe_len.get(bore, 0))
                w = float(ftin(want))
                ok = w == 0 and got == 0 or (w > 0 and abs(got - w) / w <= 0.10)
                out.append({"item": k, "bom": fmt_in(F(w)), "emitted": fmt_in(F(got)), "pass": ok,
                            "note": "cut length vs centreline: +/-10% magnitude check"})
            else:
                got = self.pcf.census.get(k, 0)
                out.append({"item": k, "bom": int(want), "emitted": got, "pass": got == int(want)})
        return out


def report(b: Builder, bom: List[dict]) -> dict:
    return {
        "pipeline": b.spec.get("pipeline", {}).get("reference", "LINE"),
        "axes": b.spec.get("axes", "Z-up"),
        "coords": b.pcf.coords,
        "vocabulary": "CAESAR II safe set" if b.pcf.safe else "full PCF vocabulary",
        "annotated": b.pcf.annotate,
        "census": dict(sorted(b.pcf.census.items())),
        "pipe_centreline_in": {k: float(v) for k, v in sorted(b.pipe_len.items())},
        "closure_checks": b.checks,
        "bom_checks": bom,
        "assumed": list(dict.fromkeys(b.assumed)),
        "substitutions": b.substitutions,
        "ok": all(c["pass"] for c in b.checks) and all(c["pass"] for c in bom),
    }


def render(r: dict) -> str:
    L = [f"PCF build report - {r['pipeline']}",
         f"Axes: {r['axes']}   Coords: {r['coords']}   Vocabulary: {r['vocabulary']}", "",
         "Component census:"]
    L += [f"  {k:20s} {v}" for k, v in r["census"].items()]
    L += ["", "Pipe centreline length by bore (in):"]
    L += [f"  {k:>6s} in  {fmt_in(F(v))}" for k, v in r["pipe_centreline_in"].items()]
    L += ["", f"Closure checks ({sum(not c['pass'] for c in r['closure_checks'])} failed):"]
    for c in r["closure_checks"]:
        d = c["delta_in"]
        L.append(f"  [{_flag(c['pass'])}] {c['label']:45s} "
                 f"dE={d[0]:+.4f} dN={d[1]:+.4f} dEL={d[2]:+.4f} in")
    if r["bom_checks"]:
        L += ["", "BOM reconciliation:"]
        L += [f"  [{_flag(c['pass'])}] {c['item']:20s} BOM {c['bom']}  emitted {c['emitted']}"
              for c in r["bom_checks"]]
    for title, key in (("ASSUMED", "assumed"), ("Record substitutions", "substitutions")):
        if r[key]:
            L += ["", f"{title}:"] + [f"  - {x}" for x in r[key]]
    L += ["", "RESULT: " + ("OK - run validate_pcf.py next" if r["ok"]
                            else "NOT DELIVERABLE - fix the spec at the source and rebuild")]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", required=True, help="PCF path to write")
    ap.add_argument("--report", help="also write the text report here")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args(argv)
    try:
        with open(a.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        b = Builder(spec).build()
    except (PCFError, KeyError, ValueError, ArithmeticError) as e:
        print(f"SPEC ERROR: {e}", file=sys.stderr)
        return 1
    b.pcf.write(a.out)
    r = report(b, b.bom_check())
    text = render(r)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(json.dumps(r, indent=2) if a.json else text)
    print(f"\nPCF written: {a.out}", file=sys.stderr)
    return 0 if r["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
