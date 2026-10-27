---
name: stress-screening
description: "Hand-check ASME B31.3 / B31.1 sustained, occasional and expansion (SUS/OCC/EXP) stress the way a reviewer will. Use when the user asks about S_A, the f factor or cycle count, Eq. 17, 1.33 Sh or the k factor, which document gives the SIF (B31J vs Appendix D), the formal analysis exemption, support span, spring variability, or wants to check what CAESAR II or AutoPIPE applied."
---

# Stress Screening — B31.1 and B31.3 hand checks

Pipe stress calculations are rejected for **procedure** far more often than for arithmetic. A calc that states its code edition, cites every allowable to a table line, shows all three load cases and declares its assumptions survives review even if a number moves. A correct number with no traceability does not.

So this skill does two jobs. It runs the screening arithmetic that a reviewer re-does by hand (`scripts/stress_screening.py`), and it makes sure the calc sheet around that arithmetic is defensible. Optimize for the reader who has to re-derive it.

## Scope

| This skill | Not this skill |
|---|---|
| SUS / OCC / EXP hand checks against the code allowables the user supplies | Building the static load cases in CAESAR II or AutoPIPE — hand off to the `load-case-builder` skill in this pack if it is installed |
| Which equation generation and which SIF document govern, by code and edition | Computing SIFs or flexibility factors. **This skill never computes an i.** The user reads it from B31J or Appendix D |
| Formal-analysis exemption, support span, spring variability, section properties | Wall thickness and pressure design — hand off to the `pressure-design` skill in this pack if it is installed |
| The calc-sheet format and the rejection checklist | Wind and seismic magnitudes, sway-brace hardware, nozzle-load qualification of rotating equipment |

The user's own licensed copies of the codes are the authority for every clause cited here. Where a point needs confirming, name the clause and edition and ask the user to check the printed page rather than guessing.

---

## Step 0 — The basis interview

Interactive. Ask these in one pass, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the output. Do not silently default.

1. **Code: B31.1 or B31.3?** They are not interchangeable, and their allowables differ for the same material.
2. **Edition year.** It decides the equation generation (Step 1). Ask for it. If the user cannot give it, proceed with a clearly marked **ASSUMED** edition, but do not present the result as a final calc sheet until the edition is confirmed.
3. B31.3 only: **fluid service category.** Chapter IX high-pressure piping uses a different occasional factor (1.20, K302.3.6(a)).
4. **Owner practices** invoked on the project (a stress design criteria document, a PIP practice). They apply on top of the code — see "Owner practices" below. Ask; do not assume.
5. Is the liberal allowance (Eq. (1b)) permitted by the project spec? Many specs forbid it.
6. **Cycles.** Equivalent full displacement cycles N over design life. Do not silently assume f = 1.0 — see Step 4.
7. **Installation temperature** — ask, never assume 70 °F. Plus the **minimum and maximum metal temperatures** the line will ever see, including steam-out, regeneration, defrost and ambient extremes.
8. Geometry: NPS, wall, corrosion/erosion allowance and mill tolerance, product form, component type at each node (elbow, tee type, reducer, threaded joint).
9. **Load standard and edition** for wind and seismic (ASCE 7-10, 7-16 or 7-22). It is a separate edition question from the piping code, and the jurisdiction's adopted building code usually sets it.

Section properties for the sustained check are code-specific. **B31.3** (¶320.1): section modulus uses nominal wall less all allowances (mechanical, corrosion, erosion); the area for axial and pressure terms deducts only the allowances that affect the inside diameter; weight uses nominal wall. **B31.1** (¶104.8.1): nominal section modulus and nominal wall, no corrosion deduction. State which basis you used — mixing them silently is a finding.

---

## Step 1 — Resolve the edition before computing anything

The equation forms changed between editions, and using the wrong generation is the most common serious error. Run:

```
python scripts/stress_screening.py basis --code B31.3 --edition 2022
```

It returns structure only — which SIF document governs, which `equation` value to pass to the f-factor tool, which occasional-factor rule applies, the f-cap rule, the exemption form, and the ASD position. It never returns a table value.

| Code and edition | SIF source | f-factor form | Notes |
|---|---|---|---|
| B31.3-2018 and earlier | Appendix D | `f = 6.0·N^-0.2`, `N_E = Σ Ni·ri⁵` | |
| B31.3-2020 | B31J (Appendix D deleted) | same legacy form | software offering a legacy Appendix D toggle produces a non-compliant result |
| B31.3-2022 and later | B31J | `f = 20·N^-0.333`, `N_E = Σ Ni·ri³` (¶302.3.5(d) eqs. (1c)/(1d)) | sustained Eq. (23a) unchanged; 2024 adds ¶320.1(b): absent more applicable data, the B31J Table 1-1 General Note (d) sustained index shall be used |
| B31.1-2020 and earlier | Appendix D | `f = 6.0·N^-0.2`, cap 1.0 | the exemption uses `K1 = 30·S_A/E_a` from the 2016 edition on |
| B31.1-2022 | Appendix D; B31J permitted (General Note (b)) | same | |
| B31.1-2024 | B31J (Appendix D deleted) | same | B31.1 (since 2020) writes its own sustained indices in ¶104.8.1 / Fig. 104.8-1 — I = greater of 0.75·i and 1.00, i from B31J Table 1-1 — so do not import B31.3's General Note (d) rule; 2024 replaces the pressure term with S_lp |

Write the resolved row into the Basis section of the calc sheet.

---

## Step 2 — The three load cases, always all three

A calc that omits a load case is incomplete however good the other two are. If occasional loads are judged negligible, say so and say why ("no wind load; line is indoors; seismic exempt per ASCE 7 13.1.4") — silence is the defect.

**Sustained (SUS)** — pressure + weight + other sustained mechanical loads.

```
S_Lp = P·D / (4t)
sqrt form (B31.3 ¶320.2 Eq. 23a, 2016–2024; B31.1 Fig. 104.8-1 from 2020):
                           S_L = sqrt[(S_Lp + S_b)² + (2·S_t)²]   (B31.1 writes the torsion term as I_t·M_t/Z)
additive form (B31.1-2016 / 2018 only):
                           S_L = P·D_o/(4·t_n) + 0.75·i·M_A/Z,  0.75·i ≥ 1.0
limit:                     S_L ≤ S_h
```

Use the **sustained** stress index, not the expansion SIF, and the section basis for the code (above). Which factor multiplies the sustained moment is edition-specific (a 0.75·i form in earlier editions, B31J-derived sustained indices in the 2024 editions): read the printed equation for the edition and enter the resulting `S_b` — the tool takes `S_b` and `S_t` already computed.

**Occasional (OCC)** — sustained plus each occasional event, **one event at a time**. Wind and earthquake are not combined (B31.1 ¶101.5.2 says so; B31.3 ¶302.3.6(a) states they need not be considered concurrent). Do not forget PSV reaction, water hammer and slug flow where they apply.

| Code | Occasional allowable | Basis |
|---|---|---|
| B31.3 | `S_L + S_occ ≤ 1.33·S_h`, flat | ¶302.3.6(a). Chapter IX high pressure: 1.20 (K302.3.6(a)) |
| B31.1 | `S_o ≤ k·S_h`, k = 1.15 or 1.20 | ¶104.8.2. 1.15 needs ≤ 8 h at any one time **and** ≤ 800 h/yr; 1.20 needs ≤ 1 h **and** ≤ 80 h/yr |

The B31.3 1.33 is a different clause from the ¶302.2.4(f) pressure/temperature *variation* allowance; conflating them is a common error. Under B31.1 the factor needs a stated duration basis: a k with no duration written next to it is the specific finding reviewers look for. Verify clause numbers against the printed page of the project edition before citing them.

**Expansion (EXP)** — computed from the **range** between the two governing thermal states, never from either state alone, and checked against `S_A`. Use the expansion SIFs. Confirm the range brackets the true extremes: a line that goes both above and below ambient has a range larger than either excursion.

```
S_b = sqrt[(i_i·M_i)² + (i_o·M_o)²] / Z          S_t = M_t / (2Z)
S_E = sqrt[(|S_a| + S_b)² + (2·S_t)²]            B31.3 ¶319.4.4 Eq. (17)
```

`S_a` (axial stress range) is the extra term in the B31.3 form; for B31.1 leave it at 0 and confirm the printed equation of the edition. Seismic anchor movement and settlement are displacement loads: they belong in this check, not in the occasional check.

Also run, and say whether you ran: the **installed (cold)** case for support liftoff and spring travel, and the **hydrotest** case for lines whose contents are lighter than water.

---

## Step 3 — Occasional loads and the ASD question

ASCE 7 wind speeds and seismic E are strength level; ASCE 7's own ASD combinations apply 0.6 to wind and 0.7 to earthquake. The piping codes differ:

- **B31.1-2024** (¶101.5.2 wind, ¶101.5.3 earthquake): ASCE 7 loads may be used, **except the ASD reduction factor shall not be applied**. Applying 0.6W or 0.7E is a finding.
- **B31.3** (¶301.5.2, ¶301.5.3): loads "may be as described in ASCE 7" and nothing is said about the factor. Default to **no reduction**, flag it ASSUMED, and apply 0.6 / 0.7 only on written direction of the owner specification or the engineer of record, citing that document.
- If you do reduce for stress, keep **unreduced** companion cases for support loads and displacements. The difference is 1/0.6 = 1.67× on wind force; never leave it unstated.

---

## Step 4 — Allowable range S_A and the f factor

```
S_A = f·(1.25·S_c + 0.25·S_h)                     base form
S_A = f·[1.25·(S_c + S_h) − S_L]                  liberal form, only where the spec permits and S_h > S_L
```

`S_c` and `S_h` are read from the code's allowable stress table for the actual material, form and temperature; interpolate linearly between adjacent tabulated temperatures where the code permits it, and show the interpolation. The tool computes the **base** form only. A line that passes only with the liberal form has no margin — say so.

**The f equation changed.** B31.3-2022 and later use `f = 20·N^-0.333`; earlier B31.3 editions and every B31.1 edition use `f = 6.0·N^-0.2`. Below roughly 7,000 cycles the two agree closely enough that the error hides. Above that the newer form is more conservative: at N = 22,500 the legacy form gives 0.809 and the 2022 form 0.711. A system that passed under an older edition can fail on re-rate. Pass `equation: "legacy"` or `"b313-2022"` to `piping.fatigue-factor` (the tool exits 2 if it is omitted; run `basis` to resolve it), and let the output's `equation` string go into the report. Both forms floor f at 0.15.

**The cap differs by code.**

- B31.1: f ≤ 1.0, no exceptions. Applying 1.2 under B31.1 is a straightforward rejection (the tool warns when it sees `fmax > 1` on the legacy form).
- B31.3: f ≤ f_m, where f_m = 1.2 **only** for ferrous material with SMTS ≤ 75 ksi at a design metal temperature ≤ 700 °F, otherwise 1.0. The user supplies `fmax`; confirm which of the two applies and write the reason down.

With partial-range cycle sets, `N_E = Σ N_i·r_i^p` (p = 5 legacy, p = 3 for the 2022 form), r being each set's range as a fraction of the maximum.

If the user has no cycle count, do not assume f = 1.0 quietly. Ask, or write it prominently: "f = 1.0 assumed, which requires N ≤ 7,000 equivalent full cycles over the design life — confirm." Startup/shutdown is the obvious cycle source; batch cycles, regeneration, steam-out and outdoor day/night swings are what push a line past 7,000.

**Cold spring is not a stress credit.** Neither code lets it reduce the computed displacement stress range; shakedown removes the benefit in a few cycles. It affects reactions only. If a design needs cold spring to pass the stress check, it does not pass.

---

## Step 5 — SIFs: get the source right, then do not compute them

Resolve the governing document with `basis` (Step 1). Then:

- **`i` is always an input.** Ask the user to read it from B31J or Appendix D for the specific component, name the table/sketch they used, and record it in the calc. Do not estimate or "recall" a SIF, and do not reproduce a closed-form SIF equation or table row.
- **In-plane and out-of-plane are routinely transposed at tees.** For elbows `i_i > i_o`; for tees `i_o > i_i`. A swap moves the branch result materially with no warning from the software. Every leg of a tee gets its own SIF; reducing tees differ between run and branch.
- A SIF is never below 1.0 (the tool rejects `ii` or `io` below 1).
- A reducing branch combines a reduced sustained index with an effective section modulus; if the design hangs on that node, check it locally.
- Software that still offers a "legacy Appendix D" toggle under B31.3-2020 or later, or B31.1-2024, is not code-compliant for that edition.

---

## Step 6 — The formal-analysis exemption

Both codes (B31.3 ¶319.4.1(c); B31.1 ¶119.7.1, 2016 and later) allow a line to skip formal analysis when

```
D·y / (L − U)²  ≤  K1 = 30·S_A / E_a
```

Unit basis (the 30 is a US-units constant): `D` pipe OD in **inches**, `y` resultant of the total displacement strains to be absorbed in **inches**, `L` developed length and `U` anchor-to-anchor straight-line distance in **feet**, `S_A` and `E_a` in psi. `E_a` is the code's reference (room-temperature) modulus; read it from the code table.

Users over-read this exemption, so state these every time it comes up:

1. The code says no general proof can be offered that the equation is accurate or consistently conservative.
2. Passing gives **no assurance that terminal reactions are acceptably low.**
3. It is disqualified by more than two points of fixation, any intermediate restraint, or non-uniform pipe size. Pass `fixation_points`, `intermediate_restraints` and `uniform_size`. If any of the three is omitted and the ratio is within K1, the tool returns status `na` with `exempt: null` and the message "disqualifier inputs not confirmed - cannot conclude exempt": ask the user, do not assume. A ratio above 1 or a known disqualifier still returns `fail`.
4. Passing discharges the displacement-stress obligation **only**. Sustained stress, occasional loads, equipment nozzle loads, support loads and flange leakage are all still open, and in practice any line at rotating equipment is analyzed regardless.
5. The code's other routes (a replacement of a system with a successful record, or a line readily judged adequate by comparison with an analyzed one) are separate paragraphs with their own conditions; confirm them in the printed edition.

---

## Step 7 — Support spans

Compute both criteria and take the smaller span. For equal spans under uniform load w on level rigid supports:

```
bending:     M = w·L²/C1    →  L = sqrt(C1·Z·S / w)
deflection:  δ = C2·w·L⁴/(E·I)   →  L = (δ·E·I / (C2·w))^(1/4)
units:       w lb/ft, Z in³, I in⁴, E psi, S psi, δ in, L ft
             (w is converted to lb/in and L solved in inches, then divided by 12)
```

| End condition | C1 | C2 |
|---|---|---|
| `simple` | 8 | 5/384 |
| `fixed` (fixed-fixed, or an interior span of a long run) | 12 | 1/384 |
| `two_span` | 8 | 0.00542 |
| `three_span` | 10 | 0.00688 |
| `continuous` (default) | 8 | 0.00688 |

These are beam theory, derived in the tool source. `continuous` is the envelope over every equal-span continuous beam of two or more spans — the two-span support moment with the three-span end-span deflection — so it is conservative when the layout is not known. Name the layout to tighten it.

- **E is at operating temperature**, and **w includes** contents, insulation, cladding and tracing. `E`, the allowable bending stress `S` and the allowable sag `δ` are all user-supplied and the basis for each must be stated in the calc. Pass the longitudinal pressure stress as `S_pressure` to subtract it from `S`. To test a proposed span, pass it as `L_actual_ft`: the output adds `utilization`, `bending_stress_at_actual_psi` and `sag_at_actual_in`, and the status becomes pass or fail.
- Deflection typically governs small bore; bending governs large bore and dense contents.
- **Not covered:** concentrated loads (valves, flanges, blinds) between supports; spans next to a change of direction (reduce); natural frequency near rotating equipment; hydrotest weight on vapour lines; unequal spans and overhangs.
- Tabulated spans in the code and in MSS SP-58 are lookups with narrow, stated bases (pipe weight, water-filled, temperature limit, bending stress, sag). Where a span or stress calculation is performed, or loads are concentrated, calculate the span instead of reading the table, and never read a table value back from memory.

---

## Step 8 — Spring hangers

```
cold load   = hot load + rate·travel
variability = |rate·travel| / hot load
```

- **Variable springs: variability ≤ 25 %** (MSS SP-58 §7.7.1.2, Eq. 1). **Constant supports: deviation ≤ 6 %** (§7.7.1.3). B31.3-2022 and 2024 reference the 2018 edition of SP-58, so say so if you use a provision that exists only in a later edition.
- In the tool, `supports.spring-variability` takes `limit` in **percent** (25), but `supports.max-spring-rate` takes `variabilityLimit` as a **fraction** (0.25). Do not mix them.
- Report hot load, cold load, travel, rate and variability for **every** spring, and check springs in the installed case as well as the operating case. A spring that tops or bottoms out in the cold case is a finding.
- A tighter limit on a variable spring is a project-specification choice, not an SP-58 figure for that device.
- The attachment of the support (trunnion, lug, clip) needs its own local-stress check; the stress calc ends at the restraint load.

---

## Owner practices

Owner practices (stress design criteria, PIP practices) may add rules on top of the code: with and without friction runs, a sag limit, rod-hanger rotation limits, extra mandatory load cases, rules on rotating-equipment nozzle loads. **Ask whether one is invoked; do not assume.** Two examples where PIP PNC00004 is invoked: it sets a 16 mm (⅝ in.) sag limit (§3.2.11.1) and never credits cold spring in `S_E` (§3.2.14.3–.4). Open the practice before citing a clause into a sealed calc, and state the code edition beside it.

---

## Running the tool

`scripts/stress_screening.py` (Python 3.9+, standard library only). Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.

- **Run `python scripts/stress_screening.py list` first** to get the exact field names (for example `SA`, not `S_A`). Names are case-sensitive and unknown names are rejected with exit code 2.
- **Every number you state comes from a script run**, including side comparisons, what-ifs and sensitivity remarks (for example "what would f be at 7,000 cycles"): run the script again rather than computing in your head.
- A pre-flight check runs before the engine. It stops physically impossible inputs with exit code 2 (negative pressure, wall of D/2 or more, `f` above 1.2, `k` outside 1.0 to 1.33, an unrecognised sustained `method`, no fatigue `equation`) and adds warnings for implausible ones (`f` above 1.0, an unusual `k`, a spring `limit` below 1 that looks like a fraction). Quote those warnings in the findings.

```
python scripts/stress_screening.py list
python scripts/stress_screening.py <module-id> --input '<json>'
python scripts/stress_screening.py <module-id> --input-file inputs.json
python scripts/stress_screening.py basis --code B31.1 --edition 2024
```

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

Each call prints a JSON envelope `{module, status, output, warnings, citation, inputs, user_supplied}`; `user_supplied` lists the inputs that are code or project values the user must be able to cite. Exit code 2 means bad input. Illustrative call (every number below is a placeholder, not a code value):

```
python scripts/stress_screening.py screen.support-span --input '{"w": 24, "E": 1.0e7, "S_allow": 3000, "delta_allow": 0.25, "OD": 6.625, "t": 0.28, "end_condition": "simple"}'
```

Present the output with its citation and warnings, and carry the `equation` string and any warning into the calc sheet. A `status` of `na` means the module reports a value with no pass/fail. The tool does not read tables and does not compute SIFs; every allowable, modulus and `i` in the inputs comes from the user's licensed copy.

---

## Output format — the calc sheet

Keep this order; it mirrors how a reviewer reads.

```
# Pipe Stress Calculation — [line number / system]

## 1. Basis
Code, edition, fluid service, owner practices (with edition), load standard and edition (and why),
ASD-factor position for wind/seismic, resolved equation generation and SIF source, software and version.

## 2. Inputs
Geometry, material, conditions, cycle count, site data. Every assumed value flagged ASSUMED.

## 3. Allowable stresses and factors
Each value with its full citation: code, edition, table, material spec, grade, product form,
temperature, notes. Interpolation arithmetic shown. f derivation and cap reason shown.

## 4. Load cases
### 4.1 Sustained    equation used, S_L, allowable, ratio, PASS/FAIL
### 4.2 Occasional   each event separately, with its derivation; k or 1.33 and its duration basis
### 4.3 Expansion    range basis, S_E, S_A, ratio, PASS/FAIL; SAM and settlement if present
### 4.4 Installed / hydrotest   run or dismissed, with reason

## 5. Supports (if in scope)
Spans (both criteria, governing), spring table (hot/cold load, travel, rate, variability),
local-stress checks called out.

## 6. Findings and assumptions
Open items, values the user must confirm, anything that would change the conclusion.

## 7. References
Every code paragraph, with edition.
```

"[material], [value] psi" with no table, edition or temperature is not a citation. Every allowable needs the full chain, and the user supplies it.

---

## Before you hand it over — rejection checklist

Each is a five-second check that prevents a re-issue.

1. Code edition undeclared, or equation generation not matched to it (f form, SIF source).
2. A load case missing, or silently dropped with no reason.
3. Allowable taken at the wrong temperature, or with no table line cited.
4. Sustained check using expansion SIFs, or a section basis that does not match the code (B31.3: Z less all allowances; B31.1: nominal Z).
5. Expansion range that does not bracket installed-to-operating, or ignores a below-ambient state.
6. SIFs transposed in-plane/out-of-plane at a tee, or a tee leg sharing another leg's SIF.
7. Wrong SIF document for the edition (Appendix D under an edition that deleted it).
8. f = 1.0 assumed with no cycle count; f = 1.2 applied under B31.1; f cap given with no reason under B31.3.
9. Cold spring credited in `S_E`.
10. Liberal allowance used without spec permission, or without stating that it consumes the margin.
11. B31.1 k with no stated duration; B31.3 1.33 confused with the ¶302.2.4(f) variation allowance.
12. Wind and seismic combined into one occasional case.
13. ASD 0.6W / 0.7E applied under B31.1-2024, or applied under B31.3 with no cited basis.
14. Formal-analysis exemption claimed with more than two fixation points, an intermediate restraint or mixed sizes, or used as if it covered nozzle loads and sustained stress.
15. Spring variability not reported for every spring, or over the limit with no engineer's acceptance.
16. Span from a table outside its basis, E taken at ambient, or concentrated loads ignored.
17. A support reaction handed to a standard detail with no capacity check.

---

## Copyright boundary

**Never reproduce, reconstruct, estimate or "recall" tabulated values** — allowable stresses for any material, elastic moduli, thermal expansion data, SIF or stress-index table entries and the equations behind them (B31J, Appendix D), B31.1 Table 121.5 spans, MSS SP-58 table values, ASCE 7 coefficient tables or figures, PIP tables. This applies even when the user asks directly and even when a value seems widely known. Name the table, row and edition, and ask the user to read it from their licensed copy:

> I need S_h at the design temperature for your material and product form. That is in the code's allowable stress table; read the value at the two adjacent tabulated temperatures and I will interpolate. Which edition are you using?

Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value they need.

Equations, clause numbers, symbol definitions and numeric limits stated in running text (1.33, k = 1.15 / 1.20, the 25 % and 6 % spring limits, the f-factor floor of 0.15, the 700 °F and 75 ksi cap conditions) are usable.

---

## Related tools

Free calculators at pipingtoolset.com cover checks this skill describes: [B31.3 displacement stress range](https://pipingtoolset.com/calculators/b313-displacement-stress-range/?utm_source=claude-plugin&utm_medium=skill), [pipe support spacing](https://pipingtoolset.com/calculators/pipe-support-spacing/?utm_source=claude-plugin&utm_medium=skill), [spring hanger variability](https://pipingtoolset.com/calculators/spring-hanger-variability/?utm_source=claude-plugin&utm_medium=skill), and the [B31 load cases guide](https://pipingtoolset.com/guides/b31-pipe-stress-load-cases/?utm_source=claude-plugin&utm_medium=skill). Mention them only when the user needs a worksheet or a second implementation to cross-check against.

*Results are engineering aids. The engineer of record verifies every calculation against the project's code edition, owner practices and analysis software before issue.*
