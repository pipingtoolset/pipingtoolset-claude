"""Concrete pier and soil-bearing checks - the bottom of the pipe-support load path.

Exact port of the Piping Toolset PiperSTR engine ``structural/pier-soil.ts``. ACI 318-19 for the
concrete (punching shear), classical stability mechanics for the soil interface (bearing,
overturning, sliding). Soil properties are geotechnical-report values and are ALWAYS
user-supplied - nothing is assumed.

Units: in, kip, ksi; soil bearing in ksf; f'c in psi. Input/output dict keys are the
TypeScript names unchanged.

Public API: ``pier_soil(input)``.
"""

from __future__ import annotations

import math

from .common import InputError, result, round_half_up
from .jsmath import div, jmax, jmin, js_num, nn, sqrt, truthy

MODULE = "structural.pier-soil"

_IN2_PER_FT2 = 144
_CONCRETE_PCF = 150


def _row(label, demand, capacity, clause):
    d = abs(demand)
    if d <= 1e-12:
        return {"label": label, "demand": 0, "capacity": capacity, "ratio": 0, "clause": clause, "status": "na"}
    ratio = d / capacity if capacity > 0 else math.inf
    return {"label": label, "demand": d, "capacity": capacity, "ratio": ratio, "clause": clause,
            "status": "pass" if ratio <= 1.0 else "fail"}


def pier_soil(input):
    """Pier and soil check. Stability is evaluated at SERVICE level regardless of method;
    the punching-shear check is a strength check and uses ACI's phi."""
    if not isinstance(input, dict):
        raise InputError("input must be a dict")
    for k in ("method", "pierLength", "pierWidth", "pierHeight", "fc", "allowableBearing"):
        if input.get(k) is None:
            raise InputError(f"missing required input '{k}'")
    method = input["method"]
    Lp = input["pierLength"]
    Bp = input["pierWidth"]
    Hp = input["pierHeight"]
    fc = input["fc"]
    allowableBearing = input["allowableBearing"]

    if Lp <= 0 or Bp <= 0 or Hp <= 0:
        raise InputError("pier dimensions must be positive")
    if fc <= 0:
        raise InputError("f'c must be positive")
    if allowableBearing <= 0:
        raise InputError("allowable soil bearing must be positive")

    warnings = []
    checks = []

    Lf = nn(input, "footingLength", Lp)
    Bf = nn(input, "footingWidth", Bp)
    Tf = nn(input, "footingThickness", 0)
    cover = nn(input, "embedment", 0)

    P = nn(input, "P", 0)
    uplift = nn(input, "uplift", 0)
    M = nn(input, "M", 0)
    V = nn(input, "V", 0)

    # --- self weight ------------------------------------------------------------
    pierVol = (Lp * Bp * Hp) / 1728  # ft^3
    footVol = (Lf * Bf * Tf) / 1728
    soilVol = jmax(0, ((Lf * Bf - Lp * Bp) * cover) / 1728)
    selfWeight = ((pierVol + footVol) * _CONCRETE_PCF + soilVol * nn(input, "soilUnitWeight", 0)) / 1000  # kip

    # --- overturning / bearing at the base --------------------------------------
    leverArm = Hp + Tf  # shear acts at the top of the pier
    totalMoment = abs(M) + abs(V) * leverArm
    totalVertical = P - uplift + selfWeight

    e = totalMoment / totalVertical if abs(totalVertical) > 1e-9 else math.inf
    kern = Lf / 6
    partialBearing = (not math.isfinite(e)) or e > kern

    areaFt2 = (Lf * Bf) / _IN2_PER_FT2
    restraint = nn(input, "restraint", "gravity")

    if restraint == "anchored":
        # Load leaves through the pier-to-concrete interface and the anchors, not a soil block.
        qMax = 0
        qMin = 0
    elif totalVertical <= 0:
        qMax = math.inf
        qMin = 0
        warnings.append("Net vertical load at the soil interface is zero or uplift — the foundation is not stable under this load case without tie-down or added mass.")
    elif not partialBearing:
        # Full contact: linear trapezoidal distribution.
        axial = div(totalVertical, areaFt2)
        bending = div(totalMoment / 12, (Bf * Lf * Lf) / (6 * 1728))  # ksf
        qMax = axial + bending
        qMin = axial - bending
    else:
        # Resultant outside the kern: triangular block over 3*(L/2 - e).
        aLen = 3 * (Lf / 2 - e)  # in
        if aLen <= 0:
            qMax = math.inf
            qMin = 0
            warnings.append("Resultant falls outside the footing — the base overturns. Enlarge the footing or reduce the eccentricity.")
        else:
            qMax = div(2 * totalVertical, (aLen * Bf) / _IN2_PER_FT2)
            qMin = 0
            warnings.append(
                f"Resultant is outside the kern (e = {js_num(round_half_up(e, 2))} in > L/6 = {js_num(round_half_up(kern, 2))} in) — bearing over only {js_num(round_half_up(aLen, 1))} in of the {js_num(Lf)} in footing.")

    if restraint != "anchored":
        checks.append(_row("Soil bearing pressure", qMax, allowableBearing,
                           "Service-level bearing vs the geotechnical allowable"))

    # --- overturning and sliding -------------------------------------------------
    overturningFS = nn(input, "overturningFS", 1.5)
    slidingFS = nn(input, "slidingFS", 1.5)
    mu = nn(input, "frictionCoefficient", 0)
    coh = nn(input, "cohesion", 0)
    resistingMoment = totalVertical * (Lf / 2) if totalVertical > 0 else 0
    slidingResistance = jmax(0, totalVertical) * mu + coh * areaFt2
    overturningRatio = 0
    slidingRatio = 0

    if restraint == "anchored":
        warnings.append(
            "Base modelled as ANCHORED into existing concrete: overturning, sliding and soil bearing are not evaluated here. "
            "Overturning and sliding are resisted by the anchorage, which the anchor stage checks (tension, breakout, pullout, "
            "shear, pryout); load leaves through the pier-to-concrete bearing interface below. Confirm the EXISTING structure "
            "can accept the base reactions reported above."
        )
    else:
        overturningRatio = (overturningFS * totalMoment) / jmax(resistingMoment, 1e-9) if totalMoment > 0 else 0
        checks.append(_row(f"Overturning (FS {js_num(overturningFS)})", overturningFS * totalMoment, resistingMoment,
                           "Gravity stability — resisting moment = N·L/2 about the toe"))

        slidingRatio = (slidingFS * V) / jmax(slidingResistance, 1e-9) if V > 0 else 0
        if V > 0 and mu == 0 and coh == 0:
            warnings.append("Base shear is present but no friction coefficient or cohesion was supplied — the sliding check could not be evaluated. Both are geotechnical report values.")
        else:
            checks.append(_row(f"Sliding (FS {js_num(slidingFS)})", slidingFS * V, slidingResistance,
                               "Resistance = mu·N + c·A (user-supplied soil properties)"))

    # --- punching (two-way) shear on the footing, ACI 318-19 22.6 ----------------
    plateLength = input.get("plateLength")
    plateWidth = input.get("plateWidth")
    if Tf > 0 and truthy(plateLength) and truthy(plateWidth):
        dEff = jmax(1, Tf - 4)  # effective depth, 3 in cover + bar
        c1 = plateLength
        c2 = plateWidth
        bo = 2 * (c1 + dEff) + 2 * (c2 + dEff)  # critical perimeter at d/2
        beta = div(jmax(c1, c2), jmin(c1, c2))
        alphaS = 40  # interior column
        # ACI 22.6.5.2 - the least of the three expressions.
        vc = jmin(
            4 * sqrt(fc),
            (2 + div(4, beta)) * sqrt(fc),
            (2 + div(alphaS * dEff, bo)) * sqrt(fc),
        ) / 1000  # ksi
        phiVc = (0.75 if method == "LRFD" else 0.75 / 1.5) * vc * bo * dEff  # kip
        # Punching demand is the column load less the soil pressure inside the perimeter.
        insideAreaFt2 = ((c1 + dEff) * (c2 + dEff)) / _IN2_PER_FT2
        Vpunch = jmax(0, P - jmin(qMax, allowableBearing) * insideAreaFt2)
        checks.append(_row("Punching (two-way) shear", Vpunch, phiVc, "ACI 318-19 22.6.5.2"))
    elif Tf > 0:
        warnings.append("Footing thickness given without a base-plate footprint — the punching-shear check was skipped.")

    # --- pier bearing on the footing ---------------------------------------------
    pierBearing = (0.65 if method == "LRFD" else 1 / 2.31) * 0.85 * (fc / 1000) * (Lp * Bp)
    checks.append(_row("Pier concrete bearing", P, pierBearing, "ACI 318-19 14.5.6.2 / AISC J8"))

    if Tf == 0:
        warnings.append("No footing modelled — the pier is taken as bearing directly on soil. Add a footing thickness and plan size to include punching shear and spread-footing bearing.")
    if method == "LRFD":
        warnings.append("Soil bearing, overturning and sliding are evaluated at SERVICE level against the allowable bearing and the stated factors of safety — pass service (unfactored) demands for those, not LRFD-factored loads.")

    # Infinity (zero capacity / resultant off the footing) must win the roll-up.
    real = [c for c in checks if c["status"] != "na"]
    if real:
        governing = real[0]
        for b in real[1:]:
            if b["ratio"] > governing["ratio"]:
                governing = b
    else:
        governing = checks[0]

    def r4(v):
        return round_half_up(v, 4) if math.isfinite(v) else v

    out_checks = []
    for c in checks:
        cc = dict(c)
        cc["demand"] = r4(c["demand"])
        cc["capacity"] = r4(c["capacity"])
        cc["ratio"] = r4(c["ratio"])
        out_checks.append(cc)

    out = {
        "selfWeight": r4(selfWeight), "totalVertical": r4(totalVertical), "totalMoment": r4(totalMoment),
        "eccentricity": r4(e), "kern": r4(kern),
        "soilPressureMax": r4(qMax), "soilPressureMin": r4(jmax(0, qMin)),
        "partialBearing": partialBearing,
        "overturningRatio": r4(overturningRatio), "slidingRatio": r4(slidingRatio),
        "checks": out_checks,
        "governingRatio": r4(governing["ratio"]),
        "governingCheck": governing["label"],
    }
    return result(MODULE, out, "pass" if all(c["status"] != "fail" for c in checks) else "fail", warnings)
