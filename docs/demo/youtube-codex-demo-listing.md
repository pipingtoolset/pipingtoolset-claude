# YouTube listing: PipingToolset for ChatGPT and Codex demo

Built by `edit-tools/build_codex_demo.py` from the five Codex recordings (2026-10-28), re-rendered
2026-11-02 with the ACI CODE-318-25 captions (PR #31). Published 2026-11-02 as a new video,
**LfTiA0Wv2EA** (1920x1080, 30 fps, 4:05, silent), replacing VHD-XIeQu2s (10-28, 4:12); `VIDEO.id`
in `scripts/seo/openai-content.mjs` (pipecalcpro) carries it and the `/openai/` page embeds it.
YouTube title as uploaded: "Piping Toolset for OpenAI ChatGPT & Codex: B31.3 wall thickness, and a
pipe support check". `PipingToolset_for_ChatGPT_Codex_demo.srt` is the English subtitle track; the
same captions are burned in, so the track is for search and accessibility.

**Re-render 2026-11-02 (console workstream B12).** The 2026-10-28 cut carried pre-connector page copy
("practicing, licensed piping engineer" on the /openai/ page, "What reaches PipingToolset: Nothing"
without the connector clause) and an "ACI 318-19" caption. The /openai/ page shot (recording
`PipingToolset_Codex_install_intro.mp4`, 22-30 s) is cut, the privacy caption now carries the connector
clause, the report caption no longer names ACI 318-19, and the plugin-listing and pipe-support
footage carries an on-screen "Recorded on plugin 0.5.x" label. The recordings themselves are unchanged;
re-record the page shot, the listing and the pipe-support run on 0.9.0 and drop the labels.
Output in `docs/demo/rerender-2026-11-02/` (gitignored). Description below carries UTMs
(`utm_campaign=openai-plugin-demo`).

## Title

PipingToolset for ChatGPT and Codex: B31.3 wall thickness, a refused table value and a pipe support check, every number from a script

(97 characters; YouTube allows 100.)

## Description

```
The same seven ASME B31.1 / B31.3 piping skills that ship for Claude, installed in the ChatGPT desktop app through the Codex plugin marketplace. No narration: captions describe each step.

What you see:
• Add the marketplace (github.com/pipingtoolset/pipingtoolset-claude) and install PipingToolset from the Plugins view; seven skills appear under the PipingToolset mark.
• Prompt 1, pressure-design: B31.3-2022, NPS 6 seamless, 750 psig at 600 F, S = 17,900 psi from the user's copy. The skill runs pressure_design.py: t = 0.13650 in, tm = 0.19900 in, order 0.22743 in; 0.280 in nominal passes with 1,008 psi allowable.
• Prompt 2: "What is the allowable stress for A106 Grade B at 650 F? Just give me the number." No number. It names Table A-1 (A-1C in 2024) and the row to read.
• Prompt 3, pipe-support: PS-201, a CSA type 1 t-post with CAESAR II restraint loads. The skill asks for what it is missing, runs 23 ASCE 7-22 LRFD combinations through support_calc.py (governing: arm-to-column weld base metal, UR 0.888), re-runs the optimizer at a 0.85 cap, and writes the calc report, result JSON and spec files, with every assumed input marked ASSUMED.

Note on the footage: the plugin listing and pipe-support segments were recorded on plugin 0.5.x and are labelled on screen. Release 0.9.0 (2026-11-01) checks pipe supports to ACI CODE-318-25 and AISC 360-22 by default; the numbers shown are from the earlier run.

Three rules hold in every skill: the assistant never does the arithmetic, it never recalls a code table value, and the edition is an input, never a silent default. The plugin sends nothing to PipingToolset: the skills and scripts make no network calls, carry no telemetry and need no account with us. The optional Engineering Data connector, if you enable it, sends only lookup keys.

Install
  codex plugin marketplace add pipingtoolset/pipingtoolset-claude
  then install PipingToolset from the Plugins view in the ChatGPT desktop app or Codex.

Landing page: https://pipingtoolset.com/openai/?utm_source=youtube&utm_medium=video&utm_campaign=openai-plugin-demo
For Claude: https://pipingtoolset.com/claude/?utm_source=youtube&utm_medium=video&utm_campaign=openai-plugin-demo
Source, releases, changelog: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/?utm_source=youtube&utm_medium=video&utm_campaign=openai-plugin-demo

Chapters
0:00 Title and the ChatGPT desktop app
0:12 Add the marketplace and install
0:31 The seven skills in Plugin settings
0:43 Prompt 1: B31.3 wall thickness (pressure-design)
1:05 The result and the review items
1:24 Prompt 2: a table value is refused
1:50 Prompt 3: pipe support PS-201 (pipe-support)
2:09 The skill asks, then 23 LRFD combinations
2:39 Optimizer re-run and the ASSUMED list
2:55 The calc report, limit states and compliance matrix
3:20 Reviewer findings and optimized alternatives
3:39 Files written to the working folder, and links

Results are engineering aids. The engineer of record verifies them before issue. ChatGPT and Codex are products of OpenAI; Claude is a product of Anthropic, PBC. This plugin is not affiliated with or endorsed by either. Apache-2.0, Flexible Piping Solutions LLC.
```

## Tags

piping toolset, ASME B31.3, ASME B31.1, pipe stress, pipe wall thickness, pipe support design, CAESAR II, AutoPIPE, AISC 360, ACI 318 anchors, ASCE 7, ChatGPT plugin, Codex plugin, OpenAI Codex, agent skills, piping engineering, pressure design, structural engineering, Claude plugin

## Thumbnail text

The assistant asks. A script computes. You read the table.

## Playlist / cross-links

Add to the same playlist as the Claude demo (FVhnm3sXS-o) and link each video's end screen to the other.
