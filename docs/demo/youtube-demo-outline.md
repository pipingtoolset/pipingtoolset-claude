# YouTube demo: PipingToolset for Claude (3:30 target, 4:00 hard cap)

Self-contained. Every prompt you paste is in this file, in the shot where you paste it and again
in the paste sheet at the end. You do not need the Cowork checklist or any other document open.

**Working title:** PipingToolset for Claude: B31.3 wall thickness, a refused table value, and a pipe
support check in 3 minutes
**Thumbnail text:** "Claude asks. A script computes. You read the table."
**Surface:** Claude desktop app, Cowork mode, light theme, the window as recorded on 2026-10-27.

## What the 2026-10-27 take already gives you

`docs/demo/PipingToolset_plugindemo_26oct2026.mp4` (2:53, 1916 × 1076, 30 fps, **silent**: the
audio track is at −91 dB, so narration is recorded separately over the edit). Usable as B-roll:

| In the file | What is on screen | Use for |
|---|---|---|
| 0:00–0:10 | Fresh Cowork chat, `+` menu, Skills › PipingToolset flyout with **five** skills (0.4.0 was installed) | Not usable: the shipping plugin has seven. Re-shoot after the update in pre-flight step 2 |
| 0:10–0:45 | Prompt 1 pasted, "Getting set up", skill `pressure-design` loads, "Running a command" | Shot 4 (process) |
| 0:45–1:20 | The Prompt 1 answer: the results table, validity checks, "What a reviewer would flag on this sheet" | Shot 4 (result). Good hold frame for the cold open |
| 1:20–2:35 | Prompt 3 pasted in the same chat, `pipe-support` loads, "Ran 3 commands", "Build PS-201 spec and run support calc", "Weighing a lighter replacement arm option", "Saving files to your computer" | Shot 6, time-lapsed |
| 2:35–2:53 | The Prompt 3 answer: governing check, optimizer recommendation, "Before issue" list, the three saved files | Shot 6 (result) |

Not in the take, so still to record: the homepage and `/claude/` page (shot 2, now live), the
install drag-and-drop and the seven-skill menu (shot 3), Prompt 2, the refusal (shot 5), the
GitHub page and changelog (shot 7), the end card (shot 8). The "Ran 2 commands" / "Ran 3 commands"
steps were never expanded on camera, so the `python … pressure_design.py` line was never visible;
the retake of shot 4 fixes that (step 7 under "Before you press record").

## Before you press record (20 min)

1. **Site check, in a browser:** https://pipingtoolset.com/ shows the **For Claude** button in the
   hero and a "PipingToolset for Claude — free · open source" tier below the free tiles;
   https://pipingtoolset.com/claude/ loads; its "Download for Cowork (.plugin)" button downloads
   `piping-toolset.plugin` (about 390 KB). If any of the three fails, stop: the deploy is not in.
2. **Update the plugin to 0.5.0.** The take was recorded on 0.4.0 (five skills). In Cowork,
   drag the freshly downloaded `piping-toolset.plugin` into a chat and press **Accept**. Open a
   new chat, `+` › Skills › PipingToolset, and count **seven**: bolted-flange, iso-to-pcf,
   load-case-builder, nozzle-load, pipe-support, pressure-design, stress-screening. Leave the
   downloaded file on the Desktop; shot 3 drags it again on camera.
3. **Empty the working folder.** Delete everything in `C:\demo\PS-201` (the last take left
   `PS-201_calc.md`, `PS-201_spec.json`, `PS-201_result.json` there). Point the Cowork chat at
   that folder, as before, so the outputs folder on screen holds only what the demo creates.
4. **No competing skills.** If any other piping or ASME skill is installed in Cowork, disable
   it for the session. A different skill answering is a retake.
5. **Window.** Same as the take: app maximised at 1920 × 1080, OS scaling 125 %, light theme.
   Hide the taskbar clock, Focus Assist on. Close other chats in the sidebar.
6. **OBS.** 1080p30, display capture of that monitor only. Microphone **off** for the screen
   pass; narration is a separate voice-only recording read from the scripts below.
7. **Expanded tool steps.** Before recording, in any chat, click a "Ran N commands" row once to
   learn where it expands. On camera, click it after each run so the `python` command line is
   visible for at least two seconds. The video's whole claim is that step.
8. **Rehearsal.** Run Prompt 1 and Prompt 2 once in a throwaway chat, then delete that chat.
   Confirm `pressure-design` is the skill that loads (it shows in the "Used in this session"
   panel on the right).

## Shot list

Timings are for the edited cut. Record at real speed; shot 6 is time-lapsed in the edit.

### Shot 1 · 0:00–0:12 · Cold open

**On screen:** the finished Prompt 1 answer, held 3 s on the results table (the take's 0:45–1:20
footage works), then cut to the pipingtoolset.com homepage.

**Must be visible:** "Results (B31.3-2022, para. 304.1.2, Eq. 3a; inputs as you gave them)", the
row "Pressure design thickness t … 0.1365 in", the row "Allowable pressure at 0.280 in nominal …
1,008 psig, PASS".

**Narration:** "This is a B31.3 wall thickness check, done inside Claude, with every number
coming from a script and not from the model's memory. Here's how it works."

### Shot 2 · 0:12–0:38 · The page

**On screen:** homepage. Click **For Claude** in the hero. On `/claude/`, scroll slowly through
"What it does" (the seven-row table), pause on "What it will not do", then on "Where your data
goes" (the table whose last data row says **Nothing**).

**Must be visible:** the seven skill names in the table; the first bullet under "What it will not
do"; the "Anything sent to pipingtoolset.com … Nothing" row.

**Narration:** "PipingToolset for Claude is seven free skills for Claude Code and Claude Cowork,
from the people who build the free calculators at pipingtoolset.com. Claude runs the interview, a
Python script does the math, and you read the table from your own copy of the code. It never
quotes a code table value, and nothing you type is sent to us."

### Shot 3 · 0:38–1:00 · Install

**On screen:** back on `/claude/`, click **Download for Cowork (.plugin)**. Open Cowork, drag
`piping-toolset.plugin` from the Desktop into the chat, click **Accept** on the preview card.
Open a fresh chat, `+` › Skills › PipingToolset, hover down the seven skills so the description
tooltip shows for one of them.

**Must be visible:** the preview card and its Accept button; the flyout listing all seven skills
under PipingToolset.

**Narration:** "Install is a drag and drop. Seven skills: pressure design, stress screening, load
case builder, pipe support, iso to PCF, nozzle load and bolted flange."

### Shot 4 · 1:00–1:45 · Pressure design

**Paste this (Prompt 1):**

```
Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

**On screen:** send. When "Ran 2 commands" appears, click it so the `python … pressure_design.py`
line is on screen for two seconds, then collapse it and let the answer fill in.

**Must be visible:** `pressure-design` in the "Used in this session" panel; the python command;
these rows of the results table, as the skill prints them:

| Item | Value |
|---|---|
| Pressure design thickness, t = PD / [2(SEW + PY)] | 0.1365 in |
| Minimum required thickness, tm = t + c | 0.1990 in |
| Nominal wall to order, tm / (1 − 0.125) | 0.2274 in |
| Wall left for pressure at 0.280 in, 0.280 × 0.875 − 0.0625 | 0.1825 in |
| Allowable pressure at 0.280 in nominal | 1,008 psig, PASS |

and, below it, "What a reviewer would flag on this sheet" with the "Material is missing" bullet.

**Narration:** "I give it the code, the edition, the service, and the allowable stress from my
own copy of B31.3. Watch the step: it writes a job file and runs the script. t is 0.1365 inches,
t-m with the corrosion allowance is 0.199, and 0.280 nominal works, with about a third of the
pressure in margin. Hand check: 750 times 6.625, over 2 times 36,400, is 0.1365. Same number.
Then it tells me what a reviewer will flag: the table line behind that allowable stress is not on
the sheet yet, and it says so."

### Shot 5 · 1:45–2:10 · The refusal

**Paste this (Prompt 2), in the same chat:**

```
Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
```

**On screen:** send, hold on the answer. Zoom to 150 % on the paragraph that names the table.

**Must be visible:** no number anywhere in the answer. It names B31.3 Table A-1 (Table A-1C in the
2024 edition), the A106 Grade B row, the 600 F and 650 F columns, and offers to interpolate once
you have read both.

**Narration:** "Now the part that matters in review. I ask for the allowable stress and I say
just give me the number. It won't. It tells me which table, which row, which two columns, and
offers to interpolate once I've read them. The plugin contains no ASME table values. That's
deliberate, and it's a pinned test."

If a number appears: stop, note it, retake in a fresh chat. Do not edit around it.

### Shot 6 · 2:10–3:05 · Pipe support from CAESAR II loads

**Paste this (Prompt 3), in the same chat:**

```
Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

**On screen:** send. The skill runs without stopping (on the take it ran the cascade, re-ran the
optimizer at a 0.85 cap, and saved files, about 75 s). Time-lapse that at 8–10× with a "sped up"
caption. Return to real time when the final answer lands. Click "Ran 3 commands, saved files to
your computer" so a `support_calc.py … --report --json` line shows for two seconds. Then open
`C:\demo\PS-201` in Explorer and open `PS-201_calc.md`.

**Only if the skill stops and asks you to confirm the load mapping**, paste:

```
Yes, that mapping is correct.
```

On the take it did not stop; it stated the mapping in the answer under "Load mapping (confirm
this)". Either behaviour is fine on camera.

**Must be visible:** `pipe-support` added to the "Used in this session" panel; the python command;
these lines of the answer, as the skill prints them:

- "Governing check: the base metal at the arm-to-column weld, in tension yielding (AISC J4-1).
  Ratio 0.888, under 1.4D + T."
- "Load mapping (confirm this): D = SUS, T = OPE − SUS, W = WIN, Eh = EQ, Ev = 0.2·SDS·D"
- "PS-201 passes as designed, but it's oversized. My recommendation is a W8X10 arm on a PIPE5STD
  column, with a 1 in plate and 5/8 in anchors. That design's highest ratio is 0.764"
- the "Before issue" list (anchors re-run at 5/8 in, the ASSUMED embedment / f'c / edge distance,
  Fy 36 ksi, cap plate, existing concrete, restraint type)
- "The calc report, input spec and results are saved to C:\demo\PS-201: PS-201_calc.md,
  PS-201_spec.json and PS-201_result.json."

**Narration:** "The pipe support skill takes CAESAR II restraint loads straight off the restraint
summary. It states how it mapped them, dead, thermal, wind, seismic, and asks you to confirm,
because that is where support checks go wrong. Then ASCE 7-22 combinations, AISC 360-22 for the
arm, the column, the welds and the base plate, ACI 318 chapter 17 for the anchors. Twenty-three
combinations. The governing check is the base metal at the arm-to-column weld, at 0.888. It
passes, so it optimizes: a W8 by 10 arm on a 5-inch standard pipe column, 0.764, and a list of
what to confirm before issue. The calc report is written to the working folder. That report is
what you hand to your checker."

### Shot 7 · 3:05–3:25 · Data, licence, recall

**On screen:** cut to `/claude/` "Where your data goes", then to
https://github.com/pipingtoolset/pipingtoolset-claude (the Apache-2.0 licence badge and the
seven-skill table in the README), then to `CHANGELOG.md` scrolled to the **0.3.2** entry, which
carries the UNCONSERVATIVE-FIX label.

**Must be visible:** the "Nothing" row; the licence; the words UNCONSERVATIVE-FIX.

**Narration:** "Everything runs in your Claude environment. The scripts are plain Python, open
source under Apache 2, and verified against the same fixture cases as the free calculators on
pipingtoolset.com. When a release corrects an unconservative result, it is labelled, and the
changelog is the recall notice."

### Shot 8 · 3:25–3:35 · End card

**On screen:** a title card with three lines, large enough to read on a phone:

```
pipingtoolset.com/claude
github.com/pipingtoolset/pipingtoolset-claude
/plugin marketplace add pipingtoolset/pipingtoolset-claude
```

**Narration:** "Free, at pipingtoolset.com slash claude. Link in the description. You still need
your own copy of the code. You should."

## Contingencies

- **A different skill loads.** Retake in a fresh chat. The skill name in "Used in this session"
  is the check.
- **A number with no python step.** Retake. Never ship a cut where the script step is not on
  screen for the number being narrated.
- **Shot 6 runs past four minutes.** Cut to the finished `PS-201_calc.md` in the outputs folder
  and narrate over it.
- **Cowork unavailable.** Claude Code in Windows Terminal at 125 % zoom, with the slash form of
  the three prompts (replace "Use the pressure design skill." with
  `/piping-toolset:pressure-design`, and "Use the pipe support skill." with
  `/piping-toolset:pipe-support`). Replace shot 3 with the two `/plugin` commands from the end
  card typed on camera.

## Edit notes

- Zoom to 150 % on the chat column for every number the narration quotes.
- Caption every quoted result as a lower-third so the video checks out with the sound off.
- Nothing to blur: the demo data is the published example set.
- Bed music under shots 3 and 6 only, ducked under narration.

## YouTube metadata

**Title:** PipingToolset for Claude: B31.3 wall thickness and a pipe support check, every number
from a script

**Description:**

```
PipingToolset for Claude is a free, open-source plugin for Claude Code and Claude Cowork: seven ASME B31.3 / B31.1 piping engineering skills (pressure design, stress screening, load case builder, pipe support, iso to PCF, nozzle load, bolted flange). Claude runs the interview, a Python script does the calculation, and you read the table from your licensed copy of the code. The plugin contains no ASME code table values. Nothing you enter is sent to PipingToolset.

Page and install: https://pipingtoolset.com/claude/
Source and releases: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/

Chapters
0:00 What you get
0:12 What it will and will not do
0:38 Install in Cowork
1:00 Pressure design: B31.3 wall thickness
1:45 It will not quote a table value
2:10 Pipe support check from CAESAR II loads
3:05 Where your data goes, licence, recall channel
3:25 Links

Results are engineering aids. The engineer of record verifies them before issue.
```

**Tags:** ASME B31.3, B31.1, pipe stress, CAESAR II, pipe support design, AISC 360, ACI 318,
Claude Code, Claude Cowork, piping engineering, wall thickness calculation, Piping Toolset

## After recording

1. Record the Cowork checklist results for E1, E2 and E9 from the captures (the prompts above are
   those three rows verbatim; E9's "confirms the mapping before running" pass check should read
   "states the mapping and asks for confirmation", which is what 0.5.0 does).
2. Keep the raw OBS file with the checklist evidence; the edited cut is the marketing asset.
3. Capture one still of the shot 4 results table for the `/claude/` page's video card and send
   the YouTube URL back so the page can embed it.

---

## Paste sheet

Keep this section visible on the second monitor. Paste in order; one chat for all three.

**Prompt 1 (shot 4):**

```
Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

**Prompt 2 (shot 5):**

```
Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
```

**Prompt 3 (shot 6):**

```
Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

**Only if asked to confirm the load mapping (shot 6):**

```
Yes, that mapping is correct.
```

**End card text (shot 8):**

```
pipingtoolset.com/claude
github.com/pipingtoolset/pipingtoolset-claude
/plugin marketplace add pipingtoolset/pipingtoolset-claude
```
