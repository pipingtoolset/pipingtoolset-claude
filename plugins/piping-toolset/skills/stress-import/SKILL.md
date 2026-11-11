---
name: stress-import
description: "Get a piping model into CAESAR II or AutoPIPE with every support on a node: PDF stress isometrics built as a validated PCF, Revit PCF exports cleaned, Navisworks NWC hangers mined and snapped, the CAESAR II neutral file repaired after APCF import, the AutoPIPE translator and its crashes handled. Use on any PCF import, orphan nodes, missing hangers, node numbering, NTL or E751 errors."
compatibility: Method and review guidance only; this edition has no scripts
---

> **Directory edition: method and review guidance, no calculation scripts.**
> This edition ships without the Python scripts of the full plugin, so nothing in it is run as a
> program. Wherever the text below or a reference file names a script, a module id or a path under
> `scripts/`, read that as a description of the method and not as a command.
>
> 1. Work each calculation by hand from the method in the reference files, and show every equation,
>    input, unit and intermediate value.
> 2. Head every numeric result `HAND CALCULATION, NOT ENGINE-VERIFIED` and give it the result status
>    `screening`. Report each ratio as within or exceeds. Write no PASS, OK or issue-grade wording.
> 3. The builders and converters named below (PCF, neutral file, load case tables) are not in this
>    edition. Give the method and the checks; write such a file only as plain text the user can
>    review line by line, and say it has not been through the validator.
> 4. Tell the user once that the fixture-verified engine is in the full plugin on GitHub
>    (pipingtoolset/pipingtoolset-claude) and in the calculators at pipingtoolset.com. Those scripts
>    are not available from this edition.


# Stress import: piping source to an analysis-ready model

Four sources, two targets, one method. The source decides how the centreline is built; the
target decides the record vocabulary and the post-import repair; the method is the same every
time: **compute each coordinate once, never move geometry, put every support on a node, and
prove the file with an independent check before anyone opens it in the analysis program.**

A PCF that imports badly is almost never wrong about the pipe. It is wrong about the joins:
independently rounded ends, weightless weld rigids, flanges written as couplings, zero valve
weights, no supports. This skill fixes those in a script, never in the importer's tolerance and
never by hand.

## 1. Pick the route

| Source the user has | Route | Read |
|---|---|---|
| PDF stress isometrics | **A**: transcribe to a walk spec, `build_pcf.py` builds it in exact fractions, `validate_pcf.py` proves it | [reading-isos.md](references/reading-isos.md), [spec-format.md](references/spec-format.md) |
| Revit / Fabrication PCF exports | **B**: de-duplicate, re-vocabulary, heal joints, add supports by rule and from BIM (`pcf2caesar.py` or `pcf_prep.py`) | [revit-pcf.md](references/revit-pcf.md) |
| Navisworks NWC (hangers, trapezes, stands) | **C**: `nwc_supports.py` mines them; the builder snaps them to the centreline | [bim-models.md](references/bim-models.md) |
| IFC fabrication model, no PCF of the governing model | **D**: recover ports from the meshes, rebuild fitting by fitting (method only; the detector is not shipped) | [bim-models.md](references/bim-models.md) |
| A job that imported badly (.CII, NTXT, OUT, NTL, .wrn) | **E**: audit and repair the neutral file or the NTL | [caesar-apcf.md](references/caesar-apcf.md), [autopipe-translator.md](references/autopipe-translator.md) |

| Target | Vocabulary and post-import | Read |
|---|---|---|
| CAESAR II (APCF) | `PCF_RES_MAP` / `PCF_SIF_MAP`, neutral-file repair with `fix_cii.py` | [caesar-apcf.md](references/caesar-apcf.md), [caesar-import.md](references/caesar-import.md) |
| AutoPIPE (Bentley PCF Translator) | translator settings, `ap_bendcheck.py` before, `fix_closures.py` after | [autopipe-translator.md](references/autopipe-translator.md) |

Before building anything, settle **which model is the basis**: on one job the engineer's
Revit PCFs differed from the contractor's fabrication model by over 12 in on most spools, and
the first build was thrown away. A model the user sees in a viewer is the contractor's model.

## 2. Basis interview, then ask with cards

Read the drawings, the specification and the analyst's notes, then ask the decisions that
change the build, in one round where possible:

- **Code and edition.** Hydronic building services are often B31.9 by specification; the
  analyst usually chooses B31.3 or B31.1. The edition is an input, never a default.
- **Design P and T per line** (the schedules); installation temperature; fluid and density.
- **Vertical axis and units.** PCF is Z-up by convention; Y-up Isogen output is why third-party
  PCFs come in lying on their side. Route A writes mm (bore NPS x 25.4), routes B to D inches.
  Say the convention back to the user.
- **Models to build** (one per system pair), the analysis box, small-bore limit.
- **Support basis:** BIM hangers plus rule fill, or rule only; the span table and vertical
  limit **from the project specification** (never from memory).
- **Nozzle treatment** (anchor both nozzles unless told otherwise), node bands per line, rigid
  weights (vendor or fabrication-model weights on every rigid).
- **The SKEYs the site emits.** Harvest them from one of the user's own Isogen or Revit PCFs.
- **Project basis record.** If a `pipingtoolset.project-basis/1` record exists (an earlier
  skill run this session, or a file the user names), reuse it: ask only for what is missing,
  never relabel a field, and pass it as `--project-basis <file>`
  ([format](references/project-basis.md)). Its ASSUMED items head the report.

Record every answer. Everything not answered is ASSUMED in the handover, never silently filled.

## 3. Build

Standard-library Python 3.9+. The scripts make no network calls and nothing from the drawings
or the model leaves the user's machine. Script paths are relative to this skill's directory:
call them by full path from wherever the session is working, do not change into the skill
folder (in Cowork it is a read-only mount and the working directory is the outputs folder), and
write every job file and output to the working directory so the user can open them.

| Script | Role |
|---|---|
| `scripts/build_pcf.py` | Route A: JSON walk spec to PCF plus build report (closure checks, BOM reconciliation, ASSUMED list) |
| `scripts/validate_pcf.py` | Checks any PCF, including third-party exports: connectivity, zero-length elements, off-line supports, unsafe records, bore jumps, CRLF |
| `scripts/pcf_lib.py` | Exact-fraction geometry and emitters behind the builder |
| `scripts/pcf2caesar.py` | Route B to CAESAR II: Revit PCFs to one PCF per line plus a combined file, supports by rule and from BIM, walk order |
| `scripts/pcf_prep.py` | Route B to AutoPIPE: one translator-ready PCF per model, fused welds, healed joints, flanges, weights, attributes 1 to 9, supports |
| `scripts/nwc_supports.py` | Route C: supports and in-line items out of a Navisworks NWC, no Navisworks needed |
| `scripts/pcf_check.py` | Pre-import checks on any PCF: pieces and their anchors, free ends, zero-length and sliver parts, supports off node, bend legs, bore jumps, spans over the table |
| `scripts/plot_pcf.py` | Plan and two elevations as SVG with supports coloured by type; look at it |
| `scripts/ap_bendcheck.py` (+ `ap_pcf.py`) | Predicts AutoPIPE E726-15 and W726-8 on a PCF or NTL before the translator runs |
| `scripts/ntl_closures.py`, `scripts/fix_closures.py` | Lists loop closures in a translated NTL; moves them off flange and valve points (the E751-1 crash) |
| `scripts/cii.py`, `scripts/fix_cii.py`, `scripts/verify_cii.py` | Route E: node bands per line, per-line T/P, fluid density and anchor codes in the CAESAR II neutral file, with an independent proof |
| `scripts/examples/` | `demo-line.json` and `minimal-proven.json` (route A), `revit-to-caesar.job.json`, `revit-to-autopipe.job.json`, `nwc-families.example.json`, `lines.example.json` (route E) |

**Route A.** Read the drawing in this order: title block and notes, continuation references,
dimension chains, bill of materials, supports; use the text layer and image zooms together, and
a dimension whose arrows you have not seen is one you have not read. Transcribe to a walk spec
with dimensions exactly as printed (`"13.7/8"`, never a decimal); every stated coordinate is a
`check`, every unreadable item goes in `assumed`. Then
`python scripts/build_pcf.py spec.json -o line.pcf --report line-report.txt` (exit 0 clean,
2 a closure or BOM check failed, 1 the spec is defective) and
`python scripts/validate_pcf.py line.pcf --skeys <site list>`. The builder carries dimensions
as `Fraction`, runs one cursor so adjacent components share a coordinate, computes bend
tangents from corners, interpolates sloped runs on elevation profiles and refuses off-line
points and zero-length elements. Never edit coordinates by hand: fix the spec and rebuild.

**Routes B to D.** One job JSON per analysis model, then the builder for the target. The
non-negotiables, whatever the route: geometry is never moved (splits add nodes on the existing
centreline; the only permitted moves are logged heals, each listed with its size); one PCF per
line so per-line T/P import, plus a combined file as the connectivity fallback; main run first
and branches after, so the importer numbers nodes in sequence; only record types the importer
has been seen to accept, rigids with `WEIGHT`, caps as FLBL rigids; supports per
[support-rules.md](references/support-rules.md), each split onto a node and named
`<prefix>-<TYPE>_<line><nnn>` so the restraint map reads it and the tag survives into the
analysis; small bore below the limit dropped and counted; buried pipe cut at the box with a
virtual anchor.

## 4. Check before anyone imports

Run `scripts/pcf_check.py file.pcf --span-table "<NPS:ft,...>" --vert-max-ft <ft>` on every
PCF. A hard failure (an unanchored piece, a zero-length element, a support off node) means the
file is not delivered. Spans are measured along the shortest path through tees, the way a
reviewer walks them; a degree-2 walk misses the crossover spans. Without a span table from the
specification the span check is skipped and the output says so.

Then an **independent check with its own parser** (it must not read the builder): component
counts by type and size against the source, rigid weight total, line split (supply + return =
combined), supports on nodes and BIM hangers placed, equipment ends, connectivity, maximum
geometry move with its exceptions, CRLF. Its report is a deliverable. It names rather than
fails on model-only tee points, Revit 1/16 in elbow leg differences, intentional temperature
zones and coordination gaps in the source.

`scripts/plot_pcf.py file.pcf file.svg "<model>" --floors <ft,...>` draws the model. A floor
stand floating 8 ft above its slab is obvious in the picture and invisible in the counts.

For AutoPIPE, run `ap_bendcheck.py` on the PCF: target networks as expected, near-miss pairs 0,
E726-15 0, W726-8 0.

## 5. The import (the user runs the program; the skill supplies the recipe)

Deliver file locations and stop. Do not drive the analysis program unless asked.

- **CAESAR II:** [caesar-apcf.md](references/caesar-apcf.md) sections 1 to 3 give the APCF
  settings, the restraint-map block (`ANC`, never `+ANC`), the SIF map and the job-naming rules.
  Ask for the NTXT and OUT back.
- **AutoPIPE:** [autopipe-translator.md](references/autopipe-translator.md) gives the settings
  (tolerance 0.01 in, no auto-anchors, no rigid flanges, attribute mapping 1 to 9). Before the
  NTL is opened, run `ntl_closures.py` then `fix_closures.py`, and scan the cards. When it
  crashes, ask for the MSG and CHK or a screen recording and read the on-screen error before
  bisecting.

## 6. Repair the CAESAR II neutral file (route E, and after every APCF import)

APCF numbers every file from 10 and cannot carry per-line T/P from a combined PCF, so the
imported model always needs one pass:

```
python scripts/fix_cii.py COMBINED.CII fixed.CII node_map.csv lines.json
python scripts/verify_cii.py COMBINED.CII fixed.CII node_map.csv lines.json   # must print PASS
```

`lines.json` names each line's PCF, start node, band end and T1, plus the increment, P1,
insulation and the fluid **density** (water 0.03611 lb/in^3; the neutral file holds a density,
not a specific gravity, and 1.0 there is 27.7 x water). Elements are assigned to lines by
matching both end nodes to the line's PCF points, then renumbered in element order so numbers
rise along each run. Anchors imported as code 6 (from `+ANC`) become code 1. Bends, restraints,
SIFs, rigids, reducers and COORDS follow the renumbering; `verify_cii.py` proves geometry,
pointers, tags and the unchanged sections byte for byte and exits 1 otherwise. Keep every band
below 9999 so the model can still be translated to AutoPIPE.

## 7. Audit the OUT / NTXT and hand over

Read the OUT for errors (target 0) and the warning catalogue, code and edition, node bands,
restraint types and tags, T1/P1 per line, walls and material, the centre-of-gravity report
(hand-check the fluid weight: bore area x length x density), the bill of materials against the
PCF, allowables (flagged VERIFY against the user's copy of the table, never reproduced) and the
intersection SIF table.

The handover ([support-rules.md](references/support-rules.md), "Handover note") states what
was modelled, what was assumed, what moved, every SKEY and record substitution, what the PCF
cannot carry ([caesar-import.md](references/caesar-import.md)), what the analyst still sets, and
a numbered list for their judgement. Route A also delivers the build report, the validation
output and the report's `Result status` line verbatim; while it reads `manual check required`
or `assumed`, nothing is issued. A PCF and a repaired neutral file are geometry, components and
restraints. They are not the load case set and not a code check, and the note says so.

## Components, SKEYs and supports

SKEYs drive how CAESAR II classifies a component, its SIF treatment in particular, through the
site's `PCF_SIF_MAP`. An invented SKEY imports as an unrecognised item. Use SKEYs harvested from
the user's own PCFs; for a type the site list leaves open, use the nearest confirmed SKEY in
the same family, keep the true identity in the description, and tell the user. Rigids take a
weight: hand-corrected weights after import are the review finding this skill exists to
prevent. Supports carry their restraint by SKEY and direction (`ANCH`, `SKID` + `UP`, `GUID`
with both sides, `SPRG`) or by `NAME` through the restraint map, and every support sits on the
modelled centreline: a "support offline at ..." note is dimensioned to the steel, so model it
at the pipe station and keep the note in the description.

## With the Engineering Data connector

The Engineering Data connector is optional and separate from this plugin; this skill works as
written without it. If its tools are present, call `verify_connector` once per session;
`get_skey_map` answers without an account and returns Piping Toolset's SKEY vocabulary
(`scope` `isogen`) and the CAESAR II-safe record set (`scope` `caesar-safe`), not the user's
site list: a SKEY harvested from the user's own PCFs always wins. A SKEY taken from the map goes
in the spec's `skeyOverrides` ([format](references/spec-format.md#skeyoverrides)), is recorded
as connector-supplied in the handover with the scope and group it came from, and is checked
against the site's own output before issue. On an error or absent tools, use the SKEY rules
above, unchanged. A call sends only `scope` and `component`, never the drawing, the model or
the spec. The scripts themselves make no network calls.

## Lessons that were paid for

- `SPECIFIC-GRAVITY 1.0` in a PCF became 1.0 lb/in^3 in CAESAR II. Read the CoG report first.
- `+ANC` in the restraint map is not an anchor. Check restraint types in the NTXT.
- Job names with periods hang the conversion. Work locally, not on a synced cloud folder.
- Grooved bridging without excluding housings collapses every coupling to zero length.
- Strut trapezes sit below the pipe, clevis hangers on the centreline; a wrong sign snaps BIM
  hangers to the wrong tier.
- Olet header points must be connection points in a connectivity check, or every branch is
  its own piece.
- AutoPIPE crashes on a loop closure at a flange or valve point (E751-1); CAESAR II does not.

## Related skills in this pack

Once the model is in, `load-case-builder` builds the static load case set and
`pipe-stress-check` hand-checks the results, reviews the run and supplies the allowables and
SIF-source judgement; `nozzle-load` judges the loads at equipment; `pipe-support` checks the
support steel. This skill produces geometry, components and restraints only. It never selects
allowables, SIFs or load cases, and it contains no code table values.
