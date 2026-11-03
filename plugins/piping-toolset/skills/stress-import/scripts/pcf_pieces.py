"""pcf_pieces - list the connected pieces of a pcf2caesar output PCF.

Usage: python pcf_pieces.py out.pcf
       python pcf_pieces.py --help

For each piece (largest first): component count, the bores present, the Z / X / Y extent in
feet and the supports on it counted by NAME prefix (the part of the NAME before the first
underscore, e.g. PTS-ANC). A piece with no ANC support floats in CAESAR II unless an equipment
end lands on it. Helper module of pcf2caesar.py: also importable (load_out).

Exit codes: 0 done, 2 usage error, 1 the file could not be read.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collections
import pcflib
from pcf_graph import components


def load_out(path):
    recs = pcflib.parse(path, 'out')
    comps = [r for r in recs if r['type'] != 'SUPPORT']
    sups = [r for r in recs if r['type'] == 'SUPPORT']
    return comps, sups


def main(argv):
    if len(argv) == 1 and argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if len(argv) != 1:
        sys.stderr.write('usage: python pcf_pieces.py out.pcf\n')
        return 2
    try:
        comps, sups = load_out(argv[0])
    except OSError as e:
        sys.stderr.write('cannot read %s\n' % e)
        return 1
    for c in comps:
        if c['type'] == 'TEE':
            c['pts'].pop('CENTRE-POINT', None)
        if c['type'] == 'OLET' and 'CENTRE-POINT' in c['pts']:
            c['pts']['HEADER'] = c['pts'].pop('CENTRE-POINT')
    cs = components([c for c in comps if pcflib.conn_points(c)])
    sk = {pcflib.key(s['pts']['CO-ORDS']): s for s in sups if 'CO-ORDS' in s['pts']}
    for i, c in enumerate(sorted(cs, key=len, reverse=True)):
        nodes = {pcflib.key(p) for e in c for p in pcflib.conn_points(e)}
        ss = [sk[k] for k in nodes if k in sk]
        kinds = collections.Counter(s['attrs'].get('NAME', '').split('_')[0] for s in ss)
        zs = [p[2] for e in c for p in pcflib.conn_points(e)]
        xs = [p[0] for e in c for p in pcflib.conn_points(e)]
        ys = [p[1] for e in c for p in pcflib.conn_points(e)]
        bores = sorted({b for e in c for b in e['bore'].values()})
        print(f'piece {i}: {len(c)} comps, bores {bores}, Z {min(zs)/12:.1f}..{max(zs)/12:.1f} ft, '
              f'X {min(xs)/12:.1f}..{max(xs)/12:.1f}, Y {min(ys)/12:.1f}..{max(ys)/12:.1f}  '
              f'supports {dict(kinds)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
