---
name: pressure-design
description: "Traceable ASME B31.3 / B31.1 pressure design by bundled script. Use when the user asks for wall thickness, a schedule check, MAWP or allowable pressure, branch reinforcement, bend or miter checks, or hydrotest / leak test pressure (304.1.2, 104.1.2, 345.4.2). The user supplies S, E, W, Y from a licensed copy or, with the optional connector, from a cited lookup; no code table values are embedded."
compatibility: Requires Python 3.9+ (standard library only)
---

# Pressure Design — B31.1 and B31.3

Pressure-design calcs are rarely rejected for arithmetic. They are rejected for **basis and traceability**: no code edition, an allowable stress with no table line behind it, a missing weld-strength factor, mill tolerance forgotten, a corrosion allowance applied to the wrong thing. The equations are short. The citation chain is what a reviewer reads.

So this skill does two things. It interviews for the basis before computing anything, and it runs the arithmetic through a deterministic script (`scripts/pressure_design.py`) so the numbers are reproducible and the working is shown. No code-table value is embedded: each comes from the user or, optionally, from the connector section below, with its citation.

## Scope

| This skill | Not this skill |
|---|---|
| Straight-pipe thickness and allowable pressure; branch reinforcement; bends; miters; leak test pressure | Sustained, occasional and expansion stress, SIFs, spans. Hand off to the `stress-screening` skill in this pack if it is installed; otherwise say that check is outside this skill. |
| Edition and table-name traceability for the inputs | Load case sets for CAESAR II or AutoPIPE — use the `load-case-builder` skill |
| The calc sheet and its findings list | External pressure (304.1.3), reducers, closures and blanks (304.4, 304.5), flange ratings, B31.3 Chapter IX high-pressure piping, Category M special requirements |

The user's own licensed copies of the codes are the authority for every clause cited here. Where a point needs confirming, name the clause and edition and ask the user to check the printed page rather than guessing.

---

## Step 0 — The basis interview

Ask these together, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the calc sheet. Do not silently default.

**Project basis record.** If one exists (written by an earlier skill this session, or a file the user names), reuse it: run with `--project-basis project-basis.json`, ask only for what it lacks and never relabel a field. Fill map: [references/project-basis.md](references/project-basis.md).

1. **Code: B31.1 or B31.3?** They are not interchangeable. Different equation symbols (`Y` in B31.3, `y` in B31.1), different tables, different allowables for the same material. The MAWP and bend modules take it as the `code` input (MAWP also B31.9 or B31.12).
2. **Edition year.** It decides which tables hold the inputs, and table names move between editions. Pointers: [table names by edition](references/modules.md#table-names-by-edition). Ask for it and pass it as `edition` (it decides whether the B31.1 equation carries W). If the user cannot give it, proceed with a clearly marked **ASSUMED** edition, but do not present the result as a final calc sheet until the edition is confirmed.
3. **B31.3 only: fluid service** — Normal, Category D, Category M, or Chapter IX high pressure. This skill covers the Normal-service equations only; for Category M or high-pressure piping say the calc needs the code's additional requirements.
4. **Design pressure and design temperature**, and whether they are coincident. Design metal temperature, not fluid temperature, selects the allowable stress.
5. **Material:** specification, grade, **product form** (seamless, ERW, EFW, spiral, cast). Product form sets the quality factor E.
6. **Joint type, W and its basis:** longitudinal weld type; W at the design temperature (B31.3 Table 302.3.5, para. 302.3.5(e); B31.1 Table 102.4.7-1, para. 102.4.7; the notes carry the temperature thresholds); and **why** W is what it is, passed as `W_basis` (`seamless`, `below creep range per table note`, `longitudinal weld, confirmed`, or the user's words). W = 1.0 or no W needs that basis, except where the equation has no W (B31.9, B31.12); B31.1-2016 needs it for the para. 104.1.1 route. Never fill it in yourself.
7. **Allowances:** corrosion, erosion, thread or groove depth (sum them as `c` in B31.3, `A` in B31.1), and any mechanical allowance.
8. **Mill under-tolerance** as a fraction, from the pipe material specification the user is buying to.
9. **Pipe size and candidate schedule** or wall, if the question is "does this work" rather than "what do I need".
10. **Owner practice** invoked (a project piping spec may impose a stricter test or reinforcement rule). Ask; do not assume.

---

## Copyright-safe lookups

ASME's tabulated data is copyrighted. **Never reproduce, reconstruct, estimate or "recall" an allowable stress, a quality factor E, a weld strength reduction factor W, a coefficient Y or y, a B36.10M / B36.19M wall-thickness table entry, or any other tabulated value.** This holds even when the user asks directly and even when a value seems widely known. Never state a code-table value yourself; record the user's value with its full citation chain (material spec/grade/form, table, edition, temperature). A value returned by the connector carries its citation and is recorded as connector-supplied; it is still verified against your copy before issue.

Instead, identify exactly which value is needed and where it lives, and ask the user to read it from their licensed copy. Frame it as a lookup instruction:

> I need **S** at the design temperature. That is B31.3-[edition] Table [A-1 / A-1C], material **[spec and grade]**, product form **[seamless / welded]**. Read the value at the tabulated temperature below and the one above your design temperature, plus any notes on that line. The code permits linear interpolation between adjacent tabulated temperatures; I will show the arithmetic. Extrapolating above the highest tabulated temperature is not permitted.

Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value they need.

Equations, clause numbers, symbol definitions and numeric limits stated in running text (t ≥ D/6, P/(S·E) > 0.385, the 45–90° branch range) are usable. Pointers to where an input lives (table names are pointers only: confirm the table name in your copy):

| Input | B31.3 | B31.1 |
|---|---|---|
| Allowable stress S | Appendix A (table name moves with edition — see Step 0) | Mandatory Appendix A |
| Quality factor E | Appendix A quality-factor tables | the longitudinal weld joint factor table in para. 102.4 and the Appendix A notes |
| Weld strength reduction W | Table 302.3.5 | Table 102.4.7-1 (para. 102.4.7) |
| Coefficient Y (B31.3) / y (B31.1) | Table 304.1.1 | Table 104.1.2(A) |

Verify each table name and number against the printed page of the user's edition before it goes on a sealed sheet.

---

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; everything above works without it. If its tools are present, call `verify_connector` once per session. Then make one `lookup_value` call per value the job needs (never sweep a table), choosing the dataset by the code basis from Step 0, and pass each result to the script in a `code_values` block with `"source": "connector"` and the lookup's own `unit`, which the script converts where it can, ksi to psi ([field rules](references/modules.md#connector-supplied-values-code_values)). Put the returned citation with its notes, the `rows_used` entries and the `verify_at` line on the sheet. Use a value only when its citation names the edition and table of record. On a `mode` of `pointer`, pass it as that slot's `code_values` entry with `"mode": "pointer"` and no value (the run is `pointer only`) and ask the user for the value. On a one-line account or daily-limit message, any other error, or when the tools are not present, use the interview and the lookup instruction above for that slot, unchanged, and quote nothing new. A call sends only the dataset, the row key and the temperature.

| Slot | Tool and dataset_id | Key fields | What comes back |
|---|---|---|---|
| `S` at design temperature, `ST` at test temperature | `lookup_value`: `b313-allowable-stresses-2024` (B31.3) or `b311-allowable-stresses-2024` (B31.1) | `spec`, plus as the reply asks: B31.3 `grade`, `classCond`, `size`, `productForm`, `lineNo`, `uns`; B31.1 `grade`, `typeClass`, `sizeOrDia`, `productForm`, `table`, `notes`; `T` (°F); `column` `S` | `S` in ksi, interpolated between the two tabulated temperatures, never extrapolated. B31.1 values include the `E` or `F` named in `eOrF` |
| `E` | `lookup_value`: `b313-ej-factors` (welded, column `ej`), `b313-ec-factors` (castings, column `ec`) or `b311-e-factors` (column `e`) | `no`, plus `seamType`, `examination` as asked; `examination` alone for `b313-ec-factors` | the factor, with the joint type |
| `W` (B31.3) | `lookup_value`: `b313-w-factors` | `steelGroup`, `T` | `W` at a tabulated temperature column |
| `Y` (B31.3), `y` (B31.1) | `lookup_value`: `b313-y-coefficients` or `b311-y-coefficients` | `material`, `T` | `Y` or `y` at a tabulated temperature column |
| Nominal wall `t` (`piping.b31-allowable-pressure`) | `get_pipe_dimensions` | `nps`, `schedule` | `od` and the wall, in inches (B36.10M / B36.19M) |

`W` and `Y` / `y` are read at tabulated columns only: a `T` between columns returns an error, so use the interview for that slot. B31.1 `W`, `hydroFactor` and `pneumaticFactor` have no dataset. For B31.1, confirm on the user's copy that the `E` you enter does not count the `E` or `F` already inside the returned `S` a second time.

---

## How to run the calculators

`scripts/pressure_design.py` — Python 3.9+, standard library only. Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.

```
python scripts/pressure_design.py list                      # modules, units, which inputs are user-supplied
python scripts/pressure_design.py b313-wall-thickness --input-file job.json
python scripts/pressure_design.py piping.b313-wall-thickness --input '{"P": 1000, "D": 10, "S": 24800, "E": 1, "W": 1, "W_basis": "seamless", "edition": "2022", "Y": 0.4, "c": 0.1, "millTolerance": 0.125}'
```

The numbers above are placeholders to show the shape of a complete input, not code values. `job.json` holds the same object. Quoting inline JSON on a command line is shell-dependent (PowerShell in particular mangles it), so prefer the file route: write the object to `job.json` in the working directory with the file tool, then pass `--input-file job.json`.

- **Run `python scripts/pressure_design.py list` first** to get the exact field names; do not guess them.
- **Every number you state comes from a script run**, including side comparisons, what-ifs and sensitivity remarks (for example "what would the wall be at 10 % lower pressure"): run the script again rather than computing in your head.
- A pre-flight check runs before the engine. It stops physically impossible inputs with exit code 2 (negative pressure or allowance, E or W above 1, Y or y outside 0 to 1, a wall of D/2 or more, allowances that consume the wall, a miter radius R1 that does not exceed r2) and adds warnings for implausible ones (ST/S above 2, a pneumatic factor above 1.33). Quote those warnings in the findings.
- **US customary only:** psi, in., in.², degrees (the equations are unit-consistent).
- Input names are **case-sensitive** and unknown names are rejected: `Y` (B31.3) and `y` (B31.1) are different fields on different modules.
- Output is a JSON envelope: `status` (`pass` / `fail` / `na`, or `manual check required` / `pointer only`), `output`, `warnings`, the paragraph `citation`, an echo of `inputs` (the basis texts included), `user_supplied` (the table values the user must cite), `defaults_applied` (never W), and `weld_factor_basis` (W, its basis and source) on every module that carries W.
- **W gate.** Where the equation carries W, W omitted or W = 1.0 without `W_basis` exits 2 naming the W table and edition. Never retry with a basis the user did not give.
- **Validity gate** (straight pipe, MAWP, bends): `validity` reports `P_over_SE` against 0.385 and the thickness against D/6. On a trip, `status` is `manual check required`, `output` is empty and the numbers sit in `equation_value` as an **equation value, not a design basis**; quote the `banner` (it names the clause) and write no PASS, schedule or margin. Otherwise `result_grade` is `calculated`, or `manual check required` on a special-service record. Details: [modules.md](references/modules.md).
- **Result status.** `result_status` is the worst performed word of `checks[]`: calculated, screening, manual check required, pointer only, not checked ([meanings](references/project-basis.md#result-status-words)). Write PASS, a schedule or margin only when `banner_allowed` is true, whatever `status` says.
- Exit code 2 with a one-line message means bad input. Fix it; never retry with guessed values.
- Results are rounded to the precision shown (5 decimals on thickness, 3 on pressure).

---

## Modules

Each module's equations, inputs, validity limits and reviewer notes are in [references/modules.md](references/modules.md). Read the matching section before you run a module.

| Module id | What it computes | Code paragraph | Detail |
|---|---|---|---|
| `piping.b313-wall-thickness` | Pressure design thickness, minimum required thickness and nominal wall to order, B31.3 | B31.3 304.1.2, Eq. (3a) | [section 1](references/modules.md#1-straight-pipe--pressure-design-thickness-b313) |
| `piping.b311-wall-thickness` | Minimum required thickness and nominal wall to order, B31.1 | B31.1 104.1.2 | [section 2](references/modules.md#2-straight-pipe--pressure-design-thickness-b311) |
| `piping.b31-allowable-pressure` | Schedule check: allowable pressure (MAWP) of a selected nominal wall | B31.3 304.1.2 Eq. (3a), solved for P | [section 3](references/modules.md#3-schedule-check-and-allowable-pressure-mawp) |
| `piping.branch-reinforcement` | Area-replacement check of a branch connection, with margin in in.^2 | B31.3 304.3.3 | [section 4](references/modules.md#4-branch-connection-reinforcement--area-replacement) |
| `piping.bend-thickness` | Required thickness after bending at intrados, extrados and sidewall | B31.3 304.2.1; B31.1 102.4.5 | [section 5](references/modules.md#5-pipe-bends--thickness-after-bending) |
| `piping.miter-allowable-pressure` | Allowable pressure of a single or multiple miter bend | B31.3 304.2.3, Eq. (4a)/(4b)/(4c) | [section 6](references/modules.md#6-mitered-bends--allowable-pressure) |
| `piping.leak-test-pressure` | Hydrostatic and pneumatic leak test pressure (piping minimum) | B31.3 345.4.2 Eq. (24), 345.5.4; B31.1 137 | [section 7](references/modules.md#7-leak-test-pressure) |

Quote `P_over_SE` from `validity`; `th` and `tb` come from the two wall-thickness runs. What a module does not evaluate is listed in its `not checked` rows.

---

## Output format — the calc sheet

Keep this order; it mirrors how a reviewer reads. Fill every field or mark it ASSUMED.

```
# Pressure Design Calculation — [line number / system]
Result status: [result_status_line from the run]

## 1. Basis
`basis_section` first when a record was used. Then:
Code and edition year; B31.3 fluid service; owner practices; design P and T (and
whether coincident); material spec, grade, product form; joint type;
allowances (corrosion, erosion, thread/groove, mechanical); mill under-tolerance
and its source. ASSUMED items listed first.

## 2. Inputs
Table of every input with units. Each unanswered or defaulted item flagged ASSUMED.

## 3. Code-table values (user-supplied or connector-supplied, cited)
One row per S, E, W, Y (B31.3) or y (B31.1), ST, factors:
value | code, edition, table | material spec and grade | product form | temperature |
table notes applied | interpolation arithmetic (if any) | source (user or connector).
The W row also carries W_basis and weld_factor_basis.basis_source from the envelope.
"A number with no table line behind it" is a finding against the sheet itself.

## 4. Calculation
Per check: the equation as written in references/modules.md (sections 1-7), the script command
and its output (status, output, warnings), then the arithmetic restated in words
for the reviewer.

## 5. Result against nominal / schedule
Thin-wall validity first: P_over_SE against 0.385 and the thickness against D/6, from `validity`.
tOrder vs the selected nominal wall (read by the user from B36.10M / B36.19M or mill data);
allowable pressure vs design pressure; reinforcement margin; test pressure.
PASS or FAIL for each, with the margin, only where banner_allowed is true.
A "manual check required" or "pointer only" run shows the banner, the equation value labelled
"equation value, not a design basis", the clause, and no PASS, schedule or margin.

## 6. Findings and assumptions
Every script warning, every ASSUMED item, every not checked row, the validity result (P_over_SE, t vs D/6) and
the W basis, every hand check (345.2.1(a) yield check, R1 minimum on miters), anything that
would change the conclusion.

## 7. References
Every paragraph cited, with edition.
```

## Before you hand it over — rejection checklist

1. **Edition undeclared**, or a table name quoted from a different edition than the one on record.
2. S taken at the wrong temperature (fluid instead of design metal temperature), or the next-lower-temperature value used without interpolating (non-conservative).
3. E taken from the wrong product form or joint type.
4. **W missing** where it applies, or W = 1.0 with no stated basis (`W_basis`) on the sheet.
5. **Mill under-tolerance omitted** from the ordered thickness, or applied twice.
6. Allowances: corrosion applied to the wrong side of the equation, or thread depth left out of `c` / `A`.
7. t ≥ D/6 or P/(S·E) > 0.385 passed over silently, or a `manual check required` run reported as a thickness, a schedule or a PASS.
8. Schedule claimed adequate without comparing the **nominal** wall to tOrder.
9. Branch connection with no reinforcement check, or `th` / `tb` copied from a different design condition.
10. Bend checked at the sidewall only.
11. Leak test: component limits unchecked, hydrotest stress against yield unchecked, or an owner-spec ceiling presented as a code requirement.
12. Any tabulated value typed in without its table line.

## Hand-offs

- Sustained, occasional and expansion stress, SIFs and allowable stress range: the `stress-screening` skill in this pack, if installed. This skill ends at pressure design.
- Static load case sets for CAESAR II or AutoPIPE: the `load-case-builder` skill.

## Related tools

The free calculators at [pipingtoolset.com/calculators](https://pipingtoolset.com/calculators/?utm_source=claude-plugin&utm_medium=skill) cover related sizing checks; mention them only when the user needs one of those numbers.

*Results are engineering aids. The engineer of record verifies every calculation against the project's code edition, owner practices and the tables of record before issue.*
