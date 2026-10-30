# Load case spec format

`scripts/loadcase_gen.py --spec <file>` reads one JSON object. Build it from the Step 0 interview; every field you could not confirm stays in the spec with its assumed value **and** is listed as ASSUMED in the output.

## Top level

| Field | Required | Type | Meaning |
|---|---|---|---|
| `code` | yes | `"B31.1"` or `"B31.3"` | Governing piping code |
| `edition` | strongly advised | string, e.g. `"2022"` | Code edition. Missing → a BASIS finding. Drives the B31.1-2024 ASD check. |
| `thermal_states` | yes | list of states (below) | One per distinct thermal/pressure condition. **Every** state, at every friction multiplier, is in Maximum Operating and in every extraction-matrix row it can govern. |
| `primary_state` | advised with more than one state | key of a declared state | The state the hanger design pair runs at (`W+T` of this state, springs Ignored) and the one the matrix lists first. Default: the first declared state, with an `ASSUMED: primary state = <key>` finding when more than one state is declared. Set it to the maximum operating state. It never limits coverage. An unknown key exits 2. |
| `occasionals` | no | list of occasionals (below) | Every occasional load, one entry per direction |
| `frictions` | no | list of `[label, multiplier]` | Default `[["w/ Friction", 1.0], ["w/o Friction", 0.0]]`. Multipliers scale the modelled μ. |
| `hangers` | no | bool, default `true` | CAESAR-designed springs. Adds the HGR block and `H` to OPE/SUS. |
| `hanger_friction` | advised when `hangers` is true | number ≥ 0 | Friction multiplier of the hanger design pair (CAESAR II runs one recommended pair, not one per friction variant). Default: the first `frictions` multiplier, with an `ASSUMED: hanger design pair … runs at friction multiplier <x>` finding. A negative or non-numeric value exits 2. |
| `hydrotest` | no | bool, default `true` | Adds `WW+HP(+H)`, one case per friction multiplier, so no friction-dependent hydrotest reaction is missed; confirm in your CAESAR II version that the multiplier is applied to the HYD case. Each is listed under code stress and under support loads. |
| `inter_state_expansion_ranges` | no | bool, default `true` | Adds an Algebraic range case `OPE(a) − OPE(b)` between every pair of operating states, **per friction multiplier**, named `EXPANSION RANGE <a> to <b> (<friction label>)` |
| `occ_combine_method` | no | `"Scalar"` or `"ABS"`, default `"Scalar"` | Method for the SUS + pure-occasional code case |
| `code_values` | no | object | Absent, `null` or `{}` only. The generator has no code-table input, so a block with any entry exits 2 with `code_values.<name> is not an input of loadcase_gen.py`; a value is never dropped silently. The shared shape is `{name: {value, unit, citation, source}}` |

## Thermal state

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | Short symbolic handle, unique (`"op"`, `"des"`, `"steamout"`) |
| `name` | yes | Description text used in case labels |
| `T`, `P` | yes | CAESAR II vectors, e.g. `"T1"`, `"P1"` |
| `D` | no | Imposed displacement vector for this state, e.g. `"D1"` |
| `role` | no | `"operating"`, `"design"`, `"upset"`, `"steamout"` … (documentation only) |
| `cycles` | no | Equivalent full cycles N for this state (feeds the f factor in the stress check) |

## Occasional

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | Unique handle (`"win_px"`) |
| `name` | yes | Description, e.g. `"Wind +X"` — must match the vector and sign (QC item 3) |
| `vector` | yes | `"U1"`/`"U2"`/`"U3"`, `"WIN1"`–`"WIN4"`, `"F1"`… |
| `sign` | no | `"+"` (default) or `"-"` |
| `base` | no | Key of the thermal state it rides on; default `"op"` |
| `kind` | no | `"psv"`, `"seismic"`, `"snow"`, `"wind"` or `"other"`; sets which Max envelope it joins |
| `scale` | no | ASD reduction factor, a number with 0 < scale < 1, supplied by the user (for example 0.6 wind, 0.7 seismic). **Only** with a written owner/EOR direction; an error under B31.1-2024. The scaled `OPE+OCC` case (labelled `REDUCED`) feeds the code-stress occasional path only. The generator adds an **unreduced companion** per occasional × friction (block `OPE+OCC-UNRED`, labelled `UNREDUCED`), and Maximum Operating, support loads and displacements read the companion, never the reduced case. With no `scale` anywhere no companion is added. |

## Minimal example

```json
{
  "code": "B31.1",
  "edition": "2024",
  "thermal_states": [
    {"key": "op", "name": "NORMAL OPERATING", "T": "T1", "P": "P1"}
  ],
  "occasionals": [
    {"key": "seis_px", "name": "Seismic +X", "vector": "U1", "sign": "+", "kind": "seismic"},
    {"key": "seis_mx", "name": "Seismic -X", "vector": "U1", "sign": "-", "kind": "seismic"},
    {"key": "seis_v",  "name": "Seismic vertical", "vector": "U2", "sign": "-", "kind": "seismic"}
  ]
}
```

A full two-state example is in `scripts/examples/two-state-b313.json`. It deliberately puts snow on `U2`, the only vertical uniform vector, so the generator's QC findings (no vertical seismic component; the U2 conflict) have something to report; do not copy that assignment into a real spec. It also leaves `primary_state` and `hanger_friction` unset, so its output shows the two ASSUMED findings; set both in a real spec.

## Output

`--format json` returns `code`, `edition`, `total_cases`, `primary_state`, `hanger_friction` (`null` without hangers), `cases` (the table rows), `extraction_matrix` (`[{purpose, cases: [L-numbers], basis}]`), `qc` and `findings`.

`qc` is the resolved-case-set check ([qc-gate.md](qc-gate.md) item 17): `{"pass": bool, "counts": {states, frictions, occasionals, scaled_occasionals, state_pairs_ranged, expected_cases, generated_cases, checks, misses}, "misses": [text]}`. The same result is the last QC finding: `QC: resolved case set complete …` or `ERROR: resolved case set has N miss(es) … Do not issue this set.`

## Errors

The generator exits with status 2 and a one-line message when the spec cannot produce a valid set: an unknown field, an occasional riding a state that does not exist, an unknown `kind`, a `primary_state` that is not a declared state key, a negative or non-numeric `hanger_friction`, an empty `frictions` list, a negative or non-numeric friction multiplier, a `scale` that is not a number with 0 < scale < 1, a duplicated state key, occasional key or friction multiplier (multipliers compared as numbers, so `1` and `1.0` collide; case keys are built from them, so a duplicate would let a reference resolve to the wrong case), or a reference that would point forward. Fix the spec and rerun; never hand-edit the resolved numbers.
