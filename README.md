# PipingToolset for Claude

**B31 calcs you can reproduce and defend in review, with Claude.**
Claude does the interview. A script does the math. You read the table.

Four ASME B31.1 / B31.3 piping engineering skills for Claude Code and Cowork, from the
people who build the free calculators at [pipingtoolset.com](https://pipingtoolset.com).
Written and maintained by a practicing piping engineer at Flexible Piping Solutions LLC.

| Skill | What it does |
|---|---|
| `pressure-design` | Code-basis interview, then wall thickness, allowable pressure, branch reinforcement, bends, miters and leak-test pressure to B31.3 / B31.1, with a calc sheet that shows the edition, the equation and every input |
| `stress-screening` | Sustained, occasional and expansion hand checks, the f factor by edition, which document supplies the SIFs, the formal-analysis exemption, support spans and spring variability |
| `load-case-builder` | Complete B31.1 / B31.3 static load case sets for CAESAR II and AutoPIPE, generated symbolically so references never go stale, with a QC gate and a report extraction matrix |
| `iso-to-pcf` | PDF stress isometrics to a clean CAESAR II PCF: Claude transcribes the drawing, a script builds the geometry in exact fractions (bend tangents, branches, sloped profiles) and a validator catches orphan nodes, zero-length elements and off-line supports before import |

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

Requires Claude Code (or Cowork) with Python 3 available on the machine that runs the skills.

```
/plugin marketplace add pipingtoolset/pipingtoolset-claude
/plugin install piping-toolset@pipingtoolset
```

For a local checkout: `/plugin marketplace add <path-to-this-checkout>`.

Invoke a skill by name, because other installed skills on the same topics would otherwise compete:
`/piping-toolset:pressure-design`, `/piping-toolset:stress-screening`, `/piping-toolset:load-case-builder`,
`/piping-toolset:iso-to-pcf`. The plugin shows as **PipingToolset** in the plugin list; its id (and the
command prefix) stays `piping-toolset` so existing installs keep working.

## Try it in twenty seconds

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

See [`ROADMAP.md`](ROADMAP.md) for the plan and [`CHANGELOG.md`](CHANGELOG.md) for releases.
A release labelled **UNCONSERVATIVE-FIX** corrects a result that could have been less conservative
than the code requires; update when you see one.

## Licence

Copyright © 2026 Flexible Piping Solutions LLC. Licensed under the
[Apache License, Version 2.0](LICENSE). "Piping Toolset" is a name of Flexible Piping Solutions LLC;
see [NOTICE](NOTICE).
