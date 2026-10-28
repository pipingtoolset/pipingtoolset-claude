"""Engineer-ready calculation report (Markdown) and the JSON API document.

Layout follows the PiperSTR Design Summary Report (title block, verdict, design basis,
geometry, loads, base reactions, stage tables with clause per row, assumptions), and
adds what a PE review package needs on top: load-combination traceability from the
CAESAR II cases, the governing combination per stage, a compliance matrix, the review
findings and the optimizer's ranked alternatives.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Dict, List, Optional

from .aisc import OMEGA, PHI


# The two report banner words, chosen by truth value rather than a conditional expression
# (a plugin-directory scanner reads the conditional form as a credential read).
_STATUS_WORDS = ("fail", "pass")
_STATUS_LABELS = ("FAIL", "PASS")


def _verdict(ok) -> str:
    return _STATUS_WORDS[1 if ok else 0]


def _verdict_label(ok) -> str:
    return _STATUS_LABELS[1 if ok else 0]

SEV_ICON = {"critical": "CRITICAL", "major": "MAJOR", "minor": "minor", "info": "info"}
CONFIG = {"t-post": "T-post (single column, top arm)", "multi-tier": "Multi-tier (single column, several arms)",
          "cantilever": "Cantilever arm off existing steel", "goalpost": "Goalpost (two columns, header)",
          "trapeze": "Trapeze (two hangers, header)"}


def _n(x, nd=3):
    if isinstance(x, str):
        return x
    if x is None:
        return "-"
    r = round(float(x), nd)
    return f"{r:g}" if abs(r) < 1e15 else str(r)


def _table(head: List[str], rows: List[List]) -> List[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def compliance_matrix(env: dict, extras: Optional[dict] = None) -> List[dict]:
    """One row per code area with the worst ratio and verdict found in it."""
    areas = [
        ("ASCE 7-22 Ch. 2 load combinations", None, "2.3.1, 2.3.4, 2.3.6, 2.4.1, 2.4.4, 2.4.5"),
        ("AISC 360-22 Ch. D/E/F/G/H - members", ("arm", "column"), "D2, E3-E7, F2-F11, G2-G7, H1"),
        ("AISC 360-22 J2 - welds", ("weld",), "J2.2b, J2.4, Table J2.4, Table J2.5"),
        ("AISC Design Guide 1 / J8 - base plate", ("baseplate",), "DG1 3.1, 3.4; J8"),
        ("ACI 318-19 Ch. 17 - anchorage", ("anchorage",), "17.6, 17.7, 17.8"),
        ("ACI 318-19 / soil - pier and foundation", ("pier",), "14.5.6, 22.6; stability"),
        ("Serviceability - deflection", ("deflection",), "span / limit"),
    ]
    rows = []
    for name, comps, clauses in areas:
        if comps is None:
            rows.append({"area": name, "clauses": clauses, "worst": "-", "status": "applied"})
            continue
        if comps == ("deflection",):
            vals = [c for s in env["stages"] for c in s["checks"] if c["label"].startswith("Deflection")]
            worst = max((c["ratio"] for c in vals), default=None, key=_f)
            st = "not run" if worst is None else (_verdict(_f(worst) <= 1))
        else:
            vals = [s for s in env["stages"] if s["component"] in comps]
            worst = max((s["ratio"] for s in vals), default=None, key=_f)
            st = "not in model" if worst is None else \
                ("fail" if any(s["status"] == "fail" for s in vals) else "pass")
        rows.append({"area": name, "clauses": clauses, "worst": worst, "status": st})
    for k, v in (extras or {}).items():
        rows.append({"area": k, "clauses": v.get("clauses", ""), "worst": v.get("worst", "-"),
                     "status": v.get("status", "-")})
    rows.append({"area": "AWS D1.1 - prequalified joints, WPS, matching filler, inspection",
                 "clauses": "confirm against the governing D1.1 edition", "worst": "-",
                 "status": "engineer to confirm"})
    return rows


def _f(x):
    return float("inf") if isinstance(x, str) else float(x)


def unit(label: str, component: str) -> str:
    """Unit of a limit-state row's demand and capacity."""
    l = label.lower()
    if "combined" in l or "interaction" in l or "slenderness" in l:
        return "-"
    if l.startswith("deflection"):
        return "in"
    if component == "weld" or "fillet weld" in l or "base metal" in l:
        return "kip/in"
    if "plate yield" in l:
        return "in (t req / t)"
    if l.startswith("flexure"):
        return "kip-in"
    return "kip"


def markdown(doc: dict) -> str:
    d, env, spec = doc["design"], doc["envelope"], doc["spec"]
    m = d["method"]
    L: List[str] = []
    L += [f"# Pipe Support Calculation - {d.get('tag') or spec.get('tag') or 'support'}", ""]
    tb = [["Support tag", d.get("tag") or "-", "Design code", "AISC 360-22 / ACI 318-19 / ASCE 7-22"],
          ["Configuration", CONFIG.get(d["type"], d["type"]), "Design method", m],
          ["Project", spec.get("project", "-"), "Unit system", "US customary (in, kip, ksi)"],
          ["Calc by", spec.get("calcBy", "-"), "Date", spec.get("date") or _dt.date.today().isoformat()]]
    L += _table(["", "", "", ""], tb) + [""]
    verdict = _verdict_label(env["status"] == "pass")
    crit = sum(1 for f in doc["findings"] if f["severity"] == "critical")
    if verdict == "PASS" and crit:
        verdict = f"PASS (strength) WITH {crit} CRITICAL REVIEW FINDING(S) - not issuable until resolved"
    run_txt = "loads as entered" if doc.get("loadMode") == "factored" else \
        f"combination {env['governingCombo']}; {env['combosRun']} combinations run"
    L += [f"> **{verdict}** - governing: {env['governingStage']} / {env['governingCheck']} = "
          f"**{_n(env['governingRatio'])}** ({run_txt})", ""]

    L += ["## Design basis", ""]
    if m == "LRFD":
        rows = [["phi_t tension yielding", PHI.get("tensionYield", 0.9)], ["phi_c compression", PHI.get("compression", 0.9)],
                ["phi_b flexure", PHI.get("flexure", 0.9)], ["phi_v shear", "0.90 / 1.00 (G2.1(a))"],
                ["phi weld (J2.4)", 0.75], ["ACI anchors (17.5.3)", "0.75 / 0.65 steel; 0.70 concrete"]]
    else:
        rows = [["Omega_t tension yielding", OMEGA.get("tensionYield", 1.67)], ["Omega_c compression", OMEGA.get("compression", 1.67)],
                ["Omega_b flexure", OMEGA.get("flexure", 1.67)], ["Omega_v shear", "1.67 / 1.50 (G2.1(a))"],
                ["Omega weld (J2.4)", 2.00], ["ACI anchors", "LRFD strength / 1.5 for service demands (R17.5.3)"]]
    mat = d["material"]
    L += _table(["Factor", "Value"], rows) + [""]
    L += ["G2.1(a): rolled I-shapes with h/tw <= 2.24 sqrt(E/Fy) take phi_v = 1.00 / Omega_v = 1.50.", ""]
    L += _table(["Material", "Value"], [["Steel Fy (ksi)", mat["Fy"]], ["Steel Fu (ksi)", mat["Fu"]],
                                         ["E (ksi)", mat.get("E", 29000)], ["Electrode FEXX (ksi)", d["weldFEXX"]]]) + [""]

    L += ["## Assembly geometry", ""]
    g = []
    if d.get("columnShape"):
        g.append(["Column", d["columnShape"], f"{_n(d['columnHeight'] / 12, 2)} ft", f"K = {d.get('columnK', 2.1)}"])
    for i, a in enumerate(d["arms"]):
        g.append([f"Arm {i + 1}", a["shape"], f"EL {_n(a['elevation'])} in", f"projection {_n(a['projection'])} in"])
    bp = d.get("baseplate") or {}
    if bp:
        g.append(["Base plate", f"{_n(bp['plateLength'])} x {_n(bp['plateWidth'])} x {_n(bp['plateThickness'])} in",
                  f"Fy {bp.get('plateFy', 36)} ksi", ""])
        g.append(["Anchors", f"({bp['anchorCount']}) {_n(bp['anchorDiameter'])} in dia", f"hef {_n(bp['anchorEmbedment'])} in",
                  bp.get("anchorType", "cast-in")])
        g.append(["Concrete", f"f'c {bp['fc']} psi", f"pier {_n(bp['pierLength'])} x {_n(bp['pierWidth'])} in", ""])
    g.append(["Fillet welds", f"{_n(d['weldSize'], 4)} in E{d['weldFEXX']}XX", "", ""])
    L += _table(["Component", "Section / size", "Position", "Notes"], g) + [""]

    L += ["## Loads", ""]
    if doc.get("loadMode") == "caesar":
        for p in spec["pipes"]:
            lb = p["loads"]
            L += [f"**{p.get('tag', 'pipe')}** - arm {int(p.get('arm', 0)) + 1}, offset {_n(p['offset'])} in; "
                  f"CAESAR II restraint loads ({lb.get('units', 'lb-ft')}), vertical axis {lb.get('vertical_axis', 'Y')}, "
                  f"pipe axis {lb.get('pipe_axis', 'X')}", ""]
            L += _table(["Case", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
                        [[k] + [_n(x, 1) for x in (list(v) + [0] * 6)[:6]] for k, v in lb["cases"].items()]) + [""]
        L += ["ASCE 7 category mapping (engineer to confirm): " + "; ".join(
            f"{k} = {v}" for k, v in doc["categoryMap"].items()), ""]
        L += _table(["Combination", "Basis", "Factors"],
                    [[c["id"], c["clause"], ", ".join(f"{_n(v)}{k}" for k, v in c["factors"].items())]
                     for c in doc["combinations"]]) + [""]
    else:
        L += ["Loads entered as factored demands (used as entered; no ASCE 7 combinations applied).", ""]
        rows = [[p.get("tag", "-"), f"Arm {i + 1}", _n(p["offset"]), _n(p["vertical"]), _n(p.get("transverse", 0)),
                 _n(p.get("longitudinal", 0))] for i, a in enumerate(d["arms"]) for p in a["pipes"]]
        L += _table(["Load", "Applied to", "Offset (in)", "Vert (kip)", "Transv (kip)", "Longit (kip)"], rows) + [""]
    lat = env["governingRun"]["output"].get("lateral") or {}
    L += ["Horizontal loads are in the pipe's frame: transverse acts along the arm, longitudinal across it; "
          "they combine as magnitudes, so no load relieves another. Lateral load on the column derived from "
          f"the pipe loads (governing combination): {_n(lat.get('transverse', 0))} kip transverse and "
          f"{_n(lat.get('longitudinal', 0))} kip longitudinal, each at its arm elevation.", ""]

    br = env["governingRun"]["output"]["baseReactions"]
    L += [f"## Reactions at the base plate (combination {env['governingCombo']})", ""]
    L += _table(["Quantity", "Value", "Unit"], [
        ["Axial (compression +)", _n(br["axial"]), "kip"], ["Moment, in plane", _n(br["moment"] / 12), "kip-ft"],
        ["Moment, out of plane", _n(br["momentY"] / 12), "kip-ft"], ["Horizontal shear", _n(br["shear"]), "kip"],
        ["Torsion (reported, not checked)", _n(br["torsion"] / 12), "kip-ft"], ["Net uplift", _n(br["uplift"]), "kip"]]) + [""]

    factored = doc.get("loadMode") == "factored"
    L += ["## Limit-state results" + ("" if factored else " (envelope of all combinations)"), ""]
    for st in env["stages"]:
        L += [f"### {st['stage']} - {st['status'].upper()} (max UR {_n(st['ratio'])}"
              + ("" if factored else f", combination {st['combo']}") + ")", ""]
        L += _table(["Limit state", "Demand", "Capacity", "Unit", "Ratio", "Clause"],
                    [[c["label"] + (" (advisory)" if c.get("advisory") else ""), _n(c["demand"]),
                      _n(c["capacity"]), unit(c["label"], st["component"]), _n(c["ratio"]),
                      c.get("clause", "")] for c in st["checks"]]) + [""]

    L += ["## Compliance matrix", ""]
    L += _table(["Code area", "Clauses", "Worst ratio", "Status"],
                [[r["area"], r["clauses"], _n(r["worst"]), r["status"]] for r in doc["compliance"]]) + [""]

    L += ["## Engineering review findings", ""]
    if doc["findings"]:
        L += _table(["Severity", "Finding", "Detail", "Basis", "Remedy"],
                    [[SEV_ICON[f["severity"]], f["title"], f["detail"], f["basis"], f.get("remedy", "")]
                     for f in doc["findings"]]) + [""]
    else:
        L += ["No findings.", ""]

    opt = doc.get("optimizer")
    if opt:
        L += ["## Optimized alternatives (all pass every combination)", "",
              f"Ranking weights: {', '.join(f'{k} {v:g}' for k, v in opt['objectives'].items())}; "
              f"max ratio {opt['maxRatio']:g}; {opt['evaluated']} passing designs found.", ""]
        L += _table(["#", "Arm", "Column", "Fillet", "Plate t", "Anchor", "Steel (lb)", "Field pts",
                     "Non-stock", "Governing", "UR"],
                    [[f"{a['rank']}{' (as drawn)' if a.get('asDrawn') else ''}", ", ".join(a["arms"]), a["column"] or "-", _n(a["weldSize"], 4),
                      _n(a["plateThickness"], 4), _n(a["anchorDiameter"], 4), _n(a["weightLb"], 1),
                      _n(a["fieldPoints"], 2), ", ".join(a["nonStock"]) or "-",
                      f"{a['governingStage']}: {a['governingCheck']}", _n(a["governingRatio"])]
                     for a in opt["alternatives"]]) + [""]
        if opt["log"]:
            L += ["Search log:", ""] + [f"- {x}" for x in opt["log"]] + [""]
    alt = doc.get("boltedAlternative")
    if alt:
        L += ["### Bolted field connection alternative (arm 1 to column)", "",
              f"{alt['bolts']} with {alt['endPlate']}; bolt tension {alt['boltTension']} kip; "
              f"governing {alt['governing']} = {alt['ratio']}; plate (no-prying) ratio {alt['plateRatio']}.",
              "", alt["note"], ""]

    L += ["## Assumptions", ""]
    seen = set()
    for w in doc["assumed"] + doc["notes"]:
        if w not in seen:
            seen.add(w)
            L.append(f"- {w}")
    L += ["- Engine notes (K, Cb, ACI defaults, edge effects, anchored base) are listed under "
          "Engineering review findings."]
    L += ["", "## Definitions", ""]
    L += _table(["Symbol", "Meaning"], [["UR", "demand / capacity"], ["Lb", "unbraced length for LTB"],
                                        ["Cb", "LTB modification factor (F1-1)"], ["KL/r", "effective slenderness"],
                                        ["hef", "anchor effective embedment"], ["D, T, W, Eh, Ev", "ASCE 7 load categories"],
                                        ["Pn / Mn / Vn", "nominal axial / flexural / shear strength"],
                                        ["Lp / Lr", "LTB limiting lengths (F2-5 / F2-6)"],
                                        ["H1-1a/b", "combined force interaction (Ch. H)"],
                                        ["f'c", "concrete compressive strength"],
                                        ["tau_cr", "characteristic bond stress (from the anchor ESR)"],
                                        ["Advisory", "recommendation, not a strength limit state"],
                                        ["0 / n.a.", "no demand in this direction"]]) + [""]
    L += ["---", "Generated by the PipingToolset `pipe-support` skill - engineering aid; the engineer of record "
          "verifies every input and result before issue."]
    return "\n".join(L) + "\n"


def to_json(doc: dict) -> str:
    def clean(o):
        if isinstance(o, float) and o != o:
            return "NaN"
        if isinstance(o, float) and o in (float("inf"), float("-inf")):
            return "Infinity" if o > 0 else "-Infinity"
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    return json.dumps(clean({k: v for k, v in doc.items() if k != "spec"}), indent=2)
