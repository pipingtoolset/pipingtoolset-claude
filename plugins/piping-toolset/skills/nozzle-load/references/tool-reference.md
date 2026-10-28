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
- a missing or non-positive `annexF` constant for the pump type (the message names the key), or an unknown key inside `annexF`;
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

with `check.json` holding `"standard": "PVP2011-57100 Table 1A, derived"`, the `applied` set from the piping run, and `allowable` set to the derived values. Quote the log, the warnings and the citation in the calc sheet.

## What the tool does not do

It does not read tables, does not know any equipment's allowables, does not resolve loads to a point except for pump Annex F, does not check movements, does not draw the API 650 nomograms, and does not decide who must approve a load beyond a standard's limit. Every allowable, limit, figure reading and stress comes from the user's licensed copy.
