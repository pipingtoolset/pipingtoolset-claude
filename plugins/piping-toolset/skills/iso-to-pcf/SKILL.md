---
name: iso-to-pcf
description: "Turn PDF stress isometrics into a clean, CAESAR II-ready PCF: transcribe the drawing to a JSON walk, build it with exact fraction arithmetic, then validate connectivity, zero-length elements and on-line supports. Use when the user asks to convert an iso or isometric PDF to a PCF, import a line into CAESAR II, or fix a PCF that imports with orphan nodes or broken continuity (Isogen, SKEY)."
compatibility: Requires Python 3.9+ (standard library only)
---

# Isometric PDF → CAESAR II PCF

A PCF that imports badly is almost never wrong about the *pipe*. It is wrong about the
*joins*. CAESAR II makes one node per distinct coordinate. If each component's ends are
rounded independently, a run arrives as a scatter of near-coincident nodes with hairline
elements between them, and someone spends an afternoon merging nodes that should never
have been separate.

This skill is built on one rule: **a coordinate is computed once and reused**. It is never
recomputed by a second route. The bundled builder enforces that, so your job and the assistant's is
to **transcribe the drawing faithfully**. The script does all of the geometry.

| File | Role |
|---|---|
| `scripts/build_pcf.py` | JSON walk spec → PCF + build report (closure checks, BOM reconciliation, ASSUMED list) |
| `scripts/validate_pcf.py` | Checks any PCF, including third-party exports, before it goes near CAESAR II |
| `scripts/pcf_lib.py` | Exact-fraction geometry and emitters, if a job needs a custom script |
| `scripts/examples/minimal-proven.json` | Small line using only import-proven records: the first file to import on a new CAESAR II install |
| `scripts/examples/demo-line.json` | Synthetic worked example that uses every item type |
| `references/spec-format.md` | The walk spec: point forms, item types, profiles, checks |
| `references/reading-isos.md` | Getting dimensions out of the PDF; the dot-fraction convention; SKEYs |
| `references/caesar-import.md` | The importer's map files, the safe record set, and what a PCF cannot carry |

Standard-library Python 3.9+. The scripts make no network calls, and nothing from the iso leaves the user's machine. Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.

## Workflow

1. **Basis interview.** Before reading a single dimension, confirm:
   - **Vertical axis.** The default is Z-up (E→X, N→Y, EL→Z). `Y-up` writes X=E, Y=EL, Z=−N.
     Isogen output is often Y-up, which is why third-party PCFs come in lying on their side.
     Say the convention back to the user. Getting it wrong costs a full rebuild.
   - **Output units.** mm, for coordinates **and** bore (nominal size × 25.4, so NPS 4 → `101.6`),
     exactly as import-proven Isogen PCFs are written. You enter bores as NPS; the builder converts.
   - **The SKEYs the user's site actually emits.** Ask for one of their own Isogen PCFs and
     harvest the SKEYs from it (`references/reading-isos.md`).
   - **Drawing set and revision**, and which sheets are in scope.
2. **Read the drawing.** In a chat host (Claude Cowork, the ChatGPT desktop app) the user attaches the iso PDF and the skill reads it from the working directory; in a terminal host (Claude Code, Codex CLI) the user gives the path. Read in this order: title block and notes → continuation references → dimension
   chains → bill of materials → supports. Use the text layer and image zooms together. A dimension
   whose arrows you have not seen is a dimension you have not read.
3. **Transcribe to a walk spec** (`references/spec-format.md`). Copy dimensions exactly as
   printed (`"13.7/8"`, `"2635'0.7/16"`). Never convert them to decimals. Record every stated
   coordinate and elevation as a `check` or a profile anchor. Anything that cannot be read
   goes in `assumed`. It is never guessed silently.
4. **Build** (spec, PCF and report all in the working directory): `python scripts/build_pcf.py spec.json -o line.pcf --report line-report.txt`.
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
  direction. The builder computes `T = R·tan(θ/2)`, runs the pipe to the tangent, and writes a
  `BEND` record (SKEY `BEBW`, `ANGLE` in centidegrees, 90° → `9000`, `BEND-RADIUS` in mm) with
  the corner as `CENTRE-POINT`. That is how import-proven files carry elbows. If the
  tangents use up the whole straight between two fittings, no pipe element is written. Zero-length
  elements are refused outright.
- **Sloped runs are profiles, not chained deltas.** Stated elevations become profile anchors,
  and every station on the run is interpolated between them, so each one lands on the drawing's
  own numbers. Chaining fall × length accumulates one rounding per segment. Make every
  explicitly stated elevation (a tee, a grade break) an anchor. Don't interpolate straight
  past one.
- **Off-line is an error.** A point that is not ahead of the cursor along the current direction
  stops the build. That catches transcription slips at the item that caused them.
- **Import-proven format by default.** The header, record types, attribute order and units
  mirror PCFs that import cleanly into CAESAR II. `ITEM-DESCRIPTION`, `WEIGHT` and support `NAME`
  are written by default (import-proven); `"annotate": false` gives the bare form. `ITEM-CODE` is
  never written. Branch legs are written after the main run, as Isogen does.
- **Supports sit on nodes.** A support part-way along a run splits the pipe there, so the
  restraint lands on a node. A support behind the cursor is an error. Blinds, caps, instruments and eccentric reducers are mapped onto that set with
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
  weight unit (lb by default). Without one, CAESAR II estimates, and hand-corrected rigid weights
  are a common review finding. Spot-check one rigid's weight in CAESAR II after the first import.
- **Supports.** The restraint type is carried by the support SKEY and direction, as in the
  import-proven files: `ANCH` (anchor, no direction), `SKID` (resting, `UP`), `GUID` (guide; give
  `["EAST", "WEST"]` or `["NORTH", "SOUTH"]` for both sides, written as two records), `SPRG`
  (spring, `UP`). Every support goes on the modelled centreline. An iso note like "support offline at
  E… N… EL…" is dimensioned to the steel, not the pipe. Model it at the pipe station and keep the
  note in the description. Give each support its drawing tag as `name`, so the analyst can tie
  the restraint back to the support drawing.

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as written without it. If its tools are present, call `verify_connector` once per session; `get_skey_map` answers without an account. It returns Piping Toolset's SKEY vocabulary, not the user's site list: a SKEY harvested from the user's own Isogen PCFs always wins. For a component type the site list leaves open, a SKEY taken from the map goes in the spec's `skeyOverrides` ([format](references/spec-format.md#skeyoverrides)), is recorded as connector-supplied in the handover note with the scope and group it came from, and is checked against the site's own Isogen output before issue. On an error or absent tools, use the SKEY rules above, unchanged. A call sends only `scope` and `component`, never the iso or the spec.

| Slot | Tool | Key fields | What comes back |
|---|---|---|---|
| SKEY vocabulary (`skey`, default SKEYs) | `get_skey_map` | `scope` `isogen`; `component`, a group name such as `valve_prefix` | component prefixes, end-condition suffixes, fitting and support keys |
| CAESAR II safe record set | `get_skey_map` | `scope` `caesar-safe`; `component`, a group name such as `safe_substitutions` | the PCF records, substitutions and default SKEYs that import cleanly into CAESAR II |

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
