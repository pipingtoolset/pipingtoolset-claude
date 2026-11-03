#!/usr/bin/env python3
"""plot_pcf.py - plan and two elevations of a PCF as an SVG, supports marked by NAME prefix.

Python 3.9+, standard library only (writes SVG; no plotting library needed).

Usage: python plot_pcf.py file.pcf out.svg "title" [--floors -1.25,20,38.33] [--width 1800]

Support markers by NAME (or SKEY) prefix: *ANC red square, *BASE green triangle, *RSR magenta
diamond, *BHGR / *BTRP orange (BIM hangers and trapezes), *HGR blue triangle, anything else grey.
Lines are weighted by bore. Units: PCF coordinates in inches, drawn in feet. Floors (ft) are
dashed horizontals on the two elevations. A floor stand floating 8 ft above its slab is obvious
in the picture and invisible in the counts; look at the drawing before handover.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcflib  # noqa: E402

VIEWS = [('plan X-Y', 0, 1), ('elevation Y-Z', 1, 2), ('elevation X-Z', 0, 2)]


def style(name):
    n = (name or '').upper()
    if 'ANC' in n:
        return 'square', 'red', 5
    if 'BASE' in n:
        return 'up', 'green', 5
    if 'RSR' in n:
        return 'diamond', 'magenta', 5
    if 'BHGR' in n or 'BTRP' in n:
        return 'down', 'darkorange', 4
    if 'HGR' in n:
        return 'down', 'blue', 3
    return 'circle', 'grey', 3


def marker(kind, x, y, s, colour):
    if kind == 'square':
        return '<rect x="%.1f" y="%.1f" width="%d" height="%d" fill="%s"/>' % (x - s, y - s, 2 * s, 2 * s, colour)
    if kind == 'up':
        return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>' % (x, y - s, x - s, y + s, x + s, y + s, colour)
    if kind == 'down':
        return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>' % (x, y + s, x - s, y - s, x + s, y - s, colour)
    if kind == 'diamond':
        return '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"/>' % (
            x, y - s, x + s, y, x, y + s, x - s, y, colour)
    return '<circle cx="%.1f" cy="%.1f" r="%d" fill="%s"/>' % (x, y, s, colour)


def segments(e):
    P = e['pts']
    if e['type'] == 'OLET':
        return [(P['CENTRE-POINT'], P['BRANCH1-POINT'])] if 'CENTRE-POINT' in P and 'BRANCH1-POINT' in P else []
    if 'BRANCH1-POINT' in P:
        c = P.get('CENTRE-POINT', P['END1'])
        return [(P['END1'], P['END2']), (c, P['BRANCH1-POINT'])]
    if e['type'] == 'BEND' and 'CENTRE-POINT' in P:
        return [(P['END1'], P['CENTRE-POINT']), (P['CENTRE-POINT'], P['END2'])]
    if 'END1' in P and 'END2' in P:
        return [(P['END1'], P['END2'])]
    return []


def render(pcf, title, floors=(), width=1800):
    recs = pcflib.parse(pcf, 'x')
    comps = [r for r in recs if r['type'] not in pcflib.GEOM_SKIP and r['type'] != 'SUPPORT' and r['pts']]
    sups = [r for r in recs if r['type'] == 'SUPPORT' and 'CO-ORDS' in r['pts']]
    segs = [(e, s, t) for e in comps for s, t in segments(e)]
    if not segs:
        raise SystemExit('plot_pcf: no drawable components in %s' % pcf)
    pts = [p for _, s, t in segs for p in (s, t)] + [s['pts']['CO-ORDS'] for s in sups]
    ft = lambda v: v / 12.0
    pw = width / 3.0
    margin = 40
    out = []
    panels_h = 0
    for col, (label, u, v) in enumerate(VIEWS):
        us = [ft(p[u]) for p in pts]
        vs = [ft(p[v]) for p in pts]
        if col > 0 and floors:
            vs += list(floors)
        umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
        span_u, span_v = max(umax - umin, 1e-6), max(vmax - vmin, 1e-6)
        scale = min((pw - 2 * margin) / span_u, (pw - 2 * margin) / span_v)
        ph = span_v * scale + 2 * margin + 20
        panels_h = max(panels_h, ph)
        ox = col * pw + margin
        X = lambda a: ox + (a - umin) * scale
        Y = lambda b: margin + 20 + (vmax - b) * scale
        out.append('<text x="%.1f" y="16" font-size="13" font-family="sans-serif">%s %s (ft)</text>' % (ox, title, label))
        if col > 0:
            for z in floors:
                out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="black" stroke-width="0.5" stroke-dasharray="6,4"/>'
                           % (ox, Y(z), ox + pw - 2 * margin, Y(z)))
        for e, s, t in segs:
            lw = 0.4 + (max(e['bore'].values()) if e['bore'] else 2) / 10.0
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#8c8c8c" stroke-width="%.2f"/>'
                       % (X(ft(s[u])), Y(ft(s[v])), X(ft(t[u])), Y(ft(t[v])), lw))
        for sp in sups:
            kind, colour, size = style(sp['attrs'].get('NAME', '') or sp['attrs'].get('SKEY', ''))
            p = sp['pts']['CO-ORDS']
            out.append(marker(kind, X(ft(p[u])), Y(ft(p[v])), size, colour))
    legend = ('<text x="%d" y="%.1f" font-size="11" font-family="sans-serif">red ANC, green BASE, magenta RSR, '
              'orange BIM hangers and trapezes, blue rule HGR, grey other; dashed = floors</text>' % (margin, panels_h + 14))
    head = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            '<rect width="100%%" height="100%%" fill="white"/>' % (width, panels_h + 30, width, panels_h + 30))
    return head + ''.join(out) + legend + '</svg>'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('pcf')
    ap.add_argument('svg')
    ap.add_argument('title')
    ap.add_argument('--floors', default='', help='comma-separated floor elevations in ft')
    ap.add_argument('--width', type=int, default=1800)
    a = ap.parse_args(argv)
    floors = [float(x) for x in a.floors.split(',') if x.strip()]
    svg = render(a.pcf, a.title, floors, a.width)
    with open(a.svg, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    print('wrote', a.svg)
    return 0


if __name__ == '__main__':
    sys.exit(main())
