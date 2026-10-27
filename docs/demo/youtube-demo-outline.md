# YouTube demo: PipingToolset for Claude (3:30 target, 4:00 hard cap)

Record during today's Cowork checklist run (2026-10-27). Every prompt below is a row of
`tests/e2e/COWORK-CHECKLIST.md`, so the recording doubles as test evidence: keep the raw captures.

**Working title:** PipingToolset for Claude: B31.3 wall thickness, a refused table value, and a pipe support check in 3 minutes
**Thumbnail text:** "Claude asks. A script computes. You read the table."
**Surface:** Claude Cowork (the visual install, the skills menu and the outputs folder all read on camera). Claude Code gets a 10-second cutaway only.

## Before you press record (15 min)

1. Fresh Cowork workspace or a new chat with no other piping skills installed, so nothing competes with the PipingToolset skills.
2. Download `piping-toolset.plugin` from the latest GitHub Release to the Desktop so the drag is short and visible.
3. Create an empty folder `C:\demo\PS-201` and point the Cowork chat's working folder at it, so the outputs folder on screen holds only what the demo creates.
4. Window at 1920 × 1080, Cowork maximised, OS display scaling 125 % so chat text is legible at YouTube's 1080p. Light theme (matches the website screenshots).
5. OBS: 1080p30, display capture of that monitor only, microphone on a separate track so narration can be re-recorded. Hide the taskbar clock and any notification toasts (Focus Assist on).
6. Clear anything personal from view: other chats in the Cowork sidebar, browser tabs, email. The GitHub account name will appear on the release page; that is fine.
7. Have the three prompts in a plain-text file open on a second monitor to paste from. Paste, do not type live; typing on camera costs 20 seconds per prompt.
8. One rehearsal run of E1 and E2 end to end before recording, to warm the model and confirm the skill triggers under the PipingToolset name.

## Shot list

Timings are for the edited cut. Record everything at real speed; the pipe-support run is time-lapsed in the edit.

| # | Time | On screen (your actions) | Inputs you paste | What must be visible | Narration |
|---|---|---|---|---|---|
| 1 | 0:00–0:12 | Cold open on the finished E1 answer: the calc table with t = 0.13650 in and the ADEQUATE verdict. Hold 3 s, then cut to the pipingtoolset.com homepage. | none | The table, the equation citation ¶304.1.2 Eq. (3a), the line "S, E, W, Y user-supplied" | "This is a B31.3 wall thickness check, done inside Claude, with every number coming from a script and not from the model's memory. Here's how it works." |
| 2 | 0:12–0:35 | Homepage, scroll to the new "PipingToolset for Claude" section, click through to /claude/. Pause on "What it will not do" and "Where your data goes". | none | The three rules, the data table showing "Nothing" in the PipingToolset column | "PipingToolset for Claude is five skills for Claude Code and Cowork. Claude runs the interview, a Python script does the math, and you read the table. It never quotes a code table value, and nothing you type is sent to us." |
| 3 | 0:35–1:00 | Install: open Cowork, drag `piping-toolset.plugin` from the Desktop into the chat, click Accept on the preview card. Open a fresh chat, open the skills menu, hover the five PipingToolset skills. | none | The preview card, the Accept button, the five skill names under PipingToolset | "Install is a drag and drop. Five skills: pressure design, stress screening, load case builder, pipe support, and iso to PCF." |
| 4 | 1:00–1:45 | Run E1. Paste the prompt, send. Expand the tool step so the `python ... pressure_design.py` command is on screen for a beat. Then the answer table. | `Use the pressure design skill. B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in, design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at 600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and does 0.280 in nominal wall work?` | The python command; t = 0.13650 in; tm = 0.19900 in; 0.280 × 0.875 = 0.245 ≥ 0.199 → adequate; S/E/W/Y echoed as user-supplied; ¶304.1.2 Eq. (3a) | "I give it the code, the edition, the service, and the allowable stress from my own copy. Watch the step: it writes a job file and runs the script. t is 0.1365, t-m is 0.199, and 0.280 nominal less mill tolerance is 0.245, so the wall is adequate. Hand check: 750 times 6.625 over 2 times 36,400 is 0.1365. Same number." |
| 5 | 1:45–2:10 | Run E2 in the same chat. Paste, send. Hold on the refusal. | `Use the pressure design skill. What's the allowable stress for A106 Grade B at 650 F under B31.3? Just give me the number.` | No number anywhere. It names Table A-1 (A-1C in 2024), the material row, the two temperature columns, and offers to interpolate once you read both | "Now the part that matters in review. I ask for the allowable stress and I say just give me the number. It won't. It tells me which table, which row, which two columns, and offers to interpolate once I've read them. The plugin contains no ASME table values. That's deliberate and it's tested." |
| 6 | 2:10–3:05 | Run E9. Paste, send. The skill confirms the load-axis mapping (answer "yes" or confirm as prompted). Time-lapse the run at 8–10× with a visible "sped up" caption. Return to real time for the governing check, the optimizer table, then open the outputs folder and open `calc.md`. | `Use the pipe support skill. Check support PS-201: CSA type 1 t-post, W6X15 column 8 ft, W6X15 arm 24 in at EL 96. Two 6 in lines at 8 and 18 in. CAESAR II restraint loads (lb, Y up, pipes run along X): 6-P-1201 SUS 0,-850,0 OPE 180,-920,-140 WIN 0,0,210 EQ 0,0,260; 6-P-1202 SUS 0,-1100,0 OPE 240,-1180,-190 WIN 0,0,260 EQ 0,0,320. SDS 0.5, LRFD, 4 x 3/4 adhesive anchors, tau 800 psi from the ESR. Then optimize it.` Follow-up when asked to confirm the D/T/W/Eh mapping: `Yes, that mapping is correct.` | The mapping confirmation; the `support_calc.py ... --report --json` command; governing stage, check, combination and clause; the optimizer table with the recommended option; `calc.md` and `result.json` in the outputs folder | "The pipe support skill takes CAESAR II restraint loads straight off the restraint summary. It confirms the load mapping before it runs anything, because that is where support checks go wrong. Then ASCE 7-22 combinations, AISC 360-22 for the arm, column, welds and base plate, ACI 318 Chapter 17 for the anchors. It names the governing check and clause, proposes lighter code-passing alternatives, and writes the calc report to the outputs folder. That report is what you hand to your checker." |
| 7 | 3:05–3:25 | Cut to /claude/ "Where your data goes" table, then the GitHub repository page with the Apache-2.0 badge and the CHANGELOG open at an UNCONSERVATIVE-FIX entry. | none | The data table; the licence; the changelog label | "Everything runs in your Claude environment. The scripts are plain Python, open source, and verified against the same fixture cases as the free calculators on pipingtoolset.com. When a release corrects an unconservative result, it is labelled, and the changelog is the recall notice." |
| 8 | 3:25–3:35 | End card: pipingtoolset.com/claude/, the GitHub URL, the Cowork and Claude Code install lines. | none | URL text large enough to read on a phone | "Free, at pipingtoolset.com slash claude. Link in the description. You still need your own copy of the code. You should." |

## Contingencies

- **E9 runs long or asks more questions than expected.** Record it anyway; the time-lapse absorbs up to four minutes of real time. If it exceeds that, cut to the finished `calc.md` and narrate over it.
- **A different skill triggers.** That is a test failure (record it in the checklist) and a retake: start a fresh chat and re-paste. Do not edit around it.
- **The skill states a number without a python step visible.** Retake. The video's entire claim is the script step; never ship a cut where it is not on screen.
- **Cowork is unavailable.** Fall back to Claude Code in Windows Terminal at 125 % zoom with the slash form of the same three prompts (`/piping-toolset:pressure-design ...`, `/piping-toolset:pipe-support ...`). Replace shot 3 with the two `/plugin` commands.

## Edit notes

- Zoom to 150 % on the chat column for every number the narration quotes; YouTube on a phone is the baseline.
- Caption every quoted result as a lower-third so the video is checkable with the sound off.
- Blur or crop nothing in the chat; the demo data is the published example set and contains no client information.
- Royalty-free bed music under shots 3 and 6 only, ducked under narration.

## YouTube metadata

**Title:** PipingToolset for Claude: B31.3 wall thickness and a pipe support check, every number from a script

**Description:**
PipingToolset for Claude is a free, open-source plugin for Claude Code and Claude Cowork: five ASME B31.3 / B31.1 piping engineering skills. Claude runs the interview, a Python script does the calculation, and you read the table. The plugin contains no ASME code table values; you read those from your licensed copy. Nothing you enter is sent to PipingToolset.

Page and install: https://pipingtoolset.com/claude/
Source and releases: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/

Chapters
0:00 What you get
0:12 What it will and will not do
0:35 Install in Cowork
1:00 Pressure design: B31.3 wall thickness
1:45 It will not quote a table value
2:10 Pipe support check from CAESAR II loads
3:05 Where your data goes, licence, recall channel
3:25 Links

Results are engineering aids. The engineer of record verifies them before issue.

**Tags:** ASME B31.3, B31.1, pipe stress, CAESAR II, pipe support design, AISC 360, ACI 318, Claude Code, Claude Cowork, piping engineering, wall thickness calculation, Piping Toolset

## After recording

1. Fill in the COWORK-CHECKLIST results table for E1, E2 and E9 from the captures.
2. Keep the raw OBS file with the checklist evidence; the edited cut is the marketing asset.
3. Capture one still of shot 4's result table for the /claude/ page's video card and the og:image.
