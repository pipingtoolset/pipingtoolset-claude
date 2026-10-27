# Method ladder - why the screen comes first, and the clause map

The order of the ladder is fixed. Each rung answers a different question, and none of them replaces the next.

## Why the pressure-equivalent screen runs first

1. It needs almost nothing: the load, the design pressure, the gasket reaction diameter G and the rating the user already holds. It can be run at the first review of a restraint summary, before the flange is fully specified.
2. It is conservative, so a pass is informative. A pass says the loads are small enough that the joint can be reported as passing the screen; the detailed analysis is optional unless the owner requires it.
3. A failure is not a verdict. The screen converts the moment to an equivalent axial pressure load. The detailed analysis then asks the questions the screen cannot: bolt area, gasket seating, flange stress and rigidity.
4. It is always reported, even when the detailed analysis is also run. A reviewer who sees only the detailed result cannot tell whether the quick check was skipped.

## The rungs

| Rung | Question it answers | What a pass proves | What it does not prove |
|---|---|---|---|
| 1. Pressure-equivalent screen (`connections.flange-equivalent-pressure`) | Is the combined load, expressed as a pressure, within the flange rating (or the owner's percentage of it)? | The loads are within a conservative envelope of the rating basis | Bolt stress, gasket seating, flange stress, rigidity, creep relaxation, assembly bolt load. It is not a stress check |
| 2. Detailed VIII-2 4.16 analysis (`aux.app2-flange-integral`) | Do the bolts, hub, ring and rigidity hold at design pressure plus the equivalent external load, in both the operating and the seating case? | Bolt area adequacy and flange stresses against allowables under a pressure-equivalent treatment of the external loads | That the pressure-equivalent treatment is the Code's own external-moment treatment (it is not); fatigue; leakage rate of a specific gasket |
| 3. Interaction methods (named, not computed) | Is the joint acceptable by a published criterion for standard flanges (UG-44(b) / 4.16.12, NC-3658.3) or by a different model (EN 1591-1)? | Per the method's own conditions | Anything outside those conditions |

## The screen, derived

The moment M on a gasket circle of diameter G is replaced by an axial force 4M/G acting at the gasket circle. Adding the axial force F and dividing by the area enclosed by the gasket circle, pi G^2 / 4:

```
Pe = P + 4 (F + 4|M|/G) / (pi G^2)  =  P + 16|M|/(pi G^3) + 4F/(pi G^2)
```

- M is a magnitude. Its sign is an artefact of the analysis frame and can never relieve the joint.
- F is signed, tension positive. VIII-2 4.16.13 defines FA as the external tensile net-section force and neglects a compressive net-section force (FA = 0). The screen therefore uses F = max(F, 0) unless the owner agrees to credit compression (`creditCompression` true, which still draws a warning); if compression is credited, run the tensile case separately and report both. For the detailed analysis, run `aux.app2-flange-integral` with `Fax` set to max(F, 0) on the same rule, and say which was done.
- Pe is compared with the rated pressure the user read at design temperature (B16.5 2.4: the rating temperature is the temperature of the pressure-containing shell). PIP PNC00004 3.2.10.2 allows the equivalent pressure method or other methods the owner approves; 3.2.10.3 leaves acceptance to the owner's requirements.

## Clause map

Clause text is paraphrased from the printed standards; confirm each point on the user's copy. Items marked **confirm on the printed page** are ones where the equation or table body could not be verified here: the user checks them on the printed page.

### ASME B31.3

| Clause | What it says | Role here |
|---|---|---|
| 304.5.1(a) | Flanges not in accordance with 303 or 304.5.1(b) or (d) are qualified per 304.7.2 | Out of scope: unlisted designs |
| 304.5.1(b) | A flange may be designed to VIII-1 Mandatory Appendix 2 or VIII-2 4.16 using this Code's allowable stresses and temperature limits. Nomenclature as Appendix 2 except P is the design gage pressure, Sa the bolt design stress at atmospheric temperature, Sb the bolt design stress at design temperature, and Sf the product S times E times W for the flange or pipe material | The route Step 3 follows. Sf and Sn are therefore the B31.3 product S x E x W, with the table lines cited |
| 304.5.1(c) | The rules in (b) do not apply where the gasket extends outside the bolts (usually to the flange OD) | Full-face gaskets are out of scope |
| 304.5.1(d) | For flanges making solid contact outside the bolts, VIII-1 Appendix Y should be used | Out of scope |
| 304.5.1(e) | See VIII-1 Appendix S for bolted joint assembly considerations | Pointer for assembly |
| 308.1 to 308.4 | Listed flanges and gaskets; slip-on rules; welding neck for severe cyclic conditions (308.2.4); facing compatible with gasket and bolting; gasket seating load compatible with flange rating, facing, flange strength and bolting (308.4, see F308.4) | Context for selection and for the seating case |
| 309 | Bolting, see F309 | Bolt material and tightening |
| Appendix F, F312.1(a)(2) | UG-44(b) is one acceptable method for qualifying external piping loads on welding neck flanges to B16.5 or B16.47. Nomenclature as UG-44(b) except PD is the maximum operating pressure at operating temperature for the condition analyzed and PR the flange pressure rating at design temperature | The accepted interaction method; named in Step 4, not computed |

### ASME B31.1

| Clause | What it says | Role here |
|---|---|---|
| 104.5.1(a) | Flanges NPS 24 and smaller to B16.1 and B16.5 are suitable at primary service ratings, except B16.5 slip-on flanges, limited to no higher than the Class 300 primary service rating (see 127.4.4). The unlettered text that continues 104.5.1(a) gives the design rule for flanges not made to the Table 126.1-1 standards: design to Section VIII, Division 1, with P the B31.1 design pressure and Sa, Sb and Sf redefined as B31.1 allowables (Sa and Sb from Mandatory Appendix A, Table A-10; Sf the allowable stress of the flange material or pipe from the Appendix A allowable stress tables, see 102.3.1) | Rating basis, and the B31.1 route for Step 3. B31.1 names Section VIII Division 1 only, not VIII-2. VIII-1 Appendix 2 in the 2025 edition points to VIII-2 4.16 for its deleted paragraphs, so the user confirms with their B31.1 edition which edition of VIII-1 it references before applying 4.16. Paraphrased: confirm the paragraph split on the printed page |
| 104.5.1(b) | The flange design rule above does not apply to full-face gaskets (the exclusion) | Full-face gaskets are out of scope |
| 104.5.1(c) | Bolting per 108.5 | Bolt material and tightening |
| 108.1 | Sends flanges to 104.5.1 or the Table 126.1-1 standards | Selection context |

### ASME B16.5

| Clause | What it says | Role here |
|---|---|---|
| 2.1 | Pressure-temperature ratings are the maximum allowable working gage pressures at temperature; linear interpolation for intermediate temperatures is permitted, none between class designations | Where the rated pressure comes from |
| 2.2, 2.3.1 | A flanged joint is flanges, gasket and bolting acting together; ratings apply to joints meeting the bolting and gasket limits and made up with good alignment and assembly practice (controlled tightening per PCC-1) | The rating is conditional on assembly |
| 2.3.2 | Mixed joints: the joint rating is the lower of the two flange ratings at that temperature | Use the lower rating |
| 2.4 | Rating temperature is the temperature of the pressure-containing shell; below 38 C (100 F) the rating is no greater than the 38 C rating | Design metal temperature, not fluid temperature |
| 2.5.1 to 2.5.3 | Advisory notes on leakage from piping forces and moments at high and low temperature. 2.5.2: above 200 C (400 F) for Class 150 and above 400 C (750 F) for other classes, joints may leak unless severe external loads and thermal gradients are avoided | Flag in the findings when the design temperature is in that range |

### ASME BPVC Section VIII

| Clause | What it says | Role here |
|---|---|---|
| VIII-1 (2025) Appendix 2 | Revised in its entirety. Paragraphs 2-3 and 2-5 to 2-14 are deleted and mapped by Table 2-1-1 to VIII-2 Part 4.16 (2-5 to 4.16.2 and 4.16.6, 2-6 to 2-8 and 2-11 to 4.16.7, 2-14 to 4.16.7 and Table 4.16.10). 2-4 and 2-15 are retained | Cite 4.16 |
| VIII-2 4.16.3.1 | Flange types: integral, welded slip-on, loose, reverse | The tool covers integral (with hub) and loose (no hub) |
| VIII-2 4.16.5 and Table 4.16.1 | Gasket factors m and y are suggested values that have generally proved satisfactory; they are not mandatory and other values may be used if based on testing or literature and agreed (4.16.5.1) | m and y need a table line and the agreement, if any |
| VIII-2 4.16.6 | Design bolt loads in five steps: design P and T; select the gasket and take m and y; set N, b0, b, G; operating bolt load; gasket seating bolt load. Ab must be at least Am. Equations are numbered 4.16.1 to 4.16.9. Equation bodies, and exactly which number is which of Wo, Wg and Am: confirm on the printed page | Verify the equations on the printed page |
| VIII-2 4.16.7 | Flange design procedure, Steps 5 to 10: flange forces (Eq. 4.16.10 to 4.16.13), operating moment (4.16.14 or 4.16.15), the moment Moe by Eq. 4.16.16 using Table 4.16.7, moment arms from Table 4.16.6, gasket seating moment (4.16.17 or 4.16.18), stresses from Table 4.16.8, acceptance from Table 4.16.9, rigidity from Table 4.16.10. The shear check on lap-joint shear and welds is limited to 0.8 of the neck or pipe allowable. Confirm all of these equation and table bodies on the printed page | Verify on the printed page. The tool's external-load treatment is not the Code's Moe term |
| VIII-2 Table 4.16.4, 4.16.5 | Terms involving K = A/B; stress factors F, V, f (integral) and FL, VL (loose with hub). Confirm the equations on the printed page. The retired figures for F, V, FL, VL and f all map to Table 4.16.5 | Hub-factor source; see `references/app2-engine.md` |
| VIII-2 Table 4.16.10 | Rigidity criterion; general notes give KR (KI) 0.3 for integral and 0.2 for loose flanges unless the user specifies otherwise. Uses moments without the bolt-spacing correction | Rigidity J |
| VIII-2 Table 4.16.11 | Bolt spacing equations; the correction is applied when specified by the user or designated agent | Bsc option |
| VIII-2 4.16.12 | External forces and moments on standard welding-neck flanges: (a) design pressure within the rating, (b) assembly bolt load per PCC-1 Appendix O, (c) bolting at least SA-193 B8 Cl. 2, (d) the interaction equation (Eq. 4.16.19, confirm on the printed page) | Named in Step 4 |
| VIII-2 4.16.13 | Nomenclature. FA is the external tensile net-section force; a compressive net-section force is neglected (FA = 0). The allowables are written Sbg, Sbo (bolt), Sfg, Sfo (flange), Sng, Sno (neck or pipe) at gasket seating (g) and design (o) temperature. Sa, Sb, Sf and Sn are not defined under those names there | Mapping below |
| VIII-1 UG-44(b) | External loads on welding neck flanges: (1) MAWP corrected for static head within the rating at design temperature; (2) assembly bolt load per PCC-1 Appendix O; (3) bolting at least SA-193 B8 Cl. 2 at the size and temperature; (4) an interaction among corrected pressure, external moment and external axial force. The interaction equation: confirm on the printed page. Table UG-44-1 gives the moment factor FM by size range and class | Named in Step 4 |

Symbol mapping used by the tool: Sa is Sbg, Sb is Sbo, SfAmbient is Sfg, Sf is Sfo, SnAmbient is Sng, Sn is Sno. B31.3 304.5.1(b) uses the names Sa, Sb and Sf.

### Other documents

| Document | What it says | Role here |
|---|---|---|
| ASME III NC-3658 | NC-3658.1 any flanged joint: analyze per Section III Appendix XI or XIII, or satisfy the rated-pressure comparison with an equivalent pressure. NC-3658.2 standard flanges at moderate pressure and temperature (B16.5, B16.47, AWWA C207 Class E). NC-3658.3 B16.5 flanges with bolting of S at least 20,000 psi at 100 F: Level A pressure not above the rated pressure, Level B not above 1.1 times, Level C not above 1.5 times, with moment limits that carry yield-strength ratios of the Sy/36,000 form capped at 1. The moment equations: confirm on the printed page | Named in Step 4 for owners who invoke it |
| PCC-1 Appendix O | Section titles: simple approach, joint component approach (with a spiral-wound approach for B16.20 gaskets), determining flange limits | Assembly bolt stress; supports the UG-44(b) route |
| PIP PNC00004 3.2.10 | 3.2.10.1 external bending moments on flanges shall be considered. 3.2.10.2 external loads may be analyzed by the equivalent pressure method or other methods the owner approves. 3.2.10.3 acceptance criteria per the owner's requirements | The owner sets the acceptance value |
| EN 1591-1 | European flange joint calculation | Named, not computed |
