# PipingToolset for Claude, ChatGPT and Codex

**B31 calcs you can reproduce and defend in review, with the assistant you already use.**
The assistant does the interview. A script does the math. You read the table.

Seven piping engineering skills, one plugin, installable in Claude Code and Claude Cowork, in
ChatGPT and OpenAI Codex, and in any assistant that reads the Agent Skills format (Cursor, GitHub
Copilot, Gemini CLI and others), from the people who build the free calculators at
[pipingtoolset.com](https://pipingtoolset.com). Written and maintained by a practicing piping
engineer at Flexible Piping Solutions LLC. The same folder carries both a Claude manifest and an
Agent Plugins 1.0 manifest, so the install you pick changes nothing about what the skills do.

The plugin is free and the skills run entirely on your side. An optional
[Engineering Data connector](#engineering-data-connector) can hand the assistant a cited code-table
value instead of making you look it up, within what your pipingtoolset.com plan covers. Every skill
works without it.

| | Claude | ChatGPT / Codex |
|---|---|---|
| Landing page | [pipingtoolset.com/claude/](https://pipingtoolset.com/claude/) | [pipingtoolset.com/openai/](https://pipingtoolset.com/openai/) |
| Install file | `piping-toolset.plugin` (drag into Cowork) | `codex plugin marketplace add pipingtoolset/pipingtoolset-claude` |
| Invoke | `/piping-toolset:pressure-design` or name it in Cowork | `$pressure-design` in Codex, name it in ChatGPT |
| Manifest read | `.claude-plugin/plugin.json` | `plugin.json` (Agent Plugins 1.0, `extensions.com.openai`) |
| Engineering Data connector | Declared by the plugin in `.mcp.json` | Not declared; you add it by hand (see [Add the connector](#add-the-connector)) |

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

1. **The assistant never does the arithmetic.** Each skill ships standard-library Python scripts.
   Every number a skill states comes from a script run on inputs you supplied. The scripts reproduce
   the pipingtoolset.com calculation engine's locked test cases (`tests/fixtures/calc-core`; a red
   parity test blocks a release).
2. **The assistant never recalls a code table value.** Allowable stresses, moduli, SIFs, spans,
   ASCE 7 coefficients: the skill names the table, row and edition and takes the value from one of
   two places, your own copy of the standard or, if you have enabled the optional connector and your
   plan covers the table, a connector lookup that arrives with its citation. Asking it for "just the
   number" with neither is a pinned test, and the answer is no. The one exception is `pipe-support`,
   which bundles the AISC 360-22 tables and the AISC Shapes Database (both published free by AISC) and
   the ASCE 7-22 and ACI 318-19 factors it uses; its `references/code-basis.md` lists every one.
3. **The edition is an input, never a silent default.** Anything you leave unanswered is marked
   ASSUMED on the calc sheet.

The skills make no network calls. Their scripts run in your own assistant's environment, and what
you type goes to Anthropic or OpenAI under the terms of your own account with them. The only part
of the plugin that talks to pipingtoolset.com is the optional
[Engineering Data connector](#engineering-data-connector), and it sends only what a table lookup
needs. Leave it disconnected and nothing you enter is sent to PipingToolset or Flexible Piping
Solutions.

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

### In ChatGPT and Codex

The plugin folder carries an [Agent Plugins 1.0](https://agent-plugins.org) manifest
(`plugins/piping-toolset/plugin.json`) with the OpenAI listing block, and the repository carries
`.agents/plugins/marketplace.json`, so OpenAI's tools read it directly.

1. With the Codex CLI installed, register the marketplace:

   ```
   codex plugin marketplace add pipingtoolset/pipingtoolset-claude
   ```

2. Install **PipingToolset** from the plugin picker: `/plugins` in the Codex CLI or IDE
   extension, or **Customize › Plugins** in the ChatGPT desktop app, where it shows with the
   PipingToolset mark and "By Flexible Piping Solutions LLC".
3. Invoke a skill as `$pressure-design` (or `/skills`) in Codex, or name it in plain words in
   ChatGPT, as in Cowork. Codex runs the scripts with your machine's Python 3.9+; the ChatGPT desktop
   app and Codex cloud run them in their own sandbox.

The OpenAI plugin directory listing is submitted from the same archive (`piping-toolset.zip`, the
`.plugin` under a `.zip` name, from the
[latest release](https://github.com/pipingtoolset/pipingtoolset-claude/releases/latest)); until it
is listed, the marketplace route above is the install.

### Other assistants

The skills are plain [Agent Skills](https://agentskills.io), so the same repository installs into
any host that reads that format.

| Assistant | Command |
|---|---|
| Any Agent Skills host via the `skills` CLI (Cursor, Copilot, Codex, Gemini CLI and others) | `npx skills add pipingtoolset/pipingtoolset-claude` |
| GitHub CLI | `gh skill install pipingtoolset/pipingtoolset-claude` |
| Manus, Perplexity and other skills-upload hosts | Upload `piping-toolset-skills.zip` from the [latest release](https://github.com/pipingtoolset/pipingtoolset-claude/releases/latest); it holds only the `skills/` folder, no manifest, no connector declaration and no logo |

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
2026-10-27). There is nothing else to install. The skills and their scripts send nothing anywhere.
With the connector declared, your assistant contacts pipingtoolset.com when a session starts and
when a skill asks for a value; every skill works with it disconnected. The connector is optional
and has its own section below.

### Invoking a skill

In Cowork, pick the skill from the skills menu or name it in plain words, for example "use the pipe
support skill to check PS-201" or "use the pressure design skill: B31.3-2022, NPS 6 ...". Naming it
matters, because other installed skills on the same topics would otherwise compete.

In Claude Code, use the slash form: `/piping-toolset:pressure-design`, `/piping-toolset:stress-screening`,
`/piping-toolset:load-case-builder`, `/piping-toolset:iso-to-pcf`, `/piping-toolset:pipe-support`,
`/piping-toolset:nozzle-load`, `/piping-toolset:bolted-flange`. The
plugin shows as **PipingToolset** in the plugin list; its id (and the command prefix) stays
`piping-toolset` so existing installs keep working.

## Engineering Data connector

An optional remote server for the Model Context Protocol (MCP): `pipingtoolset-data` at
`https://pipingtoolset.com/mcp` (Streamable HTTP, stateless). The plugin declares it in `.mcp.json`
for Claude Code and Cowork, so those hosts offer it. It does not declare it for Codex or the ChatGPT
desktop app: in 0.7.0 a declaration there made Codex ask for a sign-in at install, which an optional
connector must not do, so in those hosts you add it by hand (below). Installing the plugin does not
contact it or ask you to sign in. The plugin stays free, every skill works without the connector,
and the refusal prompts behave the same with it off. Setup and the dataset list:
[pipingtoolset.com/docs/connector/](https://pipingtoolset.com/docs/connector/).

### What is sent

The skills and their scripts make no network calls. When you enable the connector, the assistant
sends it only lookup keys: the standard, the material or table row, a temperature, a size. It does
not send your full inputs, loads, drawings or project data. Connecting contacts pipingtoolset.com;
disconnect the server in your host and nothing is sent there. A value the connector serves reaches
the script as a cited input marked as connector-supplied, next to the ones you typed, and the calc
sheet shows the source of each. A script still does all the arithmetic.

### What it serves

Currently:

| Needs | Served |
|---|---|
| No account | Worked examples of the data-free modules (`get_fixture_example`); ISOGEN SKEY and CAESAR II-safe PCF mappings (`get_skey_map`); AISC shapes (`get_aisc_shape`); pointers (`get_pointer`) to where a value is printed |
| A signed-in paid pipingtoolset.com account: Pro, Pro Plus or Ultimate | The ASME and API tables the plan covers, each cited to standard, edition, table and row. Pro: B31.3 Table A-1C and B31.1 Appendix A allowable stresses and bolting; the B31.3 E, W and Y and B31.1 E and y factor tables; B31J Table 1-1 component rows (row text only: the SIF number itself is still supplied by you or computed by a script); B31.1 Table 121.5-1 spans; BPE tables; B36.10M and B36.19M pipe dimensions (`get_pipe_dimensions`). Pro Plus adds B16.5 ratings and dimensions, B16.20, UCS-66 and BPVC VIII-2 Table 4.16.1 gasket factors. Ultimate adds API 610 Tables 5a and 5b, API 560 Tables 7 to 10, API 660 Table 2 and API 661 Table 4, one value per lookup (a six-component allowable set is six lookups, each cited). A higher plan includes the tables of the lower ones |
| Pointer only, at every plan | PVP2011-57100 tables; ASCE 7-22; AISC 360 and ACI tables; NEMA SM-23. The connector returns the table, row key, column and edition and no value; you read the value from your own copy |

Which plan covers which table is the site's tiering today and can change, and a table's source can
move between served and pointer-only (the four API tables currently serve values at Ultimate and can
return to pointer-only); each result states the tier it needed and whether it is a
value or a pointer. The docs page above has the current list of every dataset.

### What a result looks like

Every answer from `lookup_value` is one envelope: the value and its unit, the column, a citation
(standard, edition, table, row, column and any table notes), whether the value was served or is a
pointer, the tier required, the dataset id and version with a hash of the rows used, the tabulated
entries it interpolated between when it did, a one-line summary and where to verify it. A pointer
returns the same fields with the value empty. An illustrative call:

```
lookup_value  dataset_id: b313-allowable-stresses-2024  key: { spec: A106, grade: B, T: 650 }  column: S
```

Values arrive cited and are still yours to verify against your own copy before anything is issued.
The edition in the citation is the edition that was read, so check it against your project's
edition basis. The other tools are `find_dataset`, `describe_dataset` and `list_keys` for finding a
dataset and the key fields that identify one row, and `verify_connector` for a self-check.

### Sign-in

Open tools need no account. A table your plan covers needs you signed in to a paid pipingtoolset.com
account. Sign-in goes through pipingtoolset.com, handled by your host, and requires you to confirm
that your assistant account is set not to train on your conversations. A signed-out request for a
paid table starts the host's sign-in; a signed-in request your plan does not cover returns one line
naming the plan it needs and the [pricing page](https://pipingtoolset.com/pricing/).

### Add the connector

Installing the plugin already declares the server in Claude Code and Cowork. Codex and the ChatGPT
desktop app do not get a declaration from the plugin, so use these lines there, or to add it by hand
anywhere, or without the plugin.

- **claude.ai custom connector.** Settings › Connectors › Add custom connector. Name it
  `PipingToolset Data`, enter the URL `https://pipingtoolset.com/mcp`, and if asked how to register
  a client choose **Register automatically**. Press **Sign in** when a lookup needs your plan; open
  tools work before you sign in.
- **Claude Code.**

  ```
  claude mcp add --transport http pipingtoolset-data https://pipingtoolset.com/mcp
  ```

  Run `/mcp` to see the server and sign in when a lookup needs your plan.
- **ChatGPT.** Turn on developer mode in the connector settings, create a connector with the MCP
  server URL `https://pipingtoolset.com/mcp` and OAuth authentication, and sign in through
  pipingtoolset.com when asked.
- **Codex.** Installing the plugin adds no server and asks for no sign-in. Codex takes a streamable
  HTTP server by URL:

  ```
  codex mcp add pipingtoolset-data --url https://pipingtoolset.com/mcp
  codex mcp login pipingtoolset-data
  ```

  or in `~/.codex/config.toml`:

  ```
  [mcp_servers.pipingtoolset-data]
  url = "https://pipingtoolset.com/mcp"
  ```

To turn it off, disconnect or disable `pipingtoolset-data` in the host's connector or MCP settings.
The skills then ask you to read each table value from your own copy, exactly as before.

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

Expected, with the connector off or no paid plan signed in: no number. It names B31.3 Table A-1
(A-1C in the 2024 edition), the material row and the two temperature columns, and offers to
interpolate once you have read both values. With the [connector](#engineering-data-connector)
enabled and a plan that covers the table, the assistant may instead read the value from the
connector and show it with its citation; check it against your own copy.

More prompts, with pass criteria, are in [`tests/e2e/PROMPTS.md`](tests/e2e/PROMPTS.md).

## Project basis record

Since 0.8.0 the seven skills share one record of the project facts, so you state them once. It is a
JSON file, schema `pipingtoolset.project-basis/1`, passed to any script as `--project-basis
project-basis.json` or as a top-level `project_basis` object in the job file. It holds project data
and pointers only. S, E, W, Y, ratings, allowables and gasket factors never go in it; they stay
`code_values` entries with their citations.

| Key | What it carries |
|---|---|
| `project` | name, number, line, revision, calcBy, date |
| `code` | standard (B31.3, B31.1, B31.9, B31.12 or another), edition, route (for example Normal fluid service, Chapter IX) |
| `service` | fluid category (Normal, Category D, Category M, High Pressure), fluid, corroded, cyclic |
| `states` | one entry per condition: key, name, role (operating, design, upset, steamout, hydrotest ...), T_F, P_psig, cycles, CAESAR II slot (T1, P1, D1); plus `installation_T_F` |
| `units` | system (USC or SI) and any unit that differs from the system default |
| `load_case_ids` | software (CAESAR II or AutoPIPE), version, the case ids for SUS, OPE, EXP, OCC, HYD, HGR |
| `equipment_axes` | global vertical (Y or Z), pipe axis, nozzle axis map |
| `materials`, `owner_practice`, `citations` | material id, spec, grade, form and use; owner documents with their items; citation pointers |
| `assumptions` | each item with status ASSUMED or confirmed, a note and an owner |

Every key but `schema` is optional; an unknown key exits 2. The full schema and each skill's fill
map are in `references/project-basis.md` inside every skill (one canonical copy, pinned by a test).

**Hand-off.** The first skill run in a session (usually `load-case-builder`, whose basis interview
collects most of it) writes the agreed record to `project-basis.json` in your working folder. Each
later skill runs with `--project-basis project-basis.json` and asks only for its own inputs.

1. An input the job file leaves out is filled from the record where the skill has a slot (for
   example the design state's pressure for `pressure-design` and `bolted-flange`, the vertical axis
   for `pipe-support` and `iso-to-pcf`, the design temperature for `nozzle-load`).
2. An input given in both places that differs stops the run, exit 2, `project_basis.<path>
   conflicts with input <name>`. The record never overrides what you typed, and no field is
   relabelled.
3. The result gains `project_basis_applied` (`fields_used` with filled, agreed or noted, the
   ASSUMED items verbatim, and `conflicts`), and section 1 of every calc sheet renders the record
   with every ASSUMED item at the top.
4. When a fact changes, edit the record and rerun the skills whose `fields_used` name it.

`tests/test_project_basis_handoff.py` runs all seven scripts on one record and checks that each
result equals the run with the same values typed in.

**Result status.** Every result carries `result_status` and `checks[]` beside the existing pass,
fail or na `status`, and every calc sheet has a `Result status: <word> - <why>` line under its
title.

| Word | Meaning |
|---|---|
| calculated | every input confirmed, no gate tripped, no reconstructed factor |
| screening | a screening method by definition (flange pressure-equivalent screen, PVP2011 derived set, span screen, flexibility exemption) or a reconstructed factor in the chain |
| manual check required | a validity gate tripped, or a code-required item the script cannot evaluate for these inputs |
| pointer only | a required value was given only as a pointer; that check did not run |
| not checked | a check the module does not perform, listed from the skill's known limits; it never sets the result word |

The result word is the worst of the checks the module performs, in the order manual check
required, pointer only, screening, calculated; `not checked` rows are listed and never set it, so a
clean run reads `calculated` and the line names what was not performed. Every ASSUMED input (in the
record or the skill's own list) gives one `ASSUMED inputs` check graded manual check required. No
skill prints PASS, OK, ISSUE or DELIVERABLE while the word is manual check required or pointer only,
or screening with an unresolved reconstructed factor; the status word is printed instead.

## What the skills will not do

They never reproduce tabulated ASME, API or PIP values from memory or from a file in the plugin: a value
comes from your own copy of the standard or, if you enable the optional connector, from a cited lookup.
`pipe-support` is the disclosed exception for AISC 360-22, the AISC Shapes Database, and the ASCE 7-22
and ACI 318-19 factors (see its `references/code-basis.md`).
They do not replace a flexibility analysis in CAESAR II or AutoPIPE; `stress-screening` is a hand
check of what the program applied. Results are engineering aids. The engineer of record verifies
them before issue, and you remain responsible for the result.

## Development

Tests use the Python standard library only:

```
python -m unittest discover -s tests -v
```

`tests/golden/` locks the load-case generator's output and the PCF builder's output (`demo-line.pcf`,
CRLF, kept byte-exact by `.gitattributes`) for the worked examples. A change to case order,
combination strings or QC text must be a deliberate golden update, reviewed by the engineer of record.
`tools/sync_fixtures.py --check` confirms the vendored calc-core fixture snapshot is current.
`tools/sync_shared_blocks.py --check` confirms that the shared `project_basis` and `result_status`
code blocks, `references/project-basis.md` and `scripts/examples/project-basis.example.json` in
every skill are byte copies of `tools/shared/` (run it without `--check` to rewrite them).
`python tools/package_plugin.py --check` builds `piping-toolset.plugin` (Cowork and Agent Plugins
hosts), `piping-toolset.zip` (the same bytes, for the OpenAI plugin portal) and
`piping-toolset-skills.zip` (skills-only upload) for a release, and checks that every image the
manifests reference and the connector declaration (`.mcp.json`) travel inside the first two archives
and stay out of the skills-only one, and that no Agent Plugins connector file has come back.
`tests/test_manifests.py` keeps the Claude and Agent Plugins manifests in step and holds the OpenAI
listing block to the portal's limits (30-character display name and subtitle, 4000-character
description, square icons of at least 48 px).
`tests/test_connector_manifest.py` pins the connector declaration (one server, one https URL, no
headers, nothing stored for sign-in), the packaging facts above, the rule that no skill script imports a
network module, and the wording rules for the listing copy. CI also runs
the agentskills.io reference validator, `skills-ref validate`, on each skill folder; locally:

```
python -m pip install skills-ref==0.1.1
python -m skills_ref.cli validate plugins/piping-toolset/skills/pressure-design
```

See [`ROADMAP.md`](ROADMAP.md) for the plan and [`CHANGELOG.md`](CHANGELOG.md) for releases.
A release labelled **UNCONSERVATIVE-FIX** corrects a result that could have been less conservative
than the code requires; update when you see one.

## Licence

Copyright © 2026 Flexible Piping Solutions LLC. Licensed under the
[Apache License, Version 2.0](LICENSE). "Piping Toolset" is a name of Flexible Piping Solutions LLC;
see [NOTICE](NOTICE). Claude is a product of Anthropic, PBC; ChatGPT and Codex are products of
OpenAI. This plugin is not affiliated with or endorsed by either.
