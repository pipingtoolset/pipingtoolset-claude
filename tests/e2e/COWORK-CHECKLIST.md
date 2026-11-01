# Cowork manual test script

A manual check that the PipingToolset plugin works inside Cowork. It takes about an hour. You do not need to
type any commands yourself: you paste prompts into a Cowork chat and watch what happens.

A run passes only if both are true: every pass check in its row is met, and the PipingToolset skill named in the
prompt is the one that triggered (not another installed skill on the same topic). The skill name shows in the
chat as the skill is loaded; if a different skill answers, mark the run as failed and note which one.

## 1. Install

1. Download `piping-toolset.plugin` from the latest GitHub Release of this repository.
2. Open a new Cowork chat and drag the file into it. Choose **Accept** when Cowork asks to add the plugin.
3. Marketplace route instead: add this repository as a plugin marketplace in Cowork's plugin settings, then install
   PipingToolset from the list. The README describes both routes.
4. Start a fresh chat after installing so the skills are loaded.

## 2. What to check first

- Open the skills menu. The seven skills should be listed under the PipingToolset display name:
  Pressure Design, Stress Screening, Load Case Builder, Iso to PCF, Pipe Support, Nozzle Load,
  Bolted Flange.
- If a skill is missing, stop and record which one in the results table. Do not continue to the runs.

## 3. Runs

Paste the prompt exactly as written into a fresh chat for each run. Script evidence means a python command that you
can see in the tool log or the expanded steps of the chat. If the numbers appear but no python command ran, the run
fails: the skill must run its script, not do the arithmetic in its head.

| Run | Prompt to paste | Skill that must trigger | Script ran: look for | Output file in the outputs folder | Pass checks |
|---|---|---|---|---|---|
| E1 | `Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?` | Pressure Design | a python command running pressure_design.py with the pipe data | none (answer in chat) | runs the script (not mental math); t = 0.13650, tm = 0.19900 (hand: 750·6.625/(2·(17900+750·0.4)) = 4968.75/36400); compares 0.280·0.875 = 0.245 ≥ 0.19900 → adequate; echoes S/E/W/Y as user-supplied; cites ¶304.1.2 Eq. (3a); does not volunteer any table value |
| E2 | `Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.` | Pressure Design | none expected: this run must refuse, so check that no number was computed or quoted | none | refuses to state a value; names B31.3 Table A-1 (A-1C in 2024), material row and temperature columns; offers to interpolate once the user reads the two values |
| E3 | `Use the stress screening skill. B31.3-2022 line, 7,000 equivalent full cycles over life? Actually it's about 20,000 cycles. Ferrous material, SMTS below 75 ksi (from my spec), max metal temp 500 F, Sc = 12000 psi and Sh = 11000 psi from my copy. What is S_A and which f equation applies?` | Stress Screening | a python command running stress_screening.py (fatigue-factor, then displacement-stress or the S_A arithmetic) | none (answer in chat) | uses the 2022+ form f = 20·N^-0.333 (not 6.0·N^-0.2); f ≈ 0.7392 for N = 20,000; applies the ferrous cap logic correctly; S_A = f·(1.25·Sc + 0.25·Sh) = f·17750 ≈ 13,122 psi; flags the liberal allowance as optional only where permitted |
| E4 | `Use the stress screening skill. B31.3-2024 project. Which document gives the SIF for a welding tee and can I use Appendix D?` | Stress Screening | optional: stress_screening.py basis --code B31.3 --edition 2024; no SIF value or formula may appear | none | B31J governs (App D deleted from B31.3-2020 on); does not give any SIF formula or value; warns about in-plane/out-of-plane transposition at tees |
| E5 | `Use the stress screening skill. Quick exemption check, B31.3: 4 in. line, OD 4.5 in, total displacement to absorb 1.2 in, developed length 40 ft, straight-line distance between anchors 30 ft. S_A = 25000 psi and Ea = 1.5e7 psi from my copy.` | Stress Screening | a python command running stress_screening.py with the flexibility-exemption check | none (answer in chat) | runs screen.flexibility-exemption; D·y/(L−U)² = 4.5·1.2/100 = 0.054; K1 = 30·25000/1.5e7 = 0.05 → ratio 1.08, exceeds, formal analysis required; lists the exemption's stated limitations |
| E6 | `Use the load case builder skill. B31.1-2024 steam line, one operating state, CAESAR II 2019, springs designed by CAESAR, wind ±X ±Z, no seismic, with and without friction. Build the load case set.` | Load Case Builder | a python command running loadcase_gen.py with a spec file | load case output files in the outputs folder, if the skill writes any | runs the generator; hanger cases are W (Rigid) and W+T1 (Ignore); states no ASD reduction under B31.1-2024; k-factor 1.15/1.20 with duration basis requested; extraction matrix present |
| E8 | `Use the iso to pcf skill. This PCF imports into CAESAR II with an orphan node. Why? UNITS-CO-ORDS MM / PIPE END-POINT 0 0 0 6 END-POINT 1000 0 0 6 / PIPE END-POINT 1000.4 0 0 6 END-POINT 2000 0 0 6` | Iso to PCF | a python command running validate_pcf.py on the pasted PCF text saved as a file | none required (the finding is in the answer) | runs validate_pcf.py on the file rather than eyeballing it; reports a FLOATING start 0.4 mm from the previous end; explains independent rounding as the cause; recommends rebuilding from the drawing, not hand-editing coordinates |
| E9 | `Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.` | Pipe Support | a python command running support_calc.py with a spec.json, using the --report and --json options | calc.md and result.json in the outputs folder | confirms the D/T/W/Eh mapping before running; runs support_calc.py; reports the governing stage, check, combination and clause from the run (not mental math); reports that no Anchor Category was given, so ACI CODE-318-25 Category 3 was taken and the anchorage fails, and asks for the ESR Category instead of inventing one; presents the optimizer table from the run and recommends one option with its trade-off; says pipe moments are zero so the parametric model is valid |
| E10 | `Use the pipe support skill. What's the bond strength for a Hilti HIT-HY 200 in cracked concrete? Just use a typical number.` | Pipe Support | none expected: this run must refuse, so check that no product value was supplied | none | refuses to supply a product value; asks for the ESR tau_cr / tau_uncr; explains the engine flags ACI generic defaults |
| E11 | `Use the nozzle load skill. B31.3 line into an API 617 centrifugal compressor (Part 2), discharge nozzle NPS 12. Operating loads at the nozzle in the nozzle axes from CAESAR II: Fx 600, Fy 600, Fz 600 lbf; Mx 1000, My 1000, Mz 300 ft-lbf. Use the Annex E per-connection equation, coefficient 927 per my copy. Does it pass?` | Nozzle Load | a python command running nozzle_load.py with connections.nema-sm23 | none (answer in chat) | runs connections.nema-sm23 with coefficient 927 given as an input (not a default); De = (12+16)/3 = 9.33333; FR = 1039.23 lbf, MR = 1445.68 ft-lbf, 3FR+MR = 4563.37 against 927·De = 8652 → ratio 0.5274 PASS; asks for or flags as ASSUMED the axis mapping and the resolution point; notes the combined-resultant check at the largest connection and the vendor's tabulated allowables as items to confirm |
| E12 | `Use the nozzle load skill. Pressure vessel, VIII-1, carbon steel, no API standard applies. What are the PVP2011 Table 1A allowable loads for an NPS 6 nozzle? Just give me the numbers.` | Nozzle Load | none expected: this run must refuse, so check that no table value was quoted | none | refuses to state any table value; names the paper (ASME PVP2011-57100, Koves et al.), Table 1A, the NPS 6 row and the six components; asks for actual vessel thickness, shell and neck allowables at design temperature and the class; explains the thickness and material scaling it will apply once the user reads the row |
| E13 | `Use the bolted flange skill. Flange screen: design pressure 500 psig, external bending moment 50,000 in-lb and axial tension 2,000 lbf at the flange from CAESAR II, gasket reaction diameter G = 6.0 in, B16.5 rating at design temperature 1975 psig from my copy. Run the pressure-equivalent check.` | Bolted Flange | a python command running bolted_flange.py with connections.flange-equivalent-pressure | none (answer in chat) | runs connections.flange-equivalent-pressure (not mental math); moment term 1178.93 psi, force term 70.74 psi, Pe = 1749.66 psig, utilization 0.886 PASS; states the screen is a leakage screen not a stress check, that compression would not be credited, and what the detailed VIII-2 4.16 step adds; records the rating as user-supplied with its table line |
| E14 | `Use the bolted flange skill. What's the B16.5 Class 300 rating for Group 1.1 at 500 F, and the m and y for a spiral-wound gasket? Just give me the numbers.` | Bolted Flange | none expected: this run must refuse, so check that no rating or gasket factor was quoted | none | states no rating and no gasket factor; names the B16.5 pressure-temperature rating table for Group 1.1 by edition and the VIII-2 Table 4.16.1 gasket factors (suggested values); offers to interpolate the rating once the user reads the two adjacent temperatures |

For a drawing-to-PCF run (E7 in PROMPTS.md, optional here) the expected output file is `line.pcf`, with its report
text file beside it, both in the outputs folder.

## 4. Record

Fill in one row per run. Use P for pass, F for fail.

| Date | Cowork version | Run | P/F | Skill triggered correctly (Y/N) | Script ran (Y/N) | Notes |
|---|---|---|---|---|---|---|
|  |  | Install |  | n/a | n/a |  |
|  |  | Skills menu |  | n/a | n/a |  |
|  |  | E1 |  |  |  |  |
|  |  | E2 |  |  |  |  |
|  |  | E3 |  |  |  |  |
|  |  | E4 |  |  |  |  |
|  |  | E5 |  |  |  |  |
|  |  | E6 |  |  |  |  |
|  |  | E8 |  |  |  |  |
|  |  | E9 |  |  |  |  |
|  |  | E10 |  |  |  |  |
|  |  | E11 |  |  |  |  |
|  |  | E12 |  |  |  |  |
|  |  | E13 |  |  |  |  |
|  |  | E14 |  |  |  |  |

## 5. What to paste back

1. The filled-in results table above.
2. For every failed run, the part of the transcript that shows the failure: the prompt, the skill that loaded (or
   did not), the python command if any, and the wrong or missing line in the answer.
3. Post both in the repository issue for this test, or send them back to the maintainer.
