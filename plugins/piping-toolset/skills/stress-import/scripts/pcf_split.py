"""pcf_split - split the merged Revit elements into the job's analysis models.

Helper for pcf2caesar.py (import it; it has no command line).

split_models(job, base) returns (models, chillers, ends, straddle):
  models     {model name: [elements]} for elements wholly inside the model box. A connected piece
             goes to the model whose PCF tags exclusively own most of its elements (job key
             "models" = {name: [tags]}; default one model holding every tag). A piece that no
             tag owns goes by bore when the job gives "unassigned_by_bore"
             ({"max_bore_in": n, "le": model, "gt": model}), else to the first model.
  chillers   UNDEFINED equipment-body elements whose first bore equals the job's
             "chiller_body_bore_in" (none when the key is absent); removed from the models.
  ends       END-* records (open ends, END-CONNECTION-EQUIPMENT ...).
  straddle   elements that cross the box edge (their loose ends become cut anchors).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collections
import pcflib
from pcf_graph import components
from pcf_union import load, box, inbox


def split_models(job, base):
    E, ends = load(job, base)
    bx = box(job)
    cbore = job.get('chiller_body_bore_in')

    def is_chiller(e):
        return cbore is not None and e['type'] == 'UNDEFINED' and e['bore'].get('END1') == float(cbore)

    cfg = job.get('models') or {job.get('model', 'ALL'): list(job['pcf_files'])}
    tag_model = {t: m for m, tags in cfg.items() for t in tags}
    names = list(cfg)
    inb = [e for e in E if all(inbox(p, bx) for p in pcflib.conn_points(e))]
    straddle = [e for e in E if any(inbox(p, bx) for p in pcflib.conn_points(e))
                and not all(inbox(p, bx) for p in pcflib.conn_points(e))]
    chillers = [e for e in inb if is_chiller(e)]
    rest = [e for e in inb if not is_chiller(e)]
    models = {m: [] for m in names}
    rule = job.get('unassigned_by_bore')
    for c in components(rest):
        excl = collections.Counter(next(iter(e['files'])) for e in c if len(e['files']) == 1)
        votes = collections.Counter()
        for tag, n in excl.items():
            if tag in tag_model:
                votes[tag_model[tag]] += n
        if not votes:
            if rule:
                b = max(e['bore'].get('END1', 0) for e in c)
                m = rule['le'] if b <= float(rule['max_bore_in']) else rule['gt']
            else:
                m = names[0]
        else:
            m = max(names, key=lambda n: votes[n])
        if m not in models:
            raise ValueError('unassigned_by_bore names a model that is not in "models": %r' % m)
        for e in c:
            e['model'] = m
        models[m].extend(c)
    return models, chillers, ends, straddle
