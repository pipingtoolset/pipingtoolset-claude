# Changelog

All notable changes to the `piping-toolset` plugin are recorded here. Dates are UTC.

Labels: **UNCONSERVATIVE-FIX** marks a correction where a previous release could
have produced a result less conservative than the code requires. Installed copies
keep a defect until the plugin is updated, so each such entry names the skill, the
affected inputs and the release that fixed it. GitHub Releases carry the same
label and are the recall channel.

## [0.5.0] — 2026-10-27

Two new skills, and distribution to assistants other than Claude. No change to any existing
skill's calculations, scripts, fixtures or golden files; every number the five earlier skills
produce is identical to 0.4.0.

- **New `nozzle-load`**: piping forces and moments on equipment nozzles against the allowables
  for that equipment type. Ported from the pipingtoolset.com calculation engine, fixture-locked
  (`tests/fixtures/calc-core`): `connections.nozzle-load-check` (six-component ratios, resultants,
  governing component), `connections.nema-sm23` (the 3F + M ≤ coefficient · De combined form used
  by API 617 Annex E, API 611 Annex I, API 612 Annex D and NEMA SM-23; the coefficient is a
  required input), `connections.api610-annexf` (API 610 Annex F, horizontal F.1 to F.5 and
  vertical in-line F.6 to F.11). New, hand-checked: `equipment.pvp2011-allowables` (the method of
  ASME PVP2011-57100 "Establishing Allowable Nozzle Loads" as the default for pressure vessels
  with no API or vendor allowable: thickness square-law extrapolation, the 18,800 / 17,100 psi
  material ratio capped at 1.0, force-with-d and moment-with-d² interpolation, owner factor; the
  user reads the Table 1A / 1B / 2 row), `equipment.nozzle-load-sum` (API 661 7.1.10.2 header
  sum and the 7.1.10.3 bay multiple), `equipment.api650-annexp-ordinates` (API 650 Annex P.2.7
  nomogram ordinates; the user reads the boundary). PIP RECE002 design-stage margins and
  resolution points are an optional owner-practice basis item. No API, NEMA or paper table value
  is embedded.
- **New `bolted-flange`**: piping loads on bolted flanged joints. The pressure-equivalent screen
  (`connections.flange-equivalent-pressure`, ported, fixture-locked) runs first and is always
  reported; the BPVC Section VIII Division 2 Part 4.16 analysis (`aux.app2-flange-integral`,
  ported, fixture-locked, integral and loose, hub and shape factors, bolt loads, SH / SR / ST,
  2-8(a) cap, bolt-spacing correction, rigidity J) follows. The closed-form hub factors F, V, f
  are a reconstruction that matches AutoPIPE to four digits, stated as such in the script and the
  references, and may be overridden with values read from the Code figures. New:
  `connections.flange-derive` (N, b₀, b, G, bolt root area, g₀ / g₁ / h from user-read raw values).
  UG-44(b) / 4.16.12, ASME III NC-3658.3 and EN 1591-1 are named as the next rungs, not computed.
  B16.5 dimensions and ratings, B16.20 gasket dimensions, Table 4.16.1 gasket factors and every
  allowable stress are user-supplied.
- Pack: `tools/sync_fixtures.py` vendors five more engine modules (22 modules, 74 cases). The
  engine's two Table 4.16.5 curve-fit cases are excluded by rule, with the reason in `MANIFEST.json`,
  and a fixture whose name is a Windows device name (`aux.*`) is vendored with a leading underscore;
  `tests/test_skill_references.py` asserts seven skills; README, ROADMAP and the prompt set
  (`tests/e2e/PROMPTS.md`) cover the new skills; plugin and marketplace manifests at 0.5.0.
- `plugins/piping-toolset/plugin.json`: an Agent Plugins 1.0 manifest (agent-plugins.org) next
  to the unchanged `.claude-plugin/plugin.json`, so the same folder installs in OpenAI Codex and
  any other Agent Plugins host. `tests/test_manifests.py` fails if the two manifests disagree on
  name, version or description, or if either marketplace drifts from them.
- `.agents/plugins/marketplace.json`: the Codex marketplace file for
  `codex plugin marketplace add pipingtoolset/pipingtoolset-claude`.
- **All seven skills**: frontmatter gains the Agent Skills `compatibility` field,
  `Requires Python 3.9+ (standard library only)`. Nothing else in the skills changed.
- Packaging: `tools/package_plugin.py` also builds `piping-toolset-skills.zip` (only `skills/`,
  for ChatGPT, Manus and Perplexity uploads), reproducibly; CI uploads it and attaches it to the
  GitHub Release beside the `.plugin`. The `.plugin` now carries the root `plugin.json` too.
- README: "Other assistants" section with the Codex, `npx skills` and `gh skill` install commands,
  where the skills land, and the note that those commands need the repository to be public.

## [0.4.0] — 2026-10-26

Cowork support. No calculation, script-engine, fixture or golden change; every number the
skills produce is identical to 0.3.2. The invocation surface changes for every user, hence the
minor bump.

- **All five skills**: run instructions no longer say "run from this skill's directory".
  Scripts are called by full path from the session's working directory and every input and
  output file (`job.json`, `spec.json`, calc reports, result JSON, PCF files) is written to the
  working directory. In Cowork the plugin folder is a read-only mount and the working directory
  is the outputs folder, so the deliverables surface as downloadable files.
- **All five skills**: descriptions rewritten third person with the phrases engineers type, so
  the skills trigger from plain language in Cowork, which has no `/piping-toolset:` prefix.
  Skill names are unchanged.
- `stress-screening`, `load-case-builder`, `pressure-design`: SKILL.md bodies trimmed under
  3,000 words; the detail moved verbatim into each skill's `references/` folder and is linked
  from the body. Nothing was removed from the pack.
- `iso-to-pcf`: the PDF-reading reference leads with the tools expected in the Cowork
  sandbox (pdfplumber, pypdf, poppler) and keeps PyMuPDF as the optional faster route.
- `pressure-design`: the PowerShell here-string example replaced by shell-neutral wording.
- Packaging: `tools/package_plugin.py` builds `piping-toolset.plugin` (the Cowork install
  file) reproducibly; CI uploads it on every run and attaches it to the GitHub Release on a
  `v*` tag. README gains a Cowork install path, a requirements line and plain-language usage.
- `tests/e2e/PROMPTS.md` gains a Cowork form of every prompt; `tests/e2e/COWORK-CHECKLIST.md`
  is the manual acceptance script for a Cowork session.
- `docs/cowork-readiness-audit-2026-10-26.md` records the audit behind this release.

## [0.3.2] — 2026-10-26

- **UNCONSERVATIVE-FIX** `pipe-support`: WT (tee) arm flexure was always evaluated on
  the AISC 360-22 F9 **stem-in-tension** branch (Mp = min(Fy·Zx, 1.6·My), B > 0 in
  F9-5, flange local buckling).
  - **Affected:** every assembly with a WT arm. A flange-up tee (pipes resting on the
    flange, stem down — the usual detail) hogs at the column face with its stem in
    compression, where F9 gives Mp = My, B < 0 and the F9.4 stem local-buckling limit.
    On a WT5X11 at Lb = 24 in the arm's φMn is 55.73 kip-in, not the 89.16 reported by
    0.3.0 / 0.3.1 — a 37 % overstatement. Other arm shapes are not affected.
  - **Fix:** follows the pipingtoolset.com engine fix (2026-10-26). New per-arm input
    `stemOrientation` ("down" = flange up, the default; "up" = inverted). The cascade
    maps it per member: cantilever arm → stem down is compression; goalpost / trapeze
    header (sagging) → stem down is tension. A WT arm with no orientation given is
    analysed stem down and warned.
  - **Affected inputs:** any `pipe-support` run whose `design.arms[].shape` is a WT.
    Upgrade and re-run; if the tee is inverted, set `stemOrientation: "up"`.
- `pipe-support`: ACI 318-19 **17.6.2.6 splitting factor ψcp,N** is now evaluated for
  post-installed anchors in **uncracked** concrete (it was pinned at 1.0): 1.0 when
  ca,min ≥ cac, else max(ca,min / cac, 1.5·hef / cac). New base-plate input `cac` from the
  anchor's ESR; omitted, the Table 17.9.5 default (adhesive 2·hef, mechanical 4·hef) is
  used with a warning. Cracked concrete (the default) and cast-in anchors are unchanged,
  so no earlier result moves unless `cracked: false` was set.
- `pipe-support`: **goalpost / trapeze headers are checked.** With `columnSpacing` given,
  each arm is also analysed as a header — a simple span between the column centrelines
  with the pipes as point loads at their offsets (reactions, Mmax, shear, deflection by
  superposition), through the AISC D–H check with Lb = span and K = 1 — as a new `header`
  stage. The header statics are reported and a warning names the heavier column when the
  reactions split worse than 55/45.
- `pipe-support` reviewer, two new findings (P.E. rulings 2026-10-26): the J10.1
  column-flange check assumes web-only fillets — if the arm flanges are also welded the
  loaded width is bf and the check must be re-run; and when an **ASD** anchorage stage is
  governed by a wind combination, re-run the anchorage in LRFD (the engine's fixed 1/1.5
  conversion is about 10 % unconservative against 0.6W — kept as documented behaviour).
- `pipe-support`: the "Base metal governs over the weld metal (AISC J4)" warning now fires
  only when the base-metal ratio is ≥ 0.5; the J4 rows stay in every weld-stage table.
  The J10.1 clause states its loaded width (tw + 2w, web fillets only).
- Parity goldens regenerated from the fixed engine (new WT, header and ψcp,N cases);
  calc-core fixtures re-vendored (one WT5X11 member case, two ψcp,N base-plate cases,
  each hand-checked in the engine repo). The PS-101 verification is unchanged: it has no
  WT, header or uncracked concrete.

## [0.3.1] — 2026-10-23

- **UNCONSERVATIVE-FIX** `pipe-support`: in 0.3.0 the column-to-base-plate fillet
  weld's base metal was checked on the base plate, which is the thicker part.
  - **Affected:** every assembly with a base plate. The weld stage could report a
    ratio lower than the J4 limit on the column element allows. For example, PS-101
    published 0.200 where the true value is higher.
  - **0.3.0 mitigation:** it carried a `[cross-check]` row that recomputed J4-4 on the
    column side. Supports reported by 0.3.0 with that row are not affected; the row
    showed the governing value.
  - **Fix:** follows the pipingtoolset.com engine fix (2026-10-23):
    - the base part is the thinner element;
    - J4 is split by direction (J4-1 / J4-2 on the normal component, J4-4 on the
      direct shear);
    - each line gets t/2 where both faces of one web or leg are welded;
    - J10.1 column-flange local bending is checked at the arm-to-column joint;
    - the J2.2b along-edge maximum is no longer applied to T-joint fillets.
  - **Cleanup:** the plugin's `[cross-check]` row is retired.
  - **Affected inputs:** any `pipe-support` run with a base plate, and any arm-to-column
    weld. Upgrade and re-run.
- Parity goldens regenerated from the fixed engine. The PS-101 verification is
  re-baselined to the corrected engine.

## [0.3.0] — unreleased

- New skill `pipe-support`: structural check of a pipe support assembly at one
  restraint, from CAESAR II restraint loads.
  - **Engine:** the pipingtoolset.com PiperSTR engine (AISC 360-22 members, J2 fillet
    welds, Design Guide 1 base plate, ACI 318-19 Chapter 17 anchorage, pier/soil, the
    t-post / multi-tier / cantilever / goalpost / trapeze cascade) ported to standard-library
    Python.
  - **Parity:** locked to the web engine by its fixtures and by several hundred goldens
    generated by running the web engine itself.
  - **Verification:** a published PiperSTR Design Summary Report (PS-101) is reproduced
    value for value (148 values).
  - **New modules:**
    - ASCE 7-22 LRFD/ASD combinations from SUS / OPE / wind / seismic / hydrotest cases
      (T per 2.3.4 / 2.4.4; reversal; Ev = 0.2 SDS D);
    - AISC 360-22 J3/J4 bolted connections and no-prying end plates;
    - J2 / AWS D1.1 weld detailing and groove welds;
    - constructability rules;
    - an enumerating optimizer that ranks code-passing alternatives by steel weight,
      field work and stocked sizes;
    - an automated reviewer (severity-ranked findings, including a cross-check of the
      column-to-base-plate weld base metal);
    - a Markdown calc report with a compliance matrix, and a JSON API output.
  - **Shapes:** AISC Shapes Database v16 shapes vendored with attribution.

## [0.2.0] — unreleased

- New skill `iso-to-pcf`: PDF stress isometrics to a CAESAR II-ready PCF. Claude
  transcribes the drawing into a JSON walk spec; `build_pcf.py` builds it in exact
  fraction arithmetic with a single cursor (bend tangents from corners, tee and olet
  branches, elevation profiles for sloped runs, closure checks, BOM reconciliation)
  and writes only the CAESAR II safe record set by default; `validate_pcf.py` checks
  any PCF for floating or zero-length elements, off-line olets and supports, unsafe
  record types and bore changes. Synthetic worked example and golden output.
- `iso-to-pcf` output format corrected to match PCFs that import cleanly into
  CAESAR II (the first build's PCF failed to import): `UNITS-BORE MM` with bore
  = NPS x 25.4 (was `INCH` with raw NPS under mm coordinates); bare header (no
  free-text `ATTRIBUTE1`); elbows as `BEND` + `BEBW` + `ANGLE 9000` +
  `BEND-RADIUS`; `TEE` with `CENTRE-POINT`; supports as `CO-ORDS`/`SKEY`
  (`ANCH`/`SKID`/`GUID`/`SPRG`)/`SUPPORT-DIRECTION` on a node (pipe split at the
  support); no `ITEM-CODE`; branch legs written after the main run;
  `UNITS-WEIGHT LBS`.
  The validator now errors on bore/coordinate unit mismatch, inch bores under
  `UNITS-BORE MM`, `ELBOW` records and supports off a node. New
  `examples/minimal-proven.json`.
- `iso-to-pcf` live-import confirmed in CAESAR II (four-file ladder: proven
  records only; plus descriptions, weights and support names; plus gasket and
  olet; full sloped demo line). `GASKET` and `OLET` promoted to the proven set,
  and `ITEM-DESCRIPTION` / `WEIGHT` / support `NAME` are now written by default
  (`"annotate": false` for the bare form).
- Plugin display name is now **PipingToolset** (`displayName`); the id and the
  `/piping-toolset:<skill>` command prefix are unchanged.
- Plugin icon (`assets/icon.png`, gray line-art grid-elbow mark) for the plugin
  directory listing.
- Skill descriptions shortened to under 300 characters for a cleaner slash-command
  popup; tests cap them at 400.

## [0.1.0] — unreleased

First public release candidate.

- `load-case-builder`: B31.1/B31.3 static load case sets for CAESAR II and
  AutoPIPE, generated symbolically; QC gate; report extraction matrix.
- `pressure-design`: code-basis interview and B31.3/B31.1 pressure design —
  wall thickness, allowable pressure, branch reinforcement, bends, miters, leak
  test — with bundled scripts that reproduce the pipingtoolset.com calculation
  engine's locked test cases.
- `stress-screening`: sustained, occasional and expansion hand checks, f factor
  by edition, SIF-source resolution, formal-analysis exemption, support spans,
  spring variability.
- No code table values are embedded; every number a skill states comes from a
  script run on inputs the user supplied.
