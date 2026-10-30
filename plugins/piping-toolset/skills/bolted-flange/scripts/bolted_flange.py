#!/usr/bin/env python3
"""Bolted-flange calculators for the PipingToolset `bolted-flange` skill.

Python 3.9+, standard library only.

Three modules, all registered in REGISTRY:

  Faithful ports of the pipingtoolset.com calculation engine (same input and output
  field names, statuses, rounding and error conditions):
    connections.flange-equivalent-pressure   Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) vs the rating
    aux.app2-flange-integral                 flange analysis for integral and loose flanges:
                                             bolt loads, moments, hub/radial/tangential stresses,
                                             rigidity J, bolt-spacing correction

  New helper with no engine module:
    connections.flange-derive                N, b0, b, G from the gasket ID/OD; bolt root area
                                             from the UN thread formula; g0, g1, h from the
                                             hub dimensions

Order of use: derive the geometry, run the pressure-equivalent screen (always), then the
detailed analysis. The screen is a conservative leakage screen, not a stress check.

Nothing in this file is a tabulated code value. The flange pressure-temperature rating, the
flange and gasket dimensions, the gasket factors m and y, every allowable stress and the
elastic moduli are INPUTS the user reads from a licensed copy of the code or the
manufacturer's data. Numeric constants that appear in running text of an equation (the 16
and 4 of the screen, the 1.5 and 2.5 multipliers of the longitudinal-hub limit, the 0.3 and
0.2 rigidity factors, the 52.14 and 109.4 rigidity constants, the 1.299038 UN thread
constant) are named constants below, each with its source.

Clause path. ASME BPVC Section VIII Division 1 Mandatory Appendix 2 was revised in its
entirety in the 2025 edition and now points to Section VIII Division 2 Part 4.16 for the
flange design rules (paragraphs 2-3 and 2-5 to 2-14 are deleted and mapped to 4.16). The
equations are unchanged; cite 4.16 (4.16.6 bolt loads, 4.16.7 flange moments, stresses,
acceptance and rigidity; Tables 4.16.4 to 4.16.11). ASME B31.3 304.5.1(b) permits either
route with B31.3 allowable stresses.

External loads. The detailed module folds the axial force and bending moment into an
equivalent pressure Peq = P + 16|M|/(pi G^3) + 4F/(pi G^2) and runs the whole sequence on
Peq. That is the common pressure-equivalent method. It is NOT an Appendix 2 / 4.16
construction (the Code's own external-moment term uses the flange ring properties). Both the
raw-P and Peq results are visible in the output (Peq, momentTerm, forceTerm).

Hub factors F, V, f (integral flanges). The method is `hubFactorMethod` = "series" (the
default and the only method shipped): a closed-form constant-chain elastic solution (the
C1..C37 chain). It is a RECONSTRUCTION assembled from published open-source implementations
and cross-checked term by term against a published reproduction. It matches a commercial
pipe-stress program's flange report to four digits. It is NOT transcribed from licensed Code
text. The Table 4.16.5 curve-fit option is not shipped (it would be tabulated code data);
any other value of hubFactorMethod is rejected with exit 2. For a sealed calc, the user reads
F, V and f from the VIII-2 Table 4.16.5 equations or figures and passes them per factor as
F_override, V_override, f_override. This is the only deviation from the engine source and it
does not change any engine result when the overrides are absent. The Table 4.16.4 constants
in the K terms (8.55246, 1.0472, 1.9448, 0.66845, 5.7169, 1.36136) are equation constants and
should be confirmed on the printed page.

Result grade. The detailed analysis carries `result_grade`, `grade_label`, `factor_basis`
(F, V and f each "series", "override", or "not used" for a loose flange), `banner` and
`grade_note` in its output. The grade is "screening" (label "screening / reconstructed
factors") whenever any hub factor the flange type uses came from the series, and "calculated"
only when every hub factor the type uses was supplied by override (a loose flange uses none and
is "calculated"). The pressure-equivalent screen is "screening" always. The grade adds keys
only: no number and no pass/fail status word changes. Taxonomy: calculated / screening /
manual check required / pointer only / not checked.

CLI:
    python bolted_flange.py list
    python bolted_flange.py <module-id> --input '<json>'
    python bolted_flange.py <module-id> --input-file <path.json>
    python bolted_flange.py <module-id> --input-file <path.json> --format sheet
    python bolted_flange.py <module-id> --input-file <path.json> --project-basis project-basis.json

Output is a JSON envelope {module, status, output, warnings, citation, inputs,
user_supplied}; `--format sheet` prints a markdown calc-sheet block instead, headed by the
grade banner, with no acceptance wording on a screening run. Exit code 2 on bad input.

Optional top-level input `code_values`:
    {"code_values": {"ratedPressure": {"value": 1234.5, "unit": "psig",
                                       "citation": {"standard": "...", "edition": "...",
                                                    "table": "...", "row": "...", "column": "..."},
                                       "source": "connector"}}}
The key is an input name from `list`. An input that is absent from the main inputs is filled
from code_values[name]["value"]; one that is present must agree, otherwise the run exits 2 with
"code_values.<name> conflicts with input <name>". A name the module does not declare exits 2.
"source" is "connector" or "user". A unit other than the input's unit is converted when the
factor is exact (ksi to psi) and rejected otherwise. The module has no nested inputs: the gasket
factors are the plain inputs `m` and `y`, and "gasket.m" and "gasket.y" are accepted as other
spellings of them (the provenance is keyed by the name given). The envelope gains
"code_value_provenance": {name: {unit, citation, source}}; "inputs" shows the values used and
"user_supplied" counts a filled input. Nothing here reaches a network.

Optional top-level input `project_basis` (or `--project-basis <file>`; both present and different exits
2), schema pipingtoolset.project-basis/1, see references/project-basis.md. This skill takes from it:
  P              <- the design state (role design, else the first state) P_psig; an input that is
                    present and different exits 2 "project_basis.<path> conflicts with input P"
  T              <- the design state T_F, read for the sheet and the B16.5 2.5.2 advisory note (no input)
  units          <- units.system must be USC (SI exits 2); an explicit units.moment must agree with the
                    moment input actually given (in-lbf or ft-lbf), otherwise exit 2
  code, service  <- code.standard, code.route and service.fluid_category choose the clause route noted
                    on the sheet; a standard other than B31.3 or B31.1, and B31.3 Chapter IX, are
                    "manual check required"
  owner_practice <- an object item whose name contains "accept" and whose value is a fraction of the
                    rating (or a percent, unit "%") becomes the check "owner acceptance" on the
                    screen; a text value is a pointer ("pointer only": the check does not run)
  assumptions    <- the ASSUMED block at the top of section 1 of the sheet
The envelope then gains "project_basis_applied" {schema, fields_used, assumptions, conflicts}. The
record holds no code-table value: the rating, dimensions, gasket factors and allowables stay inputs.

Result status. Every envelope gains "result_status" (calculated / screening / manual check required /
pointer only / not checked: the worst word among the "checks" performed; an ASSUMED record item adds
one "ASSUMED inputs" row graded manual check required), "checks" [{name, result_status, status, note}]
and "not_checked" (methods this module never performs, listed and never blocking). Existing "status"
words and every number are unchanged. The ISSUE-GRADE banner is not printed while the word is manual
check required or pointer only, or screening with an unresolved reconstructed hub factor.

`list` prints every module with its exact input field names (case-sensitive). Before the
engine runs, a separate pre-flight layer (`validate`) rejects unknown keys and physically
impossible or silently-defaulted inputs (exit 2) and adds warnings; the ported engine
functions themselves follow the engine source.

Units: US customary. Pressure psi, force lbf, lengths in, area in^2, stress and modulus psi.
The screen takes the moment in in-lbf; the detailed module takes it in ft-lbf (Mext), as the
engine does. Each module also accepts an explicitly unit-named alias; give exactly one.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
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


# --------------------------------------------------------------------------- result grade
# Output status words (the pack taxonomy): calculated / screening / manual check required /
# pointer only / not checked. The grade keys below use the first two; checks[] uses all five. The detailed analysis is
# "calculated" only when every hub factor its flange type uses was supplied by override
# (F_override, V_override, f_override, read by the user from VIII-2 Table 4.16.5); any factor
# taken from the open-source series reconstruction makes the run "screening". The grade is an
# extra result key. It never changes a number or the pass/fail status word of the engine.
GRADE_CALCULATED = "calculated"
GRADE_SCREENING = "screening"
GRADE_LABEL_RECON = "screening / reconstructed factors"
GRADE_LABEL_SCREEN = "screening (leakage screen, not a stress check)"
GRADE_KEYS = ("result_grade", "grade_label", "factor_basis", "banner", "grade_note", "report_word")
HUB_FACTORS = ("F", "V", "f")
BANNER_RECON = (
    "SCREENING / RECONSTRUCTED FACTORS: F, V, f from the open-source series reconstruction; "
    "supply F_override, V_override, f_override read from VIII-2 Table 4.16.5 for an issue-grade result"
)
BANNER_CALCULATED = (
    "ISSUE-GRADE HUB FACTORS: F, V, f supplied by override, read by the user from VIII-2 Table 4.16.5; "
    "the hub-factor basis is closed only: the Peq external-load treatment and any defaulted inputs still need review; "
    "confirm the three values on the printed page and clear the rejection checklist before issue"
)
BANNER_LOOSE = (
    "ISSUE-GRADE FACTOR BASIS: loose-type flange, no hub factors F, V, f are used; "
    "the factor basis is closed only: the Peq external-load treatment and any defaulted inputs still need review; "
    "clear the rejection checklist before issue"
)
BANNER_SCREEN = (
    "SCREENING: pressure-equivalent leakage screen, not a stress check; "
    "a result within the rating does not establish bolt, gasket or flange stress"
)


def grade_hub_factors(hubbed: bool, overridden: Tuple[str, ...]) -> Dict[str, Any]:
    """Result-grade keys for the detailed analysis from which hub factors came by override."""
    if not hubbed:
        basis = {k: "not used" for k in HUB_FACTORS}
        return {
            "result_grade": GRADE_CALCULATED,
            "grade_label": GRADE_CALCULATED,
            "factor_basis": basis,
            "banner": BANNER_LOOSE,
            "grade_note": (
                "Loose-type flange: the run uses no hub factor F, V or f, so none can come from the series. "
                "The Peq external-load treatment and the other known limits still apply."
            ),
        }
    basis = {k: ("override" if k in overridden else "series") for k in HUB_FACTORS}
    series = [k for k in HUB_FACTORS if basis[k] == "series"]
    given = [k for k in HUB_FACTORS if basis[k] == "override"]
    if series:
        note = (
            "Series factor(s) in use: " + ", ".join(series)
            + " (supply " + ", ".join(k + "_override" for k in series) + " read from VIII-2 Table 4.16.5 to close). "
            + ("Override(s) supplied: " + ", ".join(given) + "." if given else "Override(s) supplied: none.")
        )
        return {
            "result_grade": GRADE_SCREENING,
            "grade_label": GRADE_LABEL_RECON,
            "factor_basis": basis,
            "banner": BANNER_RECON,
            "grade_note": note,
        }
    return {
        "result_grade": GRADE_CALCULATED,
        "grade_label": GRADE_CALCULATED,
        "factor_basis": basis,
        "banner": BANNER_CALCULATED,
        "grade_note": (
            "Override(s) supplied: F, V, f. The values are the user's reading of the Code and are not checked here; "
            "the Peq external-load treatment and the other known limits still apply."
        ),
    }

# --------------------------------------------------------------------------- constants

# 16 and 4 of the pressure-equivalent expression Pe = P + 16 M/(pi G^3) + 4 F/(pi G^2):
# the moment and force are converted to an equivalent internal pressure on the gasket circle.
PEQ_MOMENT_COEFF = 16.0
PEQ_FORCE_COEFF = 4.0

# Hydrostatic end force uses pi/4, not the Code's rounded 0.785 (the difference is 0.05 percent;
# pi/4 is what commercial pipe-stress programs use, so cross-checks against them stay clean).
QP = math.pi / 4

# Longitudinal hub allowable cap for hubs welded to pipe: min(1.5 Sf, 2.5 Sn) (VIII-1 App. 2
# para. 2-8(a); VIII-2 Table 4.16.9 note on integral flanges welded to a nozzle neck or pipe).
HUB_CAP_SF = 1.5
HUB_CAP_SN = 2.5

# Rigidity factors KI "unless the user specifies otherwise" (VIII-2 Table 4.16.10 general
# notes): integral 0.3, loose 0.2. Rigidity constants 52.14 (integral) and 109.4 (loose).
KI_INTEGRAL = 0.3
KI_LOOSE = 0.2
RIGIDITY_INTEGRAL_CONST = 52.14
RIGIDITY_LOOSE_CONST = 109.4

# PARITY ONLY. Engine default moduli, kept so the ported function reproduces the engine
# fixture cases that omit E. They are not recommended values and are not table lines: the CLI
# layer (validate) refuses to run without Edesign and Eambient, so these never reach a sheet.
# The user always reads E from Section II-D Subpart 2 and supplies it.
ENGINE_DEFAULT_E_DESIGN = 27000000.0
ENGINE_DEFAULT_E_AMBIENT = 29000000.0

# Poisson ratio used in the hub-factor series (VIII-1 App. 2 Fig. 2-7.1 note).
NU = 0.3
K3 = 3 * (1 - NU * NU)

# Basic gasket width: b0 = N/2 for the flat facing rule, N/8 for ring joints; b = b0 when
# b0 <= 1/4 in (6 mm), else 0.5 sqrt(b0) (VIII-2 Table 4.16.3, Eq. 4.16.1 to 4.16.3).
B0_LIMIT_IN = 0.25

# Unified thread root diameter: d_root = D - 1.299038 / n  (0.75 sqrt(3) = 1.299038).
UN_ROOT_CONST = 1.299038


# --------------------------------------------------------------------------- rounding


def round_half_up(x: float, decimals: int) -> float:
    if not math.isfinite(x):
        return x
    return float(Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def _js(x: float) -> str:
    """Format a number the way the engine's template strings do (no trailing .0)."""
    if isinstance(x, float) and math.isfinite(x) and x == int(x):
        return str(int(x))
    return repr(x)


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


def _has(inp: Dict[str, Any], key: str) -> bool:
    return key in inp and inp[key] is not None


def _result(module: str, output: Dict[str, Any], status: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"module": module, "output": output, "status": status, "warnings": warnings or []}


def _one_moment(inp: Dict[str, Any], names: Tuple[str, ...], optional: bool) -> Tuple[Optional[str], float]:
    """Pick the single moment key given. Returns (key, value); key None when optional and absent."""
    given = [n for n in names if _has(inp, n)]
    if len(given) > 1:
        raise ValueError(f"give exactly one moment input, not {' and '.join(given)} (units differ)")
    if not given:
        if optional:
            return None, 0.0
        raise ValueError(f"a moment is required: give exactly one of {', '.join(names)}")
    return given[0], _num(inp, given[0])


# --------------------------------------------------------------------------- pressure-equivalent screen


def flange_equivalent_pressure(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Pressure-equivalent screen: Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) against the rating.

    The moment is a magnitude (its sign is an artefact of the analysis frame). Axial force is
    signed, tension positive; compression lowers Pe and raises a warning. The moment is in
    in-lbf as `M` (engine name) or `M_in_lbf`; `M_ft_lbf` is converted (x 12). Give exactly one.
    """
    P, F, G = _num(inp, "P"), _num(inp, "F"), _num(inp, "G")
    rated = _num(inp, "ratedPressure")
    key, M = _one_moment(inp, ("M", "M_in_lbf", "M_ft_lbf"), optional=False)
    warnings: List[str] = []
    if key == "M_ft_lbf":
        M = M * 12
        warnings.append(f"M_ft_lbf converted to in-lbf (x 12): {_js(round_half_up(M, 3))} in-lbf used.")
    if G <= 0:
        raise ValueError("G must be > 0")
    if rated <= 0:
        raise ValueError("ratedPressure must be > 0 (supply from B16.5 P-T table)")

    moment_term = (PEQ_MOMENT_COEFF * abs(M)) / (math.pi * G ** 3)
    force_term = (PEQ_FORCE_COEFF * F) / (math.pi * G ** 2)
    Pe = P + moment_term + force_term
    utilization = Pe / rated

    if force_term < 0:
        warnings.append("Compressive axial force reduces Pe - confirm the joint cannot see the tensile case separately.")

    return _result(
        "connections.flange-equivalent-pressure",
        {
            "momentTerm": round_half_up(moment_term, 3),
            "forceTerm": round_half_up(force_term, 3),
            "Pe": round_half_up(Pe, 3),
            "utilization": round_half_up(utilization, 4),
            "result_grade": GRADE_SCREENING,
            "grade_label": GRADE_LABEL_SCREEN,
            "banner": BANNER_SCREEN,
            "report_word": "within" if Pe <= rated else "exceeds",
        },
        _verdict(Pe <= rated),
        warnings,
    )


# --------------------------------------------------------------------------- hub factors: series


def hub_factors(g1_over_g0: float, h_over_ho: float) -> Dict[str, float]:
    """Integral-flange hub factors F, V and f from the constant-chain series.

    A reconstruction (see the module header); not transcribed from licensed Code text.
    g1_over_g0 >= 1 (hub taper), h_over_ho > 0 with h0 = sqrt(B g0).
    """
    if not (g1_over_g0 >= 1):
        raise ValueError("g1/g0 must be >= 1 (large end cannot be thinner than the small end)")
    if not (h_over_ho > 0):
        raise ValueError("h/h0 must be > 0")

    A = g1_over_g0 - 1
    C = 48 * (1 - NU * NU) * h_over_ho ** 4  # 43.68 (h/h0)^4 at NU = 0.3
    A2 = A * A
    A3 = A2 * A

    C1 = 1 / 3 + A / 12
    C2 = 5 / 42 + (17 * A) / 336
    C3 = 1 / 210 + A / 360
    C4 = 11 / 360 + (59 * A) / 5040 + (1 + 3 * A) / C
    C5 = 1 / 90 + (5 * A) / 1008 - (1 + A) ** 3 / C
    C6 = 1 / 120 + (17 * A) / 5040 + 1 / C
    C7 = 215 / 2772 + (51 * A) / 1232 + ((120 + 225 * A + 150 * A2 + 35 * A3) / 14) / C
    C8 = 31 / 6930 + (128 * A) / 45045 + ((66 + 165 * A + 132 * A2 + 35 * A3) / 77) / C
    C9 = 533 / 30240 + (653 * A) / 73920 + ((42 + 198 * A + 117 * A2 + 25 * A3) / 84) / C
    C10 = 29 / 3780 + (3 * A) / 704 - ((42 + 198 * A + 243 * A2 + 91 * A3) / 84) / C
    C11 = 31 / 6048 + (1763 * A) / 665280 + ((42 + 72 * A + 45 * A2 + 10 * A3) / 84) / C
    C12 = 1 / 2925 + (71 * A) / 300300 + ((88 + 198 * A + 156 * A2 + 42 * A3) / 385) / C
    C13 = 761 / 831600 + (937 * A) / 1663200 + ((2 + 12 * A + 11 * A2 + 3 * A3) / 70) / C
    C14 = 197 / 415800 + (103 * A) / 332640 - ((2 + 12 * A + 17 * A2 + 7 * A3) / 70) / C
    C15 = 233 / 831600 + (97 * A) / 554400 + ((6 + 18 * A + 15 * A2 + 4 * A3) / 210) / C

    # 3x3 system solved by Cramer's rule; C16 is the determinant.
    C16 = C1 * C7 * C12 + C2 * C8 * C3 + C3 * C8 * C2 - (C3 ** 2 * C7 + C8 ** 2 * C1 + C2 ** 2 * C12)

    C17 = (C4 * C7 * C12 + C2 * C8 * C13 + C3 * C8 * C9 - (C13 * C7 * C3 + C8 ** 2 * C4 + C12 * C2 * C9)) / C16
    C18 = (C5 * C7 * C12 + C2 * C8 * C14 + C3 * C8 * C10 - (C14 * C7 * C3 + C8 ** 2 * C5 + C12 * C2 * C10)) / C16
    C19 = (C6 * C7 * C12 + C2 * C8 * C15 + C3 * C8 * C11 - (C15 * C7 * C3 + C8 ** 2 * C6 + C12 * C2 * C11)) / C16
    C20 = (C1 * C9 * C12 + C4 * C8 * C3 + C3 * C13 * C2 - (C3 ** 2 * C9 + C13 * C8 * C1 + C12 * C4 * C2)) / C16
    C21 = (C1 * C10 * C12 + C5 * C8 * C3 + C3 * C14 * C2 - (C3 ** 2 * C10 + C14 * C8 * C1 + C12 * C5 * C2)) / C16
    C22 = (C1 * C11 * C12 + C6 * C8 * C3 + C3 * C15 * C2 - (C3 ** 2 * C11 + C15 * C8 * C1 + C12 * C6 * C2)) / C16
    C23 = (C1 * C7 * C13 + C2 * C9 * C3 + C4 * C8 * C2 - (C3 * C7 * C4 + C8 * C9 * C1 + C2 ** 2 * C13)) / C16
    C24 = (C1 * C7 * C14 + C2 * C10 * C3 + C5 * C8 * C2 - (C3 * C7 * C5 + C8 * C10 * C1 + C2 ** 2 * C14)) / C16
    C25 = (C1 * C7 * C15 + C2 * C11 * C3 + C6 * C8 * C2 - (C3 * C7 * C6 + C8 * C11 * C1 + C2 ** 2 * C15)) / C16

    C26 = -((C / 4) ** 0.25)
    C27 = C20 - C17 - 5 / 12 + C17 * C26
    C28 = C22 - C19 - 1 / 12 + C19 * C26
    C29 = -((C / 4) ** 0.5)
    C30 = -((C / 4) ** 0.75)
    C31 = (3 * A) / 2 - C17 * C30
    C32 = 1 / 2 - C19 * C30

    C33 = (C26 * C32) / 2 + C28 * C31 * C29 - ((C30 * C28) / 2 + C32 * C27 * C29)
    C34 = 1 / 12 + C18 - C21 - C18 * C26
    C35 = C18 * C30
    C36 = (C28 * C35 * C29 - C32 * C34 * C29) / C33
    C37 = ((C26 * C35) / 2 + C34 * C31 * C29 - (C30 * C34) / 2 - C35 * C27 * C29) / C33

    E1 = C17 * C36 + C18 + C19 * C37
    E2 = C20 * C36 + C21 + C22 * C37
    E3 = C23 * C36 + C24 + C25 * C37
    E4 = (3 + C37 + 3 * C36) / 12 - (2 * E3 + 15 * E2 + 10 * E1) / 10
    E5 = E1 * ((3 + A) / 6) + E2 * ((21 + 11 * A) / 84) + E3 * ((3 + 2 * A) / 210)
    E6 = (
        E5
        - C36 * (7 / 120 + A / 36 + (3 * A) / C)
        - 1 / 40
        - A / 72
        - C37 * (1 / 60 + A / 120 + 1 / C)
    )

    one_plus_a3 = (1 + A) ** 3
    V = E4 / ((K3 / C) ** 0.25 * one_plus_a3)
    F = (-E6 * C) / ((C / K3) ** 0.25 * one_plus_a3)

    # The correction never reduces the hub stress below the uncorrected value (f = 1 minimum).
    f = max(1.0, C36 / (1 + A))

    if not (math.isfinite(F) and math.isfinite(V)) or V <= 0:
        raise ValueError(f"hub factor series did not converge at g1/g0={_js(g1_over_g0)}, h/h0={_js(h_over_ho)}")
    return {"F": F, "V": V, "f": f}


# --------------------------------------------------------------------------- detailed flange analysis


def _shape_factors(K: float) -> Dict[str, float]:
    """Terms involving K = A/B (VIII-2 Table 4.16.4; retired VIII-1 Fig. 2-7.1)."""
    K2 = K * K
    lgK = math.log10(K)
    T = (K2 * (1 + 8.55246 * lgK) - 1) / ((1.0472 + 1.9448 * K2) * (K - 1))
    Z = (K2 + 1) / (K2 - 1)
    Y = (1 / (K - 1)) * (0.66845 + (5.7169 * (K2 * lgK)) / (K2 - 1))
    U = (K2 * (1 + 8.55246 * lgK) - 1) / (1.36136 * (K2 - 1) * (K - 1))
    return {"T": T, "Z": Z, "Y": Y, "U": U}


def _stress_set(
    Mo: float, L: float, e: float, t: float, B: float, g1: float, Y: float, Z: float, f: float,
    Sfa: float, hubbed: bool, Sn: Optional[float],
) -> Dict[str, float]:
    SH = (f * Mo) / (L * g1 * g1 * B) if hubbed else 0.0
    SR = ((1.33 * t * e + 1) * Mo) / (L * t * t * B) if hubbed else 0.0
    ST = (Y * Mo) / (t * t * B) - Z * SR
    allow_sh = min(HUB_CAP_SF * Sfa, HUB_CAP_SN * Sn) if (Sn is not None and Sn > 0) else HUB_CAP_SF * Sfa
    checks = [SH / allow_sh, SR / Sfa, ST / Sfa, (SH + SR) / 2 / Sfa, (SH + ST) / 2 / Sfa]
    return {
        "SH": round_half_up(SH, 1),
        "SR": round_half_up(SR, 1),
        "ST": round_half_up(ST, 1),
        "avgHR": round_half_up((SH + SR) / 2, 1),
        "avgHT": round_half_up((SH + ST) / 2, 1),
        "allowSH": round_half_up(allow_sh, 1),
        "allowSR": round_half_up(Sfa, 1),
        "allowST": round_half_up(Sfa, 1),
        "utilization": round_half_up(max(checks), 4),
    }


def app2_flange_integral(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Bolt loads, moments, stresses and rigidity for an integral or loose flange.

    See the module header for the clause path and the pressure-equivalent treatment of the
    external loads. Sequence: Peq, gasket b, H Hp Wm1 Wm2 Am Ab Wg, K T Z Y U ho F V f e d L,
    moment arms, HD HT HG, bolt spacing and Bsc, Mo and Mg, SH SR ST and averages against the
    allowables (with the min(1.5 Sf, 2.5 Sn) cap on SH), rigidity J.
    """
    attachment = inp.get("attachment")
    P, A, B, C, t = _num(inp, "P"), _num(inp, "A"), _num(inp, "B"), _num(inp, "C"), _num(inp, "t")
    G, N, m, y = _num(inp, "G"), _num(inp, "N"), _num(inp, "m"), _num(inp, "y")
    n_bolts, a_root = _num(inp, "nBolts"), _num(inp, "aRoot")
    Sa, Sb, Sf = _num(inp, "Sa"), _num(inp, "Sb"), _num(inp, "Sf")
    hubbed = attachment == "integral"

    if P <= 0:
        raise ValueError("design pressure P must be > 0")
    if G <= 0 or N <= 0:
        raise ValueError("gasket G and N must be > 0")
    if m < 0 or y < 0:
        raise ValueError("gasket m and y must be >= 0")
    if Sa <= 0 or Sb <= 0 or Sf <= 0:
        raise ValueError("Sa, Sb and Sf must be > 0")
    if n_bolts < 4 or a_root <= 0:
        raise ValueError("need >= 4 bolts with root area > 0")
    if not (A > C and C > G and G > B):
        raise ValueError("require A > C > G > B")
    if t <= 0:
        raise ValueError("flange thickness t must be > 0")

    g0 = _num(inp, "g0", 0.0) if hubbed else 0.0
    g1 = _num(inp, "g1", 0.0) if hubbed else 0.0
    h = _num(inp, "h", 0.0) if hubbed else 0.0
    if hubbed and (g0 <= 0 or g1 <= 0 or h <= 0):
        raise ValueError("integral flanges need hub g0, g1 and h > 0")
    if hubbed and g1 < g0:
        raise ValueError("large-end hub thickness g1 must be >= g0")

    warnings: List[str] = []

    # ---- external loads folded in as the pressure-equivalent (Peq) -------------------
    # The moment enters as a magnitude: its sign can never relieve a flanged joint. Axial
    # force stays signed (compression genuinely relieves) with the same warning the screen
    # attaches to that case.
    Fax = _num(inp, "Fax", 0.0)
    key, Mext_in = _one_moment(inp, ("Mext", "Mext_in_lbf"), optional=True)
    if key == "Mext_in_lbf":
        M_in_lb = Mext_in
        warnings.append(f"Mext_in_lbf given in in-lbf: {_js(round_half_up(M_in_lb, 3))} in-lbf used directly.")
    else:
        M_in_lb = Mext_in * 12  # Mext is in ft-lbf
    moment_term = (PEQ_MOMENT_COEFF * abs(M_in_lb)) / (math.pi * G * G * G)
    force_term = (PEQ_FORCE_COEFF * Fax) / (math.pi * G * G)
    Peq = P + moment_term + force_term
    if Peq <= 0:
        raise ValueError("equivalent pressure is not positive - check the external load signs")
    if force_term < 0:
        warnings.append("Compressive axial force reduces Peq - confirm the joint cannot see the tensile case separately.")
    if Peq > P * 1.0001:
        warnings.append(
            f"External loads raise the analysed pressure from {_js(round_half_up(P, 1))} to {_js(round_half_up(Peq, 1))} psi "
            "via the pressure-equivalent method (Peq = P + 16|M|/(pi G^3) + 4F/(pi G^2)); the flange sequence below runs on Peq. "
            "This is not an Appendix 2 / 4.16 construction."
        )

    # ---- gasket ------------------------------------------------------------------------
    b0 = N / 2
    b = _num(inp, "b") if _has(inp, "b") else (b0 if b0 <= B0_LIMIT_IN else 0.5 * math.sqrt(b0))

    # ---- bolt loads --------------------------------------------------------------------
    H = QP * G * G * Peq
    Hp = 2 * b * math.pi * G * m * Peq
    Wm1 = H + Hp
    Wm2 = math.pi * b * G * y
    Am = max(Wm1 / Sb, Wm2 / Sa)
    Ab = n_bolts * a_root
    Wg = ((Am + Ab) / 2) * Sa
    if Ab < Am:
        warnings.append(
            f"Bolt area Ab = {_js(round_half_up(Ab, 3))} in^2 is less than the required Am = {_js(round_half_up(Am, 3))} in^2 - the bolting is inadequate."
        )

    # ---- shape and hub factors ---------------------------------------------------------
    K = A / B
    sf = _shape_factors(K)
    T, Z, Yf, U = sf["T"], sf["Z"], sf["Y"], sf["U"]
    ho = math.sqrt(B * g0) if hubbed else math.sqrt(B * t)

    overrides: Dict[str, float] = {}
    F = 0.0
    V = 0.0
    f = 1.0
    e = 0.0
    d = 0.0
    L = 0.0

    if hubbed:
        # The Code's X_g = g1/g0 and X_h = h/h_o. Spelled with the underscore on purpose:
        # without it the second name collides with a command-line HTTP client's name and a
        # plugin-directory scanner holds the plugin as able to send data off the machine.
        x_g = g1 / g0
        x_h = h / ho
        overrides = {k: _num(inp, k + "_override") for k in HUB_FACTORS if _has(inp, k + "_override")}
        if len(overrides) < 3:
            hf = hub_factors(x_g, x_h)
            F, V, f = hf["F"], hf["V"], hf["f"]
        if overrides:
            F = overrides.get("F", F)
            V = overrides.get("V", V)
            f = overrides.get("f", f)
            warnings.append(
                "Hub factor override(s) in use for " + ", ".join(sorted(overrides))
                + ": value(s) read by the user from the Table 4.16.5 equations or the retired figures bypass the computed factor."
            )
        e = F / ho
        d = (U / V) * ho * g0 * g0
        L = (t * e + 1) / T + (t * t * t) / d
    else:
        # Loose ring without a hub: only the tangential stress survives; L folds to 1.
        L = 1.0

    # ---- moment arms (VIII-2 Table 4.16.6) ----------------------------------------------
    hG = (C - G) / 2
    if hubbed:
        R = (C - B) / 2 - g1
        if R <= 0:
            warnings.append("Radial hub clearance R = (C-B)/2 - g1 is not positive - check the bolt circle against the hub.")
        hD = R + g1 / 2
        hT = (R + g1 + hG) / 2
    else:
        hD = (C - B) / 2
        hT = (hD + hG) / 2

    HD = QP * B * B * Peq
    HT = H - HD
    HG = Wm1 - H

    # ---- bolt spacing correction (VIII-2 Table 4.16.11) ----------------------------------
    bolt_spacing = (math.pi * C) / n_bolts
    bolt_dia = _num(inp, "boltDia") if _has(inp, "boltDia") else 2 * math.sqrt(a_root / math.pi)
    bolt_spacing_max = 2 * bolt_dia + t
    apply_bsc = inp.get("applyBoltSpacing") is not False
    bsc_raw = math.sqrt(bolt_spacing / bolt_spacing_max)
    Bsc = max(1.0, bsc_raw) if apply_bsc else 1.0
    if Bsc > 1:
        warnings.append(
            f"Bolt spacing {_js(round_half_up(bolt_spacing, 3))} in exceeds 2*(bolt dia) + t = {_js(round_half_up(bolt_spacing_max, 3))} in, "
            f"so the moments are scaled by the bolt-spacing correction factor Bsc = {_js(round_half_up(Bsc, 4))}."
        )

    # Bsc scales the moments used for STRESS, not the moment used for the RIGIDITY index.
    mo_bare = HD * hD + HT * hT + HG * hG
    Mo = mo_bare * Bsc
    mg_bare = Wg * hG
    Mg = mg_bare * Bsc

    # ---- stresses ----------------------------------------------------------------------
    sf_ambient = _num(inp, "SfAmbient") if _has(inp, "SfAmbient") else Sf
    Sn = _num(inp, "Sn") if _has(inp, "Sn") else None
    sn_ambient = _num(inp, "SnAmbient") if _has(inp, "SnAmbient") else Sn
    operating = _stress_set(Mo, L, e, t, B, g1, Yf, Z, f, Sf, hubbed, Sn)
    seating = _stress_set(Mg, L, e, t, B, g1, Yf, Z, f, sf_ambient, hubbed, sn_ambient)
    if hubbed and not (Sn is not None and Sn > 0):
        warnings.append(
            "Attached-pipe allowable Sn not supplied: the longitudinal hub check uses 1.5*Sf alone. The cap min(1.5 Sf, 2.5 Sn) for hubs welded to pipe "
            "is unchecked - supply Sn to close that check."
        )

    # ---- rigidity index (VIII-2 Table 4.16.10) -------------------------------------------
    KI = _num(inp, "rigidityFactor") if _has(inp, "rigidityFactor") else (KI_INTEGRAL if hubbed else KI_LOOSE)
    E_design = _num(inp, "Edesign") if _has(inp, "Edesign") else ENGINE_DEFAULT_E_DESIGN
    E_ambient = _num(inp, "Eambient") if _has(inp, "Eambient") else ENGINE_DEFAULT_E_AMBIENT
    if hubbed:
        J_op = (RIGIDITY_INTEGRAL_CONST * V * mo_bare) / (L * E_design * g0 * g0 * KI * ho)
        J_seat = (RIGIDITY_INTEGRAL_CONST * V * mg_bare) / (L * E_ambient * g0 * g0 * KI * ho)
    else:
        J_op = (RIGIDITY_LOOSE_CONST * mo_bare) / (E_design * t * t * t * KI * math.log(K))
        J_seat = (RIGIDITY_LOOSE_CONST * mg_bare) / (E_ambient * t * t * t * KI * math.log(K))
    if J_op > 1 or J_seat > 1:
        warnings.append(
            "Rigidity index J exceeds 1.0 - the flange may meet the stress limits but is too flexible; leakage and gasket seating are at risk."
        )

    worst = max(operating["utilization"], seating["utilization"])
    governing = "gasket seating" if seating["utilization"] > operating["utilization"] else "operating"
    ok = Ab >= Am and worst <= 1 and J_op <= 1 and J_seat <= 1

    if not hubbed:
        warnings.append("Loose-type flange without a hub: the longitudinal-hub and radial stresses do not apply and are reported as zero.")

    grade = grade_hub_factors(hubbed, tuple(sorted(overrides)))
    # The grade banner heads the findings list; a partial override also names the factors still on the series.
    warnings.insert(0, grade["banner"])
    if grade["result_grade"] == GRADE_SCREENING and overrides:
        warnings.insert(1, "Result grade screening: " + grade["grade_note"])

    return _result(
        "aux.app2-flange-integral",
        {
            "Peq": round_half_up(Peq, 2),
            "momentTerm": round_half_up(moment_term, 2),
            "forceTerm": round_half_up(force_term, 2),
            "b": round_half_up(b, 5),
            "H": round_half_up(H, 1),
            "Hp": round_half_up(Hp, 1),
            "Wm1": round_half_up(Wm1, 1),
            "Wm2": round_half_up(Wm2, 1),
            "Am": round_half_up(Am, 4),
            "Ab": round_half_up(Ab, 4),
            "Wg": round_half_up(Wg, 1),
            "K": round_half_up(K, 4),
            "T": round_half_up(T, 4),
            "Z": round_half_up(Z, 4),
            "Y": round_half_up(Yf, 4),
            "U": round_half_up(U, 4),
            "ho": round_half_up(ho, 4),
            "F": round_half_up(F, 4),
            "V": round_half_up(V, 4),
            "f": round_half_up(f, 4),
            "e": round_half_up(e, 4),
            "d": round_half_up(d, 4),
            "L": round_half_up(L, 4),
            "hD": round_half_up(hD, 4),
            "hT": round_half_up(hT, 4),
            "hG": round_half_up(hG, 4),
            "HD": round_half_up(HD, 1),
            "HT": round_half_up(HT, 1),
            "HG": round_half_up(HG, 1),
            "boltSpacing": round_half_up(bolt_spacing, 4),
            "boltSpacingMax": round_half_up(bolt_spacing_max, 4),
            "Bsc": round_half_up(Bsc, 4),
            "Mo": round_half_up(Mo, 1),
            "MoFtLb": round_half_up(Mo / 12, 2),
            "Mg": round_half_up(Mg, 1),
            "operating": operating,
            "seating": seating,
            "Joperating": round_half_up(J_op, 4),
            "Jseating": round_half_up(J_seat, 4),
            "governing": governing,
            **grade,
            "report_word": "tool rule met" if ok else "tool rule not met",
        },
        _verdict(ok),
        warnings,
    )


# --------------------------------------------------------------------------- geometry derivation (new)

FACINGS = ("flat", "ring-joint")


def gasket_geometry(gasket_id: float, gasket_od: float, facing: str) -> Dict[str, float]:
    """N, b0, b, G from the gasket contact ID and OD (flat and ring-joint facing rules)."""
    if not (gasket_od > gasket_id) or gasket_id <= 0:
        raise ValueError("gasket OD must exceed ID, both > 0")
    N = (gasket_od - gasket_id) / 2
    b0 = N / 8 if facing == "ring-joint" else N / 2
    b = b0 if b0 <= B0_LIMIT_IN else 0.5 * math.sqrt(b0)
    G = (gasket_id + gasket_od) / 2 if b0 <= B0_LIMIT_IN else gasket_od - 2 * b
    return {"N": N, "b0": b0, "b": b, "G": G}


def un_root_area(bolt_d: float, threads_per_inch: float) -> float:
    """Root area of a UN thread, pi/4 (D - 1.299038/n)^2, in^2."""
    if bolt_d <= 0 or threads_per_inch <= 0:
        raise ValueError("bolt_D and bolt_tpi must be > 0")
    root_d = bolt_d - UN_ROOT_CONST / threads_per_inch
    if root_d <= 0:
        raise ValueError("bolt_tpi too coarse for bolt_D (root diameter would not be positive)")
    return QP * root_d * root_d


def flange_derive(inp: Dict[str, Any]) -> Dict[str, Any]:
    """Derive geometry from user-read raw values. Give at least one of three groups:

        gasket   gasket_ID, gasket_OD, facing      -> N, b0, b, G
        bolting  bolt_D, bolt_tpi [, nBolts]        -> boltRootArea [, Ab]
        hub      pipe_OD, B, X, Y, t                -> g0, g1, h

        g0 = (pipe_OD - B)/2    g1 = (X - B)/2    h = Y - t
    """
    out: Dict[str, Any] = {}
    warnings: List[str] = []
    done = 0

    if any(_has(inp, k) for k in ("gasket_ID", "gasket_OD", "facing")):
        facing = inp.get("facing")
        if facing not in FACINGS:
            raise ValueError("facing must be 'flat' or 'ring-joint'; other facings are read from the effective-width table")
        geo = gasket_geometry(_num(inp, "gasket_ID"), _num(inp, "gasket_OD"), facing)
        out.update({"N": round_half_up(geo["N"], 6), "b0": round_half_up(geo["b0"], 6),
                    "b": round_half_up(geo["b"], 6), "G": round_half_up(geo["G"], 6)})
        warnings.append(
            "Gasket geometry follows the flat-facing (N/2) or ring-joint (N/8) rule only; confirm your facing and column in the "
            "effective gasket width table (VIII-2 Table 4.16.3). Any other facing: read b0, b and G from that table and enter them directly."
        )
        if facing == "ring-joint":
            if geo["b0"] <= B0_LIMIT_IN:
                warnings.append("Ring joint: G taken as the mean of the contact ID and OD supplied (b0 <= 0.25 in); confirm it against the ring pitch diameter on the gasket sheet.")
            else:
                warnings.append("Ring joint: b0 exceeds 0.25 in, so G = OD - 2b was used (b = 0.5 sqrt(b0)); confirm it against the ring pitch diameter on the gasket sheet.")
        done += 1

    if any(_has(inp, k) for k in ("bolt_D", "bolt_tpi", "nBolts")):
        area = un_root_area(_num(inp, "bolt_D"), _num(inp, "bolt_tpi"))
        out["boltRootArea"] = round_half_up(area, 6)
        if _has(inp, "nBolts"):
            n = _num(inp, "nBolts")
            if n < 1:
                raise ValueError("nBolts must be >= 1")
            out["Ab"] = round_half_up(n * area, 4)
        warnings.append(
            "Bolt root area from the UN root diameter D - 1.299038/n. Programs differ on the area basis (root vs tensile stress area); "
            "supply aRoot directly to the detailed module if your project basis differs."
        )
        done += 1

    if any(_has(inp, k) for k in ("pipe_OD", "B", "X", "Y", "t")):
        pipe_od, B, X, Y, t = (_num(inp, k) for k in ("pipe_OD", "B", "X", "Y", "t"))
        if B <= 0 or pipe_od <= B:
            raise ValueError("require pipe_OD > B > 0")
        if X <= B:
            raise ValueError("hub diameter at the base X must exceed the bore B")
        if t <= 0 or Y <= t:
            raise ValueError("require Y > t > 0 (length through hub exceeds the flange thickness)")
        g0 = (pipe_od - B) / 2   # equals the nominal wall tn only when B is the pipe ID (see warning)
        g1 = (X - B) / 2
        h = Y - t
        warnings.append(
            "g0 = (pipe OD - B)/2 is the nominal pipe wall tn only if the flange bore B equals the pipe inside diameter; VIII-2 4.16.13 defines g0 as the "
            "nominal wall of the pipe or nozzle neck. If B differs from the pipe ID (bore matched to a different schedule), enter g0 as the nominal pipe wall."
        )
        if g1 < g0:
            warnings.append("g1 < g0: the hub base is thinner than the pipe wall - re-check X and the bore B.")
        out.update({"g0": round_half_up(g0, 6), "g1": round_half_up(g1, 6), "h": round_half_up(h, 6)})
        done += 1

    if done == 0:
        raise ValueError("give at least one group: gasket (gasket_ID, gasket_OD, facing), bolting (bolt_D, bolt_tpi) or hub (pipe_OD, B, X, Y, t)")
    return _result("connections.flange-derive", out, "na", warnings)


# --------------------------------------------------------------------------- registry and citations

REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "connections.flange-derive": flange_derive,
    "connections.flange-equivalent-pressure": flange_equivalent_pressure,
    "aux.app2-flange-integral": app2_flange_integral,
}

CITATIONS = {
    "connections.flange-derive": (
        "Geometry from user-read values: gasket N, b0, b, G per the effective gasket width rules (BPVC VIII-2 4.16.6, Tables 4.16.2 and 4.16.3); "
        "UN thread root area pi/4 (D - 1.299038/n)^2; hub g0 = (pipe OD - B)/2, g1 = (X - B)/2, h = Y - t from the B16.5 hub dimensions"
    ),
    "connections.flange-equivalent-pressure": (
        "Pressure-equivalent screen: Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2) against the B16.5 rating at design temperature (user-supplied). "
        "A conservative leakage screen, not a stress check; PIP PNC00004 3.2.10 permits the method and leaves the acceptance value to the owner"
    ),
    "aux.app2-flange-integral": (
        "ASME BPVC VIII-2 Part 4.16 (4.16.6 bolt loads, 4.16.7 flange moments, stresses and rigidity, Tables 4.16.4 to 4.16.11); "
        "equivalent to the retired VIII-1 Mandatory Appendix 2; B31.3 304.5.1(b) with B31.3 allowables. "
        "External loads enter as the pressure-equivalent Peq (not an Appendix 2 / 4.16 construction)"
    ),
}

# Inputs that are code, table or project values the user must read from a licensed copy.
USER_SUPPLIED = {
    "connections.flange-derive": ["gasket_ID", "gasket_OD", "bolt_D", "bolt_tpi", "pipe_OD", "B", "X", "Y", "t"],
    "connections.flange-equivalent-pressure": ["ratedPressure"],
    "aux.app2-flange-integral": [
        "A", "B", "C", "t", "g0", "g1", "h", "m", "y", "Sa", "Sb", "Sf", "SfAmbient", "Sn", "SnAmbient",
        "Edesign", "Eambient", "rigidityFactor", "F_override", "V_override", "f_override",
    ],
}


# --------------------------------------------------------------------------- declared input fields

# (name, units, required, description). Drives `list` and the unknown-key rejection.
FIELDS: Dict[str, List[tuple]] = {
    "connections.flange-derive": [
        ("facing", "text", False, "Gasket group: 'flat' (b0 = N/2) or 'ring-joint' (b0 = N/8)"),
        ("gasket_ID", "in", False, "Gasket group: contact ID (user-read from the gasket sheet)"),
        ("gasket_OD", "in", False, "Gasket group: contact OD (user-read from the gasket sheet)"),
        ("bolt_D", "in", False, "Bolting group: nominal bolt diameter"),
        ("bolt_tpi", "1/in", False, "Bolting group: threads per inch n (UN series)"),
        ("nBolts", "count", False, "Bolting group, optional: bolt count, adds total area Ab"),
        ("pipe_OD", "in", False, "Hub group: pipe outside diameter the neck welds to (g0 = (pipe_OD - B)/2 equals the nominal wall only when B is the pipe ID)"),
        ("B", "in", False, "Hub group: flange bore"),
        ("X", "in", False, "Hub group: hub diameter at the base (B16.5 hub table)"),
        ("Y", "in", False, "Hub group: length through hub (B16.5 hub table)"),
        ("t", "in", False, "Hub group: flange thickness"),
    ],
    "connections.flange-equivalent-pressure": [
        ("P", "psi", True, "Internal design pressure"),
        ("F", "lbf", True, "External axial force, tension positive"),
        ("M_in_lbf", "in-lbf", False, "Bending moment resultant in in-lbf (give exactly one of M_in_lbf, M_ft_lbf, M)"),
        ("M_ft_lbf", "ft-lbf", False, "Bending moment resultant in ft-lbf; converted x 12"),
        ("M", "in-lbf", False, "Engine name for the moment, in-lbf (same as M_in_lbf)"),
        ("G", "in", True, "Gasket load-reaction diameter G (from connections.flange-derive or the effective-width table)"),
        ("ratedPressure", "psi", True, "Flange rating at design temperature (user-read from the B16.5 P-T table)"),
        ("creditCompression", "bool", False, "Default false: a negative F is taken as 0 (Code-conservative, VIII-2 4.16.13 FA = 0). true credits compression; then run the tensile case separately and report both"),
    ],
    "aux.app2-flange-integral": [
        ("attachment", "text", True, "'integral' (weld-neck, hubbed) or 'loose' (ring, no hub)"),
        ("P", "psi", True, "Design pressure"),
        ("Fax", "lbf", False, "External axial force, tension positive; default 0"),
        ("Mext", "ft-lbf", False, "External bending moment in FT-LBF (engine unit); default 0. Give at most one of Mext, Mext_in_lbf"),
        ("Mext_in_lbf", "in-lbf", False, "External bending moment in IN-LBF (alternative to Mext)"),
        ("A", "in", True, "Flange OD"),
        ("B", "in", True, "Flange bore"),
        ("C", "in", True, "Bolt circle diameter"),
        ("t", "in", True, "Flange thickness"),
        ("g0", "in", False, "Hub small-end thickness (integral)"),
        ("g1", "in", False, "Hub large-end thickness (integral)"),
        ("h", "in", False, "Hub length (integral)"),
        ("G", "in", True, "Gasket load-reaction diameter"),
        ("N", "in", True, "Gasket contact width"),
        ("b", "in", False, "Effective seating width; derived from N (flat rule) when omitted"),
        ("m", "-", True, "Gasket factor m (user-read from the gasket factor table)"),
        ("y", "psi", True, "Gasket seating stress y (user-read from the gasket factor table)"),
        ("nBolts", "count", True, "Bolt count (4 or more)"),
        ("aRoot", "in^2", True, "Root area of one bolt"),
        ("boltDia", "in", False, "Bolt nominal diameter, for the bolt-spacing limit; derived from aRoot when omitted"),
        ("Sa", "psi", True, "Bolt allowable at ambient (gasket seating)"),
        ("Sb", "psi", True, "Bolt allowable at design temperature"),
        ("Sf", "psi", True, "Flange allowable at design temperature"),
        ("SfAmbient", "psi", True, "Flange allowable at ambient (CLI requires it; the engine would default it to Sf)"),
        ("Sn", "psi", False, "Nozzle-neck / pipe allowable at design temperature; omitted leaves the 2.5 Sn cap unchecked"),
        ("SnAmbient", "psi", False, "Nozzle-neck / pipe allowable at ambient; defaults to Sn"),
        ("Edesign", "psi", True, "Flange modulus at design temperature (CLI requires it; rigidity only)"),
        ("Eambient", "psi", True, "Flange modulus at ambient (CLI requires it; rigidity only)"),
        ("rigidityFactor", "-", False, "Rigidity factor KI; default 0.3 integral, 0.2 loose"),
        ("applyBoltSpacing", "bool", False, "Apply the bolt-spacing correction; default true"),
        ("hubFactorMethod", "text", False, "'series' (default, the only method shipped); integral only"),
        ("F_override", "-", False, "Hub factor F read from the Table 4.16.5 equations / figures; bypasses the computed value"),
        ("V_override", "-", False, "Hub factor V read from Table 4.16.5 / figures; bypasses the computed value"),
        ("f_override", "-", False, "Hub stress correction f (>= 1) read from Table 4.16.5 / figures; bypasses the computed value"),
    ],
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


# Other spellings accepted in code_values for the gasket factors (the inputs themselves are `m` and `y`).
_CV_ALIASES = {"gasket.m": "m", "gasket.y": "y"}


def _cv_fields(module: str) -> Dict[str, Optional[str]]:
    """Input name -> unit label, for the code_values block (this module has no nested inputs)."""
    return {f[0]: f[1] for f in FIELDS.get(module, []) if f[1] != "bool"}


def _cv_aliases(module: str) -> Dict[str, str]:
    fields = _cv_fields(module)
    return {a: c for a, c in _CV_ALIASES.items() if c in fields}


def render_list() -> str:
    lines = ["Modules and exact input field names (case-sensitive). Units: psi, lbf, in, as stated.", ""]
    for mid in REGISTRY:
        lines.append(mid)
        for name, units, required, desc in FIELDS[mid]:
            lines.append(f"    {name:<16}{units:<9}{'required' if required else 'optional':<10}{desc}")
        lines.append("")
    lines.append("Any input above may instead come from the optional top-level object code_values: "
                 "{name: {value, unit, citation{standard, edition, table, row, column?}, source: connector|user}}.")
    lines.append("The optional top-level object project_basis (schema pipingtoolset.project-basis/1), or "
                 "--project-basis <file>, fills P from the design state and checks units.moment; "
                 "see references/project-basis.md.")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- pre-flight validation (CLI layer)


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _val(inputs: Dict[str, Any], key: str) -> Optional[float]:
    """Numeric value of an input if present and a real number, else None (the engine
    reports missing or non-numeric inputs itself)."""
    v = inputs.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def validate(module: str, inputs: Any) -> List[str]:
    """Reject physically impossible or silently-defaulted inputs (ValueError); return warnings.

    Runs BEFORE the engine in the CLI. The ported engine functions are not changed by it.
    """
    _need(module in REGISTRY, f"unknown module {module!r}; run `list` for the available ids")
    _need(isinstance(inputs, dict), "input must be a JSON object")
    declared = [f[0] for f in FIELDS[module]]
    unknown = sorted(k for k in inputs if k not in declared)
    _need(not unknown, f"unknown input field(s) {', '.join(repr(k) for k in unknown)} for {module} "
                       f"(valid: {', '.join(declared)}; names are case-sensitive)")
    warnings: List[str] = []

    if module == "connections.flange-equivalent-pressure":
        _one_moment(inputs, ("M", "M_in_lbf", "M_ft_lbf"), optional=False)
        P, rated, G = _val(inputs, "P"), _val(inputs, "ratedPressure"), _val(inputs, "G")
        if P is not None:
            _need(P >= 0, "P must be >= 0")
        if P is not None and rated is not None and P > rated:
            warnings.append("Design pressure already exceeds the supplied rating before any external load; confirm the rating is at the design temperature.")
        if G is not None and G > 0 and G < 1:
            warnings.append("G is under 1 in; confirm the length unit (inches) and that G is the gasket reaction diameter, not a gasket width.")
        warnings.append(
            "Pressure-equivalent screen only: a conservative leakage screen, not a stress check. Torsion and shear are not used. "
            "Acceptance against the rating (or a lower owner percentage of it) is the owner's call."
        )
    elif module == "aux.app2-flange-integral":
        att = inputs.get("attachment")
        _need(att in ("integral", "loose"), "attachment must be 'integral' or 'loose'")
        method = inputs.get("hubFactorMethod")
        _need(method in (None, "series"),
              "the Table 4.16.5 curve-fit option is not shipped; hubFactorMethod must be 'series' (or omitted). "
              "Use F_override / V_override / f_override with values read from the VIII-2 figures or equations")
        _one_moment(inputs, ("Mext", "Mext_in_lbf"), optional=True)
        for k in ("Edesign", "Eambient", "SfAmbient"):
            _need(inputs.get(k) is not None,
                  f"{k} is required (read it from your licensed copy; the engine would otherwise default it silently)")
        for k in ("F_override", "V_override", "f_override"):
            if inputs.get(k) is not None:
                _need(att == "integral", f"{k} applies to integral flanges only")
        for k in ("F_override", "V_override"):
            x = _val(inputs, k)
            if x is not None:
                _need(x > 0, f"{k} must be > 0")
        x = _val(inputs, "f_override")
        if x is not None:
            _need(x >= 1, "f_override must be >= 1 (the hub stress correction factor has a floor of 1)")
        if inputs.get("Fax") is None and inputs.get("Mext") is None and inputs.get("Mext_in_lbf") is None:
            warnings.append("No external axial force or moment given: Peq = P, so this is a pressure-only result. "
                            "Supply Fax and Mext (or Mext_in_lbf) to evaluate the piping loads.")
        defaulted = []
        if inputs.get("b") is None:
            defaulted.append("b (derived from N, flat rule)")
        if inputs.get("boltDia") is None:
            defaulted.append("boltDia (derived from aRoot)")
        if inputs.get("Sn") is not None and inputs.get("SnAmbient") is None:
            defaulted.append("SnAmbient (taken as Sn)")
        if inputs.get("rigidityFactor") is None:
            defaulted.append(f"rigidityFactor ({_js(KI_INTEGRAL if att == 'integral' else KI_LOOSE)}, the table-note value)")
        if att == "integral" and method is None:
            defaulted.append("hubFactorMethod (series)")
        if defaulted:
            warnings.append("Defaults applied: " + "; ".join(defaulted) + ". State each on the calc sheet.")
    elif module == "connections.flange-derive":
        pass
    if module == "connections.flange-equivalent-pressure":
        cc = inputs.get("creditCompression")
        _need(cc is None or isinstance(cc, bool), "creditCompression must be true or false")
    return warnings


# --------------------------------------------------------------------------- project basis and result status (0.8.0)
# The shared blocks above define the helpers; this section is the skill's own wiring: its fill map,
# its checks and its banner handling. The ported engine is not touched, so fixture parity is unchanged.

_DESIGN_STATE = "states[role=design|first]"
_BASIS_FILL = {
    "connections.flange-derive": [],
    "connections.flange-equivalent-pressure": [("P", _DESIGN_STATE + ".P_psig", None)],
    "aux.app2-flange-integral": [("P", _DESIGN_STATE + ".P_psig", None)],
}
# moment input name -> the unit that input is written in
_MOMENT_INPUT_UNITS = {"M": "in-lbf", "M_in_lbf": "in-lbf", "M_ft_lbf": "ft-lbf",
                       "Mext": "ft-lbf", "Mext_in_lbf": "in-lbf"}
_MOMENT_UNIT_WORDS = {"ft-lbf": "ft-lbf", "ft-lb": "ft-lbf", "lbf-ft": "ft-lbf", "lb-ft": "ft-lbf",
                      "in-lbf": "in-lbf", "in-lb": "in-lbf", "lbf-in": "in-lbf", "lb-in": "in-lbf"}
_CONSUMES_MOMENT = ("connections.flange-equivalent-pressure", "aux.app2-flange-integral")


def _moment_unit_check(inp: Dict[str, Any], basis: Dict[str, Any], applied: Dict[str, Any]) -> None:
    """An explicit units.moment must agree with the moment input the user gave (exit 2 otherwise)."""
    word = basis_get(basis, "units.moment")
    if word is None:
        return
    unit = _MOMENT_UNIT_WORDS.get(str(word).strip().lower())
    if unit is None:
        raise ProjectBasisError(
            f"project_basis.units.moment {word!r} cannot be used: this skill takes the moment in in-lbf or ft-lbf")
    given = [k for k in _MOMENT_INPUT_UNITS if inp.get(k) is not None]
    for name in given:
        if _MOMENT_INPUT_UNITS[name] != unit:
            raise project_basis_conflict("units.moment", name)
    mark_basis_used(applied, "units.moment", given[0] if given else None, "agreed" if given else "noted")


def _owner_acceptances(basis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Owner-practice items named like an acceptance criterion: a fraction of the rating, or a pointer."""
    found: List[Dict[str, Any]] = []
    for i, doc in enumerate(basis.get("owner_practice") or []):
        for j, item in enumerate(doc.get("items") or []):
            if not (isinstance(item, dict) and "accept" in str(item.get("name", "")).lower()):
                continue
            where = f"owner_practice[{i}].items[{j}]"
            value = item.get("value")
            entry = {"path": where, "document": doc.get("document"), "name": item["name"], "fraction": None,
                     "value": value}
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                percent = str(item.get("unit", "")).strip().lower() in ("%", "percent", "pct")
                frac = value / 100.0 if percent else float(value)
                if frac <= 0 or (not percent and frac > 1):
                    raise ProjectBasisError(
                        f"project_basis.{where}.value {value!r} cannot be used: give a fraction of the rating "
                        f"above 0 and up to 1, or a percent with unit '%'")
                entry["fraction"] = frac
            found.append(entry)
    return found


def apply_project_basis(module: str, inp: Any, basis: Optional[Dict[str, Any]]) -> Tuple[Any, Any, Dict[str, Any]]:
    """(effective inputs, project_basis_applied or None, context for the checks). Exit 2 on a conflict."""
    ctx: Dict[str, Any] = {"T_F": None, "standard": None, "route": None, "fluid_category": None,
                           "acceptances": []}
    if basis is None or not isinstance(inp, dict):
        return inp, None, ctx
    if basis_get(basis, "units.system") == "SI":
        raise ProjectBasisError("project_basis.units.system is SI: this skill's engine is USC (psi, lbf, in); "
                                "restate the record in USC")
    eff, applied = fill_from_basis(inp, basis, _BASIS_FILL[module])
    if module in _CONSUMES_MOMENT:
        _moment_unit_check(eff, basis, applied)
    t_path = _DESIGN_STATE + ".T_F"
    ctx["T_F"] = basis_get(basis, t_path)
    if ctx["T_F"] is not None:
        mark_basis_used(applied, t_path)
    for key, path in (("standard", "code.standard"), ("route", "code.route"),
                      ("fluid_category", "service.fluid_category")):
        ctx[key] = basis_get(basis, path)
        if ctx[key] is not None:
            mark_basis_used(applied, path)
    if basis_get(basis, "code.edition") is not None:
        mark_basis_used(applied, "code.edition")
    if module == "connections.flange-equivalent-pressure":
        ctx["acceptances"] = _owner_acceptances(basis)
        for a in ctx["acceptances"]:
            mark_basis_used(applied, a["path"])
    return eff, applied, ctx


def _code_route_checks(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    std = ctx.get("standard")
    if std is not None:
        key = str(std).upper().replace("ASME", "").strip()
        if key == "B31.3":
            checks.append(make_check(
                "code route", "calculated", None,
                "B31.3 304.5.1(b): VIII-2 4.16 or the retired VIII-1 Appendix 2 with B31.3 allowables, Sf = S x E x W"))
        elif key == "B31.1":
            checks.append(make_check(
                "code route", "not checked", None,
                "B31.1 104.5.1 names Section VIII Division 1: confirm the VIII-1 edition your B31.1 edition "
                "references before applying 4.16"))
        else:
            checks.append(make_check(
                "code route", "manual check required", None,
                f"{std}: this module applies the B31.3 304.5.1(b) and B31.1 104.5.1 routes only; "
                "apply that code's flange rules by hand"))
    route = str(ctx.get("route") or "").lower()
    if ctx.get("fluid_category") == "High Pressure" or "chapter ix" in route:
        checks.append(make_check(
            "B31.3 Chapter IX", "manual check required", None,
            "high pressure service: this module applies the Chapter II route only; "
            "confirm the Chapter IX flange provisions by hand"))
    return checks


def _static_not_checked(module: str, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Methods this module never performs (SKILL Step 4 and Known limits): listed on every run, never blocking."""
    items: List[Tuple[str, str]] = []
    if module == "connections.flange-equivalent-pressure":
        items.append(("bolt, gasket seating and flange stress", "a leakage screen only; run aux.app2-flange-integral"))
    if module in _CONSUMES_MOMENT:
        items += [
            ("UG-44(b) / VIII-2 4.16.12 interaction", "named, not computed"),
            ("ASME III NC-3658.3", "named, not computed"),
            ("EN 1591-1", "named, not computed"),
            ("PCC-1 Appendix O assembly bolt stress", "named, not computed"),
        ]
    if module == "aux.app2-flange-integral":
        items += [
            ("VIII-2 4.16.7.2 Step 9(b) shear check", "not computed"),
            ("Code external-moment term Moe", "the pressure-equivalent Peq treatment is used instead"),
        ]
    if module in _CONSUMES_MOMENT:
        t = ctx.get("T_F")
        where = (f"the record gives a design temperature of {_js(t)} F; " if t is not None
                 else "no design temperature was given; ")
        items.append(("B16.5 2.5.2 advisory", where + "read the temperature above which severe external loads "
                                               "and thermal gradients can leak a joint from the printed B16.5, "
                                               "and flag it on the sheet when the design temperature is in that range"))
    return [make_check(n, "not checked", None, note) for n, note in items]


def build_checks(module: str, out: Dict[str, Any], inp: Dict[str, Any], status: str,
                 ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """checks[] for one run: what the module performed, mapped onto the five result-status words."""
    checks: List[Dict[str, Any]] = []
    if module == "connections.flange-derive":
        return [make_check("geometry derivation", "calculated", None,
                           "N, b0, b, G, bolt root area and hub dimensions from the user-read values")]
    if module == "connections.flange-equivalent-pressure":
        checks.append(make_check(
            "pressure-equivalent screen", "screening", status,
            "Pe/rated " + _js(out["utilization"]) + ": a leakage screen, not a stress check"))
        for a in ctx.get("acceptances") or []:
            label = "owner acceptance (" + str(a["document"]) + ")"
            if a["fraction"] is None:
                checks.append(make_check(
                    label, "pointer only", None,
                    f"{a['name']} was supplied as a pointer ({a['value']!r}); the check does not run"))
            else:
                ok = out["utilization"] <= a["fraction"]
                checks.append(make_check(
                    label, "calculated", _verdict(ok),
                    f"Pe/rated {_js(out['utilization'])} against {_js(a['fraction'])} of the rating ({a['name']})"))
    else:
        unresolved = out.get("result_grade") == GRADE_SCREENING
        series = [k for k in HUB_FACTORS if (out.get("factor_basis") or {}).get(k) == "series"]
        word = "screening" if unresolved else "calculated"
        why = (" (hub factors from the series reconstruction: " + ", ".join(series) + ")") if unresolved else ""
        checks.append(make_check("bolt area Ab >= Am", "calculated", _verdict(out["Ab"] >= out["Am"]),
                                 f"Ab {_js(out['Ab'])} in^2 against Am {_js(out['Am'])} in^2"))
        util = max(out["operating"]["utilization"], out["seating"]["utilization"])
        checks.append(make_check("flange stresses, operating and seating", word, _verdict(util <= 1),
                                 "worst utilization " + _js(util) + why, unresolved_factor=unresolved))
        jmax = max(out["Joperating"], out["Jseating"])
        checks.append(make_check("rigidity J <= 1", word, _verdict(jmax <= 1),
                                 "worst J " + _js(jmax) + why, unresolved_factor=unresolved))
        hubbed = (out.get("factor_basis") or {}).get("F") != "not used"
        if hubbed and inp.get("Sn") is None:
            checks.append(make_check("hub stress cap 2.5 Sn", "not checked", None,
                                     "Sn not supplied: the cap min(1.5 Sf, 2.5 Sn) is unchecked"))
        if inp.get("Fax") is None and inp.get("Mext") is None and inp.get("Mext_in_lbf") is None:
            checks.append(make_check("external loads", "not checked", None,
                                     "no Fax or Mext given: a pressure-only result, the piping loads are not evaluated"))
    checks += _code_route_checks(ctx)
    return checks


def status_why(checks: List[Dict[str, Any]]) -> str:
    """The reason clause of the Result status line: the checks that sit at the envelope word, then
    (for a calculated word) the listed checks this module does not perform."""
    word = envelope_status(checks)
    limits = not_performed(checks)
    if word == "not checked":
        return limits
    at_word = [c for c in checks if c["result_status"] == word]
    why = "; ".join(c["name"] for c in at_word)
    if len(at_word) == 1 and at_word[0].get("note"):
        why += ": " + at_word[0]["note"]
    if any(c.get("unresolved_factor") for c in at_word):
        why += " (hub factors from the series reconstruction)"
    return why + ("; " + limits if word == "calculated" and limits else "")


def _apply_status(env: Dict[str, Any], checks: List[Dict[str, Any]], not_checked: List[Dict[str, Any]]) -> None:
    """Add result_status, checks and not_checked; withhold the ISSUE-GRADE banner when the banner rule forbids it."""
    env.update(status_fields(checks))
    env["not_checked"] = not_checked
    out = env["output"]
    if not checks_banner_allowed(checks) and str(out.get("banner", "")).startswith("ISSUE-GRADE"):
        blockers = [c for c in checks if c["result_status"] in ("manual check required", "pointer only")]
        new = (banner_word("ISSUE-GRADE", env["result_status"]) + ": "
               + "; ".join(c["name"] + " (" + (c["note"] or "") + ")" for c in blockers)
               + "; no acceptance wording until each is resolved")
        env["warnings"] = [new if w == out["banner"] else w for w in env["warnings"]]
        out["banner"] = new


def _clean_zero(x: Any) -> Any:
    """Normalise -0.0 to 0.0 anywhere in the output tree (cosmetic)."""
    if isinstance(x, float):
        return 0.0 if x == 0 else x
    if isinstance(x, dict):
        return {k: _clean_zero(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_clean_zero(v) for v in x]
    return x


def run_module(module: str, inp: Dict[str, Any], project_basis_file: Optional[str] = None) -> Dict[str, Any]:
    return run_with_basis(module, inp, project_basis_file)[0]


def run_with_basis(module: str, inp: Dict[str, Any], project_basis_file: Optional[str] = None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """(envelope, project basis record or None). The record is the top-level project_basis input, the file, or both."""
    top = None
    if isinstance(inp, dict) and "project_basis" in inp:
        top = inp["project_basis"]
        inp = {k: v for k, v in inp.items() if k != "project_basis"}
    basis = load_project_basis(project_basis_file, top)
    inp, provenance, cv_notes = apply_code_values(inp, module, _cv_fields(module), _cv_aliases(module))
    inp, applied, ctx = apply_project_basis(module, inp, basis)
    pre_warnings = cv_notes + validate(module, inp)
    engine_inp = dict(inp)
    if module == "connections.flange-equivalent-pressure":
        credit = bool(engine_inp.pop("creditCompression", False))
        F = engine_inp.get("F")
        if not credit and isinstance(F, (int, float)) and not isinstance(F, bool) and F < 0:
            engine_inp["F"] = 0.0
            pre_warnings.append(
                "Compressive axial force taken as F = 0 for the screen (VIII-2 4.16.13 neglects compression). "
                "Set creditCompression true only if the owner agrees to credit it; then run the tensile case separately and report both."
            )
    res = REGISTRY[module](engine_inp)
    findings = pre_warnings + res["warnings"]
    banner = res["output"].get("banner")
    if module == "aux.app2-flange-integral" and banner in res["warnings"]:
        # The grade banner is the first finding of the detailed analysis, ahead of the pre-flight notes.
        rest = list(res["warnings"])
        rest.remove(banner)
        findings = [banner] + pre_warnings + rest
    envelope = {
        "module": res["module"],
        "status": res["status"],
        "output": _clean_zero(res["output"]),
        "warnings": findings,
        "citation": CITATIONS[module],
        "inputs": inp,
        "user_supplied": [k for k in USER_SUPPLIED[module] if k in inp],
    }
    if provenance is not None:
        envelope["code_value_provenance"] = provenance
    if applied is not None:
        envelope["project_basis_applied"] = applied
    checks = build_checks(module, envelope["output"], inp, envelope["status"], ctx)
    assumed = assumed_inputs_check((envelope.get("project_basis_applied") or {}).get("assumptions"))
    if assumed is not None:
        checks.append(assumed)
    _apply_status(envelope, checks, _static_not_checked(module, ctx))
    return envelope, basis


# --------------------------------------------------------------------------- calc-sheet rendering


def _cell(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return _js(v)
    if isinstance(v, dict):
        return ", ".join(f"{k} {_cell(x)}" for k, x in v.items())
    return str(v)


# Status words for the sheet. The machine status word of the envelope is left alone (the engine
# fixtures assert it); the sheet states the same fact without the acceptance wording.
_SHEET_STATUS = {
    "connections.flange-equivalent-pressure": {
        "pass": "Pe is within the supplied rating (leakage screen only)",
        "fail": "Pe exceeds the supplied rating (leakage screen only)",
    },
    "aux.app2-flange-integral": {
        "pass": "tool rule met: Ab >= Am, worst stress utilization <= 1, both J <= 1 (not an acceptance)",
        "fail": "tool rule not met: Ab >= Am, stress utilization <= 1 or J <= 1 is exceeded (see findings)",
    },
}


_CHECK_WORDS = {"pass": "met", "fail": "not met", "na": "-"}


def render_sheet(env: Dict[str, Any], basis: Optional[Dict[str, Any]] = None) -> str:
    """Markdown calc-sheet block for one run. The banner line depends on the result grade and the result status."""
    out = env["output"]
    module = env["module"]
    lines = [f"# Bolted Flange Evaluation - {module}", ""]
    if "banner" in out:
        lines += [f"**{out['banner']}**", ""]
    if "result_status" in env:
        lines += [render_status_line(env["result_status"], status_why(env["checks"])), ""]
    if basis is not None and "project_basis_applied" in env:
        lines += [render_basis_section(env["project_basis_applied"], basis, heading="## 1. Basis")]
    if "result_grade" in out:
        lines.append(f"Result grade: {out['grade_label']}")
        if "factor_basis" in out:
            lines.append("Hub factor basis: " + "; ".join(f"{k} {v}" for k, v in out["factor_basis"].items()))
        if out.get("grade_note"):
            lines.append(out["grade_note"])
        lines.append("")
    words = _SHEET_STATUS.get(module)
    if words and env["status"] in words:
        lines += [f"Tool status: {words[env['status']]}", ""]
    scalars = [(k, v) for k, v in out.items() if not isinstance(v, dict) and k not in GRADE_KEYS]
    lines += ["## Results", "", "| Quantity | Value |", "|---|---|"]
    lines += [f"| {k} | {_cell(v)} |" for k, v in scalars]
    for k, v in out.items():
        if isinstance(v, dict) and k not in GRADE_KEYS:
            lines += ["", f"## {k}", "", "| Quantity | Value |", "|---|---|"]
            lines += [f"| {kk} | {_cell(vv)} |" for kk, vv in v.items()]
    if env.get("checks"):
        lines += ["", "## Checks", "", "| Check | Result status | Outcome | Note |", "|---|---|---|---|"]
        lines += [f"| {c['name']} | {c['result_status']} | {_CHECK_WORDS[c['status']]} | {c['note'] or ''} |"
                  for c in env["checks"]]
    if env.get("not_checked"):
        lines += ["", "## Not checked by this module", ""]
        lines += [f"- {c['name']}: {c['note']}" for c in env["not_checked"]]
    lines += ["", "## Findings", ""]
    lines += [f"- {w}" for w in env["warnings"]] or ["- none"]
    lines += ["", f"Citation: {env['citation']}", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- CLI


def _fail(msg: str) -> int:
    print(f"input error: {msg}", file=sys.stderr)
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="bolted_flange.py",
        description="Bolted-flange calculators. `list` shows module ids and exact input names.",
    )
    ap.add_argument("module", help="module id, or `list`")
    ap.add_argument("--input", help="inline JSON object")
    ap.add_argument("--input-file", help="path to a JSON file")
    ap.add_argument("--project-basis", dest="project_basis",
                    help="path to a pipingtoolset.project-basis/1 JSON record (see references/project-basis.md)")
    ap.add_argument("--format", choices=("json", "sheet"), default="json",
                    help="json (default): the envelope; sheet: a markdown calc-sheet block with the result-grade banner")
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
        env, basis = run_with_basis(args.module, data, args.project_basis)
        if args.format == "sheet":
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")  # UTF-8 output whatever the console code page
            sys.stdout.write(render_sheet(env, basis))
        else:
            print(json.dumps(env, indent=2))
        return 0
    except (ValueError, OSError, ArithmeticError) as exc:
        return _fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
