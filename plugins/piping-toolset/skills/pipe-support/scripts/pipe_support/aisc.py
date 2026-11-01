"""AISC 360-22 member design - stdlib Python port of the PiperSTR engine.

Faithful port of three modules of the pipingtoolset.com PiperSTR engine (structural):

  * aisc-section.ts  - section model, Table B4.1 classification, Chapter B3 factors
  * aisc-strength.ts - nominal strengths, Chapters D, E, F, G (+ Cb, F1-1)
  * aisc-member.ts   - the member check, plus the two deflection helpers

Sections, materials and demands are plain dicts with the TypeScript camelCase keys; the
result is the same result dict the TypeScript engine returns, so JSON equality
with a pipingtoolset.com PiperSTR run is possible. Units: in, in^2, in^3, in^4, kip, ksi,
kip*in.

Data boundary (same as the TypeScript engine): the EQUATIONS live here; section
property VALUES arrive as inputs - from data/aisc_shapes.json, an index whose
``parts`` are family-group files under data/aisc_shapes/ (AISC's free Shapes Database
v16.0 plus computed L/HSS/PIPE rows; each part stays under 256 KiB so plugin
directories inspect every row) - or user-entered.

JavaScript semantics are mirrored on purpose: ``??`` defaults only replace None,
``x || y`` / ``!x`` treat 0 as falsy, Math.sqrt of a negative is NaN, division by zero is
Infinity/NaN, and numbers embedded in strings print the way a JS template literal does.

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import json
import math
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

try:  # package import (scripts/ on sys.path) and flat import both work
    from .common import InputError, need, result, round_half_up, verdict
except ImportError:  # pragma: no cover
    from common import InputError, need, result, round_half_up, verdict  # type: ignore

MODULE = "structural.aisc-member"

# --------------------------------------------------------------------------- #
# JS-semantics helpers
# --------------------------------------------------------------------------- #

_INF = float("inf")
_NAN = float("nan")


def _t(x: Any) -> bool:
    """JavaScript truthiness for numbers / undefined."""
    return not (x is None or x == 0 or (isinstance(x, float) and math.isnan(x)))


def _n(x: Any, default: Any) -> Any:
    """``x ?? default``."""
    return default if x is None else x


def _sq(x: float) -> float:
    """Math.sqrt: NaN for negatives."""
    if x != x:
        return _NAN
    return math.sqrt(x) if x >= 0 else _NAN


def _div(a: float, b: float) -> float:
    """IEEE division as JavaScript does it (no ZeroDivisionError)."""
    try:
        return a / b
    except ZeroDivisionError:
        if a != a or a == 0:
            return _NAN
        neg = (a < 0) != (math.copysign(1.0, b) < 0)
        return -_INF if neg else _INF


def _pow(a: float, b: float) -> float:
    """Math.pow."""
    try:
        return math.pow(a, b)
    except OverflowError:
        return _INF
    except ValueError:
        return _NAN


def _min(*xs: float) -> float:
    """Math.min (NaN propagates)."""
    if any(x != x for x in xs):
        return _NAN
    return min(xs)


def _max(*xs: float) -> float:
    """Math.max (NaN propagates)."""
    if any(x != x for x in xs):
        return _NAN
    return max(xs)


def _js_num(x: Any) -> str:
    """Format a number the way a JavaScript template literal does (6.0 -> '6')."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    x = float(x)
    if x != x:
        return "NaN"
    if x in (_INF, -_INF):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    tup = Decimal(repr(abs(x))).as_tuple()
    raw = "".join(str(d) for d in tup.digits)
    k = len(raw) + tup.exponent  # JS's n: decimal point position relative to the digit string
    digits = raw.rstrip("0")
    n = len(digits)
    if n <= k <= 21:
        return sign + digits + "0" * (k - n)
    if 0 < k <= 21:
        return sign + digits[:k] + "." + digits[k:]
    if -6 < k <= 0:
        return sign + "0." + "0" * (-k) + digits
    e = k - 1
    mant = digits[0] + ("." + digits[1:] if n > 1 else "")
    return f"{sign}{mant}e{'+' if e >= 0 else '-'}{abs(e)}"


def _reduce_min(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """results.reduce((a, b) => (a.value <= b.value ? a : b))"""
    acc = rows[0]
    for b in rows[1:]:
        acc = acc if acc["value"] <= b["value"] else b
    return acc


# --------------------------------------------------------------------------- #
# aisc-section.ts
# --------------------------------------------------------------------------- #

#: Chapter B3 resistance factors.
PHI = {
    "tensionYield": 0.90,
    "tensionRupture": 0.75,
    "compression": 0.90,
    "flexure": 0.90,
    "shear": 0.90,
    "shearRolled": 1.00,  # G2.1(a)
}

#: Chapter B3 safety factors.
OMEGA = {
    "tensionYield": 1.67,
    "tensionRupture": 2.00,
    "compression": 1.67,
    "flexure": 1.67,
    "shear": 1.67,
    "shearRolled": 1.50,
}

DEFAULT_E = 29000
DEFAULT_G = 11200

#: AISC D1 / E2 recommended slenderness limits (advisory).
SLENDERNESS_LIMIT = {"tension": 300, "compression": 200}


def design(nominal: float, method: str, phi: float, omega: float) -> float:
    """Apply the method's factor to a nominal strength (LRFD: phi*Rn, otherwise Rn/omega)."""
    return phi * nominal if method == "LRFD" else nominal / omega


def kc_factor(hOverTw: float) -> float:
    """kc = 4/sqrt(h/tw) bounded to [0.35, 0.76] (Table B4.1b note; F3-2 for every I-shape)."""
    kc = _div(4, _sq(hOverTw))
    return _min(0.76, _max(0.35, kc))


def flange_slenderness(s: Dict[str, Any]) -> float:
    """Flange slenderness b/t of the compression element, per family."""
    if s.get("bf2tf") is not None:
        return s["bf2tf"]
    kind = s.get("kind")
    bf, tf, tw, d = s.get("bf"), s.get("tf"), s.get("tw"), s.get("d")
    if kind in ("I", "C", "T"):
        if not _t(bf) or not _t(tf):
            return 0
        return bf / tf if kind == "C" else bf / (2 * tf)
    if kind == "L":
        if not _t(tw):
            return 0
        return _max(d, _n(bf, d)) / tw
    if kind == "HSS-RECT":
        if not _t(bf) or not _t(tw):
            return 0
        return (bf - 3 * tw) / tw
    if kind == "HSS-ROUND":
        if not _t(tw):
            return 0
        return d / tw
    raise InputError(f"unsupported section kind: {kind}")


def web_slenderness(s: Dict[str, Any]) -> float:
    """Web slenderness h/tw of the section."""
    if s.get("htw") is not None:
        return s["htw"]
    kind = s.get("kind")
    tw, tf, d, bf = s.get("tw"), s.get("tf"), s.get("d"), s.get("bf")
    if kind in ("I", "C"):
        if not _t(tw) or not _t(tf):
            return 0
        k = _n(s.get("kdes"), tf)
        return (d - 2 * k) / tw
    if kind == "T":
        return d / tw if _t(tw) else 0
    if kind == "L":
        return _min(d, _n(bf, d)) / tw if _t(tw) else 0
    if kind == "HSS-RECT":
        return (d - 3 * tw) / tw if _t(tw) else 0
    if kind == "HSS-ROUND":
        return d / tw if _t(tw) else 0
    raise InputError(f"unsupported section kind: {kind}")


def _classify(lam: float, lam_p: float, lam_r: float) -> str:
    if lam <= lam_p:
        return "compact"
    if lam <= lam_r:
        return "noncompact"
    return "slender"


def classify_section(s: Dict[str, Any], m: Dict[str, Any]) -> Dict[str, Any]:
    """Table B4.1a / B4.1b classification. Returns {flange, web, flexure, axial}."""
    E = _n(m.get("E"), DEFAULT_E)
    Fy = m["Fy"]
    sq = _sq(E / Fy)
    lamF = flange_slenderness(s)
    lamW = web_slenderness(s)
    kind = s.get("kind")

    if kind in ("I", "C"):
        built = _t(s.get("builtUp"))
        kc = kc_factor(lamW if _t(lamW) else 1) if built else 1
        FL = 0.7 * Fy  # B4.1b case 11, built-up
        fP = 0.38 * sq
        fR = 0.95 * _sq((kc * E) / FL) if built else 1.0 * sq
        fRax = 0.64 * _sq((kc * E) / Fy) if built else 0.56 * sq
        wP = 3.76 * sq
        wR = 5.70 * sq
        wRax = 1.49 * sq
    elif kind == "T":
        fP = 0.38 * sq
        fR = 1.0 * sq
        fRax = 0.56 * sq
        wP = 0.84 * sq
        wR = 1.52 * sq
        wRax = 0.75 * sq
    elif kind == "L":
        fP = 0.54 * sq
        fR = 0.91 * sq
        fRax = 0.45 * sq
        wP, wR, wRax = fP, fR, fRax
    elif kind == "HSS-RECT":
        fP = 1.12 * sq
        fR = 1.40 * sq
        fRax = 1.40 * sq
        wP = 2.42 * sq
        wR = 5.70 * sq
        wRax = 1.40 * sq
    elif kind == "HSS-ROUND":
        fP = 0.07 * (E / Fy)
        fR = 0.31 * (E / Fy)
        fRax = 0.11 * (E / Fy)
        wP, wR, wRax = fP, fR, fRax
    else:
        raise InputError(f"unsupported section kind: {kind}")

    flange = {
        "lambda": lamF, "lambdaP": fP, "lambdaR": fR, "lambdaRAxial": fRax,
        "flex": _classify(lamF, fP, fR),
        "axial": "nonslender" if lamF <= fRax else "slender",
    }
    web = {
        "lambda": lamW, "lambdaP": wP, "lambdaR": wR, "lambdaRAxial": wRax,
        "flex": _classify(lamW, wP, wR),
        "axial": "nonslender" if lamW <= wRax else "slender",
    }
    order = ["compact", "noncompact", "slender"]
    flexure = order[max(order.index(flange["flex"]), order.index(web["flex"]))]
    axial = "slender" if flange["axial"] == "slender" or web["axial"] == "slender" else "nonslender"
    return {"flange": flange, "web": web, "flexure": flexure, "axial": axial}


_KIND = {
    "W": "I", "M": "I", "S": "I", "HP": "I", "B": "I", "LWF": "I", "JR": "I", "BWF": "I",
    "BLB": "I", "BJ": "I",
    "C": "C", "MC": "C",
    "WT": "T",
    "L": "L",
    "HSS-RECT": "HSS-RECT", "HSS-SQ": "HSS-RECT",
    "HSS-ROUND": "HSS-ROUND", "PIPE": "HSS-ROUND",
}

_SECTION_KEYS = (
    "A", "bf", "tw", "tf", "kdes", "bf2tf", "htw",
    "Ix", "Zx", "Sx", "rx", "Iy", "Zy", "Sy", "ry",
    "J", "Cw", "rts", "ho", "ro", "H",
    "Iz", "Iw", "Sz", "Sw", "rz", "rw", "alpha", "C",
)
# Shapes-database columns renamed on the section: centroid x / y -> xbar / ybar.
_SECTION_RENAMES = (("x", "xbar"), ("y", "ybar"))


def section_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build a section dict from an aisc_shapes.json row (absent fields stay absent)."""
    kind = _KIND.get(row.get("family"))
    if not kind:
        raise InputError(f"unsupported shape family: {row.get('family')}")
    out: Dict[str, Any] = {"label": row["label"], "kind": kind, "d": _n(row.get("d"), 0)}
    for k in _SECTION_KEYS:
        if row.get(k) is not None:
            out[k] = row[k]
    for src, dst in _SECTION_RENAMES:
        if row.get(src) is not None:
            out[dst] = row[src]
    return out


def angle_geometry(s: Dict[str, Any]) -> Dict[str, Any]:
    """Principal-axis geometry of a single angle from its legs and thickness (E4-4, E5, F10).

    Frame: heel at the origin, LONG leg along +y (x in [0, t]), SHORT leg along +x (y in [0, t])
    - the shapes-database orientation. The section is the sharp-cornered two-rectangle
    idealisation, so this is geometry, not table data; tabulated Iw, Iz, Sw, Sz, rw, rz, x-bar
    and y-bar are preferred where the section carries them. The shear centre is the leg
    mid-line intersection (t/2, t/2); beta_w (F10-4) is integrated numerically and returned as
    a magnitude.
    """
    t = _n(s.get("tw"), 0)
    d = s["d"]
    bl = _max(d, _n(s.get("bf"), d))
    bs = _min(d, _n(s.get("bf"), d))
    if t <= 0 or bl <= 0 or bs <= 0:
        raise InputError("angleGeometry: leg widths and thickness must be positive")
    rects = [r for r in ((0, t, 0, bl), (t, bs, 0, t)) if r[1] > r[0] and r[3] > r[2]]
    A = Sx1 = Sy1 = 0.0
    for x0, x1, y0, y1 in rects:
        a = (x1 - x0) * (y1 - y0)
        A += a
        Sx1 += (a * (x0 + x1)) / 2
        Sy1 += (a * (y0 + y1)) / 2
    xg, yg = Sx1 / A, Sy1 / A
    Ix = Iy = Ixy = 0.0
    for x0, x1, y0, y1 in rects:
        b, h = x1 - x0, y1 - y0
        a = b * h
        cx, cy = (x0 + x1) / 2 - xg, (y0 + y1) / 2 - yg
        Ix += (b * h ** 3) / 12 + a * cy * cy
        Iy += (h * b ** 3) / 12 + a * cx * cx
        Ixy += a * cx * cy
    theta = 0.5 * math.atan2(-2 * Ixy, Ix - Iy)
    c, sn = math.cos(theta), math.sin(theta)

    def to_w(x, y):
        return x * c + y * sn

    def to_z(x, y):
        return -x * sn + y * c

    xbar = _n(s.get("xbar"), xg)
    ybar = _n(s.get("ybar"), yg)
    wo = to_w(t / 2 - xbar, t / 2 - ybar)
    zo = to_z(t / 2 - xbar, t / 2 - ybar)

    IwG = IzG = wMax = zMax = betaInt = 0.0
    N = 200
    for x0, x1, y0, y1 in rects:
        alongX = x1 - x0 > y1 - y0
        nx, ny = (N, 8) if alongX else (8, N)
        hx, hy = (x1 - x0) / nx, (y1 - y0) / ny
        dA = hx * hy
        for i in range(nx):
            for j in range(ny):
                x = x0 + (i + 0.5) * hx - xg
                y = y0 + (j + 0.5) * hy - yg
                w, z = to_w(x, y), to_z(x, y)
                IwG += z * z * dA
                IzG += w * w * dA
                betaInt += z * (w * w + z * z) * dA
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            wMax = _max(wMax, abs(to_w(x - xg, y - yg)))
            zMax = _max(zMax, abs(to_z(x - xg, y - yg)))
    Iw = _n(s.get("Iw"), IwG)
    Iz = _n(s.get("Iz"), IzG)
    zoG = to_z(t / 2 - xg, t / 2 - yg)
    betaW = 0 if abs(bl - bs) < 1e-9 else abs(betaInt / IwG - 2 * zoG)
    return {
        "t": t, "bl": bl, "bs": bs, "xbar": xbar, "ybar": ybar, "theta": theta,
        "Iw": Iw, "Iz": Iz,
        # Bending about w stresses the fibres farthest along z, and vice versa.
        "Sw": _n(s.get("Sw"), IwG / zMax),
        "Sz": _n(s.get("Sz"), IzG / wMax),
        "rw": _n(s.get("rw"), _sq(Iw / s["A"])),
        "rz": _n(s.get("rz"), _sq(Iz / s["A"])),
        "wo": wo, "zo": zo, "betaW": betaW,
    }


# --------------------------------------------------------------------------- #
# Shape lookup (data/aisc_shapes.json index + data/aisc_shapes/*.json parts; port of
# code-data-service findShape etc.)
# --------------------------------------------------------------------------- #

_SHAPES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aisc_shapes.json")
_SHAPES_CACHE: Dict[str, Any] = {}


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", "", label).upper()


def load_shapes() -> List[Dict[str, Any]]:
    """All rows of the vendored AISC shapes dataset (cached).

    ``aisc_shapes.json`` is an index: metadata plus ``parts``, the family-group files
    under ``data/aisc_shapes/`` in the original row order. Concatenating them in that
    order reproduces the single-file dataset row for row (``row_count`` is checked).
    A single-file dataset with ``rows`` at the top level is still accepted.
    """
    if "rows" not in _SHAPES_CACHE:
        with open(_SHAPES_PATH, "r", encoding="utf-8") as fh:
            index = json.load(fh)
        rows: List[Dict[str, Any]] = list(index.get("rows", []))
        base = os.path.dirname(_SHAPES_PATH)
        for rel in index.get("parts", []):
            with open(os.path.join(base, *rel.split("/")), "r", encoding="utf-8") as fh:
                rows.extend(json.load(fh)["rows"])
        expected = index.get("row_count")
        if expected is not None and expected != len(rows):
            raise InputError(f"aisc_shapes.json lists {expected} rows but its parts hold {len(rows)}")
        _SHAPES_CACHE["rows"] = rows
        _SHAPES_CACHE["by_label"] = {_norm_label(r["label"]): r for r in rows}  # last wins, like Map
    return _SHAPES_CACHE["rows"]


def find_shape(label: str) -> Optional[Dict[str, Any]]:
    """Row for a label (upper-cased, whitespace stripped), or None."""
    load_shapes()
    return _SHAPES_CACHE["by_label"].get(_norm_label(label))


def shapes_by_family(family: str, current_only: bool = True) -> List[Dict[str, Any]]:
    """Rows of one family; ``current_only`` drops rows with current == False."""
    return [r for r in load_shapes()
            if r.get("family") == family and (not current_only or r.get("current") is not False)]


# --------------------------------------------------------------------------- #
# aisc-strength.ts
# --------------------------------------------------------------------------- #

def _nominal(value: float, clause: str, detail: Optional[Dict[str, float]] = None,
             warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": value, "clause": clause}
    if detail is not None:
        out["detail"] = detail
    if warnings is not None:
        out["warnings"] = warnings
    return out


def _to_fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed: exact binary value, ties away from zero."""
    if x != x:
        return "NaN"
    if x in (_INF, -_INF):
        return "Infinity" if x > 0 else "-Infinity"
    q = Decimal(1).scaleb(-digits)
    v = Decimal(abs(x)).quantize(q, rounding=ROUND_HALF_UP)
    s = f"{v:.{digits}f}"
    return ("-" + s) if x < 0 and v != 0 else s


_PI2 = math.pi ** 2


# ----- Chapter D - tension -------------------------------------------------- #

def tension_strength(s: Dict[str, Any], m: Dict[str, Any],
                     opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """D2-1 yielding and D2-2/D3-1 rupture. Returns {yielding, rupture, governing}.

    U defaults to 1.0 except for single angles (Table D3.1): the larger of Case 8 (0.80 with
    four or more fasteners per line, 0.60 with three) and Case 2 (1 - xbar/l) when its data is
    given, never below the D3 connected-element minimum; with no connection data U is that D3
    floor with the SHORTER leg connected, and a warning says so.
    """
    opts = opts or {}
    A = s["A"]
    An = _n(opts.get("An"), A)
    warnings: List[str] = []
    basis = ""
    if opts.get("U") is not None:
        U = opts["U"]
        basis = "U given"
    elif s.get("kind") == "L":
        t = _n(s.get("tw"), 0)
        bs = _min(s["d"], _n(s.get("bf"), s["d"]))
        floor = _min(1, (bs * t) / A) if t > 0 else 0  # D3 minimum
        n = opts.get("nBoltsPerLine")
        U8 = None if n is None else (0.8 if n >= 4 else (0.6 if n == 3 else None))
        l, xb = opts.get("connectionLength"), opts.get("xbar")
        U2 = _max(0, 1 - xb / l) if (xb is not None and l is not None and l > 0) else None
        known = [u for u in (U8, U2) if u is not None]
        if known:
            Ut = _max(*known)
            U = _max(Ut, floor)
            basis = (f"Table D3.1 Case 8 ({_js_num(n)} fasteners per line)" if Ut == U8
                     else "Table D3.1 Case 2, U = 1 - x̄/l")
            if U > Ut:
                basis += "; raised to the D3 connected-element minimum"
        else:
            U = floor
            basis = "Table D3.1 Case 2 lower bound = D3 connected-element minimum (shorter leg)"
            warnings.append(
                f"Single-angle shear lag: no connection data, so U = {_to_fixed(floor, 3)} — Table D3.1 Case 2 at its D3 "
                "lower bound, the shorter leg's area over Ag (the most conservative U the Specification permits). "
                "Supply U, or the fasteners per line (Case 8: 0.80 for four or more, 0.60 for three) or x̄ and the "
                "connection length l (Case 2)."
            )
    else:
        U = 1.0
    Ae = An * U
    yielding = _nominal(m["Fy"] * A, "D2-1 (gross-section yielding)", {"Ag": A})
    rupture = _nominal(m["Fu"] * Ae, f"D2-2 (net-section rupture{('; ' + basis) if basis else ''})",
                       {"An": An, "U": U, "Ae": Ae}, warnings)
    governing = yielding if yielding["value"] <= rupture["value"] else rupture
    return {"yielding": yielding, "rupture": rupture, "governing": governing}


# ----- Chapter E - compression ---------------------------------------------- #

def _critical_stress(Fe: float, Fy: float, E: float = DEFAULT_E):
    """E3-2 / E3-3 from an elastic buckling stress (4.71 sqrt(E/Fy) <=> Fy/Fe <= 2.25)."""
    inelastic = _div(Fy, Fe) <= 2.25
    Fn = _pow(0.658, _div(Fy, Fe)) * Fy if inelastic else 0.877 * Fe
    return Fn, inelastic


# Table E7.1 rows: (a) stiffened except rect-HSS walls, (b) rect-HSS walls, (c) all other.
_E71 = {"a": (0.18, 1.31), "b": (0.20, 1.38), "c": (0.22, 1.49)}


def _effective_area(s, m, cls, Fn):
    """E7 effective area: lambda_r is the AXIAL limit of Table B4.1a, c1/c2 from Table E7.1."""
    E = _n(m.get("E"), DEFAULT_E)
    Fy = m["Fy"]
    A = s["A"]
    if cls["axial"] == "nonslender":
        return A, None

    kind = s.get("kind")
    if kind == "HSS-ROUND":
        Dt = _div(s["d"], _n(s.get("tw"), 1))
        if Dt <= 0.11 * (E / Fy):
            return A, None  # E7-6
        if Dt <= 0.45 * (E / Fy):
            return (0.038 * (E / Fy) / Dt + 2 / 3) * A, "E7-7"
        return A, "D/t exceeds 0.45E/Fy — outside Spec E7 applicability"

    removed = [0.0]

    def reduce(lam, lamR, b, t, n, row):
        if lam <= 0 or b <= 0 or t <= 0:
            return
        if lam <= lamR * _sq(_div(Fy, Fn)):
            return  # E7-2: be = b
        c1, c2 = row
        Fel = _pow(c2 * (lamR / lam), 2) * Fy  # E7-5
        be = b * (1 - c1 * _sq(_div(Fel, Fn))) * _sq(_div(Fel, Fn))  # E7-3
        removed[0] += n * _max(0, b - _min(b, be)) * t

    fl, wb = cls["flange"], cls["web"]
    tw, tf, bf = _n(s.get("tw"), 0), _n(s.get("tf"), 0), _n(s.get("bf"), 0)
    d = s["d"]
    if kind == "I":
        reduce(fl["lambda"], fl["lambdaRAxial"], bf / 2, tf, 4, _E71["c"])  # four flange outstands
        reduce(wb["lambda"], wb["lambdaRAxial"], wb["lambda"] * tw, tw, 1, _E71["a"])  # web, b = h
    elif kind == "C":
        reduce(fl["lambda"], fl["lambdaRAxial"], bf, tf, 2, _E71["c"])
        reduce(wb["lambda"], wb["lambdaRAxial"], wb["lambda"] * tw, tw, 1, _E71["a"])
    elif kind == "T":
        reduce(fl["lambda"], fl["lambdaRAxial"], bf / 2, tf, 2, _E71["c"])  # two flange outstands
        reduce(wb["lambda"], wb["lambdaRAxial"], d, tw, 1, _E71["c"])  # stem, b = d
    elif kind == "L":
        reduce(fl["lambda"], fl["lambdaRAxial"], _max(d, bf if _t(bf) else d), tw, 1, _E71["c"])  # long leg
        reduce(wb["lambda"], wb["lambdaRAxial"], _min(d, bf if _t(bf) else d), tw, 1, _E71["c"])  # short leg
    elif kind == "HSS-RECT":
        reduce(fl["lambda"], fl["lambdaRAxial"], fl["lambda"] * tw, tw, 2, _E71["b"])
        reduce(wb["lambda"], wb["lambdaRAxial"], wb["lambda"] * tw, tw, 2, _E71["b"])

    return _max(0.1 * A, A - removed[0]), ("E7 effective area" if removed[0] > 0 else None)


def _polar_radius(s, warnings):
    """ro_bar^2 and H for E4-3 (E4-8, E4-9), from ro / H, shear-centre data, or H = 1 with a warning."""
    A = s["A"]
    base = (s["Ix"] + _n(s.get("Iy"), s["Ix"])) / A
    ro, H = s.get("ro"), s.get("H")
    if ro is not None and ro > 0:
        ro2 = ro * ro
        return ro2, _n(H, _min(1, base / ro2))
    if H is not None and 0 < H <= 1:
        return base / H, H
    xo, yo = s.get("xo"), s.get("yo")
    if xo is None and yo is None and s.get("kind") == "T" and s.get("ybar") is not None and _n(s.get("tf"), 0) > 0:
        xo = 0
        yo = s["ybar"] - _n(s.get("tf"), 0) / 2
    if xo is not None or yo is not None:
        o2 = _n(xo, 0) ** 2 + _n(yo, 0) ** 2
        ro2 = o2 + base
        return ro2, 1 - o2 / ro2
    warnings.append(
        "E4-3: no shear-centre data (ro, H, or xo/yo) for this section — ro_bar² = (Ix+Iy)/Ag and H = 1 were used, "
        "which ignores the shear-centre offset and OVERSTATES the flexural-torsional buckling stress. Supply ro and H (or xo, yo)."
    )
    return base, 1


def _e44_lowest_root(Fex, Fey, Fez, xo, yo, ro2):
    """Lowest root of the E4-4 cubic by bisection on (0, min Fe]."""
    kx, ky = (xo * xo) / ro2, (yo * yo) / ro2

    def f(F):
        return (F - Fex) * (F - Fey) * (F - Fez) - F * F * (F - Fey) * kx - F * F * (F - Fex) * ky

    lo, hi = 0.0, _min(Fex, Fey, Fez)
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def compression_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any],
                         L: Dict[str, Any]) -> Dict[str, Any]:
    """E3 flexural buckling (each axis), E4 torsional / flexural-torsional, E7 slender.

    L = {"Lcx": in, "Lcy": in, "Lcz": in (optional, defaults to Lcy), "angleE5": optional}.
    Single angles go through E5 (_compression_angle).
    """
    if s.get("kind") == "L":
        return _compression_angle(s, m, cls, L)
    E = _n(m.get("E"), DEFAULT_E)
    G = _n(m.get("G"), DEFAULT_G)
    Fy = m["Fy"]
    A = s["A"]
    Lcx, Lcy = L["Lcx"], L["Lcy"]
    Lcz = _n(L.get("Lcz"), Lcy)
    kind = s.get("kind")
    warnings: List[str] = []

    rx = _n(s.get("rx"), _sq(s["Ix"] / A))
    ry = _n(s.get("ry"), _sq(s["Iy"] / A) if _t(s.get("Iy")) else rx)
    cands: List[Dict[str, Any]] = []

    def add_flexural(Lc, r, axis):
        if r <= 0 or Lc <= 0:
            return
        sl = Lc / r
        cands.append({"Fe": (_PI2 * E) / (sl * sl), "clause": f"E3-4 (flexural buckling, {axis})", "slender": sl})

    add_flexural(Lcx, rx, "x-x")
    add_flexural(Lcy, ry, "y-y")

    J = _n(s.get("J"), 0)
    Cw = _n(s.get("Cw"), 0)
    Iy = _n(s.get("Iy"), s["Ix"])
    if J > 0 and Lcz > 0:
        if kind == "I":
            Fe = _div((_PI2 * E * Cw) / (Lcz * Lcz) + G * J, s["Ix"] + Iy)  # E4-2
            if math.isfinite(Fe) and Fe > 0:
                cands.append({"Fe": Fe, "clause": "E4-2 (torsional buckling)",
                              "slender": _div(Lcz, _n(s.get("rz"), ry))})
        elif kind in ("T", "C"):
            # E4-3, singly symmetric: y is the axis of symmetry for a tee, x for a channel (Fex, E4-5).
            ro2, H = _polar_radius(s, warnings)
            symX = kind == "C"
            Lsym, rsym = (Lcx, rx) if symX else (Lcy, ry)
            Fes = _div(_PI2 * E, _pow(_div(Lsym, rsym), 2))  # E4-5 / E4-6
            Fez = _div((_PI2 * E * Cw) / (Lcz * Lcz) + G * J, A * ro2)  # E4-7
            disc = 1 - _div(4 * Fes * Fez * H, _pow(Fes + Fez, 2))
            if disc >= 0:
                Fe = ((Fes + Fez) / (2 * H)) * (1 - _sq(disc))  # E4-3
                if Fe > 0:
                    cands.append({"Fe": Fe,
                                  "clause": f"E4-3 (flexural-torsional buckling, {'Fex for a channel' if symX else 'Fey'})",
                                  "slender": _div(Lsym, rsym)})

    if not cands:
        raise InputError("compressionStrength: no valid buckling mode — check r and unbraced lengths")
    gov = cands[0]
    for b in cands[1:]:
        gov = gov if gov["Fe"] <= b["Fe"] else b
    Fn, inelastic = _critical_stress(gov["Fe"], Fy, E)
    Ae, note = _effective_area(s, m, cls, Fn)

    return {
        "value": Fn * Ae,
        "clause": f"{gov['clause']}; {'E3-2 inelastic' if inelastic else 'E3-3 elastic'}"
                  f"{('; ' + note) if note else ''}",
        "detail": {
            "Fe": gov["Fe"], "Fn": Fn, "Ae": Ae,
            "slenderness": gov["slender"],
            "slendernessLimit": 4.71 * _sq(E / Fy),
        },
        "warnings": warnings,
    }


def _compression_angle(s, m, cls, L):
    """Single-angle compression: E3 (E5 effective slenderness when stated) and E4-4 FTB."""
    E = _n(m.get("E"), DEFAULT_E)
    G = _n(m.get("G"), DEFAULT_G)
    Fy = m["Fy"]
    A = s["A"]
    Lcx, Lcy = L["Lcx"], L["Lcy"]
    Lcz = _n(L.get("Lcz"), Lcy)
    warnings: List[str] = []
    g = angle_geometry(s)
    rx = _n(s.get("rx"), _sq(s["Ix"] / A))
    ry = _n(s.get("ry"), _sq(s["Iy"] / A) if _t(s.get("Iy")) else rx)
    longIsY = s["d"] >= _n(s.get("bf"), s["d"])  # shapes-database orientation: long leg along y

    flex: List[Dict[str, Any]] = []
    e5 = L.get("angleE5")
    if e5 and _t(e5.get("conditionsMet")):
        Lm = _n(e5.get("L"), _max(Lcx, Lcy))
        ratio = g["bl"] / g["bs"]
        equal = ratio < 1 + 1e-9
        if not equal and ratio >= 1.7:
            warnings.append(f"E5 condition (5) not met: long/short leg = {_to_fixed(ratio, 2)} >= 1.7, so the E5 "
                            "effective slenderness is not used.")
        else:
            # ra = radius of gyration about the geometric axis PARALLEL to the connected leg.
            connectedIsY = (e5.get("connectedLeg") == "long") == longIsY
            ra = ry if connectedIsY else rx
            Lr = Lm / ra
            short = (not equal) and e5.get("connectedLeg") == "short"
            if e5.get("truss") == "planar":
                KLr, eq = (72 + 0.75 * Lr, "E5-1") if Lr <= 80 else (32 + 1.25 * Lr, "E5-2")
                if short:
                    KLr = _max(KLr + 4 * (ratio * ratio - 1), 0.95 * Lm / g["rz"])
                    eq += ", E5(a)(2)"
            else:
                KLr, eq = (60 + 0.8 * Lr, "E5-3") if Lr <= 75 else (45 + Lr, "E5-4")
                if short:
                    KLr = _max(KLr + 6 * (ratio * ratio - 1), 0.82 * Lm / g["rz"])
                    eq += ", E5(b)(2)"
            if KLr > 200:
                warnings.append(f"E5 condition (4) not met: Lc/r = {_to_fixed(KLr, 1)} > 200, so the E5 effective "
                                "slenderness is not used.")
            else:
                flex = [{"Fe": (_PI2 * E) / (KLr * KLr),
                         "clause": f"{eq} (single-angle effective slenderness, L/ra = {_to_fixed(Lr, 1)})",
                         "slender": KLr}]
    if not flex:
        def add(Lc, r, axis):
            if r > 0 and Lc > 0:
                flex.append({"Fe": _div(_PI2 * E, _pow(Lc / r, 2)), "clause": f"E3-4 (flexural buckling, {axis})",
                             "slender": Lc / r})
        add(Lcx, rx, "x-x")
        add(Lcy, ry, "y-y")
        # Minor principal axis, over the shorter geometric unbraced length.
        add(_min(Lcx, Lcy), g["rz"], "z-z principal")
        warnings.append(
            "Single angle: E5 effective slenderness NOT applied (its conditions were not stated as met, or failed) — the axial "
            "strength is the CONCENTRIC E3 value. An angle connected through one leg is eccentrically loaded: check it for "
            "combined axial load and flexure under Chapter H (H2) with the connection eccentricity, or supply angleE5."
        )
    if not flex:
        raise InputError("compressionStrength: no valid buckling mode — check r and unbraced lengths")

    gov = flex[0]
    for b in flex[1:]:
        gov = gov if gov["Fe"] <= b["Fe"] else b
    Fn3, inel3 = _critical_stress(gov["Fe"], Fy, E)
    Ae, note = _effective_area(s, m, cls, Fn3)
    best = {
        "value": Fn3 * Ae,
        "clause": f"{gov['clause']}; {'E3-2 inelastic' if inel3 else 'E3-3 elastic'}{('; ' + note) if note else ''}",
        "detail": {"Fe": gov["Fe"], "Fn": Fn3, "Ae": Ae, "slenderness": gov["slender"],
                   "slendernessLimit": 4.71 * _sq(E / Fy)},
    }

    # E4: flexural-torsional buckling when b/t > 0.71 sqrt(E/Fy) (b = longest leg).
    J, Cw = _n(s.get("J"), 0), _n(s.get("Cw"), 0)
    if g["bl"] / g["t"] > 0.71 * _sq(E / Fy) and J > 0 and Lcz > 0:
        ro2 = g["wo"] ** 2 + g["zo"] ** 2 + (s["Ix"] + _n(s.get("Iy"), s["Ix"])) / A  # E4-9
        Lw, Lz = _max(Lcx, Lcy), _min(Lcx, Lcy)
        Few = _div(_PI2 * E, _pow(Lw / g["rw"], 2))
        Fez_ = _div(_PI2 * E, _pow(Lz / g["rz"], 2))
        Fet = _div((_PI2 * E * Cw) / (Lcz * Lcz) + G * J, A * ro2)  # E4-7
        Fe = _e44_lowest_root(Few, Fez_, Fet, g["wo"], g["zo"], ro2)  # E4-4
        Fn4, inel4 = _critical_stress(Fe, Fy, E)
        Pn = Fn4 * A  # E4-1
        if Pn < best["value"]:
            best = {
                "value": Pn,
                "clause": "E4-4 (single-angle flexural-torsional buckling, principal axes); E4-1 Pn = Fn*Ag; "
                          f"{'E3-2 inelastic' if inel4 else 'E3-3 elastic'}",
                "detail": {"Fe": Fe, "Fn": Fn4, "Ae": A, "slenderness": Lw / g["rw"],
                           "slendernessLimit": 4.71 * _sq(E / Fy), "H": 1 - (g["wo"] ** 2 + g["zo"] ** 2) / ro2},
            }
    best = dict(best)
    best["warnings"] = warnings
    return best


# ----- Chapter F - flexure --------------------------------------------------- #

def _rts_of(s):
    if _t(s.get("rts")):
        return s["rts"]
    Iy, Cw, Sx = _n(s.get("Iy"), 0), _n(s.get("Cw"), 0), _n(s.get("Sx"), 0)
    return _sq(_sq(Iy * Cw) / Sx) if Iy > 0 and Cw > 0 and Sx > 0 else 0


def _rt_of(s, cls):
    """rt for an I-shape with a rectangular compression flange (F4-11, aw per F4-12)."""
    bf, tf, tw = _n(s.get("bf"), 0), _n(s.get("tf"), 0), _n(s.get("tw"), 0)
    hc = cls["web"]["lambda"] * tw
    aw = (hc * tw) / (bf * tf) if bf > 0 and tf > 0 else 0  # F4-12
    return (bf / _sq(12 * (1 + aw / 6)) if bf > 0 else 0), aw  # F4-11


def _flexure_ic(s, m, cls, f):
    """Major-axis flexure of I-shapes and channels: F2 / F3 (compact web), F4, F5."""
    if cls["web"]["flex"] == "noncompact" and _n(s.get("Sx"), 0) > 0:
        return _flexure_f4(s, m, cls, f)
    if cls["web"]["flex"] == "slender" and _n(s.get("Sx"), 0) > 0:
        return _flexure_f5(s, m, cls, f)
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Cb = _n(f.get("Cb"), 1.0)
    Lb = f["Lb"]
    Zx, Sx, ry = _n(s.get("Zx"), 0), _n(s.get("Sx"), 0), _n(s.get("ry"), 0)
    Mp = Fy * Zx  # F2-1
    results = [_nominal(Mp, "F2-1 (yielding)", {"Mp": Mp})]

    rts = _rts_of(s)
    ho = _n(s.get("ho"), s["d"] - _n(s.get("tf"), 0))
    J = _n(s.get("J"), 0)
    c = (ho / 2) * _sq(_n(s.get("Iy"), 0) / s["Cw"]) if (s.get("kind") == "C" and _t(s.get("Cw"))) else 1.0

    if ry > 0 and rts > 0 and ho > 0 and Sx > 0:
        Lp = 1.76 * ry * _sq(E / Fy)  # F2-5
        term = (J * c) / (Sx * ho)
        Lr = 1.95 * rts * (E / (0.7 * Fy)) * _sq(term + _sq(term * term + 6.76 * _pow((0.7 * Fy) / E, 2)))  # F2-6
        if Lb <= Lp:
            results.append(_nominal(Mp, "F2-1 (Lb <= Lp, LTB does not apply)", {"Lp": Lp, "Lr": Lr, "Lb": Lb}))
        elif Lb <= Lr:
            Mn = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * ((Lb - Lp) / (Lr - Lp)))  # F2-2
            results.append(_nominal(_min(Mn, Mp), "F2-2 (inelastic LTB)", {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb}))
        else:
            sl = Lb / rts
            Fcr = ((Cb * _PI2 * E) / (sl * sl)) * _sq(1 + 0.078 * term * sl * sl)  # F2-4
            results.append(_nominal(_min(Fcr * Sx, Mp), "F2-3 (elastic LTB)",
                                    {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb, "Fcr": Fcr}))

    fl, wb = cls["flange"], cls["web"]
    if fl["flex"] != "compact" and Sx > 0:
        lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
        if fl["flex"] == "noncompact":
            Mn = Mp - (Mp - 0.7 * Fy * Sx) * ((lam - lamP) / (lamR - lamP))  # F3-1
            results.append(_nominal(Mn, "F3-1 (noncompact flange, FLB)",
                                    {"lambda": lam, "lambdaP": lamP, "lambdaR": lamR}))
        else:
            # kc = 4/sqrt(h/tw), 0.35..0.76, for EVERY doubly symmetric I-shape (not only built-up).
            kc = kc_factor(wb["lambda"] if _t(wb["lambda"]) else 1)
            Mn = (0.9 * E * kc * Sx) / (lam * lam)  # F3-2
            results.append(_nominal(Mn, "F3-2 (slender flange, FLB)", {"lambda": lam, "kc": kc}))

    return _reduce_min(results)


def _flexure_f4(s, m, cls, f):
    """F4: doubly symmetric I-shapes (channels alike) with a NONCOMPACT web; Rpc per F4-9b."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Cb = _n(f.get("Cb"), 1.0)
    Lb = f["Lb"]
    Sx, Zx, J = _n(s.get("Sx"), 0), _n(s.get("Zx"), 0), _n(s.get("J"), 0)
    ho = _n(s.get("ho"), s["d"] - _n(s.get("tf"), 0))
    Myc = Fy * Sx  # F4-4
    Mp = _min(Fy * Zx, 1.6 * Fy * Sx)
    wb = cls["web"]
    lw, lpw, lrw = wb["lambda"], wb["lambdaP"], wb["lambdaR"]
    Rpc = _min(Mp / Myc, Mp / Myc - (Mp / Myc - 1) * ((lw - lpw) / (lrw - lpw)))  # F4-9b
    RM = Rpc * Myc
    FL = 0.7 * Fy  # F4-6a
    results = [_nominal(RM, "F4-1 (compression flange yielding, Rpc F4-9b)", {"Rpc": Rpc, "Myc": Myc})]

    rt, aw = _rt_of(s, cls)
    if rt > 0 and ho > 0:
        Lp = 1.1 * rt * _sq(E / Fy)  # F4-7
        term = J / (Sx * ho)
        Lr = 1.95 * rt * (E / FL) * _sq(term + _sq(term * term + 6.76 * _pow(FL / E, 2)))  # F4-8
        if Lp < Lb <= Lr:
            Mn = Cb * (RM - (RM - FL * Sx) * ((Lb - Lp) / (Lr - Lp)))  # F4-2
            results.append(_nominal(_min(Mn, RM), "F4-2 (inelastic LTB)",
                                    {"Lp": Lp, "Lr": Lr, "rt": rt, "aw": aw, "Lb": Lb, "Cb": Cb}))
        elif Lb > Lr:
            sl = Lb / rt
            Fcr = ((Cb * _PI2 * E) / (sl * sl)) * _sq(1 + 0.078 * term * sl * sl)  # F4-5
            results.append(_nominal(_min(Fcr * Sx, RM), "F4-3 (elastic LTB)",
                                    {"Lp": Lp, "Lr": Lr, "rt": rt, "Fcr": Fcr, "Lb": Lb, "Cb": Cb}))

    fl = cls["flange"]
    if fl["flex"] != "compact":
        lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
        if fl["flex"] == "noncompact":
            Mn = RM - (RM - FL * Sx) * ((lam - lamP) / (lamR - lamP))  # F4-13
            results.append(_nominal(Mn, "F4-13 (noncompact flange, FLB)", {"lambda": lam}))
        else:
            kc = kc_factor(lw if _t(lw) else 1)
            results.append(_nominal((0.9 * E * kc * Sx) / (lam * lam), "F4-14 (slender flange, FLB)",
                                    {"lambda": lam, "kc": kc}))
    return _reduce_min(results)


def _flexure_f5(s, m, cls, f):
    """F5: I-shapes with a SLENDER web (doubly symmetric: Sxc = Sxt, F5.4 does not apply)."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Cb = _n(f.get("Cb"), 1.0)
    Lb = f["Lb"]
    Sx = _n(s.get("Sx"), 0)
    rt, aw = _rt_of(s, cls)
    awR = _min(10, aw)
    hc_tw = cls["web"]["lambda"]
    Rpg = _min(1.0, 1 - (awR / (1200 + 300 * awR)) * (hc_tw - 5.7 * _sq(E / Fy)))  # F5-6
    results = [_nominal(Rpg * Fy * Sx, "F5-1 (compression flange yielding)", {"Rpg": Rpg, "aw": awR})]

    if rt > 0:
        Lp = 1.1 * rt * _sq(E / Fy)  # F4-7
        Lr = math.pi * rt * _sq(E / (0.7 * Fy))  # F5-5
        Fcr = None
        eq = ""
        if Lp < Lb <= Lr:
            Fcr = _min(Fy, Cb * (Fy - 0.3 * Fy * ((Lb - Lp) / (Lr - Lp))))  # F5-3
            eq = "F5-3 inelastic"
        elif Lb > Lr:
            Fcr = _min(Fy, (Cb * _PI2 * E) / _pow(Lb / rt, 2))  # F5-4
            eq = "F5-4 elastic"
        if Fcr is not None:
            results.append(_nominal(Rpg * Fcr * Sx, f"F5-2 (LTB, {eq})",
                                    {"Lp": Lp, "Lr": Lr, "rt": rt, "Fcr": Fcr, "Rpg": Rpg, "Lb": Lb, "Cb": Cb}))

    fl = cls["flange"]
    if fl["flex"] != "compact":
        lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
        kc = kc_factor(hc_tw if _t(hc_tw) else 1)
        nc = fl["flex"] == "noncompact"
        Fcr = (Fy - 0.3 * Fy * ((lam - lamP) / (lamR - lamP))) if nc else (0.9 * E * kc) / (lam * lam)  # F5-8 / F5-9
        results.append(_nominal(Rpg * Fcr * Sx, f"F5-7 (FLB, {'F5-8' if nc else 'F5-9'})",
                                {"lambda": lam, "Fcr": Fcr, "kc": kc, "Rpg": Rpg}))
    return _reduce_min(results)


def _flexure_minor_ic(s, m, cls):
    """Minor-axis flexure of I-shapes, channels and tees: F6."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Zy, Sy = _n(s.get("Zy"), 0), _n(s.get("Sy"), 0)
    Mp = _min(Fy * Zy, 1.6 * Fy * Sy)  # F6-1
    fl = cls["flange"]
    if fl["flex"] == "compact":
        return _nominal(Mp, "F6-1 (yielding)", {"Mp": Mp})
    lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
    if fl["flex"] == "noncompact":
        return _nominal(Mp - (Mp - 0.7 * Fy * Sy) * ((lam - lamP) / (lamR - lamP)),
                        "F6-2 (noncompact flange)", {"lambda": lam, "lambdaP": lamP, "lambdaR": lamR})
    Fcr = (0.70 * E) / (lam * lam)  # F6-4 (0.70E in 360-22)
    return _nominal(Fcr * Sy, "F6-3 (slender flange, Fcr F6-4)", {"Fcr": Fcr, "lambda": lam})


def _flexure_hss_rect(s, m, cls, major, f):
    """Rectangular / square HSS flexure: F7, with F7.4 LTB about the major axis."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Z = _n(s.get("Zx") if major else s.get("Zy"), 0)
    S = _n(s.get("Sx") if major else s.get("Sy"), 0)
    Mp = Fy * Z  # F7-1
    results = [_nominal(Mp, "F7-1 (yielding)", {"Mp": Mp})]

    fl = cls["flange"] if major else cls["web"]
    if fl["flex"] == "noncompact":
        Mn = Mp - (Mp - Fy * S) * ((fl["lambda"] - fl["lambdaP"]) / (fl["lambdaR"] - fl["lambdaP"]))  # F7-2
        results.append(_nominal(_min(Mn, Mp), "F7-2 (noncompact flange)", {"lambda": fl["lambda"]}))
    elif fl["flex"] == "slender":
        t = _n(s.get("tw"), 0)
        b = fl["lambda"] * t
        be = _min(b, 1.92 * t * _sq(E / Fy) * (1 - (0.38 / fl["lambda"]) * _sq(E / Fy)))  # F7-4
        Se = S * (be / _max(b, 1e-9))
        results.append(_nominal(Fy * Se, "F7-3 (slender flange, effective Se)", {"be": be, "b": b}))

    wb = cls["web"] if major else cls["flange"]
    if wb["flex"] == "noncompact":
        Mn = Mp - (Mp - Fy * S) * ((wb["lambda"] - wb["lambdaP"]) / (wb["lambdaR"] - wb["lambdaP"]))  # F7-6
        results.append(_nominal(_min(Mn, Mp), "F7-6 (noncompact web)", {"lambda": wb["lambda"]}))

    # Lateral-torsional buckling, F7.4 - major-axis bending only.
    J, ry, Sx = _n(s.get("J"), 0), _n(s.get("ry"), 0), _n(s.get("Sx"), 0)
    Lb = f["Lb"]
    if major and J > 0 and ry > 0 and Sx > 0 and Mp > 0 and Lb > 0:
        Cb = _n(f.get("Cb"), 1.0)
        rJA = _sq(J * s["A"])
        Lp = (0.13 * E * ry * rJA) / Mp  # F7-10
        Lr = (2 * E * ry * rJA) / (0.7 * Fy * Sx)  # F7-11
        if Lp < Lb <= Lr:
            Mn = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * ((Lb - Lp) / (Lr - Lp)))  # F7-8
            results.append(_nominal(_min(Mn, Mp), "F7-8 (inelastic LTB)", {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb}))
        elif Lb > Lr:
            Mn = (2 * E * Cb * rJA) / (Lb / ry)  # F7-9
            results.append(_nominal(_min(Mn, Mp), "F7-9 (elastic LTB)", {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb}))
    return _reduce_min(results)


def _flexure_hss_round(s, m, cls):
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    S, Z = _n(s.get("Sx"), 0), _n(s.get("Zx"), 0)
    Dt = cls["flange"]["lambda"]
    if cls["flexure"] == "compact":
        return _nominal(Fy * Z, "F8-1 (yielding)", {"Dt": Dt})
    if cls["flexure"] == "noncompact":
        return _nominal((0.021 * E / Dt + Fy) * S, "F8-2 (noncompact wall)", {"Dt": Dt})
    Fcr = (0.33 * E) / Dt  # F8-4
    return _nominal(Fcr * S, "F8-3 (slender wall)", {"Fcr": Fcr, "Dt": Dt})


def _angle_ltb(My, Mcr):
    """F10-2 / F10-3 from My and Mcr."""
    if _div(My, Mcr) <= 1.0:
        return _min(1.5 * My, (1.92 - 1.17 * _sq(_div(My, Mcr))) * My), "F10-2"
    return (0.92 - _div(0.17 * Mcr, My)) * Mcr, "F10-3"


def _angle_llb(Fy, E, Sc, lam_d):
    """F10.3 leg local buckling with Sc and the b/t of the leg whose toe is in compression."""
    lam, lamP, lamR = lam_d["lambda"], lam_d["lambdaP"], lam_d["lambdaR"]
    if lam <= lamP:
        return None
    if lam <= lamR:
        return _nominal(Fy * Sc * (2.43 - 1.72 * lam * _sq(Fy / E)), "F10-6 (noncompact leg, LLB)",
                        {"lambda": lam, "Sc": Sc})
    Fcr = (0.71 * E) / (lam * lam)  # F10-8
    return _nominal(Fcr * Sc, "F10-7 (slender leg, LLB)", {"Fcr": Fcr, "lambda": lam, "Sc": Sc})


def _flexure_angle(s, m, cls, major, f):
    """Single-angle flexure: F10 (geometric axis with continuousLTR, F10.2(2)(i) for an equal-leg
    angle without axial compression, otherwise principal axes resolved by H2-1)."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Sgeo = _n(s.get("Sx") if major else s.get("Sy"), 0)

    if _t(f.get("continuousLTR")):
        My = Fy * Sgeo
        rs = [_nominal(1.5 * My, "F10-1 (yielding, 1.5My, geometric axis — continuous LTR)", {"My": My})]
        llb = _angle_llb(Fy, E, Sgeo, cls["flange"])
        if llb:
            rs.append(llb)
        return _reduce_min(rs)

    g = angle_geometry(s)
    Cb = _min(1.5, _n(f.get("Cb"), 1.0))  # F10-4 note: Cb <= 1.5
    Lb = f["Lb"]
    equal = abs(g["bl"] - g["bs"]) < 1e-9
    warnings: List[str] = []

    if equal and not _t(f.get("axialCompression")):
        # F10.2(2)(i)(a): equal-leg angle, geometric axis, no lateral-torsional restraint.
        My = 0.8 * Fy * Sgeo
        rs = [_nominal(1.5 * My, "F10-1 (yielding, My = 0.80 geometric)", {"My": My})]
        if Lb > 0:
            b, t = g["bl"], g["t"]
            Mcr = ((0.58 * E * b ** 4 * t * Cb) / (Lb * Lb)) * (_sq(1 + 0.88 * _pow((Lb * t) / (b * b), 2)) - 1)  # F10-5a
            val, eq = _angle_ltb(My, Mcr)
            rs.append(_nominal(val, f"{eq} (LTB, Mcr F10-5a toe in compression, geometric axis)",
                               {"Mcr": Mcr, "My": My, "Lb": Lb, "Cb": Cb}))
        llb = _angle_llb(Fy, E, 0.8 * Sgeo, cls["flange"])
        if llb:
            rs.append(llb)
        warnings.append("Equal-leg angle without continuous lateral-torsional restraint: geometric-axis F10.2(2)(i) "
                        "with the toe assumed in compression (F10-5a, My and Sc = 0.80 of the geometric values). Set "
                        "continuousLTR only when the angle is continuously restrained.")
        out = dict(_reduce_min(rs))
        out["warnings"] = warnings
        return out

    # Principal-axis route.
    MyW, MyZ = Fy * g["Sw"], Fy * g["Sz"]
    rw = [_nominal(1.5 * MyW, "F10-1 (w-axis)", {"My": MyW})]
    if Lb > 0:
        bw = -g["betaW"]  # long leg in compression
        k = (4.4 * bw * g["rz"]) / (Lb * g["t"])
        Mcr = ((9 * E * s["A"] * g["rz"] * g["t"] * Cb) / (8 * Lb)) * (_sq(1 + k * k) + k)  # F10-4
        val, eq = _angle_ltb(MyW, Mcr)
        rw.append(_nominal(val, f"{eq} (w-axis LTB, Mcr F10-4)", {"Mcr": Mcr, "My": MyW, "betaW": bw, "Lb": Lb, "Cb": Cb}))
    llbW = _angle_llb(Fy, E, g["Sw"], cls["flange"])
    if llbW:
        rw.append(llbW)
    rz = [_nominal(1.5 * MyZ, "F10-1 (z-axis)", {"My": MyZ})]
    llbZ = _angle_llb(Fy, E, g["Sz"], cls["flange"])
    if llbZ:
        rz.append(llbZ)
    Mnw, Mnz = _reduce_min(rw), _reduce_min(rz)
    c, sn = abs(math.cos(g["theta"])), abs(math.sin(g["theta"]))
    cw, cz = (c, sn) if major else (sn, c)
    value = _div(1, _div(cw, Mnw["value"]) + _div(cz, Mnz["value"]))
    warnings.append(
        f"Single angle without continuous lateral-torsional restraint{' carrying axial compression' if equal else ''}: "
        f"principal-axis F10 (alpha = {_to_fixed((g['theta'] * 180) / math.pi, 1)}°), geometric moment resolved into w "
        f"and z and combined linearly (H2-1). beta_w = -{_to_fixed(g['betaW'], 2)} in (long leg in compression, "
        "conservative; two-rectangle idealisation). Combined with axial load this member belongs in H2 — set "
        "continuousLTR only when the angle is continuously restrained."
    )
    return _nominal(value, f"F10 principal axes: Mnw {Mnw['clause']}, Mnz {Mnz['clause']}; H2-1 resolution",
                    {"Mnw": Mnw["value"], "Mnz": Mnz["value"], "alpha": g["theta"], "betaW": -g["betaW"]}, warnings)


def _flexure_tee(s, m, cls, f):
    """Tee flexure about the major axis: F9."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Lb = f["Lb"]
    Sx, Zx = _n(s.get("Sx"), 0), _n(s.get("Zx"), 0)
    My = Fy * Sx  # F9-3
    stem_comp = f.get("stemInCompression") is True
    # Stem in tension: Mp = Fy*Zx <= 1.6*My (F9-2). Stem in compression: Mp = My (F9-4) - the
    # stem tip yields first and there is no plastic reserve. The orientation is an input since
    # 2026-10-26; before that only the tension branch was evaluated, which was UNCONSERVATIVE for
    # a flange-up WT cantilever arm (hogging puts the stem in compression).
    Mp = My if stem_comp else _min(Fy * Zx, 1.6 * My)  # F9-2 / F9-4
    results = [_nominal(Mp, "F9-1 (yielding, F9-4 stem in compression: Mp = My)" if stem_comp else "F9-1 (yielding, F9-2)",
                        {"Mp": Mp, "My": My})]

    # LTB, F9.2. B is NEGATIVE when the stem is in compression (F9-12).
    J, Iy = _n(s.get("J"), 0), _n(s.get("Iy"), 0)
    ry = _n(s.get("ry"), _sq(Iy / s["A"]) if Iy > 0 else 0)
    if Lb > 0 and J > 0 and Iy > 0:
        B = (-2.3 if stem_comp else 2.3) * (s["d"] / Lb) * _sq(Iy / J)  # F9-11 / F9-12
        Mcr = ((1.95 * E) / Lb) * _sq(Iy * J) * (B + _sq(1 + B * B))  # F9-10
        if stem_comp:
            results.append(_nominal(_min(Mcr, My), "F9-13 (LTB, stem in compression, Mcr F9-10 with B F9-12 < 0)",
                                    {"Lb": Lb, "Mcr": Mcr, "B": B}))
        elif ry > 0 and Sx > 0:
            Lp = 1.76 * ry * _sq(E / Fy)  # F9-8
            Lr = 1.95 * (E / Fy) * (_sq(Iy * J) / Sx) * _sq(2.36 * (Fy / E) * ((s["d"] * Sx) / J) + 1)  # F9-9
            if Lp < Lb <= Lr:
                Mn = Mp - (Mp - My) * ((Lb - Lp) / (Lr - Lp))  # F9-6
                results.append(_nominal(Mn, "F9-6 (inelastic LTB, stem in tension)", {"Lp": Lp, "Lr": Lr, "Lb": Lb}))
            elif Lb > Lr:
                results.append(_nominal(_min(Mcr, Mp), "F9-7 (elastic LTB, Mcr F9-10, B F9-11 > 0)",
                                        {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Mcr": Mcr, "B": B}))
    fl = cls["flange"]
    if stem_comp:
        # Local buckling of the tee stem in flexural compression, F9.4(a): Mn = Fcr*Sx with Fcr
        # stepped on d/tw against 0.84*sqrt(E/Fy) and 1.52*sqrt(E/Fy).
        tw = _n(s.get("tw"), 0)
        if tw > 0 and Sx > 0:
            lam = s["d"] / tw
            k = _sq(E / Fy)
            if lam <= 0.84 * k:
                Fcr = Fy  # F9-17
            elif lam <= 1.52 * k:
                Fcr = (1.43 - 0.515 * lam * _sq(Fy / E)) * Fy  # F9-18
            else:
                Fcr = (1.52 * E) / (lam * lam)  # F9-19
            results.append(_nominal(Fcr * Sx, "F9-16 (stem local buckling)", {"lambda": lam, "Fcr": Fcr}))
    elif fl["flex"] != "compact" and Sx > 0:
        # Flange local buckling of the tee flange (F9.3(a)) - only when the flange is the
        # compression element. Sx stands in for Sxc (conservative).
        lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
        nc = fl["flex"] == "noncompact"
        if nc:
            Mn = _min(Mp - (Mp - 0.7 * Fy * Sx) * ((lam - lamP) / (lamR - lamP)), 1.6 * My)  # F9-14
        else:
            Mn = (0.7 * E * Sx) / (lam * lam)  # F9-15
        results.append(_nominal(Mn, f"{'F9-14' if nc else 'F9-15'} (flange local buckling)", {"lambda": lam}))
    return _reduce_min(results)


def flexural_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any],
                      f: Dict[str, Any], axis: str) -> Dict[str, Any]:
    """Flexural strength about ``axis`` ("major" | "minor").

    f = {"Lb": in, "Cb"?, "stemInCompression"?, "continuousLTR"?, "axialCompression"?}.
    """
    kind = s.get("kind")
    if kind in ("I", "C"):
        return _flexure_ic(s, m, cls, f) if axis == "major" else _flexure_minor_ic(s, m, cls)
    if kind == "HSS-RECT":
        return _flexure_hss_rect(s, m, cls, axis == "major", f)
    if kind == "HSS-ROUND":
        return _flexure_hss_round(s, m, cls)
    if kind == "L":
        return _flexure_angle(s, m, cls, axis == "major", f)
    if kind == "T":
        return _flexure_tee(s, m, cls, f) if axis == "major" else _flexure_minor_ic(s, m, cls)
    raise InputError(f"unsupported section kind: {kind}")


# ----- Chapter G - shear ------------------------------------------------------ #

def cv2(htw: float, kv: float, E: float, Fy: float) -> float:
    """Web shear buckling coefficient Cv2 (G2-9, G2-10, G2-11)."""
    k = _sq((kv * E) / Fy)
    if htw <= 1.10 * k:
        return 1.0  # G2-9
    if htw <= 1.37 * k:
        return _div(1.10 * k, htw)  # G2-10
    return _div(1.51 * kv * E, htw * htw * Fy)  # G2-11


def shear_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any], axis: str) -> Dict[str, Any]:
    """Shear strength; result carries ``rolledExempt`` (G2.1(a) phi=1.00 / omega=1.50).

    I, C major G2.1 (Cv1); T stem / angle leg G3-1 (kv 1.2, Cv2); rect HSS G4-1 (kv 5, Cv2);
    round HSS G5-1 with G5-2b; I, C, T minor G6-1 per flange (bf/2tf, channels bf/tf).
    """
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    tw, tf, bf = _n(s.get("tw"), 0), _n(s.get("tf"), 0), _n(s.get("bf"), 0)
    kind = s.get("kind")
    tw1 = tw if _t(tw) else 1

    if kind == "HSS-ROUND":
        Dt = _div(s["d"], tw1)
        Fcr = _min(0.6 * Fy, _div(0.78 * E, _pow(Dt, 1.5)))  # G5-2b, <= 0.6Fy
        Vn = Fcr * (s["A"] / 2)  # G5-1
        return {"value": Vn, "clause": "G5-1 (round HSS, Fcr G5-2b)", "detail": {"Fcr": Fcr, "Dt": Dt},
                "rolledExempt": False}

    def g2(Aw, lam, kv, clause):
        C = cv2(lam, kv, E, Fy)
        return {"value": 0.6 * Fy * Aw * C, "clause": clause, "detail": {"Aw": Aw, "Cv2": C, "kv": kv, "lambda": lam},
                "rolledExempt": False}

    if kind == "HSS-RECT":
        # G4: Aw = 2*h*t for the two walls parallel to the shear.
        h = cls["web"]["lambda"] * tw if axis == "major" else cls["flange"]["lambda"] * tw
        return g2(2 * h * tw, _div(h, tw1), 5.0, "G4-1 (rectangular HSS)")
    if kind == "L":
        # G3: the leg parallel to the shear - long leg (along y) for major-axis shear.
        b = s["d"] if axis == "major" else (bf if _t(bf) else s["d"])
        return g2(b * tw, _div(b, tw1), 1.2, "G3-1 (single-angle leg)")
    if kind == "T" and axis == "major":
        return g2(s["d"] * tw, _div(s["d"], tw1), 1.2, "G3-1 (tee stem)")
    if axis == "minor":
        # G6-1 per shear-resisting flange: two for I and C, one for a tee.
        n = 1 if kind == "T" else 2
        lam = (bf / tf if kind == "C" else bf / (2 * tf)) if bf > 0 and tf > 0 else 0
        return g2(n * bf * tf, lam, 1.2, "G6-1 (minor-axis shear, flanges)")

    # --- G2.1 webs of I-shapes and channels, major axis -----------------------
    Aw = s["d"] * tw
    kv = 5.34
    lam = cls["web"]["lambda"]
    rolled_exempt = kind == "I" and not _t(s.get("builtUp")) and lam <= 2.24 * _sq(E / Fy)
    if rolled_exempt or lam <= 1.10 * _sq((kv * E) / Fy):
        Cv1 = 1.0  # G2-3
    else:
        Cv1 = _div(1.10 * _sq((kv * E) / Fy), lam)  # G2-4
    return {
        "value": 0.6 * Fy * Aw * Cv1,  # G2-1
        "clause": f"G2-1 (web shear){' [G2.1(a)]' if rolled_exempt else ''}",
        "detail": {"Aw": Aw, "Cv1": Cv1, "kv": kv, "lambda": lam},
        "rolledExempt": rolled_exempt,
    }


def cb_from_moments(Mmax: float, Ma: float, Mb: float, Mc: float) -> float:
    """Cb from quarter-point moment magnitudes (F1-1); 1.0 if the segment is unloaded."""
    denom = 2.5 * Mmax + 3 * Ma + 4 * Mb + 3 * Mc
    if denom <= 0:
        return 1.0
    return _min(3.0, (12.5 * Mmax) / denom)


# --------------------------------------------------------------------------- #
# aisc-member.ts
# --------------------------------------------------------------------------- #

_ZERO_TOL = 1e-12


def _ratio_row(label: str, demand: float, capacity: float, clause: str) -> Dict[str, Any]:
    d = abs(demand)
    if d <= _ZERO_TOL:
        return {"label": label, "demand": 0, "capacity": capacity, "ratio": 0, "clause": clause, "status": "na"}
    if capacity <= _ZERO_TOL:
        return {"label": label, "demand": d, "capacity": capacity, "ratio": _INF, "clause": clause,
                "status": "fail"}
    ratio = d / capacity
    return {"label": label, "demand": d, "capacity": capacity, "ratio": ratio, "clause": clause,
            "status": verdict(ratio <= 1.0)}


def aisc_member_design(input: Dict[str, Any]) -> Dict[str, Any]:  # noqa: A002 - TS parameter name
    """Full AISC 360-22 member check. Returns the CalcResult-shaped dict.

    input keys: section, material, method ("LRFD"|"ASD"), Lx, Ly, Lb, Lz, Kx, Ky, Kz, Cb,
    stemInCompression, An, U, nBoltsPerLine, connectionEccentricity, connectionLength,
    continuousLTR, angleE5, span, deflectionLimit, demand {P, axialTension, Mx, My, Vx, Vy, deflection}.
    Raises InputError only on geometrically impossible input.
    """
    s = need(input, "section", "steel section dict")
    m = need(input, "material", "{Fy, Fu, E?, G?}")
    method = need(input, "method", "LRFD or ASD")
    q = need(input, "demand", "demand dict")
    Lx = need(input, "Lx", "unbraced length, in")
    need(s, "A", "section")
    need(s, "Ix", "section")
    need(m, "Fy", "material")
    need(m, "Fu", "material")
    if s["A"] <= 0 or s["Ix"] <= 0:
        raise InputError("section A and Ix must be positive")
    if m["Fy"] <= 0 or m["Fu"] <= 0:
        raise InputError("Fy and Fu must be positive")
    if Lx <= 0:
        raise InputError("Lx must be positive")

    Ly = _n(input.get("Ly"), Lx)
    Lb = _n(input.get("Lb"), Ly)
    Lz = _n(input.get("Lz"), Ly)
    Kx, Ky, Kz = _n(input.get("Kx"), 1.0), _n(input.get("Ky"), 1.0), _n(input.get("Kz"), 1.0)
    warnings: List[str] = []
    axialComp = (not _t(q.get("axialTension"))) and _n(q.get("P"), 0) > 0

    cls = classify_section(s, m)

    tens = tension_strength(s, m, {
        "An": input.get("An"), "U": input.get("U"),
        "nBoltsPerLine": input.get("nBoltsPerLine"), "xbar": input.get("connectionEccentricity"),
        "connectionLength": input.get("connectionLength"),
    })
    e5 = input.get("angleE5")
    if e5:
        e5 = dict(e5)
        e5["L"] = _n(e5.get("L"), Lx)
    comp = compression_strength(s, m, cls, {"Lcx": Kx * Lx, "Lcy": Ky * Ly, "Lcz": Kz * Lz, "angleE5": e5 or None})
    fIn = {"Lb": Lb, "Cb": input.get("Cb"), "continuousLTR": input.get("continuousLTR"), "axialCompression": axialComp}
    mnx = flexural_strength(s, m, cls, dict(fIn, stemInCompression=input.get("stemInCompression")), "major")
    mny = flexural_strength(s, m, cls, fIn, "minor")
    vnx = shear_strength(s, m, cls, "major")
    vny = shear_strength(s, m, cls, "minor")

    Pc_t = _min(
        design(tens["yielding"]["value"], method, PHI["tensionYield"], OMEGA["tensionYield"]),
        design(tens["rupture"]["value"], method, PHI["tensionRupture"], OMEGA["tensionRupture"]),
    )
    Pc_c = design(comp["value"], method, PHI["compression"], OMEGA["compression"])
    Mcx = design(mnx["value"], method, PHI["flexure"], OMEGA["flexure"])
    Mcy = design(mny["value"], method, PHI["flexure"], OMEGA["flexure"])
    Vcx = design(vnx["value"], method,
                 PHI["shearRolled"] if vnx["rolledExempt"] else PHI["shear"],
                 OMEGA["shearRolled"] if vnx["rolledExempt"] else OMEGA["shear"])
    Vcy = design(vny["value"], method, PHI["shear"], OMEGA["shear"])

    rx = _n(s.get("rx"), _sq(s["Ix"] / s["A"]))
    ry = _n(s.get("ry"), _sq(s["Iy"] / s["A"]) if _t(s.get("Iy")) else rx)
    slx = _div(Kx * Lx, rx)
    sly = _div(Ky * Ly, ry)
    slGov = _max(slx, sly)
    tension = bool(_t(q.get("axialTension")))
    slLimit = SLENDERNESS_LIMIT["tension"] if tension else SLENDERNESS_LIMIT["compression"]

    P = _n(q.get("P"), 0)
    Mx_, My_ = _n(q.get("Mx"), 0), _n(q.get("My"), 0)
    axialCap = Pc_t if tension else Pc_c
    axialClause = tens["governing"]["clause"] if tension else comp["clause"]

    checks: List[Dict[str, Any]] = [
        _ratio_row("Axial tension" if tension else "Axial compression", P, axialCap, axialClause),
        _ratio_row("Flexure, major axis", Mx_, Mcx, mnx["clause"]),
        _ratio_row("Flexure, minor axis", My_, Mcy, mny["clause"]),
        _ratio_row("Shear, major axis", _n(q.get("Vx"), 0), Vcx, vnx["clause"]),
        _ratio_row("Shear, minor axis", _n(q.get("Vy"), 0), Vcy, vny["clause"]),
    ]

    pr = P / axialCap if axialCap > _ZERO_TOL else 0
    mrx = Mx_ / Mcx if Mcx > _ZERO_TOL else 0
    mry = My_ / Mcy if Mcy > _ZERO_TOL else 0
    useA = pr >= 0.2
    interaction = pr + (8 / 9) * (mrx + mry) if useA else pr / 2 + (mrx + mry)
    interactionEquation = "H1-1a" if useA else "H1-1b"
    if P > _ZERO_TOL and (_t(q.get("Mx")) or _t(q.get("My"))):
        checks.append({
            "label": "Combined axial + flexure",
            "demand": interaction, "capacity": 1.0, "ratio": interaction,
            "clause": f"{interactionEquation} (Pr/Pc = {_js_num(round_half_up(pr, 3))})",
            "status": verdict(interaction <= 1.0),
        })

    checks.append({
        "label": "Slenderness L/r (D1 advisory)" if tension else "Slenderness KL/r (E2 advisory)",
        "demand": slGov, "capacity": slLimit, "ratio": slGov / slLimit,
        "clause": "D1 recommended limit 300" if tension else "E2 recommended limit 200",
        "status": verdict(slGov <= slLimit),
        "advisory": True,
    })

    defl = q.get("deflection")
    if defl is not None and defl > 0:
        span = _n(input.get("span"), Lx)
        denom = _n(input.get("deflectionLimit"), 240)
        allow = span / denom
        checks.append({
            "label": f"Deflection (L/{_js_num(denom)})",
            "demand": defl, "capacity": allow, "ratio": defl / allow if allow > 0 else _INF,
            "clause": f"Serviceability — span {_js_num(round_half_up(span, 2))} in / {_js_num(denom)}",
            "status": verdict(defl <= allow),
        })

    kind = s.get("kind")
    if cls["axial"] == "slender":
        warnings.append("Section has slender compression elements — Chapter E7 effective area applied; "
                        "verify against the Manual for the governing edition.")
    # Assumptions reported by the strength functions, for the limit states in use.
    surfaced = set()

    def surface(nom, used):
        if not used:
            return
        for w in nom.get("warnings") or []:
            if w not in surfaced:
                surfaced.add(w)
                warnings.append(w)

    surface(tens["rupture"], q.get("axialTension") is True and P > 0)
    surface(comp, axialComp)
    surface(mnx, Mx_ != 0)
    surface(mny, My_ != 0)
    if kind == "L":
        warnings.append(
            "Single-angle flexure: F10 geometric-axis design (continuous lateral-torsional restraint stated) — F10-1 "
            "yielding and F10.3 leg local buckling." if _t(input.get("continuousLTR")) else
            "Single-angle flexure: no continuous lateral-torsional restraint, so F10.2 lateral-torsional buckling is "
            "checked (F10-2/F10-3). Set continuousLTR only when the angle is continuously restrained.")
        if axialComp and (Mx_ != 0 or My_ != 0):
            warnings.append("Single angle with axial load and flexure: AISC F10 sends this to H2 (stress interaction "
                            "about the principal axes); the H1 interaction reported here is an approximation.")
    if axialComp and (input.get("Kx") is None or input.get("Ky") is None):
        if input.get("Kx") is None and input.get("Ky") is None:
            axes = "both axes"
        elif input.get("Kx") is None:
            axes = "the x-axis"
        else:
            axes = "the y-axis"
        warnings.append(
            f"K = 1.0 assumed for {axes} — valid only for a member braced against sidesway (App. 7, 7.2.3(a)). A "
            "cantilever (fixed-free) or sway-permitted column needs K from a sidesway buckling analysis (App. 7, "
            "7.2.3(b)), e.g. 2.1 for a fixed-base free-top post: supply Kx and Ky.")
    if kind == "T":
        sic = input.get("stemInCompression")
        if sic is None:
            warnings.append("Tee flexure assumes the stem in tension (no orientation supplied). With the stem in "
                            "compression F9 caps Mn at My, B goes negative (F9-12) and stem local buckling (F9.4) "
                            "applies — supply stemInCompression.")
        elif sic:
            warnings.append("Tee stem in flexural compression: F9 uses Mp = My, B < 0 in the LTB term and the "
                            "F9.4 stem local-buckling limit.")
        else:
            warnings.append("Tee stem in flexural tension: F9 yielding Mp <= 1.6·My with B > 0 in the LTB term.")
    if slGov > slLimit:
        warnings.append(f"KL/r = {_js_num(round_half_up(slGov, 1))} exceeds the AISC recommended limit of "
                        f"{_js_num(slLimit)}.")
    if _n(input.get("Cb"), 1.0) == 1.0 and Lb > 0 and Mx_ > 0:
        warnings.append("Cb = 1.0 assumed (uniform moment). A computed Cb from the segment's quarter-point "
                        "moments will usually increase the LTB capacity.")
    if defl is None:
        warnings.append("No deflection supplied — serviceability was not checked. Pipe-support spans are "
                        "frequently deflection-governed.")

    real = [c for c in checks if c["status"] != "na" and not c.get("advisory")]
    if real:
        governing = real[0]
        for b in real[1:]:
            governing = b if b["ratio"] > governing["ratio"] else governing
    else:
        governing = checks[0]

    def r4(v):
        return round_half_up(v, 4)

    fl, wb = cls["flange"], cls["web"]
    out_checks = []
    for c in checks:
        o = dict(c)
        o["demand"] = r4(c["demand"])
        o["capacity"] = r4(c["capacity"])
        o["ratio"] = r4(c["ratio"]) if math.isfinite(c["ratio"]) else c["ratio"]
        out_checks.append(o)

    output = {
        "label": s.get("label"),
        "method": method,
        "classification": {
            "flexure": cls["flexure"], "axial": cls["axial"],
            "flangeLambda": r4(fl["lambda"]), "flangeLambdaP": r4(fl["lambdaP"]), "flangeLambdaR": r4(fl["lambdaR"]),
            "webLambda": r4(wb["lambda"]), "webLambdaP": r4(wb["lambdaP"]), "webLambdaR": r4(wb["lambdaR"]),
        },
        "capacity": {
            "tension": r4(Pc_t), "compression": r4(Pc_c),
            "momentX": r4(Mcx), "momentY": r4(Mcy),
            "shearX": r4(Vcx), "shearY": r4(Vcy),
        },
        "slenderness": {"x": r4(slx), "y": r4(sly), "governing": r4(slGov), "limit": slLimit},
        "checks": out_checks,
        "interaction": r4(interaction),
        "interactionEquation": interactionEquation,
        "governingRatio": r4(governing["ratio"]) if math.isfinite(governing["ratio"]) else governing["ratio"],
        "governingCheck": governing["label"],
    }
    status = verdict(all(c.get("advisory") or c["status"] != "fail" for c in checks))
    return result(MODULE, output, status, warnings)


def simple_span_deflection(args: Dict[str, Any]) -> float:
    """Mid-span deflection (in), simply supported: 5wL^4/384EI + PL^3/48EI.

    args: {w (kip/in), P (kip), L (in), I (in^4), E (ksi, default 29000)}.
    """
    E = _n(args.get("E"), DEFAULT_E)
    L, I = need(args, "L"), need(args, "I")
    if L <= 0 or I <= 0:
        raise InputError("L and I must be positive")
    w, P = _n(args.get("w"), 0), _n(args.get("P"), 0)
    return (5 * w * _pow(L, 4)) / (384 * E * I) + (P * _pow(L, 3)) / (48 * E * I)


def cantilever_deflection(args: Dict[str, Any]) -> float:
    """Tip deflection (in) of a cantilever: PL^3/3EI + wL^4/8EI. Same args as above."""
    E = _n(args.get("E"), DEFAULT_E)
    L, I = need(args, "L"), need(args, "I")
    if L <= 0 or I <= 0:
        raise InputError("L and I must be positive")
    w, P = _n(args.get("w"), 0), _n(args.get("P"), 0)
    return (P * _pow(L, 3)) / (3 * E * I) + (w * _pow(L, 4)) / (8 * E * I)
