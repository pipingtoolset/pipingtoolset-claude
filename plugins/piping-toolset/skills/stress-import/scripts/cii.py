"""Minimal CAESAR II neutral (.CII v5) reader: elements + aux sections."""
import re, sys, math, collections
NUM = re.compile(r'-?\d+\.\d+E[+-]\d+')
def sections(path):
    secs, cur = {}, None
    for ln in open(path, encoding='latin-1'):
        if ln.startswith('#$'):
            cur = ln[2:].strip(); secs[cur] = []
        elif cur: secs[cur].append(ln.rstrip('\n'))
    return secs
def reals(line): return [float(x) for x in NUM.findall(line)]
def ints(line): return [int(x) for x in line.split()]
def elements(secs):
    L = secs['ELEMENTS']; out = []; i = 0
    while i < len(L):
        r = []
        for k in range(9): r += reals(L[i + k])
        names = (L[i + 9].strip(), L[i + 10].strip())
        p = ints(L[i + 12]) + ints(L[i + 13]) + ints(L[i + 14])
        out.append(dict(frm=r[0], to=r[1], dx=r[2], dy=r[3], dz=r[4], od=r[5], wt=r[6], ins=r[7], t1=r[9], p1=r[18], r=r, ptr=p, names=names))
        i += 15
    return out
def restraints(secs):
    L = secs['RESTRANT']; recs = []
    for i in range(0, len(L), 24):
        slots = []
        for k in range(6):
            a = reals(L[i+4*k]); b = reals(L[i+4*k+1])
            if a[0] or a[1]:
                slots.append(dict(node=a[0], type=a[1], stif=a[2], gap=a[3], mu=a[4], cnode=a[5], dir=b[:3], tag=L[i+4*k+2].strip(), guid=L[i+4*k+3].strip()))
        recs.append(slots)
    return recs
