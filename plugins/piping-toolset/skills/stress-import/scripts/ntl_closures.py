"""List loop-closure points in an AutoPIPE .ntl: a point name that starts a SEG and is also the
target of a later RUN/VALV/BEND/RED card. Report what components sit at each closure.

Usage: python ntl_closures.py file.ntl [more.ntl ...]
       python ntl_closures.py --help

Output, per file: '## name closures: N', then one line per closure with the point name, the card
that starts the SEG, the card that closes it and the component cards (FLA, TEE, VALV, BEND, RED)
found at that point. A closure with FLA or VALV is what fix_closures.py moves.

Exit codes: 0 done, 2 usage error.
"""
import os
import sys, collections
def closures(fn):
    L = open(fn, errors="ignore").read().replace("\r", "").split("\n")
    seg = {}; tgt = collections.defaultdict(list); ann = collections.defaultdict(set)
    for i, l in enumerate(L):
        t = l[:4].strip(); f = l.split()
        if t == "SEG": seg[f[1]] = i
        elif t in ("RUN", "VALV", "BEND", "RED") and len(f) > 1:
            if f[1] in seg and i > seg[f[1]]: tgt[f[1]].append((t, i))
        if t in ("FLA", "TEE", "VALV", "BEND", "RED") and len(f) > 1: ann[f[1]].add(t)
    out = []
    for p, hits in tgt.items():
        i = seg[p]; first = next((L[k][:4].strip() for k in range(i + 1, i + 6) if L[k][:4].strip() in ("RUN", "VALV", "BEND", "RED")), None)
        out.append((p, first, sorted(ann[p]), hits[0][0]))
    return out
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write("usage: python ntl_closures.py file.ntl [more.ntl ...]\n")
        raise SystemExit(2)
    if sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0)
    for fn in sys.argv[1:]:
        c = closures(fn); print("##", os.path.basename(fn), "closures:", len(c))
        for r in c: print("   point", r[0], "| SEG starts with", r[1], "| closed by", r[3], "| components at point", r[2])
