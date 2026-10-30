# Pressure design modules - detail

Per-module equations, inputs, validity limits and reviewer notes for the pressure-design skill. Relocated from SKILL.md; the module list, units and field names always come from `python scripts/pressure_design.py list`.

## Table names by edition

A pointer only, moved from the Step 0 interview: in B31.3 the basic allowable stress table is Table A-1 through the 2022 edition and Table A-1C in 2024, and the quality-factor tables are A-1A / A-1B through 2022 and A-2 / A-3 in 2024. Confirm the table name in your copy (ask the user to check the printed page of their own).

## 1. Straight pipe — pressure design thickness, B31.3

Module `piping.b313-wall-thickness`. Citation: B31.3 para. 304.1.2, Eq. (3a).

```
t      = P·D / [ 2·(S·E·W + P·Y) ]        pressure design thickness
tm     = t + c                             minimum required thickness
tOrder = tm / (1 − mill tolerance)         nominal wall to order
```

| Input | Units | Source |
|---|---|---|
| P, D | psi, in. | design basis |
| **S, E, W, Y** | psi, –, –, – | **user-supplied** table values |
| c | in. | corrosion + erosion + mechanical allowances |
| millTolerance | fraction | material specification |
| `W_basis`, `edition` | text | basis inputs, recorded on the sheet and never used in the equation (see below) |

**Validity gate.** Eq. (3a) is the thin-wall form: B31.3 para. 304.1.2(b) calls for special consideration of theory of failure, fatigue and thermal stress when **t ≥ D/6 or P/(S·E) > 0.385**. The script tests both and reports them in a `validity` object: `P_over_SE` (P/(S·E), W not included, as the clause writes it), `P_over_SE_limit` 0.385, `P_over_SE_exceeds`, `thickness` (t), `D_over_6`, `t_over_D6`, `thin_wall_valid` and the `clause`. Inside both limits the run carries `result_grade` `calculated` and the numbers are unchanged. When either trips, the run **stops as a design basis**: `status` and `result_grade` are `manual check required`, `output` is empty, the numbers move to `equation_value` labelled "equation value, not a design basis", and `banner` (also the first warning) names the trigger and the clause. Write no PASS and no schedule on such a run: report the ratio, the equation value as an equation value, and that the thickness needs the special-consideration treatment of 304.1.2(b), outside this script.

**W and its basis.** Eq. (3a) carries W in every B31.3 edition this pack covers. `W` is a required input; **W = 1.0 is accepted only with `W_basis`**, a short reason recorded on the sheet: `seamless`, `below creep range per table note`, `longitudinal weld, confirmed`, or free text. W = 1.0 with no `W_basis` (and no cited `code_values` entry for W) exits 2 with the table to read: Table 302.3.5 through the 2022 edition, Table 302.3.5-1 in 2024 (para. 302.3.5(e)); give `edition` and the message names the one for that year. A reduced W (below 1.0) runs without a basis; cite its table line in section 3. The envelope's `weld_factor_basis` records W, the basis and where it came from; `defaults_applied` never holds W.

**Report:** t, tm, tOrder, and the selected nominal wall (next section). State that tOrder already includes the mill under-tolerance and that `c` is the sum of every allowance.

## 2. Straight pipe — pressure design thickness, B31.1

Module `piping.b311-wall-thickness`. Citation: B31.1 para. 104.1.2.

```
tm     = P·D / [ 2·(S·E·W + P·y) ] + A
tOrder = tm / (1 − mill tolerance)
```

The module's `t` is the pressure term before the allowance and `tm = t + A`. User-supplied: **S, E, W, y**.

**W and its basis.** W is a live multiplicative term in Eq. (7) from the 2018 edition on (para. 102.4.7, Table 102.4.7-1). For those editions, and when `edition` is not given, W omitted with no `W_basis`, or W = 1.0 with no `W_basis`, exits 2 naming Table 102.4.7-1 and the edition; W omitted with a `W_basis` is applied as 1.0 on that basis and shown in `inputs`. In **B31.1-2016** para. 104.1.1 picks the equation: Eq. (7) of para. 104.1.2 (no W) for seamless pipe or pipe below the creep range, Eq. (11) of para. 104.1.4 (S·E·W, the engine's own form) for longitudinal- or spiral-welded pipe in the creep range, with W from Table 102.4.7. Because that route can require W, a 2016 run still needs W or a `W_basis` naming the route (exit 2 otherwise, naming para. 104.1.1 and Table 102.4.7). A W below 1.0 is recorded as the para. 104.1.4 route; W = 1.0 or a basis alone is recorded as para. 104.1.2 and a warning puts the para. 104.1.4 limit on the sheet. Any other year is treated as carrying W.

**Validity gate.** B31.1 reads the thick-wall case as Do/tm < 6: the general note to the y table (Table 104.1.2-1; Table 104.1.2(A) in 2016) replaces y there, and this script does not apply that note. The `validity` object therefore compares **tm** (not t) with D/6. B31.1 states no P/(S·E) limit; the pack also stops the run at the B31.3 304.1.2(b) trigger, P/(S·E) > 0.385, as a pack rule confirmed by the P.E. 2026-10-30 (author, licensed P.E.) (not a B31.1 requirement), and the `clause` says so. A trip gives `manual check required` exactly as in section 1.

## 3. Schedule check and allowable pressure (MAWP)

Module `piping.b31-allowable-pressure`. Citation: B31.3 para. 304.1.2 Eq. (3a), solved for P.

```
tp = t_nominal·(1 − mill tolerance) − A          thickness available for pressure
P  = 2·S·E·W·Mf·tp / ( D − 2·y·tp )
```

Workflow for a schedule check:

1. Section 1 or 2 gives tOrder.
2. Ask the user to read the nominal wall of the candidate standard wall (ASME B36.10M / B36.19M, or the mill's data) for this NPS. **Do not supply it.** With the connector it comes from `get_pipe_dimensions` and is recorded as connector-supplied.
3. Check nominal ≥ tOrder. Then run this module with the selected nominal wall to report the actual allowable pressure and compare to design pressure. The margin is the finding.

The coefficient field is named `y` in this module for both codes: enter Y (B31.3, Table 304.1.1) or y (B31.1, Table 104.1.2(A) / 104.1.2-1) there and say which on the sheet. `Mf` is the B31.12 hydrogen material performance factor; use 1.0 for every other code. If no thickness remains after tolerance and allowances the module returns `fail` with allowable pressure 0, and no validity gate is applied.

**Code, W and its basis.** Give `code` (`B31.3`, `B31.1`, `B31.9` or `B31.12`) and `edition`. W multiplies `S·E` exactly as in the thickness equation. For B31.3, for B31.1 from 2018, and when `code` is not given, W omitted or W = 1.0 needs `W_basis` (exit 2 otherwise, naming B31.3 Table 302.3.5 / 302.3.5-1 or B31.1 Table 102.4.7-1). B31.9 and B31.12 equations have no W term: the run records that and needs no basis; a W below 1.0 entered for them is applied and warned as conservative. B31.1-2016 follows the para. 104.1.1 route of section 2.

**Validity gate.** The `validity` object reports `P_over_SE` with P = the **computed allowable pressure** (times Mf for B31.12, as B31.12 para. IP-3.2.1(b) writes it), against 0.385, and the **nominal wall t** against D/6 (the engine's own check, conservative against tp). Either trip gives `manual check required`: the allowable pressure is then an equation value, not a design basis, and is not compared with the design pressure as a pass.

## 4. Branch connection reinforcement — area replacement

Module `piping.branch-reinforcement`. Citation: B31.3 para. 304.3.3.

```
d1 = [ Db − 2·(Tb − c) ] / sinβ                     effective opening
d2 = max[ d1 , (Tb − c) + (Th − c) + d1/2 ]         reinforcement half-width
L4 = min[ 2.5·(Th − c) , 2.5·(Tb − c) + Tr ]        reinforcement height
A1 = th·d1·(2 − sinβ)                                area required
A2 = (2·d2 − d1)·(Th − th − c)                       excess in header
A3 = 2·L4·(Tb − tb − c) / sinβ                       excess in branch
A4 = pad area inside the zone + welds (supplied)
PASS if  A2 + A3 + A4 ≥ A1
```

Inputs: header `Dh, Th, th`, branch `Db, Tb, tb`, allowance `c`, branch angle `betaDeg` (45–90), pad `Tr, Dp` (0 if none), and `A4welds`, the added area of welds and other metal inside the zone. No input here is a code-table value. **`th` and `tb` are pressure design thicknesses from Section 1 or 2** for header and branch, each with its own E, W and Y — run the wall-thickness calc for both first and quote them.

Notes a reviewer will ask about:

- **Check first whether the calc is needed.** A listed fitting or a connection that meets the clause's own exemptions needs no area calc; look at 304.3.2 before running this one.
- `Th` and `Tb` are the measured or minimum thicknesses in the clause, not corroded and not necessarily catalog nominal. If you only have nominal, say which you used; using nominal × (1 − mill tolerance) is the conservative reading.
- The script implements the B31.3 area method. B31.1 (104.3.1) and other sections carry code-specific zone rules; if the project is B31.1, say the result is a screening check against the B31.3 form and have the user confirm the zone limits.
- Warnings are findings: header undersized for pressure alone (A2 < 0), pad outside the zone (no credit taken), or a zone wider than the header (check adjacent openings).
- The margin is `(A2 + A3 + A4) − A1`. Report it in in.², with the status.

## 5. Pipe bends — thickness after bending

Module `piping.bend-thickness`. Citation: B31.3 para. 304.2.1 (I-factor), B31.1 para. 102.4.5.

```
I_intrados  = [ 4·(R/D) − 1 ] / [ 4·(R/D) − 2 ]
I_extrados  = [ 4·(R/D) + 1 ] / [ 4·(R/D) + 2 ]
I_sidewall  = 1
tm(I) = P·D / ( 2·[ S·E·W / I + P·y ] ) + A
```

`R` is the bend radius to the **centerline**. User-supplied: **S, E, W** and the coefficient (field `y`; Y for B31.3, y for B31.1). Give `code` (`B31.3` or `B31.1`) and `edition`: W omitted or W = 1.0 needs `W_basis` as in sections 1 and 2 (B31.1-2016 Eq. (3) has no W). Eq. (3c) is the straight-pipe equation with S·E·W divided by I, so the same thin-wall gate applies: `validity` reports P/(S·E) against 0.385 and the intrados pressure thickness (tmIntrados − A, the largest on the bend) against D/6, and a trip gives `manual check required`. The module reports the required minimum thickness at the intrados, extrados and sidewall. These are the thicknesses required **after bending**: the intrados requirement is the largest, but the extrados thins during forming, so the *pre-bend* wall must be chosen against the bending process's predicted thinning. The script does not predict that thinning; get it from the bender and state the source. A warning appears for R/D < 1 — tight radii need the bending procedure confirmed.

## 6. Mitered bends — allowable pressure

Module `piping.miter-allowable-pressure`. Citation: B31.3 para. 304.2.3, Eq. (4a)/(4b)/(4c).

```
Multiple miters, θ ≤ 22.5°:   P = min(Pm1, Pm2)
  Pm1 = (S·E·W·Tc / r2) · Tc / ( Tc + 0.643·tanθ·√(r2·Tc) )            Eq. (4a)
  Pm2 = (S·E·W·Tc / r2) · (R1 − r2) / (R1 − r2/2)                       Eq. (4b)
Single miter, θ ≤ 22.5°:      P = Pm1  (the same form as Eq. (4a))
Single miter, θ > 22.5°:
  Pm  = (S·E·W·Tc / r2) · Tc / ( Tc + 1.25·tanθ·√(r2·Tc) )             Eq. (4c)
```

The script implements exactly these branches (B31.3 ¶304.2.3); verify the equation numbering in your edition. For a single miter, `Pm2` is not evaluated and is reported as `null` in the output.

`Tc` is the wall available for pressure (thickness less tolerance and allowances), `r2` the mean pipe radius, `R1` the effective bend radius to the centerline, `θ` the miter half-angle (the angle of cut), and `miters` the number of cuts. User-supplied: **S, E, W**; W omitted or W = 1.0 needs `W_basis` (B31.3 Table 302.3.5 / 302.3.5-1). The result names the governing equation. Eq. (4a)–(4c) are not the 304.1.2 straight-pipe equation and the clause states no D/6 or P/(S·E) limit for them, so this module carries no thin-wall `validity` gate.

The script does **not** check the clause's minimum `R1` for a multiple miter, which depends on a tabulated size-dependent value — have the user check it on their copy. A multiple miter with θ > 22.5° is flagged as outside Eq. (4a)/(4b); treat those as single miters.

## 7. Leak test pressure

Module `piping.leak-test-pressure`. Citation: B31.3 para. 345.4.2 Eq. (24) and 345.5.4; B31.1 para. 137.

```
P_hydro = hydroFactor · P · (ST / S)                 optional ceiling on ST/S: stressRatioCap
P_pneu  = pneumaticFactor · P
```

`ST` is the allowable stress at the **test** temperature and `S` at the **design** temperature, both from the same table line — **user-supplied**, as are the two factors. Both codes use 1.5 for the hydrostatic factor. The pneumatic factor is a code factor that the user supplies: use the code's pneumatic factor (B31.3 ¶345.5.4; B31.1 ¶137.5) and confirm the value in your edition. Cite the paragraph on the sheet.

Points to state on the sheet:

- **No ceiling on ST/S is applied by default.** The engine's reference notes record that Eq. (24) carries no limit on the ratio in the 2016–2024 B31.3 texts (confirm on the edition of record); the code's own limit is the yield / component-rating ceiling of 345.2.1(a), which this script does **not** evaluate — the user must check the resulting stress. `stressRatioCap` is optional and represents an **owner specification** limit only. If the cap engages, the script says so and reports the uncapped code minimum in the warning.
- `pneumaticMaxFactor` is optional; if supplied and exceeded, a warning cites 345.5.4. The second 345.5.4 limit (90 % of the 345.2.1(a) pressure) is not evaluated.
- The result is the **piping minimum**. Flange, valve and equipment test limits must be checked separately; the script always prints that warning.
- For a system of mixed materials, run each and state which ratio governs.

## Connector-supplied values (`code_values`)

Every module accepts an optional top-level `code_values` block: the route for a value the Engineering Data connector returned, or a value the user read, together with its citation. Shape (a template, not a code value):

```
"code_values": {
  "S": {"value": <number from the lookup>, "unit": "ksi",
        "citation": {"standard": "...", "edition": "...", "table": "...", "row": "...", "column": "S"},
        "source": "connector"}
}
```

| Field | Meaning |
|---|---|
| name (the key) | The module input it fills, spelled exactly as `list` prints it (`S`, `ST`, `E`, `W`, `Y`, `y`, `t`). A name the module does not declare stops the run (exit code 2) |
| `value` | A number (or a string), the number as the lookup returned it |
| `unit` | Required. The unit the lookup returned, so ksi stays `"ksi"`; `null` for a dimensionless value. The script converts a unit it can convert exactly (ksi to psi) and says so in `warnings`; any other mismatch is rejected |
| `citation` | `standard`, `edition`, `table` and `row` (all non-empty strings), and `column` when there is one, copied from the lookup's `citation` |
| `source` | `connector` for a returned value, `user` for a value the user read |

Rules:

- An input missing from the main inputs is filled from `code_values[name].value`. An input present in both places with different values stops the run, exit code 2, with `code_values.<name> conflicts with input <name>`; fix the job file, do not edit one side to match.
- The envelope gains `code_value_provenance`, `{name: {unit, citation, source}}`, for every entry. `inputs` shows the values used, and `user_supplied` lists a filled input as it lists a typed one. Quote any unit-conversion note in `warnings`, and copy the provenance into section 3 of the calc sheet with its source column.
- Put only the entries the module being run declares in that job file; an entry for another module's input is an error. The script makes no network calls.
- `S` and `ST` come back from the connector in ksi and the modules take psi: pass `"unit": "ksi"` and let the script convert. `E`, `W`, `Y` and `y` are dimensionless (`"unit": null`). `t` (`piping.b31-allowable-pressure`) is in inches, as `get_pipe_dimensions` returns it.
- `piping.b31-allowable-pressure` takes the coefficient as `y` for both codes: fill it from the `Y` or `y` lookup and say which on the sheet.

## Project basis and result status (0.8.0)

The shared record and the five status words are described in [project-basis.md](project-basis.md). This skill's part:

**Fill map.** With a `project_basis` object in the job file, or `--project-basis project-basis.json` on the command line (both given with different content exits 2):

| Input | From the record | Rule |
|---|---|---|
| `code` (MAWP and bend modules) | `code.standard` | `ASME B31.3` and `B31.3` read the same. On every module the standard must be one the module serves (b313 and miter: B31.3; b311: B31.1, B31.5, B31.9; MAWP: B31.3, B31.1, B31.9, B31.12; bend: B31.3, B31.1; branch and leak test: B31.3, B31.1), else exit 2 `project_basis.code.standard conflicts with input <module> ...` |
| `edition` (modules that carry W) | `code.edition` | `2022` typed as a number agrees with `"2022"` |
| `P` (b313, b311, bend, leak test) | the design state's `P_psig` (role `design`, else the first state) | a different typed P exits 2 |
| `W_basis` (modules that carry W) | `materials[use=pipe]` with form `seamless` | only when `W_basis` is absent and W is absent or 1.0; the E-below-1 warning still fires |
| none (MAWP, miter) | the design state's `P_psig` | compared with `allowablePressure` as a calculated check |
| none | design `T_F`, the pipe material, `owner_practice`, `project`, `service.fluid_category` | recorded as `noted` for the sheet |

`units.system` SI exits 2: the engine is US customary. An input present in both places that differs exits 2 with `project_basis.<path> conflicts with input <name>`. The envelope gains `project_basis_applied` and `basis_section`, the markdown for calc-sheet section 1 with every ASSUMED item first.

**Checks.** Every envelope carries `result_status`, `checks[]`, `banner_allowed` and `result_status_line` (copy it under the sheet title). `status` keeps its words.

| Word | When this skill gives it |
|---|---|
| calculated | per check: the module's own check ran from the inputs given; the validity gate held; the allowable pressure was compared with a design pressure from the record. As the envelope word: every clean run, since `not checked` rows never set it |
| screening | branch reinforcement on a B31.1 record: the B31.3 area method used as a screening check (section 4) |
| manual check required | the thin-wall validity gate tripped; or the record has an ASSUMED item (one `ASSUMED inputs` row, note `confirm before issue: <items>`, `banner_allowed` false); or the record says Category M, High Pressure, or a Chapter VIII / IX route, whose additional requirements this skill does not evaluate. The fluid-service flag also adds a `MANUAL CHECK REQUIRED:` warning, sets `banner` when no gate or pointer banner holds it, and sets `result_grade` to `manual check required` on the gated modules; `status` and `output` keep the engine's words and numbers |
| pointer only | a `code_values` entry `{"mode": "pointer", "citation": {"standard", "table", ...}, "source": "connector"}` with no value: `status` and `result_grade` are `pointer only`, `output` is empty, no equation runs, and `value_pointers` names where to read the value |
| not checked | the module's known limits: nominal wall against tOrder and external pressure (straight pipe); para. 304.3.2 need for the calculation and adjacent openings (branch); thinning during bending (bend); minimum R1 (miter); para. 345.2.1(a) stress, the para. 345.5.4 90 % limit and component limits (leak test); allowable pressure against design pressure when no record gives one (MAWP, miter) |

A clean run of a module with listed limits reads `calculated`: the limits stay in `checks` as `not checked`, `banner_allowed` stays true and the line names what was not performed. Write no PASS, schedule or margin while `banner_allowed` is false, whatever `status` says: `status` is the engine's word and may read `pass` or `fail` beside a blocking `result_status`.

The shipped `scripts/examples/project-basis.example.json` is the pack's shared sample and is independent of `b313-wall-thickness.json`: its design state P differs from that file's P, so pairing the two exits 2 with `project_basis.states[role=design|first].P_psig conflicts with input P`. Drop P from the job file to take it from the record, or edit the record's design state.
