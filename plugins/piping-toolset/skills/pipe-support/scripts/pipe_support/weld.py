"""Fillet-weld design - AISC 360-22 Chapter J2: J2.4(a) Eq. J2-4 (Rn = Fnw*Awe*kds).

kds = 1.0 by default ("all other conditions"); the Eq. J2-5 directional factor only with the
``strainCompatibility`` opt-in on a linear group loaded through its CG. The J2.2b(c)/(d) fillet
limits and the J4 base-metal checks (J4-3 shear yielding, J4-4 shear rupture) are included.

Exact port of the Piping Toolset PiperSTR engine's ``connection-weld`` TypeScript module. Units: in, kip,
ksi. Input/output dict keys are the TypeScript names unchanged.

Public API: ``fillet_weld(input) -> CalcResult dict``, ``min_fillet_size(t) -> float``.
"""

from __future__ import annotations

import math

from .common import InputError, result, round_half_up, verdict
from .jsmath import div, jmax, js_num, nn, pow_, truthy

MODULE = "structural.fillet-weld"

# phi / omega for welds (AISC Table J2.5) - connection-weld.ts PHI_WELD / OMEGA_WELD.
_PHI_WELD = 0.75
_OMEGA_WELD = 2.00
# J4.2(a) shear yielding of an element (Eq. J4-3) - connection-weld.ts PHI_SHEAR_YIELD / OMEGA_SHEAR_YIELD.
_PHI_SHEAR_YIELD = 1.00
_OMEGA_SHEAR_YIELD = 1.50
# aisc-section.ts PHI.tensionRupture / OMEGA.tensionRupture (J4-4 base-metal rupture).
_PHI_TENSION_RUPTURE = 0.75
_OMEGA_TENSION_RUPTURE = 2.00
# aisc-section.ts PHI.tensionYield / OMEGA.tensionYield (J4-1 base-metal tension yielding).
_PHI_TENSION_YIELD = 0.90
_OMEGA_TENSION_YIELD = 1.67


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
    """Fillet weld check (resultant stress on a unit-throat line, Eq. J2-4; kds per strainCompatibility)."""
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
    Lpattern = L
    length_in = input.get("length")
    if length_in is not None:
        if length_in <= 0:
            raise InputError("weld length must be positive")
        Sw *= length_in / L
        L = length_in

    # --- J2.2b(c)/(d): limits on one weld segment -------------------------------
    # One line of the group: the whole length for "single", half for "two-parallel", the
    # shorter side for "all-round" (each scaled with any supplied length override).
    if pattern == "single":
        segmentLength = L
    elif pattern == "two-parallel":
        segmentLength = L / 2
    else:
        segmentLength = min(depth, width) * (L / Lpattern)
    # J2.2b(c): a strength-designed fillet shorter than 4w is credited with an effective SIZE of
    # at most L/4. Applied to every line of the group (conservative for an all-round weld).
    wEff = w
    if segmentLength < 4 * w:
        wEff = min(w, segmentLength / 4)
        warnings.append(
            f"Weld segment length {js_num(round_half_up(segmentLength, 4))} in is less than 4x the {js_num(w)} in leg "
            f"size — AISC J2.2b(c): the effective weld size is limited to L/4 = {js_num(round_half_up(wEff, 4))} in, "
            "used for the throat.")
    # J2.2b(d): end-loaded fillets longer than 100w.
    endLoadedFactor = 1.0
    lw = segmentLength / w
    if lw > 100:
        if truthy(input.get("endLoaded")):
            endLoadedFactor = 180 / lw if lw > 300 else min(1.0, 1.2 - 0.002 * lw)
            if lw > 300:
                warnings.append(
                    f"End-loaded fillet {js_num(round_half_up(segmentLength, 4))} in long exceeds 300w — AISC J2.2b(d): "
                    f"effective length taken as 180w = {js_num(round_half_up(180 * w, 4))} in "
                    f"(capacity x {js_num(round_half_up(endLoadedFactor, 4))}).")
            else:
                warnings.append(
                    f"End-loaded fillet {js_num(round_half_up(segmentLength, 4))} in long exceeds 100w — AISC J2.2b(d) "
                    f"Eq. J2-1: beta = 1.2 - 0.002(l/w) = {js_num(round_half_up(endLoadedFactor, 4))} applied to the capacity.")
        else:
            warnings.append(
                f"Weld segment {js_num(round_half_up(segmentLength, 4))} in is longer than 100w. If the fillet is "
                "END-LOADED, AISC J2.2b(d) Eq. J2-1 reduces its effective length (beta = 1.2 - 0.002 l/w) — set "
                "endLoaded to apply it.")

    throat = 0.707 * wEff
    Awe = throat * L

    # --- stress resultant on the unit-throat line (kip/in) --------------------
    Vt = nn(input, "Vtransverse", 0)
    Vp = nn(input, "Vparallel", 0)
    P = nn(input, "Pnormal", 0)
    M = nn(input, "M", 0)

    fTransverse = math.hypot(Vt / L, P / L + (M / Sw if Sw > 0 else 0))
    fParallel = Vp / L
    fResultant = math.hypot(fTransverse, fParallel)

    # Angle of the resultant to the weld longitudinal axis (Eq. J2-5).
    theta = math.atan2(fTransverse, abs(fParallel)) if fResultant > 0 else 0

    # kds (J2.4(a)): Eq. J2-5 only where strain compatibility is satisfied - an explicit opt-in
    # valid only for a linear group loaded through its CG.
    directionalFactor = 1.0
    if input.get("strainCompatibility") == "linear-through-cg":
        if pattern == "all-round":
            warnings.append("strainCompatibility 'linear-through-cg' ignored: an all-round weld is not a linear weld "
                            "group (AISC J2.4(a) User Note) — kds = 1.0.")
        elif M != 0:
            warnings.append("strainCompatibility 'linear-through-cg' ignored: the group carries moment, so it is not "
                            "loaded through its centre of gravity (AISC J2.4(a) User Note) — kds = 1.0.")
        else:
            directionalFactor = 1.0 + 0.5 * pow_(math.sin(theta), 1.5)  # Eq. J2-5

    # --- design strength: J2.4(a) Eq. J2-4, Rn = Fnw*Awe*kds ---------------------
    Fnw = 0.6 * FEXX  # Table J2.5
    designPerInch = endLoadedFactor * _design(Fnw * throat * directionalFactor, method, _PHI_WELD, _OMEGA_WELD)
    demandPerInch = fResultant
    ratio = demandPerInch / designPerInch if designPerInch > 0 else math.inf

    # --- size limits -----------------------------------------------------------
    tBase = input.get("basePartThickness")
    minSize = min_fillet_size(tBase) if truthy(tBase) else 0
    # J2.2b(b): along an edge of material 1/4 in or thicker, w <= t - 1/16.
    if truthy(tBase):
        maxSize = tBase if tBase < 0.25 else tBase - 0.0625
    else:
        maxSize = math.inf
    if truthy(tBase) and w < minSize:
        warnings.append(
            f"Fillet size {js_num(w)} in is below the Table J2.4 minimum of {js_num(minSize)} in for a {js_num(tBase)} in part.")
    if truthy(tBase) and input.get("alongEdge") is not False and w > maxSize:
        warnings.append(
            f"Fillet size {js_num(w)} in exceeds the J2.2b maximum of {js_num(round_half_up(maxSize, 4))} in along the edge of a {js_num(tBase)} in part.")

    # --- base metal (J4), split by direction ------------------------------------
    # The moment and axial force pull the base metal NORMAL to the weld: tension yielding (J4-1) and
    # rupture (J4-2). The direct shears run along it: the lower of shear yielding (J4-3) and shear
    # rupture (J4-4), per J4.2. Each component is checked against its own limit state on the
    # thickness available to one weld line; the highest ratio governs.
    bf = input.get("baseForces")
    normalPerInch = abs((bf["normal"] if bf else P) / L + (M / Sw if Sw > 0 else 0))
    shearPerInch = abs(bf["shear"]) / L if bf else math.hypot(Vt / L, Vp / L)
    tJ4 = input.get("baseMetalThickness")
    if tJ4 is None:
        tJ4 = tBase
    baseTensionYieldPerInch = None
    baseTensionRupturePerInch = None
    baseShearYieldPerInch = None
    baseShearRupturePerInch = None
    baseMetalPerInch = None
    baseMetalRatio = None
    baseFu = input.get("baseFu")
    if truthy(baseFu) and truthy(tJ4):
        def over(d, c):
            return d / c if c > 0 else math.inf
        baseFy = input.get("baseFy")
        baseTensionRupturePerInch = _design(baseFu * tJ4, method, _PHI_TENSION_RUPTURE, _OMEGA_TENSION_RUPTURE)
        baseShearRupturePerInch = _design(0.6 * baseFu * tJ4, method, _PHI_TENSION_RUPTURE, _OMEGA_TENSION_RUPTURE)  # J4-4
        baseMetalPerInch = baseShearRupturePerInch
        if truthy(baseFy):
            baseShearYieldPerInch = _design(0.6 * baseFy * tJ4, method, _PHI_SHEAR_YIELD, _OMEGA_SHEAR_YIELD)  # J4-3
            baseMetalPerInch = min(baseShearYieldPerInch, baseShearRupturePerInch)
        ratios = [over(normalPerInch, baseTensionRupturePerInch), over(shearPerInch, baseMetalPerInch)]
        if truthy(baseFy):
            baseTensionYieldPerInch = _design(baseFy * tJ4, method, _PHI_TENSION_YIELD, _OMEGA_TENSION_YIELD)
            ratios.append(over(normalPerInch, baseTensionYieldPerInch))
        baseMetalRatio = jmax(*ratios)
        # Said only when it matters (P.E. ruling 2026-10-26): the J4 rows are always in the
        # table, so the warning is reserved for a joint using at least half its base metal.
        if baseMetalRatio > ratio and baseMetalRatio >= 0.5:
            warnings.append("Base metal governs over the weld metal (AISC J4) — the connected part, not the fillet, sets this joint's strength.")

    if M != 0 and pattern == "single":
        warnings.append("A single fillet carrying moment is eccentric and not self-balancing — confirm the joint detail can develop it.")

    def r4(v):
        return round_half_up(v, 4)

    out = {
        "length": r4(L), "throat": r4(throat), "effectiveSize": r4(wEff),
        "segmentLength": r4(segmentLength), "endLoadedFactor": r4(endLoadedFactor),
        "Awe": r4(Awe), "Sw": r4(Sw),
        "stress": r4(fResultant / throat),
        "theta": r4((theta * 180) / math.pi),
        "directionalFactor": r4(directionalFactor),
        "designPerInch": r4(designPerInch),
        "demandPerInch": r4(demandPerInch),
        "ratio": r4(ratio) if math.isfinite(ratio) else ratio,
        "minSize": r4(minSize),
        "maxSize": r4(maxSize) if math.isfinite(maxSize) else maxSize,
        "normalPerInch": r4(normalPerInch),
        "shearPerInch": r4(shearPerInch),
        "baseMetalThickness": r4(tJ4) if truthy(tJ4) else None,
        "baseTensionYieldPerInch": None if baseTensionYieldPerInch is None else r4(baseTensionYieldPerInch),
        "baseTensionRupturePerInch": None if baseTensionRupturePerInch is None else r4(baseTensionRupturePerInch),
        "baseShearYieldPerInch": None if baseShearYieldPerInch is None else r4(baseShearYieldPerInch),
        "baseShearRupturePerInch": None if baseShearRupturePerInch is None else r4(baseShearRupturePerInch),
        "baseMetalPerInch": None if baseMetalPerInch is None else r4(baseMetalPerInch),
        "baseMetalRatio": (None if baseMetalRatio is None
                           else r4(baseMetalRatio) if math.isfinite(baseMetalRatio) else baseMetalRatio),
    }
    # The joint is no stronger than its base metal: either limit state fails it.
    ok = ratio <= 1.0 and (baseMetalRatio is None or baseMetalRatio <= 1.0)
    return result(MODULE, out, verdict(ok), warnings)
