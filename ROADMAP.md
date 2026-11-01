# PipingToolset skill pack — roadmap

One plugin, `piping-toolset` (display name **PipingToolset**), with seven skills distributed as a group.

| Skill | What it does | Status |
|---|---|---|
| `load-case-builder` | Complete B31.1/B31.3 static load case sets for CAESAR II and AutoPIPE, generated symbolically so references never go stale; QC gate; report extraction matrix | Built. 0.8.0: writes the first project basis record of a session (code, edition, states, software, ASSUMED block) and fills its spec from one |
| `pressure-design` | Code-basis interview, edition logic and copyright-safe lookups for B31.3/B31.1 pressure design: wall thickness, allowable pressure, branch reinforcement, bends, miters, leak test | Built. 0.8.0: P, edition and W_basis from the project basis record; result status with pointer-only `code_values` entries |
| `stress-screening` | Sustained / occasional / expansion hand checks, f factor by edition, SIF-source resolution, formal-analysis exemption, support spans, springs | Built. 0.8.0: fatigue equation and N, exemption code and edition from the project basis record; known limits listed as not checked |
| `pipe-support` | Support assembly check (ASCE 7-22 combos from CAESAR II loads, AISC 360-22 members/welds/bolts, DG1 base plate, ACI CODE-318-25 Ch. 17 anchors with 318-19 selectable, pier), review findings, optimizer, calc report | Built (0.3.0; header-beam check and WT stem orientation 0.3.2; 0.8.0 title block, load units and axes from the project basis record, verdict follows the result status; 0.9.0 ACI CODE-318-25 anchorage and AISC 360-22 conformance port). Next: fatigue/vibration/seismic workflows (plan phase 4), company-standard detail library |
| `iso-to-pcf` | PDF stress isometrics to a CAESAR II PCF: JSON walk spec, exact-fraction builder, CAESAR II safe record set, validator | Built (0.2.0) — live CAESAR II import confirmed 2026-10-23 (four-file ladder incl. the demo line); 0.8.0 axes and line reference from the project basis record, RESULT line follows the result status |
| `nozzle-load` | Piping loads on equipment nozzles against the allowables for that equipment: API 610 Table 5 and Annex F, API 617 / 611 / 612 and NEMA SM-23 combined form, API 660 / 661 / 560 per-component and header-sum checks, API 650 Annex P ordinates, the PVP2011-57100 method as the default for pressure vessels with no API allowable, PIP RECE002 design-stage margins as an owner practice | Built (0.5.0; 0.8.0 design temperature and owner-factor basis from the project basis record, derived sets without a status held for a manual check). Next: VIII-2 4.5.15 local-stress module (WRC 537 / 297 curve values user-supplied), CAESAR II restraint-summary parser |
| `bolted-flange` | Piping loads on bolted flanged joints: mandatory pressure-equivalent screen against the user-read B16.5 rating, then the BPVC VIII-2 Part 4.16 (Appendix 2 method) analysis for integral and loose flanges with rigidity | Built (0.5.0; 0.8.0 P from the project basis record, no PASS banner while hub factors are reconstructed). Next: UG-44(b) / 4.16.12 interaction, ASME III NC-3658.3 service levels, EN 1591-1 screen |

**0.8.0 (B8, B9):** one shared project basis record (`pipingtoolset.project-basis/1`) consumed by all seven skills, and one result-status taxonomy (calculated, screening, manual check required, pointer only, not checked) with the banner rule on every calc sheet. Shared code is copied byte for byte from `tools/shared/` by `tools/sync_shared_blocks.py`; `tests/test_project_basis_handoff.py` runs the seven scripts on one record. Open for a pack-wide ruling: whether `not checked` should rank below `calculated` in the result word, and one word for an ASSUMED record item in every skill.

## Remaining before release

1. Engineer-of-record review of every page of the seven skills.
2. Eval prompt set per skill (`tests/e2e/PROMPTS.md` is the starting set).
3. Licence terms and pricing decided.
4. ~~Repository history squashed before the first public push.~~ Repository made public 2026-10-27 without a squash: the history was scanned (no secrets, single committer, largest blob the pipe-support golden file) and the drafts on pipingtoolset.com needed working links for the launch video.

## Rules every skill in this pack follows

1. **No tabulated ASME, API or PIP values**, ever — allowables, moduli, SIFs, spans, ASCE 7 hazard coefficients, PIP tables. Name the table, row and edition; the user reads it from their licensed copy. The one disclosed exception is pipe-support, which embeds the AISC 360-22 tables and the AISC Shapes Database (both published free by AISC), the ASCE 7-22 load-combination factors and the ACI 318-19 Ch. 17 factors its equations need; each is listed in `skills/pipe-support/references/code-basis.md`.
2. **One engine.** Every script that computes a code equation reproduces the pipingtoolset.com calculation engine's fixture cases exactly (`tests/fixtures/calc-core`, refreshed with `tools/sync_fixtures.py`); a red parity test blocks release.
3. **Edition is an input**, never a silent default; unanswered basis items are marked ASSUMED.
4. **Every number a skill states comes from a script run**, including side comparisons.
5. **No personal or third-party proprietary material** — enforced by `tests/content_guard.py`.
