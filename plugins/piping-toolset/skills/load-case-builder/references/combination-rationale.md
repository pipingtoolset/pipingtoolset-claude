# Combination rationale

Relocated verbatim from the load-case-builder SKILL.md (Steps 3 and 5).

## Why blocks 4, 7 and 8 exist instead of `W+P1+U1`

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

## Seismic with SRSS, and where SAM goes

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

## The 0.6W / 0.7E question — a three-way conflict

1. **CAESAR II's help topic on ASCE 7 wind and seismic load combinations** says CAESAR II evaluates piping by allowable stress design and that the load reduction factors (0.7 seismic, 0.6 wind) belong in the stress-compliance cases, with unreduced companion cases for support loads and deflections.
2. **CAESAR II 2019 (v11) and later**: the Seismic Wizard no longer applies the 0.7 factor, for consistency with wind, which never applied 0.6.
3. **ASME B31.1-2024** §101.5.2 and §101.5.3: wind and earthquake loads may be taken from ASCE/SEI 7, except that the ASD reduction factor shall not be applied. **B31.3-2024** §301.5.2/.3 is silent.

So the software's documentation, the software's own wizard, and the code disagree. Resolve it explicitly:

- **B31.1-2024**: strength level, no reduction. Applying 0.6/0.7 is a finding.
- **B31.3**: default to no reduction, flag it ASSUMED, and apply 0.6/0.7 only on the written direction of the owner spec or engineer of record — and record that direction.
- Either way, if you *do* reduce for stress, keep **unreduced** companion cases for support loads and displacements. The difference is 1/0.6 = 1.67× on wind force; never leave it unstated.

## Occasional allowables (Step 5)

**B31.3** §302.3.6(a): `S_L + S_occ ≤ 1.33·S_h`, flat. Wind and earthquake need not be considered concurrent — stated in the clause. Chapter IX high-pressure piping: **1.20**, per K302.3.6(a). This is a different clause from the §302.2.4(f) pressure/temperature *variation* allowance (33 % for ≤ 10 h per event and ≤ 100 h/yr; 20 % for ≤ 50 h per event and ≤ 500 h/yr) — conflating the two is a common error.

**B31.1** §104.8.2: `S_o ≤ k·S_h`, with **k = 1.15** for occasional loads acting ≤ 8 h at any one time *and* ≤ 800 h/yr, and **k = 1.20** for ≤ 1 h at any one time *and* ≤ 80 h/yr. Both conditions must hold. Set the CAESAR II occasional factor to match and write the duration justification into the calc — an occasional factor with no stated duration basis is the specific finding reviewers look for under B31.1. Verify the clause number against the printed page of the project's edition before citing it.

## Friction and hot modulus (Step 4)

**Friction is a multiplier, not μ.** The Load Case Options friction column scales the modelled coefficient: 1.0 = as modelled, 0.0 = frictionless. Bracketing several multipliers in one run is legitimate. Where PIP PNC00004 is invoked, §3.2.3 requires with **and** without friction, the governing result taken, and **both documented**; frictionless alone is valid only if the whole system is spring- or rod-hung.

**Hot modulus** (Load Case Options) uses E at temperature instead of ambient E for equipment-load cases. It can materially reduce strain-based nozzle loads — read E at temperature from the code's modulus table for the actual material. It is legitimate for nozzle qualification, **not** for the code stress check, which uses the reference modulus.

## Report extraction matrix

Relocated verbatim from the load-case-builder SKILL.md (Step 8). Every case set ends with a table saying which cases feed which qualification. Generate it from the resolved numbering, never from another job; the generator prints it.

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
