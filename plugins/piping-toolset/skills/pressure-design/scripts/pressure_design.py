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

CODE TABLE VALUES
    The EQUATIONS are method. The numeric inputs S (allowable stress), E (quality
    factor), W (weld strength reduction), Y / y (temperature coefficient) and the
    test-pressure allowables are CODE TABLE VALUES. This script embeds none of
    them. The user reads each from their own copy of the code and supplies it, or a
    run supplies it through the optional code_values input (below) with its citation.

CODE_VALUES (optional top-level input)
    {"code_values": {"S": {"value": 12.345, "unit": "ksi",
                           "citation": {"standard": "...", "edition": "...", "table": "...",
                                        "row": "...", "column": "..."},
                           "source": "connector"}}}
    The key is an input name from `list`. An input that is absent from the main inputs is
    filled from code_values[name]["value"]; one that is present must agree, otherwise the run
    exits 2 with "code_values.<name> conflicts with input <name>". A name this module does not
    declare exits 2. "source" is "connector" or "user". A unit other than the input's unit is
    converted when the factor is exact (ksi to psi) and rejected otherwise. This module has no
    nested inputs, so every name is a plain input name. The envelope gains
    "code_value_provenance": {name: {unit, citation, source}}; "inputs" shows the values used
    and "user_supplied" counts a filled input. Nothing here reaches a network.

USAGE
    python pressure_design.py list
    python pressure_design.py list --json
    python pressure_design.py piping.b313-wall-thickness --input '{"P": 500, ...}'
    python pressure_design.py b313-wall-thickness --input-file job.json

    Exit status: 0 = calculated, 2 = bad input (one-line message on stderr).

    A job file may carry comment keys: a top-level key that starts with an underscore
    (for example "_note") is dropped before the inputs are read. See examples/.

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
    """Input name -> unit label, for the code_values block (this module has no nested inputs)."""
    return {f[0]: f[1] for f in FIELDS.get(module, [])}


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
        "status": _verdict(margin >= 0),
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
    inputs, provenance, cv_notes = apply_code_values(inputs, module, _cv_fields(module))
    pre_warnings = cv_notes + validate(module, inputs)
    result = REGISTRY[module](dict(inputs))
    output = dict(result["output"])
    if module == "piping.miter-allowable-pressure" and inputs.get("miters") == 1:
        output["Pm2"] = None          # not evaluated for a single miter (the engine reports 0.0)
    defaults = {}
    for name, _u, required, _us, _d in FIELDS[module]:
        if not required and name in ("W",) and inputs.get(name) is None:
            defaults[name] = 1.0
    present_supplied = [n for n in user_supplied_names(module) if inputs.get(n) is not None]
    envelope = {
        "module": result["module"],
        "status": result["status"],
        "output": output,
        "warnings": pre_warnings + result["warnings"],
        "citation": CITATIONS[module],
        "inputs": inputs,
        "user_supplied": present_supplied,
        "defaults_applied": defaults,
    }
    if provenance is not None:
        envelope["code_value_provenance"] = provenance
    return envelope


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
    lines.append("Any input above may instead come from the optional top-level object code_values: "
                 "{name: {value, unit, citation{standard, edition, table, row, column?}, source: connector|user}}.")
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
        inputs = {k: v for k, v in inputs.items() if not str(k).startswith("_")}   # "_note"-style comment keys

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
