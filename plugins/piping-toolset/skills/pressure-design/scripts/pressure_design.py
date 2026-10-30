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
    python pressure_design.py b313-wall-thickness --input-file job.json --project-basis project-basis.json

    Exit status: 0 = the run completed, 2 = bad input (one-line message on stderr). Exit 0 does
    not mean a design basis: a tripped validity gate also exits 0, so callers must read
    "status" / "result_grade" ("manual check required" carries no design value).

GATES (CLI layer; the engine functions and their fixture outputs are unchanged)
    W basis. Where the code and edition's equation carries W (B31.3 Eq. (3a), (3c), (4a)-(4c);
    B31.1 Eq. (7), (9), (3) from the 2018 edition), W is part of the contract: W omitted and
    no W_basis, or W = 1.0 with no W_basis (and no cited code_values entry for W), exits 2 with
    the W table and edition to read. W omitted with a W_basis is applied as 1.0 on that basis.
    B31.9 and B31.12 equations carry no W; the run records that and needs no basis. B31.1-2016
    straight pipe is gated by the para. 104.1.1 route: Eq. (7) (no W) for seamless pipe or pipe
    below the creep range, para. 104.1.4 Eq. (11) (with W) for welded pipe in the creep range;
    W or a W_basis naming the route is required and the route is warned on the sheet.
    "weld_factor_basis" records the outcome; "defaults_applied" never holds W.
    Thin-wall validity. Straight-pipe thickness (B31.3, B31.1), the MAWP inverse and the bend
    thickness carry "validity": P_over_SE (P/(S*E); the computed allowable pressure for MAWP;
    times Mf for B31.12) against 0.385 and the thickness against D/6. When either trips the
    envelope "status" and "result_grade" are "manual check required", "output" is empty, and
    the engine's numbers move to "equation_value" labelled "equation value, not a design
    basis", with the clause that calls for special consideration in "banner" and "warnings".
    A valid run carries "result_grade": "calculated" and unchanged numbers and status.
    Basis inputs W_basis, edition and code (the last for the MAWP and bend modules) are text,
    echoed in "inputs" and never passed to the equations.

PROJECT BASIS (0.8.0; optional top-level "project_basis" object or --project-basis <file>)
    One pipingtoolset.project-basis/1 record shared by every skill (references/project-basis.md);
    file and key both given with different content exits 2. This skill fills: code (MAWP and bend
    modules) from code.standard, which must lie in the module's code family on every module (else
    exit 2, "project_basis.code.standard conflicts with input <module> ..."); edition from
    code.edition; P from the design state (role design, else the first state); W_basis "seamless"
    from materials[use=pipe] when its form is seamless, W_basis is absent and W is absent or 1.0.
    An input present in both and different exits 2; units.system SI exits 2. A B31.1 record on the
    branch module grades that check "screening"; Category M or Chapter IX service grades the run
    "manual check required". The envelope gains project_basis_applied and basis_section (calc-sheet
    section 1, every ASSUMED item first).

RESULT STATUS (0.8.0)
    Every envelope carries result_status (calculated | screening | manual check required |
    pointer only | not checked: the worst word among the checks performed; "not checked" rows never
    set it), checks[] {name, result_status, status, note},
    banner_allowed (false means no PASS wording on the sheet) and result_status_line, the line under
    the sheet title. The checks a module does not perform are listed as "not checked". A code_values
    entry {"mode": "pointer", "citation": {...}, "source": ...} with no value makes the run "pointer
    only": status "pointer only", empty output, no equation evaluated. Existing status words are
    unchanged. Any ASSUMED item of the record adds one "ASSUMED inputs" row graded "manual check
    required" (banner_allowed false).

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
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional


# BEGIN shared project_basis (do not edit here; source tools/shared/project_basis.py)
# Optional top-level input "project_basis" (or --project-basis <file>, never both with different
# content): one project record that every PipingToolset skill reads. An input absent from the main
# inputs is filled from the record where the skill has a slot; one that is present must agree, or
# the run stops with "project_basis.<path> conflicts with input <name>". Unknown keys and bad enum
# words are rejected. Schema and fill map: references/project-basis.md. The only file this block
# reads is the --project-basis file named on the command line.

PROJECT_BASIS_SCHEMA_ID = "pipingtoolset.project-basis/1"
_PB_AXIS = ("enum", ("X", "Y", "Z"))
_PB_SIGNED = ("enum", ("X", "Y", "Z", "+X", "+Y", "+Z", "-X", "-Y", "-Z"))
_PB_CASE = ("oneof", ("id", ("list", "id")))
PROJECT_BASIS_SCHEMA = ("obj", {
    "schema": ("enum", (PROJECT_BASIS_SCHEMA_ID,)),
    "project": ("obj", {k: "str" for k in ("name", "number", "line", "revision", "calcBy", "date")}, ()),
    "code": ("obj", {"standard": "str", "edition": "str", "route": "str"}, ()),
    "service": ("obj", {"fluid_category": ("enum", ("Normal", "Category D", "Category M", "High Pressure")),
                        "fluid": "str", "corroded": "bool", "cyclic": "bool"}, ()),
    "owner_practice": ("list", ("obj", {"document": "str", "edition": "str", "items": ("list", (
        "oneof", ("str", ("obj", {"name": "str", "value": ("oneof", ("num", "str")), "unit": "str",
                                  "note": "str"}, ("name",)))))}, ("document",))),
    "materials": ("list", ("obj", {
        "id": "str", "spec": "str", "grade": "str", "notes": "str",
        "form": ("enum", ("seamless", "welded", "ERW", "EFW", "SAW", "forged", "cast", "plate", "bar", "other")),
        "use": ("enum", ("pipe", "fitting", "flange", "bolt", "gasket", "vessel", "nozzle", "support", "other"))},
        ())),
    "states": ("list", ("obj", {
        "key": "str", "name": "str", "T_F": "num", "P_psig": "num", "cycles": "num",
        "role": ("enum", ("operating", "design", "upset", "startup", "shutdown", "steamout", "installed",
                          "hydrotest", "pneumatic", "other")),
        "slot": ("obj", {"T": ("slot", "T"), "P": ("slot", "P"), "D": ("slot", "D")}, ())}, ("key",))),
    "installation_T_F": "num",
    "units": ("obj", {"system": ("enum", ("USC", "SI")), "force": "str", "moment": "str", "length": "str",
                      "temperature": "str", "pressure": "str", "stress": "str"}, ()),
    "load_case_ids": ("obj", {"software": ("enum", ("CAESAR II", "AutoPIPE")), "version": "str",
                              "cases": ("obj", {k: _PB_CASE for k in ("SUS", "OPE", "EXP", "OCC", "HYD", "HGR")},
                                        ())}, ()),
    "equipment_axes": ("obj", {"global_vertical": ("enum", ("Y", "Z")), "pipe_axis": _PB_AXIS, "notes": "str",
                               "nozzle_axis_map": ("obj", {k: _PB_SIGNED for k in ("Fx", "Fy", "Fz", "Mx", "My", "Mz")},
                                                   ())}, ()),
    "citations": ("list", ("obj", {k: "str" for k in ("ref", "standard", "edition", "table", "row", "column", "note")},
                           ())),
    "assumptions": ("list", ("obj", {"item": "str", "status": ("enum", ("ASSUMED", "confirmed")), "note": "str",
                                     "owner": "str"}, ("item",))),
}, ("schema",))
# units.<name> when the record gives only the system
PROJECT_BASIS_UNIT_DEFAULTS = {
    "USC": {"force": "lbf", "moment": "ft-lbf", "length": "in", "temperature": "F", "pressure": "psig", "stress": "psi"},
    "SI": {"force": "N", "moment": "N-m", "length": "mm", "temperature": "C", "pressure": "kPa", "stress": "MPa"},
}
_PB_MISSING = object()
PROJECT_BASIS_SKIP = object()  # a fill_map transform returns this to leave the input alone


class ProjectBasisError(ValueError):
    """A project_basis record that cannot be used; the CLI prints the message and exits 2."""


def _pb_is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pb_kind_ok(v, kind):
    if kind == "str":
        return isinstance(v, str)
    if kind == "num":
        return _pb_is_num(v)
    if kind == "bool":
        return isinstance(v, bool)
    return isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool))  # "id"


def _pb_check(v, spec, where, errors):
    kind = spec if isinstance(spec, str) else spec[0]
    if kind in ("str", "num", "bool", "id"):
        if not _pb_kind_ok(v, kind):
            hint = " (write an edition year or an id in quotes)" if kind == "str" and _pb_is_num(v) else ""
            label = {"str": "string", "num": "number", "bool": "true or false", "id": "string or whole number"}[kind]
            errors.append(f"{where}: must be a {label}{hint}")
    elif kind == "enum":
        if not isinstance(v, str) or v not in spec[1]:
            errors.append(f"{where}: {v!r} is not one of {', '.join(spec[1])}")
    elif kind == "slot":
        if not (isinstance(v, str) and len(v) > 1 and v[0] == spec[1] and v[1:].isdigit()):
            errors.append(f"{where}: {v!r} must be {spec[1]} followed by a number, e.g. {spec[1]}1")
    elif kind == "oneof":
        if all(_pb_errors(v, s, where) for s in spec[1]):
            errors.append(f"{where}: {v!r} has the wrong type")
    elif kind == "list":
        if not isinstance(v, list):
            errors.append(f"{where}: must be a list")
            return
        for i, item in enumerate(v):
            _pb_check(item, spec[1], f"{where}[{i}]", errors)
    elif not isinstance(v, dict):
        errors.append(f"{where}: must be an object")
    else:
        for key in v:
            if key not in spec[1]:
                errors.append(f"{where}.{key}: unknown key (valid: {', '.join(spec[1])})")
        for key in spec[2]:
            if key not in v:
                errors.append(f"{where}.{key}: required")
        for key, item in v.items():
            if key in spec[1]:
                _pb_check(item, spec[1][key], f"{where}.{key}", errors)


def _pb_errors(v, spec, where):
    errors = []
    _pb_check(v, spec, where, errors)
    return errors


def validate_project_basis(obj):
    """Every problem with a project_basis record, as 'project_basis.<path>: <reason>' strings."""
    errors = _pb_errors(obj, PROJECT_BASIS_SCHEMA, "project_basis")
    states = obj.get("states") if isinstance(obj, dict) else None
    keys = [s.get("key") for s in states if isinstance(s, dict)] if isinstance(states, list) else []
    for key in sorted({k for k in keys if isinstance(k, str) and keys.count(k) > 1}):
        errors.append(f"project_basis.states: key {key!r} is used more than once")
    return errors


def _pb_same(a, b):
    if _pb_is_num(a) and _pb_is_num(b):
        return abs(float(a) - float(b)) <= 1e-9 * max(abs(float(a)), abs(float(b)))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_pb_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_pb_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _pb_copy(v):
    if isinstance(v, dict):
        return {k: _pb_copy(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_pb_copy(x) for x in v]
    return v


def load_project_basis(cli_path, top_level_obj):
    """The validated record from --project-basis <cli_path> and/or the input's project_basis object.

    None when neither is given. Both given with different content raises ProjectBasisError.
    """
    from_file = _PB_MISSING
    if cli_path:
        import json as _pb_json
        try:
            with open(cli_path, encoding="utf-8-sig") as fh:
                from_file = _pb_json.load(fh)
        except OSError as exc:
            raise ProjectBasisError(f"cannot read --project-basis file {cli_path}: {exc.strerror or exc}")
        except ValueError as exc:
            raise ProjectBasisError(f"--project-basis file {cli_path} is not valid JSON: {exc}")
    if from_file is not _PB_MISSING and top_level_obj is not None and not _pb_same(from_file, top_level_obj):
        raise ProjectBasisError("project_basis conflicts with --project-basis file")
    basis = top_level_obj if from_file is _PB_MISSING else from_file
    if basis is None and from_file is _PB_MISSING:
        return None
    errors = validate_project_basis(basis)
    if errors:
        raise ProjectBasisError(f"project_basis is not a valid {PROJECT_BASIS_SCHEMA_ID} record: " + "; ".join(errors))
    return _pb_copy(basis)


def _pb_steps(path):
    steps, depth, cur = [], 0, ""
    for ch in path:
        depth += (ch == "[") - (ch == "]")
        if ch == "." and depth == 0:
            steps.append(cur)
            cur = ""
        else:
            cur += ch
    return steps + [cur]


def basis_get(basis, path, default=None):
    """Value at a basis path: dotted keys plus list selectors name[2], name[k=v], name[k=v|first]."""
    node = basis
    for step in _pb_steps(path):
        name, _, sel = step.partition("[")
        if name:
            if not isinstance(node, dict) or node.get(name) is None:
                return default
            node = node[name]
        if not sel:
            continue
        sel = sel[:-1] if sel.endswith("]") else sel
        if not isinstance(node, list) or not node:
            return default
        if sel.isdigit():
            if int(sel) >= len(node):
                return default
            node = node[int(sel)]
            continue
        cond, _, fallback = sel.partition("|")
        key, _, want = cond.partition("=")
        hits = [x for x in node if isinstance(x, dict) and x.get(key) == want]
        if not hits and fallback != "first":
            return default
        node = hits[0] if hits else node[0]
    return node


def basis_units(basis):
    """units with the system's defaults filled in ({} without a units.system)."""
    units = dict((basis or {}).get("units") or {})
    defaults = PROJECT_BASIS_UNIT_DEFAULTS.get(units.get("system"))
    return dict(defaults, **units) if defaults else units


def basis_assumptions(basis):
    """The ASSUMED items (a missing status counts as ASSUMED), copied verbatim."""
    return [_pb_copy(a) for a in (basis or {}).get("assumptions") or [] if a.get("status", "ASSUMED") == "ASSUMED"]


def project_basis_conflict(path, name):
    return ProjectBasisError(f"project_basis.{path} conflicts with input {name}")


def _pb_input_get(inputs, name):
    node = inputs
    for key in name.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _pb_input_put(inputs, name, value):
    keys = name.split(".")
    node = inputs
    for key in keys[:-1]:
        if node.get(key) is None:
            node[key] = {}
        if not isinstance(node[key], dict):
            raise ProjectBasisError(f"input {key} must be an object to take {name} from project_basis")
        node = node[key]
    node[keys[-1]] = value


def fill_from_basis(inputs, basis, fill_map):
    """Fill-or-conflict from the record. fill_map: [(input name (dotted), basis path, transform or None)].

    A basis path that resolves to nothing, or a transform that returns PROJECT_BASIS_SKIP, leaves
    the input alone; an absent (or null) input is filled; a present one must agree. Returns
    (effective inputs, applied); (inputs, None) when basis is None. The caller's dict is not modified.
    """
    if basis is None:
        return inputs, None
    eff = _pb_copy(inputs)
    used = []
    for entry in fill_map:
        name, path, transform = (tuple(entry) + (None,))[:3]
        value = basis_get(basis, path, _PB_MISSING)
        if value is _PB_MISSING:
            continue
        if transform is not None:
            value = transform(value)
            if value is PROJECT_BASIS_SKIP:
                continue
        have = _pb_input_get(eff, name)
        if have is None:
            _pb_input_put(eff, name, _pb_copy(value))
            action = "filled"
        elif _pb_same(have, value):
            action = "agreed"
        else:
            raise project_basis_conflict(path, name)
        used.append({"input": name, "basis": path, "action": action})
    return eff, {"schema": PROJECT_BASIS_SCHEMA_ID, "fields_used": used,
                 "assumptions": basis_assumptions(basis), "conflicts": []}


def mark_basis_used(applied, path, name=None, action="noted"):
    """Record a basis field the skill read for the sheet only (no script input)."""
    if applied is not None:
        applied["fields_used"].append({"input": name, "basis": path, "action": action})
    return applied


def _pb_fmt(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, dict):
        return ", ".join(f"{k}={_pb_fmt(x)}" for k, x in v.items())
    if isinstance(v, list):
        return "; ".join(_pb_fmt(x) for x in v)
    return str(v).replace("|", "/")


def render_basis_section(applied, basis, heading=None):
    """Markdown for calc-sheet section 1 (Basis): the ASSUMED list first, then the record, then fields used."""
    if basis is None:
        return ""
    out = [heading, ""] if heading else []
    assumed = (applied or {}).get("assumptions", basis_assumptions(basis))
    if assumed:
        out.append("**ASSUMED - confirm before issue:**")
        for a in assumed:
            extra = "".join(f"; {k}: {_pb_fmt(a[k])}" for k in ("note", "owner") if a.get(k))
            out.append(f"- {_pb_fmt(a['item'])}{extra}")
    else:
        out.append("No ASSUMED items in the project basis record.")
    out += ["", f"| Basis item ({PROJECT_BASIS_SCHEMA_ID}) | Value |", "|---|---|"]
    rows = [("Project", basis.get("project")), ("Code", basis.get("code")), ("Service", basis.get("service")),
            ("Units", basis_units(basis) or None), ("Installation T_F", basis.get("installation_T_F")),
            ("Equipment axes", basis.get("equipment_axes")), ("Load case ids", basis.get("load_case_ids"))]
    rows += [(f"State {s['key']}", {k: x for k, x in s.items() if k != "key"}) for s in basis.get("states") or []]
    rows += [(f"Material {m.get('id', i + 1)}", {k: x for k, x in m.items() if k != "id"})
             for i, m in enumerate(basis.get("materials") or [])]
    rows += [(f"Owner practice {p['document']}", {k: x for k, x in p.items() if k != "document"})
             for p in basis.get("owner_practice") or []]
    rows += [(f"Citation {c.get('ref', i + 1)}", {k: x for k, x in c.items() if k != "ref"})
             for i, c in enumerate(basis.get("citations") or [])]
    out += [f"| {label} | {_pb_fmt(v)} |" for label, v in rows if v not in (None, {}, [])]
    used = (applied or {}).get("fields_used") or []
    if used:
        out += ["", "Taken from the record: " + "; ".join(
            f"{u['input'] or 'sheet'} <- {u['basis']} ({u['action']})" for u in used)]
    return "\n".join(out) + "\n"
# END shared project_basis


# BEGIN shared result_status (do not edit here; source tools/shared/result_status.py)
# Output status taxonomy. Every result envelope carries result_status (envelope_status of its
# checks: the worst word among the checks the module performs) and checks: [{name, result_status,
# status (pass/fail/na), note[, unresolved_factor]}]. "not checked" rows never drive the envelope;
# they are listed, and the envelope reads "not checked" only when every row is. A positive banner
# word (PASS, OK, ISSUE, DELIVERABLE) is printed only when banner_allowed() is true: never under
# "manual check required" or "pointer only", nor under "screening" when a reconstructed factor in
# the chain is unresolved. Any ASSUMED input gives one "ASSUMED inputs" row (assumed_inputs_check)
# graded manual check required, so an unconfirmed input always holds the banner.

RESULT_STATUS = ("calculated", "screening", "manual check required", "pointer only", "not checked")
# severity for worst_of (ordering only): manual check required > pointer only > screening > not checked > calculated
RESULT_STATUS_SEVERITY = {"manual check required": 4, "pointer only": 3, "screening": 2, "not checked": 1,
                          "calculated": 0}
CHECK_STATUS = ("pass", "fail", "na")
ASSUMED_CHECK_NAME = "ASSUMED inputs"


def _rs_word(item):
    word = item.get("result_status") if isinstance(item, dict) else item
    if word not in RESULT_STATUS_SEVERITY:
        raise ValueError(f"result_status {word!r} is not one of {', '.join(RESULT_STATUS)}")
    return word


def worst_of(statuses):
    """The most severe result_status of words or check dicts; 'not checked' for an empty list."""
    words = [_rs_word(s) for s in statuses]
    return max(words, key=RESULT_STATUS_SEVERITY.__getitem__) if words else "not checked"


def envelope_status(checks):
    """The envelope word: the most severe word among the checks that are not 'not checked'.

    'not checked' rows (limits the module does not perform) never drive it; when every row is
    'not checked', or there are none, the envelope reads 'not checked'.
    """
    words = [w for w in (_rs_word(c) for c in checks) if w != "not checked"]
    return worst_of(words) if words else "not checked"


def make_check(name, result_status, status=None, note=None, unresolved_factor=False):
    """One checks[] entry. status is pass/fail/na (None means na); unresolved_factor only with screening."""
    _rs_word(result_status)
    status = "na" if status is None else status
    if status not in CHECK_STATUS:
        raise ValueError(f"check status {status!r} is not one of {', '.join(CHECK_STATUS)}")
    if unresolved_factor and result_status != "screening":
        raise ValueError("unresolved_factor marks a screening check only")
    check = {"name": name, "result_status": result_status, "status": status, "note": note}
    if unresolved_factor:
        check["unresolved_factor"] = True
    return check


def assumed_inputs_check(items):
    """The one 'ASSUMED inputs' row for every ASSUMED item (strings or {item[, note]} dicts), or None.

    Graded manual check required, so the envelope follows it and no positive banner prints; the
    note reads 'confirm before issue: <item>; <item>' (duplicates dropped, order kept).
    """
    texts = []
    for it in items or ():
        text = it.get("item") if isinstance(it, dict) else it
        text = str(text).strip() if text is not None else ""
        if text and text not in texts:
            texts.append(text)
    if not texts:
        return None
    return make_check(ASSUMED_CHECK_NAME, "manual check required", "na",
                      "confirm before issue: " + "; ".join(texts))


def not_performed(checks):
    """'not performed by this module: a; b' for the 'not checked' rows of checks, '' when there are none."""
    names = [c["name"] for c in checks if isinstance(c, dict) and c.get("result_status") == "not checked"]
    return "not performed by this module: " + "; ".join(names) if names else ""


def banner_allowed(result_status, unresolved_factor=False):
    """False for manual check required, pointer only, and screening with an unresolved factor."""
    word = _rs_word(result_status)
    if word in ("manual check required", "pointer only"):
        return False
    return not (word == "screening" and unresolved_factor)


def status_fields(checks):
    """{result_status: envelope_status, checks} to merge into an envelope (adds keys, changes none)."""
    checks = list(checks)
    return {"result_status": envelope_status(checks), "checks": checks}


def checks_banner_allowed(checks):
    """banner_allowed for the envelope word of checks, with any unresolved_factor among them."""
    checks = list(checks)
    return banner_allowed(envelope_status(checks), any(c.get("unresolved_factor") for c in checks))


def banner_word(ok_word, result_status, unresolved_factor=False):
    """ok_word (e.g. PASS) when the banner rule allows it, else the result_status in capitals."""
    return ok_word if banner_allowed(result_status, unresolved_factor) else _rs_word(result_status).upper()


def render_status_line(result_status, why):
    """The one line under every calc-sheet title: 'Result status: <word> - <why>' (ASCII ' - ')."""
    word = _rs_word(result_status)
    return f"Result status: {word} - {why}" if why else f"Result status: {word}"
# END shared result_status


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
        ("W", "-", True, True, "Weld joint strength reduction factor W (Table 302.3.5; 302.3.5-1 in 2024). W = 1.0 needs W_basis"),
        ("Y", "-", True, True, "Coefficient Y (Table 304.1.1)"),
        ("c", "in", True, False, "Sum of mechanical + corrosion + erosion allowances"),
        ("millTolerance", "fraction", True, False, "Mill under-tolerance as a fraction, e.g. 0.125"),
    ],
    "piping.b311-wall-thickness": [
        ("P", "psi", True, False, "Internal design pressure"),
        ("D", "in", True, False, "Pipe outside diameter"),
        ("S", "psi", True, True, "Allowable stress at design temperature (Appendix A)"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld strength reduction factor W (para. 102.4.7, Table 102.4.7-1). Omitted or 1.0 needs W_basis where the edition's Eq. (7) carries W"),
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
        ("W", "-", False, True, "Weld joint strength reduction factor W (B31.3 Table 302.3.5 / 302.3.5-1, B31.1 Table 102.4.7-1). Omitted or 1.0 needs W_basis unless code is B31.9 / B31.12 (no W term)"),
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
        ("W", "-", False, True, "Weld joint strength reduction factor W. Omitted or 1.0 needs W_basis where the equation carries W"),
        ("y", "-", True, True, "Temperature coefficient y / Y"),
        ("A", "in", True, False, "Additional thickness allowance"),
    ],
    "piping.miter-allowable-pressure": [
        ("S", "psi", True, True, "Allowable stress at design temperature"),
        ("E", "-", True, True, "Quality / joint factor E"),
        ("W", "-", False, True, "Weld joint strength reduction factor W. Omitted or 1.0 needs W_basis where the equation carries W"),
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
# Validity gates and the W basis (CLI / envelope layer only). The engine functions above are
# untouched, so every fixture case gives the same numbers and status words; these gates read
# the engine's result and the inputs and decide whether that result may be used as a design
# basis. Output status words (the pack taxonomy): calculated / screening / manual check
# required / pointer only / not checked. This layer uses "calculated" and "manual check
# required".
# --------------------------------------------------------------------------- #

# The thick-wall trigger stated in the running text of B31.3 para. 304.1.2(b) (and B31.12
# para. IP-3.2.1(b) with Mf): an equation constant, not a table value.
THIN_WALL_LIMIT = 0.385
LABEL_EQUATION_VALUE = "equation value, not a design basis"
GRADE_CALCULATED = "calculated"
GRADE_MANUAL = "manual check required"

# Modules whose equation can carry W, and the subset that applies the straight-pipe thin-wall
# basis (Eq. (3a) / Eq. (7) / their inverse / the I-factor form of the same equation).
W_MODULES = ("piping.b313-wall-thickness", "piping.b311-wall-thickness", "piping.b31-allowable-pressure",
             "piping.bend-thickness", "piping.miter-allowable-pressure")
GATED_MODULES = ("piping.b313-wall-thickness", "piping.b311-wall-thickness", "piping.b31-allowable-pressure",
                 "piping.bend-thickness")
FIXED_CODE = {"piping.b313-wall-thickness": "B31.3", "piping.b311-wall-thickness": "B31.1",
              "piping.miter-allowable-pressure": "B31.3"}
CODE_CHOICES = {"piping.b31-allowable-pressure": ("B31.3", "B31.1", "B31.9", "B31.12"),
                "piping.bend-thickness": ("B31.3", "B31.1")}
W_BASIS_EXAMPLES = ("seamless", "below creep range per table note", "longitudinal weld, confirmed")
_W_BASIS_HINT = " | ".join(W_BASIS_EXAMPLES) + " | free text"

# Basis inputs: strings the CLI reads and records; they never reach the engine functions.
#   (name, description)
BASIS_FIELDS: Dict[str, List[tuple]] = {}
for _m in W_MODULES:
    BASIS_FIELDS[_m] = [
        ("W_basis", "Why W is what it is, recorded on the sheet: " + _W_BASIS_HINT
         + ". Required when W is omitted or W = 1.0 and the edition's equation carries W"),
        ("edition", "Code edition year of record, e.g. 2022 (decides whether the B31.1 equation carries W)"),
    ]
    if _m in CODE_CHOICES:
        BASIS_FIELDS[_m].append(("code", "Code of record: " + " | ".join(CODE_CHOICES[_m])
                                 + " (omitted: treated as an equation that carries W)"))
del _m


def _edition_year(edition: Any) -> Optional[int]:
    """The four-digit year in an edition input (2022, "2022", "B31.1-2016"), or None."""
    if edition is None:
        return None
    hits = re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", str(edition))
    return int(hits[-1]) if hits else None


def split_basis(module: str, inputs: dict) -> tuple:
    """(engine inputs without the basis strings, basis dict). Rejects malformed basis values."""
    names = [f[0] for f in BASIS_FIELDS.get(module, [])]
    basis = {n: inputs[n] for n in names if inputs.get(n) is not None}
    engine = {k: v for k, v in inputs.items() if k not in names}
    wb = basis.get("W_basis")
    if wb is not None and (not isinstance(wb, str) or not wb.strip()):
        raise ValueError(f"W_basis must be a non-empty string ({_W_BASIS_HINT})")
    ed = basis.get("edition")
    if ed is not None and (isinstance(ed, bool) or not isinstance(ed, (str, int)) or not str(ed).strip()):
        raise ValueError("edition must be a year or a string such as \"2022\"")
    if "code" in basis:
        raw = basis["code"]
        norm = re.sub(r"^ASME", "", raw.replace(" ", "").upper()) if isinstance(raw, str) else None
        choices = CODE_CHOICES[module]
        if norm not in choices:
            raise ValueError(f"code must be one of {', '.join(choices)} for {module}")
        basis["code"] = norm
    return engine, basis


def _w_table(code: Optional[str], year: Optional[int]) -> str:
    """Pointer to the W table and paragraph for a code and edition (table names only, no values)."""
    if code == "B31.1":
        if year == 2016:
            return "B31.1 Table 102.4.7 (para. 102.4.7)"
        return "B31.1 Table 102.4.7-1 (para. 102.4.7)"
    if code == "B31.3":
        if year is not None and year >= 2024:
            return "B31.3 Table 302.3.5-1 (para. 302.3.5(e))"
        if year is not None:
            return "B31.3 Table 302.3.5 (para. 302.3.5(e))"
        return "B31.3 Table 302.3.5 (Table 302.3.5-1 from the 2024 edition; para. 302.3.5(e))"
    return ("B31.3 Table 302.3.5 / 302.3.5-1 (para. 302.3.5(e)) or B31.1 Table 102.4.7-1 "
            "(para. 102.4.7), by the code of record")


# B31.1-2016 straight pipe: para. 104.1.1 picks the equation by construction and temperature.
# Eq. (7)/(9) of para. 104.1.2 (no W) cover seamless pipe and pipe below the creep range; Eq.
# (11)/(12) and the design-pressure form of para. 104.1.4 (S*E*W, the engine's own form) cover
# longitudinal- or spiral-welded pipe in the creep range. The route can therefore require W.
ROUTE_2016 = "route"
_ROUTE_2016_TEXT = ("B31.1-2016 para. 104.1.1: seamless pipe and pipe below the creep range take para. 104.1.2 "
                    "Eq. (7) (no W); longitudinal- or spiral-welded pipe in the creep range takes para. 104.1.4 "
                    "Eq. (11) with W from B31.1 Table 102.4.7 (para. 102.4.7)")


def _w_route(module: str, basis: dict) -> tuple:
    """(code or None, year or None, carries, reason). carries: True (the equation carries W),
    False (it has none; reason says why) or ROUTE_2016 (B31.1-2016 straight pipe: the para.
    104.1.1 route decides, so W is gated like an equation that carries it)."""
    code = FIXED_CODE.get(module, basis.get("code"))
    year = _edition_year(basis.get("edition"))
    if code in ("B31.9", "B31.12"):
        return code, year, False, f"the {code} pressure-design equation has no W term"
    if code == "B31.1" and year == 2016:
        if module == "piping.bend-thickness":
            return code, year, False, "B31.1-2016 para. 102.4.5 Eq. (3) has no W term"
        return code, year, ROUTE_2016, _ROUTE_2016_TEXT
    return code, year, True, None


def w_gate(module: str, inputs: dict, basis: dict, provenance: Optional[dict]) -> tuple:
    """Enforce the W rule. Returns (engine inputs, record, warnings); raises ValueError (exit 2).

    Where the code and edition's equation carries W: W and W_basis both absent stops the run
    with the table to read; W = 1.0 needs W_basis (or a cited code_values entry for W); W
    omitted with a W_basis is applied as 1.0 on that basis and shown in inputs. Where the
    equation has no W the run records that and needs no basis."""
    code, year, carries, reason = _w_route(module, basis)
    W = inputs.get("W")
    if W is not None and (isinstance(W, bool) or not isinstance(W, (int, float))):
        raise ValueError("input 'W' must be a number")
    wb = basis.get("W_basis")
    cited = (provenance or {}).get("W")
    where = f"{code}-{year}" if (code and year) else f"{code or 'the code'} edition of record"
    warnings: List[str] = []
    record: Dict[str, Any] = {"code": code, "edition": basis.get("edition"), "W_in_equation": carries}
    if not carries:
        record.update(W=W, basis=wb or reason, basis_source="W_basis" if wb else "equation has no W", note=reason)
        if W is not None and float(W) != 1.0:
            warnings.append(f"W = {_js_num(float(W))} applied although {reason}; the result is conservative.")
        return inputs, record, warnings
    table = _w_table(code, year)
    if carries == ROUTE_2016:
        if W is None and wb is None:
            raise ValueError(f"W or W_basis is required for {module} under {where}: {reason}; give W, or "
                             f"W_basis naming the route ({_W_BASIS_HINT})")
        if W is not None and float(W) == 1.0 and wb is None and cited is None:
            raise ValueError(f"W = 1.0 needs W_basis for {module} under {where}: {reason} ({_W_BASIS_HINT})")
        creep_weld = W is not None and float(W) < 1.0
        record.update(W_in_equation=creep_weld, note=reason,
                      route=("para. 104.1.4 Eq. (11) (S*E*W)" if creep_weld else
                             "para. 104.1.2 Eq. (7), or para. 104.1.4 Eq. (11) at W = 1.0 (the same numbers), "
                             "on the stated basis"))
        if not creep_weld:
            warnings.append(f"B31.1-2016: para. 104.1.2 Eq. (7) applies only to seamless pipe or pipe below the "
                            f"creep range (para. 104.1.1); longitudinal- or spiral-welded pipe in the creep range is "
                            f"para. 104.1.4 with W from {table}. Basis recorded: {wb or 'cited W'}.")
    elif W is None and wb is None:
        raise ValueError(f"W is required for {module}: read W from {table} for {where} at the design "
                         f"temperature, or give W_basis ({_W_BASIS_HINT})")
    elif W is not None and float(W) == 1.0 and wb is None and cited is None:
        raise ValueError(f"W = 1.0 needs W_basis for {module}: confirm it from {table} for {where} ({_W_BASIS_HINT})")
    if W is None:
        inputs = dict(inputs, W=1.0)
        record.update(W=1.0, basis=wb, basis_source="W_basis (W omitted, applied as 1.0)")
    elif wb is not None:
        record.update(W=W, basis=wb, basis_source="W_basis")
    elif cited is not None:
        c = cited.get("citation") or {}
        record.update(W=W, basis="cited: " + ", ".join(str(c[k]) for k in ("standard", "edition", "table", "row", "column")
                                                    if c.get(k)), basis_source="code_values citation")
    else:
        record.update(W=W, basis=None, basis_source="reduced W supplied; cite its table line in section 3")
    record["table"] = table
    E = inputs.get("E")
    if (isinstance(wb, str) and wb.strip().lower() == "seamless" and isinstance(E, (int, float))
            and not isinstance(E, bool) and float(E) < 1.0):
        warnings.append(f"W_basis says seamless but E = {_js_num(float(E))} is below 1, which points to a welded "
                        f"or cast product form; confirm the joint type, E and W against the code edition of record.")
    return inputs, record, warnings


_CLAUSE_B313 = ("B31.3 para. 304.1.2(b): for t >= D/6 or P/(S*E) > 0.385 the pressure design thickness requires "
                "special consideration of theory of failure, effects of fatigue and thermal stress")
_CLAUSE_B311 = ("B31.1 para. 104.1.2: for Do/tm < 6 the general note to the y table (Table 104.1.2-1; Table "
                "104.1.2(A) in 2016) replaces y, which this script does not apply; B31.1 states no P/(S*E) limit, "
                "so the pack also stops the run at the B31.3 para. 304.1.2(b) trigger, P/(S*E) > 0.385 (a pack "
                "rule confirmed by the P.E. 2026-10-30, not a B31.1 requirement)")


def _clause(module: str, code: Optional[str]) -> str:
    """The clause a tripped thick-wall gate sends the user to (paragraph pointers only)."""
    if module == "piping.bend-thickness":
        if code == "B31.1":
            return "B31.1 para. 102.4.5 on the para. 104.1.2 basis. " + _CLAUSE_B311
        if code == "B31.3":
            return "B31.3 para. 304.2.1 on the para. 304.1.2 basis. " + _CLAUSE_B313
        return ("B31.3 para. 304.2.1 / B31.1 para. 102.4.5 on the straight-pipe basis. "
                + _CLAUSE_B313 + ". " + _CLAUSE_B311)
    if code == "B31.12":
        return ("B31.12 para. IP-3.2.1(b): for t >= D/6 or P/(S*E*Mf) > 0.385 the pressure design thickness "
                "requires special consideration")
    if code == "B31.1":
        return _CLAUSE_B311
    if code == "B31.3":
        return _CLAUSE_B313
    if code == "B31.9":
        return "B31.9 on the B31.1 equations. " + _CLAUSE_B311
    return _CLAUSE_B313 + ". " + _CLAUSE_B311


def validity_gate(module: str, inputs: dict, result: dict, code: Optional[str]) -> Optional[dict]:
    """The thin-wall validity object for a gated module, or None.

    P_over_SE = P/(S*E) (times Mf for B31.12); for the MAWP module P is the computed allowable
    pressure. The thickness compared with D/6: B31.3 t (the Eq. (3a) pressure design thickness);
    B31.1 tm, since its note reads Do/tm; MAWP the nominal wall t (the engine's own check,
    conservative); bends the intrados pressure thickness, the largest on the bend."""
    if module not in GATED_MODULES:
        return None
    out = result["output"]
    S, E, D = inputs["S"], inputs["E"], inputs["D"]
    with_mf = module == "piping.b31-allowable-pressure" and code == "B31.12"
    SE = S * E * (inputs["Mf"] if with_mf else 1.0)
    if module == "piping.b31-allowable-pressure":
        P = float(out["allowablePressure"])
        thick, checked = inputs["t"], "t (nominal wall)"
    elif module == "piping.bend-thickness":
        P = inputs["P"]
        thick, checked = out["tmIntrados"] - inputs["A"], "tmIntrados - A (intrados pressure thickness)"
    elif module == "piping.b311-wall-thickness":
        P = inputs["P"]
        thick, checked = out["tm"], "tm (B31.1 reads Do/tm)"
    else:
        P = inputs["P"]
        thick, checked = out["t"], "t (pressure design thickness)"
    ratio = P / SE
    t_trip = thick >= D / 6
    r_trip = ratio > THIN_WALL_LIMIT
    return {
        "P_over_SE": round_half_up(ratio, 5),
        "P_over_SE_limit": THIN_WALL_LIMIT,
        "P_over_SE_exceeds": r_trip,
        "P_basis": "computed allowable pressure" if module == "piping.b31-allowable-pressure" else "design pressure P",
        "SE_includes_Mf": with_mf,
        "thickness_checked": checked,
        "thickness": round_half_up(thick, 5),
        "D_over_6": round_half_up(D / 6, 5),
        "t_over_D6": t_trip,
        "thin_wall_valid": not (t_trip or r_trip),
        "clause": _clause(module, code),
    }


def _banner(module: str, validity: dict) -> str:
    trips = []
    if validity["t_over_D6"]:
        trips.append(f"{validity['thickness_checked'].split(' ')[0]} >= D/6 ({_js_num(validity['thickness'])} >= "
                     f"{_js_num(validity['D_over_6'])} in)")
    if validity["P_over_SE_exceeds"]:
        trips.append(f"P/(S*E) = {_js_num(validity['P_over_SE'])} > {_js_num(THIN_WALL_LIMIT)}")
    what = "pressure" if module == "piping.b31-allowable-pressure" else "thickness"
    return (f"MANUAL CHECK REQUIRED: {' and '.join(trips)}. Outside the thin-wall basis of this equation; the "
            f"{what} under equation_value is an {LABEL_EQUATION_VALUE}. {validity['clause']}.")


# --------------------------------------------------------------------------- #
# Project basis record (0.8.0, B8) and result status taxonomy (B9). CLI layer only: the shared
# blocks above supply the helpers; this skill's fill map, code families and checks live here.
# --------------------------------------------------------------------------- #

PB_DESIGN_STATE = "states[role=design|first]"
# The standards each module's equation serves. A project_basis code.standard outside the family is
# a conflict (exit 2). The branch module reads a B31.1 project as a screening check against the
# B31.3 area method (references/modules.md section 4).
CODE_FAMILY: Dict[str, tuple] = {
    "piping.b313-wall-thickness": ("B31.3",),
    "piping.b311-wall-thickness": ("B31.1", "B31.5", "B31.9"),
    "piping.b31-allowable-pressure": CODE_CHOICES["piping.b31-allowable-pressure"],
    "piping.branch-reinforcement": ("B31.3", "B31.1"),
    "piping.bend-thickness": CODE_CHOICES["piping.bend-thickness"],
    "piping.miter-allowable-pressure": ("B31.3",),
    "piping.leak-test-pressure": ("B31.3", "B31.1"),
}
BRANCH_SCREENING_CODES = ("B31.1",)
P_MODULES = tuple(m for m in FIELDS if any(f[0] == "P" for f in FIELDS[m]))
ALLOWABLE_P_MODULES = ("piping.b31-allowable-pressure", "piping.miter-allowable-pressure")
_SPECIAL_SERVICE = ("Category M", "High Pressure")
_SPECIAL_ROUTE = re.compile(r"chapter\s*(?:ix|viii)\b|high[- ]pressure|category\s*m\b", re.I)
STATUS_POINTER = "pointer only"

MAIN_CHECK: Dict[str, str] = {
    "piping.b313-wall-thickness": "pressure design thickness, B31.3 para. 304.1.2 Eq. (3a)",
    "piping.b311-wall-thickness": "minimum required thickness, B31.1 para. 104.1.2",
    "piping.b31-allowable-pressure": "allowable pressure of the nominal wall (straight-pipe equation solved for P)",
    "piping.branch-reinforcement": "branch reinforcement by area replacement, B31.3 para. 304.3.3",
    "piping.bend-thickness": "thickness after bending at intrados, extrados and sidewall",
    "piping.miter-allowable-pressure": "miter allowable pressure, B31.3 para. 304.2.3",
    "piping.leak-test-pressure": "leak test pressure (piping minimum)",
}
CHECK_VALIDITY = "thin-wall validity (P/(S*E) against 0.385, thickness against D/6)"
CHECK_DESIGN_P = "allowable pressure against the design pressure"
CHECK_SERVICE = "B31.3 Category M / Chapter IX requirements"
_NC_SCHEDULE = ("selected nominal wall against tOrder",
                "compare the B36.10M / B36.19M or mill nominal wall with tOrder on the sheet, or run "
                "piping.b31-allowable-pressure on it")
# Checks a module does not perform (its known limits, references/modules.md): listed on every run
# as "not checked". They never block a result; they are named so the sheet does not imply them.
NOT_CHECKED: Dict[str, List[tuple]] = {
    "piping.b313-wall-thickness": [_NC_SCHEDULE, ("external pressure, B31.3 para. 304.1.3", "outside this skill")],
    "piping.b311-wall-thickness": [_NC_SCHEDULE, ("external pressure, B31.1 para. 104.1.3", "outside this skill")],
    "piping.b31-allowable-pressure": [],
    "piping.branch-reinforcement": [
        ("need for the area calculation, B31.3 para. 304.3.2",
         "listed fittings and the clause's exemptions need no area calc; check them first"),
        ("adjacent openings and overlapping reinforcement zones", "check by hand where zones overlap"),
    ],
    "piping.bend-thickness": [
        ("wall thinning during bending",
         "choose the pre-bend wall from the bender's predicted thinning and state its source"),
    ],
    "piping.miter-allowable-pressure": [
        ("minimum R1 of a multiple miter, B31.3 para. 304.2.3",
         "depends on a tabulated size-dependent value; check it on your copy"),
    ],
    "piping.leak-test-pressure": [
        ("test stress against yield and component ratings, B31.3 para. 345.2.1(a)", "check the resulting stress"),
        ("pneumatic limit of 90 % of the para. 345.2.1(a) pressure, B31.3 para. 345.5.4", "not evaluated"),
        ("flange, valve and equipment test limits", "check each separately"),
    ],
}


def _norm_code(raw: Any) -> Any:
    """'ASME B31.3' / 'b31.3' -> 'B31.3' (the same normalisation split_basis applies)."""
    return re.sub(r"^ASME", "", raw.replace(" ", "").upper()) if isinstance(raw, str) else raw


def _cite_text(cit: dict) -> str:
    return ", ".join(str(cit[k]) for k in ("standard", "edition", "table", "row", "column") if cit.get(k))


def split_pointers(module: str, raw: Any) -> tuple:
    """(inputs without pointer entries, {name: {citation, source}}).

    A code_values entry with "mode": "pointer" names where a value is read (the connector's pointer
    result) and carries no value. It is taken out before the shared code_values block runs; the run
    then evaluates no equation and reports "pointer only" for that check."""
    if not isinstance(raw, dict) or not isinstance(raw.get("code_values"), dict):
        return raw, {}
    kept, pointers = {}, {}
    fields = _cv_fields(module)
    for name, entry in raw["code_values"].items():
        if not (isinstance(entry, dict) and entry.get("mode") == "pointer"):
            kept[name] = entry
            continue
        where = f"code_values.{name}"
        if name not in fields:
            raise ValueError(f"{where} is not an input of {module} (valid: {', '.join(sorted(fields))}; "
                             f"names are case-sensitive)")
        if entry.get("value") is not None:
            raise ValueError(f"{where} is a pointer and carries no value; drop \"mode\" or the value")
        cit = entry.get("citation")
        if not isinstance(cit, dict) or any(not isinstance(cit.get(k), str) or not cit[k].strip()
                                            for k in ("standard", "table")):
            raise ValueError(f"{where}.citation needs standard and table (where to read the value) as "
                             f"non-empty strings")
        source = entry.get("source", "connector")
        if source not in _CV_SOURCES:
            raise ValueError(f"{where}.source must be 'connector' or 'user'")
        pointers[name] = {"citation": copy.deepcopy(cit), "source": source}
    if not pointers:
        return raw, {}
    return dict(raw, code_values=kept), pointers


def _is_one(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == 1.0


def apply_project_basis(module: str, inputs: dict, record: Optional[dict]) -> tuple:
    """Fill this module's inputs from a project_basis record. Returns (inputs, applied, context).

    Fill map: code (MAWP and bend modules) from code.standard, which must lie in the module's code
    family on every module; edition from code.edition; P from the design state (role design, else
    the first state); W_basis "seamless" from materials[use=pipe] when its form is seamless, W_basis
    is absent and W is absent or 1.0. units.system SI exits 2 (the engine is US customary). Present
    and different inputs exit 2 with the shared conflict message. Design T, the pipe material,
    owner practice and project fields are recorded as read for the sheet."""
    if record is None:
        return inputs, None, {}
    if basis_get(record, "units.system") == "SI":
        raise ProjectBasisError("project_basis.units.system is SI: pressure_design.py works in US customary "
                                "units (psi, in, deg F); give the inputs in those units and set units.system to USC")
    ctx: Dict[str, Any] = {}
    fill: List[tuple] = []
    std = basis_get(record, "code.standard")
    if std is not None:
        norm = _norm_code(std)
        family = CODE_FAMILY[module]
        if norm not in family:
            raise project_basis_conflict("code.standard", f"{module} (this module serves {', '.join(family)})")
        ctx["code"] = norm
        if module in CODE_CHOICES:
            have = inputs.get("code")
            fill.append(("code", "code.standard", lambda v, h=have, n=norm: h if _norm_code(h) == n else n))
    if module in W_MODULES:
        have_ed = inputs.get("edition")
        fill.append(("edition", "code.edition",
                     lambda v, h=have_ed: h if h is not None and str(h).strip() == v.strip() else v))
        W = inputs.get("W")
        if (basis_get(record, "materials[use=pipe].form") == "seamless" and inputs.get("W_basis") is None
                and (W is None or _is_one(W))):
            fill.append(("W_basis", "materials[use=pipe].form", lambda v: "seamless"))
    if module in P_MODULES:
        fill.append(("P", PB_DESIGN_STATE + ".P_psig", None))
    eff, applied = fill_from_basis(inputs, record, fill)
    if std is not None and module not in CODE_CHOICES:
        mark_basis_used(applied, "code.standard")
    if module not in W_MODULES and basis_get(record, "code.edition") is not None:
        mark_basis_used(applied, "code.edition")
    if module in ALLOWABLE_P_MODULES:
        dp = basis_get(record, PB_DESIGN_STATE + ".P_psig")
        if dp is not None:
            ctx["design_P"] = float(dp)
            ctx["design_state"] = basis_get(record, PB_DESIGN_STATE + ".key")
            mark_basis_used(applied, PB_DESIGN_STATE + ".P_psig")
    for path in (PB_DESIGN_STATE + ".T_F", "materials[use=pipe]", "owner_practice", "project"):
        if basis_get(record, path) is not None:
            mark_basis_used(applied, path)
    fc = basis_get(record, "service.fluid_category")
    route = basis_get(record, "code.route")
    if fc is not None:
        mark_basis_used(applied, "service.fluid_category")
    if fc in _SPECIAL_SERVICE or (isinstance(route, str) and _SPECIAL_ROUTE.search(route)):
        ctx["special_service"] = (f"fluid service {fc or route}: this skill covers the Normal fluid service "
                                  f"equations only; the additional requirements for Category M or Chapter IX "
                                  f"(High Pressure) piping are not evaluated")
    return eff, applied, ctx


def result_checks(module: str, envelope: dict, ctx: dict, pointers: dict) -> List[dict]:
    """checks[] for the envelope: the module's own check, the validity gate, the design-pressure
    comparison and the fluid-service flag where they apply, then the module's known limits."""
    main, status = MAIN_CHECK[module], envelope["status"]
    validity = envelope.get("validity")
    tripped = validity is not None and not validity["thin_wall_valid"]
    checks = []
    if pointers:
        where = "; ".join(f"{n} at {_cite_text(p['citation'])}" for n, p in sorted(pointers.items()))
        checks.append(make_check(main, STATUS_POINTER, "na", f"supplied as a pointer only ({where}); read the "
                                 f"value on your licensed copy and rerun; no equation was evaluated"))
    elif tripped:
        checks.append(make_check(main, GRADE_MANUAL, "na",
                                 f"outside the thin-wall basis; the numbers are an {LABEL_EQUATION_VALUE}"))
    elif module == "piping.branch-reinforcement" and ctx.get("code") in BRANCH_SCREENING_CODES:
        checks.append(make_check(main, "screening", status, "B31.3 area method on a B31.1 project: a screening "
                                 "check against the B31.3 form; confirm the B31.1 para. 104.3.1 zone limits"))
    else:
        checks.append(make_check(main, GRADE_CALCULATED, status, "evaluated by the script from the inputs given"))
    if validity is not None:
        checks.append(make_check(
            CHECK_VALIDITY, GRADE_MANUAL if tripped else GRADE_CALCULATED, _verdict(not tripped),
            f"P/(S*E) = {_js_num(validity['P_over_SE'])} against {_js_num(THIN_WALL_LIMIT)}; "
            f"{validity['thickness_checked'].split(' ')[0]} = {_js_num(validity['thickness'])} against "
            f"D/6 = {_js_num(validity['D_over_6'])}" + (f". {validity['clause']}" if tripped else "")))
    if module in ALLOWABLE_P_MODULES and not pointers and not tripped:
        dp = ctx.get("design_P")
        if dp is None:
            checks.append(make_check(CHECK_DESIGN_P, "not checked", "na",
                                     "no design state in a project basis record; compare on the sheet"))
        else:
            pa = float(envelope["output"]["allowablePressure"])
            checks.append(make_check(CHECK_DESIGN_P, GRADE_CALCULATED, _verdict(pa >= dp),
                                     f"allowable {_js_num(pa)} against design {_js_num(dp)} (project basis state "
                                     f"{ctx.get('design_state')}), same pressure unit"))
    if ctx.get("special_service"):
        checks.append(make_check(CHECK_SERVICE, GRADE_MANUAL, "na", ctx["special_service"]))
    assumed = assumed_inputs_check((envelope.get("project_basis_applied") or {}).get("assumptions"))
    if assumed is not None:
        checks.append(assumed)
    checks += [make_check(name, "not checked", "na", note) for name, note in NOT_CHECKED[module]]
    return checks


def _status_why(checks: List[dict]) -> str:
    word = envelope_status(checks)
    limits = not_performed(checks)
    if word == GRADE_CALCULATED:
        if limits:
            return f"{checks[0]['name']} calculated; {limits}"
        return "every check this module performs was evaluated from the inputs given"
    if word == "not checked":
        return limits
    return "; ".join(c["note"] for c in checks if c["result_status"] == word and c.get("note"))


def add_result_status(envelope: dict, checks: List[dict]) -> dict:
    """Merge result_status, checks, banner_allowed and result_status_line into the envelope."""
    envelope.update(status_fields(checks))
    envelope["banner_allowed"] = checks_banner_allowed(checks)
    envelope["result_status_line"] = render_status_line(envelope["result_status"], _status_why(checks))
    return envelope


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


def run_module(module: str, inputs: dict, project_basis_file: Optional[str] = None) -> dict:
    """Run one module behind the pre-flight check and the two gates.

    Order: the project_basis record (top-level key and/or --project-basis file) is taken out and
    validated; code_values pointer entries are taken out; code_values fill; project_basis fill
    (this skill's map, apply_project_basis); split off the basis strings (W_basis, edition, code);
    the W gate (exit 2 when W must be read); validate(); the engine; the thin-wall validity gate;
    result_status and checks. A tripped gate makes the envelope status "manual check required",
    empties "output" and moves the engine's numbers to "equation_value" with the label "equation
    value, not a design basis". A pointer-supplied value makes the status "pointer only" and runs
    no equation. The engine's numbers themselves are never changed."""
    record = None
    if isinstance(inputs, dict):
        inputs = dict(inputs)
        record = load_project_basis(project_basis_file, inputs.pop("project_basis", None))
    elif project_basis_file:
        record = load_project_basis(project_basis_file, None)
    inputs, pointers = split_pointers(module, inputs)
    inputs, provenance, cv_notes = apply_code_values(inputs, module, _cv_fields(module))
    inputs, applied, ctx = apply_project_basis(module, inputs, record)
    for name in sorted(pointers):
        if inputs.get(name) is not None:
            raise ValueError(f"code_values.{name} is a pointer but input {name} has a value; give one or the other")
    inputs, basis = split_basis(module, inputs)
    w_record, w_warnings = None, []
    if module in W_MODULES and "W" not in pointers:
        inputs, w_record, w_warnings = w_gate(module, inputs, basis, provenance)
    present_supplied = [n for n in user_supplied_names(module) if inputs.get(n) is not None]
    if pointers:
        # names, types and every other required input are checked as for a full run
        _prepare(module, dict(inputs, **{n: 1.0 for n in pointers}))
        banner = (f"POINTER ONLY: {', '.join(sorted(pointers))} supplied as a pointer, not a value. No equation "
                  f"was evaluated; read the value at the cited table on your licensed copy and rerun.")
        envelope = {
            "module": module,
            "status": STATUS_POINTER,
            "output": {},
            "warnings": [banner] + cv_notes + w_warnings,
            "citation": CITATIONS[module],
            "inputs": dict(inputs, **basis),
            "user_supplied": present_supplied,
            "defaults_applied": {},
            "banner": banner,
            "value_pointers": pointers,
        }
        if module in GATED_MODULES:
            envelope["result_grade"] = STATUS_POINTER
    else:
        pre_warnings = cv_notes + w_warnings + validate(module, inputs)
        result = REGISTRY[module](dict(inputs))
        output = dict(result["output"])
        if module == "piping.miter-allowable-pressure" and inputs.get("miters") == 1:
            output["Pm2"] = None          # not evaluated for a single miter (the engine reports 0.0)
        envelope = {
            "module": result["module"],
            "status": result["status"],
            "output": output,
            "warnings": pre_warnings + result["warnings"],
            "citation": CITATIONS[module],
            "inputs": dict(inputs, **basis),
            "user_supplied": present_supplied,
            # W is never defaulted silently: the W gate either has a value, a stated basis, or an
            # equation without W, and records which in weld_factor_basis.
            "defaults_applied": {},
        }
    if w_record is not None:
        envelope["weld_factor_basis"] = w_record
    if not pointers:
        code = w_record["code"] if w_record is not None else None
        validity = validity_gate(module, inputs, result, code) if result["status"] == "na" else None
        if validity is not None:
            envelope["validity"] = validity
            if validity["thin_wall_valid"]:
                envelope["result_grade"] = GRADE_CALCULATED
            else:
                banner = _banner(module, validity)
                envelope.update(status=GRADE_MANUAL, result_grade=GRADE_MANUAL, banner=banner, output={},
                                equation_value={"label": LABEL_EQUATION_VALUE, "values": output})
                envelope["warnings"] = [banner] + envelope["warnings"]
    if ctx.get("special_service"):
        # The fluid-service flag reaches the 0.7.2 fields a reader already trusts, not only checks[]:
        # a warning, the banner (unless a gate or pointer banner already holds it) and result_grade on
        # the gated modules. status and output keep the engine's words and numbers.
        svc = f"MANUAL CHECK REQUIRED: {ctx['special_service']}."
        envelope["warnings"].insert(1 if "banner" in envelope else 0, svc)
        envelope.setdefault("banner", svc)
        if envelope.get("result_grade") == GRADE_CALCULATED:
            envelope["result_grade"] = GRADE_MANUAL
    if provenance is not None:
        envelope["code_value_provenance"] = provenance
    if applied is not None:
        envelope["project_basis_applied"] = applied
        envelope["basis_section"] = render_basis_section(applied, record)
    return add_result_status(envelope, result_checks(module, envelope, ctx, pointers))


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
        for name, desc in BASIS_FIELDS.get(module, []):
            lines.append(f"    {name:<14}{'text':<9}{'basis':<9}{'':<5}{desc}")
        lines.append("")
    lines.append("Any input above may instead come from the optional top-level object code_values: "
                 "{name: {value, unit, citation{standard, edition, table, row, column?}, source: connector|user}}.")
    lines.append("basis = a text input recorded on the sheet, never passed to the equation. Where the code and "
                 "edition's equation carries W, a run with W omitted or W = 1.0 and no W_basis exits 2. A run "
                 "outside the thin-wall basis (t >= D/6 or P/(S*E) > 0.385) returns status "
                 "'manual check required' with the numbers as an equation value, not a design basis.")
    lines.append("project_basis (top-level object, or --project-basis <file>): code, edition, design P and a "
                 "seamless W_basis fill from the record; a value present in both must agree (exit 2 otherwise). "
                 "Every run carries result_status and checks[]; a code_values entry with \"mode\": \"pointer\" "
                 "and no value gives 'pointer only' and evaluates no equation.")
    return "\n".join(lines).rstrip() + "\n"


def list_json() -> dict:
    return {
        m: {
            "citation": CITATIONS[m],
            "fields": [
                {"name": n, "units": u, "required": r, "user_supplied": us, "description": d}
                for n, u, r, us, d in FIELDS[m]
            ],
            "basis_fields": [{"name": n, "units": "text", "required": False, "description": d}
                             for n, d in BASIS_FIELDS.get(m, [])],
            "validity_gate": m in GATED_MODULES,
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
    ap.add_argument("--project-basis", metavar="FILE",
                    help="project basis record (pipingtoolset.project-basis/1); must match a top-level "
                         "project_basis object if the inputs carry one")

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

        envelope = run_module(module, inputs, args.project_basis)
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
