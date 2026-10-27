# QC gate — full checklist

Relocated verbatim from the load-case-builder SKILL.md (Step 9).

Run every item. Each is a defect class that can happen when a template is reused on a larger job.

1. **Stale cross-references.** Does every combination reference resolve to the case its description claims? When a template is reused on a larger job the old numbers can carry over — a "sustained" case can turn out to be an operating-with-wind case, and a "Maximum Occasional" an expansion case.
2. **Envelope completeness.** Does the top-level Maximum Occasional include **every** occasional kind? An envelope that lists PSV, snow and wind but not the seismic maximum means seismic stress is never code-checked.
3. **Direction labels.** Does each occasional case's description match the vector actually in it (a "Wind +X" label on a −X combination)?
4. **Vertical seismic present?** `E_v = 0.2·S_DS·W_p` concurrent, and `U2` not double-booked with snow.
5. **Expansion completeness.** One EXP case per state × friction pair.
6. **Linear shortcut on a nonlinear model.** Any standalone "pure wind/seismic" case scalar-added to sustained, in a model with friction, gaps or one-way restraints.
7. Forward references — a combination referencing a later case.
8. Intermediate (pure occasional) cases set to Suppress.
9. Friction: both variants present, governing taken, both documented.
10. Occasional factor matches the code, edition and stated duration.
11. ASD reduction position stated and consistent with the code.
12. Hanger Rigid (`W`) and Ignore (`W+T1`) cases present, carrying no `H`, and ahead of any As-Designed case.
13. Expansion range brackets the true extremes, including any below-ambient state and any inter-state range.
14. Wind shape factor zeroed where the line goes indoors; first-node elevation set.
15. SAM and settlement in the expansion check, not the occasional check.
16. Static seismic not used where anchor movements exist; water hammer not modelled statically.

The generator checks items 4, 5, 7, 10 and 11 automatically and prints its findings. The rest need the model.
