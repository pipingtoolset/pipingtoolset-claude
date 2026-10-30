"""CAESAR II restraint loads -> ASCE 7-22 load categories -> LRFD / ASD combinations.

A stress program reports the load each restraint carries per LOAD CASE (SUS, OPE,
occasional wind / seismic, hydrotest). Structural design needs those loads split into
ASCE 7 load CATEGORIES (D, T, W, Eh, Ev, L, ...) and recombined with the ASCE 7-22
factors. The mapping is an engineering judgement, so it is an explicit, reported input
with conservative defaults - never hidden:

    D   = SUS reaction                 (pipe + contents + insulation; F treated as D, 2.3.1)
    T   = OPE - SUS                    (thermal / friction self-straining effect)
    W   = pure wind reaction           (CAESAR occasional case, e.g. WIN1 alone, or OPE+W - OPE)
    Eh  = pure seismic reaction        (U1 / U2 / U3 alone, or OPE+E - OPE)
    Ev  = 0.2 SDS D                    (ASCE 7-22 12.4.2.2) when SDS is given
    L   = user live load on the support (usually zero for pipe supports)
    HYD = hydrotest reaction           (checked as its own D-type combination)

Combinations are ASCE 7-22 2.3.1 / 2.3.6 (LRFD) and 2.4.1 / 2.4.5 (ASD), copied from the
Standard. Pipe supports carry no roof, snow, rain, flood or ice loads, so Lr, S, R, Fa,
Di, Wi terms are omitted; supply them as extra categories if a support is exposed to them.

T is not given fixed factors by ASCE 7-22: 2.3.4 requires an LRFD load factor >= 1.0 and
2.4.4 permits reducing T to no less than 0.75 of its value where it is unlikely to
coincide with other maxima. The factors used are inputs (defaults 1.0 / 1.0) and every
combination is also run with T absent, because "effects of one or more loads not acting
shall be considered" (2.3.1, 2.4.1) - friction can relieve as well as add.

Wind and seismic reverse, so each is applied with + and - sign.

Sign convention: CAESAR II reports the load ON the restraint in global axes, so a weight
support shows a NEGATIVE vertical force. `support_demands()` converts to the engine's
convention (vertical positive DOWN, horizontal as magnitudes).

Units in: lb and ft-lb (CAESAR II English defaults) or kip / kip-in; out: kip, kip*in.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from .common import InputError

Vec = List[float]
AXES = ("X", "Y", "Z")
COMPONENTS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")

# --- ASCE 7-22 combinations, verbatim factors (Lr/S/R/flood/ice terms omitted). ---------
# Each entry: (id, clause, {category: factor}). "Wpm"/"Epm" mark +/- reversal variants.
LRFD = [
    ("1a", "ASCE 7-22 2.3.1 (1a)", {"D": 1.4}),
    ("2a", "ASCE 7-22 2.3.1 (2a)", {"D": 1.2, "L": 1.6}),
    ("3a", "ASCE 7-22 2.3.1 (3a)", {"D": 1.2, "L": 1.0}),
    ("3a-W", "ASCE 7-22 2.3.1 (3a), 0.5W companion", {"D": 1.2, "W": 0.5}),
    ("4a", "ASCE 7-22 2.3.1 (4a)", {"D": 1.2, "W": 1.0, "L": 1.0}),
    ("5a", "ASCE 7-22 2.3.1 (5a)", {"D": 0.9, "W": 1.0}),
    ("6", "ASCE 7-22 2.3.6 (6)", {"D": 1.2, "Ev": 1.0, "Eh": 1.0, "L": 1.0}),
    ("7", "ASCE 7-22 2.3.6 (7)", {"D": 0.9, "Ev": -1.0, "Eh": 1.0}),
    # D at its minimum factor with T alone: 2.3.1 "effects of one or more loads not acting
    # shall be considered" - governs uplift / reversal when thermal or friction opposes D.
    ("0.9D", "ASCE 7-22 2.3.1 (5a) D factor with W not acting; 2.3.4 T", {"D": 0.9}),
]
ASD = [
    ("1a", "ASCE 7-22 2.4.1 (1a)", {"D": 1.0}),
    ("2a", "ASCE 7-22 2.4.1 (2a)", {"D": 1.0, "L": 1.0}),
    ("4a", "ASCE 7-22 2.4.1 (4a)", {"D": 1.0, "L": 0.75}),
    ("5a", "ASCE 7-22 2.4.1 (5a)", {"D": 1.0, "W": 0.6}),
    ("6a", "ASCE 7-22 2.4.1 (6a)", {"D": 1.0, "L": 0.75, "W": 0.45}),
    ("7a", "ASCE 7-22 2.4.1 (7a)", {"D": 0.6, "W": 0.6}),
    ("8", "ASCE 7-22 2.4.5 (8)", {"D": 1.0, "Ev": 0.7, "Eh": 0.7}),
    ("9", "ASCE 7-22 2.4.5 (9)", {"D": 1.0, "Ev": 0.525, "Eh": 0.525, "L": 0.75}),
    ("10", "ASCE 7-22 2.4.5 (10)", {"D": 0.6, "Ev": -0.7, "Eh": 0.7}),
    ("0.6D", "ASCE 7-22 2.4.1 (7a) D factor with W not acting; 2.4.4 T", {"D": 0.6}),
]
REVERSING = ("W", "Eh")

_COMBO_ID = re.compile(r"^ASD-(.+?)(?:[+-](?:T)?|\+T)?(?: \(service\))?$")


def asd_wind_combo(combo_id: str) -> bool:
    """True when an envelope combination id names an ASD combination that carries wind.

    Ids are built by combinations() as "<method>-<cid>[+|-][+T]", e.g. "ASD-5a+",
    "ASD-7a-+T"; the cid is looked up in the ASD table so this never depends on the clause
    text. One source for the envelope's ASD wind-anchorage guard (optimizer.envelope) and the
    reviewer's defence-in-depth finding (review._asd_wind_anchorage); code-basis item 10."""
    m = _COMBO_ID.match(str(combo_id or ""))
    if not m:
        return False
    tag = m.group(1)
    for cid, _clause, fac in ASD:
        if tag == cid or (tag.startswith(cid) and tag[len(cid):len(cid) + 1] in ("+", "-")):
            return "W" in fac
    return False


# The wind-anchorage factor margin (code-basis item 10). ASCE 7-22 2.4.1 (5a) carries 0.6W in
# ASD where 2.3.1 (4a)/(5a) carry 1.0W in LRFD, so a wind-governed ASD anchorage implies a
# strength-to-ASD factor of 1/0.6; the engine converts with the fixed ACI 318-19 R17.5.3
# value (baseplate._ASD_ANCHOR_FACTOR). Their quotient bounds how much a wind combination's
# ASD anchorage ratio can be understated; equation constants, not table values.
ASD_WIND_LOAD_FACTOR = 0.6


def asd_wind_margin() -> float:
    """(1/0.6) / 1.5 = 1.111...: the most a wind combination's ASD anchorage ratio can be
    understated by the fixed 1/1.5 conversion (code-basis item 10)."""
    from .baseplate import _ASD_ANCHOR_FACTOR
    return (1.0 / ASD_WIND_LOAD_FACTOR) / _ASD_ANCHOR_FACTOR


def asd_wind_could_govern(wind_ratio, governing_ratio) -> bool:
    """True when an ASD wind combination's anchorage ratio, raised by asd_wind_margin(), reaches
    the governing (non-wind) ratio: under the 1/0.6 treatment that wind combination could
    govern. Covers a near-governing wind combination and a tie the envelope broke in favour of
    an earlier non-wind id. Non-numeric ratios (an infinite string) never trigger it."""
    if not isinstance(wind_ratio, (int, float)) or not isinstance(governing_ratio, (int, float)):
        return False
    return wind_ratio * asd_wind_margin() >= governing_ratio


def _vec(v, name: str) -> Vec:
    if not isinstance(v, (list, tuple)) or len(v) not in (3, 6):
        raise InputError(f"load case {name}: give [Fx, Fy, Fz] or [Fx, Fy, Fz, Mx, My, Mz]")
    v = [float(x) for x in v]
    return v + [0.0] * (6 - len(v))


def _add(a: Vec, b: Vec, k: float = 1.0) -> Vec:
    return [x + k * y for x, y in zip(a, b)]


def categories(spec: dict) -> Tuple[Dict[str, Vec], List[str]]:
    """Resolve the ASCE categories (kip, kip*in, CAESAR global axes and signs).

    spec keys:
      units: "lb-ft" (default, CAESAR English: lb and ft-lb) | "kip-in"
      cases: {"SUS": [...], "OPE": [...], "WIN": [...], "EQ": [...], "HYD": [...], ...}
      map:   optional {category: expression}; expression is a case name or "A-B".
             Defaults: D=SUS, T=OPE-SUS, W=WIN (if given), Eh=EQ (if given), HYD=HYD.
      L:     optional live-load vector (same units)
      SDS:   optional, for Ev = 0.2 SDS D (12.4.2.2)
    """
    units = spec.get("units", "lb-ft")
    if units == "lb-ft":
        kF, kM = 1e-3, 12e-3         # lb -> kip, ft-lb -> kip*in
    elif units == "kip-in":
        kF, kM = 1.0, 1.0
    else:
        raise InputError("loads.units must be 'lb-ft' (CAESAR II English) or 'kip-in'")
    raw = spec.get("cases") or {}
    if "SUS" not in raw:
        raise InputError("loads.cases needs at least SUS (the sustained restraint load)")
    cases = {k.upper(): [c * (kF if i < 3 else kM) for i, c in enumerate(_vec(v, k))]
             for k, v in raw.items()}
    notes: List[str] = []
    default_map = {"D": "SUS"}
    if "OPE" in cases:
        default_map["T"] = "OPE-SUS"
    else:
        notes.append("No OPE case: thermal/friction effect T not included - confirm the support "
                     "sees no operating load beyond sustained.")
    for cat, names in (("W", ("WIN", "WIND", "W")), ("Eh", ("EQ", "SEIS", "U", "E")),
                       ("HYD", ("HYD", "HYDRO"))):
        for n in names:
            if n in cases:
                default_map[cat] = n
                break
    mapping = dict(default_map)
    mapping.update(spec.get("map") or {})
    spec_map_out = spec.get("_resolvedMap")
    if isinstance(spec_map_out, dict):
        spec_map_out.update(mapping)
    out: Dict[str, Vec] = {}
    for cat, expr in mapping.items():
        parts = [p.strip().upper() for p in str(expr).split("-")]
        for p in parts:
            if p not in cases:
                raise InputError(f"category {cat} = {expr!r} uses unknown case {p!r}")
        v = list(cases[parts[0]])
        for p in parts[1:]:
            v = _add(v, cases[p], -1.0)
        out[cat] = v
    if "L" in spec:
        out["L"] = [c * (kF if i < 3 else kM) for i, c in enumerate(_vec(spec["L"], "L"))]
    vi = AXES.index((spec.get("vertical_axis") or "Y").upper())
    if "SDS" in spec and spec["SDS"] is not None:
        ev = [0.0] * 6
        ev[vi] = 0.2 * float(spec["SDS"]) * out["D"][vi]      # vertical seismic: vertical only
        out["Ev"] = ev
        notes.append(f"Ev = 0.2 SDS D (vertical component only) with SDS = {spec['SDS']} "
                     "(ASCE 7-22 12.4.2.2).")
    elif "Eh" in out:
        notes.append("Seismic case given without SDS: Ev taken as zero - supply SDS for 12.4.2.2.")
    # sanity checks on the CAESAR II input (sign convention, pure occasional cases)
    dv = out["D"][vi]
    if dv > 0:
        notes.append("CHECK: the SUS vertical force is positive (upward on the restraint). CAESAR II "
                     "reports a weight support's load as negative - confirm the sign convention.")
    for cat in ("W", "Eh"):
        if cat in out and abs(dv) > 1e-9 and abs(out[cat][vi] - dv) <= 0.1 * abs(dv):
            notes.append(f"CHECK: the {cat} case's vertical force is within 10 % of SUS - it looks like a "
                         "combined OCC case (SUS+W / SUS+E). Give the pure occasional case or D is counted twice.")
    return out, notes


def combinations(spec: dict, method: str) -> Tuple[List[dict], List[str], Dict[str, Vec]]:
    """All ASCE 7-22 combinations for the method, each as a 6-vector in kip / kip*in.

    Returns (combos, notes, categories). Each combo: {id, clause, factors, vector}.
    """
    if method not in ("LRFD", "ASD"):
        raise InputError("method must be LRFD or ASD")
    cats, notes = categories(spec)
    zero = [0.0] * 6
    t_factor = float(spec.get("T_factor", 1.0))
    if method == "LRFD" and t_factor < 1.0:
        raise InputError("ASCE 7-22 2.3.4: the LRFD load factor on T shall not be less than 1.0")
    if method == "ASD" and t_factor < 0.75:
        raise InputError("ASCE 7-22 2.4.4: the fraction of T combined shall not be less than 0.75")
    table = LRFD if method == "LRFD" else ASD
    combos: List[dict] = []
    for cid, clause, fac in table:
        if any(c in ("W",) for c in fac) and "W" not in cats:
            continue
        if any(c in ("Eh", "Ev") for c in fac) and "Eh" not in cats:
            continue
        if cid in ("0.9D", "0.6D") and "T" not in cats:
            continue                        # only meaningful with T (otherwise 5a / 7a cover it)
        if "L" in fac and "L" not in cats and cid in ("2a", "3a") and method == "LRFD":
            continue                        # identical to 1a/D-only when L is absent
        if "L" in fac and "L" not in cats and cid in ("2a", "4a") and method == "ASD":
            continue
        signs = [1, -1] if any(c in fac for c in REVERSING) else [1]
        for s in signs:
            t_opts = (True,) if cid in ("0.9D", "0.6D") else ((True, False) if "T" in cats else (False,))
            for with_t in t_opts:
                f = dict(fac)
                for c in REVERSING:
                    if c in f:
                        f[c] *= s
                if with_t:
                    f["T"] = t_factor
                v = list(zero)
                for c, k in f.items():
                    if c in cats:
                        v = _add(v, cats[c], k)
                tag = cid + ("" if len(signs) == 1 else ("+" if s > 0 else "-")) + ("+T" if with_t else "")
                combos.append({"id": f"{method}-{tag}", "clause": clause + (
                    f"; T x {t_factor:g} (2.3.4)" if with_t and method == "LRFD"
                    else f"; T x {t_factor:g} (2.4.4)" if with_t else ""),
                    "factors": f, "vector": v})
    if "HYD" in cats:
        k = 1.4 if method == "LRFD" else 1.0
        combos.append({"id": f"{method}-HYD", "clause": f"hydrotest treated as D ({k:g} x HYD); "
                       "confirm the owner's test-load criteria", "factors": {"HYD": k},
                       "vector": [k * c for c in cats["HYD"]]})
    notes.append(f"T factor {t_factor:g} (ASCE 7-22 {'2.3.4: >= 1.0' if method == 'LRFD' else '2.4.4: >= 0.75'}); "
                 "every combination also run without T.")
    return combos, notes, cats


def support_demands(vector: Vec, vertical_axis: str = "Y", pipe_axis: str = "X") -> dict:
    """Map a combination vector (CAESAR global, load ON the restraint) to engine demands.

    vertical  = load pushing DOWN on the support (kip, + down, - = uplift)
    transverse   = |horizontal across the pipe|  (acts along the arm)
    longitudinal = |horizontal along the pipe|   (acts across the arm)
    moments are returned for the reviewer; the parametric assemblies take forces only.
    """
    va, pa = vertical_axis.upper(), pipe_axis.upper()
    if va not in AXES or pa not in AXES or va == pa:
        raise InputError("vertical_axis and pipe_axis must be two different axes of X, Y, Z")
    ta = next(a for a in AXES if a not in (va, pa))
    i = {a: n for n, a in enumerate(AXES)}
    vector = list(vector) + [0.0] * (6 - len(vector))      # forces-only rows carry no moments
    return {"vertical": -vector[i[va]],
            "transverse": abs(vector[i[ta]]),
            "longitudinal": abs(vector[i[pa]]),
            "moments": {f"M{a.lower()}": vector[3 + i[a]] for a in AXES}}


def governing(combos: Sequence[dict], vertical_axis: str = "Y", pipe_axis: str = "X") -> List[dict]:
    """Envelope candidates worth running through the assembly: max down, max uplift,
    max transverse, max longitudinal, max resultant horizontal. Deduplicated."""
    rows = [(c, support_demands(c["vector"], vertical_axis, pipe_axis)) for c in combos]
    pick = {
        "max vertical (down)": max(rows, key=lambda r: r[1]["vertical"]),
        "max uplift": min(rows, key=lambda r: r[1]["vertical"]),
        "max transverse": max(rows, key=lambda r: r[1]["transverse"]),
        "max longitudinal": max(rows, key=lambda r: r[1]["longitudinal"]),
        "max horizontal resultant": max(rows, key=lambda r: (r[1]["transverse"] ** 2 + r[1]["longitudinal"] ** 2)),
    }
    out: Dict[str, dict] = {}
    for why, (c, d) in pick.items():
        if why == "max uplift" and d["vertical"] >= 0:
            continue
        e = out.setdefault(c["id"], {"combo": c, "demands": d, "why": []})
        e["why"].append(why)
    return list(out.values())
