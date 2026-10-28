# Owner practices - PIP RECE002 and PIP PNC00004 routing

Relocated detail for Step 0 item 6 of `SKILL.md`. An owner practice sits **on top of** the equipment standard and the vendor datasheet. It never replaces them, and it applies only if the project invokes it. Ask. Do not assume.

## 1. PIP RECE002 - Design of Piping Loads on Rotating Machinery Nozzles

Clause references are paraphrased from the user's copy of the practice (Reaffirmation 2026) and must be confirmed on the printed page of the edition the project invokes. Open the practice before citing a paragraph into a sealed calc, and put its edition beside the citation.

### When a nozzle load calculation is required (4.1.1.3)

Calculate piping loads on machinery nozzles if any one of these applies:

1. the pipe is NPS 3 (DN 80) or larger;
2. the system temperature is above 300 F (150 C);
3. the system temperature is -150 F (-100 C) or below;
4. the machinery is vital or sensitive;
5. the machinery has a history of nozzle load sensitivity or problems.

### Resolution points (4.1.2)

| Machine | Resolve at | Clause |
|---|---|---|
| Steam turbine | the exhaust flange, per API 611 or API 612 | 4.1.2.1 |
| Centrifugal compressor | the fixed end per API 617; if there is no fixed-end nozzle, the largest nozzle | 4.1.2.2 |
| Centrifugal pump | the intersection of the shaft centreline and the casing transverse centreline, per API 610, and the individual nozzle limits are also satisfied | 4.1.2.3 |

### Which allowable governs (4.2.1.2)

If the manufacturer gives nozzle load values and the equipment also complies with an industry standard that gives different values, use the **lower** values as the basis, unless the purchaser and the manufacturer both approve otherwise. Record both sets in the calc and say which governed.

### Design-stage factors (4.2.2 and 4.2.3)

The factors apply to the *allowable nozzle loads* of the industry standard or the manufacturer, during piping layout and system design. They are limits on what piping may use at the design stage, not new allowables.

| Machinery class | Basis | Design-stage limit | Clause |
|---|---|---|---|
| Vital or sensitive | industry allowables (or the manufacturer's) | at most **50%** of the allowable nozzle loads during layout and design, because of prediction difficulty and installation error | 4.2.2.3 |
| Vital or sensitive, not bought to a published allowable standard, or the manufacturer gives none | allowable values calculated per Hydraulic Institute (ANSI) 9.6.2 | at most **25%** of those values | 4.2.2.4 |
| Installed (as-built) loading, vital or sensitive | the values of the practice's Table 1, read by the user | calculated final loading may reach the Table 1 values (the table's column mapping needs a visual check on the printed page) | 4.2.2.8 |
| Essential (spared) | the manufacturer's allowables, or the agreed industry standard | up to **100%**, calculated without a multiplier (as in API 610 Annex F) | 4.2.3.3 |
| Essential (spared), no manufacturer allowable and no stated code compliance | allowable values calculated per Hydraulic Institute (ANSI) 9.6.2 | at most **50%** of those values | 4.2.3.4 |

Essential machinery's actual nozzle loading must also be field verified and documented by the flange alignment checks of PIP REIE686 / API RP 686 (4.2.3.5).

### Piping layout rules the practice adds (4.3)

- **Anchors** (4.3.1.3): unless otherwise specified, no anchors or restraints within 10 pipe diameters of machinery nozzles, so blinding and machinery removal are possible; suction piping is vertically supported so temporary strainers can be removed without temporary supports.
- **Cold spring** (4.3.1.9): cold spring to compensate for pipe growth is not permitted.

### How the skill implements it

The design-stage factors are the optional `ownerFactor` input (0 < f ≤ 1):

- On `equipment.pvp2011-allowables` it multiplies the derived set.
- On `connections.nozzle-load-check`, `connections.nema-sm23`, `connections.api610-annexf` and `equipment.nozzle-load-sum` the CLI layer multiplies the entered allowables (the check's allowable set, the SM-23 coefficient, the Table 5 ranges, the header limits) before the check runs, and the run says so in its warnings. The ratios and the status are then against the factored allowables. Exception: `connections.api610-annexf` with `pumpType` vertical-inline rejects `ownerFactor` (exit 2), because the factor would scale only the Table 5 ranges and not the F.6 to F.11 principal-stress limit that sets the status; run it without a factor and judge against the owner's practice separately.

Use it with a stated basis: "ownerFactor 0.5, PIP RECE002 4.2.2.3, vital machinery, layout stage". The verdict against the unfactored allowable is a second run with the factor omitted; report both when the machinery is vital or sensitive. The tool does not classify machinery, and the default is no factor.

For pumps, the factor scales the Table 5 base ranges entered to `connections.api610-annexf`, so every Annex F limit (the component screen, the interaction terms, the pump-centre limits) scales with it. The practice's 100% value for essential machinery is stated as calculated without a multiplier, as in Annex F; whether that means Table 5 at 1x or the Annex F limits is a reading to confirm with the owner and record. For compressors and turbines the factor scales the SM-23 coefficient; the vendor-sheet combined resultants are not computed by the tool.

The existing note in `connections.nozzle-load-check` (the warning when the maximum ratio exceeds 0.5) points to 4.2.2.3 and 4.2.3.3; it does not change the verdict.

## 2. PIP PNC00004 - piping stress design criteria

PNC00004 is the owner's piping stress practice. This skill does not restate it. Route as follows when the project invokes it:

1. **Cold spring and sag.** Its cold spring and sag provisions (for example a 16 mm sag limit and no cold spring credit in the expansion stress) are carried by the `stress-screening` skill; cite the paragraph from the project's copy.
2. **Equipment nozzle loads.** Open the practice and read what it says about rotating machinery and equipment nozzle loads. If it refers the engineer to PIP RECE002 or to the equipment standards, apply section 1 of this file; if it states its own factors or load cases, those are the owner's rule and take their place as the owner factor, cited by paragraph and edition. The clauses to look for (confirm each in the project's copy and edition):
   - 3.3.1: the lesser of the manufacturer's values or the listed references governs.
   - 3.3.2: rotating machinery is evaluated per PIP RECE002.
   - 3.3.4: air-cooled exchangers per API 661 or the vendor's values.
   - 3.3.5: vessels and exchangers are evaluated by WRC 107 / 297, or by an owner-approved local method outside their limits, with no extrapolation of the curves. When PNC00004 is invoked, the PVP2011-57100 derivation in this skill is a layout-stage estimate only and 3.3.5 governs the vessel check.
   - 3.3.6: tank nozzle loads per the owner's requirements.
   - 3.2.14.3: no cold spring on rotating-machinery piping unless the owner approves.
3. **Load cases.** Its load case list (friction runs, extra mandatory cases) governs the cases fed to this skill: see `load-case-builder`.

Record in the calc sheet which owner practice was invoked, with its edition, and which paragraph set each factor. If the project does not invoke one, write "No owner practice invoked" in the Basis section; silence is the defect.
