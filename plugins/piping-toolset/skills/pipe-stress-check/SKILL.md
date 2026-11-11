---
name: pipe-stress-check
description: "Check ASME B31.1 / B31.3 pipe stress the way a reviewer will: sustained, occasional and expansion hand checks (S_A, the f factor, Eq. 17, 1.33 Sh or k), which document gives the SIF (B31J or Appendix D), the formal analysis exemption, support span, spring variability, ASCE 7 occasional loads, and a cold-eye review of a CAESAR II / AutoPIPE run or a calc package with findings register and verdict."
compatibility: Method and review guidance only; this edition has no scripts
---

> **Directory edition: method and review guidance, no calculation scripts.**
> This edition ships without the Python scripts of the full plugin, so nothing in it is run as a
> program. Wherever the text below or a reference file names a script, a module id or a path under
> `scripts/`, read that as a description of the method and not as a command.
>
> 1. Work each calculation by hand from the method in the reference files, and show every equation,
>    input, unit and intermediate value.
> 2. Head every numeric result `HAND CALCULATION, NOT ENGINE-VERIFIED` and give it the result status
>    `screening`. Report each ratio as within or exceeds. Write no PASS, OK or issue-grade wording.
> 3. The builders and converters named below (PCF, neutral file, load case tables) are not in this
>    edition. Give the method and the checks; write such a file only as plain text the user can
>    review line by line, and say it has not been through the validator.
> 4. Tell the user once that the fixture-verified engine is in the full plugin on GitHub
>    (pipingtoolset/pipingtoolset-claude) and in the calculators at pipingtoolset.com. Those scripts
>    are not available from this edition.


# Pipe stress check: hand checks and cold-eye review, B31.1 and B31.3

Pipe stress calculations are rejected for **procedure** far more often than for arithmetic. A
calc that states its edition, cites every allowable to a table line, shows all three load cases,
traces every report to the archived model and declares its assumptions survives review even if
a number moves. A correct number with no traceability does not.

This skill runs the screening arithmetic a reviewer re-does by hand
(`scripts/pipe_stress_check.py`), makes the calc sheet around it defensible, and reviews someone
else's analysis or calc package with a cold eye and a severity-ranked findings register
([review-protocol.md](references/review-protocol.md)).

## Scope

| This skill | Not this skill |
|---|---|
| SUS / OCC / EXP hand checks against the allowables the user supplies; f, S_A, k or 1.33; the exemption; spans; springs; section properties | Building the static load cases: the `load-case-builder` skill in this pack, if it is installed |
| Which equation generation and which SIF document govern, by code and edition; the ASD position for ASCE 7 loads; owner practices on top of the code | Computing SIFs or flexibility factors. **This skill never computes an i.** The user reads it from B31J or Appendix D |
| Cold-eye review of a stress run or a calc package: traceability, modelling, documentation, verdict | Getting the model in: the `stress-import` skill. Nozzle allowables: `nozzle-load`. Flange leakage: `bolted-flange`. Support steel: `pipe-support` |
| The calc-sheet format and the rejection checklist | Wall thickness, MAWP and hydrotest pressure (outside this pack); sway-brace hardware; wind and seismic magnitudes beyond the ASCE 7 form |

The user's own licensed copies of the codes are the authority for every clause cited here;
where a point needs confirming, name the clause and edition and ask for the printed page.

---

## Two ways in

**A line to check.** Steps 0 to 8 below, then the calc sheet.

**An analysis or package to review.** Steps 0 and 1 to fix the basis, then
[review-protocol.md](references/review-protocol.md): inventory and scope, the traceability
chain (reports from the archived model, civil cases per the matrix, iso bubbles and hanger
boxes that match the model, P/T per the line list and the design criteria, gaps and friction
per the criteria and shown on the iso, every assigned line present, checklist answers that
agree with the model, an independent check behind the stamp), the hand checks of Steps 2 to 8 on
the governing nodes, severity (critical, major, minor, observation), and a verdict
recommendation (Accepted, Accepted as noted, Rejected and resubmit, Cannot verify). The
reviewer checks; the engineer of record signs. The package is read-only; findings cite evidence.

---

## Step 0: the basis interview

Ask these together, accept a partial answer, and mark every unanswered item **ASSUMED** at the
top of the output. Do not silently default.

1. **Code: B31.1 or B31.3?** Not interchangeable; their allowables differ for the same material.
2. **Edition year.** It decides the equation generation (Step 1). Proceed on a marked ASSUMED
   edition if needed, but present no final sheet until it is confirmed.
3. B31.3 only: **fluid service category.** Chapter IX uses a different occasional factor.
4. **Owner practices** invoked (a stress design criteria document, PIP PNC00004 / PNC00001 /
   RECE002): [owner-practices.md](references/owner-practices.md). Ask; do not assume.
5. Is the liberal allowance (Eq. (1b)) permitted by the project specification?
6. **Cycles.** Equivalent full displacement cycles N over design life; never assume f = 1.0.
7. **Installation temperature** (never assume 70 F) and the **minimum and maximum metal
   temperatures** the line will ever see, including steam-out, regeneration, defrost, ambient.
8. Geometry: NPS, wall, corrosion and erosion allowance, mill tolerance, product form, the
   component type at each node (elbow, tee type, reducer, threaded joint).
9. **Load standard and edition** for wind and seismic (ASCE 7-10, 7-16 or 7-22) and the ASD
   position; site data (Risk Category, exposure, SDS, SDC, Ip, supporting structure).
10. For a review: software and version, the code year set in it, the archived job name and date.

**Project basis record.** When one exists (from an earlier skill run in this session, or a file
the user names), reuse it: ask only for what is missing, never relabel a field. Pass it as
`--project-basis <file>` or a top-level `project_basis` object
([schema and fill map](references/project-basis.md)).

Section properties for the sustained check are code-specific (B31.3 320.1 deducts all
allowances for Z; B31.1 104.8.1 uses nominal Z and wall). State the basis used
([detail](references/load-cases-and-allowables.md)).

---

## Step 1: resolve the edition before computing anything

The equation forms changed between editions, and the wrong generation is the most common
serious error. Run:

```
python scripts/pipe_stress_check.py basis --code B31.3 --edition 2022
```

It returns structure only: which SIF document governs, which `equation` the f-factor tool
takes, the occasional-factor rule, the f-cap rule, the exemption form and the ASD position. It
never returns a table value. The edition rows for both codes are in
[load-cases-and-allowables.md](references/load-cases-and-allowables.md#edition-table). Write
the resolved row into the Basis section of the sheet.

---

## Step 2: the three load cases, always all three

A calc that omits a load case is incomplete. If occasional loads are judged negligible, say so
and why; silence is the defect.

- **Sustained (SUS):** pressure, weight and other sustained loads, with the **sustained** index
  (never the expansion SIF) and the code's section basis; limit S_h. The tool takes `S_b` and
  `S_t` already computed; the sqrt and additive forms are in the reference.
- **Occasional (OCC):** sustained plus **one event at a time**; wind and earthquake are not
  combined. B31.3 uses a flat 1.33 S_h (1.20 for Chapter IX); B31.1 uses k = 1.15 or 1.20, and a
  k with no stated duration basis is a finding. The 1.33 is not the 302.2.4(f) variation
  allowance. Relief thrust, hammer and slug flow are run or dismissed with a reason.
- **Expansion (EXP):** from the **range** between the two governing thermal states, with the
  expansion SIFs, against S_A (B31.3 Eq. (17)). Seismic anchor movement and settlement belong
  here, not in OCC. Also run, and say whether you ran, the **installed (cold)** case for liftoff
  and spring travel, and the **hydrotest** case for lines whose contents are lighter than water.

Equations and the occasional-allowable table:
[load-cases-and-allowables.md](references/load-cases-and-allowables.md).

---

## Step 3: occasional loads and the ASD question

ASCE 7 wind speeds and seismic E are strength level; ASCE 7's own ASD combinations apply 0.6 to
wind and 0.7 to earthquake. **B31.1-2024** (101.5.2, 101.5.3) says the ASD reduction factor
shall not be applied; applying it is a finding. **B31.3** (301.5.2, 301.5.3) says nothing:
default to no reduction, flag it ASSUMED, and apply 0.6 / 0.7 only on written direction of the
owner or the engineer of record, citing that document, and keep unreduced companion cases for
support loads. How to build the wind and seismic loads edition by edition (qz forms, Kd inside
or outside qz, Fp forms, the 13.1.4 and 13.6.7.3 exemptions, "deemed to comply", B31E, sway
bracing): [occasional-loads.md](references/occasional-loads.md).

---

## Step 4: allowable range S_A and the f factor

S_A uses the base form f (1.25 S_c + 0.25 S_h); the liberal form applies only where the
specification permits and S_h > S_L, and a line within the allowable only with it has no margin.
S_c and S_h come from the allowable-stress table for the actual material and temperature (show
the interpolation); the tool computes the base form only.

- **The f equation changed.** B31.3-2022 and later use `f = 20 N^-0.333`; earlier B31.3 and every
  B31.1 edition use `f = 6.0 N^-0.2`. Set `equation` to `"legacy"` or `"b313-2022"` in the
  `piping.fatigue-factor` input (run `basis` to resolve it) and carry the output's `equation`
  string into the report.
- **The cap differs by code.** B31.1: f at most 1.0, no exceptions. B31.3: f at most f_m, 1.2
  only for ferrous material with SMTS at most 75 ksi and design metal temperature at most 700 F,
  otherwise 1.0; write the reason down.
- No cycle count: never assume f = 1.0 quietly; state that it needs N at most 7,000 equivalent
  full cycles, to be confirmed.
- **Cold spring is not a stress credit** under either code; it affects reactions only.

Worked comparison, partial-range cycles (`N_E`), the floor and cap logic:
[load-cases-and-allowables.md](references/load-cases-and-allowables.md).

---

## Step 5: SIFs, get the source right, then do not compute them

Resolve the governing document with `basis` (Step 1). Then:

- **`i` is always an input.** Ask the user to read it from B31J or Appendix D for the specific
  component, name the table or sketch, and record it. Do not estimate or recall a SIF, and do
  not reproduce a closed-form SIF equation or table row.
- **In-plane and out-of-plane are routinely transposed at tees.** For elbows `i_i > i_o`; for
  tees `i_o > i_i`. Every leg of a tee gets its own SIF; reducing tees differ run to branch.
- A SIF is never below 1.0 (the tool rejects `ii`, `io` or `it` below 1). `it` (default 1.0,
  warned when `Mt` is not zero) scales `S_t = it Mt / (2Z)`.
- Software still offering a legacy Appendix D toggle under B31.3-2020 or later, or B31.1-2024 or
  later, is not code-compliant for that edition; B31.1-2020 and 2022 104.8 already take ii, io,
  it from B31J.

---

## Step 6: the formal-analysis exemption

Both codes (B31.3 319.4.1(c); B31.1 119.7.1, 2016 and later) allow a line to skip formal
analysis when `D y / (L - U)^2 <= K1 = 30 S_A / E_a`. Users over-read it, so state every time:
no general proof of accuracy exists; no assurance of low terminal reactions; it is disqualified
by more than two fixation points, any intermediate restraint or non-uniform size (give
`fixation_points`, `intermediate_restraints`, `uniform_size`; if one is omitted the tool returns
`na`, so ask, do not assume); and it discharges displacement stress only. Where PIP PNC00004 is
invoked, its stress-critical list overrides the exemption for every line it names.
[exemption-and-spans.md](references/exemption-and-spans.md).

---

## Step 7: support spans

Compute both the bending and deflection criteria with `screen.support-span` and take the smaller
span. E is at operating temperature; w includes contents, insulation, cladding and tracing; E,
S and the allowable sag are user-supplied with their basis stated (a PIP PNC00004 project sets
the sag limit). Include `L_actual_ft` to test a proposed span. Concentrated loads, spans next
to a change of direction, natural frequency near machinery and hydrotest on vapour lines are
not covered and are called out. Calculate the span; never read a table span back from memory.
[exemption-and-spans.md](references/exemption-and-spans.md).

---

## Step 8: spring hangers

Variable springs: variability |rate x travel| / hot load at most 25 % (MSS SP-58 7.7.1.2);
constant supports: deviation at most 6 % (7.7.1.3). Report hot load, cold load, travel, rate and
variability for **every** spring, installed and operating; one that tops or bottoms out in the
cold case is a finding. `supports.spring-variability` takes `limit` in **percent** (25) but
`supports.max-spring-rate` takes `variabilityLimit` as a **fraction** (0.25).
[spring-hangers.md](references/spring-hangers.md).

The chain does not end at the restraint load: a standard detail's design load is usually
user-defined, so the reaction is still checked against the member (`pipe-support`), and
trunnions, lugs and welded clips need a local-stress check (WRC 107 / 297 / 537 or FEA).

---

## Owner practices

Owner practices (a stress design criteria document, PIP PNC00004, PNC00001, RECE002) add rules
on top of the code: with and without friction runs, a sag limit, rod-hanger rotation limits,
extra mandatory cases, hydrotest on permanent supports, machinery nozzle-load triggers and
design-stage caps, no cold spring. **Ask whether one is invoked; do not assume.** Clause pointers
and the PIP-invoked checks: [owner-practices.md](references/owner-practices.md). Open the
practice before citing a clause into a sealed calc, and state the code edition beside it.

---

## Running the tool

`scripts/pipe_stress_check.py` (Python 3.9+, standard library only). Script paths are relative
to this skill's directory. Call them by full path from wherever the session is working; do not
change into the skill folder (in Cowork it is a read-only mount and the working directory is
the outputs folder). Write `job.json` and every output file to the working directory, never into
the skill folder, so the user can open and download them.

- **Run `python scripts/pipe_stress_check.py list` first** for the exact field names (`SA`, not
  `S_A`). Names are case-sensitive; unknown names exit 2.
- **Every number you state comes from a script run**, including side comparisons, what-ifs and
  every recomputation in a review: run the script again rather than computing in your head.
- A pre-flight check stops impossible inputs with exit code 2 and warns on implausible ones;
  quote those warnings ([tool-reference.md](references/tool-reference.md)).

```
python scripts/pipe_stress_check.py list
python scripts/pipe_stress_check.py <module-id> --input '<json>'
python scripts/pipe_stress_check.py <module-id> --input-file inputs.json
python scripts/pipe_stress_check.py basis --code B31.1 --edition 2024
```

Modules ([tool-reference.md](references/tool-reference.md)):
`piping.displacement-stress`, `piping.sustained-stress`, `piping.fatigue-factor`,
`supports.spring-variability`, `supports.max-spring-rate`, `noncode.pipe-section`,
`screen.support-span`, `screen.flexibility-exemption`.

Each call prints a JSON envelope `{module, status, output, warnings, citation, inputs,
user_supplied}` plus the status fields below; exit code 2 means bad input, including a record
that conflicts with an input. Quote warnings and the `equation` string in the calc sheet.

**Result status.** `result_status` is calculated, screening, manual check required, assumed,
pointer only or not checked. Put `result_status_line` under the sheet title and `basis_section`
(with a record) in section 1. While the status is manual check required, assumed or pointer
only, write no PASS or OK: `banner` then holds the status word.

---

## Output format: the calc sheet

Keep this order; it mirrors how a reviewer reads. A review puts its findings register (severity,
evidence, action, status) in section 6 and the verdict at the top.

```
# Pipe Stress Calculation / Review: [line number or calc number]
Result status: [word] - [why]

## 1. Basis (ASSUMED items first)
Code, edition, fluid service, owner practices (with edition), load standard and edition (and why),
ASD position, resolved equation generation and SIF source, software and version, archived job.

## 2. Inputs
Geometry, material, conditions, cycle count, site data. Every assumed value flagged ASSUMED.

## 3. Code-table values (user-supplied or connector-supplied, cited)
Each value with its full citation: code, edition, table, material spec, grade, product form,
temperature, notes. Interpolation shown. f derivation and cap reason shown. A source column.

## 4. Load cases
### 4.1 Sustained    equation used, S_L, allowable, ratio, verdict
### 4.2 Occasional   each event separately, with its derivation; k or 1.33 and its duration basis
### 4.3 Expansion    range basis, S_E, S_A, ratio, verdict; SAM and settlement if present
### 4.4 Installed / hydrotest   run or dismissed, with reason

## 5. Supports and nozzles (if in scope)
Spans (both criteria, governing), spring table, local-stress checks called out,
machinery nozzle loads resolved at the right point against the owner's class percentage.

## 6. Findings and assumptions
Open items, values the user must confirm, anything that would change the conclusion;
in a review, the severity-ranked register and the verdict.

## 7. References
Every code paragraph, with edition; every PIP clause with edition and revision type.
```

"[material], [value] psi" with no table, edition or temperature is not a citation.

---

## Before you hand it over: rejection checklist

Run the checklist in [rejection-checklist.md](references/rejection-checklist.md) before issue.
**Open that file before issue; the body does not repeat the items.**

---

## Copyright boundary

**Never reproduce, reconstruct, estimate or "recall" tabulated values**: allowable stresses for
any material, elastic moduli, thermal expansion data, SIF or stress-index table entries and the
equations behind them (B31J, Appendix D), B31.1 Table 121.5 spans, MSS SP-58 table values, ASCE
7 coefficient tables or figures, PIP tables and figures. This applies even when the user asks
directly and even when a value seems widely known. Name the table, row and edition, and ask the
user to read it from their licensed copy:

> I need S_h at the design temperature for your material and product form. That is in the
> code's allowable stress table; read the value at the two adjacent tabulated temperatures and I
> will interpolate. Which edition are you using?

Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to
read the specific value they need. A value returned by the connector carries its citation and is
recorded as connector-supplied; it is still verified against your copy before issue.

Equations, clause numbers, symbol definitions and numeric limits stated in running text (1.33,
k = 1.15 / 1.20, the spring limits, the f floor and cap conditions) are usable.

---

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as
written without it. If its tools are present, call `verify_connector` once per session, then
make one call per value the job needs. Pass returned allowables to the script in a
`code_values` block with `"source": "connector"` and the lookup's own `unit`, which the script
converts ksi to psi ([field rules](references/tool-reference.md#connector-supplied-values-code_values)),
and put the citation, `rows_used` and `verify_at` line on the sheet. Use a value only when its
citation names the edition and table of record. On a `mode` of `pointer`, a one-line account or
daily-limit message, any other error, or absent tools, use the interview and the lookup wording
above, unchanged, and quote nothing new. A call sends only the dataset, the row key and the
temperature. The slot table is in
[tool-reference.md](references/tool-reference.md#connector-lookups-by-slot). `ii`, `io` and
`it` stay user-supplied: no `i` is returned, and this skill never computes one.

---

*Results are engineering aids. The engineer of record verifies every calculation and every
review finding against the project's code edition, owner practices and analysis software
before issue.*
