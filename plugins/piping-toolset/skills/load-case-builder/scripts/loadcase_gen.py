#!/usr/bin/env python3
"""
loadcase_gen.py - B31-compliant static load case set generator for CAESAR II / AutoPIPE.

Part of the PipingToolset skill pack (pipingtoolset.com).

WHY THIS EXISTS
    Hand-maintained load case templates break in one specific way: every combination
    case references other cases by NUMBER (L4-L30, L30+L37). Insert one operating
    state and every downstream reference silently points at the wrong case. The
    analysis still runs. The numbers are still plausible. The calc is wrong.

    This generator holds every reference SYMBOLICALLY and resolves to L-numbers in a
    single final pass, so a reference can never go stale. Numbers are an output,
    never an input.

DESIGN BASIS
    CAESAR II load-case semantics as published by COADE / Hexagon (component letters,
    hanger-design sequence, Suppress on intermediate cases, combination methods), the
    nonlinear-restraint argument for the three-tier occasional pattern, ASME B31.1 /
    B31.3 / B31E occasional-load clauses, and ASCE 7 Chapter 13. Clause-level
    citations are in SKILL.md. No tabulated code values are embedded here.

USAGE
    python loadcase_gen.py --example                  # built-in two-state B31.3 example
    python loadcase_gen.py --spec my_job.json         # your project spec
    python loadcase_gen.py --spec my_job.json --format csv > cases.csv
    python loadcase_gen.py --spec my_job.json --format json
    python loadcase_gen.py --spec my_job.json --project-basis project-basis.json

    Exit status: 0 = built, 2 = spec error (unknown or forward reference, bad field).

    A project basis record (pipingtoolset.project-basis/1, the spec key "project_basis" or
    --project-basis <file>; both given and different exits 2) fills code, edition,
    thermal_states and primary_state where the spec leaves them out; a spec value that differs
    exits 2 with "project_basis.<path> conflicts with input <name>". The report and the JSON
    carry result_status (the five-word taxonomy) and checks[]; spec-format.md has both.

    A spec key "code_values" (the optional block the other PipingToolset calculators take,
    {input name: {value, unit, citation, source}}) may be absent, null or empty. This generator
    has no code-table inputs, so a block with any entry exits 2 with
    "code_values.<name> is not an input of loadcase_gen.py": a value is never dropped silently.

COVERAGE
    Every thermal state x every friction multiplier reaches Maximum Operating and every
    extraction-matrix row it can govern; HYD and inter-state ranges are generated per
    friction multiplier. An occasional with an ASD "scale" keeps it on the code-stress path
    and gets an unreduced companion (block OPE+OCC-UNRED) that feeds Maximum Operating,
    support loads and displacements. "primary_state" and "hanger_friction" set the hanger
    design pair only; they never limit coverage. The resolved case set is checked against
    the spec after numbering (qc-gate.md item 17) and returned as "qc" in the JSON output.

UNITS / CONVENTIONS
    Y is vertical (CAESAR II default). Friction values are CAESAR II FRICTION
    MULTIPLIERS on the modelled mu, not mu itself.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal


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


# --------------------------------------------------------------------------------------
# Domain model
# --------------------------------------------------------------------------------------

StressType = Literal["HGR", "HYD", "OPE", "SUS", "EXP", "OCC", "FAT"]
Method = Literal["", "Algebraic", "Scalar", "ABS", "SRSS", "Max", "Min", "SignMax", "SignMin"]

# Occasional kinds that each get their own Max envelope. Wind and earthquake are never
# combined with each other (B31.1 101.5.2; B31.3 302.3.6(a)).
ENVELOPE_KINDS = ("psv", "seismic", "snow", "wind", "other")


@dataclass
class ThermalState:
    """One operating condition: a paired temperature / pressure / displacement set."""
    key: str                      # symbolic handle, e.g. "op"
    name: str                     # "OPERATING CASE CONDITION"
    T: str                        # "T1"
    P: str                        # "P1"
    D: str | None = None          # "D1" or None
    role: str = "operating"       # "operating" | "design" | "upset" | "steamout" | ...
    cycles: int | None = None     # N for this state, for the f-factor / FAT work


@dataclass
class Occasional:
    """One occasional load vector riding on one thermal state, in one direction."""
    key: str                      # "seis_px"
    name: str                     # "Seismic +X"
    vector: str                   # "U1", "WIN1", "F1"
    sign: str = "+"               # "+" or "-"
    base: str = "op"              # ThermalState.key this rides on
    kind: str = "other"           # one of ENVELOPE_KINDS
    scale: float | None = None    # ASD reduction (0.6 wind / 0.7 seismic) only if policy says so


@dataclass
class Case:
    """A single CAESAR II static load case."""
    key: str
    block: str
    stress: StressType
    desc: str
    terms: list[str] = field(default_factory=list)            # primitive: ["W","D1","T1","P1","H"]
    refs: list[tuple[int, str]] = field(default_factory=list)  # combination: [(+1,"key"),(-1,"key")]
    method: Method = ""
    friction: float | None = None
    hanger: str | None = None                                 # "Rigid" | "Ignore" | "As Designed"
    suppress: bool = False
    number: int = 0                                           # assigned at resolve time

    @property
    def is_combination(self) -> bool:
        return bool(self.refs)


class SpecError(ValueError):
    """The project spec cannot produce a valid case set."""


def _edition_year(edition: str) -> int | None:
    digits = "".join(ch for ch in edition if ch.isdigit())
    return int(digits[:4]) if len(digits) >= 4 else None


# --------------------------------------------------------------------------------------
# Project basis record (B8): this generator's fill map. The shared block above validates,
# fills and conflicts; only the mapping lives here.
# --------------------------------------------------------------------------------------

# Record states with these roles are not thermal states of a case set (the hydrotest is block 2,
# the installed state is the reference temperature), so they never become thermal_states.
_NOT_THERMAL_ROLES = ("hydrotest", "pneumatic", "installed")


def _state_record(s: dict[str, Any]) -> dict[str, Any]:
    """A spec thermal state with the ThermalState defaults explicit, so fill-or-conflict compares
    meaning, not spelling (an omitted role is "operating", an omitted D or cycles is null)."""
    out = dict(s)
    for k, v in (("D", None), ("role", "operating"), ("cycles", None)):
        out.setdefault(k, v)
    return out


def _basis_thermal_states(basis: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """(thermal states built from the record's slotted states, keys of states with no T/P slot)."""
    built: list[dict[str, Any]] = []
    unslotted: list[str] = []
    for st in basis.get("states") or []:
        if st.get("role") in _NOT_THERMAL_ROLES:
            continue
        slot = st.get("slot") or {}
        if not slot.get("T") or not slot.get("P"):
            unslotted.append(st["key"])
            continue
        built.append({"key": st["key"], "name": st.get("name") or st["key"], "T": slot["T"],
                      "P": slot["P"], "D": slot.get("D"), "role": st.get("role") or "operating",
                      "cycles": st.get("cycles")})
    return built, unslotted


def apply_project_basis(spec: dict[str, Any], basis: dict[str, Any] | None
                        ) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    """(effective spec, project_basis_applied, notes) for this generator's fill map:
    code and edition from code; thermal_states from states (key, name, role, cycles, slot
    T/P/D); primary_state from the first operating state, else the first state; the software,
    owner practice and assumptions are read for the report only. (spec, None, []) without a record."""
    if basis is None:
        return spec, None, []
    spec = dict(spec)
    ed = spec.get("edition")
    if isinstance(ed, (int, float)) and not isinstance(ed, bool):
        spec["edition"] = str(ed)                        # the generator reads str(edition) anyway
    given = spec.get("thermal_states")
    if isinstance(given, list):
        spec["thermal_states"] = [_state_record(s) if isinstance(s, dict) else s for s in given]
    built, unslotted = _basis_thermal_states(basis)
    fill_map: list[tuple[str, str, Any]] = [("code", "code.standard", None),
                                            ("edition", "code.edition", None)]
    notes: list[str] = []
    if unslotted:
        if given is None:
            raise ProjectBasisError(f"project_basis.states[key={unslotted[0]}].slot needs T and P to "
                                    "fill thermal_states (or give thermal_states in the spec)")
        notes.append(f"NOTE: project basis state(s) {', '.join(unslotted)} carry no T/P slot, so "
                     "thermal_states and primary_state are the spec's, not checked against the record.")
    elif built:
        primary = next((s["key"] for s in built if s["role"] == "operating"), built[0]["key"])
        fill_map.append(("thermal_states", "states", lambda _v: built))
        fill_map.append(("primary_state", "states[role=operating|first].key", lambda _v: primary))
    eff, applied = fill_from_basis(spec, basis, fill_map)
    software = basis_get(basis, "load_case_ids.software")
    if software:
        mark_basis_used(applied, "load_case_ids.software", "--format")
        if software == "AutoPIPE":
            notes.append("NOTE: project basis software is AutoPIPE; run --format autopipe for the "
                         "component map and confirm the occasional construction in AutoPIPE.")
    for i, practice in enumerate(basis.get("owner_practice") or []):
        mark_basis_used(applied, f"owner_practice[{i}]")
        if any("friction" in str(item).lower() for item in practice.get("items") or []) \
                and len(eff.get("frictions") or [[0, 1.0], [0, 0.0]]) < 2:
            notes.append(f"NOTE: owner practice {practice['document']} carries a friction item but "
                         "the spec runs one friction multiplier; run with and without friction.")
    if applied["assumptions"]:
        mark_basis_used(applied, "assumptions")
    return eff, applied, notes


def resolve_project_basis(spec: Any, cli_path: str | None = None
                          ) -> tuple[Any, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Pop the spec's project_basis key, load it and/or --project-basis, apply this fill map.
    Returns (effective spec, basis, applied, notes); the spec object itself when neither is given."""
    if not isinstance(spec, dict) or ("project_basis" not in spec and not cli_path):
        return spec, None, None, []
    rest = {k: v for k, v in spec.items() if k != "project_basis"}
    basis = load_project_basis(cli_path, spec.get("project_basis"))
    if basis is None:
        return rest, None, None, []
    eff, applied, notes = apply_project_basis(rest, basis)
    return eff, basis, applied, notes


# --------------------------------------------------------------------------------------
# Result status (B9): this generator's checks. Six QC items are evaluated here; the other
# eleven need the model and are listed as "not checked" (qc-gate.md).
# --------------------------------------------------------------------------------------

NOT_CHECKED_QC_ITEMS: tuple[tuple[int, str], ...] = (
    (1, "stale cross-references against the model's case descriptions"),
    (2, "envelope completeness in the model file"),
    (3, "direction labels against the vectors in the model"),
    (6, "linear shortcut on a nonlinear model"),
    (8, "pure occasional cases set to Suppress in the model"),
    (9, "friction variants run, governing result taken, both documented"),
    (12, "hanger Rigid / Ignore cases in the model, carrying no H"),
    (13, "expansion range brackets the true extremes"),
    (14, "wind shape factor and first-node elevation"),
    (15, "SAM and settlement in the expansion check"),
    (16, "no static seismic with anchor movements; no static water hammer"),
)


# --------------------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------------------

class LoadCaseSet:
    """Builds, resolves and renders a complete static load case set."""

    def __init__(self, spec: dict[str, Any], project_basis_file: str | None = None) -> None:
        try:
            spec, self.basis, self.basis_applied, self.basis_notes = resolve_project_basis(
                spec, project_basis_file)
        except ProjectBasisError as exc:
            raise SpecError(str(exc)) from exc
        self.spec = spec
        cv = spec.get("code_values")                            # no code-table slots here: absent, null or empty only
        if cv is not None and not isinstance(cv, dict):
            raise SpecError("code_values must be an object (this generator has no code-table inputs)")
        if cv:
            raise SpecError(f"code_values.{next(iter(cv))} is not an input of loadcase_gen.py "
                            "(this generator has no code-table inputs)")
        try:
            self.code: str = spec["code"]                       # "B31.1" | "B31.3"
            self.states = [ThermalState(**s) for s in spec["thermal_states"]]
            self.occ = [Occasional(**o) for o in spec.get("occasionals", [])]
        except (KeyError, TypeError) as exc:
            raise SpecError(f"spec is missing or has an unknown field: {exc}") from exc
        if self.code not in ("B31.1", "B31.3"):
            raise SpecError(f"code must be 'B31.1' or 'B31.3', got {self.code!r}")
        if not self.states:
            raise SpecError("thermal_states must list at least one operating state")
        self.edition: str = str(spec.get("edition", "UNSTATED"))
        self.frictions: list[tuple[str, float]] = [tuple(f) for f in spec.get(
            "frictions", [["w/ Friction", 1.0], ["w/o Friction", 0.0]])]
        self.hangers: bool = spec.get("hangers", True)
        self.hydrotest: bool = spec.get("hydrotest", True)
        self.inter_state_ranges: bool = spec.get("inter_state_expansion_ranges", True)
        self.occ_combine: Method = spec.get("occ_combine_method", "Scalar")  # Scalar or ABS
        self.cases: list[Case] = []
        self.findings: list[str] = []
        self.qc: dict[str, Any] = {}
        self.checks: list[dict[str, Any]] = []
        self.result_status: str = "not checked"
        if not self.frictions:
            raise SpecError("frictions must list at least one [label, multiplier] pair")
        for _, fv in self.frictions:
            if isinstance(fv, bool) or not isinstance(fv, (int, float)) or fv < 0:
                raise SpecError(f"friction multiplier must be a number >= 0, got {fv!r}")
        for label, keys in (("thermal state", [s.key for s in self.states]),
                            ("occasional", [o.key for o in self.occ]),
                            # compared as numbers so 1 and 1.0 are one multiplier
                            ("friction multiplier", [float(fv) for _, fv in self.frictions])):
            dup = sorted({k for k in keys if keys.count(k) > 1})
            if dup:
                # Case keys are built from these handles; a duplicate would make two cases
                # share one key and a reference resolve to the wrong one.
                raise SpecError(f"duplicate {label} {dup[0]!r}: every {label} must be unique")
        self._by_state = {s.key: s for s in self.states}
        for o in self.occ:
            if o.base not in self._by_state:
                raise SpecError(f"occasional {o.key!r} rides on unknown state {o.base!r}")
            if o.kind not in ENVELOPE_KINDS:
                raise SpecError(f"occasional {o.key!r} has kind {o.kind!r}; "
                                f"use one of {', '.join(ENVELOPE_KINDS)}")
            # scale is an ASD reduction: a number strictly between 0 and 1. 0 (falsy) used
            # to read as unscaled, and >= 1 was labelled REDUCED; both are refused now.
            if o.scale is not None and (isinstance(o.scale, bool)
                                        or not isinstance(o.scale, (int, float))
                                        or not 0 < o.scale < 1):
                raise SpecError(f"occasional {o.key!r} has scale {o.scale!r}; scale is an ASD "
                                "reduction factor, a number with 0 < scale < 1 (omit it for an "
                                "unreduced occasional)")
        # Primary state: hanger design and the rows the matrix labels "primary". It never
        # limits coverage - every state is enveloped and extracted whatever it is set to.
        ps = spec.get("primary_state")
        if ps is not None and ps not in self._by_state:
            raise SpecError(f"primary_state {ps!r} is not the key of a declared thermal state")
        self.primary_state_declared: bool = ps is not None
        self.primary: ThermalState = self._by_state[ps] if ps is not None else self.states[0]
        # Friction multiplier for the hanger design pair (CAESAR II runs one recommended pair).
        hf = spec.get("hanger_friction")
        if hf is not None and (isinstance(hf, bool) or not isinstance(hf, (int, float)) or hf < 0):
            raise SpecError(f"hanger_friction must be a friction multiplier >= 0, got {hf!r}")
        self.hanger_friction_declared: bool = hf is not None
        self.hanger_friction: float = float(hf) if hf is not None else self.frictions[0][1]

    # -- helpers ------------------------------------------------------------------------

    def _add(self, c: Case) -> Case:
        self.cases.append(c)
        return c

    def _primitive_terms(self, st: ThermalState, *, thermal: bool, hanger: bool) -> list[str]:
        """W [+D] [+T] +P [+H]. Sustained drops D and T; that is the whole difference."""
        terms = ["W"]
        if thermal:
            if st.D:
                terms.append(st.D)
            terms.append(st.T)
        terms.append(st.P)
        if hanger and self.hangers:
            terms.append("H")
        return terms

    @staticmethod
    def _k(*parts: str) -> str:
        return ":".join(parts)

    def _max_ope_members(self) -> list[str]:
        """Maximum Operating: per friction, each state's OPE case followed by the OPE+OCC
        cases riding on that state (unreduced companion where the occasional is scaled)."""
        out: list[str] = []
        for _, fv in self.frictions:
            for st in self.states:
                out.append(self._k("ope", st.key, str(fv)))
                out += [self._load_occ_key(o, fv) for o in self.occ if o.base == st.key]
        return out

    # -- blocks -------------------------------------------------------------------------

    def _block_hanger(self) -> None:
        """Hanger design, CAESAR II's recommended pair: W with springs Rigid sizes the load;
        W+T<primary state's T slot> with springs Ignored sizes the travel. H is the OUTPUT
        of these two cases, so it first appears in the As-Designed cases that follow. Both
        must precede them.
        The pair is run once, for the primary state (spec primary_state, default the first
        declared) at one friction multiplier (spec hanger_friction, default the first
        declared); both are stated in the QC findings and the extraction matrix."""
        if not self.hangers:
            return
        primary = self.primary
        self._add(Case(key="hgr:rigid", block="HGR", stress="HGR", desc="WEIGHT FOR HANGER LOADS",
                       terms=["W"], hanger="Rigid", friction=self.hanger_friction))
        self._add(Case(key="hgr:travel", block="HGR", stress="HGR",
                       desc="OPERATING FOR HANGER TRAVEL",
                       terms=["W", primary.T],
                       hanger="Ignore", friction=self.hanger_friction))

    def _block_hydro(self) -> None:
        """WW = water-filled weight, HP = hydro pressure. Insulation weight in the hydro case
        is a CAESAR II configuration choice; state it. The hydrotest is run once per
        friction variant like every other primitive case, so a support load or movement that
        governs only with friction off reaches the hydrotest extraction too. Whether your
        CAESAR II version applies the friction multiplier to the HYD case is NOT asserted
        here; confirm it in the program before relying on the w/o Friction HYD case."""
        if not self.hydrotest:
            return
        terms = ["WW", "HP"] + (["H"] if self.hangers else [])
        for fname, fval in self.frictions:
            self._add(Case(key=self._k("hyd", str(fval)), block="HYD", stress="HYD",
                           desc=f"HYDRO TEST CASE ({fname})", terms=terms, friction=fval))

    def _block_operating(self) -> None:
        """Base operating cases: every thermal state x every friction multiplier."""
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("ope", st.key, str(fval)), block="OPE", stress="OPE",
                               desc=f"{st.name} {fname}",
                               terms=self._primitive_terms(st, thermal=True, hanger=True),
                               friction=fval, hanger="As Designed" if self.hangers else None))

    def _block_operating_with_occ(self) -> None:
        """The occasional is solved FROM the operating position, because nonlinear restraint
        status (gaps, one-way supports, friction) differs there from the modelled position."""
        for fname, fval in self.frictions:
            for o in self.occ:
                st = self._by_state[o.base]
                term = f"{o.sign}{o.scale}{o.vector}" if o.scale else f"{o.sign}{o.vector}"
                terms = self._primitive_terms(st, thermal=True, hanger=True) + [term]
                # A scaled (ASD-reduced) case feeds the code-stress occasional path only; its
                # label says so. The unscaled description is unchanged from 0.7.0.
                occ_name = f"{o.scale} {o.name} REDUCED" if o.scale else o.name
                self._add(Case(key=self._k("opeocc", o.key, str(fval)), block="OPE+OCC",
                               stress="OPE", desc=f"{st.name} with {occ_name} ({fname})",
                               terms=terms, friction=fval,
                               hanger="As Designed" if self.hangers else None))

    def _block_operating_with_occ_unreduced(self) -> None:
        """Unreduced companions of every ASD-scaled OPE+OCC case (owner ruling 2026-10-30).
        The reduced case keeps the scale for the code-stress occasional path; the support-
        load and displacement extraction and the Maximum Operating envelope read these
        instead, so a 0.6W / 0.7E factor never reaches a reaction or a movement. No case is
        added when no occasional carries a scale, so an unscaled set is unchanged."""
        for fname, fval in self.frictions:
            for o in self.occ:
                if not o.scale:
                    continue
                st = self._by_state[o.base]
                terms = self._primitive_terms(st, thermal=True, hanger=True) + [f"{o.sign}{o.vector}"]
                self._add(Case(key=self._k("opeoccu", o.key, str(fval)), block="OPE+OCC-UNRED",
                               stress="OPE", desc=f"{st.name} with {o.name} UNREDUCED ({fname})",
                               terms=terms, friction=fval,
                               hanger="As Designed" if self.hangers else None))

    def _load_occ_key(self, o: Occasional, fval: float) -> str:
        """The OPE+OCC case that feeds support loads and displacements for one occasional:
        the unreduced companion when the occasional is scaled, otherwise the case itself."""
        return self._k("opeoccu" if o.scale else "opeocc", o.key, str(fval))

    def _block_sustained(self) -> None:
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("sus", st.key, str(fval)), block="SUS", stress="SUS",
                               desc=f"SUSTAINED {st.name} ({fname})",
                               terms=self._primitive_terms(st, thermal=False, hanger=True),
                               friction=fval, hanger="As Designed" if self.hangers else None))

    def _block_expansion(self) -> None:
        """EXP = OPE - SUS, Algebraic. Plus inter-state ranges: when one leg runs hot and
        another cold, the governing range is between two operating states, not between
        either one and ambient."""
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("exp", st.key, str(fval)), block="EXP", stress="EXP",
                               desc=f"EXPANSION {st.name} ({fname})", method="Algebraic",
                               refs=[(+1, self._k("ope", st.key, str(fval))),
                                     (-1, self._k("sus", st.key, str(fval)))]))
        # Inter-state ranges per friction multiplier, like the single-state EXP cases: a
        # range that governs only with friction off must exist as a case.
        if self.inter_state_ranges and len(self.states) > 1:
            for i in range(len(self.states)):
                for j in range(i + 1, len(self.states)):
                    a, b = self.states[i], self.states[j]
                    for fname, fval in self.frictions:
                        self._add(Case(key=self._k("exprange", a.key, b.key, str(fval)), block="EXP",
                                       stress="EXP",
                                       desc=f"EXPANSION RANGE {a.name} to {b.name} ({fname})",
                                       method="Algebraic",
                                       refs=[(+1, self._k("ope", a.key, str(fval))),
                                             (-1, self._k("ope", b.key, str(fval)))]))

    def _block_pure_occasional(self) -> None:
        """(OPE + occ) - OPE, Algebraic. Intermediate only, so output is suppressed."""
        for fname, fval in self.frictions:
            for o in self.occ:
                self._add(Case(key=self._k("pure", o.key, str(fval)), block="OCC-PURE", stress="OCC",
                               desc=f"Pure {o.name} ({fname})", method="Algebraic", suppress=True,
                               refs=[(+1, self._k("opeocc", o.key, str(fval))),
                                     (-1, self._k("ope", o.base, str(fval)))]))

    def _block_code_occasional(self) -> None:
        """SUS + pure occ, Scalar. Scalar sums the STRESSES, which is the form the code
        check needs (S_L + S_L,occ <= k*Sh). Algebraic here would be wrong."""
        for fname, fval in self.frictions:
            for o in self.occ:
                self._add(Case(key=self._k("occ", o.key, str(fval)), block="OCC-CODE", stress="OCC",
                               desc=f"{o.name} Code Stress Case ({fname})", method=self.occ_combine,
                               refs=[(+1, self._k("sus", o.base, str(fval))),
                                     (+1, self._k("pure", o.key, str(fval)))]))

    def _block_envelopes(self) -> None:
        """Max envelopes. The overall occasional envelope must include every occasional kind;
        an envelope that omits one silently drops it from the code check."""
        # Every thermal state x every friction variant: a reaction or movement that governs
        # in a non-primary state, or only with friction off, must still reach the support-
        # load and displacement envelope. Scaled occasionals enter through their unreduced
        # companions, never through the reduced (code-stress) case.
        self._add(Case(key="max:ope", block="MAX", stress="OPE", desc="Maximum Operating",
                       method="Max", refs=[(+1, k) for k in self._max_ope_members()]))

        group_keys: list[str] = []
        for kind in ENVELOPE_KINDS:
            members = [self._k("occ", o.key, str(f)) for _, f in self.frictions
                       for o in self.occ if o.kind == kind]
            if not members:
                continue
            gk = f"max:{kind}"
            self._add(Case(key=gk, block="MAX", stress="OCC",
                           desc=f"Maximum {kind.capitalize()} Occasional", method="Max",
                           refs=[(+1, m) for m in members]))
            group_keys.append(gk)

        if group_keys:
            self._add(Case(key="max:occ", block="MAX", stress="OCC", desc="Maximum Occasional",
                           method="Max", refs=[(+1, g) for g in group_keys]))

    # -- build / resolve ----------------------------------------------------------------

    def build(self) -> "LoadCaseSet":
        self._block_hanger()
        self._block_hydro()
        self._block_operating()
        self._block_operating_with_occ()
        self._block_operating_with_occ_unreduced()
        self._block_sustained()
        self._block_expansion()
        self._block_pure_occasional()
        self._block_code_occasional()
        self._block_envelopes()
        self._resolve()
        self._qc()
        return self

    def _resolve(self) -> None:
        """Assign L-numbers in list order, then verify every symbolic reference points
        BACKWARD. A forward reference is a hard error, not a warning."""
        for i, c in enumerate(self.cases, start=1):
            c.number = i
        index = {c.key: c for c in self.cases}
        for c in self.cases:
            for _, ref in c.refs:
                if ref not in index:
                    raise SpecError(f"L{c.number} '{c.desc}' references unknown case '{ref}'")
                if index[ref].number >= c.number:
                    raise SpecError(
                        f"L{c.number} '{c.desc}' references L{index[ref].number} which is not "
                        f"earlier in the set. CAESAR II combination cases must reference "
                        f"previously defined cases.")

    def combo_string(self, c: Case) -> str:
        if not c.is_combination:
            s = c.terms[0]
            for t in c.terms[1:]:
                s += t if t[0] in "+-" else f"+{t}"
            return s
        index = {x.key: x for x in self.cases}
        if c.method == "Max":
            return ", ".join(f"L{index[r].number}" for _, r in c.refs)
        out = ""
        for sign, ref in c.refs:
            n = index[ref].number
            out += (f"L{n}" if not out else (f"+L{n}" if sign > 0 else f"-L{n}"))
        return out

    # -- QC -----------------------------------------------------------------------------

    def _qc(self) -> None:
        f = self.findings
        year = _edition_year(self.edition)
        if self.edition == "UNSTATED" or year is None:
            f.append("BASIS: code edition not stated. An undeclared edition is a review finding.")

        if len(self.states) > 1 and not self.primary_state_declared:
            f.append(f"ASSUMED: primary state = {self.primary.key} (first declared) for the hanger "
                     "design pair and the primary-labelled matrix rows. Set primary_state to the "
                     "maximum operating state to confirm it. Coverage does not depend on it: every "
                     "state is enveloped and extracted.")
        if self.hangers and not self.hanger_friction_declared:
            f.append(f"ASSUMED: hanger design pair (W Rigid, W+{self.primary.T} Ignore) runs at "
                     f"friction multiplier {self.hanger_friction:.1f} (first declared friction "
                     "variant). Set hanger_friction to confirm it.")

        kinds = {o.kind for o in self.occ}
        if "seismic" in kinds and "wind" in kinds:
            f.append("OK: wind and seismic are separate envelopes; they are never combined "
                     "(B31.1 101.5.2; B31.3 302.3.6(a)).")

        # Vertical seismic
        vert = [o for o in self.occ if o.kind == "seismic" and o.vector.upper() == "U2"]
        seis = [o for o in self.occ if o.kind == "seismic"]
        snow = [o for o in self.occ if o.kind == "snow"]
        if seis and not vert:
            f.append("GAP: no vertical seismic component. ASCE 7 Ch. 13 requires concurrent "
                     "Ev = 0.2*SDS*Wp. U2 is the only vertical uniform vector in CAESAR II.")
        if snow and any(o.vector.upper() == "U2" for o in snow) and seis and not vert:
            f.append("CONFLICT: U2 carries snow, so no vector remains for Ev. 'Uniform Load in "
                     "G's' is a GLOBAL flag, so a snow vector entered in lb/ft while it is on "
                     "is read as g's. Dedicate U2 to Ev and carry snow as weight, or run snow "
                     "and seismic as separate sets.")

        # Envelope completeness
        env = next((c for c in self.cases if c.key == "max:occ"), None)
        if env:
            covered = {r.split(":")[1] for _, r in env.refs}
            missing = kinds - covered
            if missing:
                f.append(f"ERROR: Maximum Occasional envelope omits {sorted(missing)}.")
            else:
                f.append("OK: Maximum Occasional envelope covers every occasional kind present.")

        # Friction policy
        if len(self.frictions) < 2:
            f.append("NOTE: only one friction multiplier. Where PIP PNC00004 is invoked, "
                     "3.2.3 requires running with and without friction and taking the "
                     "governing result.")

        # Occasional allowable
        if self.code == "B31.3":
            f.append("ALLOWABLE: B31.3 302.3.6(a) - sustained + occasional <= 1.33*Sh (flat); "
                     "Chapter IX high-pressure piping uses 1.20 (K302.3.6(a)).")
        else:
            f.append("ALLOWABLE: B31.1 104.8.2 - k = 1.15 (<= 8 h at one time AND <= 800 h/yr) "
                     "or 1.20 (<= 1 h AND <= 80 h/yr). Set the CAESAR II occasional factor to "
                     "match and write the duration justification into the calc.")

        # ASD reduction policy - the software documentation, the software wizard and the code
        # do not agree; the position must be stated either way.
        scaled = [o for o in self.occ if o.scale]
        companions = (f"Unreduced companions ({len(scaled) * len(self.frictions)} OPE+OCC-UNRED "
                      "cases) are generated for every scaled occasional x friction and feed "
                      "Maximum Operating, support loads and displacements; the REDUCED cases "
                      "feed the code-stress occasional path only.")
        if self.code == "B31.1" and scaled:
            if year is not None and year >= 2024:
                f.append("ERROR: B31.1-2024 101.5.2 / 101.5.3 state the ASD reduction factor "
                         "shall not be applied, but occasional terms carry a scale factor. "
                         "Remove it. " + companions)
            else:
                f.append("CHECK: occasional terms carry an ASD scale factor under B31.1 "
                         f"{self.edition}. B31.1-2024 prohibits it; for earlier editions cite "
                         "the owner or EOR direction that permits it. " + companions)
        elif scaled:
            f.append("ASD: 0.6W / 0.7E reduction applied for stress. B31.3 is silent on the "
                     "factor; cite the owner or EOR direction. " + companions)
        elif self.occ:
            f.append("ASD: no 0.6W / 0.7E reduction applied (strength level). This matches "
                     "B31.1-2024 and the conservative reading of B31.3, and differs from the "
                     "CAESAR II help topic on ASCE 7 load combinations. State the position "
                     "and who accepted it.")

        # Expansion completeness
        n_exp = sum(1 for c in self.cases if c.block == "EXP" and c.key.startswith("exp:"))
        expect = len(self.states) * len(self.frictions)
        if n_exp < expect:
            f.append(f"GAP: {n_exp} expansion cases for {expect} state x friction pairs.")

        # Resolved case set against the declared spec (qc-gate.md item 17)
        self.qc = self._qc_case_set()
        q = self.qc
        if q["pass"]:
            c = q["counts"]
            extra = []
            if c["scaled_occasionals"]:
                extra.append(f"{c['scaled_occasionals']} scaled with unreduced companions")
            if c["state_pairs_ranged"]:
                extra.append(f"{c['state_pairs_ranged']} inter-state pairs")
            f.append(f"QC: resolved case set complete - {c['generated_cases']} cases match the "
                     f"{c['expected_cases']} the spec declares ({c['states']} states x "
                     f"{c['frictions']} friction variants, {c['occasionals']} occasionals"
                     + (", " + ", ".join(extra) if extra else "") + f"); {c['checks']} "
                     "coverage, reference, envelope and matrix checks, 0 misses.")
        else:
            shown = q["misses"][:10]
            more = len(q["misses"]) - len(shown)
            f.append(f"ERROR: resolved case set has {len(q['misses'])} miss(es): "
                     + "; ".join(shown)
                     + (f"; (+{more} more in the JSON qc block)" if more > 0 else "")
                     + ". Do not issue this set.")

        f.extend(self.basis_notes)
        self._status()

    def _status(self) -> None:
        """checks[] and result_status (B9). The envelope word is the shared envelope_status
        ("not checked" rows are listed, never the word); every ASSUMED item (the generator's and
        the record's) goes into the one shared "ASSUMED inputs" row. QC findings keep their OK
        prefix: they are check results, not a banner."""
        f = self.findings
        year = _edition_year(self.edition)
        chk: list[dict[str, Any]] = []
        assumed = [x[len("ASSUMED: "):] for x in f if x.startswith("ASSUMED: ")]
        assumed += [a["item"] for a in (self.basis_applied or {}).get("assumptions", [])]
        row = assumed_inputs_check([x.split(". ")[0].rstrip(".") for x in assumed])  # the item, not the advice
        if row is not None:
            chk.append(row)
        unstated = self.edition == "UNSTATED" or year is None
        chk.append(make_check("code edition", "manual check required" if unstated else "calculated",
                              "na" if unstated else "pass",
                              "edition not stated; the occasional factor and the B31.1-2024 ASD rule "
                              "depend on it" if unstated else f"{self.code} {self.edition}"))
        seis = any(o.kind == "seismic" for o in self.occ)
        bad4 = any(x.startswith(("GAP: no vertical seismic", "CONFLICT: U2")) for x in f)
        chk.append(make_check("QC 4 vertical seismic and U2", "calculated",
                              "na" if not seis else ("fail" if bad4 else "pass"),
                              "no seismic occasional" if not seis else
                              ("vertical seismic missing or U2 double-booked" if bad4
                               else "a vertical seismic component is present; U2 is not double-booked")))
        bad5 = any(x.startswith("GAP: ") and "expansion cases for" in x for x in f)
        chk.append(make_check("QC 5 expansion completeness", "calculated", "fail" if bad5 else "pass",
                              "one EXP case per state x friction"))
        chk.append(make_check("QC 7 forward references", "calculated", "pass",
                              "every combination references an earlier case (a forward one exits 2)"))
        if not self.occ:
            chk.append(make_check("QC 10 occasional factor", "calculated", "na", "no occasional load"))
        elif self.code == "B31.3":
            hp = (basis_get(self.basis, "service.fluid_category") == "High Pressure"
                  or "chapter ix" in str(basis_get(self.basis, "code.route", "")).lower())
            chk.append(make_check("QC 10 occasional factor", "calculated", "na",
                                  "the record names Chapter IX / High Pressure service, so "
                                  "K302.3.6(a) 1.20 Sh applies; set it in the model" if hp else
                                  "302.3.6(a) 1.33 Sh (1.20 under Chapter IX); set it in the model"))
        else:
            chk.append(make_check("QC 10 occasional factor", "manual check required", "na",
                                  "104.8.2 k = 1.15 or 1.20 depends on the occasional duration, "
                                  "which is not an input; write the justification into the calc"))
        scaled = any(o.scale for o in self.occ)
        if not self.occ:
            chk.append(make_check("QC 11 ASD position", "calculated", "na", "no occasional load"))
        elif not scaled:
            chk.append(make_check("QC 11 ASD position", "calculated", "pass",
                                  "strength level, no 0.6W / 0.7E reduction"))
        elif self.code == "B31.1" and year is not None and year >= 2024:
            chk.append(make_check("QC 11 ASD position", "calculated", "fail",
                                  "B31.1-2024 101.5.2 / 101.5.3 prohibit the reduction"))
        else:
            chk.append(make_check("QC 11 ASD position", "manual check required", "na",
                                  "a 0.6W / 0.7E reduction needs the owner or EOR written direction, "
                                  "which the generator cannot verify"))
        chk.append(make_check("QC 17 resolved case set", "calculated",
                              "pass" if self.qc.get("pass") else "fail",
                              f"{self.qc['counts']['misses']} miss(es) in "
                              f"{self.qc['counts']['checks']} checks"))
        for item, what in NOT_CHECKED_QC_ITEMS:
            chk.append(make_check(f"QC {item} {what}", "not checked", "na",
                                  "needs the model; check by hand (references/qc-gate.md)"))
        if self.hydrotest and len(self.frictions) > 1:
            chk.append(make_check("HYD friction multiplier in the software", "not checked", "na",
                                  "confirm the CAESAR II version applies it to the HYD case"))
        if basis_get(self.basis, "load_case_ids.software") == "AutoPIPE":
            chk.append(make_check("AutoPIPE occasional construction", "not checked", "na",
                                  "subtract-then-scalar is unconfirmed for AutoPIPE"))
        fields = status_fields(chk)
        self.checks, self.result_status = fields["checks"], fields["result_status"]

    def status_line(self) -> str:
        """'Result status: <word> - <why>' under the report title (shared render_status_line)."""
        rs = self.result_status
        fails = [c["name"] for c in self.checks if c["status"] == "fail"]
        n_nc = sum(1 for c in self.checks if c["result_status"] == "not checked")
        if rs == "manual check required":
            why = "confirm " + ", ".join(f"{c['name']} ({c['note']})" if c["name"] == ASSUMED_CHECK_NAME
                                         else c["name"] for c in self.checks if c["result_status"] == rs)
        else:
            why = "QC items 4, 5, 7, 10, 11 and 17 calculated"
        if fails:
            why += f"; fails: {', '.join(fails)}"
        why += f"; not performed by this module: {n_nc} items that need the model"
        return render_status_line(rs, why)

    def _qc_case_set(self) -> dict[str, Any]:
        """Compare the generated set with what the spec declares, independently of the
        block builders: every state x friction (OPE, SUS, EXP), every occasional x friction
        (OPE+OCC, pure, code OCC, and the unreduced companion when scaled), every state pair
        x friction when inter-state ranges are on, HYD per friction, the hanger pair, the
        envelope membership and the extraction matrix rows."""
        have = {c.key: c for c in self.cases}
        misses: list[str] = []
        checks = 0
        expected: set[str] = set()
        F = [str(fv) for _, fv in self.frictions]

        def need(key: str, what: str, refs: list[tuple[int, str]] | None = None) -> None:
            nonlocal checks
            checks += 1
            expected.add(key)
            c = have.get(key)
            if c is None:
                misses.append(f"missing {what} [{key}]")
            elif refs is not None and c.refs != refs:
                misses.append(f"{what} [{key}] references {c.refs}, expected {refs}")

        def refs_of(key: str) -> set[str]:
            c = have.get(key)
            return {r for _, r in c.refs} if c else set()

        def member(env: str, key: str, what: str) -> None:
            nonlocal checks
            checks += 1
            if key not in refs_of(env):
                misses.append(f"{what} [{key}] is not in {env}")

        if self.hangers:
            need("hgr:rigid", "hanger design Rigid case")
            need("hgr:travel", "hanger design travel case")
        if self.hydrotest:
            for fv in F:
                need(f"hyd:{fv}", f"HYD case at friction {fv}")
        for st in self.states:
            for fv in F:
                need(f"ope:{st.key}:{fv}", f"OPE {st.key} x friction {fv}")
                need(f"sus:{st.key}:{fv}", f"SUS {st.key} x friction {fv}")
                need(f"exp:{st.key}:{fv}", f"EXP {st.key} x friction {fv}",
                     [(+1, f"ope:{st.key}:{fv}"), (-1, f"sus:{st.key}:{fv}")])
        pairs = 0
        if self.inter_state_ranges and len(self.states) > 1:
            for i, a in enumerate(self.states):
                for b in self.states[i + 1:]:
                    pairs += 1
                    for fv in F:
                        need(f"exprange:{a.key}:{b.key}:{fv}",
                             f"inter-state range {a.key}-{b.key} x friction {fv}",
                             [(+1, f"ope:{a.key}:{fv}"), (-1, f"ope:{b.key}:{fv}")])
        load_occ: set[str] = set()
        for o in self.occ:
            for fv in F:
                need(f"opeocc:{o.key}:{fv}", f"OPE+OCC {o.key} x friction {fv}")
                need(f"pure:{o.key}:{fv}", f"pure occasional {o.key} x friction {fv}",
                     [(+1, f"opeocc:{o.key}:{fv}"), (-1, f"ope:{o.base}:{fv}")])
                need(f"occ:{o.key}:{fv}", f"code occasional {o.key} x friction {fv}",
                     [(+1, f"sus:{o.base}:{fv}"), (+1, f"pure:{o.key}:{fv}")])
                if o.scale:
                    need(f"opeoccu:{o.key}:{fv}", f"unreduced companion {o.key} x friction {fv}")
                    load_occ.add(f"opeoccu:{o.key}:{fv}")
                else:
                    load_occ.add(f"opeocc:{o.key}:{fv}")

        # Envelopes
        need("max:ope", "Maximum Operating envelope")
        for st in self.states:
            for fv in F:
                member("max:ope", f"ope:{st.key}:{fv}", "OPE case")
        for k in sorted(load_occ):
            member("max:ope", k, "load-path OPE+OCC case")
        for o in self.occ:
            if o.scale:
                for fv in F:
                    checks += 1
                    if f"opeocc:{o.key}:{fv}" in refs_of("max:ope"):
                        misses.append(f"REDUCED case [opeocc:{o.key}:{fv}] is in max:ope; "
                                      "support loads would be understated")
        kinds = [k for k in ENVELOPE_KINDS if any(o.kind == k for o in self.occ)]
        for kind in kinds:
            need(f"max:{kind}", f"Maximum {kind} envelope")
            for o in self.occ:
                if o.kind == kind:
                    for fv in F:
                        member(f"max:{kind}", f"occ:{o.key}:{fv}", "code occasional case")
        if kinds:
            need("max:occ", "Maximum Occasional envelope")
            for kind in kinds:
                member("max:occ", f"max:{kind}", "kind envelope")

        # Extraction matrix: each row lists every case its purpose needs
        rows = {purpose: set(keys) for purpose, keys, _ in self.matrix_rows()}

        def in_row(purpose: str, key: str) -> None:
            nonlocal checks
            checks += 1
            if key not in rows.get(purpose, set()):
                misses.append(f"matrix row '{purpose}' does not list [{key}]")

        for st in self.states:
            for fv in F:
                for purpose in ("Code stress - Sustained", "Support loads - Sustained",
                                "Displacements - Sustained"):
                    in_row(purpose, f"sus:{st.key}:{fv}")
                in_row("Code stress - Expansion", f"exp:{st.key}:{fv}")
                in_row("Flange / nozzle loads - Operating", f"ope:{st.key}:{fv}")
        for k in sorted(x for x in expected if x.startswith("exprange:")):
            in_row("Code stress - Expansion range between states", k)
        if self.hydrotest:
            for fv in F:
                in_row("Code stress - Hydrotest", f"hyd:{fv}")
                in_row("Support loads - Hydrotest", f"hyd:{fv}")
        if self.hangers:
            in_row("Hanger design - Rigid load / Ignore travel", "hgr:rigid")
            in_row("Hanger design - Rigid load / Ignore travel", "hgr:travel")
        if kinds:
            in_row("Code stress - Occasional", "max:occ")
        in_row("Support loads - Max Operating", "max:ope")
        in_row("Displacements - Max Operating", "max:ope")
        for k in sorted(x for x in load_occ if x.startswith("opeoccu:")):
            in_row("Support loads / displacements - Occasional UNREDUCED", k)

        unexpected = sorted(set(have) - expected)
        for k in unexpected:
            misses.append(f"unexpected case [{k}] not declared by the spec")
        n_scaled = sum(1 for o in self.occ if o.scale)
        return {
            "pass": not misses,
            "counts": {
                "states": len(self.states), "frictions": len(F), "occasionals": len(self.occ),
                "scaled_occasionals": n_scaled, "state_pairs_ranged": pairs,
                "expected_cases": len(expected), "generated_cases": len(self.cases),
                "checks": checks, "misses": len(misses),
            },
            "misses": misses,
        }

    # -- render -------------------------------------------------------------------------

    def rows(self) -> list[dict[str, Any]]:
        return [{
            "L": c.number, "Combination": self.combo_string(c), "Description": c.desc,
            "Stress Type": c.stress, "Method": c.method or "-",
            "Friction": "-" if c.friction is None else f"{c.friction:.1f}",
            "Hanger": c.hanger or "-", "Output": "Suppress" if c.suppress else "Include",
        } for c in self.cases]

    def to_markdown(self) -> str:
        rows = self.rows()
        hdr = list(rows[0].keys())
        out = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
        out += ["| " + " | ".join(str(r[h]) for h in hdr) + " |" for r in rows]
        return "\n".join(out)

    def to_csv(self) -> str:
        buf = io.StringIO()
        rows = self.rows()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    def to_json(self) -> str:
        n = {c.key: c.number for c in self.cases}
        return json.dumps({
            "code": self.code, "edition": self.edition, "total_cases": len(self.cases),
            "primary_state": self.primary.key,
            "hanger_friction": self.hanger_friction if self.hangers else None,
            "cases": self.rows(),
            "extraction_matrix": [{"purpose": a, "cases": [n.get(k, "MISSING " + k) for k in keys], "basis": c}
                                  for a, keys, c in self.matrix_rows()],
            "qc": self.qc, "findings": self.findings,
            "result_status": self.result_status, "checks": self.checks,
            **({"project_basis_applied": self.basis_applied} if self.basis is not None else {}),
        }, indent=2)

    def matrix_rows(self) -> list[tuple[str, list[str], str]]:
        """(purpose, case keys, basis) for the report extraction matrix. Every row that a
        state or friction variant can govern lists every state x friction case; the QC
        case-set check verifies that independently."""
        have = {c.key for c in self.cases}
        F = [str(fv) for _, fv in self.frictions]
        ordered = [self.primary] + [s for s in self.states if s is not self.primary]
        sus = [self._k("sus", s.key, fv) for s in self.states for fv in F]
        exp = [self._k("exp", s.key, fv) for s in self.states for fv in F]
        ranges = [c.key for c in self.cases if c.key.startswith("exprange:")]
        hyd = [self._k("hyd", fv) for fv in F if self._k("hyd", fv) in have]
        ope = [self._k("ope", s.key, fv) for s in ordered for fv in F]
        unred = [c.key for c in self.cases if c.block == "OPE+OCC-UNRED"]
        scaled = bool(unred)
        every = "every state x friction"
        rows: list[tuple[str, list[str], str]] = [
            ("Code stress - Sustained", sus, f"{self.code} sustained; {every}"),
            ("Code stress - Expansion", exp, f"{self.code} expansion, S_A; {every}"),
        ]
        if ranges:
            rows.append(("Code stress - Expansion range between states", ranges,
                         "inter-state range, every state pair x friction; take the greatest S_E"))
        if "max:occ" in have:
            rows.append(("Code stress - Occasional", ["max:occ"],
                         f"{self.code} occasional envelope"
                         + ("; ASD-scaled terms are REDUCED here (stress path only)" if scaled
                            else "")))
        if hyd:
            rows.append(("Code stress - Hydrotest", hyd, "test case; every friction variant"))
        if "hgr:rigid" in have:
            rows.append(("Hanger design - Rigid load / Ignore travel", ["hgr:rigid", "hgr:travel"],
                         f"CAESAR II hanger design pair; primary state {self.primary.key}, "
                         f"friction {self.hanger_friction:.1f}"))
        rows.append(("Support loads - Sustained", sus, f"hanger/restraint design; {every}"))
        if hyd:
            rows.append(("Support loads - Hydrotest", hyd,
                         "restraint load under test weight; every friction variant"))
        envelope = ("every OPE and OPE+OCC case, all states x friction"
                    + ("; scaled occasionals enter UNREDUCED" if scaled else ""))
        rows.append(("Support loads - Max Operating", ["max:ope"],
                     f"governing operating reaction; {envelope}"))
        if unred:
            rows.append(("Support loads / displacements - Occasional UNREDUCED", unred,
                         "ASD-scaled occasionals at full magnitude; never read the REDUCED "
                         "OPE+OCC cases for loads or movements"))
        rows += [
            ("Displacements - Sustained", sus, f"vertical sag limit; {every}"),
            ("Displacements - Max Operating", ["max:ope"], f"lateral movement; {envelope}"),
            ("Flange / nozzle loads - Operating", ope,
             f"manufacturer or WRC allowable; {every}, take the governing; primary state "
             f"{self.primary.key} listed first"),
        ]
        return rows

    def report_matrix(self) -> str:
        """Which load cases feed which qualification. Regenerated from the resolved
        numbering; this is the table that goes stale when a template is copied."""
        n = {c.key: c.number for c in self.cases}
        out = ["| Purpose | Load Case(s) | Basis |", "|---|---|---|"]
        out += [f"| {a} | {', '.join(str(n.get(k, 'MISSING ' + k)) for k in keys)} | {c} |"
                for a, keys, c in self.matrix_rows()]
        return "\n".join(out)

    def to_autopipe(self) -> str:
        """CAESAR II -> AutoPIPE component mapping. VERIFY against your AutoPIPE version:
        whether AutoPIPE needs the same subtract-then-scalar occasional construction has
        not been confirmed."""
        m = {"W": "GR (Gravity)", "WW": "GR with water content / Hydrotest weight",
             "WNC": "GR, empty (no contents)", "HP": "Hydrotest pressure",
             "H": "Spring hanger preload (automatic)", "T#": "T1..Tn thermal",
             "P#": "P1..Pn pressure", "D#": "Imposed displacement (anchor movement)",
             "U#": "Uniform / static-g earthquake E1..En", "WIN#": "Wind W1..Wn",
             "F#": "User-defined point force (PSV thrust)"}
        out = ["| CAESAR II | AutoPIPE equivalent |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in m.items()]
        return "\n".join(out)


# --------------------------------------------------------------------------------------
# Example spec - a generic two-state B31.3 line with PSV, seismic, snow and wind
# --------------------------------------------------------------------------------------

EXAMPLE_SPEC: dict[str, Any] = {
    "code": "B31.3", "edition": "2022",
    "thermal_states": [
        {"key": "op",  "name": "OPERATING CASE CONDITION", "T": "T1", "P": "P1", "D": "D1",
         "role": "operating"},
        {"key": "des", "name": "DESIGN CASE CONDITION", "T": "T2", "P": "P2", "D": "D2",
         "role": "design"},
    ],
    "frictions": [["w/ Friction", 1.0], ["w/o Friction", 0.0]],
    "hangers": True, "hydrotest": True,
    "inter_state_expansion_ranges": False,
    "occasionals": [
        {"key": "psv_op",  "name": "PSV Pop Off",        "vector": "F1",   "base": "op",  "kind": "psv"},
        {"key": "psv_des", "name": "Design PSV Pop Off", "vector": "F2",   "base": "des", "kind": "psv"},
        {"key": "seis_px", "name": "Seismic +X", "vector": "U1", "sign": "+", "base": "op", "kind": "seismic"},
        {"key": "seis_mx", "name": "Seismic -X", "vector": "U1", "sign": "-", "base": "op", "kind": "seismic"},
        {"key": "seis_pz", "name": "Seismic +Z", "vector": "U3", "sign": "+", "base": "op", "kind": "seismic"},
        {"key": "seis_mz", "name": "Seismic -Z", "vector": "U3", "sign": "-", "base": "op", "kind": "seismic"},
        {"key": "snow",    "name": "Snow -Y",   "vector": "U2", "sign": "-", "base": "op", "kind": "snow"},
        {"key": "win_px",  "name": "Wind +X", "vector": "WIN1", "base": "op", "kind": "wind"},
        {"key": "win_mx",  "name": "Wind -X", "vector": "WIN2", "base": "op", "kind": "wind"},
        {"key": "win_pz",  "name": "Wind +Z", "vector": "WIN3", "base": "op", "kind": "wind"},
        {"key": "win_mz",  "name": "Wind -Z", "vector": "WIN4", "base": "op", "kind": "wind"},
    ],
}


def render_basis_block(s: LoadCaseSet) -> str:
    """Section 1 Basis: every ASSUMED item first (the record's and the generator's), then the
    record (shared render_basis_section). Empty when there is neither a record nor an ASSUMED item."""
    gen = [{"item": x[len("ASSUMED: "):].rstrip("."), "note": "generator default"}
           for x in s.findings if x.startswith("ASSUMED: ")]
    heading = "### 1 Basis"
    if s.basis is not None:
        applied = dict(s.basis_applied, assumptions=s.basis_applied["assumptions"] + gen)
        return render_basis_section(applied, s.basis, heading=heading)
    if not gen:
        return ""
    lines = [heading, "", "**ASSUMED - confirm before issue:**"]
    lines += [f"- {a['item']}; note: {a['note']}" for a in gen]
    lines += ["", "No project basis record was given; code, edition and states are the spec's."]
    return "\n".join(lines) + "\n"


def render_report(s: LoadCaseSet) -> str:
    basis = render_basis_block(s)
    parts = [
        f"## Load case set - {s.code} {s.edition}",
        s.status_line() + "\n",
    ] + ([basis] if basis else []) + [
        s.to_markdown(),
        "\n### Report extraction matrix\n",
        s.report_matrix(),
        "\n### QC findings\n",
        "\n".join(f"- {x}" for x in s.findings),
        f"\nTotal cases: {len(s.cases)}",
    ]
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a B31 static load case set.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="path to a JSON project spec")
    src.add_argument("--example", action="store_true", help="use the built-in example spec")
    ap.add_argument("--format", choices=("md", "csv", "json", "autopipe"), default="md")
    ap.add_argument("--project-basis", metavar="FILE",
                    help="pipingtoolset.project-basis/1 record (JSON); fills what the spec leaves out")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")       # UTF-8 output whatever the console code page

    if args.example:
        spec = EXAMPLE_SPEC
    else:
        try:
            with open(args.spec, encoding="utf-8") as fh:
                spec = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"spec error: {exc}", file=sys.stderr)
            return 2

    try:
        s = LoadCaseSet(spec, project_basis_file=args.project_basis).build()
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2

    if args.format == "csv":
        sys.stdout.write(s.to_csv())
    elif args.format == "json":
        print(s.to_json())
    elif args.format == "autopipe":
        print(s.to_autopipe())
    else:
        sys.stdout.write(render_report(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
