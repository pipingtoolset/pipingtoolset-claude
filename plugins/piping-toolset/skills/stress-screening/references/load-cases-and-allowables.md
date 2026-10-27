# Load cases and allowable range - full detail

Relocated verbatim from `SKILL.md` (Step 2 and Step 4). The body of `SKILL.md` carries the rules in summary; this file holds the equations, the occasional-allowable table and the f-factor detail.

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

Use the **sustained** stress index, not the expansion SIF, and the section basis for the code (see 'Section properties for the sustained check' at the end of this file). Which factor multiplies the sustained moment is edition-specific (a 0.75·i form in earlier editions, B31J-derived sustained indices in the 2024 editions): read the printed equation for the edition and enter the resulting `S_b` — the tool takes `S_b` and `S_t` already computed.

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

## Section properties for the sustained check (from Step 0)

Section properties for the sustained check are code-specific. **B31.3** (¶320.1): section modulus uses nominal wall less all allowances (mechanical, corrosion, erosion); the area for axial and pressure terms deducts only the allowances that affect the inside diameter; weight uses nominal wall. **B31.1** (¶104.8.1): nominal section modulus and nominal wall, no corrosion deduction. State which basis you used — mixing them silently is a finding.
