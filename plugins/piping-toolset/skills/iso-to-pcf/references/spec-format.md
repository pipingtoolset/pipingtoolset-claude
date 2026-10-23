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
| `pipeline` | | `{"reference": "<line no>", "attributes": [["DESIGN-TEMPERATURE", "..."], ["ATTRIBUTE2", "text"], ...]}`. Only names the importer's `PCF_MAP.xml` reads carry data into the job (`caesar-import.md` lists the defaults); others are notes |
| `axes` | | `"Z-up"` (default: X=E, Y=N, Z=EL) or `"Y-up"` (X=E, Y=EL, Z=−N) |
| `units` | | `"MM"` (default) or `"INCH"` coordinates. Bore is always inches |
| `weight_units` | | `"KGS"` (default) or `"LBS"`, for `weight` on rigids |
| `profiles` | | Elevation profiles for sloped runs (below) |
| `assumed` | | Strings: everything not readable on the drawing. Copied into the report |
| `bom` | | Counts to reconcile (see *BOM keys* below): `{"ELBOW": 4, "FLANGE": 2, "PIPE-LENGTH:6": "145'0", ...}` |
| `full_vocabulary` | | `true` writes native `FLANGE-BLIND`, `CAP`, `MISC-COMPONENT`, `REDUCER-ECCENTRIC` and `BEND-RADIUS` instead of the CAESAR II safe set. Use it only for an importer known to accept them |

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
`item_code`, `skey`, `weight` (rigids). Inline fittings can also take `pipe_desc` and
`pipe_code` for the pipe the builder inserts in front of them.

| `type` | Keys | Behaviour |
|---|---|---|
| `pipe` | `to` | Straight pipe from the cursor to the point. Must lie ahead along the run |
| `flange` `gasket` `valve` `blind` `cap` `misc` `coupling` | `len` (face-to-face) or `to`, optional `at` | Optional `at` inserts pipe up to that stated start first |
| `reducer` | `bore` (new NPS), `len` or `to`, `eccentric`, `flat` | Concentric by default. Eccentric needs `to` (the offset end point); the offset is carried by the end points. `flat` (`FLAT-DIRECTION`) is written **only** with `full_vocabulary`; in the safe set the flat side is lost from the record, so put it in `desc` |
| `elbow` / `bend` | `corner`, `out`, `radius` (`"LR"`, `"SR"` or a dimension), optional `angle` | Tangents from the corner. `LR` = 1.5×NPS and `SR` = 1.0×NPS are logged as ASSUMED. The written `ANGLE` and tangents always come from the in/out **directions**; a stated `angle` is only checked against them (within 0.25°). A trimmed elbow therefore needs a vector `out` (e.g. 89.5° → `{"e": "1", "n": "114.5/8"}`) |
| `tee` | `centre`, `C` (centre-to-end, run), `M` (centre-to-end, branch; default C), `branch_dir`, `branch_bore`, `branch: [items]` | Pipe up to the run start, tee, then walks the branch from the branch end. The main walk continues from the far run end with the anchor at the centre |
| `olet` | `at`, `height`, `branch_dir`, `branch_bore`, `branch: [items]` | Sits on the run and does not move the cursor. Place it in the walk **before** the pipe that passes it |
| `support` | `at`, `name`, `skey` (default `01HG`), `direction` (default `UP`) | Does not move the cursor. The point must lie on the centreline (the validator checks) |
| `check` | `label`, `expect` (point), `of` (`"anchor"` default or `"cursor"`), `tol` (default `"0.1/16"`) | Closure check against a stated coordinate. A failure means exit 2 |

## Default SKEYs

Every default is a common Isogen SKEY, **not** a confirmed one for any particular site. Override
with `skey` wherever the user's own Isogen output differs (`reading-isos.md`), and pass the
site's list to `validate_pcf.py --skeys`.

| Item | Default SKEY | Status |
|---|---|---|
| `flange` | `FLWN` | common |
| `blind` | `FLBL` | common |
| `elbow` | `ELBW` | common |
| `tee` | `TEBW` | common; check its SIF-map type |
| `olet` | `WTBW` | common; check its SIF-map type |
| `reducer` concentric / eccentric | `RCBW` / `RECC` | `RCBW` **unconfirmed** - set `skey` from site output |
| `support` | `01HG` | site-specific example only |
| `bend`, `valve`, `gasket`, `cap`, `misc`, `coupling` | none | set `skey` (valves especially) |

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
