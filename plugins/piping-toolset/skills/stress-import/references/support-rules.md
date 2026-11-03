# Support placement rules and the handover note

These rules place a **layout to analyse**, not a support design. Every rule support is
ASSUMED; every BIM support is the contractor's layout. The analyst decides. The rules are job
keys of `pcf2caesar.py` and `pcf_prep.py` (`support_rules`, `boundary_rules`); the numbers
below are the defaults one central-plant job used and are placeholders until the project
specification replaces them.

## Rules, in placement priority

| # | Rule | Type / NAME suffix | Restraint |
|---|---|---|---|
| 1 | Every equipment nozzle (both nozzles of a pump, chiller, exchanger, air separator, expansion tank) | `-ANC` | ANC |
| 2 | Every cut where the model leaves the analysis box (buried mains, rack drops) | `-ANC` (virtual) | ANC |
| 3 | **Base support at the first low elbow off each nozzle** (within `base_bend_max_above_ff_ft` of the floor); if none within `base_walk_max_ft`, a stand 2 ft out on the first straight pipe. Any equipment connection should have a support nearby before it is carried by hangers from above | `-BASE` | +Y with friction |
| 4 | BIM clevis hangers and strut trapezes, snapped to the pipe they carry | `-BHGR`, `-BTRP` | +Y, +Y with friction |
| 5 | Riser support at each floor crossing (`riser_floors_ft` + 1 ft), no more than `riser_max_ft` apart on verticals, 2 ft above top-entry nozzles | `-RSR` | +Y with friction + GUI |
| 6 | A support on the horizontal side of every bend (within 1 ft) not already covered | `-HGR` | +Y |
| 7 | Span fill between supports to the specification table, measured gap-wise by the largest bore in the gap | `-HGR` | +Y |

Rules of engagement that cost time when ignored:

- Supports merge only along the **same pipe** (a hanger on a parallel line 18 in away is not
  the same support).
- Base supports are never dropped in favour of an anchor on the same node.
- No support below the slab (`no_support_below_ft`); buried pipe is unsupported in the model.
- Equal-size tee branches get a support 18 in out (`tee_carry_ratio` 0.5).
- A span that crosses a bend is measured along the pipe.
- Supports are placed on the centreline and the pipe is split there; geometry never moves.
- Spring isolators called for by the specification near chillers and pumps (for example the
  first three supports within 50 ft of a nozzle) are tagged `spec_isolator_candidate`, modelled
  rigid, and left to the analyst.

## The span table is a project input

`span_table_ft` (the builders) and `--span-table` (`pcf_check.py`) take the maximum horizontal
span by NPS **from the project specification** (the hangers-and-supports section) or from the
analyst, and `riser_max_ft` / `--vert-max-ft` the vertical limit. No table is embedded and
none is read back from memory: without one, `pcf_check.py` says the span check was skipped. A
specification table is a geometric layout rule, not a code allowable; the stress check of the
span belongs to the `pipe-stress-check` skill.

## Support list columns (CSV)

`support_id, type, restraint_as_imported, line, X_ft, Y_ft, Z_ft, NPS, basis,
equipment_identity, spec_isolator_candidate, status, reviewer_markup`

plus an equipment list (tag, identity guess, line, NPS, xyz, basis) and a pieces list
(components, anchors, supports per connected piece). `status` is one of `BIM: <contractor>
model`, `ASSUMED equipment nozzle anchor`, `ASSUMED virtual anchor (buried transition)`,
`ASSUMED rule-placed (not BIM)`.

## Handover note (README_<model>_<rev>.md), always

1. Status line: who runs the test import, whether the analyst has reviewed it.
2. Files table.
3. What it is: source and basis model, transform, counts by record type, small bore dropped,
   cuts, rigid weights total against the source, geometry moved (with every exception listed).
4. Supports table by type with counts, restraint, source. State that BIM supports are the
   contractor's layout, not a support design.
5. Import recipe: the RES_MAP block and APCF settings (CAESAR II) or the translator settings
   and the post-translate checks (AutoPIPE), per-line T/P, code and edition (ASSUMED until
   confirmed), and the request to send back the NTXT and OUT (or the MSG and CHK).
6. For the analyst's judgement, numbered: code, edition and design pressure; grooved joints;
   fishmouth and fabricated-tee SIFs; nozzle anchors and isolator candidates; spans over the
   table; cross-links; coordination gaps; reducers; temperature cases; load cases.
7. What the analyst still sets: friction, gaps, guide and anchor intent, load cases
   (`load-case-builder`), allowables and SIF sources (`pipe-stress-check`; read from licensed
   copies, never tabulated here), spring selection, nozzle allowables (`nozzle-load`).

A PCF and a repaired neutral file are geometry, components and restraints. They are not the
load case set and not a code check, and the note says so.

An email or transmittal to the analyst is staged as text for the user to send, never sent by
the skill. Order: status, file path, what is in it, the numbered verify list.
