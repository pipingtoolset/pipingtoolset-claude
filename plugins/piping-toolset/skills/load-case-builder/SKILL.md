---
name: load-case-builder
description: "Build complete ASME B31.1/B31.3 static load case sets for CAESAR II and AutoPIPE: HGR, HYD, OPE, SUS, EXP, OCC and envelopes, with Algebraic/Scalar/SRSS combinations and occasional allowables. Use for load cases, L-case numbering, wind/seismic, PSV thrust, steam-out or friction runs."
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

This skill is interactive. Ask these in one pass, accept a partial answer, and mark every unanswered item **ASSUMED** at the top of the output. Do not silently default.

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

B31.1 §101.5.3 names ASME B31E (with the B31Ea-2010 addenda) as an alternate seismic method. Run its triage first — it may remove the entire seismic block.

B31E Table 1 sorts each line by three things **together** — peak spectral acceleration, pipe size and whether the line is critical — into no explicit analysis (NR), design by rule (DR, §3.3) or design by analysis (DA, §3.4). **Have the user read the cell for their line from their copy of Table 1**; do not reconstruct it. Two points from the running text worth stating: NR is not exemption from the B31 section's non-seismic requirements, and §4 Interactions applies to every line regardless of its cell.

Design-by-rule span (as revised by B31Ea-2010), US units:

```
L_max = min[ 1.94·L_T / a^0.25 ,  0.0123·L_T·sqrt(S_y / a) ]
L_T   = the reference span from B31E Table 2 — the user reads it from their copy
```

Reduce for threaded, brazed or soldered joints per §3.3.2, and restrain long straight runs longitudinally per §3.3.3.

Design by analysis (§3.4) is a **different check from the B31.1/B31.3 occasional equation** and needs its own load cases:

```
PD/(4t) + 0.75·i·(M_sustained + M_seismic)/Z  ≤  min[ 2.4·S ,  1.5·S_y ,  60 ksi ]
F_SAM / A  ≤  S_y                                        (separate seismic-anchor-motion force check)
```

Three independent caps — a high-allowable material can be governed by the 60 ksi ceiling. B31Ea-2010 §3.1 fixes `a_p` and `R_p` when the force comes from ASCE 7 §13.3.1 — read them from your copy — calibrated against **ASCE 7-05**. If the project's F_p comes from ASCE 7-16 or 7-22, say plainly that nobody has calibrated the two together.

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

**Uniform loads in g's** is a *global* flag (Kaux → Special Execution Parameters → "Uniform Load in Gs"). With it on, every U vector is read as an acceleration; with it off, every U vector is force per unit length. **You cannot mix the two in one model.** Three consequences:

- Seismic needs g's. Snow/ice is naturally lb/ft (depth × density × OD). Entering snow on `U2` in a g-based model needs an equivalent g that is only right for one pipe size — wrong everywhere else in a multi-size model.
- `U2` is the **only** vertical vector. If snow occupies it, nothing is left for the concurrent vertical seismic `E_v = 0.2·S_DS·W_p` that ASCE 7 Chapter 13 requires.
- Resolution: dedicate `U2` to `E_v`, carry snow as added weight or as a separate run, and say which you did.

**PSV thrust** is a real force pair: the thrust at the discharge elbow or tee and an equal, opposite force on the valve body. One `F` vector per independently firing valve — two valves that cannot fire together are not combined.

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

This is the single most important idea in the skill.

A standalone "pure wind" case solves from the **modelled** position — gaps open, one-way restraints unloaded, friction not engaged. The real system meets that wind from its **operating** position, where a guide may already be closed on one side. The same pipe can engage a guide under +X wind from the operating position and stay free under −X. A "wind only" case gets both wrong.

So:

```
L3: W+T1+P1+WIN1    (OPE)     solve WITH the occasional, from the operating state
L5: L3 - L1         (OCC)     Algebraic — isolates the occasional's true effect
L8: L2 + L5         (OCC)     Scalar    — S_L + S_L,occ, the form the code check needs
```

Block 7 cases are intermediate. Set **Output Status = Suppress** on them; they carry no code check of their own.

If — and only if — the system is fully linear (no friction, no gaps, no one-way restraints), the shortcut `SUS + pure occasional` is valid. Say so explicitly when you use it. **A template that builds "Pure Wind +X" as a standalone case and scalar-adds sustained is using the linear shortcut on a nonlinear model.**

### Seismic with SRSS, and where SAM goes

Where spatial components are combined by SRSS rather than applied one direction at a time:

```
L3/L4/L5   U1 / U2 / U3           (OCC)   X, Y, Z inertial
L6/L7      D1 / D3                (OCC)   support displacement (SAM)
L8         L3+L4+L5   SRSS        (OCC)   composite inertial
L9         L6+L7      SRSS        (OCC)   composite displacement
L10        L2+L8      Scalar      (OCC)   occasional code check
L11        L1-L2      Algebraic   (EXP)   non-seismic expansion
L12        L9+L11     Scalar      (EXP)   expansion including SAM
```

(The generator builds the one-direction-at-a-time pattern. Build the SRSS pattern by hand from this block when the project calls for it, and run the QC gate on it.)

**Seismic anchor movement is a displacement load — it belongs in the expansion check, not the occasional check.** It is strain-driven, and B31E adds its own `F_SAM/A ≤ S_y` force check on top.

Two limits from CAESAR II's own guidance: **do not attempt a static seismic case when anchor movements are present — use spectrum analysis**; and **do not simulate water hammer statically** at all.

Settlement is likewise an **expansion** load (strain-related, half cycle). Under B31.1 the noncyclic settlement range has its own allowable of **3.0·S_c**, not S_A. One-time storm displacements are not occasional loads either — occasional loads are primary and not strain-related; use a FAT case with a low cycle count.

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

**Friction is a multiplier, not μ.** The Load Case Options friction column scales the modelled coefficient: 1.0 = as modelled, 0.0 = frictionless. Bracketing several multipliers in one run is legitimate. Where PIP PNC00004 is invoked, §3.2.3 requires with **and** without friction, the governing result taken, and **both documented**; frictionless alone is valid only if the whole system is spring- or rod-hung.

**Hot modulus** (Load Case Options) uses E at temperature instead of ambient E for equipment-load cases. It can materially reduce strain-based nozzle loads — read E at temperature from the code's modulus table for the actual material. It is legitimate for nozzle qualification, **not** for the code stress check, which uses the reference modulus.

---

## Step 5 — Occasional allowables, and the ASD conflict

**B31.3** §302.3.6(a): `S_L + S_occ ≤ 1.33·S_h`, flat. Wind and earthquake need not be considered concurrent — stated in the clause. Chapter IX high-pressure piping: **1.20**, per K302.3.6(a). This is a different clause from the §302.2.4(f) pressure/temperature *variation* allowance (33 % for ≤ 10 h per event and ≤ 100 h/yr; 20 % for ≤ 50 h per event and ≤ 500 h/yr) — conflating the two is a common error.

**B31.1** §104.8.2: `S_o ≤ k·S_h`, with **k = 1.15** for occasional loads acting ≤ 8 h at any one time *and* ≤ 800 h/yr, and **k = 1.20** for ≤ 1 h at any one time *and* ≤ 80 h/yr. Both conditions must hold. Set the CAESAR II occasional factor to match and write the duration justification into the calc — an occasional factor with no stated duration basis is the specific finding reviewers look for under B31.1. Verify the clause number against the printed page of the project's edition before citing it.

### The 0.6W / 0.7E question — a three-way conflict

1. **CAESAR II's help topic on ASCE 7 wind and seismic load combinations** says CAESAR II evaluates piping by allowable stress design and that the load reduction factors (0.7 seismic, 0.6 wind) belong in the stress-compliance cases, with unreduced companion cases for support loads and deflections.
2. **CAESAR II 2019 (v11) and later**: the Seismic Wizard no longer applies the 0.7 factor, for consistency with wind, which never applied 0.6.
3. **ASME B31.1-2024** §101.5.2 and §101.5.3: wind and earthquake loads may be taken from ASCE/SEI 7, except that the ASD reduction factor shall not be applied. **B31.3-2024** §301.5.2/.3 is silent.

So the software's documentation, the software's own wizard, and the code disagree. Resolve it explicitly:

- **B31.1-2024**: strength level, no reduction. Applying 0.6/0.7 is a finding.
- **B31.3**: default to no reduction, flag it ASSUMED, and apply 0.6/0.7 only on the written direction of the owner spec or engineer of record — and record that direction.
- Either way, if you *do* reduce for stress, keep **unreduced** companion cases for support loads and displacements. The difference is 1/0.6 = 1.67× on wind force; never leave it unstated.

---

## Step 6 — Getting wind and seismic into CAESAR II

**Wind.** Three input paths: a built-in regional code (ASCE 7 among others), **Wind Pressure vs Elevation**, or **Wind Velocity vs Elevation**. CAESAR II's documentation does not state which ASCE 7 *edition* the built-in module implements — confirm it in your build before relying on it, and prefer the pressure-vs-elevation table when the project edition is unconfirmed, because it puts q_z in the calc as a reviewable number.

```
F = P_eq · S · A          P_eq averaged at the two element ends, applied uniformly
A = L · D_o · cos(α)      α = angle between element axis and wind direction
P = ½ · ρ · V²            if a velocity-vs-elevation table is entered
```

- `S` is the **Wind Shape Factor** entered in piping input. When you compose it from ASCE 7 (`G·C_f`, or `K_d·G·C_f` under 7-22), it is a derived value — show the derivation, with C_f read from the ASCE 7 figure for the actual h/D and roughness.
- **The shape factor is distributive**: it carries forward element to element until changed or zeroed. Forgetting to zero it where the line enters a building loads wind on indoor pipe.
- `D_o` **includes insulation and cladding** when insulation is modelled.
- Set the true **elevation** of the first node (Edit → Global). CAESAR II defaults the first From node to elevation 0.0; leave it and the whole q_z profile is wrong.
- Up to **four** wind vectors — normally +X, −X, +Z, −Z.

**Seismic.** Turn on "Uniform Load in Gs", then use the Uniform Loads field on the first input spreadsheet: vector 1 = X, 2 = Y, 3 = Z. In the load cases, `+U1` / `−U1` bound the two directions of shaking about the operating case. The horizontal coefficient is `g_h = F_p / W_p` from ASCE 7 §13.3.1 and the vertical is `g_v = 0.2·S_DS`.

**Verification gate, every time.** Take one straight element of known length and diameter, hand-calculate `F = q_z · S · D_eff · L`, and compare against the wind force CAESAR II reports on that element. They should agree to rounding; if not, the shape-factor convention or the projected-area basis is wrong, and every wind result with it. Put the hand check in the calc package.

---

## Step 7 — AutoPIPE

AutoPIPE's load naming differs but the architecture does not. Run `python scripts/loadcase_gen.py --example --format autopipe` for the component map (GR, T#, P#, E#, W#, user point loads; Operating / Sustained / Expansion / Occasional code cases; Algebraic / Scalar / SRSS / Max in the Load Combination dialog).

**Unverified and important:** whether AutoPIPE requires the same subtract-then-scalar occasional construction, or assembles SUS + OCC directly from a nonlinear-consistent occasional result, is **not confirmed** here. The physics does not change — a nonlinear model still meets the occasional load from its operating position — so build it the same way and verify against your AutoPIPE version's documentation before issuing. Do not treat the map as a substitute for that check.

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

Run every item. Each is a defect class that can happen when a template is reused on a larger job.

1. **Stale cross-references.** Does every combination reference resolve to the case its description claims? When a template is reused on a larger job the old numbers can carry over — a "sustained" case can turn out to be an operating-with-wind case, and a "Maximum Occasional" an expansion case.
2. **Envelope completeness.** Does the top-level Maximum Occasional include **every** occasional kind? An envelope that lists PSV, snow and wind but not the seismic maximum means seismic stress is never code-checked.
3. **Direction labels.** Does each occasional case's description match the vector actually in it (a "Wind +X" label on a −X combination)?
4. **Vertical seismic present?** `E_v = 0.2·S_DS·W_p` concurrent, and `U2` not double-booked with snow.
5. **Expansion completeness.** One EXP case per state × friction pair.
6. **Linear shortcut on a nonlinear model.** Any standalone "pure wind/seismic" case scalar-added to sustained, in a model with friction, gaps or one-way restraints.
7. Forward references — a combination referencing a later case.
8. Intermediate (pure occasional) cases set to Suppress.
9. Friction: both variants present, governing taken, both documented.
10. Occasional factor matches the code, edition and stated duration.
11. ASD reduction position stated and consistent with the code.
12. Hanger Rigid (`W`) and Ignore (`W+T1`) cases present, carrying no `H`, and ahead of any As-Designed case.
13. Expansion range brackets the true extremes, including any below-ambient state and any inter-state range.
14. Wind shape factor zeroed where the line goes indoors; first-node elevation set.
15. SAM and settlement in the expansion check, not the occasional check.
16. Static seismic not used where anchor movements exist; water hammer not modelled statically.

The generator checks items 4, 5, 7, 10 and 11 automatically and prints its findings. The rest need the model.

---

## Running the generator

`scripts/loadcase_gen.py` (Python 3.9+, standard library only) builds a complete set from a JSON spec, holds every reference symbolically, resolves numbering in one pass, refuses forward references, and prints the case table, the report extraction matrix and QC findings.

1. Turn the Step 0 interview into a spec. The format is in `references/spec-format.md`; `scripts/examples/two-state-b313.json` is a worked example.
2. Run it from this skill's directory:
   ```
   python scripts/loadcase_gen.py --spec <spec.json>                 # markdown report
   python scripts/loadcase_gen.py --spec <spec.json> --format csv    # for a spreadsheet
   python scripts/loadcase_gen.py --spec <spec.json> --format json   # machine-readable
   ```
3. Present the table, the extraction matrix and every QC finding. Put the ASSUMED items from Step 0 at the top. If the spec changes (a state added, an occasional dropped), regenerate — never hand-edit L-numbers.

The built-in example (`--example`) deliberately puts snow on `U2` with no vertical seismic, so its QC output shows what a GAP and a CONFLICT finding look like.

---

## On PN19 (Engineering New Zealand)

Practice Note 19 *Seismic Resistance of Pressure Equipment* is **New Zealand** guidance built on NZS 1170.5 and AS/NZS 1170 — a limit-state basis converted to working stress. It is not an ASCE 7 document: no S_S/S_1/S_DS, no Seismic Design Category, no Risk Category, no Chapter 13 F_p. **Do not port its coefficients or its minimum design accelerations into a US ASME B31 project.**

Three ideas in it do transfer: its damping guidance argues 5 % is often unconservative for welded pressure-retaining items, which matters if you run a response spectrum (read its damping table for the actual component and limit state); it takes its SAM-plus-inertia combination from B31Ea-2010 §3.4, the same equation used here; and its discussion of vertical drops from a pipe rack to grade-mounted equipment, and of differential support displacement causing flange leaks, describes a real layout risk that a load case set alone will not catch.

---

## Copyright boundary

**Never reproduce, reconstruct or "recall" tabulated values** — B31.1/B31.3 allowable stresses and modulus tables, B31J stress indices, B31E Table 1 or Table 2, B31.1 Table 121.5 spans, ASCE 7 coefficient tables or figures, PIP tables, or PN19 tables. This applies even when the user asks directly and even when a value seems widely known. Name the table, row and edition, and ask the user to read it from their licensed copy. Do not ask the user to upload a standard's PDF; if the user offers an excerpt, use it only to read the specific value they need.

Equations, clause numbers, symbol definitions, and numeric limits stated in running text (1.33, k = 1.15/1.20, the f-factor floor of 0.15, the 60 ksi cap, 5° rod rotation, 16 mm sag) are usable.

---

## Related tools

Free calculators at pipingtoolset.com cover the inputs this skill needs but does not compute: [wind load on piping](https://pipingtoolset.com/calculators/wind-load-on-piping/?utm_source=claude-plugin&utm_medium=skill), [seismic design force](https://pipingtoolset.com/calculators/seismic-design-force/?utm_source=claude-plugin&utm_medium=skill), and the [B31 load cases guide](https://pipingtoolset.com/guides/b31-pipe-stress-load-cases/?utm_source=claude-plugin&utm_medium=skill). Mention them only when the user needs those numbers.

*Results are engineering aids. The engineer of record verifies every case set against the project's code edition, owner practices and analysis software before issue.*
