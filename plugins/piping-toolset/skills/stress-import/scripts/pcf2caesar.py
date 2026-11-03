#!/usr/bin/env python3
"""pcf2caesar.py - Revit/PipeEX PCF exports -> CAESAR II-ready PCFs with supports.

Stdlib only. Python 3.9+. Run:  python -I pcf2caesar.py job.json
Helper modules beside it: pcflib.py, pcf_union.py, pcf_split.py, pcf_graph.py. Optional diagnostic:
pcf_pieces.py OUT.pcf lists the connected pieces of an output file with their supports.

What it does (each step is logged in the report):
  1. Load the Revit system PCFs named in the job ("pcf_files"), de-duplicate elements exported
     in more than one file (same REVIT-ID + type + end points), keep only what lies inside the
     job's model box ("box_ft").
  2. Remove equipment-body records (UNDEFINED records whose first bore equals
     "chiller_body_bore_in", e.g. a 4-port chiller body) and record their ports as equipment
     nozzles; split the network into the job's models ("models") by connectivity.
  3. Drop small bore (<= small_bore_max), drop WELD / END-* records, ELBOW -> BEND (radius from
     geometry), COUPLING -> PIPE, placeholder SKEYs -> CAESAR-proven SKEYs.
  4. Assign each element to a line ("lines") from its Revit file, propagating shared ones.
  5. Classify open ends: equipment-body port, equipment (END-CONNECTION-EQUIPMENT), box cut,
     job overrides ("end_overrides"), else free end.
  6. Place supports by rule: anchors at equipment and cuts, a support at every bend on its
     horizontal side, base supports at the first low bend from each equipment nozzle, riser
     supports at floor crossings, span fill to the job's span table ("span_table_ft", taken from
     the project specification).
  7. Split pipes at support points so every support sits on a node.
  8. Emit one PCF per line plus a combined PCF, walk-ordered (main run first, branches after) so
     CAESAR II numbers nodes in sequence. CRLF, INCH.
Geometry is never moved: splits add nodes on the existing centreline only.

Record types converted: PIPE, COUPLING (as PIPE), ELBOW/BEND, TEE, REDUCER-CONCENTRIC, VALVE (Revit
writes flanges as COUPLING). Any other record with end points is listed under the report's errors
(exit 2). Records without end points, such as SUPPORT, are skipped with a warning: the script
places its own supports.

Outputs, in the job's outdir: NAME_<line>.pcf per line, NAME_combined.pcf, NAME_supports.csv (every
support with its basis; all are ASSUMED rule placements to be verified), NAME_report.json and
NAME.log.

Exit codes: 0 done, 2 done but the report lists errors (unhandled record types, supports dropped
off-node ...), 1 the job or an input file could not be read (bad key, missing file), 2 also for a
usage error.

Job JSON (paths relative to the job file; unknown keys such as "_comment" are ignored).
Project-specific values are job keys; the span table and the distances come from the project
specification, never from this script.
  name                  output stem and log name (default "job")
  outdir        (req.)  output folder, created if missing
  model         (req.)  which of "models" to build (optional when there is one model)
  pcf_dir               folder of the PCF files (default: the job's folder)
  pcf_files     (req.)  {tag: file name} one Revit PCF per tag; tags are used by "models"/"lines"
  box_ft                [xmin, xmax, ymin, ymax] or {xmin,xmax,ymin,ymax,zmin,zmax}, ft, plant
                        coordinates; records outside are dropped, records crossing it are cut
                        ends (default: no box)
  models                {model name: [tags]}: connected pieces are given to the model whose tags
                        exclusively own most of their elements (default: one model of all tags)
  unassigned_by_bore    {"max_bore_in": n, "le": model, "gt": model} for pieces that no tag owns
                        (default: the first model)
  lines         (req.)  {line: {"files": [tags], "pcf_attributes": {PCF attribute: value}}}
  small_bore_max        drop records at or below this bore, in (default 2.0)
  chiller_body_bore_in  first bore of UNDEFINED equipment-body records to remove (default: none)
  chiller_tag_prefix    tag prefix for those bodies (default "EQ")
  chiller_port_lines    {"END1": line, "BRANCH1-POINT": line} line of each body port
  end_overrides         [{xyz_ft: [x,y,z], kind: EQUIP|CUT|FREE, tag, basis}] classify an open end
  equipment_ff_ft       [floor elevations, ft] used to find a nozzle's floor (default none)
  base_bend_max_above_ff_ft (6), base_walk_max_ft (15), near_support_max_ft (5), near_nozzle_in (24)
                        base-support rule: first low bend from each equipment nozzle, else a
                        support on the first straight pipe near_nozzle_in off the nozzle
  riser_floors_ft       floor elevations that get a riser support
  riser_clamp_above_floor_ft  height of that support above the floor, ft (default 1.0)
  riser_max_ft          longest unsupported vertical run, ft (default 14)
  span_table_ft (req.)  [[max NPS, span ft], ...] ascending NPS; the example values are placeholders
  merge_in              supports closer than this on one pipe are merged (default 18)
  tee_carry_ratio (0.5), near_tee_in (18)   branch-near-header rule
  no_support_below_ft   drop non-anchor supports below this elevation, ft (buried pipe)
  support_prefix        support NAME prefix, NAME <prefix>-<TYPE>_<model><nnn> (default "PTS")
  project_identifier    PROJECT-IDENTIFIER written to each PCF (default: not written)
  area                  AREA written to each PCF (default: not written)
"""
import sys, os, json, math, collections, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcflib
from pcf_split import split_models
from pcf_graph import components

log = logging.getLogger('pcf2caesar')
Q = 0.0625                                   # node merge grid, in

def K(p):
    return pcflib.key(p, Q)

def sub(a, b): return tuple(a[i] - b[i] for i in range(3))
def addv(a, b, k=1.0): return tuple(a[i] + k * b[i] for i in range(3))
def norm(v): return math.sqrt(sum(c * c for c in v))
def unit(v):
    n = norm(v)
    return tuple(c / n for c in v) if n > 0 else (0.0, 0.0, 0.0)
def dot(a, b): return sum(a[i] * b[i] for i in range(3))

def is_vertical(d, tol=0.05): return abs(unit(d)[2]) > 1 - tol
def is_horizontal(d, tol=0.05): return abs(unit(d)[2]) < tol

def span_ft(nps, table):
    for row in table:
        if nps <= row[0] + 1e-6:
            return row[1]
    return table[-1][1]

# --------------------------------------------------------------------------------------------
class Comp:
    """One component in output form."""
    _n = 0
    def __init__(self, typ, pts, bore, src=None, **kw):
        Comp._n += 1
        self.id = Comp._n
        self.typ = typ            # PIPE BEND TEE REDUCER-CONCENTRIC VALVE
        self.pts = dict(pts)      # END1 END2 [CENTRE] [BRANCH]
        self.bore = dict(bore)
        self.src = src            # source element dict
        self.line = None
        self.kw = kw              # radius, angle, skey, weight, desc
    def ends(self):
        out = [self.pts['END1'], self.pts['END2']]
        if 'BRANCH' in self.pts:
            out.append(self.pts['BRANCH'])
        return out
    def segments(self):
        """straight segments (p, q, role) used for runs and supports."""
        if self.typ == 'BEND':
            return [(self.pts['END1'], self.pts['CENTRE'], 'bendleg'),
                    (self.pts['CENTRE'], self.pts['END2'], 'bendleg')]
        if self.typ == 'TEE':
            c = self.pts['CENTRE']
            return [(self.pts['END1'], c, 'run'), (c, self.pts['END2'], 'run'),
                    (c, self.pts['BRANCH'], 'branch')]
        return [(self.pts['END1'], self.pts['END2'], self.typ.lower())]
    def maxbore(self):
        return max(self.bore.values())

# --------------------------------------------------------------------------------------------
def convert(elems, job, rep):
    """Revit element dicts -> Comp list (step 3)."""
    out, dropped = [], collections.Counter()
    sbm = job.get('small_bore_max', 2.0)
    for e in elems:
        t = e['type']
        b = e['bore']
        mb = max(b.values()) if b else 0
        if mb <= sbm:
            dropped[f'{t} <= {sbm} in'] += 1
            continue
        P = e['pts']
        if t == 'PIPE' or t == 'COUPLING':
            c = Comp('PIPE', {'END1': P['END1'], 'END2': P['END2']},
                     {'END1': b['END1'], 'END2': b['END2']}, e,
                     desc=('PIPE' if t == 'PIPE' else 'COUPLING (as PIPE)'))
            if t == 'COUPLING':
                rep['substitutions'].append(f"COUPLING RID {e['revit_id']} -> PIPE")
        elif t in ('BEND', 'ELBOW'):
            a, z, cn = P['END1'], P['END2'], P['CENTRE-POINT']
            ta, tb = norm(sub(cn, a)), norm(sub(z, cn))
            th = math.degrees(math.acos(max(-1, min(1, dot(unit(sub(cn, a)), unit(sub(z, cn)))))))
            if 'BEND-RADIUS' in e['attrs'] and e['attrs']['BEND-RADIUS'].strip():
                R = float(e['attrs']['BEND-RADIUS'])
            else:
                R = min(ta, tb) / math.tan(math.radians(th / 2))
                rep['substitutions'].append(
                    f"ELBOW RID {e['revit_id']} {b['END1']} in: no BEND-RADIUS, R={R:.3f} in from geometry -> BEND")
            if R * math.tan(math.radians(th / 2)) > min(ta, tb) + 0.01:
                rep['errors'].append(f"bend RID {e['revit_id']} tangent overlap")
            c = Comp('BEND', {'END1': a, 'END2': z, 'CENTRE': cn},
                     {'END1': b['END1'], 'END2': b['END2']}, e,
                     radius=R, angle=int(round(th * 100)), desc=f'BEND {th:.1f} deg R {R:.2f}')
        elif t == 'TEE':
            c = Comp('TEE', {'END1': P['END1'], 'END2': P['END2'], 'CENTRE': P['CENTRE-POINT'],
                             'BRANCH': P['BRANCH1-POINT']},
                     {'END1': b['END1'], 'END2': b['END2'], 'BRANCH': b['BRANCH1-POINT']}, e, desc='TEE')
            if b['BRANCH1-POINT'] <= sbm:
                rep['notes'].append(f"TEE RID {e['revit_id']}: {b['BRANCH1-POINT']} in branch dropped; branch leg kept as stub")
        elif t == 'REDUCER-CONCENTRIC':
            c = Comp('REDUCER-CONCENTRIC', {'END1': P['END1'], 'END2': P['END2']},
                     {'END1': b['END1'], 'END2': b['END2']}, e, desc='REDUCER CONC')
        elif t == 'VALVE':
            c = Comp('VALVE', {'END1': P['END1'], 'END2': P['END2']},
                     {'END1': b['END1'], 'END2': b['END2']}, e, desc='VALVE (Revit VYFL)')
            rep['assumed'].append(f"VALVE RID {e['revit_id']} {b['END1']} in: no Revit weight; weightless rigid until set from submittal")
        else:
            dropped[f'{t} (unsupported here)'] += 1
            rep['errors'].append(f"unhandled record {t} RID {e['revit_id']}")
            continue
        out.append(c)
    rep['dropped'] = dict(dropped)
    return out

# --------------------------------------------------------------------------------------------
def assign_lines(comps, job, seeds=None):
    """seeds: node key -> line (chiller ports); applied to comps whose Revit file set is ambiguous."""
    lines = job['lines']                    # {CHS: {files:[CHWS]}, ...}
    f2l = {f: ln for ln, v in lines.items() for f in v['files']}
    node_comps = collections.defaultdict(list)
    for c in comps:
        for p in c.ends():
            node_comps[K(p)].append(c)
    pending = []
    seeds = seeds or {}
    for c in comps:
        ls = {f2l[f] for f in c.src['files'] if f in f2l}
        seeded = [seeds[K(p)] for p in c.ends() if K(p) in seeds]
        if seeded:
            c.line = seeded[0]
        elif len(ls) == 1:
            c.line = ls.pop()
        else:
            pending.append(c)
    changed = True
    while pending and changed:
        changed = False
        for c in list(pending):
            votes = collections.Counter(n.line for p in c.ends() for n in node_comps[K(p)] if n.line)
            if votes:
                c.line = votes.most_common(1)[0][0]
                pending.remove(c)
                changed = True
    for c in pending:
        c.line = next(iter(lines))
    return len(pending)

# --------------------------------------------------------------------------------------------
def classify_ends(comps, chillers, ends, straddle, job):
    prefix = job.get('chiller_tag_prefix', 'EQ')
    deg = collections.Counter(K(p) for c in comps for p in c.ends())
    endrec = {K(e['pts']['CO-ORDS']): e for e in ends}
    chport = {}
    for i, u in enumerate(sorted(chillers, key=lambda u: -u['pts']['END1'][1])):
        for k, p in u['pts'].items():
            if not k.startswith('CENTRE'):
                chport[K(p)] = (f'{prefix}-{"ABCDEFGH"[i]}', k)
    cut = set()
    for e in straddle:
        for p in pcflib.conn_points(e):
            cut.add(K(p))
    over_list = [(tuple(v * 12 for v in o['xyz_ft']), o) for o in job.get('end_overrides', [])]
    def over_get(p):
        for q, o in over_list:
            if norm(sub(p, q)) < 1.0:
                return o
        return None
    pt = {K(p): p for c in comps for p in c.ends()}
    bore = {}
    for c in comps:
        for k, p in c.pts.items():
            if k in c.bore:
                bore[K(p)] = c.bore[k]
    out = []
    n_eq = 0
    for k, d in deg.items():
        if d != 1:
            continue
        p = pt[k]
        rec = {'key': k, 'xyz': p, 'bore': bore.get(k)}
        line = next(c.line for c in comps if any(K(q) == k for q in c.ends()))
        rec['line'] = line
        o = over_get(p)
        if o:
            rec.update(kind=o['kind'], tag=o['tag'], basis=o.get('basis', 'job override'))
        elif k in chport:
            rec.update(kind='EQUIP', tag=f"{chport[k][0]} port {chport[k][1]} (identity VFY)", port=chport[k][1],
                       basis='port of a removed equipment-body (UNDEFINED) record; nozzle identity ASSUMED')
        elif k in cut:
            rec.update(kind='CUT', tag='pipe cut at the model box',
                       basis='straddling pipe removed; virtual anchor ASSUMED')
        elif k in endrec and endrec[k]['type'] == 'END-CONNECTION-EQUIPMENT':
            n_eq += 1
            rec.update(kind='EQUIP', tag=f'EQ-{n_eq:02d} (identity VFY)', basis='Revit END-CONNECTION-EQUIPMENT')
        else:
            rec.update(kind='FREE', tag='open end', basis=(endrec[k]['type'] if k in endrec else 'undeclared'))
        out.append(rec)
    return out

# --------------------------------------------------------------------------------------------
class Net:
    """Graph of straight segments for run / walk logic."""
    def __init__(self, comps):
        self.comps = comps
        self.seg = []                     # (p, q, comp, role)
        self.at = collections.defaultdict(list)   # node -> [(seg idx, other end)]
        for c in comps:
            for p, q, role in c.segments():
                i = len(self.seg)
                self.seg.append((p, q, c, role))
                self.at[K(p)].append(i)
                self.at[K(q)].append(i)
        self.node_pt = {}
        for p, q, c, r in self.seg:
            self.node_pt[K(p)] = p
            self.node_pt[K(q)] = q

    def runs(self):
        """maximal collinear chains of non-bend segments. returns list of lists of (seg idx, fwd)"""
        used, runs = set(), []
        for i, (p, q, c, role) in enumerate(self.seg):
            if role == 'bendleg' or i in used:
                continue
            d = unit(sub(q, p))
            chain = [i]
            used.add(i)
            for direction in (1, -1):
                cur = i
                node = q if direction == 1 else p
                while True:
                    nxt = None
                    for j in self.at[K(node)]:
                        if j in used or self.seg[j][3] == 'bendleg':
                            continue
                        a, b = self.seg[j][0], self.seg[j][1]
                        dj = unit(sub(b, a))
                        if abs(abs(dot(dj, d)) - 1) < 1e-3:
                            nxt = j
                            break
                    if nxt is None:
                        break
                    used.add(nxt)
                    a, b = self.seg[nxt][0], self.seg[nxt][1]
                    node = b if K(a) == K(node) else a
                    if direction == 1:
                        chain.append(nxt)
                    else:
                        chain.insert(0, nxt)
            runs.append(chain)
        return runs

    def run_geometry(self, chain):
        """ordered points along a chain and arc positions."""
        if len(chain) == 1:
            p, q = self.seg[chain[0]][0], self.seg[chain[0]][1]
            return [p, q]
        pts = []
        s0, s1 = self.seg[chain[0]], self.seg[chain[1]]
        shared = {K(s0[0]), K(s0[1])} & {K(s1[0]), K(s1[1])}
        start = s0[1] if K(s0[0]) in shared else s0[0]
        pts.append(start)
        cur = start
        for j in chain:
            a, b = self.seg[j][0], self.seg[j][1]
            cur = b if K(a) == K(cur) else a
            pts.append(cur)
        return pts

# --------------------------------------------------------------------------------------------
def place_supports(comps, endinfo, job, rep, seed=None):
    net = Net(comps)
    sup = {}                               # node key -> dict(type, pt, why, bore)
    for sd in (seed or []):                # BIM supports (contractor model) go in first, high priority
        sup[K(sd['pt'])] = dict(pt=sd['pt'], type=sd['type'], why=sd['why'], bore=sd['bore'], prio=sd.get('prio', 60))
    table = job['span_table_ft']
    eqtypes = {'EQUIP', 'CUT'}

    def add(pt, typ, why, bore, prio):
        k = K(pt)
        old = sup.get(k)
        if old is None or prio > old['prio']:
            sup[k] = dict(pt=pt, type=typ, why=why, bore=bore, prio=prio)
        return k

    # 1 anchors
    for r in endinfo:
        if r['kind'] in eqtypes:
            add(r['xyz'], 'ANC', f"{r['kind']}: {r['tag']}", r['bore'], 100)

    # 2 bends: support on horizontal side
    for c in comps:
        if c.typ != 'BEND':
            continue
        a, z, cn = c.pts['END1'], c.pts['END2'], c.pts['CENTRE']
        ha, hz = is_horizontal(sub(cn, a)), is_horizontal(sub(z, cn))
        if ha and hz:
            add(a, 'HGR', 'bend (horizontal plane), support at every bend', c.bore['END1'], 10)
        elif ha:
            add(a, 'HGR', 'bend, horizontal side', c.bore['END1'], 10)
        elif hz:
            add(z, 'HGR', 'bend, horizontal side', c.bore['END2'], 10)

    # 3 base supports from equipment nozzles: walk to first low bend
    ff = job.get('equipment_ff_ft', [])
    low = job.get('base_bend_max_above_ff_ft', 6.0)
    walk_max = job.get('base_walk_max_ft', 15.0) * 12
    comp_at = collections.defaultdict(list)
    for c in comps:
        for p in c.ends():
            comp_at[K(p)].append(c)
    base_report = []
    for r in endinfo:
        if r['kind'] != 'EQUIP':
            continue
        zff = max([f for f in ff if f * 12 <= r['xyz'][2] + 1], default=None)
        if zff is None:
            continue
        node, dist, seen, found = r['key'], 0.0, set(), None
        while dist < walk_max:
            cs = [c for c in comp_at[node] if c.id not in seen]
            if len(cs) != 1:
                break
            c = cs[0]
            seen.add(c.id)
            if c.typ == 'TEE':
                break
            ends = [K(p) for p in (c.pts['END1'], c.pts['END2'])]
            other = ends[1] if ends[0] == node else ends[0]
            if c.typ == 'BEND':
                a, z = c.pts['END1'], c.pts['END2']
                if max(a[2], z[2]) <= max((zff + low) * 12, r['xyz'][2] + 36):
                    cn = c.pts['CENTRE']
                    if is_horizontal(sub(cn, a)):
                        lowpt = a
                    elif is_horizontal(sub(z, cn)):
                        lowpt = z
                    else:
                        lowpt = a if a[2] < z[2] else z
                    found = lowpt
                    break
            dist += norm(sub(net.node_pt[other], net.node_pt[node]))
            node = other
        if found and norm(sub(found, r['xyz'])) < 12.0:
            # elbow right at the nozzle: put the base support on the bend's far end so it is not lost in the anchor
            for c in comp_at[K(found)]:
                if c.typ == 'BEND':
                    found = c.pts['END2'] if K(c.pts['END1']) == K(found) else c.pts['END1']
                    break
        if found and dist <= job.get('near_support_max_ft', 5.0) * 12:
            add(found, 'BASE', f"base support at first low bend from {r['tag']} (base-support rule)", r['bore'], 50)
            base_report.append((r['tag'], round(dist / 12, 1), 'BASE at first low bend'))
            continue
        if found:                                     # low bend exists but is far: keep it and add a near support
            add(found, 'BASE', f"base support at first low bend from {r['tag']} (base-support rule)", r['bore'], 50)
            base_report.append((r['tag'], round(dist / 12, 1), 'BASE at first low bend (far) + near-nozzle support'))
        # no low bend: support on the first straight pipe (> 6 in) off the nozzle, near_nozzle_in from it
        nn = job.get('near_nozzle_in', 24.0)
        placed, node, acc, seen2 = False, r['key'], 0.0, set()
        for _ in range(25):
            cs = [c for c in comp_at[node] if c.id not in seen2]
            if len(cs) != 1 or cs[0].typ == 'BEND':
                break
            c = cs[0]
            seen2.add(c.id)
            if c.typ == 'TEE':
                ke = [K(c.pts['END1']), K(c.pts['END2'])]
                if node not in ke:
                    break                                   # entered from branch
                nxt = ke[1] if ke[0] == node else ke[0]
                acc += norm(sub(net.node_pt[nxt], net.node_pt[node]))
                node = nxt
                continue
            a = net.node_pt[node]
            e1, e2 = c.pts['END1'], c.pts['END2']
            b = e2 if K(e1) == node else e1
            seglen = norm(sub(b, a))
            if c.typ == 'PIPE' and seglen > 6:
                t = min(max(nn - acc, 3.0), seglen - 3.0)
                p = addv(a, unit(sub(b, a)), t)
                typ = 'RSR' if is_vertical(sub(b, a)) else 'BASE'
                add(p, typ, f"support near nozzle {r['tag']} (base-support rule; {'vertical' if typ == 'RSR' else 'horizontal'} pipe)", r['bore'], 45)
                base_report.append((r['tag'], round((acc + t) / 12, 1), f'{typ} on first pipe off nozzle (no low bend)'))
                placed = True
                break
            acc += seglen
            node = K(b)
        if not placed:
            base_report.append((r['tag'], None, 'no low bend and no straight pipe within reach; VFY'))
    rep['base_supports'] = base_report

    # 4 risers: floor crossings on vertical runs
    floors = job.get('riser_floors_ft', [])
    above = job.get('riser_clamp_above_floor_ft', 1.0)
    runs = net.runs()
    for chain in runs:
        pts = net.run_geometry(chain)
        d = sub(pts[-1], pts[0])
        if not is_vertical(d):
            continue
        z0, z1 = sorted((pts[0][2], pts[-1][2]))
        for f in floors:
            zc = (f + above) * 12
            if z0 + 6 < zc < z1 - 6:
                x, y = pts[0][0], pts[0][1]
                b = min(net.seg[j][2].maxbore() for j in chain)
                add((x, y, zc), 'RSR', f'riser support at floor {f} ft + {above:g} ft', b, 40)

    # 4b long verticals: no more than riser_max_ft between supports
    rmax = job.get('riser_max_ft', 14.0) * 12
    for chain in runs:
        pts = net.run_geometry(chain)
        d = sub(pts[-1], pts[0])
        if not is_vertical(d) or norm(d) <= rmax:
            continue
        u = unit(d)
        total = norm(d)
        fixed = [0.0, total]                     # ends are bends / anchors / tees
        for k, v in sup.items():
            t = dot(sub(v['pt'], pts[0]), u)
            if 0 < t < total and norm(sub(addv(pts[0], u, t), v['pt'])) < 1.0:
                fixed.append(t)
        fixed.sort()
        b = min(net.seg[j][2].maxbore() for j in chain)
        for a, z in zip(fixed, fixed[1:]):
            if z - a > rmax:
                n = math.ceil((z - a) / rmax)
                for i in range(1, n):
                    p = addv(pts[0], u, a + (z - a) * i / n)
                    add(p, 'RSR', f'riser guide/clamp, {rmax / 12:.0f} ft max (riser_max_ft); attachment VFY', b, 30)

    # 5 span fill on horizontal runs
    for chain in runs:
        pts = net.run_geometry(chain)
        d = sub(pts[-1], pts[0])
        if norm(d) < 1 or not is_horizontal(d):
            continue
        b = min(min(net.seg[j][2].bore.values()) for j in chain)
        L = span_ft(b, table) * 12
        s = [0.0]
        for i in range(1, len(pts)):
            s.append(s[-1] + norm(sub(pts[i], pts[i - 1])))
        total = s[-1]
        u = unit(d)
        # supported positions on this run
        fixed = []
        for i, p in enumerate(pts):
            k = K(p)
            if k in sup:
                fixed.append(s[i])
        for k, v in sup.items():                       # supports placed mid-run earlier
            p = v['pt']
            t = dot(sub(p, pts[0]), u)
            if 0 < t < total and norm(sub(addv(pts[0], u, t), p)) < 0.1:
                fixed.append(t)

        def end_state(p):
            k = K(p)
            if k in sup:
                return 'sup'
            segs = net.at[k]
            if len(segs) == 1:
                return 'free'
            roles = {net.seg[j][3] for j in segs}
            if 'branch' in roles or 'run' in roles:
                return 'tee'                           # header / branch junction: carried by header
            if 'bendleg' in roles:
                return 'bend'
            return 'other'
        st0, st1 = end_state(pts[0]), end_state(pts[-1])
        def bend_virtual(p):
            """run ends at an unsupported bend end: if the bend's other end carries a support, that
            support sits 'arc' behind this end (path via the corner); else put a support here."""
            k = K(p)
            for c in comp_at[k]:
                if c.typ != 'BEND':
                    continue
                e1, e2, cn = c.pts['END1'], c.pts['END2'], c.pts['CENTRE']
                other = e2 if K(e1) == k else e1
                if K(other) in sup:
                    return norm(sub(cn, e1)) + norm(sub(e2, cn))
            add(p, 'HGR', 'bend, second side (span across bend)', b, 9)
            return 0.0
        def header_ratio(p):
            bs = [max(net.seg[j][2].bore.values()) for j in net.at[K(p)]]
            return b / max(bs) if bs else 0
        for st, pos, sgn in ((st0, 0.0, -1), (st1, total, 1)):
            if st == 'tee' and header_ratio(pts[0] if sgn < 0 else pts[-1]) > job.get('tee_carry_ratio', 0.5) and total > 36:
                d0 = min(job.get('near_tee_in', 18.0), total / 2)
                tpos = pos - sgn * d0
                add(addv(pts[0], u, tpos), 'HGR', 'branch near equal-size tee (header does not carry it)', b, 8)
                fixed.append(tpos)
            elif st in ('tee', 'other'):
                fixed.append(pos)
            elif st == 'bend':
                fixed.append(pos + sgn * bend_virtual(pts[0] if sgn < 0 else pts[-1]))
        if st0 == 'free' and total > 48:
            fixed.append(min(12.0, total))
            add(addv(pts[0], u, min(12.0, total)), 'HGR', 'near free end', b, 5)
        if st1 == 'free' and total > 48:
            fixed.append(max(total - 12.0, 0))
            add(addv(pts[0], u, max(total - 12.0, 0)), 'HGR', 'near free end', b, 5)
        fixed = sorted(set(round(x, 3) for x in fixed))
        pipe_iv = []                                   # (s0, s1, span in) for pipe segments
        for i, j in enumerate(chain):
            sg = net.seg[j]
            if sg[3] == 'pipe':
                pipe_iv.append((s[i], s[i + 1], span_ft(sg[2].bore['END1'], table) * 12))
        def gap_L(a, z):
            ls = [Lp for s0, s1, Lp in pipe_iv if s1 > a + 1e-6 and s0 < z - 1e-6]
            return min(ls) if ls else L
        if not fixed:
            Lg = gap_L(0, total)
            n = max(1, math.ceil(total / Lg))
            fixed_new = [total * (i + 0.5) / n for i in range(n)]
        else:
            fixed_new = []
            for a, z in zip(fixed, fixed[1:]):
                Lg = gap_L(a, z)
                if z - a > Lg:
                    n = math.ceil((z - a) / Lg)
                    fixed_new += [a + (z - a) * i / n for i in range(1, n)]
        centres = {K(c.pts['CENTRE']) for c in comps if c.typ == 'TEE'}
        segpos = []                                   # (s0, s1, is_pipe)
        for i, j in enumerate(chain):
            segpos.append((s[i], s[i + 1], net.seg[j][3] == 'pipe'))
        for t in fixed_new:
            tt, snap_pt = t, None
            for i, (s0, s1, isp) in enumerate(segpos):
                if s0 - 1e-6 <= t <= s1 + 1e-6 and not isp:
                    c0, c1 = K(pts[i]) in centres, K(pts[i + 1]) in centres
                    if c0 and not c1:
                        snap_pt = pts[i + 1]
                    elif c1 and not c0:
                        snap_pt = pts[i]
                    else:
                        snap_pt = pts[i] if (t - s0) <= (s1 - t) else pts[i + 1]   # nearer end of the fitting
                    break
            add(snap_pt if snap_pt is not None else addv(pts[0], u, tt), 'HGR', f'span fill to the job span table (span_table_ft)', b, 1)

    # 6 merge supports closer than merge_in along same pipe (keep higher priority)
    merge = job.get('merge_in', 18.0)
    run_pts = [net.run_geometry(ch) for ch in runs]
    comp_nodes = [set(K(p) for p in c.ends()) for c in comps]
    def on_same_pipe(p, q):
        """True if p and q lie on one straight run, or are end nodes of one component (e.g. a bend)."""
        kp, kq = K(p), K(q)
        if any(kp in cn and kq in cn for cn in comp_nodes):
            return True
        for rp in run_pts:
            a, z = rp[0], rp[-1]
            L_ = norm(sub(z, a))
            if L_ < 1e-6:
                continue
            u_ = unit(sub(z, a))
            ok = True
            for x in (p, q):
                t = dot(sub(x, a), u_)
                if not (-0.1 <= t <= L_ + 0.1) or norm(sub(addv(a, u_, t), x)) > 0.1:
                    ok = False
                    break
            if ok:
                return True
        return False
    keys = sorted(sup, key=lambda k: -sup[k]['prio'])
    kept = {}
    for k in keys:
        v = sup[k]
        p = v['pt']
        clash = False
        for j, w in kept.items():
            dd = norm(sub(p, w['pt']))
            if dd >= merge:
                continue
            if v['prio'] >= 30 and w['prio'] >= 30 and dd >= 6:
                continue                       # keep base / riser supports even beside an anchor
            if v['prio'] >= 30 and w['prio'] < 30:
                continue
            if on_same_pipe(p, w['pt']):
                clash = True
                break
        if not clash:
            kept[k] = v
    rep['supports_merged_away'] = len(sup) - len(kept)
    zb = job.get('no_support_below_ft')
    if zb is not None:
        drop = [k for k, v in kept.items() if v['type'] != 'ANC' and v['pt'][2] < zb * 12]
        for k in drop:
            del kept[k]
        rep['supports_dropped_buried'] = len(drop)
    return kept

# --------------------------------------------------------------------------------------------
def split_at_supports(comps, sup):
    """split PIPE comps at support points lying inside them; returns new list."""
    out = []
    items = list(sup.items())
    moved = {}
    for c in comps:
        if c.typ != 'PIPE':
            out.append(c)
            continue
        a, b = c.pts['END1'], c.pts['END2']
        L = norm(sub(b, a))
        u = unit(sub(b, a))
        cuts = []
        for k, v in items:
            p = v['pt']
            t = dot(sub(p, a), u)
            if 0.5 < t < L - 0.5 and norm(sub(addv(a, u, t), p)) < 0.1:
                cuts.append(round(t, 4))
                moved[k] = addv(a, u, round(t, 4))       # support moves exactly onto the centreline
        if not cuts:
            out.append(c)
            continue
        cuts = sorted(set(cuts))
        prev = a
        for t in cuts + [L]:
            q = b if t == L else addv(a, u, t)
            n = Comp('PIPE', {'END1': prev, 'END2': q}, {'END1': c.bore['END1'], 'END2': c.bore['END1']},
                     c.src, desc=c.kw.get('desc', 'PIPE'))
            n.line = c.line
            out.append(n)
            prev = q
    for k, q in moved.items():
        v = sup.pop(k)
        v['pt'] = q
        sup[K(q)] = v
    return out

# --------------------------------------------------------------------------------------------
def walk_order(comps, starts):
    """order + orient comps: depth-first, run continued before branches."""
    at = collections.defaultdict(list)
    for c in comps:
        for p in c.ends():
            at[K(p)].append(c)
    done, order = set(), []
    remaining = set(c.id for c in comps)
    byid = {c.id: c for c in comps}

    def orient(c, entry):
        if c.typ == 'TEE':
            if K(c.pts['END2']) == entry:
                c.pts['END1'], c.pts['END2'] = c.pts['END2'], c.pts['END1']
                c.bore['END1'], c.bore['END2'] = c.bore['END2'], c.bore['END1']
            return
        if K(c.pts['END2']) == entry:
            c.pts['END1'], c.pts['END2'] = c.pts['END2'], c.pts['END1']
            c.bore['END1'], c.bore['END2'] = c.bore['END2'], c.bore['END1']

    def go(entry_key):
        branch_q = collections.deque([entry_key])
        while branch_q:
            node = branch_q.popleft()
            while True:
                cand = [c for c in at[node] if c.id not in done]
                if not cand:
                    break
                # prefer collinear continuation, then largest bore
                c = sorted(cand, key=lambda c: -c.maxbore())[0]
                for extra in cand:
                    if extra is not c:
                        branch_q.append(node)
                done.add(c.id)
                orient(c, node)
                order.append(c)
                if c.typ == 'TEE':
                    ke1, ke2, kb = K(c.pts['END1']), K(c.pts['END2']), K(c.pts['BRANCH'])
                    if node == kb:
                        branch_q.append(ke2)
                        node = ke1 if ke1 != node else ke2
                    else:
                        branch_q.append(kb)
                        node = ke2
                else:
                    node = K(c.pts['END2'])

    for s in starts:
        if any(c.id not in done for c in at[s]):
            go(s)
    while len(done) < len(comps):
        # start new piece from a degree-1 node of the remainder
        rest = [c for c in comps if c.id not in done]
        deg = collections.Counter(K(p) for c in rest for p in c.ends())
        k = next((K(p) for c in rest for p in c.ends() if deg[K(p)] == 1), K(rest[0].pts['END1']))
        go(k)
    return order

# --------------------------------------------------------------------------------------------
def fmt_pt(p, bore=None):
    s = f"{p[0]:16.4f}{p[1]:16.4f}{p[2]:16.4f}"
    return s + (f"{bore:12.4f}" if bore is not None else '')

SUPMAP = {   # name prefix -> (SKEY, direction) fallback when PCF_RES_MAP is not edited
    'ANC': ('ANCH', None), 'HGR': ('SKID', 'UP'), 'BASE': ('SKID', 'UP'), 'RSR': ('SKID', 'UP'),
    'BHGR': ('SKID', 'UP'), 'BTRP': ('SKID', 'UP')}

def emit(path, pipeline, attrs, order, sup, sup_ids, job=None):
    job = job or {}
    prefix = job.get('support_prefix', 'PTS')
    L = ['ISOGEN-FILES ISOGEN.FLS', 'UNITS-BORE INCH', 'UNITS-CO-ORDS INCH', 'UNITS-WEIGHT LBS',
         'UNITS-BOLT-DIA INCH', 'UNITS-BOLT-LENGTH INCH', f'PIPELINE-REFERENCE {pipeline}']
    if job.get('project_identifier'):
        L.append(f"    PROJECT-IDENTIFIER {job['project_identifier']}")
    if job.get('area'):
        L.append(f"    AREA {job['area']}")
    for k, v in attrs.items():
        L.append(f'    {k} {v}')
    emitted = set()
    def sup_rec(k):
        if k in emitted or k not in sup:
            return []
        emitted.add(k)
        v = sup[k]
        skey, dr = SUPMAP[v['type']]
        r = ['SUPPORT', '    CO-ORDS     ' + fmt_pt(v['pt'], v['bore']), f'    SKEY {skey}']
        if dr:
            r.append(f'    SUPPORT-DIRECTION {dr}')
        r.append(f"    NAME {prefix}-{v['type']}_{sup_ids[k]}")
        return r
    for c in order:
        P, B = c.pts, c.bore
        L.append(c.typ)
        L.append('    END-POINT   ' + fmt_pt(P['END1'], B['END1']))
        L.append('    END-POINT   ' + fmt_pt(P['END2'], B['END2']))
        if c.typ == 'BEND':
            L.append('    CENTRE-POINT' + fmt_pt(P['CENTRE']))
            L += ['    SKEY BEBW', f"    ANGLE {c.kw['angle']}", f"    BEND-RADIUS {c.kw['radius']:.4f}"]
        elif c.typ == 'TEE':
            L.append('    CENTRE-POINT' + fmt_pt(P['CENTRE']))
            L.append('    BRANCH1-POINT' + fmt_pt(P['BRANCH'], B['BRANCH']))
            L.append('    SKEY TEBW')
        elif c.typ == 'REDUCER-CONCENTRIC':
            L.append('    SKEY RCBW')
        elif c.typ == 'VALVE':
            L.append('    SKEY VVFL')
        rid = c.src['revit_id'] if c.src else ''
        L.append(f"    ITEM-DESCRIPTION {c.kw.get('desc', c.typ)} RID{rid}")
        for p in c.ends():
            L += sup_rec(K(p))
    with open(path, 'w', newline='') as f:
        f.write('\r\n'.join(L) + '\r\n')
    return emitted

# --------------------------------------------------------------------------------------------
def main(jobpath):
    with open(jobpath, encoding='utf-8') as fh:
        job = json.load(fh)
    base = os.path.dirname(os.path.abspath(jobpath))
    job.setdefault('name', 'job')
    outdir = os.path.join(base, job['outdir'])          # an absolute outdir stays absolute
    os.makedirs(outdir, exist_ok=True)
    handlers = [logging.FileHandler(os.path.join(outdir, job['name'] + '.log'), 'w', encoding='utf-8'),
                logging.StreamHandler()]
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s', handlers=handlers, force=True)
    rep = collections.defaultdict(list)
    rep['job'] = job['name']
    models, chillers, ends, straddle = split_models(job, base)
    if 'model' not in job:
        if len(models) != 1:
            raise KeyError("model (job key 'model' names which of %s to build)" % sorted(models))
        job['model'] = next(iter(models))
    if job['model'] not in models:
        raise KeyError("model %r is not one of %s" % (job['model'], sorted(models)))
    elems = models[job['model']]
    log.info('model %s: %d deduplicated Revit elements in the model box', job['model'], len(elems))
    rep['revit_elements_in'] = len(elems)
    rep['chillers_removed'] = len(chillers)
    comps = convert(elems, job, rep)
    log.info('converted %d components; dropped %s', len(comps), rep['dropped'])
    seeds = {}
    cpl = job.get('chiller_port_lines', {})
    for u in chillers:
        for kname, ln in cpl.items():
            if kname in u['pts']:
                seeds[K(u['pts'][kname])] = ln
    unres = assign_lines(comps, job, seeds)
    rep['line_unresolved'] = unres
    endinfo = classify_ends(comps, chillers, ends, straddle, job)
    rep['ends'] = [{k: (v if k != 'key' else None) for k, v in r.items() if k != 'key'} for r in endinfo]
    sup = place_supports(comps, endinfo, job, rep)
    comps = split_at_supports(comps, sup)
    # supports must now be on nodes
    nodes = {K(p) for c in comps for p in c.ends()}
    nb = collections.defaultdict(list)
    for c in comps:
        for kk, p in c.pts.items():
            if kk in c.bore:
                nb[K(p)].append(c.bore[kk])
    for k, v in sup.items():
        if nb.get(k):
            v['bore'] = max(nb[k])
    off = [k for k in sup if k not in nodes]
    node_list = {K(p): p for c in comps for p in c.ends()}
    for k in off:
        v = sup.pop(k)
        near = min(node_list.values(), key=lambda q: norm(sub(q, v['pt'])))
        d = norm(sub(near, v['pt']))
        if d <= 18.0 and K(near) not in sup:
            v['pt'] = near
            v['why'] += f' (snapped {d:.1f} in to nearest node)'
            sup[K(near)] = v
            rep['notes'].append(f"support snapped {d:.1f} in to node at {tuple(round(c / 12, 2) for c in near)} ft")
        else:
            rep['errors'].append(f"support off-node dropped at {tuple(round(c / 12, 2) for c in v['pt'])} ft ({v['why']})")
    # number supports in walk order per line
    order_all = []
    for ln in job['lines']:
        lc = [c for c in comps if c.line == ln]
        starts = [r['key'] for r in endinfo if r['line'] == ln and r['kind'] in ('CUT', 'EQUIP')]
        starts.sort(key=lambda k: (0 if any(r['key'] == k and r['kind'] == 'CUT' for r in endinfo) else 1))
        order_all.append((ln, walk_order(lc, starts)))
    sup_ids, n = {}, 0
    for ln, order in order_all:
        for c in order:
            for p in c.ends():
                k = K(p)
                if k in sup and k not in sup_ids:
                    n += 1
                    sup_ids[k] = f'{job["model"]}{n:03d}'
    files = []
    emitted_all = set()
    for ln, order in order_all:
        attrs = job['lines'][ln].get('pcf_attributes', {})
        pth = os.path.join(outdir, f"{job['name']}_{ln}.pcf")
        em = emit(pth, ln, attrs, order, {k: v for k, v in sup.items() if k not in emitted_all}, sup_ids, job)
        emitted_all |= em
        files.append(pth)
        log.info('wrote %s: %d components, %d supports', pth, len(order), len(em))
        rep['files'].append({'path': os.path.basename(pth), 'line': ln, 'components': len(order), 'supports': len(em)})
    # combined fallback
    comb = os.path.join(outdir, f"{job['name']}_combined.pcf")
    emit(comb, job['model'], {}, [c for _, o in order_all for c in o], sup, sup_ids, job)
    rep['files'].append({'path': os.path.basename(comb), 'line': 'ALL', 'components': len(comps), 'supports': len(sup)})
    # support list
    import csv
    with open(os.path.join(outdir, f"{job['name']}_supports.csv"), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['support_id', 'type', 'line', 'X_ft', 'Y_ft', 'Z_ft', 'NPS', 'basis', 'status'])
        line_at = {K(p): c.line for c in comps for p in c.ends()}
        for k, v in sorted(sup.items(), key=lambda kv: sup_ids.get(kv[0], '')):
            w.writerow([sup_ids.get(k), v['type'], line_at.get(k), *(round(c / 12, 3) for c in v['pt']), v['bore'],
                        v['why'], 'ASSUMED rule-placed' if v['type'] != 'ANC' or 'CUT' in v['why'] else 'ASSUMED equipment anchor'])
    rep['support_counts'] = dict(collections.Counter(v['type'] for v in sup.values()))
    rep['component_counts'] = dict(collections.Counter(c.typ for c in comps))
    with open(os.path.join(outdir, f"{job['name']}_report.json"), 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=1, default=str)
    log.info('supports %s; errors %d', rep['support_counts'], len(rep['errors']))
    return rep


def cli(argv):
    if len(argv) == 1 and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if len(argv) != 1:
        sys.stderr.write('usage: python pcf2caesar.py job.json   (python pcf2caesar.py --help for the job keys)\n')
        return 2
    try:
        rep = main(argv[0])
    except (OSError, KeyError, ValueError) as e:      # JSONDecodeError is a ValueError
        sys.stderr.write('pcf2caesar failed: %s: %s\n' % (type(e).__name__, e))
        return 1
    return 2 if rep['errors'] else 0

if __name__ == '__main__':
    sys.exit(cli(sys.argv[1:]))
