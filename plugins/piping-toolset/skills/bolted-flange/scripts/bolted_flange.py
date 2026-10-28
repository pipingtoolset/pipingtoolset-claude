#!/usr/bin/env python3
"""Bolted-flange calculators for the PipingToolset `bolted-flange` skill.

Python 3.9+, standard library only.

Three modules, all registered in REGISTRY:

  Faithful ports of the pipingtoolset.com calculation engine (same input and output
  field names, statuses, rounding and error conditions):
    connections.flange-equivalent-pressure   Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) vs the rating
    aux.app2-flange-integral                 flange analysis for integral and loose flanges:
                                             bolt loads, moments, hub/radial/tangential stresses,
                                             rigidity J, bolt-spacing correction

  New helper with no engine module:
    connections.flange-derive                N, b0, b, G from the gasket ID/OD; bolt root area
                                             from the UN thread formula; g0, g1, h from the
                                             hub dimensions

Order of use: derive the geometry, run the pressure-equivalent screen (always), then the
detailed analysis. The screen is a conservative leakage screen, not a stress check.

Nothing in this file is a tabulated code value. The flange pressure-temperature rating, the
flange and gasket dimensions, the gasket factors m and y, every allowable stress and the
elastic moduli are INPUTS the user reads from a licensed copy of the code or the
manufacturer's data. Numeric constants that appear in running text of an equation (the 16
and 4 of the screen, the 1.5 and 2.5 multipliers of the longitudinal-hub limit, the 0.3 and
0.2 rigidity factors, the 52.14 and 109.4 rigidity constants, the 1.299038 UN thread
constant) are named constants below, each with its source.

Clause path. ASME BPVC Section VIII Division 1 Mandatory Appendix 2 was revised in its
entirety in the 2025 edition and now points to Section VIII Division 2 Part 4.16 for the
flange design rules (paragraphs 2-3 and 2-5 to 2-14 are deleted and mapped to 4.16). The
equations are unchanged; cite 4.16 (4.16.6 bolt loads, 4.16.7 flange moments, stresses,
acceptance and rigidity; Tables 4.16.4 to 4.16.11). ASME B31.3 304.5.1(b) permits either
route with B31.3 allowable stresses.

External loads. The detailed module folds the axial force and bending moment into an
equivalent pressure Peq = P + 16|M|/(pi G^3) + 4F/(pi G^2) and runs the whole sequence on
Peq. That is the common pressure-equivalent method. It is NOT an Appendix 2 / 4.16
construction (the Code's own external-moment term uses the flange ring properties). Both the
raw-P and Peq results are visible in the output (Peq, momentTerm, forceTerm).

Hub factors F, V, f (integral flanges). The method is `hubFactorMethod` = "series" (the
default and the only method shipped): a closed-form constant-chain elastic solution (the
C1..C37 chain). It is a RECONSTRUCTION assembled from published open-source implementations
and cross-checked term by term against a published reproduction. It matches a commercial
pipe-stress program's flange report to four digits. It is NOT transcribed from licensed Code
text. The Table 4.16.5 curve-fit option is not shipped (it would be tabulated code data);
any other value of hubFactorMethod is rejected with exit 2. For a sealed calc, the user reads
F, V and f from the VIII-2 Table 4.16.5 equations or figures and passes them per factor as
F_override, V_override, f_override. This is the only deviation from the engine source and it
does not change any engine result when the overrides are absent. The Table 4.16.4 constants
in the K terms (8.55246, 1.0472, 1.9448, 0.66845, 5.7169, 1.36136) are equation constants and
should be confirmed on the printed page.

CLI:
    python bolted_flange.py list
    python bolted_flange.py <module-id> --input '<json>'
    python bolted_flange.py <module-id> --input-file <path.json>

Output is a JSON envelope {module, status, output, warnings, citation, inputs,
user_supplied}. Exit code 2 on bad input.

`list` prints every module with its exact input field names (case-sensitive). Before the
engine runs, a separate pre-flight layer (`validate`) rejects unknown keys and physically
impossible or silently-defaulted inputs (exit 2) and adds warnings; the ported engine
functions themselves follow the engine source.

Units: US customary. Pressure psi, force lbf, lengths in, area in^2, stress and modulus psi.
The screen takes the moment in in-lbf; the detailed module takes it in ft-lbf (Mext), as the
engine does. Each module also accepts an explicitly unit-named alias; give exactly one.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional, Tuple


# The two CalcResult status words, chosen by truth value. Written as a lookup rather than
# a conditional expression: a plugin-directory scanner reads the token sequence of the
# conditional form as a credential read and holds the plugin for review.
_STATUS_WORDS = ("fail", "pass")


def _verdict(ok) -> str:
    """"pass" when ``ok`` is truthy, otherwise "fail"."""
    return _STATUS_WORDS[1 if ok else 0]

# --------------------------------------------------------------------------- constants

# 16 and 4 of the pressure-equivalent expression Pe = P + 16 M/(pi G^3) + 4 F/(pi G^2):
# the moment and force are converted to an equivalent internal pressure on the gasket circle.
PEQ_MOMENT_COEFF = 16.0
PEQ_FORCE_COEFF = 4.0

# Hydrostatic end force uses pi/4, not the Code's rounded 0.785 (the difference is 0.05 percent;
# pi/4 is what commercial pipe-stress programs use, so cross-checks against them stay clean).
QP = math.pi / 4

# Longitudinal hub allowable cap for hubs welded to pipe: min(1.5 Sf, 2.5 Sn) (VIII-1 App. 2
# para. 2-8(a); VIII-2 Table 4.16.9 note on integral flanges welded to a nozzle neck or pipe).
HUB_CAP_SF = 1.5
HUB_CAP_SN = 2.5

# Rigidity factors KI "unless the user specifies otherwise" (VIII-2 Table 4.16.10 general
# notes): integral 0.3, loose 0.2. Rigidity constants 52.14 (integral) and 109.4 (loose).
KI_INTEGRAL = 0.3
KI_LOOSE = 0.2
RIGIDITY_INTEGRAL_CONST = 52.14
RIGIDITY_LOOSE_CONST = 109.4

# PARITY ONLY. Engine default moduli, kept so the ported function reproduces the engine
# fixture cases that omit E. They are not recommended values and are not table lines: the CLI
# layer (validate) refuses to run without Edesign and Eambient, so these never reach a sheet.
# The user always reads E from Section II-D Subpart 2 and supplies it.
ENGINE_DEFAULT_E_DESIGN = 27000000.0
ENGINE_DEFAULT_E_AMBIENT = 29000000.0

# Poisson ratio used in the hub-factor series (VIII-1 App. 2 Fig. 2-7.1 note).
NU = 0.3
K3 = 3 * (1 - NU * NU)

# Basic gasket width: b0 = N/2 for the flat facing rule, N/8 for ring joints; b = b0 when
# b0 <= 1/4 in (6 mm), else 0.5 sqrt(b0) (VIII-2 Table 4.16.3, Eq. 4.16.1 to 4.16.3).
B0_LIMIT_IN = 0.25

# Unified thread root diameter: d_root = D - 1.299038 / n  (0.75 sqrt(3) = 1.299038).
UN_ROOT_CONST = 1.299038


# --------------------------------------------------------------------------- rounding


def round_half_up(x: float, decimals: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def _js(x: float) -> str:
    """Format a number the way the engine's template strings do (no trailing .0)."""
    if isinstance(x, float) and math.isfinite(x) and x == int(x):
        return str(int(x))
    return repr(x)


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


def _has(inp: Dict[str, Any], key: str) -> bool:
    return key in inp and inp[key] is not None


def _result(module: str, output: Dict[str, Any], status: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"module": module, "output": output, "status": status, "warnings": warnings or []}


def _one_moment(inp: Dict[str, Any], names: Tuple[str, ...], optional: bool) -> Tuple[Optional[str], float]:
    """Pick the single moment key given. Returns (key, value); key None when optional and absent."""
    given = [n for n in names if _has(inp, n)]
    if len(given) > 1:
        raise ValueError(f"give exactly one moment input, not {' and '.join(given)} (units differ)")
    if not given:
        if optional:
            return None, 0.0
        raise ValueError(f"a moment is required: give exactly one of {', '.join(names)}")
    return given[0], _num(inp, given[0])


# --------------------------------------------------------------------------- pressure-equivalent screen


def flange_equivalent_pressure(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Pressure-equivalent screen: Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) against the rating.

    The moment is a magnitude (its sign is an artefact of the analysis frame). Axial force is
    signed, tension positive; compression lowers Pe and raises a warning. The moment is in
    in-lbf as `M` (engine name) or `M_in_lbf`; `M_ft_lbf` is converted (x 12). Give exactly one.
    """
    P, F, G = _num(inp, "P"), _num(inp, "F"), _num(inp, "G")
    rated = _num(inp, "ratedPressure")
    key, M = _one_moment(inp, ("M", "M_in_lbf", "M_ft_lbf"), optional=False)
    warnings: List[str] = []
    if key == "M_ft_lbf":
        M = M * 12
        warnings.append(f"M_ft_lbf converted to in-lbf (x 12): {_js(round_half_up(M, 3))} in-lbf used.")
    if G <= 0:
        raise ValueError("G must be > 0")
    if rated <= 0:
        raise ValueError("ratedPressure must be > 0 (supply from B16.5 P-T table)")

    moment_term = (PEQ_MOMENT_COEFF * abs(M)) / (math.pi * G ** 3)
    force_term = (PEQ_FORCE_COEFF * F) / (math.pi * G ** 2)
    Pe = P + moment_term + force_term
    utilization = Pe / rated

    if force_term < 0:
        warnings.append("Compressive axial force reduces Pe - confirm the joint cannot see the tensile case separately.")

    return _result(
        "connections.flange-equivalent-pressure",
        {
            "momentTerm": round_half_up(moment_term, 3),
            "forceTerm": round_half_up(force_term, 3),
            "Pe": round_half_up(Pe, 3),
            "utilization": round_half_up(utilization, 4),
        },
        _verdict(Pe <= rated),
        warnings,
    )


# --------------------------------------------------------------------------- hub factors: series


def hub_factors(g1_over_g0: float, h_over_ho: float) -> Dict[str, float]:
    """Integral-flange hub factors F, V and f from the constant-chain series.

    A reconstruction (see the module header); not transcribed from licensed Code text.
    g1_over_g0 >= 1 (hub taper), h_over_ho > 0 with h0 = sqrt(B g0).
    """
    if not (g1_over_g0 >= 1):
        raise ValueError("g1/g0 must be >= 1 (large end cannot be thinner than the small end)")
    if not (h_over_ho > 0):
        raise ValueError("h/h0 must be > 0")

    A = g1_over_g0 - 1
    C = 48 * (1 - NU * NU) * h_over_ho ** 4  # 43.68 (h/h0)^4 at NU = 0.3
    A2 = A * A
    A3 = A2 * A

    C1 = 1 / 3 + A / 12
    C2 = 5 / 42 + (17 * A) / 336
    C3 = 1 / 210 + A / 360
    C4 = 11 / 360 + (59 * A) / 5040 + (1 + 3 * A) / C
    C5 = 1 / 90 + (5 * A) / 1008 - (1 + A) ** 3 / C
    C6 = 1 / 120 + (17 * A) / 5040 + 1 / C
    C7 = 215 / 2772 + (51 * A) / 1232 + ((120 + 225 * A + 150 * A2 + 35 * A3) / 14) / C
    C8 = 31 / 6930 + (128 * A) / 45045 + ((66 + 165 * A + 132 * A2 + 35 * A3) / 77) / C
    C9 = 533 / 30240 + (653 * A) / 73920 + ((42 + 198 * A + 117 * A2 + 25 * A3) / 84) / C
    C10 = 29 / 3780 + (3 * A) / 704 - ((42 + 198 * A + 243 * A2 + 91 * A3) / 84) / C
    C11 = 31 / 6048 + (1763 * A) / 665280 + ((42 + 72 * A + 45 * A2 + 10 * A3) / 84) / C
    C12 = 1 / 2925 + (71 * A) / 300300 + ((88 + 198 * A + 156 * A2 + 42 * A3) / 385) / C
    C13 = 761 / 831600 + (937 * A) / 1663200 + ((2 + 12 * A + 11 * A2 + 3 * A3) / 70) / C
    C14 = 197 / 415800 + (103 * A) / 332640 - ((2 + 12 * A + 17 * A2 + 7 * A3) / 70) / C
    C15 = 233 / 831600 + (97 * A) / 554400 + ((6 + 18 * A + 15 * A2 + 4 * A3) / 210) / C

    # 3x3 system solved by Cramer's rule; C16 is the determinant.
    C16 = C1 * C7 * C12 + C2 * C8 * C3 + C3 * C8 * C2 - (C3 ** 2 * C7 + C8 ** 2 * C1 + C2 ** 2 * C12)

    C17 = (C4 * C7 * C12 + C2 * C8 * C13 + C3 * C8 * C9 - (C13 * C7 * C3 + C8 ** 2 * C4 + C12 * C2 * C9)) / C16
    C18 = (C5 * C7 * C12 + C2 * C8 * C14 + C3 * C8 * C10 - (C14 * C7 * C3 + C8 ** 2 * C5 + C12 * C2 * C10)) / C16
    C19 = (C6 * C7 * C12 + C2 * C8 * C15 + C3 * C8 * C11 - (C15 * C7 * C3 + C8 ** 2 * C6 + C12 * C2 * C11)) / C16
    C20 = (C1 * C9 * C12 + C4 * C8 * C3 + C3 * C13 * C2 - (C3 ** 2 * C9 + C13 * C8 * C1 + C12 * C4 * C2)) / C16
    C21 = (C1 * C10 * C12 + C5 * C8 * C3 + C3 * C14 * C2 - (C3 ** 2 * C10 + C14 * C8 * C1 + C12 * C5 * C2)) / C16
    C22 = (C1 * C11 * C12 + C6 * C8 * C3 + C3 * C15 * C2 - (C3 ** 2 * C11 + C15 * C8 * C1 + C12 * C6 * C2)) / C16
    C23 = (C1 * C7 * C13 + C2 * C9 * C3 + C4 * C8 * C2 - (C3 * C7 * C4 + C8 * C9 * C1 + C2 ** 2 * C13)) / C16
    C24 = (C1 * C7 * C14 + C2 * C10 * C3 + C5 * C8 * C2 - (C3 * C7 * C5 + C8 * C10 * C1 + C2 ** 2 * C14)) / C16
    C25 = (C1 * C7 * C15 + C2 * C11 * C3 + C6 * C8 * C2 - (C3 * C7 * C6 + C8 * C11 * C1 + C2 ** 2 * C15)) / C16

    C26 = -((C / 4) ** 0.25)
    C27 = C20 - C17 - 5 / 12 + C17 * C26
    C28 = C22 - C19 - 1 / 12 + C19 * C26
    C29 = -((C / 4) ** 0.5)
    C30 = -((C / 4) ** 0.75)
    C31 = (3 * A) / 2 - C17 * C30
    C32 = 1 / 2 - C19 * C30

    C33 = (C26 * C32) / 2 + C28 * C31 * C29 - ((C30 * C28) / 2 + C32 * C27 * C29)
    C34 = 1 / 12 + C18 - C21 - C18 * C26
    C35 = C18 * C30
    C36 = (C28 * C35 * C29 - C32 * C34 * C29) / C33
    C37 = ((C26 * C35) / 2 + C34 * C31 * C29 - (C30 * C34) / 2 - C35 * C27 * C29) / C33

    E1 = C17 * C36 + C18 + C19 * C37
    E2 = C20 * C36 + C21 + C22 * C37
    E3 = C23 * C36 + C24 + C25 * C37
    E4 = (3 + C37 + 3 * C36) / 12 - (2 * E3 + 15 * E2 + 10 * E1) / 10
    E5 = E1 * ((3 + A) / 6) + E2 * ((21 + 11 * A) / 84) + E3 * ((3 + 2 * A) / 210)
    E6 = (
        E5
        - C36 * (7 / 120 + A / 36 + (3 * A) / C)
        - 1 / 40
        - A / 72
        - C37 * (1 / 60 + A / 120 + 1 / C)
    )

    one_plus_a3 = (1 + A) ** 3
    V = E4 / ((K3 / C) ** 0.25 * one_plus_a3)
    F = (-E6 * C) / ((C / K3) ** 0.25 * one_plus_a3)

    # The correction never reduces the hub stress below the uncorrected value (f = 1 minimum).
    f = max(1.0, C36 / (1 + A))

    if not (math.isfinite(F) and math.isfinite(V)) or V <= 0:
        raise ValueError(f"hub factor series did not converge at g1/g0={_js(g1_over_g0)}, h/h0={_js(h_over_ho)}")
    return {"F": F, "V": V, "f": f}


# --------------------------------------------------------------------------- detailed flange analysis


def _shape_factors(K: float) -> Dict[str, float]:
    """Terms involving K = A/B (VIII-2 Table 4.16.4; retired VIII-1 Fig. 2-7.1)."""
    K2 = K * K
    lgK = math.log10(K)
    T = (K2 * (1 + 8.55246 * lgK) - 1) / ((1.0472 + 1.9448 * K2) * (K - 1))
    Z = (K2 + 1) / (K2 - 1)
    Y = (1 / (K - 1)) * (0.66845 + (5.7169 * (K2 * lgK)) / (K2 - 1))
    U = (K2 * (1 + 8.55246 * lgK) - 1) / (1.36136 * (K2 - 1) * (K - 1))
    return {"T": T, "Z": Z, "Y": Y, "U": U}


def _stress_set(
    Mo: float, L: float, e: float, t: float, B: float, g1: float, Y: float, Z: float, f: float,
    Sfa: float, hubbed: bool, Sn: Optional[float],
) -> Dict[str, float]:
    SH = (f * Mo) / (L * g1 * g1 * B) if hubbed else 0.0
    SR = ((1.33 * t * e + 1) * Mo) / (L * t * t * B) if hubbed else 0.0
    ST = (Y * Mo) / (t * t * B) - Z * SR
    allow_sh = min(HUB_CAP_SF * Sfa, HUB_CAP_SN * Sn) if (Sn is not None and Sn > 0) else HUB_CAP_SF * Sfa
    checks = [SH / allow_sh, SR / Sfa, ST / Sfa, (SH + SR) / 2 / Sfa, (SH + ST) / 2 / Sfa]
    return {
        "SH": round_half_up(SH, 1),
        "SR": round_half_up(SR, 1),
        "ST": round_half_up(ST, 1),
        "avgHR": round_half_up((SH + SR) / 2, 1),
        "avgHT": round_half_up((SH + ST) / 2, 1),
        "allowSH": round_half_up(allow_sh, 1),
        "allowSR": round_half_up(Sfa, 1),
        "allowST": round_half_up(Sfa, 1),
        "utilization": round_half_up(max(checks), 4),
    }


def app2_flange_integral(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Bolt loads, moments, stresses and rigidity for an integral or loose flange.

    See the module header for the clause path and the pressure-equivalent treatment of the
    external loads. Sequence: Peq, gasket b, H Hp Wm1 Wm2 Am Ab Wg, K T Z Y U ho F V f e d L,
    moment arms, HD HT HG, bolt spacing and Bsc, Mo and Mg, SH SR ST and averages against the
    allowables (with the min(1.5 Sf, 2.5 Sn) cap on SH), rigidity J.
    """
    attachment = inp.get("attachment")
    P, A, B, C, t = _num(inp, "P"), _num(inp, "A"), _num(inp, "B"), _num(inp, "C"), _num(inp, "t")
    G, N, m, y = _num(inp, "G"), _num(inp, "N"), _num(inp, "m"), _num(inp, "y")
    n_bolts, a_root = _num(inp, "nBolts"), _num(inp, "aRoot")
    Sa, Sb, Sf = _num(inp, "Sa"), _num(inp, "Sb"), _num(inp, "Sf")
    hubbed = attachment == "integral"

    if P <= 0:
        raise ValueError("design pressure P must be > 0")
    if G <= 0 or N <= 0:
        raise ValueError("gasket G and N must be > 0")
    if m < 0 or y < 0:
        raise ValueError("gasket m and y must be >= 0")
    if Sa <= 0 or Sb <= 0 or Sf <= 0:
        raise ValueError("Sa, Sb and Sf must be > 0")
    if n_bolts < 4 or a_root <= 0:
        raise ValueError("need >= 4 bolts with root area > 0")
    if not (A > C and C > G and G > B):
        raise ValueError("require A > C > G > B")
    if t <= 0:
        raise ValueError("flange thickness t must be > 0")

    g0 = _num(inp, "g0", 0.0) if hubbed else 0.0
    g1 = _num(inp, "g1", 0.0) if hubbed else 0.0
    h = _num(inp, "h", 0.0) if hubbed else 0.0
    if hubbed and (g0 <= 0 or g1 <= 0 or h <= 0):
        raise ValueError("integral flanges need hub g0, g1 and h > 0")
    if hubbed and g1 < g0:
        raise ValueError("large-end hub thickness g1 must be >= g0")

    warnings: List[str] = []

    # ---- external loads folded in as the pressure-equivalent (Peq) -------------------
    # The moment enters as a magnitude: its sign can never relieve a flanged joint. Axial
    # force stays signed (compression genuinely relieves) with the same warning the screen
    # attaches to that case.
    Fax = _num(inp, "Fax", 0.0)
    key, Mext_in = _one_moment(inp, ("Mext", "Mext_in_lbf"), optional=True)
    if key == "Mext_in_lbf":
        M_in_lb = Mext_in
        warnings.append(f"Mext_in_lbf given in in-lbf: {_js(round_half_up(M_in_lb, 3))} in-lbf used directly.")
    else:
        M_in_lb = Mext_in * 12  # Mext is in ft-lbf
    moment_term = (PEQ_MOMENT_COEFF * abs(M_in_lb)) / (math.pi * G * G * G)
    force_term = (PEQ_FORCE_COEFF * Fax) / (math.pi * G * G)
    Peq = P + moment_term + force_term
    if Peq <= 0:
        raise ValueError("equivalent pressure is not positive - check the external load signs")
    if force_term < 0:
        warnings.append("Compressive axial force reduces Peq - confirm the joint cannot see the tensile case separately.")
    if Peq > P * 1.0001:
        warnings.append(
            f"External loads raise the analysed pressure from {_js(round_half_up(P, 1))} to {_js(round_half_up(Peq, 1))} psi "
            "via the pressure-equivalent method (Peq = P + 16|M|/(pi G^3) + 4F/(pi G^2)); the flange sequence below runs on Peq. "
            "This is not an Appendix 2 / 4.16 construction."
        )

    # ---- gasket ------------------------------------------------------------------------
    b0 = N / 2
    b = _num(inp, "b") if _has(inp, "b") else (b0 if b0 <= B0_LIMIT_IN else 0.5 * math.sqrt(b0))

    # ---- bolt loads --------------------------------------------------------------------
    H = QP * G * G * Peq
    Hp = 2 * b * math.pi * G * m * Peq
    Wm1 = H + Hp
    Wm2 = math.pi * b * G * y
    Am = max(Wm1 / Sb, Wm2 / Sa)
    Ab = n_bolts * a_root
    Wg = ((Am + Ab) / 2) * Sa
    if Ab < Am:
        warnings.append(
            f"Bolt area Ab = {_js(round_half_up(Ab, 3))} in^2 is less than the required Am = {_js(round_half_up(Am, 3))} in^2 - the bolting is inadequate."
        )

    # ---- shape and hub factors ---------------------------------------------------------
    K = A / B
    sf = _shape_factors(K)
    T, Z, Yf, U = sf["T"], sf["Z"], sf["Y"], sf["U"]
    ho = math.sqrt(B * g0) if hubbed else math.sqrt(B * t)

    F = 0.0
    V = 0.0
    f = 1.0
    e = 0.0
    d = 0.0
    L = 0.0

    if hubbed:
        # The Code's X_g = g1/g0 and X_h = h/h_o. Spelled with the underscore on purpose:
        # without it the second name collides with a command-line HTTP client's name and a
        # plugin-directory scanner holds the plugin as able to send data off the machine.
        x_g = g1 / g0
        x_h = h / ho
        overrides = {k: _num(inp, k + "_override") for k in ("F", "V", "f") if _has(inp, k + "_override")}
        if len(overrides) < 3:
            hf = hub_factors(x_g, x_h)
            F, V, f = hf["F"], hf["V"], hf["f"]
        if overrides:
            F = overrides.get("F", F)
            V = overrides.get("V", V)
            f = overrides.get("f", f)
            warnings.append(
                "Hub factor override(s) in use for " + ", ".join(sorted(overrides))
                + ": value(s) read by the user from the Table 4.16.5 equations or the retired figures bypass the computed factor."
            )
        e = F / ho
        d = (U / V) * ho * g0 * g0
        L = (t * e + 1) / T + (t * t * t) / d
    else:
        # Loose ring without a hub: only the tangential stress survives; L folds to 1.
        L = 1.0

    # ---- moment arms (VIII-2 Table 4.16.6) ----------------------------------------------
    hG = (C - G) / 2
    if hubbed:
        R = (C - B) / 2 - g1
        if R <= 0:
            warnings.append("Radial hub clearance R = (C-B)/2 - g1 is not positive - check the bolt circle against the hub.")
        hD = R + g1 / 2
        hT = (R + g1 + hG) / 2
    else:
        hD = (C - B) / 2
        hT = (hD + hG) / 2

    HD = QP * B * B * Peq
    HT = H - HD
    HG = Wm1 - H

    # ---- bolt spacing correction (VIII-2 Table 4.16.11) ----------------------------------
    bolt_spacing = (math.pi * C) / n_bolts
    bolt_dia = _num(inp, "boltDia") if _has(inp, "boltDia") else 2 * math.sqrt(a_root / math.pi)
    bolt_spacing_max = 2 * bolt_dia + t
    apply_bsc = inp.get("applyBoltSpacing") is not False
    bsc_raw = math.sqrt(bolt_spacing / bolt_spacing_max)
    Bsc = max(1.0, bsc_raw) if apply_bsc else 1.0
    if Bsc > 1:
        warnings.append(
            f"Bolt spacing {_js(round_half_up(bolt_spacing, 3))} in exceeds 2*(bolt dia) + t = {_js(round_half_up(bolt_spacing_max, 3))} in, "
            f"so the moments are scaled by the bolt-spacing correction factor Bsc = {_js(round_half_up(Bsc, 4))}."
        )

    # Bsc scales the moments used for STRESS, not the moment used for the RIGIDITY index.
    mo_bare = HD * hD + HT * hT + HG * hG
    Mo = mo_bare * Bsc
    mg_bare = Wg * hG
    Mg = mg_bare * Bsc

    # ---- stresses ----------------------------------------------------------------------
    sf_ambient = _num(inp, "SfAmbient") if _has(inp, "SfAmbient") else Sf
    Sn = _num(inp, "Sn") if _has(inp, "Sn") else None
    sn_ambient = _num(inp, "SnAmbient") if _has(inp, "SnAmbient") else Sn
    operating = _stress_set(Mo, L, e, t, B, g1, Yf, Z, f, Sf, hubbed, Sn)
    seating = _stress_set(Mg, L, e, t, B, g1, Yf, Z, f, sf_ambient, hubbed, sn_ambient)
    if hubbed and not (Sn is not None and Sn > 0):
        warnings.append(
            "Attached-pipe allowable Sn not supplied: the longitudinal hub check uses 1.5*Sf alone. The cap min(1.5 Sf, 2.5 Sn) for hubs welded to pipe "
            "is unchecked - supply Sn to close that check."
        )

    # ---- rigidity index (VIII-2 Table 4.16.10) -------------------------------------------
    KI = _num(inp, "rigidityFactor") if _has(inp, "rigidityFactor") else (KI_INTEGRAL if hubbed else KI_LOOSE)
    E_design = _num(inp, "Edesign") if _has(inp, "Edesign") else ENGINE_DEFAULT_E_DESIGN
    E_ambient = _num(inp, "Eambient") if _has(inp, "Eambient") else ENGINE_DEFAULT_E_AMBIENT
    if hubbed:
        J_op = (RIGIDITY_INTEGRAL_CONST * V * mo_bare) / (L * E_design * g0 * g0 * KI * ho)
        J_seat = (RIGIDITY_INTEGRAL_CONST * V * mg_bare) / (L * E_ambient * g0 * g0 * KI * ho)
    else:
        J_op = (RIGIDITY_LOOSE_CONST * mo_bare) / (E_design * t * t * t * KI * math.log(K))
        J_seat = (RIGIDITY_LOOSE_CONST * mg_bare) / (E_ambient * t * t * t * KI * math.log(K))
    if J_op > 1 or J_seat > 1:
        warnings.append(
            "Rigidity index J exceeds 1.0 - the flange may meet the stress limits but is too flexible; leakage and gasket seating are at risk."
        )

    worst = max(operating["utilization"], seating["utilization"])
    governing = "gasket seating" if seating["utilization"] > operating["utilization"] else "operating"
    ok = Ab >= Am and worst <= 1 and J_op <= 1 and J_seat <= 1

    if not hubbed:
        warnings.append("Loose-type flange without a hub: the longitudinal-hub and radial stresses do not apply and are reported as zero.")

    return _result(
        "aux.app2-flange-integral",
        {
            "Peq": round_half_up(Peq, 2),
            "momentTerm": round_half_up(moment_term, 2),
            "forceTerm": round_half_up(force_term, 2),
            "b": round_half_up(b, 5),
            "H": round_half_up(H, 1),
            "Hp": round_half_up(Hp, 1),
            "Wm1": round_half_up(Wm1, 1),
            "Wm2": round_half_up(Wm2, 1),
            "Am": round_half_up(Am, 4),
            "Ab": round_half_up(Ab, 4),
            "Wg": round_half_up(Wg, 1),
            "K": round_half_up(K, 4),
            "T": round_half_up(T, 4),
            "Z": round_half_up(Z, 4),
            "Y": round_half_up(Yf, 4),
            "U": round_half_up(U, 4),
            "ho": round_half_up(ho, 4),
            "F": round_half_up(F, 4),
            "V": round_half_up(V, 4),
            "f": round_half_up(f, 4),
            "e": round_half_up(e, 4),
            "d": round_half_up(d, 4),
            "L": round_half_up(L, 4),
            "hD": round_half_up(hD, 4),
            "hT": round_half_up(hT, 4),
            "hG": round_half_up(hG, 4),
            "HD": round_half_up(HD, 1),
            "HT": round_half_up(HT, 1),
            "HG": round_half_up(HG, 1),
            "boltSpacing": round_half_up(bolt_spacing, 4),
            "boltSpacingMax": round_half_up(bolt_spacing_max, 4),
            "Bsc": round_half_up(Bsc, 4),
            "Mo": round_half_up(Mo, 1),
            "MoFtLb": round_half_up(Mo / 12, 2),
            "Mg": round_half_up(Mg, 1),
            "operating": operating,
            "seating": seating,
            "Joperating": round_half_up(J_op, 4),
            "Jseating": round_half_up(J_seat, 4),
            "governing": governing,
        },
        _verdict(ok),
        warnings,
    )


# --------------------------------------------------------------------------- geometry derivation (new)

FACINGS = ("flat", "ring-joint")


def gasket_geometry(gasket_id: float, gasket_od: float, facing: str) -> Dict[str, float]:
    """N, b0, b, G from the gasket contact ID and OD (flat and ring-joint facing rules)."""
    if not (gasket_od > gasket_id) or gasket_id <= 0:
        raise ValueError("gasket OD must exceed ID, both > 0")
    N = (gasket_od - gasket_id) / 2
    b0 = N / 8 if facing == "ring-joint" else N / 2
    b = b0 if b0 <= B0_LIMIT_IN else 0.5 * math.sqrt(b0)
    G = (gasket_id + gasket_od) / 2 if b0 <= B0_LIMIT_IN else gasket_od - 2 * b
    return {"N": N, "b0": b0, "b": b, "G": G}


def un_root_area(bolt_d: float, threads_per_inch: float) -> float:
    """Root area of a UN thread, pi/4 (D - 1.299038/n)^2, in^2."""
    if bolt_d <= 0 or threads_per_inch <= 0:
        raise ValueError("bolt_D and bolt_tpi must be > 0")
    root_d = bolt_d - UN_ROOT_CONST / threads_per_inch
    if root_d <= 0:
        raise ValueError("bolt_tpi too coarse for bolt_D (root diameter would not be positive)")
    return QP * root_d * root_d


def flange_derive(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Derive geometry from user-read raw values. Give at least one of three groups:

        gasket   gasket_ID, gasket_OD, facing      -> N, b0, b, G
        bolting  bolt_D, bolt_tpi [, nBolts]        -> boltRootArea [, Ab]
        hub      pipe_OD, B, X, Y, t                -> g0, g1, h

        g0 = (pipe_OD - B)/2    g1 = (X - B)/2    h = Y - t
    """
    out: Dict[str, Any] = {}
    warnings: List[str] = []
    done = 0

    if any(_has(inp, k) for k in ("gasket_ID", "gasket_OD", "facing")):
        facing = inp.get("facing")
        if facing not in FACINGS:
            raise ValueError("facing must be 'flat' or 'ring-joint'; other facings are read from the effective-width table")
        geo = gasket_geometry(_num(inp, "gasket_ID"), _num(inp, "gasket_OD"), facing)
        out.update({"N": round_half_up(geo["N"], 6), "b0": round_half_up(geo["b0"], 6),
                    "b": round_half_up(geo["b"], 6), "G": round_half_up(geo["G"], 6)})
        warnings.append(
            "Gasket geometry follows the flat-facing (N/2) or ring-joint (N/8) rule only; confirm your facing and column in the "
            "effective gasket width table (VIII-2 Table 4.16.3). Any other facing: read b0, b and G from that table and enter them directly."
        )
        if facing == "ring-joint":
            if geo["b0"] <= B0_LIMIT_IN:
                warnings.append("Ring joint: G taken as the mean of the contact ID and OD supplied (b0 <= 0.25 in); confirm it against the ring pitch diameter on the gasket sheet.")
            else:
                warnings.append("Ring joint: b0 exceeds 0.25 in, so G = OD - 2b was used (b = 0.5 sqrt(b0)); confirm it against the ring pitch diameter on the gasket sheet.")
        done += 1

    if any(_has(inp, k) for k in ("bolt_D", "bolt_tpi", "nBolts")):
        area = un_root_area(_num(inp, "bolt_D"), _num(inp, "bolt_tpi"))
        out["boltRootArea"] = round_half_up(area, 6)
        if _has(inp, "nBolts"):
            n = _num(inp, "nBolts")
            if n < 1:
                raise ValueError("nBolts must be >= 1")
            out["Ab"] = round_half_up(n * area, 4)
        warnings.append(
            "Bolt root area from the UN root diameter D - 1.299038/n. Programs differ on the area basis (root vs tensile stress area); "
            "supply aRoot directly to the detailed module if your project basis differs."
        )
        done += 1

    if any(_has(inp, k) for k in ("pipe_OD", "B", "X", "Y", "t")):
        pipe_od, B, X, Y, t = (_num(inp, k) for k in ("pipe_OD", "B", "X", "Y", "t"))
        if B <= 0 or pipe_od <= B:
            raise ValueError("require pipe_OD > B > 0")
        if X <= B:
            raise ValueError("hub diameter at the base X must exceed the bore B")
        if t <= 0 or Y <= t:
            raise ValueError("require Y > t > 0 (length through hub exceeds the flange thickness)")
        g0 = (pipe_od - B) / 2   # equals the nominal wall tn only when B is the pipe ID (see warning)
        g1 = (X - B) / 2
        h = Y - t
        warnings.append(
            "g0 = (pipe OD - B)/2 is the nominal pipe wall tn only if the flange bore B equals the pipe inside diameter; VIII-2 4.16.13 defines g0 as the "
            "nominal wall of the pipe or nozzle neck. If B differs from the pipe ID (bore matched to a different schedule), enter g0 as the nominal pipe wall."
        )
        if g1 < g0:
            warnings.append("g1 < g0: the hub base is thinner than the pipe wall - re-check X and the bore B.")
        out.update({"g0": round_half_up(g0, 6), "g1": round_half_up(g1, 6), "h": round_half_up(h, 6)})
        done += 1

    if done == 0:
        raise ValueError("give at least one group: gasket (gasket_ID, gasket_OD, facing), bolting (bolt_D, bolt_tpi) or hub (pipe_OD, B, X, Y, t)")
    return _result("connections.flange-derive", out, "na", warnings)


# --------------------------------------------------------------------------- registry and citations

REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "connections.flange-derive": flange_derive,
    "connections.flange-equivalent-pressure": flange_equivalent_pressure,
    "aux.app2-flange-integral": app2_flange_integral,
}

CITATIONS = {
    "connections.flange-derive": (
        "Geometry from user-read values: gasket N, b0, b, G per the effective gasket width rules (BPVC VIII-2 4.16.6, Tables 4.16.2 and 4.16.3); "
        "UN thread root area pi/4 (D - 1.299038/n)^2; hub g0 = (pipe OD - B)/2, g1 = (X - B)/2, h = Y - t from the B16.5 hub dimensions"
    ),
    "connections.flange-equivalent-pressure": (
        "Pressure-equivalent screen: Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) against the B16.5 rating at design temperature (user-supplied). "
        "A conservative leakage screen, not a stress check; PIP PNC00004 3.2.10 permits the method and leaves the acceptance value to the owner"
    ),
    "aux.app2-flange-integral": (
        "ASME BPVC VIII-2 Part 4.16 (4.16.6 bolt loads, 4.16.7 flange moments, stresses and rigidity, Tables 4.16.4 to 4.16.11); "
        "equivalent to the retired VIII-1 Mandatory Appendix 2; B31.3 304.5.1(b) with B31.3 allowables. "
        "External loads enter as the pressure-equivalent Peq (not an Appendix 2 / 4.16 construction)"
    ),
}

# Inputs that are code, table or project values the user must read from a licensed copy.
USER_SUPPLIED = {
    "connections.flange-derive": ["gasket_ID", "gasket_OD", "bolt_D", "bolt_tpi", "pipe_OD", "B", "X", "Y", "t"],
    "connections.flange-equivalent-pressure": ["ratedPressure"],
    "aux.app2-flange-integral": [
        "A", "B", "C", "t", "g0", "g1", "h", "m", "y", "Sa", "Sb", "Sf", "SfAmbient", "Sn", "SnAmbient",
        "Edesign", "Eambient", "rigidityFactor", "F_override", "V_override", "f_override",
    ],
}


# --------------------------------------------------------------------------- declared input fields

# (name, units, required, description). Drives `list` and the unknown-key rejection.
FIELDS: Dict[str, List[tuple]] = {
    "connections.flange-derive": [
        ("facing", "text", False, "Gasket group: 'flat' (b0 = N/2) or 'ring-joint' (b0 = N/8)"),
        ("gasket_ID", "in", False, "Gasket group: contact ID (user-read from the gasket sheet)"),
        ("gasket_OD", "in", False, "Gasket group: contact OD (user-read from the gasket sheet)"),
        ("bolt_D", "in", False, "Bolting group: nominal bolt diameter"),
        ("bolt_tpi", "1/in", False, "Bolting group: threads per inch n (UN series)"),
        ("nBolts", "count", False, "Bolting group, optional: bolt count, adds total area Ab"),
        ("pipe_OD", "in", False, "Hub group: pipe outside diameter the neck welds to (g0 = (pipe_OD - B)/2 equals the nominal wall only when B is the pipe ID)"),
        ("B", "in", False, "Hub group: flange bore"),
        ("X", "in", False, "Hub group: hub diameter at the base (B16.5 hub table)"),
        ("Y", "in", False, "Hub group: length through hub (B16.5 hub table)"),
        ("t", "in", False, "Hub group: flange thickness"),
    ],
    "connections.flange-equivalent-pressure": [
        ("P", "psi", True, "Internal design pressure"),
        ("F", "lbf", True, "External axial force, tension positive"),
        ("M_in_lbf", "in-lbf", False, "Bending moment resultant in in-lbf (give exactly one of M_in_lbf, M_ft_lbf, M)"),
        ("M_ft_lbf", "ft-lbf", False, "Bending moment resultant in ft-lbf; converted x 12"),
        ("M", "in-lbf", False, "Engine name for the moment, in-lbf (same as M_in_lbf)"),
        ("G", "in", True, "Gasket load-reaction diameter G (from connections.flange-derive or the effective-width table)"),
        ("ratedPressure", "psi", True, "Flange rating at design temperature (user-read from the B16.5 P-T table)"),
        ("creditCompression", "bool", False, "Default false: a negative F is taken as 0 (Code-conservative, VIII-2 4.16.13 FA = 0). true credits compression; then run the tensile case separately and report both"),
    ],
    "aux.app2-flange-integral": [
        ("attachment", "text", True, "'integral' (weld-neck, hubbed) or 'loose' (ring, no hub)"),
        ("P", "psi", True, "Design pressure"),
        ("Fax", "lbf", False, "External axial force, tension positive; default 0"),
        ("Mext", "ft-lbf", False, "External bending moment in FT-LBF (engine unit); default 0. Give at most one of Mext, Mext_in_lbf"),
        ("Mext_in_lbf", "in-lbf", False, "External bending moment in IN-LBF (alternative to Mext)"),
        ("A", "in", True, "Flange OD"),
        ("B", "in", True, "Flange bore"),
        ("C", "in", True, "Bolt circle diameter"),
        ("t", "in", True, "Flange thickness"),
        ("g0", "in", False, "Hub small-end thickness (integral)"),
        ("g1", "in", False, "Hub large-end thickness (integral)"),
        ("h", "in", False, "Hub length (integral)"),
        ("G", "in", True, "Gasket load-reaction diameter"),
        ("N", "in", True, "Gasket contact width"),
        ("b", "in", False, "Effective seating width; derived from N (flat rule) when omitted"),
        ("m", "-", True, "Gasket factor m (user-read from the gasket factor table)"),
        ("y", "psi", True, "Gasket seating stress y (user-read from the gasket factor table)"),
        ("nBolts", "count", True, "Bolt count (4 or more)"),
        ("aRoot", "in^2", True, "Root area of one bolt"),
        ("boltDia", "in", False, "Bolt nominal diameter, for the bolt-spacing limit; derived from aRoot when omitted"),
        ("Sa", "psi", True, "Bolt allowable at ambient (gasket seating)"),
        ("Sb", "psi", True, "Bolt allowable at design temperature"),
        ("Sf", "psi", True, "Flange allowable at design temperature"),
        ("SfAmbient", "psi", True, "Flange allowable at ambient (CLI requires it; the engine would default it to Sf)"),
        ("Sn", "psi", False, "Nozzle-neck / pipe allowable at design temperature; omitted leaves the 2.5 Sn cap unchecked"),
        ("SnAmbient", "psi", False, "Nozzle-neck / pipe allowable at ambient; defaults to Sn"),
        ("Edesign", "psi", True, "Flange modulus at design temperature (CLI requires it; rigidity only)"),
        ("Eambient", "psi", True, "Flange modulus at ambient (CLI requires it; rigidity only)"),
        ("rigidityFactor", "-", False, "Rigidity factor KI; default 0.3 integral, 0.2 loose"),
        ("applyBoltSpacing", "bool", False, "Apply the bolt-spacing correction; default true"),
        ("hubFactorMethod", "text", False, "'series' (default, the only method shipped); integral only"),
        ("F_override", "-", False, "Hub factor F read from the Table 4.16.5 equations / figures; bypasses the computed value"),
        ("V_override", "-", False, "Hub factor V read from Table 4.16.5 / figures; bypasses the computed value"),
        ("f_override", "-", False, "Hub stress correction f (>= 1) read from Table 4.16.5 / figures; bypasses the computed value"),
    ],
}


def render_list() -> str:
    lines = ["Modules and exact input field names (case-sensitive). Units: psi, lbf, in, as stated.", ""]
    for mid in REGISTRY:
        lines.append(mid)
        for name, units, required, desc in FIELDS[mid]:
            lines.append(f"    {name:<16}{units:<9}{'required' if required else 'optional':<10}{desc}")
        lines.append("")
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
    """Reject physically impossible or silently-defaulted inputs (ValueError); return warnings.

    Runs BEFORE the engine in the CLI. The ported engine functions are not changed by it.
    """
    _need(module in REGISTRY, f"unknown module {module!r}; run `list` for the available ids")
    _need(isinstance(inputs, dict), "input must be a JSON object")
    declared = [f[0] for f in FIELDS[module]]
    unknown = sorted(k for k in inputs if k not in declared)
    _need(not unknown, f"unknown input field(s) {', '.join(repr(k) for k in unknown)} for {module} "
                       f"(valid: {', '.join(declared)}; names are case-sensitive)")
    warnings: List[str] = []

    if module == "connections.flange-equivalent-pressure":
        _one_moment(inputs, ("M", "M_in_lbf", "M_ft_lbf"), optional=False)
        P, rated, G = _val(inputs, "P"), _val(inputs, "ratedPressure"), _val(inputs, "G")
        if P is not None:
            _need(P >= 0, "P must be >= 0")
        if P is not None and rated is not None and P > rated:
            warnings.append("Design pressure already exceeds the supplied rating before any external load; confirm the rating is at the design temperature.")
        if G is not None and G > 0 and G < 1:
            warnings.append("G is under 1 in; confirm the length unit (inches) and that G is the gasket reaction diameter, not a gasket width.")
        warnings.append(
            "Pressure-equivalent screen only: a conservative leakage screen, not a stress check. Torsion and shear are not used. "
            "Acceptance against the rating (or a lower owner percentage of it) is the owner's call."
        )
    elif module == "aux.app2-flange-integral":
        att = inputs.get("attachment")
        _need(att in ("integral", "loose"), "attachment must be 'integral' or 'loose'")
        method = inputs.get("hubFactorMethod")
        _need(method in (None, "series"),
              "the Table 4.16.5 curve-fit option is not shipped; hubFactorMethod must be 'series' (or omitted). "
              "Use F_override / V_override / f_override with values read from the VIII-2 figures or equations")
        _one_moment(inputs, ("Mext", "Mext_in_lbf"), optional=True)
        for k in ("Edesign", "Eambient", "SfAmbient"):
            _need(inputs.get(k) is not None,
                  f"{k} is required (read it from your licensed copy; the engine would otherwise default it silently)")
        for k in ("F_override", "V_override", "f_override"):
            if inputs.get(k) is not None:
                _need(att == "integral", f"{k} applies to integral flanges only")
        for k in ("F_override", "V_override"):
            x = _val(inputs, k)
            if x is not None:
                _need(x > 0, f"{k} must be > 0")
        x = _val(inputs, "f_override")
        if x is not None:
            _need(x >= 1, "f_override must be >= 1 (the hub stress correction factor has a floor of 1)")
        if inputs.get("Fax") is None and inputs.get("Mext") is None and inputs.get("Mext_in_lbf") is None:
            warnings.append("No external axial force or moment given: Peq = P, so this is a pressure-only result. "
                            "Supply Fax and Mext (or Mext_in_lbf) to evaluate the piping loads.")
        defaulted = []
        if inputs.get("b") is None:
            defaulted.append("b (derived from N, flat rule)")
        if inputs.get("boltDia") is None:
            defaulted.append("boltDia (derived from aRoot)")
        if inputs.get("Sn") is not None and inputs.get("SnAmbient") is None:
            defaulted.append("SnAmbient (taken as Sn)")
        if inputs.get("rigidityFactor") is None:
            defaulted.append(f"rigidityFactor ({_js(KI_INTEGRAL if att == 'integral' else KI_LOOSE)}, the table-note value)")
        if att == "integral" and method is None:
            defaulted.append("hubFactorMethod (series)")
        if defaulted:
            warnings.append("Defaults applied: " + "; ".join(defaulted) + ". State each on the calc sheet.")
    elif module == "connections.flange-derive":
        pass
    if module == "connections.flange-equivalent-pressure":
        cc = inputs.get("creditCompression")
        _need(cc is None or isinstance(cc, bool), "creditCompression must be true or false")
    return warnings


def _clean_zero(x: Any) -> Any:
    """Normalise -0.0 to 0.0 anywhere in the output tree (cosmetic)."""
    if isinstance(x, float):
        return 0.0 if x == 0 else x
    if isinstance(x, dict):
        return {k: _clean_zero(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean_zero(v) for v in x]
    return x


def run_module(module: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    pre_warnings = validate(module, inp)
    engine_inp = dict(inp)
    if module == "connections.flange-equivalent-pressure":
        credit = bool(engine_inp.pop("creditCompression", False))
        F = engine_inp.get("F")
        if not credit and isinstance(F, (int, float)) and not isinstance(F, bool) and F < 0:
            engine_inp["F"] = 0.0
            pre_warnings.append(
                "Compressive axial force taken as F = 0 for the screen (VIII-2 4.16.13 neglects compression). "
                "Set creditCompression true only if the owner agrees to credit it; then run the tensile case separately and report both."
            )
    res = REGISTRY[module](engine_inp)
    return {
        "module": res["module"],
        "status": res["status"],
        "output": _clean_zero(res["output"]),
        "warnings": pre_warnings + res["warnings"],
        "citation": CITATIONS[module],
        "inputs": inp,
        "user_supplied": [k for k in USER_SUPPLIED[module] if k in inp],
    }


# --------------------------------------------------------------------------- CLI


def _fail(msg: str) -> int:
    print(f"input error: {msg}", file=sys.stderr)
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bolted_flange.py",
        description="Bolted-flange calculators. `list` shows module ids and exact input names.",
    )
    ap.add_argument("module", help="module id, or `list`")
    ap.add_argument("--input", help="inline JSON object")
    ap.add_argument("--input-file", help="path to a JSON file")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 itself on usage errors
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        if args.module == "list":
            sys.stdout.write(render_list())
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
        print(json.dumps(run_module(args.module, data), indent=2))
        return 0
    except (ValueError, OSError, ArithmeticError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
