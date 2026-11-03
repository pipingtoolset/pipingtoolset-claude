#!/usr/bin/env python3
"""fix_cii.py - repair a CAESAR II neutral file (.CII, format 5.0 / CAESAR II 15) after an APCF import.

Python 3.9+, standard library only.

APCF cannot set the start node or increment per PCF and numbers every file 10, 20, 30 ...,
so two lines imported into one job collide. It also cannot carry per-line T/P from a combined
PCF, and a '+ANC' entry in PCF_RES_MAP.TXT imports as restraint code 6 instead of code 1 (ANC).
This script fixes all three without touching geometry, element order, rigids, bends or SIFs.

Usage:
  python fix_cii.py in.CII out.CII node_map.csv lines.json

lines.json (see examples/lines.example.json):
  {
    "inc": 5, "p1": 150.0, "insul_in": 1.0, "fluid_den_lb_in3": 0.0361111,
    "tol_in": 0.05,
    "lines": {
      "CHS": {"pcf": "CHS.pcf", "start": 10,   "band_end": 4995, "t1": 40.0},
      "CHR": {"pcf": "CHR.pcf", "start": 5000, "band_end": 9995, "t1": 58.0}
    }
  }
Each element is assigned to the line whose PCF contains both its end points (within tol_in).
Keep every band below 9999: AutoPIPE renames CAESAR II nodes >= 10000 alphanumerically.
Fluid: the neutral file carries a DENSITY in lb/in^3, not a specific gravity. Water = 62.4/1728.
Afterwards run verify_cii.py (in.CII, out.CII, node_map.csv, lines.json); it must print PASS.

Exit codes: 0 written; 2 input or format problem (message names it); nothing is written on 2.
"""
import collections
import csv
import json
import math
import re
import sys

NUM = re.compile(r'-?\d+\.\d+E[+-]\d+')


def fail(msg):
    print('fix_cii: ' + str(msg), file=sys.stderr)
    sys.exit(2)


def fmt(vals):                       # CAESAR II neutral real line: 2 spaces + %13.6E fields
    return '  ' + ''.join('%13.6E' % v for v in vals)


def reals(s):
    return [float(x) for x in NUM.findall(s)]


def read(path):
    with open(path, encoding='latin-1') as fh:
        lines = fh.read().split('\n')
    idx = {l[2:].strip(): i for i, l in enumerate(lines) if l.startswith('#$')}
    order = sorted(idx.items(), key=lambda kv: kv[1])
    rng = {}
    for k, (name, i) in enumerate(order):
        j = order[k + 1][1] if k + 1 < len(order) else len(lines)
        rng[name] = (i + 1, j)
    return lines, rng


class PointIndex:
    """Nearest-point distance queries on a fixed set of 3-D points (uniform grid, stdlib only)."""

    def __init__(self, points, cell):
        self.cell = float(cell) if cell > 0 else 1.0
        self.grid = collections.defaultdict(list)
        self.n = 0
        for p in points:
            self.grid[self._key(p)].append(tuple(p))
            self.n += 1

    def _key(self, p):
        return (math.floor(p[0] / self.cell), math.floor(p[1] / self.cell), math.floor(p[2] / self.cell))

    def nearest_dist(self, p, radius):
        """Distance to the nearest indexed point within `radius`, else a value greater than radius."""
        if self.n == 0:
            return float('inf')
        r = int(math.ceil(radius / self.cell))
        kx, ky, kz = self._key(p)
        best = float('inf')
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    for q in self.grid.get((kx + dx, ky + dy, kz + dz), ()):
                        d = math.dist(p, q)
                        if d < best:
                            best = d
        return best


def pcf_points(path):
    pts = []
    with open(path, encoding='latin-1') as fh:
        for ln in fh:
            t = ln.split()
            if t and t[0] in ('END-POINT', 'CENTRE-POINT', 'BRANCH1-POINT', 'CO-ORDS'):
                pts.append(tuple(float(v) for v in t[1:4]))
    return pts


def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def to_pcf(p):                       # CAESAR II (X, Y up, Z) -> PCF (X, Y, Z up)
    return (p[0], -p[2], p[1])


def main(src, dst, mapcsv, cfg_path):
    with open(cfg_path, encoding='utf-8') as fh:
        cfg = json.load(fh)
    INC, P1, INSUL = cfg.get('inc', 5), cfg.get('p1', 0.0), cfg.get('insul_in', 0.0)
    FLUID = cfg.get('fluid_den_lb_in3', 62.4 / 1728.0)
    TOL = cfg.get('tol_in', 0.05)
    LINES = cfg.get('lines') or fail('lines.json has no "lines"')
    L, R = read(src)
    for sec in ('ELEMENTS', 'COORDS', 'BEND', 'RESTRANT', 'SIF&TEES'):
        if sec not in R:
            fail('section #$ %s not found in %s' % (sec, src))
    a, b = R['ELEMENTS']
    for ln in L[a:a + 9]:
        if fmt(reals(ln)) != ln.rstrip():
            fail('formatter mismatch on element line: %r' % ln)
    E = []
    for i in range(a, b, 15):
        r = []
        for k in range(9):
            r += reals(L[i + k])
        E.append(dict(i=i, r=r))
    if not E:
        fail('no elements')
    # coordinates (CAESAR II frame: X, Y up, Z) from COORDS seeds + element deltas
    ca, cb = R['COORDS']
    pos = {}
    for ln in L[ca + 1:cb]:
        if ln.strip():
            v = reals(ln)
            pos[float(int(ln[:15]))] = (v[0] * 12.0, v[1] * 12.0, v[2] * 12.0)
    changed = True
    while changed:
        changed = False
        for e in E:
            f, t, d = e['r'][0], e['r'][1], tuple(e['r'][2:5])
            if f in pos and t not in pos:
                pos[t] = vadd(pos[f], d)
                changed = True
            elif t in pos and f not in pos:
                pos[f] = vsub(pos[t], d)
                changed = True
    nodes_all = {x for e in E for x in e['r'][:2]}
    if not nodes_all <= set(pos):
        fail('unresolved nodes (no COORDS seed reaches them): %s' % sorted(nodes_all - set(pos))[:10])
    trees = {}
    for k, v in LINES.items():
        if 'pcf' not in v or 'start' not in v:
            fail('line %s needs "pcf" and "start"' % k)
        trees[k] = PointIndex(pcf_points(v['pcf']), TOL)
    member = {n: {k for k, T in trees.items() if T.nearest_dist(to_pcf(pos[n]), TOL) <= TOL}
              for n in nodes_all}
    miss = [int(n) for n, m in member.items() if not m]
    if miss:
        fail('nodes on no PCF (check tol_in / axis convention): %s' % miss[:10])
    nxt = {k: v['start'] for k, v in LINES.items()}
    new, eline = {}, []
    for e in E:
        f, t = e['r'][0], e['r'][1]
        both = member[f] & member[t]
        if len(both) == 1:
            ln = next(iter(both))
        elif len(member[t]) == 1:
            ln = next(iter(member[t]))
        else:
            ln = sorted(member[f])[0]
        eline.append(ln)
        for n in (f, t):
            if n not in new:
                nl = next(iter(member[n])) if len(member[n]) == 1 else ln
                new[n] = nxt[nl]
                nxt[nl] += INC
    for k, v in LINES.items():
        if nxt[k] - INC > v.get('band_end', 9995):
            fail('%s overflows its band (last node %d > band_end %s)' % (k, nxt[k] - INC, v.get('band_end', 9995)))
    for e, ln in zip(E, eline):
        r = e['r'][:]
        r[0], r[1] = float(new[r[0]]), float(new[r[1]])
        if INSUL:
            r[7] = INSUL
        if 't1' in LINES[ln]:
            r[9] = LINES[ln]['t1']
        if P1:
            r[18] = P1
        r[31] = FLUID
        chunks = [r[0:6], r[6:12], r[12:18], r[18:24], r[24:30], r[30:36], r[36:42], r[42:48], r[48:53]]
        for k, c in enumerate(chunks):
            L[e['i'] + k] = fmt(c)
    # BEND aux: fields 3,5,7 are bend mid/near nodes = TO-1 / TO-2 of the bend element
    ba, bb = R['BEND']
    for e in E:
        p = int(L[e['i'] + 12].split()[0])
        if not p:
            continue
        i0 = ba + 3 * (p - 1)
        v = reals(L[i0]) + reals(L[i0 + 1]) + reals(L[i0 + 2])
        oldto = e['r'][1]
        nt = new[oldto]
        for fi in (3, 5, 7):
            if v[fi]:
                off = oldto - v[fi]
                if not 0 < off < 10:
                    fail('bend node %s is not just below its TO node %s' % (v[fi], oldto))
                v[fi] = float(nt - off)
        L[i0], L[i0 + 1], L[i0 + 2] = fmt(v[0:6]), fmt(v[6:12]), fmt(v[12:14])
    # RESTRANT: 24 lines / record, 6 slots x (values, dir, tag, guid); code 6 -> 1 (ANC)
    ra, rb = R['RESTRANT']
    fixed_anc = 0
    for i in range(ra, rb, 24):
        for k in range(6):
            j = i + 4 * k
            if j >= rb:
                break
            v = reals(L[j])
            if len(v) < 6 or not (v[0] or v[1]):
                continue
            v[0] = float(new[v[0]])
            if v[5]:
                v[5] = float(new[v[5]])
            if v[1] == 6.0:
                v[1] = 1.0
                fixed_anc += 1
                L[j + 1] = fmt([0.0, 0.0, 0.0])
            L[j] = fmt(v)
    # SIF&TEES: 2 slots x 42 values per element record, node at slot[0]
    sa, sb_ = R['SIF&TEES']
    vals = []
    spans = []
    for j in range(sa, sb_):
        vv = reals(L[j])
        spans.append((j, len(vv)))
        vals += vv
    for s in range(0, len(vals), 42):
        if vals[s]:
            vals[s] = float(new[vals[s]])
    k = 0
    for j, n in spans:
        L[j] = fmt(vals[k:k + n])
        k += n
    for j in range(ca + 1, cb):
        ln = L[j]
        if ln.strip():
            n = float(int(ln[:15]))
            v = reals(ln)
            L[j] = '%15d' % new[n] + ''.join('%13.6E' % x for x in v)
    for sec in ('DISPLMNT', 'FORCMNT', 'EQUIPMNT', 'FLANGES', 'EXPJT', 'UNIFORM', 'WIND', 'OFFSETS'):
        if sec in R:
            x, y = R[sec]
            if any(l.strip() for l in L[x:y]):
                fail('%s is not empty: extend the fixer first' % sec)
    with open(dst, 'w', encoding='latin-1', newline='\r\n') as fh:
        fh.write('\n'.join(L))
    with open(mapcsv, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['old_node', 'new_node', 'line', 'X_in', 'Y_in', 'Z_in'])
        for n in sorted(new, key=lambda n: new[n]):
            p = to_pcf(pos[n])
            w.writerow([int(n), new[n], '/'.join(sorted(member[n])), *[round(x, 3) for x in p]])
    print('elements', len(E), 'nodes', len(new), 'anchors fixed', fixed_anc,
          {k: '%d-%d' % (v['start'], nxt[k] - INC) for k, v in LINES.items()},
          'elements per line', dict(collections.Counter(eline)),
          'shared nodes', sum(1 for m in member.values() if len(m) > 1))
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 5:
        print(__doc__.split('Usage:')[1].split('\n')[1].strip(), file=sys.stderr)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:5]))
