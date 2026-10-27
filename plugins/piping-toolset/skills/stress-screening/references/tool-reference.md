# Tool reference - modules, envelope and pre-flight

Relocated verbatim from the "Running the tool" section of `SKILL.md`. The body keeps the run rules, the command forms and a one-line-per-module table.

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
