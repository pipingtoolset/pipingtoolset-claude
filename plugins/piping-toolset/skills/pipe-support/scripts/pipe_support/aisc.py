"""AISC 360-22 member design - stdlib Python port of the PiperSTR engine.

Faithful port of three modules of the pipingtoolset.com PiperSTR engine (structural):

  * aisc-section.ts  - section model, Table B4.1 classification, Chapter B3 factors
  * aisc-strength.ts - nominal strengths, Chapters D, E, F, G (+ Cb, F1-1)
  * aisc-member.ts   - the member check, plus the two deflection helpers

Sections, materials and demands are plain dicts with the TypeScript camelCase keys; the
result is the same result dict the TypeScript engine returns, so JSON equality
with a pipingtoolset.com PiperSTR run is possible. Units: in, in^2, in^3, in^4, kip, ksi,
kip*in.

Licensing firewall (same as the TypeScript engine): the EQUATIONS live here; section
property VALUES arrive as inputs - from data/aisc_shapes.json (AISC's free Shapes
Database v16.0 plus computed L/HSS/PIPE rows) or user-entered.

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
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:  # package import (scripts/ on sys.path) and flat import both work
    from .common import InputError, need, result, round_half_up
except ImportError:  # pragma: no cover
    from common import InputError, need, result, round_half_up  # type: ignore

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
    """Web slenderness kc for built-up I-shapes: 4/sqrt(h/tw) bounded to [0.35, 0.76]."""
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
        "lambda": lamF, "lambdaP": fP, "lambdaR": fR,
        "flex": _classify(lamF, fP, fR),
        "axial": "nonslender" if lamF <= fRax else "slender",
    }
    web = {
        "lambda": lamW, "lambdaP": wP, "lambdaR": wR,
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
    "Iz", "Iw", "Sz", "Sw", "rz", "rw", "C",
)


def section_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build a section dict from an aisc_shapes.json row (absent fields stay absent)."""
    kind = _KIND.get(row.get("family"))
    if not kind:
        raise InputError(f"unsupported shape family: {row.get('family')}")
    out: Dict[str, Any] = {"label": row["label"], "kind": kind, "d": _n(row.get("d"), 0)}
    for k in _SECTION_KEYS:
        if row.get(k) is not None:
            out[k] = row[k]
    return out


# --------------------------------------------------------------------------- #
# Shape lookup (data/aisc_shapes.json; port of code-data-service findShape etc.)
# --------------------------------------------------------------------------- #

_SHAPES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "aisc_shapes.json")
_SHAPES_CACHE: Dict[str, Any] = {}


def _norm_label(label: str) -> str:
    return re.sub(r"\s+", "", label).upper()


def load_shapes() -> List[Dict[str, Any]]:
    """All rows of the vendored AISC shapes dataset (cached)."""
    if "rows" not in _SHAPES_CACHE:
        with open(_SHAPES_PATH, "r", encoding="utf-8") as fh:
            rows = json.load(fh)["rows"]
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

def _nominal(value: float, clause: str, detail: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": value, "clause": clause}
    if detail is not None:
        out["detail"] = detail
    return out


# ----- Chapter D - tension -------------------------------------------------- #

def tension_strength(s: Dict[str, Any], m: Dict[str, Any],
                     opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """D2-1 yielding and D2-2/D3-1 rupture. Returns {yielding, rupture, governing}."""
    opts = opts or {}
    A = s["A"]
    An = _n(opts.get("An"), A)
    U = _n(opts.get("U"), 0.6 if s.get("kind") == "L" else 1.0)
    Ae = An * U
    yielding = _nominal(m["Fy"] * A, "D2-1 (gross-section yielding)", {"Ag": A})
    rupture = _nominal(m["Fu"] * Ae, "D2-2 (net-section rupture)", {"An": An, "U": U, "Ae": Ae})
    governing = yielding if yielding["value"] <= rupture["value"] else rupture
    return {"yielding": yielding, "rupture": rupture, "governing": governing}


# ----- Chapter E - compression ---------------------------------------------- #

def _critical_stress(Fe: float, Fy: float, E: float):
    inelastic = _div(Fy, Fe) <= 2.25
    Fn = _pow(0.658, _div(Fy, Fe)) * Fy if inelastic else 0.877 * Fe
    return Fn, inelastic


def _effective_area(s, m, cls, Fn):
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

    stiffened = kind == "HSS-RECT"
    c1 = 0.20 if stiffened else 0.22
    c2 = 1.38 if stiffened else 1.49

    removed = [0.0]

    def reduce(lam, lamR, b, t, n):
        if lam <= lamR or t <= 0:
            return
        Fel = (c2 * (lamR / lam)) ** 2 * Fy  # E7-5
        be = b * (1 - c1 * _sq(Fel / Fn)) * _sq(Fel / Fn)  # E7-3
        removed[0] += n * _max(0, b - _min(b, be)) * t

    bf, tf, tw = s.get("bf"), s.get("tf"), s.get("tw")
    fl, wb = cls["flange"], cls["web"]
    if kind in ("I", "C"):
        if _t(bf) and _t(tf):
            outstand = bf if kind == "C" else bf / 2
            reduce(fl["lambda"], fl["lambdaR"], outstand, tf, 2 if kind == "C" else 4)
        if _t(tw):
            reduce(wb["lambda"], wb["lambdaR"], wb["lambda"] * tw, tw, 1)
    elif kind == "HSS-RECT" and _t(tw):
        reduce(fl["lambda"], fl["lambdaR"], fl["lambda"] * tw, tw, 2)
        reduce(wb["lambda"], wb["lambdaR"], wb["lambda"] * tw, tw, 2)
    elif _t(tw):
        reduce(fl["lambda"], fl["lambdaR"], fl["lambda"] * tw, tw, 1)
        reduce(wb["lambda"], wb["lambdaR"], wb["lambda"] * tw, tw, 1)

    return _max(0.1 * A, A - removed[0]), "E7 effective area"


def compression_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any],
                         L: Dict[str, Any]) -> Dict[str, Any]:
    """E3 flexural buckling (each axis), E4 torsional / flexural-torsional, E7 slender.

    L = {"Lcx": in, "Lcy": in, "Lcz": in (optional, defaults to Lcy)}.
    """
    E = _n(m.get("E"), DEFAULT_E)
    G = _n(m.get("G"), DEFAULT_G)
    Fy = m["Fy"]
    A = s["A"]
    Lcx, Lcy = L["Lcx"], L["Lcy"]
    Lcz = _n(L.get("Lcz"), Lcy)
    kind = s.get("kind")

    rx = _n(s.get("rx"), _sq(s["Ix"] / A))
    ry = _n(s.get("ry"), _sq(s["Iy"] / A) if _t(s.get("Iy")) else rx)
    cands: List[Dict[str, Any]] = []

    def add_flexural(Lc, r, axis):
        if r <= 0 or Lc <= 0:
            return
        sl = Lc / r
        cands.append({"Fe": (math.pi ** 2 * E) / (sl * sl),
                      "clause": f"E3-4 (flexural buckling, {axis})", "slender": sl})

    add_flexural(Lcx, rx, "x-x")
    add_flexural(Lcy, ry, "y-y")
    if kind == "L" and _t(s.get("rz")):
        add_flexural(_min(Lcx, Lcy), s["rz"], "z-z principal")

    J = _n(s.get("J"), 0)
    Cw = _n(s.get("Cw"), 0)
    Iy = _n(s.get("Iy"), s["Ix"])
    if J > 0 and Lcz > 0:
        if kind == "I":
            Fe = _div((math.pi ** 2 * E * Cw) / (Lcz * Lcz) + G * J, s["Ix"] + Iy)
            if math.isfinite(Fe) and Fe > 0:
                cands.append({"Fe": Fe, "clause": "E4-2 (torsional buckling)",
                              "slender": _div(Lcz, _n(s.get("rz"), ry))})
        elif kind in ("T", "C"):
            ro = _n(s.get("ro"), _sq((s["Ix"] + Iy) / A))
            H = _n(s.get("H"), 1)
            Fey = _div(math.pi ** 2 * E, _pow(_div(Lcy, ry), 2))
            Fez = _div((math.pi ** 2 * E * Cw) / (Lcz * Lcz) + G * J, A * ro * ro)
            disc = 1 - _div(4 * Fey * Fez * H, _pow(Fey + Fez, 2))
            if disc >= 0:
                Fe = ((Fey + Fez) / (2 * H)) * (1 - _sq(disc))
                if Fe > 0:
                    cands.append({"Fe": Fe, "clause": "E4-3 (flexural-torsional buckling)",
                                  "slender": _div(Lcy, ry)})

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
    }


# ----- Chapter F - flexure --------------------------------------------------- #

def _rts_of(s):
    if _t(s.get("rts")):
        return s["rts"]
    Iy, Cw, Sx = _n(s.get("Iy"), 0), _n(s.get("Cw"), 0), _n(s.get("Sx"), 0)
    return _sq(_sq(Iy * Cw) / Sx) if Iy > 0 and Cw > 0 and Sx > 0 else 0


def _flexure_ic(s, m, cls, f):
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Cb = _n(f.get("Cb"), 1.0)
    Lb = f["Lb"]
    Zx, Sx, ry = _n(s.get("Zx"), 0), _n(s.get("Sx"), 0), _n(s.get("ry"), 0)
    Mp = Fy * Zx
    results = [_nominal(Mp, "F2-1 (yielding)", {"Mp": Mp})]

    rts = _rts_of(s)
    ho = _n(s.get("ho"), s["d"] - _n(s.get("tf"), 0))
    J = _n(s.get("J"), 0)
    c = (ho / 2) * _sq(_n(s.get("Iy"), 0) / s["Cw"]) if (s.get("kind") == "C" and _t(s.get("Cw"))) else 1.0

    if ry > 0 and rts > 0 and ho > 0 and Sx > 0:
        Lp = 1.76 * ry * _sq(E / Fy)  # F2-5
        term = (J * c) / (Sx * ho)
        Lr = 1.95 * rts * (E / (0.7 * Fy)) * _sq(term + _sq(term * term + 6.76 * ((0.7 * Fy) / E) ** 2))  # F2-6
        if Lb <= Lp:
            results.append(_nominal(Mp, "F2-1 (Lb <= Lp, LTB does not apply)", {"Lp": Lp, "Lr": Lr, "Lb": Lb}))
        elif Lb <= Lr:
            Mn = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * ((Lb - Lp) / (Lr - Lp)))  # F2-2
            results.append(_nominal(_min(Mn, Mp), "F2-2 (inelastic LTB)", {"Lp": Lp, "Lr": Lr, "Lb": Lb, "Cb": Cb}))
        else:
            sl = Lb / rts
            Fcr = ((Cb * math.pi ** 2 * E) / (sl * sl)) * _sq(1 + 0.078 * term * sl * sl)  # F2-4
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
            kc = kc_factor(wb["lambda"] if _t(wb["lambda"]) else 1) if _t(s.get("builtUp")) else 1
            Mn = (0.9 * E * kc * Sx) / (lam * lam)  # F3-2
            results.append(_nominal(Mn, "F3-2 (slender flange, FLB)", {"lambda": lam, "kc": kc}))

    if wb["flex"] == "noncompact" and Sx > 0:
        Myc = Fy * Sx
        lam, lamP, lamR = wb["lambda"], wb["lambdaP"], wb["lambdaR"]
        Mn = Mp - (Mp - Myc) * ((lam - lamP) / (lamR - lamP))
        results.append(_nominal(Mn, "F4 (noncompact web)", {"lambda": lam, "lambdaP": lamP, "lambdaR": lamR}))
    elif wb["flex"] == "slender" and Sx > 0:
        tw = _n(s.get("tw"), 0)
        aw = _min(10, _div(tw * wb["lambda"] * tw, _n(s.get("bf"), 1) * _n(s.get("tf"), 1)))
        hc_tw = wb["lambda"]
        Rpg = _min(1.0, 1 - (aw / (1200 + 300 * aw)) * (hc_tw - 5.7 * _sq(E / Fy)))
        results.append(_nominal(Rpg * Fy * Sx, "F5-1 (slender web)", {"Rpg": Rpg, "aw": aw}))

    return _reduce_min(results)


def _flexure_minor_ic(s, m, cls):
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
    Fcr = (0.69 * E) / (lam * lam)  # F6-4
    return _nominal(Fcr * Sy, "F6-3 (slender flange)", {"Fcr": Fcr, "lambda": lam})


def _flexure_hss_rect(s, m, cls, major):
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Z = _n(s.get("Zx") if major else s.get("Zy"), 0)
    S = _n(s.get("Sx") if major else s.get("Sy"), 0)
    Mp = Fy * Z  # F7-1
    results = [_nominal(Mp, "F7-1 (yielding)", {"Mp": Mp})]

    fl = cls["flange"] if major else cls["web"]
    if fl["flex"] == "noncompact":
        Mn = Mp - (Mp - Fy * S) * (3.57 * fl["lambda"] * _sq(Fy / E) - 4.0)  # F7-2
        results.append(_nominal(_min(Mn, Mp), "F7-2 (noncompact flange)", {"lambda": fl["lambda"]}))
    elif fl["flex"] == "slender":
        t = _n(s.get("tw"), 0)
        b = fl["lambda"] * t
        be = _min(b, 1.92 * t * _sq(E / Fy) * (1 - (0.38 / fl["lambda"]) * _sq(E / Fy)))  # F7-4
        Se = S * (be / _max(b, 1e-9))
        results.append(_nominal(Fy * Se, "F7-3 (slender flange, effective Se)", {"be": be, "b": b}))

    wb = cls["web"] if major else cls["flange"]
    if wb["flex"] == "noncompact":
        Mn = Mp - (Mp - Fy * S) * (0.305 * wb["lambda"] * _sq(Fy / E) - 0.738)  # F7-5
        results.append(_nominal(_min(Mn, Mp), "F7-5 (noncompact web)", {"lambda": wb["lambda"]}))
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


def _flexure_angle(s, m, cls, major):
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    S = _n(s.get("Sx") if major else s.get("Sy"), 0)
    My = Fy * S
    results = [_nominal(1.5 * My, "F10-1 (yielding, 1.5My)", {"My": My})]
    fl = cls["flange"]
    lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
    if lam > lamP:
        if lam <= lamR:
            results.append(_nominal(Fy * S * (2.43 - 1.72 * lam * _sq(Fy / E)),
                                    "F10-6 (noncompact leg, LLB)", {"lambda": lam}))
        else:
            Fcr = (0.71 * E) / (lam * lam)
            results.append(_nominal(Fcr * S, "F10-7 (slender leg, LLB)", {"Fcr": Fcr, "lambda": lam}))
    return _reduce_min(results)


def _flexure_tee(s, m, cls, f):
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    Lb = f["Lb"]
    Sx, Zx = _n(s.get("Sx"), 0), _n(s.get("Zx"), 0)
    My = Fy * Sx
    Mp = _min(Fy * Zx, 1.6 * My)  # F9-2
    results = [_nominal(Mp, "F9-1 (yielding)", {"Mp": Mp, "My": My})]

    J, Iy = _n(s.get("J"), 0), _n(s.get("Iy"), 0)
    if Lb > 0 and J > 0 and Iy > 0:
        B = 2.3 * (s["d"] / Lb) * _sq(Iy / J)
        Mcr = ((1.95 * E) / Lb) * _sq(Iy * J) * (B + _sq(1 + B * B))  # F9-4
        results.append(_nominal(_min(Mcr, Mp), "F9-4 (LTB)", {"Lb": Lb, "Mcr": Mcr}))
    fl = cls["flange"]
    if fl["flex"] != "compact" and Sx > 0:
        lam, lamP, lamR = fl["lambda"], fl["lambdaP"], fl["lambdaR"]
        if fl["flex"] == "noncompact":
            Mn = Mp - (Mp - 0.7 * Fy * Sx) * ((lam - lamP) / (lamR - lamP))
        else:
            Mn = (0.7 * E * Sx) / (lam * lam)
        results.append(_nominal(Mn, "F9 (flange local buckling)", {"lambda": lam}))
    return _reduce_min(results)


def flexural_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any],
                      f: Dict[str, Any], axis: str) -> Dict[str, Any]:
    """Flexural strength about ``axis`` ("major" | "minor"); f = {"Lb": in, "Cb": optional}."""
    kind = s.get("kind")
    if kind in ("I", "C"):
        return _flexure_ic(s, m, cls, f) if axis == "major" else _flexure_minor_ic(s, m, cls)
    if kind == "HSS-RECT":
        return _flexure_hss_rect(s, m, cls, axis == "major")
    if kind == "HSS-ROUND":
        return _flexure_hss_round(s, m, cls)
    if kind == "L":
        return _flexure_angle(s, m, cls, axis == "major")
    if kind == "T":
        return _flexure_tee(s, m, cls, f) if axis == "major" else _flexure_minor_ic(s, m, cls)
    raise InputError(f"unsupported section kind: {kind}")


# ----- Chapter G - shear ------------------------------------------------------ #

def shear_strength(s: Dict[str, Any], m: Dict[str, Any], cls: Dict[str, Any], axis: str) -> Dict[str, Any]:
    """Shear strength; result carries ``rolledExempt`` (G2.1(a) phi=1.00 / omega=1.50)."""
    E, Fy = _n(m.get("E"), DEFAULT_E), m["Fy"]
    tw, tf, bf = _n(s.get("tw"), 0), _n(s.get("tf"), 0), _n(s.get("bf"), 0)
    kind = s.get("kind")

    if kind == "HSS-ROUND":
        Dt = _div(s["d"], tw if _t(tw) else 1)
        Fcr = _min(0.6 * Fy, _div(0.78 * E, _pow(Dt, 1.5)))
        Vn = Fcr * (s["A"] / 2)  # G6-1
        return {"value": Vn, "clause": "G6-1 (round HSS)", "detail": {"Fcr": Fcr, "Dt": Dt},
                "rolledExempt": False}
    if kind == "HSS-RECT":
        h = cls["web"]["lambda"] * tw if axis == "major" else cls["flange"]["lambda"] * tw
        Aw = 2 * h * tw
        kv = 5.0
        lam = _div(h, tw)
        clause = "G4 (rectangular HSS)"
    elif axis == "major":
        Aw = s["d"] * tw
        kv = 5.34
        lam = cls["web"]["lambda"]
        clause = "G2-1 (web shear)"
    else:
        Aw = 2 * bf * tf
        kv = 1.2
        lam = bf / (2 * tf) if bf > 0 and tf > 0 else 0
        clause = "G7 (flange shear, weak axis)"

    rolled_exempt = (kind == "I" and axis == "major" and not _t(s.get("builtUp"))
                     and cls["web"]["lambda"] <= 2.24 * _sq(E / Fy))
    if rolled_exempt or lam <= 1.10 * _sq((kv * E) / Fy):
        Cv1 = 1.0  # G2-3
    else:
        Cv1 = _div(1.10 * _sq((kv * E) / Fy), lam)  # G2-4

    return {
        "value": 0.6 * Fy * Aw * Cv1,
        "clause": f"{clause}{' [G2.1(a)]' if rolled_exempt else ''}",
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
            "status": "pass" if ratio <= 1.0 else "fail"}


def aisc_member_design(input: Dict[str, Any]) -> Dict[str, Any]:  # noqa: A002 - TS parameter name
    """Full AISC 360-22 member check. Returns the CalcResult-shaped dict.

    input keys: section, material, method ("LRFD"|"ASD"), Lx, Ly, Lb, Lz, Kx, Ky, Kz, Cb,
    An, U, span, deflectionLimit, demand {P, axialTension, Mx, My, Vx, Vy, deflection}.
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

    cls = classify_section(s, m)

    tens = tension_strength(s, m, {"An": input.get("An"), "U": input.get("U")})
    comp = compression_strength(s, m, cls, {"Lcx": Kx * Lx, "Lcy": Ky * Ly, "Lcz": Kz * Lz})
    mnx = flexural_strength(s, m, cls, {"Lb": Lb, "Cb": input.get("Cb")}, "major")
    mny = flexural_strength(s, m, cls, {"Lb": Lb, "Cb": input.get("Cb")}, "minor")
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
            "status": "pass" if interaction <= 1.0 else "fail",
        })

    checks.append({
        "label": "Slenderness L/r (D1 advisory)" if tension else "Slenderness KL/r (E2 advisory)",
        "demand": slGov, "capacity": slLimit, "ratio": slGov / slLimit,
        "clause": "D1 recommended limit 300" if tension else "E2 recommended limit 200",
        "status": "pass" if slGov <= slLimit else "fail",
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
            "status": "pass" if defl <= allow else "fail",
        })

    kind = s.get("kind")
    if cls["axial"] == "slender":
        warnings.append("Section has slender compression elements — Chapter E7 effective area applied; "
                        "verify against the Manual for the governing edition.")
    if kind == "L":
        warnings.append("Single-angle flexure uses the F10 geometric-axis route (leg tips in compression). "
                        "Angles bent about a principal axis, or unrestrained against lateral-torsional "
                        "rotation, need the full F10.3 check.")
        if not _t(input.get("U")) and P > 0 and tension:
            warnings.append("Shear lag factor U defaulted to 0.60 for the angle (single-leg connection assumed). "
                            "Supply U from Table D3.1 when the connection is known.")
    if kind == "T":
        warnings.append("Tee flexure assumes the stem in tension. With the stem in compression F9 caps Mn at "
                        "My — confirm the orientation.")
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
    status = "pass" if all(c.get("advisory") or c["status"] != "fail" for c in checks) else "fail"
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
