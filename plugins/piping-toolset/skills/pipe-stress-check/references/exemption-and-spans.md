# Formal-analysis exemption and support spans - full detail

Relocated verbatim from `SKILL.md` (Step 6 and Step 7). The body of `SKILL.md` carries the rules in summary; this file holds the exemption caveats and the span equations and end-condition table.

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
