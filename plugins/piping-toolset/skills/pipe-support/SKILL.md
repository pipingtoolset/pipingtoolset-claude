---
name: pipe-support
description: "Check a pipe support assembly (arm, column, welds, bolts, base plate, anchors, pier) for CAESAR II restraint loads: ASCE 7-22 combinations, AISC 360-22, ACI CODE-318-25 or 318-19 Ch. 17, AWS D1.1. Use when the user asks to check, review or optimize a pipe support, t-post, trapeze, goalpost or cantilever arm. Reviews it like a PE and proposes optimized code-passing alternatives with a calc report."
compatibility: Requires Python 3.9+ (standard library only)
---

# Pipe Support - structural check, review and optimisation

A pipe-support calc is rejected for three reasons, in order of frequency. The load path is
incomplete (a moment or horizontal load never reaches the anchors). The loads are wrong
(service loads checked against factored strength, or occasional loads that never reverse).
Or a connection is assumed rather than checked (a weld sized by eye, anchors with no
breakout check). This skill closes all three:

1. **Loads** come from the stress program: CAESAR II restraint loads per load case, mapped to
   ASCE 7-22 categories and recombined. The mapping is shown and confirmed, never hidden.
2. **The whole load path** is one deterministic cascade: arm → arm-to-column weld → column →
   column-to-base weld → base plate → anchors → pier/soil. Every stage's reactions become
   the next stage's demands, for every combination.
3. **Connections and detailing** are checked, not assumed: J2 welds, J3/J4 bolts, Design
   Guide 1 plates, ACI CODE-318-25 Chapter 17 anchors (ACI 318-19 selectable with
   `baseplate.aciEdition`), AWS D1.1 detailing items.

The engine is the pipingtoolset.com **PiperSTR** engine, ported to standard-library Python and
locked to it by parity tests. That includes a value-for-value reproduction of a published
PiperSTR Design Summary Report (`tests/test_pipe_support_ps101.py`). **The assistant never computes a
capacity, ratio or alternative itself.** Every number in a response comes from a
`support_calc.py` run.

| File | Role |
|---|---|
| `scripts/support_calc.py` | One spec in → envelope, review findings, optimizer, Markdown report, JSON |
| `scripts/pipe_support/` | Engine: `aisc` (D/E/F/G/H), `weld`, `bolts` (J3/J4), `detailing` (J2 + D1.1 items), `baseplate` (DG1 + ACI 17), `pier`, `assembly` (cascade), `loads` (ASCE 7-22), `optimizer`, `review`, `report` |
| `scripts/pipe_support/data/aisc_shapes.json` | Index of the 1,506 AISC shapes (AISC Shapes Database v16 + computed L/HSS/Pipe), with attribution; the rows are in four family-group parts under `data/aisc_shapes/` |
| `scripts/examples/ps-201-caesar.json` | CAESAR II-mode example (SUS/OPE/WIN/EQ, optimizer on). It enters no Anchor Category, so on the ACI CODE-318-25 default the anchorage takes Category 3 and FAILS (exit 2) with a major review finding; with the ESR Category entered (Category 1: 0.742) its CSA preset anchor values and one ASSUMED item make it read MANUAL CHECK REQUIRED and exit 3 until confirmed |
| `scripts/examples/ps-101-factored.json` | Factored-mode example; reproduces the PS-101 PiperSTR report |
| `references/spec-format.md` | Every spec key |
| `references/review-protocol.md` | How to review a support, a drawing or a calc package; finding severities |
| `references/code-basis.md` | Editions, what is embedded vs supplied, engine limits and known deviations |

## Workflow

1. **Basis interview.** Ask for anything missing. Never default silently. If a project basis
   record exists (an earlier skill's `project-basis.json`, or a file the user names), pass it
   with `--project-basis`, ask only for what it lacks and never relabel a field
   ([record and fill map](references/project-basis.md)).
   - **Configuration**: t-post, multi-tier, cantilever off existing steel, goalpost or trapeze.
     The two CSA presets (`csa-type-1`, `csa-type-2`) are good starting points.
   - **Geometry**: arm projection and elevation, column height, each pipe's offset from the
     column centreline, existing shapes if this is a check rather than a design.
   - **Loads**: the CAESAR II restraint summary for this node, one row per load case
     (SUS, OPE, the pure occasional wind and seismic cases, HYD), with units and the
     vertical axis. Ask for **SDS** if there is a seismic case (Ev = 0.2 SDS D).
   - **Method**: LRFD or ASD. **Materials**: Fy/Fu, FEXX. **Base**: plate, anchor type and
     size, embedment, f'c, pier size, and the **ACI edition** (ACI CODE-318-25 by default,
     `aciEdition: "318-19"` for a legacy project). Post-installed anchors need the product's
     **ESR values**: bond stress tau_cr (and tau_uncr for the group bond equation), kc and the
     ACI 355.2 / 355.4 **Anchor Category**. With no Category the engine takes Category 3, the
     lowest psi_a (Table 17.5.4.1), and the review raises a finding; ask for it. Ask whether
     the anchorage is redundant (Table 21.2.1; nonredundant is the default), for the rod fya,
     and whether there is a grout pad. The engine flags ACI generic defaults.
   - **Pier**: anchored into existing concrete, or a gravity pier/footing on soil
     (allowable bearing and friction from the geotech report, always user-supplied).
   - **Fabrication**: is the arm-to-column joint a shop weld, a field weld or bolted? This
     drives the optimizer's field-work score. A bolted end-plate alternative is always sized.
2. **Confirm the load mapping** before running: D = SUS, T = OPE − SUS, W = pure wind,
   Eh = pure seismic, HYD on its own. Say it back to the user. The T factor defaults to 1.0
   for both methods. LRFD may not go lower (2.3.4); ASD may be reduced to 0.75 (2.4.4) if the
   engineer accepts it. Every combination also runs without T.
3. **Write the spec** (`references/spec-format.md`) to `spec.json` in the working directory and run:
   `python scripts/support_calc.py spec.json --report calc.md --json result.json`.
   Script paths below are relative to this skill's directory. Call them by their full path from wherever the session is working; do not change into the skill folder (in Cowork it is a read-only mount and the working directory is the outputs folder). Write `job.json` and every output file to the working directory, never into the skill folder, so the user can open and download them.
   - **Exit 0:** every combination passes, there is no critical review finding and the
     result status is not manual check required or pointer only.
   - **Exit 3:** not issuable although no limit state fails: a critical finding (pipe
     moments the model cannot carry), the ASD wind-anchorage guard (`references/code-basis.md`
     item 10), or a result status of manual check required or pointer only
     ([outputs](references/spec-format.md#outputs)). The verdict line reads NOT ISSUABLE or
     the status word, never PASS. Never present exit 3 as a clean pass.
   - **Exit 2:** a limit state fails.
   - **Exit 1:** the spec is defective.
4. **Review like a checker** (`references/review-protocol.md`). Lead with the verdict and
   the governing limit state, its combination and its clause. Then go through the engine's
   findings by severity, and add your own judgement findings, labelled **[reviewer]**, about
   anything the model cannot see: the drawing, the load path, constructability, missing
   information.
5. **Optimise.** This works in CAESAR II mode and in factored mode. Present the ranked
   alternatives table from the run, not a list you made up. Every alternative passes every
   combination and the weld base-metal (J4) and column-flange (J10.1) checks, and none has an
   anchorage stage held by the ASD wind guard.
   Explain *why* each one ranks where it does (weight, field work, stocked sizes), what
   governs it, and what changes in the field (bolted versus welded, fewer families, standard
   plate). If the user wants reserve margin, re-run with `optimize.maxRatio` (for example 0.85).
6. **Deliver** the Markdown calc report, the JSON, and a short summary: verdict, result
   status, governing check, top findings, the recommended alternative and why, and what the engineer of
   record must still confirm.

## Rules

- **Every number comes from a script run**, including "what if" comparisons. Change the
  spec and re-run.
- **Never state a code table value from memory.** Anchor product data (bond stress, kc,
  edge limits) comes from the user's ESR. Soil values come from the geotech report. A value
  returned by the connector carries its citation and is recorded as connector-supplied; it is
  still verified against your copy before issue.
- **A failing result is never softened.** Report it with its clause, the combination that
  governs and the engine's remedy direction.
- **Pipe moments.** The parametric assemblies carry pipe forces, not moments. If the
  restraint report has moments, the review raises a critical finding. Say so plainly and
  recommend a frame model, or confirm the restraint is a simple support.
- **Status words.** Stages read *pass*, *fail* or *manual check required*; the envelope adds
  `result_status` and `checks[]` (calculated, screening, manual check required, pointer only,
  not checked). Report a held stage or check with its reason, never as a pass. For the ASD
  wind guard, recommend the LRFD re-run.
- **Service versus strength.** Soil bearing, overturning and sliding are service-level
  checks. With LRFD and a gravity pier, the envelope runs those checks on the ASD
  combinations automatically. Tell the user.
- **Known engine behaviour** is listed in `references/code-basis.md`. Mention an item when
  the design is close to a limit in the element it affects.
- **Preset values are never silent.** Anchor and concrete values taken from a CSA preset
  are listed in the report's assumptions as not user-supplied and graded manual check
  required in one `preset inputs` row, as every ASSUMED item is in one `ASSUMED inputs` row;
  either holds the PASS banner. Replace the bond stress with the anchor ESR value before issue.
- **Anchor Category is never invented.** It is an ESR value. If the user has none, run with it
  unset (Category 3, conservative), report the finding and say what Category 1 or 2 would need
  to be confirmed; never enter a Category to make a design pass.
- **Weld strength uses kds = 1.0** (AISC J2.4(a)). The Eq. J2-5 directional increase is an
  opt-in of the weld engine for a linear group loaded through its centre of gravity; the
  assembly's welds all carry moment and never take it.

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as written without it. If its tools are present, call `verify_connector` once per session. `get_aisc_shape` returns shape properties. The other slots below are currently pointer-only: `get_pointer` says where to read the value (standard, edition, table, row key, columns) and never returns one, so the user still reads it from the AISC Specification tables, the ASCE Hazard Tool report or the anchor's ESR. Record the value the user reads in the spec's `code_values` block with `"source": "user"` and the pointer's citation ([field rules](references/spec-format.md#code_values)); a value the connector returns would carry `"source": "connector"`. A `code_values` error also exits 2, with a message and no verdict. On a pointer, an account or daily-limit message, any other error, or absent tools, use the basis interview, unchanged, and quote nothing new. In the summary, list every such value with its citation and source. A call sends only the standard, the row key and the designation. `get_pointer` takes `standard` (for example `AISC 360`) and `quantity`; the table's id is the `id` its result returns.

| Slot | Tool and id returned | Key fields | What comes back |
|---|---|---|---|
| AISC label (`columnShape`, `arms[].shape`) | `get_aisc_shape` | `designation`, for example W8X31, HSS6X6X3/8, PIPE4STD | dimensions and section properties. The engine reads its own embedded index and never calls the connector, so this is a cross-check of the label |
| `material.Fy`, `material.Fu` | `get_pointer`: `aisc360-22-fy-fu` | `specification`, `grade` | the location only |
| `SDS` | `get_pointer`: `asce7-22-sds` | `latitude`, `longitude`, `siteClass`, `riskCategory` | the location only (the ASCE Hazard Tool) |
| Anchor product values (`bondStrength`, `cac`, kc, spacing and edge limits) | `get_pointer`: `aci318-19-ch17-anchor-product` | `product`, `diameter`, `embedment`, `concrete` | the location only (the ESR) |

Soil values and the slip-critical pretension have no dataset; they stay with the geotech report and the bolt specification.

## Related skills in this pack

`load-case-builder` sets up the CAESAR II load cases that produce these restraint loads.
`stress-screening` hand-checks the piping. `iso-to-pcf` builds the model from the isos.
This skill starts where the stress analysis ends: at the support.
