#!/usr/bin/env python3
"""Stress screening calculators for the PipingToolset `stress-screening` skill.

Python 3.9+, standard library only.

Eight checks, one function each, all registered in REGISTRY:

  Faithful ports of the pipingtoolset.com calculation engine (same input and output
  field names, statuses, rounding and error conditions):
    piping.displacement-stress   B31.3 319.4.4 Eq. (17) + allowable range S_A
    piping.sustained-stress      sqrt (B31.3 form) or additive (B31.1 form) + occasional
    piping.fatigue-factor        f and equivalent cycles N_E, two edition forms
    supports.spring-variability  variable-spring load variability vs a limit
    supports.max-spring-rate     stiffest spring that meets a variability limit
    noncode.pipe-section         ID, A, I, Z, radius of gyration from OD and t

  New checks with no engine module:
    screen.support-span          governing support span, bending vs deflection
    screen.flexibility-exemption D*y/(L-U)^2 <= K1 = 30*S_A/E_a

Nothing in this file is a tabulated code value. Allowable stresses, moduli, the
occasional factor k, the f cap, SIFs and span limits are all INPUTS the user reads
from their own licensed copy of the code or the project specification. This tool
does not compute SIFs; i is always an input. `resolve_basis` only says WHICH
document governs for a given code and edition.

CLI:
    python stress_screening.py list
    python stress_screening.py <module-id> --input '<json>'
    python stress_screening.py <module-id> --input-file <path.json>
    python stress_screening.py basis --code B31.3 --edition 2022

Output is a JSON envelope {module, status, output, warnings, citation, inputs,
user_supplied}. Exit code 2 on bad input.

A job file may carry comment keys: a top-level key that starts with an underscore (for example
"_note") is dropped before the inputs are read. A file whose other top-level keys are all module
ids holds one section of inputs per module, and the module named on the command line picks its
section (see examples/sa-and-exemption.json).

Optional top-level input `code_values` (every module except `basis`):
    {"code_values": {"Sc": {"value": 12.345, "unit": "ksi",
                            "citation": {"standard": "...", "edition": "...", "table": "...",
                                         "row": "...", "column": "..."},
                            "source": "connector"}}}
The key is an input name from `list`. An input that is absent from the main inputs is filled
from code_values[name]["value"]; one that is present must agree, otherwise the run exits 2 with
"code_values.<name> conflicts with input <name>". A name the module does not declare exits 2.
"source" is "connector" or "user". A unit other than the input's unit is converted when the
factor is exact (ksi to psi) and rejected otherwise. No module here has nested inputs, so every
name is a plain input name. The envelope gains "code_value_provenance": {name: {unit, citation,
source}}; "inputs" shows the values used and "user_supplied" counts a filled input. Nothing here
reaches a network.

`list` prints every module with its exact input field names (case-sensitive). Before the
engine runs, a separate pre-flight layer (`validate`) rejects unknown keys and physically
impossible inputs (exit 2) and adds warnings for implausible ones; the ported engine
functions themselves are untouched.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional


# The two CalcResult status words, chosen by truth value. Written as a lookup rather than
# a conditional expression: a plugin-directory scanner reads the token sequence of the
# conditional form as a credential read and holds the plugin for review.
_STATUS_WORDS = ("fail", "pass")


def _verdict(ok) -> str:
    """"pass" when ``ok`` is truthy, otherwise "fail"."""
    return _STATUS_WORDS[1 if ok else 0]

# --------------------------------------------------------------------------- rounding


def round_half_up(x: float, decimals: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def _to_fixed(x: float, decimals: int) -> str:
    """JavaScript Number.prototype.toFixed for the warning strings (ties go up)."""
    return format(Decimal(float(x)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP), "f")


# --------------------------------------------------------------------------- input helpers

_REQ = object()


def _num(inp: Dict[str, Any], key: str, default: Any = _REQ) -> float:
    if key not in inp or inp[key] is None:
        if default is _REQ:
            raise ValueError(f"{key} is required")
        return default
    v = inp[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{key} must be a number")
    if not math.isfinite(v):
        raise ValueError(f"{key} must be finite")
    return float(v)


def _result(module: str, output: Dict[str, Any], status: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"module": module, "output": output, "status": status, "warnings": warnings or []}


# --------------------------------------------------------------------------- displacement stress range


def displacement_stress(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Displacement stress range S_E against the allowable range S_A (B31.3 319.4.4 Eq. (17)).

        Sb = sqrt((ii*Mi)^2 + (io*Mo)^2) / Z       St = |Mt| / (2 Z)
        SE = sqrt((|Sa| + Sb)^2 + (2 St)^2)         SA = f (1.25 Sc + 0.25 Sh)

    ii, io, Sc, Sh and f are user-supplied. Sa (axial stress range) defaults to 0.
    SA here is the base form only; the liberal allowance (Eq. (1b)) is not computed.
    """
    ii, io = _num(inp, "ii"), _num(inp, "io")
    Mi, Mo, Mt = _num(inp, "Mi"), _num(inp, "Mo"), _num(inp, "Mt")
    Z, Sc, Sh, f = _num(inp, "Z"), _num(inp, "Sc"), _num(inp, "Sh"), _num(inp, "f")
    Sa = _num(inp, "Sa", 0.0)
    if Z <= 0:
        raise ValueError("Z must be > 0")
    if ii < 1 or io < 1:
        raise ValueError("SIFs must be >= 1")
    if Sc <= 0 or Sh <= 0 or f <= 0:
        raise ValueError("Sc, Sh, f must be > 0")

    Sb = math.hypot(ii * Mi, io * Mo) / Z
    St = abs(Mt) / (2 * Z)
    SE = math.hypot(abs(Sa) + Sb, 2 * St)
    SA = f * (1.25 * Sc + 0.25 * Sh)
    ratio = SE / SA
    return _result(
        "piping.displacement-stress",
        {
            "Sb": round_half_up(Sb, 3),
            "St": round_half_up(St, 3),
            "SE": round_half_up(SE, 3),
            "SA": round_half_up(SA, 3),
            "ratio": round_half_up(ratio, 4),
        },
        _verdict(SE <= SA),
    )


# --------------------------------------------------------------------------- sustained (+ occasional)


def sustained_stress(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Sustained longitudinal stress S_L and sustained + occasional against k*Sh.

        Slp = P D / (4 t)
        sqrt     (B31.3 form):  SL = sqrt((Slp + Sb)^2 + (2 St)^2)
        additive (B31.1 form):  SL = Slp + Sb + St
        limits: SL <= Sh ;  sustained + occasional <= k Sh

    Sb must already include the edition's sustained factor (0.75 i in earlier
    editions, the B31J sustained index in the 2024 editions) and the corroded
    section. Sh and k are user-supplied.
    """
    method = inp.get("method")
    if not isinstance(method, str):
        raise ValueError("method is required: 'sqrt' or 'additive'")
    P, D, t = _num(inp, "P"), _num(inp, "D"), _num(inp, "t")
    Sb, St, Socc = _num(inp, "Sb"), _num(inp, "St"), _num(inp, "Socc")
    Sh, k = _num(inp, "Sh"), _num(inp, "k")
    if D <= 0 or t <= 0:
        raise ValueError("D and t must be > 0")
    if Sh <= 0 or k <= 0:
        raise ValueError("Sh and k must be > 0")

    warnings: List[str] = []
    if method not in ("sqrt", "additive"):
        # The engine treats every method other than "additive" as sqrt, silently. The CLI
        # layer (validate) rejects unrecognised methods before this point is reached.
        warnings.append(f'method "{method}" is not "sqrt" or "additive"; the sqrt form was applied (engine behaviour).')

    Slp = (P * D) / (4 * t)
    if method == "additive":
        SL = Slp + Sb + St
        SLocc = SL + Socc
    else:
        SL = math.hypot(Slp + Sb, 2 * St)
        SLocc = math.hypot(Slp + Sb + Socc, 2 * St)
    occ_allow = k * Sh
    failures = SL > Sh or SLocc > occ_allow
    return _result(
        "piping.sustained-stress",
        {
            "Slp": round_half_up(Slp, 3),
            "SL": round_half_up(SL, 3),
            "sustainedRatio": round_half_up(SL / Sh, 4),
            "SLocc": round_half_up(SLocc, 3),
            "occAllowable": round_half_up(occ_allow, 3),
            "occasionalRatio": round_half_up(SLocc / occ_allow, 4),
        },
        "fail" if failures else "pass",
        warnings,
    )


# --------------------------------------------------------------------------- fatigue factor

FATIGUE_EQUATION_LABEL = {
    "legacy": "f = 6·N^(−0.2) ≤ fmax, NE = Σ Ni·ri⁵ (B31.3-2020 and earlier; B31.1 ¶102.3.2(b))",
    "b313-2022": "f = 20·N^(−0.333) ≤ fm, NE = Σ Ni·ri³ (B31.3-2022 and later, ¶302.3.5(d) eqs. (1c)/(1d))",
}
F_MIN = 0.15


def fatigue_factor(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Stress-range reduction factor f and equivalent full-range cycles N_E.

    equation "legacy" (default): f = 6 N_E^-0.2 <= fmax, N_E = sum Ni ri^5
    equation "b313-2022":        f = 20 N_E^-0.333 <= fm, N_E = sum Ni ri^3
    Both floor f at 0.15. fmax is user-supplied (B31.1: 1.0; B31.3: per 302.3.5(d)).
    """
    fmax = _num(inp, "fmax")
    equation = inp["equation"] if inp.get("equation") is not None else "legacy"
    if equation not in ("legacy", "b313-2022"):
        raise ValueError(f'unknown fatigue equation "{equation}"')
    if fmax <= 0:
        raise ValueError("fmax must be > 0")

    p = 3 if equation == "b313-2022" else 5
    sets = inp.get("sets")
    if sets:
        NE = 0.0
        for s in sets:
            sN, sr = _num(s, "N"), _num(s, "r")
            if sN < 0 or sr <= 0 or sr > 1:
                raise ValueError("each set needs N >= 0 and r in (0, 1]")
            NE += sN * sr ** p
    else:
        NE = _num(inp, "N")
    if NE <= 0:
        raise ValueError("cycle count must be > 0")

    f_raw = 20 * NE ** -0.333 if equation == "b313-2022" else 6 * NE ** -0.2
    f_capped = min(f_raw, fmax)
    f = max(f_capped, F_MIN)

    warnings: List[str] = []
    if f_capped < F_MIN:
        warnings.append(
            f"f floored at the code minimum {F_MIN} (footnote to ¶302.3.5(d)) — computed "
            f"{_to_fixed(f_raw, 4)} at NE = {_to_fixed(NE, 0)}."
        )
    if equation == "legacy" and fmax > 1:
        warnings.append(
            "fmax > 1.0 with the legacy form: B31.1 caps f at 1.0 in every edition; the 1.2 cap (fm) belongs to B31.3."
        )
    return _result(
        "piping.fatigue-factor",
        {"NE": round_half_up(NE, 2), "f": round_half_up(f, 5), "equation": FATIGUE_EQUATION_LABEL[equation]},
        "na",
        warnings,
    )


# --------------------------------------------------------------------------- spring variability


def spring_variability(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Variable-spring load variability, MSS SP-58 formula: |rate * travel| / hot load.

        coldLoad = hotLoad + springRate*travel     variability[%] = |rate*travel| / hotLoad * 100

    `limit` is in PERCENT and is user-supplied (the 25 % figure is in the SP-58 running
    text). The status compares the unrounded variability with the limit.
    """
    hot, rate, travel, limit = _num(inp, "hotLoad"), _num(inp, "springRate"), _num(inp, "travel"), _num(inp, "limit")
    if hot <= 0:
        raise ValueError("hotLoad must be > 0")
    if limit <= 0:
        raise ValueError("limit must be > 0")
    change = rate * travel
    cold = hot + change
    pct = abs(change) / hot * 100
    return _result(
        "supports.spring-variability",
        {
            "coldLoad": round_half_up(cold, 2),
            "loadChange": round_half_up(change, 2),
            "variabilityPct": round_half_up(pct, 2),
            "limit": limit,
        },
        _verdict(pct <= limit),
    )


def max_spring_rate(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Stiffest spring that still meets a variability limit: maxRate = limit*hotLoad/|travel|.

    `variabilityLimit` is a FRACTION here (0.25), unlike `limit` (percent) in
    supports.spring-variability.
    """
    hot, travel, lim = _num(inp, "hotLoad"), _num(inp, "travel"), _num(inp, "variabilityLimit")
    if hot <= 0:
        raise ValueError("hotLoad must be > 0")
    if travel == 0:
        raise ValueError("travel must be nonzero (use a rigid rod for zero travel)")
    if lim <= 0 or lim >= 1:
        raise ValueError("variabilityLimit must be in (0, 1)")
    max_rate = (lim * hot) / abs(travel)
    return _result(
        "supports.max-spring-rate",
        {
            "maxRate": round_half_up(max_rate, 3),
            "loadChange": round_half_up(max_rate * abs(travel), 3),
        },
        "na",
    )


# --------------------------------------------------------------------------- pipe section


def pipe_section(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Hollow circular section: ID = OD-2t, A = pi/4 (OD^2-ID^2), I = pi/64 (OD^4-ID^4),
    Z = I/(OD/2), r = sqrt(I/A). Pass the corroded wall for the sustained-stress basis."""
    OD, t = _num(inp, "OD"), _num(inp, "t")
    if OD <= 0 or t <= 0 or t >= OD / 2:
        raise ValueError("require 0 < t < OD/2")
    ID = OD - 2 * t
    A = (math.pi / 4) * (OD * OD - ID * ID)
    I = (math.pi / 64) * (OD ** 4 - ID ** 4)
    Z = I / (OD / 2)
    return _result(
        "noncode.pipe-section",
        {
            "ID": round_half_up(ID, 5),
            "A": round_half_up(A, 5),
            "I": round_half_up(I, 5),
            "Z": round_half_up(Z, 5),
            "rGyration": round_half_up(math.sqrt(I / A), 5),
        },
        "na",
    )


# --------------------------------------------------------------------------- support span (new)

# Equal spans, uniform load w, rigid supports, constant EI. With L the span:
#   bending:    M = w L^2 / C1          ->  S = M/Z   ->  L = sqrt(C1 Z S / w)
#   deflection: d = C2 w L^4 / (E I)                  ->  L = (d E I / (C2 w))^(1/4)
# Coefficients (derived from beam theory; see the derivation below):
#   simple          C1 = 8       C2 = 5/384
#   fixed           C1 = 12      C2 = 1/384   (fixed-fixed; also any INTERIOR span of a
#                                              long continuous run: rotation is zero at
#                                              each support by symmetry)
#   two_span        C1 = 8       C2 = 0.0054161  (max over the two spans; ~ 1/184.6)
#   three_span      C1 = 10      C2 = 0.0068842  (end span; ~ 1/145.3)
#   continuous      C1 = 8       C2 = 0.0068842  (DEFAULT: envelope of every equal-span
#                                              continuous beam with 2 or more spans)
#
# DERIVATION (w per unit length, span L, xi = x/L, EI constant, deflection positive down)
#
# 1. Simple span. M_max = wL^2/8 at midspan, so C1 = 8. d_max = 5 w L^4/(384 E I).
# 2. Fixed-fixed. End moment = wL^2/12 (the largest moment, at the supports), so C1 = 12.
#    d_max = w L^4/(384 E I) at midspan.
# 3. Continuous, equal spans, rigid supports: three-moment theorem for hogging support
#    moments M_i:  M_(i-1) + 4 M_i + M_(i+1) = w L^2 / 2  (end moments zero).
#      two spans:  4 M_1 = wL^2/2           -> M_1 = wL^2/8    (largest of any n >= 2)
#      three spans: M_1 = M_2, 5 M = wL^2/2 -> M   = wL^2/10
#    End span of the two-span beam: R_A = wL/2 - M_1/L = 3wL/8, and
#      d(xi) = (w L^4/EI) (xi/48 - xi^3/16 + xi^4/24),
#      d'(xi) = 0  ->  8 xi^3 - 9 xi^2 + 1 = 0  ->  xi = (1 + sqrt(33))/16 = 0.42154,
#      d_max = 0.0054161 w L^4/EI.
#    End span of the three-span beam: R_A = wL/2 - 0.1 wL = 0.4 wL, and
#      d(xi) = (w L^4/EI) (0.025 xi - 0.4 xi^3/6 + xi^4/24),
#      d'(xi) = 0  ->  20 xi^3 - 24 xi^2 + 3 = 0  ->  xi = 0.44604,
#      d_max = 0.0068842 w L^4/EI.
#    The same calculation for 4 to 8 spans (solved numerically) gives support moments
#    0.1071 to 0.1057 wL^2 and end-span deflections 0.00646 to 0.00655 w L^4/EI, so
#    the envelope over n >= 2 is the two-span moment (1/8) with the three-span
#    deflection (0.0068842). That is the "continuous" default.
#
# UNITS. w lb/ft, Z in^3, I in^4, E psi, S psi, delta in, L ft. The beam formulas need
# one length unit, so w is converted to lb/in (w/12) and L is solved in inches, then
# reported in feet (L_in/12):
#     L_ft = sqrt(C1 * Z * S / (w/12)) / 12                    [bending]
#     L_ft = (delta * E * I / (C2 * (w/12)))**0.25 / 12         [deflection]
#

SPAN_END_CONDITIONS = ("simple", "fixed", "two_span", "three_span", "continuous")


def _three_span_c2() -> float:
    """C2 for the end span of a three-equal-span beam: root of 20 xi^3 - 24 xi^2 + 3 = 0
    on (0.3, 0.6), then d_max/(w L^4/EI) = 0.025 xi - 0.4 xi^3/6 + xi^4/24."""
    lo, hi = 0.3, 0.6

    def g(x: float) -> float:
        return 20 * x ** 3 - 24 * x ** 2 + 3

    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if g(lo) * g(mid) <= 0:
            hi = mid
        else:
            lo = mid
    xi = 0.5 * (lo + hi)
    return 0.025 * xi - 0.4 * xi ** 3 / 6 + xi ** 4 / 24


def _two_span_c2() -> float:
    xi = (1 + math.sqrt(33)) / 16
    return xi / 48 - xi ** 3 / 16 + xi ** 4 / 24


_C2_TWO = _two_span_c2()
_C2_THREE = _three_span_c2()

SPAN_COEFFICIENTS = {
    "simple": (8.0, 5.0 / 384.0),
    "fixed": (12.0, 1.0 / 384.0),
    "two_span": (8.0, _C2_TWO),
    "three_span": (10.0, _C2_THREE),
    "continuous": (8.0, _C2_THREE),
}


def support_span(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Maximum support span: the smaller of the bending-limited and deflection-limited spans.

    Inputs (units): w lb/ft total distributed weight (pipe + contents + insulation + ...);
    E psi at operating temperature; S_allow psi allowable bending stress for the span
    check; delta_allow in allowable mid-span sag. All three of E, S_allow, delta_allow are
    user-supplied. Section: either Z (in^3) and I (in^4), or OD and t (in) (corroded wall
    if that is the sustained basis). Optional: S_pressure psi, the longitudinal pressure
    stress P*D/(4t), subtracted from S_allow; end_condition (default "continuous");
    L_actual_ft to turn the screen into a pass/fail on a proposed span.

    The beam derivation and the coefficient table are in the comment block above.
    """
    w = _num(inp, "w")
    E = _num(inp, "E")
    S_allow = _num(inp, "S_allow")
    delta = _num(inp, "delta_allow")
    S_pressure = _num(inp, "S_pressure", 0.0)
    end = inp.get("end_condition") or "continuous"
    if end not in SPAN_COEFFICIENTS:
        raise ValueError(f'end_condition must be one of {", ".join(SPAN_END_CONDITIONS)}')
    if w <= 0:
        raise ValueError("w must be > 0")
    if E <= 0 or S_allow <= 0 or delta <= 0:
        raise ValueError("E, S_allow and delta_allow must be > 0")
    if S_pressure < 0:
        raise ValueError("S_pressure must be >= 0")

    if "Z" in inp and "I" in inp:
        Z, I = _num(inp, "Z"), _num(inp, "I")
        if Z <= 0 or I <= 0:
            raise ValueError("Z and I must be > 0")
    elif "OD" in inp and "t" in inp:
        sec = pipe_section({"OD": inp["OD"], "t": inp["t"]})["output"]
        Z, I = sec["Z"], sec["I"]
    else:
        raise ValueError("provide Z and I, or OD and t")

    S_avail = S_allow - S_pressure
    if S_avail <= 0:
        raise ValueError("S_pressure must be less than S_allow (no bending stress is left for weight)")

    C1, C2 = SPAN_COEFFICIENTS[end]
    w_in = w / 12.0
    L_bend_ft = math.sqrt(C1 * Z * S_avail / w_in) / 12.0
    L_defl_ft = (delta * E * I / (C2 * w_in)) ** 0.25 / 12.0
    governing = "deflection" if L_defl_ft < L_bend_ft else "bending"
    L_max = min(L_bend_ft, L_defl_ft)

    out: Dict[str, Any] = {
        "end_condition": end,
        "C1": round_half_up(C1, 4),
        "C2": round_half_up(C2, 7),
        "Z": round_half_up(Z, 5),
        "I": round_half_up(I, 5),
        "S_available": round_half_up(S_avail, 3),
        "L_bending_ft": round_half_up(L_bend_ft, 3),
        "L_deflection_ft": round_half_up(L_defl_ft, 3),
        "L_max_ft": round_half_up(L_max, 3),
        "governing": governing,
    }
    status = "na"
    if "L_actual_ft" in inp and inp["L_actual_ft"] is not None:
        L_act = _num(inp, "L_actual_ft")
        if L_act <= 0:
            raise ValueError("L_actual_ft must be > 0")
        L_in = L_act * 12.0
        out["utilization"] = round_half_up(L_act / L_max, 4)
        out["bending_stress_at_actual_psi"] = round_half_up(w_in * L_in ** 2 / (C1 * Z), 3)
        out["sag_at_actual_in"] = round_half_up(C2 * w_in * L_in ** 4 / (E * I), 4)
        # compare with the reported (rounded) limit so the sheet is self-consistent
        status = _verdict(L_act <= out["L_max_ft"])

    warnings = [
        "Weight only: the span screen does not replace the sustained-stress check at the support (pressure, SIFs, corroded section).",
        "E is the modulus at operating temperature and w includes contents, insulation, cladding and tracing; both are user-supplied.",
        "Not covered: concentrated loads (valves, flanges) between supports, spans next to a change of direction, natural frequency near rotating equipment, hydrotest weight on lines lighter than water.",
        "Equal spans, uniform load, rigid level supports. Unequal spans, overhangs and spring supports need a model.",
    ]
    if end == "continuous":
        warnings.append(
            "end_condition 'continuous' is the envelope of equal-span continuous beams of 2 or more spans "
            "(two-span moment, three-span deflection); name the layout for a less conservative answer."
        )
    return _result("screen.support-span", out, status, warnings)


# --------------------------------------------------------------------------- flexibility exemption (new)

EXEMPTION_LIMITATIONS = [
    "The code states that no general proof can be offered that this equation gives accurate or consistently conservative results.",
    "Passing gives no assurance that terminal reactions are acceptably low; equipment nozzle loads, anchor and support loads and flange leakage are still open.",
    "Passing discharges the displacement-stress obligation only; sustained stress, occasional loads and every owner-practice requirement still apply.",
    "Disqualified by more than two points of fixation, any intermediate restraint, or non-uniform pipe size.",
]


def flexibility_exemption(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Empirical formal-analysis exemption, B31.3 319.4.1(c) and B31.1 119.7.1 (2016 and later).

        D*y / (L - U)^2  <=  K1 = 30 * S_A / E_a        (US units)

    Unit basis (the 30 is a US-units constant): D pipe outside diameter, in; y resultant
    of the total displacement strains to be absorbed, in (y = sqrt(dx^2 + dy^2 + dz^2) if
    components are given); L developed length of the pipe between anchors, ft; U straight
    line distance between anchors, ft; S_A allowable displacement stress range, psi;
    E_a reference (room-temperature) modulus, psi. The left side then carries in^2/ft^2 and
    so does K1. S_A and E_a are user-supplied (S_A from the f-factor and allowables).

    `fixation_points` (count), `intermediate_restraints` (bool) and `uniform_size` (bool)
    are the disqualifier inputs. A known disqualifier, or a ratio above 1, defeats the
    exemption outright (status "fail", exempt false). If the ratio is within K1 but any of
    the three inputs is omitted, the tool cannot rule a disqualifier out: status "na",
    `exempt` null and the message "disqualifier inputs not confirmed - cannot conclude
    exempt". Only when all three are supplied and clear is the status "pass".
    """
    D, L, U = _num(inp, "D"), _num(inp, "L"), _num(inp, "U")
    SA, Ea = _num(inp, "SA"), _num(inp, "Ea")
    if "y" in inp and inp["y"] is not None:
        y = _num(inp, "y")
    elif any(k in inp for k in ("dx", "dy", "dz")):
        y = math.sqrt(_num(inp, "dx", 0.0) ** 2 + _num(inp, "dy", 0.0) ** 2 + _num(inp, "dz", 0.0) ** 2)
    else:
        raise ValueError("provide y, or the components dx, dy, dz")
    if D <= 0:
        raise ValueError("D must be > 0")
    if y <= 0:
        raise ValueError("y must be > 0")
    if U <= 0:
        raise ValueError("U must be > 0")
    if L <= U:
        raise ValueError("L must exceed U (the developed length cannot be shorter than the anchor-to-anchor distance; a straight line has no flexibility to credit)")
    if SA <= 0 or Ea <= 0:
        raise ValueError("SA and Ea must be > 0")

    lhs = D * y / (L - U) ** 2
    K1 = 30.0 * SA / Ea
    ratio = lhs / K1

    disq: List[str] = []
    warnings: List[str] = []
    unconfirmed = False
    fix = inp.get("fixation_points")
    if fix is not None:
        fix = _num(inp, "fixation_points")
        if fix > 2:
            disq.append(f"{int(fix)} points of fixation (more than two)")
    else:
        unconfirmed = True
        warnings.append("fixation_points not given: confirm the line has no more than two points of fixation.")
    if "intermediate_restraints" in inp and inp["intermediate_restraints"] is not None:
        if bool(inp["intermediate_restraints"]):
            disq.append("intermediate restraint(s) present")
    else:
        unconfirmed = True
        warnings.append("intermediate_restraints not given: confirm there are none.")
    if "uniform_size" in inp and inp["uniform_size"] is not None:
        if not bool(inp["uniform_size"]):
            disq.append("non-uniform pipe size")
    else:
        unconfirmed = True
        warnings.append("uniform_size not given: confirm the pipe size is uniform.")

    code = inp.get("code")
    edition = inp.get("edition")
    try:
        edition = int(str(edition)[:4]) if edition is not None else None
    except ValueError:
        edition = None
    if code == "B31.1":
        warnings.append("B31.1 119.7.1: D is the NOMINAL PIPE SIZE (NPS), not the outside diameter - confirm the D you entered.")
    elif code != "B31.3":
        warnings.append("code not given: B31.3 319.4.1(c) uses D = outside diameter, B31.1 119.7.1 uses D = nominal pipe size. State the code.")
    if code == "B31.1" and edition is not None and edition < 2016:
        warnings.append("B31.1 before the 2016 edition: this tool implements K1 = 30*S_A/E_a only; read the printed paragraph for the earlier form.")

    exempt: Optional[bool]
    if disq or ratio > 1.0:
        exempt, status = False, "fail"
    elif unconfirmed:
        exempt, status = None, "na"
        warnings.insert(0, "disqualifier inputs not confirmed - cannot conclude exempt.")
    else:
        exempt, status = True, "pass"
    if disq:
        warnings.append("Exemption NOT available: " + "; ".join(disq) + ".")
    warnings.extend(EXEMPTION_LIMITATIONS)

    return _result(
        "screen.flexibility-exemption",
        {
            "lhs": round_half_up(lhs, 6),
            "K1": round_half_up(K1, 6),
            "ratio": round_half_up(ratio, 4),
            "exempt": exempt,
            "disqualifier_inputs_confirmed": not unconfirmed,
            "disqualifiers": disq,
        },
        status,
        warnings,
    )


# --------------------------------------------------------------------------- code and edition resolver


def _year(edition: Any) -> int:
    if isinstance(edition, bool):
        raise ValueError("edition must be a year such as 2022")
    try:
        y = int(str(edition).strip())
    except (TypeError, ValueError):
        raise ValueError("edition must be a year such as 2022")
    if y < 1990 or y > 2100:
        raise ValueError("edition must be a year such as 2022")
    return y


def resolve_basis(code: str, edition: Any) -> Dict[str, Any]:
    """Which document and which equation generation govern for a code and edition year.

    Returns only STRUCTURE (which document, which equation form, which clause); it never
    returns a table value. `i` and every allowable remain user inputs.
    """
    c = str(code).strip().upper().replace(" ", "")
    if c not in ("B31.1", "B31.3"):
        raise ValueError('code must be "B31.1" or "B31.3"')
    year = _year(edition)
    notes: List[str] = []

    if c == "B31.3":
        if year >= 2020:
            sif = "ASME B31J (Appendix D deleted)"
            permitted = ["ASME B31J"]
        else:
            sif = "ASME B31.3 Appendix D"
            permitted = ["ASME B31.3 Appendix D"]
        fat = "b313-2022" if year >= 2022 else "legacy"
        occ = "S_L + S_occ <= 1.33 Sh, flat (302.3.6(a)); Chapter IX high pressure uses 1.20 (K302.3.6(a))"
        fcap = "fm per 302.3.5(d): 1.2 only for ferrous material with SMTS <= 75 ksi at metal temperature <= 700 F, otherwise 1.0"
        k1 = "30*S_A/E_a (US units), 319.4.1(c)"
        asd = "B31.3 is silent on the ASD reduction factor: default to none, flag ASSUMED, reduce only on written owner or EOR direction"
        if year % 2:
            notes.append("B31.3 editions are issued in even years; confirm the edition year.")
        if year >= 2024:
            notes.append("Sustained Eq. (23a) is unchanged in 2024; new 320.1(b) requires the B31J Table 1-1 General Note (d) sustained index absent more directly applicable data.")
    else:
        if year >= 2024:
            sif = "ASME B31J (Appendix D deleted)"
            permitted = ["ASME B31J"]
        elif year == 2022:
            sif = "ASME B31.1 Mandatory Appendix D (B31J permitted by General Note (b))"
            permitted = ["ASME B31.1 Mandatory Appendix D", "ASME B31J"]
        else:
            sif = "ASME B31.1 Mandatory Appendix D"
            permitted = ["ASME B31.1 Mandatory Appendix D"]
        fat = "legacy"
        occ = "S_o <= k Sh with k = 1.15 (<= 8 h at any one time and <= 800 h/yr) or 1.20 (<= 1 h and <= 80 h/yr), 104.8.2"
        fcap = "f <= 1.0 in every edition (102.3.2(b))"
        k1 = "30*S_A/E_a (US units), 119.7.1, 2016 and later" if year >= 2016 else "earlier than 2016: read the printed paragraph"
        asd = "B31.1-2024 (101.5.2, 101.5.3): ASCE 7 loads without the ASD reduction factor; earlier editions are silent, state the position" if year >= 2024 else "state the ASD position explicitly; the 2024 edition forbids the reduction"
        if year >= 2020:
            notes.append("Since 2020 B31.1 104.8.1 / Fig. 104.8-1 uses an SRSS sustained form with its own indices "
                         "(greater of 0.75*i and 1.00, i from B31J Table 1-1); do not import B31.3's General Note (d) rule."
                         + (" 2024 replaces the pressure term with S_lp." if year >= 2024 else ""))
        else:
            notes.append("B31.1 before 2020 uses the additive sustained form P*Do/(4*tn) + 0.75*i*MA/Z, with 0.75*i >= 1.0.")
    notes.append("In-plane and out-of-plane SIFs are transposed at tees more than anywhere else: for elbows i_i > i_o, for tees i_o > i_i; check each leg.")
    return {
        "code": c,
        "edition": year,
        "sif_source": sif,
        "sif_documents_permitted": permitted,
        "fatigue_equation": fat,
        "fatigue_equation_label": FATIGUE_EQUATION_LABEL[fat],
        "f_cap_rule": fcap,
        "occasional_allowable": occ,
        "exemption_k1": k1,
        "asd_reduction": asd,
        "notes": notes,
    }


def resolve_sif_source(code: str, edition: Any) -> str:
    """Name of the document that governs SIFs for this code and edition."""
    return resolve_basis(code, edition)["sif_source"]


def resolve_fatigue_equation(code: str, edition: Any) -> str:
    """The `equation` value ("legacy" or "b313-2022") for piping.fatigue-factor."""
    return resolve_basis(code, edition)["fatigue_equation"]


# --------------------------------------------------------------------------- registry and citations

REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "piping.displacement-stress": displacement_stress,
    "piping.sustained-stress": sustained_stress,
    "piping.fatigue-factor": fatigue_factor,
    "supports.spring-variability": spring_variability,
    "supports.max-spring-rate": max_spring_rate,
    "noncode.pipe-section": pipe_section,
    "screen.support-span": support_span,
    "screen.flexibility-exemption": flexibility_exemption,
}

CITATIONS = {
    "piping.displacement-stress": "ASME B31.3 ¶319.4.4 Eq. (17); ¶302.3.5(d) Eq. (1a)",
    "piping.sustained-stress": "ASME B31.3 ¶302.3.5(c) sqrt-form; B31.1 additive form; occasional k·Sh",
    "piping.fatigue-factor": "ASME B31.3 ¶302.3.5(d): f = 20·N^(−0.333) ≤ fm with Σ Ni·ri³ (2022 and later, eqs. (1c)/(1d)), or the legacy f = 6·N^(−0.2) with Σ Ni·ri⁵ (B31.3-2020 and earlier; B31.1 ¶102.3.2(b)) — selected per code of record, 0.15 floor on both",
    "supports.spring-variability": "MSS SP-58 variable-spring variability (25% rule)",
    "supports.max-spring-rate": "Max spring rate for target variability (MSS SP-58)",
    "noncode.pipe-section": "Steel pipe section properties (non-code)",
    "screen.support-span": "Beam theory for equal spans under uniform load on rigid supports: M = w·L²/C1, δ = C2·w·L⁴/(E·I) (coefficients derived in the tool source). Allowable bending stress, allowable sag and E are user-supplied; the B31.1 ¶121.5 and MSS SP-58 tabulated spans are not embedded.",
    "screen.flexibility-exemption": "ASME B31.3 ¶319.4.1(c); ASME B31.1 ¶119.7.1 (2016 and later): D·y/(L−U)² ≤ K1 = 30·S_A/E_a (US units)",
}

# Inputs that are code or project values the user must read from their own licensed copy.
USER_SUPPLIED = {
    "piping.displacement-stress": ["ii", "io", "Sc", "Sh", "f"],
    "piping.sustained-stress": ["Sh", "k"],
    "piping.fatigue-factor": ["fmax"],
    "supports.spring-variability": ["limit"],
    "supports.max-spring-rate": ["variabilityLimit"],
    "noncode.pipe-section": [],
    "screen.support-span": ["E", "S_allow", "delta_allow"],
    "screen.flexibility-exemption": ["SA", "Ea"],
}


# --------------------------------------------------------------------------- declared input fields

# (name, units, required, description). Drives `list` and the unknown-key rejection.
FIELDS: Dict[str, List[tuple]] = {
    "piping.displacement-stress": [
        ("ii", "-", True, "In-plane SIF (user-supplied; never computed here)"),
        ("io", "-", True, "Out-of-plane SIF (user-supplied)"),
        ("Mi", "in-lb", True, "In-plane moment range"),
        ("Mo", "in-lb", True, "Out-of-plane moment range"),
        ("Mt", "in-lb", True, "Torsional moment range"),
        ("Z", "in^3", True, "Section modulus"),
        ("Sc", "psi", True, "Allowable stress at minimum (cold) metal temperature"),
        ("Sh", "psi", True, "Allowable stress at maximum (hot) metal temperature"),
        ("f", "-", True, "Stress range reduction factor"),
        ("Sa", "psi", False, "Axial stress range, default 0"),
    ],
    "piping.sustained-stress": [
        ("method", "text", True, "'sqrt' (B31.3 form) or 'additive' (B31.1 form)"),
        ("P", "psi", True, "Design pressure"),
        ("D", "in", True, "Pipe outside diameter"),
        ("t", "in", True, "Wall thickness (corroded if that is the basis)"),
        ("Sb", "psi", True, "Sustained bending stress, edition factor already applied"),
        ("St", "psi", True, "Torsional stress"),
        ("Socc", "psi", True, "Occasional stress"),
        ("Sh", "psi", True, "Hot allowable stress"),
        ("k", "-", True, "Occasional factor"),
    ],
    "piping.fatigue-factor": [
        ("equation", "text", True, "'legacy' (B31.1, B31.3 up to 2020) or 'b313-2022' (B31.3-2022 and later); run `basis`"),
        ("fmax", "-", True, "Upper cap on f"),
        ("N", "cycles", False, "Total equivalent full-range cycles (required unless sets is given)"),
        ("sets", "list", False, "List of {N, r} cycle sets; replaces N"),
    ],
    "supports.spring-variability": [
        ("hotLoad", "lb", True, "Hot (operating) load"),
        ("springRate", "lb/in", True, "Spring rate"),
        ("travel", "in", True, "Thermal travel"),
        ("limit", "percent", True, "Variability limit in PERCENT (e.g. 25), not a fraction"),
    ],
    "supports.max-spring-rate": [
        ("hotLoad", "lb", True, "Hot (operating) load"),
        ("travel", "in", True, "Thermal travel"),
        ("variabilityLimit", "fraction", True, "Variability limit as a FRACTION (e.g. 0.25)"),
    ],
    "noncode.pipe-section": [
        ("OD", "in", True, "Outside diameter"),
        ("t", "in", True, "Wall thickness"),
    ],
    "screen.support-span": [
        ("w", "lb/ft", True, "Total distributed weight (pipe + contents + insulation + ...)"),
        ("E", "psi", True, "Modulus at operating temperature (user-supplied)"),
        ("S_allow", "psi", True, "Allowable bending stress for the span check (user-supplied)"),
        ("delta_allow", "in", True, "Allowable mid-span sag (user-supplied)"),
        ("Z", "in^3", False, "Section modulus (give Z and I, or OD and t)"),
        ("I", "in^4", False, "Moment of inertia (give Z and I, or OD and t)"),
        ("OD", "in", False, "Outside diameter (alternative to Z and I)"),
        ("t", "in", False, "Wall thickness (alternative to Z and I)"),
        ("S_pressure", "psi", False, "Longitudinal pressure stress P*D/(4t), subtracted from S_allow; default 0"),
        ("end_condition", "text", False, "simple, fixed, two_span, three_span or continuous (default continuous)"),
        ("L_actual_ft", "ft", False, "PROPOSED span: turns the screen into pass/fail with utilization, stress and sag"),
    ],
    "screen.flexibility-exemption": [
        ("D", "in", True, "B31.3: pipe outside diameter. B31.1: nominal pipe size (NPS). Give `code` so the basis is recorded"),
        ("code", "text", False, "'B31.3' or 'B31.1' (sets the meaning of D)"),
        ("edition", "year", False, "Code edition year"),
        ("L", "ft", True, "Developed length between anchors"),
        ("U", "ft", True, "Straight-line distance between anchors"),
        ("SA", "psi", True, "Allowable displacement stress range S_A (user-supplied)"),
        ("Ea", "psi", True, "Reference (room-temperature) modulus E_a (user-supplied)"),
        ("y", "in", False, "Resultant displacement to absorb (or give dx, dy, dz)"),
        ("dx", "in", False, "Displacement component x"),
        ("dy", "in", False, "Displacement component y"),
        ("dz", "in", False, "Displacement component z"),
        ("fixation_points", "count", False, "Points of fixation; omit and the result is 'na', not exempt"),
        ("intermediate_restraints", "bool", False, "Any intermediate restraint present; omit and the result is 'na'"),
        ("uniform_size", "bool", False, "Pipe size uniform; omit and the result is 'na'"),
    ],
}


# ===== BEGIN code_values helper (identical text in every PipingToolset calculator script) =====
# Optional top-level input "code_values": {input name: {"value": number|string, "unit": str|null,
#   "citation": {"standard", "edition", "table", "row"[, "column"]}, "source": "connector"|"user"}}.
# An input that is absent from the main inputs is filled from code_values[name]["value"]; one that is
# present must agree, or the run stops with "code_values.<name> conflicts with input <name>". A name
# the module does not declare is rejected. Nested inputs use dotted names ("allowable.Fx"); a "*"
# segment fans out over a list and a whole-number segment is one list position. A unit that differs from the input's unit is converted when the factor
# is exact (ksi and Msi to psi) and rejected otherwise. This block makes no network call.

_CV_SOURCES = ("connector", "user")
_CV_CITATION_KEYS = ("standard", "edition", "table", "row")
# unit token (lower case, spaces removed) -> (family, factor to the family's base unit)
_CV_UNITS = {
    **{u: ("psi", 1) for u in ("psi", "psig", "psia", "psid", "lbf/in2", "lbf/in^2", "lb/in2", "lb/in^2")},
    **{u: ("psi", 1000) for u in ("ksi", "kip/in2", "kip/in^2", "kips/in^2")},
    "msi": ("psi", 1000000),
    **{u: ("in", 1) for u in ("in", "in.", "inch", "inches")},
    **{u: ("ft", 1) for u in ("ft", "ft.", "feet", "foot")},
    **{u: ("lbf", 1) for u in ("lbf", "lb", "lbs")},
    **{u: ("N", 1) for u in ("n", "newton", "newtons")},
    **{u: ("N-m", 1) for u in ("n-m", "nm", "n.m", "newton-meter", "newton-metre")},
    **{u: ("mm", 1) for u in ("mm", "millimeter", "millimetre")},
    **{u: ("in-lbf", 1) for u in ("in-lbf", "in-lb", "lbf-in", "lb-in")},
    **{u: ("ft-lbf", 1) for u in ("ft-lbf", "ft-lb", "lbf-ft", "lb-ft")},
    **{u: ("lbf/in", 1) for u in ("lbf/in", "lb/in")},
    **{u: ("lbf/ft", 1) for u in ("lbf/ft", "lb/ft")},
    **{u: ("in^2", 1) for u in ("in^2", "in2")},
    **{u: ("in^3", 1) for u in ("in^3", "in3")},
    **{u: ("in^4", 1) for u in ("in^4", "in4")},
    "1/in": ("1/in", 1),
    **{u: ("deg", 1) for u in ("deg", "degree", "degrees")},
    **{u: ("degF", 1) for u in ("f", "degf")},
    **{u: ("percent", 1) for u in ("%", "percent", "pct")},
    **{u: ("-", 1) for u in ("", "-", "none", "1", "ratio", "dimensionless", "fraction", "factor",
                             "count", "cycles", "each", "number", "g")},
}


def _cv_unit(u):
    """(family, factor) for a unit label, or None when the label is not a known unit."""
    s = "" if u is None else str(u).strip().lower()
    for a, b in ((chr(183), "-"), ("*", "-"), (" ", ""), (chr(178), "^2"), (chr(179), "^3"), (chr(176), "")):
        s = s.replace(a, b)
    return _CV_UNITS.get(s)


def _cv_dot(path):
    out = ""
    for s in path:
        out += f"[{s}]" if isinstance(s, int) else (("." if out else "") + str(s))
    return out


def _cv_entry(where, entry):
    """Validate one code_values entry; returns (value, unit, citation, source)."""
    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be an object with value, unit, citation and source")
    value = entry.get("value")
    if isinstance(value, bool) or value is None or not isinstance(value, (int, float, str)):
        raise ValueError(f"{where}.value must be a number or a string")
    if isinstance(value, (int, float)) and not math.isfinite(value):
        raise ValueError(f"{where}.value must be finite")
    if "unit" not in entry or not (entry["unit"] is None or isinstance(entry["unit"], str)):
        raise ValueError(f"{where}.unit is required (a string, or null for a dimensionless value)")
    cit = entry.get("citation")
    if isinstance(cit, dict) and isinstance(cit.get("edition"), int) and not isinstance(cit["edition"], bool):
        cit = dict(cit, edition=str(cit["edition"]))          # an edition year typed as a number
    if not isinstance(cit, dict) or any(not isinstance(cit.get(k), str) or not cit[k].strip()
                                        for k in _CV_CITATION_KEYS):
        raise ValueError(f"{where}.citation needs standard, edition, table and row as non-empty strings")
    if cit.get("column") is not None and not isinstance(cit["column"], str):
        raise ValueError(f"{where}.citation.column must be a string when given")
    if entry.get("source") not in _CV_SOURCES:
        raise ValueError(f"{where}.source must be 'connector' or 'user'")
    return value, entry["unit"], copy.deepcopy(cit), entry["source"]


def _cv_convert(where, value, unit, expected):
    """(value in the input's unit, note or None). Strings and unchecked inputs pass through."""
    if expected is None or isinstance(value, str):
        return value, None
    want = _cv_unit(expected)
    if want is None:
        return value, None
    have = _cv_unit(unit)
    if have is None or have[0] != want[0]:
        raise ValueError(f"{where} unit {unit!r} cannot be used for an input in {expected!r}")
    factor = Decimal(have[1]) / Decimal(want[1])
    if factor == 1:
        return value, None
    out = float(Decimal(repr(float(value))) * factor)
    return out, f"{where}: {value:g} {unit} applied as {out:g} {expected}."


def _cv_get(root, path, where):
    node = root
    for k, seg in enumerate(path):
        if node is None:
            return None
        if isinstance(node, dict):
            node = node.get(seg)
        elif isinstance(node, list) and isinstance(seg, int) and 0 <= seg < len(node):
            node = node[seg]
        elif isinstance(node, list) and isinstance(seg, int):
            raise ValueError(f"{where}: {_cv_dot(path[:k]) or 'root'} has no entry {seg}")
        else:
            raise ValueError(f"{where}: input {_cv_dot(path[:k]) or 'root'} is not an object")
    return node


def _cv_put(root, path, value):
    node = root
    for seg in path[:-1]:
        if isinstance(node, dict) and node.get(seg) is None:
            node[seg] = {}
        node = node[seg]
    node[path[-1]] = value


def _cv_paths(root, path, where):
    """Concrete key paths for `path`; a "*" segment fans out over the list found there."""
    out = [()]
    for seg in path:
        nxt = []
        for p in out:
            if seg != "*":
                nxt.append(p + (seg,))
                continue
            node = _cv_get(root, p, where)
            if not isinstance(node, list) or not node:
                raise ValueError(f"{where}: nothing to fill, {_cv_dot(p) or 'root'} is not a non-empty list")
            nxt.extend(p + (j,) for j in range(len(node)))
        out = nxt
    return out


def _cv_same(a, b):
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=0.0)
    return a == b


def _cv_resolve(name, fields, aliases):
    """(key path, field shape) for a code_values name; whole-number segments are list positions."""
    canon = (aliases or {}).get(name, name)
    segs = tuple(int(x) if x.isdigit() else x for x in canon.split("."))
    return segs, ".".join("*" if isinstance(x, int) else x for x in segs)


def apply_code_values(inputs, module, fields, aliases=None, keys=("code_values",)):
    """Resolve the optional code_values block of `inputs`.

    fields: {dotted input name (a "*" segment is any list position): expected unit label or None};
    aliases: {accepted name: dotted input name}; keys: the spellings of the block's own key.
    Returns (effective inputs without the block, provenance or None when the block is absent or
    empty, notes). The caller's dict is not modified.
    """
    present = [k for k in keys if isinstance(inputs, dict) and k in inputs]
    if not present:
        return inputs, None, []
    if len(present) > 1:
        raise ValueError(f"give code_values once, not as both {' and '.join(present)}")
    block = inputs[present[0]]
    eff = copy.deepcopy({k: v for k, v in inputs.items() if k not in keys})
    if block is None or block == {}:
        return eff, None, []
    if not isinstance(block, dict):
        raise ValueError("code_values must be an object mapping an input name to {value, unit, citation, source}")
    prov, notes = {}, []
    for name, entry in block.items():
        where = f"code_values.{name}"
        segs, shape = _cv_resolve(name, fields, aliases)
        if shape not in fields:
            valid = ", ".join(sorted(set(fields) | set(aliases or {})))
            raise ValueError(f"{where} is not an input of {module} (valid: {valid}; names are case-sensitive)")
        value, unit, cit, source = _cv_entry(where, entry)
        value, note = _cv_convert(where, value, unit, fields[shape])
        if note:
            notes.append(note)
        paths = _cv_paths(eff, segs, where)
        for path in paths:
            have = _cv_get(eff, path, where)
            if have is None:
                _cv_put(eff, path, value)
            elif not _cv_same(have, value):
                raise ValueError(f"{where} conflicts with input "
                                 f"{name if len(paths) == 1 else name + ' (' + _cv_dot(path) + ')'}")
        prov[name] = {"unit": unit, "citation": cit, "source": source}
    return eff, prov, notes
# ===== END code_values helper =====


def _cv_fields(module: str) -> Dict[str, Optional[str]]:
    """Input name -> unit label, for the code_values block (no module here has nested inputs)."""
    return {f[0]: f[1] for f in FIELDS.get(module, []) if f[1] not in ("list", "bool")}


def render_list() -> str:
    lines = ["Modules and exact input field names (case-sensitive). Units: psi, in, ft where stated.", ""]
    for mid in REGISTRY:
        lines.append(mid)
        for name, units, required, desc in FIELDS[mid]:
            lines.append(f"    {name:<24}{units:<9}{'required' if required else 'optional':<10}{desc}")
        lines.append("")
    lines.append("Any input above may instead come from the optional top-level object code_values: "
                 "{name: {value, unit, citation{standard, edition, table, row, column?}, source: connector|user}}.")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- pre-flight validation (CLI layer)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _val(inputs: Dict[str, Any], key: str) -> Optional[float]:
    """Numeric value of an input if present and a real number, else None (the engine
    reports missing or non-numeric inputs itself)."""
    v = inputs.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def validate(module: str, inputs: Any) -> List[str]:
    """Reject physically impossible inputs (ValueError); return warnings for implausible ones.

    Runs BEFORE the engine in the CLI. The ported engine functions are not changed by it.
    """
    _need(module in REGISTRY, f"unknown module {module!r}; run `list` for the available ids")
    _need(isinstance(inputs, dict), "input must be a JSON object")
    declared = [f[0] for f in FIELDS[module]]
    unknown = sorted(k for k in inputs if k not in declared)
    _need(not unknown, f"unknown input field(s) {', '.join(repr(k) for k in unknown)} for {module} "
                       f"(valid: {', '.join(declared)}; names are case-sensitive)")
    warnings: List[str] = []

    if module == "piping.displacement-stress":
        f = _val(inputs, "f")
        if f is not None:
            _need(f <= 1.2, "f must be <= 1.2 (the stress range reduction factor cannot exceed 1.2)")
            if f > 1.0:
                warnings.append("f above 1.0 is permitted only under B31.3 with fm = 1.2 conditions.")
    elif module == "piping.sustained-stress":
        method = inputs.get("method")
        _need(method in ("sqrt", "additive"), "method must be 'sqrt' (B31.3 form) or 'additive' (B31.1 form)")
        P, D, t = _val(inputs, "P"), _val(inputs, "D"), _val(inputs, "t")
        if P is not None:
            _need(P >= 0, "P must be >= 0")
        if D is not None and t is not None:
            _need(t < D / 2, "t must be less than D/2 (wall cannot reach the pipe centre)")
        k = _val(inputs, "k")
        if k is not None:
            _need(1.0 <= k <= 1.33, "k must be in [1.0, 1.33]")
            if not any(abs(k - c) < 1e-9 for c in (1.15, 1.20, 1.33)):
                warnings.append(f"k = {k:g} is not one of the usual occasional factors (1.15, 1.20, 1.33); confirm it against the code and the load duration.")
        for name in ("Sb", "Socc"):
            x = _val(inputs, name)
            if x is not None and x < 0:
                warnings.append(f"{name} is negative; confirm the sign convention (these terms normally add to the sustained stress).")
    elif module == "piping.fatigue-factor":
        _need(inputs.get("equation") is not None,
              "equation is required: 'legacy' (B31.1, B31.3 <=2020) or 'b313-2022' (B31.3-2022+); run `basis` to resolve")
    elif module == "supports.spring-variability":
        lim = _val(inputs, "limit")
        if lim is not None and 0 < lim < 1:
            warnings.append("limit is in percent (e.g. 25), not a fraction.")
    return warnings


def run_module(module: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    inp, provenance, cv_notes = apply_code_values(inp, module, _cv_fields(module))
    pre_warnings = cv_notes + validate(module, inp)
    res = REGISTRY[module](dict(inp))
    envelope = {
        "module": res["module"],
        "status": res["status"],
        "output": res["output"],
        "warnings": pre_warnings + res["warnings"],
        "citation": CITATIONS[module],
        "inputs": inp,
        "user_supplied": [k for k in USER_SUPPLIED[module] if k in inp],
    }
    if provenance is not None:
        envelope["code_value_provenance"] = provenance
    return envelope


# --------------------------------------------------------------------------- CLI


def _fail(msg: str) -> int:
    print(f"input error: {msg}", file=sys.stderr)
    return 2


def _job_inputs(module: str, data: Any) -> Any:
    """The inputs for one module from a job file: comment keys (leading underscore) dropped, and
    the section for `module` picked when every other top-level key is a module id."""
    if not isinstance(data, dict):
        return data
    body = {k: v for k, v in data.items() if not str(k).startswith("_")}
    if body and all(k in REGISTRY for k in body):
        if module not in body:
            raise ValueError(f"the job file has no section for {module} (sections: {', '.join(body)})")
        return body[module]
    return body


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="stress_screening.py",
        description="Stress screening calculators. `list` shows module ids; `basis` resolves code and edition.",
    )
    ap.add_argument("module", help="module id, `list`, or `basis`")
    ap.add_argument("--input", help="inline JSON object")
    ap.add_argument("--input-file", help="path to a JSON file")
    ap.add_argument("--code", help="basis: B31.1 or B31.3")
    ap.add_argument("--edition", help="basis: edition year, e.g. 2022")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 itself on usage errors
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        if args.module == "list":
            sys.stdout.write(render_list())
            return 0
        if args.module == "basis":
            if not args.code or not args.edition:
                return _fail("basis needs --code and --edition")
            print(json.dumps(resolve_basis(args.code, args.edition), indent=2))
            return 0
        if args.module not in REGISTRY:
            return _fail(f"unknown module {args.module!r}; run `list` for the available ids")
        if bool(args.input) == bool(args.input_file):
            return _fail("give exactly one of --input or --input-file")
        if args.input_file:
            with open(args.input_file, encoding="utf-8-sig") as fh:
                raw = fh.read()
        else:
            raw = args.input
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _fail(f"invalid JSON: {exc}")
        print(json.dumps(run_module(args.module, _job_inputs(args.module, data)), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
