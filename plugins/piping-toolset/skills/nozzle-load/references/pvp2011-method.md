# Vessel nozzle allowables - the PVP2011-57100 method

The default for a pressure vessel nozzle with no API or vendor allowable. The source is the paper "Establishing Allowable Nozzle Loads" by Koves, Upitis, Cullotta and Latif, ASME PVP2011-57100 (Pressure Vessels and Piping Division Conference, 2011). Cite it by that name. The user reads the paper's table rows from their own copy; **no table value is embedded** in this skill, and this file quotes the paper only in short clauses.

## What the paper provides

Three tables of allowable loads by nozzle size (NPS 2 to 24), each giving six coincident components for a vessel nozzle:

| Table | Class | Vessel thickness basis (exclusive of corrosion allowance) |
|---|---|---|
| 1A | Class 150 | 0.25 in and above |
| 1B | Class 150 | 0.375 in and above |
| 2 | Class 300 | 0.375 in and above |

Component names as the paper tabulates them: axial `Fx`, longitudinal `Fy` and circumferential `Fz` forces in lbf; longitudinal `Mz`, circumferential `My` and torsion `Mx` moments in ft-lbf. Axes in the paper's nomenclature: x is the nozzle centreline directed radially out, y is the vessel centreline directed up, and z is x cross y (right-hand rule). Map the piping stress model's axes onto these before any comparison (axes-and-load-cases.md).

The paper also says its own basis is general: the tables are for **carbon steel** (SA-516 Gr. 70 vessel shell; SA-106 Gr. B or SA-105 nozzle neck) at a design temperature not above **650 F**, **reinforced nozzles** except NPS 2 (taken as Schedule 40 and unreinforced), thickness limits **exclusive of corrosion allowance**, and vessel diameter to thickness ratios D/T up to **320** (the paper notes that this is not a general limit). Integral reinforcement is assumed only when the vessel thickness exceeds 1.25 in; the final nozzle and vessel design details remain the vessel engineer's responsibility.

## How the paper arrived at the tables (what the limits mean)

- Basis: ASME Section VIII Division 1 construction, with Division 2 stress limits applied to the elastic finite element results: primary local membrane at the nozzle-to-shell junction within 1.5S, primary plus secondary membrane plus bending within 3Sps (Sps being the average of the ambient and design temperature Division 1 allowable stresses), and the nominal stress intensity in the nozzle neck within S. The Division 2 supplemental requirement of paragraph 5.6 was also checked and did not govern.
- The 3Sps limit may be exceeded by up to 25 percent for typical low-cycle applications, where primary loads plus restrained free end displacement are considered (the paper's Note 1, based on fatigue life at small strain increase).
- The evaluation is of **total operating loads** (forces and moments together) assumed to be a minimum of **50% primary**. Apply the derived set to the total operating load, not to the sustained part alone and not to the thermal part alone.
- Class 150 wall thickness is not controlled by pressure, so the Class 150 tables use assumed minimum thicknesses (1/4 in for Table 1A, 3/8 in for Table 1B) rather than a pressure design thickness; Class 300 uses an assumed minimum (3/8 in). The loads are scaled up or down until the stress limits and the B16.5 flange joint limits are met, and the tables reflect the worst geometry and pressure within each class. FEA used shell elements; the effective thickness of shell plus pad is `te = (T^2.5 + tp^2.5)^0.4` (eq. 3), and where local membrane stress governed, additional FEA used the full pad thickness. The paper compares a solid-element model of a Class 300 vessel (within 10 percent) and notes that the high-pressure class results should be validated by solid-element models.
- Size scaling: forces scale with nozzle diameter, `Force = constant x d` (eq. 1), and moments with the diameter squared, `Moment = constant x d^2` (eq. 2). The paper's tables for intermediate sizes were obtained from these forms with the constants taken from each FEA run.
- Loads exceeding the table values need individual special analysis.

## Scaling rules the tool applies

The tool applies the rules in this order and writes each to the `log` of the result.

1. **Interpolation (optional, intermediate NPS).** The user reads the two adjacent table rows and gives `lowerNPS`, `lowerRow`, `upperNPS`, `upperRow`. The paper prints eq. (1) `Force = constant x d` and eq. (2) `Moment = constant x d^2`, and says its intermediate sizes came from them with the constants derived from each FEA analysis (NPS 2, 6, 12, 18 and 24). That is proportional scaling through the origin from a fitted constant. Between two rows the user has read, the tool uses the straight-line form in d (forces) and in d^2 (moments):

   ```
   F(d) = F1 + (F2 - F1) (d - d1) / (d2 - d1)
   M(d) = M1 + (M2 - M1) (d^2 - d1^2) / (d2^2 - d1^2)
   ```

   The straight-line form between two user-read rows is the skill's own choice; eq. (1) and eq. (2) themselves are printed in the paper. For comparison the tool also reports `proportionalBound`: the eq. (1) / eq. (2) proportional estimate from each row (force x d / d_row, moment x d^2 / d_row^2), lower of the two per component, and warns where the affine value is above it. The bound is the conservative set. It never extrapolates, and when an intermediate size matters to the verdict, say so and have the vessel engineer confirm.

2. **Thickness, eq. (4).** For a vessel thickness T below the table's basis thickness the paper gives, for Table 1A and thicknesses below 1/4 in, `M(T) = M(1/4) x (T / 0.25)^2` for any force or moment. The tool applies the same form to the table's own basis thickness:

   ```
   value(T) = value(basis) x (T / basis)^2      (T below the basis)
   ```

   The reasoning in the paper: for a fixed reaction load, local membrane stress goes inversely with thickness and local bending stress inversely with thickness squared, so the squared form is conservative when the stresses are primary. The paper reports FEA validation for the form where the applied pressure is below the maximum allowed by the ratio (T / 0.25)^2. The tool warns whenever T is below the basis, and warns that the extension to Table 1B and Table 2 is not the paper's own statement. For a Class 150 vessel with 0.25 in <= T < 0.375 in, use Table 1A (basis 0.25 in, no thickness factor) rather than Table 1B scaled by the square law; the paper wrote eq. (4) only for T below 1/4 in against Table 1A. Thickness above the basis earns **no credit**: the table is a floor, not a slope. Use T without the corrosion allowance.

3. **Material and temperature ratio.** For materials other than SA-516 Gr. 70 shells with SA-106 Gr. B or SA-105 necks, or for design temperatures above 650 F, the paper multiplies the table values by the lowest of

   ```
   S_vessel / 18,800   and   S_nozzle / 17,100,   not exceeding 1.0
   ```

   where S is the Division 1 allowable stress of the specified material at the design temperature, read by the user from the stress tables of Section II-D. The 18,800 psi and 17,100 psi are the paper's reference values (the allowable stress of the shell and neck basis materials at 650 F). The ratio never exceeds 1.0: a stronger material earns no uplift. The paper says for low-modulus materials such as aluminium the local deformation at the nozzle exceeds that of a carbon steel vessel, so the ratio does not cover them. Individual analysis.

4. **Owner factor (optional).** A factor from the owner's practice, 0 < f ≤ 1, multiplies the result (for example the PIP RECE002 design-stage factors, owner-practices.md). The tool logs it with the basis the user states.

The derived six-component set is then the allowable set for `connections.nozzle-load-check`, which compares the applied loads, component by component, with the derived values. The two checks together are the vessel nozzle evaluation.

## Limits of applicability - state these in the calc sheet

| Limit | Source in the paper | Tool behaviour |
|---|---|---|
| Division 1 construction | tables intended for Section VIII Division 1 | Scope warning on every run |
| Carbon steel, design temperature at or below 650 F | basis materials and temperature; above 650 F the paper's only adjustment is the stress ratio | Warns above 650 F (the ratio does not capture creep-range behaviour: confirm with the vessel engineer) and for any other material; warns if not stated |
| Reinforced nozzles except NPS 2 | NPS 2 is Schedule 40 and unreinforced | Scope warning |
| No corrosion allowance in the thickness | "thickness limits are exclusive of corrosion allowance" | The input T excludes it; the interview asks |
| NPS 2 to 24 | table range | Warns outside it |
| D/T up to 320 | developed for diameter to thickness ratios up to 320 | Warns above it with the optional vessel diameter; flags it if not given |
| Total operating loads, at least 50% primary | stated basis of the evaluation; wholly primary loads are inside it, wholly secondary is the conservative case | Notes the basis when `loadsPrimary` is true and flags it if unstated: apply the set to total operating load, not a sustained or thermal part alone |
| Pad and stress limits | developed with an effective pad thickness (full-thickness pad where local membrane governed) and Division 2 limits: 1.5S local membrane, 3Sps membrane plus bending, with the 25% note | Reference only |
| Loads above the derived set | "loads exceeding the specified values require individual special analysis" | Not a pass or fail of the vessel: needs individual analysis |

**Loads above the derived set** need individual analysis by one of: local stress by WRC 537 or WRC 297 at the nozzle (curve values read by the user from the bulletin), the ASME STP-PT-074 approach, or finite element analysis with stress classification per ASME VIII-2 paragraph 4.5.15. This skill identifies the need; it does not run those methods. The vessel engineer owns the nozzle and reinforcement design, and the vessel's vendor datasheet loads override the derived set where the vendor provides them.

## Statement to carry into the calc sheet

"Allowable nozzle loads derived by the method of 'Establishing Allowable Nozzle Loads' (ASME PVP2011-57100) from Table [1A / 1B / 2], row NPS [n], read by the user from their copy; scaled for vessel thickness T = [..] in (eq. 4), the material and temperature ratio [..] (S_vessel [..], S_nozzle [..] psi at [..] F, from Section II-D, edition [..]), and owner factor [..] ([basis]). The set applies to total operating loads on a Division 1 vessel. Loads above it need individual analysis."
