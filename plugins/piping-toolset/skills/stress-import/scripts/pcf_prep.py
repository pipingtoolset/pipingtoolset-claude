#!/usr/bin/env python3
"""
pcf_prep.py - turn raw Revit / Fabrication PCF exports into ONE clean, AutoPIPE-ready
PCF per analysis model, for the Bentley PCF Translator (AutoPIPE).

Pipeline (driven by a job JSON - see examples/revit-to-autopipe.job.json):
  1. read every PCF matched by the job's globs (inch or mm coordinates)
  2. drop continuation records (END-POSITION-*, END-CONNECTION-PIPELINE) - these
     are what made the translator prompt "could not map END-POSITION-OPEN"
  3. clip to the model box (plant coordinates, ft)
  4. delete fabrication shop-weld COUPLINGs (1/8" long) and fuse their two nodes
  5. heal the remaining near-coincident joints (<= heal_tol_in) by snapping each
     cluster to one coordinate; fittings (elbows, tees, reducers, valves, flanges) win
     over pipe ends, so fitting geometry is preserved and pipe lengths absorb the
     adjustment
  6. rewrite flange COUPLINGs as FLANGE / FLANGE-BLIND with FLWN / FLSO / FLBL
     SKEYs, so the translator builds flanges instead of weightless RIGID pipe
  7. set valve weights from the job's weight table and write them to WEIGHT and to
     COMPONENT-ATTRIBUTE8 (the translator's "Rigid-Weight" mapping)
  8. write design data per system as COMPONENT-ATTRIBUTE1..9, following the
     translator's Attribute Mapping tab: 1 pressure, 2 temperature, 3 material,
     4 wall, 5 insulation thickness, 6 insulation density, 7 corrosion allowance,
     8 rigid weight, 9 fluid density
  9. place supports from a support CSV (nwc_supports.py output): snap each to the
     pipe centreline(s) it carries, split the pipe there, and write SUPPORT
     records whose SKEY maps through PCFIn.map [SUPPORT-TYPE] (HANG -> rod hanger
     V-stop, SKID -> shoe V-stop, GUID, ANCH ...)
 10. write one PIPELINE-REFERENCE, CRLF line endings, and validate connectivity

Every assumption the job makes is echoed into the report as ASSUMED.
Standard library only. Python 3.9+.

  python pcf_prep.py job.json [--log run.log]
Exit codes: 0 clean, 2 built with warnings that need review, 1 failed.

Outputs, in the job's output_dir, named from output_stem: STEM.pcf (the AutoPIPE-ready PCF,
CRLF), STEM_report.json (every step's counts plus the ASSUMED list), and, when the step ran,
STEM_supports.csv, STEM_infill_supports.csv, STEM_free_ends.csv, STEM_elbows_normalized.csv,
STEM_bridged_items.csv. Treat the report as the review list: warnings name the keys to fill.

Job JSON keys (paths are relative to the job file; unknown keys, including "_comment", are
ignored). Everything project-specific is a job key; nothing below is a code value.
  name                       free text, echoed to the report
  pcf_globs        (req.)    list of globs of Revit/Fabrication PCF files, merged into one model
  output_dir       (req.)    output folder, created if missing
  output_stem                output file stem (default "model")
  pipeline_reference         PIPELINE-REFERENCE written to the PCF (default: the stem)
  assumed                    list of strings echoed into the report as ASSUMED
  box_ft                     {xmin,xmax,ymin,ymax,zmin,zmax} model box in ft, plant coordinates
  clip_mode                  "any" (keep a record if any point is in the box) or "all"
  heal_tol_in                joints this close (in) are fused; default 0.25
  weld_match, fuse_rtypes    regex on ITEM-DESCRIPTION and record types (default COUPLING) treated
                             as a weld stand-in: removed and both its nodes fused
  retype                     [{from, match, to, skey}] retype records by description regex
  flange_map                 [{match, record, skey}] COUPLING-as-flange -> FLANGE / FLANGE-BLIND
  normalize_elbows           true/false (default true); elbow_margin_in (default 0.0625)
  straighten_max_dev_in      largest off-axis joint straightened (default 0.25)
  valve_weights              [{match, nps, weight_lb}] valve weights (Revit gives 0 lb)
  systems                    [{name, file_match, pressure_psig, temperature_F, material,
                             wall_in, insulation_thk_in, insulation_density_pcf, corrosion_in,
                             fluid_density_pcf}] written to COMPONENT-ATTRIBUTE1..9
  desc_schedule_tag          schedule token appended to every ITEM-DESCRIPTION lacking "SCH"
  nwc_items_csv, bridge      bridge collinear gaps of in-line items the export left out;
                             bridge keys: max_gap_in (36), reducer_max_gap_in (0 = off),
                             label_radius_in (36), unidentified_label, fallback_labels {nps: text},
                             item_weights [{match, nps, weight_lb, skey}], by_length
                             [{nps, len_in, tol_in, label, weight_lb}], as ("valve" or "rigid"),
                             valve_skey (default VVFL)
  not_inline_extra_regex     extra regex of NWC element names that are never in-line items
  three_way                  {match, port_radius_in (14), tee_leg_in (1), schedule} complete a
                             bridged 3-way valve with a tee; schedule defaults to desc_schedule_tag
  supports_csv               nwc_supports.py output; with support_rules {CLASS: {max_horiz_in,
                             min_dz_in, max_dz_in, multi_pipe, max_pipes, same_level_in,
                             tag_prefix, node_fallback, system_tag_must_match}, "_family_overrides":
                             {family substring: overrides}, "_min_support_spacing_in": 12};
                             support_system_match is a regex on the CSV system column
                             (default matches all); min_segment_in (1) is the shortest pipe a
                             split may leave; support_desc_max (32), support_skey_override {}
  infill                     {max_span_ft_by_nps {nps: ft}, hang_above_ft, trigger_factor (1.25),
                             join_across_fittings_in, count_run_ends, skey}: rest supports on
                             long runs; the spans are a PROJECT INPUT taken from the project
                             specification, never from this script
  boundary_rules             [{name, match {rtype, bore, min_bore, dir, near_box_edge_in,
                             z_min_ft, z_max_ft, horizontal}, action ANCH|FREE, tag, note}]
                             first matching rule classifies each free end; ANCH writes a support
  drop_fragments_max_components  drop disconnected pieces of at most this many components
  expected_collapse_match    regex of component descriptions allowed to collapse to zero length
  pcf_pipe_match, nwc_pipe_name_prefix  report NWC pipe named PREFIX* (default "Pipe-") whose
                             name does not match pcf_pipe_match (off unless pcf_pipe_match is set)
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import logging
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

LOG = logging.getLogger("pcf_prep")
Vec = Tuple[float, float, float]

DROP_TYPES = {"END-POSITION-OPEN", "END-POSITION-NULL", "END-POSITION-CLOSED",
              "END-CONNECTION-PIPELINE", "END-CONNECTION-EQUIPMENT", "ISO-SPLIT-POINT"}
FITTING_PRIORITY = {"ELBOW": 5, "BEND": 5, "TEE": 5, "OLET": 5, "REDUCER-CONCENTRIC": 4,
                    "REDUCER-ECCENTRIC": 4, "VALVE": 4, "FLANGE": 3, "FLANGE-BLIND": 3,
                    "COUPLING": 2, "PIPE": 1}
POINT_KEYS = ("END-POINT", "BRANCH1-POINT")
SUPPORT_SKEY = {"CLEVIS": "HANG", "TRAPEZE": "HANG", "STAND": "SKID", "ROLLER": "SKID",
                "RISER": "SKID", "GUIDE": "GUID", "ANCHOR": "ANCH"}


# --------------------------------------------------------------------------- model
@dataclass
class Comp:
    rtype: str
    lines: List[str]                       # attribute lines, without the record keyword
    src: str
    system: str = ""
    pts: List[Vec] = field(default_factory=list)   # END-POINTs then BRANCH1
    bores: List[float] = field(default_factory=list)
    tails: List[str] = field(default_factory=list)  # end-prep tokens after bore
    centre: Optional[Vec] = None
    co: Optional[Vec] = None
    desc: str = ""
    skey: str = ""
    weight: Optional[float] = None
    drop: bool = False

    def attr(self, key: str) -> Optional[str]:
        for ln in self.lines:
            t = ln.split(None, 1)
            if t and t[0] == key:
                return t[1].strip() if len(t) > 1 else ""
        return None

    def set_attr(self, key: str, value: str) -> None:
        for i, ln in enumerate(self.lines):
            t = ln.split(None, 1)
            if t and t[0] == key:
                self.lines[i] = f"    {key} {value}"
                return
        self.lines.append(f"    {key} {value}")


def parse_pcf(path: Path, scale: float) -> Tuple[List[str], List[Comp]]:
    """Return header lines and components; coordinates scaled to inches."""
    header: List[str] = []
    comps: List[Comp] = []
    cur: Optional[Comp] = None
    in_mat = False
    with path.open(encoding="latin-1") as f:
        for raw in f:
            ln = raw.rstrip("\r\n")
            if not ln.strip():
                continue
            if not ln[0].isspace():
                kw = ln.split()[0]
                if kw == "MATERIALS":
                    in_mat, cur = True, None
                    continue
                if in_mat:
                    continue
                if kw.startswith(("ISOGEN", "UNITS")) or kw == "PIPELINE-REFERENCE":
                    if not comps:
                        header.append(ln)
                    cur = None
                    continue
                cur = Comp(rtype=kw, lines=[], src=path.name)
                comps.append(cur)
                continue
            if cur is None:
                if not comps:
                    header.append(ln)
                continue
            t = ln.split()
            k = t[0]
            if k in POINT_KEYS:
                cur.pts.append(tuple(float(v) * scale for v in t[1:4]))
                cur.bores.append(float(t[4]) if len(t) > 4 else 0.0)
                cur.tails.append(" ".join(t[5:]))
                cur.lines.append(f"__{k}__")          # placeholder keeps order
                continue
            if k == "CENTRE-POINT":
                cur.centre = tuple(float(v) * scale for v in t[1:4])
                cur.lines.append("__CENTRE__")
                continue
            if k == "CO-ORDS":
                cur.co = tuple(float(v) * scale for v in t[1:4])
                cur.lines.append("__CO__")
                continue
            if k == "SKEY":
                cur.skey = t[1] if len(t) > 1 else ""
            elif k == "ITEM-DESCRIPTION":
                cur.desc = ln.split(None, 1)[1].strip() if len(t) > 1 else ""
            elif k == "WEIGHT":
                try:
                    cur.weight = float(t[1])
                except (IndexError, ValueError):
                    cur.weight = None
            cur.lines.append(ln)
    return header, comps


# --------------------------------------------------------------------------- geometry
def dist(a: Vec, b: Vec) -> float:
    return math.dist(a, b)


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def lerp(a: Vec, b: Vec, t: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


class UF:
    def __init__(self) -> None:
        self.p: Dict[int, int] = {}

    def find(self, x: int) -> int:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


class Grid:
    """Spatial hash of point references for near-neighbour queries."""

    def __init__(self, cell: float) -> None:
        self.cell = cell
        self.d: Dict[Tuple[int, int, int], List[int]] = defaultdict(list)

    def key(self, p: Vec) -> Tuple[int, int, int]:
        return tuple(int(math.floor(c / self.cell)) for c in p)

    def add(self, i: int, p: Vec) -> None:
        self.d[self.key(p)].append(i)

    def near(self, p: Vec) -> List[int]:
        k = self.key(p)
        out: List[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    out.extend(self.d.get((k[0] + dx, k[1] + dy, k[2] + dz), ()))
        return out


# --------------------------------------------------------------------------- steps
def in_box(p: Vec, box: Optional[dict]) -> bool:
    if not box:
        return True
    x, y, z = (c / 12.0 for c in p)
    return (box.get("xmin", -1e9) <= x <= box.get("xmax", 1e9) and
            box.get("ymin", -1e9) <= y <= box.get("ymax", 1e9) and
            box.get("zmin", -1e9) <= z <= box.get("zmax", 1e9))


def heal(comps: List[Comp], tol: float, report: dict) -> None:
    """Fuse weld couplings, then snap every near-coincident endpoint cluster."""
    refs: List[Tuple[int, int]] = []          # (comp idx, point idx)
    pts: List[Vec] = []
    for ci, c in enumerate(comps):
        if c.drop:
            continue
        for pi, p in enumerate(c.pts):
            refs.append((ci, pi))
            pts.append(p)
    uf = UF()
    grid = Grid(max(tol, 0.05) * 2)
    for i, p in enumerate(pts):
        grid.add(i, p)
    gaps = Counter()
    for i, p in enumerate(pts):
        for j in grid.near(p):
            if j > i:
                d = dist(p, pts[j])
                if d <= tol:
                    if d > 1e-4:
                        gaps[round(d, 3)] += 1
                    uf.union(i, j)
    # weld couplings: fuse both ends, then drop the weld
    ref_index = {r: i for i, r in enumerate(refs)}
    welds = 0
    for ci, c in enumerate(comps):
        if c.drop or c.rtype not in report.get("_fuse_rtypes", ("COUPLING",)) or not re.search(report["_weld_re"], c.desc, re.I):
            continue
        if len(c.pts) == 2:
            uf.union(ref_index[(ci, 0)], ref_index[(ci, 1)])
        c.drop = True
        welds += 1
    clusters: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(pts)):
        clusters[uf.find(i)].append(i)
    moved, maxmove = 0, 0.0
    for members in clusters.values():
        live = [m for m in members if not comps[refs[m][0]].drop]
        if not live:
            # cluster made only of weld ends (weld between two other welds) - keep first
            live = members
        best = max(FITTING_PRIORITY.get(comps[refs[m][0]].rtype, 0) for m in live)
        anchors = [pts[m] for m in live if FITTING_PRIORITY.get(comps[refs[m][0]].rtype, 0) == best]
        target = tuple(sum(v[k] for v in anchors) / len(anchors) for k in range(3))
        for m in members:
            ci, pi = refs[m]
            d = dist(comps[ci].pts[pi], target)
            if d > 1e-6:
                moved += 1
                maxmove = max(maxmove, d)
            comps[ci].pts[pi] = target
    # a component whose own ends collapsed is now zero-length: drop and report it
    collapsed = []
    for c in comps:
        if not c.drop and len(c.pts) >= 2 and dist(c.pts[0], c.pts[1]) < 1e-3:
            c.drop = True
            collapsed.append(f"{c.rtype} '{c.desc}'")
    report["heal"] = dict(tolerance_in=tol, weld_couplings_removed=welds, joints_closed=sum(gaps.values()),
                          gap_sizes_in=dict(gaps.most_common(10)), endpoints_moved=moved,
                          max_move_in=round(maxmove, 4), collapsed_components=dict(Counter(collapsed)))


def fix_flanges(comps: List[Comp], fl_map: List[dict], report: dict) -> None:
    n = Counter()
    for c in comps:
        if c.drop or c.rtype != "COUPLING":
            continue
        for rule in fl_map:
            if re.search(rule["match"], c.desc, re.I):
                c.rtype = rule["record"]
                c.skey = rule["skey"]
                c.set_attr("SKEY", rule["skey"])
                n[rule["skey"]] += 1
                break
    report["flanges_rewritten"] = dict(n)


# --------------------------------------------------------------------------- geometry clean-up for AutoPIPE
STRAIGHT_TYPES = {"PIPE", "FLANGE", "FLANGE-BLIND", "VALVE", "MISC-COMPONENT", "REDUCER-CONCENTRIC", "COUPLING"}


def _unit(v: Vec) -> Optional[Vec]:
    L = math.sqrt(dot(v, v))
    return None if L < 1e-9 else (v[0] / L, v[1] / L, v[2] / L)


def _point_index(comps: List[Comp]) -> Dict[Tuple[float, float, float], List[Tuple[int, int]]]:
    idx: Dict[Tuple[float, float, float], List[Tuple[int, int]]] = defaultdict(list)
    for ci, c in enumerate(comps):
        if c.drop or c.rtype == "SUPPORT":
            continue
        for pi, p in enumerate(c.pts):
            idx[tuple(round(v, 3) for v in p)].append((ci, pi))
    return idx


def fix_overlapping_valves(comps: List[Comp], report: dict, reach_in: float = 6.0) -> None:
    """Revit sometimes places a wafer/lug valve on the wrong side of its flange face, inside the
    flange. The translator then logs 'Overlapping Components',
    and the flange gap on the other side becomes two false free ends (were anchored as CUT).
    Re-seat the valve between the two flange faces it belongs between."""
    idx = _point_index(comps)
    fixed = []
    for vi, v in enumerate(comps):
        if v.drop or v.rtype != "VALVE" or len(v.pts) != 2:
            continue
        for k in (0, 1):
            shared, inner = v.pts[k], v.pts[1 - k]
            fl = [(ci, pi) for ci, pi in idx.get(tuple(round(x, 3) for x in shared), [])
                  if ci != vi and comps[ci].rtype in ("FLANGE", "FLANGE-BLIND") and len(comps[ci].pts) == 2]
            if not fl:
                continue
            fc, fpi = fl[0]
            f = comps[fc]
            u = _unit(sub(f.pts[1 - fpi], shared))         # into the flange body
            w = _unit(sub(inner, shared))                  # into the valve body
            if not u or not w or dot(u, w) < 0.999:        # valve does not lie inside the flange
                continue
            # look for a free flange face behind the shared face, on the same axis
            best = None
            for key, refs in idx.items():
                if len(refs) != 1:
                    continue
                ci, pi = refs[0]
                if comps[ci].rtype not in ("FLANGE", "FLANGE-BLIND"):
                    continue
                d = sub(key, shared)
                L = math.sqrt(dot(d, d))
                if 0.05 < L <= reach_in and dot(d, u) <= -0.999 * L and (best is None or L < best[0]):
                    best = (L, comps[ci].pts[pi])
            if best is None:
                continue
            old = list(v.pts)
            v.pts = [best[1], shared] if k == 1 else [shared, best[1]]
            fixed.append(dict(valve=v.desc[:60], old=[tuple(round(c, 3) for c in p) for p in old],
                              new=[tuple(round(c, 3) for c in p) for p in v.pts]))
            idx = _point_index(comps)
            break
    report["valves_reseated"] = fixed


def align_offset_valves(comps: List[Comp], report: dict, max_off_in: float = 1.0, max_chain: int = 12) -> None:
    """A valve whose two ends sit on different parallel axes (e.g. an 8in valve on a blind-flanged
    stub with a 0.551 in vertical step, an 11.5 deg kink) is put back on one axis by translating the
    DEAD-END side (the chain of straight parts that ends at a free end, e.g. a blind flange) onto
    the axis of the connected side. Live-both-sides cases are only reported."""
    idx = _point_index(comps)
    key = lambda p: tuple(round(v, 3) for v in p)
    fixed, reported = [], []
    for vi, v in enumerate(comps):
        if v.drop or v.rtype != "VALVE" or len(v.pts) != 2:
            continue
        sides = []
        for k in (0, 1):
            nb = [(j, pj) for j, pj in idx.get(key(v.pts[k]), []) if j != vi]
            sides.append(nb[0] if len(nb) == 1 else None)
        if None in sides:
            continue
        # axis of each side from the neighbouring straight component
        axes = []
        for (j, pj) in sides:
            c = comps[j]
            axes.append(_unit(sub(c.pts[pj], c.pts[1 - pj])) if c.rtype in STRAIGHT_TYPES and len(c.pts) == 2 else None)
        if None in axes or dot(axes[0], axes[1]) > -0.9999:
            continue                                   # not two parallel, opposed straight neighbours
        u = axes[0]
        d = sub(v.pts[1], v.pts[0])
        along = dot(d, u)
        off = (d[0] - u[0] * along, d[1] - u[1] * along, d[2] - u[2] * along)
        m = math.sqrt(dot(off, off))
        if m < 0.01 or m > max_off_in:
            continue
        # walk each side to see if it is a short dead-end chain
        def chain(k: int) -> Optional[List[int]]:
            seen, out = {vi}, []
            j, pj = sides[k]
            for _ in range(max_chain):
                c = comps[j]
                if c.rtype not in STRAIGHT_TYPES or len(c.pts) != 2:
                    return None
                out.append(j)
                seen.add(j)
                far = c.pts[1 - pj]
                nb = [(a, b) for a, b in idx.get(key(far), []) if a not in seen]
                if not nb:
                    return out                         # free end reached
                if len(nb) > 1:
                    return None
                j, pj = nb[0]
            return None
        c1, c0 = chain(1), chain(0)
        if c1 is not None and (c0 is None or len(c1) <= len(c0)):
            move, shift = c1, (-off[0], -off[1], -off[2]); vk = 1
        elif c0 is not None:
            move, shift = c0, off; vk = 0
        else:
            reported.append(dict(valve=v.desc[:50], offset_in=round(m, 3), at=key(v.pts[0])))
            continue
        for j in move:
            comps[j].pts = [(p[0] + shift[0], p[1] + shift[1], p[2] + shift[2]) for p in comps[j].pts]
        v.pts[vk] = (v.pts[vk][0] + shift[0], v.pts[vk][1] + shift[1], v.pts[vk][2] + shift[2])
        fixed.append(dict(valve=v.desc[:50], offset_in=round(m, 3), dead_end_parts_moved=len(move),
                          at=key(v.pts[0])))
        idx = _point_index(comps)
    report["offset_valves_aligned"] = fixed
    if reported:
        report["offset_valves_REVIEW"] = reported


def straighten_inline(comps: List[Comp], report: dict, max_dev_in: float = 0.25, passes: int = 3) -> None:
    """Project the joint between two straight in-line components back onto the line through
    their outer ends. Joint healing (fittings win) can leave a fitting-to-fitting joint a few
    hundredths off-axis; AutoPIPE reports that as 'Kink in straight run' (seen as 2.5 deg at a
    6in valve). Only joints shared by exactly two straight components are
    moved, by at most max_dev_in, never eccentric reducers."""
    moved, maxmove = 0, 0.0
    for _ in range(passes):
        idx = _point_index(comps)
        n = 0
        for key, refs in idx.items():
            if len(refs) != 2:
                continue
            (ca, pa), (cb, pb) = refs
            A, B = comps[ca], comps[cb]
            if A.rtype not in STRAIGHT_TYPES or B.rtype not in STRAIGHT_TYPES or len(A.pts) != 2 or len(B.pts) != 2:
                continue
            P, Pa, Pb = A.pts[pa], A.pts[1 - pa], B.pts[1 - pb]
            u = _unit(sub(Pb, Pa))
            if not u:
                continue
            t = dot(sub(P, Pa), u)
            Q = (Pa[0] + u[0] * t, Pa[1] + u[1] * t, Pa[2] + u[2] * t)
            d = dist(P, Q)
            if d < 1e-4 or d > max_dev_in or t <= 0 or t >= dist(Pa, Pb):
                continue
            A.pts[pa] = Q
            B.pts[pb] = Q
            n += 1
            maxmove = max(maxmove, d)
        moved += n
        if not n:
            break
    report["straightened_joints"] = dict(count=moved, max_move_in=round(maxmove, 4))


def normalize_elbows(comps: List[Comp], report: dict, margin_in: float = 0.0625) -> None:
    """Make every elbow that butts another fitting a true AutoPIPE bend.

    The PCF Translator writes each ELBOW as a TIP plus a radius R = mean(T1, T2) / tan(theta/2)
    from the two Revit tangent lengths. AutoPIPE then needs R*tan(theta/2) of straight on BOTH
    legs. Revit elbows are often 0.03-0.06 in asymmetric, so the short leg overshoots when it
    butts a fitting (no pipe to absorb it): E726-15 'undefined bend' + W726-8 'kink' (seen on
    rolling offsets made of a 90 and a 45 deg elbow). Back-to-back elbows also need their shared leg on
    the TIP-to-TIP line.

    Fix, per elbow that touches another elbow or has unequal legs and touches any non-pipe:
      * both legs set to min(T1, T2) - margin_in, TIP fixed (routing unchanged);
      * a leg shared with another elbow is re-aimed along TIP->TIP;
      * the slack goes to the adjacent pipe, or to a short filler PIPE when the neighbour
        is a fitting. The radius drops by margin/tan(theta/2) (~3 % on a 3in 45, recorded)."""
    idx = _point_index(comps)
    PIPE_DESC.clear()
    for c in comps:
        if not c.drop and c.rtype == "PIPE" and c.bores and c.desc:
            PIPE_DESC.setdefault((c.src, round(c.bores[0], 3)), c.desc)
            PIPE_DESC.setdefault(("*", round(c.bores[0], 3)), c.desc)

    def neigh(ci: int, p: Vec) -> List[Tuple[int, int]]:
        return [(cj, pj) for cj, pj in idx.get(tuple(round(v, 3) for v in p), []) if cj != ci]

    plan: Dict[int, List[Vec]] = {}
    for ci, c in enumerate(comps):
        if c.drop or c.rtype not in ("ELBOW", "BEND") or c.centre is None or len(c.pts) != 2:
            continue
        nb = [neigh(ci, p) for p in c.pts]
        types = [[comps[j].rtype for j, _ in n] for n in nb]
        T = [dist(p, c.centre) for p in c.pts]
        # Only elbows butted to another elbow or a reducer: the class AutoPIPE rejected.
        # Elbows on flanges/valves imported clean and are left exactly as Revit drew them
        # (trimming them too made the translator's nominal 'L' radius overshoot: E726-15 on 28
        # bends in one test).
        touch_elbow = any(t in ("ELBOW", "BEND") for ts in types for t in ts)
        touch_red = any(t.startswith("REDUCER") for ts in types for t in ts)
        if not (touch_elbow or (touch_red and abs(T[0] - T[1]) > 0.005)):
            continue                                           # symmetric elbow on a reducer: fine as is
        dirs = []
        for k, p in enumerate(c.pts):
            d = _unit(sub(p, c.centre))
            other = next((comps[j] for j, _ in nb[k] if comps[j].rtype in ("ELBOW", "BEND") and comps[j].centre), None)
            if other is not None:
                d2 = _unit(sub(other.centre, c.centre))
                if d2 and d and dot(d, d2) > math.cos(math.radians(3)):
                    d = d2
            dirs.append(d)
        theta = 180.0 - math.degrees(math.acos(max(-1.0, min(1.0, dot(dirs[0], dirs[1])))))
        if theta < 1.0:
            continue
        nps = c.bores[0] if c.bores else 0.0
        t_nom = 1.5 * nps * math.tan(math.radians(theta / 2))    # LR elbow: R = 1.5 x NPS
        room = []
        for k in (0, 1):
            ts = types[k]
            if not ts:
                room.append(T[k])
            elif all(t == "PIPE" for t in ts):
                pl = min(dist(comps[j].pts[0], comps[j].pts[1]) for j, _ in nb[k])
                room.append(T[k] + max(0.0, pl - 0.5))       # pipe absorbs
            elif any(t in ("ELBOW", "BEND") for t in ts):
                room.append(T[k] - margin_in / 2)              # filler between the two elbows
            else:
                room.append(T[k] - margin_in)                  # reducer / valve / flange: keep straight
        if t_nom <= min(room):
            Tn = t_nom                                         # translator writes 'L', exact match
        else:
            # cannot fit nominal: explicit radius, kept >3.5 % below nominal so the translator
            # does not round it to 'L' (written as L within ~2 %, explicit at +3 %: calibrated on
            # translator output)
            Tn = min(min(room), 0.965 * t_nom)
        if Tn <= 0.25 * min(T):
            continue
        new = [(c.centre[0] + d[0] * Tn, c.centre[1] + d[1] * Tn, c.centre[2] + d[2] * Tn) for d in dirs]
        plan[ci] = new

    fillers, retargeted, rows = 0, 0, []
    done_pairs = set()
    for ci, new in plan.items():
        c = comps[ci]
        old = list(c.pts)
        for k in (0, 1):
            nb = neigh(ci, old[k])
            pipes = [(j, pj) for j, pj in nb if comps[j].rtype == "PIPE"]
            elb = [(j, pj) for j, pj in nb if j in plan]
            if elb:                                    # back-to-back: one filler between the two new ends
                j, pj = elb[0]
                pair = tuple(sorted((ci, j)))
                if pair in done_pairs:
                    continue
                done_pairs.add(pair)
                a, b = new[k], plan[j][pj]
                if dist(a, b) > 0.005:
                    comps.append(_filler(c, a, b, k))
                    fillers += 1
            elif pipes and len(nb) == len(pipes):     # pipe absorbs the slack
                for j, pj in pipes:
                    comps[j].pts[pj] = new[k]
                retargeted += 1
            elif nb:                                   # fitting / valve / flange: filler pipe
                comps.append(_filler(c, new[k], old[k], k))
                fillers += 1
        for k in (0, 1):
            c.pts[k] = new[k]
        th = math.degrees(math.acos(max(-1.0, min(1.0, dot(_unit(sub(new[0], c.centre)), _unit(sub(new[1], c.centre)))))))
        bend = 180.0 - th
        rows.append(dict(desc=c.desc[:30], nps=c.bores[0] if c.bores else "",
                         tip=tuple(round(v, 3) for v in c.centre), legs_old_in=[round(t, 4) for t in
                         (dist(old[0], c.centre), dist(old[1], c.centre))],
                         leg_new_in=round(dist(new[0], c.centre), 4), angle_deg=round(bend, 2),
                         radius_new_in=round(dist(new[0], c.centre) / math.tan(math.radians(bend / 2)), 3)
                         if bend > 0.5 else ""))
    report["elbows_normalized"] = dict(count=len(plan), filler_pipes=fillers, pipes_retargeted=retargeted,
                                       margin_in=margin_in)
    report["_elbow_rows"] = rows


PIPE_DESC: Dict[Tuple[str, float], str] = {}


def _filler(el: Comp, a: Vec, b: Vec, k: int) -> Comp:
    """Short PIPE for elbow-tangent slack; description copied from a real pipe of the same file and
    bore so the translator assigns the same schedule (e.g. '...SCH40...')."""
    bore = el.bores[k] if k < len(el.bores) else (el.bores[0] if el.bores else 0.0)
    keep = [ln for ln in el.lines if ln.strip().split(" ")[0] in ("PIPING-SPEC", "SPOOL-IDENTIFIER")]
    d = PIPE_DESC.get((el.src, round(bore, 3))) or PIPE_DESC.get(("*", round(bore, 3))) or "Pipe"
    return Comp(rtype="PIPE", lines=["__END-POINT__", "__END-POINT__",
                                     f"    ITEM-DESCRIPTION {d} (elbow tangent filler)"] + keep,
                src=el.src, system=el.system, pts=[a, b], bores=[bore, bore],
                tails=[el.tails[k] if k < len(el.tails) else "", el.tails[k] if k < len(el.tails) else ""],
                desc="Pipe - elbow tangent filler")


def set_valve_weights(comps: List[Comp], table: List[dict], report: dict) -> None:
    unmatched = Counter()
    done = Counter()
    for c in comps:
        if c.drop or c.rtype != "VALVE":
            continue
        if "BRIDGED" in (c.attr("ITEM-DESCRIPTION") or ""):
            continue                                  # weight set by bridge_gaps item_weights
        bore = max(c.bores) if c.bores else 0.0
        w = None
        for row in table:
            if re.search(row["match"], c.desc, re.I) and abs(float(row["nps"]) - bore) < 0.01:
                w = row.get("weight_lb")
                break
        if w in (None, "", 0):
            unmatched[f"{c.desc} @ NPS {bore:g}"] += 1
            continue
        c.weight = float(w)
        c.set_attr("WEIGHT", f"{float(w):.3f}")
        done[f"{c.desc} @ NPS {bore:g}"] += 1
    report["valve_weights_set"] = dict(done)
    report["valve_weights_MISSING"] = dict(unmatched)


def set_attributes(comps: List[Comp], systems: List[dict], report: dict) -> None:
    order = ["pressure_psig", "temperature_F", "material", "wall_in", "insulation_thk_in",
             "insulation_density_pcf", "corrosion_in", None, "fluid_density_pcf"]
    unknown = Counter()
    for c in comps:
        if c.drop:
            continue
        sysdef = next((s for s in systems if re.search(s["file_match"], c.src, re.I)), None)
        if sysdef is None:
            unknown[c.src] += 1
            continue
        c.system = sysdef["name"]
        for n, key in enumerate(order, start=1):
            if n == 8:
                if c.weight and c.rtype in ("VALVE", "FLANGE", "FLANGE-BLIND", "MISC-COMPONENT"):
                    c.set_attr("COMPONENT-ATTRIBUTE8", f"{c.weight:.3f}")
                continue
            val = sysdef.get(key)
            if val not in (None, ""):
                c.set_attr(f"COMPONENT-ATTRIBUTE{n}", str(val))
    if unknown:
        report["components_without_system"] = dict(unknown)


# --------------------------------------------------------------------------- gaps the export left
# NWC element names that are never an in-line item (pipe, fittings, supports, model scaffolding).
# Add project names with the job key "not_inline_extra_regex".
NOT_INLINE_BASE = (r"Pipe-|Shop Weld|Weld Neck|Slip-On|Blind|Elbow|Tee|Reducer|Cap|Olet|"
                   r"Fabrication Skin|Insulation|Mechanical:|MEP Fabrication|.*SUPPORT|Level|Workset|"
                   r"Pipe Systems")


def not_inline_re(extra: str = "") -> "re.Pattern":
    return re.compile("^(" + NOT_INLINE_BASE + (("|" + extra) if extra else "") + ")", re.I)


def node_table(comps: List[Comp]):
    """node key -> list of (comp idx, point idx); outward unit direction per free end."""
    nodes: Dict[Tuple[float, float, float], List[Tuple[int, int]]] = defaultdict(list)
    for ci, c in enumerate(comps):
        if c.drop or c.rtype == "SUPPORT":
            continue
        for pi, p in enumerate(c.pts):
            nodes[tuple(round(v, 3) for v in p)].append((ci, pi))
    return nodes


def outward(c: Comp, pi: int) -> Optional[Vec]:
    p = c.pts[pi]
    if c.rtype in ("ELBOW", "BEND", "TEE") and c.centre is not None:
        base = c.centre
    elif len(c.pts) >= 2:
        base = c.pts[1 - pi] if pi < 2 else c.centre
    else:
        return None
    if base is None:
        return None
    d = sub(p, base)
    L = math.sqrt(dot(d, d))
    return None if L < 1e-6 else (d[0] / L, d[1] / L, d[2] / L)


def bridge_gaps(comps: List[Comp], cfg: dict, items: List[dict], report: dict) -> None:
    """Close collinear, same-bore gaps between free ends with a RIGID stand-in for the
    in-line item the PCF export omitted (strainer, control valve, meter ...)."""
    max_len = float(cfg.get("max_gap_in", 36.0))
    weights = cfg.get("item_weights", [])
    not_inline = not_inline_re(str(cfg.get("not_inline_extra_regex", "")))
    nodes = node_table(comps)
    free = [(k, v[0]) for k, v in nodes.items() if len(v) == 1]
    ends = []
    for k, (ci, pi) in free:
        u = outward(comps[ci], pi)
        if u:
            ends.append((k, ci, pi, u, comps[ci].bores[pi] if pi < len(comps[ci].bores) else 0.0))
    pairs = []
    for i in range(len(ends)):
        ki, ci, pi, ui, bi = ends[i]
        for j in range(i + 1, len(ends)):
            kj, cj, pj, uj, bj = ends[j]
            red_max = float(cfg.get("reducer_max_gap_in", 0.0))
            if abs(bi - bj) > 0.01 and red_max <= 0:
                continue
            v = sub(kj, ki)
            L = math.sqrt(dot(v, v))
            if L < 0.05 or L > (max_len if abs(bi - bj) <= 0.01 else red_max):
                continue
            if dot(v, ui) >= 0.995 * L and -dot(v, uj) >= 0.995 * L:
                pairs.append((L, i, j))
    pairs.sort()
    used = set()
    made = []
    for L, i, j in pairs:
        if i in used or j in used:
            continue
        used.update((i, j))
        ki, ci, _, _, b = ends[i]
        kj, _, _, _, b2 = ends[j]
        mid = lerp(ki, kj, 0.5)
        if abs(b - b2) > 0.01:
            # collinear gap between two sizes: the export dropped a concentric reducer
            src = comps[ci]
            big, small = max(b, b2), min(b, b2)
            nc = Comp(rtype="REDUCER-CONCENTRIC", lines=["__END-POINT__", "__END-POINT__", "    SKEY RCBW",
                      f"    ITEM-DESCRIPTION Reducer Concentric {big:g}x{small:g} (BRIDGED - not in PCF export)"],
                      src=src.src, system=src.system, pts=[ki, kj], bores=[b, b2], tails=["", ""],
                      desc="Reducer Concentric (bridged)", skey="RCBW")
            comps.append(nc)
            made.append(dict(label=f"Reducer Concentric {big:g}x{small:g}", nps=f"{b:g}x{b2:g}", length_in=round(L, 3),
                             weight_lb="library", x_ft=round(mid[0] / 12, 2), y_ft=round(mid[1] / 12, 2),
                             z_ft=round(mid[2] / 12, 2)))
            continue
        label = cfg.get("unidentified_label", "UNIDENTIFIED IN-LINE ITEM")
        bylen = next((r for r in cfg.get("by_length", []) if abs(float(r["nps"]) - b) < 0.01
                      and abs(float(r["len_in"]) - L) <= float(r.get("tol_in", 0.15))), None)
        best = None
        for it in items:
            q = (float(it["x_ft"]) * 12, float(it["y_ft"]) * 12, float(it["z_ft"]) * 12)
            d = dist(q, mid)
            nm = it.get("name", "")
            if d <= float(cfg.get("label_radius_in", 36.0)) and nm and re.match(r"[A-Za-z][A-Za-z0-9 _.()-]{4,}$", nm) \
                    and not not_inline.match(nm) and (best is None or d < best[0]):
                best = (d, nm)
        if bylen:
            label = bylen["label"]
        elif best:
            label = best[1]
        else:
            label = cfg.get("fallback_labels", {}).get(f"{b:g}", label)
        if bylen:
            w = bylen.get("weight_lb")
        else:
            w = next((r.get("weight_lb") for r in weights if re.search(r["match"], label, re.I)
                      and abs(float(r.get("nps", b)) - b) < 0.01), None)
        src = comps[ci]
        # In-line item -> VALVE record (AutoPIPE VALV: rigid element carrying its full weight).
        # As a MISC-COMPONENT/SP rigid the translator wrote only HALF the weight as a WGT point
        # load (confirmed in AutoPIPE). Set "as": "rigid" in the job to revert.
        as_rigid = str(cfg.get("as", "valve")).lower() == "rigid"
        skey = next((r.get("skey") for r in weights if re.search(r["match"], label, re.I) and r.get("skey")),
                    cfg.get("valve_skey", "VVFL"))
        rtype, sk = ("MISC-COMPONENT", "SP") if as_rigid else ("VALVE", skey)
        nc = Comp(rtype=rtype, lines=["__END-POINT__", "__END-POINT__", f"    SKEY {sk}",
                                      f"    ITEM-DESCRIPTION {label} (BRIDGED - not in PCF export)"],
                  src=src.src, system=src.system, pts=[ki, kj], bores=[b, b], tails=["PL", "PL"] if not as_rigid else ["", ""],
                  desc=label, skey=sk, weight=float(w) if w not in (None, "") else None)
        if nc.weight:
            nc.set_attr("WEIGHT", f"{nc.weight:.3f}")
        comps.append(nc)
        made.append(dict(label=label, nps=b, length_in=round(L, 3), weight_lb=w if w not in (None, "") else "MISSING",
                         x_ft=round(mid[0] / 12, 2), y_ft=round(mid[1] / 12, 2), z_ft=round(mid[2] / 12, 2)))
    report["bridged_gaps"] = dict(count=len(made), by_label=dict(Counter(m["label"] for m in made)),
                                  weights_missing=sum(1 for m in made if m["weight_lb"] == "MISSING"))
    report["_bridges"] = made



def attach_three_way(comps: List[Comp], cfg: dict, report: dict) -> None:
    """A bridged 3-way valve is a 2-port rigid; its third (bypass) port is left as a free flange
    face about 1/2 valve-length off the run. Split the valve at its midpoint and add a rigid
    third leg to that free end. Weight split 40/40/20 (halves/leg) so the total is unchanged."""
    rx = cfg.get("match")
    if not rx:
        return
    rad = float(cfg.get("port_radius_in", 14.0))
    nodes = node_table(comps)
    free = {k: v[0] for k, v in nodes.items() if len(v) == 1}
    done, legs = 0, []
    for ci in range(len(comps)):
        c = comps[ci]
        if c.drop or c.rtype != "VALVE" or not re.search(rx, c.desc, re.I) or len(c.pts) != 2:
            continue
        a, b = c.pts
        mid = lerp(a, b, 0.5)
        ax = sub(b, a)
        L = math.sqrt(dot(ax, ax))
        best = None
        for k, (fj, fp) in free.items():
            v = sub(k, mid)
            d = math.sqrt(dot(v, v))
            if d < 1.0 or d > rad or abs(dot(v, ax)) / (d * L) > 0.05:
                continue
            if best is None or d < best[0]:
                best = (d, k, fj, fp)
        if not best:
            continue
        W = c.weight or 0.0
        b_bore = comps[best[2]].bores[best[3]] if best[3] < len(comps[best[2]].bores) else c.bores[0]
        def mk(p0, p1, w, bore0, bore1, tag):
            n = Comp(rtype="VALVE", lines=["__END-POINT__", "__END-POINT__", f"    SKEY {c.skey or 'VVFL'}",
                     f"    ITEM-DESCRIPTION {c.desc} {tag} (BRIDGED - not in PCF export)"],
                     src=c.src, system=c.system, pts=[p0, p1], bores=[bore0, bore1], tails=["PL", "PL"],
                     desc=f"{c.desc} {tag}", skey=c.skey or "VVFL", weight=w if w else None)
            if w:
                n.set_attr("WEIGHT", f"{w:.3f}")
            for ln in c.lines:
                if ln.strip().startswith("COMPONENT-ATTRIBUTE"):
                    n.lines.append(ln)
            return n
        c.drop = True
        def nb_src(pt):
            for cj, cc in enumerate(comps):
                if cj == ci or cc.drop or cc.rtype == "SUPPORT":
                    continue
                if any(dist(q, pt) < 1e-3 for q in cc.pts):
                    return cc.src
            return c.src
        # AutoPIPE will not start a VALVE at a 3-connection point ("CANNOT PUT VALVE AT THIS POINT").
        # Put a real TEE at the valve centre and hang the three
        # rigid valve pieces off its ends: VALVE a->p1, TEE p1-p2 (centre mid, branch q), VALVE p2->b,
        # VALVE q->port.
        leg = float(cfg.get("tee_leg_in", 1.0))
        u_run = tuple(x / L for x in ax)
        v_br = sub(best[1], mid)
        u_br = tuple(x / best[0] for x in v_br)
        p1 = tuple(mid[k] - u_run[k] * leg for k in range(3))
        p2 = tuple(mid[k] + u_run[k] * leg for k in range(3))
        q = tuple(mid[k] + u_br[k] * leg for k in range(3))
        pa, pb, pc = mk(a, p1, 0.4 * W, c.bores[0], c.bores[0], "half A"), mk(p2, b, 0.4 * W, c.bores[1], c.bores[1], "half B"), \
            mk(q, best[1], 0.2 * W, b_bore, b_bore, "port C")
        tee = Comp(rtype="TEE", lines=["__END-POINT__", "__END-POINT__", "__CENTRE__", "__BRANCH1-POINT__", "    SKEY TEPL",
                   f"    ITEM-DESCRIPTION TEE - 3-WAY VALVE BODY JUNCTION (MODEL ONLY) - {cfg.get('schedule', 'STD')}"],
                   src=c.src, system=c.system, pts=[p1, p2, q], bores=[c.bores[0], c.bores[1], b_bore], tails=["BW", "BW", "BW"],
                   centre=mid, desc=f"TEE - 3-WAY VALVE BODY JUNCTION (MODEL ONLY) - {cfg.get('schedule', 'STD')}", skey="TEPL")
        pa.src, pb.src, pc.src = nb_src(a), nb_src(b), nb_src(best[1])
        tee.src = pa.src
        for n in (pa, pb, pc):
            n.lines = [ln for ln in n.lines if not ln.strip().startswith("COMPONENT-ATTRIBUTE")]
        comps.extend([pa, tee, pb, pc])
        free.pop(best[1], None)
        done += 1
        legs.append(dict(valve=c.desc, x_ft=round(mid[0] / 12, 2), y_ft=round(mid[1] / 12, 2), z_ft=round(mid[2] / 12, 2),
                         port_offset_in=round(best[0], 2)))
    report["three_way_valves_completed"] = dict(count=done, rows=legs)

def boundary_conditions(comps: List[Comp], rules: List[dict], box: Optional[dict], report: dict) -> List[dict]:
    """Classify every remaining free end and write explicit ANCH supports where the end is a real
    boundary (equipment nozzle, riser tie-in, model cut). Blind flanges and capped valves stay free.
    Use with the translator's 'Add anchors at free ends' OFF so the model carries only intended anchors."""
    nodes = node_table(comps)
    free = [(k, v[0]) for k, v in nodes.items() if len(v) == 1]
    rows, counts = [], Counter()
    seq = Counter()
    for k, (ci, pi) in sorted(free):
        c = comps[ci]
        u = outward(c, pi) or (0.0, 0.0, 0.0)
        bore = c.bores[pi] if pi < len(c.bores) else 0.0
        edge = min(abs(k[0] / 12 - box.get("xmin", -1e9)), abs(k[0] / 12 - box.get("xmax", 1e9)),
                   abs(k[1] / 12 - box.get("ymin", -1e9)), abs(k[1] / 12 - box.get("ymax", 1e9))) * 12 if box else 1e9
        hit = None
        for r in rules:
            m = r.get("match", {})
            if "rtype" in m and not re.search(m["rtype"], c.rtype):
                continue
            if "bore" in m and abs(float(m["bore"]) - bore) > 0.01:
                continue
            if "min_bore" in m and bore < float(m["min_bore"]) - 0.01:
                continue
            if "dir" in m:
                ax = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}[m["dir"]]
                if dot(u, ax) < 0.99:
                    continue
            if "near_box_edge_in" in m and edge > float(m["near_box_edge_in"]):
                continue
            if "z_min_ft" in m and k[2] / 12 < float(m["z_min_ft"]):
                continue
            if "z_max_ft" in m and k[2] / 12 > float(m["z_max_ft"]):
                continue
            if "horizontal" in m and bool(m["horizontal"]) != (abs(u[2]) < 0.1):
                continue
            hit = r
            break
        name = hit["name"] if hit else "UNCLASSIFIED"
        action = hit["action"] if hit else "FREE"
        counts[(name, action)] += 1
        tag = ""
        if action == "ANCH":
            seq[hit["tag"]] += 1
            tag = f"{hit['tag']}-{c.system or 'X'}-{seq[hit['tag']]:02d}"
            s = Comp(rtype="SUPPORT", lines=["__CO__", "    SKEY ANCH", f"    NAME {tag}",
                                             f"    ITEM-DESCRIPTION BND {hit['tag']} {name}"],
                     src="boundary", co=k, bores=[bore], desc=name)
            comps.append(s)
        rows.append(dict(x_ft=round(k[0] / 12, 3), y_ft=round(k[1] / 12, 3), z_ft=round(k[2] / 12, 3), system=c.system,
                         end_component=c.rtype, nps=bore, direction=",".join(f"{v:.0f}" for v in u),
                         classification=name, action=action, support_name=tag, note=hit.get("note", "") if hit else
                         "review: not matched by any boundary rule"))
    report["boundaries"] = {f"{n} -> {a}": v for (n, a), v in counts.items()}
    return rows


def drop_duplicate_pipes(comps: List[Comp], report: dict, tol: float = 0.25) -> None:
    """Revit sometimes exports a second PIPE lying on top of already-modelled pipe/fittings.
    Drop a PIPE when its two ends and midpoint all lie on OTHER straight components."""
    dropped = []
    seen_exact = {}
    for i, c in enumerate(comps):                  # identical copies (same type, same ends)
        if c.drop or c.rtype == "SUPPORT" or len(c.pts) != 2:
            continue
        key = (c.rtype, frozenset(tuple(round(v, 2) for v in p) for p in c.pts))
        if key in seen_exact:
            c.drop = True
            dropped.append(dict(at_ft=[round(v / 12, 2) for v in c.pts[0]], length_in=round(dist(*c.pts), 2),
                                nps=c.bores[0], kind="exact duplicate"))
        else:
            seen_exact[key] = i
    segs = [(i, c.pts[0], c.pts[1]) for i, c in enumerate(comps)
            if not c.drop and c.rtype != "SUPPORT" and len(c.pts) == 2]

    def on_other(p: Vec, skip: int) -> bool:
        for j, a, b in segs:
            if j == skip:
                continue
            d = sub(b, a)
            L2 = dot(d, d)
            if L2 < 1e-9:
                continue
            t = dot(sub(p, a), d) / L2
            if -1e-6 <= t <= 1 + 1e-6 and dist(p, lerp(a, b, t)) <= tol:
                return True
        return False

    deg = Counter(tuple(round(v, 3) for v in p) for c in comps if not c.drop and c.rtype != "SUPPORT" for p in c.pts)
    for i, c in enumerate(comps):
        if c.drop or c.rtype != "PIPE" or len(c.pts) != 2:
            continue
        a, b = c.pts
        # only the stray copy has a dangling end; the real run is connected at both ends
        dangling = deg[tuple(round(v, 3) for v in a)] == 1 or deg[tuple(round(v, 3) for v in b)] == 1
        if dangling and on_other(a, i) and on_other(b, i) and on_other(lerp(a, b, 0.5), i):
            c.drop = True
            segs = [sg for sg in segs if sg[0] != i]
            dropped.append(dict(at_ft=[round(v / 12, 2) for v in a], length_in=round(dist(a, b), 2), nps=c.bores[0]))
    report["duplicate_pipes_dropped"] = dropped


def drop_fragments(comps: List[Comp], box: Optional[dict], max_comps: int, report: dict) -> None:
    """Remove small disconnected pieces cut by the model box (and lone single parts)."""
    uf = UF()
    nodes = node_table(comps)
    keys = list(nodes)
    idx = {k: i for i, k in enumerate(keys)}
    for ci, c in enumerate(comps):
        if c.drop or c.rtype == "SUPPORT":
            continue
        ks = [idx[tuple(round(v, 3) for v in p)] for p in c.pts]
        for k in ks[1:]:
            uf.union(ks[0], k)
    members: Dict[int, set] = defaultdict(set)
    for k, refs in nodes.items():
        for ci, _ in refs:
            members[uf.find(idx[k])].add(ci)
    edge = 6.0  # in
    dropped = []
    for root, cis in members.items():
        if len(cis) > max_comps:
            continue
        pts = [p for ci in cis for p in comps[ci].pts]
        touches = box is not None and any(
            min(abs(p[0] / 12 - box.get("xmin", -1e9)), abs(p[0] / 12 - box.get("xmax", 1e9)),
                abs(p[1] / 12 - box.get("ymin", -1e9)), abs(p[1] / 12 - box.get("ymax", 1e9))) * 12 < edge + 24
            for p in pts)
        span = max((dist(p, q) for p in pts for q in pts), default=0.0)
        if touches or len(cis) == 1 or span < 24.0:     # < 2 ft isolated pieces: slab sleeves, stray stubs
            for ci in cis:
                comps[ci].drop = True
            dropped.append(dict(components=len(cis), types=dict(Counter(comps[ci].rtype for ci in cis)),
                                at_ft=[round(v / 12, 1) for v in pts[0]]))
    report["fragments_dropped"] = dropped


# --------------------------------------------------------------------------- supports
def load_supports(path: Path, box: Optional[dict], sys_re: str, cls_ok: Sequence[str]) -> List[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("x_ft") in ("", None) or r.get("cls") not in cls_ok:
                continue
            if r.get("system") and not re.search(sys_re, r["system"], re.I):
                continue                      # tagged to another system (VRF, domestic ...)
            p = (float(r["x_ft"]) * 12, float(r["y_ft"]) * 12, float(r["z_ft"]) * 12)
            if not in_box(p, box):
                continue
            r["_p"] = p
            rows.append(r)
    return rows


def pipe_axis(a: Vec, b: Vec) -> Optional[str]:
    d = sub(b, a)
    L = math.sqrt(dot(d, d))
    if L < 1e-6:
        return None
    u = tuple(abs(v) / L for v in d)
    if u[2] > 0.999:
        return "V"
    if u[2] < 0.01:
        return "H"
    return "S"   # sloped


def candidates(sp: dict, comps: List[Comp], rules: dict) -> List[Tuple[int, float, Vec, float]]:
    """(comp idx, station t, foot point, score) of pipes this support carries."""
    p = sp["_p"]
    cls = sp["cls"]
    r = dict(rules[cls])
    for fam_key, ov in rules.get("_family_overrides", {}).items():
        if fam_key.lower() in sp.get("family", "").lower():
            r.update(ov)
    out = []
    for ci, c in enumerate(comps):
        if c.drop or c.rtype != "PIPE" or len(c.pts) != 2:
            continue
        if r.get("system_tag_must_match") and sp.get("system") and c.system and \
                not re.search(r["system_tag_must_match"].get(c.system, "^$"), sp["system"], re.I):
            continue
        a, b = c.pts
        ax = pipe_axis(a, b)
        if ax is None:
            continue
        if cls == "RISER" and ax != "V":
            continue
        if cls != "RISER" and ax == "V":
            continue
        d = sub(b, a)
        L2 = dot(d, d)
        t = dot(sub(p, a), d) / L2
        if t < -1e-6 or t > 1 + 1e-6:
            continue
        t = min(1.0, max(0.0, t))
        foot = lerp(a, b, t)
        dh = math.hypot(foot[0] - p[0], foot[1] - p[1])
        dz = foot[2] - p[2]                    # +ve: pipe above support point
        if cls == "RISER":
            if dh <= r["max_horiz_in"]:
                foot = (foot[0], foot[1], p[2])
                tt = (p[2] - a[2]) / (b[2] - a[2])
                if 0.0 <= tt <= 1.0:
                    out.append((ci, tt, lerp(a, b, tt), dh))
            continue
        if dh <= r["max_horiz_in"] and r["min_dz_in"] <= dz <= r["max_dz_in"]:
            out.append((ci, t, foot, math.hypot(dh, dz)))
    out.sort(key=lambda x: x[3])
    if not out and r.get("node_fallback", True):
        # support sits at a fitting (elbow, tee, valve, flange): use the nearest node
        best = None
        for ci, c in enumerate(comps):
            if c.drop or c.rtype == "SUPPORT":
                continue
            for q in c.pts:
                dh = math.hypot(q[0] - p[0], q[1] - p[1])
                dz = q[2] - p[2]
                if dh <= r["max_horiz_in"] and r["min_dz_in"] <= dz <= r["max_dz_in"]:
                    s = math.hypot(dh, dz)
                    if best is None or s < best[3]:
                        best = (-1, 0.0, q, s, ci)
        return [best[:4]] if best else []
    if not out:
        return out
    if not r.get("multi_pipe"):
        return out[:1]
    # trapezes / shared stands: keep pipes parallel to the nearest one
    ref = comps[out[0][0]]
    rdir = sub(ref.pts[1], ref.pts[0])
    rn = math.sqrt(dot(rdir, rdir))
    keep = []
    lvl = float(r.get("same_level_in", 3.0))
    z_ref = out[0][2][2]
    for o in out:
        c = comps[o[0]]
        d = sub(c.pts[1], c.pts[0])
        # same tier: parallel to the nearest pipe and bottom-of-pipe within lvl of it
        bop_ref = z_ref - comps[out[0][0]].bores[0] / 2
        bop = o[2][2] - c.bores[0] / 2
        if abs(dot(d, rdir)) / (math.sqrt(dot(d, d)) * rn) > 0.995 and abs(bop - bop_ref) <= lvl:
            keep.append(o)
    return keep[: r.get("max_pipes", 6)]


def split_pipe(comps: List[Comp], ci: int, foot: Vec, min_seg: float) -> Vec:
    """Split PIPE ci at foot; return the node used (may be an existing end)."""
    c = comps[ci]
    a, b = c.pts
    if dist(a, foot) < min_seg:
        return a
    if dist(b, foot) < min_seg:
        return b
    new = Comp(rtype="PIPE", lines=list(c.lines), src=c.src, system=c.system, pts=[foot, b],
               bores=list(c.bores), tails=list(c.tails), desc=c.desc, skey=c.skey, weight=None)
    c.pts = [a, foot]
    comps.append(new)
    return foot


def place_supports(comps: List[Comp], sups: List[dict], rules: dict, min_seg: float,
                   report: dict) -> List[Comp]:
    placed: List[Comp] = []
    log_rows = []
    used: List[Tuple[Vec, str]] = []
    unassigned = Counter()
    merged = Counter()
    for sp in sups:
        hits = candidates(sp, comps, rules)
        if not hits:
            unassigned[f"{sp['cls']}: {sp['family']}"] += 1
            log_rows.append(dict(guid=sp.get("guid", ""), cls=sp["cls"], family=sp["family"],
                                 x_ft=sp["x_ft"], y_ft=sp["y_ft"], z_ft=sp["z_ft"], status="UNASSIGNED",
                                 pipe_nps="", node_x_in="", node_y_in="", node_z_in="", snap_in=""))
            continue
        for ci, t, foot, score in hits:
            if any(dist(foot, u) < 1.0 for u, _ in used):
                continue                      # duplicate support at same node
            # Two BIM supports a few inches apart on the same straight line are one physical
            # support modelled twice (typ. two stand families side by side).
            # Keeping both creates a sub-6" pipe between two V-stops; in one job such a pair at an
            # elbow tangent crashed PCFin.exe (0xc0000409).  First support wins.
            msp = float(rules.get("_min_support_spacing_in", 12.0))
            twin = next((u for u, _ in used if dist(foot, u) < msp and
                         sum(abs(foot[k] - u[k]) > 0.5 for k in range(3)) <= 1), None)
            if twin is not None:
                merged[f"{sp['cls']}: {sp['family']}"] += 1
                log_rows.append(dict(guid=sp.get("guid", ""), cls=sp["cls"], family=sp["family"],
                                     x_ft=sp["x_ft"], y_ft=sp["y_ft"], z_ft=sp["z_ft"],
                                     status=f"MERGED (within {msp:g} in of support at "
                                            f"{twin[0]:.2f},{twin[1]:.2f},{twin[2]:.2f})",
                                     pipe_nps="", node_x_in=round(foot[0], 3), node_y_in=round(foot[1], 3),
                                     node_z_in=round(foot[2], 3), snap_in=round(score, 2)))
                continue
            if ci >= 0:
                node = split_pipe(comps, ci, foot, min_seg)
                bore = comps[ci].bores[0] if comps[ci].bores else 0.0
            else:
                node = foot
                bore = max((c.bores[0] for c in comps if not c.drop and c.pts and
                            any(dist(q, node) < 1e-3 for q in c.pts)), default=0.0)
            used.append((node, sp["cls"]))
            pref = rules[sp['cls']].get('tag_prefix', sp['cls'][:3])
            for fk, ov in rules.get("_family_overrides", {}).items():
                if fk.lower() in sp.get("family", "").lower() and ov.get("tag_prefix"):
                    pref = ov["tag_prefix"]
            tag = f"{pref}-{(sp.get('guid') or 'X')[-6:]}"
            n_same = sum(1 for c in placed if c.desc == sp["family"] and f"NAME {tag}" in c.lines[2])
            if n_same:                        # one stand / trapeze carrying several pipes
                tag = f"{tag}-{chr(65 + n_same)}"
            s = Comp(rtype="SUPPORT", lines=["__CO__", f"    SKEY {SUPPORT_SKEY[sp['cls']]}",
                                              f"    NAME {tag}",
                                              f"    ITEM-DESCRIPTION {sp['cls']} {sp['family']}"],
                     src="supports", co=node, bores=[bore], desc=sp["family"])
            placed.append(s)
            log_rows.append(dict(guid=sp.get("guid", ""), cls=sp["cls"], family=sp["family"],
                                 x_ft=sp["x_ft"], y_ft=sp["y_ft"], z_ft=sp["z_ft"], status="PLACED",
                                 pipe_nps=bore, node_x_in=round(node[0], 3), node_y_in=round(node[1], 3),
                                 node_z_in=round(node[2], 3), snap_in=round(score, 2)))
    report["supports"] = dict(input=len(sups), placed=len(placed),
                              by_class=dict(Counter(r["cls"] for r in log_rows if r["status"] == "PLACED")),
                              unassigned=dict(unassigned), merged_twins=dict(merged))
    report["_support_rows"] = log_rows
    return placed


# --------------------------------------------------------------------------- infill supports
def straight_runs(comps: List[Comp], join_gap_in: float = 0.05):
    """Group straight horizontal in-line components into continuous runs along one line.
    Returns list of (axis_index, line_key, [ (s0, s1, comp_idx) ...] sorted, merged intervals)."""
    lines: Dict[tuple, List[Tuple[float, float, int]]] = defaultdict(list)
    for ci, c in enumerate(comps):
        if c.drop or c.rtype in ("SUPPORT", "ELBOW", "BEND", "TEE") or len(c.pts) != 2:
            continue
        a, b = c.pts
        d = sub(b, a)
        L = math.sqrt(dot(d, d))
        if L < 1e-3 or abs(d[2]) > 1e-3 * L:
            continue                                   # vertical / sloped: not infilled
        ax = 0 if abs(d[0]) > abs(d[1]) else 1
        if abs(d[1 - ax]) > 1e-3 * L:
            continue                                   # skewed in plan
        key = (ax, round(a[1 - ax], 1), round(a[2], 1))
        s0, s1 = sorted((a[ax], b[ax]))
        lines[key].append((s0, s1, ci))
    runs = []
    for key, segs in lines.items():
        segs.sort()
        cur = [segs[0]]
        for sg in segs[1:]:
            if sg[0] <= cur[-1][1] + join_gap_in:          # join across tee bodies on the same line
                cur.append(sg)
            else:
                runs.append((key, cur))
                cur = [sg]
        runs.append((key, cur))
    return runs


def infill_supports(comps: List[Comp], cfg: dict, report: dict) -> None:
    """Add resting supports on long horizontal stretches the BIM left unsupported.
    The spacing comes from the model's own BIM support layout (median spacing per NPS on runs
    with 3+ BIM supports), so it reflects the project's installed practice, capped by cfg."""
    sup = [c for c in comps if not c.drop and c.rtype == "SUPPORT" and c.co is not None]
    runs = straight_runs(comps, float(cfg.get("join_across_fittings_in", 0.05)))

    def stations(key, run):
        ax, _, _ = key
        out = []
        for sp in sup:
            p = sp.co
            if abs(p[2] - key[2]) < 0.2 and abs(p[1 - ax] - key[1]) < 0.2 and run[0][0] - 0.1 <= p[ax] <= run[-1][1] + 0.1:
                out.append(p[ax])
        return sorted(out)

    hang_z = float(cfg.get("hang_above_ft", 1e9)) * 12      # above this CL elevation a run is overhead (hung)

    def tier(key):
        return "overhead" if key[2] > hang_z else "floor"

    spacing: Dict[Tuple[float, str], List[float]] = defaultdict(list)
    for key, run in runs:
        st = stations(key, run)
        if len(st) >= 3:
            bore = comps[run[0][2]].bores[0]
            spacing[(bore, tier(key))] += [b - a for a, b in zip(st, st[1:]) if b - a > 12.0]
    med = {k: sorted(v)[len(v) // 2] for k, v in spacing.items() if v}
    cap = {float(k): float(v) * 12 for k, v in cfg.get("max_span_ft_by_nps", {}).items()}
    targets = []                                   # (point, bore, span) - placed after planning
    for key, run in runs:
        bore = comps[run[0][2]].bores[0]
        span = med.get((bore, tier(key))) or cap.get(bore)
        if bore in cap:
            span = min(span, cap[bore]) if span else cap[bore]
        if not span:
            continue
        ax = key[0]
        st = stations(key, run)
        pts = sorted(set([run[0][0]] + st + [run[-1][1]])) if cfg.get("count_run_ends", True) else sorted(st)
        for a_, b_ in zip(pts, pts[1:]):
            gap = b_ - a_
            if gap <= span * float(cfg.get("trigger_factor", 1.25)):
                continue
            n = int(math.ceil(gap / span)) - 1
            for k in range(1, n + 1):
                st_k = a_ + gap * k / (n + 1)
                host = next((ci for s0, s1, ci in run if s0 + 1 <= st_k <= s1 - 1 and comps[ci].rtype == "PIPE"), None)
                if host is None:
                    continue                   # station falls on a valve / flange / strainer: skip
                a, b = comps[host].pts
                t = (st_k - a[ax]) / (b[ax] - a[ax])
                targets.append((lerp(a, b, t), bore, span, tier(key)))
    added = []
    for p_, bore, span, tr in targets:
        host = None
        for ci, c in enumerate(comps):          # re-find the host: earlier splits may have moved it
            if c.drop or c.rtype != "PIPE" or len(c.pts) != 2:
                continue
            a, b = c.pts
            d = sub(b, a)
            L2 = dot(d, d)
            t = dot(sub(p_, a), d) / L2 if L2 else -1
            if 0 <= t <= 1 and dist(lerp(a, b, t), p_) < 0.01:
                host = ci
                break
        if host is None:
            continue
        sysn = comps[host].system
        node = split_pipe(comps, host, p_, 1.0)
        tag = f"INF-{sysn or 'X'}-{len(added) + 1:03d}"
        skey = "HANG" if tr == "overhead" else cfg.get("skey", "SKID")
        comps.append(Comp(rtype="SUPPORT", lines=["__CO__", f"    SKEY {skey}", f"    NAME {tag}",
                                                  f"    ITEM-DESCRIPTION INFILL {'HANGER' if skey == 'HANG' else 'REST'} VERIFY"],
                          src="infill", co=node, bores=[bore], desc="infill"))
        added.append(dict(name=tag, nps=bore, tier=tr, skey=skey, span_used_ft=round(span / 12, 1), x_ft=round(node[0] / 12, 2),
                          y_ft=round(node[1] / 12, 2), z_ft=round(node[2] / 12, 2)))
    report["infill_supports"] = dict(count=len(added), bim_median_spacing_ft={f"{k[0]:g} {k[1]}": round(v / 12, 1) for k, v in med.items()},
                                     cap_ft=cfg.get("max_span_ft_by_nps", {}))
    report["_infill"] = added


# --------------------------------------------------------------------------- output
def fmt(p: Vec) -> str:
    return f"{p[0]:.4f}  {p[1]:.4f}  {p[2]:.4f}"


SKEY_OVERRIDE: Dict[str, str] = {}
SUPPORT_DESC_MAX = 32


def write_pcf(path: Path, header: List[str], pipeline: str, comps: List[Comp], scale_out: float) -> None:
    out: List[str] = []
    for h in header:
        if h.split()[0] in ("ISOGEN-FILES",) or h.startswith("UNITS"):
            out.append(h)
    if not any(l.startswith("UNITS-CO-ORDS") for l in out):
        out = ["ISOGEN-FILES ISOGEN.FLS", "UNITS-BORE INCH", "UNITS-CO-ORDS INCH", "UNITS-WEIGHT LBS"]
    out.append(f"PIPELINE-REFERENCE {pipeline}")
    for c in comps:
        if c.drop:
            continue
        out.append(c.rtype)
        pi = 0
        for ln in c.lines:
            if ln.startswith("__END-POINT__") or ln.startswith("__BRANCH1-POINT__"):
                key = "END-POINT" if ln.startswith("__END") else "BRANCH1-POINT"
                p = tuple(v / scale_out for v in c.pts[pi])
                tail = f"  {c.tails[pi]}" if c.tails[pi] else ""
                out.append(f"    {key}  {fmt(p)}  {c.bores[pi]:.4f}{tail}")
                pi += 1
            elif ln == "__CENTRE__":
                out.append(f"    CENTRE-POINT  {fmt(tuple(v / scale_out for v in c.centre))}")
            elif ln == "__CO__":
                b = f"  {c.bores[0]:.4f}" if c.rtype == "SUPPORT" and c.bores else ""
                out.append(f"    CO-ORDS  {fmt(tuple(v / scale_out for v in c.co))}{b}")
            else:
                if c.rtype == "SUPPORT" and ln.strip().startswith("SKEY "):
                    k = ln.split()[1]
                    ln = f"    SKEY {SKEY_OVERRIDE.get(k, k)}"
                if c.rtype == "SUPPORT" and ln.strip().startswith("ITEM-DESCRIPTION "):
                    # keep SUPPORT descriptions short (translator log width). NB the PCFin.exe
                    # 0xc0000409 crash was two supports 5in apart at an elbow - see place_supports
                    txt = ln.strip()[len("ITEM-DESCRIPTION "):]
                    ln = f"    ITEM-DESCRIPTION {txt[:SUPPORT_DESC_MAX]}"
                out.append(ln if ln.startswith(" ") else f"    {ln}")
    path.write_bytes(("\r\n".join(out) + "\r\n").encode("latin-1", "replace"))


def connectivity(comps: List[Comp]) -> dict:
    uf = UF()
    key = {}
    deg = Counter()
    linked = set()

    def nid(p: Vec) -> int:
        k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
        if k not in key:
            key[k] = len(key)
        return key[k]

    for c in comps:
        if c.drop or c.rtype == "SUPPORT":
            continue
        ids = [nid(p) for p in c.pts]
        for i in ids:
            deg[i] += 1
        for i in ids[1:]:
            uf.union(ids[0], i)
        for a in ids:
            for b in ids:
                if a < b:
                    linked.add((a, b))                 # two ends of one component: short part, not a gap
    roots = Counter(uf.find(i) for i in deg)
    near_miss = 0
    pts = list(key.keys())
    g = Grid(0.5)
    for i, p in enumerate(pts):
        g.add(i, p)
    for i, p in enumerate(pts):
        for j in g.near(p):
            if j > i and (i, j) not in linked and 1e-3 < math.dist(p, pts[j]) < 0.25:
                near_miss += 1
    return dict(nodes=len(key), networks=len(roots), free_ends=sum(1 for v in deg.values() if v == 1),
                largest_network_nodes=max(roots.values()) if roots else 0, near_miss_pairs=near_miss)


# --------------------------------------------------------------------------- main
def run(job_path: Path) -> int:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    base = job_path.parent
    out_dir = (base / job["output_dir"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"job": job.get("name"), "ASSUMED": job.get("assumed", []),
                    "_weld_re": job.get("weld_match", r"Shop Weld"),
                    "_fuse_rtypes": tuple(job.get("fuse_rtypes", ["COUPLING"]))}
    files: List[Path] = []
    for g in job["pcf_globs"]:
        files += [Path(p) for p in sorted(glob.glob(str((base / g) if not Path(g).is_absolute() else g)))]
    files = [f for f in dict.fromkeys(files)]
    if not files:
        LOG.error("no PCF files matched %s", job["pcf_globs"])
        return 1
    header: List[str] = []
    comps: List[Comp] = []
    dropped = Counter()
    for f in files:
        txt = f.read_text(encoding="latin-1", errors="replace")
        m = re.search(r"UNITS-CO-ORDS\s+(\w+)", txt)
        unit = (m.group(1).upper() if m else "INCH")
        scale = 1.0 if unit.startswith("INCH") else 1 / 25.4
        h, cs = parse_pcf(f, scale)
        header = header or h
        for c in cs:
            if c.rtype in DROP_TYPES:
                dropped[c.rtype] += 1
                continue
            comps.append(c)
        LOG.info("read %-70s %5d records (%s)", f.name[:70], len(cs), unit)
    report["files"] = [f.name for f in files]
    report["continuation_records_dropped"] = dict(dropped)

    box = job.get("box_ft")
    before = len(comps)
    mode = job.get("clip_mode", "any")
    kept = []
    for c in comps:
        pts = c.pts or ([c.co] if c.co else [])
        inside = [in_box(p, box) for p in pts]
        if (any(inside) if mode == "any" else all(inside)):
            kept.append(c)
    comps = kept
    report["clip"] = dict(box_ft=box, mode=mode, before=before, after=len(comps))
    LOG.info("clip: %d -> %d components", before, len(comps))

    retyped = Counter()
    for rule in job.get("retype", []):
        for c in comps:
            if c.drop or c.rtype != rule["from"] or not re.search(rule["match"], c.desc, re.I):
                continue
            c.rtype = rule["to"]
            if rule.get("skey"):
                c.skey = rule["skey"]
                c.set_attr("SKEY", rule["skey"])
            if rule["to"] in ("VALVE", "PIPE"):
                # a 2-point VALVE/PIPE carries no CENTRE-POINT; Revit's MISC one is off-axis
                c.lines = [ln for ln in c.lines if ln != "__CENTRE__"]
                c.centre = None
            if rule["to"] == "PIPE":
                c.lines = [ln for ln in c.lines if not ln.strip().startswith(("SKEY", "WEIGHT"))]
                c.skey, c.weight = "", None
            retyped[f'{rule["from"]}->{rule["to"]} {c.desc}'] += 1
    report["retyped"] = dict(retyped)
    pre = connectivity(comps)
    report["connectivity_before"] = pre
    heal(comps, float(job.get("heal_tol_in", 0.25)), report)
    fix_flanges(comps, job.get("flange_map", []), report)
    drop_duplicate_pipes(comps, report)
    fix_overlapping_valves(comps, report)
    align_offset_valves(comps, report)
    straighten_inline(comps, report, float(job.get("straighten_max_dev_in", 0.25)))
    elbow_rows: List[dict] = []
    if job.get("normalize_elbows", True):
        normalize_elbows(comps, report, float(job.get("elbow_margin_in", 0.0625)))
        elbow_rows = report.pop("_elbow_rows")
    bridges: List[dict] = []
    if job.get("bridge"):
        items: List[dict] = []
        if job.get("nwc_items_csv"):
            with (base / job["nwc_items_csv"]).resolve().open(encoding="utf-8") as f:
                items = [r for r in csv.DictReader(f) if in_box((float(r["x_ft"]) * 12, float(r["y_ft"]) * 12,
                                                                   float(r["z_ft"]) * 12), box)]
        bridge_cfg = dict(job["bridge"])
        bridge_cfg.setdefault("not_inline_extra_regex", job.get("not_inline_extra_regex", ""))
        bridge_gaps(comps, bridge_cfg, items, report)
        bridges = report.pop("_bridges")
        if items and job.get("pcf_pipe_match"):
            # NWC pipe the PCF export skipped: named like the project's pipe family prefix but not
            # like anything the PCF carries (pcf_pipe_match is the regex the PCF pipe names match).
            pfx = job.get("nwc_pipe_name_prefix", "Pipe-")
            other = Counter(f"{r['name'][:34]} | {r['system'][:40]}" for r in items
                            if r["name"].startswith(pfx) and re.search(job.get("support_system_match", ".*"), r["system"])
                            and not re.search(job["pcf_pipe_match"], r["name"]))
            if other:
                report["nwc_pipe_not_in_pcf"] = dict(other)
    if job.get("three_way"):
        tw_cfg = dict(job["three_way"])
        tw_cfg.setdefault("schedule", job.get("desc_schedule_tag") or "STD")
        attach_three_way(comps, tw_cfg, report)
    if bridges:
        rep2: dict = {}
        straighten_inline(comps, rep2, float(job.get("straighten_max_dev_in", 0.25)))
        report["straightened_joints_after_bridge"] = rep2["straightened_joints"]
    if job.get("drop_fragments_max_components"):
        drop_fragments(comps, box, int(job["drop_fragments_max_components"]), report)
    set_valve_weights(comps, job.get("valve_weights", []), report)
    set_attributes(comps, job.get("systems", []), report)

    sched = job.get("desc_schedule_tag")
    if sched:
        # PCF Translator takes the AutoPIPE schedule from ITEM-DESCRIPTION; a record without a
        # schedule token (nipples, flanges/fittings that start a segment) defaults to STD and the
        # following fittings inherit it. Tag every such record with the line schedule.
        ntag = 0
        for c in comps:
            if c.drop or c.rtype == "SUPPORT" or re.search(r"SCH", c.desc, re.I):
                continue
            c.desc = f"{c.desc} - {sched}"
            for i, ln in enumerate(c.lines):
                if ln.strip().startswith("ITEM-DESCRIPTION"):
                    c.lines[i] = f"{ln.rstrip()} - {sched}"
                    break
            else:
                c.lines.append(f"    ITEM-DESCRIPTION {c.desc}")
            ntag += 1
        report["schedule_tagged_descriptions"] = dict(tag=sched, count=ntag)
    sup_rows: List[dict] = []
    if job.get("supports_csv"):
        sp_path = (base / job["supports_csv"]).resolve()
        rules = job["support_rules"]
        sups = load_supports(sp_path, box, job.get("support_system_match", ".*"),
                             [k for k in rules if not k.startswith("_")])
        placed = place_supports(comps, sups, rules, float(job.get("min_segment_in", 1.0)), report)
        comps.extend(placed)
        sup_rows = report.pop("_support_rows")
    inf_rows: List[dict] = []
    if job.get("infill"):
        infill_supports(comps, job["infill"], report)
        inf_rows = report.pop("_infill")
    bnd_rows: List[dict] = []
    if job.get("boundary_rules"):
        bnd_rows = boundary_conditions(comps, job["boundary_rules"], box, report)
    post = connectivity(comps)
    report["connectivity_after"] = post
    report.pop("_weld_re", None)
    report.pop("_fuse_rtypes", None)

    global SUPPORT_DESC_MAX
    SUPPORT_DESC_MAX = int(job.get("support_desc_max", 32))
    SKEY_OVERRIDE.clear()
    SKEY_OVERRIDE.update(job.get("support_skey_override", {}))
    stem = job.get("output_stem", "model")
    pcf_out = out_dir / f"{stem}.pcf"
    write_pcf(pcf_out, header, job.get("pipeline_reference", stem), comps, 1.0)
    if sup_rows:
        with (out_dir / f"{stem}_supports.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(sup_rows[0].keys()))
            w.writeheader()
            w.writerows(sup_rows)
    if inf_rows:
        with (out_dir / f"{stem}_infill_supports.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(inf_rows[0].keys()))
            w.writeheader()
            w.writerows(inf_rows)
    if bnd_rows:
        with (out_dir / f"{stem}_free_ends.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(bnd_rows[0].keys()))
            w.writeheader()
            w.writerows(bnd_rows)
    if elbow_rows:
        with (out_dir / f"{stem}_elbows_normalized.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(elbow_rows[0].keys()))
            w.writeheader()
            w.writerows(elbow_rows)
    if bridges:
        with (out_dir / f"{stem}_bridged_items.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(bridges[0].keys()))
            w.writeheader()
            w.writerows(bridges)
    counts = Counter(c.rtype for c in comps if not c.drop)
    report["output"] = dict(pcf=pcf_out.name, records=dict(counts))
    (out_dir / f"{stem}_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")

    warn = []
    if report.get("valve_weights_MISSING"):
        warn.append(f"{sum(report['valve_weights_MISSING'].values())} valves have no weight - fill valve_weights")
    if post["near_miss_pairs"]:
        warn.append(f"{post['near_miss_pairs']} near-miss node pairs remain")
    if report.get("supports", {}).get("unassigned"):
        warn.append(f"{sum(report['supports']['unassigned'].values())} supports not assigned to a pipe")
    if report.get("bridged_gaps", {}).get("weights_missing"):
        warn.append(f"{report['bridged_gaps']['weights_missing']} bridged in-line items have no weight")
    if report.get("boundaries", {}).get("UNCLASSIFIED -> FREE"):
        warn.append(f"{report['boundaries']['UNCLASSIFIED -> FREE']} free ends not matched by a boundary rule")
    exp = job.get("expected_collapse_match", "$^")
    odd = {k: v for k, v in report["heal"]["collapsed_components"].items() if not re.search(exp, k, re.I)}
    if odd:
        warn.append(f"{sum(odd.values())} unexpected components collapsed to zero length: {odd}")
    LOG.info("connectivity before: %s", pre)
    LOG.info("connectivity after : %s", post)
    for wmsg in warn:
        LOG.warning(wmsg)
    LOG.info("wrote %s", pcf_out)
    return 2 if warn else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", type=Path)
    ap.add_argument("--log", type=Path)
    a = ap.parse_args(argv)
    handlers = [logging.StreamHandler(sys.stdout)]
    if a.log:
        handlers.append(logging.FileHandler(a.log, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    try:
        return run(a.job)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as e:
        LOG.exception("failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
