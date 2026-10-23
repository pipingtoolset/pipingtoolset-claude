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

Exit codes: 0 every combination passes and no critical review finding; 3 every
combination passes but a critical review finding stands (e.g. pipe moments the model
cannot carry); 2 a limit state fails; 1 the spec is defective.
Standard library only (Python 3.9+).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipe_support import loads as L  # noqa: E402
from pipe_support import optimizer as O  # noqa: E402
from pipe_support import report as R  # noqa: E402
from pipe_support import review as V  # noqa: E402
from pipe_support.assembly import CSA_PRESETS, analyze_assembly  # noqa: E402
from pipe_support.common import InputError  # noqa: E402


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
    design = resolve_design(spec)
    method = design["method"]
    doc = {"spec": spec, "design": design, "notes": [],
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
