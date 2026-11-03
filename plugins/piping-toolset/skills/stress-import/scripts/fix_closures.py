"""fix_closures.py - move AutoPIPE loop closures off flange/valve points in a PCF-Translator .ntl.

AutoPIPE 2025/2026 treats a loop-closure point (a point that starts a SEG and is later re-entered by
a RUN card) as a junction. When that point also carries a flange and the start of a valve, AutoPIPE
reports E751-1 'Invalid tee ... SIF not calculated' and then crashes (0xc0000005). Seen on a
loop closed at a flanged valve.

Fix: the closing segment ends ... RUN Q / RUN P + FLA P. Move the 'RUN P + FLA P' block to the start
of the opening segment and start that segment at Q instead (coords of P minus the RUN P delta). The
loop then closes at Q, a plain pipe point. Geometry, components and properties are unchanged.

Usage: python fix_closures.py in.ntl out.ntl
       python fix_closures.py --help

Reads the .ntl as Latin-1 with CRLF line ends (what the PCF Translator writes) and writes it back
the same way. Prints one 'closure moved' line per fix and 'fixed N'. Stops after 50 fixes.
Run ntl_closures.py first to see which points are loop closures.

Exit codes: 0 done (also when nothing needed fixing), 1 the 50-fix safety stop or an input that
does not match the expected card layout, 2 usage error.
"""
import sys
STOP = ("***", "RUN ", "SEG ", "VALV", "BEND", "RED ", "TEE ", "VSTP", "ANC ", "RVER 2.3")

def find_one(L):
    segs = {l.split()[1]: i for i, l in enumerate(L) if l.startswith("SEG ")}
    ann = {}
    for l in L:
        if l[:4].strip() in ("FLA", "VALV", "TEE") and len(l.split()) > 1:
            ann.setdefault(l.split()[1], set()).add(l[:4].strip())
    for P, s in segs.items():
        c = next((i for i in range(s + 1, len(L)) if L[i].startswith("RUN ") and L[i].split()[1] == P), None)
        if c is not None and ({"FLA", "VALV"} & ann.get(P, set())):
            return P, s, c
    return None

def fix(L, P, s, c):
    q = next(i for i in range(c - 1, 0, -1) if L[i].startswith("RUN "))
    Q = L[q].split()[1]
    e = c + 1
    while e < len(L) and not L[e].startswith(STOP):
        e += 1
    block = L[c:e]
    d = [float(x) for x in L[c].split()[2:5]]
    sp = L[s].split()[2:5]
    pQ = [float(sp[k]) - d[k] for k in range(3)]
    f = L[s].split()
    newseg = L[s].replace(f[1], Q, 1)
    pos = newseg.index(Q) + len(Q)
    for old, new in zip(sp, pQ):
        # replace each coordinate where it sits, scanning left to right (replacing by value would
        # hit the wrong field when two coordinates print the same, e.g. 0.000 and 0.000)
        i = newseg.index(old, pos)
        txt = f"{new:.3f}".rjust(len(old))
        newseg = newseg[:i] + txt + newseg[i + len(old):]
        pos = i + len(txt)
    ins = s + 1
    if L[ins].startswith("PIPE "):
        ins += 1
    assert c > ins, "closing tail must come after the opening SEG"
    return L[:s] + [newseg] + L[s + 1:ins] + block + L[ins:c] + L[e:], (P, Q, [round(x, 3) for x in pQ], len(block))

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0)
    if len(sys.argv) != 3:
        sys.stderr.write("usage: python fix_closures.py in.ntl out.ntl\n")
        raise SystemExit(2)
    L = open(sys.argv[1], "rb").read().decode("latin-1").split("\r\n")
    log = []
    while (h := find_one(L)):
        L, info = fix(L, *h)
        log.append(info)
        if len(log) > 50:
            raise SystemExit("too many fixes - stop")
    open(sys.argv[2], "wb").write("\r\n".join(L).encode("latin-1"))
    for f in log:
        print(f"closure moved: {f[0]} -> {f[1]} at {f[2]} (moved {f[3]} lines)")
    print("fixed", len(log))
