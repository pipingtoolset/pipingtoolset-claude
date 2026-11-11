# B31E triage detail

Relocated verbatim from the load-case-builder SKILL.md (Step 1).

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
