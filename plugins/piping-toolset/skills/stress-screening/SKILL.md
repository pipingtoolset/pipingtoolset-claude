---
name: stress-screening
description: "Hand-check ASME B31.3 / B31.1 sustained, occasional and expansion (SUS/OCC/EXP) stress the way a reviewer will. Use when the user asks about S_A, the f factor or cycle count, Eq. 17, 1.33 Sh or the k factor, which document gives the SIF (B31J vs Appendix D), the formal analysis exemption, support span, spring variability, or wants to check what CAESAR II or AutoPIPE applied."
compatibility: Requires Python 3.9+ (standard library only)
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

Section properties for the sustained check are code-specific (B31.3 ¶320.1 deducts all allowances for Z; B31.1 ¶104.8.1 uses nominal Z and wall). State which basis you used; mixing them silently is a finding. Detail: [references/load-cases-and-allowables.md](references/load-cases-and-allowables.md).

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

A calc that omits a load case is incomplete. If occasional loads are judged negligible, say so and why; silence is the defect. Run all three:

- **Sustained (SUS)**: pressure + weight + other sustained mechanical loads, using the **sustained** stress index (never the expansion SIF) and the code's section basis; limit S_h. The tool takes `S_b` and `S_t` already computed; the sqrt and additive forms are in the reference.
- **Occasional (OCC)**: sustained plus **one event at a time**; wind and earthquake are not combined. B31.3 uses a flat 1.33·S_h (1.20 for Chapter IX); B31.1 uses k = 1.15 or 1.20, and a k with no stated duration basis is a finding. Do not conflate the B31.3 1.33 with the ¶302.2.4(f) variation allowance.
- **Expansion (EXP)**: computed from the **range** between the two governing thermal states, with the expansion SIFs, against S_A (B31.3 Eq. (17)). Seismic anchor movement and settlement belong here, not in OCC. Also run, and say whether you ran, the **installed (cold)** case for support liftoff and spring travel, and the **hydrotest** case for lines whose contents are lighter than water.

Equations and the occasional-allowable table are in [references/load-cases-and-allowables.md](references/load-cases-and-allowables.md).

---

## Step 3 — Occasional loads and the ASD question

ASCE 7 wind speeds and seismic E are strength level; ASCE 7's own ASD combinations apply 0.6 to wind and 0.7 to earthquake. The piping codes differ:

- **B31.1-2024** (¶101.5.2 wind, ¶101.5.3 earthquake): ASCE 7 loads may be used, **except the ASD reduction factor shall not be applied**. Applying 0.6W or 0.7E is a finding.
- **B31.3** (¶301.5.2, ¶301.5.3): loads "may be as described in ASCE 7" and nothing is said about the factor. Default to **no reduction**, flag it ASSUMED, and apply 0.6 / 0.7 only on written direction of the owner specification or the engineer of record, citing that document.
- If you do reduce for stress, keep **unreduced** companion cases for support loads and displacements. The difference is 1/0.6 = 1.67× on wind force; never leave it unstated.

---

## Step 4 — Allowable range S_A and the f factor

S_A uses the base form f·(1.25·S_c + 0.25·S_h); the liberal form applies only where the spec permits and S_h > S_L, and a line that passes only with it has no margin. S_c and S_h come from the code's allowable stress table for the actual material and temperature (show any interpolation); the tool computes the base form only.

- **The f equation changed.** B31.3-2022 and later use `f = 20·N^-0.333`; earlier B31.3 and every B31.1 edition use `f = 6.0·N^-0.2`. Pass `equation: "legacy"` or `"b313-2022"` to `piping.fatigue-factor` (run `basis` to resolve it) and carry the output's `equation` string into the report.
- **The cap differs by code.** B31.1: f ≤ 1.0, no exceptions (1.2 is a rejection). B31.3: f ≤ f_m, 1.2 only for ferrous material with SMTS ≤ 75 ksi at design metal temperature ≤ 700 °F, otherwise 1.0; write the reason down.
- No cycle count: never assume f = 1.0 quietly; ask, or state that f = 1.0 needs N ≤ 7,000 equivalent full cycles, to be confirmed.
- **Cold spring is not a stress credit** under either code; it affects reactions only.

Worked comparison, partial-range cycles (`N_E`), the f floor and cap logic: [references/load-cases-and-allowables.md](references/load-cases-and-allowables.md).

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

Both codes (B31.3 ¶319.4.1(c); B31.1 ¶119.7.1, 2016 and later) allow a line to skip formal analysis when `D·y / (L − U)² ≤ K1 = 30·S_A / E_a`. Users over-read it, so state every time: no general proof of accuracy exists; no assurance of low terminal reactions; it is disqualified by more than two fixation points, any intermediate restraint or non-uniform size (pass `fixation_points`, `intermediate_restraints`, `uniform_size`; if one is omitted the tool returns `na`, so ask, do not assume); and it discharges displacement stress only.

Unit basis and full caveats: [references/exemption-and-spans.md](references/exemption-and-spans.md).

---

## Step 7 — Support spans

Compute both the bending and deflection criteria with `screen.support-span` and take the smaller span. E is at operating temperature, w includes contents, insulation, cladding and tracing, and E, S and the allowable sag are user-supplied with their basis stated. Pass `L_actual_ft` to test a proposed span. Concentrated loads, direction changes, rotating-equipment frequency, unequal spans and overhangs are not covered. Calculate the span; never read a table span back from memory.

Equations and end-condition table: [references/exemption-and-spans.md](references/exemption-and-spans.md).

---

## Step 8 — Spring hangers

Variable springs: variability |rate·travel| / hot load ≤ 25 % (MSS SP-58 §7.7.1.2); constant supports: deviation ≤ 6 % (§7.7.1.3). Report hot load, cold load, travel, rate and variability for **every** spring, installed and operating; a spring that tops or bottoms out cold is a finding. In the tool, `supports.spring-variability` takes `limit` in **percent** (25) but `supports.max-spring-rate` takes `variabilityLimit` as a **fraction** (0.25); do not mix them.

Formulas and notes: [references/spring-hangers.md](references/spring-hangers.md).

---

## Owner practices

Owner practices (stress design criteria, PIP practices) may add rules on top of the code: with and without friction runs, a sag limit, rod-hanger rotation limits, extra mandatory load cases, rules on rotating-equipment nozzle loads. **Ask whether one is invoked; do not assume.** Two examples where PIP PNC00004 is invoked: it sets a 16 mm (⅝ in.) sag limit (§3.2.11.1) and never credits cold spring in `S_E` (§3.2.14.3–.4). Open the practice before citing a clause into a sealed calc, and state the code edition beside it.

---

## Running the tool

`scripts/stress_screening.py` (Python 3.9+, standard library only). Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.

- **Run `python scripts/stress_screening.py list` first** to get the exact field names (for example `SA`, not `S_A`). Names are case-sensitive and unknown names are rejected with exit code 2.
- **Every number you state comes from a script run**, including side comparisons, what-ifs and sensitivity remarks (for example "what would f be at 7,000 cycles"): run the script again rather than computing in your head.
- A pre-flight check runs before the engine: it stops physically impossible inputs with exit code 2 and adds warnings for implausible ones. Quote those warnings in the findings. The full list of checks is in [references/tool-reference.md](references/tool-reference.md).

```
python scripts/stress_screening.py list
python scripts/stress_screening.py <module-id> --input '<json>'
python scripts/stress_screening.py <module-id> --input-file inputs.json
python scripts/stress_screening.py basis --code B31.1 --edition 2024
```

| Module id | What it does |
|---|---|
| `piping.displacement-stress` | S_E vs S_A (Eq. 17) |
| `piping.sustained-stress` | S_L and occasional stress, ratios |
| `piping.fatigue-factor` | N_E and f, either edition form |
| `supports.spring-variability` | spring cold load and variability % |
| `supports.max-spring-rate` | stiffest spring within a variability fraction |
| `noncode.pipe-section` | ID, A, I, Z, r from OD and wall |
| `screen.support-span` | bending, deflection and governing span |
| `screen.flexibility-exemption` | `D·y/(L−U)²` vs K1 and disqualifiers |

Each call prints a JSON envelope `{module, status, output, warnings, citation, inputs, user_supplied}`; exit code 2 means bad input. Quote warnings and the `equation` string in the calc sheet. Every allowable, modulus and `i` comes from the user's licensed copy. Per-module outputs, an illustrative call and the meaning of status `na` are in [references/tool-reference.md](references/tool-reference.md).

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
### 4.1 Sustained    equation used, S_L, allowable, ratio, verdict (within or exceeds the allowable)
### 4.2 Occasional   each event separately, with its derivation; k or 1.33 and its duration basis
### 4.3 Expansion    range basis, S_E, S_A, ratio, verdict; SAM and settlement if present
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

Run the 17-item checklist in [references/rejection-checklist.md](references/rejection-checklist.md) before issue. It covers edition and equation generation, all three load cases, allowable citations, SIF source and orientation, f and its cap, cold spring, k duration, ASD position, exemption over-claims, spring variability, span basis and support capacity. **Open that file before issue; the body does not repeat the items.**

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
