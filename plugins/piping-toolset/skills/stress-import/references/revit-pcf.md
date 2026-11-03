# Route B: Revit / Fabrication PCF exports

Revit MEP (Fabrication Parts) exports a PCF per system. The export is geometry with the wrong
record vocabulary for a stress model, and it carries no supports. Everything below was
confirmed on data-hall and central-plant hydronic jobs against the Bentley PCF Translator's own
`.ntl` and `.pcflog` output and against CAESAR II's APCF importer.

## What is wrong with a raw Revit PCF

| Defect | Seen as | Fix (`pcf_prep.py` for AutoPIPE, `pcf2caesar.py` for CAESAR II) |
|---|---|---|
| Elements exported in more than one system file | hundreds of elements duplicated across files | De-duplicate on `REVIT-ID` + type + end points |
| Equipment bodies exported as piping | multi-port `UNDEFINED` chiller or pump bodies tying supply to return | Remove; their ports become equipment nozzles (anchors) |
| Shop and field welds, gaskets, bolt kits | 1/8 in `COUPLING` or `WELD` records; the translator makes weightless 1/8 in rigids of them | Fuse into the adjacent pipe (`fuse_rtypes`, `weld_match`) |
| Flanges as `COUPLING` / `COCP` (older exports) | weightless rigids, "Overlapping Components" in the pcflog | Retype `FLANGE` / `FLANGE-BLIND` with FLWN / FLSO / FLBL and a weight |
| Butterfly valves as `MISC-COMPONENT`, weight 0, an off-axis `CENTRE-POINT` | lug valves | Retype `VALVE`, strip the centre point, set the weight (`retype`) |
| Threaded nipples as `COUPLING` | | Retype `PIPE` |
| `ELBOW` with no radius | elbows at pump nozzles | `BEND` with the radius from geometry; flag below 1.0 D |
| Open joints of 0.005 to 0.13 in (gasket faces, 0.050 in typical) | the translator's 0.001 in tolerance leaves dozens of segments and auto-anchors | Heal joints up to `heal_tol_in`; fittings keep their coordinates, pipe lengths absorb the move |
| Continuation records `END-POSITION-OPEN`, `END-CONNECTION-PIPELINE` | one "could not map" prompt per record | Drop them; classify the ends yourself |
| Valve `WEIGHT 0.000` | weightless rigids | Weight table in the job, written to `WEIGHT` (and the translator's rigid-weight attribute) |
| No `SUPPORT` records | | Supports come from the NWC or the IFC (`bim-models.md`) and from rules (`support-rules.md`) |
| Non-fabrication accessories missing (strainers, control valves, meters, flex loops) | collinear gaps of 1 to 36 in | Bridge by NPS and gap length (`bridge.by_length`), weight from the submittal, label `VFY`: names in the NWC near a gap are often noise |
| Three-way and multi-port valves | a `VALVE` starting at a three-connection point, which AutoPIPE refuses | `three_way`: valve half A, a `TEE` at the centre, valve half B, a valve stub for port C |
| Schedule only in `ITEM-DESCRIPTION` | the translator defaults to STD and passes it to downstream fittings | Put a `SCH` token in every description (`desc_schedule_tag`) or set the default deliberately |
| A valve placed inside its own flange | overlapping components, false cut anchors | Re-seat it between the flange faces (`fix_overlapping_valves`) |
| Routing that differs from the contractor's fabrication model | more than half the spools 12 in or more off | Confirm **which model is the basis** before building; a PCF of the wrong model is wasted work |

## Which builder

| Target | Script | Job file | Output |
|---|---|---|---|
| AutoPIPE (Bentley PCF Translator) | `scripts/pcf_prep.py job.json` | `scripts/examples/revit-to-autopipe.job.json` | one AutoPIPE-ready PCF per analysis model, support list, bridged-items list, report |
| CAESAR II (APCF) | `scripts/pcf2caesar.py job.json` | `scripts/examples/revit-to-caesar.job.json` | one PCF per line plus a combined PCF in walk order, support list, report |

Both are standard-library Python driven by one job JSON per analysis model. Both split pipes at
support points so every support sits on a node, never move fitting geometry except by a logged
heal, and write CRLF. Read each script's docstring for the full key list; the example job files
carry one placeholder value per key, to be replaced from the project.

Steps the CAESAR II builder logs, in order: load and de-duplicate, keep what lies inside
`box_ft`; remove equipment bodies and record their ports as nozzles; split the network by
connectivity; drop small bore below `small_bore_max`, drop `WELD` and `END-*` records, `ELBOW`
to `BEND`, `COUPLING` to `PIPE`, placeholder SKEYs to CAESAR II-proven ones; assign each element
to a line from its source file, propagating shared stubs by connectivity; classify open ends
(equipment nozzle, box cut, job override, else free); place supports by rule and merge BIM
seeds; split at supports; emit per-line and combined PCFs.

Do **not** write `SPECIFIC-GRAVITY` into the pipeline attributes for CAESAR II (see
`caesar-apcf.md` section 1): the neutral file holds a density, not a specific gravity.

## Record set the importers accept

`PIPE`, `BEND` (SKEY BEBW, `ANGLE` in centidegrees, `BEND-RADIUS`), `TEE` (TEBW), `OLET`
(TERF for fabricated branches; `CENTRE-POINT` on the header, `BRANCH1-POINT`),
`REDUCER-CONCENTRIC` (RCBW; an eccentric written as concentric keeps its offset ends and is
logged), `FLANGE` (FLWN, FLBL for blinds and caps) and `VALVE` (VVFL) as rigids with `WEIGHT`,
`SUPPORT` with `CO-ORDS`, `SKEY`, `SUPPORT-DIRECTION` and `NAME`. A cap is emitted as a
`FLANGE` FLBL rigid with its weight rather than a pipe stub: it imports as a closed end, not a
free end, and carries the weight. The AutoPIPE translator also takes `HANG` (rod-hanger
V-stop) and `MISC-COMPONENT` / `SP` stand-ins (`autopipe-translator.md`).

## What the Revit PCF cannot tell you

Design temperature and pressure (the schedules and the mechanical specification), insulation
(the insulation specification section), the code (hydronic building services are often B31.9
by specification; the analyst may choose B31.3 or B31.1, and the edition is an input), the
equipment behind each nozzle (read the schedule and the plan), hanger attachment (deck or
mezzanine steel), and whether a supply-to-return cross-link is a real bypass or a mislabel
(check the P&ID). Each goes in the handover as ASSUMED or VFY.
