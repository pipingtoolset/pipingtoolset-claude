# Rejection checklist - full list

Relocated from the "Before you hand it over" section of `SKILL.md`. Run every item before handing a calc sheet over. Each is a five-minute check that prevents a re-issue.

1. **Axis mapping unstated.** No table of equipment axis against global direction and sign, or the mapping copied from another nozzle or another pump. Load sets in the wrong axes pass silently.
2. **Wrong resolution point.** Pump loads not resolved to the intersection of the shaft and casing transverse centrelines; a compressor resolved at a small nozzle instead of the fixed end or the largest nozzle; a turbine resolved anywhere but the exhaust.
3. **2x against 1x confusion.** The 2x Table 5 limit of Annex F presented as a piping allowable. Table 5 at 1x is the allowance; 2x is the casing design margin, so loads between them need Annex F and the vendor's direction. The exception is API 610 6.5.3: for OH3 / OH6 vertical in-line pumps whose supports are not anchored, 2x Table 5 on side nozzles is permitted, and F.2 governs beyond it. Confirm the support condition and the vendor datasheet before flagging or accepting a 2x load.
4. **Loads not in the corroded condition** where API 660, API 661 or API 560 require it, or a new-condition run used without saying so.
5. **Table or standard edition unstated**, or a table name quoted from a different edition than the one on record. A row with no table line behind it is a finding against the sheet itself.
6. **SM-23 coefficient unstated.** The coefficient (927 for API 617 E.1b, 500 for API 611 I.1b and API 612 D.1b, or the owner's SM-23 value) with no equation named, or applied to the wrong machine.
7. **Annex F used without purchaser approval**, or without the vendor's direction on how it applies, or a 2x result reported as final when only F.1.2 a) was run (interaction and pump-centre checks also needed).
8. **Paper tables used outside their basis.** PVP2011-57100 values applied to a non-Division 1 vessel, a design temperature above 650 F taken as a pass without the stress ratio logged and the vessel engineer's confirmation (the paper extends the tables above 650 F only through the stress ratio), aluminium or another low-modulus material, D/T above 320, an NPS outside 2 to 24, a thickness below the table basis without the eq. (4) factor logged, or loads that are not total operating loads.
9. **Thermal case omitted.** Only sustained loads compared, or the expansion range alone taken as the operating load.
10. **Friction and cold spring unaddressed.** No statement whether friction was in the loads; no with-and-without comparison where both were run; cold spring credited, or present where PIP RECE002 forbids it.
11. **Vendor allowables not attached.** A datasheet or letter that gives different limits is not in the calc, or the standard's value is used without checking whether the manufacturer's is lower (the lower governs under PIP RECE002 4.2.1.2).
12. **Units mixed.** ft-lbf against in-lbf (a 12x error), or N·m against N·mm, between the piping output, the table and the tool. Check the units field on Annex F.
13. **Hydrotest case compared** with an operating allowable, or a hydrotest condition ignored where the vendor requires one. State the decision either way.
14. **Header sum omitted for API 661.** Each nozzle checked against Table 4 but the sum for the header (7.1.10.2) and the bay total (7.1.10.3) not run, or run with the limits of a different edition, or the bay multiplier applied to the wrong quantity.
15. **Auxiliary connections or large nozzles mishandled.** Vents and drains included where the standard excludes them, or a nozzle above the table's largest size checked against an extrapolated value instead of purchaser-specified loads.
16. **Heater movements ignored.** API 560 terminals compared on loads only; the allowable movements not listed.
17. **Annex P read as a pass.** The ordinates computed but the verdict stated without both points plotted on the printed nomograms, or YF, YL, YC read from the wrong figure or at the wrong λ.
18. **Owner practice factor unsourced.** A 50% or 25% factor applied with no clause, edition and machinery class, or a verdict reported only against the factored allowable when the machinery is vital or sensitive.
19. **Vendor-sheet items left silent.** The combined resultant at the exhaust or largest connection, the vertical-down exhaust allowance, and datasheet multipliers (1.85x, 3x) not listed as items awaiting the vendor.
20. **A load above the derived vessel set called a failure or a pass.** It needs individual analysis (WRC 537 / 297, VIII-2 4.5.15 or FEA); say so and name who owns it.
