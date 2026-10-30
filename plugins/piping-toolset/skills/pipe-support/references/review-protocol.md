# Review protocol - reviewing like the checker who signs it

The engine produces the numbers and a first set of findings (`review.py`). Your job is the
part a model cannot do: test whether the model represents the real support, and say
clearly what a reviewer would send back.

## Finding severities

| Severity | Meaning | Examples |
|---|---|---|
| **critical** | Fails, or the model cannot carry a load that exists | ratio > 1; pipe moments at an anchor; uplift with no anchorage; the drawing shows a different shape than the calc |
| **major** | Within 10 % of a limit, a possibly unconservative input, or a detailing violation | 0.9 ≤ UR ≤ 1.0; weld base metal on the wrong part; fillet outside J2.2b limits; ACI default kc used for an adhesive anchor in a final design |
| **minor** | Advisory, constructability, overdesign | KL/r near 200; UR < 0.4; three shape families on one support; non-standard plate |
| **info** | Basis items to confirm | K = 2.1, Cb = 1.0, T factor, existing-structure capacity |

Label your own findings **[reviewer]** and engine findings **[engine]**.

## Output status words

A stage, a compliance row and the envelope carry one of: **pass**, **fail**, or
**manual check required** (a validity guard holds the result; the ratio shown is the
engine's, but it is not a pass). The verdict line is FAIL when any limit state fails; otherwise NOT ISSUABLE
when a guard holds a stage; otherwise PASS, or PASS (strength) WITH n CRITICAL REVIEW
FINDING(S). Never present a NOT ISSUABLE or a held stage as a pass, and never soften it to
"passes with a note". The guard today:

- **ASD anchorage governed by a wind combination** (code-basis item 10; owner ruling
  2026-10-30, superseding the 2026-10-26 "documented only" ruling; P.E. confirmed 2026-10-30).
  Verdict: "NOT ISSUABLE - ASD anchorage governed by wind combination `<id>`: run anchorage in
  LRFD or resolve the ACI strength-to-ASD factor treatment (code-basis item 10)". The engine
  also raises the *major* finding "ASD anchorage governed by a wind combination", which says
  the guard applied. Recommend re-running with `"method": "LRFD"` for the anchorage verdict.
  The guard also holds the stage when a non-wind combination governs but the worst wind
  combination's ratio x (1/0.6)/1.5 reaches it (*near-governing*), and, in factored mode,
  unless the spec sets `factored_wind: false` (the engineer's declaration that the entered
  loads carry no wind). In factored mode ask whether the entered loads carry 0.6W before
  accepting that declaration.

## What to check, in this order

1. **Load path.** Does every load the restraint report shows reach the foundation? Watch
   for moments, uplift, and longitudinal loads at a line stop or anchor. Check that the
   occasional cases are pure (not OPE+WIN) and the vertical-axis sign is correct.
2. **Governing limit state.** Name it, its combination and its clause, and explain in one
   sentence *why* it governs (lever arm, LTB length, edge-clipped breakout cone, ...).
3. **Near misses.** Anything ≥ 0.9, and any advisory near its limit.
4. **Connections and detailing.** Fillet size limits by the thinner part; base-metal
   rupture; bolt spacing and edge distance; anchor edge and spacing against 1.5 hef; plate
   thickness increments; the matching-filler class.
5. **Basis.** K and Cb assumptions; ESR values for post-installed anchors; whether the pier
   is anchored into existing concrete (then the EXISTING structure must take the base
   reactions, so say so) or a gravity pier on soil (service-level stability).
6. **Constructability.** Field welds, especially overhead; weld access around the column
   base; mixed shape families; erection sequence for multi-tier arms.
7. **Optimisation.** If UR < 0.4 anywhere or a lighter, simpler alternative passes,
   present the optimizer table and recommend one option with its trade-off.

## Reviewing a drawing or a calc package

When the user supplies a support drawing (PDF) or someone else's calculation:

1. Read the title block, revision, support tag and line numbers.
2. Transcribe the geometry and member sizes into a spec. Mark anything not dimensioned as
   ASSUMED. Never guess silently.
3. Run the spec. Compare its governing results with the package's own numbers,
   **line by line** (the PS-101 verification test is the model for this). Every difference
   is a finding: a different section, load or K, or an omitted check.
4. List the checks the package **omits** (commonly: base-metal rupture at welds, anchor
   breakout with edge reduction, pryout, deflection, uplift combinations, 0.9D + W).
5. Report the result as a checker's comment sheet, as a table of *Item / Drawing or calc
   reference / Finding / Severity / Required action*.

## Optimizer - presenting alternatives

- Show the ranked table from the run. Every row passed every combination, and no row has an
  anchorage stage held by the ASD wind guard. In ASD with wind governing the anchorage the
  table can be empty; the search log says the guard held the pairings. Say so and offer the
  LRFD re-run.
- Explain the objectives the user chose (weight, field work, stocked sizes) and how each
  option scores on them.
- Note what each option changes in fabrication and erection.
- If the best option is within 5 % of a limit, offer a re-run with `optimize.maxRatio`
  below 1.0 rather than recommending a just-passing design for a support that may pick up
  more load.
- The bolted end-plate alternative is sized on a thick-plate (no prying) basis. Column
  flange local bending (J10) and the arm-to-end-plate weld are still to be checked if it
  is chosen. Say so.

## The PE-ready package

The Markdown report is structured for issue: title block, verdict, design basis, geometry,
loads and combination traceability, base reactions, per-stage limit-state tables with
clauses, a compliance matrix, findings, alternatives, assumptions and definitions. Before
handing it over, make sure the assumptions list includes every ASSUMED input and every
ESR or geotech value with its source.
