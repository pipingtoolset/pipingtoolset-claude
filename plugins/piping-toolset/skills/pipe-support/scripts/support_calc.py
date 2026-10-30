#!/usr/bin/env python3
"""support_calc - pipe-support assembly check, review and optimisation from one spec.

    python support_calc.py spec.json [--report calc.md] [--json result.json]
                                     [--no-optimize] [--quiet] [--project-basis basis.json]

Spec (references/spec-format.md):
  design   assembly input (PiperSTR field names) WITHOUT pipe loads, or
  preset   "csa-type-1" | "csa-type-2" with `design` keys as overrides
  pipes    [{tag, arm, offset, loads: {units, cases{SUS,OPE,WIN,EQ,HYD}, map, SDS,
            vertical_axis, pipe_axis}}]                -> CAESAR II mode (ASCE 7-22 combos)
           or omit `pipes` and put factored loads on design.arms[].pipes -> factored mode
  T_factor, fabrication {armToColumn}, optimize {objectives, families, maxRatio, top} | false,
  assumed [..], tag, project, calcBy, date
  code_values optional {name: {value, unit, citation{standard, edition, table, row, column?},
              source: "connector"|"user"}} - see CODE VALUES below (the spelling codeValues
              is accepted too; give one of them)

CODE VALUES (optional `code_values` block in the spec)
  Names: the full spec paths design.material.Fy, design.material.Fu, design.material.E,
  design.weldFEXX, design.baseplate.plateFy, design.baseplate.anchorFuta,
  design.baseplate.bondStrength, design.baseplate.cac, design.baseplate.anchorStressArea and
  pipes.<n>.loads.SDS (n = the 0-based pipe position). Shorter spellings are accepted for the
  same slots: Fy, Fu, E, weldFEXX, plateFy, anchorFuta, bondStrength, cac, anchorStressArea,
  material.Fy, baseplate.bondStrength, ... and SDS or loads.SDS for every pipe at once.
  A value the spec leaves out is filled from code_values[name]["value"], and it replaces the
  same key of a preset; a value the spec gives must agree, otherwise the run exits 2 with
  "code_values.<name> conflicts with input <name>" (stderr, no verdict; a failed limit state
  prints a verdict and also exits 2, so read the message). A name outside the list, a bad
  entry or a unit that cannot be used also exits 2. "source" is "connector" or "user". A unit
  other than the input's unit (ksi, psi, in, in^2; g or none for SDS) is converted when the
  factor is exact (Msi or ksi to psi or ksi) and rejected otherwise. SDS needs CAESAR II mode
  (pipes). The result document gains "code_value_provenance" {name: {unit, citation, source}}
  and "code_value_applied" {name: {value, unit}}, and the Markdown report gains a "Code-table
  values" table. Nothing here reaches a network.

PROJECT BASIS (optional top-level `project_basis`, or --project-basis <file>; never both with
  different content): the shared pipingtoolset.project-basis/1 record (references/project-basis.md).
  Filled when the spec leaves them out, exit 2 "project_basis.<path> conflicts with input <name>"
  when they differ: project, calcBy, date <- project.name/calcBy/date; in CAESAR II mode
  pipes.<n>.loads.units <- units (USC lbf + ft-lbf -> lb-ft, kip + kip-in -> kip-in; SI exits 2),
  pipes.<n>.loads.vertical_axis <- equipment_axes.global_vertical, pipes.<n>.loads.pipe_axis <-
  equipment_axes.pipe_axis. ASSUMED items join `assumed`; materials[use=support] and
  load_case_ids are carried to the sheet (no Fy/Fu and no loads.map is filled from them). The
  result gains "project_basis_applied" and the report a "Basis - project basis record" section.

RESULT STATUS: the envelope gains "result_status" (calculated | screening | manual check required |
  pointer only | not checked, the worst word among the checks performed; ASSUMED items and CSA preset
  anchor values each give one row graded manual check required) and "checks" [{name, result_status, status,
  note}]; the result document repeats "result_status". A guard-held stage, a critical review
  finding the model cannot carry, or a seismic case without SDS is manual check required; SDS given
  only as a pointer (a string) is pointer only (Ev does not run); anchorage on CSA preset values is
  screening; the Known-limits items are listed as not checked. No PASS is printed under manual
  check required or pointer only.

Exit codes: 0 every combination passes, no critical review finding and the result status allows
a PASS; 3 not issuable although no limit state fails: a critical review finding stands (e.g.
pipe moments the model cannot carry), a validity guard holds a stage at "manual check required"
(ASD anchorage governed by a wind combination, code-basis item 10: the verdict line reads "NOT
ISSUABLE - ASD anchorage governed by wind combination <id>: ..." and never PASS), or the result
status is manual check required or pointer only; 2 a limit state fails, or the code_values block
or the project basis record cannot be applied (message "input error: ..." on stderr, no
verdict); 1 the spec is defective.
Standard library only (Python 3.9+).
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipe_support import loads as L  # noqa: E402
from pipe_support import optimizer as O  # noqa: E402
from pipe_support import report as R  # noqa: E402
from pipe_support import review as V  # noqa: E402
from pipe_support.assembly import CSA_PRESETS, analyze_assembly  # noqa: E402
from pipe_support.common import InputError  # noqa: E402


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


class CodeValuesError(ValueError):
    """A code_values block that cannot be applied; the CLI prints the message and exits 2."""


# Inputs the code_values block can fill: dotted path in the spec ("*" = every list entry) -> the input's unit.
_CV_FIELDS = {
    "design.material.Fy": "ksi", "design.material.Fu": "ksi", "design.material.E": "ksi",
    "design.weldFEXX": "ksi",
    "design.baseplate.plateFy": "ksi", "design.baseplate.anchorFuta": "ksi",
    "design.baseplate.bondStrength": "psi", "design.baseplate.cac": "in",
    "design.baseplate.anchorStressArea": "in^2",
    "pipes.*.loads.SDS": "-",
}
_CV_ALIASES = {}
for _canon in _CV_FIELDS:
    _parts = _canon.split(".")
    _CV_ALIASES[_parts[-1]] = _canon
    if len(_parts) > 2:
        _CV_ALIASES[".".join(_parts[1:] if _parts[0] == "design" else _parts[-2:])] = _canon


def _cv_applied(spec: dict, provenance: dict) -> dict:
    """{name: {value, unit}} as used in the run, read back from the filled spec."""
    out = {}
    for name in provenance:
        segs, shape = _cv_resolve(name, _CV_FIELDS, _CV_ALIASES)
        path = _cv_paths(spec, segs, name)[0]
        out[name] = {"value": _cv_get(spec, path, name), "unit": _CV_FIELDS[shape]}
    return out


FABRICATION = ("shop-weld", "field-weld", "bolted")
PRESET_SUPPLIED = ("bondStrength", "anchorFuta", "anchorType", "anchorEmbedment", "fc")


def resolve_design(spec: dict) -> dict:
    if spec.get("preset") and spec["preset"] not in CSA_PRESETS:
        raise InputError(f"unknown preset {spec['preset']!r}: {sorted(CSA_PRESETS)}")
    d = copy.deepcopy(CSA_PRESETS[spec["preset"]]) if spec.get("preset") else {}
    for k, v in (spec.get("design") or {}).items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            d[k] = {**d[k], **v}
        else:
            d[k] = copy.deepcopy(v)
    for k in ("method", "type", "arms", "material", "weldSize", "weldFEXX", "columnHeight"):
        if k not in d:
            raise InputError(f"design.{k} is required")
    d.setdefault("tag", spec.get("tag"))
    fab = (spec.get("fabrication") or {}).get("armToColumn", "shop-weld")
    if fab not in FABRICATION:
        raise InputError(f"fabrication.armToColumn must be one of {FABRICATION}")
    return d


def preset_provenance(spec: dict) -> list:
    """Anchor/concrete values taken from a preset rather than the user - never silent."""
    if not spec.get("preset"):
        return []
    given = ((spec.get("design") or {}).get("baseplate") or {})
    pre = CSA_PRESETS[spec["preset"]].get("baseplate") or {}
    out = []
    for k in PRESET_SUPPLIED:
        if k in pre and k not in given:
            out.append(f"{k} = {pre[k]} taken from the {spec['preset']} preset, NOT from the user"
                       + (" or an ESR - replace with the anchor product's ESR value before issue"
                          if k == "bondStrength" else " - confirm"))
    return out


def factored_spec(spec: dict, design: dict) -> dict:
    """Factored mode: the loads on design.arms[].pipes become one demand set, so the same
    envelope, review and optimizer run on them."""
    s = copy.deepcopy(spec)
    pipes, dem, seen = [], {}, set()
    for ai, arm in enumerate(design["arms"]):
        for pi, p in enumerate(arm.get("pipes") or []):
            tag = p.get("tag") or f"arm{ai + 1}-pipe{pi + 1}"
            if tag in seen:
                tag = f"{tag}#{ai + 1}.{pi + 1}"
            seen.add(tag)
            pipes.append({"tag": tag, "arm": ai, "offset": p["offset"]})
            dem[tag] = {"vertical": p["vertical"], "transverse": p.get("transverse", 0),
                        "longitudinal": p.get("longitudinal", 0)}
    if not pipes:
        raise InputError("factored mode needs loads on design.arms[].pipes (or give `pipes` with CAESAR II loads)")
    s["pipes"] = pipes
    s["_factoredSets"] = [{"id": "as entered", "clause": "factored loads as entered", "demands": dem}]
    return s


# ---------------------------------------------------------------- project basis (B8, 0.8.0)

# project_basis.units force / moment words -> this engine's loads.units word
_PB_LOAD_UNITS = (
    ("lb-ft", ("lb", "lbs", "lbf"), ("ft-lb", "ft-lbf", "lb-ft", "lbf-ft")),
    ("kip-in", ("kip", "kips"), ("kip-in", "in-kip", "kips-in", "in-kips")),
)


def _pb_refuse_si(basis) -> None:
    if basis_units(basis).get("system") == "SI":
        raise ProjectBasisError("project_basis.units.system SI cannot be used: pipe-support reads CAESAR II "
                                "restraint loads in US customary units (lb with ft-lb, or kip with kip-in); "
                                "convert the loads or set units.system to USC")


def _pb_load_units(units):
    """project_basis.units -> loads.units ("lb-ft" or "kip-in"); PROJECT_BASIS_SKIP without force and moment."""
    u = basis_units({"units": units})
    force, moment = u.get("force"), u.get("moment")
    if force is None and moment is None:
        return PROJECT_BASIS_SKIP
    f, m = str(force or "").strip().lower(), str(moment or "").strip().lower()
    for word, forces, moments in _PB_LOAD_UNITS:
        if f in forces and m in moments:
            return word
    raise ProjectBasisError(f"project_basis.units force {force!r} with moment {moment!r} cannot be used: "
                            "pipe-support reads lb with ft-lb (loads.units lb-ft) or kip with kip-in (kip-in)")


def _pb_assumed_text(a: dict) -> str:
    out = f"ASSUMED (project basis): {a['item']}"
    if a.get("note"):
        out += f"; {a['note']}"
    if a.get("owner"):
        out += f" (owner: {a['owner']})"
    return out


def apply_project_basis(spec: dict, basis):
    """(effective spec, project_basis_applied) after this skill's fill map; (spec, None) without a record."""
    if basis is None:
        return spec, None
    _pb_refuse_si(basis)
    pipes = spec.get("pipes")
    caesar = isinstance(pipes, list) and bool(pipes)
    fill = [("project", "project.name", None), ("calcBy", "project.calcBy", None), ("date", "project.date", None)]
    view = dict(spec)
    if caesar:
        # fill_from_basis walks objects only, so the pipe list is viewed as {"0": pipe, "1": pipe, ...}
        view["pipes"] = {str(i): p for i, p in enumerate(pipes)}
        for i in range(len(pipes)):
            fill += [(f"pipes.{i}.loads.units", "units", _pb_load_units),
                     (f"pipes.{i}.loads.vertical_axis", "equipment_axes.global_vertical", None),
                     (f"pipes.{i}.loads.pipe_axis", "equipment_axes.pipe_axis", None)]
    eff, applied = fill_from_basis(view, basis, fill)
    if caesar:
        eff["pipes"] = [eff["pipes"][str(i)] for i in range(len(pipes))]
    elif basis.get("units"):
        mark_basis_used(applied, "units", None, "noted")          # factored loads are kip as entered
    if basis_get(basis, "materials[use=support]") is not None:
        mark_basis_used(applied, "materials[use=support]", "design.material", "noted")
    if basis.get("load_case_ids"):
        mark_basis_used(applied, "load_case_ids", None, "noted")
    assumed = [_pb_assumed_text(a) for a in applied["assumptions"]]
    if assumed:
        have = eff.get("assumed")
        if have is not None and not isinstance(have, list):
            raise InputError("assumed must be a list of strings")
        eff["assumed"] = list(have or []) + [a for a in assumed if a not in (have or [])]
        mark_basis_used(applied, "assumptions", "assumed", "filled")
    return eff, applied


def _pb_notes(basis) -> list:
    """Sheet notes for the record fields this skill carries but does not fill."""
    out = []
    mat = basis_get(basis, "materials[use=support]")
    if mat is not None:
        txt = ", ".join(f"{k} {mat[k]}" for k in ("id", "spec", "grade", "form") if mat.get(k))
        out.append(f"Support material from the project basis: {txt}. Fy and Fu are not in the record; they "
                   "come from design.material or code_values, cited.")
    cases = basis_get(basis, "load_case_ids.cases") or {}
    if cases:
        ids = "; ".join(f"{k} = {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in cases.items())
        out.append(f"Stress-program load case ids from the project basis: {ids}. The restraint rows in "
                   "pipes[].loads.cases must come from these cases; loads.map is not filled from them (the "
                   "engine keys the cases SUS / OPE / WIN / EQ / HYD and an OCC id does not say wind or seismic).")
    if basis_get(basis, "load_case_ids.software") == "AutoPIPE":
        out.append("load_case_ids.software is AutoPIPE: the engine reads the CAESAR II convention (the load ON "
                   "the restraint, global axes, signed) - confirm the AutoPIPE support-reaction sign before use.")
    return out


# ---------------------------------------------------------------- result status (B9, 0.8.0)

def preset_supplied_keys(spec: dict) -> list:
    """The PRESET_SUPPLIED base-plate keys a run takes from its CSA preset, not from the user."""
    if not spec.get("preset"):
        return []
    given = ((spec.get("design") or {}).get("baseplate") or {})
    pre = CSA_PRESETS[spec["preset"]].get("baseplate") or {}
    return [k for k in PRESET_SUPPLIED if k in pre and k not in given]


def _split_sds(spec: dict):
    """(spec without pointer SDS values, {"given", "missing", "pointer": [(tag, value)]}).

    An SDS given as a string (a pointer id or a "read from" text) is a pointer only: it is removed
    so the run goes on without Ev, and the Ev check reads "pointer only"."""
    out = {"given": [], "missing": [], "pointer": []}
    pipes = spec.get("pipes") or []
    if not isinstance(pipes, list) or not pipes:
        return spec, out
    if any(isinstance(p, dict) and isinstance((p.get("loads") or {}).get("SDS"), str) for p in pipes):
        spec = copy.deepcopy(spec)
        pipes = spec["pipes"]
    for i, p in enumerate(pipes):
        lb = (p.get("loads") or {}) if isinstance(p, dict) else {}
        tag = (p.get("tag") if isinstance(p, dict) else None) or f"pipe {i + 1}"
        v = lb.get("SDS")
        if isinstance(v, str):
            out["pointer"].append((tag, v))
            lb.pop("SDS")
        elif v is None:
            out["missing"].append((tag, None))
        else:
            out["given"].append((tag, v))
    return spec, out


def _refuse_pointer_values(cv_applied) -> None:
    """A code_values string for a numeric slot other than SDS: nothing can run without it (exit 2)."""
    for name, used in (cv_applied or {}).items():
        if isinstance(used.get("value"), str) and not name.endswith("SDS"):
            raise CodeValuesError(f"code_values.{name} is a pointer only ({used['value']!r}): read the value "
                                  "from the cited table and give it as a number; the checks that use it cannot "
                                  "run without it")


_PRESET_COMPONENTS = {"fc": ("baseplate", "anchorage")}      # every other preset key feeds the anchorage only


def _stage_check(st: dict, preset_keys: list, preset) -> dict:
    status, ratio = st["status"], st.get("ratio")
    where = f"max UR {R._n(ratio)}" + (f" under {st['combo']}" if st.get("combo") else "")
    if status == O.MANUAL_CHECK:
        g = st.get("asdWindGuard") or {}
        return make_check(st["stage"], "manual check required", st.get("engineStatus", "na"),
                          f"held by the ASD wind-anchorage guard ({g.get('trigger', 'governing')}); engine status "
                          f"{st.get('engineStatus', '-')} at {where}; code-basis item 10")
    if status == "na":
        return make_check(st["stage"], "not checked", "na", "no demand on this stage in the model")
    keys = [k for k in preset_keys if st["component"] in _PRESET_COMPONENTS.get(k, ("anchorage",))]
    if keys:   # graded once, in the "preset inputs" row
        return make_check(st["stage"], "calculated", status,
                          f"{where}; on {', '.join(keys)} from the {preset} preset (see preset inputs)")
    return make_check(st["stage"], "calculated", status, where)


PRESET_CHECK_NAME = "preset inputs"


def preset_inputs_check(spec: dict):
    """One "preset inputs" row (manual check required) for the anchor and concrete values a run takes
    from its CSA preset, each flagged in the report as to be replaced or confirmed; None without any."""
    keys = preset_supplied_keys(spec)
    if not keys:
        return None
    pre = CSA_PRESETS[spec["preset"]]["baseplate"]
    items = [f"{k} = {pre[k]} from the {spec['preset']} preset"
             + (" (replace with the anchor product's ESR value)" if k == "bondStrength" else "") for k in keys]
    return make_check(PRESET_CHECK_NAME, "manual check required", "na",
                      "confirm before issue: " + "; ".join(items))


_PB_ASSUMED_PREFIX = "ASSUMED (project basis): "


def assumed_check(spec: dict):
    """The shared "ASSUMED inputs" row for the spec's assumed[] list (the record's ASSUMED items are
    already in it), or None when the list is empty."""
    items = [a[len(_PB_ASSUMED_PREFIX):] if isinstance(a, str) and a.startswith(_PB_ASSUMED_PREFIX) else a
             for a in spec.get("assumed") or []]
    return assumed_inputs_check(items)


def result_checks(doc: dict, spec: dict, sds: dict) -> list:
    """The checks[] list of the envelope (B9 taxonomy; references/project-basis.md)."""
    env, design = doc["envelope"], doc["design"]
    preset_keys = preset_supplied_keys(spec)
    checks = [_stage_check(st, preset_keys, spec.get("preset")) for st in env["stages"]]
    caesar = doc["loadMode"] == "caesar"
    seismic = caesar and "Eh" in doc.get("categoryMap", {})
    if caesar:
        checks.append(make_check("ASCE 7-22 load combinations", "calculated", "na",
                                 f"{env.get('combosRun', '-')} combinations from the restraint loads; category "
                                 "mapping in the report, engineer to confirm"))
    else:
        checks.append(make_check("Loads as entered (factored mode)", "calculated", "na",
                                 "user-factored demands; no ASCE 7 combination applied"))
    if seismic:
        name = "Vertical seismic Ev = 0.2 SDS D (ASCE 7-22 12.4.2.2)"
        if sds["missing"]:
            checks.append(make_check(name, "manual check required", "na",
                                     f"SDS not given for {', '.join(t for t, _ in sds['missing'])}: Ev taken as "
                                     "zero, which 12.4.2.2 permits only under its exceptions - give SDS and re-run"))
        elif sds["pointer"]:
            checks.append(make_check(name, "pointer only", "na",
                                     "SDS supplied only as a pointer for " + ", ".join(
                                         f"{t} ({v})" for t, v in sds["pointer"])
                                     + ": Ev did not run (the seismic combinations carry no Ev) - read SDS and "
                                     "re-run"))
        else:
            checks.append(make_check(name, "calculated", "na", "SDS = " + ", ".join(
                f"{R._n(v)} ({t})" for t, v in sds["given"])))
    for f in doc["findings"]:
        if f["severity"] == "critical" and not f["title"].startswith("FAILS"):
            checks.append(make_check(f["title"], "manual check required", "na",
                                     f.get("remedy") or f.get("basis") or "critical review finding"))
    checks += [c for c in (assumed_check(spec), preset_inputs_check(spec)) if c is not None]
    nc = []
    if design.get("columnShape"):
        nc.append(("Column torsion (AISC 360-22 H3)", "torsion is reported at the base, not checked"))
    if seismic:
        nc.append(("Seismic overstrength combinations (ASCE 7-22 Em with Omega0)",
                   "not generated; map a case scaled by Omega0 as Eh and re-run where the anchorage needs it"))
    if design.get("type") in ("goalpost", "trapeze") and not design.get("columnSpacing"):
        nc.append(("Header span between the columns", "no columnSpacing given, so the header is not checked"))
    if any(r["status"] == "not run" for r in doc["compliance"]):
        nc.append(("Serviceability - deflection", "no deflection row in the model"))
    nc.append(("Snow, rain, ice and flood loads (ASCE 7-22 Lr, S, R, Fa, Di, Wi)",
               "not generated; supply them as extra categories if the support is exposed"))
    nc.append(("AWS D1.1 prequalified joints, WPS, filler metal, inspection",
               "cited by topic only; engineer to confirm against the governing edition"))
    checks += [make_check(n, "not checked", "na", why) for n, why in nc]
    return checks


def _status_why(checks: list, word: str) -> str:
    hits = [c for c in checks if c["result_status"] == word]
    names = ", ".join(c["name"] for c in hits)
    limits = not_performed(checks)
    if word == "calculated":
        return "every check run is calculated from the given inputs" + (f"; {limits}" if limits else "")
    if word == "not checked":
        return limits
    if word == "screening":
        return "screening inputs: " + "; ".join(f"{c['name']} ({c['note'].split('; ')[-1]})" for c in hits)
    if word == "pointer only":
        return f"not issuable, a required value is a pointer only (that check did not run): {names}"
    held = [f"{c['name']} ({c['note']})" if c["name"] in (ASSUMED_CHECK_NAME, PRESET_CHECK_NAME) else c["name"]
            for c in hits]
    return "not issuable, held for a manual check: " + ", ".join(held)


def apply_result_status(doc: dict, spec: dict, sds: dict) -> None:
    """Merge result_status and checks into the envelope; doc["_status"] carries the banner decision."""
    checks = result_checks(doc, spec, sds)
    doc["envelope"].update(status_fields(checks))
    word = doc["envelope"]["result_status"]
    doc["result_status"] = word
    unresolved = any(c.get("unresolved_factor") for c in checks)
    why = _status_why(checks, word)
    doc["_status"] = {"banner_allowed": checks_banner_allowed(checks), "word": banner_word("PASS", word, unresolved),
                      "why": why, "line": render_status_line(word, why)}


def run(spec: dict, optimize: bool = True, project_basis_file=None) -> dict:
    spec = dict(spec)
    basis = load_project_basis(project_basis_file, spec.pop("project_basis", None))
    spec, pb_applied = apply_project_basis(spec, basis)
    try:
        spec, cv_provenance, cv_notes = apply_code_values(spec, "the support spec", _CV_FIELDS, _CV_ALIASES,
                                                          keys=("code_values", "codeValues"))
    except ValueError as exc:
        raise CodeValuesError(str(exc)) from None
    cv_applied = _cv_applied(spec, cv_provenance) if cv_provenance is not None else None
    _refuse_pointer_values(cv_applied)
    spec, sds = _split_sds(spec)
    design = resolve_design(spec)
    method = design["method"]
    if "factored_wind" in spec and not isinstance(spec["factored_wind"], bool):
        raise InputError("factored_wind: give true or false (do the factored loads carry a wind term?)")
    doc = {"spec": spec, "design": design, "notes": list(cv_notes),
           "assumed": list(spec.get("assumed", [])) + preset_provenance(spec)}
    if basis is not None:
        doc["notes"] += _pb_notes(basis)
    if sds["pointer"]:
        doc["notes"].append("SDS supplied only as a pointer for " + ", ".join(t for t, _ in sds["pointer"])
                            + ": Ev = 0.2 SDS D not applied; read SDS and re-run.")
    if spec.get("pipes"):
        doc["loadMode"] = "caesar"
        sets, notes = O.demand_sets(spec, method)
        doc["notes"] += notes
        resolved: dict = {}
        combos, _, cats = L.combinations({**spec["pipes"][0]["loads"], "_resolvedMap": resolved,
                                          "T_factor": spec.get("T_factor", 1.0)}, method)
        present = set(cats)
        doc["combinations"] = [{"id": c["id"], "clause": c["clause"],
                                "factors": {k: v for k, v in c["factors"].items() if k in present}}
                               for c in combos]
        cmap = {k: v.replace("-", " - ") for k, v in resolved.items()}
        if "Ev" in cats:
            cmap["Ev"] = "0.2 SDS D"
        doc["categoryMap"] = cmap
        run_spec = spec
        env = O.envelope(design, sets, spec, O._service(spec, design))
        if "factored_wind" in spec:
            doc["notes"].append("factored_wind is read in factored mode only; ignored here (CAESAR II mode "
                                "builds the combinations, so the wind guard sees them).")
    else:
        doc["loadMode"] = "factored"
        run_spec = factored_spec(spec, design)
        env = O.envelope(design, run_spec["_factoredSets"], run_spec)
        doc["notes"].append("Factored mode: loads used exactly as entered - no ASCE 7 combinations applied.")
    doc["envelope"] = env
    opt = None
    ocfg = spec.get("optimize", {})
    if optimize and ocfg is not False:
        opt = O.optimize(design, run_spec)
        keep = isinstance(ocfg, dict) and ocfg.get("includeDesigns")
        for a in opt["alternatives"]:
            if not keep:
                a.pop("design", None)
    doc["optimizer"] = opt
    doc["boltedAlternative"] = V.bolted_arm_alternative(design, env, method)
    doc["findings"] = V.review(design, env, spec, opt)
    doc["criticalFindings"] = sum(1 for f in doc["findings"] if f["severity"] == "critical")
    doc["compliance"] = R.compliance_matrix(env)
    if cv_provenance is not None:
        doc["code_value_provenance"] = cv_provenance
        doc["code_value_applied"] = cv_applied
    if pb_applied is not None:
        doc["project_basis_applied"] = pb_applied
        doc["_basis_section"] = render_basis_section(pb_applied, basis, heading="## Basis - project basis record")
    apply_result_status(doc, spec, sds)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--report", help="write the Markdown calculation report here")
    ap.add_argument("--json", help="write the JSON result document here")
    ap.add_argument("--no-optimize", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print only the one-line verdict")
    ap.add_argument("--project-basis", help="the shared project basis record (pipingtoolset.project-basis/1)")
    a = ap.parse_args(argv)
    try:
        with open(a.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        if not isinstance(spec, dict):
            raise InputError("the spec must be a JSON object")
        doc = run(spec, optimize=not a.no_optimize, project_basis_file=a.project_basis)
    except (CodeValuesError, ProjectBasisError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    except (InputError, KeyError, ValueError, TypeError) as e:
        print(f"SPEC ERROR: {e}", file=sys.stderr)
        return 1
    md = R.markdown(doc)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(md)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            fh.write(R.to_json(doc))
    env = doc["envelope"]
    crit = doc["criticalFindings"]
    if a.quiet:
        print(R.cli_verdict(doc))
    else:
        sys.stdout.buffer.write(md.encode("utf-8"))
    if env["status"] == "fail":
        return 2
    if env["status"] != "pass" or crit or not doc["_status"]["banner_allowed"]:
        return 3                            # critical finding, a guard, or a result status that blocks PASS
    return 0


if __name__ == "__main__":
    sys.exit(main())
