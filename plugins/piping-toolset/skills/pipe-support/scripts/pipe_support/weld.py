"""Fillet-weld design - AISC 360-22 Chapter J2 with the J2.4(b) directional increase.

Exact port of the Piping Toolset PiperSTR engine ``structural/connection-weld.ts``. Units: in, kip,
ksi. Input/output dict keys are the TypeScript names unchanged.

Public API: ``fillet_weld(input) -> CalcResult dict``, ``min_fillet_size(t) -> float``.
"""

from __future__ import annotations

import math

from .common import InputError, result, round_half_up
from .jsmath import div, js_num, nn, pow_, truthy

MODULE = "structural.fillet-weld"

# phi / omega for welds (AISC Table J2.5) - connection-weld.ts PHI_WELD / OMEGA_WELD.
_PHI_WELD = 0.75
_OMEGA_WELD = 2.00
# aisc-section.ts PHI.tensionRupture / OMEGA.tensionRupture (J4-4 base-metal rupture).
_PHI_TENSION_RUPTURE = 0.75
_OMEGA_TENSION_RUPTURE = 2.00


def _design(nominal, method, phi, omega):
    """aisc-section.ts design(): LRFD -> phi*Rn, otherwise (ASD) Rn/omega."""
    return phi * nominal if method == "LRFD" else div(nominal, omega)


def min_fillet_size(t):
    """Minimum fillet weld size, AISC Table J2.4, keyed on the thinner part joined."""
    if t <= 0.25:
        return 0.125
    if t <= 0.5:
        return 0.1875
    if t <= 0.75:
        return 0.25
    return 0.3125


def fillet_weld(input):
    """Fillet weld check (resultant stress on a unit-throat line, J2.4(b) increase)."""
    if not isinstance(input, dict):
        raise InputError("input must be a dict")
    for k in ("method", "size", "FEXX", "pattern", "depth"):
        if input.get(k) is None:
            raise InputError(f"missing required input '{k}'")
    method = input["method"]
    w = input["size"]
    FEXX = input["FEXX"]
    pattern = input["pattern"]
    depth = input["depth"]
    width = nn(input, "width", 0)
    if w <= 0:
        raise InputError("weld size must be positive")
    if FEXX <= 0:
        raise InputError("FEXX must be positive")
    if depth <= 0:
        raise InputError("weld depth must be positive")

    warnings = []

    # --- weld group geometry (unit throat) ------------------------------------
    if pattern == "two-parallel":
        L = 2 * depth
        Sw = (2 * depth * depth) / 6
    elif pattern == "all-round":
        if width <= 0:
            raise InputError("'all-round' pattern needs a width")
        L = 2 * (depth + width)
        Sw = (depth * depth) / 3 + width * depth
    elif pattern == "single":
        L = depth
        Sw = (depth * depth) / 6
    else:
        raise InputError(f"unknown weld pattern {pattern!r}")
    length_in = input.get("length")
    if length_in is not None:
        if length_in <= 0:
            raise InputError("weld length must be positive")
        Sw *= length_in / L
        L = length_in

    throat = 0.707 * w
    Awe = throat * L

    # --- stress resultant on the unit-throat line (kip/in) --------------------
    Vt = nn(input, "Vtransverse", 0)
    Vp = nn(input, "Vparallel", 0)
    P = nn(input, "Pnormal", 0)
    M = nn(input, "M", 0)

    fTransverse = math.hypot(Vt / L, P / L + (M / Sw if Sw > 0 else 0))
    fParallel = Vp / L
    fResultant = math.hypot(fTransverse, fParallel)

    theta = math.atan2(fTransverse, abs(fParallel)) if fResultant > 0 else 0
    directionalFactor = 1.0 + 0.5 * pow_(math.sin(theta), 1.5)

    # --- design strength -------------------------------------------------------
    Fnw = 0.6 * FEXX * directionalFactor  # J2-5
    designPerInch = _design(Fnw * throat, method, _PHI_WELD, _OMEGA_WELD)
    demandPerInch = fResultant
    ratio = demandPerInch / designPerInch if designPerInch > 0 else math.inf

    # --- size limits -----------------------------------------------------------
    tBase = input.get("basePartThickness")
    minSize = min_fillet_size(tBase) if truthy(tBase) else 0
    # J2.2b: along an edge of material 1/4 in or thicker, w <= t - 1/16.
    if truthy(tBase):
        maxSize = tBase if tBase < 0.25 else tBase - 0.0625
    else:
        maxSize = math.inf
    if truthy(tBase) and w < minSize:
        warnings.append(
            f"Fillet size {js_num(w)} in is below the Table J2.4 minimum of {js_num(minSize)} in for a {js_num(tBase)} in part.")
    if truthy(tBase) and w > maxSize:
        warnings.append(
            f"Fillet size {js_num(w)} in exceeds the J2.2b maximum of {js_num(round_half_up(maxSize, 4))} in along the edge of a {js_num(tBase)} in part.")

    # --- base metal shear rupture (J4-4) ---------------------------------------
    baseMetalPerInch = None
    baseFu = input.get("baseFu")
    if truthy(baseFu) and truthy(tBase):
        baseMetalPerInch = _design(0.6 * baseFu * tBase, method, _PHI_TENSION_RUPTURE, _OMEGA_TENSION_RUPTURE)
        if baseMetalPerInch < designPerInch:
            warnings.append("Base-metal shear rupture governs over the weld metal — the connected part, not the fillet, sets this joint's strength.")

    if M != 0 and pattern == "single":
        warnings.append("A single fillet carrying moment is eccentric and not self-balancing — confirm the joint detail can develop it.")
    if L / w < 4 and length_in is None:
        warnings.append("Weld length is less than 4x the leg size — J2.2b requires the effective length be taken as 1/4 of the actual length in that case.")

    def r4(v):
        return round_half_up(v, 4)

    out = {
        "length": r4(L), "throat": r4(throat), "Awe": r4(Awe), "Sw": r4(Sw),
        "stress": r4(fResultant / throat),
        "theta": r4((theta * 180) / math.pi),
        "directionalFactor": r4(directionalFactor),
        "designPerInch": r4(designPerInch),
        "demandPerInch": r4(demandPerInch),
        "ratio": r4(ratio) if math.isfinite(ratio) else ratio,
        "minSize": r4(minSize),
        "maxSize": r4(maxSize) if math.isfinite(maxSize) else maxSize,
        "baseMetalPerInch": None if baseMetalPerInch is None else r4(baseMetalPerInch),
    }
    return result(MODULE, out, "pass" if ratio <= 1.0 else "fail", warnings)
