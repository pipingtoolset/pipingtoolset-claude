# Tool reference - modules, envelope and pre-flight

Relocated verbatim from the "Running the tool" section of `SKILL.md`. The body keeps the run rules, the command forms and the module ids.

## Pre-flight check

- A pre-flight check runs before the engine. It stops physically impossible inputs with exit code 2 (negative pressure, wall of D/2 or more, `f` above 1.2, `k` outside 1.0 to 1.33, an unrecognised sustained `method`, no fatigue `equation`) and adds warnings for implausible ones (`f` above 1.0, an unusual `k`, a spring `limit` below 1 that looks like a fraction). Quote those warnings in the findings.

## Module table

| Module id | What it does |
|---|---|
| `piping.displacement-stress` | `S_b`, `S_t`, `S_E`, `S_A`, ratio (Eq. 17) |
| `piping.sustained-stress` | `S_Lp`, `S_L`, occasional stress, both ratios (sqrt or additive form) |
| `piping.fatigue-factor` | `N_E` and f for either edition form; output names the equation used |
| `supports.spring-variability` | cold load, load change, variability % vs a limit |
| `supports.max-spring-rate` | stiffest spring meeting a variability fraction |
| `noncode.pipe-section` | ID, A, I, Z, radius of gyration from OD and wall |
| `screen.support-span` | bending span, deflection span, governing span; pass/fail on a proposed span when `L_actual_ft` is given |
| `screen.flexibility-exemption` | `D·y/(L−U)²`, K1, ratio, disqualifiers; `na` when the disqualifier inputs are not all confirmed |

## Output envelope

Each call prints a JSON envelope `{module, status, output, warnings, citation, inputs, user_supplied}`; `user_supplied` lists the inputs that are code or project values the user must be able to cite. Exit code 2 means bad input. Illustrative call (every number below is a placeholder, not a code value):

```
python scripts/stress_screening.py screen.support-span --input '{"w": 24, "E": 1.0e7, "S_allow": 3000, "delta_allow": 0.25, "OD": 6.625, "t": 0.28, "end_condition": "simple"}'
```

Present the output with its citation and warnings, and carry the `equation` string and any warning into the calc sheet. A `status` of `na` means the module reports a value with no pass/fail. The tool does not read tables and does not compute SIFs; every allowable, modulus and `i` in the inputs comes from the user's licensed copy.

## Connector-supplied values (`code_values`)

Every module except `basis` accepts an optional top-level `code_values` block: the route for a value the Engineering Data connector returned, or a value the user read, together with its citation. Shape (a template, not a code value):

```
"code_values": {
  "Sh": {"value": <number from the lookup>, "unit": "ksi",
         "citation": {"standard": "...", "edition": "...", "table": "...", "row": "...", "column": "S"},
         "source": "connector"}
}
```

| Field | Meaning |
|---|---|
| name (the key) | The module input it fills, spelled exactly as `list` prints it (`Sc`, `Sh`). A name the module does not declare stops the run (exit code 2) |
| `value` | A number (or a string), the number as the lookup returned it |
| `unit` | Required. The unit the lookup returned, so ksi stays `"ksi"`; `null` for a dimensionless value. The script converts a unit it can convert exactly (ksi to psi) and says so in `warnings`; any other mismatch is rejected |
| `citation` | `standard`, `edition`, `table` and `row` (all non-empty strings), and `column` when there is one, copied from the lookup's `citation` |
| `source` | `connector` for a returned value, `user` for a value the user read |

Rules:

- An input missing from the main inputs is filled from `code_values[name].value`. An input present in both places with different values stops the run, exit code 2, with `code_values.<name> conflicts with input <name>`; fix the job file, do not edit one side to match.
- The envelope gains `code_value_provenance`, `{name: {unit, citation, source}}`, for every entry. `inputs` shows the values used, and `user_supplied` lists a filled input as it lists a typed one. Quote any unit-conversion note in `warnings`, and copy the provenance into section 3 of the calc sheet with its source column.
- Put only the entries the module being run declares in that job file; an entry for another module's input is an error. The script makes no network calls.
- `Sc` and `Sh` come back from the connector in ksi and the modules take psi: pass `"unit": "ksi"` and let the script convert. `Sc` is read at the minimum metal temperature and `Sh` at the maximum; each is its own lookup. `ii`, `io`, `E`, `Ea`, `S_allow` and `delta_allow` are not connector values; the span from `b311-support-spans` is a cross-check and goes in no module.
