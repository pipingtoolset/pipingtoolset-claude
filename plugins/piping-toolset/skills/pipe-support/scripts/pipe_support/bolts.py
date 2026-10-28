"""Bolted connections - AISC 360-22 Chapter J3 (bolts) and J4 (affected elements).

New in the plugin (PiperSTR has no bolted-joint module). Covers the joints a pipe support
actually uses: a bolted shear tab / clip on an arm, an end plate on an arm cantilevered
off a column or existing steel, and a bolted base/clamp plate.

    bolt shear and tension             J3.6, Table J3.2
    combined tension + shear           J3.7 (J3-3a / J3-3b)
    bearing and tear-out at holes      J3.10 (J3-6a, J3-6c), deformation a design consideration
    slip resistance (optional)         J3.8 (J3-4) - pretension Tb is an INPUT (Table J3.1)
    block shear                        J4.3 (J4-5)
    tension rupture on the net section J4.1(b) with B4.3 net area (+1/16 in)
    shear yielding / rupture           J4.2 (J4-3, J4-4)
    end plate thickness for no prying  AISC Manual Part 9 thick-plate criterion
    detailing: min spacing J3.3, min edge Table J3.4, max spacing/edge J3.5, holes Table J3.3

Specification values used (AISC 360-22 is published free by AISC): Table J3.2 nominal
stresses, Table J3.3 standard hole sizes, Table J3.4 minimum edge distances. Slip-critical
pretension (Table J3.1) and the slip class are user inputs.

Units: in, kip, ksi.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from .common import InputError, need, result, round_half_up, verdict

R4 = lambda x: round_half_up(x, 4)  # noqa: E731

# Table J3.2 nominal stresses, ksi: (Fnt, Fnv threads included N, Fnv threads excluded X)
BOLT_GRADES = {
    "A307": (45.0, 27.0, 27.0),
    "GROUP-A": (90.0, 54.0, 68.0),     # ASTM F3125 A325 / F1852
    "GROUP-B": (113.0, 68.0, 84.0),    # ASTM F3125 A490 / F2280
    "GROUP-C": (150.0, 90.0, 113.0),   # ASTM F3043 / F3111
}
ALIASES = {"A325": "GROUP-A", "F3125-A325": "GROUP-A", "F1852": "GROUP-A",
           "A490": "GROUP-B", "F3125-A490": "GROUP-B", "F2280": "GROUP-B",
           "F3043": "GROUP-C", "F3111": "GROUP-C"}

# Table J3.4 minimum edge distance from the centre of a standard hole, in.
_MIN_EDGE = [(0.5, 0.75), (0.625, 0.875), (0.75, 1.0), (0.875, 1.125), (1.0, 1.25),
             (1.125, 1.5), (1.25, 1.625)]

PHI = {"bolt": 0.75, "bearing": 0.75, "block": 0.75, "rupture": 0.75, "yield_shear": 1.00,
       "slip_std": 1.00}
OMEGA = {"bolt": 2.00, "bearing": 2.00, "block": 2.00, "rupture": 2.00, "yield_shear": 1.50,
         "slip_std": 1.50}


def grade(name: str):
    g = ALIASES.get(name.upper(), name.upper())
    if g not in BOLT_GRADES:
        raise InputError(f"bolt grade {name!r}: use A307, A325 / Group-A, A490 / Group-B, Group-C")
    return g, BOLT_GRADES[g]


def hole_diameter(d: float, hole: str = "STD") -> float:
    """Table J3.3 standard hole: d + 1/16 for d < 1 in, d + 1/8 for d >= 1 in.
    Only STD is computed; oversize / slotted holes are flagged for manual review."""
    if hole != "STD":
        raise InputError("only standard (STD) holes are computed; oversized/slotted holes need "
                         "Table J3.3 dimensions entered as hole_diameter")
    return d + (1 / 16 if d < 1.0 else 1 / 8)


def min_edge_distance(d: float) -> float:
    """Table J3.4 (standard holes); over 1 1/4 in: 1.25 d."""
    for dia, e in _MIN_EDGE:
        if abs(d - dia) < 1e-9:
            return e
    if d > 1.25:
        return 1.25 * d
    raise InputError(f"bolt diameter {d} in is not a Table J3.4 size (1/2 to 1 1/4 in, or > 1 1/4)")


def _design(nominal: float, method: str, key: str) -> float:
    return nominal * PHI[key] if method == "LRFD" else nominal / OMEGA[key]


def bolt_group(inp: dict) -> dict:
    """Check one bolt group and the connected plies.

    inp:
      method        "LRFD" | "ASD"
      grade         bolt grade (A307, A325/Group-A, A490/Group-B, Group-C)
      d             bolt diameter, in
      threads       "N" (included in shear plane, default - conservative) | "X"
      nBolts        bolts in the group
      shearPlanes   1 (single shear, default) | 2
      rows, cols    bolt pattern (rows along the load); rows*cols == nBolts
      spacing       centre-to-centre pitch along the load, in
      gauge         centre-to-centre gauge across the load, in
      edgeLoaded    end distance in the direction of load, in (from last bolt to edge)
      edgeSide      side edge distance, in
      plies         [{"t": in, "Fy": ksi, "Fu": ksi, "name": str}, ...] - every ply in the
                    joint; the thinnest/weakest governs bearing and the J4 checks
      V             shear on the group, kip (resultant, concentric)
      T             tension on the group, kip (0 if none)
      eccentricity  in-plane eccentricity of V, in (elastic method, optional)
      slipCritical  {"Tb": kip (Table J3.1), "mu": 0.30 | 0.50, "hf": 1.0, "Du": 1.13}
      holeDiameter  override, in (oversize/slot)
    """
    method = need(inp, "method")
    gname, (Fnt, FnvN, FnvX) = grade(need(inp, "grade"))
    d = float(need(inp, "d"))
    n = int(need(inp, "nBolts"))
    rows, cols = int(inp.get("rows", n)), int(inp.get("cols", 1))
    if rows * cols != n:
        raise InputError("rows x cols must equal nBolts")
    ns = int(inp.get("shearPlanes", 1))
    Fnv = FnvX if inp.get("threads", "N") == "X" else FnvN
    Ab = math.pi * d * d / 4
    dh = float(inp.get("holeDiameter") or hole_diameter(d))
    s = float(inp.get("spacing", 3 * d))
    g = float(inp.get("gauge", 3 * d))
    Le = float(need(inp, "edgeLoaded"))
    Ls = float(inp.get("edgeSide", Le))
    plies = inp.get("plies") or []
    if not plies:
        raise InputError("plies: list every connected ply with t, Fy, Fu")
    V, T = float(inp.get("V", 0.0)), float(inp.get("T", 0.0))
    ecc = float(inp.get("eccentricity", 0.0))
    checks: List[dict] = []
    warnings: List[str] = []

    def row(name, demand, capacity, clause, detail=None):
        ratio = demand / capacity if capacity > 0 else (math.inf if demand > 0 else 0.0)
        checks.append({"check": name, "demand": R4(demand), "capacity": R4(capacity),
                       "ratio": R4(ratio), "clause": clause, **({"detail": detail} if detail else {})})

    # --- per-bolt demand: elastic method for in-plane eccentricity (conservative vs IC)
    rv = V / n
    if ecc and n > 1:
        xs = [(c - (cols - 1) / 2) * g for c in range(cols)]
        ys = [(r - (rows - 1) / 2) * s for r in range(rows)]
        Ip = sum(x * x + y * y for x in xs for y in ys)
        M = V * ecc
        xmax, ymax = max(abs(x) for x in xs), max(abs(y) for y in ys)
        rv = math.hypot(V / n + M * xmax / Ip, M * ymax / Ip)   # V along the rows (y)
        warnings.append("Eccentric shear by the elastic method (AISC Manual Part 7) - "
                        "conservative relative to the instantaneous-centre method.")
    rt = T / n

    # --- J3.6 bolt shear and tension
    phiRnv = _design(Fnv * Ab * ns, method, "bolt")
    row("Bolt shear", rv, phiRnv, "AISC 360-22 J3.6 (J3-1), Table J3.2",
        {"Fnv": Fnv, "Ab": R4(Ab), "planes": ns})
    if T > 0:
        frv = rv / (Ab * ns)
        if method == "LRFD":
            Fnt_p = min(Fnt, 1.3 * Fnt - Fnt / (PHI["bolt"] * Fnv) * frv)
        else:
            Fnt_p = min(Fnt, 1.3 * Fnt - OMEGA["bolt"] * Fnt / Fnv * frv)
        Fnt_p = max(Fnt_p, 0.0)
        row("Bolt tension (with shear interaction)", rt, _design(Fnt_p * Ab, method, "bolt"),
            "AISC 360-22 J3.7 (J3-2, J3-3a/b)", {"Fnt": Fnt, "Fnt'": R4(Fnt_p), "frv": R4(frv)})

    # --- J3.8 slip resistance (serviceability-level slip at standard holes)
    sc = inp.get("slipCritical")
    if sc:
        Tb = float(need(sc, "Tb", "minimum pretension from AISC 360-22 Table J3.1"))
        mu, hf, Du = float(sc.get("mu", 0.30)), float(sc.get("hf", 1.0)), float(sc.get("Du", 1.13))
        ksc = 1 - T / (Du * Tb * n) if method == "LRFD" else 1 - 1.5 * T / (Du * Tb * n)
        Rn = mu * Du * hf * Tb * ns * max(ksc, 0.0)
        row("Slip resistance", rv, _design(Rn, method, "slip_std"), "AISC 360-22 J3.8 (J3-4), J3.9 ksc",
            {"mu": mu, "Tb": Tb, "ksc": R4(ksc)})

    # --- J3.10 bearing and tear-out on the critical ply (deformation at service is a concern)
    edge_bolts = cols                      # bolts in the row nearest the loaded edge
    inner_bolts = n - edge_bolts
    for p in plies:
        t, Fu = float(need(p, "t")), float(need(p, "Fu"))
        name = p.get("name", "ply")
        lc_edge = Le - dh / 2
        lc_inner = s - dh
        rn_bear = 2.4 * d * t * Fu
        rn_edge = min(1.2 * lc_edge * t * Fu, rn_bear)
        rn_inner = min(1.2 * lc_inner * t * Fu, rn_bear)
        detail = {"lc_edge": R4(lc_edge), "lc_inner": R4(lc_inner), "rn_bolt_bearing": R4(rn_bear)}
        if ecc and n > 1:
            # eccentric group: the most-loaded bolt against the weakest single-bolt strength
            weakest_bolt = rn_edge if rows == 1 else min(rn_edge, rn_inner)
            row(f"Bearing / tear-out, critical bolt ({name})", rv,
                _design(weakest_bolt, method, "bearing"), "AISC 360-22 J3.10 (J3-6a, J3-6c)", detail)
        else:
            # concentric group strength = sum of the individual bolt strengths
            group = edge_bolts * rn_edge + inner_bolts * rn_inner
            row(f"Bearing / tear-out ({name})", V, _design(group, method, "bearing"),
                "AISC 360-22 J3.10 (J3-6a, J3-6c)", detail)

    # --- J4 on the weakest ply (block shear along the loaded edge, net section, shear)
    weakest = min(plies, key=lambda p: float(p["t"]) * float(p["Fu"]))
    t, Fy, Fu = float(weakest["t"]), float(need(weakest, "Fy")), float(weakest["Fu"])
    dn = dh + 1 / 16                       # B4.3b net-area hole allowance
    Lv = Le + (rows - 1) * s               # shear plane length along the load
    Ubs = 1.0                              # uniform tension stress (J4.3)

    def rn_block(Agv, Anv, Ant):
        return min(0.6 * Fu * Anv + Ubs * Fu * Ant, 0.6 * Fy * Agv + Ubs * Fu * Ant)
    # Pattern L: one shear plane along the outer bolt line, tension plane to the side edge
    Agv = Lv * t
    Anv = (Lv - (rows - 0.5) * dn) * t
    Ant = ((cols - 1) * g + Ls - (cols - 0.5) * dn) * t
    patterns = [("L-shaped to side edge", rn_block(Agv, Anv, Ant), Agv, Anv, Ant)]
    if cols > 1:
        # Pattern U: two shear planes, tension plane between the outer gauge lines
        Agv2, Anv2 = 2 * Lv * t, 2 * (Lv - (rows - 0.5) * dn) * t
        Ant2 = ((cols - 1) * g - (cols - 1) * dn) * t
        patterns.append(("U-shaped between gauge lines", rn_block(Agv2, Anv2, Ant2), Agv2, Anv2, Ant2))
    pname, rn_bs, Agv, Anv, Ant = min(patterns, key=lambda x: x[1])
    row(f"Block shear ({weakest.get('name', 'ply')})", V, _design(rn_bs, method, "block"),
        "AISC 360-22 J4.3 (J4-5)",
        {"pattern": pname, "Agv": R4(Agv), "Anv": R4(Anv), "Ant": R4(Ant), "Ubs": Ubs})
    width = inp.get("plyWidth")
    if width:
        width = float(width)
        Ag = width * t
        An = (width - cols * dn) * t
        if V > 0:
            row(f"Shear yielding ({weakest.get('name', 'ply')})", V,
                _design(0.6 * Fy * Ag, method, "yield_shear"), "AISC 360-22 J4.2(a) (J4-3)")
            row(f"Shear rupture ({weakest.get('name', 'ply')})", V,
                _design(0.6 * Fu * An, method, "rupture"), "AISC 360-22 J4.2(b) (J4-4)")
        if T > 0:
            An_t = min(An, 0.85 * Ag)
            row(f"Tension rupture, net section ({weakest.get('name', 'ply')})", T,
                _design(Fu * An_t, method, "rupture"), "AISC 360-22 J4.1(b) (J4-2), An <= 0.85Ag")

    # --- detailing (J3.3, J3.4, J3.5)
    det = detailing(d, s, g, Le, Ls, min(float(p["t"]) for p in plies), dh, rows, cols)
    gov = max(checks, key=lambda c: c["ratio"])
    out = {"grade": gname, "d": d, "holeDiameter": R4(dh), "nBolts": n, "method": method,
           "checks": checks, "detailing": det,
           "governingCheck": gov["check"], "governingRatio": gov["ratio"]}
    status = "fail" if gov["ratio"] > 1.0 or any(x["severity"] == "violation" for x in det) else "pass"
    return result("structural.bolt-group", out, status, warnings)


def detailing(d, s, g, Le, Ls, tmin, dh, rows, cols) -> List[dict]:
    out: List[dict] = []

    def add(sev, msg, clause):
        out.append({"severity": sev, "message": msg, "clause": clause})
    smin = 8 / 3 * d
    for name, val, n in (("pitch", s, rows), ("gauge", g, cols)):
        if n > 1 and val < smin - 1e-9:
            add("violation", f"Bolt {name} {val:g} in < 2 2/3 d = {smin:.3f} in", "AISC 360-22 J3.3")
        elif n > 1 and val < 3 * d - 1e-9:
            add("advisory", f"Bolt {name} {val:g} in < preferred 3d = {3 * d:g} in", "AISC 360-22 J3.3")
    emin = min_edge_distance(d)
    for name, val in (("end", Le), ("side", Ls)):
        if val < emin - 1e-9:
            add("violation", f"{name.title()} distance {val:g} in < Table J3.4 minimum {emin:g} in",
                "AISC 360-22 J3.4, Table J3.4")
    emax = min(12 * tmin, 6.0)
    for name, val in (("end", Le), ("side", Ls)):
        if val > emax + 1e-9:
            add("advisory", f"{name.title()} distance {val:g} in > 12t (6 in max) = {emax:g} in",
                "AISC 360-22 J3.5")
    smax = min(24 * tmin, 12.0)
    if max(s if rows > 1 else 0, g if cols > 1 else 0) > smax + 1e-9:
        add("advisory", f"Spacing exceeds 24t (12 in max) = {smax:g} in for painted members",
            "AISC 360-22 J3.5(a)")
    if d < 0.625:
        add("constructability", f"{d:g} in bolts: 5/8 in minimum is customary for structural "
            "connections; 3/4 in standardises the job", "detailing practice")
    return out


def end_plate_no_prying(inp: dict) -> dict:
    """Minimum end-plate (or angle leg) thickness so prying can be neglected.

    t_min = sqrt(4 T b' / (phi p Fu))  (LRFD, phi = 0.90)   AISC Manual Part 9
    t_min = sqrt(Omega 4 T b' / (p Fu)) (ASD, Omega = 1.67)
    with b' = b - d/2 (b = bolt line to face of web/weld toe) and p the tributary
    length per bolt. T is the tension per bolt.
    """
    method = need(inp, "method")
    T, b, d = float(need(inp, "T")), float(need(inp, "b")), float(need(inp, "d"))
    p, Fu, t = float(need(inp, "p")), float(need(inp, "Fu")), float(need(inp, "t"))
    bp = b - d / 2
    if bp <= 0:
        raise InputError("bolt line too close to the web: b - d/2 <= 0")
    tmin = math.sqrt(4 * T * bp / (0.90 * p * Fu)) if method == "LRFD" else \
        math.sqrt(1.67 * 4 * T * bp / (p * Fu))
    ratio = (tmin / t) ** 2 if t > 0 else math.inf     # tension capacity scales with t^2
    out = {"tmin": R4(tmin), "t": t, "bPrime": R4(bp), "ratio": R4(ratio),
           "clause": "AISC Manual Part 9 thick-plate (no-prying) criterion"}
    return result("structural.end-plate-prying", out, verdict(ratio <= 1.0),
                  [] if ratio <= 1.0 else ["Plate thinner than the no-prying minimum: either "
                   "thicken it or run a full prying analysis (Manual Part 9) - prying adds bolt tension."])
