---
name: iso-to-pcf
description: "Turn PDF stress isometrics into a clean, CAESAR II-ready PCF: transcribe the drawing to a JSON walk, build it with exact fraction arithmetic, then validate connectivity, zero-length elements and on-line supports. Also repairs PCFs that import with orphan nodes or broken continuity."
---

# Isometric PDF → CAESAR II PCF

A PCF that imports badly is almost never wrong about the *pipe*. It is wrong about the
*joins*. CAESAR II makes one node per distinct coordinate. If each component's ends are
rounded independently, a run arrives as a scatter of near-coincident nodes with hairline
elements between them, and someone spends an afternoon merging nodes that should never
have been separate.

This skill is built on one rule: **a coordinate is computed once and reused**. It is never
recomputed by a second route. The bundled builder enforces that, so your job and Claude's is
to **transcribe the drawing faithfully**. The script does all of the geometry.

| File | Role |
|---|---|
| `scripts/build_pcf.py` | JSON walk spec → PCF + build report (closure checks, BOM reconciliation, ASSUMED list) |
| `scripts/validate_pcf.py` | Checks any PCF, including third-party exports, before it goes near CAESAR II |
| `scripts/pcf_lib.py` | Exact-fraction geometry and emitters, if a job needs a custom script |
| `scripts/examples/demo-line.json` | Synthetic worked example that uses every item type |
| `references/spec-format.md` | The walk spec: point forms, item types, profiles, checks |
| `references/reading-isos.md` | Getting dimensions out of the PDF; the `X.n/d` convention; SKEYs |
| `references/caesar-import.md` | The importer's map files, the safe record set, and what a PCF cannot carry |

Standard-library Python 3.9+. Nothing leaves the user's machine.

## Workflow

1. **Basis interview.** Before reading a single dimension, confirm:
   - **Vertical axis.** The default is Z-up (E→X, N→Y, EL→Z). `Y-up` writes X=E, Y=EL, Z=−N.
     Isogen output is often Y-up, which is why third-party PCFs come in lying on their side.
     Say the convention back to the user. Getting it wrong costs a full rebuild.
   - **Output units.** The default is mm coordinates. Bore is always in inches.
   - **The SKEYs the user's site actually emits.** Ask for one of their own Isogen PCFs and
     harvest the SKEYs from it (`references/reading-isos.md`).
   - **Drawing set and revision**, and which sheets are in scope.
2. **Read the drawing** in this order: title block and notes → continuation references → dimension
   chains → bill of materials → supports. Use the text layer and image zooms together. A dimension
   whose arrows you have not seen is a dimension you have not read.
3. **Transcribe to a walk spec** (`references/spec-format.md`). Copy dimensions exactly as
   printed (`"13.7/8"`, `"2635'0.7/16"`). Never convert them to decimals. Record every stated
   coordinate and elevation as a `check` or a profile anchor. Anything that cannot be read
   goes in `assumed`. It is never guessed silently.
4. **Build:** `python scripts/build_pcf.py spec.json -o line.pcf --report line-report.txt`.
   Exit 0 means clean. Exit 2 means a closure check or BOM count failed. Exit 1 means the spec is
   defective: an off-line point, a tangent overrun, or an unreadable dimension.
5. **Validate:** `python scripts/validate_pcf.py line.pcf --skeys <the site's list>`.
   **A file with any error is not delivered.** Fix the spec and rebuild. Never edit coordinates
   in the PCF by hand.
6. **Hand over** (see below).

## Rules the builder enforces (and why)

- **Exact arithmetic.** Iso dimensions are binary fractions of an inch, so they are carried as
  `Fraction` and converted to mm only when written. A 0.4 mm float drift is invisible in the file
  and becomes a duplicate node on import. Trig results (bend tangents, sloped direction cosines)
  are snapped to 1/10000 in immediately.
- **One cursor.** Each component starts at the cursor and moves it to its own end, so adjacent
  components share one coordinate. Branches (tee legs, olet stubs) save the cursor, walk, and
  restore it.
- **Dimensions run from the last stated point.** Relative dimensions are measured from the
  *anchor*: the last corner, tee centre, olet, support or component end. That matches how isos
  chain their dimensions.
- **Bends from corners.** Give the corner (theoretical intersection point) and the outgoing
  direction. The builder computes `T = R·tan(θ/2)`, runs the pipe to the tangent, writes
  `ANGLE` in centidegrees (90° → `9000`), and leaves the corner as `CENTRE-POINT`. If the
  tangents use up the whole straight between two fittings, no pipe element is written. Zero-length
  elements are refused outright.
- **Sloped runs are profiles, not chained deltas.** Stated elevations become profile anchors,
  and every station on the run is interpolated between them, so each one lands on the drawing's
  own numbers. Chaining fall × length accumulates one rounding per segment. Make every
  explicitly stated elevation (a tee, a grade break) an anchor. Don't interpolate straight
  past one.
- **Off-line is an error.** A point that is not ahead of the cursor along the current direction
  stops the build. That catches transcription slips at the item that caused them.
- **Safe record set by default.** Only record types proven to import cleanly (verified on one
  CAESAR II v15 build; conservative on others) are written. Blinds, caps, instruments and eccentric reducers are mapped onto that set with
  no loss of geometry, and every substitution is listed in the report
  (`references/caesar-import.md`).

## Checks that pay for themselves

- **Closure checks.** Every coordinate the drawing states independently (a continuation
  point, a nozzle, an elevation callout) goes in the spec as a `check`. Aim for zero failures
  at 1/16 in. A miss of about 1/8 in is usually **drawing rounding**: isos display to 1/16 in, and a
  chain of rounded dimensions can disagree with a stated elevation. Prefer the stated coordinate,
  loosen that one check's `tol`, and record which value governed in `assumed`.
- **BOM reconciliation.** The BOM is an independent count. Put elbow, tee, olet, flange,
  valve and gasket counts in `bom`. `PIPE-LENGTH:<bore>` is a ±10 % magnitude check only, because
  BOM lengths are cut lengths, not centreline lengths. A mismatch means a missed fitting.
  Finding it here is far cheaper than finding it in the model.
- **Validator.** It checks connectivity as a tree (a component may start at any node already
  placed, and a tee is 3-legged). It also flags zero-length elements, olets and supports off the
  centreline, unsafe record types, bore changes without a reducer, asymmetric elbow
  tangents, and LF line endings. Run it on third-party PCFs too: it finds orphan-node causes in
  seconds.
- **Not machine-checked:** SKEYs against the site's own Isogen output, continuation coordinates
  against the adjoining sheet, and the axis declaration. Check those by hand before handover.

## Components and supports

- **SKEYs drive how CAESAR II classifies a component** (its SIF treatment in particular). An
  invented SKEY imports as an unrecognised item. Use SKEYs harvested from the user's own Isogen
  PCFs. If a component type has none, use the nearest confirmed SKEY in the same family, keep
  the true identity in the description, and **tell the user**.
- **Weights on rigids.** Valves, flanges, blinds and instruments take `weight` in the PCF's
  weight unit. Without one, CAESAR II estimates, and hand-corrected rigid weights are a common
  review finding.
- **Supports.** Every support goes on the modelled centreline. An iso note like "support offline at
  E… N… EL…" is dimensioned to the steel, not the pipe. Model it at the pipe station and keep the
  note in the description. Name supports `TYPE_TAG` (for example `PG-2A_PS-0235`). The importer
  matches restraint types on the `NAME` prefix, and the full string still carries the support
  tag back to the support drawing.

## Handover

Deliver the `.pcf` (CRLF line endings, written by the builder), the build report, the validation
output, and a short build note that states:

- drawing set and revision, axis convention, datum, coordinate units
- every ASSUMED item, including the elbow radius basis and any rounding-governed closure
- every SKEY substitution and record-type substitution
- **what the PCF does not carry**, which the analyst sets in CAESAR II after import:
  material, design and operating temperatures and pressures (unless mapped through the
  importer's attribute map), insulation, fluid density, restraint stiffness, gaps and friction,
  hanger design data, wind and seismic data, corrosion allowance and mill tolerance

A PCF is geometry and components. It is not a load case set and not a code check. Say so,
so nobody mistakes an imported model for one that is ready to run.

## Related skills in this pack

Once the model is in CAESAR II, `load-case-builder` builds the static load case set and
`stress-screening` hand-checks the results. `pressure-design` covers wall thickness for the
lines you just modelled. This skill produces geometry only. It never selects allowables, SIFs
or load cases, and it contains no code table values.
