# Tool reference - modules, envelope and pre-flight

Detail for the "Running the tool" section of `SKILL.md`. The script is `scripts/nozzle_load.py`; run `python scripts/nozzle_load.py list` for the exact field names (case-sensitive) before writing a job file.

## Module table

| Module id | Origin | Inputs the user reads (never defaulted) | Status |
|---|---|---|---|
| `connections.nozzle-load-check` | pipingtoolset.com calculation engine | `allowable` (six components) | pass or fail |
| `connections.nema-sm23` | pipingtoolset.com calculation engine | `coefficient` | pass or fail |
| `connections.api610-annexf` | pipingtoolset.com calculation engine | `annexF` (the method constants), `suctionAllowable`, `dischargeAllowable`, and for vertical in-line pumps `suctionBore`, `dischargeBore` | pass or fail |
| `equipment.nozzle-load-sum` | new in this pack | `limits` (six components), `multiplier` for a bay | pass or fail |
| `equipment.api650-annexp-ordinates` | new in this pack | `YF`, `YL`, `YC` from the figures | always `na` |
| `equipment.pvp2011-allowables` | new in this pack | the table row (`row`, or `lowerRow` and `upperRow`), `S_vessel`, `S_nozzle`, the table | always `na` |

The first three reproduce the engine's published fixture cases exactly (same input and output names, status strings, rounding and thrown-error conditions). The new modules are checked against hand-derived cases.

## Load sets

Every load set is an object with the six keys `Fx`, `Fy`, `Fz`, `Mx`, `My`, `Mz`, in the equipment's nozzle axes and one consistent unit system. USC modules expect lbf and ft-lbf; the Annex F `units` field selects USC or SI for the unit system of the `annexF` stress constants and for the arm conversion (12 or 1000).

## The `annexF` block

`connections.api610-annexf` requires `annexF`, an object the user fills from the Annex F equations of the edition of record. No key has a default and each must be a number above zero. Horizontal pumps need the first five keys; vertical in-line pumps need the last three, in the `units` system given.

| Key | Where the user reads it |
|---|---|
| `componentMultiple` | F.1.2 a) |
| `resultantDenominator` | Eq. F.1 / F.2 |
| `interactionLimit` | the sum limit of Eq. F.1 / F.2 |
| `centreForceFactor` | Eq. F.3 / F.5 |
| `centreMyFactor` | Eq. F.4 |
| `sigmaPLimit` | Eq. F.6 (SI) or F.9 (USC) |
| `kSigma` | Eq. F.7 (SI) or F.10 (USC) |
| `kTau` | Eq. F.8 (SI) or F.11 (USC) |

A vertical in-line run may also carry `componentMultiple`; without it the informational per-component screen is skipped and a warning says so. The block is echoed in `inputs` and listed in `user_supplied`.

## Per-module outputs

- `connections.nozzle-load-check`: `FR`, `MR` (resultants), `ratios` per component (`|applied| / allowable`), `maxRatio`, `governing`. Pass needs every ratio at or below 1. A warning appears when `maxRatio` exceeds 0.5 as a reminder of PIP RECE002 design-stage limits; it never changes the status.
- `connections.nema-sm23`: `De`, `Fr`, `Mr`, `index` (`3·Fr + Mr`), `allowable` (`coefficient · De`), `ratio`. `De` is the NPS up to 8, otherwise `(NPS + 16)/3`.
- `connections.api610-annexf`: per-component ratios against the `componentMultiple` times the Table 5 range; for `horizontal`, the resultants, Eq. F.1 and F.2 values and ratios, the resolved loads `FXCA` to `MRCA`, and the ratios of Eq. F.3, F.4 and F.5; for `vertical-inline`, the stresses `SigmaL`, `Tau`, `SigmaP` and ratios against the principal stress limit. `checks` lists every equation evaluated; `governingRatio` and `governingEquation` name the controlling one. For a vertical in-line pump the per-component screen is advisory.
- `equipment.nozzle-load-sum`: `sum` (signed), `absoluteSum` (informational, signs aligned), `effectiveLimit` (limit times multiplier), `ratios`, `maxRatio`, `governing`, `FR`, `MR`, `perNozzle`.
- `equipment.api650-annexp-ordinates`: `lambda`, `FP`, `XA_over_sqrtRt`, `XB_over_sqrtRt`, `XC_over_sqrtRt`, `abscissa`, `ordinateP5a`, `ordinateP5b`, and the per-unit-load scale factors `abscissaPerFR`, `ordinateP5aPerML`, `ordinateP5bPerMC`. The status is `na`: plot the points on the printed nomograms.
- `equipment.pvp2011-allowables`: `base` (the row used, after interpolation), `proportionalBound` (interpolation only: the eq. (1) / eq. (2) proportional estimate from each row, lower taken), `thicknessFactor`, `stressRatioVessel`, `stressRatioNozzle`, `stressRatio` (applied), `ownerFactor`, `totalFactor`, `derived` (the six-component allowable set), `log` (one line per factor applied) and `units`.

## Owner factor

`ownerFactor` (0 < f ≤ 1) is optional. On `equipment.pvp2011-allowables` it is part of the derivation. On the other modules that take it, the CLI layer multiplies the entered allowables before the module runs, adds a warning that says so, and echoes the original inputs unchanged. `connections.api610-annexf` with `pumpType` vertical-inline rejects it (exit 2): the factor would scale only the Table 5 ranges, not the F.6 to F.11 principal-stress limit that sets the status. For horizontal pumps the "within the Table 5 range" note is reworded to refer to the factored range. Omit it for no factor.

## Pre-flight check

A pre-flight check runs before the engine and stops with exit code 2 on:

- an unknown module id, an unknown top-level field, or an unknown key inside a load set, a position `{x, y, z}` or a bore `{Do, Di}` (for example `FX` for `Fx`);
- a missing `standard` label on the check and the sum;
- `NPS` or `coefficient` at or below zero for SM-23, a non-positive allowable or limit, a `multiplier` at or below zero, an `ownerFactor` outside (0, 1], or any `ownerFactor` other than 1 with `pumpType` vertical-inline; a non-string `table`;
- an Annex F `pumpType` or `units` outside the allowed values, and missing positions (horizontal) or bores (vertical in-line), or a bore with `Do` not greater than `Di`;
- a missing or non-positive `annexF` constant for the pump type (the message names the key), or an unknown key inside `annexF`; the run stops (exit 2) rather than defaulting it;
- Annex P geometry that is not positive, `L` not greater than `a`, `t` not less than `R`;
- a PVP2011 `table` outside 1A, 1B and 2, a `material` outside the listed values, a non-positive thickness or stress, a `row` given together with an interpolation set, an interpolation NPS outside the two rows, an incomplete interpolation set.

It adds warnings for implausible inputs and for every scope limit: a bay multiplier below 1; a single nozzle in a sum; λ outside 0.1 to 30; T below the table basis; design temperature above 650 F or not stated; a material other than killed carbon steel; aluminium; D/T above 320 or not given; the character of the loads not stated. Quote every warning in the findings.

## Illustrative call

Every number below is a placeholder, not a code value. The row is a flat set of 1000 lbf and 1000 ft-lbf, the vessel thickness 0.1875 in is below the 0.25 in basis of Table 1A, and the stress for the shell is half of the paper's reference value.

```
python scripts/nozzle_load.py equipment.pvp2011-allowables --input-file job.json
```

with `job.json`:

```
{
  "table": "1A", "NPS": 6,
  "row": {"Fx": 1000, "Fy": 1000, "Fz": 1000, "Mx": 1000, "My": 1000, "Mz": 1000},
  "T": 0.1875, "S_vessel": 9400, "S_nozzle": 17100,
  "designTempF": 400, "material": "killed-carbon-steel", "D": 48, "loadsPrimary": false
}
```

The run returns the derived set (the table row times 0.5625 for thickness times 0.5 for the stress ratio, here 281.25 for every component) and a log of each factor. Chain it into the check by copying `derived` into `allowable`:

```
python scripts/nozzle_load.py connections.nozzle-load-check --input-file check.json
```

with `check.json` holding `"standard": "PVP2011-57100 Table 1A, derived"`, the `applied` set from the piping run, and `allowable` set to the derived values. Pass `"derivedSetStatus"` (accepted only on `connections.nozzle-load-check` and `equipment.nozzle-load-sum`; one of the five status words, otherwise exit 2) with the derivation run's `result_status` so the check inherits it. A `standard` label containing "derived" or "PVP2011" without it is manual check required, because the derivation's scope limits are then unknown: a derived set is at least screening, and a derivation that tripped a scope limit makes the check manual check required. Quote the log, the warnings and the citation in the calc sheet.

## Project basis record

Every module accepts the optional top-level object `project_basis` (schema `pipingtoolset.project-basis/1`, fields in [project-basis.md](project-basis.md)) or `--project-basis <file>`; both given and different exits 2 with `project_basis conflicts with --project-basis file`. The record is removed before validation, so it never reaches the engine and fixture parity is untouched. An input absent from the main input is filled from the record; one that is present must agree, otherwise exit 2 with `project_basis.<path> conflicts with input <name>`. This skill's slots:

| Input | Module | Taken from the record |
|---|---|---|
| `units` | `connections.api610-annexf` | `units.system` |
| `designTempF` | `equipment.pvp2011-allowables` | the design state `T_F` (`states[role=design]`, else the first state) |
| `ownerFactorBasis` | `equipment.pvp2011-allowables` | `owner_practice` document and edition; a label the user already wrote is kept |

Read for the sheet only (`noted` in `project_basis_applied.fields_used`): `units.system`, `equipment_axes.nozzle_axis_map` and `owner_practice`. An SI record stops `connections.nema-sm23` and `equipment.pvp2011-allowables` (USC only, exit 2). The `ownerFactor` value is never taken from the record: read it from the owner document and enter it. A numeric owner item with no `ownerFactor` in the run only adds a warning. The envelope gains `project_basis_applied` (`schema`, `fields_used`, `assumptions` copied verbatim, `conflicts`) and `project_basis_section`, the sheet's section 1 with every ASSUMED item first.

## Result status and checks

The envelope gains `result_status` (the worst word among the checks performed; a `not checked` row is listed but never sets it; an ASSUMED item in the record adds one `ASSUMED inputs` row graded manual check required), `checks` (`name`, `result_status`, `status`, `note`), `result_status_line` (the line under the sheet title) and `banner`. Existing `status` words and values do not change. Severity: manual check required, then pointer only, then screening, then not checked, then calculated. No `unresolved_factor` arises here: every constant is a user input or a named constant of the paper.

| Word | When it appears in this skill |
|---|---|
| calculated | the ratio, sum or equation checks on allowables the user entered, with no scope limit tripped |
| screening | the PVP2011 derivation inside the paper's basis; a check or sum against a set marked with `derivedSetStatus` |
| manual check required | a PVP2011 scope limit outside the paper's basis or not stated (NPS range, design temperature, material, D/T, character of the loads, eq. (4) on Table 1B or 2, interpolation above the proportional bound); Annex P lambda outside the plotted range; a derived set that reported this word; a derived-set label with no `derivedSetStatus` |
| pointer only | an owner practice limit recorded in the project basis as a pointer (an item named as a factor, fraction, percent, margin or limit with no numeric value, or a plain-text item with one of those words and no decimal or percent value) while no `ownerFactor` is entered: that check does not run |
| not checked | SM-23 vendor-sheet combined resultant items; Annex F shaft displacement limits and approval, and the skipped per-component screen of a vertical in-line run without `componentMultiple`; API 560 terminal movements when the standard label names 560; the Annex P acceptance boundary |

`banner` is PASS or FAIL for the pass and fail modules and NA for the `na` modules. PASS is replaced by the status word in capitals under manual check required or pointer only (and under screening with an unresolved factor); FAIL always prints. The sheet repeats the banner and the status line.

## What the tool does not do

It does not read tables, does not know any equipment's allowables, does not resolve loads to a point except for pump Annex F, does not check movements, does not draw the API 650 nomograms, and does not decide who must approve a load beyond a standard's limit. Every allowable, limit, figure reading and stress comes from the user's licensed copy.

## Connector-supplied values (`code_values`)

Every module accepts an optional top-level `code_values` block: the route for a value the Engineering Data connector returned, or a value the user read, together with its citation. Shape (a template, not a code value):

```
"code_values": {
  "S_vessel": {"value": <number from the lookup>, "unit": "ksi",
               "citation": {"standard": "...", "edition": "...", "table": "...", "row": "...", "column": "S"},
               "source": "connector"}
}
```

| Field | Meaning |
|---|---|
| name (the key) | The module input it fills, spelled exactly as `list` prints it. A nested input uses a dotted name: `applied.Fx`, `allowable.Mz`, `limits.Fy`, `row.Fx`, `lowerRow.Mx`, `upperRow.My`, `annexF.kSigma`, `suctionBore.Do`, `dischargePosition.x`. A name the module does not declare stops the run (exit code 2) |
| `value` | A number (or a string), the number as the lookup returned it |
| `unit` | Required. The unit the lookup returned, so ksi stays `"ksi"`; `null` for a dimensionless value. The script converts a unit it can convert exactly (ksi to psi) and says so in `warnings`; any other mismatch is rejected |
| `citation` | `standard`, `edition`, `table` and `row` (all non-empty strings), and `column` when there is one, copied from the lookup's `citation` |
| `source` | `connector` for a returned value, `user` for a value the user read |

Rules:

- An input missing from the main inputs is filled from `code_values[name].value`. An input present in both places with different values stops the run, exit code 2, with `code_values.<name> conflicts with input <name>`; fix the job file, do not edit one side to match.
- The envelope gains `code_value_provenance`, `{name: {unit, citation, source}}`, for every entry. `inputs` shows the values used, and `user_supplied` lists a filled input as it lists a typed one. Quote any unit-conversion note in `warnings`, and copy the provenance into section 3 of the calc sheet with its source column.
- Put only the entries the module being run declares in that job file; an entry for another module's input is an error. The script makes no network calls.
- `S_vessel` and `S_nozzle` (`equipment.pvp2011-allowables`) come back in ksi: pass `"unit": "ksi"` and let the script convert. The load-table slots (`allowable`, `suctionAllowable`, `dischargeAllowable`, `limits`) can come back as values too: see [Equipment load tables from the connector](#equipment-load-tables-from-the-connector).
- Every other table row, coefficient, constant and figure reading is pointer-only today: the user reads it, and it is entered as an ordinary input or as a `code_values` entry with `"source": "user"` and the pointer's standard, edition and table in `citation` (the force and moment components of a load set are unit-checked: lbf and ft-lbf, or N and N-m for the `api610-annexf` sets when `units` is `SI`; `nozzle-load-sum` limits take the unit of your load sets and are not checked). An `ownerFactor` is applied after the fill, to the values as filled.

## Equipment load tables from the connector

Currently the connector serves four equipment load tables as cited values at the Ultimate tier: API 610 Tables 5a and 5b, API 660 Table 2, API 661 Table 4 and API 560 Tables 7 to 10. Each table's tier and whether it returns a value or a pointer are stated in each reply and can change, so read the `mode` of every reply and never assume it.

1. `verify_connector` once per session, then `describe_dataset` for the dataset id (its key fields and columns, and the daily lookup limit) and `list_keys` for the exact row text. Do not type a row label from memory: a `lookup_value` with a guessed label returns "No row matches that key", and the fix is `list_keys`, not a retry with another guess. Pass every key field the listed row carries, `line` included.
2. One `lookup_value` call per value. A six-component set is six calls, each with its own citation; a pump's suction and discharge sets are twelve. Use the unit-system columns that match the job: USC lbf and ft-lbf, SI N and N-m.
3. Enter each result as one scalar `code_values` entry with `"source": "connector"`, the lookup's own `unit` and its citation copied whole: `allowable.Fx` to `allowable.Mz`, `suctionAllowable.Fx` to `suctionAllowable.Mz`, `dischargeAllowable.*`, or `limits.*`. The scalar contract above carries them as it is; no other key changes shape.
4. Copy the six citations into section 3 of the calc sheet with `connector` in the source column. If the vendor datasheet gives different values, use those.

| Dataset | Key fields | Columns used |
|---|---|---|
| `api610-nozzle-loads` | `table` (`5a` USC or `5b` SI), `nozzle` (a row label as the table prints it, for example "Each top nozzle", never "suction" or "discharge"), `nps`, `line` | `FX FY FZ MX MY MZ`; not the resultants `FR`, `MR` |
| `api660-nozzle-loads` | `sizeNps`, `flangeClass` (a string, `"150"`), `line` | `FxLbf FyLbf FzLbf MxFtLbf MyFtLbf MzFtLbf`, or `FxN FyN FzN MxNm MyNm MzNm` for SI |
| `api661-nozzle-loads` | `sizeNps` | the same six columns as 660, each a per-nozzle value (7.1.10.1). The header-sum limit of 7.1.10.2 is not a served row: the `limits` slot is read from the copy and entered as a user value |
| `api560-terminal-loads` | `table` (`7` to `10`), `sizeNps`, `component` (`Tubes` or `Manifolds`), `orientation` where the table has it, `line` | the same six columns as 660; not the movement columns of Tables 8 and 10, which this skill does not check |

The table lists the datasets' structure (`describe_dataset` states it in each session), not table values. `line` addresses a row by position when the key fields match more than one. On a `mode` of `pointer`, a reply naming a plan the account is not on, a daily-limit message or any other error, the value is not available through the connector: say in one line what the reply said, do not press the user toward a plan, and use the interview, where the user reads the row from their copy or the vendor datasheet.
