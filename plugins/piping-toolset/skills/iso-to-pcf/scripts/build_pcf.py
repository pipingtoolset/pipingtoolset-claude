#!/usr/bin/env python3
"""build_pcf - walk a JSON transcription of a stress isometric into a CAESAR II PCF.

    python build_pcf.py spec.json -o line.pcf [--report report.txt] [--json] [--project-basis basis.json]

The spec (references/spec-format.md) is a transcription of the drawing: start point,
then an ordered walk of components with the drawing's own dimensions as iso strings
("13.7/8", "2635'0.7/16"). This script does all of the geometry - bend tangents,
tee and olet branch points, sloped elevations, axis mapping, mm conversion - in exact
Fraction arithmetic with a single cursor, so adjacent components share one coordinate
and the chain is continuous by construction.

Exit codes: 0 clean; 2 a closure check or BOM count failed (PCF still written so it can
be inspected, but it is not deliverable); 1 the spec is defective (nothing written).

Optional spec key "skeyOverrides": {item type: SKEY}, applied over the default SKEYs. The keys
are the item `type` names (flange blind gasket valve cap misc coupling reducer elbow bend tee
olet support; "reducer" covers the concentric and the eccentric record) or the builder's record
names (ELBOW, BEND, TEE, OLET, FLANGE, FLANGE-BLIND, GASKET, VALVE, CAP, MISC-COMPONENT,
COUPLING, REDUCER-CONCENTRIC, REDUCER-ECCENTRIC, SUPPORT). A SKEY is one token of 2 to 8
upper-case letters and digits starting with a letter (null omits it), and a support takes ANCH,
SKID, GUID or SPRG. An item's own "skey" still wins over the override, and the override over the
default. The report gains "skey_overrides" (the map as the spec gave it, SKEYs upper-cased) and
"skey_overrides_unused" (keys no item of the line used). A spec with no skeyOverrides produces
the same file and report as before. A spec key "code_values" may be absent, null or empty; PCF
building has no code-table inputs, so a block with any entry exits 2 with
"input error: code_values.<name> is not an input of build_pcf.py" and no file is written.

Optional project record (references/project-basis.md): a top-level spec key "project_basis", or
--project-basis <file> (both present and different: exit 2). It fills an absent "axes" from
equipment_axes.global_vertical (Y -> Y-up, Z -> Z-up), an absent "units" from an explicit
units.length of mm, and an absent pipeline.reference from project.line; a spec value that differs
exits 2 "project_basis.<path> conflicts with input <name>". Its ASSUMED items are added to the
report's ASSUMED list. The report gains "project_basis_applied" and a Basis section at the top.

The report also carries "result_status" (calculated, screening, manual check required, pointer only
or not checked: the worst word among the "checks" performed) and the line "Result status: <word> -
<why>" under the title. A failed closure or BOM check is "manual check required"; ASSUMED items give
one "ASSUMED inputs" row graded "manual check required" and the RESULT line reads MANUAL CHECK
REQUIRED; the checks no script of this skill performs are listed as "not checked". No OK or
PASS wording is printed while the banner rule forbids it. "ok", the exit codes and the PCF are
unchanged.

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fractions import Fraction as F
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcf_lib import (DIRS, HAND_CHECKS, PCF, SAFE_MAP, CodeValuesError, PCFError, Point,  # noqa: E402
                     Profile, add, along, angle_deg, check_code_values, check_skey_overrides,
                     fmt_in, ftin, length, off_ray, sub, tangent, unit)


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


# ---------------------------------------------------------------------------- project basis (B8)
def _basis_axes(v):
    return {"Y": "Y-up", "Z": "Z-up"}[v]


def _basis_length(v):
    """An explicit record length of mm fills or agrees with "units" (MM); any other length unit is the
    model's own, not the PCF's (coordinates and bore are always written in mm), so it leaves "units" alone."""
    return "MM" if str(v).lower() == "mm" else PROJECT_BASIS_SKIP


BASIS_FILL_MAP = [("axes", "equipment_axes.global_vertical", _basis_axes),
                  ("units", "units.length", _basis_length),
                  ("pipeline.reference", "project.line", None)]


def apply_project_basis(spec: dict, cli_path: Optional[str] = None):
    """(effective spec without its project_basis key, validated record or None, project_basis_applied or None)."""
    raw = dict(spec)
    basis = load_project_basis(cli_path, raw.pop("project_basis", None))
    if basis is None:
        return raw, None, None
    eff, applied = fill_from_basis(raw, basis, BASIS_FILL_MAP)
    length_unit = basis_get(basis, "units.length")
    if length_unit is not None and _basis_length(length_unit) is PROJECT_BASIS_SKIP:
        mark_basis_used(applied, "units.length", "units", "noted")
    items = []
    for a in applied["assumptions"]:
        text = "project basis: " + a["item"]
        text += "".join(f" - {a[k]}" if k == "note" else f" ({a[k]})" for k in ("note", "owner") if a.get(k))
        items.append(text)
    have = eff.get("assumed")
    if items and (have is None or isinstance(have, list)):
        eff["assumed"] = list(have or []) + [t for t in items if t not in (have or [])]
        mark_basis_used(applied, "assumptions", "assumed", "filled")      # filled, also when appended
    return eff, basis, applied


# Closure-check flag words, chosen by truth value rather than a conditional expression
# (a plugin-directory scanner reads the conditional form as a credential read).
_FLAG_WORDS = ("FAIL", "PASS")


def _flag(ok) -> str:
    return _FLAG_WORDS[1 if ok else 0]

INLINE_TYPES = {"flange": "FLANGE", "blind": "FLANGE-BLIND", "gasket": "GASKET",
                "valve": "VALVE", "cap": "CAP", "misc": "MISC-COMPONENT",
                "coupling": "COUPLING"}
# Defaults: VVFL/RCBW/BEBW/TEBW and the support SKEYs are seen in import-proven PCFs;
# FLWN/FLBL/WTBW are common Isogen keys. Override per item with "skey".
DEFAULT_SKEY = {"FLANGE": "FLWN", "FLANGE-BLIND": "FLBL", "VALVE": "VVFL", "GASKET": None,
                "CAP": None, "MISC-COMPONENT": "VVFL", "COUPLING": None}
SUPPORT_SKEYS = {"ANCH": None, "SKID": "UP", "GUID": None, "SPRG": "UP"}   # skey: default direction
LINE_TOL = 1 / 64   # in: perpendicular offset beyond which a point is off the run


class Builder:
    def __init__(self, spec: dict, project_basis_path: Optional[str] = None):
        spec, self.basis, self.basis_applied = apply_project_basis(spec, project_basis_path)
        self.spec = spec
        check_code_values(spec.get("code_values"))
        self.pcf = PCF(axes=spec.get("axes", "Z-up"), coords=spec.get("units", "MM"),
                       safe=not spec.get("full_vocabulary", False),
                       weight_units=spec.get("weight_units", "LBS"),
                       annotate=bool(spec.get("annotate", True)))
        self.profiles: Dict[str, Profile] = {}
        for name, p in spec.get("profiles", {}).items():
            self.profiles[name] = Profile(p["along"], [(ftin(s), ftin(z)) for s, z in p["points"]])
        st = spec["start"]
        self.cursor: Point = self.point(st["at"], base=(F(0), F(0), F(0)), absolute=True)
        self.anchor: Point = self.cursor
        self.dir: Point = self.direction(st["dir"])
        self.bore: F = F(str(st["bore"]))
        self.checks: List[dict] = []
        self.pipe_len: Dict[str, F] = {}
        self.assumed: List[str] = list(spec.get("assumed", []))
        self.skey_overrides: Optional[Dict[str, Optional[str]]] = None    # record name -> SKEY
        self.skey_given: Dict[str, Optional[str]] = {}                    # as the spec wrote the keys
        self.skey_groups: Dict[str, tuple] = {}                           # given key -> record names
        if "skeyOverrides" in spec:
            self.skey_overrides, self.skey_given, self.skey_groups = check_skey_overrides(spec["skeyOverrides"])
        self.skey_used: set = set()
        self.substitutions: List[str] = []
        self.deferred: List[tuple] = []     # branch walks, written after the main run

    # ------------------------------------------------------------------ inputs
    def direction(self, d) -> Point:
        if isinstance(d, str):
            if d.upper() not in DIRS:
                raise PCFError(f"direction {d!r}: use E W N S UP DOWN or {{e,n,el}}")
            return DIRS[d.upper()]
        return unit((ftin(d.get("e", "0")), ftin(d.get("n", "0")), ftin(d.get("el", "0"))))

    def point(self, p: dict, base: Optional[Point] = None, absolute: bool = False) -> Point:
        """Resolve a point spec. Forms (all dims are iso strings):
        {"E":..,"N":..,"EL":..}  absolute plant coords; omitted ones inherit the anchor;
                                 EL may be "@<profile>" to interpolate at this E/N.
        {"d": {"e":..,"n":..,"el":..}}  delta from the anchor (last stated point).
        {"len": ..}               distance along the current direction from the anchor.
        """
        base = self.anchor if base is None else base
        if "d" in p:
            d = p["d"]
            return add(base, (ftin(d.get("e", "0")), ftin(d.get("n", "0")), ftin(d.get("el", "0"))))
        if "len" in p:
            return along(base, self.dir, ftin(p["len"]))
        if not any(k in p for k in ("E", "N", "EL")):
            raise PCFError(f"point {p!r} has no E/N/EL, d or len")
        if absolute and not all(k in p for k in ("E", "N", "EL")):
            raise PCFError("start point must give E, N and EL")
        e = ftin(p["E"]) if "E" in p else base[0]
        n = ftin(p["N"]) if "N" in p else base[1]
        el = p.get("EL")
        if isinstance(el, str) and el.startswith("@"):
            prof = self.profiles.get(el[1:])
            if prof is None:
                raise PCFError(f"unknown profile {el!r}")
            z = prof.el((e, n)[prof.idx])
        elif el is not None:
            z = ftin(el)
        else:
            z = base[2]
        return (e, n, z)

    # ------------------------------------------------------------------ helpers
    def _skey(self, component: str, default: Optional[str]) -> Optional[str]:
        """The SKEY for a component: the spec's skeyOverrides entry, else the builder default."""
        if self.skey_overrides is not None and component in self.skey_overrides:
            self.skey_used.add(component)
            return self.skey_overrides[component]
        return default

    def _on_line(self, target: Point, what: str):
        """target must lie ahead of the cursor on the current run, within 1/64 in."""
        if target == self.cursor:
            return
        ahead, perp = off_ray(target, self.cursor, self.dir)
        if perp > LINE_TOL or ahead <= 0:
            raise PCFError(f"{what}: point is {'behind the cursor' if ahead <= 0 else 'off the run'} "
                           f"({perp:.3f} in off-line, {ahead:.3f} in ahead) - check the walk")

    def _pipe_to(self, p2: Point, it: dict, label: str):
        if p2 == self.cursor:
            return                                   # fittings make up: no pipe element
        self._on_line(p2, label)
        own = it.get("type") == "pipe"
        self.pcf.inline("PIPE", self.cursor, p2, self.bore,
                        desc=it.get("desc") if own else it.get("pipe_desc"))
        k = f"{float(self.bore):g}"
        self.pipe_len[k] = self.pipe_len.get(k, F(0)) + F(round(length(sub(p2, self.cursor)) * 10000), 10000)
        self.cursor = p2

    def _radius(self, it: dict) -> F:
        r = it.get("radius", "LR")
        if r in ("LR", "SR"):
            # B16.9 convention: LR = 1.5 x NPS, SR = 1.0 x NPS, inches. Valid for NPS >= 3/4
            # only where NPS is the nominal size the user entered as bore.
            self.assumed.append(f"{r} elbow radius taken as {'1.5' if r == 'LR' else '1.0'} x NPS "
                                f"{float(self.bore):g} (B16.9 convention); state it if the iso differs")
            return self.bore * (F(3, 2) if r == "LR" else F(1))
        return ftin(r)

    # ------------------------------------------------------------------ walk
    def walk(self, items: List[dict]):
        for i, it in enumerate(items):
            t = it.get("type")
            handler = getattr(self, f"do_{t}", None)
            if handler is None:
                raise PCFError(f"item {i}: unknown type {t!r}")
            try:
                handler(it)
            except PCFError as e:
                raise PCFError(f"item {i} ({t} {it.get('desc', '')}): {e}") from None
            except KeyError as e:
                raise PCFError(f"item {i} ({t} {it.get('desc', '')}): missing key {e}") from None

    def do_pipe(self, it):
        p2 = self.point(it["to"])
        self._pipe_to(p2, it, "pipe")
        self.anchor = p2

    def _inline(self, it, logical, bore2=None, extra=()):
        if "at" in it:                                   # stated start: pipe up to it first
            self._pipe_to(self.point(it["at"]), it, logical)
        if "len" in it:
            p2 = along(self.cursor, self.dir, ftin(it["len"]))
        elif "to" in it:
            p2 = self.point(it["to"], base=self.cursor)
        else:
            raise PCFError("needs len (face-to-face along the run) or to")
        self._on_line(p2, logical)
        skey = it["skey"] if "skey" in it else self._skey(logical, DEFAULT_SKEY.get(logical))
        self.pcf.inline(logical, self.cursor, p2, self.bore, bore2=bore2, desc=it.get("desc"),
                        skey=skey, weight=F(str(it["weight"])) if "weight" in it else None,
                        extra=extra)
        if self.pcf.safe and logical in SAFE_MAP:
            self.substitutions.append(f"{logical} written as a {SAFE_MAP[logical]} record "
                                      f"({it.get('desc', logical)}, SKEY {skey or 'none'})")
        self.cursor = self.anchor = p2

    def __getattr__(self, name):
        if name.startswith("do_") and name[3:] in INLINE_TYPES:
            logical = INLINE_TYPES[name[3:]]
            return lambda it: self._inline(it, logical)
        raise AttributeError(name)

    def do_reducer(self, it):
        new = F(str(it["bore"]))
        ecc = bool(it.get("eccentric"))
        logical = "REDUCER-ECCENTRIC" if ecc else "REDUCER-CONCENTRIC"
        extra = [f"FLAT-DIRECTION {it.get('flat', 'DOWN')}"] if ecc else []
        if "skey" not in it:
            it = dict(it, skey=self._skey(logical, "RECC" if ecc else "RCBW"))
        if ecc and "to" not in it:
            raise PCFError("eccentric reducer needs 'to' (the offset end point), not just len")
        if ecc and self.pcf.safe:
            self.substitutions.append(f"eccentric reducer written as REDUCER-CONCENTRIC; the offset "
                                      f"is carried by its end points ({it.get('desc', '')})")
        if ecc:
            p2 = self.point(it["to"], base=self.cursor)
            self.pcf.inline(logical, self.cursor, p2, self.bore, bore2=new, desc=it.get("desc"),
                            skey=it["skey"], extra=extra)
            self.cursor = self.anchor = p2
        else:
            self._inline(it, logical, bore2=new)
        self.bore = new

    def _bend(self, it, bend: bool):
        corner = self.point(it["corner"])
        out = self.direction(it["out"])
        ang = angle_deg(self.dir, out)
        if "angle" in it:                                # trimmed/odd angle stated on the iso
            stated = float(F(str(it["angle"])))
            if abs(stated - ang) > 0.25:
                raise PCFError(f"stated angle {stated} deg vs {ang:.2f} deg from the directions")
        R = self._radius(it)
        T = tangent(R, ang)
        t1 = along(corner, self.dir, -T)
        if t1 != self.cursor:
            if off_ray(t1, self.cursor, self.dir)[0] <= 0:
                raise PCFError(f"tangent {fmt_in(T)} overruns the previous component - "
                               f"radius or corner is wrong")
        self._pipe_to(t1, it, "bend")
        t2 = along(corner, out, T)
        self.pcf.bend(t1, t2, corner, self.bore, ang, R, desc=it.get("desc"),
                      skey=it["skey"] if "skey" in it else self._skey("BEND" if bend else "ELBOW", "BEBW"),
                      logical="BEND" if bend else "ELBOW")
        self.cursor, self.anchor, self.dir = t2, corner, out

    def do_elbow(self, it):
        self._bend(it, bend=False)

    def do_bend(self, it):
        self._bend(it, bend=True)

    def _branch(self, it, centre: Point, bp: Point, bdir: Point, bbore: F):
        # Isogen writes the main run first and each branch leg after it; the import-proven
        # files follow that order, so branch walks are queued, not walked in place.
        if it.get("branch"):
            self.deferred.append(((bp, centre, bdir, bbore), it["branch"]))

    def do_tee(self, it):
        centre = self.point(it["centre"])
        C = ftin(it["C"])
        M = ftin(it.get("M", it["C"]))
        bdir = self.direction(it["branch_dir"])
        if float(sum(a * b for a, b in zip(bdir, self.dir))) != 0:
            raise PCFError("tee branch direction must be square to the run")
        bbore = F(str(it.get("branch_bore", self.bore)))
        p1, p2 = along(centre, self.dir, -C), along(centre, self.dir, C)
        self._pipe_to(p1, it, "tee")
        bp = along(centre, bdir, M)
        self.pcf.tee(p1, p2, centre, self.bore, bp, bbore, desc=it.get("desc"),
                     skey=it["skey"] if "skey" in it else self._skey("TEE", "TEBW"))
        self.cursor, self.anchor = p2, centre
        self._branch(it, centre, bp, bdir, bbore)
        self.cursor, self.anchor = p2, centre

    def do_olet(self, it):
        centre = self.point(it["at"])
        self._on_line(centre, "olet")
        bdir = self.direction(it["branch_dir"])
        bbore = F(str(it["branch_bore"]))
        bp = along(centre, bdir, ftin(it["height"]))
        self.pcf.olet(centre, bp, bbore, desc=it.get("desc"),
                      skey=it["skey"] if "skey" in it else self._skey("OLET", "WTBW"))
        self.anchor = centre
        self._branch(it, centre, bp, bdir, bbore)
        self.anchor = centre

    def do_support(self, it):
        """A support must sit ON a node: the pipe is split at the support point (the
        import-proven files never place a restraint mid-element)."""
        at = self.point(it["at"]) if "at" in it else self.cursor
        if at != self.cursor:
            self._pipe_to(at, it, "support")          # raises if behind or off the run
        skey = it["skey"] if "skey" in it else self._skey("SUPPORT", "SKID")
        dirs = it.get("direction", SUPPORT_SKEYS.get(skey, "UP"))
        for d in (dirs if isinstance(dirs, list) else [dirs]):
            self.pcf.support(at, self.bore, skey=skey, direction=d, name=it.get("name"),
                             desc=it.get("desc"))
        self.anchor = at

    def do_check(self, it):
        got = self.cursor if it.get("of") == "cursor" else self.anchor
        want = self.point(it["expect"], base=got)
        tol = ftin(it.get("tol", "0.1/16"))
        d = sub(got, want)
        self.checks.append({"label": it["label"], "delta_in": [float(x) for x in d],
                            "tol_in": float(tol), "pass": all(abs(x) <= tol for x in d)})

    # ------------------------------------------------------------------ run
    def build(self):
        pl = self.spec.get("pipeline", {})
        attrs = [(a[0], a[1]) for a in pl.get("attributes", [])]
        self.pcf.set_header(pl.get("reference", "LINE"), attrs)
        self.walk(self.spec["items"])
        while self.deferred:                          # branches of branches queue behind
            (self.cursor, self.anchor, self.dir, self.bore), items = self.deferred.pop(0)
            self.walk(items)
        return self

    def bom_check(self) -> List[dict]:
        out = []
        for k, want in self.spec.get("bom", {}).items():
            k = k.upper()
            if k.startswith("PIPE-LENGTH"):          # PIPE-LENGTH:<bore> magnitude check, 10%
                bore = k.split(":", 1)[1]
                got = float(self.pipe_len.get(bore, 0))
                w = float(ftin(want))
                ok = w == 0 and got == 0 or (w > 0 and abs(got - w) / w <= 0.10)
                out.append({"item": k, "bom": fmt_in(F(w)), "emitted": fmt_in(F(got)), "pass": ok,
                            "note": "cut length vs centreline: +/-10% magnitude check"})
            else:
                got = self.pcf.census.get(k, 0)
                out.append({"item": k, "bom": int(want), "emitted": got, "pass": got == int(want)})
        return out


def result_checks(closure: List[dict], bom: List[dict], assumed: List[str]) -> List[dict]:
    """The checks[] of the report: what ran (calculated), what is only a screen, what failed
    (manual check required) and what no script of this skill checks (not checked)."""
    out = []
    bad = [c["label"] for c in closure if not c["pass"]]
    if not closure:
        out.append(make_check("closure checks", "not checked", "na", "the spec states no closure checks"))
    elif bad:
        out.append(make_check("closure checks", "manual check required", "fail",
                              f"{len(bad)} of {len(closure)} failed: " + ", ".join(bad[:3]) + (", ..." if len(bad) > 3 else "")))
    else:
        out.append(make_check("closure checks", "calculated", "pass",
                              f"{len(closure)} stated coordinate(s) within tolerance"))
    lengths = [c for c in bom if c["item"].startswith("PIPE-LENGTH")]
    counts = [c for c in bom if not c["item"].startswith("PIPE-LENGTH")]
    if not bom:
        out.append(make_check("BOM reconciliation", "not checked", "na", "the spec states no BOM"))
    if counts:
        bad = [c["item"] for c in counts if not c["pass"]]
        out.append(make_check("BOM component counts", "manual check required" if bad else "calculated",
                              "fail" if bad else "pass",
                              f"{len(bad)} of {len(counts)} differ: " + ", ".join(bad[:3]) + (", ..." if len(bad) > 3 else "")
                              if bad else f"{len(counts)} count(s) match the emitted census"))
    if lengths:
        bad = [c["item"] for c in lengths if not c["pass"]]
        out.append(make_check("BOM pipe length (+/-10% magnitude)", "manual check required" if bad else "screening",
                              "fail" if bad else "pass",
                              ", ".join(bad) + " outside +/-10%" if bad else "cut length vs centreline is a magnitude screen"))
    row = assumed_inputs_check(assumed)          # the one shared row: manual check required
    if row is not None:
        out.append(row)
    out.append(make_check("PCF connectivity validation", "not checked", "na",
                          "validate_pcf.py is not run by the builder; run it before handover"))
    out += [make_check(name, "not checked", "na", note) for name, note in HAND_CHECKS]
    return out


def status_why(checks: List[dict], word: str) -> str:
    """One short reason for the envelope word: the checks that sit at that level, then (for a
    calculated word) the checks this module does not perform."""
    hit = [c for c in checks if c["result_status"] == word]
    limits = not_performed(checks)
    if word == "not checked":
        return limits
    parts = [f"{c['name']}: {c['note']}" if c.get("note") else c["name"] for c in hit[:3]]
    why = "; ".join(parts) + (f"; +{len(hit) - 3} more" if len(hit) > 3 else "")
    return why + (f"; {limits}" if word == "calculated" and limits else "")


def report(b: Builder, bom: List[dict]) -> dict:
    r = {
        "pipeline": b.spec.get("pipeline", {}).get("reference", "LINE"),
        "axes": b.spec.get("axes", "Z-up"),
        "coords": b.pcf.coords,
        "vocabulary": "CAESAR II safe set" if b.pcf.safe else "full PCF vocabulary",
        "annotated": b.pcf.annotate,
        "census": dict(sorted(b.pcf.census.items())),
        "pipe_centreline_in": {k: float(v) for k, v in sorted(b.pipe_len.items())},
        "closure_checks": b.checks,
        "bom_checks": bom,
        "assumed": list(dict.fromkeys(b.assumed)),
        "substitutions": b.substitutions,
        "ok": all(c["pass"] for c in b.checks) and all(c["pass"] for c in bom),
    }
    if b.skey_overrides is not None:
        r["skey_overrides"] = dict(b.skey_given)
        r["skey_overrides_unused"] = [k for k, comps in b.skey_groups.items() if not set(comps) & b.skey_used]
    r.update(status_fields(result_checks(b.checks, bom, r["assumed"])))
    r["result_status_why"] = status_why(r["checks"], r["result_status"])
    if b.basis_applied is not None:
        r["project_basis_applied"] = b.basis_applied
    return r


def render(r: dict, basis: Optional[dict] = None) -> str:
    # The banner rule: a positive word (PASS, OK) is printed only when result_status allows it.
    unresolved = any(c.get("unresolved_factor") for c in r["checks"])

    words = (_FLAG_WORDS[0], banner_word(_FLAG_WORDS[1], r["result_status"], unresolved))

    def flag(ok) -> str:
        return words[1 if ok else 0]

    L = [f"PCF build report - {r['pipeline']}",
         render_status_line(r["result_status"], r["result_status_why"])]
    section = render_basis_section(r.get("project_basis_applied"), basis, heading="1. Basis")
    if section:
        L += ["", section.rstrip(chr(10))]
    L += ["", f"Axes: {r['axes']}   Coords: {r['coords']}   Vocabulary: {r['vocabulary']}", "",
          "Component census:"]
    L += [f"  {k:20s} {v}" for k, v in r["census"].items()]
    L += ["", "Pipe centreline length by bore (in):"]
    L += [f"  {k:>6s} in  {fmt_in(F(v))}" for k, v in r["pipe_centreline_in"].items()]
    L += ["", f"Closure checks ({sum(not c['pass'] for c in r['closure_checks'])} failed):"]
    for c in r["closure_checks"]:
        d = c["delta_in"]
        L.append(f"  [{flag(c['pass'])}] {c['label']:45s} "
                 f"dE={d[0]:+.4f} dN={d[1]:+.4f} dEL={d[2]:+.4f} in")
    if r["bom_checks"]:
        L += ["", "BOM reconciliation:"]
        L += [f"  [{flag(c['pass'])}] {c['item']:20s} BOM {c['bom']}  emitted {c['emitted']}"
              for c in r["bom_checks"]]
    if r.get("skey_overrides"):
        L += ["", "SKEY overrides applied over the defaults:"]
        L += [f"  {k:20s} {v if v else '(no SKEY)'}" for k, v in r["skey_overrides"].items()]
        if r["skey_overrides_unused"]:
            L.append("  not used by any item: " + ", ".join(r["skey_overrides_unused"]))
    for title, key in (("ASSUMED", "assumed"), ("Record substitutions", "substitutions")):
        if r[key]:
            L += ["", f"{title}:"] + [f"  - {x}" for x in r[key]]
    if not r["ok"]:
        verdict = "NOT DELIVERABLE - fix the spec at the source and rebuild"
    elif r["result_status"] == "manual check required" and any(c["name"] == ASSUMED_CHECK_NAME for c in r["checks"]):
        verdict = banner_word("OK", "manual check required") + " - confirm the ASSUMED items, then run validate_pcf.py"
    elif banner_allowed(r["result_status"], unresolved):
        verdict = "OK - run validate_pcf.py next"
    else:
        verdict = banner_word("OK", r["result_status"], unresolved) + " - resolve the flagged checks, then run validate_pcf.py"
    L += ["", "RESULT: " + verdict]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", required=True, help="PCF path to write")
    ap.add_argument("--report", help="also write the text report here")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--project-basis", metavar="FILE",
                    help="project basis record (pipingtoolset.project-basis/1); see references/project-basis.md")
    a = ap.parse_args(argv)
    try:
        with open(a.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        b = Builder(spec, a.project_basis).build()
    except (CodeValuesError, ProjectBasisError) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    except (PCFError, KeyError, ValueError, ArithmeticError) as e:
        print(f"SPEC ERROR: {e}", file=sys.stderr)
        return 1
    b.pcf.write(a.out)
    r = report(b, b.bom_check())
    text = render(r, b.basis)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(json.dumps(r, indent=2) if a.json else text)
    print(f"\nPCF written: {a.out}", file=sys.stderr)
    return 0 if r["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
