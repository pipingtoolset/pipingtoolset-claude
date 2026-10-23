# PipingToolset skill pack — roadmap

One plugin, `piping-toolset` (display name **PipingToolset**), with four skills distributed as a group.

| Skill | What it does | Status |
|---|---|---|
| `load-case-builder` | Complete B31.1/B31.3 static load case sets for CAESAR II and AutoPIPE, generated symbolically so references never go stale; QC gate; report extraction matrix | Built |
| `pressure-design` | Code-basis interview, edition logic and copyright-safe lookups for B31.3/B31.1 pressure design: wall thickness, allowable pressure, branch reinforcement, bends, miters, leak test | Built |
| `stress-screening` | Sustained / occasional / expansion hand checks, f factor by edition, SIF-source resolution, formal-analysis exemption, support spans, springs | Built |
| `iso-to-pcf` | PDF stress isometrics to a CAESAR II PCF: JSON walk spec, exact-fraction builder, CAESAR II safe record set, validator | Built (0.2.0) — live CAESAR II import confirmed 2026-10-23 (four-file ladder incl. the demo line) |

## Remaining before release

1. Engineer-of-record review of every page of the four skills.
2. Eval prompt set per skill (`tests/e2e/PROMPTS.md` is the starting set).
3. Licence terms and pricing decided.
4. Repository history squashed before the first public push.

## Rules every skill in this pack follows

1. **No tabulated code values**, ever — allowables, moduli, SIFs, spans, ASCE 7 coefficients, PIP tables. Name the table, row and edition; the user reads it from their licensed copy.
2. **One engine.** Every script that computes a code equation reproduces the pipingtoolset.com calculation engine's fixture cases exactly (`tests/fixtures/calc-core`, refreshed with `tools/sync_fixtures.py`); a red parity test blocks release.
3. **Edition is an input**, never a silent default; unanswered basis items are marked ASSUMED.
4. **Every number a skill states comes from a script run**, including side comparisons.
5. **No personal or third-party proprietary material** — enforced by `tests/content_guard.py`.
