"""Automated engineering review of an enveloped support design.

Produces findings a reviewer would raise, each backed by an engine number, ranked
critical > major > minor > info:

  critical   a strength limit state fails, or a demand the model cannot carry is present
  major      within 10 % of a limit, a possibly unconservative modelling input, a
             detailing violation
  minor      advisories, constructability, overdesign worth optimising
  info       basis items the engineer must confirm

Claude reads these, adds drawing/judgement findings of its own (labelled as such), and
explains them; it does not change a ratio or a verdict.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import detailing as DT
from .aisc import find_shape
from .bolts import bolt_group, end_plate_no_prying
from .common import round_half_up
from .loads import ASD as ASD_TABLE

SEV_ORDER = {"critical": 0, "major": 1, "minor": 2, "info": 3}

# Governing check -> what usually fixes it (direction for the engineer, not a design).
REMEDY = [
    ("LTB", "lateral-torsional buckling governs: brace the compression flange, shorten Lb, "
            "compute Cb, or use a section with higher ry / an HSS"),
    ("FLB", "flange local buckling governs: choose a compact-flange section"),
    ("buckling", "member buckling governs: reduce KL (bracing / lower K) or increase r"),
    ("Deflection", "deflection governs: stiffer section (higher Ix) or shorter projection"),
    ("weld", "weld governs: larger fillet or longer weld; if base metal governs, thicken the connected part"),
    ("Base-metal", "base metal governs the joint: thicker connected element, not a bigger weld"),
    ("breakout", "concrete breakout governs: widen the pier or increase edge distance; deeper "
                 "embedment does not help when 17.6.2.1.2 caps hef; or add anchor reinforcement"),
    ("bond", "adhesive bond governs: deeper embedment or the ESR's higher tau for the product"),
    ("pryout", "pryout governs: deeper embedment or more anchors"),
    ("Base plate yield", "base plate bending governs: thicker plate, or stiffeners to cut the cantilever"),
    ("bearing", "concrete bearing governs: larger plate or pier, or higher f'c"),
    ("Soil", "soil bearing governs: larger footing"),
    ("Overturning", "overturning governs: larger/heavier footing or anchor to existing structure"),
    ("Sliding", "sliding governs: larger footing, shear key, or passive resistance (geotech)"),
]


def _f(sev, title, detail, basis, remedy=None, source="engine"):
    return {"severity": sev, "title": title, "detail": detail, "basis": basis,
            **({"remedy": remedy} if remedy else {}), "source": source}


def _remedy(text: str) -> Optional[str]:
    for key, fix in REMEDY:
        if key.lower() in (text or "").lower():
            return fix
    return None


def _num(x):
    return float("inf") if isinstance(x, str) else x


def review(design: dict, env: dict, spec: dict, opt: Optional[dict] = None) -> List[dict]:
    out: List[dict] = []
    # 1. strength results
    for st in env["stages"]:
        r = _num(st["ratio"])
        what = f"{st['stage']}: {st['governing']} = {st['ratio']} under {st['combo']}"
        if st["status"] == "fail" or r > 1.0:
            out.append(_f("critical", f"FAILS - {st['stage']}", what, _clause(st),
                          _remedy(st["governing"]) or _remedy(st["stage"])))
        elif r >= 0.9:
            out.append(_f("major", f"Near limit - {st['stage']}", what + " (within 10 % of capacity)",
                          _clause(st), _remedy(st["governing"])))
        for c in st.get("checks", []):
            if c.get("advisory") and _num(c["ratio"]) > 0.9:
                out.append(_f("minor", f"Advisory near limit - {c['label']}",
                              f"{st['stage']}: {c['demand']} vs {c['capacity']} ({c['ratio']})",
                              c.get("clause", "")))
    # 2. overdesign -> optimisation opportunity
    g = _num(env["governingRatio"])
    if g < 0.4:
        msg = f"Highest utilisation is {env['governingRatio']} ({env['governingStage']})."
        if opt and opt.get("alternatives"):
            best = opt["alternatives"][0]
            base_w = _weight(design)
            msg += (f" Best ranked alternative: arm {', '.join(best['arms'])}, column {best['column']}, "
                    f"{best['weightLb']} lb vs {base_w} lb as drawn, governing ratio {best['governingRatio']}.")
        out.append(_f("minor", "Overdesigned - optimisation opportunity", msg, "utilisation < 0.40"))
    # 3. engine warnings, classified
    for w in dict.fromkeys(env.get("warnings") or env["governingRun"]["warnings"]):
        sev = "info"
        lw = w.lower()
        if "exceeds the j2.2b maximum" in lw:
            sev = "major"
        elif "below the table j2.4 minimum" in lw:
            sev = "major"
        elif "governs over the weld metal" in lw or "17.6.2.1.2" in lw or "clipped" in lw \
                or "j10.1" in lw:
            sev = "minor"
        if lw.startswith("no deflection supplied"):
            w += " (applies to the column stage: a cantilever post has no deflection limit in the model)"
        out.append(_f(sev, _title(w), w, "engine warning"))
    # 4. checks the parametric engine does not make
    out += _pipe_moments(spec)
    out += _j10_flange_weld_note(env)
    out += _asd_wind_anchorage(design, env)
    for f in DT.constructability({**design, "connections": spec.get("fabrication")}):
        out.append(_f("minor" if f["severity"] != "violation" else "major",
                      f"Detailing - {f['severity']}", f["message"], f["clause"]))
    seen, uniq = set(), []
    for f in out:
        k = (f["title"], f["detail"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    uniq.sort(key=lambda f: SEV_ORDER[f["severity"]])
    return uniq


def _title(text: str, n: int = 72) -> str:
    """First clause of an engine message, cut at a word boundary."""
    t = text
    for sep in (" — ", " - ", ". ", "; ", " ("):
        t = t.split(sep)[0]
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0] + " ..."


def _clause(st):
    for c in st.get("checks", []):
        if c["label"] == st["governing"]:
            return c.get("clause", "")
    return ""


def _weight(design):
    w = 0.0
    for a in design["arms"]:
        w += (find_shape(a["shape"]).get("W") or 0) * a["projection"] / 12
    if design.get("columnShape"):
        w += (find_shape(design["columnShape"]).get("W") or 0) * design["columnHeight"] / 12
    bp = design.get("baseplate") or {}
    if bp:
        w += bp["plateLength"] * bp["plateWidth"] * bp["plateThickness"] * 0.2836
    return round_half_up(w, 1)


def _pipe_moments(spec: dict) -> List[dict]:
    out = []
    for p in spec.get("pipes", []):
        cases = (p.get("loads") or {}).get("cases") or {}
        big = {k: v for k, v in cases.items() if len(v) == 6 and any(abs(m) > 1e-6 for m in v[3:])}
        if big:
            out.append(_f("critical", f"Pipe moments at {p.get('tag', 'pipe')} are not carried by the model",
                          f"Cases with moments: {', '.join(sorted(big))}. The parametric assemblies take "
                          "pipe forces only. A restraint that resists moment (anchor, rigid line stop) "
                          "needs those moments added to the arm and column - model it as a frame or "
                          "confirm the restraint is a simple support (moments ~0).",
                          "load path completeness"))
    return out


def _j10_flange_weld_note(env: dict) -> List[dict]:
    """P.E. ruling 2026-10-26: the engine's J10.1 loaded width is tw + 2w, the footprint of the
    two web/leg fillets. If the arm FLANGES are also welded to the column flange, the loaded
    width is the arm's bf: the 0.15·bf exemption may no longer apply and J10.1 must be checked
    with that detail. The engine does not know the flange welds, so the reviewer says so."""
    out = []
    for st in env["stages"]:
        if st.get("component") != "weld":
            continue
        for c in st.get("checks", []):
            if c["label"] == "Column flange local bending" and "web fillets only" in (c.get("clause") or ""):
                out.append(_f("info", "J10.1 loaded width assumes web fillets only",
                              f"{st['stage']}: column flange local bending ratio {c['ratio']} on a loaded width of "
                              "tw + 2w (the two web fillets). If the arm flanges are also welded to the column, the "
                              "loaded width is the arm flange width bf — re-run the check with that detail.",
                              c.get("clause", "")))
    for w in dict.fromkeys(env.get("warnings") or env["governingRun"]["warnings"]):
        if "J10.1 column-flange local bending not required" in w:
            out.append(_f("minor", "J10.1 exemption rests on web-only fillets",
                          w + " That exemption assumes the arm is welded along its web or leg only. If the arm "
                          "flanges are also welded, the loaded width is bf, the 0.15·bf exemption may not hold "
                          "and J10.1 must be checked — re-run with that detail.",
                          "AISC 360-22 J10.1"))
    return out


_COMBO_ID = re.compile(r"^ASD-(.+?)(?:[+-](?:T)?|\+T)?(?: \(service\))?$")


def asd_wind_combo(combo_id: str) -> bool:
    """True when an envelope combination id names an ASD combination that carries wind.

    Ids are built by loads.combinations as "<method>-<cid>[+|-][+T]", e.g. "ASD-5a+",
    "ASD-7a-+T"; the cid is looked up in the ASD table so this never depends on the clause text."""
    m = _COMBO_ID.match(str(combo_id or ""))
    if not m:
        return False
    tag = m.group(1)
    for cid, _clause, fac in ASD_TABLE:
        if tag == cid or (tag.startswith(cid) and tag[len(cid):len(cid) + 1] in ("+", "-")):
            return "W" in fac
    return False


def _asd_wind_anchorage(design: dict, env: dict) -> List[dict]:
    """P.E. ruling 2026-10-26 (code-basis item 10, deliberately not changed in the engine): in
    ASD the ACI 318-19 strength-design anchor capacity is converted with a fixed 1/1.5
    (R17.5.3). Where a 0.6W combination governs anchorage the implied factor is 1/0.6 = 1.67,
    so ASD anchorage can be about 10 % unconservative there. Recommend LRFD."""
    out = []
    for st in env["stages"]:
        if st.get("component") != "anchorage":
            continue
        combo = str(st.get("combo") or "")
        if not asd_wind_combo(combo):
            continue
        out.append(_f("major", "ASD anchorage governed by a wind combination",
                      f"{st['stage']}: {st['governing']} = {st['ratio']} under {combo}. The engine converts the "
                      "ACI 318-19 strength capacity to allowable with a fixed 1/1.5 (R17.5.3); a 0.6W ASD "
                      "combination implies 1/0.6 = 1.67, so this row can be about 10 % unconservative. "
                      "Run the anchorage in LRFD (ACI 318-19 Ch. 17 is strength design) or check the "
                      "wind-governed anchors by hand with the 0.6W / 1.0W pairing.",
                      "ACI 318-19 R17.5.3; ASCE 7-22 2.4.1",
                      "re-run with method LRFD for the anchorage verdict"))
    return out


def bolted_arm_alternative(design: dict, env: dict, method: str) -> Optional[dict]:
    """Size a bolted end-plate field connection for arm 1 from the arm stage's governing
    combination: 4 bolts, 2 rows 1.5 in outside each flange, A325-N.

    Moment: compression bears through the compression flange, so the two TENSION bolts
    carry M / (d - tf/2 + 1.5) between them, plus their share of any axial tension. They
    are checked as their own group (J3.6/J3.7, bearing on the chosen plate), and the plate
    on the AISC Manual Part 9 thick-plate (no prying) basis with b = 1.5 in, p = bf/2."""
    if not design.get("arms"):
        return None
    arm = design["arms"][0]
    st = next((s for s in env["stages"] if s["component"] == "arm"), None)
    if not st:
        return None
    M = V = P = 0.0
    for c in st["checks"]:
        if c["label"].startswith("Flexure, major"):
            M = _num(c["demand"])
        if c["label"].startswith("Shear, major"):
            V = _num(c["demand"])
        if c["label"].startswith("Axial"):
            P = _num(c["demand"])
    row = find_shape(arm["shape"]) or {}
    d_arm = row.get("d") or 6.0
    tf = row.get("tf") or row.get("tw") or 0.25
    bf = row.get("bf") or d_arm
    lever = d_arm - tf / 2 + 1.5                 # tension bolt row to compression-flange centroid
    T_bolt = M / lever / 2 + max(P, 0.0) / 4     # per tension bolt (2 bolts in the tension row)
    gauge = max(3.0, bf + 1.5)
    for db in (0.625, 0.75, 0.875, 1.0):
        for t in (0.5, 0.625, 0.75, 0.875, 1.0, 1.25, 1.5):
            bg = bolt_group({"method": method, "grade": "A325", "d": db, "nBolts": 2, "rows": 1, "cols": 2,
                             "gauge": gauge, "edgeLoaded": 1.5, "edgeSide": 1.5,
                             "plies": [{"t": t, "Fy": 36, "Fu": 58, "name": "end plate"}],
                             "V": V / 2, "T": 2 * T_bolt})
            if bg["status"] != "pass":
                continue
            ep = end_plate_no_prying({"method": method, "T": T_bolt, "b": 1.5, "d": db,
                                      "p": max(bf / 2, 2 * db), "Fu": 58, "t": t})
            if ep["status"] == "pass":
                return {"bolts": f"4 - {DT._frac(db)} A325-N (2 in the tension row)", "endPlate": f"PL {DT._frac(t)} A36",
                        "boltTension": round_half_up(T_bolt, 3), "lever": round_half_up(lever, 3),
                        "governing": bg["output"]["governingCheck"],
                        "ratio": bg["output"]["governingRatio"], "plateRatio": ep["output"]["ratio"],
                        "note": "Shop-weld the end plate to the arm, bolt to the column in the field. Demands "
                                "from the arm stage's governing combination; thick-plate (no-prying) basis. "
                                "Column flange local bending (J10), the arm-to-end-plate weld and the other "
                                "combinations' M/V/P pairs still need checking when this option is chosen."}
    return None
