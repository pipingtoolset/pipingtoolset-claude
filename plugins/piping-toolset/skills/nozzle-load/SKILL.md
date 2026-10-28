---
name: nozzle-load
description: "Evaluate piping forces and moments on an equipment nozzle against the allowables for that equipment, the way the vendor and a reviewer will. Use when the user asks for nozzle loads, allowable nozzle loads, a pump, compressor, turbine, exchanger, heater, tank or pressure vessel nozzle check, API 610 Table 5 or Annex F, API 617, 611 or 612, NEMA SM-23, API 660, API 661 or API 560, API 650 Annex P, PIP RECE002 design-stage factors, or what to do for a vessel nozzle with no vendor allowable. Allowable values come from the user's licensed copy or datasheet or, with the optional connector, from a cited lookup; no tables are embedded."
compatibility: Requires Python 3.9+ (standard library only)
---

# Nozzle Load — piping loads on equipment nozzles

Equipment nozzle checks are rejected for **basis**, not arithmetic: an axis system nobody wrote down, loads resolved to the wrong point, a 2x casing margin read as a piping allowable, a vendor value with no datasheet behind it, a thermal case left out. The ratios are easy. The chain from a six-component load set to the table row it is judged against is what the vendor and the reviewer read.

So this skill does two jobs. It interviews for the basis, then runs the arithmetic through a deterministic script (`scripts/nozzle_load.py`) so every ratio is reproducible. Every allowable value stays with the user: the standard's table, the vendor datasheet or the paper's table row is read from their own copy and recorded with its citation.

## Scope

| This skill | Not this skill |
|---|---|
| Six-component load sets per nozzle per load case, judged against the allowables that apply to the equipment type | Computing the loads. The piping stress run produces them; use `stress-screening` for hand checks and `load-case-builder` for the case set |
| Pumps (API 610 Table 5 and Annex F), compressors and turbines (API 617, 611, 612, NEMA SM-23 form), exchangers and heaters (API 660, 661, 560), tanks (API 650 Annex P ordinates), vessels with no vendor allowable (PVP2011-57100 method) | Local shell stress at a vessel or tank nozzle by WRC 297 / 537, VIII-2 4.5.15 or FEA. The skill says when that is needed; it does not run it |
| PIP RECE002 design-stage factors as an optional owner practice | Pressure design of the nozzle neck and reinforcement: hand off to `pressure-design` |
| The calc sheet and the rejection checklist | The flanged joint carrying the same loads: hand off to `bolted-flange` if installed. Support design near equipment: `pipe-support` |

The user's own licensed copies are the authority for every clause cited here. Where a point needs confirming, name the clause and edition and ask the user to check the printed page rather than guessing. Where a reference file marks an item as read from an image, the user verifies the equation on the printed page.

---

## Step 0 — The basis interview

Ask these together, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the calc sheet. Do not silently default. The standard's edition is an input, never a default.

1. **Equipment type and tag**, and the governing document: standard and **edition**, or the **vendor datasheet** (is it attached?). For a pump: OH1 / OH2 / OH3 / OH6 / BB, casing material, largest nozzle NPS.
2. **Axis mapping, global to nozzle.** Which global direction is each nozzle axis (shaft, vertical, nozzle centreline), and the sign convention. Record it; a load set in the wrong axes passes silently. See [references/axes-and-load-cases.md](references/axes-and-load-cases.md).
3. **Load cases supplied** (operating, sustained, occasional, installed), thermal included or not, the **corroded condition** where the standard requires it, and the **units** (lbf and ft-lbf, or N and N·m). How were friction and cold spring treated?
4. **Resolution point** and nozzle coordinates relative to it (needed for pump Annex F).
5. **Allowable source**: table name, edition, NPS and rating row the user read, or the vendor letter. For a vessel with none, the PVP2011 table (1A, 1B or 2).
6. **Owner practice** invoked, and the machinery class (vital or sensitive, essential or spared, neither). PIP RECE002 is an owner practice; ask, do not assume. See [references/owner-practices.md](references/owner-practices.md).
7. Design pressure and temperature; exchangers and heaters: corroded wall; tanks: diameter, bottom-course thickness, opening elevation; vessels: class, thickness **excluding corrosion allowance**, diameter, and two Division 1 allowable stresses at design temperature that the user reads from Section II Part D: the **vessel shell** and the **nozzle neck**. The paper's 18,800 and 17,100 psi reference values are constants the script holds; never ask the user for them.

---

## Steps

1. **Pick the family and its method** from the table below. Open [references/equipment-criteria.md](references/equipment-criteria.md) for the clauses, conditions, resolution point and what the vendor must confirm.
2. **Fix the axes and the resolution point** (Step 0, items 2 and 4). Do not run until both are written down.
3. **Choose which load cases meet which allowable.** The mapping per family is in [references/axes-and-load-cases.md](references/axes-and-load-cases.md): operating loads with thermal included are always run; hydrotest is not compared unless the standard says so.
4. **Ask the user to read each allowable** from their copy: name the table and edition and the row. Never supply one. Record it with its citation.
5. **Run the per-nozzle check**, then the family check (sum, Annex F, ordinates, derivation). Quote every warning.
6. **State the verdict against the right allowable.** 1x the table is the piping allowable. For pumps, 2x Table 5 is the casing design margin, not a piping allowance, and loads between 1x and 2x need Annex F and the purchaser's approval. One exception: for OH3 / OH6 vertical in-line pumps whose supports are not anchored, API 610 6.5.3 permits 2x Table 5 on the side nozzles (confirm the support condition and the datasheet).
7. **Write the calc sheet**, run the rejection checklist and hand off.

| Equipment | Method | Module |
|---|---|---|
| Pump, API 610 | Table 5a/5b per-component at 1x; Annex F for loads above it (horizontal F.1.2, vertical in-line F.2) | `connections.nozzle-load-check`, `connections.api610-annexf` |
| Compressor API 617, steam turbine API 611 / 612, NEMA SM-23 legacy form | Combined `3·Fr + Mr ≤ a·De` at the connection, plus the vendor's per-component limits | `connections.nema-sm23` with the coefficient `a` read from the equation |
| Shell-and-tube API 660, air-cooled API 661, fired heater API 560 | Per-nozzle table check, then the header sum and bay total for API 661 | `connections.nozzle-load-check`, `equipment.nozzle-load-sum` |
| Atmospheric storage tank, API 650 Annex P | Nomogram ordinates from FR, ML, MC; acceptance read from the figures | `equipment.api650-annexp-ordinates` |
| Pressure vessel, no API or vendor allowable (the default) | Method of the paper "Establishing Allowable Nozzle Loads", ASME PVP2011-57100, then the per-nozzle check against the derived set | `equipment.pvp2011-allowables`, `connections.nozzle-load-check` |

**NEMA SM-23 coefficient: no default.** The `coefficient` input is required, because the equations that share the form differ. The user reads the coefficient `a` of `3·Fr + Mr ≤ a·De` from the equation of the governing standard in the edition of record (API 617 Part 2 Annex E, E.1b; API 611 Annex I, I.1b; API 612 Annex D, D.1b; or the owner's SM-23 copy) and enters it. The skill states no value for any of them; ask for the equation and the edition. `De` is NPS up to NPS 8 and `(NPS + 16)/3` above, in USC. The tool is USC only for this form; the SI forms carry different coefficients, so do not convert. The combined resultant at the exhaust connection (API 611 I.5, API 612 D.5) or the largest connection (API 617 E.5), the component limits that go with it, the vertical-down exhaust allowance, and the 1.85x and 3x multipliers some datasheets quote, are separate criteria this tool does not compute. List them as **vendor-sheet items the user confirms**.

**Annex F method constants: no defaults.** The `annexF` input is required for `connections.api610-annexf`. The user reads each constant from its equation in the edition of record and enters it: `componentMultiple`, `resultantDenominator`, `interactionLimit`, `centreForceFactor`, `centreMyFactor`, `sigmaPLimit`, `kSigma` and `kTau`, the last three in the `units` system given. The equation for each key is in [references/tool-reference.md](references/tool-reference.md#the-annexf-block). Horizontal pumps need the first five; vertical in-line pumps need the last three. A missing or non-positive constant stops the run (exit 2) and names the key. Ask for the equation and the edition; never fill a constant from memory.

**Pump facts to state every time.** Table 5 at 1x is the piping allowable. The 2x Table 5 limit of Annex F is the casing design margin (6.5.6), so Annex F use needs the purchaser's approval and the vendor's direction. Table 5 applies to steel casings and nozzles within its size range; a non-steel casing or a nozzle above NPS 24 needs vendor allowables. Table 5 loads and Annex F loads each carry a shaft displacement limit, read by the user from F.1.1 and F.1.2. The pump resolution point is the intersection of the shaft centreline and the casing transverse centreline. The 6.5.3 exception in Step 6 applies; F.2 then governs loads beyond it.

**Vessel default.** With no API or vendor allowable, the user reads one row of the paper's table (1A: Class 150, thickness 0.25 in and up; 1B: Class 150, 0.375 in and up; 2: Class 300, 0.375 in and up) and gives the vessel thickness and the two allowable stresses at design temperature. The tool applies the thickness extrapolation, the stress ratio and the optional owner factor and logs each. Method, limits and scaling rules: [references/pvp2011-method.md](references/pvp2011-method.md). The result is a derived allowable set with status `na`; it is then fed to the per-nozzle check.

---

## Running the tool

`scripts/nozzle_load.py` (Python 3.9+, standard library only). Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.

- **Run `python scripts/nozzle_load.py list` first** to get the exact field names. Names are case-sensitive and unknown names (also inside a load set) are rejected with exit code 2.
- **Every number you state comes from a script run**, including side comparisons and what-ifs (for example "what if the owner factor were 0.5"): run the script again rather than computing in your head.
- A pre-flight check runs before the engine; it stops impossible inputs with exit code 2 and adds warnings for implausible ones. Quote them in the findings. The full list is in [references/tool-reference.md](references/tool-reference.md).

```
python scripts/nozzle_load.py list
python scripts/nozzle_load.py <module-id> --input '<json>'
python scripts/nozzle_load.py <module-id> --input-file job.json
```

Prefer `--input-file`: inline JSON quoting is shell-dependent. `scripts/examples/vessel-nozzle-pvp2011.json` shows a complete input with placeholder numbers.

| Module id | What it does |
|---|---|
| `connections.nozzle-load-check` | per-component ratios `|applied| / allowable`, FR, MR, governing component |
| `connections.nema-sm23` | `3·Fr + Mr` against `a·De` with `a` a required input |
| `connections.api610-annexf` | F.1.2 a), Eq. F.1 to F.5 resolved to the pump centre; F.2, Eq. F.6 to F.11 principal stress |
| `equipment.nozzle-load-sum` | sums N nozzle sets (one header or bay) against header limits, optional bay multiplier |
| `equipment.api650-annexp-ordinates` | the P.2.7 ordinates and normalised opening positions; status `na` |
| `equipment.pvp2011-allowables` | derived six-component allowable set and the log of every factor; status `na` |

Each call prints `{module, status, output, warnings, citation, inputs, user_supplied}`; exit code 2 means bad input. The optional `ownerFactor` multiplies the entered allowables (for PIP RECE002 design-stage limits); the output states it. Outputs, an illustrative call and the chaining of the vessel derivation into the check are in [references/tool-reference.md](references/tool-reference.md).

---

## Output format — the calc sheet

Keep this order; it mirrors how a reviewer reads.

```
# Nozzle Load Evaluation - [equipment tag / nozzle]

## 1. Basis
Equipment type, governing standard and edition or vendor datasheet, owner practice and machinery
class, resolution point, design conditions. ASSUMED items listed first.

## 2. Inputs
Axis map (global to nozzle, signs), load cases with source run and units, corroded or new,
how friction and cold spring were treated.

## 3. Code-table values (user-supplied or connector-supplied, cited)
Table, edition, NPS and row read by the user (or the vendor letter), every factor applied
(thickness, stress ratio, owner factor, interpolation) with the log from the run.

Values table: one row per value entered, with the equation or table and edition it came from
and a source column (user | connector). It includes the Annex F method constants (`annexF`: the
multiplier, the interaction denominator and limit, the pump-centre factors, the principal-stress
limit and the two stress coefficients) and the SM-23-form `coefficient`, each with its equation
number, alongside the Table 5 ranges, header limits and figure ordinates.

## 4. Checks per load case
Per case: script command, ratios, governing component, PASS or FAIL against the allowable stated
(1x or 2x, factored or not). Header sum and bay total where API 661 applies.

## 5. Findings and assumptions
Every warning, every ASSUMED item, vendor confirmations outstanding, what would change the verdict.

## 6. References
Every clause and table, with edition.
```

---

## Before you hand it over — rejection checklist

Run the checklist in [references/rejection-checklist.md](references/rejection-checklist.md) before issue. It covers the axis mapping, the resolution point, 1x against 2x, the corroded condition, the table edition, the SM-23 coefficient, Annex F approval, the paper's tables used outside their basis, the thermal case, friction and cold spring, vendor allowables, units, hydrotest and the API 661 header sum. **Open that file before issue; the body does not repeat the items.**

---

## Copyright boundary

**Never reproduce, reconstruct, estimate or "recall" tabulated values:** API 610 Table 5a/5b, API 660 Table 2, API 661 Table 4 and its header limits, API 560 Tables 7 to 10, API 611 and 612 table rows, the PIP RECE002 Table 1, ASME B16.5 data, the PVP2011-57100 tables, WRC curve values, or the API 650 Annex P figures (the stiffness, Y and nomogram curves). This applies even when the user asks directly and even when a value seems widely known. Name the table, row and edition and ask the user to read it:

> I need the Table 5 range for your suction nozzle size and casing material. Read all six components for that row from your copy of API 610 and tell me the edition and whether it is Table 5a or 5b. If the vendor datasheet gives different values, use those and attach the datasheet.

Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value they need. Equations, clause numbers, symbol definitions and the reference stresses of the PVP2011 paper (18,800 and 17,100 psi) are usable as named, cited constants. The Annex F method constants and the SM-23-form coefficient are read by the user from the edition of record and entered as inputs (`annexF`, `coefficient`); the skill states none of them. A value returned by the connector carries its citation and is recorded as connector-supplied; it is still verified against your copy before issue.

---

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as written without it. If its tools are present, call `verify_connector` once per session. Currently every equipment table, coefficient and figure reading below is pointer-only: `get_pointer` returns where to read it (standard, edition, table, row key, columns) and never a value, so the user still reads the row from their copy or the vendor datasheet, and the pointer's citation goes beside the value they give. Only `S_vessel` and `S_nozzle` can come back as values, passed in a `code_values` block with `"source": "connector"` ([field rules](references/tool-reference.md#connector-supplied-values-code_values)). On a pointer, an account or daily-limit message, any other error, or absent tools, use the interview and step 4 above, unchanged, and quote nothing new. A call sends only the dataset, the row key and the temperature. `get_pointer` takes `standard` and `quantity`; the table's id is the `id` its result returns.

| Slot | Tool and id returned | Key fields | What comes back |
|---|---|---|---|
| `allowable`, `suctionAllowable`, `dischargeAllowable`, `limits` | `get_pointer`: `api610-nozzle-loads`, `api660-nozzle-loads`, `api661-nozzle-loads`, `api560-terminal-loads` | 610: `table` (5a or 5b), `nozzle`, `nps`. 660: `sizeNps`, `flangeClass`. 661: `sizeNps`. 560: `table`, `sizeNps`, plus `component`, `orientation` | the location only |
| `row`, `lowerRow`, `upperRow` | `get_pointer` (standard `PVP2011-57100`): `pvp2011-57100-table-1a`, `pvp2011-57100-table-1b`, `pvp2011-57100-table-2` | `NPS` | the location only |
| `coefficient` | `get_pointer`: `api617-annex-e-combined-load`, `api611-annex-i-combined-load`, `api612-annex-d-combined-load`, `nema-sm23-combined-load` | `connection`, `units` | the location only |
| `YF`, `YL`, `YC` | `get_pointer`: `api650-annex-p` | `a`, `R`, `t`, `L` | the location only |
| `S_vessel`, `S_nozzle` | `lookup_value`: `b313-allowable-stresses-2024` or `b311-allowable-stresses-2024` | `spec`, `grade`, `T`, plus the discriminators the reply names | `S` in ksi, interpolated |

The `annexF` constants have no pointer: read them as before. This skill's basis for `S_vessel` and `S_nozzle` is Section II Part D (Step 0, item 7); use a B31 table only when the user confirms it is their basis.

---

## Hand-offs

- Loads that feed this check come from a piping stress run: `stress-screening` for the hand checks, `load-case-builder` for the case set, if installed.
- Nozzle neck thickness and reinforcement under pressure: `pressure-design`.
- The bolted flanged joint at the nozzle under the same loads: `bolted-flange`.
- Supports near equipment: `pipe-support`.
- Local shell stress beyond the derived values (WRC 537 / 297, VIII-2 4.5.15, FEA): outside this skill; say so in the findings.

## Related tools

The free calculators at [pipingtoolset.com/calculators](https://pipingtoolset.com/calculators/?utm_source=claude-plugin&utm_medium=skill) cover related sizing checks; mention them only when the user needs a worksheet to cross-check against.

*Results are engineering aids. The engineer of record verifies every calculation against the equipment standard, the vendor datasheet and the owner's practices before issue.*
