# PipingToolset for Claude

**B31 calcs you can reproduce and defend in review, with Claude.**
Claude does the interview. A script does the math. You read the table.

Seven piping engineering skills for Claude Code and Cowork, and for any assistant that reads
the Agent Skills format (OpenAI Codex and ChatGPT, Cursor, GitHub Copilot and others), from the
people who build the free calculators at [pipingtoolset.com](https://pipingtoolset.com).
Written and maintained by a practicing piping engineer at Flexible Piping Solutions LLC.

| Skill | What it does |
|---|---|
| `pressure-design` | Code-basis interview, then wall thickness, allowable pressure, branch reinforcement, bends, miters and leak-test pressure to B31.3 / B31.1, with a calc sheet that shows the edition, the equation and every input |
| `stress-screening` | Sustained, occasional and expansion hand checks, the f factor by edition, which document supplies the SIFs, the formal-analysis exemption, support spans and spring variability |
| `load-case-builder` | Complete B31.1 / B31.3 static load case sets for CAESAR II and AutoPIPE, generated symbolically so references never go stale, with a QC gate and a report extraction matrix |
| `pipe-support` | Pipe support assemblies (arm, column, welds, bolts, base plate, anchors, pier) checked for CAESAR II restraint loads: ASCE 7-22 combinations, AISC 360-22, ACI 318-19 Chapter 17 and AWS D1.1 detailing, with a PE-style review, ranked code-passing alternatives (lighter, less field work, stocked sizes) and an engineer-ready calc report. The pipingtoolset.com PiperSTR engine, verified against a published PiperSTR report value for value |
| `iso-to-pcf` | PDF stress isometrics to a clean CAESAR II PCF: Claude transcribes the drawing, a script builds the geometry in exact fractions (bend tangents, branches, sloped profiles) and a validator catches orphan nodes, zero-length elements and off-line supports before import |
| `nozzle-load` | Piping forces and moments on equipment nozzles, checked the way the vendor will: API 610 Table 5 and Annex F for pumps, the API 617 / 611 / 612 and NEMA SM-23 combined form for compressors and turbines, API 660 / 661 / 560 per-component and header-sum checks for exchangers and heaters, API 650 Annex P ordinates for tank shells, and the PVP2011-57100 method as the default for a pressure vessel with no API allowable. The user reads every table row; the script applies the scaling rules and the ratios. PIP RECE002 design-stage margins as an owner practice |
| `bolted-flange` | Piping loads on a bolted flanged joint in a fixed order: the pressure-equivalent screen first, always, against the B16.5 rating the user reads, then the BPVC Section VIII Division 2 Part 4.16 analysis (the Appendix 2 method) for integral and loose flanges, with bolt area, hub, radial and tangential stresses and rigidity. Flange dimensions, gasket factors, ratings and allowables all come from the user's copies |

## How it works

1. **Claude never does the arithmetic.** Each skill ships standard-library Python scripts. Every
   number a skill states comes from a script run on inputs you supplied. The scripts reproduce the
   pipingtoolset.com calculation engine's locked test cases (`tests/fixtures/calc-core`; a red
   parity test blocks a release).
2. **Claude never recalls a code table value.** Allowable stresses, moduli, SIFs, spans, ASCE 7
   coefficients: the skill names the table, row and edition and asks you to read the value from
   your own licensed copy. Asking it for "just the number" is a pinned test, and the answer is no.
3. **The edition is an input, never a silent default.** Anything you leave unanswered is marked
   ASSUMED on the calc sheet.

Nothing you enter is sent to PipingToolset or Flexible Piping Solutions. The scripts run in your
own Claude environment; what you type goes to Claude under your own Anthropic account's terms.

## Install

### In Claude Cowork

1. Download `piping-toolset.plugin` from the
   [latest GitHub Release](https://github.com/pipingtoolset/pipingtoolset-claude/releases/latest)
   of pipingtoolset/pipingtoolset-claude.
2. Drag the file into a Cowork chat. A preview card appears; press **Accept**.

Or, in the app's plugin settings, add the marketplace `pipingtoolset/pipingtoolset-claude`.

To update, install the new `.plugin` from the latest release. An installed copy keeps any defect it
shipped with until you update it, so **UNCONSERVATIVE-FIX** releases (see
[`CHANGELOG.md`](CHANGELOG.md)) are the recall channel.

### In Claude Code

```
/plugin marketplace add pipingtoolset/pipingtoolset-claude
/plugin install piping-toolset@pipingtoolset
```

For a local checkout: `/plugin marketplace add <path-to-this-checkout>`.

### Other assistants

The skills are plain [Agent Skills](https://agentskills.io) and the plugin carries an
[Agent Plugins 1.0](https://agent-plugins.org) manifest, so the same repository installs into
assistants other than Claude. These commands need the repository to be **public**; while
`pipingtoolset/pipingtoolset-claude` is private they return "not found".

| Assistant | Command |
|---|---|
| OpenAI Codex (CLI, IDE, ChatGPT desktop) | `codex plugin marketplace add pipingtoolset/pipingtoolset-claude`, then install **PipingToolset** from the plugin picker |
| Any Agent Skills host via the `skills` CLI (Cursor, Copilot, Codex, Gemini CLI and others) | `npx skills add pipingtoolset/pipingtoolset-claude` |
| GitHub CLI | `gh skill install pipingtoolset/pipingtoolset-claude` |
| ChatGPT, Manus, Perplexity (file upload) | Upload `piping-toolset-skills.zip` from the [latest release](https://github.com/pipingtoolset/pipingtoolset-claude/releases/latest); it holds only the `skills/` folder |

Where the skills land after a CLI install:

| Scope | Path |
|---|---|
| Project (default) | `.agents/skills/<skill-name>/` in the current repository |
| User (`--global` / `-g`) | `~/.agents/skills/<skill-name>/` |

Hosts without a `/piping-toolset:` prefix see the seven skills by name (`pressure-design`,
`stress-screening`, `load-case-builder`, `pipe-support`, `iso-to-pcf`, `nozzle-load`, `bolted-flange`); name the one you want in
plain words, as in Cowork. Each skill's frontmatter states its only requirement, Python 3.9+ with
the standard library, so a host can check it before running a script.

### Requirements

Python 3.9 or newer wherever the skills run: your own machine for Claude Code; Cowork's built-in
sandbox provides it (confirmed on a live Cowork session with `tests/e2e/COWORK-CHECKLIST.md`,
2026-10-27). There is nothing else to install, and nothing is sent to PipingToolset.

### Invoking a skill

In Cowork, pick the skill from the skills menu or name it in plain words, for example "use the pipe
support skill to check PS-201" or "use the pressure design skill: B31.3-2022, NPS 6 ...". Naming it
matters, because other installed skills on the same topics would otherwise compete.

In Claude Code, use the slash form: `/piping-toolset:pressure-design`, `/piping-toolset:stress-screening`,
`/piping-toolset:load-case-builder`, `/piping-toolset:iso-to-pcf`, `/piping-toolset:pipe-support`,
`/piping-toolset:nozzle-load`, `/piping-toolset:bolted-flange`. The
plugin shows as **PipingToolset** in the plugin list; its id (and the command prefix) stays
`piping-toolset` so existing installs keep working.

## Try it in twenty seconds

In Cowork, drop the leading slash and say "use the pressure design skill:" instead.

```
/piping-toolset:pressure-design B31.3-2022, normal fluid service. NPS 6 seamless pipe, OD 6.625 in,
design 750 psig at 600 F, corrosion allowance 0.0625 in, 12.5% mill tolerance. My allowable S at
600 F is 17900 psi from my copy, E = 1.0, W = 1.0, Y = 0.4. What minimum thickness do I need and
does 0.280 in nominal wall work?
```

Expected: the script runs, t = 0.13650 in and t_m = 0.19900 in (¶304.1.2 Eq. (3a)), 0.280 × 0.875 =
0.245 in ≥ 0.19900 in, so the nominal wall is adequate; S, E, W and Y are echoed as user-supplied.

Then ask for what it will not give you:

```
/piping-toolset:pressure-design What's the allowable stress for A106 Grade B at 650 F under B31.3?
Just give me the number.
```

Expected: no number. It names B31.3 Table A-1 (A-1C in the 2024 edition), the material row and the
two temperature columns, and offers to interpolate once you have read both values.

More prompts, with pass criteria, are in [`tests/e2e/PROMPTS.md`](tests/e2e/PROMPTS.md).

## What the skills will not do

They never reproduce tabulated code values. They do not replace a flexibility analysis in CAESAR II
or AutoPIPE; `stress-screening` is a hand check of what the program applied. Results are engineering
aids. The engineer of record verifies them before issue, and you remain responsible for the result.

## Development

Tests use the Python standard library only:

```
python -m unittest discover -s tests -v
```

`tests/golden/` locks the load-case generator's output and the PCF builder's output (`demo-line.pcf`,
CRLF, kept byte-exact by `.gitattributes`) for the worked examples. A change to case order,
combination strings or QC text must be a deliberate golden update, reviewed by the engineer of record.
`tools/sync_fixtures.py --check` confirms the vendored calc-core fixture snapshot is current.
`python tools/package_plugin.py` builds `piping-toolset.plugin` (Cowork and Agent Plugins hosts) and
`piping-toolset-skills.zip` (skills-only upload) for a release; `tests/test_manifests.py` keeps the
Claude and Agent Plugins manifests in step.

See [`ROADMAP.md`](ROADMAP.md) for the plan and [`CHANGELOG.md`](CHANGELOG.md) for releases.
A release labelled **UNCONSERVATIVE-FIX** corrects a result that could have been less conservative
than the code requires; update when you see one.

## Licence

Copyright © 2026 Flexible Piping Solutions LLC. Licensed under the
[Apache License, Version 2.0](LICENSE). "Piping Toolset" is a name of Flexible Piping Solutions LLC;
see [NOTICE](NOTICE).
