---
name: load-case-builder
description: "Build complete ASME B31.1 / B31.3 static load case sets for CAESAR II and AutoPIPE: HGR, HYD, OPE, SUS, EXP, OCC and envelopes with Algebraic / Scalar / SRSS combinations and occasional allowables. Use when the user asks for load cases, a load case set, combination cases or L-case numbering, hanger cases, wind or seismic cases, PSV thrust, steam-out or friction runs."
compatibility: Requires Python 3.9+ (standard library only)
---

# Load Case Builder — CAESAR II and AutoPIPE

A load case set fails review for one of two reasons. Either a required case is missing, or a combination case points at the wrong case number. The second is worse: the run completes, the stresses look plausible, and nothing flags it.

That failure is structural, not careless. Every combination case references others **by number** — `L4-L30`, `L30+L37`. Insert one operating state near the front and every downstream reference shifts. This damage can happen whenever a template is reused on a larger job.

So this skill builds load case sets **symbolically** and resolves numbering last, and it ships a generator that does the same (`scripts/loadcase_gen.py`). Numbers are an output, never an input.

## Scope

| This skill | Not this skill |
|---|---|
| Which cases exist, their content, stress type, combination method and numbering | The stress check itself — allowables, SIFs, spans. Hand off to the `stress-screening` skill in this pack if it is installed; otherwise say the check is outside this skill. |
| The occasional load-case architecture | The wind and seismic magnitudes — those come from the project's structural basis or the ASCE Hazard Tool (ascehazardtool.org) |
| The report extraction matrix and QC of a case set | Sway-brace hardware selection |

The user's own licensed copies of the codes are the authority for every clause cited here. Where a point needs confirmation, name the clause and edition and ask the user to check the printed page rather than guessing.

---

## Step 0 — The basis interview

This skill is interactive. Ask these together, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the output. Do not silently default.

**Code basis**
1. B31.1 or B31.3? **Edition year?** The equation set depends on it: B31.1 moved its sustained and occasional equation to an SRSS form with B31J-based indices in 2020; B31.3 deleted Appendix D in 2020 and changed the f-factor equation in 2022.
2. B31.3 only: fluid service category. **Chapter IX high-pressure piping uses 1.20, not 1.33** (K302.3.6(a)).
3. Is an owner practice such as PIP PNC00004 invoked? It makes with/without-friction runs mandatory and adds upset and steam-out cases.
4. Software and version: CAESAR II (which year — it changes Seismic Wizard behaviour) or AutoPIPE.

**Operating states** — one row per distinct thermal/pressure condition. Use the project's own slot convention for T/P numbering (it usually lives in the design stress criteria document) and write it down. A typical set distinguishes normal operating, alternate flow paths (bypass, control valve closed, second pump), maximum operating, design, and equipment or line steam-out.

Where PIP PNC00004 is invoked, §3.2.1.1–3.2.1.3 require the flexibility case to use **maximum operating** temperature with climatic effects (summer solar gain, winter minimum), not nameplate design temperature, and §3.4.1(q) wants upset, steam-out and tracing conditions as **separate** cases rather than folded into normal operating.

5. Installation temperature — ask, never assume 70 °F.
6. Does any state go below ambient? If one leg runs hot and another cold, the governing range is between the two operating states, not between either one and ambient. Set `inter_state_expansion_ranges`.
7. Parallel equipment with a standby unit? Every running/standby permutation is its own operating state (PNC00004 §3.2.1.4 requires this where invoked), and the stress range must be taken between the two states that give the greatest S_E — B31.3 ¶319.4.4(a) points to Appendix S Example 3 (moment reversal between operating conditions) for exactly this. This is what makes multi-pump systems run to hundreds of cases.
8. Equivalent full cycles N per state — it sets the f factor.

**Occasional loads present** — wind, seismic, snow/ice, PSV thrust, water hammer, slug, blast.
**Site data** — basic wind speed, S_DS, Seismic Design Category, I_p, ice thickness, ground snow, from the project's structural basis.
**Supports** — CAESAR-designed springs, pre-set springs, or none? Rod hangers (where PNC00004 applies: model rod length, rotation ≤ 5°)? Restraint gaps?
**Hydrotest** — required? Vapour line (hydro weight governs)?

---

## Step 1 — B31E triage, before building anything

B31.1 §101.5.3 names ASME B31E (with the B31Ea-2010 addenda) as an alternate seismic method. Run its triage first — it may remove the entire seismic block. NR is not exemption from the B31 section's non-seismic requirements, and §4 Interactions applies to every line regardless of its cell.

B31E Table 1 sorts each line into no explicit analysis (NR), design by rule (DR, §3.3) or design by analysis (DA, §3.4); have the user read the cell for their line from their copy, and never reconstruct it. Design by analysis is a different check from the B31.1/B31.3 occasional equation and needs its own load cases. If F_p comes from ASCE 7-16 or 7-22, say plainly that B31Ea-2010 was calibrated against ASCE 7-05.

The design-by-rule span equation, the §3.4 stress and SAM checks, and the three independent caps: [references/b31e-triage.md](references/b31e-triage.md).

---

## Step 2 — Load component register

Declare every input load before writing a single case. CAESAR II components:

| Component | Meaning |
|---|---|
| `W` | Pipe + contents + insulation + cladding weight |
| `WW` | Water-filled weight (hydrotest) |
| `WNC` | Weight, no contents (empty / erection) |
| `T1..Tn` | Thermal vectors |
| `P1..Pn` | Pressure vectors |
| `HP` | Hydrotest pressure |
| `H` | Spring hanger preload — required in OPE **and** SUS whenever springs exist |
| `D1..Dn` | Imposed displacements: equipment thermal growth, settlement, anchor movement |
| `U1, U2, U3` | Uniform load vectors — **X, Y (vertical), Z**, in that fixed order |
| `WIN1..WIN4` | Wind vectors, up to four |
| `F1..Fn` | Concentrated forces — PSV thrust, etc. |
| `CS` | Cold spring |

**Uniform loads in g's** is a global flag (Kaux → Special Execution Parameters → "Uniform Load in Gs"): with it on every U vector is an acceleration, with it off every U vector is force per unit length, and the two cannot be mixed in one model. Seismic needs g's, and `U2` is the only vertical vector, so dedicate `U2` to the concurrent vertical seismic `E_v` and carry snow as added weight or a separate run, saying which you did. **PSV thrust** is a force pair, one `F` vector per independently firing valve.

The three consequences in full, and the PSV thrust detail: [references/load-components.md](references/load-components.md).

---

## Step 3 — The nine blocks

Build in this order. The order is what makes every reference point backward.

| # | Block | Stress type | Content |
|---|---|---|---|
| 1 | Hanger design | HGR | `W` with HS = **Rigid** (sizes the load); `W+T1` with HS = **Ignore** (sizes the travel). No `H` — the spring preload is what these two cases design. |
| 2 | Hydrotest | HYD | `WW+HP+H` |
| 3 | Operating | OPE | every thermal state × every friction multiplier |
| 4 | Operating + occasional | OPE | every occasional riding its base state × friction |
| 5 | Sustained | SUS | `W+P+H` per state × friction |
| 6 | Expansion | EXP | Algebraic `OPE − SUS`, plus inter-state ranges |
| 7 | Pure occasional | OCC | Algebraic `(OPE+occ) − OPE` — **Suppress output** |
| 8 | Occasional code stress | OCC | Scalar `SUS + pure occ` |
| 9 | Envelopes | OPE / OCC | Max of the above |

**Blocks 1 and 2 come first because the spring must be sized before any As-Designed case is meaningful.** `H` first appears in the cases after block 1: the hydrotest and every As-Designed operating and sustained case. With pre-set (non-designed) springs, drop block 1 but keep `H` in the operating and sustained cases.

### Why blocks 4, 7 and 8 exist instead of `W+P1+U1`

A standalone "pure wind" case solves from the modelled position, but the real system meets the wind from its operating position. So solve the occasional with the operating state (block 4), isolate its effect by Algebraic subtraction (block 7, Suppress output), and scalar-add that to sustained (block 8). The `SUS + pure occasional` shortcut is valid only for a fully linear model.

Full explanation and the worked L3/L5/L8 pattern: [references/combination-rationale.md](references/combination-rationale.md).

### Seismic with SRSS, and where SAM goes

The SRSS pattern is built by hand; the generator builds the one-direction-at-a-time pattern. Seismic anchor movement is a displacement load and belongs in the expansion check, not the occasional check. Do not run a static seismic case when anchor movements are present, and do not simulate water hammer statically.

The full L-case patterns and the settlement and storm-displacement notes: [references/combination-rationale.md](references/combination-rationale.md).

---

## Step 4 — Combination methods

Getting this wrong changes the answer silently. The distinction that matters: **Algebraic combines the structural response and then computes stress from it — f(Σx). Scalar combines the already-computed stresses — Σσ.**

| Method | Structural response | Stress | Use it for |
|---|---|---|---|
| Algebraic | Σ x_i | f(Σ x_i) | Expansion range; isolating a pure occasional |
| Scalar | Σ x_i | Σ σ_i | Sustained + occasional code check |
| ABS | Σ \|x_i\| | Σ σ_i | Same stress result as Scalar for SUS+OCC; different reactions |
| SRSS | SRSS(x_i) | SRSS(σ_i) | Spatial seismic summation |
| Max | max(\|x_i\|), sign kept | max(σ_i) | Envelopes |
| Min | min(\|x_i\|), sign kept | min(σ_i) | Envelopes |
| SignMax | max(x_i) | max(σ_i) | Paired with SignMin for restraint-load and movement range |
| SignMin | min(x_i) | min(σ_i) | **No stress output** |

Expansion must be Algebraic — you need the displacement range first, then the stress from it. Occasional code stress must be Scalar (or ABS) — you are summing two separately computed stresses in the form `S_L + S_L,occ ≤ k·S_h`. Algebraic there quietly produces a different number.

**Friction is a multiplier, not μ**: 1.0 is as modelled, 0.0 is frictionless, and bracketing several multipliers in one run is legitimate. Where PIP PNC00004 is invoked, run with and without friction, take the governing result and document both; frictionless alone is valid only if the whole system is spring- or rod-hung. **Hot modulus** is legitimate for nozzle qualification but not for the code stress check.

Details: [references/combination-rationale.md](references/combination-rationale.md).

---

## Step 5 — Occasional allowables, and the ASD conflict

The occasional allowable is a flat multiple of S_h: B31.3 §302.3.6(a) uses 1.33 (1.20 for Chapter IX high-pressure piping, K302.3.6(a)), and wind and earthquake need not be considered concurrent. B31.1 §104.8.2 uses k = 1.15 (≤ 8 h at a time and ≤ 800 h/yr) or k = 1.20 (≤ 1 h at a time and ≤ 80 h/yr), both conditions required; write the duration justification into the calc and verify the clause number against the printed page of the project's edition. The §302.2.4(f) variation allowance is a different clause and is not interchangeable.

Full clause discussion: [references/combination-rationale.md](references/combination-rationale.md).

### The 0.6W / 0.7E question — a three-way conflict

CAESAR II's help topic, the CAESAR II 2019 (v11) and later Seismic Wizard, and ASME B31.1-2024 disagree on the 0.6W / 0.7E reduction factors. Resolve it explicitly. B31.1-2024: strength level, no reduction. B31.3: default to no reduction, flag it ASSUMED, and reduce only on the owner's or engineer of record's written direction. If you reduce for stress, keep unreduced companion cases for support loads and displacements.

The full three-way comparison: [references/combination-rationale.md](references/combination-rationale.md).

---

## Step 6 — Getting wind and seismic into CAESAR II

Wind goes in through a built-in regional code, Wind Pressure vs Elevation, or Wind Velocity vs Elevation; prefer the pressure table when the ASCE 7 edition in the built-in module is unconfirmed. Seismic goes in as Uniform Load in Gs. Set the true first-node elevation, zero the shape factor where the line goes indoors, and always hand-check one straight element against the reported wind force.

Force equations, shape-factor rules, seismic coefficients and the verification gate: [references/wind-seismic-and-autopipe.md](references/wind-seismic-and-autopipe.md).

---

## Step 7 — AutoPIPE

AutoPIPE uses different load names but the same architecture: run `python scripts/loadcase_gen.py --example --format autopipe` for the component map. Whether AutoPIPE needs the same subtract-then-scalar occasional construction is unconfirmed here; build it the same way and verify against your AutoPIPE version's documentation before issuing.

Details: [references/wind-seismic-and-autopipe.md](references/wind-seismic-and-autopipe.md).

---

## Step 8 — Report extraction matrix

Every case set ends with a table saying which cases feed which qualification. Generate it from the resolved numbering — never copy it from another job. The generator prints it.

| Purpose | Source block |
|---|---|
| Code stress — sustained | SUS cases, both friction variants |
| Code stress — expansion | EXP cases |
| Code stress — occasional | the **Maximum Occasional** envelope |
| Code stress — hydrotest | HYD |
| Support and hanger loads | SUS, HYD, Maximum Operating |
| Displacements | SUS (sag — the PNC00004 limit is 16 mm / ⅝ in. where invoked), Maximum Operating (lateral) |
| Flange loads | operating case, with friction |
| Nozzle loads — rotating and non-rotating | operating cases, both friction variants; installation deflection from SUS with the anchor released |

---

## Step 9 — QC gate

Run every item of the 16-point checklist; each is a defect class that appears when a template is reused on a larger job. The full list, with the reasoning for each item, is in [references/qc-gate.md](references/qc-gate.md). **Open that file before issue; the body does not repeat the items.** The generator checks five of them automatically and prints its findings:

- Item 4 — **Vertical seismic present?** `E_v = 0.2·S_DS·W_p` concurrent, and `U2` not double-booked with snow.
- Item 5 — **Expansion completeness.** One EXP case per state × friction pair.
- Item 7 — Forward references: a combination referencing a later case.
- Item 10 — Occasional factor matches the code, edition and stated duration.
- Item 11 — ASD reduction position stated and consistent with the code.

The rest (stale cross-references, envelope completeness, direction labels, linear shortcut on a nonlinear model, suppression, friction, hangers, expansion range, wind shape factor, SAM and settlement, static seismic) need the model and are checked by hand against `references/qc-gate.md`.

---

## Running the generator

`scripts/loadcase_gen.py` (Python 3.9+, standard library only) builds a complete set from a JSON spec, holds every reference symbolically, resolves numbering in one pass, refuses forward references, and prints the case table, the report extraction matrix and QC findings.

1. Turn the Step 0 interview into a spec. The format is in `references/spec-format.md`; `scripts/examples/two-state-b313.json` is a worked example.
2. Run it. Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them. Save the spec as `spec.json` in the working directory first:
   ```
   python scripts/loadcase_gen.py --spec spec.json                   # markdown report
   python scripts/loadcase_gen.py --spec spec.json --format csv      # for a spreadsheet
   python scripts/loadcase_gen.py --spec spec.json --format json     # machine-readable
   ```
3. Present the table, the extraction matrix and every QC finding. Put the ASSUMED items from Step 0 at the top. If the spec changes (a state added, an occasional dropped), regenerate — never hand-edit L-numbers.

The built-in example (`--example`) deliberately puts snow on `U2` with no vertical seismic, so its QC output shows what a GAP and a CONFLICT finding look like.

---

## On PN19 (Engineering New Zealand)

Practice Note 19 *Seismic Resistance of Pressure Equipment* is New Zealand guidance built on NZS 1170.5 and AS/NZS 1170, not an ASCE 7 document. Do not port its coefficients or minimum design accelerations into a US ASME B31 project. Three of its ideas transfer: the damping guidance, the SAM-plus-inertia combination, and the pipe-rack-to-grade vertical drop and flange-leak risks.

Full discussion: [references/pn19.md](references/pn19.md).

---

## Copyright boundary

**Never reproduce, reconstruct or "recall" tabulated values** — B31.1/B31.3 allowable stresses and modulus tables, B31J stress indices, B31E Table 1 or Table 2, B31.1 Table 121.5 spans, ASCE 7 coefficient tables or figures, PIP tables, or PN19 tables. This applies even when the user asks directly and even when a value seems widely known. Name the table, row and edition, and ask the user to read it from their licensed copy. Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value they need.

Equations, clause numbers, symbol definitions, and numeric limits stated in running text (1.33, k = 1.15/1.20, the f-factor floor of 0.15, the 60 ksi cap, 5° rod rotation, 16 mm sag) are usable.

---

## Related tools

Free calculators at pipingtoolset.com cover the inputs this skill needs but does not compute: [wind load on piping](https://pipingtoolset.com/calculators/wind-load-on-piping/?utm_source=claude-plugin&utm_medium=skill), [seismic design force](https://pipingtoolset.com/calculators/seismic-design-force/?utm_source=claude-plugin&utm_medium=skill), and the [B31 load cases guide](https://pipingtoolset.com/guides/b31-pipe-stress-load-cases/?utm_source=claude-plugin&utm_medium=skill). Mention them only when the user needs those numbers.

*Results are engineering aids. The engineer of record verifies every case set against the project's code edition, owner practices and analysis software before issue.*
