# Cold-eye review of a stress analysis or a calc package

A calc package fails review for **traceability** far more often than for arithmetic. In a set
of reference packages that all came back "rejected, resubmit", not one headline defect was a
stress over its allowable. They were: a checklist copied from another calc, a restraint report
run from a `_TEST` job instead of the archived model, the no-friction sustained case
transmitted to civil where the load-case matrix named the with-friction one, a node bubble on
the iso that is not in the model, hanger boxes from an earlier run, gaps modelled against the
design criteria and not shown on the iso, a line assigned to the calc but never analysed, an
approval stamp by the originator with no independent check. Every one is detectable from the
files. The checker's job is the judgement on top.

The reviewer is the **checker**, not the approver: produce findings and a recommendation; the
engineer of record signs. The package is read-only; write the register outside it.

## 1. Inventory and confirm scope

Read the inventory back in two lines: the archived model chosen (and any `_TEST` or extra
jobs), the iso set, the checklist, the report, the civil load matrix, the line list, what is
missing. A typical EPC package: line list (the source of record for P/T, insulation and scope),
P&IDs, pipe specifications, stress isometrics and report (restraint summary, civil load-case
matrix, raw isos, PCF files), equipment data (GA and vendor nozzle data), calculations (the
archived model, configuration file, local-stress runs), communications, the firm's stress
checklist form, and the project's piping stress design criteria (DSC) at its current revision.

## 2. The traceability chain a reviewer walks

State each link in the register, with the evidence (file, sheet or page, node, values):

1. Every report (restraint summary, hanger table, displacements) was run from the **archived**
   model: same job name, date after the last input save. A `_TEST` job in a report header is a
   finding.
2. The civil transmission uses the cases the project's civil load-case matrix names (hydro,
   wind and no-wind, maximum design, the sustained case **with** friction, the pure occasional
   cases). A substituted case is a finding.
3. Every node bubble on the stress iso exists in the model at the support it marks; every spring
   box value (rate, cold load, hot load, travel, size) equals the model output, not an earlier
   run; travel transcribed to the wrong rounding is a finding.
4. Model temperatures and pressures follow the line list and the DSC condition definitions
   (for example T1/P1 maximum operating, T2/P2 design, T3 minimum); the hydrotest basis is cited
   to the code's test-pressure paragraph.
5. Modelled gaps, non-default stiffness and friction follow the DSC; any gap that is modelled is
   dimensioned on the iso.
6. Lines the line list assigns to the calc number are all in the package.
7. The checklist header names this calc, and its answers agree with the model (springs present
   means the spring item is not N/A).
8. The approval stamp is backed by an independent checker in the checklist.

## 3. Run the hand checks on the governing nodes

Use the modules in `tool-reference.md` on the nodes the report says govern: the displacement
stress range with the user-read SIFs and `it`, the sustained and occasional ratios, f and N_E
from the stated cycles, spring variability for every spring, the span screen where supports look
sparse, the exemption only where it was claimed. Every allowable is read by the user from the
project edition and cited on the sheet; the review recomputes with the same inputs and reports
any difference as a finding with the two numbers side by side.

## 4. Severity, kept consistent across offices

| Severity | Meaning | Examples |
|---|---|---|
| **critical** | the calc could be non-compliant, unsafe or unverifiable | node tags that do not exist or point at the wrong support; lines assigned to the calc not analysed; geometry more than 3 in off at supports or nozzles; results not from the archived model; no independent check behind an approval stamp; the wrong equation generation for the edition |
| **major** | rework required | DSC deviations (gaps, friction, ambient and minimum temperatures, P/T not per the line list, hydro basis); hanger data differing from the model; wrong civil load cases; placeholder nozzle allowables (identical in all six components, or exactly half of another nozzle); liftoff not evaluated; checklist answers contradicted by the model; f or k or the SIF source wrong for the edition |
| **minor** | documentation | stamp and date format, rounding, missing listings, naming |
| **observation** | information, good practice, items to confirm | |

## 5. Recommend a verdict

**Accepted**; **Accepted as noted** (minors and observations only); **Rejected, resubmit** (any
critical, or majors that change results); **Cannot verify** (insufficient inputs: the model or
the iso did not load, or more than a quarter of the checks could not run). Never recommend
acceptance while a critical is open or coverage is insufficient.

## 6. Satellite-office defect patterns, in order of frequency

Checklist copied from another calc and not adapted, or answered without the model evidence;
report run from a different job or date than the archived model; hanger boxes from an earlier
run; construction gaps and non-default stiffness modelled and not noted on the iso; friction
missing or non-standard (an outlier coefficient, frictionless away from nozzles); ambient and
minimum temperature not per the DSC; T1/P1 at normal instead of maximum operating; placeholder
nozzle limits; merged reference models with unnamed anchors, duplicate trains and zero-weight
rigids; a self-signed stamp; lines on the line list for the calc but not in the package.

## 7. Modelling findings from the rejection catalogue

- **Load cases.** Only SUS and EXP run, no OCC at all; hydrotest missing on vapour lines; no
  installed (cold) case, so liftoff and spring travel are unverified; the operating case run but
  no separate sustained case with springs at hot load, so S_L is contaminated by thermal; relief,
  surge or slug cases missing on relief headers; upset and alternate cases (steam-out,
  regeneration, spare-pump idle, single-train, startup bypass) missing.
- **Thermal range.** The expansion case run operating-to-operating rather than from the
  installation temperature to each extreme; a line that goes both above and below ambient
  analysed for one direction only; installation temperature assumed 70 F on a winter or
  summer erection with no sensitivity; outdoor ambient extremes ignored; several thermal cases
  run but only the worst reported with no proof it is the range-governing one.
- **Supports and restraints.** Rest supports modelled +Y but detailed as welded shoes, or the
  reverse; friction omitted on long runs (anchor and guide loads under-predicted); guides and
  stops with no corresponding steel, or steel assumed rigid; springs with liftoff, bottomed-out
  travel or over-limit variability accepted; support loads never transmitted; table spans used
  with concentrated loads; no support at or next to heavy in-line items.
- **SIFs.** Legacy Appendix D under an edition that deleted it; in-plane and out-of-plane
  transposed at tees; a single SIF on all three legs; sustained indices confused with expansion
  SIFs; no SIF at fabricated tees, sockolets, threaded joints or fillet-welded attachments; a
  pad modelled with no pad thickness; a SIF below 1.0 accepted from software.
- **Cold spring.** Taken as a stress credit; shown on the iso with no fabrication procedure,
  gap dimension or hold point; assumed achieved at 100 %.
- **Documentation.** Code edition not stated; software version, code year setting and units not
  recorded; allowables with no table, material, grade, form and temperature; the input iso not
  reconciled with the issued revision; nozzle allowables cited with no vendor data attached;
  no basis for the allowable sag or bending stress behind a span; flange leakage not addressed
  on a hot or Category M line.

## 8. The stress iso

The iso is the contract between the analysis and the field: every support, spring, anchor and
boundary on it traces to a node in the archived model, and every number in a hanger box is the
number in that model's output. Expect an axes triad, node bubbles at every restraint, spring
and equipment anchor (plus tees and in-line rigid ends where the office convention is "full"),
support tags verified against the model, restraint symbols and add/change callouts for new or
changed supports, spring hanger data boxes, displacement callouts above the project threshold
(value and load case), and the stress stamp (calc number, revision, date, initials). Read the
markups back against the model, node by node, before the bubbles tab of the register is signed.

## 9. Deliver

The findings register (severity, finding, evidence, required action, status), the verdict
recommendation, and, if asked, a short transmittal to the originating office: verdict, the
criticals and majors as numbered actions with evidence, what to resubmit. Stage it as text for
the user to send. Findings cite evidence; ASSUMED items say so; no tabulated code value is
reproduced in a finding: cite the table, material and temperature for the checker to read.
