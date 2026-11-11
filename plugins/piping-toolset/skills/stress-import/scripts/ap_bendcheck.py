#!/usr/bin/env python3
"""ap_bendcheck.py - predict AutoPIPE E726-15 (undefined bend) and W726-8 (kink)
from an AutoPIPE NTL file (Bentley PCF Translator output) or from the source PCF
(emulating the translator; needs ap_pcf.py alongside).

usage: python ap_bendcheck.py file.ntl|file.pcf [--tol IN] [--kink DEG] [--verbose]

Run it on the prepared PCF before translating, and again on the .ntl the translator wrote.
Output: 'E726-15 undefined bends: N' with one line per bend (point, position in inches, how
many inches short) and 'W726-8 kinks > X deg: N' with one line per point. --verbose adds
every bend margin, worst first.

Exit codes: 0 the check ran (finding bends or kinks does not change it; read the counts),
2 usage error (argparse), 1 the file could not be read.

Calibrated against the error lists AutoPIPE reported for two earlier imports (exact match
in both modes):
 * T = R*tan(theta/2), theta from prev point -> TIP -> next point.
 * E726-15 '<bend> N' when T > (distance TIP->previous point) + TOL or
   T > (distance TIP->next point) + TOL; if the neighbour is itself a BEND, its
   T is deducted. Every written point obstructs (pipe ends, elbow ends incl. the
   'xxxF' far end, flange points, valve/reducer ends, tee points, supports).
   TOL window from data: 0.0061 < TOL < 0.027 in; default 0.01 in.
 * W726-8: for each undefined bend, both neighbour points are reported (angle
   not modelled -> nan) unless the neighbour is a bend or its other element is a
   reducer/valve. Elsewhere: angle between adjacent straight elements (bend
   tangent points used) > KINK deg, exempt where either element is a
   reducer or valve. 0.7-0.8 deg cases were NOT reported, 2.4 deg was -> 1.0 deg.
 * PCF mode: radius written 'L' when |R/(1.5*NPS)-1| <= 2.5% (window 1.85%..3.11%),
   R = mean(T1,T2)/tan(theta/2), TIP = CENTRE-POINT.
"""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python -I

TOL_IN = 0.01         # see report; set by calibration
KINK_DEG = 1.0        # calibrated: 0.7-0.8 deg not reported, 2.4 deg reported


def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def mul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def norm(a): return math.sqrt(a[0]**2+a[1]**2+a[2]**2)
def unit(a):
    n = norm(a)
    return (a[0]/n, a[1]/n, a[2]/n) if n > 1e-12 else (0.0, 0.0, 0.0)
def ang(u, v):
    u, v = unit(u), unit(v)
    d = max(-1.0, min(1.0, u[0]*v[0]+u[1]*v[1]+u[2]*v[2]))
    return math.degrees(math.acos(d))


def fnum(s):
    s = s.strip()
    return float(s) if s else 0.0


# ---------------------------------------------------------------- NTL parser
def parse_ntl(path):
    """returns list of chains; chain = list of dict(name, xyz(in), kind, R, nps)"""
    chains, cur, coords = [], None, {}
    sec_nps, nps = {}, None
    for line in open(path, errors='replace'):
        line = line.rstrip('\n')
        key = line[:4].strip()
        if key in ('UUID', 'RVER') or line.startswith('    *'):
            continue
        if key == 'PIPE':
            nm = line[5:20].split()[0]
            m = re.match(r'([\d.]+)', nm)
            if nm not in sec_nps:
                sec_nps[nm] = float(m.group(1)) if m else None
            nps = sec_nps[nm]
            continue
        if key == 'SEG':
            name = line[5:20].split()[0]
            xyz = tuple(fnum(line[c:c+10])*12.0 for c in (20, 30, 40))
            if name in coords:
                xyz = coords[name]
            cur = [dict(name=name, xyz=xyz, kind='SEG', R=None, nps=nps)]
            chains.append(cur)
            coords[name] = xyz
            continue
        if key in ('RUN', 'BEND', 'RED', 'VALV') and cur is not None:
            name = line[5:20].split()[0]
            d = tuple(fnum(line[c:c+10])*12.0 for c in (20, 30, 40))
            xyz = add(cur[-1]['xyz'], d)
            R = None
            if key == 'BEND':
                rf = line[50:60].strip()
                R = 'L' if rf.startswith('L') else float(rf)
            p = dict(name=name, xyz=xyz, kind=key, R=R, nps=nps)
            cur.append(p)
            coords.setdefault(name, xyz)
            continue
        if key == '***':
            cur = None
    for ch in chains:
        for p in ch:
            if p['R'] == 'L':
                p['R'] = 1.5*p['nps']
    return chains


# ---------------------------------------------------------------- analysis
def analyse(chains, tol=TOL_IN, kink=KINK_DEG):
    """returns (undefined list, kinks list, margins list)
    undefined: (label, xyz, margin) ; margin = room - T (in), <0 => error"""
    und, kinks, margins = [], [], []
    for ch in chains:
        n = len(ch)
        # sweep 1: tangent lengths
        T = [0.0]*n
        th = [0.0]*n
        for i, p in enumerate(ch):
            if p['kind'] == 'BEND' and 0 < i < n-1:
                a = sub(p['xyz'], ch[i-1]['xyz'])
                b = sub(ch[i+1]['xyz'], p['xyz'])
                th[i] = ang(a, b)
                T[i] = p['R']*math.tan(math.radians(th[i])/2.0)
        # sweep 2: room
        for i, p in enumerate(ch):
            if p['kind'] != 'BEND' or not (0 < i < n-1):
                continue
            back = norm(sub(p['xyz'], ch[i-1]['xyz']))
            fwd = norm(sub(ch[i+1]['xyz'], p['xyz']))
            if ch[i-1]['kind'] == 'BEND':
                back -= T[i-1]
            if ch[i+1]['kind'] == 'BEND':
                fwd -= T[i+1]
            mb, mf = back - T[i], fwd - T[i]
            m = min(mb, mf)
            margins.append((p['name'], p['xyz'], T[i], th[i], p['R'], mb, mf))
            if m < -tol:
                und.append((p['name'] + ' N', p['xyz'], m))
        # kinks at non-bend interior points, using bend tangent points
        eff = []
        for i, p in enumerate(ch):
            if p['kind'] == 'BEND' and 0 < i < n-1 and th[i] > 1e-6:
                ui = unit(sub(p['xyz'], ch[i-1]['xyz']))
                uo = unit(sub(ch[i+1]['xyz'], p['xyz']))
                eff.append(('B', p['name'], sub(p['xyz'], mul(ui, T[i])), add(p['xyz'], mul(uo, T[i]))))
            else:
                eff.append(('P', p['name'], p['xyz'], p['xyz']))
        undset = {u[0][:-2] for u in und}
        # kind of the element ending at node j (reducer / valve bodies are exempt)
        ek = lambda j: ch[j].get('via') or ch[j]['kind']
        exempt = lambda j: ek(j) in ('RED', 'VALV')
        exempt_seg = lambda j, o: exempt(max(j, o))   # element between nodes j,o
        conflict, skip = set(), set()
        for i, p in enumerate(ch):
            if p['kind'] != 'BEND' or not (0 < i < n-1):
                continue
            if p['name'] in undset:
                # AutoPIPE kinks both neighbours of an undefined bend,
                # unless that neighbour's other side is a reducer/valve
                for j, o in ((i-1, i-2), (i+1, i+2)):
                    if ch[j]['kind'] == 'BEND' or exempt(j):
                        continue
                    if 0 <= o < n and exempt_seg(j, o):
                        continue
                    conflict.add(j)
            skip.update((i-1, i+1))   # neighbours of bends: only via conflict
        for i in sorted(conflict):
            kinks.append((ch[i]['name'], ch[i]['xyz'], float('nan')))
        for i in range(1, n-1):
            if eff[i][0] != 'P' or i in conflict:
                continue
            a = sub(eff[i][2], eff[i-1][3])
            b = sub(eff[i+1][2], eff[i][2])
            if i in skip and (norm(a) < 0.1 or norm(b) < 0.1):
                continue
            # eccentric reducers / valve bodies are exempt in AutoPIPE
            if exempt(i) or exempt(i+1):
                continue
            prev_pt = eff[i-1][3]
            next_pt = eff[i+1][2]
            a = sub(eff[i][2], prev_pt)
            b = sub(next_pt, eff[i][2])
            if norm(a) < 1e-6 or norm(b) < 1e-6:
                continue
            k = ang(a, b)
            if k > kink:
                kinks.append((eff[i][1], ch[i]['xyz'], k))
    return und, kinks, margins


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--tol', type=float, default=TOL_IN)
    ap.add_argument('--kink', type=float, default=KINK_DEG)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args(argv)
    if a.file.lower().endswith('.pcf'):
        import ap_pcf
        chains, info = ap_pcf.pcf_chains(a.file)
        print(info)
    else:
        chains = parse_ntl(a.file)
    und, kinks, margins = analyse(chains, a.tol, a.kink)
    print('E726-15 undefined bends: %d' % len(und))
    for nm, xyz, m in und:
        print('  %-8s at (%.2f, %.2f, %.2f) in  short by %.3f in' % (nm, xyz[0], xyz[1], xyz[2], -m))
    print('W726-8 kinks > %.2f deg: %d' % (a.kink, len(kinks)))
    for nm, xyz, k in kinks:
        print('  %-8s %6.1f deg at (%.2f, %.2f, %.2f) in' % (nm, k, xyz[0], xyz[1], xyz[2]))
    if a.verbose:
        print('bend margins (in): name T theta R back fwd')
        for nm, xyz, T, th, R, mb, mf in sorted(margins, key=lambda r: min(r[5], r[6])):
            print('  %-8s T=%.3f th=%.2f R=%.3f back=%.4f fwd=%.4f' % (nm, T, th, R, mb, mf))


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except OSError as e:
        sys.stderr.write('cannot read %s\n' % e)
        sys.exit(1)
