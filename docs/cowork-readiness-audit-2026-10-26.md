# PipingToolset plugin — Cowork readiness audit

Date: 2026-10-26. Plugin `piping-toolset` 0.3.2 at commit a9f5a6e (main). Auditor: Kai (orchestrator session).

Goal: a piping engineer who has never opened the Claude Code console installs the plugin in
Claude Cowork (the desktop app's knowledge-work mode), picks a skill, and gets a defensible
calc sheet without typing a slash command or a shell command.

## Verdict

🟡 **Close. The plugin is structurally Cowork-compatible today; what blocks a non-console user is
documentation and skill wording, not code.** Three must-fix items, five should-fix items, one live
test still owed. Estimated effort: one day of edits plus a one-hour Cowork session.

## Evidence base

| Checked | Result |
|---|---|
| `claude plugin validate plugins/piping-toolset` and the marketplace manifest | Both pass, nothing to report |
| Component types used | Skills only (`skills/*/SKILL.md` + `references/` + `scripts/`). No `commands/`, agents, hooks or MCP. This is exactly the shape Cowork's own plugin guide recommends |
| Script dependencies | Python standard library only (math, json, argparse, fractions, decimal, csv). No pip, no network |
| Script portability | All five entry points run by **absolute path from a foreign working directory** and write outputs there (tested from the scratchpad: pressure_design, stress_screening, loadcase_gen, support_calc, build_pcf + validate_pcf, all exit 0). Data files load relative to `__file__` (`aisc_shapes.json`) |
| Plugin size | 1.1 MB including icon |
| Python in the Cowork sandbox | Not directly inspectable here (no Cowork install on this PC). Inferred from Anthropic's account-synced xlsx and pdf skills, which run `python scripts/...` with pip libraries "preinstalled" and poppler's `pdftotext`. The Cowork plugin guide uses `/tmp`, `zip -r` and `mnt/.plugins`, so the sandbox is Linux |
| SKILL.md word counts | stress-screening 4,163; load-case-builder 4,042; pressure-design 3,373; iso-to-pcf 1,596; pipe-support 1,106. Cowork guidance: body under 3,000 words, ideally 1,500–2,000 |

Not verified: an actual Cowork session with the plugin installed. The 2026-08-01 memory note on
Cowork's Windows-side layout (`local-agent-mode-sessions`, Desktop Commander as the only
filesystem route) no longer matches the current plugin guide, which describes a Linux sandbox with
mounted plugins. Treat that note as stale until a live run confirms the current behaviour.

## Status (same day)

Fixes 1, 2 and 5 applied on branch `claude/kai-cowork-usability-audit-03c2b9` (five SKILL.md files, 354 tests green, validator clean; three description tests pin exact phrases such as "formal analysis exemption", "schedule check" and a 400-character ceiling, so future rewrites must keep them). Fixes 3, 4, 6, 7, 8 and the live Cowork test remain.

## Must fix (blocks a Cowork user)

### 1. "Run from this skill's directory" — change to absolute script paths and outputs in the working folder

Four skills instruct: *Run it from this skill's directory*, and every example is
`python scripts/<tool>.py ...` with outputs such as `calc.md`, `result.json`, `line.pcf`, `job.json`
written to the current directory. In Cowork the plugin is a read-only mount and the working
directory is the session's outputs folder, so Claude either fails to write or wanders into the
plugin tree. The scripts themselves need no change (proven above).

Edit each SKILL.md "How to run" section to the pattern Anthropic's own xlsx skill uses:

- "Script paths below are relative to this skill's directory; call them by their full path from
  wherever the session is working."
- "Write `job.json`, reports, JSON results and PCF files to the current working directory (in
  Cowork, the outputs folder, where the user can download them). Never write into the skill folder."

Files: `skills/pressure-design/SKILL.md` (How to run), `skills/stress-screening/SKILL.md`
(Running the tool), `skills/load-case-builder/SKILL.md` (Running the generator),
`skills/pipe-support/SKILL.md` (step 3), `skills/iso-to-pcf/SKILL.md` (steps 4–5).

Side benefit: in Cowork the calc report, result JSON and PCF then surface as downloadable files,
which is the deliverable a reviewer wants anyway.

### 2. Skill descriptions must carry trigger phrases — Cowork has no `/piping-toolset:` prefix

The README, every e2e prompt and the "invoke by name" advice assume the Claude Code slash form.
Cowork users pick a skill from the skills menu or rely on Claude matching the frontmatter
description to what they typed. The five descriptions are accurate capability summaries, but not
written as triggers, and `pressure-design` is second person ("You supply S, E, W, Y").

Rewrite each description third person with the phrases an engineer actually types. Keep the
`name` fields unchanged so existing installs keep working. Draft:

| Skill | Trigger phrases to include |
|---|---|
| pressure-design | "wall thickness", "minimum thickness", "does schedule 40 work", "MAWP", "allowable pressure", "branch reinforcement", "miter", "bend thinning", "hydrotest pressure", "leak test", "B31.3", "B31.1", "304.1.2", "104.1.2" |
| stress-screening | "sustained stress", "expansion stress", "S_A", "f factor", "cycles", "SIF", "B31J", "Appendix D", "flexibility exemption", "support span", "spring variability", "1.33 Sh", "k factor", "check what CAESAR applied" |
| load-case-builder | "load cases", "load case set", "L1 L2", "combination cases", "CAESAR II", "AutoPIPE", "hanger cases", "wind seismic cases", "PSV thrust", "steam-out", "friction cases", "occasional allowable" |
| pipe-support | "pipe support", "t-post", "trapeze", "goalpost", "cantilever arm", "base plate", "anchor bolts", "ESR", "W6X15", "restraint loads", "check this support", "optimize the support" |
| iso-to-pcf | "isometric", "iso PDF", "PCF", "CAESAR II import", "orphan node", "stress iso to CAESAR", "Isogen", "SKEY" |

Also update the README to say: in Cowork, name the skill in plain words ("use the pipe support
skill to check PS-201…") or pick it from the skills menu; the slash form is for Claude Code only.

### 3. An install path with no console: ship a `.plugin` file and write the click path

README "Install" is `/plugin marketplace add …` and `/plugin install …`, both Claude Code CLI.
Cowork installs a plugin two ways: a marketplace added from a GitHub URL in the app's plugin
settings, or a `.plugin` file (a zip of the plugin folder) dropped into the chat, which shows a
preview and an Accept button. The second is the one a new user can follow without help.

- Add a CI job (and a GitHub Release asset) that builds `piping-toolset.plugin`:
  `cd plugins/piping-toolset && zip -r ../../piping-toolset.plugin . -x "*.DS_Store"`.
  GitHub Releases is already the UNCONSERVATIVE-FIX recall channel, so the `.plugin` belongs there.
- README gets a "Cowork" install section: download the `.plugin` from the release, drag it into a
  Cowork chat, press Accept; or add the marketplace `pipingtoolset/pipingtoolset-claude` in
  Settings → Plugins. State that updates mean re-installing the new `.plugin` (installed copies keep
  a defect until updated, as the CHANGELOG already says).
- The existing `.claude-plugin/marketplace.json` is the shared schema and validates; no change.

## Should fix (quality and context cost in Cowork)

4. **Trim the three long SKILL.md bodies under 3,000 words.** Cowork loads the user's whole
   account skill set, so body length costs context on every trigger. Move to `references/`:
   stress-screening's module table and edition tables; load-case-builder's PN19 section, the
   AutoPIPE map and the worked example; pressure-design's per-module equation blocks (keep the
   interview, rules and output format in the body). Golden tests are unaffected.
5. **Remove the PowerShell-only advice.** The here-string example in pressure-design's How to run
   is Windows-console noise in a Linux sandbox. Replace with shell-neutral wording: "write the
   inputs to `job.json` with the file tool, then pass `--input-file job.json`." Same idea covers
   Claude Code on Windows, which was the reason the note exists.
6. **iso-to-pcf PDF route.** `references/reading-isos.md` leads with `pip install pymupdf (the
   user's environment)`. In Cowork, pip or network may be unavailable, while `pdfplumber`, `pypdf`
   and `pdftotext -layout` are preinstalled (Anthropic's pdf skill relies on them). Lead with
   those; keep PyMuPDF as the optional faster route. Add one line: in Cowork the user attaches the
   iso PDF to the chat.
7. **A Cowork test column in `tests/e2e/PROMPTS.md`.** The ten prompts are the right set; add a
   plain-language form of each (no slash prefix) and a pass check that the intended skill
   triggered. `run_e2e.py` stays Claude Code only; the Cowork pass is a manual checklist until
   Cowork has a headless runner.
8. **Say what the plugin needs, once.** A short "Requirements" line in README and in each
   description's tail: Python 3.9+ in the environment that runs the skills (Claude Code on your
   machine, or Cowork's built-in sandbox), nothing installed, nothing sent to PipingToolset.

## What already works and should not change

- Skills-only plugin, shared schema, validator-clean, under 2 MB.
- Standard-library scripts with `__file__`-relative data, proven path-independent.
- Interview-first skill design. A new Claude user is still a piping engineer; the basis interview
  is the right front door and needs no simplification.
- Copyright boundary, parity tests, golden files, content guard: all untouched by this work.

## Suggested release

Ship as **0.4.0**: no calculation changes, but the invocation surface (descriptions, run
instructions, install path) changes for every user. CHANGELOG entry under a "Cowork support"
heading. Then the one-hour live test: install the `.plugin` in a Cowork session, run E1 and E9 in
plain language, confirm the script ran (not mental math), the calc sheet landed in the outputs
folder, and the right skill triggered against whatever other skills that account has.

## Order of work

1. SKILL.md run-instruction wording (fix 1) and description rewrite (fix 2) — one PR, docs only.
2. README Cowork section + CI `.plugin` packaging + Release asset (fix 3).
3. Body trims to `references/` (fix 4), PowerShell note (5), PDF route (6), PROMPTS column (7),
   requirements line (8).
4. Bump to 0.4.0, CHANGELOG, tag, release with the `.plugin` attached.
5. Live Cowork test; record the result (and the current Cowork sandbox layout) in the project
   memory bank, replacing the stale 2026-08-01 note.
