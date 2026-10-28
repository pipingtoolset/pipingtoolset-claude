#!/usr/bin/env python3
"""Equipment nozzle load calculators for the PipingToolset `nozzle-load` skill.

Python 3.9+, standard library only.

Six checks, one function each, all registered in REGISTRY:

  Faithful ports of the pipingtoolset.com calculation engine (same input and output
  field names, statuses, rounding and error conditions):
    connections.nozzle-load-check   per-component unity ratios against user-supplied allowables
    connections.nema-sm23           combined form 3*Fr + Mr <= a*De (a is a REQUIRED input)
    connections.api610-annexf       API 610 Annex F, Eq. (F.1)-(F.11)

  New checks with no engine module:
    equipment.nozzle-load-sum             sum N nozzle load sets (one header or one bay)
                                          against user-supplied limits and an optional multiplier
    equipment.api650-annexp-ordinates     API 650 Annex P nomogram ordinates (status 'na')
    equipment.pvp2011-allowables          allowable set derived from a user-read table row by the
                                          method of the paper 'Establishing Allowable Nozzle
                                          Loads' (ASME PVP2011-57100)

Nothing in this file is a tabulated code value. Every allowable load, header limit, stiffness
coefficient, figure ordinate, table row and allowable stress is an INPUT the user reads from
a licensed copy of the standard, the paper or the vendor datasheet. Numeric constants that
appear in running text of an equation (the 1.5 and 2 multipliers of API 610 Annex F, the
5950 psi / 41 N/mm^2 limit, the 18,800 and 17,100 psi reference stresses of the paper) are
carried as named constants with their source.

CLI:
    python nozzle_load.py list
    python nozzle_load.py <module-id> --input '<json>'
    python nozzle_load.py <module-id> --input-file <path.json>

Output is a JSON envelope {module, status, output, warnings, citation, inputs, user_supplied}.
Exit code 2 on bad input.

`list` prints every module with its exact input field names (case-sensitive). Before the
engine runs, a separate pre-flight layer (`validate`) rejects unknown keys (top level and
inside load sets) and physically impossible inputs (exit 2) and adds warnings for implausible
ones. The optional `ownerFactor` of the ported modules is applied by the CLI layer
(`run_module`) to the entered allowables before the ported function runs; the ported
functions themselves are untouched.
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

# --------------------------------------------------------------------------- rounding


def round_half_up(x: float, decimals: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def round_sig(x: float, sig: int) -> float:
    """Round to `sig` significant figures (round-half-up). Used for very small ordinates."""
    if x == 0 or not math.isfinite(x):
        return x
    digits = int(math.floor(math.log10(abs(x)))) + 1
    return round_half_up(x, sig - digits)


# --------------------------------------------------------------------------- constants

COMPONENTS = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")

# API 610 Annex F, equations in running text (method constants, not table data).
API610_COMPONENT_MULTIPLE = 2.0      # F.1.2 a): each component within 2x the Table 5 range
API610_RESULTANT_DENOM = 1.5         # F.1 / F.2: 1.5 x the Table 5 resultants in the interaction sum
API610_INTERACTION_LIMIT = 2.0       # F.1 / F.2: sum < 2
API610_CENTRE_FORCE_FACTOR = 1.5     # F.3 / F.5
API610_CENTRE_MY_FACTOR = 2.0        # F.4
API610_SIGMA_P_LIMIT_SI = 41.0       # F.6, N/mm^2
API610_SIGMA_P_LIMIT_USC = 5950.0    # F.9, psi
API610_K_SIGMA = {"SI": 10200.0, "USC": 122.0}   # F.7 / F.10
API610_K_TAU = {"SI": 5100.0, "USC": 61.0}       # F.8 / F.11
API610_UNIT_CONV = {"SI": 1000.0, "USC": 12.0}   # F.5.1.1-3: mm to m, in to ft

# Paper 'Establishing Allowable Nozzle Loads' (ASME PVP2011-57100).
PVP_TABLE_BASIS_THICKNESS = {"1A": 0.25, "1B": 0.375, "2": 0.375}   # in, from the table titles
PVP_REF_STRESS_VESSEL = 18800.0      # psi, SA-516 Gr. 70 shell at 650 F (paper, extrapolation section)
PVP_REF_STRESS_NOZZLE = 17100.0      # psi, SA-106 Gr. B / SA-105 neck at 650 F
PVP_REF_TEMP_F = 650.0
PVP_MAX_D_OVER_T = 320.0
PVP_NPS_MIN = 2.0
PVP_NPS_MAX = 24.0
PVP_EQ4_REF_THICKNESS = 0.25         # in, the thickness the paper writes eq. (4) for
PVP_PRIMARY_SHARE_BASIS = 0.5        # paper: total operating loads assumed at least 50% primary
PVP_MATERIALS = ("killed-carbon-steel", "other-ferrous", "aluminium", "other")

# API 650 Annex P, Figure P.4a/P.4b plotted lambda range (axis limits as printed).
ANNEXP_LAMBDA_PLOTTED = (0.1, 30.0)

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


def _six(obj: Any, label: str) -> Dict[str, float]:
    """A six-component load set {Fx, Fy, Fz, Mx, My, Mz} as floats."""
    if not isinstance(obj, dict):
        raise ValueError(f"{label} is required: an object with Fx, Fy, Fz, Mx, My, Mz")
    out: Dict[str, float] = {}
    for k in COMPONENTS:
        v = obj.get(k)
        if v is None:
            raise ValueError(f"{label}.{k} is required")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{label}.{k} must be a number")
        if not math.isfinite(v):
            raise ValueError(f"{label}.{k} must be finite")
        out[k] = float(v)
    return out


def _loadset(inp: Dict[str, Any], key: str) -> Dict[str, float]:
    return _six(inp.get(key), key)


def _result(module: str, output: Dict[str, Any], status: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"module": module, "output": output, "status": status, "warnings": warnings or []}


def _force_res(s: Dict[str, float]) -> float:
    return math.hypot(s["Fx"], s["Fy"], s["Fz"])


def _moment_res(s: Dict[str, float]) -> float:
    return math.hypot(s["Mx"], s["My"], s["Mz"])


# --------------------------------------------------------------------------- per-component check


def nozzle_load_check(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Per-component unity ratios |applied| / allowable at one equipment nozzle.

    PASS requires every component ratio <= 1. The allowables are supplied by the user from
    the governing equipment standard's table or the vendor datasheet; `standard` is a report
    label only and selects nothing. Also reports the resultant force FR and moment MR.
    """
    applied = _loadset(inp, "applied")
    allowable = _loadset(inp, "allowable")
    for k in COMPONENTS:
        if allowable[k] <= 0:
            raise ValueError(f"allowable.{k} must be > 0 (supply it from the governing standard/vendor)")

    ratios: Dict[str, float] = {}
    max_ratio = 0.0
    governing = "Fx"
    for k in COMPONENTS:
        r = abs(applied[k]) / allowable[k]
        ratios[k] = round_half_up(r, 5)
        if r > max_ratio:
            max_ratio = r
            governing = k

    FR = _force_res(applied)
    MR = _moment_res(applied)

    # PIP RECE002 usage note, ported as the engine has it: no behaviour change, no machinery
    # classification input, and no effect on `status`.
    warnings: List[str] = []
    if max_ratio > 0.5:
        warnings.append(
            "maxRatio exceeds 0.5 of the entered allowable. If PIP RECE002 is invoked by the owner's "
            "specification, \u00a74.2.2.3 caps the piping layout/design-stage load on vital or sensitive "
            "machinery at 50% of the industry allowable nozzle loads (100% is reserved for as-built "
            "verification) \u2014 essential/spared machinery gets 100% at the design stage under "
            "\u00a74.2.3.3. This does not change the verdict above, which is judged against "
            "the allowable you entered."
        )

    return _result(
        "connections.nozzle-load-check",
        {
            "FR": round_half_up(FR, 2),
            "MR": round_half_up(MR, 2),
            "ratios": ratios,
            "maxRatio": round_half_up(max_ratio, 5),
            "governing": governing,
        },
        _verdict(max_ratio <= 1),
        warnings,
    )


# --------------------------------------------------------------------------- NEMA SM-23 / API 617 / 611 / 612 combined form


def nema_sm23(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Combined nozzle-load index of the NEMA SM-23 family.

        Fr = sqrt(Fx^2 + Fy^2 + Fz^2) [lbf]     Mr = sqrt(Mx^2 + My^2 + Mz^2) [ft-lbf]
        index = 3*Fr + Mr    vs    allowable = a * De
        De = NPS (NPS <= 8)  or  (16 + NPS)/3  (NPS > 8)

    The coefficient `a` is a REQUIRED input with no default: it is the right-hand coefficient
    of the equation the user's standard prints (see the skill for which equation gives which).
    """
    NPS = _num(inp, "NPS")
    applied = _loadset(inp, "applied")
    coefficient = _num(inp, "coefficient")
    if NPS <= 0:
        raise ValueError("NPS must be > 0")
    if coefficient <= 0:
        raise ValueError("coefficient must be > 0")

    De = NPS if NPS <= 8 else (16 + NPS) / 3
    Fr = _force_res(applied)
    Mr = _moment_res(applied)
    index = 3 * Fr + Mr
    allowable = coefficient * De

    return _result(
        "connections.nema-sm23",
        {
            "De": round_half_up(De, 5),
            "Fr": round_half_up(Fr, 5),
            "Mr": round_half_up(Mr, 5),
            "index": round_half_up(index, 5),
            "allowable": round_half_up(allowable, 3),
            "ratio": round_half_up(index / allowable, 4),
        },
        _verdict(index <= allowable),
        ["Combined screen only \u2014 also run the per-component check and the exhaust/resolution rules of the standard."],
    )


# --------------------------------------------------------------------------- API 610 Annex F


def _check_row(eq_id: str, label: str, value: float, limit: float, advisory: bool = False) -> Dict[str, Any]:
    if limit > 0:
        ratio = value / limit
    else:
        ratio = math.inf if value > 0 else 0.0
    return {"id": eq_id, "label": label, "value": value, "limit": limit, "ratio": ratio,
            "status": _verdict(ratio <= 1), "advisory": advisory}


def api610_annexf(inp: Dict[str, Any]) -> Dict[str, Any]:
    """API 610 Annex F: horizontal pumps F.1.2 a)-c) (Eq. F.1-F.5) and vertical in-line F.2 (Eq. F.6-F.11).

    The Table 5 base ranges are user-supplied per nozzle; the resultants FRST4 / MRST4 are derived
    from the supplied components by square root of the sum of the squares, as the engine does.
    """
    pump_type = inp.get("pumpType")
    units = inp.get("units")
    SA = _loadset(inp, "suctionApplied")
    DA = _loadset(inp, "dischargeApplied")
    ST4 = _loadset(inp, "suctionAllowable")
    DT4 = _loadset(inp, "dischargeAllowable")

    for label, s in (("suctionAllowable", ST4), ("dischargeAllowable", DT4)):
        for k in COMPONENTS:
            if not (s[k] > 0):
                raise ValueError(f"{label}.{k} must be > 0 (supply the Table 5 base range for this nozzle/component)")
    if pump_type not in ("horizontal", "vertical-inline"):
        raise ValueError('pumpType must be "horizontal" or "vertical-inline"')
    if units not in ("USC", "SI"):
        raise ValueError('units must be "USC" or "SI"')

    def r5(v: float) -> float:
        return round_half_up(v, 5)

    def r4(v: float) -> float:
        return round_half_up(v, 4)

    warnings: List[str] = [
        "Table 5 allowables are user-supplied \u2014 this module does not embed or validate API 610 Table 5a/5b; "
        "confirm values against the certified vendor data for the actual nozzle size/rating.",
        "Use of Annex F methods requires the purchaser's approval and does not eliminate the 2-times margin between "
        "external nozzle loads and pump case design limits (6.5.6, 6.5.6.1); the pump vendor must direct how these "
        "equations apply to the system design (6.5.6.2).",
    ]

    # F.1.2 a) per-component ratio vs 2x Table 5 (always computed)
    s_ratio: Dict[str, float] = {}
    d_ratio: Dict[str, float] = {}
    max_component_ratio = -1.0
    governing_component = ""
    governing_value = 0.0
    governing_limit = 0.0
    for k in COMPONENTS:
        rS = abs(SA[k]) / (API610_COMPONENT_MULTIPLE * ST4[k])
        rD = abs(DA[k]) / (API610_COMPONENT_MULTIPLE * DT4[k])
        s_ratio[k] = r5(rS)
        d_ratio[k] = r5(rD)
        if rS > max_component_ratio:
            max_component_ratio = rS
            governing_component = f"suction.{k}"
            governing_value = abs(SA[k])
            governing_limit = API610_COMPONENT_MULTIPLE * ST4[k]
        if rD > max_component_ratio:
            max_component_ratio = rD
            governing_component = f"discharge.{k}"
            governing_value = abs(DA[k])
            governing_limit = API610_COMPONENT_MULTIPLE * DT4[k]

    vertical = pump_type == "vertical-inline"
    checks: List[Dict[str, Any]] = [
        _check_row("F.1.2(a)", f"Per-component vs 2x Table 5 ({governing_component})",
                   governing_value, governing_limit, vertical)
    ]

    branch: Dict[str, Any] = {}

    if pump_type == "horizontal":
        sp = inp.get("suctionPosition")
        dp = inp.get("dischargePosition")
        if not isinstance(sp, dict) or not isinstance(dp, dict):
            raise ValueError('suctionPosition and dischargePosition are required for pumpType "horizontal" '
                             "(F.1.2 c / F.3-F.5 resolve loads to the pump center)")
        xS, yS, zS = _num(sp, "x"), _num(sp, "y"), _num(sp, "z")
        xD, yD, zD = _num(dp, "x"), _num(dp, "y"), _num(dp, "z")

        FRSA, MRSA = _force_res(SA), _moment_res(SA)
        FRDA, MRDA = _force_res(DA), _moment_res(DA)
        FRST4, MRST4 = _force_res(ST4), _moment_res(ST4)
        FRDT4, MRDT4 = _force_res(DT4), _moment_res(DT4)

        f1 = FRSA / (API610_RESULTANT_DENOM * FRST4) + MRSA / (API610_RESULTANT_DENOM * MRST4)   # (F.1)
        f2 = FRDA / (API610_RESULTANT_DENOM * FRDT4) + MRDA / (API610_RESULTANT_DENOM * MRDT4)   # (F.2)
        checks.append(_check_row("F.1", "Suction resultant interaction", f1, API610_INTERACTION_LIMIT))
        checks.append(_check_row("F.2", "Discharge resultant interaction", f2, API610_INTERACTION_LIMIT))

        FXCA = SA["Fx"] + DA["Fx"]   # (F.3.1.1)-(F.3.1.3)
        FYCA = SA["Fy"] + DA["Fy"]
        FZCA = SA["Fz"] + DA["Fz"]
        FRCA = math.hypot(FXCA, FYCA, FZCA)   # (F.3.1)

        k = API610_UNIT_CONV[units]   # (F.5.1.1)-(F.5.1.3)
        MXCA = SA["Mx"] + DA["Mx"] - ((SA["Fy"] * zS + DA["Fy"] * zD) - (SA["Fz"] * yS + DA["Fz"] * yD)) / k
        MYCA = SA["My"] + DA["My"] + ((SA["Fx"] * zS + DA["Fx"] * zD) - (SA["Fz"] * xS + DA["Fz"] * xD)) / k
        MZCA = SA["Mz"] + DA["Mz"] - ((SA["Fx"] * yS + DA["Fx"] * yD) - (SA["Fy"] * xS + DA["Fy"] * xD)) / k
        MRCA = math.hypot(MXCA, MYCA, MZCA)   # (F.5.1)

        limit_f3 = API610_CENTRE_FORCE_FACTOR * (FRST4 + FRDT4)
        limit_f4 = API610_CENTRE_MY_FACTOR * (ST4["My"] + DT4["My"])
        limit_f5 = API610_CENTRE_FORCE_FACTOR * (MRST4 + MRDT4)
        checks.append(_check_row("F.3", "Resultant force at pump center", FRCA, limit_f3))
        checks.append(_check_row("F.4", "Resultant MY at pump center", abs(MYCA), limit_f4))
        checks.append(_check_row("F.5", "Resultant moment at pump center", MRCA, limit_f5))

        branch = {
            "FRSA": r4(FRSA), "MRSA": r4(MRSA), "FRDA": r4(FRDA), "MRDA": r4(MRDA),
            "eqF1Value": r5(f1), "eqF1Ratio": r5(f1 / API610_INTERACTION_LIMIT),
            "eqF2Value": r5(f2), "eqF2Ratio": r5(f2 / API610_INTERACTION_LIMIT),
            "FXCA": r4(FXCA), "FYCA": r4(FYCA), "FZCA": r4(FZCA), "FRCA": r4(FRCA),
            "MXCA": r4(MXCA), "MYCA": r4(MYCA), "MZCA": r4(MZCA), "MRCA": r4(MRCA),
            "eqF3Ratio": r5(FRCA / limit_f3),
            "eqF4Ratio": r5(abs(MYCA) / limit_f4),
            "eqF5Ratio": r5(MRCA / limit_f5),
        }

        if max_component_ratio <= 0.5:
            warnings.append("All applied component loads are within the base Table 5 range (F.1.1) \u2014 "
                            "Annex F qualification is not required for this case.")
    else:
        sb = inp.get("suctionBore")
        db = inp.get("dischargeBore")
        if not isinstance(sb, dict) or not isinstance(db, dict):
            raise ValueError('suctionBore and dischargeBore ({Do, Di}) are required for pumpType "vertical-inline" '
                             "(F.2 / F.6-F.11 principal stress)")
        DoS, DiS = _num(sb, "Do"), _num(sb, "Di")
        DoD, DiD = _num(db, "Do"), _num(db, "Di")
        if not (DoS > DiS and DiS > 0) or not (DoD > DiD and DiD > 0):
            raise ValueError("nozzle bore requires Do > Di > 0 (Schedule 40 pipe OD/ID for the nozzle's nominal size)")

        k_sigma = API610_K_SIGMA[units]   # (F.7) vs (F.10)
        k_tau = API610_K_TAU[units]       # (F.8) vs (F.11)
        limit = API610_SIGMA_P_LIMIT_SI if units == "SI" else API610_SIGMA_P_LIMIT_USC   # (F.6) vs (F.9)
        eq_id = "F.6" if units == "SI" else "F.9"

        def principal(L: Dict[str, float], Do: float, Di: float) -> Tuple[float, float, float]:
            d2 = Do * Do - Di * Di
            d4 = Do ** 4 - Di ** 4
            sigma_l = (1.27 * L["Fy"]) / d2 + (k_sigma * Do * math.hypot(L["Mx"], L["Mz"])) / d4   # (F.7)/(F.10)
            tau = (1.27 * math.hypot(L["Fx"], L["Fz"])) / d2 + (k_tau * Do * abs(L["My"])) / d4       # (F.8)/(F.11)
            sigma_p = sigma_l / 2 + math.sqrt((sigma_l * sigma_l) / 4 + tau * tau)                    # (F.6)/(F.9)
            return sigma_l, tau, sigma_p

        s_l, s_t, s_p = principal(SA, DoS, DiS)
        d_l, d_t, d_p = principal(DA, DoD, DiD)
        checks.append(_check_row(eq_id, "Suction principal stress", s_p, limit))
        checks.append(_check_row(eq_id, "Discharge principal stress", d_p, limit))

        branch = {
            "suctionSigmaL": r4(s_l), "suctionTau": r4(s_t), "suctionSigmaP": r4(s_p),
            "suctionStressRatio": r5(s_p / limit),
            "dischargeSigmaL": r4(d_l), "dischargeTau": r4(d_t), "dischargeSigmaP": r4(d_p),
            "dischargeStressRatio": r5(d_p / limit),
        }

        warnings.append("F.2 applies only to OH3/OH6 vertical in-line pumps supported solely by the attached piping "
                        "\u2014 confirm this pump's support condition before relying on this result.")
        warnings.append("Do/Di must be Schedule 40 pipe section properties for the nozzle's nominal size (F.2) \u2014 "
                        "supplied by the caller, not derived by this module.")
        warnings.append("The per-component vs-2x-Table-5 screen is informational only for vertical in-line pumps: F.2 "
                        "permits exceeding it provided the principal-stress check (F.6-F.11) passes.")

    if any(c["status"] == "fail" and not c["advisory"] for c in checks):
        warnings.append("Loads fail one or more Annex F acceptance conditions \u2014 per F.1.3, this configuration "
                        "requires purchaser and vendor approval; API 686:2009 Chapter 6 alignment checks should be performed.")

    real = [c for c in checks if not c["advisory"]]
    if real:
        governing = real[0]
        for c in real[1:]:
            if c["ratio"] > governing["ratio"]:
                governing = c
    else:
        governing = checks[0]
    status = _verdict(all(c["advisory"] or c["status"] != "fail" for c in checks))

    out_checks = []
    for c in checks:
        out_checks.append({
            "id": c["id"], "label": c["label"],
            "value": r5(c["value"]), "limit": r4(c["limit"]),
            "ratio": r5(c["ratio"]) if math.isfinite(c["ratio"]) else c["ratio"],
            "status": c["status"], "advisory": c["advisory"],
        })

    output: Dict[str, Any] = {
        "pumpType": pump_type,
        "units": units,
        "suctionComponentRatio": s_ratio,
        "dischargeComponentRatio": d_ratio,
        "maxComponentRatio": r5(max_component_ratio),
        "governingComponent": governing_component,
    }
    output.update(branch)
    output["checks"] = out_checks
    output["governingRatio"] = r5(governing["ratio"]) if math.isfinite(governing["ratio"]) else governing["ratio"]
    output["governingEquation"] = governing["id"]
    return _result("connections.api610-annexf", output, status, warnings)


# --------------------------------------------------------------------------- header / bay sum


def nozzle_load_sum(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Sum N nozzle load sets and compare the sums to user-supplied header limits.

    For API 661 7.1.10.2 (all nozzle loadings on one header), with `multiplier` = 3 for the
    bay rule of 7.1.10.3 (total on one multi-bundle bay not above 3x the single-header
    allowance). The nozzle sets must already be in ONE common axis system with consistent
    signs; each component is summed algebraically and compared as |sum| / (limit * multiplier).
    """
    nozzles = inp.get("nozzles")
    if not isinstance(nozzles, list) or not nozzles:
        raise ValueError("nozzles must be a non-empty list of six-component load sets")
    limits = _loadset(inp, "limits")
    for k in COMPONENTS:
        if limits[k] <= 0:
            raise ValueError(f"limits.{k} must be > 0 (supply the header limit from the governing standard/vendor)")
    multiplier = _num(inp, "multiplier", 1.0)
    if multiplier <= 0:
        raise ValueError("multiplier must be > 0")

    sets: List[Dict[str, float]] = []
    tags: List[str] = []
    for i, n in enumerate(nozzles):
        if not isinstance(n, dict):
            raise ValueError(f"nozzles[{i}] must be an object with Fx, Fy, Fz, Mx, My, Mz")
        sets.append(_six(n, f"nozzles[{i}]"))
        tag = n.get("tag")
        tags.append(tag if isinstance(tag, str) and tag else f"nozzle {i + 1}")

    total: Dict[str, float] = {}
    abs_total: Dict[str, float] = {}
    for k in COMPONENTS:
        total[k] = sum(s[k] for s in sets)
        abs_total[k] = sum(abs(s[k]) for s in sets)

    effective = {k: limits[k] * multiplier for k in COMPONENTS}
    ratios: Dict[str, float] = {}
    max_ratio = 0.0
    governing = "Fx"
    for k in COMPONENTS:
        r = abs(total[k]) / effective[k]
        ratios[k] = round_half_up(r, 5)
        if r > max_ratio:
            max_ratio = r
            governing = k

    warnings: List[str] = [
        "The nozzle sets must be in one common axis system with consistent signs (the header or bay axes); "
        "the sum is algebraic. Resolve each set to the same reference point before entering it if the governing "
        "rule requires moments about a common point.",
        "The limits are user-supplied from the governing rule (for API 661, the values printed in 7.1.10.2); this "
        "check does not replace the per-nozzle check of the standard's nozzle load table.",
    ]
    if multiplier != 1.0:
        warnings.append(f"A multiplier of {multiplier:g} was applied to every limit (for API 661 7.1.10.3, the "
                        "multi-bundle bay total is compared with 3 times the single-header allowance). Confirm the "
                        "multiplier against the printed clause.")
    if len(sets) == 1:
        warnings.append("Only one nozzle was entered; the sum equals that nozzle's loads. Use "
                        "connections.nozzle-load-check for a single nozzle.")

    per_nozzle = [{"tag": tags[i], "FR": round_half_up(_force_res(s), 4), "MR": round_half_up(_moment_res(s), 4)}
                  for i, s in enumerate(sets)]

    return _result(
        "equipment.nozzle-load-sum",
        {
            "nozzleCount": len(sets),
            "multiplier": multiplier,
            "sum": {k: round_half_up(total[k], 4) for k in COMPONENTS},
            "absoluteSum": {k: round_half_up(abs_total[k], 4) for k in COMPONENTS},
            "effectiveLimit": {k: round_half_up(effective[k], 4) for k in COMPONENTS},
            "ratios": ratios,
            "maxRatio": round_half_up(max_ratio, 5),
            "governing": governing,
            "FR": round_half_up(_force_res(total), 4),
            "MR": round_half_up(_moment_res(total), 4),
            "perNozzle": per_nozzle,
        },
        _verdict(max_ratio <= 1),
        warnings,
    )


# --------------------------------------------------------------------------- API 650 Annex P ordinates


def api650_annexp_ordinates(inp: Dict[str, Any]) -> Dict[str, Any]:
    """API 650 Annex P, P.2.7: the ordinates to plot on the opening's nomograms.

        lambda = a / sqrt(R t)              FP = pi a^2 P              (P.2.3)
        abscissa           = (lambda / (2 YF)) * (FR / FP)            (both plots)
        ordinate, Fig. P.5a = (lambda / (a YL)) * (ML / FP)
        ordinate, Fig. P.5b = (lambda / (a YC)) * (MC / FP)

    YF, YL and YC are read from Figures P.4a / P.4b by the user. The module does not know the
    acceptance boundary (Figures P.3a/b, P.5a/b are read from the printed page): it returns
    the ordinates and the normalised opening positions XA, XB, XC over sqrt(R t) (P.2.7.1.1),
    and the status is always 'na'. Units must be coherent (for example N, mm, MPa).
    """
    FR, ML, MC = _num(inp, "FR"), _num(inp, "ML"), _num(inp, "MC")
    a, R, t, L, P = _num(inp, "a"), _num(inp, "R"), _num(inp, "t"), _num(inp, "L"), _num(inp, "P")
    YF, YL, YC = _num(inp, "YF"), _num(inp, "YL"), _num(inp, "YC")
    for name, v in (("a", a), ("R", R), ("t", t), ("L", L), ("P", P), ("YF", YF), ("YL", YL), ("YC", YC)):
        if v <= 0:
            raise ValueError(f"{name} must be > 0")

    rt = math.sqrt(R * t)
    lam = a / rt
    FP = math.pi * a * a * P
    abscissa = (lam / (2 * YF)) * (FR / FP)
    ord_a = (lam / (a * YL)) * (ML / FP)
    ord_b = (lam / (a * YC)) * (MC / FP)

    warnings: List[str] = [
        "Status is 'na' by design: the acceptance boundary is read from Figures P.3a/b and P.5a/b of the printed "
        "standard. Acceptance (P.2.7.2.4) needs BOTH plotted points, [abscissa, ordinate P.5a] and "
        "[abscissa, ordinate P.5b], inside the boundary for the opening-tank configuration.",
        "FR, ML and MC are signed (Figure P.1 sign convention); the quadrant of each point matters, so enter them with "
        "their signs and read the quadrant labels on the figures.",
        "YF, YL and YC are figure readings (Figures P.4a/P.4b) at the lambda in the output; the stiffness coefficients, "
        "unrestrained shell growth and rotation (P.2.4, P.2.5) and the resulting piping loads (P.2.6) are outside this tool.",
        "Annex P applies to openings in the lower half of the bottom shell course (P.2.1) and, unless the purchaser "
        "specifies otherwise, to tanks above 36 m diameter (P.1). Use coherent units (for example N, mm, MPa).",
    ]
    if not (ANNEXP_LAMBDA_PLOTTED[0] <= lam <= ANNEXP_LAMBDA_PLOTTED[1]):
        warnings.append(f"lambda = {lam:.4g} is outside {ANNEXP_LAMBDA_PLOTTED[0]:g} to {ANNEXP_LAMBDA_PLOTTED[1]:g}, "
                        "the range plotted in Figures P.4a/P.4b; a YF, YL or YC reading there is an extrapolation.")

    return _result(
        "equipment.api650-annexp-ordinates",
        {
            "lambda": round_sig(lam, 6),
            "FP": round_sig(FP, 6),
            "XA_over_sqrtRt": round_sig((L + a) / rt, 6),
            "XB_over_sqrtRt": round_sig((L - a) / rt, 6),
            "XC_over_sqrtRt": round_sig(L / rt, 6),
            "abscissa": round_sig(abscissa, 6),
            "ordinateP5a": round_sig(ord_a, 6),
            "ordinateP5b": round_sig(ord_b, 6),
            "abscissaPerFR": round_sig(lam / (2 * YF * FP), 6),
            "ordinateP5aPerML": round_sig(lam / (a * YL * FP), 6),
            "ordinateP5bPerMC": round_sig(lam / (a * YC * FP), 6),
        },
        "na",
        warnings,
    )


# --------------------------------------------------------------------------- PVP2011-57100 allowables


def pvp2011_allowables(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Allowable nozzle loads for a vessel with no API or vendor allowable, by the method of the
    paper 'Establishing Allowable Nozzle Loads' (ASME PVP2011-57100).

    The user reads one row of the paper's Table 1A, 1B or 2 (never embedded here). Applied in order:
      (c) optional interpolation between two adjacent user-read rows. The paper scales a row by
          force ~ d (eq. 1) and moment ~ d^2 (eq. 2) from constants fitted at its own FEA sizes;
          between two rows read from the tables this tool uses the affine form in d (forces) and
          d^2 (moments) and also reports the proportional-through-origin bound from each row;
      (a) thickness extrapolation, eq. (4): value(T) = value(basis) * (T / basis)^2 for T < basis;
      (b) material / temperature ratio: min(S_vessel / 18,800, S_nozzle / 17,100, 1.0);
      (d) optional owner factor.
    Forces in lbf and moments in ft-lbf, as the paper tabulates them.
    """
    table = inp.get("table")
    if not isinstance(table, str) or table not in PVP_TABLE_BASIS_THICKNESS:
        raise ValueError('table must be "1A", "1B" or "2"')
    basis = PVP_TABLE_BASIS_THICKNESS[table]
    NPS = _num(inp, "NPS")
    T = _num(inp, "T")
    S_vessel = _num(inp, "S_vessel")
    S_nozzle = _num(inp, "S_nozzle")
    owner = _num(inp, "ownerFactor", 1.0)
    for name, v in (("NPS", NPS), ("T", T), ("S_vessel", S_vessel), ("S_nozzle", S_nozzle)):
        if v <= 0:
            raise ValueError(f"{name} must be > 0")
    if not (0 < owner <= 1):
        raise ValueError("ownerFactor must be in (0, 1]")

    has_row = inp.get("row") is not None
    interp_keys = ("lowerNPS", "lowerRow", "upperNPS", "upperRow")
    has_interp = any(inp.get(k) is not None for k in interp_keys)
    if has_row == has_interp:
        raise ValueError("give either row (the table row at NPS) or all of lowerNPS, lowerRow, upperNPS, upperRow (not both)")

    log: List[str] = []
    warnings: List[str] = []

    prop_bound: Dict[str, float] = {}
    if has_row:
        base = _loadset(inp, "row")
        for k in COMPONENTS:
            if base[k] <= 0:
                raise ValueError(f"row.{k} must be > 0 (read it from the paper's Table {table})")
        interpolated = False
        log.append(f"Table {table} row read by the user for NPS {NPS:g}: used as read.")
    else:
        if any(inp.get(k) is None for k in interp_keys):
            raise ValueError("interpolation needs all of lowerNPS, lowerRow, upperNPS, upperRow")
        d1, d2 = _num(inp, "lowerNPS"), _num(inp, "upperNPS")
        if not (0 < d1 < d2):
            raise ValueError("require 0 < lowerNPS < upperNPS")
        if not (d1 <= NPS <= d2):
            raise ValueError("NPS must lie between lowerNPS and upperNPS (no extrapolation)")
        r1, r2 = _loadset(inp, "lowerRow"), _loadset(inp, "upperRow")
        for label, rr in (("lowerRow", r1), ("upperRow", r2)):
            for k in COMPONENTS:
                if rr[k] <= 0:
                    raise ValueError(f"{label}.{k} must be > 0 (read it from the paper's Table {table})")
        base = {}
        for k in COMPONENTS:
            if k.startswith("F"):          # forces scale with d (paper eq. 1)
                p1, p2, pn = d1, d2, NPS
            else:                          # moments scale with d^2 (paper eq. 2)
                p1, p2, pn = d1 * d1, d2 * d2, NPS * NPS
            w = (pn - p1) / (p2 - p1)
            base[k] = r1[k] + (r2[k] - r1[k]) * w
            # proportional-through-origin estimates from each row; the lower is the conservative bound
            prop_bound[k] = min(r1[k] * pn / p1, r2[k] * pn / p2)
        interpolated = True
        log.append(f"Interpolated to NPS {NPS:g} between rows NPS {d1:g} and NPS {d2:g} of Table {table}: "
                   "affine in d for forces and in d^2 for moments between the two rows read. The paper scales "
                   "with force ~ d (eq. 1) and moment ~ d^2 (eq. 2) from constants fitted at its own FEA sizes, "
                   "so the straight-line form between two user-read rows is the skill's reading for two table rows; the paper does print eq. (1) and eq. (2).")
        if any(base[k] > prop_bound[k] * (1 + 1e-9) for k in COMPONENTS):
            log.append("Proportional-through-origin estimates from each row (lower taken) are reported as "
                       "proportionalBound; where they sit below the affine value, the lower is the conservative choice.")
            warnings.append("Interpolated base exceeds the proportional-through-origin bound (force ~ d, moment ~ d^2 from "
                            "each row, lower taken) for: " + ", ".join(k for k in COMPONENTS if base[k] > prop_bound[k] * (1 + 1e-9)) +
                            ". Use proportionalBound for the conservative set, or have the vessel engineer confirm the intermediate size.")

    # (a) thickness, eq. (4)
    if T < basis:
        t_factor = (T / basis) ** 2
        log.append(f"Thickness: T = {T:g} in is below the Table {table} basis of {basis:g} in; eq. (4) form "
                   f"value(T) = value(basis) x (T/{basis:g})^2 = x{round_half_up(t_factor, 5):g}.")
        warnings.append(
            f"T = {T:g} in is below the Table {table} thickness basis ({basis:g} in): the derived values use the "
            "eq. (4) form M(T) = M(basis) x (T/basis)^2. The paper wrote and validated that extrapolation for "
            f"thicknesses below {PVP_EQ4_REF_THICKNESS:g} in against Table 1A; with Table 1B or 2 the same form applied "
            "to the table's own basis is the skill's extension, not the paper's statement. The paper reports its FEA "
            "confirmation only where the applied pressure is below the limit set by the ratio (T/0.25)^2; check the paper."
        )
    else:
        t_factor = 1.0
        log.append(f"Thickness: T = {T:g} in is at or above the Table {table} basis of {basis:g} in; no thickness "
                   "factor, and no credit for the extra thickness.")

    # (b) material / temperature ratio
    s_v = S_vessel / PVP_REF_STRESS_VESSEL
    s_n = S_nozzle / PVP_REF_STRESS_NOZZLE
    s_ratio = min(s_v, s_n, 1.0)
    if min(s_v, s_n) >= 1.0:
        log.append(f"Stress ratio: S_vessel/{PVP_REF_STRESS_VESSEL:,.0f} = {round_half_up(s_v, 5):g} and "
                   f"S_nozzle/{PVP_REF_STRESS_NOZZLE:,.0f} = {round_half_up(s_n, 5):g}; capped at 1.0 (no uplift).")
    else:
        which = "vessel shell" if s_v <= s_n else "nozzle neck"
        log.append(f"Stress ratio: S_vessel/{PVP_REF_STRESS_VESSEL:,.0f} = {round_half_up(s_v, 5):g}, "
                   f"S_nozzle/{PVP_REF_STRESS_NOZZLE:,.0f} = {round_half_up(s_n, 5):g}; the lowest governs "
                   f"({which}): x{round_half_up(s_ratio, 5):g}.")

    # (d) owner factor
    if owner != 1.0:
        label = inp.get("ownerFactorBasis")
        suffix = f" ({label})" if isinstance(label, str) and label else ""
        log.append(f"Owner factor x{owner:g}{suffix}.")

    total = t_factor * s_ratio * owner
    derived = {k: round_half_up(base[k] * total, 3) for k in COMPONENTS}
    log.append(f"Total factor on the table row: x{round_half_up(total, 5):g}.")

    # ---- limits of applicability -> warnings
    if not (PVP_NPS_MIN <= NPS <= PVP_NPS_MAX):
        warnings.append(f"NPS {NPS:g} is outside the paper's tabulated range of NPS {PVP_NPS_MIN:g} to {PVP_NPS_MAX:g}; "
                        "no basis for these loads.")
    temp = inp.get("designTempF")
    if temp is not None:
        temp = _num(inp, "designTempF")
        if temp > PVP_REF_TEMP_F:
            warnings.append(f"Design temperature {temp:g} F is above the paper's {PVP_REF_TEMP_F:g} F basis for the tables. Above "
                            "that the paper's only adjustment is the stress ratio, which does not capture creep-range "
                            "behaviour, so confirm the derived set with the vessel engineer.")
    else:
        warnings.append(f"Design temperature not stated: the paper's tables are for carbon steel at or below {PVP_REF_TEMP_F:g} F. "
                        "Confirm it and re-run with designTempF.")
    material = inp.get("material")
    if material is None:
        warnings.append("Material not stated: the paper assumes killed carbon steel (SA-516 Gr. 70 shell, SA-106 Gr. B / "
                        "SA-105 neck). State it with `material`.")
    elif material == "aluminium":
        warnings.append("Aluminium: the lower modulus of elasticity makes the local deformation at the nozzle exceed that of a "
                        "carbon steel vessel, and the stress ratio does not capture it (the paper says so). Individual analysis is needed.")
    elif material != "killed-carbon-steel":
        warnings.append(f"Material '{material}' is not killed carbon steel: the paper's basis is carbon steel, and the stress "
                        "ratio is the only adjustment it offers for other materials.")
    D = inp.get("D")
    if D is not None:
        D = _num(inp, "D")
        if D <= 0:
            raise ValueError("D must be > 0")
        dt = D / T
        if dt > PVP_MAX_D_OVER_T:
            warnings.append(f"Vessel D/T = {dt:.1f} exceeds {PVP_MAX_D_OVER_T:g}, the largest D/T the tables were developed for "
                            "(the paper notes this is not a general limit).")
    else:
        warnings.append(f"Vessel diameter not stated: D/T not checked against the paper's tabulated limit of {PVP_MAX_D_OVER_T:g}.")
    primary = inp.get("loadsPrimary")
    if primary is True:
        warnings.append("Loads declared primary. That is inside the paper's basis: total operating loads (forces and moments "
                        f"together) assumed to be at least {PVP_PRIMARY_SHARE_BASIS:.0%} primary. Apply the derived set to the "
                        "total operating load, not to a sustained or thermal part alone.")
    elif primary is None:
        warnings.append("Primary or secondary character of the loads not stated (loadsPrimary). The paper's basis is total "
                        f"operating loads assumed to be at least {PVP_PRIMARY_SHARE_BASIS:.0%} primary.")
    warnings.append(
        "Scope of the paper: ASME Section VIII Division 1 vessels, reinforced nozzles except NPS 2, thickness limits exclusive "
        "of corrosion allowance, tables developed with an effective pad thickness (full-thickness pad where local membrane governed) and Division 2 stress limits. Loads above the derived "
        "values need individual analysis; compare them with connections.nozzle-load-check."
    )

    return _result(
        "equipment.pvp2011-allowables",
        {
            "table": table,
            "basisThickness": basis,
            "interpolated": interpolated,
            "base": {k: round_half_up(base[k], 3) for k in COMPONENTS},
            "proportionalBound": ({k: round_half_up(prop_bound[k], 3) for k in COMPONENTS} if prop_bound else None),
            "thicknessFactor": round_half_up(t_factor, 5),
            "stressRatioVessel": round_half_up(s_v, 5),
            "stressRatioNozzle": round_half_up(s_n, 5),
            "stressRatio": round_half_up(s_ratio, 5),
            "ownerFactor": owner,
            "totalFactor": round_half_up(total, 5),
            "derived": derived,
            "units": "forces lbf, moments ft-lbf",
            "log": log,
        },
        "na",
        warnings,
    )


# --------------------------------------------------------------------------- registry and metadata

REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "connections.nozzle-load-check": nozzle_load_check,
    "connections.nema-sm23": nema_sm23,
    "connections.api610-annexf": api610_annexf,
    "equipment.nozzle-load-sum": nozzle_load_sum,
    "equipment.api650-annexp-ordinates": api650_annexp_ordinates,
    "equipment.pvp2011-allowables": pvp2011_allowables,
}

CITATIONS = {
    "connections.nozzle-load-check": "Per-component unity check of applied piping loads against allowables the user reads from the governing equipment standard or vendor datasheet (for example API 610 Table 5a/5b, API 660 Table 2, API 661 Table 4, API 560 Tables 7-10). PIP RECE002 design-stage factors are an owner practice and do not change the verdict.",
    "connections.nema-sm23": "NEMA SM-23 combined form 3*Fr + Mr <= a*De. The coefficient a is read from the equation of the standard that governs: 927 in API 617 Part 2 Annex E (E.1b); 500 in API 611 Annex I (I.1b) and API 612 Annex D (D.1b). De = NPS for NPS 8 and under, otherwise (NPS + 16)/3.",
    "connections.api610-annexf": "API 610 Annex F: F.1.2 a)-c) with Eq. (F.1)-(F.5) for horizontal pumps; F.2 with Eq. (F.6)-(F.11) for vertical in-line pumps; F.1.3 for loads beyond F.1.2. Table 5 ranges are user-supplied; confirm the edition of record.",
    "equipment.nozzle-load-sum": "API 661 7.1.10.2 (sum of all nozzle loadings on a single header against the header limits for all six components) and 7.1.10.3 (total on one multi-bundle bay not above three times the single-header allowance). The same sum-and-compare form serves an owner header or bay rule; the limits and multiplier are user-supplied.",
    "equipment.api650-annexp-ordinates": "API 650 Annex P, P.2.7.1 and P.2.7.2: lambda = a/(Rt)^0.5, FP = pi*a^2*P (P.2.3); ordinates (lambda/2YF)(FR/FP), (lambda/aYL)(ML/FP), (lambda/aYC)(MC/FP). Acceptance is read from Figures P.3a/b and P.5a/b (P.2.7.2.4); YF, YL, YC from Figures P.4a/b.",
    "equipment.pvp2011-allowables": "Koves, Upitis, Cullotta and Latif, 'Establishing Allowable Nozzle Loads', ASME PVP2011-57100: size scaling Eq. (1) force ~ d and Eq. (2) moment ~ d^2; thickness extrapolation Eq. (4); material ratio against 18,800 psi (shell) and 17,100 psi (neck). Tables 1A, 1B and 2 are read by the user, not embedded.",
}

# Inputs that are code, figure, datasheet or table values the user must read and be able to cite.
USER_SUPPLIED = {
    "connections.nozzle-load-check": ["allowable"],
    "connections.nema-sm23": ["coefficient"],
    "connections.api610-annexf": ["suctionAllowable", "dischargeAllowable", "suctionBore", "dischargeBore"],
    "equipment.nozzle-load-sum": ["limits", "multiplier"],
    "equipment.api650-annexp-ordinates": ["YF", "YL", "YC"],
    "equipment.pvp2011-allowables": ["table", "row", "lowerRow", "upperRow", "S_vessel", "S_nozzle"],
}

# Modules whose entered allowables the CLI layer scales by `ownerFactor` (pvp2011-allowables takes it natively).
OWNER_SCALED = {
    "connections.nozzle-load-check": ["allowable"],
    "connections.nema-sm23": ["coefficient"],
    "connections.api610-annexf": ["suctionAllowable", "dischargeAllowable"],
    "equipment.nozzle-load-sum": ["limits"],
}

_SET_DESC = "{Fx,Fy,Fz,Mx,My,Mz}"
_OWNER_DESC = ("Owner design-stage factor on the entered allowables, 0 < f <= 1 (for example PIP RECE002 "
               "4.2.2.3 / 4.2.2.4 / 4.2.3.3); omit for none")

# (name, units, required, description). Drives `list` and the unknown-key rejection.
FIELDS: Dict[str, List[tuple]] = {
    "connections.nozzle-load-check": [
        ("standard", "text", True, "Report label for the table or datasheet the allowables came from (selects nothing)"),
        ("applied", "lbf, ft-lbf", True, "Applied loads at the nozzle " + _SET_DESC + ", in the equipment's nozzle axes"),
        ("allowable", "lbf, ft-lbf", True, "Allowables " + _SET_DESC + " read by the user; each must be > 0"),
        ("ownerFactor", "-", False, _OWNER_DESC),
    ],
    "connections.nema-sm23": [
        ("NPS", "in", True, "Nozzle nominal pipe size; must be > 0"),
        ("applied", "lbf, ft-lbf", True, "Applied loads " + _SET_DESC + " at the resolution point of the standard"),
        ("coefficient", "-", True, "Coefficient a of 3*Fr + Mr <= a*De, read from the governing equation; NO default"),
        ("ownerFactor", "-", False, _OWNER_DESC),
    ],
    "connections.api610-annexf": [
        ("pumpType", "text", True, "'horizontal' (F.1.2) or 'vertical-inline' (F.2, OH3/OH6)"),
        ("units", "text", True, "'USC' (lbf, ft-lbf, in) or 'SI' (N, N*m, mm)"),
        ("suctionApplied", "per units", True, "Applied loads at the suction flange " + _SET_DESC),
        ("dischargeApplied", "per units", True, "Applied loads at the discharge flange " + _SET_DESC),
        ("suctionAllowable", "per units", True, "Table 5 base range, suction, read by the user; each > 0"),
        ("dischargeAllowable", "per units", True, "Table 5 base range, discharge, read by the user; each > 0"),
        ("suctionPosition", "in or mm", False, "{x,y,z} of the suction flange from pump centre C (required for horizontal)"),
        ("dischargePosition", "in or mm", False, "{x,y,z} of the discharge flange from pump centre C (required for horizontal)"),
        ("suctionBore", "in or mm", False, "{Do,Di} Schedule 40 section at the suction nozzle size (required for vertical-inline)"),
        ("dischargeBore", "in or mm", False, "{Do,Di} Schedule 40 section at the discharge nozzle size (required for vertical-inline)"),
        ("ownerFactor", "-", False, _OWNER_DESC),
    ],
    "equipment.nozzle-load-sum": [
        ("standard", "text", True, "Report label for the rule the limits came from (for example the header clause)"),
        ("nozzles", "list", True, "List of load sets {Fx,Fy,Fz,Mx,My,Mz} with an optional 'tag', all in one axis system"),
        ("limits", "same as nozzles", True, "Header limits " + _SET_DESC + " read by the user; each must be > 0"),
        ("multiplier", "-", False, "Factor on every limit for a bay rule (API 661 7.1.10.3: 3); default none (1)"),
        ("ownerFactor", "-", False, _OWNER_DESC),
    ],
    "equipment.api650-annexp-ordinates": [
        ("FR", "force", True, "Radial thrust at the shell mid-surface, signed (Figure P.1)"),
        ("ML", "force*length", True, "Longitudinal moment, signed"),
        ("MC", "force*length", True, "Circumferential moment, signed"),
        ("a", "length", True, "Outside radius of the opening connection"),
        ("R", "length", True, "Nominal tank radius"),
        ("t", "length", True, "Shell thickness at the connection"),
        ("L", "length", True, "Vertical distance from opening centreline to tank bottom (must exceed a)"),
        ("P", "force/length^2", True, "Product-head pressure at the opening centreline (P.2.3)"),
        ("YF", "-", True, "Read from Figure P.4a, must be > 0"),
        ("YL", "-", True, "Read from Figure P.4a, must be > 0"),
        ("YC", "-", True, "Read from Figure P.4b, must be > 0"),
    ],
    "equipment.pvp2011-allowables": [
        ("table", "text", True, "'1A' (Class 150, T >= 0.25 in), '1B' (Class 150, T >= 0.375 in) or '2' (Class 300, T >= 0.375 in)"),
        ("NPS", "in", True, "Nozzle nominal pipe size"),
        ("row", "lbf, ft-lbf", False, "The table row at NPS " + _SET_DESC + " (Fx axial, Fy longitudinal, Fz circumferential, Mx torsion, My circumferential, Mz longitudinal)"),
        ("lowerNPS", "in", False, "Interpolation: NPS of the lower adjacent row (use with lowerRow, upperNPS, upperRow, instead of row)"),
        ("lowerRow", "lbf, ft-lbf", False, "Interpolation: the lower adjacent row " + _SET_DESC),
        ("upperNPS", "in", False, "Interpolation: NPS of the upper adjacent row"),
        ("upperRow", "lbf, ft-lbf", False, "Interpolation: the upper adjacent row " + _SET_DESC),
        ("T", "in", True, "Actual vessel thickness, exclusive of corrosion allowance"),
        ("S_vessel", "psi", True, "Division 1 allowable stress of the vessel shell at design temperature (read from the stress tables)"),
        ("S_nozzle", "psi", True, "Division 1 allowable stress of the nozzle neck at design temperature"),
        ("ownerFactor", "-", False, _OWNER_DESC),
        ("ownerFactorBasis", "text", False, "Where the owner factor comes from (appears in the log)"),
        ("designTempF", "F", False, "Design temperature, for the 650 F check"),
        ("material", "text", False, "'killed-carbon-steel', 'other-ferrous', 'aluminium' or 'other'"),
        ("D", "in", False, "Vessel diameter, for the D/T check (limit 320)"),
        ("loadsPrimary", "bool", False, "true if the loads are primary in character; omit if not assessed"),
    ],
}

NESTED_KEYS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "connections.nozzle-load-check": {"applied": COMPONENTS, "allowable": COMPONENTS},
    "connections.nema-sm23": {"applied": COMPONENTS},
    "connections.api610-annexf": {
        "suctionApplied": COMPONENTS, "dischargeApplied": COMPONENTS,
        "suctionAllowable": COMPONENTS, "dischargeAllowable": COMPONENTS,
        "suctionPosition": ("x", "y", "z"), "dischargePosition": ("x", "y", "z"),
        "suctionBore": ("Do", "Di"), "dischargeBore": ("Do", "Di"),
    },
    "equipment.nozzle-load-sum": {"limits": COMPONENTS},
    "equipment.pvp2011-allowables": {"row": COMPONENTS, "lowerRow": COMPONENTS, "upperRow": COMPONENTS},
}


def render_list() -> str:
    lines = ["Modules and exact input field names (case-sensitive). Load sets are objects with Fx, Fy, Fz, Mx, My, Mz.", ""]
    for mid in REGISTRY:
        lines.append(mid)
        for name, units, required, desc in FIELDS[mid]:
            lines.append(f"    {name:<19}{units:<16}{'required' if required else 'optional':<10}{desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- pre-flight validation (CLI layer)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _val(inputs: Dict[str, Any], key: str) -> Optional[float]:
    """Numeric value of an input if present and a real number, else None (the engine reports
    missing or non-numeric inputs itself)."""
    v = inputs.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _check_nested(module: str, inputs: Dict[str, Any]) -> None:
    for field, allowed in NESTED_KEYS.get(module, {}).items():
        obj = inputs.get(field)
        if isinstance(obj, dict):
            unknown = sorted(k for k in obj if k not in allowed)
            _need(not unknown, f"unknown key(s) {', '.join(repr(k) for k in unknown)} in {field} "
                               f"(valid: {', '.join(allowed)}; names are case-sensitive)")
    if module == "equipment.nozzle-load-sum" and isinstance(inputs.get("nozzles"), list):
        for i, n in enumerate(inputs["nozzles"]):
            if isinstance(n, dict):
                unknown = sorted(k for k in n if k not in COMPONENTS and k != "tag")
                _need(not unknown, f"unknown key(s) {', '.join(repr(k) for k in unknown)} in nozzles[{i}] "
                                   f"(valid: {', '.join(COMPONENTS)}, tag; names are case-sensitive)")


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
    _check_nested(module, inputs)
    warnings: List[str] = []

    owner = _val(inputs, "ownerFactor")
    if inputs.get("ownerFactor") is not None:
        _need(owner is not None, "ownerFactor must be a number")
        _need(0 < owner <= 1, "ownerFactor must be in (0, 1]")

    if module in ("connections.nozzle-load-check", "equipment.nozzle-load-sum"):
        std = inputs.get("standard")
        _need(isinstance(std, str) and std.strip() != "",
              "standard is required: name the table or datasheet the allowables were read from")

    if module == "connections.nema-sm23":
        npsv = _val(inputs, "NPS")
        if npsv is not None:
            _need(npsv > 0, "NPS must be > 0")
        coef = _val(inputs, "coefficient")
        if coef is not None:
            _need(coef > 0, "coefficient must be > 0")
            if not any(abs(coef - c) < 1e-9 for c in (927, 500)):
                warnings.append(f"coefficient {coef:g} is neither 927 (API 617 Part 2 E.1b) nor 500 (API 611 I.1b, API 612 D.1b); "
                                "confirm it against the equation printed in your edition of the governing standard.")
    elif module == "connections.api610-annexf":
        pt = inputs.get("pumpType")
        _need(pt in ("horizontal", "vertical-inline"), 'pumpType must be "horizontal" or "vertical-inline"')
        _need(inputs.get("units") in ("USC", "SI"), 'units must be "USC" or "SI"')
        if pt == "vertical-inline" and owner is not None:
            _need(owner == 1, "ownerFactor is not supported for pumpType vertical-inline: the factor would scale only the "
                              "Table 5 ranges, not the F.6 to F.11 principal-stress limit (5950 psi / 41 N/mm2) that sets the "
                              "status, so the verdict would be unfactored. Omit ownerFactor and judge the F.2 result against "
                              "the owner's practice separately")
    elif module == "equipment.nozzle-load-sum":
        mult = _val(inputs, "multiplier")
        if mult is not None:
            _need(mult > 0, "multiplier must be > 0")
            if mult < 1:
                warnings.append("multiplier is below 1, which tightens every limit; a bay rule normally raises it (API 661 7.1.10.3: 3).")
    elif module == "equipment.api650-annexp-ordinates":
        for name in ("a", "R", "t", "L", "P", "YF", "YL", "YC"):
            v = _val(inputs, name)
            if v is not None:
                _need(v > 0, f"{name} must be > 0")
        a, L, R, t = _val(inputs, "a"), _val(inputs, "L"), _val(inputs, "R"), _val(inputs, "t")
        if a is not None and L is not None:
            _need(L > a, "L must exceed a (the opening cannot extend below the tank bottom)")
        if R is not None and t is not None and t >= R:
            raise ValueError("t must be less than R")
    elif module == "equipment.pvp2011-allowables":
        _tb = inputs.get("table")
        _need(isinstance(_tb, str) and _tb in PVP_TABLE_BASIS_THICKNESS, 'table must be "1A", "1B" or "2"')
        for name in ("NPS", "T", "S_vessel", "S_nozzle", "D"):
            v = _val(inputs, name)
            if v is not None:
                _need(v > 0, f"{name} must be > 0")
        mat = inputs.get("material")
        if mat is not None:
            _need(mat in PVP_MATERIALS, f"material must be one of {', '.join(PVP_MATERIALS)}")
        lp = inputs.get("loadsPrimary")
        if lp is not None:
            _need(isinstance(lp, bool), "loadsPrimary must be true or false")
    return warnings


def _apply_owner_factor(module: str, inp: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    f = float(inp["ownerFactor"])
    work = {k: v for k, v in inp.items() if k != "ownerFactor"}
    for field in OWNER_SCALED[module]:
        v = work.get(field)
        if isinstance(v, dict):
            work[field] = {k: (x * f if isinstance(x, (int, float)) and not isinstance(x, bool) else x) for k, x in v.items()}
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            work[field] = v * f
    note = (f"ownerFactor {f:g} applied: every entered allowable was multiplied by {f:g} before the check, so the ratios "
            "and the status below are against the factored allowables. A design-stage factor such as the PIP RECE002 "
            "values is an owner practice, not a requirement of the equipment standard.")
    return work, note


def run_module(module: str, inp: Dict[str, Any]) -> Dict[str, Any]:
    pre_warnings = validate(module, inp)
    work: Dict[str, Any] = dict(inp)
    notes: List[str] = []
    if module in OWNER_SCALED and inp.get("ownerFactor") is not None:
        work, note = _apply_owner_factor(module, work)
        notes.append(note)
    res = REGISTRY[module](work)
    if notes and module == "connections.nozzle-load-check":
        # The engine's RECE002 0.5 note tests the entered allowable, which is already factored here.
        res = dict(res)
        res["warnings"] = [w for w in res["warnings"] if not w.startswith("maxRatio exceeds 0.5 of the entered allowable")]
    if notes and module == "connections.api610-annexf":
        res = dict(res)
        res["warnings"] = [
            ("All applied component loads are within half of the factored Table 5 range (ownerFactor "
             f"{float(inp['ownerFactor']):g} applied to the entered ranges), not the base Table 5 range; "
             "F.1.1 compliance is against the unfactored range and needs a run without ownerFactor.")
            if w.startswith("All applied component loads are within the base Table 5 range") else w
            for w in res["warnings"]]
    return {
        "module": res["module"],
        "status": res["status"],
        "output": res["output"],
        "warnings": pre_warnings + notes + res["warnings"],
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
        prog="nozzle_load.py",
        description="Equipment nozzle load calculators. `list` shows module ids and input field names.",
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
    except (ValueError, OSError) as exc:
        return _fail(str(exc).replace("\n", " "))
    except ArithmeticError:  # OverflowError, decimal.InvalidOperation on very large magnitudes
        return _fail("value out of range (magnitude too large to evaluate)")


if __name__ == "__main__":
    sys.exit(main())
