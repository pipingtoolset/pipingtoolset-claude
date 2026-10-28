# YouTube listing: PipingToolset for ChatGPT and Codex demo

Built by `edit-tools/build_codex_demo.py` from the five Codex recordings (2026-10-28). Upload
`PipingToolset_for_ChatGPT_Codex_demo.mp4` (1920x1080, 30 fps, 4:12, silent) and attach
`PipingToolset_for_ChatGPT_Codex_demo.srt` as the English subtitle track; the same captions are
burned in, so the track is for search and accessibility. After publishing, put the video id into
`VIDEO.id` in `scripts/seo/openai-content.mjs` (pipecalcpro) and the `/openai/` page switches from
the Claude demo to this one.

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

Three rules hold in every skill: the assistant never does the arithmetic, it never recalls a code table value, and the edition is an input, never a silent default. The skills and scripts make no network calls, carry no telemetry and need no account with us. The optional Engineering Data connector, if you enable it, sends only lookup keys.

Install
  codex plugin marketplace add pipingtoolset/pipingtoolset-claude
  then install PipingToolset from the Plugins view in the ChatGPT desktop app or Codex.

Landing page: https://pipingtoolset.com/openai/
For Claude: https://pipingtoolset.com/claude/
Source, releases, changelog: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/

Chapters
0:00 Title
0:05 Install from the marketplace in the ChatGPT desktop app
0:51 Prompt 1: B31.3 wall thickness (pressure-design)
1:14 The result and the review items
1:33 Prompt 2: a table value is refused
1:55 Prompt 3: pipe support PS-201 (pipe-support)
2:18 The skill asks, then 23 LRFD combinations
2:47 Optimizer re-run and the ASSUMED list
3:03 The calc report, limit states and compliance matrix
3:28 Reviewer findings and optimized alternatives
3:47 Files written to the working folder
4:03 Links

Results are engineering aids. The engineer of record verifies them before issue. ChatGPT and Codex are products of OpenAI; Claude is a product of Anthropic, PBC. This plugin is not affiliated with or endorsed by either. Apache-2.0, Flexible Piping Solutions LLC.
```

## Tags

piping toolset, ASME B31.3, ASME B31.1, pipe stress, pipe wall thickness, pipe support design, CAESAR II, AutoPIPE, AISC 360, ACI 318 anchors, ASCE 7, ChatGPT plugin, Codex plugin, OpenAI Codex, agent skills, piping engineering, pressure design, structural engineering, Claude plugin

## Thumbnail text

The assistant asks. A script computes. You read the table.

## Playlist / cross-links

Add to the same playlist as the Claude demo (40lcLzIzHEg) and link each video's end screen to the other.
