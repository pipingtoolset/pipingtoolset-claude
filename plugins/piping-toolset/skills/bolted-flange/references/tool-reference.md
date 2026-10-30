# Tool reference - modules, fields, envelope and pre-flight

Always run `python scripts/bolted_flange.py list` for the live field names. Names are case-sensitive. Units are U.S. customary: psi, lbf, in, in^2.

## Modules

| Module id | What it does | Status |
|---|---|---|
| `connections.flange-derive` | Gasket N, b0, b, G (flat and ring-joint rules); UN bolt root area and total area; hub g0, g1, h | always `na` |
| `connections.flange-equivalent-pressure` | The screen: momentTerm, forceTerm, Pe, utilization | `pass` if Pe <= rated, else `fail` |
| `aux.app2-flange-integral` | The detailed analysis: Peq, bolt loads, moments, stresses and averages for both cases, J, governing case | `pass` only if Ab >= Am, worst utilization <= 1, and both J <= 1 |

`connections.flange-equivalent-pressure` and `aux.app2-flange-integral` reproduce the pipingtoolset.com calculation engine's fixture cases exactly: same input names, output names, statuses, rounding and thrown-error conditions. `connections.flange-derive` is new and has no engine module.

## connections.flange-derive

Give at least one group. Each group is all-or-nothing. Carry the results into the detailed module: pass `b`, `G` and `N` from here into `aux.app2-flange-integral`, always for ring joints (when `b` is omitted the engine uses the flat rule, b0 = N/2, which is wrong for a ring joint).

| Group | Inputs | Outputs |
|---|---|---|
| Gasket | `facing` ("flat" or "ring-joint"), `gasket_ID`, `gasket_OD` | N, b0, b, G |
| Bolting | `bolt_D`, `bolt_tpi`, optional `nBolts` | boltRootArea, Ab (with nBolts) |
| Hub | `pipe_OD`, `B`, `X`, `Y`, `t` | g0, g1, h |

Rules: N = (OD - ID)/2; b0 = N/2 (ring joint N/8); b = b0 if b0 <= 0.25 in, else 0.5 sqrt(b0); G = (ID + OD)/2 if b0 <= 0.25 in, else OD - 2b. Root area = pi/4 (D - 1.299038/n)^2. g0 = (pipe OD - B)/2, g1 = (X - B)/2, h = Y - t. Outputs are rounded to 6 places (Ab to 4). Warnings: the ring-joint warning states whether G was the mean of ID and OD (b0 at most 0.25 in) or OD - 2b (above that); every hub run warns that g0 = (pipe OD - B)/2 is the nominal pipe wall only when B equals the pipe ID (VIII-2 4.16.13 defines g0 as the nominal wall).

## connections.flange-equivalent-pressure

| Input | Units | Notes |
|---|---|---|
| `P` | psi | Design pressure for the load case |
| `F` | lbf | Axial force, tension positive |
| `M_in_lbf` / `M_ft_lbf` / `M` | in-lbf / ft-lbf / in-lbf | Give **exactly one**. `M` is the engine's name and is in-lbf. `M_ft_lbf` is multiplied by 12 and the tool says so |
| `G` | in | Gasket reaction diameter |
| `ratedPressure` | psi | User-read B16.5 rating at design temperature (or the owner's percentage of it) |
| `creditCompression` | bool | Optional, default false. When false a negative `F` is taken as 0 and the tool warns. Set true only if the owner agrees to credit compression; then run the tensile case separately and report both |

Outputs: `momentTerm` (3 decimals), `forceTerm`, `Pe`, `utilization` (4 decimals). Every run carries a warning that this is a leakage screen and not a stress check, and that torsion and shear are not used.

## aux.app2-flange-integral

Required: `attachment` ("integral" or "loose"), `P`, `A`, `B`, `C`, `t`, `G`, `N`, `m`, `y`, `nBolts`, `aRoot`, `Sa`, `Sb`, `Sf`, and for the CLI `SfAmbient`, `Edesign`, `Eambient`. Integral also needs `g0`, `g1`, `h`. Optional: `Fax`, `Mext` (ft-lbf) or `Mext_in_lbf`, `b`, `boltDia`, `Sn`, `SnAmbient`, `rigidityFactor`, `applyBoltSpacing`, `hubFactorMethod`, `F_override`, `V_override`, `f_override`.

Outputs, in engine order: Peq, momentTerm, forceTerm, b, H, Hp, Wm1, Wm2, Am, Ab, Wg, K, T, Z, Y, U, ho, F, V, f, e, d, L, hD, hT, hG, HD, HT, HG, boltSpacing, boltSpacingMax, Bsc, Mo, MoFtLb, Mg, then `operating` and `seating` stress sets (SH, SR, ST, avgHR, avgHT, allowSH, allowSR, allowST, utilization), Joperating, Jseating, governing.

Equations and symbols: [app2-engine.md](app2-engine.md).

Result-grade keys (added after `governing`; no engine value changes): `result_grade` (`screening` or `calculated`), `grade_label` ("screening / reconstructed factors" or "calculated"), `factor_basis` (`{F, V, f}` each `series`, `override`, or `not used` for a loose flange), `banner`, `grade_note`. Rule: `screening` whenever any hub factor the flange type uses came from the series; `calculated` only when `F_override`, `V_override` and `f_override` were all supplied, or the flange is loose. The banner is also the first entry in `warnings`; a partial override adds an entry naming the factors still on the series. The screen carries `result_grade` `screening` (label "screening (leakage screen, not a stress check)") and a `banner`, always. Taxonomy: calculated / screening / manual check required / pointer only / not checked.

The importable function `app2_flange_integral` falls back to engine default moduli (named `ENGINE_DEFAULT_E_DESIGN` and `ENGINE_DEFAULT_E_AMBIENT` in the script) when E is omitted. They exist only so the ported function reproduces the engine fixtures that omit E. They are not recommended values and not table lines; the command line refuses to run without `Edesign` and `Eambient`.

Compression: pass `Fax` = max(F, 0) to follow VIII-2 4.16.13 (FA is the tensile net-section force only). Omitting both `Fax` and `Mext` gives a pressure-only result (Peq = P) and the tool warns.

## Envelope

```
{ "module", "status", "output", "warnings", "citation", "inputs", "user_supplied" }
```

`status` is the engine's machine word (`pass` / `fail` / `na`) and stays as the fixtures assert it. It is not the report wording: on a `screening` run state the result as "within" or "exceeds" with the ratios, never PASS. The output key `report_word` carries that wording ("within" / "exceeds" for the screen, "tool rule met" / "tool rule not met" for the detailed analysis): relay it, not `status`. `--format sheet` prints a markdown calc-sheet block (banner, grade, factor basis, results, findings) that does this; the default `--format json` prints the envelope. `user_supplied` lists the inputs present in the call that are code, table or project values the user must be able to cite. When the call carried `code_values`, the envelope also has `code_value_provenance` (below). `status` `na` means a value with no pass/fail. Exit code 2 with a one-line `input error: ...` message means bad input; fix it, never retry with guessed values.

## Pre-flight (before the engine)

Rejected with exit 2:

- unknown input field names (the message lists the valid ones);
- no moment, or more than one moment unit, on the screen; both `Mext` and `Mext_in_lbf` on the detailed module;
- `attachment` other than integral or loose; `hubFactorMethod` other than series (the curve-fit option is not shipped; use the override inputs);
- `Edesign`, `Eambient` or `SfAmbient` missing on the detailed module (the engine would default them silently);
- hub overrides on a loose flange; `F_override` or `V_override` not above 0; `f_override` below 1;
- negative design pressure on the screen;
- the engine's own conditions: G, ratedPressure, N, t not positive; m or y negative; Sa, Sb, Sf not positive; fewer than four bolts; A > C > G > B not satisfied; hub dimensions missing or g1 below g0; Peq not positive.

Warnings added (quote them in the findings):

- the screen is a leakage screen, not a stress check; design pressure already above the rating; a G under 1 in;
- `M_ft_lbf` converted to in-lbf; compression taken as F = 0 on the screen; compression reducing Peq on the detailed module; no `Fax` or `Mext` given (pressure-only);
- external loads raising the analysed pressure, and that this is not an Appendix 2 / 4.16 construction;
- defaults applied (b, boltDia, SnAmbient, rigidityFactor, hubFactorMethod);
- the result-grade banner (`SCREENING / RECONSTRUCTED FACTORS` or the issue-grade line) as the first finding, and for a partial override the factors still on the series;
- Sn not supplied (2.5 Sn cap unchecked); hub-factor overrides in use;
- bolt area inadequate; bolt-spacing correction applied; radial hub clearance not positive; rigidity J above 1; a loose flange reporting zero hub and radial stress.

## Illustrative calls

Every number is a placeholder, not a code value.

```
python scripts/bolted_flange.py connections.flange-derive --input-file job.json
python scripts/bolted_flange.py connections.flange-equivalent-pressure --input-file job.json
python scripts/bolted_flange.py aux.app2-flange-integral --input-file scripts/examples/integral-weld-neck.json
```

A screen `job.json` looks like `{"P": 300, "F": 4000, "M_in_lbf": 120000, "G": 17.29, "ratedPressure": 500}`. Quoting inline JSON on a command line is shell-dependent (PowerShell in particular mangles it), so write `job.json` to the working directory with the file tool and pass `--input-file`.

## Connector-supplied values (`code_values`)

Every module accepts an optional top-level `code_values` block: the route for a value the Engineering Data connector returned, or a value the user read, together with its citation. Shape (a template, not a code value):

```
"code_values": {
  "ratedPressure": {"value": <number from the lookup>, "unit": "psig",
                    "citation": {"standard": "...", "edition": "...", "table": "...", "row": "...", "column": "rating"},
                    "source": "connector"}
}
```

| Field | Meaning |
|---|---|
| name (the key) | The module input it fills, spelled exactly as `list` prints it; this skill has no nested inputs, and `gasket.m` and `gasket.y` are accepted spellings of `m` and `y`. A name the module does not declare stops the run (exit code 2) |
| `value` | A number (or a string), the number as the lookup returned it |
| `unit` | Required. The unit the lookup returned, so ksi stays `"ksi"`; `null` for a dimensionless value. The script converts a unit it can convert exactly (ksi to psi) and says so in `warnings`; any other mismatch is rejected |
| `citation` | `standard`, `edition`, `table` and `row` (all non-empty strings), and `column` when there is one, copied from the lookup's `citation` |
| `source` | `connector` for a returned value, `user` for a value the user read |

Rules:

- An input missing from the main inputs is filled from `code_values[name].value`. An input present in both places with different values stops the run, exit code 2, with `code_values.<name> conflicts with input <name>`; fix the job file, do not edit one side to match.
- The envelope gains `code_value_provenance`, `{name: {unit, citation, source}}`, for every entry. `inputs` shows the values used, and `user_supplied` lists a filled input as it lists a typed one. Quote any unit-conversion note in `warnings`, and copy the provenance into section 3 of the calc sheet with its source column.
- Put only the entries the module being run declares in that job file; an entry for another module's input is an error. The script makes no network calls.
- The entries each module declares: `ratedPressure` for `connections.flange-equivalent-pressure`; `A`, `C`, `t`, `m`, `y`, `nBolts`, `Sa`, `Sb`, `Sf`, `SfAmbient`, `Sn`, `SnAmbient` for `aux.app2-flange-integral`; `gasket_ID`, `gasket_OD`, `bolt_D`, `nBolts`, `X`, `Y`, `t` for `connections.flange-derive`.
- The connector returns allowables in ksi and ratings in psig: pass the unit as returned and the script converts ksi to psi. Dimensions are in inches; `m` is dimensionless (`"unit": null`).
- `Sf` under B31.3 is S x E x W: form the product by a script run, enter it with `"unit": "ksi"`, cite the `S` line in `citation`, list the `E` and `W` lines in `row`, and show the three lookups and the product on the sheet.
