#!/usr/bin/env python3
"""pcf_lib - exact-arithmetic geometry and PCF component emitters.

Every coordinate is carried as fractions.Fraction inches (exact) and converted to the
output unit only in the formatting call. Never introduce floats into geometry: a
sub-millimetre float drift is invisible in the file and becomes a duplicate node on
import. The one unavoidable float source is trigonometry (bend tangents, sloped
direction cosines); those are snapped straight back to a fixed-denominator Fraction.

Points are plant tuples (E, N, EL). The axis mapping to PCF X/Y/Z is applied only when
a point is written, so geometry code never thinks about it.

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import math
import re
from fractions import Fraction as F
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[F, F, F]

MM_PER_IN = F(254, 10)
SNAP = 10000  # denominator for snapped trig results (1/10000 in)

# Record types a CAESAR II PCF import is known to accept without crashing. Anything else
# is mapped onto this set by the emitters when `safe` is on (the default); see
# references/caesar-import.md.
SAFE_RECORDS = ("PIPE", "ELBOW", "BEND", "TEE", "OLET", "FLANGE", "GASKET", "VALVE",
                "REDUCER-CONCENTRIC", "SUPPORT", "WELD")

AXES = {
    # name: (description, mapper (E, N, EL) -> (X, Y, Z))
    "Z-up": ("X=E, Y=N, Z=EL (Z vertical)", lambda p: (p[0], p[1], p[2])),
    "Y-up": ("X=E, Y=EL, Z=-N (Y vertical)", lambda p: (p[0], p[2], -p[1])),
}

DIRS: Dict[str, Point] = {
    "E": (F(1), F(0), F(0)), "W": (F(-1), F(0), F(0)),
    "N": (F(0), F(1), F(0)), "S": (F(0), F(-1), F(0)),
    "UP": (F(0), F(0), F(1)), "DOWN": (F(0), F(0), F(-1)),
}


class PCFError(ValueError):
    """A geometry or input defect that must be fixed at the source, not in the file."""


# --------------------------------------------------------------------------- dimensions

_DIM = re.compile(r"""^\s*(?P<neg>-)?\s*
    (?:(?P<ft>\d+)\s*')?\s*-?\s*
    (?P<inch>\d+)?
    (?:\.(?P<num>\d+)/(?P<den>\d+)|\s+(?P<num2>\d+)/(?P<den2>\d+)|/(?P<den3>\d+))?
    \s*"?\s*$""", re.X)


def ftin(s) -> F:
    """Parse an isometric dimension to exact Fraction inches.

    Iso callout convention: ``X.n/d`` means X **and** n/d inches, never a decimal.
      "2635'0.7/16" -> 2635 ft 0 7/16 in      "13.7/8" -> 13 7/8 in
      "5'4" -> 5 ft 4 in      "4" -> 4 in      "0.1/2" -> 1/2 in
      "5' 4 1/2" and "-1'2" are also accepted. Plain ints/Fractions pass through.
    A true decimal ("13.875") is rejected: on an iso it is almost always a misread
    fraction, and silently accepting it is the error this parser exists to stop.
    """
    if isinstance(s, (int, F)):
        return F(s)
    if not isinstance(s, str):
        raise PCFError(f"dimension must be a string like 13.7/8, got {s!r}")
    m = _DIM.match(s)
    if not m or (m.group("ft") is None and m.group("inch") is None and m.group("num") is None):
        raise PCFError(f"unreadable dimension {s!r} (use iso style: 2635'0.7/16, 13.7/8, 5'4)")
    if any(d is not None and int(d) == 0 for d in (m.group("den"), m.group("den2"), m.group("den3"))):
        raise PCFError(f"zero denominator in {s!r}")
    if m.group("den3") is not None:                      # "7/16" with no whole part
        whole, num, den = F(0), F(m.group("inch") or 0), F(m.group("den3"))
        frac = num / den
    else:
        whole = F(m.group("inch") or 0)
        num = m.group("num") or m.group("num2")
        den = m.group("den") or m.group("den2")
        frac = F(int(num), int(den)) if num else F(0)
        if num and not frac < 1:
            raise PCFError(f"fraction part of {s!r} is not less than 1 inch")
    v = F(int(m.group("ft") or 0)) * 12 + whole + frac
    return -v if m.group("neg") else v


def frac_round(x: float, denom: int = SNAP) -> F:
    """Snap a float (trig result) to a fixed-denominator Fraction."""
    return F(round(x * denom), denom)


def fmt_in(v: F) -> str:
    """Human-readable feet-inches-sixteenths for reports (rounded to 1/16)."""
    neg = v < 0
    t = round(abs(v) * 16)
    ft, rem = divmod(t, 192)
    inch, six = divmod(rem, 16)
    f = F(six, 16)
    s = f"{ft}'{inch}" + (f".{f.numerator}/{f.denominator}" if six else "")
    return ("-" if neg else "") + s


# --------------------------------------------------------------------------- vectors

def add(p: Point, v: Point, k: F = F(1)) -> Point:
    return (p[0] + k * v[0], p[1] + k * v[1], p[2] + k * v[2])


def sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def length(v: Point) -> float:
    return math.sqrt(float(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]))


def unit(v: Point) -> Point:
    """Exact direction representative: the axis unit vector when axis-aligned, else the
    vector itself (exact Fractions, NOT normalised - snapping direction cosines makes
    tangent points drift off a sloped line). Use along() to step a distance on it."""
    nz = [c for c in v if c != 0]
    if not nz:
        raise PCFError("zero-length direction")
    if len(nz) == 1:
        return tuple(F(1 if c > 0 else -1) if c != 0 else F(0) for c in v)  # type: ignore
    return v


def along(p: Point, d: Point, dist: F) -> Point:
    """p + dist along direction d. Exact for an axis direction; for a sloped or skewed d
    the point is computed in floats from the true unit vector and snapped once."""
    if sum(1 for c in d if c != 0) == 1:
        return add(p, d, dist / (abs(d[0]) + abs(d[1]) + abs(d[2])))
    L = length(d)
    return tuple(p[i] + frac_round(float(dist) * float(d[i]) / L) for i in range(3))  # type: ignore


def off_ray(target: Point, origin: Point, d: Point) -> Tuple[float, float]:
    """(distance ahead along d, perpendicular offset) of target from origin, inches."""
    v = sub(target, origin)
    t = float(v[0] * d[0] + v[1] * d[1] + v[2] * d[2]) / length(d)
    return t, math.sqrt(max(0.0, float(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) - t * t))


def angle_deg(u: Point, w: Point) -> float:
    """Included turn angle between two directions, degrees."""
    dot = float(u[0] * w[0] + u[1] * w[1] + u[2] * w[2]) / (length(u) * length(w))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def seg_dist(p: Point, a: Point, b: Point) -> float:
    """Distance from point p to segment ab (float, for checks only)."""
    ab, ap = sub(b, a), sub(p, a)
    L2 = float(ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2)
    if L2 == 0:
        return length(ap)
    t = max(0.0, min(1.0, float(ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / L2))
    return math.sqrt(sum((float(ap[i]) - t * float(ab[i])) ** 2 for i in range(3)))


# --------------------------------------------------------------------------- profiles

class Profile:
    """Elevation profile along one plan axis: interpolate EL between stated anchors.

    Interpolating between the drawing's own stated elevations lands every intermediate
    station on the drawing's numbers by construction, where chaining slope x length
    accumulates one rounding per segment.
    """

    def __init__(self, along: str, points: Sequence[Tuple[F, F]]):
        if along not in ("E", "N"):
            raise PCFError("profile 'along' must be E or N")
        if len(points) < 2:
            raise PCFError("a profile needs at least two (station, EL) anchors")
        self.idx = 0 if along == "E" else 1
        self.pts = sorted(points)
        for (s1, _), (s2, _) in zip(self.pts, self.pts[1:]):
            if s1 == s2:
                raise PCFError("duplicate profile station")

    def el(self, station: F) -> F:
        lo, hi = self.pts[0][0], self.pts[-1][0]
        if not lo <= station <= hi:
            raise PCFError(f"station {fmt_in(station)} outside profile {fmt_in(lo)}..{fmt_in(hi)}")
        for (s1, z1), (s2, z2) in zip(self.pts, self.pts[1:]):
            if s1 <= station <= s2:
                return z1 + (station - s1) / (s2 - s1) * (z2 - z1)
        raise AssertionError("unreachable")


# --------------------------------------------------------------------------- writer

class PCF:
    """Accumulates PCF records. Coordinates are written in mm (default) or inches."""

    def __init__(self, axes: str = "Z-up", coords: str = "MM", safe: bool = True,
                 weight_units: str = "KGS"):
        if axes not in AXES:
            raise PCFError(f"axes must be one of {sorted(AXES)}")
        if coords not in ("MM", "INCH"):
            raise PCFError("coords must be MM or INCH")
        self.axes, self.coords, self.safe, self.weight_units = axes, coords, safe, weight_units
        self.records: List[Tuple[str, List[str]]] = []
        self.header: List[str] = []
        self.census: Dict[str, int] = {}

    # ---- formatting
    def c(self, v: F) -> str:
        return f"{float(v * MM_PER_IN if self.coords == 'MM' else v):.4f}"

    def pt(self, p: Point, bore: Optional[F] = None) -> str:
        x, y, z = AXES[self.axes][1](p)
        s = f"{self.c(x)}  {self.c(y)}  {self.c(z)}"
        if bore is not None:
            s += f"  {float(bore):.4f}"
        return s

    def set_header(self, reference: str, attributes: Sequence[Tuple[str, str]] = ()):
        h = ["ISOGEN-FILES            ISOGEN.FLS",
             "UNITS-BORE              INCH",
             f"UNITS-CO-ORDS           {self.coords}",
             f"UNITS-WEIGHT            {self.weight_units}",
             "UNITS-BOLT-DIA          INCH",
             "UNITS-BOLT-LENGTH       INCH",
             f"PIPELINE-REFERENCE      {reference}",
             f"    ATTRIBUTE1  COORDS {self.coords} - {AXES[self.axes][0]}"]
        for k, v in attributes:
            h.append(f"    {k}  {v}")
        self.header = h

    def _rec(self, logical: str, kind: str, attrs: List[str]):
        self.census[logical] = self.census.get(logical, 0) + 1
        self.records.append((kind, attrs))

    @staticmethod
    def _common(code: Optional[str], desc: Optional[str], kind: str) -> List[str]:
        return [f"ITEM-CODE   {code or 'PCF-' + kind}",
                f"ITEM-DESCRIPTION   {(desc or kind).upper()}"]

    # ---- two-ended inline components
    def inline(self, logical: str, p1: Point, p2: Point, bore: F, bore2: Optional[F] = None,
               desc: Optional[str] = None, code: Optional[str] = None, skey: Optional[str] = None,
               weight: Optional[F] = None, extra: Sequence[str] = ()):
        """logical: PIPE FLANGE FLANGE-BLIND GASKET VALVE CAP MISC-COMPONENT COUPLING
        REDUCER-CONCENTRIC REDUCER-ECCENTRIC. Mapped onto SAFE_RECORDS when safe."""
        if p1 == p2:
            raise PCFError(f"zero-length {logical} ({desc or ''}) - fix the walk, do not emit it")
        kind = logical
        extra = list(extra)
        if self.safe:
            kind = {"FLANGE-BLIND": "FLANGE", "CAP": "PIPE", "MISC-COMPONENT": "VALVE",
                    "COUPLING": "PIPE", "REDUCER-ECCENTRIC": "REDUCER-CONCENTRIC"}.get(logical, logical)
            extra = [e for e in extra if not e.startswith("FLAT-DIRECTION")]
        a = [f"END-POINT    {self.pt(p1, bore)}",
             f"END-POINT    {self.pt(p2, bore2 if bore2 is not None else bore)}"]
        a += self._common(code, desc, logical)
        if skey and kind != "PIPE":
            a.append(f"SKEY  {skey}")
        a += extra
        if weight is not None:
            a.append(f"WEIGHT  {float(weight):.2f}")
        self._rec(logical, kind, a)

    def elbow(self, t1: Point, t2: Point, corner: Point, bore: F, angle: float, radius: F,
              desc=None, code=None, skey: Optional[str] = "ELBW", bend: bool = False):
        a = [f"END-POINT    {self.pt(t1, bore)}",
             f"END-POINT    {self.pt(t2, bore)}",
             f"CENTRE-POINT     {self.pt(corner)}"]
        kind = "BEND" if bend else "ELBOW"
        a += self._common(code, desc, kind)
        if skey:
            a.append(f"SKEY  {skey}")
        a.append(f"ANGLE  {angle * 100:.4f}")           # centidegrees: 90 deg -> 9000.0000
        if not self.safe:
            a.append(f"BEND-RADIUS  {self.c(radius)}")   # derivable from corner + tangents
        self._rec(kind, kind, a)

    def tee(self, p1: Point, p2: Point, bore: F, bp: Point, bbore: F, desc=None, code=None,
            skey: Optional[str] = "TEBW"):
        a = [f"END-POINT    {self.pt(p1, bore)}",
             f"END-POINT    {self.pt(p2, bore)}",
             f"BRANCH1-POINT   {self.pt(bp, bbore)}"]   # no CENTRE-POINT: import-proven shape
        a += self._common(code, desc, "TEE")
        if skey:
            a.append(f"SKEY  {skey}")
        self._rec("TEE", "TEE", a)

    def olet(self, centre: Point, bp: Point, bbore: F, desc=None, code=None,
             skey: Optional[str] = "WTBW"):
        a = [f"CENTRE-POINT   {self.pt(centre)}",
             f"BRANCH1-POINT   {self.pt(bp, bbore)}"]
        a += self._common(code, desc, "OLET")
        if skey:
            a.append(f"SKEY  {skey}")
        self._rec("OLET", "OLET", a)

    def support(self, at: Point, bore: F, name: str, skey: str = "01HG",
                direction: str = "UP", desc=None, code=None):
        # Attribute order follows the CAESAR II example PCFs: CO-ORDS, SUPPORT-DIRECTION,
        # SKEY, ITEM-CODE, ITEM-DESCRIPTION, NAME.
        a = [f"CO-ORDS    {self.pt(at, bore)}",
             f"SUPPORT-DIRECTION  {direction}",
             f"SKEY  {skey}"]
        a += self._common(code, desc, "SUPPORT")
        a.append(f"NAME  {name}")
        self._rec("SUPPORT", "SUPPORT", a)

    # ---- output
    def text(self) -> str:
        out = list(self.header)
        for kind, attrs in self.records:
            out.append(kind)
            out += ["    " + x for x in attrs]
        return "\r\n".join(out) + "\r\n"   # CRLF: the CAESAR II importer is a Windows tool

    def write(self, path: str):
        with open(path, "w", encoding="ascii", newline="") as fh:
            fh.write(self.text())


def tangent(radius: F, angle: float) -> F:
    """Corner-to-tangent distance T = R tan(theta/2), snapped to 1/10000 in."""
    if not 0 < angle < 180:
        raise PCFError(f"bend angle {angle:.2f} deg out of range")
    return frac_round(float(radius) * math.tan(math.radians(angle) / 2))
