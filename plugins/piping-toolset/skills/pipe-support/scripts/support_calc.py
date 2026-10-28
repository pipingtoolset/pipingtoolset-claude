#!/usr/bin/env python3
"""support_calc - pipe-support assembly check, review and optimisation from one spec.

    python support_calc.py spec.json [--report calc.md] [--json result.json]
                                     [--no-optimize] [--quiet]

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

Exit codes: 0 every combination passes and no critical review finding; 3 every
combination passes but a critical review finding stands (e.g. pipe moments the model
cannot carry); 2 a limit state fails, or the code_values block cannot be applied (message
"input error: ..." on stderr, no verdict); 1 the spec is defective.
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


def run(spec: dict, optimize: bool = True) -> dict:
    try:
        spec, cv_provenance, cv_notes = apply_code_values(spec, "the support spec", _CV_FIELDS, _CV_ALIASES,
                                                          keys=("code_values", "codeValues"))
    except ValueError as exc:
        raise CodeValuesError(str(exc)) from None
    design = resolve_design(spec)
    method = design["method"]
    doc = {"spec": spec, "design": design, "notes": list(cv_notes),
           "assumed": list(spec.get("assumed", [])) + preset_provenance(spec)}
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
        doc["code_value_applied"] = _cv_applied(spec, cv_provenance)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--report", help="write the Markdown calculation report here")
    ap.add_argument("--json", help="write the JSON result document here")
    ap.add_argument("--no-optimize", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="print only the one-line verdict")
    a = ap.parse_args(argv)
    try:
        with open(a.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        doc = run(spec, optimize=not a.no_optimize)
    except CodeValuesError as e:
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
    head = "FAIL" if env["status"] != "pass" else (f"PASS WITH {crit} CRITICAL FINDING(S)" if crit else "PASS")
    verdict = (f"{head} - {env['governingStage']} / {env['governingCheck']} = "
               f"{env['governingRatio']} ({env['governingCombo']})")
    verdict = verdict.replace("\u2014", "-").encode("ascii", "replace").decode("ascii")
    if a.quiet:
        print(verdict)
    else:
        sys.stdout.buffer.write(md.encode("utf-8"))
    return 2 if env["status"] != "pass" else (3 if crit else 0)


if __name__ == "__main__":
    sys.exit(main())
