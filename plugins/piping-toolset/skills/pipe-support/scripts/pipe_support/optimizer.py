"""Load-combination envelope and design optimizer for a pipe-support assembly.

Every number here comes from the engine (assembly.analyze_assembly and the modules it
calls). The optimizer never estimates a capacity: it ENUMERATES code-checked candidates
and ranks the ones that pass. The assistant explains the ranking; it does not invent it.

Envelope: each design is run for every ASCE 7-22 combination (loads.combinations) and
the worst ratio per stage is kept with the combination that produced it. With LRFD, a
pier that is not anchored into existing concrete is checked at SERVICE level (ASD
combinations), because soil bearing, overturning and sliding are allowable-stress checks.

Search (per family, lightest first): arm shape, column shape, then the smallest standard
fillet, base plate thickness and anchor diameter that pass. Screening uses the governing
combinations only; every finalist is re-run against ALL combinations before it is shown.

Ranking objectives (weights from the spec, default 1 each):
    weight    steel weight of arms + column + base plate, lb
    field     field-effort points (field welds, weld passes, drilled anchors, bolts)
    standard  count of non-stocked sizes (shapes, plate, fillet, anchor)
"""

from __future__ import annotations

import copy
import itertools
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import loads as L
from .aisc import find_shape, shapes_by_family
from .assembly import analyze_assembly
from .common import InputError, round_half_up

STEEL_LB_PER_IN3 = 0.2836

# Stocked sizes common in pipe-support fabrication (preference list, not a code limit).
STOCK = {
    "W": "W4X13 W6X9 W6X12 W6X15 W6X20 W6X25 W8X10 W8X13 W8X15 W8X18 W8X21 W8X24 W8X31 "
         "W10X12 W10X15 W10X19 W10X22 W10X26 W10X33 W12X14 W12X16 W12X19 W12X26 W12X35 W12X40",
    "HSS-SQ": "HSS3X3X1/4 HSS4X4X1/4 HSS4X4X3/8 HSS5X5X1/4 HSS5X5X3/8 HSS6X6X1/4 HSS6X6X3/8 "
              "HSS8X8X1/4 HSS8X8X3/8 HSS8X8X1/2",
    "HSS-RECT": "HSS4X3X1/4 HSS6X4X1/4 HSS6X4X3/8 HSS8X4X1/4 HSS8X4X3/8 HSS8X6X3/8",
    "PIPE": "PIPE3STD PIPE4STD PIPE5STD PIPE6STD PIPE8STD PIPE4XS PIPE6XS",
    "L": "L3X3X1/4 L3X3X3/8 L4X4X1/4 L4X4X3/8 L4X4X1/2 L4X3X3/8 L5X5X3/8 L6X6X3/8 L6X4X3/8",
    "C": "C4X5.4 C6X8.2 C6X10.5 C8X11.5 C10X15.3 C12X20.7",
    "MC": "MC6X12 MC8X8.5",
}
STOCK_SET = {s for v in STOCK.values() for s in v.split()}
FILLETS = [3 / 16, 1 / 4, 5 / 16, 3 / 8, 7 / 16, 1 / 2]
PLATES = [0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.5, 1.75, 2.0]
ANCHORS = [0.625, 0.75, 0.875, 1.0, 1.25]
DEFAULT_FAMILIES = {"arm": ["W", "HSS-SQ", "PIPE", "L", "C"], "column": ["W", "HSS-SQ", "PIPE"]}


# ------------------------------------------------------------------ demand sets

def demand_sets(spec: dict, method: str) -> Tuple[List[dict], List[str]]:
    """Per combination, the {pipe tag: {vertical, transverse, longitudinal}} map.

    spec["pipes"] lists each pipe with arm index, offset and its CAESAR II load block
    (loads.categories spec + vertical_axis / pipe_axis). Every pipe must give the same
    load-case names so the combinations line up.
    """
    pipes = spec.get("pipes") or []
    if not pipes:
        raise InputError("spec.pipes: give at least one pipe with its CAESAR II restraint loads")
    per_pipe = []
    notes: List[str] = []
    for p in pipes:
        lb = p.get("loads") or {}
        combos, n, _ = L.combinations({**lb, "T_factor": spec.get("T_factor", lb.get("T_factor", 1.0))}, method)
        notes += [f"{p.get('tag', 'pipe')}: {x}" for x in n]
        per_pipe.append((p, {c["id"]: c for c in combos}))
    ids = [c for c in per_pipe[0][1]]
    for p, cmap in per_pipe[1:]:
        if set(cmap) != set(ids):
            raise InputError("all pipes on a support must give the same set of load cases "
                             "(SUS / OPE / WIN / EQ / HYD) so the combinations line up")
    sets = []
    for cid in ids:
        dem = {}
        for p, cmap in per_pipe:
            lb = p.get("loads") or {}
            dem[p.get("tag", "pipe")] = L.support_demands(cmap[cid]["vector"], lb.get("vertical_axis", "Y"),
                                                          lb.get("pipe_axis", "X"))
        sets.append({"id": cid, "clause": per_pipe[0][1][cid]["clause"], "demands": dem})
    return sets, list(dict.fromkeys(notes))


def apply(design: dict, dem: Dict[str, dict], spec: dict) -> dict:
    """Assembly input for one combination: pipes placed on their arms with the demands."""
    d = copy.deepcopy(design)
    for arm in d["arms"]:
        arm["pipes"] = []
    for p in spec["pipes"]:
        tag = p.get("tag", "pipe")
        arm = d["arms"][int(p.get("arm", 0))]
        x = dem[tag]
        arm["pipes"].append({"tag": tag, "offset": p["offset"], "vertical": x["vertical"],
                             "transverse": x["transverse"], "longitudinal": x["longitudinal"]})
    return d


# ------------------------------------------------------------------ envelope

def envelope(design: dict, sets: Sequence[dict], spec: dict,
             service_sets: Optional[Sequence[dict]] = None) -> dict:
    """Run the assembly for every combination; keep the worst ratio per stage."""
    per_stage: Dict[str, dict] = {}
    runs = []
    warnings: List[str] = []
    for s in sets:
        res = analyze_assembly(apply(design, s["demands"], spec))
        runs.append((s["id"], res))
        warnings += res["warnings"]
        for st in res["output"]["stages"]:
            if service_sets is not None and st["component"] == "pier":
                continue
            cur = per_stage.get(st["stage"])
            if cur is None or _gt(st["ratio"], cur["ratio"]):
                per_stage[st["stage"]] = {"stage": st["stage"], "component": st["component"],
                                          "ratio": st["ratio"], "governing": st["governing"],
                                          "status": st["status"], "combo": s["id"], "checks": st["checks"],
                                          "run": res}
    if service_sets is not None:
        sdesign = dict(design, method="ASD")
        for s in service_sets:
            res = analyze_assembly(apply(sdesign, s["demands"], spec))
            for st in res["output"]["stages"]:
                if st["component"] != "pier":
                    continue
                cur = per_stage.get(st["stage"])
                if cur is None or _gt(st["ratio"], cur["ratio"]):
                    per_stage[st["stage"]] = {"stage": st["stage"], "component": "pier",
                                              "ratio": st["ratio"], "governing": st["governing"],
                                              "status": st["status"], "combo": s["id"] + " (service)",
                                              "checks": st["checks"], "run": res}
    stages = list(per_stage.values())
    gov = max(stages, key=lambda x: _key(x["ratio"])) if stages else None
    # Base reactions and engine notes are reported from the run that governs the verdict.
    gov_run = gov["run"] if gov else runs[0][1]
    for st in stages:
        st.pop("run", None)
    return {"stages": stages,
            "warnings": list(dict.fromkeys(warnings)),
            "status": "fail" if any(s["status"] == "fail" for s in stages) else "pass",
            "governingRatio": gov["ratio"] if gov else 0.0,
            "governingStage": gov["stage"] if gov else "-",
            "governingCheck": gov["governing"] if gov else "-",
            "governingCombo": gov["combo"] if gov else "-",
            "governingRun": gov_run,
            "combosRun": len(runs) + (len(service_sets) if service_sets else 0)}


def _key(x):
    return float("inf") if isinstance(x, str) else x


def _gt(a, b):
    return _key(a) > _key(b)


def needs_service(design: dict) -> bool:
    return design.get("method") == "LRFD" and bool(design.get("pier")) and \
        (design["pier"].get("restraint") or "gravity") != "anchored"


# ------------------------------------------------------------------ search

def _stage_ok(env: dict, component: str, arm_index: Optional[int] = None, limit: float = 1.0) -> bool:
    rows = [s for s in env["stages"] if s["component"] == component]
    if arm_index is not None and component == "arm":
        rows = [s for s in rows if s["stage"].startswith(f"Arm {arm_index + 1} ")]
    return bool(rows) and all(s["status"] != "fail" and _key(s["ratio"]) <= limit for s in rows)


def _weld_ok(env: dict, limit: float = 1.0) -> bool:
    rows = [s for s in env["stages"] if s["component"] == "weld"]
    if any("exceeds the J2.2b maximum" in w for w in env.get("warnings", [])):
        return False                       # an alternative must satisfy J2.2b, not just strength
    return all(s["status"] != "fail" and _key(s["ratio"]) <= limit for s in rows)


def lightest(design: dict, sets, spec, family: str, set_shape: Callable[[dict, str], None],
             ok: Callable[[dict], bool], cap: int = 120, keep: int = 4) -> List[str]:
    """The `keep` lightest shapes of a family that pass as MEMBERS, lightest first.
    More than one is kept because the lightest member often has too thin a wall for its
    welds (J2.2b maximum, base-metal rupture); the pairing step then steps up in weight."""
    rows = sorted(shapes_by_family(family), key=lambda r: (r.get("W") or 0, r["label"]))[:cap]
    found: List[str] = []
    for r in rows:
        d = copy.deepcopy(design)
        set_shape(d, r["label"])
        try:
            env = envelope(d, sets, spec)
        except (InputError, ValueError, ZeroDivisionError):
            continue
        if ok(env):
            found.append(r["label"])
            if len(found) >= keep:
                break
    return found


def tune_list(design: dict, sets, spec, values, setter, ok) -> Tuple[Optional[float], dict]:
    for v in values:
        d = copy.deepcopy(design)
        setter(d, v)
        try:
            env = envelope(d, sets, spec)
        except (InputError, ValueError, ZeroDivisionError):
            continue
        if ok(env):
            return v, d
    return None, design


def optimize(design: dict, spec: dict) -> dict:
    """Rank code-passing alternatives to `design` (an assembly input without loads)."""
    method = design["method"]
    opt = spec.get("optimize") if isinstance(spec.get("optimize"), dict) else {}
    limit = float(opt.get("maxRatio", 1.0))
    weights = {"weight": 1.0, "field": 1.0, "standard": 1.0, **(opt.get("objectives") or {})}
    fams = {**DEFAULT_FAMILIES, **(opt.get("families") or {})}
    if spec.get("_factoredSets"):
        all_sets = screen = spec["_factoredSets"]
    else:
        all_sets, _ = demand_sets(spec, method)
        screen_ids = {c["combo"]["id"] for p in spec["pipes"] for c in _gov_for_pipe(p, spec, method)}
        screen = [s for s in all_sets if s["id"] in screen_ids] or all_sets
    log: List[str] = [f"Screening on {len(screen)} governing combination(s) of {len(all_sets)}; "
                      "every finalist re-checked against all of them, J2.2b weld limits included."]
    has_column = design.get("type") != "cantilever"
    candidates: List[dict] = []

    def set_arms(d, label):
        for a in d["arms"]:
            a["shape"] = label
    arm_choices: List[Tuple[str, List[str]]] = []
    for fam in fams["arm"]:
        got = lightest(design, screen, spec, fam, set_arms,
                       lambda e: all(_stage_ok(e, "arm", i, limit) for i in range(len(design["arms"]))))
        if got:
            arm_choices.append((fam, got))
        else:
            log.append(f"No {fam} arm in the searched range passes - family dropped.")
    col_choices: List[Tuple[str, List[Optional[str]]]] = [("-", [None])]
    if has_column:
        col_choices = []
        for fam in fams["column"]:
            got = lightest(design, screen, spec, fam, lambda d, l: d.__setitem__("columnShape", l),
                           lambda e: _stage_ok(e, "column", None, limit))
            if got:
                col_choices.append((fam, got))
            else:
                log.append(f"No {fam} column in the searched range passes - family dropped.")

    for (af, arms_ok), (cf, cols_ok) in itertools.product(arm_choices, col_choices):
        pairs = sorted(itertools.product(arms_ok, cols_ok), key=lambda p: _pair_weight(design, *p))
        got = None
        for arm, col in pairs:                     # lightest pairing whose connections also work
            got = _complete(design, arm, col, screen, all_sets, spec, limit, has_column)
            if got:
                break
        if not got:
            log.append(f"{af} arm / {cf} column: none of the {len(pairs)} lightest member-passing "
                       "pairings also passes its welds (strength + J2.2b), plate and anchors - dropped.")
            continue
        d, env = got
        candidates.append({"design": d, "envelope": env, "families": (af, cf)})

    # seed: the design as drawn, if it passes everything, competes on the same terms
    try:
        env0 = envelope(design, all_sets, spec, _service(spec, design))
        if env0["status"] == "pass" and _key(env0["governingRatio"]) <= limit and _weld_ok(env0, limit):
            candidates.append({"design": copy.deepcopy(design), "envelope": env0, "families": ("as drawn", ""),
                               "asDrawn": True})
    except (InputError, ValueError, ZeroDivisionError):
        pass
    for c in candidates:
        c["metrics"] = metrics(c["design"], spec)
    _score(candidates, weights)
    candidates.sort(key=lambda c: c["score"])
    top = int(opt.get("top", 5))
    return {"objectives": weights, "maxRatio": limit, "log": log,
            "alternatives": [_summary(i + 1, c) for i, c in enumerate(candidates[:top])],
            "evaluated": len(candidates)}


def _pair_weight(design, arm, col):
    w = sum((find_shape(arm).get("W") or 0) * a["projection"] / 12 for a in design["arms"])
    if col:
        w += (find_shape(col).get("W") or 0) * design["columnHeight"] / 12
    return w


def _complete(design, arm, col, screen, all_sets, spec, limit, has_column):
    """Tune fillet, plate and anchors for one arm/column pair; then the full re-check."""
    d = copy.deepcopy(design)
    for a in d["arms"]:
        a["shape"] = arm
        a.pop("weldSize", None)
    if col:
        d["columnShape"] = col
    size, d = tune_list(d, screen, spec, FILLETS, lambda x, v: x.__setitem__("weldSize", v),
                        lambda e: _weld_ok(e, limit))
    if size is None:
        return None
    if d.get("baseplate") and has_column:
        t, d = tune_list(d, screen, spec, PLATES,
                         lambda x, v: x["baseplate"].__setitem__("plateThickness", v),
                         lambda e: _stage_ok(e, "baseplate", None, limit))
        if t is None:
            return None
        da, d = tune_list(d, screen, spec, ANCHORS,
                          lambda x, v: x["baseplate"].__setitem__("anchorDiameter", v),
                          lambda e: _stage_ok(e, "anchorage", None, limit))
        if da is None:
            return None
    env = envelope(d, all_sets, spec, _service(spec, d))
    if env["status"] != "pass" or _key(env["governingRatio"]) > limit or not _weld_ok(env, limit):
        return None
    return d, env


def _gov_for_pipe(p, spec, method):
    lb = p.get("loads") or {}
    combos, _, _ = L.combinations({**lb, "T_factor": spec.get("T_factor", lb.get("T_factor", 1.0))}, method)
    return L.governing(combos, lb.get("vertical_axis", "Y"), lb.get("pipe_axis", "X"))


def _service(spec, design):
    if spec.get("_factoredSets") or not needs_service(design):
        return None
    sets, _ = demand_sets(spec, "ASD")
    return sets


# ------------------------------------------------------------------ scoring

def metrics(design: dict, spec: dict) -> dict:
    w = 0.0
    nonstock: List[str] = []
    for a in design["arms"]:
        row = find_shape(a["shape"])
        w += (row.get("W") or 0) * a["projection"] / 12
        if a["shape"] not in STOCK_SET:
            nonstock.append(a["shape"])
    if design.get("columnShape"):
        row = find_shape(design["columnShape"])
        n_cols = 2 if design.get("type") in ("goalpost", "trapeze") else 1
        w += n_cols * (row.get("W") or 0) * design["columnHeight"] / 12
        if design["columnShape"] not in STOCK_SET:
            nonstock.append(design["columnShape"])
    bp = design.get("baseplate") or {}
    if bp:
        w += bp["plateLength"] * bp["plateWidth"] * bp["plateThickness"] * STEEL_LB_PER_IN3
        if bp["plateThickness"] not in PLATES:
            nonstock.append(f"PL {bp['plateThickness']}")
        if bp.get("anchorDiameter") not in ANCHORS:
            nonstock.append(f"anchor {bp.get('anchorDiameter')}")
    if design.get("weldSize") not in FILLETS:
        nonstock.append(f"fillet {design.get('weldSize')}")
    erection = (spec.get("fabrication") or {}).get("armToColumn", "shop-weld")
    field = 0.0
    if erection == "field-weld":
        field += 3.0 * len(design["arms"])
    elif erection == "bolted":
        field += 1.0 * len(design["arms"])
    ws = design.get("weldSize") or 0.25
    field += (1 if ws <= 5 / 16 else 2 if ws <= 7 / 16 else 3) * 0.5     # passes per weld
    if bp:
        drilled = bp.get("anchorType", "cast-in") != "cast-in"
        field += bp.get("anchorCount", 4) * (0.5 if drilled else 0.25)
        if bp["plateThickness"] > 1.0:
            field += 0.5                                                   # heavy plate handling
    return {"weightLb": round_half_up(w, 1), "fieldPoints": round_half_up(field, 2),
            "nonStock": nonstock}


def _score(cands: List[dict], weights: dict):
    if not cands:
        return
    wmin = min(c["metrics"]["weightLb"] for c in cands) or 1.0
    fmin = min(c["metrics"]["fieldPoints"] for c in cands) or 1.0
    for c in cands:
        m = c["metrics"]
        c["score"] = (weights["weight"] * (m["weightLb"] / wmin - 1)
                      + weights["field"] * (m["fieldPoints"] / fmin - 1)
                      + weights["standard"] * 0.25 * len(m["nonStock"]))


def _summary(rank: int, c: dict) -> dict:
    d, e, m = c["design"], c["envelope"], c["metrics"]
    bp = d.get("baseplate") or {}
    return {
        "rank": rank,
        "asDrawn": bool(c.get("asDrawn")),
        "score": round_half_up(c["score"], 4),
        "arms": [a["shape"] for a in d["arms"]],
        "column": d.get("columnShape"),
        "weldSize": d.get("weldSize"),
        "plateThickness": bp.get("plateThickness"),
        "anchorDiameter": bp.get("anchorDiameter"),
        "weightLb": m["weightLb"], "fieldPoints": m["fieldPoints"], "nonStock": m["nonStock"],
        "governingStage": e["governingStage"], "governingCheck": e["governingCheck"],
        "governingRatio": e["governingRatio"], "governingCombo": e["governingCombo"],
        "stageRatios": {s["stage"]: s["ratio"] for s in e["stages"]},
        "design": d,
    }
