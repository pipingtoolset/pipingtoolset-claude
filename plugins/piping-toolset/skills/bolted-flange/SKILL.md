---
name: bolted-flange
description: "Evaluate piping loads on a bolted flanged joint in a fixed order: a pressure-equivalent (Kellogg-type) leakage screen against the B16.5 flange rating first, then the detailed BPVC VIII-2 Part 4.16 flange analysis (the retired VIII-1 Appendix 2 method, permitted by B31.3 304.5.1(b)) with gasket seating, bolt area, hub, radial and tangential stress, and rigidity. Use when the user asks about flange leakage, whether a flange will leak under CAESAR II or AutoPIPE nozzle loads, loads on a flange at an API 610 nozzle (the flange only: the pump allowable itself belongs to the nozzle-load skill), for the equivalent pressure method (P + 16M/(pi G^3) + 4F/(pi G^2)), axial force and bending moment against a flange rating, gasket m and y, bolt load, flange stress, or UG-44(b), PCC-1 or NC-3658 flange moment limits. The user reads the rating, dimensions, gasket factors and allowables from licensed copies or, with the optional connector, from a cited lookup; no code table values are embedded."
compatibility: Requires Python 3.9+ (standard library only)
---

# Bolted Flange - loads on flanged joints

A flange evaluation is rarely rejected for arithmetic. It is rejected because the screen was run against the wrong rating, the moment was in the wrong unit, the gasket factors have no table line behind them, or a conservative screen was reported as if it were a stress check. The equations are short. The method order and the traceability are what a reviewer reads.

So this skill does two things. It runs the loads from the piping analysis through a fixed ladder - a mandatory pressure-equivalent screen, then the detailed Section VIII flange analysis - using a deterministic script (`scripts/bolted_flange.py`), and it embeds no code-table value: the user reads each one, or takes it from the optional connector section below with its citation. A screen failure is a reason to look harder, not a verdict on the joint.

## Scope

| This skill | Not this skill |
|---|---|
| Axial force and bending moment resultant on a circular bolted flanged joint (weld-neck or loose ring) against the B16.5 rating, then the VIII-2 4.16 analysis | Nozzle loads on the equipment end (pumps, turbines, vessels, exchangers) against the equipment allowable, such as API 610: hand off to the `nozzle-load` skill in this pack if it is installed |
| Geometry derivation from user-read values (gasket b and G, bolt root area, hub g0, g1, h) | Pipe stress itself (SUS / OCC / EXP, SIFs): the `stress-screening` skill, if it is installed. Load case sets: the `load-case-builder` skill |
| The calc sheet, what each rung proves, and what is not computed | Wall thickness, MAWP, hydrotest pressure: the `pressure-design` skill (the flange rating is a user-read B16.5 table value, not computed anywhere in this pack). Full-face gaskets, slip-on, lap-joint, reverse, split, nut-stop and non-circular flanges, self-energizing gaskets, EN 1591-1, ASME III service levels |

Torsion and shear are not used by either method; the sheet must say so. The user's licensed copies of the codes are the authority for every clause cited. Where a point needs confirming, name the clause and edition and ask the user to check the printed page.

---

## Step 0 - The basis interview

Ask these together, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the calc sheet. Do not silently default; the edition is an input.

1. **Code and edition:** B31.3 or B31.1, and the year. Section VIII edition: VIII-1 2025 deleted Appendix 2 paragraphs 2-3 and 2-5 to 2-14 and maps them to VIII-2 Part 4.16, so cite 4.16. B31.3 304.5.1(b) permits either VIII-1 Appendix 2 or VIII-2 4.16 using B31.3 allowables, with Sf = S x E x W. B31.1 104.5.1 names Section VIII Division 1 only, with Sa and Sb from Mandatory Appendix A Table A-10 and Sf the Appendix A flange allowable: confirm with the user's B31.1 edition which edition of VIII-1 it references before applying 4.16.
2. **Owner practice** on external loads (a stress design criteria document, PIP PNC00004). It may set an acceptance percentage of the rating, or demand the detailed analysis. Ask; do not assume.
3. **Loads from the piping program**, per load case: axial force (signed, tension positive), bending moment resultant, torsion and shear (reported, unused), **and the unit of each** (lbf, N, in-lbf, ft-lbf, N-m).
4. **Design pressure and design temperature**, coincident with each load case run.
5. **Flange:** class, NPS, type (weld-neck or loose), material group, facing.
6. **Rating at design temperature** read by the user from the B16.5 pressure-temperature table, and any owner reduction.
7. **Flange dimensions** read from the B16.5 tables: A, B, C, t; for weld-neck also hub X, Y and the pipe it welds to.
8. **Gasket:** type, facing, contact ID and OD, and m and y with the table line they came from.
9. **Bolting:** count, size, threads per inch (or a root area), material.
10. **Allowables** with their table lines: Sa (bolt, ambient), Sb (bolt, design), Sf and SfAmbient (flange), Sn (attached pipe or neck), and the flange moduli.
11. Is the bolt-spacing correction required? Is the hydrotest case in scope?

Where each input lives, with lookup wording: [references/inputs-from-tables.md](references/inputs-from-tables.md).

---

## Step 1 - Derive the geometry

Run `connections.flange-derive` on the raw values the user read. It returns N, b0, b and G (flat and ring-joint rules), bolt root area from the UN thread formula, and hub g0 = (pipe OD - B)/2, g1 = (X - B)/2, h = Y - t. Carry b, G and N from this output into `aux.app2-flange-integral`, always for ring joints (an omitted b defaults to the flat rule, b0 = N/2, which is wrong for a ring joint). Never take G as the bolt circle, and never take root area from the nominal diameter. Facings other than flat and ring joint are read from the effective gasket width table and entered directly.

## Step 2 - Pressure-equivalent screen (mandatory, always reported)

Run `connections.flange-equivalent-pressure`: Pe = P + 16|M|/(pi G^3) + 4F/(pi G^2), compared with the rated pressure the user read. This is the common pressure-equivalent (M.W. Kellogg-type) method. Say what it is every time:

- It is a **leakage screen**. It treats the moment as an equivalent axial pressure load, and it is conservative for stress. It is **not a stress check**.
- **Compression (negative F):** VIII-2 4.16.13 defines FA as the external tensile net-section force and neglects compression (FA = 0), so the screen uses F = max(F, 0) unless the owner agrees to credit compression. The tool does this by default and warns; `creditCompression: true` credits it, and then the tensile case is run separately and both are reported.
- The rating is the B16.5 rating **at design temperature**. Owner practice may require a lower percentage of it. PIP PNC00004 3.2.10 allows the equivalent pressure method but sets no acceptance value; the owner does.
- The moment is **in-lbf** in the tool (`M_in_lbf`); `M_ft_lbf` is converted. Give exactly one.

If the screen passes with margin, say the joint passes the screen and the detailed analysis is optional unless the owner requires it. If it fails, the detailed analysis follows. **A screen failure is not a joint failure.**

## Step 3 - Detailed VIII-2 4.16 analysis

Run `aux.app2-flange-integral` for the operating case (design temperature allowables) and the gasket seating case (ambient allowables). It reports bolt area adequacy (Ab >= Am), the hub, radial and tangential stresses and their averages against the allowables, the 1.5 Sf / 2.5 Sn cap on the hub stress, the rigidity index J <= 1, and the bolt-spacing correction. Method notes:

- The external loads enter as the pressure-equivalent Peq, and the whole sequence runs on Peq. That is standard practice but it is **not** an Appendix 2 / 4.16 construction; say so, and read Peq, momentTerm and forceTerm from the output.
- Compression: same rule as the screen. Run the detailed module with `Fax` set to max(F, 0) unless the owner agrees to credit compression (then run the tensile case separately and report both), and state which was done.
- If neither `Fax` nor `Mext` is given the run is pressure-only (Peq = P); the tool warns. Give the loads.
- Peq also reaches the gasket-seating case (Am includes Wm1/Sb), which is conservative; the seating result moves with the external loads.
- Supply **Sn**. Without it the 2.5 Sn cap is unchecked and the tool warns.
- Hub factors F, V, f default to a closed-form series that is a reconstruction, not Code text. For a sealed calc, have the user read F, V, f from the VIII-2 Table 4.16.5 equations or figures and pass `F_override`, `V_override`, `f_override`. The Table 4.16.5 curve-fit option is not shipped (`hubFactorMethod` other than `series` exits 2).
- The moment `Mext` is in **ft-lbf** in this module (use `Mext_in_lbf` for in-lbf). The bolt-spacing correction scales the stress moments, not the rigidity moment.
- "Pass" means the tool's pass rule, not acceptance. A failing result names what failed; report all of it.

Equations in engine order, symbols and the loose/integral differences: [references/app2-engine.md](references/app2-engine.md).

## Step 4 - What is not computed, and where it lives

Name these on the sheet; do not compute them here: the UG-44(b) / VIII-2 4.16.12 interaction, ASME III NC-3658.3, EN 1591-1, PCC-1 Appendix O, the VIII-2 4.16.7.2 Step 9(b) shear check with the Code's own external-moment term Moe, and the B16.5 2.5.2 advisory (flag it when the design temperature is in that range). Where each applies, its conditions, and the clause map: [references/method-ladder.md](references/method-ladder.md#what-is-not-computed).

---

## Running the tool

`scripts/bolted_flange.py` (Python 3.9+, standard library only). Script paths are relative to this skill's directory. Call the script by its full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them. `scripts/examples/integral-weld-neck.json` is a worked example with placeholder inputs.

- **Run `list` first** to get the exact field names; names are case-sensitive and unknown names are rejected with exit code 2.
- **Every number you state comes from a script run**, including side comparisons and what-ifs (for example "what if the moment were halved"): run it again rather than computing in your head.
- Write the object to `job.json` with the file tool and run with `--input-file job.json`; inline JSON is shell-dependent.
- A pre-flight check refuses to default the moduli and ambient flange allowable, rejects two moment units at once, and adds warnings. Quote them in the findings.

```
python scripts/bolted_flange.py list
python scripts/bolted_flange.py connections.flange-derive --input-file job.json
python scripts/bolted_flange.py connections.flange-equivalent-pressure --input-file job.json
python scripts/bolted_flange.py aux.app2-flange-integral --input-file job.json
```

| Module id | What it does |
|---|---|
| `connections.flange-derive` | N, b0, b, G; UN bolt root area; hub g0, g1, h |
| `connections.flange-equivalent-pressure` | Pe, utilization against the rating (the screen) |
| `aux.app2-flange-integral` | VIII-2 4.16 bolt loads, moments, stresses, rigidity (integral and loose) |

Each call prints `{module, status, output, warnings, citation, inputs, user_supplied}`; exit code 2 means bad input. Fields, outputs, and status meaning: [references/tool-reference.md](references/tool-reference.md).

---

## Output format - the calc sheet

```
# Bolted Flange Evaluation - [line / flange tag]

## 1. Basis
Code and edition (B31.x, Section VIII edition, 4.16 path), owner practices, load cases run,
method order, ASSUMED items first.

## 2. Inputs
Loads with units and sign convention; torsion and shear listed as not used; design P and T;
flange type, class, size; geometry; bolting. Every assumed value flagged.

## 3. Code-table values (user-supplied or connector-supplied, cited)
Rating, A B C t X Y, gasket ID/OD, m, y, Sa Sb Sf SfAmbient Sn, moduli: each with value,
table and line, edition, temperature, material, notes applied, source (user | connector).

## 4. Step 2 - Pressure-equivalent screen
Command, Pe, rated pressure, utilization, status, warnings. State: leakage screen, not a stress check.

## 5. Step 3 - Detailed analysis
Operating and gasket seating cases: Peq, Am vs Ab, moments, SH SR ST and averages vs allowables,
J, Bsc, hub-factor source (series or override). Both cases, all checks.

## 6. Findings and assumptions
Every warning, ASSUMED item, unchecked cap, method not computed (Step 4), anything that would
change the conclusion.

## 7. References
Every clause cited, with edition.
```

---

## Before you hand it over - rejection checklist

Run the checklist in [references/rejection-checklist.md](references/rejection-checklist.md) before issue. It covers the rating at the wrong temperature, G taken as the bolt circle, moment units, compression credit, the screen reported as a stress check, the 2.5 Sn cap, gasket m and y citations, Sa and Sb, loose versus integral, bolt root area, rigidity, the hydrotest case, the ring-joint rule and the owner percentage. **Open that file before issue; the body does not repeat the items.**

---

## Copyright boundary

**Never reproduce, reconstruct, estimate or "recall" tabulated values:** B16.5 pressure-temperature ratings or dimensions, B16.20 gasket dimensions, gasket factors m and y, allowable stresses for any material, elastic moduli, Table 4.16.5 factor values (curves or tabulated results), Table UG-44-1 moment factors. This applies even when the user asks directly and even when a value seems widely known. Name the table and the line, and ask the user to read it from a licensed copy:

> I need the rating at your design temperature. That is the B16.5 pressure-temperature table for your material group (U.S. customary version), Class [x]. Read the value at the tabulated temperatures either side of yours and any notes; the standard permits linear interpolation between temperatures, not between classes. Which edition are you using?

Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value needed. A value returned by the connector carries its citation and is recorded as connector-supplied; it is still verified against your copy before issue.

Equations, clause numbers, symbol definitions and numeric constants in the running text of an equation are usable, as named and cited constants in the script. The Table 4.16.5 curve-fit coefficients are tabulated code data and are not shipped; the user reads F, V and f from the VIII-2 equations or figures and passes the overrides. Where a clause's equation could not be verified here, say so and ask the user to confirm it on the printed page.

---

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as written without it. If its tools are present, call `verify_connector` once per session, then make one `lookup_value` call per value the job needs. Pass returned values to the script in a `code_values` block with `"source": "connector"` and the lookup's own `unit`, which the script converts ksi to psi ([field rules](references/tool-reference.md#connector-supplied-values-code_values); column-to-input map in [references/inputs-from-tables.md](references/inputs-from-tables.md#connector-datasets)), and put the citation, `rows_used` and `verify_at` line on the sheet. Use a value only when its citation names the edition and table of record. On a `mode` of `pointer`, an account or daily-limit message, any other error, or absent tools, use the interview and the lookup wording in that reference, unchanged, and quote nothing new. A call sends only the dataset, the row key and the temperature.

| Slot | Tool and dataset_id | Key fields | What comes back |
|---|---|---|---|
| `ratedPressure` | `lookup_value`: `b165-2017-ratings` or `b165-2025-ratings` | `group`, `class`, `T` (design °F) | `rating`, interpolated in `T` only |
| `A`, `C`, `t`, `X`, `Y`, `nBolts`, `bolt_D` | `lookup_value`: `b165-2017-dimensions` | `flangeClass`, `nps` | `odA`, `boltCircleC`, `minThk`, `hubBaseX`, `lengthThruHubY`, `nBolts`, `boltDia` |
| `gasket_ID`, `gasket_OD` | `lookup_value`: `b1620-2017-spiral-wound` | `flangeClass`, `nps` | `gasketID`, `gasketOD` |
| `m`, `y` | `lookup_value`: `gasket-factors-4161` | `family`, `material` | `m`, `y`, `facingSketch` |
| `Sa` at ambient, `Sb` at design | `lookup_value`: `b313-bolting-stresses-2024` or `b311-bolting-stresses-2024` | `spec`, `grade`, `T`, plus `size`, `lineNo`, `notes`, `sizeOrDia` as asked | `S` in ksi |
| `Sf`, `SfAmbient`, `Sn`, `SnAmbient` | `lookup_value`: `b313-allowable-stresses-2024` or `b311-allowable-stresses-2024`; B31.3 also `b313-ej-factors` or `b313-ec-factors`, and `b313-w-factors` | `spec`, `grade`, `T`, plus the discriminators the reply names | `S` in ksi. Under B31.3 304.5.1(b) `Sf` is S x E x W, a product formed by a script run |

Take the rating from the dataset edition that matches the user's B16.5 edition. `B`, `Edesign`, `Eambient`, `F_override`, `V_override` and `f_override` have no dataset. Where the user's basis for `Sa` and `Sb` is Section II Part D, read them as before.

---

## Hand-offs

- Equipment nozzle loads against the equipment's own allowable (API 610 and similar): the `nozzle-load` skill in this pack, if it is installed.
- Wall thickness, MAWP, hydrotest and leak-test pressure: the `pressure-design` skill, if it is installed. The flange rating itself is read from B16.5 by the user.
- Piping stress and the loads fed to this skill: the `stress-screening` and `load-case-builder` skills, if they are installed.

## Related tools

The free [bolted flange equivalent pressure calculator](https://pipingtoolset.com/calculators/bolted-flange-equivalent-pressure/?utm_source=claude-plugin&utm_medium=skill) runs the Step 2 screen, and the other [free calculators](https://pipingtoolset.com/calculators/?utm_source=claude-plugin&utm_medium=skill) cover related checks; mention them only when the user needs a second implementation to cross-check against.

*Results are engineering aids. The engineer of record verifies every calculation against the project's code edition, owner practices, the tables of record and the analysis software before issue.*
