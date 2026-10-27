# Rejection checklist - full list

Run every item before handing a calc sheet over. Each is a five-second check that prevents a re-issue.

1. **Rating at the wrong temperature.** The rated pressure must be read at the design metal temperature (B16.5 2.4), not at ambient, not at the fluid temperature, and not the next-lower tabulated temperature without interpolating. A mixed joint takes the lower of the two flange ratings.
2. **G taken as the bolt circle** (or the gasket OD, or the bore). G is the gasket load-reaction diameter: the mean gasket diameter for a narrow gasket, OD - 2b for a wide one. The tool requires A > C > G > B and will not accept the bolt circle for G.
3. **Moment in ft-lbf passed as in-lbf** (or N-m as lbf-in). The screen takes `M_in_lbf`; the detailed module takes `Mext` in ft-lbf. A factor of 12 understates the moment term by 92 percent. State the unit on the sheet beside every load.
4. **Compression credited silently.** VIII-2 4.16.13 takes a compressive net-section force as FA = 0. The screen clamps a negative F to 0 (with a warning) unless `creditCompression` is true, and the detailed module takes `Fax` = max(F, 0), unless the owner agrees to credit compression. If it is credited, run the tensile case separately and report both. Say which was done.
5. **Peq reported as a stress check.** The pressure-equivalent screen is a conservative leakage screen. A pass does not prove bolt, gasket or flange stress; a fail is not a joint failure.
6. **Sn omitted, so the 2.5 Sn cap is unchecked.** The hub stress limit for a hub welded to pipe is min(1.5 Sf, 2.5 Sn). Without Sn the tool uses 1.5 Sf and warns; leave that warning in the findings or supply Sn.
7. **Gasket m and y with no table line.** Both come from VIII-2 Table 4.16.1 (suggested values) or an agreement between designer and user (4.16.5.1). Record the gasket material, facing and the line.
8. **Sa and Sb swapped.** Sa is the bolt allowable at ambient (gasket seating), Sb at design temperature. Swapping them changes Am and the seating load.
9. **Loose flange run as integral, or the reverse.** The attachment decides L, the hub terms, the stresses and the rigidity expression. Welded slip-on, loose-with-hub and reverse flanges are not modelled.
10. **Bolt root area from the nominal diameter.** Use the UN root area (or the area basis the project specifies) and state which. The nominal circle overstates the area.
11. **Rigidity J ignored.** A flange that passes every stress limit but has J above 1 is too flexible; the tool fails it. Report J for both cases.
12. **Hydrotest case missing** where the owner requires it. The detailed module runs the pressure and allowables it is given; a test case needs its own run with its own basis, or a stated reason it is dismissed.
13. **Ring-joint b0 rule misapplied.** A ring joint uses b0 = N/8, not N/2; the tool takes G as the mean of the contact ID and OD when b0 is 0.25 in or less and as OD - 2b above that, so compare it with the ring pitch diameter on the gasket sheet. Other facings come from the effective-width table.
14. **Owner acceptance percentage unstated.** Say whether the rating was used at 100 percent or at the owner's percentage, and cite the practice. PIP PNC00004 3.2.10 allows the equivalent pressure method but leaves the acceptance value to the owner.
15. **Hub factors from the reconstruction on a sealed calc.** The default series is a reconstruction, not Code text. For a sealed issue, use F, V and f read from the Table 4.16.5 equations (the override inputs) or say which method was used and that it was cross-checked.
16. **Bolt-spacing correction applied or dropped without saying so.** The correction scales the stress moments, never the rigidity moment. State whether it was required.
17. **Torsion and shear dropped without saying so.** Neither method uses them. List them as reported and not used.
18. **Method not computed, not named.** UG-44(b) / 4.16.12, NC-3658.3, EN 1591-1 and PCC-1 Appendix O assembly bolt stress belong in the findings as open items, with the B16.5 2.5.2 temperature advisory where it applies.
19. **A code-table value typed in without its table line**, or a value stated that did not come from the user's licensed copy.
20. **Edition undeclared**, or a table name quoted from a different edition than the one on record.
