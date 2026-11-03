"""pcf_graph - connectivity helpers for pcf2caesar.py (import it; it has no command line).

components(elements) groups elements that share an end point into connected pieces (a list of
lists); degree(elements) counts how many elements touch each node. Nodes are pcflib.key() grid
keys, so end points within a sixteenth of an inch are one node.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collections
import pcflib


def components(es):
    par = {}

    def f(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for e in es:
        ks = [pcflib.key(p) for p in pcflib.conn_points(e)]
        for k in ks:
            f(k)
        for k in ks[1:]:
            par[f(ks[0])] = f(k)
    comp = collections.defaultdict(list)
    for e in es:
        comp[f(pcflib.key(pcflib.conn_points(e)[0]))].append(e)
    return list(comp.values())


def degree(es):
    d = collections.Counter()
    for e in es:
        for p in pcflib.conn_points(e):
            d[pcflib.key(p)] += 1
    return d
