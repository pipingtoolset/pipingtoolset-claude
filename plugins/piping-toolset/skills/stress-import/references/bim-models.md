# Routes C and D: Navisworks NWC and IFC fabrication models as support and geometry sources

Two different things come out of a BIM model: **supports** (hangers, trapezes, stands, riser
clamps that Revit never puts in a PCF) and, when no PCF of the governing model exists, **the
centreline itself**. The NWC is good for the first; an IFC export of the fabrication model can
do both. Both give a layout to analyse, never a support design.

## Route C: Navisworks NWC (supports and in-line items), `scripts/nwc_supports.py`

An `.nwc` is a chain of zlib-deflated chunks. Inflated, each Revit element carries its property
strings (family, type, category, system, IFC GUID, workset) in a record that starts with a
"By Type" marker, and an insertion point stored as three little-endian float64 values in Revit
internal feet, project coordinates: the same frame the Revit PCF export uses (x 12 for inches).
The record layout is undocumented, so the script classifies records by the strings found before
each marker, takes the first plausible XYZ triple inside the record (z inside the window you
give it), and reports what it found so the result can be checked against the PCF.

```
python scripts/nwc_supports.py MODEL.nwc -o out/L1_supports.csv --items-out out/L1_items.csv --zmin <FF-5> --zmax <deck-2> --families families.json
```

- `--zmin` / `--zmax` (ft) bound the level; without them a wrong triple from an adjacent level
  can be taken. `families.json` (`scripts/examples/nwc-families.example.json`) maps family or
  type strings to a support class; the data-hall defaults are a starting point, not a standard.
- **String pooling.** Some exports store property strings once and reference them, so a naive
  scan sees a family name but not its coordinates. If the CSV comes back nearly empty, that NWC
  is not a usable source: go to the IFC, or export selection sets to CSV from Navisworks Manage.
- Insertion points differ by family: a clevis hanger sits on the pipe centreline; a strut
  trapeze member sits **below** the pipe near its end (pipe 4 to 5 in above, 7 to 9 in off in
  plan); an angle-iron trapeze sits above the pipe, up to 8 ft off; a floor stand sits at
  finished floor, offset in plan (`VFY` when it is a multi-service stand). Exclude deck-level
  channel by elevation or family.
- **Plot the NWC items over the PCF (plan and elevation) before writing snap rules.** A wrong
  sign on the trapeze `dz` snaps struts to the wrong tier.
- Verify a sample against Navisworks (select element > Properties) before issue.

| NWC class | PCF SKEY and NAME | CAESAR II restraint | AutoPIPE |
|---|---|---|---|
| CLEVIS, TRAPEZE | SKID + UP, `*-BHGR` / `*-BTRP` (HANG for the AutoPIPE translator) | +Y (+Y with friction for struts) | V-stop, rod hanger |
| STAND, ROLLER, RISER | SKID + UP, `*-BASE` / `*-RSR` | +Y with friction (+ GUI for risers) | V-stop, shoe or rest |

Snap rules the builders apply (job keys; the defaults are a starting point): a clevis snaps to
a horizontal pipe above the clevis bottom within 3 in in plan and between -2 and +10 in of
dz less (OD/2 + insulation); a strut trapeze carries every pipe within 72 in in plan whose
insulation bottom sits on the strut top (-1 to +2.5 in). BIM seeds enter the support placer at a
lower priority than anchors, so the rule supports fill around them. Supports within 12 in on
the same run are merged; two BIM supports 5 in apart at an elbow tangent crashed the AutoPIPE
translator on one job.

## Route D: IFC export of the fabrication model (geometry and supports)

When the contractor's fabrication model is shared only through a viewer (for example Revizto),
its IFC export is the whole model: every spool, fitting, joint, hanger and trapeze with body
meshes and properties, but **no port data**. The method below recovers ports from the meshes;
the detector itself is not shipped (it needs a numerical library). Use the method with your own
tooling and feed the result to `pcf2caesar.py` as a parts list, or rebuild from the drawings.

- **Frame.** Fit `project_ft = Rz(theta) x (ifc_m / 0.3048) + t` on pipe and long-radius elbow
  ends against the element origin property. Fit it on every job; never assume identity. A good
  fit leaves a residual of about 1e-4 in on hundreds of pipes.
- **Parent and child.** The parent element carries the properties (origin, weight, OD, wall,
  insulation, service); the child carries the geometry. Hanger placements are identity: a
  hanger's location comes from the mapped-item operator plus its mesh.
- **Ports from meshes.** Planar end rings matched to the part's size or OD. On a clean model
  nearly every pipe, flange, joint, gasket, bolt set, nipple, cap, tee and elbow has its origin on
  a detected port, which is the check that the transform and the detector agree. Valves: origin
  at the midpoint. Olets and fishmouths: origin on the header axis. Reducers: origin at neither
  port.
- **Parts with no geometry** are co-located duplicates of real parts: exclude them and suggest
  a Revit "identical instances" check.
- **Joints are markers.** Welds, threaded and press joints, gaskets and bolt sets are
  zero-length; union their faces into one node and lump their weights on the adjacent valve
  (else the flange). **Grooved couplings** (rigid per the manufacturer's data) become a short
  rigid spanning the housing faces with the vendor weight; the grooved pipe ends inside the
  housing move to the housing face (logged, under 2.25 in). Exclude housings from proximity
  bridging or the couplings collapse to zero length.
- **Node clustering** within 1/16 in; detector-matched ports bridge up to 1 in; proximity
  bridging up to 0.25 in for lone ports; cluster base by family rank (pipe first, cap and
  blind last).

| Fabrication family | PCF record |
|---|---|
| pipe | PIPE (a pipe or reducer under 0.25 in is dropped and its neighbours re-pointed) |
| elbow | BEND: corner from the two port directions, R = T / tan(theta/2) |
| tee | TEE (TEBW) |
| reducer | REDUCER-CONCENTRIC (an eccentric is logged) |
| flange, blind, valve, strainer | FLANGE / VALVE rigid with the model weight |
| cap | FLANGE FLBL with weight (closed end) |
| fishmouth | OLET TERF on the split header (the header snaps to the nearest node) |
| grooved coupling | short rigid, vendor weight |
| joint, gasket, bolt set | zero-length marker, weight lumped |
| small bore at or below the limit, instruments | dropped and counted |

End classification: **EQUIP** (a facing gap at an in-line pump body, an open gasket face, an
open flange face of 8 in or more, any open flange or valve face that is not a blind) is an
anchor, both nozzles of each machine unless the analyst says otherwise; **CUT** (pipe leaving
the analysis box, buried mains) is a virtual anchor; **FREE** (closed caps and blinds).

## Content gaps to report, never silently fix

Unmated ports (coordination gaps of 9 to 10 in on small lines, stubs short of their flange),
supply-to-return cross-links (mislabel or bypass: check the P&ID), caps closing a weld gap,
eccentric reducers written as concentric, pump discharge risers with no support, spans between
BIM hangers over the specification table, BIM hangers that carry only small bore and so place
nothing. All `VFY` for the analyst.
