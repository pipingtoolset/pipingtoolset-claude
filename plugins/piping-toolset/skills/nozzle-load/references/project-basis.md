# Project basis record and result status

One record, schema `pipingtoolset.project-basis/1`, carries the project facts every PipingToolset skill needs, so the user states them once. It holds project data and pointers only: no code-table value is ever stored in it (S, E, W, Y, ratings, allowables and gasket factors stay in `code_values`, cited).

## How a skill receives it

- As a top-level `project_basis` object in the script's JSON input, or as a file: `--project-basis project-basis.json`.
- Both present with different content: exit 2, `project_basis conflicts with --project-basis file`.
- Every key is optional except `schema`. An unknown key, a bad enum word or a wrong type: exit 2 with the path, e.g. `project_basis.states[0].role: 'normal' is not one of operating, design, ...`.

## Schema

| Key | Shape |
|---|---|
| `schema` | `"pipingtoolset.project-basis/1"` (required) |
| `project` | `name`, `number`, `line`, `revision`, `calcBy`, `date` (strings) |
| `code` | `standard` (B31.3, B31.1, B31.9, B31.12 or another string), `edition` (string year), `route` (e.g. "Normal fluid service", "Chapter IX") |
| `service` | `fluid_category` (Normal, Category D, Category M, High Pressure), `fluid`, `corroded` (true/false), `cyclic` (true/false) |
| `owner_practice` | list of `{document (required), edition, items[]}`; an item is a string or `{name, value, unit, note}` |
| `materials` | list of `{id, spec, grade, form, use, notes}`; form: seamless, welded, ERW, EFW, SAW, forged, cast, plate, bar, other; use: pipe, fitting, flange, bolt, gasket, vessel, nozzle, support, other |
| `states` | list of `{key (required, unique), name, role, T_F, P_psig, cycles, slot {T, P, D}}`; role: operating, design, upset, startup, shutdown, steamout, installed, hydrotest, pneumatic, other; slot words are T1, P1, D1 style |
| `installation_T_F` | number |
| `units` | `system` (USC or SI), `force`, `moment`, `length`, `temperature`, `pressure`, `stress`; a unit left out takes the system default (USC: lbf, ft-lbf, in, F, psig, psi; SI: N, N-m, mm, C, kPa, MPa) |
| `load_case_ids` | `software` (CAESAR II or AutoPIPE), `version`, `cases {SUS, OPE, EXP, OCC, HYD, HGR}`, each an id or a list of ids |
| `equipment_axes` | `global_vertical` (Y or Z), `pipe_axis` (X, Y or Z), `nozzle_axis_map {Fx, Fy, Fz, Mx, My, Mz}` (signed global axis such as +Y or -Z), `notes` |
| `citations` | list of `{ref, standard, edition, table, row, column, note}` |
| `assumptions` | list of `{item (required), status (ASSUMED or confirmed), note, owner}`; a missing status counts as ASSUMED |

A complete example ships as `scripts/examples/project-basis.example.json`.

## Fill-or-conflict

The rule mirrors `code_values`:

1. A script input that is absent (or null) in the main input is filled from the record where the skill has a slot (table below).
2. An input present in both that agrees is kept; one that differs stops the run: exit 2, `project_basis.<path> conflicts with input <name>`. The record never overrides what the user typed.
3. The result gains `project_basis_applied`: `{schema, fields_used: [{input, basis, action}], assumptions: [ASSUMED items verbatim], conflicts: []}`; action is filled (the record's value entered a script input, including items added to an existing list such as `assumed`), agreed or noted (read for the sheet only).
4. Calc-sheet section 1 (Basis) renders from the record and lists every ASSUMED item at the top.

Interview rule: when a record exists (written by an earlier skill in the session, or a file the user names) reuse it, ask only for what is missing, and never relabel a field.

## Per-skill fill map

| Skill | Takes from the record |
|---|---|
| load-case-builder | `code`, `edition` from code; `thermal_states` from states (key, name, role, cycles, slot T/P/D); `primary_state` from the first operating state, else the first declared state; software hint from load_case_ids.software; owner friction practice as a note; assumptions into the ASSUMED block |
| pressure-design | code.standard must match the module family (b313 or b311) else conflict; `edition` from code.edition; P and T from the design state (else the first state); material citation text, and `W_basis` seamless from materials[use=pipe] when its form is seamless and W_basis is absent; units must be USC (SI exits 2) |
| stress-screening | `basis` resolution from code and edition; states for fatigue cycles and installation temperature; owner practice notes |
| pipe-support | units (USC gives lb-ft); `vertical_axis` from equipment_axes.global_vertical; `pipe_axis`; project, calcBy, date from project; design.material Fy and Fu from materials[use=support] only when given; loads.map from load_case_ids.cases; assumed from assumptions |
| iso-to-pcf | `axes` from global_vertical (Y gives Y-up, Z gives Z-up); units check (MM only); assumed from assumptions; pipeline and project names |
| nozzle-load | `units` from units.system; `designTempF` from the design state; equipment axes map carried to the sheet; ownerFactor basis from owner_practice |
| bolted-flange | route (VIII-2 4.16 or the retired Appendix 2) from code; P and T from the design state; moment unit from units.moment; owner acceptance from owner_practice |

## Hand-off between skills

1. The first skill run in a session writes the agreed record to `project-basis.json` in the user's working folder (validated by the script on its first use).
2. Every later skill runs with `--project-basis project-basis.json` and adds only its own inputs.
3. When the user changes a fact, edit the record, not one skill's input, and rerun the skills that used it (`fields_used` names them).

## Result status words

Every result envelope carries `result_status` and `checks: [{name, result_status, status, note}]`; `status` stays pass, fail or na as before. The envelope word is the most severe word among the checks the module performs: `not checked` rows never set it, and it reads `not checked` only when every row is (or there are none). A clean run of a module that performs its checks therefore reads `calculated`, with its `not checked` limits still listed in `checks` and summarised after the word.

| Word | Meaning |
|---|---|
| calculated | every input confirmed (user or connector, cited), no gate tripped, no reconstructed factor |
| screening | a screening method by definition (flange equivalent-pressure screen, PVP2011 derived set, support-span screen, flexibility exemption) or a reconstructed factor in the chain, marked `unresolved_factor` |
| manual check required | a validity gate tripped, or a code-required item the script cannot evaluate for these inputs |
| pointer only | a required value was supplied only as a pointer; that check does not run and the sheet row says so |
| not checked | a check the module does not perform (from the skill's Known limits); listed, never the envelope word unless it is the only word |

Severity, worst first: manual check required, pointer only, screening, not checked, calculated.

ASSUMED inputs (all seven skills): every ASSUMED item, whether from `project_basis.assumptions` (status ASSUMED or missing), the skill's own `assumed` list or a generator default, goes into one check row named `ASSUMED inputs`, graded manual check required, with the note `confirm before issue: <item>; <item>`. The envelope follows it, so an unconfirmed input always holds the banner. pipe-support grades preset-derived anchor and concrete values the same way in one `preset inputs` row.

Banner rule (all seven skills): no PASS, OK, ISSUE or DELIVERABLE wording while the envelope word is manual check required or pointer only, or screening with an unresolved reconstructed factor; the banner shows the status word instead. The rule governs verdict and RESULT banners only; a QC finding prefix such as load-case-builder's `OK:` is a check result and keeps its word. Each calc sheet carries one line under its title: `Result status: <word> - <why>` (ASCII hyphen with a space each side; `render_status_line` writes it).
