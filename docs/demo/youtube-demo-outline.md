# YouTube demo: PipingToolset for Claude

One recording, start to finish, in the order written here. Nothing is pre-run, nothing is pre-opened.
Every prompt you paste is printed in the step where you paste it, and all of them again in the paste
sheet at the end. This file is the only document you need open.

The video is edited afterwards: the opening three seconds of the finished video are a replay of a
result you record in step 9, so you never need to "start with an answer". Just record in order.

**Target length of the edited cut:** 3:30 (4:00 hard cap).
**Working title:** PipingToolset for Claude: B31.3 wall thickness, a refused table value, and a pipe
support check in 3 minutes
**Thumbnail text:** "Claude asks. A script computes. You read the table."

---

## Part A · Setup (not recorded, about 15 minutes)

A1. **Delete the old plugin install.** In the Claude desktop app: `+` › Plugins › Manage plugins.
    If PipingToolset is listed, remove it. The earlier install was 0.4.0 with five skills; the
    video must show seven.

A2. **Empty the working folder.** Delete everything inside `C:\demo\PS-201` so the folder exists
    and is empty. The old take left `PS-201_calc.md`, `PS-201_spec.json` and `PS-201_result.json`
    there.

A3. **Delete old chats.** In the Cowork sidebar, delete "B31.3 pipe wall thickness", "Pipe design
    and support check" and any other chat from the earlier take, so the sidebar is clean on camera.

A4. **Disable competing skills.** If any other piping, ASME or structural skill is installed,
    disable it for the session. A different skill answering a prompt is a retake.

A5. **Browser.** Open a browser window at https://pipingtoolset.com/ with no other tabs, signed
    out, bookmarks bar hidden. Confirm the hero shows a **For Claude** button and the page scrolls
    to a tier headed "PipingToolset for Claude — free · open source". Leave the window ready.

A6. **Desktop and window.** Clear the Desktop of files (the download in step 3 should be the only
    new icon). App and browser maximised at 1920 × 1080, OS scaling 125 %, light theme. Hide the
    taskbar clock, Focus Assist on.

A7. **OBS.** 1080p30, display capture of that monitor only, microphone off. Narration is
    recorded separately afterwards from the lines under each step.

A8. **Learn one click.** Open a throwaway Cowork chat and paste this to learn where the
    "Ran N commands" row expands:

```
Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

    It will fail or ask to install the skill, because you removed the plugin in A1. That is
    fine: this is only to confirm no competing skill picks it up. Delete the chat. Then delete
    the browser's download history so the step 3 download looks fresh.

Press record.

---

## Part B · Recording (in this order, real time, no pauses needed)

### Step 1 · Homepage (edit: 0:12–0:20)

**Do:** browser is on https://pipingtoolset.com/. Hold 2 s. Scroll down slowly past the free tiles
until the "PipingToolset for Claude — free · open source" tier with its three tiles is centred.
Hold 2 s. Scroll back up and click **For Claude** in the hero.

**Narration:** "PipingToolset for Claude is seven free skills for Claude Code and Claude Cowork,
from the people who build the free calculators at pipingtoolset.com."

### Step 2 · The /claude/ page (edit: 0:20–0:38)

**Do:** on https://pipingtoolset.com/claude/, scroll slowly through "What it does" (the seven-row
table), stop on "What it will not do" for 3 s, then on "Where your data goes" for 3 s (the table
whose row "Sent to pipingtoolset.com by the scripts" says **Nothing**). Scroll back to the top.

**Narration:** "Claude runs the interview, a Python script does the math, and you read the table
from your own copy of the code. It never quotes a code table value, and the scripts send
nothing to us."

### Step 3 · Download (edit: 0:38–0:44)

**Do:** click the red **Download for Cowork (.plugin)** button. Let the download finish. Open the
Desktop (or the Downloads folder if the browser saves there) so `piping-toolset.plugin` is visible.

**Narration:** "Install is a drag and drop."

### Step 4 · Install (edit: 0:44–0:54)

**Do:** open the Claude desktop app, Cowork, new chat. Drag `piping-toolset.plugin` from the
Desktop into the chat. When the preview card appears, click **Accept**. Wait for the confirmation.

**Must be visible:** the preview card and the Accept button.

**Narration:** (none; the card speaks for itself)

### Step 5 · The seven skills (edit: 0:54–1:00)

**Do:** start a fresh chat. Click `+` › Skills › PipingToolset. Move the cursor slowly down the
flyout so the description tooltip appears for two of them. Count seven on screen:
bolted-flange, iso-to-pcf, load-case-builder, nozzle-load, pipe-support, pressure-design,
stress-screening. Close the menu.

If fewer than seven are listed, stop recording, remove and reinstall the plugin, and restart from
step 4.

**Narration:** "Seven skills: pressure design, stress screening, load case builder, pipe support,
iso to PCF, nozzle load and bolted flange."

### Step 6 · Point the chat at the working folder

**Do:** in the same fresh chat, use the folder control to choose `C:\demo\PS-201` (it should
appear as a "PS-201 FOLDER" chip, as it did on the earlier take).

**Narration:** (none)

### Step 7 · Prompt 1, pressure design (edit: 1:00–1:45)

**Paste and send:**

```
Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

**Do:** when "Ran 2 commands" appears, click it so the `python … pressure_design.py` line is on
screen for 3 s, then collapse it. Let the answer finish. Scroll so the results table and the
"What a reviewer would flag on this sheet" list are both on screen. Hold 5 s.

**Must be visible:** `pressure-design` under "Used in this session" on the right; the python
command; these rows as the skill prints them:

| Item | Value |
|---|---|
| Pressure design thickness, t = PD / [2(SEW + PY)] | 0.1365 in |
| Minimum required thickness, tm = t + c | 0.1990 in |
| Nominal wall to order, tm / (1 − 0.125) | 0.2274 in |
| Wall left for pressure at 0.280 in, 0.280 × 0.875 − 0.0625 | 0.1825 in |
| Allowable pressure at 0.280 in nominal | 1,008 psig, PASS |

and the "Material is missing" bullet under "What a reviewer would flag on this sheet".

**Narration:** "I give it the code, the edition, the service, and the allowable stress from my
own copy of B31.3. Watch the step: it writes a job file and runs the script. t is 0.1365 inches,
t-m with the corrosion allowance is 0.199, and 0.280 nominal works, with about a third of the
pressure in margin. Hand check: 750 times 6.625, over 2 times 36,400, is 0.1365. Same number.
Then it tells me what a reviewer will flag: the table line behind that allowable stress is not on
the sheet yet, and it says so."

### Step 8 · Prompt 2, the refusal (edit: 1:45–2:10)

**Paste and send, same chat:**

```
Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
```

**Do:** let the answer finish. Hold 5 s on it.

**Must be visible:** no number anywhere in the answer. It names B31.3 Table A-1 (Table A-1C in the
2024 edition), the A106 Grade B row, the 600 F and 650 F columns, and offers to interpolate once
you have read both.

If any allowable stress value appears: stop, note it, delete the chat, and restart from step 6.

**Narration:** "Now the part that matters in review. I ask for the allowable stress and I say
just give me the number. It won't. It tells me which table, which row, which two columns, and
offers to interpolate once I've read them. The plugin contains no ASME table values. That's
deliberate, and it's a pinned test."

### Step 9 · Prompt 3, pipe support (edit: 2:10–3:05, time-lapsed)

**Paste and send, same chat:**

```
Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

**Do:** let it run (about 75 s on the earlier take: it runs the cascade, re-runs the optimizer at a
0.85 cap, saves files). Do not touch anything while it runs.

**Only if it stops and asks you to confirm the load mapping,** paste and send:

```
Yes, that mapping is correct.
```

(On the earlier take it did not stop; it stated the mapping inside the answer as "Load mapping
(confirm this)". Either is fine.)

When the answer finishes: click "Ran 3 commands, saved files to your computer" so a
`support_calc.py … --report --json` line is visible for 3 s, collapse it, then scroll slowly from
"PS-201 passes as designed" through "Before issue" to the last line naming the three saved files.
Hold 3 s.

**Must be visible:** `pipe-support` added under "Used in this session"; the python command; these
lines as the skill prints them:

- "Governing check: the base metal at the arm-to-column weld, in tension yielding (AISC J4-1).
  Ratio 0.888, under 1.4D + T."
- "Load mapping (confirm this): D = SUS, T = OPE − SUS, W = WIN, Eh = EQ, Ev = 0.2·SDS·D"
- "PS-201 passes as designed, but it's oversized. My recommendation is a W8X10 arm on a PIPE5STD
  column, with a 1 in plate and 5/8 in anchors. That design's highest ratio is 0.764"
- the "Before issue" list
- "The calc report, input spec and results are saved to C:\demo\PS-201: PS-201_calc.md,
  PS-201_spec.json and PS-201_result.json."

**Narration:** "The pipe support skill takes CAESAR II restraint loads straight off the restraint
summary. It states how it mapped them, dead, thermal, wind, seismic, and asks you to confirm,
because that is where support checks go wrong. Then ASCE 7-22 combinations, AISC 360-22 for the
arm, the column, the welds and the base plate, ACI 318 chapter 17 for the anchors. Twenty-three
combinations. The governing check is the base metal at the arm-to-column weld, at 0.888. It
passes, so it optimizes: a W8 by 10 arm on a 5-inch standard pipe column, 0.764, and a list of
what to confirm before issue."

### Step 10 · The calc report on disk (edit: inside 2:10–3:05)

**Do:** open Explorer at `C:\demo\PS-201`. Three files. Double-click `PS-201_calc.md` and scroll
its first page slowly. Close it.

**Narration:** "The calc report is written to the working folder. That report is what you hand to
your checker."

### Step 11 · GitHub (edit: 3:05–3:25)

**Do:** in the browser, go to https://github.com/pipingtoolset/pipingtoolset-claude. Hold 3 s on
the README (the seven-skill table and the Apache-2.0 licence badge are above the fold). Click
`CHANGELOG.md`, scroll to the **0.3.2** entry, which carries the label UNCONSERVATIVE-FIX, hold
3 s.

**Narration:** "Everything runs in your Claude environment. The scripts are plain Python, open
source under Apache 2, and verified against the same fixture cases as the free calculators on
pipingtoolset.com. When a release corrects an unconservative result, it is labelled, and the
changelog is the recall notice."

### Step 12 · Back to the data table (edit: 3:05–3:10, cut in before step 11 footage)

**Do:** browser back to https://pipingtoolset.com/claude/, scroll to "Where your data goes",
hold 3 s on the **Nothing** row ("Sent to pipingtoolset.com by the scripts").

**Narration:** (covered by the step 11 line; this is the picture under "Everything runs in your
Claude environment.")

Stop recording.

### Step 13 · End card (made in the editor, not recorded)

Three lines of text on the ink background, large enough to read on a phone:

```
pipingtoolset.com/claude
github.com/pipingtoolset/pipingtoolset-claude
/plugin marketplace add pipingtoolset/pipingtoolset-claude
```

**Narration:** "Free, at pipingtoolset.com slash claude. Link in the description. You still need
your own copy of the code. You should."

---

## Part C · Edit order

The edited video reorders the footage; the recording order above is for a clean single take.

| Edited time | Footage | Narration |
|---|---|---|
| 0:00–0:12 | 3 s hold on the step 7 results table, then cut to step 1 | "This is a B31.3 wall thickness check, done inside Claude, with every number coming from a script and not from the model's memory. Here's how it works." |
| 0:12–0:38 | steps 1 and 2 | steps 1 and 2 lines |
| 0:38–1:00 | steps 3, 4, 5 | steps 3 and 5 lines |
| 1:00–1:45 | step 7 | step 7 line |
| 1:45–2:10 | step 8 | step 8 line |
| 2:10–3:05 | step 9 at 8–10× with a "sped up" caption while it runs, real time for the answer, then step 10 | steps 9 and 10 lines |
| 3:05–3:25 | step 12, then step 11 | step 11 line |
| 3:25–3:35 | step 13 end card | step 13 line |

Step 6 is cut entirely.

- Zoom to 150 % on the chat column for every number the narration quotes.
- Caption every quoted result as a lower-third so the video checks out with the sound off.
- Nothing to blur: the demo data is the published example set.
- Bed music under 0:38–1:00 and the sped-up part of 2:10–3:05 only, ducked under narration.

## Contingencies while recording

- **A different skill loads** (the name under "Used in this session" is the check): stop, delete
  the chat, restart from step 6.
- **A number appears with no "Ran N commands" row above it:** stop, delete the chat, restart from
  step 6. The video's whole claim is the script step.
- **Step 9 runs past four minutes:** keep recording; the time-lapse absorbs it. If it stalls,
  send `Continue.` once.
- **Cowork unavailable:** record in Claude Code in Windows Terminal at 125 % zoom. Replace steps
  3 to 5 with typing the two commands from the end card. Replace "Use the pressure design skill."
  at the start of Prompts 1 and 2 with `/piping-toolset:pressure-design` and "Use the pipe
  support skill." at the start of Prompt 3 with `/piping-toolset:pipe-support`.

## YouTube metadata

**Title:** PipingToolset for Claude: B31.3 wall thickness and a pipe support check, every number
from a script

**Description:**

```
PipingToolset for Claude is a free, open-source plugin for Claude Code and Claude Cowork: seven ASME B31.3 / B31.1 piping engineering skills (pressure design, stress screening, load case builder, pipe support, iso to PCF, nozzle load, bolted flange). Claude runs the interview, a Python script does the calculation, and you read the table from your licensed copy of the code. The plugin contains no ASME code table values. The scripts make no network calls; the optional connector, if you enable it, sends lookup keys only.

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

1. Keep the raw OBS file: steps 7, 8 and 9 are the Cowork checklist runs E1, E2 and E9, and the
   recording is their evidence.
2. Capture one still of the step 7 results table for the /claude/ page's video card.
3. Send the YouTube URL back so the page can embed it.

---

## Paste sheet

Everything you paste, in order. One chat for Prompts 1, 2 and 3.

**Prompt 1 (step 7):**

```
Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?
```

**Prompt 2 (step 8):**

```
Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.
```

**Prompt 3 (step 9):**

```
Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.
```

**Only if asked to confirm the load mapping (step 9):**

```
Yes, that mapping is correct.
```

**Only if step 9 stalls:**

```
Continue.
```

**URLs (steps 1, 2, 11, 12):**

```
https://pipingtoolset.com/
https://pipingtoolset.com/claude/
https://github.com/pipingtoolset/pipingtoolset-claude
https://github.com/pipingtoolset/pipingtoolset-claude/blob/main/CHANGELOG.md
```

**End card text (step 13):**

```
pipingtoolset.com/claude
github.com/pipingtoolset/pipingtoolset-claude
/plugin marketplace add pipingtoolset/pipingtoolset-claude
```
