"""pcflib - parse Revit/PipeEX PCFs into element dicts (stdlib only).

Element dict: type, pts{END1,END2,BRANCH1..,CENTRE}, bore{...}, attrs{key:val}, revit_id, file, wall
"""
import re, math, collections

GEOM_SKIP = {'WELD', 'END-POSITION-OPEN', 'END-POSITION-CLOSED', 'END-CONNECTION-EQUIPMENT',
             'END-CONNECTION-PIPELINE', 'MATERIALS', 'ITEM-CODE'}

def parse(path, tag):
    recs, cur, header = [], None, True
    for raw in open(path, encoding='latin-1'):
        l = raw.rstrip('\r\n')
        if not l.strip():
            continue
        if not l.startswith(' '):
            kw = l.split()[0]
            if kw in ('ISOGEN-FILES', 'UNITS-BORE', 'UNITS-CO-ORDS', 'UNITS-WEIGHT', 'UNITS-BOLT-DIA',
                      'UNITS-BOLT-LENGTH', 'PIPELINE-REFERENCE'):
                cur = None
                continue
            cur = {'type': kw, 'pts': {}, 'bore': {}, 'attrs': {}, 'file': tag, 'raw': [l]}
            recs.append(cur)
            continue
        if cur is None:
            continue
        cur['raw'].append(l)
        s = l.strip().split()
        k = s[0]
        if k in ('END-POINT', 'BRANCH1-POINT', 'BRANCH2-POINT', 'BRANCH3-POINT', 'BRANCH4-POINT',
                 'BRANCH5-POINT', 'BRANCH6-POINT', 'CENTRE-POINT', 'CO-ORDS'):
            xyz = tuple(float(v) for v in s[1:4])
            if k == 'END-POINT':
                k = 'END1' if 'END1' not in cur['pts'] else 'END2'
            cur['pts'][k] = xyz
            if len(s) > 4:
                try:
                    cur['bore'][k] = float(s[4])
                except ValueError:
                    pass
            if len(s) > 5:
                cur.setdefault('endtype', {})[k] = s[5]
            if k == 'CO-ORDS' and len(s) > 5:
                cur['attrs']['ET'] = s[5]
        else:
            cur['attrs'][k] = ' '.join(s[1:])
            m = re.match(r'WALL-THICKNESS_([\d.]+)', ' '.join(s[1:]))
            if m:
                cur['wall'] = float(m.group(1))
    for r in recs:
        r['revit_id'] = r['attrs'].get('REVIT-ID', '')
    return recs

def key(p, q=0.0625):
    return tuple(round(c / q) for c in p)

def dist(a, b):
    return math.dist(a, b)

def conn_points(e):
    return [e['pts'][k] for k in e['pts'] if k != 'CENTRE' and k != 'CENTRE-POINT' and k != 'CO-ORDS']
