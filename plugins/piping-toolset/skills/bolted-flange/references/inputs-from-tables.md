# Inputs from tables - where each one lives, and how to ask for it

Every value below is read by the user from a licensed copy of the standard or from the manufacturer's data. This skill never states one. Table names are pointers only: they move between editions, and the 2025 B16.5 table numbers could not be verified here. Ask the user to confirm the table name on their printed page and to give the table, line and edition with the value.

## Input map

| Input (tool name) | Where it lives | Notes |
|---|---|---|
| `ratedPressure` | ASME B16.5 pressure-temperature ratings, "Pressure-Temperature Ratings for Group N.N Materials", U.S. customary version, for the flange material group and class | At **design metal temperature** (B16.5 2.4). Linear interpolation between temperatures is permitted; none between classes. Mixed joint: the lower of the two flange ratings (2.3.2). An owner may require a percentage of the rating: ask |
| `A`, `B`, `C`, `t` | B16.5 flange dimension table for the flange type (welding neck, etc.), class and NPS | A outside diameter, B bore (welding neck: the bore for the pipe it welds to), C bolt circle, t thickness. Use the dimension the table gives, not a catalog value |
| `X`, `Y` (to `connections.flange-derive`) | B16.5 welding-neck dimension table: hub diameter at the base (X) and length through hub (Y). The hub-and-weld-end profile tables apply by wall thickness | Confirm the column letters on the printed page |
| `pipe_OD` | The pipe the neck is welded to | g0 follows from the pipe wall |
| `gasket_ID`, `gasket_OD` | The gasket manufacturer's sheet, or ASME B16.20 ("Dimensions for Spiral-Wound Gaskets Used With ASME B16.5 Flanges", and the inner-ring and maximum-bore tables), or B16.21 for non-metallic | Contact width: the sealing element that actually bears on the facing, not the centering ring or the inner ring. Confirm against the effective gasket width table |
| `facing` | The flange facing, plus VIII-2 Table 4.16.3 (Effective Gasket Width for Determining the Bolt Loads) | The tool's rules are the flat-facing (N/2) and ring-joint (N/8) rules only |
| `m`, `y` | VIII-2 Table 4.16.1 (Gasket Factors for Determining the Bolt Loads) | The Code calls these suggested values. Other values from testing or literature, agreed between designer and user, are permitted (4.16.5.1). Record the gasket material, facing and table line, or the agreement. Minimum contact width: Table 4.16.2 |
| `nBolts`, `bolt_D`, `bolt_tpi` | B16.5 flange bolting tables (Flange Bolting Dimensional Recommendations) and the bolt specification | Threads per inch from the bolt specification, not from memory |
| `aRoot` | Computed by `connections.flange-derive` from the UN formula, or supplied | Root area is not the nominal circle and not necessarily the tensile stress area. VIII-2 4.16.13 defines the bolt area Ab on the smaller of the thread root diameter and the least unthreaded diameter, so a reduced-shank bolt takes the smaller area; PCC-1 Appendix H gives bolt root areas, a table to cross-check the UN formula against. State the basis |
| `Sa`, `Sb` | Bolt design stress: the B31.3 Appendix A bolting table (name varies by edition); for B31.1 (104.5.1), Mandatory Appendix A, Table A-10; or Section II-D Table 3 for a Section VIII basis | Sa ambient, Sb at design temperature. Do not swap them |
| `Sf`, `SfAmbient` | B31.3 Appendix A basic allowable stress table; under 304.5.1(b) Sf is the product S x E x W for the flange or pipe material. For B31.1 (104.5.1), Sf is the allowable stress of the flange material or pipe from the Appendix A allowable stress tables (see 102.3.1); it is not an S x E x W product | Design temperature and ambient, with any interpolation shown |
| `Sn`, `SnAmbient` | Same basis for the pipe or neck the hub is welded to | Needed for the 2.5 Sn cap |
| `Edesign`, `Eambient` | Section II-D Subpart 2 material properties tables, modulus of elasticity, for the flange material group | Rigidity only. No silent default: the tool refuses to run without them |
| `rigidityFactor` | VIII-2 Table 4.16.10 general notes: 0.3 for integral, 0.2 for loose, unless specified otherwise | The tool uses these when omitted and says so |
| `F_override`, `V_override`, `f_override` | VIII-2 Table 4.16.5 equations or the retired figures (2-7.2, 2-7.3, 2-7.6; they map to the table). The skill does not ship the curve fit | Evaluate the printed equations at Xg = g1/g0 and Xh = h/sqrt(B g0) |
| F, M (the loads) | The piping program's restraint or flange-load output for the load case | See below |

## Lookup-instruction wording

Use this shape. Name the table, the line, the edition and what to return.

> I need the **rating** at your design temperature. That is the B16.5 pressure-temperature table for material group [x.x], Class [xxx], U.S. customary. Read the value at the tabulated temperature below and the one above your design metal temperature, plus any notes. The standard permits linear interpolation between temperatures; I will show the arithmetic. Which edition is your copy?

> I need **m and y** for your gasket. That is VIII-2 Table 4.16.1, Gasket Factors for Determining the Bolt Loads, line [gasket material and facing]. Read both values and tell me the line, or tell me the project agreement if other values were agreed (4.16.5.1).

> I need **Sa and Sb**. Those are the bolt design stresses at atmospheric and at design temperature for [bolt material], from [B31.3 Appendix A bolting table / II-D Table 3]. Give each with its table line and edition. They are not interchangeable.

> I need **Sf and Sn** under B31.3 304.5.1(b): the product S x E x W for the flange and for the pipe, with the table line behind S, E and W. Under B31.1 104.5.1, Sf is the Appendix A allowable for the flange material and Sn the same for the pipe, each with its table line.

Do not ask the user to upload a standard's PDF.

## Derivations the tool does

| Quantity | Rule | Source |
|---|---|---|
| N | (gasket OD - gasket ID)/2 | Contact width |
| b0 | N/2 flat; N/8 ring joint | Effective gasket width rules, Table 4.16.3 |
| b | b0 if b0 <= 0.25 in, else 0.5 sqrt(b0) | Eq. 4.16.1 to 4.16.3 |
| G | (ID + OD)/2 if b0 <= 0.25 in, else OD - 2b | Table 4.16.3 |
| Bolt root area | pi/4 (D - 1.299038/n)^2, n threads per inch | UN thread geometry |
| g0 | (pipe OD - B)/2 | Equals the nominal pipe wall tn (the VIII-2 4.16.13 definition of g0) only if the bore B equals the pipe ID. If B differs, enter g0 as the nominal pipe wall; the tool warns on every hub run |
| g1 | (X - B)/2 | Hub thickness at the base |
| h | Y - t | Hub length |

For a ring joint the tool applies the same b0 test: G is the mean of the contact ID and OD when b0 (N/8) is 0.25 in or less, and OD - 2b above that. The tool's warning says which applied. The ring pitch diameter on the gasket sheet is the better G; compare.

## Loads from the piping program

- **F:** the axial force along the flange axis, signed, tension positive. Confirm the program's sign convention for the node and the direction the element leaves it.
- **M:** the resultant of the two bending components, sqrt(M1^2 + M2^2), not either component alone, and not the torsion.
- **Units:** the single most common error. Programs report in lbf and ft-lbf, lbf and in-lbf, N and N-m, or kN and kN-m. Convert to lbf and in-lbf, or give the screen `M_ft_lbf`. `aux.app2-flange-integral` takes `Mext` in **ft-lbf**; use `Mext_in_lbf` for in-lbf.
- **Which case:** run the screen per load case, with that case's pressure. Sustained plus pressure, operating, and occasional cases give different F and M. An envelope of the worst F and the worst M from different cases is conservative; say so if you use it.
- **Torsion and shear:** neither method uses them. List them as reported and not used.
