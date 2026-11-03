"""PCF reader + Bentley PCF Translator emulation for ap_bendcheck.py (import it, do not run it).

read_pcf(path)           component dicts (type, end points, centre point, branch points, supports)
written_radius(comp)     the bend radius the translator writes: 1.5 x NPS ('L') when the computed
                         R = mean(T1, T2) / tan(theta / 2) is within L_TOL of it, else R explicitly
pcf_chains(path)         point chains in the order the translator would write them, for analyse()
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python -I
from ap_bendcheck import sub, add, mul, norm, unit, ang

L_TOL = 0.025  # relative; |R/(1.5*NPS) - 1| <= L_TOL -> 'L' (calibrated window 1.85%..3.11%)
KEYS = ('PIPE', 'ELBOW', 'BEND', 'TEE', 'FLANGE', 'FLANGE-BLIND', 'VALVE', 'REDUCER-ECCENTRIC',
        'REDUCER-CONCENTRIC', 'MISC-COMPONENT', 'SUPPORT', 'OLET', 'COUPLING', 'CAP', 'GASKET',
        'INSTRUMENT', 'FILTER', 'WELD')


def read_pcf(path):
    comps, cur = [], None
    for raw in open(path, errors='replace'):
        line = raw.rstrip()
        if not line:
            continue
        if not raw[0].isspace():
            w = line.split()[0]
            cur = dict(type=w, ep=[], cp=None, bp=[], co=None, nps=None, uid=None) \
                if (w in KEYS or w.isupper() and w not in ('UNITS-BORE',) and '-' not in w[:0]) else None
            if cur is not None and not w.startswith(('UNITS', 'ISOGEN', 'PIPELINE')):
                comps.append(cur)
            continue
        if cur is None:
            continue
        t = line.split()
        k = t[0]
        if k == 'END-POINT':
            cur['ep'].append(tuple(map(float, t[1:4])))
            if cur['nps'] is None:
                cur['nps'] = float(t[4])
        elif k == 'CENTRE-POINT':
            cur['cp'] = tuple(map(float, t[1:4]))
        elif k.startswith('BRANCH') and k.endswith('-POINT'):
            cur['bp'].append(tuple(map(float, t[1:4])))
        elif k == 'CO-ORDS':
            cur['co'] = tuple(map(float, t[1:4]))
            cur['nps'] = float(t[4]) if len(t) > 4 else None
        elif k == 'UNIQUE-COMPONENT-IDENTIFIER':
            cur['uid'] = t[1]
    return comps


def elbow_radius(c):
    e1, e2 = c['ep'][:2]
    cp = c['cp']
    t1, t2 = norm(sub(e1, cp)), norm(sub(e2, cp))
    th = ang(sub(cp, e1), sub(e2, cp))
    if th < 1e-6:
        return None, th, t1, t2
    return 0.5*(t1+t2)/math.tan(math.radians(th)/2), th, t1, t2


def written_radius(c, l_tol=L_TOL):
    R, th, t1, t2 = elbow_radius(c)
    if R is None:
        return None, False
    L = 1.5*c['nps']
    if abs(R/L - 1.0) <= l_tol:
        return L, True
    return round(R, 3), False


def key(p, q=0.01):
    return (round(p[0]/q), round(p[1]/q), round(p[2]/q))


def pcf_chains(path, l_tol=L_TOL, on_tol=0.05):
    """Build point chains as the translator would write them.
    Node kinds: BEND (elbow CP = TIP, R as the translator writes it), RED/VALV
    (end of a reducer/valve element), RUN otherwise. Both elbow end-points stay
    as points (near end = previous point, far end = 'xxxF')."""
    comps = read_pcf(path)
    nodes = {}          # key -> dict(xyz, kind, R, nps)
    adj = {}            # key -> list of (key, edgekind)
    nL = nX = 0

    def node(p, kind='RUN', R=None, nps=None):
        k = key(p)
        if k not in nodes:
            nodes[k] = dict(xyz=p, kind=kind, R=R, nps=nps, name='%.2f,%.2f,%.2f' % p)
            adj[k] = []
        elif kind == 'BEND':
            nodes[k].update(kind=kind, R=R, nps=nps)
        return k

    def edge(a, b, kind):
        if a == b:
            return
        adj[a].append((b, kind)); adj[b].append((a, kind))

    supports = [c['co'] for c in comps if c['type'] == 'SUPPORT' and c['co']]
    pipes = []
    for c in comps:
        t = c['type']
        if t == 'SUPPORT' or len(c['ep']) < 2:
            continue
        e1, e2 = c['ep'][:2]
        if t in ('ELBOW', 'BEND') and c['cp']:
            R, isL = written_radius(c, l_tol)
            if R is None:
                edge(node(e1), node(e2), 'PIPE'); continue
            nL += isL; nX += (not isL)
            kc = node(c['cp'], 'BEND', R, c['nps'])
            edge(node(e1), kc, 'ELB'); edge(kc, node(e2), 'ELB')
        elif t == 'TEE' and c['cp']:
            kc = node(c['cp'])
            edge(node(e1), kc, 'PIPE'); edge(kc, node(e2), 'PIPE')
            for b in c['bp']:
                edge(kc, node(b), 'PIPE')
        elif t == 'PIPE':
            pipes.append((e1, e2))
        elif t.startswith('REDUCER'):
            edge(node(e1), node(e2), 'RED')
        elif t == 'VALVE':
            edge(node(e1), node(e2), 'VALV')
        else:
            edge(node(e1), node(e2), 'PIPE')
    # pipes split at supports lying on them
    for e1, e2 in pipes:
        d = sub(e2, e1); L = norm(d); u = unit(d)
        pts = []
        for s in supports:
            v = sub(s, e1); t = v[0]*u[0]+v[1]*u[1]+v[2]*u[2]
            if on_tol < t < L-on_tol and norm(sub(v, mul(u, t))) < 0.5:
                pts.append((t, add(e1, mul(u, t))))
        seq = [node(e1)] + [node(p) for _, p in sorted(pts)] + [node(e2)]
        for a, b in zip(seq, seq[1:]):
            edge(a, b, 'PIPE')
    # mark reducer/valve far points
    # walk chains
    chains, used = [], set()
    def ekey(a, b): return (a, b) if a < b else (b, a)

    def walk(start, nxt, kind0):
        ch = [dict(nodes[start], kind='SEG')]
        prev, cur, kind = start, nxt, kind0
        while True:
            used.add(ekey(prev, cur))
            nd = dict(nodes[cur])
            if nd['kind'] != 'BEND' and kind in ('RED', 'VALV'):
                nd['kind'] = kind
            nd['via'] = kind
            ch.append(nd)
            cand = [(b, k) for b, k in adj[cur] if ekey(cur, b) not in used]
            if not cand:
                break
            if len(adj[cur]) > 2:   # tee: continue straight-through if possible
                din = unit(sub(nodes[cur]['xyz'], nodes[prev]['xyz']))
                best = min(cand, key=lambda bk: ang(din, sub(nodes[bk[0]]['xyz'], nodes[cur]['xyz'])))
                if ang(din, sub(nodes[best[0]]['xyz'], nodes[cur]['xyz'])) > 30:
                    break
                cand = [best]
            prev, (cur, kind) = cur, cand[0]
        chains.append(ch)

    order = sorted(adj, key=lambda k: (len(adj[k]) != 1, k))
    for k in order:
        for b, kind in adj[k]:
            if ekey(k, b) not in used:
                walk(k, b, kind)
    info = 'PCF mode: %d elbows written L, %d explicit R (L_TOL=%.3f rel)' % (nL, nX, l_tol)
    return chains, info
