"""Weld detailing, groove welds and constructability - the compliance layer.

Numeric limits are AISC 360-22 Chapter J2, which is published free by AISC and agrees
with AWS D1.1 on these points. AWS D1.1 itself is NOT reproduced (it is a paid,
copyrighted code): its requirements are cited by clause topic only and listed as items
the engineer confirms against the governing D1.1 edition - prequalified joint geometry,
WPS, matching filler metal, preheat.

    fillet min size          J2.2b, Table J2.4 (by the thinner part joined)
    fillet max size          J2.2b (edge of material: t, or t - 1/16 for t >= 1/4)
    fillet min length        J2.2b (4w, else effective size <= L/4)
    long end-loaded fillets  J2.2b (J2-1), beta reduction above 100w
    PJP min effective throat J2.1, Table J2.3
    groove weld strength     J2.4, Table J2.5 (CJP = base metal; PJP by throat)

Every finding has a severity: "violation" (fails the Specification), "advisory"
(permitted but worth a second look) or "constructability" (passes code, costs money
or quality in the field).

Units: in, kip, ksi.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from .common import InputError, need, result, round_half_up

R4 = lambda x: round_half_up(x, 4)  # noqa: E731

# Table J2.4 minimum fillet size by thinner part joined, in: (t upper bound, w_min)
_MIN_FILLET = [(0.25, 1 / 8), (0.5, 3 / 16), (0.75, 1 / 4), (math.inf, 5 / 16)]
# Table J2.3 minimum PJP effective throat by thinner part joined, in
_MIN_PJP = [(0.25, 1 / 8), (0.5, 3 / 16), (0.75, 1 / 4), (1.5, 5 / 16), (2.25, 3 / 8),
            (6.0, 1 / 2), (math.inf, 5 / 8)]
# Matching filler strength classes for common pipe-support steels (AWS D1.1 matching
# filler table; listed here only as the FEXX class, not reproduced).
_MATCHING_FEXX = {"A36": 70, "A572-50": 70, "A992": 70, "A500-B": 70, "A500-C": 70,
                  "A53-B": 70, "A106-B": 70, "A1085": 70}


def finding(sev: str, msg: str, clause: str) -> Dict[str, str]:
    return {"severity": sev, "message": msg, "clause": clause}


def min_fillet(t_thinner: float) -> float:
    for tmax, w in _MIN_FILLET:
        if t_thinner <= tmax + 1e-12:
            return w
    return 5 / 16


def min_pjp_throat(t_thinner: float) -> float:
    for tmax, e in _MIN_PJP:
        if t_thinner <= tmax + 1e-12:
            return e
    return 5 / 8


def fillet_detailing(inp: dict) -> List[dict]:
    """inp: size, tThinner, tEdge (thickness of the part whose edge the fillet runs
    along, if any), length, endLoaded (bool), FEXX, baseGrade, field (bool),
    position ("flat"|"horizontal"|"vertical"|"overhead"), allRound (bool), hssWall."""
    w = float(need(inp, "size"))
    t = float(need(inp, "tThinner"))
    L = inp.get("length")
    out: List[dict] = []
    wmin = min_fillet(t)
    if w < wmin - 1e-9:
        out.append(finding("violation", f"Fillet {_frac(w)} below Table J2.4 minimum {_frac(wmin)} "
                           f"for {t:g} in thinner part", "AISC 360-22 J2.2b, Table J2.4"))
    te = inp.get("tEdge")
    if te is not None:
        te = float(te)
        wmax = te if te < 0.25 else te - 1 / 16
        if w > wmax + 1e-9:
            out.append(finding("violation", f"Fillet {_frac(w)} along a {te:g} in edge exceeds the "
                               f"maximum {_frac(wmax)}", "AISC 360-22 J2.2b"))
    if L is not None:
        L = float(L)
        if L < 4 * w - 1e-9:
            out.append(finding("advisory", f"Fillet length {L:g} in < 4w = {4 * w:g} in: effective size "
                               f"limited to L/4 = {_frac(L / 4)}", "AISC 360-22 J2.2b"))
        if inp.get("endLoaded") and L > 100 * w:
            if L / w > 300:
                msg = f"End-loaded fillet L/w = {L / w:.0f} > 300: effective length = 180w = {180 * w:g} in"
            else:
                beta = min(1.0, 1.2 - 0.002 * L / w)
                msg = f"End-loaded fillet L/w = {L / w:.0f} > 100: reduce effective length by beta = {beta:.3f}"
            out.append(finding("advisory", msg, "AISC 360-22 J2.2b (J2-1)"))
    hss = inp.get("hssWall")
    if hss is not None and w > float(hss) + 1e-9:
        out.append(finding("advisory", f"Fillet {_frac(w)} larger than the HSS wall {hss:g} in - "
                           "the wall governs; extra size adds heat and distortion, not strength",
                           "AISC 360-22 K / J2.4"))
    fexx = inp.get("FEXX")
    grade = (inp.get("baseGrade") or "").upper()
    if fexx is not None and grade in _MATCHING_FEXX and float(fexx) < _MATCHING_FEXX[grade]:
        out.append(finding("violation", f"E{int(float(fexx))}XX under-matches {grade} "
                           f"(matching class E{_MATCHING_FEXX[grade]}XX)",
                           "AWS D1.1 matching filler metal requirement; AISC 360-22 Table J2.5"))
    if w > 5 / 16 + 1e-9:
        out.append(finding("constructability", f"{_frac(w)} fillet is typically multi-pass by SMAW: "
                           "more passes, more heat, more cost - check whether a smaller fillet "
                           "with a longer weld or a PJP does the job", "AWS D1.1 prequalified WPS limits"))
    if inp.get("field"):
        pos = inp.get("position", "horizontal")
        sev = "constructability"
        if pos == "overhead":
            out.append(finding(sev, "Overhead field weld: lowest productivity and the hardest to "
                               "inspect - shop-weld this joint or make the field joint bolted",
                               "AWS D1.1 qualification by position"))
        else:
            out.append(finding(sev, "Field weld: needs a qualified welder, WPS and inspection at "
                               "site; a bolted field joint is usually cheaper", "AWS D1.1 Clause 8 inspection"))
    if inp.get("allRound") and inp.get("field"):
        out.append(finding("constructability", "All-round field fillet on a column base needs "
                           "access on all four sides - check clearance to adjacent steel and grout",
                           "detailing practice"))
    return out


def groove_weld(inp: dict) -> dict:
    """Groove weld strength, AISC 360-22 J2.4 / Table J2.5.

    inp: method, type ("CJP"|"PJP"), throat (PJP effective throat E, in), length (in),
         tThinner, FEXX, baseFy, baseFu, Tn (tension normal to the weld axis, kip),
         V (shear, kip)
    CJP: strength = base metal (Ch. J4 checks on the connected part), so the weld itself
    is not the limit state when the filler matches.
    """
    method = need(inp, "method")
    kind = need(inp, "type").upper()
    L = float(need(inp, "length"))
    t = float(need(inp, "tThinner"))
    Fy, Fu = float(need(inp, "baseFy")), float(need(inp, "baseFu"))
    FEXX = float(need(inp, "FEXX"))
    Tn, V = float(inp.get("Tn", 0.0)), float(inp.get("V", 0.0))
    checks, findings = [], []

    def dsg(n, phi, om):
        return n * phi if method == "LRFD" else n / om

    def row(name, dem, cap, clause):
        checks.append({"check": name, "demand": R4(dem), "capacity": R4(cap),
                       "ratio": R4(dem / cap if cap else math.inf), "clause": clause})
    if kind == "CJP":
        Ag = t * L
        if Tn:
            row("CJP tension = base metal yield", Tn, dsg(Fy * Ag, 0.90, 1.67), "AISC 360-22 J2.4, Table J2.5")
        if V:
            row("CJP shear = base metal shear yield", V, dsg(0.6 * Fy * Ag, 1.00, 1.50),
                "AISC 360-22 J2.4, Table J2.5 / J4.2")
        findings.append(finding("advisory", "CJP: confirm prequalified joint detail, backing/backgouge "
                                "and UT/RT acceptance - AWS D1.1 prequalified CJP joints",
                                "AWS D1.1 prequalified CJP groove welds"))
    elif kind == "PJP":
        E = float(need(inp, "throat"))
        emin = min_pjp_throat(t)
        if E < emin - 1e-9:
            findings.append(finding("violation", f"PJP effective throat {_frac(E)} below Table J2.3 "
                                    f"minimum {_frac(emin)}", "AISC 360-22 J2.1, Table J2.3"))
        Awe = E * L
        if Tn:
            row("PJP tension normal to axis (weld)", Tn, dsg(0.6 * FEXX * Awe, 0.80, 1.88),
                "AISC 360-22 J2.4, Table J2.5")
            row("PJP tension (base metal)", Tn, dsg(Fu * t * L, 0.75, 2.00), "AISC 360-22 J4.1(b)")
        if V:
            row("PJP shear (weld)", V, dsg(0.6 * FEXX * Awe, 0.75, 2.00), "AISC 360-22 J2.4, Table J2.5")
        findings.append(finding("advisory", "PJP: effective throat depends on groove angle, process "
                                "and position (AWS D1.1 prequalified PJP table) - confirm E on the WPS",
                                "AWS D1.1 prequalified PJP groove welds"))
    else:
        raise InputError("groove weld type must be CJP or PJP")
    gov = max(checks, key=lambda c: c["ratio"]) if checks else {"check": "-", "ratio": 0.0}
    out = {"type": kind, "checks": checks, "findings": findings,
           "governingCheck": gov["check"], "governingRatio": gov["ratio"]}
    bad = gov["ratio"] > 1.0 or any(f["severity"] == "violation" for f in findings)
    return result("structural.groove-weld", out, "fail" if bad else "pass")


def constructability(assembly: dict) -> List[dict]:
    """Rule-based constructability review of a resolved assembly dict:
    {"arms": [{"shape", ...}], "columnShape", "weldSize", "baseplate": {...},
     "connections": {"armToColumn": "shop-weld"|"field-weld"|"bolted"}}"""
    out: List[dict] = []
    shapes = [a.get("shape", "") for a in assembly.get("arms", [])] + [assembly.get("columnShape") or ""]
    fams = {(_family(s)) for s in shapes if s}
    if len(fams) > 2:
        out.append(finding("constructability", f"{len(fams)} different shape families "
                           f"({', '.join(sorted(fams))}) in one support - fewer families means "
                           "fewer cut lists and less fit-up variety", "fabrication practice"))
    bp = assembly.get("baseplate") or {}
    tp = bp.get("plateThickness")
    if tp and abs(tp * 8 - round(tp * 8)) > 1e-6:
        out.append(finding("constructability", f"Base plate {tp:g} in is not a 1/8 in increment - "
                           "order the next standard plate", "plate stock practice"))
    da = bp.get("anchorDiameter")
    if da and da < 0.625:
        out.append(finding("advisory", f"{_frac(da)} anchors: 5/8 in minimum is customary for "
                           "structural column bases (handling and erection loads)",
                           "AISC Design Guide 1 practice"))
    if da and bp.get("anchorEdgeDistance") and bp["anchorEdgeDistance"] < 6 * da and \
            bp.get("anchorType", "cast-in") == "cast-in":
        out.append(finding("advisory", "Cast-in anchor edge distance < 6 da: check ACI 318-19 17.9.2 "
                           "minimum edge distance if the anchors will be torqued",
                           "ACI 318-19 17.9.2"))
    if (assembly.get("connections") or {}).get("armToColumn") == "field-weld":
        out.append(finding("constructability", "Arm-to-column joint welded in the field: consider "
                           "a shop-welded arm with a bolted field splice", "fabrication practice"))
    return out


def _family(label: str) -> str:
    for p in ("HSS", "PIPE", "MC", "WT", "HP", "W", "C", "L", "S", "M"):
        if label.upper().startswith(p):
            return p
    return label


def _frac(x: float) -> str:
    """Inches as a sixteenths fraction for messages: 0.3125 -> 5/16 in."""
    n = round(x * 16)
    if abs(n / 16 - x) > 1e-6:
        return f"{x:g} in"
    whole, rem = divmod(n, 16)
    if rem == 0:
        return f"{whole} in"
    g = math.gcd(rem, 16)
    f = f"{rem // g}/{16 // g}"
    return f"{whole} {f} in" if whole else f"{f} in"
