# PipingToolset (directory edition)

Method, review and checklist guidance for ASME B31.1 / B31.3 piping stress work, by
pipingtoolset.com. Version 0.10.2.

## What this edition is

Six skills that teach Claude how a piping stress engineer and a reviewer approach a job:

- `bolted-flange`
- `load-case-builder`
- `nozzle-load`
- `pipe-stress-check`
- `pipe-support`
- `stress-import`

Each skill carries its procedure, its code paragraph references and its rejection checklists.

## What it does not include

This edition has **no calculation scripts**. The plugin directory accepts scripts only from
Verified organizations, so the Python engine of the full plugin is left out here. Claude works
each check by hand from the cited method, shows the steps, and marks every numeric result
`HAND CALCULATION, NOT ENGINE-VERIFIED`. Nothing in this edition prints PASS or issue-grade
wording, and it does not build PCF or neutral files through a validator.

The full plugin, with the fixture-verified engine, the file builders and the validators, is at
[github.com/pipingtoolset/pipingtoolset-claude](https://github.com/pipingtoolset/pipingtoolset-claude). The same engine runs the calculators at
[pipingtoolset.com](https://pipingtoolset.com).

## Code tables

No ASME, API or PIP table values are embedded. You read allowables, moduli, ratings and
coefficients from your licensed copy. An optional connector (`pipingtoolset-data`) serves cited
table values to signed-in paid accounts; the skills work without it.

## Engineering responsibility

Output is an aid to a qualified engineer and is not a sealed calculation. Check every value
against the governing code edition before issue.

## License and affiliation

Apache-2.0. Flexible Piping Solutions LLC. Not affiliated with or endorsed by Anthropic, ASME,
API or PIP.
