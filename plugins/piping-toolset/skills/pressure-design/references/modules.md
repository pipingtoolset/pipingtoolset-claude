# Pressure design modules - detail

Per-module equations, inputs, validity limits and reviewer notes for the pressure-design skill. Relocated from SKILL.md; the module list, units and field names always come from `python scripts/pressure_design.py list`.

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

**Validity.** Eq. (3a) is the thin-wall form for t < D/6. The script warns when t ≥ D/6. The code's thick-wall trigger is also **P/(S·E) > 0.385** — the script does **not** test that, so compute it by hand and report it. Past either limit the clause calls for special consideration, and the number from this equation is not a design basis.

**Report:** t, tm, tOrder, and the selected nominal wall (next section). State that tOrder already includes the mill under-tolerance and that `c` is the sum of every allowance.

## 2. Straight pipe — pressure design thickness, B31.1

Module `piping.b311-wall-thickness`. Citation: B31.1 para. 104.1.2.

```
tm     = P·D / [ 2·(S·E·W + P·y) ] + A
tOrder = tm / (1 − mill tolerance)
```

The module's `t` is the pressure term before the allowance and `tm = t + A`. **W** is a live multiplicative term in Eq. (7) from the 2018 edition on; omitting it is equivalent to W = 1.0, which the script applies silently if the field is absent — watch `defaults_applied`, and confirm from the table notes whether W = 1.0 is justified at the design temperature. User-supplied: **S, E, W, y**. The same thin-wall limits apply (t < D/6, P/(S·E) ≤ 0.385 — hand-check the second).

## 3. Schedule check and allowable pressure (MAWP)

Module `piping.b31-allowable-pressure`. Citation: B31.3 para. 304.1.2 Eq. (3a), solved for P.

```
tp = t_nominal·(1 − mill tolerance) − A          thickness available for pressure
P  = 2·S·E·Mf·tp / ( D − 2·y·tp )
```

Workflow for a schedule check:

1. Section 1 or 2 gives tOrder.
2. Ask the user to read the nominal wall of the candidate standard wall (ASME B36.10M / B36.19M, or the mill's data) for this NPS. **Do not supply it.** With the connector it comes from `get_pipe_dimensions` and is recorded as connector-supplied.
3. Check nominal ≥ tOrder. Then run this module with the selected nominal wall to report the actual allowable pressure and compare to design pressure. The margin is the finding.

The coefficient field is named `y` in this module for both codes: enter Y (B31.3, Table 304.1.1) or y (B31.1, Table 104.1.2(A)) there and say which on the sheet. `Mf` is the B31.12 hydrogen material performance factor; use 1.0 for every other code. Enter the weld joint strength reduction factor `W` (B31.3 Table 302.3.5-1 / B31.1 Table 102.4.7-1; confirm the table name in your copy) whenever the pipe is welded and W can be below 1.0 — it multiplies `S·E` exactly as in the thickness equation. It defaults to 1.0, which is also the value for codes with no W term (B31.9, B31.12); say on the sheet when the default was used. If no thickness remains after tolerance and allowances the module returns `fail` with allowable pressure 0.

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

`R` is the bend radius to the **centerline**. User-supplied: **S, E, W** and the coefficient (field `y`; Y for B31.3, y for B31.1). The module reports the required minimum thickness at the intrados, extrados and sidewall. These are the thicknesses required **after bending**: the intrados requirement is the largest, but the extrados thins during forming, so the *pre-bend* wall must be chosen against the bending process's predicted thinning. The script does not predict that thinning; get it from the bender and state the source. A warning appears for R/D < 1 — tight radii need the bending procedure confirmed.

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

`Tc` is the wall available for pressure (thickness less tolerance and allowances), `r2` the mean pipe radius, `R1` the effective bend radius to the centerline, `θ` the miter half-angle (the angle of cut), and `miters` the number of cuts. User-supplied: **S, E, W**. The result names the governing equation.

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
