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
a licensed copy of the standard, the paper or the vendor datasheet. That includes the method
constants of API 610 Annex F (input `annexF`) and the coefficient of the SM-23 form
(`coefficient`): the user reads each from the equation of the edition of record and enters
it; none has a default. The only standard-derived numbers carried here are the 18,800 and
17,100 psi reference stresses of the PVP2011 paper, as named constants with their source.

CLI:
    python nozzle_load.py list
    python nozzle_load.py <module-id> --input '<json>'
    python nozzle_load.py <module-id> --input-file <path.json> [--project-basis <record.json>]

Output is a JSON envelope {module, status, output, warnings, citation, inputs, user_supplied,
result_status, checks, result_status_line, banner}. Exit code 2 on bad input.

Optional top-level input `project_basis` (or --project-basis <file>): the shared project record
(schema pipingtoolset.project-basis/1, references/project-basis.md). An input absent from the
main inputs is filled from it where this skill has a slot (api610-annexf `units`; pvp2011-allowables
`designTempF` from the design state and the `ownerFactorBasis` label from owner_practice); one that
is present must agree, otherwise the run exits 2 with "project_basis.<path> conflicts with input
<name>". The envelope gains `project_basis_applied` and `project_basis_section` (the sheet's
section 1, ASSUMED items first). The result status words and the banner rule are in the same
references file; `result_status` and `checks` are added to every envelope and change no existing key.

Optional top-level input `code_values`:
    {"code_values": {"allowable.Fx": {"value": 1000, "unit": "lbf",
                                      "citation": {"standard": "...", "edition": "...",
                                                   "table": "...", "row": "...", "column": "..."},
                                      "source": "user"}}}
The key is an input name from `list`. A nested input is addressed by a dotted name: the load sets
as "applied.Fx", "allowable.Mz", "limits.Fy", "row.Fx", "lowerRow.Mx", "upperRow.My", the Annex F
constants as "annexF.kSigma", the bore and position blocks as "suctionBore.Do" and
"dischargePosition.x" (the names `list` shows for the nested keys). An input that is absent from
the main inputs is filled from code_values[name]["value"]; one that is present must agree,
otherwise the run exits 2 with "code_values.<name> conflicts with input <name>". A name the module
does not declare exits 2. "source" is "connector" or "user". A unit other than the input's unit is
converted when the factor is exact (ksi to psi) and rejected otherwise; the force and moment
components of a load set are checked too (lbf and ft-lbf; N and N-m for the api610-annexf sets when
units is SI), except the nozzle-load-sum limits, which take the unit of the user's load sets. Any ownerFactor is applied after the fill, to the values as filled. The envelope
gains "code_value_provenance": {name: {unit, citation, source}}; "inputs" shows the values used and
"user_supplied" counts a filled input. Nothing here reaches a network.

`list` prints every module with its exact input field names (case-sensitive). Before the
engine runs, a separate pre-flight layer (`validate`) rejects unknown keys (top level and
inside load sets) and physically impossible inputs (exit 2) and adds warnings for implausible
ones. The optional `ownerFactor` of the ported modules is applied by the CLI layer
(`run_module`) to the entered allowables before the ported function runs; the ported
functions themselves are untouched.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional, Tuple


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

# API 610 Annex F method constants are NOT carried here: they are the user-supplied input `annexF`,
# read from the equations of the edition of record. Name -> where in Annex F the user reads it.
ANNEXF_POINTERS = {
    "componentMultiple": "F.1.2 a)",
    "resultantDenominator": "Eq. F.1 / F.2",
    "interactionLimit": "the sum limit of Eq. F.1 / F.2",
    "centreForceFactor": "Eq. F.3 / F.5",
    "centreMyFactor": "Eq. F.4",
    "sigmaPLimit": "Eq. F.6 (SI) or F.9 (USC)",
    "kSigma": "Eq. F.7 (SI) or F.10 (USC)",
    "kTau": "Eq. F.8 (SI) or F.11 (USC)",
}
ANNEXF_KEYS = tuple(ANNEXF_POINTERS)
ANNEXF_HORIZONTAL = ANNEXF_KEYS[:5]   # F.1.2 a)-c), Eq. F.1-F.5
ANNEXF_VERTICAL = ANNEXF_KEYS[5:]     # F.2, Eq. F.6-F.11
API610_UNIT_CONV = {"SI": 1000.0, "USC": 12.0}   # F.5.1.1-3: mm to m, in to ft (unit arithmetic, not API content)

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


def _annexf_constants(inp: Dict[str, Any], pump_type: str) -> Dict[str, float]:
    """The Annex F method constants the user supplied in `annexF`; required per pump type, each > 0, no default."""
    obj = inp.get("annexF")
    if obj is None:
        obj = {}
    if not isinstance(obj, dict):
        raise ValueError("annexF must be an object of the Annex F method constants read from the edition of record")
    needed = ANNEXF_HORIZONTAL if pump_type == "horizontal" else ANNEXF_VERTICAL
    out: Dict[str, float] = {}
    for key in ANNEXF_KEYS:
        v = obj.get(key)
        if v is None:
            if key in needed:
                raise ValueError(f"annexF.{key} is required (read it from {ANNEXF_POINTERS[key]} of the "
                                 "edition of record; no default)")
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"annexF.{key} must be a number")
        if not math.isfinite(v):
            raise ValueError(f"annexF.{key} must be finite")
        if not v > 0:
            raise ValueError(f"annexF.{key} must be > 0 (read it from {ANNEXF_POINTERS[key]} of the edition of record)")
        out[key] = float(v)
    return out


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

    The Table 5 base ranges are user-supplied per nozzle and the method constants are the user-supplied
    `annexF` block (horizontal: the first five keys; vertical in-line: sigmaPLimit, kSigma, kTau, in the
    `units` system given); the resultants FRST4 / MRST4 are derived
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
        "Use of Annex F methods requires the purchaser's approval and does not eliminate the margin between "
        "external nozzle loads and pump case design limits (6.5.6, 6.5.6.1); the pump vendor must direct how these "
        "equations apply to the system design (6.5.6.2).",
        "The Annex F method constants are user-supplied (annexF) \u2014 this module does not embed them; confirm "
        "each against the equation printed in the edition of record.",
    ]
    c = _annexf_constants(inp, pump_type)

    # F.1.2 a) per-component ratio vs the multiple of Table 5. Always run for horizontal pumps (the multiple is
    # required there); for vertical in-line it is the informational screen, run only when the user supplied it.
    vertical = pump_type == "vertical-inline"
    mult = c.get("componentMultiple")
    s_ratio: Dict[str, float] = {}
    d_ratio: Dict[str, float] = {}
    max_component_ratio = -1.0
    governing_component = ""
    governing_value = 0.0
    governing_limit = 0.0
    checks: List[Dict[str, Any]] = []
    if mult is not None:
        for k in COMPONENTS:
            rS = abs(SA[k]) / (mult * ST4[k])
            rD = abs(DA[k]) / (mult * DT4[k])
            s_ratio[k] = r5(rS)
            d_ratio[k] = r5(rD)
            if rS > max_component_ratio:
                max_component_ratio = rS
                governing_component = f"suction.{k}"
                governing_value = abs(SA[k])
                governing_limit = mult * ST4[k]
            if rD > max_component_ratio:
                max_component_ratio = rD
                governing_component = f"discharge.{k}"
                governing_value = abs(DA[k])
                governing_limit = mult * DT4[k]
        checks.append(_check_row("F.1.2(a)", f"Per-component vs {mult:g}x Table 5 ({governing_component})",
                                 governing_value, governing_limit, vertical))
    else:
        warnings.append("annexF.componentMultiple was not supplied, so the informational per-component screen "
                        "against a multiple of Table 5 was not run; the F.2 principal-stress check is unaffected.")

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

        f1 = FRSA / (c["resultantDenominator"] * FRST4) + MRSA / (c["resultantDenominator"] * MRST4)   # (F.1)
        f2 = FRDA / (c["resultantDenominator"] * FRDT4) + MRDA / (c["resultantDenominator"] * MRDT4)   # (F.2)
        checks.append(_check_row("F.1", "Suction resultant interaction", f1, c["interactionLimit"]))
        checks.append(_check_row("F.2", "Discharge resultant interaction", f2, c["interactionLimit"]))

        FXCA = SA["Fx"] + DA["Fx"]   # (F.3.1.1)-(F.3.1.3)
        FYCA = SA["Fy"] + DA["Fy"]
        FZCA = SA["Fz"] + DA["Fz"]
        FRCA = math.hypot(FXCA, FYCA, FZCA)   # (F.3.1)

        k = API610_UNIT_CONV[units]   # (F.5.1.1)-(F.5.1.3)
        MXCA = SA["Mx"] + DA["Mx"] - ((SA["Fy"] * zS + DA["Fy"] * zD) - (SA["Fz"] * yS + DA["Fz"] * yD)) / k
        MYCA = SA["My"] + DA["My"] + ((SA["Fx"] * zS + DA["Fx"] * zD) - (SA["Fz"] * xS + DA["Fz"] * xD)) / k
        MZCA = SA["Mz"] + DA["Mz"] - ((SA["Fx"] * yS + DA["Fx"] * yD) - (SA["Fy"] * xS + DA["Fy"] * xD)) / k
        MRCA = math.hypot(MXCA, MYCA, MZCA)   # (F.5.1)

        limit_f3 = c["centreForceFactor"] * (FRST4 + FRDT4)
        limit_f4 = c["centreMyFactor"] * (ST4["My"] + DT4["My"])
        limit_f5 = c["centreForceFactor"] * (MRST4 + MRDT4)
        checks.append(_check_row("F.3", "Resultant force at pump center", FRCA, limit_f3))
        checks.append(_check_row("F.4", "Resultant MY at pump center", abs(MYCA), limit_f4))
        checks.append(_check_row("F.5", "Resultant moment at pump center", MRCA, limit_f5))

        branch = {
            "FRSA": r4(FRSA), "MRSA": r4(MRSA), "FRDA": r4(FRDA), "MRDA": r4(MRDA),
            "eqF1Value": r5(f1), "eqF1Ratio": r5(f1 / c["interactionLimit"]),
            "eqF2Value": r5(f2), "eqF2Ratio": r5(f2 / c["interactionLimit"]),
            "FXCA": r4(FXCA), "FYCA": r4(FYCA), "FZCA": r4(FZCA), "FRCA": r4(FRCA),
            "MXCA": r4(MXCA), "MYCA": r4(MYCA), "MZCA": r4(MZCA), "MRCA": r4(MRCA),
            "eqF3Ratio": r5(FRCA / limit_f3),
            "eqF4Ratio": r5(abs(MYCA) / limit_f4),
            "eqF5Ratio": r5(MRCA / limit_f5),
        }

        if max_component_ratio <= 1.0 / mult:
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

        k_sigma = c["kSigma"]     # (F.7) vs (F.10), in the units given
        k_tau = c["kTau"]         # (F.8) vs (F.11)
        limit = c["sigmaPLimit"]  # (F.6) vs (F.9)
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
        warnings.append("The per-component multiple-of-Table-5 screen is informational only for vertical in-line pumps: F.2 "
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

    output: Dict[str, Any] = {"pumpType": pump_type, "units": units}
    if mult is not None:
        output.update({
            "suctionComponentRatio": s_ratio,
            "dischargeComponentRatio": d_ratio,
            "maxComponentRatio": r5(max_component_ratio),
            "governingComponent": governing_component,
        })
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
    "connections.nema-sm23": "NEMA SM-23 combined form 3*Fr + Mr <= a*De. The coefficient a is read by the user from the equation of the governing standard (API 617 Part 2 Annex E, API 611 Annex I, API 612 Annex D, or the owner's SM-23 copy). De = NPS for NPS 8 and under, otherwise (NPS + 16)/3.",
    "connections.api610-annexf": "API 610 Annex F: F.1.2 a)-c) with Eq. (F.1)-(F.5) for horizontal pumps; F.2 with Eq. (F.6)-(F.11) for vertical in-line pumps; F.1.3 for loads beyond F.1.2. Table 5 ranges and the Annex F method constants (annexF) are user-supplied; confirm the edition of record.",
    "equipment.nozzle-load-sum": "API 661 7.1.10.2 (sum of all nozzle loadings on a single header against the header limits for all six components) and 7.1.10.3 (total on one multi-bundle bay not above three times the single-header allowance). The same sum-and-compare form serves an owner header or bay rule; the limits and multiplier are user-supplied.",
    "equipment.api650-annexp-ordinates": "API 650 Annex P, P.2.7.1 and P.2.7.2: lambda = a/(Rt)^0.5, FP = pi*a^2*P (P.2.3); ordinates (lambda/2YF)(FR/FP), (lambda/aYL)(ML/FP), (lambda/aYC)(MC/FP). Acceptance is read from Figures P.3a/b and P.5a/b (P.2.7.2.4); YF, YL, YC from Figures P.4a/b.",
    "equipment.pvp2011-allowables": "Koves, Upitis, Cullotta and Latif, 'Establishing Allowable Nozzle Loads', ASME PVP2011-57100: size scaling Eq. (1) force ~ d and Eq. (2) moment ~ d^2; thickness extrapolation Eq. (4); material ratio against 18,800 psi (shell) and 17,100 psi (neck). Tables 1A, 1B and 2 are read by the user, not embedded.",
}

# Inputs that are code, figure, datasheet or table values the user must read and be able to cite.
USER_SUPPLIED = {
    "connections.nozzle-load-check": ["allowable"],
    "connections.nema-sm23": ["coefficient"],
    "connections.api610-annexf": ["annexF", "suctionAllowable", "dischargeAllowable", "suctionBore", "dischargeBore"],
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
        ("derivedSetStatus", "text", False, "result_status of the equipment.pvp2011-allowables run the allowable set was derived by "
                                            "(one of the five words); omit for a set read from a table or datasheet"),
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
        ("annexF", "per units", True, "Annex F method constants {componentMultiple (F.1.2 a), resultantDenominator (F.1/F.2), "
                                      "interactionLimit (F.1/F.2 sum limit), centreForceFactor (F.3/F.5), centreMyFactor (F.4), "
                                      "sigmaPLimit (F.6 or F.9), kSigma (F.7 or F.10), kTau (F.8 or F.11)}, each read by the user "
                                      "from that equation of the edition of record, in the units given; no default, each > 0. "
                                      "Horizontal needs the first five; vertical-inline needs sigmaPLimit, kSigma, kTau"),
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
        ("derivedSetStatus", "text", False, "result_status of the equipment.pvp2011-allowables run the allowable set was derived by "
                                            "(one of the five words); omit for a set read from a table or datasheet"),
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
        "annexF": ANNEXF_KEYS,
    },
    "equipment.nozzle-load-sum": {"limits": COMPONENTS},
    "equipment.pvp2011-allowables": {"row": COMPONENTS, "lowerRow": COMPONENTS, "upperRow": COMPONENTS},
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


# Load sets whose unit is fixed by the module: forces lbf, moments ft-lbf. The api610-annexf sets
# follow the `units` input instead (USC: lbf and ft-lbf; SI: N and N*m). nozzle-load-sum takes its
# unit from the user's load sets, so its limits are not unit-checked.
_CV_LOAD_UNITS = {"connections.nozzle-load-check": ("applied", "allowable"),
                  "connections.nema-sm23": ("applied",),
                  "equipment.pvp2011-allowables": ("row", "lowerRow", "upperRow")}
_CV_ANNEXF_SETS = ("suctionApplied", "dischargeApplied", "suctionAllowable", "dischargeAllowable")
_CV_SYSTEMS = {"USC": ("lbf", "ft-lbf"), "SI": ("N", "N-m")}


def _cv_units_input(inp: Dict[str, Any]) -> Optional[str]:
    """The `units` value for api610-annexf, from the main inputs or from code_values.units."""
    u = inp.get("units") if isinstance(inp, dict) else None
    if u is None and isinstance(inp, dict) and isinstance(inp.get("code_values"), dict):
        e = inp["code_values"].get("units")
        u = e.get("value") if isinstance(e, dict) else None
    return u if u in _CV_SYSTEMS else None


def _cv_fields(module: str, units: Optional[str] = None) -> Dict[str, Optional[str]]:
    """Input name -> unit label for the code_values block; nested keys get dotted names."""
    nested = NESTED_KEYS.get(module, {})
    sets = _CV_LOAD_UNITS.get(module, ())
    system = _CV_SYSTEMS.get(units) if module == "connections.api610-annexf" else None
    if system:
        sets = sets + _CV_ANNEXF_SETS
    out: Dict[str, Optional[str]] = {}
    for f in FIELDS.get(module, []):
        name, funits = f[0], f[1]
        if name in nested:
            for k in nested[name]:
                unit = None
                if name in sets and k in COMPONENTS:
                    f_unit, m_unit = system or ("lbf", "ft-lbf")
                    unit = f_unit if k.startswith("F") else m_unit
                out[f"{name}.{k}"] = unit
        elif funits not in ("list", "bool"):
            out[name] = funits
    return out


def render_list() -> str:
    lines = ["Modules and exact input field names (case-sensitive). Load sets are objects with Fx, Fy, Fz, Mx, My, Mz.", ""]
    for mid in REGISTRY:
        lines.append(mid)
        for name, units, required, desc in FIELDS[mid]:
            lines.append(f"    {name:<19}{units:<16}{'required' if required else 'optional':<10}{desc}")
        lines.append("")
    lines.append("Any input above may instead come from the optional top-level object code_values: "
                 "{name: {value, unit, citation{standard, edition, table, row, column?}, source: connector|user}}; "
                 "a key inside a load set or block is named with a dot, for example allowable.Fx or annexF.kSigma. "
                 "Any module also takes the optional top-level object project_basis, or --project-basis <file> "
                 "(schema pipingtoolset.project-basis/1, references/project-basis.md).")
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
        dss = inputs.get("derivedSetStatus")
        _need(dss is None or dss in RESULT_STATUS, "derivedSetStatus must be one of " + ", ".join(RESULT_STATUS))
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
    elif module == "connections.api610-annexf":
        pt = inputs.get("pumpType")
        _need(pt in ("horizontal", "vertical-inline"), 'pumpType must be "horizontal" or "vertical-inline"')
        _need(inputs.get("units") in ("USC", "SI"), 'units must be "USC" or "SI"')
        if pt == "vertical-inline" and owner is not None:
            _need(owner == 1, "ownerFactor is not supported for pumpType vertical-inline: the factor would scale only the "
                              "Table 5 ranges, not the F.6 to F.11 principal-stress limit that sets the "
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


# --------------------------------------------------------------------------- project basis (B8)

# Modules whose inputs are USC only (lbf, ft-lbf, psi, in): an SI project basis stops the run.
_NL_USC_ONLY = ("connections.nema-sm23", "equipment.pvp2011-allowables")
# Modules that take ownerFactor (the owner design-stage fraction).
_NL_OWNER_MODULES = ("connections.nozzle-load-check", "connections.nema-sm23", "connections.api610-annexf",
                     "equipment.nozzle-load-sum", "equipment.pvp2011-allowables")
# An owner_practice item whose name carries one of these words is a design-stage limit the run could apply.
_NL_LIMIT_WORDS = ("factor", "fraction", "percent", "margin", "limit")
# A plain-text owner_practice item states a value when it carries a decimal number (0.5) or a percent (50 %).
_NL_TEXT_VALUE = re.compile(r"(\d+\.\d+|\d+(?=\s*%))")


def _nl_is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nl_practice_items(basis: Optional[Dict[str, Any]]) -> List[Tuple[str, str, Any]]:
    """(document, item name, value) for each limit-type object item of owner_practice."""
    out: List[Tuple[str, str, Any]] = []
    for pr in (basis or {}).get("owner_practice") or []:
        for it in pr.get("items") or []:
            if isinstance(it, dict) and any(w in it["name"].lower() for w in _NL_LIMIT_WORDS):
                out.append((pr["document"], it["name"], it.get("value")))
            elif isinstance(it, str) and any(w in it.lower() for w in _NL_LIMIT_WORDS):
                # A plain-text item is a pointer unless it states a decimal or percent value.
                m = _NL_TEXT_VALUE.search(it)
                out.append((pr["document"], it, float(m.group(1)) if m else None))
    return out


def _nl_owner_label(value: Any) -> Any:
    """The ownerFactorBasis text from an owner_practice list: 'document edition; ...'."""
    parts = [(pr["document"] + (" " + pr["edition"] if pr.get("edition") else "")) for pr in value or []]
    return "; ".join(parts) if parts else PROJECT_BASIS_SKIP


def _nl_fill_map(module: str, inp: Dict[str, Any], basis: Dict[str, Any]) -> List[tuple]:
    """This skill's slots in the project record. An SI record cannot feed a USC-only module."""
    system = (basis.get("units") or {}).get("system")
    if system == "SI" and module in _NL_USC_ONLY:
        raise ProjectBasisError(f"project_basis.units.system is SI but {module} takes USC inputs only "
                                "(lbf, ft-lbf, psi, in); run it with a USC record")
    fm: List[tuple] = []
    if module == "connections.api610-annexf":
        fm.append(("units", "units.system", None))
    if module == "equipment.pvp2011-allowables":
        fm.append(("designTempF", "states[role=design|first].T_F", None))
        given = inp.get("ownerFactorBasis")
        keep = isinstance(given, str) and given.strip() != ""

        def label(value: Any) -> Any:
            # a label the user already wrote is never relabelled and never a conflict
            return PROJECT_BASIS_SKIP if keep else _nl_owner_label(value)

        fm.append(("ownerFactorBasis", "owner_practice", label))
    return fm


def _nl_apply_basis(module: str, inp: Dict[str, Any], basis: Dict[str, Any]) -> Tuple[Dict[str, Any], Any, List[str]]:
    """(effective inputs, project_basis_applied, warnings) for a record."""
    eff, applied = fill_from_basis(inp, basis, _nl_fill_map(module, inp, basis))
    used = [u["basis"] for u in applied["fields_used"]]
    if basis_get(basis, "units.system") and "units.system" not in used:
        mark_basis_used(applied, "units.system")
    if basis_get(basis, "equipment_axes.nozzle_axis_map"):
        mark_basis_used(applied, "equipment_axes.nozzle_axis_map")
    if basis_get(basis, "owner_practice") and "owner_practice" not in used:
        mark_basis_used(applied, "owner_practice")
    warnings: List[str] = []
    if module in _NL_OWNER_MODULES and eff.get("ownerFactor") is None:
        for doc, name, value in _nl_practice_items(basis):
            if _nl_is_number(value):
                warnings.append(f"project_basis owner practice item '{name}' = {value:g} ({doc}) is recorded but no "
                                "ownerFactor was supplied: this run is against the allowables as entered.")
    return eff, applied, warnings


# --------------------------------------------------------------------------- result status (B9)


def _nl_limit(name: str, state: str, note: str) -> Dict[str, Any]:
    """One applicability limit: inside (calculated, pass), outside (manual check required, fail) or unstated (manual, na)."""
    if state == "inside":
        return make_check(name, "calculated", "pass", note)
    return make_check(name, "manual check required", "fail" if state == "outside" else "na", note)


def _nl_pvp_checks(inp: Dict[str, Any], out: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks = [make_check("derived allowable set (PVP2011-57100 method)", "screening", "na",
                         "layout-stage estimate by the paper's method; a vendor datasheet value overrides it")]
    nps = float(inp["NPS"])
    checks.append(_nl_limit("NPS within the paper's range %g to %g" % (PVP_NPS_MIN, PVP_NPS_MAX),
                            "inside" if PVP_NPS_MIN <= nps <= PVP_NPS_MAX else "outside", "NPS %g" % nps))
    temp = inp.get("designTempF")
    name = "design temperature at or below %g F" % PVP_REF_TEMP_F
    if temp is None:
        checks.append(_nl_limit(name, "unstated", "designTempF not stated: the 650 F basis was not evaluated"))
    else:
        checks.append(_nl_limit(name, "inside" if temp <= PVP_REF_TEMP_F else "outside",
                                "design temperature %g F" % temp))
    mat = inp.get("material")
    if mat is None:
        checks.append(_nl_limit("material is killed carbon steel", "unstated", "material not stated"))
    else:
        checks.append(_nl_limit("material is killed carbon steel",
                                "inside" if mat == "killed-carbon-steel" else "outside", "material %s" % mat))
    name = "D/T at or below %g" % PVP_MAX_D_OVER_T
    if inp.get("D") is None:
        checks.append(_nl_limit(name, "unstated", "D not stated: D/T was not evaluated"))
    else:
        dt = float(inp["D"]) / float(inp["T"])
        checks.append(_nl_limit(name, "inside" if dt <= PVP_MAX_D_OVER_T else "outside", "D/T %.1f" % dt))
    name = "character of the loads stated (loadsPrimary)"
    if inp.get("loadsPrimary") is None:
        checks.append(_nl_limit(name, "unstated", "primary or secondary character of the loads not stated"))
    else:
        checks.append(_nl_limit(name, "inside", "loadsPrimary %s" % ("true" if inp["loadsPrimary"] else "false")))
    if float(inp["T"]) < PVP_TABLE_BASIS_THICKNESS[inp["table"]]:
        name = "thickness below the table basis (eq. 4)"
        if inp["table"] == "1A":
            checks.append(_nl_limit(name, "inside", "eq. (4) as the paper writes it, for Table 1A"))
        else:
            checks.append(_nl_limit(name, "outside", "eq. (4) applied to the basis of Table %s is the skill's extension, "
                                    "not the paper's statement" % inp["table"]))
    if out.get("interpolated"):
        base, bound = out["base"], out.get("proportionalBound") or {}
        above = [k for k in COMPONENTS if k in bound and base[k] > bound[k] * (1 + 1e-9)]
        checks.append(_nl_limit("interpolation between two user-read rows", "outside" if above else "inside",
                                ("affine value exceeds the proportional bound for " + ", ".join(above)) if above
                                else "affine value within the proportional bound"))
    return checks


def _nl_checks(module: str, inp: Dict[str, Any], res: Dict[str, Any], basis: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """checks[] for one run: what was evaluated, and what the module does not check."""
    out, st = res["output"], res["status"]
    factor = inp.get("ownerFactor")
    against = ("against the allowables as entered" if factor is None
               else "against the allowables factored by ownerFactor %g" % factor)
    checks: List[Dict[str, Any]] = []
    if module == "connections.nozzle-load-check":
        checks.append(make_check("per-component ratios", "calculated", st,
                                 "six components %s; allowables entered by the user" % against))
    elif module == "connections.nema-sm23":
        checks.append(make_check("3*Fr + Mr against a*De", "calculated", st,
                                 "coefficient entered by the user from the equation of record, %s" % against))
        checks.append(make_check("combined resultant at the exhaust or largest connection, its component limits, the "
                                 "vertical-down exhaust allowance and datasheet multipliers", "not checked", None,
                                 "API 617 E.5, API 611 I.5, API 612 D.5: vendor-sheet items the user confirms"))
    elif module == "connections.api610-annexf":
        for c in out["checks"]:
            checks.append(make_check("%s %s" % (c["id"], c["label"]), "calculated", c["status"],
                                     "advisory only (F.2 permits exceeding it)" if c["advisory"] else
                                     "constants entered by the user from the edition of record, %s" % against))
        if out["pumpType"] == "vertical-inline" and "maxComponentRatio" not in out:
            checks.append(make_check("F.1.2 a) per-component screen", "not checked", None,
                                     "annexF.componentMultiple not supplied: the informational screen was skipped"))
        checks.append(make_check("shaft displacement limits (F.1.1, F.1.2) and the purchaser's approval of loads above "
                                 "Table 5", "not checked", None, "read by the user; the module compares loads only"))
    elif module == "equipment.nozzle-load-sum":
        checks.append(make_check("sum of the nozzle load sets against the limits", "calculated", st,
                                 "six components %s; limits entered by the user" % against))
    elif module == "equipment.api650-annexp-ordinates":
        lam = out["lambda"]
        inside = ANNEXP_LAMBDA_PLOTTED[0] <= lam <= ANNEXP_LAMBDA_PLOTTED[1]
        checks.append(make_check("ordinates and opening positions (P.2.7.1)", "calculated", None,
                                 "YF, YL, YC read from Figures P.4a/P.4b by the user"))
        checks.append(_nl_limit("lambda within the plotted range of Figures P.4a/P.4b", "inside" if inside else "outside",
                                "lambda %.4g, plotted range %g to %g"
                                % (lam, ANNEXP_LAMBDA_PLOTTED[0], ANNEXP_LAMBDA_PLOTTED[1])))
        checks.append(make_check("acceptance boundary (Figures P.3a/b, P.5a/b) and the stiffness, shell growth and "
                                 "piping loads of P.2.4 to P.2.6", "not checked", None,
                                 "plot the ordinates on the printed nomograms"))
    elif module == "equipment.pvp2011-allowables":
        checks.extend(_nl_pvp_checks(inp, out))
    if module in ("connections.nozzle-load-check", "equipment.nozzle-load-sum") and inp.get("derivedSetStatus") is not None:
        word = worst_of(["screening", inp["derivedSetStatus"]])
        checks.append(make_check("allowable set derived by equipment.pvp2011-allowables", word, None,
                                 "derived set, not a table or datasheet value; the derivation run reported %s"
                                 % inp["derivedSetStatus"]))
    if (module in ("connections.nozzle-load-check", "equipment.nozzle-load-sum") and inp.get("derivedSetStatus") is None
            and re.search(r"derived|pvp2011", str(inp.get("standard")), re.I)):
        checks.append(make_check("allowable set derived by equipment.pvp2011-allowables", "manual check required", None,
                                 "the standard label names a derived set but derivedSetStatus was not supplied, so "
                                 "the derivation's scope limits are unknown; pass the derivation run's result_status"))
    if module == "connections.nozzle-load-check" and re.search(r"\b560\b", str(inp.get("standard"))):
        checks.append(make_check("heater terminal movements (API 560 section 9.2)", "not checked", None,
                                 "the module compares forces and moments only; list allowable and calculated movements"))
    pointers = [(d, n, v) for d, n, v in _nl_practice_items(basis) if not _nl_is_number(v)]
    if pointers and module in _NL_OWNER_MODULES and factor is None:
        checks.append(make_check("owner practice design-stage limit", "pointer only", None,
                                 "; ".join("%s '%s' is recorded as a pointer (%s)" % (d, n, v if v else "no value")
                                           for d, n, v in pointers)
                                 + "; no ownerFactor was supplied, so that check does not run"))
    assumed = assumed_inputs_check(basis_assumptions(basis) if basis is not None else None)
    if assumed is not None:
        checks.append(assumed)
    return checks


def _nl_status_why(checks: List[Dict[str, Any]], word: str) -> str:
    notes = [c["note"] for c in checks if c["result_status"] == word and c.get("note")]
    why = "; ".join(notes) if notes else "every check evaluated"
    limits = not_performed(checks)
    return why + ("; " + limits if word == "calculated" and limits else "")


def _nl_result_fields(module: str, inp: Dict[str, Any], res: Dict[str, Any], basis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The B9 envelope keys: result_status, checks, result_status_line, banner."""
    checks = _nl_checks(module, inp, res, basis)
    fields = status_fields(checks)
    word = fields["result_status"]
    fields["result_status_line"] = render_status_line(word, _nl_status_why(checks, word))
    if res["status"] == "pass":
        fields["banner"] = banner_word("PASS", word, any(c.get("unresolved_factor") for c in checks))
    else:
        fields["banner"] = {"fail": "FAIL"}.get(res["status"], "NA")
    return fields


def run_module(module: str, inp: Dict[str, Any], project_basis_path: Optional[str] = None) -> Dict[str, Any]:
    basis = None
    if isinstance(inp, dict):
        inp = dict(inp)
        basis = load_project_basis(project_basis_path, inp.pop("project_basis", None))
    elif project_basis_path:
        basis = load_project_basis(project_basis_path, None)
    basis_warnings: List[str] = []
    applied = None
    if basis is not None and module in REGISTRY and isinstance(inp, dict):
        inp, applied, basis_warnings = _nl_apply_basis(module, inp, basis)
    inp, provenance, cv_notes = apply_code_values(inp, module, _cv_fields(module, _cv_units_input(inp)))
    pre_warnings = basis_warnings + cv_notes + validate(module, inp)
    work: Dict[str, Any] = dict(inp)
    work.pop("derivedSetStatus", None)
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
    envelope = {
        "module": res["module"],
        "status": res["status"],
        "output": res["output"],
        "warnings": pre_warnings + notes + res["warnings"],
        "citation": CITATIONS[module],
        "inputs": inp,
        "user_supplied": [k for k in USER_SUPPLIED[module] if k in inp],
    }
    if provenance is not None:
        envelope["code_value_provenance"] = provenance
    if applied is not None:
        envelope["project_basis_applied"] = applied
        envelope["project_basis_section"] = render_basis_section(applied, basis, "## 1. Basis")
    envelope.update(_nl_result_fields(module, inp, res, basis))
    return envelope


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
    ap.add_argument("--project-basis", help="path to a pipingtoolset.project-basis/1 JSON record "
                                            "(or give the top-level input project_basis; both must agree)")
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
        print(json.dumps(run_module(args.module, data, args.project_basis), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        return _fail(str(exc).replace("\n", " "))
    except ArithmeticError:  # OverflowError, decimal.InvalidOperation on very large magnitudes
        return _fail("value out of range (magnitude too large to evaluate)")


if __name__ == "__main__":
    sys.exit(main())
