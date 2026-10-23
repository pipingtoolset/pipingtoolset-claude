#!/usr/bin/env python3
"""
pressure_design.py - ASME B31.1 / B31.3 pressure-design calculators.

Part of the PipingToolset skill pack (pipingtoolset.com).

WHAT THIS IS
    Seven small, deterministic calculators for the pressure-design checks that
    calc packages are most often rejected on:

        piping.b313-wall-thickness        B31.3 para. 304.1.2 Eq. (3a)
        piping.b311-wall-thickness        B31.1 para. 104.1.2 (SEW + Py family)
        piping.b31-allowable-pressure     the same equation solved for P (MAWP)
        piping.branch-reinforcement       B31.3 para. 304.3.3 area replacement
        piping.bend-thickness             B31.3 para. 304.2.1 (I-factor)
        piping.miter-allowable-pressure   B31.3 para. 304.2.3 Eq. (4a)/(4b)/(4c)
        piping.leak-test-pressure         B31.3 para. 345.4.2 / B31.1 para. 137

    They are faithful ports of the pipingtoolset.com calculation engine: same inputs,
    same output fields, same rounding, same thrown-error conditions. Each module
    is checked against the engine's own fixtures in tests/test_pressure_design.py.

LICENSING FIREWALL
    The EQUATIONS are method. The numeric inputs S (allowable stress), E (quality
    factor), W (weld strength reduction), Y / y (temperature coefficient) and the
    test-pressure allowables are CODE TABLE VALUES. This script embeds none of
    them. The user reads each from their own licensed copy and supplies it.

USAGE
    python pressure_design.py list
    python pressure_design.py list --json
    python pressure_design.py piping.b313-wall-thickness --input '{"P": 500, ...}'
    python pressure_design.py b313-wall-thickness --input-file job.json

    Exit status: 0 = calculated, 2 = bad input (one-line message on stderr).

    Before the engine runs, a separate pre-flight layer (validate) rejects
    physically impossible inputs (exit 2) and adds warnings for implausible ones.
    The engine functions themselves are untouched.

UNITS
    The engine is unit-agnostic ("consistent units"). This CLI documents and
    expects US customary: pressure and stress in psi, lengths in in., area in
    in.^2, angles in degrees, temperature (where it matters) in deg F.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Rounding - the single rounding rule for every module (matches the pipingtoolset.com calculation engine).
# --------------------------------------------------------------------------- #

def round_half_up(x: float, decimals: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def _js_num(x: float) -> str:
    """Format a number the way JavaScript's template literals do (6.0 -> '6')."""
    if isinstance(x, float) and x.is_integer() and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


# --------------------------------------------------------------------------- #
# Field metadata: drives input validation, the `list` command and `user_supplied`.
#   (name, units, required, user_supplied, description)
# --------------------------------------------------------------------------- #

Field = tuple

FIELDS: Dict[str, List[Field]] = {
    "piping.b313-wall-thickness": [
        ("P", "psi", True, False, "Internal design pressure"),
        ("D", "in", True, False, "Pipe outside diameter"),
        ("S", "psi", True, True, "Basic allowable stress at design temperature (Appendix A table, by edition)"),
        ("E", "-", True, True, "Quality factor E (Appendix A quality-factor tables, by edition)"),
        ("W", "-", True, True, "Weld joint strength reduction factor W (Table 302.3.5)"),
        ("Y", "-", True, True, "Coefficient Y (Table 304.1.1)"),
        ("c", "in", True, False, "Sum of mechanical + corrosion + erosion allowances"),
        ("millTolerance", "fraction", True, False, "Mill under-tolerance as a fraction, e.g. 0.125"),
    ],
    "piping.b311-wall-thickness": [
        ("P", "psi", True, False, "Internal design pressure"),
        ("D", "in", True, False, "Pipe outside diameter"),
        ("S", "psi", True, True, "Allowable stress at design temperature (Appendix A)"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld strength reduction factor W (para. 102.4.7); default 1.0 - confirm it applies"),
        ("y", "-", True, True, "Temperature coefficient y (Table 104.1.2(A))"),
        ("A", "in", True, False, "Additional thickness (mechanical, corrosion, erosion, threading)"),
        ("millTolerance", "fraction", True, False, "Mill under-tolerance as a fraction, e.g. 0.125"),
    ],
    "piping.b31-allowable-pressure": [
        ("D", "in", True, False, "Pipe outside diameter"),
        ("t", "in", True, False, "Nominal wall thickness"),
        ("millTolerance", "fraction", True, False, "Mill under-tolerance as a fraction"),
        ("A", "in", True, False, "Additional thickness allowance (corrosion, threading, ...)"),
        ("S", "psi", True, True, "Allowable stress at design temperature"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld joint strength reduction factor W (B31.3 Table 302.3.5-1 / B31.1 Table 102.4.7-1); default 1.0 - codes without W (B31.9, B31.12) use 1.0"),
        ("y", "-", True, True, "Temperature coefficient y / Y"),
        ("Mf", "-", True, True, "Material performance factor (B31.12 hydrogen only; 1.0 otherwise)"),
    ],
    "piping.branch-reinforcement": [
        ("Dh", "in", True, False, "Header outside diameter"),
        ("Th", "in", True, False, "Header nominal (measured) wall"),
        ("th", "in", True, False, "Header pressure-design thickness (from the wall-thickness calc)"),
        ("Db", "in", True, False, "Branch outside diameter"),
        ("Tb", "in", True, False, "Branch nominal (measured) wall"),
        ("tb", "in", True, False, "Branch pressure-design thickness (from the wall-thickness calc)"),
        ("c", "in", True, False, "Corrosion / mechanical allowance (both header and branch)"),
        ("betaDeg", "deg", True, False, "Branch angle from the header axis, 45 to 90"),
        ("Tr", "in", True, False, "Reinforcing pad thickness (0 = none)"),
        ("Dp", "in", True, False, "Reinforcing pad outside diameter (0 = none)"),
        ("A4welds", "in^2", True, False, "Additional area from welds and other metal inside the zone"),
    ],
    "piping.bend-thickness": [
        ("P", "psi", True, False, "Internal design pressure"),
        ("D", "in", True, False, "Pipe outside diameter"),
        ("R", "in", True, False, "Bend radius to the pipe centerline"),
        ("S", "psi", True, True, "Allowable stress at design temperature"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld joint strength reduction factor W; default 1.0 - confirm it applies"),
        ("y", "-", True, True, "Temperature coefficient y / Y"),
        ("A", "in", True, False, "Additional thickness allowance"),
    ],
    "piping.miter-allowable-pressure": [
        ("S", "psi", True, True, "Allowable stress at design temperature"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld joint strength reduction factor W; default 1.0 - confirm it applies"),
        ("Tc", "in", True, False, "Wall available for pressure (nominal - mill tolerance - allowances)"),
        ("r2", "in", True, False, "Mean pipe radius, (D - T)/2"),
        ("R1", "in", True, False, "Effective miter bend radius (centerline)"),
        ("thetaDeg", "deg", True, False, "Miter half-angle (angle of cut), 0 < theta < 90"),
        ("miters", "count", True, False, "Number of miter cuts (1 = single miter)"),
    ],
    "piping.leak-test-pressure": [
        ("P", "psi", True, False, "Internal design gage pressure"),
        ("ST", "psi", True, True, "Allowable stress at test temperature"),
        ("S", "psi", True, True, "Allowable stress at design temperature"),
        ("hydroFactor", "-", True, True, "Hydrostatic factor (1.5 in B31.1 and B31.3) - confirm for the edition"),
        ("stressRatioCap", "-", False, False, "OPTIONAL owner-specification ceiling on ST/S; the code sets none"),
        ("pneumaticFactor", "-", True, True, "Pneumatic factor (B31.3 / B31.1 differ) - confirm for the edition"),
        ("pneumaticMaxFactor", "-", False, True, "OPTIONAL code upper bound on pneumaticFactor, used only to warn"),
    ],
}

SHORT = {m.split(".", 1)[1]: m for m in FIELDS}


# --------------------------------------------------------------------------- #
# Input validation (shared by every module; raises ValueError).
# --------------------------------------------------------------------------- #

def _prepare(module: str, raw: Any) -> Dict[str, Optional[float]]:
    if not isinstance(raw, dict):
        raise ValueError("input must be a JSON object")
    spec = FIELDS[module]
    names = {f[0] for f in spec}
    unknown = sorted(k for k in raw if k not in names)
    if unknown:
        raise ValueError(
            f"unknown input field(s) {', '.join(repr(k) for k in unknown)} for {module} "
            f"(valid: {', '.join(f[0] for f in spec)}; names are case-sensitive)"
        )
    out: Dict[str, Optional[float]] = {}
    for name, _units, required, _us, _desc in spec:
        v = raw.get(name)
        if v is None:
            if required:
                raise ValueError(f"missing required input '{name}'")
            out[name] = None
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"input '{name}' must be a number")
        if not math.isfinite(v):
            raise ValueError(f"input '{name}' must be finite")
        out[name] = float(v)
    return out


# --------------------------------------------------------------------------- #
# The seven calculators. Each: fn(input: dict) -> {module, output, status, warnings}
# --------------------------------------------------------------------------- #

def b313_wall_thickness(input: dict) -> dict:
    """B31.3 Eq. (3a): t = P*D / (2*(S*E*W + P*Y)); tm = t + c; tOrder = tm/(1 - mill)."""
    module = "piping.b313-wall-thickness"
    v = _prepare(module, input)
    P, D, S, E, W, Y, c, millTolerance = (v[k] for k in ("P", "D", "S", "E", "W", "Y", "c", "millTolerance"))
    if D <= 0:
        raise ValueError("D must be > 0")
    if S <= 0 or E <= 0 or W <= 0:
        raise ValueError("S, E, W must be > 0")
    if millTolerance < 0 or millTolerance >= 1:
        raise ValueError("millTolerance must be in [0, 1)")

    denom = 2 * (S * E * W + P * Y)
    t = (P * D) / denom
    tm = t + c
    tOrder = tm / (1 - millTolerance)

    warnings: List[str] = []
    # Eq. 3a is the thin-wall form; B31.3 restricts it to t < D/6. Beyond that the
    # thick-wall treatment (and a different Y) applies - flag rather than silently
    # return a non-conservative number.
    if t >= D / 6:
        warnings.append("t >= D/6: outside Eq. 3a thin-wall validity; use the thick-wall method (para. 304.1.2(b)).")

    return {
        "module": module,
        "output": {
            "t": round_half_up(t, 5),
            "tm": round_half_up(tm, 5),
            "tOrder": round_half_up(tOrder, 5),
        },
        "status": "na",
        "warnings": warnings,
    }


def b311_wall_thickness(input: dict) -> dict:
    """B31.1 para. 104.1.2: tm = P*D / (2*(S*E*W + P*y)) + A; tOrder = tm/(1 - mill)."""
    module = "piping.b311-wall-thickness"
    v = _prepare(module, input)
    P, D, S, E, y, A, millTolerance = (v[k] for k in ("P", "D", "S", "E", "y", "A", "millTolerance"))
    W = v["W"] if v["W"] is not None else 1.0
    if D <= 0:
        raise ValueError("D must be > 0")
    if S <= 0 or E <= 0:
        raise ValueError("S and E must be > 0")
    if W <= 0 or W > 1:
        raise ValueError("W must be in (0, 1]")
    if millTolerance < 0 or millTolerance >= 1:
        raise ValueError("millTolerance must be in [0, 1)")

    t = (P * D) / (2 * (S * E * W + P * y))
    tm = t + A
    tOrder = tm / (1 - millTolerance)

    warnings: List[str] = []
    if t >= D / 6:
        warnings.append("t >= D/6: outside the thin-wall validity of this equation; use the code's thick-wall treatment.")

    return {
        "module": module,
        "output": {
            "t": round_half_up(t, 5),
            "tm": round_half_up(tm, 5),
            "tOrder": round_half_up(tOrder, 5),
        },
        "status": "na",
        "warnings": warnings,
    }


def b31_allowable_pressure(input: dict) -> dict:
    """Allowable pressure of straight pipe: tp = t*(1 - mill) - A; P = 2*S*E*W*Mf*tp / (D - 2*y*tp).

    W (weld joint strength reduction factor) is optional, default 1.0, rejected outside (0, 1]:
    B31.3 Eq. (3a) and B31.1 Eq. (9) carry W; B31.9 and B31.12 have no W term."""
    module = "piping.b31-allowable-pressure"
    v = _prepare(module, input)
    D, t, millTolerance, A, S, E, y, Mf = (v[k] for k in ("D", "t", "millTolerance", "A", "S", "E", "y", "Mf"))
    W = v["W"] if v.get("W") is not None else 1.0
    if D <= 0 or t <= 0:
        raise ValueError("D and t must be > 0")
    if millTolerance < 0 or millTolerance >= 1:
        raise ValueError("millTolerance must be in [0, 1)")
    if S <= 0 or E <= 0 or Mf <= 0:
        raise ValueError("S, E, Mf must be > 0")
    if not (W > 0 and W <= 1):
        raise ValueError("W must be in (0, 1]")

    tp = t * (1 - millTolerance) - A
    warnings: List[str] = []
    if tp <= 0:
        return {
            "module": module,
            "output": {"tp": round_half_up(tp, 5), "allowablePressure": 0},
            "status": "fail",
            "warnings": ["No thickness remains for pressure after mill tolerance and allowances."],
        }
    if t >= D / 6:
        warnings.append("t >= D/6: outside thin-wall validity; use the code's thick-wall rules.")

    allowablePressure = (2 * S * E * W * Mf * tp) / (D - 2 * y * tp)

    return {
        "module": module,
        "output": {
            "tp": round_half_up(tp, 5),
            "allowablePressure": round_half_up(allowablePressure, 3),
        },
        "status": "na",
        "warnings": warnings,
    }


def branch_reinforcement(input: dict) -> dict:
    """B31.3 para. 304.3.3 area replacement. PASS if A2 + A3 + A4 >= A1."""
    module = "piping.branch-reinforcement"
    v = _prepare(module, input)
    Dh, Th, th, Db, Tb, tb, c, betaDeg, Tr, Dp, A4welds = (
        v[k] for k in ("Dh", "Th", "th", "Db", "Tb", "tb", "c", "betaDeg", "Tr", "Dp", "A4welds")
    )
    if Dh <= 0 or Db <= 0 or Db > Dh:
        raise ValueError("require 0 < Db <= Dh")
    if Th <= c or Tb <= c:
        raise ValueError("nominal walls must exceed allowance c")
    if betaDeg < 45 or betaDeg > 90:
        raise ValueError("betaDeg must be 45–90 (code area method range)")

    beta = (betaDeg * math.pi) / 180
    sinB = math.sin(beta)
    d1 = (Db - 2 * (Tb - c)) / sinB
    d2 = max(d1, Tb - c + (Th - c) + d1 / 2)
    L4 = min(2.5 * (Th - c), 2.5 * (Tb - c) + Tr)

    A1 = th * d1 * (2 - sinB)
    A2 = (2 * d2 - d1) * (Th - th - c)
    A3 = (2 * L4 * (Tb - tb - c)) / sinB

    padArea = 0.0
    warnings: List[str] = []
    if Tr > 0 and Dp > 0:
        padWidthInZone = min(Dp, 2 * d2) - Db / sinB
        if padWidthInZone > 0:
            padArea = Tr * padWidthInZone
        else:
            warnings.append("Pad lies entirely outside the reinforcement zone — no pad credit taken.")
    A4 = padArea + A4welds

    if A2 < 0:
        warnings.append("Header has no excess thickness (Th − th − c < 0) — header is undersized for pressure alone.")
    if A3 < 0:
        warnings.append("Branch has no excess thickness (Tb − tb − c < 0).")
    if 2 * d2 > Dh:
        warnings.append("Reinforcement zone 2·d2 exceeds header OD — check adjacent openings / code zone limits.")

    margin = A2 + A3 + A4 - A1

    return {
        "module": module,
        "output": {
            "d1": round_half_up(d1, 5),
            "d2": round_half_up(d2, 5),
            "L4": round_half_up(L4, 5),
            "A1": round_half_up(A1, 5),
            "A2": round_half_up(A2, 5),
            "A3": round_half_up(A3, 5),
            "A4": round_half_up(A4, 5),
            "margin": round_half_up(margin, 5),
        },
        "status": "pass" if margin >= 0 else "fail",
        "warnings": warnings,
    }


def bend_thickness(input: dict) -> dict:
    """B31.3 para. 304.2.1 Eq. (3c): tm(I) = P*D / (2*((S*E*W / I) + P*y)) + A."""
    module = "piping.bend-thickness"
    v = _prepare(module, input)
    P, D, R, S, E, y, A = (v[k] for k in ("P", "D", "R", "S", "E", "y", "A"))
    W = v["W"] if v["W"] is not None else 1.0
    if D <= 0:
        raise ValueError("D must be > 0")
    if S <= 0 or E <= 0 or W <= 0:
        raise ValueError("S, E and W must be > 0")
    if R <= D / 2:
        raise ValueError("R must exceed D/2 (bend radius to centerline)")

    RD = R / D
    Iintrados = (4 * RD - 1) / (4 * RD - 2)
    Iextrados = (4 * RD + 1) / (4 * RD + 2)

    def tm(I: float) -> float:
        return (P * D) / (2 * ((S * E * W) / I + P * y)) + A

    warnings: List[str] = []
    if RD < 1:
        warnings.append("R/D < 1: verify the bending procedure supports this tight radius (thinning may exceed the code factor).")

    return {
        "module": module,
        "output": {
            "Iintrados": round_half_up(Iintrados, 5),
            "Iextrados": round_half_up(Iextrados, 5),
            "tmIntrados": round_half_up(tm(Iintrados), 5),
            "tmExtrados": round_half_up(tm(Iextrados), 5),
            "tmCenterline": round_half_up(tm(1), 5),
        },
        "status": "na",
        "warnings": warnings,
    }


def miter_allowable_pressure(input: dict) -> dict:
    """B31.3 para. 304.2.3 Eq. (4a)/(4b)/(4c): allowable internal pressure of a mitered bend."""
    module = "piping.miter-allowable-pressure"
    v = _prepare(module, input)
    S, E, Tc, r2, R1, thetaDeg, miters = (v[k] for k in ("S", "E", "Tc", "r2", "R1", "thetaDeg", "miters"))
    W = v["W"] if v["W"] is not None else 1.0
    if S <= 0 or E <= 0 or W <= 0:
        raise ValueError("S, E and W must be > 0")
    if Tc <= 0 or r2 <= 0:
        raise ValueError("Tc and r2 must be > 0")
    if thetaDeg <= 0 or thetaDeg >= 90:
        raise ValueError("thetaDeg must be in (0, 90)")
    if miters < 1:
        raise ValueError("miters must be >= 1")
    if miters > 1 and R1 <= r2 / 2:
        raise ValueError("R1 must exceed r2/2 for the multi-miter form")

    theta = (thetaDeg * math.pi) / 180
    base = (S * E * W * Tc) / r2
    Pm1 = base * (Tc / (Tc + 0.643 * math.tan(theta) * math.sqrt(r2 * Tc)))

    warnings: List[str] = []
    Pm2 = 0.0
    if miters > 1:
        if thetaDeg > 22.5:
            warnings.append("θ > 22.5° with multiple miters is outside the Eq. 4a/4b applicability — treat as single miters.")
        Pm2 = base * ((R1 - r2) / (R1 - r2 / 2))
        allowablePressure = min(Pm1, Pm2)
        governing = "Eq. 4a" if Pm1 <= Pm2 else "Eq. 4b"
    elif thetaDeg > 22.5:
        allowablePressure = base * (Tc / (Tc + 1.25 * math.tan(theta) * math.sqrt(r2 * Tc)))
        governing = "Eq. 4c (single miter)"
    else:
        allowablePressure = Pm1
        governing = "Eq. 4a (single miter)"

    return {
        "module": module,
        "output": {
            "Pm1": round_half_up(Pm1, 3),
            "Pm2": round_half_up(Pm2, 3),
            "allowablePressure": round_half_up(allowablePressure, 3),
            "governing": governing,
        },
        "status": "na",
        "warnings": warnings,
    }


def leak_test_pressure(input: dict) -> dict:
    """Hydrostatic / pneumatic test pressure: P_hydro = hydroFactor*P*min(ST/S, cap); P_pneu = pneumaticFactor*P."""
    module = "piping.leak-test-pressure"
    v = _prepare(module, input)
    P, ST, S, hydroFactor, pneumaticFactor = (v[k] for k in ("P", "ST", "S", "hydroFactor", "pneumaticFactor"))
    stressRatioCap = v["stressRatioCap"]
    pneumaticMaxFactor = v["pneumaticMaxFactor"]
    if P <= 0:
        raise ValueError("P must be > 0")
    if ST <= 0 or S <= 0:
        raise ValueError("ST and S must be > 0")
    if hydroFactor <= 0 or pneumaticFactor <= 0:
        raise ValueError("factors must be > 0")
    if stressRatioCap is not None and stressRatioCap <= 0:
        raise ValueError("stressRatioCap must be > 0 when supplied")
    if pneumaticMaxFactor is not None and pneumaticMaxFactor <= 0:
        raise ValueError("pneumaticMaxFactor must be > 0 when supplied")

    rawRatio = ST / S
    capEngaged = stressRatioCap is not None and stressRatioCap < rawRatio
    stressRatio = min(rawRatio, stressRatioCap) if stressRatioCap is not None else rawRatio
    hydroTest = hydroFactor * P * stressRatio
    pneumaticTest = pneumaticFactor * P

    warnings: List[str] = ["Verify component (flange/valve) test limits separately — the piping minimum is not the system maximum."]
    if capEngaged:
        warnings.append(
            f"Cap engaged — the code minimum is the uncapped value (ratio {_js_num(round_half_up(rawRatio, 5))}, "
            f"hydro {_js_num(round_half_up(hydroFactor * P * rawRatio, 3))} psi); keep the {_js_num(stressRatioCap)} cap "
            f"only if your specification imposes it."
        )
    if pneumaticMaxFactor is not None and pneumaticFactor > pneumaticMaxFactor:
        warnings.append(
            f"Pneumatic factor {_js_num(pneumaticFactor)} exceeds the code upper bound {_js_num(pneumaticMaxFactor)}× — "
            f"also check the second ¶345.5.4(b) limit (90% of the ¶345.2.1(a) pressure), which this engine does not evaluate."
        )

    return {
        "module": module,
        "output": {
            "stressRatio": round_half_up(stressRatio, 5),
            "hydroTest": round_half_up(hydroTest, 3),
            "pneumaticTest": round_half_up(pneumaticTest, 3),
        },
        "status": "na",
        "warnings": warnings,
    }


REGISTRY: Dict[str, Callable[[dict], dict]] = {
    "piping.b313-wall-thickness": b313_wall_thickness,
    "piping.b311-wall-thickness": b311_wall_thickness,
    "piping.b31-allowable-pressure": b31_allowable_pressure,
    "piping.branch-reinforcement": branch_reinforcement,
    "piping.bend-thickness": bend_thickness,
    "piping.miter-allowable-pressure": miter_allowable_pressure,
    "piping.leak-test-pressure": leak_test_pressure,
}

# Citation strings per module (paragraph references only - never table values).
CITATIONS: Dict[str, str] = {
    "piping.b313-wall-thickness": "ASME B31.3 ¶304.1.2 Eq. (3a)",
    "piping.b311-wall-thickness": "ASME B31.1 ¶104.1.2 (also the B31.5 form; used for B31.9 as ¶904.1.1 permits)",
    "piping.b31-allowable-pressure": "ASME B31.3 ¶304.1.2 Eq. (3a) / B31.1 ¶104.1.2 Eq. (9), solved for P with W (B31.12 Mf supported)",
    "piping.leak-test-pressure": "ASME B31.3 ¶345.4.2 Eq. (24) / ¶345.5.4; B31.1 ¶137.4.5 via factors",
    "piping.bend-thickness": "ASME B31.3 ¶304.2.1 / B31.1 ¶102.4.5 (I-factor)",
    "piping.miter-allowable-pressure": "ASME B31.3 ¶304.2.3 Eq. (4a)/(4b)/(4c)",
    "piping.branch-reinforcement": "ASME B31.3 ¶304.3.3 area replacement",
}


# --------------------------------------------------------------------------- #
# Pre-flight validation (CLI layer only - the engine functions above are untouched).
#   validate() raises ValueError for physically impossible inputs and returns a list
#   of warnings for implausible ones.
# --------------------------------------------------------------------------- #

def validate(module: str, inputs: Any) -> List[str]:
    v = _prepare(module, inputs)          # type / missing / unknown-field checks
    warnings: List[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            raise ValueError(msg)

    # Common factors. E and W are fractions in (0, 1]; Y / y is in [0, 1).
    for name in ("E", "W"):
        x = v.get(name)
        if x is not None:
            need(x > 0, f"{name} must be > 0")
            need(x <= 1, f"{name} must be <= 1 (a quality / strength factor above 1.0 is not physical)")
    for name in ("Y", "y"):
        x = v.get(name)
        if x is not None:
            need(0 <= x < 1, f"{name} must be in [0, 1) (temperature coefficient)")
    if v.get("P") is not None:
        need(v["P"] >= 0, "P must be >= 0")
    for name in ("c", "A"):
        if v.get(name) is not None:
            need(v[name] >= 0, f"{name} must be >= 0 (allowances cannot be negative)")

    if module in ("piping.b313-wall-thickness", "piping.b311-wall-thickness"):
        allow = v["c"] if module == "piping.b313-wall-thickness" else v["A"]
        aname = "c" if module == "piping.b313-wall-thickness" else "A"
        D, P, S, E = v["D"], v["P"], v["S"], v["E"]
        W = v["W"] if v["W"] is not None else 1.0
        Yv = v["Y"] if module == "piping.b313-wall-thickness" else v["y"]
        need(allow < D / 2, f"allowance {aname} must be less than D/2 ({_js_num(D / 2)} in)")
        denom = 2 * (S * E * W + P * Yv)
        mill = v["millTolerance"]
        if D > 0 and denom > 0 and 0 <= mill < 1:
            tm = P * D / denom + allow
            need(tm < D / 2, f"required thickness tm = {_js_num(round_half_up(tm, 5))} in is not less than D/2 - impossible wall; check the inputs")
            need(tm / (1 - mill) < D / 2, "ordered thickness tOrder is not less than D/2 - impossible wall; check the inputs")
    elif module == "piping.b31-allowable-pressure":
        D, t, A = v["D"], v["t"], v["A"]
        need(t < D / 2, "t must be less than D/2 (wall cannot reach the pipe centre)")
        need(A < t, "additional thickness A must be less than the nominal wall t")
    elif module == "piping.branch-reinforcement":
        need(v["Th"] < v["Dh"] / 2, "Th must be less than Dh/2")
        need(v["Tb"] < v["Db"] / 2, "Tb must be less than Db/2")
        need(v["c"] < v["Th"] and v["c"] < v["Tb"], "allowance c must be less than both Th and Tb")
    elif module == "piping.miter-allowable-pressure":
        need(v["R1"] > v["r2"], "R1 must exceed r2 (the miter bend radius must clear the pipe radius)")
        need(v["Tc"] < 2 * v["r2"], "Tc must be less than 2*r2 (wall cannot exceed the pipe diameter)")
    elif module == "piping.leak-test-pressure":
        ratio = v["ST"] / v["S"] if v["S"] > 0 else None
        if ratio is not None and ratio > 2:
            warnings.append(f"ST/S = {_js_num(round_half_up(ratio, 4))} is above 2 - check S_T/S (both stresses from the same table line, test vs design temperature).")
        if v["pneumaticFactor"] > 1.33:
            warnings.append(f"pneumaticFactor {_js_num(v['pneumaticFactor'])} is above 1.33 - confirm the code's pneumatic factor for the edition on record.")
    return warnings


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

class CliError(Exception):
    pass


def resolve_module(name: str) -> str:
    if name in REGISTRY:
        return name
    if name in SHORT:
        return SHORT[name]
    raise CliError(f"unknown module '{name}' (run 'list' to see the available modules)")


def user_supplied_names(module: str) -> List[str]:
    return [f[0] for f in FIELDS[module] if f[3]]


def run_module(module: str, inputs: dict) -> dict:
    pre_warnings = validate(module, inputs)
    result = REGISTRY[module](dict(inputs))
    output = dict(result["output"])
    if module == "piping.miter-allowable-pressure" and inputs.get("miters") == 1:
        output["Pm2"] = None          # not evaluated for a single miter (the engine reports 0.0)
    defaults = {}
    for name, _u, required, _us, _d in FIELDS[module]:
        if not required and name in ("W",) and inputs.get(name) is None:
            defaults[name] = 1.0
    present_supplied = [n for n in user_supplied_names(module) if inputs.get(n) is not None]
    return {
        "module": result["module"],
        "status": result["status"],
        "output": output,
        "warnings": pre_warnings + result["warnings"],
        "citation": CITATIONS[module],
        "inputs": inputs,
        "user_supplied": present_supplied,
        "defaults_applied": defaults,
    }


def render_list() -> str:
    lines: List[str] = [
        "Pressure-design modules (US customary: psi, in, deg; engine is unit-consistent).",
        "[S] = code-table value the user reads from their licensed copy and supplies. Never defaulted.",
        "",
    ]
    for module in REGISTRY:
        lines.append(f"{module}  --  {CITATIONS[module]}")
        for name, units, required, us, desc in FIELDS[module]:
            tag = "required" if required else "optional"
            mark = " [S]" if us else ""
            lines.append(f"    {name:<14}{units:<9}{tag:<9}{mark:<5}{desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def list_json() -> dict:
    return {
        m: {
            "citation": CITATIONS[m],
            "fields": [
                {"name": n, "units": u, "required": r, "user_supplied": us, "description": d}
                for n, u, r, us, d in FIELDS[m]
            ],
        }
        for m in REGISTRY
    }


def _normalise_zero(obj: Any) -> Any:
    """-0.0 prints as '-0.0' in JSON; show 0.0 instead (display only)."""
    if isinstance(obj, float):
        return 0.0 if obj == 0 else obj
    if isinstance(obj, dict):
        return {k: _normalise_zero(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise_zero(v) for v in obj]
    return obj


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(
        prog="pressure_design.py",
        description="ASME B31.1/B31.3 pressure-design calculators. "
                    "'list' shows modules and fields; '<module> --input <json>' runs one.",
    )
    ap.add_argument("command", help="'list' or a module id (e.g. piping.b313-wall-thickness or b313-wall-thickness)")
    ap.add_argument("--input", help="inputs as a JSON object")
    ap.add_argument("--input-file", help="path to a JSON file holding the inputs")
    ap.add_argument("--json", action="store_true", help="with 'list': machine-readable output")

    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors already
        return int(exc.code or 0)

    try:
        if args.command == "list":
            if args.json:
                print(json.dumps(list_json(), indent=2, ensure_ascii=False))
            else:
                sys.stdout.write(render_list())
            return 0

        module = resolve_module(args.command)
        if args.input and args.input_file:
            raise CliError("give either --input or --input-file, not both")
        if args.input_file:
            try:
                with open(args.input_file, encoding="utf-8-sig") as fh:
                    raw = fh.read()
            except OSError as exc:
                raise CliError(f"cannot read --input-file: {exc.strerror or exc}")
        elif args.input:
            raw = args.input
        else:
            raise CliError("no inputs: pass --input '<json>' or --input-file <path>")
        try:
            inputs = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CliError(f"inputs are not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})")
        if not isinstance(inputs, dict):
            raise CliError("inputs must be a JSON object")

        envelope = run_module(module, inputs)
        print(json.dumps(_normalise_zero(envelope), indent=2, ensure_ascii=False))
        return 0
    except ArithmeticError as exc:
        print(f"input error: arithmetic failure ({exc}) - check the inputs", file=sys.stderr)
        return 2
    except (CliError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
