# QC gate — full checklist

Relocated from the load-case-builder SKILL.md (Step 9); item 17 and the coverage wording of items 5, 9 and 12 added in 0.7.1.

Run every item. Each is a defect class that can happen when a template is reused on a larger job.

1. **Stale cross-references.** Does every combination reference resolve to the case its description claims? When a template is reused on a larger job the old numbers can carry over — a "sustained" case can turn out to be an operating-with-wind case, and a "Maximum Occasional" an expansion case.
2. **Envelope completeness.** Does the top-level Maximum Occasional include **every** occasional kind? An envelope that lists PSV, snow and wind but not the seismic maximum means seismic stress is never code-checked.
3. **Direction labels.** Does each occasional case's description match the vector actually in it (a "Wind +X" label on a −X combination)?
4. **Vertical seismic present?** `E_v = 0.2·S_DS·W_p` concurrent, and `U2` not double-booked with snow.
5. **Expansion completeness.** One EXP case per state × friction pair, and one inter-state range per state pair × friction pair when ranges are on.
6. **Linear shortcut on a nonlinear model.** Any standalone "pure wind/seismic" case scalar-added to sustained, in a model with friction, gaps or one-way restraints.
7. Forward references — a combination referencing a later case.
8. Intermediate (pure occasional) cases set to Suppress.
9. Friction: both variants present, governing taken, both documented. Every friction variant reaches Maximum Operating, the HYD extraction and every sustained and displacement row, not only the first.
10. Occasional factor matches the code, edition and stated duration.
11. ASD reduction position stated and consistent with the code.
12. Hanger Rigid (`W`) and Ignore (`W+T` of the primary state) cases present, carrying no `H`, and ahead of any As-Designed case; the primary state (`primary_state`) and the friction multiplier the pair runs at (`hanger_friction`) are stated, not assumed silently.
13. Expansion range brackets the true extremes, including any below-ambient state and any inter-state range.
14. Wind shape factor zeroed where the line goes indoors; first-node elevation set.
15. SAM and settlement in the expansion check, not the occasional check.
16. Static seismic not used where anchor movements exist; water hammer not modelled statically.
17. **Resolved case set against the declared spec.** Every case the spec implies exists and is wired to the cases its key names: per state × friction, OPE, SUS and EXP (`OPE − SUS`); per occasional × friction, OPE+OCC, the pure occasional (`OPE+OCC − OPE` of its own base state), the code case (`SUS` of its base state `+` pure) and, when the occasional carries a `scale`, its unreduced companion; per state pair × friction, the inter-state range when ranges are on; HYD per friction; the hanger pair. Envelope membership: every OPE case of every state and friction, and every OPE+OCC case (the unreduced companion when scaled, never the reduced case), in Maximum Operating; every code occasional case in its kind envelope; every kind envelope in Maximum Occasional. Matrix membership: every SUS case in the sustained code-stress, support-load and displacement rows; every EXP and range case in its row; every HYD case in the hydrotest code-stress and support-load rows; the hanger pair in its row; every unreduced companion in the unreduced row. A case the spec does not imply is also a miss. A non-primary state, a frictionless variant or an unreduced load that governs is then always in the case the matrix points to.

The generator checks items 4, 5, 7, 10, 11 and 17 automatically and prints its findings; item 17 is also returned as the `qc` object of `--format json` (`pass`, `counts`, `misses`, [spec-format.md](spec-format.md#output)), and a miss is an `ERROR` finding: do not issue the set. It also states the item 9 and 12 bases it assumed (`ASSUMED:` findings for the primary state and the hanger friction). The rest need the model; the JSON `checks` list names each of them `not checked`, and an ASSUMED basis makes the set `manual check required` ([spec-format.md](spec-format.md#output)).
