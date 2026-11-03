"""pcf_union - load and de-duplicate the Revit system PCFs named in a pcf2caesar job.

Helper for pcf2caesar.py (import it; it has no command line).

load(job, base) reads every file in the job's "pcf_files" ({tag: file name}, relative to the
job's "pcf_dir" and then to the job file's folder), skips WELD / END-* records (keeping the
END-* ones in the second return value), and merges elements that appear in more than one file
(same REVIT-ID, type and end points) into one element whose 'files' set holds every tag.
Records with no end points (a SUPPORT record has only CO-ORDS) are skipped with a logged warning.
box(job) turns the job's "box_ft" into inches; inbox(p, box) tests a point against it.
"""
import collections
import logging
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcflib


def box(job):
    """Job 'box_ft' -> dict of limits in inches, or None. Accepts [xmin, xmax, ymin, ymax] or a
    dict with xmin/xmax/ymin/ymax and optionally zmin/zmax (all ft)."""
    b = job.get('box_ft')
    if not b:
        return None
    if isinstance(b, (list, tuple)):
        if len(b) != 4:
            raise ValueError('box_ft list must be [xmin, xmax, ymin, ymax]')
        b = dict(zip(('xmin', 'xmax', 'ymin', 'ymax'), b))
    inf = 1e9
    return {k: float(b.get(k, d)) * 12 for k, d in (('xmin', -inf), ('xmax', inf), ('ymin', -inf),
                                                     ('ymax', inf), ('zmin', -inf), ('zmax', inf))}


def inbox(p, bx):
    if bx is None:
        return True
    return (bx['xmin'] <= p[0] <= bx['xmax'] and bx['ymin'] <= p[1] <= bx['ymax']
            and bx['zmin'] <= p[2] <= bx['zmax'])


def load(job, base):
    files = job.get('pcf_files')
    if not files:
        raise KeyError("pcf_files (job key {tag: file name})")
    folder = os.path.join(base, job.get('pcf_dir', ''))
    elems = {}
    ends = []
    skipped = collections.Counter()
    for tag, name in files.items():
        for e in pcflib.parse(os.path.join(folder, name), tag):
            if e['type'] in pcflib.GEOM_SKIP:
                if e['type'].startswith('END-'):
                    ends.append(e)
                continue
            if not pcflib.conn_points(e):
                skipped[e['type']] += 1          # e.g. a SUPPORT record: it has CO-ORDS, no end points
                continue
            pts = tuple(sorted(pcflib.key(p, 0.01) for p in pcflib.conn_points(e)))
            k = (e['revit_id'], e['type'], pts)
            if k in elems:
                elems[k]['files'].add(tag)
            else:
                e['files'] = {tag}
                elems[k] = e
    if skipped:
        logging.getLogger('pcf2caesar').warning(
            'skipped %d record(s) without connection points (supports in the export are not used): %s',
            sum(skipped.values()), dict(skipped))
    return list(elems.values()), ends
