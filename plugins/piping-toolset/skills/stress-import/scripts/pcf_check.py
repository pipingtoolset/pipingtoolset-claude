#!/usr/bin/env python3
"""pcf_check.py - pre-import checks on a CAESAR II-bound PCF (stdlib only).

Usage: python pcf_check.py file.pcf [--span-table "NPS:ft,NPS:ft,..."] [--vert-max-ft FT] [--tol 0.0625]

Python 3.9+, standard library only. The span table and the vertical limit come from the PROJECT
SPECIFICATION (or the analyst); without them the span and vertical checks are skipped and said so.
No span table is embedded: never read one back from memory.

Reports, in this order (each is a known cause of a bad import or a review finding):
  pieces        connected pieces, with their anchors (ANCH SKEY or NAME containing ANC) and supports.
                A piece with no anchor will float in CAESAR unless an END-CONNECTION-EQUIPMENT lands on it.
  free ends     node that only one component touches (open ends CAESAR will not restrain)
  zero-length   components whose ends coincide (coincident nodes on import)
  tiny          components < 0.25 in (sliver pipes, 1/8 in gasket/weld rigids)
  support off   SUPPORT CO-ORDS not on any component node (restraint lost or on a spurious node)
  bend legs     BEND whose end-to-corner legs differ > 1/4 in (corner or radius wrong) or whose radius < 1.0D
                (Revit elbows routinely differ 1/16-1/8 in leg to leg; that is not flagged)
  bore jump     bore changes between adjacent components that are not reducers / tees / olets
  spans         horizontal runs between successive supports longer than the span table (ft, by NPS; --span-table)
  verticals     vertical runs between successive supports longer than --vert-max-ft
  crlf          line endings (CAESAR wants CRLF)
Exit code 1 if any hard check fails (pieces without anchor, zero-length, support off node).
"""
import sys, os, math, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcflib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pcf'); ap.add_argument('--tol', type=float, default=0.0625)
    ap.add_argument('--span-table', default='', help='"NPS:ft,..." from the project specification; omitted = spans not checked')
    ap.add_argument('--vert-max-ft', type=float, default=None, help='from the project specification; omitted = verticals not checked')
    a = ap.parse_args()
    span = sorted((float(k), float(v)) for k, v in (x.split(':') for x in a.span_table.split(',') if x.strip()))
    def allow(nps):
        if not span: return None
        for k, v in span:
            if nps <= k: return v
        return span[-1][1]
    raw = open(a.pcf, 'rb').read()
    crlf = raw.count(b'\r\n') == raw.count(b'\n')
    recs = pcflib.parse(a.pcf, 'x')
    comps = [r for r in recs if r['type'] not in pcflib.GEOM_SKIP and r['type'] != 'SUPPORT' and r['pts']]
    sups = [r for r in recs if r['type'] == 'SUPPORT']
    K = lambda p: pcflib.key(p, a.tol)
    def cpts(e):   # connection points: ends + branches, plus the header point of an OLET
        pts = pcflib.conn_points(e)
        if e['type'] == 'OLET' and 'CENTRE-POINT' in e['pts']: pts.append(e['pts']['CENTRE-POINT'])
        return pts
    hard = 0
    # graph
    par = {}
    def f(x):
        par.setdefault(x, x)
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    deg = collections.Counter(); adj = collections.defaultdict(list)
    for e in comps:
        P = e['pts']
        if e['type'] == 'OLET':
            segs = [(P['CENTRE-POINT'], P['BRANCH1-POINT'])]
        elif e['type'].startswith('TEE') or 'BRANCH1-POINT' in P:
            c = P.get('CENTRE-POINT', P['END1'])
            segs = [(P['END1'], c), (c, P['END2']), (c, P['BRANCH1-POINT'])]
        elif e['type'] == 'BEND':
            segs = [(P['END1'], P['CENTRE-POINT']), (P['CENTRE-POINT'], P['END2'])]
        else:
            segs = [(P['END1'], P['END2'])]
        e['segs'] = segs
        e['len'] = sum(math.dist(s, t) for s, t in segs)
        ks = [K(p) for p in cpts(e)]
        for k in ks: deg[k] += 1; f(k)
        for k in ks[1:]: par[f(ks[0])] = f(k)
        links = [(K(s), K(t)) for s, t in segs] if e['type'] != 'BEND' else [(K(P['END1']), K(P['END2']))]
        for s, t in links:
            if s != t:
                adj[s].append((t, e)); adj[t].append((s, e))
    supk = {}
    for s in sups:
        supk.setdefault(K(s['pts']['CO-ORDS']), []).append(s)
    nodes = set(deg)
    pieces = collections.defaultdict(list)
    for e in comps: pieces[f(K(cpts(e)[0]))].append(e)
    print(f'{a.pcf}: {len(comps)} components, {len(sups)} supports, {len(nodes)} nodes, CRLF={crlf}')
    print(f'\n== pieces ({len(pieces)})')
    for i, (root, es) in enumerate(sorted(pieces.items(), key=lambda kv: -len(kv[1]))):
        ns = {K(p) for e in es for p in cpts(e)}
        ss = [s for n in ns for s in supk.get(n, [])]
        anc = [s for s in ss if s['attrs'].get('SKEY', '') == 'ANCH' or 'ANC' in s['attrs'].get('NAME', '')]
        kinds = collections.Counter(s['attrs'].get('NAME', s['attrs'].get('SKEY', '?')).split('_')[0] for s in ss)
        zs = [p[2] / 12 for e in es for p in cpts(e)]
        flag = '' if anc else '   <-- NO ANCHOR'
        if not anc: hard += 1
        print(f'  piece {i}: {len(es)} comps, Z {min(zs):.1f}..{max(zs):.1f} ft, supports {dict(kinds)}{flag}')
    free = [n for n, d in deg.items() if d == 1]
    print(f'\n== free ends ({len(free)})')
    for n in free[:40]:
        e = adj[n][0][1]
        print(f"  {tuple(round(c * a.tol / 12, 2) for c in n)} ft  {e['type']} {e['attrs'].get('ITEM-DESCRIPTION', '')[:50]}")
    zero = [e for e in comps if e['type'] != 'OLET' and e['len'] < 1e-6]
    tiny = [e for e in comps if e['type'] != 'OLET' and 1e-6 <= e['len'] < 0.25]
    print(f'\n== zero-length ({len(zero)}), tiny < 0.25 in ({len(tiny)})')
    hard += len(zero)
    for e in zero + tiny: print(f"  {e['type']} {pcflib.conn_points(e)[0]} {e['attrs'].get('ITEM-DESCRIPTION','')[:50]}")
    off = [s for k, ss in supk.items() if k not in nodes for s in ss]
    print(f'\n== supports off node ({len(off)})'); hard += len(off)
    for s in off: print(f"  {s['attrs'].get('NAME','')} {s['pts']['CO-ORDS']}")
    print('\n== bends')
    for e in comps:
        if e['type'] != 'BEND': continue
        P = e['pts']; l1 = math.dist(P['END1'], P['CENTRE-POINT']); l2 = math.dist(P['END2'], P['CENTRE-POINT'])
        R = float(e['attrs'].get('BEND-RADIUS', 0) or 0); nps = max(e['bore'].values())
        if abs(l1 - l2) > 0.25 or (R and R < 1.0 * nps):   # Revit elbows differ by 1/16-1/8 in leg to leg; flag only > 1/4 in
            print(f"  legs {l1:.3f}/{l2:.3f} R {R} NPS {nps} at {P['CENTRE-POINT']}")
    print('\n== bore jumps')
    for n, lst in adj.items():
        es = {id(e): e for _, e in lst}.values()
        bores = {max(e['bore'].values()) for e in es if e['bore'] and e['type'] not in ('REDUCER-CONCENTRIC', 'REDUCER-ECCENTRIC', 'OLET') and not e['type'].startswith('TEE')}
        if len(bores) > 1: print(f'  {tuple(round(c * a.tol / 12, 2) for c in n)} ft bores {sorted(bores)}')
    # spans: walk from each support node along degree-2 chains to the next support
    print('\n== spans over the table / verticals over max')
    if not span: print('  spans not checked: give --span-table from the project specification')
    if a.vert_max_ft is None: print('  verticals not checked: give --vert-max-ft from the project specification')
    # shortest path from every support to its neighbouring supports (Dijkstra, not expanded past a support),
    # so a span through a tee, a branch takeoff or a loop is measured the way a reviewer would walk it
    import heapq
    seen = set(); spans_found = []
    XYZ = {}
    for e in comps:
        for p in cpts(e): XYZ[K(p)] = p
        for sg in e['segs']:
            for p in sg: XYZ.setdefault(K(p), p)
    # node graph with lengths, tee centres and bend corners as intermediate nodes
    G = collections.defaultdict(list)
    for e in comps:
        for s_, t_ in e['segs']:
            ks, kt = K(s_), K(t_); L = math.dist(s_, t_)
            if ks != kt: G[ks].append((kt, L)); G[kt].append((ks, L))
    for s0 in supk:
        if s0 not in G: continue
        dist = {s0: 0.0}; prevn = {}; pq = [(0.0, s0)]
        while pq:
            d, n = heapq.heappop(pq)
            if d > dist.get(n, 1e18): continue
            if n in supk and n != s0: continue
            for m, L in G[n]:
                nd = d + L
                if nd < dist.get(m, 1e18): dist[m] = nd; prevn[m] = n; heapq.heappush(pq, (nd, m))
        for n, d in dist.items():
            if n == s0 or n not in supk: continue
            key = frozenset([s0, n])
            if key in seen: continue
            seen.add(key)
            path = [n]
            while path[-1] != s0: path.append(prevn[path[-1]])
            pts = [XYZ[k] for k in path]
            dz = max(p[2] for p in pts) - min(p[2] for p in pts)
            dxy = max(math.dist(p[:2], pts[0][:2]) for p in pts)
            nps = max((max(e['bore'].values()) for e in comps if e['bore'] and any(K(p) in path for p in cpts(e))), default=0)
            at = tuple(round(c / 12, 2) for c in XYZ[s0])
            spans_found.append((d / 12, nps, dz < 1.0, at))
            if dz < 1.0 and span and d / 12 > allow(nps):
                print(f'  horizontal {d/12:.1f} ft > {allow(nps)} ft for NPS {nps} from {at}')
            elif dxy < 1.0 and a.vert_max_ft is not None and d / 12 > a.vert_max_ft:
                print(f'  vertical {d/12:.1f} ft > {a.vert_max_ft} ft from {at}')
    top = sorted((x for x in spans_found if x[2]), reverse=True)[:5]
    print('  longest horizontal spans found (ft, NPS, from):', [(round(l, 1), n, at) for l, n, _, at in top])
    print(f'\nHARD FAILURES: {hard}')
    sys.exit(1 if hard else 0)

if __name__ == '__main__':
    main()
