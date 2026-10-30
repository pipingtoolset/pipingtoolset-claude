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

Each call prints a JSON envelope `{module, status, output, warnings, citation, inputs, user_supplied}` plus the fields described under Result status below; `user_supplied` lists the inputs that are code or project values the user must be able to cite. Exit code 2 means bad input. Illustrative call (every number below is a placeholder, not a code value):

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

## Connector lookups by slot

| Slot | Tool and dataset_id | Key fields | What comes back |
|---|---|---|---|
| `Sc` at minimum metal temperature, `Sh` at maximum | `lookup_value`: `b313-allowable-stresses-2024` (B31.3) or `b311-allowable-stresses-2024` (B31.1) | `spec`, plus `grade`, `productForm` and any other discriminator the reply names; `T` (°F); `column` `S` | `S` in ksi, interpolated between the two tabulated temperatures |
| Suggested span (cross-check only) | `lookup_value`: `b311-support-spans` | `nps` | `waterFt`, `steamFt` |
| SIF source row (citation only) | `lookup_value`: `b31j-components` | `sketch` | `title`, `group`, `inputs`, `applicability`, `notes`: row text, never an `i` |

## Result status

Every envelope carries `result_status` (the worst word among the checks performed; a `not checked` row is listed but never sets it), `checks` (`[{name, result_status, status, note}]`, `status` being the pass, fail or na the module already reported), `result_status_line` (the line for under the sheet title) and `banner` (PASS or FAIL for a module with a verdict, null for `na`; the status word in capitals instead of PASS while the banner rule blocks it). The words, worst first: **manual check required**, **pointer only**, **screening**, **not checked**, **calculated**. The existing `status` and `output` values are unchanged.

| Module | Check and word | Raised when |
|---|---|---|
| `piping.displacement-stress` | S_E against S_A: calculated | always |
| | f above 1.0: manual check required | `f` > 1.0; the fm = 1.2 conditions (ferrous, SMTS, metal temperature) need material data this script does not have |
| `piping.sustained-stress` | S_L and S_L + S_occ: calculated | always |
| | occasional factor k: manual check required | k is not 1.15, 1.20 or 1.33 |
| | k duration basis: not checked | k = 1.15 or 1.20; the duration is not an input |
| `piping.fatigue-factor` | f and N_E: calculated | always |
| | f above 1.0: manual check required | the computed f is above 1.0 |
| | equation against code edition: calculated or not checked | calculated when a project basis record resolved it, otherwise not checked (use `basis`) |
| `supports.spring-variability` | variability against the limit: calculated | always |
| | limit unit: manual check required | `limit` is between 0 and 1 and may be a fraction |
| `supports.max-spring-rate`, `noncode.pipe-section` | the computed value: calculated | always |
| `screen.support-span` | span, bending and deflection: screening | always (a screen by definition) |
| | pressure stress in the span: not checked | `S_pressure` omitted and taken as 0 |
| | loads outside the screen: not checked | always (the module's own "not covered" list) |
| `screen.flexibility-exemption` | ratio against K1: screening | always |
| | disqualifier inputs: manual check required or calculated | manual check required when `fixation_points`, `intermediate_restraints` or `uniform_size` is missing |
| | D basis or K1 form: not checked or manual check required | not checked for B31.1 2016 or later; manual check required when `code` is absent or other than B31.3, or B31.1 is earlier than 2016 or has no edition |
| | effects the exemption does not discharge: not checked | always |

Each module also lists its permanent limits as `not checked` on every run (the `NOT_CHECKED` table in the script; the sheet must not imply them):

| Module | Listed on every run |
|---|---|
| `piping.displacement-stress` | SIF source and tee orientation (every `i` is the caller's); liberal allowance Eq. (1b) (`S_A` here is the base form only) |
| `piping.sustained-stress` | sustained index and section basis applied to `Sb`; occasional event and ASD position behind `Socc` |
| `piping.fatigue-factor` | load ranges behind `N` |
| `supports.spring-variability`, `supports.max-spring-rate` | installed (cold) case and constant-support deviation; the manufacturer's spring size |
| `screen.support-span` | wall basis of the section (plus the two span entries above) |
| `screen.flexibility-exemption`, `noncode.pipe-section` | none beyond the entries in the table above (the section is geometry only) |

A clean run of a module that performs its checks reads `calculated`; its listed limits stay in `checks` as `not checked` and the status line reads "<first check> calculated; not performed by this module: ...". `not checked` never sets the word and never blocks the banner.

An ASSUMED item in a project basis record is an unconfirmed input: it adds one `ASSUMED inputs` check, graded `manual check required`, with the note "confirm before issue: <items>". The envelope follows it and the banner prints MANUAL CHECK REQUIRED instead of PASS until the item is confirmed. The `basis` command prints the edition as the record or `--edition` gave it (the string "2022").

Pointer only does not occur in this skill. A pointer reply from the connector carries no value and is never passed to the script; the value stays a user-read input (see the connector section of `SKILL.md`). Screening never carries an unresolved reconstructed factor here: the span coefficients are derived in the tool source and every other factor is an input.

## Project basis fill map

`--project-basis <file>` or a top-level `project_basis` object (the schema and the conflict rule are in [project-basis.md](project-basis.md)). A job file may hold `project_basis` beside its module sections. An input that is absent is filled; one that is present and different stops the run with exit code 2 and `project_basis.<path> conflicts with input <name>`.

| Input | Taken from the record | Notes |
|---|---|---|
| `equation` (`piping.fatigue-factor`) | `code.standard` and `code.edition`, resolved as `basis` does | skipped for a standard other than B31.1 and B31.3 |
| `N` (`piping.fatigue-factor`) | `cycles` of the one state that carries it | not filled when `sets` is given, or when several states carry cycles (a warning says so) |
| `code`, `edition` (`screen.flexibility-exemption`) | `code.standard` (B31.1 or B31.3 only), `code.edition` | an edition typed as a number stays a number |
| `--code`, `--edition` (`basis`) | `code.standard`, `code.edition` | |
| none (sheet only) | `states`, `installation_T_F`, `owner_practice`, `code`, `units.system` | listed as noted in `project_basis_applied` |

A record with `units.system` SI stops the run: the modules take psi, in, ft and lb. The envelope gains `project_basis_applied` and `basis_section` (markdown for section 1 of the sheet, ASSUMED items first). The `basis` command prints both too. Without a record nothing changes.
