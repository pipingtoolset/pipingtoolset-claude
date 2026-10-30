# Walk spec format (`build_pcf.py`)

A spec is a faithful transcription of the isometric. It records a start point and then
walks the line in drawing order. Every dimension is a **string in iso notation**, exactly as
printed: `"13.7/8"` (13⅞ in), `"2635'0.7/16"`, `"5'4"`, `"7/16"`. A true decimal such as
`"13.875"` is rejected, because on an iso it is almost always a misread fraction.

`scripts/examples/demo-line.json` uses every feature below.

## Top level

| Key | Required | Meaning |
|---|---|---|
| `start` | yes | `{"at": {E, N, EL}, "dir": <direction>, "bore": <NPS in>}`: the first point, the initial run direction, and the bore |
| `items` | yes | The ordered walk (below) |
| `pipeline` | | `{"reference": "<line no>", "attributes": [["DESIGN-TEMPERATURE", "..."], ...]}`. Only names the importer's `PCF_MAP.xml` reads carry data into the job (`caesar-import.md`). The import-proven header has none, so leave `attributes` out unless you have checked the map. Never put free text in an `ATTRIBUTEn` the map may read as a number |
| `axes` | | `"Z-up"` (default: X=E, Y=N, Z=EL) or `"Y-up"` (X=E, Y=EL, Z=−N) |
| `units` | | `"MM"` (default, import-proven) or `"INCH"` (unproven). Coordinates **and** bore use it: `start.bore` and reducer/branch bores are entered as NPS and written ×25.4 |
| `weight_units` | | `"LBS"` (default, as in import-proven files) or `"KGS"` |
| `annotate` | | Default `true` (import-proven): writes `ITEM-DESCRIPTION` from `desc`, `WEIGHT` from `weight` and support `NAME`. `false` gives the bare form |
| `profiles` | | Elevation profiles for sloped runs (below) |
| `assumed` | | Strings: everything not readable on the drawing. Copied into the report |
| `skeyOverrides` | | Object `{item type: SKEY}` that replaces the default SKEY per component type (see [`skeyOverrides`](#skeyoverrides) below) |
| `code_values` | | Absent, `null` or `{}` only: this skill has no code-table input, so a block with any entry exits 2 with `input error: code_values.<name> is not an input of build_pcf.py` and no PCF is written. SKEY choices go in `skeyOverrides` |
| `bom` | | Counts to reconcile (see *BOM keys* below): `{"ELBOW": 4, "FLANGE": 2, "PIPE-LENGTH:6": "145'0", ...}` |
| `full_vocabulary` | | `true` writes native `ELBOW`, `FLANGE-BLIND`, `CAP`, `MISC-COMPONENT` and `REDUCER-ECCENTRIC` records instead of the CAESAR II safe set. Use it only for an importer known to accept them |

## Directions

`"E" "W" "N" "S" "UP" "DOWN"`, or a vector `{"e": .., "n": .., "el": ..}` for sloped or skewed
runs. A vector's components are dimensions, so `{"n": "100", "el": "-1"}` is a 1 % fall going north.

## Points

Each point is resolved against the **anchor**: the last stated point (corner, tee centre, olet,
support, component end, or the end of a `pipe`).

| Form | Meaning |
|---|---|
| `{"E": .., "N": .., "EL": ..}` | Absolute plant coordinates. **Omitted ones inherit the anchor's**, so `{"N": "215'0"}` means "run north to N 215'0" |
| `{"EL": "@P1"}` | Interpolate elevation on profile `P1` at this point's E or N |
| `{"d": {"e": .., "n": .., "el": ..}}` | Delta from the anchor |
| `{"len": ..}` | Distance along the current direction from the anchor |

## Items

Common optional keys on any component: `desc` (written upper-case as `ITEM-DESCRIPTION`),
`skey`, `weight` (rigids). Inline fittings can also take `pipe_desc` for the pipe the builder
inserts in front of them.

| `type` | Keys | Behaviour |
|---|---|---|
| `pipe` | `to` | Straight pipe from the cursor to the point. Must lie ahead along the run |
| `flange` `gasket` `valve` `blind` `cap` `misc` `coupling` | `len` (face-to-face) or `to`, optional `at` | Optional `at` inserts pipe up to that stated start first |
| `reducer` | `bore` (new NPS), `len` or `to`, `eccentric`, `flat` | Concentric by default. Eccentric needs `to` (the offset end point); the offset is carried by the end points. `flat` (`FLAT-DIRECTION`) is written **only** with `full_vocabulary`; in the safe set the flat side is lost from the record, so put it in `desc` |
| `elbow` / `bend` | `corner`, `out`, `radius` (`"LR"`, `"SR"` or a dimension), optional `angle` | Tangents from the corner. `LR` = 1.5×NPS and `SR` = 1.0×NPS are logged as ASSUMED. The written `ANGLE` and tangents always come from the in/out **directions**; a stated `angle` is only checked against them (within 0.25°). A trimmed elbow therefore needs a vector `out` (e.g. 89.5° → `{"e": "1", "n": "114.5/8"}`) |
| `tee` | `centre`, `C` (centre-to-end, run), `M` (centre-to-end, branch; default C), `branch_dir`, `branch_bore`, `branch: [items]` | Pipe up to the run start, then the tee (`CENTRE-POINT` included). The main walk continues from the far run end with the anchor at the centre. The branch items are walked from the branch end **after the main run** and written at the end of the file, as Isogen does |
| `olet` | `at`, `height`, `branch_dir`, `branch_bore`, `branch: [items]` | Sits on the run and does not move the cursor. Place it in the walk **before** the pipe that passes it |
| `support` | optional `at` (default: the cursor), `skey` (default `SKID`), `direction` (string, list, or `null`; default by SKEY), `name` | Lands on a node: if `at` is ahead on the run, the pipe is split there. `ANCH` gets no direction; `SKID`/`SPRG` default `UP`; `GUID` needs a direction, and a list writes one record per direction. Directions: `UP DOWN NORTH SOUTH EAST WEST` |
| `check` | `label`, `expect` (point), `of` (`"anchor"` default or `"cursor"`), `tol` (default `"0.1/16"`) | Closure check against a stated coordinate. A failure means exit 2 |

## Default SKEYs

Every default is a common Isogen SKEY, **not** a confirmed one for any particular site. Override
with `skey` wherever the user's own Isogen output differs (`reading-isos.md`), and pass the
site's list to `validate_pcf.py --skeys`.

| Item | Default SKEY | Status |
|---|---|---|
| `flange` | `FLWN` | common |
| `blind` | `FLBL` | common |
| `elbow`, `bend` | `BEBW` | import-proven (written as `BEND` records) |
| `tee` | `TEBW` | common; check its SIF-map type |
| `olet` | `WTBW` | common; check its SIF-map type |
| `reducer` concentric / eccentric | `RCBW` / `RECC` | `RCBW` import-proven; `RECC` common |
| `valve`, `misc` | `VVFL` | import-proven |
| `support` | `SKID` | import-proven, with `ANCH`, `GUID`, `SPRG` |
| `gasket`, `cap`, `coupling` | none | set `skey` if the site needs one |

## BOM keys

`bom` counts use the builder's own component names, **before** safe-set mapping: `PIPE` (not
counted from the BOM; use `PIPE-LENGTH:<bore>`), `ELBOW`, `BEND`, `TEE`, `OLET`, `FLANGE`,
`FLANGE-BLIND`, `GASKET`, `VALVE`, `CAP`, `MISC-COMPONENT`, `COUPLING`, `REDUCER-CONCENTRIC`,
`REDUCER-ECCENTRIC`, `SUPPORT`. Blinds, caps, couplings and bends count **separately** from
`FLANGE`, `PIPE` and `ELBOW`. Split an iso BOM's flange total into `FLANGE` + `FLANGE-BLIND`, or
it fails. The validator's census counts *records* after mapping, so there a blind shows as a
`FLANGE`. `PIPE-LENGTH:<bore>` (bore as written, e.g. `6`, `0.75`) is a ±10 % magnitude
check, because BOM lengths are cut lengths.

## Errors the builder raises (exit 1)

- A point that is off-line or behind the cursor. The message names the item index and type.
- A bend whose tangent overruns the previous component (radius or corner wrong).
- A stated bend angle that disagrees with the directions.
- A tee branch that is not square to the run.
- A profile station outside the profile's anchors.
- An unknown item type, an unreadable dimension, or a missing required key (`missing key 'out'`).

Every message starts with `item <index> (<type> <desc>)`. Branch items are indexed within
their own `branch` list.

## Continuation sheets

Walk each sheet in its own spec, or chain them in one. Either way, put the `CONT. ON`
coordinate in as a `check` at each hand-off, so both sheets are tied to the same stated
point.

## `skeyOverrides`

An optional top-level object `{"<item type>": "<SKEY>"}` applied over the Default SKEYs table. Precedence, highest first: the item's own `skey`, then `skeyOverrides`, then the builder default.

- **Keys** are the item `type` names (`flange`, `blind`, `gasket`, `valve`, `cap`, `misc`, `coupling`, `reducer`, `elbow`, `bend`, `tee`, `olet`, `support`; `reducer` covers the concentric and the eccentric record) or the builder's record names (`ELBOW`, `BEND`, `TEE`, `OLET`, `FLANGE`, `FLANGE-BLIND`, `GASKET`, `VALVE`, `CAP`, `MISC-COMPONENT`, `COUPLING`, `REDUCER-CONCENTRIC`, `REDUCER-ECCENTRIC`, `SUPPORT`).
- **A SKEY** is one token of 2 to 8 upper-case letters and digits starting with a letter; `null` omits the SKEY. A support takes `ANCH`, `SKID`, `GUID` or `SPRG` only. Anything else is a spec error (exit 1).
- The build report gains `skey_overrides` (the map as given, SKEYs upper-cased) and `skey_overrides_unused` (keys no item of the line used). A spec without the key builds the same file and report as before.

Where the SKEYs come from, in order of preference:

1. The user's own Isogen PCFs (see `reading-isos.md`). These are the only confirmed SKEYs for a site.
2. When the site list has no SKEY for a type, the Engineering Data connector's `get_skey_map` (`scope` `isogen` for the vocabulary, `caesar-safe` for the records that import cleanly into CAESAR II). That map is Piping Toolset's vocabulary, not the site's. Record each SKEY taken from it in `assumed` and in the handover note as a substitution, with the scope and group, and check it against the site's own Isogen output before issue.

The map never changes geometry, and a SKEY is not a code-table value, so no citation block is attached. `code_values` is refused when it has any entry (exit 2): PCF building has no code-table inputs. The script makes no network calls.

## Project basis and result status

**`project_basis`** (optional top-level object) or `--project-basis <file>` carries the record described in [project-basis.md](project-basis.md). Both given and different: exit 2, `project_basis conflicts with --project-basis file`. The builder reads three fields and reports the rest:

| Spec input | Taken from | Rule |
|---|---|---|
| `axes` | `equipment_axes.global_vertical` | `Y` gives `Y-up`, `Z` gives `Z-up` |
| `units` | `units.length` | only an explicit `mm` counts (`MM`); any other unit is the model's own, since the PCF is always written in mm, and is listed as noted |
| `pipeline.reference` | `project.line` | verbatim |

The bundled `scripts/examples/project-basis.example.json` declares a Y-vertical model, so it pairs with `scripts/examples/project-basis-line.json` (axes and reference left out, filled from the record); the other two example specs are Z-up and exit 2 against it by design. A spec value that differs from the record exits 2 with `project_basis.<path> conflicts with input <name>`; an absent one is filled. Every ASSUMED item of the record is appended to `assumed` as `project basis: <item> - <note> (<owner>)`. The report gains `project_basis_applied` and a `1. Basis` section at the top that lists every ASSUMED item first.

**`result_status`** (one of `calculated`, `screening`, `manual check required`, `pointer only`, `not checked`) is the worst word among the checks the builder performs in `checks[]` (a `not checked` row is listed but never sets it); each check is `{name, result_status, status, note}`. `ok`, the exit codes and the PCF do not change. The report prints `Result status: <word> - <why>` under its title.

| Check | Word |
|---|---|
| closure checks, all within tolerance | `calculated` |
| BOM component counts, all matching | `calculated` |
| BOM `PIPE-LENGTH` (a +/-10 % magnitude screen) | `screening` |
| `ASSUMED inputs`: one row for every ASSUMED item (spec, builder or record), note `confirm before issue: <items>` | `manual check required` |
| a closure check or BOM line that failed | `manual check required` (exit 2) |
| no closure checks or no BOM in the spec | `not checked` |
| `validate_pcf.py`, site SKEYs, continuation coordinates, axis declaration | `not checked` (never run by the builder) |

`pointer only` is not reachable here: the builder has no code-table input. A clean build with closure checks and BOM counts reads `calculated`, with the never-run rows summarised after the word as `not performed by this module: ...`. The OK, PASS and DELIVERABLE words follow the banner rule: they print only while the word is not `manual check required`, `pointer only`, or `screening` with an unresolved factor, so a failed run prints the status word in capitals where PASS would be, and `NOT DELIVERABLE`. With an ASSUMED item the last line reads `RESULT: MANUAL CHECK REQUIRED - confirm the ASSUMED items, then run validate_pcf.py`. `validate_pcf.py --json` carries the same two fields.

`validate_pcf.py` now imports `build_pcf.py` and `pcf_lib.py` (same folder), so keep the three scripts together.
