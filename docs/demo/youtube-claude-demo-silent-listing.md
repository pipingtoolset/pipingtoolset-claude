# YouTube listing: PipingToolset for Claude demo (silent, captioned)

Built by `edit-tools/build_claude_demo_silent.py` from the step recordings (2026-10-28). It
replaces the narrated 2026-10-27 cut (40lcLzIzHEg) in the same format as the ChatGPT / Codex demo
(VHD-XIeQu2s): no voice, captions burned in, the same captions in the `.srt`. Published 2026-10-28 as
h7A6Fq1cbHs and embedded on `/claude/` (`VIDEO.id` in `scripts/seo/claude-content.mjs`, pipecalcpro
PR 149). The narrated video is no longer embedded anywhere on the site.

## Title

Piping Toolset for Claude: B31.3 wall thickness, a refused table value and a pipe support check

## Description

```
Seven ASME B31.1 / B31.3 piping skills for Claude Code and Claude Cowork, from the people who build the free calculators at pipingtoolset.com. No narration: captions describe each step.

What you see:
• pipingtoolset.com and the /claude/ page: what a run looks like, the seven skills, the three rules, where your data goes.
• Install in the Claude desktop app: download piping-toolset.plugin, Settings › Plugins › Add › Upload plugin; seven skills appear under PipingToolset.
• Prompt 1, pressure-design: B31.3-2022, NPS 6 seamless, 750 psig at 600 F, S = 17,900 psi from the user's copy. The skill runs pressure_design.py: t = 0.1365 in, tm = 0.1990 in, order 0.2274 in; 0.280 in nominal passes with 1,008 psig allowable, and the sheet lists the gaps a reviewer will flag.
• Prompt 2: "What is the allowable stress for A106 Grade B at 650 F? Just give me the number." No number. It names Table A-1 (A-1C in 2024) and the row to read.
• Prompt 3, pipe-support: PS-201, a CSA type 1 t-post with CAESAR II restraint loads. support_calc.py runs 23 ASCE 7-22 LRFD combinations (governing: arm-to-column weld base metal, UR 0.888), the optimizer re-runs at a 0.85 cap (W8X10 arm, 7/8 in plate, 5/8 in anchors, 0.834), and four files land in the working folder.
• The calc report opened in Notepad, and the changelog that is the recall channel.

Three rules hold in every skill: Claude never does the arithmetic, it never recalls a code table value, and the edition is an input, never a silent default. The skills and scripts make no network calls, carry no telemetry and need no account with us. The optional Engineering Data connector, if you enable it, sends only lookup keys.

Install
  Cowork: download piping-toolset.plugin from the latest GitHub release, drag it into a chat, press Accept.
  Claude Code: /plugin marketplace add pipingtoolset/pipingtoolset-claude, then /plugin install piping-toolset@pipingtoolset.

Landing page: https://pipingtoolset.com/claude/
For ChatGPT and Codex: https://pipingtoolset.com/openai/
Source, releases, changelog: https://github.com/pipingtoolset/pipingtoolset-claude
Free calculators: https://pipingtoolset.com/calculators/

Chapters
0:00 Title
0:05 pipingtoolset.com and the /claude/ page
0:42 Download and install in the Claude desktop app
1:36 The seven skills in the plugin menu
1:54 Prompt 1: B31.3 wall thickness (pressure-design)
2:12 The result, the hand checks and the review items
2:54 Prompt 2: a table value is refused
3:18 Prompt 3: pipe support PS-201 (pipe-support)
3:36 The answer, the fixes before issue, the optimizer pick
3:52 The working folder and the calc report
4:14 Open source, fixtures, the changelog
4:50 Links

Results are engineering aids. The engineer of record verifies them before issue. Claude is a product of Anthropic, PBC; this plugin is not affiliated with or endorsed by Anthropic. Apache-2.0, Flexible Piping Solutions LLC.
```

## Tags

piping toolset, ASME B31.3, ASME B31.1, pipe stress, pipe wall thickness, pipe support design, CAESAR II, AutoPIPE, AISC 360, ACI 318 anchors, ASCE 7, Claude plugin, Claude Cowork, Claude Code, agent skills, piping engineering, pressure design, structural engineering

## Thumbnail text

Claude asks. A script computes. You read the table.

## Playlist / cross-links

Same playlist as the ChatGPT / Codex demo (VHD-XIeQu2s); link each video's end screen to the other.
