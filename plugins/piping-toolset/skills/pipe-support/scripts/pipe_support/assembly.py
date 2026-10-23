"""Pipe-support assembly cascade - the whole point of PiperSTR.

Exact port of ``structural/support-assembly.ts``. One call walks the complete load path of
a standard structural pipe support and returns every limit state in a single envelope:

    pipe loads on an arm
      -> arm member check (AISC 360-22 D/E/F/G/H) + arm deflection
        -> arm-to-column fillet weld (J2)
          -> column member check with the accumulated axial + biaxial moment
            -> column-to-base-plate weld
              -> base plate bearing / yield (Design Guide 1)
                -> anchor steel, breakout, pullout, blowout, pryout (ACI 318-19 Ch.17)
                  -> pier bearing, soil pressure, overturning, sliding, punching

Every stage's reactions become the next stage's demands. Statics only (determinate
cantilever frames), so the result is exactly reproducible.

Assembly types: "t-post", "multi-tier", "cantilever" (no column or base), "goalpost" and
"trapeze" (two columns sharing the load 50/50). Units: in, kip, ksi, kip*in.

Input / output dict keys are the TypeScript names unchanged. Public API:

    analyze_assembly(inp, resolve_shape=None) -> {"module", "output", "status", "warnings"}
    CSA_PRESETS  - the two standard assemblies (deep-copy before editing)

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import copy
import math
from typing import Any, Callable, Dict, List, Optional

from .aisc import aisc_member_design, find_shape, section_from_row
from .baseplate import base_plate_anchorage
from .common import InputError, result, round_half_up
from .jsmath import div, js_num, nn
from .pier import pier_soil
from .weld import fillet_weld

MODULE = "structural.support-assembly"
NAN = math.nan


def _default_resolve(label: str) -> Dict[str, Any]:
    row = find_shape(label)
    if row is None:
        raise InputError(f"shape not in dataset: {label}")
    return section_from_row(row)


def _hypot(a: float, b: float) -> float:
    """Math.hypot as V8 computes it (scale by the max, Kahan-sum the squares)."""
    if a != a or b != b:
        return math.inf if (a in (math.inf, -math.inf) or b in (math.inf, -math.inf)) else NAN
    xs = [abs(a), abs(b)]
    mx = max(xs)
    if mx == 0:
        return 0.0
    if mx == math.inf:
        return math.inf
    total = 0.0
    comp = 0.0
    for x in xs:
        r = x / mx
        summand = r * r - comp
        preliminary = total + summand
        comp = (preliminary - total) - summand
        total = preliminary
    return math.sqrt(total) * mx


def _r4(v: Any) -> Any:
    return round_half_up(v, 4) if isinstance(v, (int, float)) and math.isfinite(v) else v


def _stage_from(stage: str, component: str, res: Dict[str, Any], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Infinity must win the roll-up - see aisc-member.ts.
    real = [c for c in checks if c["status"] != "na" and not c.get("advisory")]
    gov = None
    if real:
        gov = real[0]
        for b in real[1:]:
            if b["ratio"] > gov["ratio"]:
                gov = b
    if any(c["status"] == "fail" and not c.get("advisory") for c in checks):
        status = "fail"
    elif checks:
        status = "pass"
    else:
        status = "na"
    return {
        "stage": stage, "component": component,
        "status": status,
        "ratio": gov["ratio"] if gov else 0,
        "governing": gov["label"] if gov else "—",
        "checks": checks,
        "warnings": res["warnings"],
    }


def _num(d: Dict[str, Any], key: str, default: Any = 0) -> Any:
    return nn(d, key, default)


def analyze_assembly(inp: Dict[str, Any],
                     resolve_shape: Optional[Callable[[str], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Analyse a complete support assembly (port of analyzeAssembly).

    ``resolve_shape(label) -> SteelSection dict``; default looks the label up in the vendored
    AISC shapes dataset and raises InputError for an unknown label.
    """
    if not isinstance(inp, dict):
        raise InputError("input must be a dict")
    resolve = resolve_shape or _default_resolve
    method = inp.get("method")
    typ = inp.get("type")
    material = inp.get("material")
    arms = inp.get("arms")
    if material is None:
        raise InputError("missing required input 'material'")
    if arms is None:
        raise InputError("missing required input 'arms'")
    if not arms:
        raise InputError("assembly needs at least one arm")
    column_height = inp.get("columnHeight")
    if typ != "cantilever":
        if column_height is None:
            raise InputError("missing required input 'columnHeight'")
        if column_height <= 0:
            raise InputError("columnHeight must be positive")

    warnings: List[str] = []
    stages: List[Dict[str, Any]] = []

    # Goalpost and trapeze share the load between two columns.
    column_share = 0.5 if typ in ("goalpost", "trapeze") else 1.0
    if column_share == 0.5 and not inp.get("columnSpacing"):
        warnings.append(
            f"{typ} configuration without a column spacing — the header span could not be checked; "
            "only the two columns and their bases were analysed.")

    # --- accumulators for the column -----------------------------------------
    axial = _num(inp, "columnSelfWeight", 0)
    momentX = 0.0       # in plane (column strong axis): gravity levers + transverse pipe loads * EL
    momentY = 0.0       # out of plane (weak axis): longitudinal pipe loads * EL
    torsion = 0.0       # sum longitudinal * offset - reported, not checked
    shearAlong = 0.0    # in-plane horizontal: sum |transverse| (+ any legacy top load)
    shearAcross = 0.0   # out-of-plane horizontal: sum |longitudinal|

    weld_FEXX = inp.get("weldFEXX")
    default_weld = inp.get("weldSize")

    # ======================================================================
    # 1-2. Arms and their welds
    # ======================================================================
    for i, arm in enumerate(arms):
        sec = resolve(arm["shape"])
        elevation = arm["elevation"]
        projection = arm["projection"]
        arm_label = f'Arm {i + 1} @ EL {js_num(elevation)}" — {arm["shape"]}'

        V = 0.0
        M = 0.0
        Talong = 0.0
        Lacross = 0.0
        Macross = 0.0
        for p in arm.get("pipes") or []:
            lever = min(abs(p["offset"]), projection)
            V += p["vertical"]
            M += p["vertical"] * lever
            Talong += abs(_num(p, "transverse", 0))
            Lacross += abs(_num(p, "longitudinal", 0))
            Macross += abs(_num(p, "longitudinal", 0)) * lever

        E = _num(material, "E", 29000)
        Ix = sec.get("Ix")
        deflection = 0.0
        for p in arm.get("pipes") or []:
            a = min(abs(p["offset"]), projection)
            num = p["vertical"] * a * a * (3 * projection - a)
            deflection += div(num, 6 * E * Ix) if Ix is not None else NAN

        arm_res = aisc_member_design({
            "section": sec, "material": material, "method": method,
            "Lx": projection, "Ly": projection, "Lb": projection,
            "Kx": 2.1, "Ky": 2.1,  # cantilever
            "demand": {"P": Talong, "Mx": M, "My": Macross, "Vx": V, "Vy": Lacross, "deflection": deflection},
            "span": projection,
            "deflectionLimit": _num(arm, "deflectionLimit", 240),
        })
        stages.append(_stage_from(arm_label, "arm", arm_res, arm_res["output"]["checks"]))

        # Arm-to-column weld: two parallel fillets down the arm depth.
        wSize = _num(arm, "weldSize", default_weld)
        thickness_pair = [_num(sec, "tw", wSize), _num(sec, "tf", wSize)]
        weld_in = {
            "method": method, "size": wSize, "FEXX": weld_FEXX,
            "pattern": "two-parallel", "depth": sec["d"],
            "Vtransverse": V, "Vparallel": _hypot(Talong, Lacross), "M": M,
            "basePartThickness": min(thickness_pair),
            "baseFy": material.get("Fy"), "baseFu": material.get("Fu"),
        }
        weld_res = fillet_weld({k: v for k, v in weld_in.items() if v is not None})
        wo = weld_res["output"]
        stages.append(_stage_from(f'Arm {i + 1} to column weld — {js_num(wSize)}" fillet', "weld", weld_res, [{
            "label": "Fillet weld stress", "demand": wo["demandPerInch"],
            "capacity": wo["designPerInch"], "ratio": wo["ratio"],
            "clause": "AISC J2-4 with the J2.4(b) directional increase", "status": weld_res["status"],
        }]))
        if Macross > 0:
            warnings.append(
                f"Arm {i + 1}: the weak-axis moment from its longitudinal pipe loads "
                f"({js_num(round_half_up(Macross, 2))} kip-in) is checked in the arm member but not in the "
                "arm-to-column weld group, which resists strong-axis moment and direct shear only.")

        # Accumulate into the column (arm elevation is the lever for horizontal loads).
        axial += V
        momentX += M + Talong * elevation
        momentY += Lacross * elevation
        torsion += Macross
        shearAlong += Talong
        shearAcross += Lacross

    # Legacy: an explicit lateral load at the column top.
    lateralTop = abs(_num(inp, "lateralLoad", 0))
    momentX += lateralTop * (column_height if column_height is not None else NAN)
    shearAlong += lateralTop

    colAxial = axial * column_share
    colMomentX = momentX * column_share
    colMomentY = momentY * column_share
    colTorsion = torsion * column_share
    colShearAlong = shearAlong * column_share
    colShearAcross = shearAcross * column_share
    colShear = _hypot(colShearAlong, colShearAcross)

    def biaxial_equivalent(N: float, B: float) -> float:
        """M_eq = Mx + My*(N/B) about the plate's N axis."""
        return colMomentX + (colMomentY * (N / B) if B > 0 else colMomentY)

    if colTorsion > 0:
        warnings.append(
            "Longitudinal (axial) pipe loads act across the arm and twist the column: "
            f"Σ L·x = {js_num(round_half_up(colTorsion, 2))} kip-in of torsion per column is reported in the "
            "base reactions but not checked — AISC 360 Chapter H3 torsion is outside this cascade.")
    if colMomentY > 0 and typ != "cantilever":
        warnings.append(
            f"Out-of-plane base moment {js_num(round_half_up(colMomentY, 2))} kip-in (longitudinal pipe loads at their "
            "arm elevations) is carried into the base weld, plate, anchors and pier as the elastic superposition "
            "M_eq = Mx + My·(N/B) about the in-plane axis — exact for the corner anchor, conservative for bearing.")

    # ======================================================================
    # 3. Column
    # ======================================================================
    baseplate = inp.get("baseplate")
    pier = inp.get("pier")
    if typ != "cantilever":
        col_label = inp.get("columnShape")
        if not col_label:
            raise InputError("columnShape is required for this assembly type")
        col = resolve(col_label)
        K = _num(inp, "columnK", 2.1)
        col_res = aisc_member_design({
            "section": col, "material": material, "method": method,
            "Lx": column_height, "Ly": column_height, "Lb": column_height,
            "Kx": K, "Ky": K,
            "demand": {"P": colAxial, "Mx": colMomentX, "My": colMomentY,
                       "Vx": colShearAlong, "Vy": colShearAcross},
        })
        stages.append(_stage_from(f"Column — {col_label}", "column", col_res, col_res["output"]["checks"]))

        if _num(inp, "columnK", 2.1) == 2.1:
            warnings.append(
                "Column K = 2.1 assumed (fixed base, free top — AISC Table C-A-7.1 case f). If the support is "
                "braced or framed at the top, supply the lower K that applies.")

        # Column-to-base-plate weld, all round the column footprint.
        col_d = col["d"]
        col_bf = nn(col, "bf", col_d)
        base_t = nn(baseplate or {}, "plateThickness", None)
        if base_t is None:
            base_t = col.get("tf")
        bw_in = {
            "method": method, "size": default_weld, "FEXX": weld_FEXX,
            "pattern": "all-round", "depth": col_d, "width": col_bf,
            "Vtransverse": colShear, "M": biaxial_equivalent(col_d, col_bf), "Pnormal": 0,
            "basePartThickness": base_t,
            "baseFy": material.get("Fy"), "baseFu": material.get("Fu"),
        }
        base_weld = fillet_weld({k: v for k, v in bw_in.items() if v is not None})
        bwo = base_weld["output"]
        stages.append(_stage_from(f'Column to base plate weld — {js_num(default_weld)}" fillet', "weld", base_weld, [{
            "label": "Fillet weld stress", "demand": bwo["demandPerInch"],
            "capacity": bwo["designPerInch"], "ratio": bwo["ratio"],
            "clause": "AISC J2-4 with the J2.4(b) directional increase", "status": base_weld["status"],
        }]))

        # ==================================================================
        # 4-5. Base plate and anchorage
        # ==================================================================
        if baseplate is not None:
            bp_in = dict(baseplate)
            bp_in.update({
                "method": method,
                "columnDepth": col_d, "columnWidth": col_bf,
                "P": colAxial,
                "M": biaxial_equivalent(baseplate["anchorSpacingLength"], baseplate["anchorSpacingWidth"]),
                "V": colShear,
                "uplift": -colAxial if colAxial < 0 else 0,
            })
            bp = base_plate_anchorage(bp_in)
            all_checks = bp["output"]["checks"]
            plate_checks = [c for c in all_checks
                            if c["label"].startswith("Base plate") or c["label"] == "Concrete bearing"]
            anchor_checks = [c for c in all_checks if not any(c is pc for pc in plate_checks)]
            stages.append(_stage_from("Base plate", "baseplate", {"status": bp["status"], "warnings": []}, plate_checks))
            stages.append(_stage_from("Anchorage", "anchorage", {"status": bp["status"], "warnings": bp["warnings"]}, anchor_checks))
        else:
            warnings.append("No base plate defined — the cascade stopped at the column. Add plate, anchor and pier data to check the base.")

        # ==================================================================
        # 6. Pier and soil
        # ==================================================================
        if pier is not None:
            ps_in = dict(pier)
            ps_in.update({
                "method": method,
                "P": colAxial, "M": biaxial_equivalent(pier["pierLength"], pier["pierWidth"]), "V": colShear,
                "uplift": -colAxial if colAxial < 0 else 0,
            })
            plate_len = (baseplate or {}).get("plateLength")
            plate_wid = (baseplate or {}).get("plateWidth")
            if plate_len is not None:
                ps_in["plateLength"] = plate_len
            else:
                ps_in.pop("plateLength", None)
            if plate_wid is not None:
                ps_in["plateWidth"] = plate_wid
            else:
                ps_in.pop("plateWidth", None)
            ps = pier_soil(ps_in)
            stages.append(_stage_from("Pier and soil", "pier", ps, ps["output"]["checks"]))
        elif baseplate is not None:
            warnings.append("No pier or soil data supplied — bearing, overturning, sliding and punching shear were not checked.")

    # --- roll up ------------------------------------------------------------
    real = [s for s in stages if s["status"] != "na"]
    if real:
        governing = real[0]
        for b in real[1:]:
            if b["ratio"] > governing["ratio"]:
                governing = b
    else:
        governing = stages[0]
    summary = {
        "pass": sum(1 for s in stages if s["status"] == "pass"),
        "fail": sum(1 for s in stages if s["status"] == "fail"),
        "na": sum(1 for s in stages if s["status"] == "na"),
    }

    out_stages = []
    for s in stages:
        o = dict(s)
        o["ratio"] = _r4(s["ratio"])
        o["checks"] = [dict(c, demand=_r4(c["demand"]), capacity=_r4(c["capacity"]), ratio=_r4(c["ratio"]))
                       for c in s["checks"]]
        out_stages.append(o)

    all_warnings = list(warnings)
    for s in stages:
        all_warnings.extend(s["warnings"])

    return result(
        MODULE,
        {
            "tag": nn(inp, "tag", "support"),
            "type": typ, "method": method,
            "baseReactions": {
                "axial": _r4(colAxial), "moment": _r4(colMomentX), "momentY": _r4(colMomentY),
                "shear": _r4(colShear),
                "uplift": _r4(-colAxial if colAxial < 0 else 0), "torsion": _r4(colTorsion),
            },
            "lateral": {"transverse": _r4(shearAlong - lateralTop), "longitudinal": _r4(shearAcross)},
            "stages": out_stages,
            "governingRatio": _r4(governing["ratio"]),
            "governingStage": governing["stage"],
            "governingCheck": governing["governing"],
            "summary": summary,
        },
        "fail" if summary["fail"] > 0 else "pass",
        all_warnings,
    )


# The two standard assemblies from the reference detail, as ready-made presets.
CSA_PRESETS: Dict[str, Dict[str, Any]] = {
    "csa-type-1": {
        "type": "t-post",
        "columnShape": "W6X15",
        "columnHeight": 96,           # 8'-0" max
        "weldSize": 0.25, "weldFEXX": 70,
        "arms": [{"shape": "W6X15", "elevation": 96, "projection": 24, "pipes": []}],  # W1 <= 24"
        "baseplate": {
            "plateLength": 12, "plateWidth": 12, "plateThickness": 1.25, "plateFy": 36,
            "fc": 4000, "pierLength": 24, "pierWidth": 24,
            "anchorType": "post-installed-adhesive",
            "anchorCount": 4, "anchorDiameter": 0.75, "anchorEmbedment": 8, "anchorFuta": 58,
            "anchorSpacingLength": 15, "anchorSpacingWidth": 15, "anchorEdgeDistance": 4.5,
            "bondStrength": 800,
        },
        "pier": {
            "pierLength": 24, "pierWidth": 24, "pierHeight": 24, "fc": 4000,
            "allowableBearing": 3, "restraint": "anchored",
        },
    },
    "csa-type-2": {
        "type": "multi-tier",
        "columnShape": "W6X15",
        "columnHeight": 96,
        "weldSize": 0.25, "weldFEXX": 70,
        "arms": [
            {"shape": "L4X3X3/8", "elevation": 96, "projection": 48, "pipes": []},  # W1 <= 48"
            {"shape": "L4X3X3/8", "elevation": 66, "projection": 48, "pipes": []},  # W2, added tier
        ],
        "baseplate": {
            "plateLength": 12, "plateWidth": 12, "plateThickness": 1.25, "plateFy": 36,
            "fc": 4000, "pierLength": 24, "pierWidth": 24,
            "anchorType": "post-installed-adhesive",
            "anchorCount": 4, "anchorDiameter": 0.75, "anchorEmbedment": 8, "anchorFuta": 58,
            "anchorSpacingLength": 15, "anchorSpacingWidth": 15, "anchorEdgeDistance": 4.5,
            "bondStrength": 800,
        },
        "pier": {
            "pierLength": 24, "pierWidth": 24, "pierHeight": 24, "fc": 4000,
            "allowableBearing": 3, "restraint": "anchored",
        },
    },
}


def csa_preset(name: str) -> Dict[str, Any]:
    """Deep copy of a CSA preset, safe to edit."""
    return copy.deepcopy(CSA_PRESETS[name])
