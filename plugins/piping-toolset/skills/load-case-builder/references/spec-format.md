# Load case spec format

`scripts/loadcase_gen.py --spec <file>` reads one JSON object. Build it from the Step 0 interview; every field you could not confirm stays in the spec with its assumed value **and** is listed as ASSUMED in the output.

## Top level

| Field | Required | Type | Meaning |
|---|---|---|---|
| `code` | yes | `"B31.1"` or `"B31.3"` | Governing piping code |
| `edition` | strongly advised | string, e.g. `"2022"` | Code edition. Missing → a BASIS finding. Drives the B31.1-2024 ASD check. |
| `thermal_states` | yes | list of states (below) | One per distinct thermal/pressure condition. The **first** is the primary state used for hanger design, Maximum Operating and the extraction matrix. |
| `occasionals` | no | list of occasionals (below) | Every occasional load, one entry per direction |
| `frictions` | no | list of `[label, multiplier]` | Default `[["w/ Friction", 1.0], ["w/o Friction", 0.0]]`. Multipliers scale the modelled μ. |
| `hangers` | no | bool, default `true` | CAESAR-designed springs. Adds the HGR block and `H` to OPE/SUS. |
| `hydrotest` | no | bool, default `true` | Adds `WW+HP(+H)` |
| `inter_state_expansion_ranges` | no | bool, default `true` | Adds an Algebraic range case between every pair of operating states |
| `occ_combine_method` | no | `"Scalar"` or `"ABS"`, default `"Scalar"` | Method for the SUS + pure-occasional code case |

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
| `scale` | no | ASD reduction factor (0.6 wind, 0.7 seismic). **Only** with a written owner/EOR direction; an error under B31.1-2024. |

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

A full two-state example is in `scripts/examples/two-state-b313.json`. It deliberately puts snow on `U2`, the only vertical uniform vector, so the generator's QC findings (no vertical seismic component; the U2 conflict) have something to report; do not copy that assignment into a real spec.

## Errors

The generator exits with status 2 and a one-line message when the spec cannot produce a valid set: an unknown field, an occasional riding a state that does not exist, an unknown `kind`, or a reference that would point forward. Fix the spec and rerun; never hand-edit the resolved numbers.
