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
| `hydrotest` | no | bool, default `true` | Adds `WW+HP(+H)`, one case per friction multiplier, so no friction-dependent hydrotest reaction is missed; confirm in your CAESAR II version that the multiplier is applied to the HYD case (the per-load-case friction multiplier covering HYD was confirmed 2026-10-30 by the author, a licensed P.E.). Each is listed under code stress and under support loads. |
| `inter_state_expansion_ranges` | no | bool, default `true` | Adds an Algebraic range case `OPE(a) − OPE(b)` between every pair of operating states, **per friction multiplier**, named `EXPANSION RANGE <a> to <b> (<friction label>)` |
| `occ_combine_method` | no | `"Scalar"` or `"ABS"`, default `"Scalar"` | Method for the SUS + pure-occasional code case |
| `project_basis` | no | object | A `pipingtoolset.project-basis/1` record ([project-basis.md](project-basis.md)); the same record can come from `--project-basis <file>`, and both given with different content exits 2 with `project_basis conflicts with --project-basis file`. What it fills: [Project basis](#project-basis) |
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

## Project basis

A spec field left out is filled from the record; a spec field that is present must agree, or the run exits 2 with `project_basis.<path> conflicts with input <name>`. The record never overrides the spec.

| Spec field | Record field | Rule |
|---|---|---|
| `code` | `code.standard` | B31.1 or B31.3 only; another standard exits 2 as an unknown code |
| `edition` | `code.edition` | a numeric spec edition is compared as text (`2022` agrees with `"2022"`) |
| `thermal_states` | `states` | one state per record state with a `slot` `T` and `P`: key, name (the key when the name is missing), `slot.T`, `slot.P`, `slot.D`, role, cycles. States with role `hydrotest`, `pneumatic` or `installed` are not thermal states and are skipped. Compared with the spec's states with the defaults made explicit (role `operating`, no `D`, no `cycles`), so an omitted default never conflicts |
| `primary_state` | `states[role=operating\|first].key` | the first operating state among those thermal states, else the first declared one (never the design state by role); filled only when `thermal_states` came from or agreed with the record |
| (`--format` hint) | `load_case_ids.software` | noted; AutoPIPE adds a NOTE finding and a `not checked` item for the occasional construction |
| (note) | `owner_practice[i]` | noted; a friction item with one friction multiplier in the spec adds a NOTE finding |
| (ASSUMED block) | `assumptions` | every ASSUMED item is listed at the top of the report |

A record state with no `T`/`P` slot exits 2 when the spec has no `thermal_states`; when the spec has them, the spec's states are used and a NOTE finding says they were not checked against the record. The report gains section `### 1 Basis` under the title: every ASSUMED item first (the record's, then the generator's defaults), then the record table and the fields taken from it.

The two shipped examples are not a pair: `scripts/examples/project-basis.example.json` is the shared record (identical in every skill, states `OPE1` and `DES`), while `two-state-b313.json` declares its own states `op` and `des`. `--example --project-basis scripts/examples/project-basis.example.json` therefore exits 2 with `project_basis.states conflicts with input thermal_states`, which is the conflict rule working, not a defect. To fill from a record, leave `code`, `edition`, `thermal_states` and `primary_state` out of the spec and set every `occasionals[].base` to a record state key.

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

`--format json` returns `code`, `edition`, `total_cases`, `primary_state`, `hanger_friction` (`null` without hangers), `cases` (the table rows), `extraction_matrix` (`[{purpose, cases: [L-numbers], basis}]`), `qc`, `findings`, `result_status`, `checks` and, with a record, `project_basis_applied` (`{schema, fields_used, assumptions, conflicts}`).

`checks` is `[{name, result_status, status, note}]` and `result_status` is the most severe word among the checks the generator performs; `not checked` rows are listed but never set it ([project-basis.md](project-basis.md#result-status-words)). The markdown report prints it as `Result status: <word> - <why>` under the title.

| Check | Word | Status |
|---|---|---|
| ASSUMED inputs: one row, present only when there is an ASSUMED item (generator defaults for `primary_state` or `hanger_friction`, or an ASSUMED item in the record); note `confirm before issue: <items>` | manual check required | na |
| code edition | manual check required when not stated, else calculated | na / pass |
| QC 4 vertical seismic and U2 | calculated | fail on the GAP or CONFLICT finding; na without seismic |
| QC 5 expansion completeness, QC 7 forward references, QC 17 resolved case set | calculated | pass / fail |
| QC 10 occasional factor | calculated for B31.3 (1.20 noted when the record names Chapter IX or High Pressure service); manual check required for B31.1 (k = 1.15 or 1.20 depends on a duration that is not an input) | na |
| QC 11 ASD position | calculated without a `scale` (pass) and for B31.1-2024 with one (fail); manual check required for any other `scale` (the owner or EOR written direction cannot be verified) | pass / fail / na |
| QC 1, 2, 3, 6, 8, 9, 12, 13, 14, 15, 16; the HYD friction multiplier in the software (hydrotest with more than one friction variant); the AutoPIPE occasional construction (record software AutoPIPE) | not checked | na |

The envelope is therefore `calculated` when everything is declared (the eleven model items stay listed as `not checked` and are summarised after the word) or `manual check required`; `screening` and `pointer only` do not occur, since the generator runs no screening method and takes no code-table value. QC findings keep their `OK:`, `GAP:` and `ERROR:` prefixes under every word: they are check results, not a banner.

`qc` is the resolved-case-set check ([qc-gate.md](qc-gate.md) item 17): `{"pass": bool, "counts": {states, frictions, occasionals, scaled_occasionals, state_pairs_ranged, expected_cases, generated_cases, checks, misses}, "misses": [text]}`. The same result is the last QC finding: `QC: resolved case set complete …` or `ERROR: resolved case set has N miss(es) … Do not issue this set.`

## Errors

The generator exits with status 2 and a one-line message when the spec cannot produce a valid set: an unknown field, an occasional riding a state that does not exist, an unknown `kind`, a `primary_state` that is not a declared state key, a negative or non-numeric `hanger_friction`, an empty `frictions` list, a negative or non-numeric friction multiplier, a `scale` that is not a number with 0 < scale < 1, a duplicated state key, occasional key or friction multiplier (multipliers compared as numbers, so `1` and `1.0` collide; case keys are built from them, so a duplicate would let a reference resolve to the wrong case), or a reference that would point forward. Fix the spec and rerun; never hand-edit the resolved numbers.
