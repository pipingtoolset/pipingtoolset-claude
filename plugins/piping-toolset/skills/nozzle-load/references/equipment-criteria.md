# Equipment criteria - clauses, conditions and vendor confirmations

One section per equipment family. Each gives the clauses, what the table supplies (the user reads it), the conditions of use, the resolution point and what the vendor must confirm. Clause numbers are paraphrased from the user's licensed copies; confirm them on the printed page of the edition on record. Items marked **image** were read from a figure or an equation whose layout could not be recovered as text: the user verifies them on the printed page before they go on a sealed sheet.

No table value appears in this file. Equations and the numeric constants in running text of an equation are cited as such.

---

## 1. Centrifugal pumps - API 610

**What the table gives.** Table 5a (USC) and 5b (SI): for each nozzle size, six component limits (three forces, three moments) and resultant columns. The user reads the row for the nozzle size, and the casing material column if the table splits by material. The skill's tool derives the resultants from the components as the square root of the sum of the squares, as Annex F does for the applied side.

**1x and 2x.** Table 5 at 1x is the piping allowable. Annex F permits loads above it only with conditions and the purchaser's approval, and it does not remove the 2x margin between external nozzle loads and the pump casing's design limits (6.5.6, 6.5.6.1). The vendor directs how Annex F applies to the system (6.5.6.2). Never describe 2x Table 5 as an allowable the piping engineer can design to, except under the clause that follows. Exception, API 610 6.5.3: for OH3 / OH6 vertical in-line pumps whose supports are not anchored to the foundation, 6.5.3 permits 2x Table 5 on the side nozzles; F.2 then governs loads beyond that. Confirm the support condition and the vendor datasheet.

**Annex F, horizontal pumps (F.1).**

| Clause | Content |
|---|---|
| F.1.1 | Loads within Table 5 limit casing distortion to the fraction of the vendor design criterion stated there (6.2.4) and keep shaft displacement under the limit stated there |
| F.1.2 a) | Each component force and moment at each nozzle flange does not exceed the Table 5 range by more than the multiplier of F.1.2 a). Displacement limit under F.1.2: the value stated there |
| F.1.2 b), Eq. F.1, F.2 | Suction: `FRSA/(d·FRST4) + MRSA/(d·MRST4) < L`, with `d` the resultant denominator and `L` the sum limit of Eq. F.1. Discharge: the same with D and Eq. F.2. FRSA is the resultant of the applied suction components; FRST4 comes from Table 5 at the suction size |
| F.1.2 c), Eq. F.3 to F.5 | Loads resolved to the pump centre C: `FRCA < kF(FRST4 + FRDT4)`, `MYCA < kM(MYST4 + MYDT4)`, `MRCA < kF(MRST4 + MRDT4)`, with `kF` the factor of Eq. F.3 / F.5 and `kM` the factor of Eq. F.4 |
| F.3.1, F.5.1 | Resolution arithmetic: `FXCA = FXSA + FXDA` and so on; the moment terms add the force-times-arm contributions, with a constant of 12 in USC (in to ft) and 1000 in SI (mm to m) |
| F.1.3 | Loads beyond F.1.2 need purchaser and vendor approval; check actual distortion by the alignment checks of API 686 Chapter 6, which allow only a small fraction of what Annex F permits |

The sign convention and the pump-type centre definitions are in Figures 23 to 27 (**image**; not verified here). The user supplies nozzle coordinates relative to C in those axes.

**Method constants are inputs.** `d`, `L`, `kF`, `kM` and the multiplier of F.1.2 a) are the tool's `resultantDenominator`, `interactionLimit`, `centreForceFactor`, `centreMyFactor` and `componentMultiple`. The user reads each from its equation in the edition of record and enters it in the `annexF` block; the skill and the script carry no default, so a run without them stops. Record the equation number and the edition beside each value in the calc sheet.

**Annex F, vertical in-line pumps (F.2).** Pumps supported only by the attached piping (OH3, OH6) may take component loads above the multiplier of F.1.2 a) times Table 5 if the principal stress at either nozzle is within the principal-stress limit of F.6 (SI) or F.9 (USC). Section properties come from Schedule 40 pipe of the nominal nozzle size, which the user reads from the pipe dimension standard. Principal stress follows Eq. F.6 to F.8 (SI) or F.9 to F.11 (USC): a longitudinal stress from the axial force and the bending resultant, a shear stress from the transverse force and the torsion, and the principal stress from the two. Axial force positive is tension; use the absolute torsional moment in the shear term. The tool takes the limit (`sigmaPLimit`) and the two stress coefficients of F.7 / F.8 (SI) or F.10 / F.11 (USC) (`kSigma`, `kTau`) as inputs, in the `units` system given; the user reads them from the printed equations, which also settles the stress symbols (**image** risk: some were reconstructed from text, so verify on the printed page).

**Conditions.** Table 5 covers steel casings and nozzles within its size range; a non-steel casing or nozzles above NPS 24 need vendor allowables. Annex F use needs the purchaser's approval.

**Resolution point.** The intersection of the shaft centreline and the casing transverse centreline (PIP RECE002 4.1.2.3 agrees), with the individual nozzle limits also satisfied.

**Vendor confirms.** Table 5 values for the actual nozzle size, rating and casing material; whether Annex F is accepted and for which pump; the support condition for a vertical in-line pump; the nozzle coordinates relative to C; any lower limit stated on the datasheet.

---

## 2. Compressors, steam turbines and the NEMA SM-23 form

All three standards share a combined form for each connection, and the tool carries it as `connections.nema-sm23` with the coefficient a required input.

| Standard | Per-connection equation (USC) | Coefficient |
|---|---|---|
| API 617 Part 2, Annex E (E.1b) | `3·Fr + Mr ≤ a·De` | read `a` from E.1b |
| API 611 Annex I (I.1b) steam turbines | `3·FR + MR ≤ a·De` | read `a` from I.1b |
| API 612 Annex D (D.1b) steam turbines | `3·FR + MR ≤ a·De` | read `a` from D.1b |
| NEMA SM-23, legacy form | same shape; coefficient from the owner's copy | read it |

Forces in lbf, moments in ft-lbf, `De` in inches. `Fr = sqrt(Fx² + Fy² + Fz²)` and `Mr = sqrt(Mx² + My² + Mz²)` (E.2, E.3; I.3, I.4; D.3, D.4). `De` equals the nominal size for connections up to NPS 8 and, above that, `(NPS + 16)/3`; the printed layout of this equation is partly **image** in some editions, and the tool's value for a 12 in nozzle (9.333) is the check. The SI forms carry different coefficients and a different arrangement of the terms; the tool does not convert, so run SM-23 in USC only.

**Applies to** each connection of the machine. API 617 Annex E covers the inlet, side stream and discharge connections of cast axially or radially split centrifugal compressors and overhung single-stage compressors with inlet pressure above 50 psig (E.1). Extraction and exhaust connections belong to the steam turbine standards, API 611 Annex I and API 612 Annex D. For low-pressure machinery (axial, low-pressure overhung, open-impeller) the vendor states the limits (E.1.2). The limits apply to the machine structure, not to the connecting pipe, flange or bolting.

**Second criterion the tool does not compute.** Each standard also gives a combined resultant at one resolution connection: API 617 E.5, a combined-resultant equation in Fc and Mc against a coefficient times Dc (USC and SI forms), resolved at the largest connection, with Dc the diameter of one circular opening of the same total area as the inlet, side stream and discharge openings, and a different expression for Dc above a threshold equivalent diameter (E.6a, E.6b), and component limits for Fc and Mc; API 611 I.5 and API 612 D.5, the same kind of equation, resolved at the exhaust connection (I.6, I.7; D.6, D.7). The user reads the coefficients and thresholds from the printed equations. For a condensing turbine with a vertical-down exhaust and an unrestrained expansion joint, the vertical force component is added and a pressure load is allowed on top (I.1.1.3, D.1.1.3). Treat all of these as **vendor-sheet items the user confirms**; state them in the findings with the clause and the outcome the vendor reports. The 1.85x and 3x multipliers some datasheets quote are the same kind of item: record what the vendor sheet says and do not apply a multiplier on the engineer's own authority.

API 617 Part 2 Annex E was checked on the printed page (9th edition). **Items to verify on the printed page** for the turbine standards: the equivalent-diameter constants in API 611 Annex I and API 612 Annex D, the API 612 coefficient against the one its worked examples use, and the wording of the API 612 `De` definition for sizes up to NPS 8.

**Resolution points** (PIP RECE002 4.1.2): steam turbines at the exhaust flange; compressors at the fixed end, or the largest nozzle if no nozzle is at the fixed end (the fixed end is usually both the suction end and the largest nozzle); pumps as in section 1.

**Vendor confirms.** The standard and edition the machine was built to, the coefficient and any multiplier on the datasheet, the resolution connection, the vertical-down exhaust allowance, and limits for machines the annex excludes.

---

## 3. Shell-and-tube exchangers - API 660

**What the table gives.** Table 2: allowable forces and moments by nozzle size, with the axes and signs of Figure 4 (7.6.9). The user reads the row and the figure.

**Conditions.** Each nozzle must withstand the simultaneous application of the forces and moments **in the corroded condition**. Non-piped auxiliary connections (vents, drains, cleaning connections) are excluded. The type of analysis is specified or agreed with the purchaser. For sizes above those in Table 2 the purchaser specifies the loads (7.6.10); no value is available to use.

**Method.** `connections.nozzle-load-check` per nozzle with the Table 2 row as the allowable.

**Vendor confirms.** The corroded condition used, the axes (Figure 4), purchaser-specified loads for large nozzles, and any exchanger-specific limit on the datasheet.

---

## 4. Air-cooled exchangers - API 661

| Clause | Content | Method |
|---|---|---|
| 7.1.10.1 | Each nozzle in its design corroded condition withstands the simultaneous loads of Figure 6 and Table 4, by nozzle size | `connections.nozzle-load-check` |
| 7.1.10.2 | The summed components of all nozzle loadings on one header must not exceed the limits printed in the clause, for all six components | `equipment.nozzle-load-sum`, limits read by the user |
| 7.1.10.3 | The total of all nozzle loads on one multi-bundle bay must not exceed three times the single-header allowance of 7.1.10.2 | `equipment.nozzle-load-sum` with `multiplier` = 3 |

All six components are limited in the header sum, not only the forces or only the moments. A note in the clause says that applying the Table 4 loads moves the header, which tends to reduce the loads toward the 7.1.10.2 values; it is not a relaxation of the sum. The tool sums the sets algebraically in one axis system; signs and the common reference point must be settled first (see axes-and-load-cases.md). Table 4 begins at DN 40 (NPS 1-1/2); the user reads the row. 7.1.10.4 is a cross-reference to 7.1.6.1.3 and was not followed here.

**Vendor confirms.** The bay layout (how many headers share the bay), the header limits as printed in the user's edition, and whether any header is a floating head with its own limits.

---

## 5. Fired heaters - API 560

**What the tables give.** Section 9.2: heater terminals accept the simultaneous application of allowable forces, moments **and movements** (plus or minus x, y, z) in the corroded condition. Tubes: Figure 1 with Tables 7 and 8. Manifolds: Figure 2 with Tables 9 and 10. Non-piped auxiliary connections are excluded. The purchaser specifies anything beyond 9.2.1 and 9.2.2, and the type of analysis is specified or agreed with the purchaser. The subclause numbers 9.2.1 and 9.2.2 were inferred from cross-references in the text; the page itself does not print them in the extraction: verify on the printed page.

**Method.** `connections.nozzle-load-check` per terminal with the user-read row. The movements are a second, separate comparison: the tool does not check them, so list the allowable and calculated movement at each terminal in the calc sheet.

**Vendor confirms.** Which table pair applies (tubes or manifold), the movement allowances, the corroded condition, and any terminal the purchaser specified differently.

---

## 6. Atmospheric storage tanks - API 650 Annex P

**Applicability.** Annex P is used for tanks above 36 m diameter unless the purchaser specifies otherwise on the data sheet, and for smaller tanks only when specified (P.1). It covers shell openings in the lower half of the bottom shell course, at the minimum elevation from the tank bottom, under external piping loads (P.2.1). Only the radial thrust FR, the longitudinal moment ML and the circumferential moment MC are normally significant (P.2.2).

**What the user reads from the standard and figures.**

- The stiffness coefficients KR, KL and KC (P.2.4, Figures P.2a to P.2l) and the unrestrained shell growth W and rotation θ (P.2.5), used by the stress analyst to calculate the piping loads at the opening (P.2.6). The equations for W and θ were **image** or garbled in the extraction; the tool does not use them, and the user takes them from the printed page.
- YF and YL from Figure P.4a and YC from Figure P.4b, by λ = a/(R·t)^0.5. The curves are image only and never reproduced here. Verify on the printed page: some editions print YL in P.2.7.2.3 for the MC point, while P.2.7.2.1 and the nomenclature give YC from Figure P.4b. The tool uses YC for the MC ordinate; read the figure your edition's text names and enter that value.
- The acceptance boundary of the opening on the nomograms of Figures P.3a/b and P.5a/b. The construction recipe (P.2.7.1) uses the positions XA, XB, XC over (R·t)^0.5 that the tool returns; the boundary itself is read from the printed figures.

**What the tool computes (P.2.7.2).** `λ = a/(R·t)^0.5`, `FP = π·a²·P` (pressure end load, P.2.3), the abscissa `(λ/2YF)(FR/FP)`, the Figure P.5a ordinate `(λ/(a·YL))(ML/FP)`, the Figure P.5b ordinate `(λ/(a·YC))(MC/FP)`, and the per-unit-load scale factors. P is the product-head pressure at the opening centreline, so FP is the pressure end load for the nozzle at that elevation. Acceptance (P.2.7.2.4): the piping loads are acceptable if **both** plotted points lie within the nomogram boundaries for the opening-tank configuration. The quadrant labels on the figures say whether tension or compression controls; they are image content and the user reads them. The status is always `na`.

**Responsibilities (P.2.8).** The manufacturer furnishes the stiffness coefficients and the unrestrained shell deflection and rotation; the purchaser furnishes the shell-opening loads from the piping flexibility analysis; the manufacturer determines acceptability. If the loads are excessive the piping is modified, or, by mutual agreement only, the opening elevation or shell thickness is changed.

**Alternative (P.3).** Local stresses by WRC 297 or VIII-2 stress calculations, or by shell-element FEA, against P.3.3: local membrane stress limited to the greater of 1.5 times the design stress or the yield strength, and combined local stresses to the greater of twice the yield strength and three times the design stress, not above the tensile strength. Loads are applied simultaneously, at least in the combinations +FR +MC +ML and -FR +MC +ML (P.3.2.5). Not run by this skill.

**Vendor (manufacturer) confirms.** The coefficients, the shell growth and rotation, the nomogram boundaries and the verdict.

---

## 7. Pressure vessels with no API or vendor allowable

This is the default. The method, its limits and the scaling rules are in [pvp2011-method.md](pvp2011-method.md). Summary: the user reads a row of the paper's table, the tool scales it for thickness, material and temperature and the owner factor, and the per-nozzle check compares the applied loads with the derived set. A load above the derived set is not a failure of the vessel; it means individual analysis is needed.

---

## 8. Optional owner practice - PIP RECE002

Design-stage factors, resolution points, the lower-of rule and the calculation triggers are in [owner-practices.md](owner-practices.md). RECE002 is not a source of allowable values; it limits the loads piping may use at the design stage.
