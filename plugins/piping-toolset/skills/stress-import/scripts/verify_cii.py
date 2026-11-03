#!/usr/bin/env python3
"""verify_cii.py - independent check of fix_cii.py output against the original neutral file.
Python 3.9+, standard library only. Exit 0 on PASS, 1 on FAILED.
Usage: python verify_cii.py original.CII fixed.CII node_map.csv [lines.json]
PASS means: same elements in the same order with the same geometry, walls and aux pointers;
every node renumbered per the map; restraint nodes/types/mu/tags kept (code 6 -> 1 allowed);
SIF and bend nodes valid; unchanged sections byte-identical; T1/P1/fluid as configured.
"""
import sys, csv, json, collections, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cii import *
a, b = sys.argv[1], sys.argv[2]
cfg = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else {}
SA, SB = sections(a), sections(b)
EA, EB = elements(SA), elements(SB)
m = {int(r['old_node']): int(r['new_node']) for r in csv.DictReader(open(sys.argv[3]))}
ok = True
def chk(c, msg):
    global ok
    if not c: ok = False; print('FAIL', msg)
chk(len(EA) == len(EB), 'element count')
t1s = {v['t1'] for v in cfg.get('lines', {}).values() if 't1' in v}
for x, y in zip(EA, EB):
    chk(m[int(x['frm'])] == y['frm'] and m[int(x['to'])] == y['to'], f"nodes {x['frm']}")
    chk(all(abs(p - q) < 1e-9 for p, q in zip(x['r'][2:7], y['r'][2:7])), f"geometry {x['frm']}")
    chk(x['ptr'] == y['ptr'], 'aux pointers')
    if t1s: chk(y['t1'] in t1s, f"T1 {y['t1']}")
    if cfg.get('p1'): chk(y['p1'] == cfg['p1'], 'P1')
    if cfg.get('insul_in'): chk(y['ins'] == cfg['insul_in'], 'insulation')
    chk(abs(y['r'][31] - cfg.get('fluid_den_lb_in3', 62.4 / 1728)) < 1e-6, 'fluid density')
RA, RB = restraints(SA), restraints(SB)
for ra, rb in zip(RA, RB):
    for p, q in zip(ra, rb):
        chk(m[int(p['node'])] == q['node'], 'restraint node')
        chk((p['type'] == 6 and q['type'] == 1) or p['type'] == q['type'], 'restraint type')
        chk(p['mu'] == q['mu'] and p['stif'] == q['stif'], 'restraint mu/stiffness')
        chk(p['tag'] == q['tag'], 'restraint tag kept')
nodesB = {e['frm'] for e in EB} | {e['to'] for e in EB}
chk(all(x['node'] in nodesB for r in RB for x in r), 'every restraint on an element node')
vals = []
for ln in SB['SIF&TEES']: vals += reals(ln)
chk(all(vals[i] in nodesB for i in range(0, len(vals), 42) if vals[i]), 'SIF nodes')
B = SB['BEND']; bends = [reals(B[i]) + reals(B[i+1]) + reals(B[i+2]) for i in range(0, len(B), 3)]
for e in EB:
    if e['ptr'][0]:
        v = bends[e['ptr'][0] - 1]
        for fi in (3, 5, 7):
            if v[fi]: chk(e['frm'] < v[fi] < e['to'] and v[fi] not in nodesB, f"bend node {v[fi]}")
for sec in ('VERSION', 'CONTROL', 'RIGID', 'ALLOWBLS', 'REDUCERS', 'MISCEL_1', 'UNITS'):
    chk(SA[sec] == SB[sec], f'{sec} changed')
print('restraint types', dict(collections.Counter(x['type'] for r in RB for x in r)),
      '| nodes', int(min(nodesB)), '-', int(max(nodesB)), len(nodesB),
      '| T1', dict(collections.Counter(e['t1'] for e in EB)))
print('PASS' if ok else 'FAILED')
sys.exit(0 if ok else 1)
