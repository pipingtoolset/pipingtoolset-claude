# Piping Toolset for Claude

Piping engineering skills for Claude from [Piping Toolset](https://pipingtoolset.com), built by a licensed piping engineer. **Private beta — not yet released.**

| Skill | Status |
|---|---|
| `load-case-builder` — complete ASME B31.1/B31.3 static load case sets for CAESAR II and AutoPIPE, with references that never go stale | Available |
| `pressure-design` — code-basis interview and copyright-safe B31 pressure design | Available |
| `stress-screening` — sustained, occasional and expansion hand checks | Available |

## Install (Claude Code / Cowork)

```
/plugin marketplace add <path-or-github-repo>
/plugin install piping-toolset@pipingtoolset
```

For local testing, run `/plugin marketplace add <path-to-this-checkout>` in Claude Code.

## What the skills will not do

They never reproduce tabulated code values (allowable stresses, moduli, SIFs, spans, ASCE 7 coefficients). They name the table, row and edition and ask you to read the value from your own licensed copy. Results are engineering aids; the engineer of record verifies them before issue.

## Development

Tests use the Python standard library only:

```
python -m unittest discover -s tests -v
```

`tests/golden/` locks the generator's output for the worked example. A change to case order, combination strings or QC text must be a deliberate golden update, reviewed by the P.E.

See `ROADMAP.md` for the plan and open items.

Copyright © 2026 Flexible Piping Solutions LLC. All rights reserved. Licence terms will be set before public release.
