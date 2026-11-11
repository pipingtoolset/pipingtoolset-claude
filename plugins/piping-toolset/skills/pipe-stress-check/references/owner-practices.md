# Owner practices on top of the code: PIP PNC00004, PNC00001 and RECE002

An owner practice sits **on top of** the code and applies only if the project invokes it. Ask;
do not assume. Cite as `PIP <number>, <Month YYYY> (<revision type>), section <n>`, state the
code edition the project adopted beside it, and open the practice before a clause goes into a
sealed calc: the section numbers below are pointers paraphrased from the user's copies and are
confirmed on the printed page. Practice types C, S, T, F and I bind when the contract invokes
them; type E guides are advisory unless the text says *shall*. PIP tables and figures are
copyrighted like ASME tables: the user reads them; nothing from them is reproduced here.

## 1. PIP PNC00004, piping stress design criteria (B31.3)

- **Which lines get formal analysis** (3.4.1, 3.4.2, 3.4.3): a stress-critical list (load- and
  stress-sensitive equipment, fired-heater and steam-generator piping, compressor and turbine
  piping, reciprocating machinery suction and discharge, pump nozzles above a size, air-cooled
  exchanger piping, relief systems, proprietary expansion devices, settlement, mixed-phase and
  slug flow, severe cyclic and vibrating service, jacketed, Category M, plastic-lined, and lines
  needing occasional-load support), plus temperature-versus-size screening charts that sort
  lines into visual, formal and comprehensive analysis. The list is not exhaustive; the charts
  are figures the user reads. Where invoked, this list overrides the code's exemption for every
  line it names: state the screening result for the line in the basis.
- **Modelling rules:** run with and without friction and take the governing result (3.2.3), with
  frictionless assumed only where the whole system is on rods or springs; model rod-hanger length
  and keep rotation within the stated limit in every condition (3.2.14.2); refractory stiffness
  for reactions only (3.2.12); a doubled unreinforced-tee SIF for non-90 deg branches absent
  better data (3.2.13.2); a support that lifts off between ambient and operating is removed for
  the sustained case or replaced by a spring (3.2.2.3); reduced flexibility at attachments on or
  within 2D of an elbow weld (3.2.13.1); a local crushing check on thin-wall lines (3.2.14.1).
- **Other mandatory cases:** relief-discharge thrust with a method the owner accepts (3.2.7),
  water hammer and slug flow (3.2.8), long-term settlement from the geotechnical report as a
  displacement case (3.2.9).
- **Sag limit** (3.2.11.1): a stated limit (16 mm, 5/8 in) used as the allowable deflection in
  the span screen unless the owner agrees a deviation in writing.
- **Cold spring:** prohibited on rotating-equipment piping without owner approval, and never
  credited in S_E (3.2.14.3, 3.2.14.4).
- **Nozzle loads** (3.3): rotating equipment per PIP RECE002; reciprocating compressors per API
  618; air coolers per API 661; vessels by WRC 107/297 within their limits, no curve
  extrapolation, otherwise FEA. The `nozzle-load` skill carries the checks.
- **Software code year** must match the contract edition and be stated (3.1.4); calc number and
  archiving per 3.5.

## 2. PIP PNC00001, pipe support criteria (B31.3, to 427 C / 800 F)

Governs support selection and attachments, which feed the model's restraint assumptions:

- Attachment and trunnion material by temperature band (4.2.1, 4.2.3); wear pads with a weep
  hole and a thickness limit (4.2.1.5, 4.2.1.6); no reinforcing pads at elbows unless specified
  (4.2.3.2); clamp material by temperature from its Table 1 (user-read), with the
  galvanized-on-stainless exception needing an isolation shield (4.2.2.2).
- Cold-insulated trunnions (4.2.4.6, 4.2.4.7); load-sensitive nozzles minimise weight and
  weight moment (4.2.5); vessel brackets close to the nozzle (4.2.6).
- Load cases and restraint obligations to state as run or dismissed: reciprocating compressor and
  pump piping restrained perpendicular to the axis regardless of an acoustic study, with
  clamp-type or hold-down supports and small-bore connections braced in two planes to the main
  line (4.2.10); acoustic-induced vibration (4.2.11); large OD (4.2.12); relief reaction
  (4.2.8); slug flow (4.2.9); momentum change and hammer (4.2.15).
- **Hydrotest** (4.2.14): if temporary supports are not provided, permanent supports carry the
  hydrotest case; where the hydro load exceeds twice operating on a spring, the spring maker
  designs for it or temporary supports are fitted.
- **Rod hangers** (4.3.3): swing within the stated limit, never in compression, not on lines
  subject to thermal bowing. The rod limit here differs from PNC00004's rotation limit: where
  both are invoked, design to the stricter and say why.
- **Springs** (4.3.6): individually sized with all design data submitted; variable springs only
  where installed-to-operating variation is within the 25 % limit; constant supports where
  variation is limited to 6 %, for large movement, or to cut nozzle loads.

## 3. PIP RECE002, piping loads on rotating machinery nozzles

- **When a calculation is mandatory** (4.1.1.3): NPS 3 and larger; above 300 F (150 C); at or
  below -150 F (-100 C); vital or sensitive machinery; a history of nozzle-load problems.
  Reciprocating or pulsating machinery also needs static, pulsation and mechanical analysis.
- **Loads to include** (4.1.1.5, 4.1.1.6): weight and contents, insulation, thermal including
  start-up, shutdown, clean-out and off-design, solar and radiant distortion, tracing,
  settlement and frost heave, restraint reactions, attached piping and shared headers; suction
  and discharge separately, then together; friction, two-phase flow, pulsation, wind, snow and
  ice, maintenance, steam-out and equipment supported by the piping where relevant. List each as
  included or dismissed.
- **Resolution point** (4.1.2): differs by machine (turbines at the exhaust flange per API 611
  or 612; compressors at the fixed end per API 617; pumps at the shaft and casing centreline
  intersection per API 610, each nozzle also satisfying its own limit; others per nozzle). A
  load reported at the flange face when the standard wants it elsewhere is a finding.
- **Lower-of rule** (4.2.1.2) and the **design-stage caps by machinery class** (4.2.2, 4.2.3):
  vital or sensitive at most 50 % of the industry allowables during layout; essential (spared)
  up to 100 %; its Table 1 fractions where the purchase standard gives no allowable (user-read).
  Ask the owner which class each machine is in and flag the answer ASSUMED if they do not say.
- **Layout** (4.3.1): no anchors or restraints within 10 pipe diameters of the nozzle unless
  specified; adjustable adjacent supports; strainers removable without temporary supports;
  **cold spring not permitted** (4.3.1.9), stricter than PNC00004. Deviations documented, and
  loads above the manufacturer's allowables accepted by the manufacturer in writing (4.3.1.7).

## 4. Other practices that touch a stress calc

| PIP | Use |
|---|---|
| PNSC0011 installation of B31.3 piping | what the field may build against what the model assumed: alignment, cold-spring gap verification, nozzle fit-up, spring travel stops |
| PNSC0021 leak testing | the hydrotest case: temporary supports, travel stops, equipment excluded, static head |
| PNF0200 vents, drains and instrument connections | small-branch geometry for the B31J SIF entry at vents, drains and taps |
| PNFJ8000 jacketed piping | analysis over all core and jacket temperature combinations; spacers are intermediate restraints |
| PNFS0001 pipe support details | nearly every detail says design load USER DEFINED: the drawings give geometry and material, not capacity, so the reaction is still checked against the member (`pipe-support`); U-bolt details are for uninsulated pipe only |
| VESV1002 vessels | nozzle local-stress limits and the WRC basis; flange external loads to UG-44(b) |
| INEG1000 / INSH1000 / INSC1000 insulation | insulation weight and wind OD; support spacing near flanges and elbows; cold vertical supports need approval |
| PLC00004 / PLC00005 | B31.4 / B31.8 facility segments only: do not import their SIF corrections or settlement treatment into B31.1 / B31.3 |

## 5. PIP-invoked projects: checks before issue

- No PNC00004 3.4.1 screening statement for the line.
- Friction not run both ways; sag limit not stated; rod-hanger rotation or swing unchecked.
- Software code year not stated; calc number missing.
- WRC curves extrapolated beyond their limits.
- Rotating-machinery nozzle loads: no RECE002 4.1.1.3 trigger statement; resolution point wrong
  for the machine; higher of OEM and standard used; a vital or sensitive machine checked at
  100 % instead of at most 50 % at layout; machinery class not declared; a restraint within
  10 D; any cold spring.
- Hydrotest case missing where permanent supports carry it, or a spring hydro load over twice
  operating with no travel stop or temporary support.
- Wear pad or trunnion material not matched to the temperature band; a repad at an elbow.
- A type E *should* cited as *shall*.
