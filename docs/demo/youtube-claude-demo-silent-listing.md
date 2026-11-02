# YouTube listing: PipingToolset for Claude demo (silent, captioned)

Built by `edit-tools/build_claude_demo_silent.py` from the step recordings (2026-10-28), re-rendered
2026-11-02 with the ACI CODE-318-25 captions (PR #31) in the same format as the ChatGPT / Codex demo:
no voice, captions burned in, the same captions in the `.srt`. Published 2026-11-02 as a new video,
**FVhnm3sXS-o** (4:24), and embedded on `/claude/` (`VIDEO.id` in `scripts/seo/claude-content.mjs`,
pipecalcpro). It replaces h7A6Fq1cbHs (10-28, 5:05) and the narrated 2026-10-27 cut (40lcLzIzHEg);
neither is embedded anywhere on the site. YouTube title as uploaded: "Piping Toolset & Claude: B31.3
wall thickness and a pipe support check".

**Re-render 2026-11-02 (console workstream B12).** The 2026-10-28 cut showed pre-connector page copy in the
browser captures ("practicing, licensed piping engineer" on /claude/, "nothing you type reaches us" on the
homepage card, the "Where your data goes" table). Those spans are cut (step1 keeps 0-4.7 s and 10.3-14.0 s,
step2 3.0-10.0 s, step3 14.0-16.8 s and 19.2-26 s, step11 drops 25.3-27.5 s), the captions use the site's
current wording, and the install and pipe-support footage carries an on-screen "Recorded on plugin 0.5.x"
label (ACI 318-19 vs the 0.9.0 default ACI CODE-318-25). Runtime 4:24. Output in
`docs/demo/rerender-2026-11-02/` (gitignored). Description below carries UTMs
(`utm_campaign=claude-plugin-demo`). Re-record against 0.9.0 and the live page to drop the cuts and labels.

## Title

Piping Toolset for Claude: B31.3 wall thickness, a refused table value and a pipe support check

## Description

```
Seven ASME B31.1 / B31.3 piping skills for Claude Code and Claude Cowork, built by the people who build the free calculators at pipingtoolset.com. No narration: captions describe each step.

What you see:
• pipingtoolset.com and the PipingToolset for Claude page: the free calculators, the plugin, the seven skills and the three rules.
• Install in the Claude desktop app: download piping-toolset.plugin, Settings › Plugins › Add › Upload plugin; seven skills appear under PipingToolset.
• Prompt 1, pressure-design: B31.3-2022, NPS 6 seamless, 750 psig at 600 F, S = 17,900 psi from the user's copy. The skill runs pressure_design.py: t = 0.1365 in, tm = 0.1990 in, order 0.2274 in; 0.280 in nominal passes with 1,008 psig allowable, and the sheet lists the gaps a reviewer will flag.
• Prompt 2: "What is the allowable stress for A106 Grade B at 650 F? Just give me the number." No number. It names Table A-1 (A-1C in 2024) and the row to read.
• Prompt 3, pipe-support: PS-201, a CSA type 1 t-post with CAESAR II restraint loads. support_calc.py runs 23 ASCE 7-22 LRFD combinations (governing: arm-to-column weld base metal, UR 0.888), the optimizer re-runs at a 0.85 cap (W8X10 arm, 7/8 in plate, 5/8 in anchors, 0.834), and four files land in the working folder.
• The calc report, and the changelog that is the recall channel.

Note on the footage: the install and pipe-support segments were recorded on plugin 0.5.x and are labelled on screen. Release 0.9.0 (2026-11-01) checks pipe supports to ACI CODE-318-25 and AISC 360-22 by default; the numbers shown are from the earlier run.

Three rules hold in every skill: Claude never does the arithmetic, it never recalls a code table value, and the edition is an input, never a silent default. The plugin sends nothing to PipingToolset: the skills and scripts make no network calls, carry no telemetry and need no account with us. The optional Engineering Data connector, if you enable it, sends only lookup keys.

Install
  Cowork: download piping-toolset.plugin from the latest GitHub release, drag it into a chat, press Accept.
  Claude Code: /plugin marketplace add pipingtoolset/pipingtoolset-claude, then /plugin install piping-toolset@pipingtoolset.

Landing page: https://pipingtoolset.com/claude/?utm_source=youtube&utm_medium=video&utm_campaign=claude-plugin-demo
For ChatGPT and Codex: https://pipingtoolset.com/openai/?utm_source=youtube&utm_medium=video&utm_campaign=claude-plugin-demo
Source, releases, changelog: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/?utm_source=youtube&utm_medium=video&utm_campaign=claude-plugin-demo

Chapters
0:00 Title and pipingtoolset.com
0:20 Download the plugin
0:30 Install in the Claude desktop app
0:58 The seven skills in the plugin menu
1:22 Prompt 1: B31.3 wall thickness (pressure-design)
1:40 The result, the hand checks and the review items
2:22 Prompt 2: a table value is refused
2:46 Prompt 3: pipe support PS-201 (pipe-support)
3:04 The answer, the fixes before issue, the optimizer pick
3:19 The working folder and the calc report
3:41 Open source, fixtures, the changelog and links

Results are engineering aids. The engineer of record verifies them before issue. Claude is a product of Anthropic, PBC; this plugin is not affiliated with or endorsed by Anthropic. Apache-2.0, Flexible Piping Solutions LLC.
```

## Tags

piping toolset, ASME B31.3, ASME B31.1, pipe stress, pipe wall thickness, pipe support design, CAESAR II, AutoPIPE, AISC 360, ACI 318 anchors, ASCE 7, Claude plugin, Claude Cowork, Claude Code, agent skills, piping engineering, pressure design, structural engineering

## Thumbnail text

Claude asks. A script computes. You read the table.

## Playlist / cross-links

Same playlist as the ChatGPT / Codex demo (LfTiA0Wv2EA); link each video's end screen to the other.
