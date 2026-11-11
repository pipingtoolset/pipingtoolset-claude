# Getting wind and seismic into CAESAR II, and AutoPIPE notes

Relocated verbatim from the load-case-builder SKILL.md (Steps 6 and 7).

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

## Step 7 — AutoPIPE

AutoPIPE's load naming differs but the architecture does not. Run `python scripts/loadcase_gen.py --example --format autopipe` for the component map (GR, T#, P#, E#, W#, user point loads; Operating / Sustained / Expansion / Occasional code cases; Algebraic / Scalar / SRSS / Max in the Load Combination dialog).

**Unverified and important:** whether AutoPIPE requires the same subtract-then-scalar occasional construction, or assembles SUS + OCC directly from a nonlinear-consistent occasional result, is **not confirmed** here. The physics does not change — a nonlinear model still meets the occasional load from its operating position — so build it the same way and verify against your AutoPIPE version's documentation before issuing. Do not treat the map as a substitute for that check.
