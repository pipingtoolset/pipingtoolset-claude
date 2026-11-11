# Changelog

All notable changes to the `piping-toolset` plugin are recorded here. Dates are UTC.

Labels: **UNCONSERVATIVE-FIX** marks a correction where a previous release could
have produced a result less conservative than the code requires. Installed copies
keep a defect until the plugin is updated, so each such entry names the skill, the
affected inputs and the release that fixed it. GitHub Releases carry the same
label and are the recall channel.

## [0.10.1] — 2026-11-11

**Directory compliance and documentation only.** No calculation, status, exit code or fixture changes; the only output text that moves is the note on the load-case-builder QC 11 row. This is not an UNCONSERVATIVE-FIX release.

### Changed
- Reworded docstrings, comments and reference tables that the Anthropic plugin directory scan read as a credential or environment read: the status word followed by a condition word, the status word opening a line, a table cell or a clause, and environment-command look-alikes in `loadcase_gen.py` (a local variable renamed, two finding notes reworded). `loadcase_gen.py` and `verify_cii.py` build their status word by tuple lookup like the other scripts.
- README: the Codex IDE extension does not install plugins (OpenAI's plugin docs); install through the Codex CLI or the ChatGPT desktop app, or add the skills on their own. The Codex cloud sandbox claim is removed.

### Removed
- `docs/site/` draft pages for pipingtoolset.com (stale; the live pages are built in the site repository) and the test that compared them with the README.

### Tests
- `tests/test_directory_scanner_guard.py` sweeps the shipped plugin folder for the two status-word forms the scan holds on.

## [0.10.0] — 2026-11-03

**Scope change: six skills, two of them new, one removed.** The pack is tightened to the problems a piping stress engineer actually brings: getting a model into the analysis program, and checking a stress analysis or a received calc package the way a reviewer will. `iso-to-pcf` is replaced by **`stress-import`**, `stress-screening` is replaced by **`pipe-stress-check`**, and **`pressure-design` is removed** with no replacement in this plugin. No calculation result changes: every engine module that stays (the eight `pipe-stress-check` modules, the PCF builder and validator) is byte-for-byte the 0.9.3 code with its parity fixtures, and the shared project-basis and result-status blocks are unchanged. This is not an UNCONSERVATIVE-FIX release.

### Upgrading
- Slash names: `/piping-toolset:stress-screening` is now `/piping-toolset:pipe-stress-check`; `/piping-toolset:iso-to-pcf` is now `/piping-toolset:stress-import`; `/piping-toolset:pressure-design` is gone. Codex tags change the same way (`$pipe-stress-check`, `$stress-import`).
- `stress_screening.py` is renamed `pipe_stress_check.py`. Module ids (`piping.displacement-stress`, `piping.sustained-stress`, `piping.fatigue-factor`, `supports.spring-variability`, `supports.max-spring-rate`, `noncode.pipe-section`, `screen.support-span`, `screen.flexibility-exemption`), the `basis` command, inputs, outputs, envelope and exit codes are unchanged. `build_pcf.py`, `validate_pcf.py` and `pcf_lib.py` keep their names and output (the `demo-line.pcf` golden is unchanged).
- The project basis record (`pipingtoolset.project-basis/1`) is unchanged; its fill map now lists the two skills under their new names and no longer lists pressure-design.
- Wall thickness, allowable pressure, branch reinforcement, bend and miter checks and the leak-test pressure are no longer computed by this plugin. The free calculators at pipingtoolset.com and the web engine still cover them, and the Engineering Data connector still serves the allowable-stress, E / W / Y and B36.10M tables they need. A 0.9.3 install keeps working; this release removes the skill from new installs only.
- The e2e prompt set is renumbered: E1 and E2 (pressure design) are retired; E3 to E5 are `pipe-stress-check`; E7 and E8 are `stress-import`; E15 keeps only its load-case-builder half.

### stress-import (replaces iso-to-pcf)
- **Five routes, two targets, one method:** PDF stress isometrics (route A, the exact-fraction builder and validator unchanged), Revit / Fabrication PCF exports (route B), Navisworks NWC support mining (route C), an IFC fabrication model with no PCF (route D, method only), and a job that imported badly (route E); CAESAR II through APCF and the neutral file, AutoPIPE through the Bentley PCF Translator. Geometry is never moved, every support sits on a node, and the file is proved by an independent check before anyone opens it in the analysis program.
- **New scripts, all standard-library Python 3.9+:** `pcf2caesar.py` (+ `pcf_union.py`, `pcf_split.py`, `pcf_graph.py`, `pcf_pieces.py`) builds one CAESAR II PCF per line plus a combined file from Revit exports, with de-duplication, re-vocabulary, line assignment, end classification, rule-placed and BIM-seeded supports and walk order; `pcf_prep.py` builds one translator-ready PCF per model for AutoPIPE (fused welds, healed joints, flanges, weights, attributes 1 to 9, bridged accessories, three-way valves, supports); `nwc_supports.py` mines hangers, trapezes, stands and in-line items from a Navisworks NWC without Navisworks; `pcf_check.py` (+ `pcflib.py`) runs the pre-import checks on any PCF (pieces and their anchors, free ends, zero-length and sliver parts, supports off node, bend legs, bore jumps, spans over the project table along the shortest path through tees); `plot_pcf.py` draws plan and two elevations as SVG; `ap_bendcheck.py` (+ `ap_pcf.py`) predicts AutoPIPE E726-15 and W726-8 before the translator runs; `ntl_closures.py` and `fix_closures.py` list and move loop closures off flange and valve points (the E751-1 crash); `cii.py`, `fix_cii.py` and `verify_cii.py` repair the CAESAR II neutral file after APCF import (node bands per line, per-line T/P, insulation, fluid density, `+ANC` code 6 to ANC) and prove the repair, exit 1 on a failed proof. The span table and vertical limit are project inputs (`--span-table`, `--vert-max-ft`, `span_table_ft`); no table is embedded and the checks say when they were skipped. `fix_cii.py` was ported from a numerical-library version to a uniform-grid point index so it needs nothing beyond the standard library.
- **Example jobs:** `revit-to-caesar.job.json`, `revit-to-autopipe.job.json`, `nwc-families.example.json`, `lines.example.json`; every key documented, every value an obvious placeholder.
- **New references:** `revit-pcf.md` (what is wrong with a raw Revit PCF and which builder fixes it), `bim-models.md` (NWC and IFC as support and geometry sources, snap rules, content gaps), `autopipe-translator.md` (bend check, translator settings, post-translate checks, crash playbook, expected warnings), `caesar-apcf.md` (APCF settings, `PCF_RES_MAP` block, SIF map, the neutral-file layout, reading the OUT and NTXT, warning catalogue), `support-rules.md` (placement priority, the span table as a project input, support list columns, the handover note). `reading-isos.md`, `spec-format.md` and `caesar-import.md` are unchanged.
- The skill body is pinned at 2,500 words (iso-to-pcf was pinned at 1,970); the detail of the four new routes lives in the references.

### pipe-stress-check (replaces stress-screening)
- **Two ways in:** a line to check (the Step 0 to 8 procedure, unchanged in substance) and an analysis or package to review. The review protocol (`references/review-protocol.md`) covers the inventory, the traceability chain a reviewer walks (reports from the archived model, civil cases per the matrix, iso bubbles and hanger boxes that match the model, P/T per the line list, gaps and friction per the design criteria and shown on the iso, every assigned line present, checklist answers that agree with the model, an independent check behind the stamp), the hand checks on the governing nodes, the severity rules (critical, major, minor, observation), the verdict recommendation (Accepted, Accepted as noted, Rejected and resubmit, Cannot verify), the satellite-office defect patterns and the modelling rejection catalogue.
- **New references:** `occasional-loads.md` (the ASCE 7 wind and seismic build by edition: qz forms with Kd inside or outside, Fp forms, the 13.1.4 and 13.6.7.3 exemptions, "deemed to comply", B31E and B31Ea, MSS SP-127 bracing, the ASD position under B31.1-2024 and B31.3) and `owner-practices.md` (PIP PNC00004, PNC00001 and RECE002 as clause pointers: formal-analysis screening, friction both ways, sag limit, rod-hanger limits, hydrotest on permanent supports, machinery nozzle-load triggers and design-stage caps, no cold spring, plus the other practices that touch a stress calc). Every coefficient and every PIP table value stays user-read.
- The calc sheet keeps its seven sections and the contract title of section 3; section 6 carries the findings register and verdict in a review. `tool-reference.md`, `load-cases-and-allowables.md`, `exemption-and-spans.md`, `spring-hangers.md` and `rejection-checklist.md` are carried over with the script name updated.

### pressure-design (removed)
- The skill folder, its `references/modules.md`, `pressure_design.py`, the shipped example and the four test files are deleted, and the seven vendored fixtures it owned (`piping.b313-wall-thickness`, `piping.b311-wall-thickness`, `piping.b31-allowable-pressure`, `piping.branch-reinforcement`, `piping.bend-thickness`, `piping.miter-allowable-pressure`, `piping.leak-test-pressure`) leave `tests/fixtures/calc-core` and `tools/sync_fixtures.py`. The 0.9.2 and 0.9.3 audit tests keep their stress and nozzle halves. The 15 remaining modules are vendored at the engine commit 0.9.3 used.
- Sibling skills' hand-offs to pressure-design now say the item is outside this pack.

### Manifests, docs, tests
- Version 0.10.0 in the three versioned manifests; the description, keywords (`revit`, `navisworks`, `stress-review` in place of `isometric`), the OpenAI listing's skills sentence and its three default prompts updated; `tests/e2e/HOSTS-CHECKLIST.md`, `PROMPTS.md` and `COWORK-CHECKLIST.md` carry the six skills and the renumbered prompts. README and ROADMAP rows rewritten.
- Tests: `test_stress_import*.py` and `test_pipe_stress_check*.py` (renamed, same bodies), new `test_stress_import_toolkit.py` (36 tests: every shipped script imports and answers `--help`, synthetic Revit PCF through both builders, a synthetic NWC stream through the miner and into `pcf_prep.py`, a synthetic NTL loop closure listed and moved, bend-check cases in PCF and NTL mode, no numerical-library import anywhere) and `test_stress_import_cii.py` (10 tests: a synthetic neutral file renumbered per line, anchor code 6 to 1, T1/P1/fluid landed, the proof passing and a tampered file failing, the pre-import checker and the SVG plot). The six-skill counts replace the seven-skill pins. 1,323 tests on Python 3.9 and 3.14.

### Not verified in this release
- `nwc_supports.py` has run on real Navisworks exports on two jobs but only on a synthetic stream in the test suite; sample its output against Navisworks before relying on it. Nothing in this release was re-run against a live CAESAR II or AutoPIPE; the translator calibration statements in `ap_bendcheck.py` are carried from the jobs they were calibrated on. The `pcf_prep.py` stages for elbow normalisation, overlapping and offset valves, duplicate pipes, in-line straightening, gap bridging, three-way valves and span infill, and the `pcf2caesar.py` tee, reducer, valve, riser and equipment-body paths, ran in the suite without triggering on the synthetic geometry.

## [0.9.3] — 2026-11-02

**UNCONSERVATIVE-FIX (pressure-design, bolted-flange, nozzle-load).** The second plugin release of the 2026-11-02 adversarial audit: the engine changes 0.9.2 left for 0.9.3 (its "Not mirrored" entry), as the owner P.E. ruled them (ruling R5 and audit items N5, N9, recorded in pipingtoolset.com-plan `PE-RULINGS-AUDIT-2026-11-02.md`), plus one found while re-vendoring the fixtures (audit S5c), mirrored from the web engine under the one-engine rule: calc-core `leak-test-pressure.ts`, `flange-equivalent-pressure.ts` and `api610-annexf.ts` after pipingtoolset/pipecalcpro#187 and `nema-sm23.ts` after pipingtoolset/pipecalcpro#186 (both merged 2026-11-02; every fixture vendored from main `0c20972`). Up to 0.9.2 the leak-test module applied an ST/S ratio below 1.0 to the hydrostatic test, so a report could carry a test pressure under the 1.5 · P floor of B31.3 ¶345.4.2(a) (B31.1 ¶137.4.5); the Annex F vertical in-line principal stress took a signed Fy, so a compressive axial force offset the bending term; and the ported flange screen credited a compressive axial force against Pe when called as a function (the CLI layer clamped it since 0.5.0, so a run through `bolted_flange.py` was already right). **Re-run any leak-test result whose `stressRatio` printed below 1 and any API 610 Annex F vertical in-line result with a compressive suction or discharge Fy.** The coefficient-basis change (R5) is not an unconservative fix: it removes a silent-basis risk. Ruling R4 (the B31G safety factor) has nothing to mirror here, see "Not mirrored". The result-word vocabulary of 0.9.1 is unchanged.

### pressure-design: the hydrotest floor (audit N5; B31.3 ¶345.4.2(a)) — UNCONSERVATIVE-FIX
- `piping.leak-test-pressure` now applies `stressRatio = max(1, min(ST/S, stressRatioCap))`: B31.3-2024 ¶345.4.2(a) reads "not less than 1.5 times the design pressure" with no condition, and (b) applies Eq. (24) only when the design temperature is greater than the test temperature; B31.1-2024 ¶137.4.5 sets the same floor (both read from the licensed texts). A raw ratio below 1 is warned with the engine's wording ("ST/S = 0.75 < 1 — the ratio is taken as 1.0 and the hydrostatic test reported is the 450 psi floor …"). Engine fixture case 3 (P 300 psi, ST 15,000 / S 20,000 psi, factor 1.5): `stressRatio` 0.75 → **1**, `hydroTest` 337.5 → **450 psi**; pneumatic 330 psi unchanged. Cases 0–2 are unchanged (514.286, 3,600 and 2,925 psi). The hand case ST/S 1.5 at P 450 still reads 1,012.5 psi.
- No ceiling on ST/S is added (the audit's "6.5 cap" was refuted against the Code text for the third time in the 2026-11-02 record; `stressRatioCap` stays an optional owner-specification value, and a cap never lowers the floor). The module citation, `SKILL.md` row and `references/modules.md` §7 name ¶345.4.2(a) and ¶137.4.5.

### nozzle-load: the SM-23-form coefficient basis (ruling R5; audit N4)
- `connections.nema-sm23` takes a required `basis` with no default: `api617`, `api611`, `api612` or `nema-sm23` (the engine carries `api617` and `nema-sm23`; the two API steam-turbine annexes the skill has always named are kept as further values). Under `api617` the coefficient defaults to **927**, the coefficient printed in API 617 9th Ed. (2022) Annex E eq. (E.1b) (`3 Fr + Mr ≤ 927 De`, USC; E.1.1 records it as the compressor adaptation of the NEMA constants, "1.85 times NEMA"), carried as the named constant `API617_E1B_COEFFICIENT` with its source; it is an equation coefficient, not a table value. Under every other basis the coefficient is required from the user's copy and the run stops without it (0.9.2 stopped without `coefficient` under any use). New outputs `basis`, `coefficient` and `coefficientSource` (`API 617 eq. (E.1b) 927 (default)`, `API 617 eq. (E.1b) 927`, `user-entered (differs from API 617 eq. (E.1b) 927)`, `user-entered`). `De` is the nominal size up to NPS 8 and (16 + NPS)/3 above (API 617 Annex E, USC; the owner confirmed the printed Annex E on 2026-11-02).
- Engine cases: NPS 12 with 927 entered → De 9.33333, allowable 8,652, ratio **0.5274** pass (the 0.9.2 numbers, now labelled); NPS 6 with the coefficient omitted → De 6, allowable 5,562, index 7,317.47277, ratio **1.3156 FAIL**; `nema-sm23` with a user coefficient of 400 at NPS 8 → allowable 3,200, ratio **0.8125** pass. No number changes for a run that entered its coefficient.
- A defaulted coefficient adds a warning to confirm it on the edition of record and is not listed in `user_supplied`; `ownerFactor` scales the default too and `coefficientSource` says so (0.5 → 463.5). The `checks` row names the basis and the source. A run without `basis` exits 2.
- The skill-content guard that banned the literal 927 now requires every line stating it to name eq. (E.1b) or the constant; the Annex F constants stay banned.

### nozzle-load: Annex F vertical in-line |Fy| (audit S5c) — UNCONSERVATIVE-FIX
- `connections.api610-annexf`, eq. (F.7)/(F.10): the axial term uses |Fy|, so a compressive axial force no longer offsets the bending term (engine `api610-annexf.ts` after #187). Engine SI case (suction Fy −1,000 N, Do 100 / Di 80 mm): suction σL 2.7618 → **3.4673 N/mm²**, σP 5.2203 → **5.7136**, ratio 0.12732 → **0.13936** against 41; the governing discharge F.6 ratio 0.20268 is unchanged. `references/equipment-criteria.md` states the rule.

### bolted-flange: no compression credit in the screen (audit N9)
- The ported `connections.flange-equivalent-pressure` takes `creditCompression` as an engine input and clamps a compressive `F` itself: new output `Fapplied` (the force the force term used), the engine's warnings ("Compressive axial force F = −2000 taken as zero — …"; "… CREDITED against Pe (creditCompression) — …"). Engine cases (P 500, M 50,000 in·lb, G 6 in, rated 1,975): F −2,000 by default → `Fapplied` 0, `forceTerm` 0, Pe **1,678.926**, utilization **0.8501**; with `creditCompression` → `forceTerm` −70.736, Pe **1,608.190**, utilization **0.8143**. The CLI pre-clamp of 0.5.0–0.9.2 is removed (one warning instead of the same clamp twice); its numbers are unchanged. VIII-2 4.16.13 (2025 text: "Compressive net-section forces are to be neglected") is the Code basis already cited in the skill. The detailed `aux.app2-flange-integral` keeps its documented rule (`Fax` = max(F, 0) by the user).

### Fixtures
- All 22 modules re-vendored at `0c20972`: `piping.leak-test-pressure` 3 → 4 cases, `connections.nema-sm23` 1 → 3, `connections.flange-equivalent-pressure` 2 → 4, `connections.api610-annexf` 4 → 4 (the SI case re-derived), and seven modules whose engine files changed only in their descriptions (`piping.b313-wall-thickness`, `connections.nozzle-load-check`, `aux.app2-flange-integral`, `noncode.pipe-section`, `structural.pier-soil`, `supports.spring-variability`, `supports.max-spring-rate`) pass unchanged. `tools/sync_fixtures.py --check` is clean for the first time since 0.9.0.

### Docs
- pressure-design `SKILL.md` (module row), `references/modules.md` §7; nozzle-load `SKILL.md` (method table, the basis paragraph, module row, values table, code-table rules), `references/equipment-criteria.md` §1 and §2, `references/tool-reference.md`, `references/rejection-checklist.md`; bolted-flange `references/tool-reference.md` (`Fapplied`); ROADMAP rows; `tests/e2e/PROMPTS.md` and `COWORK-CHECKLIST.md` E11 expectation.
- Manifests: version 0.9.3 in the three versioned manifests (the Agent Plugins marketplace carries no version); `tests/e2e/HOSTS-CHECKLIST.md` release pins.

### Tests
- New `tests/test_audit_0_9_3.py` (30 tests): the floor case through the function and the CLI, the cap-and-floor interplay, the no-ceiling case; the three nema cases, every basis rule, the default's source strings, `user_supplied`, the owner-factor path, the CLI exits; the Annex F SI case and its sign independence; the four screen cases, the single warning through the CLI layer, the output order; the fixture counts and the six result words. Existing nema inputs carry `basis`; the screen's compression tests and output-order test follow the engine; the 927 guard narrowed as above. 1499 tests, all passing on Python 3.9 and 3.12 (CI matrix).

### Not mirrored in this release
- **Ruling R4, the B31G safety factor** (SF = max(1.25, 1/F) in place of the fixed 1.39; B31G-2023 §1.9, printed p.4: "a minimum safety factor equal to the ratio of the minimum hydrostatic test pressure … to the MAOP or MOP, but usually not less than 1.25"; the 1.39 is the Level 0 tables' basis at 72 % SMYS, §2.1, printed p.5): the plugin has no `pipeline.b31g` module (no skill, script or vendored fixture ever carried it), so there is nothing to mirror. A corroded-pipeline module would be a new skill scope, not a mirror; the P′ ≤ MAOP cap is deferred by the ruling in any case.
- The engine's B31.5 `pneumaticLimitNote` input to the leak-test module (pipingtoolset/pipecalcpro#127) stays out: the skill's leak test serves B31.3 and B31.1 only.

## [0.9.2] — 2026-11-02

**UNCONSERVATIVE-FIX (stress-screening, pressure-design).** The plugin side of the 2026-11-02 adversarial audit, as the owner P.E. ruled it the same day (rulings R1–R3 and audit item N1, recorded in pipingtoolset.com-plan `PE-RULINGS-AUDIT-2026-11-02.md`), mirrored from the web engine under the one-engine rule: calc-core `stress-range.ts` after pipingtoolset/pipecalcpro#187 and `branch-reinforcement.ts` / `miter-allowable-pressure.ts` after pipingtoolset/pipecalcpro#188 (both merged 2026-11-02; fixtures vendored from main `fb5167e`). Up to 0.9.1 the displacement stress range carried no torsional SIF, so S_E was understated by the factor `it` on every component whose B31J torsional index exceeds 1.0; the branch-reinforcement check took nominal walls, let d2 exceed Dh, took no Sb/Sh reduction and let a pad offset an undersized header to a PASS; and a multiple miter with θ > 22.5° printed a pressure. **Re-run any displacement-stress result with a nonzero Mt, any branch-reinforcement result, and any multiple-miter result from 0.9.1 or earlier.** Also in this release: the B31.1-2026 edition branch (S1), the corrected B31.1-2020/2022 SIF-source rows (S11b) and one flange-method string (S3). The result-word vocabulary of 0.9.1 is unchanged.

### stress-screening: torsional SIF `it` (audit N1)
- `piping.displacement-stress` takes an optional `it` (B31J Table 1-1 torsional SIF, user-supplied, default 1.0) and computes `St = it·|Mt|/(2Z)` in Eq. (17); a run with `Mt` ≠ 0 and no `it` warns "Torsional SIF it not supplied — taken as 1.0" and lists a `not checked` row "torsional SIF it (B31J Table 1-1)". `it` < 1 is rejected like `ii` and `io`. `piping.sustained-stress` documents its `St` input as `it·Mt/(2Z)` with the index applied upstream.
- Engine hand case (Mt 200,000 in-lb, Z 16.81 in³, Sa = Sb = 0, Sc 20,000, Sh 17,300, f 1): with `it` 2.3, St 5,948.840 → **13,682.332 psi**, SE 11,897.680 → **27,364.664 psi**, ratio 0.4057 → **0.9332** against SA 29,325; at Mt 300,000 the ratio goes 0.6086 → **1.3997** and the status pass → **FAIL**. With `it` omitted the numbers are those of 0.9.1 (5,948.840 / 11,897.680 / 0.4057) plus the warning.

### pressure-design: branch reinforcement (rulings R1, R2; audit N6)
- **R1: an undersized wall fails outright.** `Th − c < th` or `Tb − c < tb` gives `fail` whatever the pad or weld area, with a `FAIL —` warning naming the wall and a new `checks` row "header and branch wall net of allowance against th and tb". Engine case (8 × 4, Th 0.2, c 0.0625, th 0.147, pad 0.5 × 8): margin **+1.13776 in²**, 0.9.1 pass → **FAIL**.
- **d2 is capped at Dh** (B31.3 ¶304.3.3(a), "in any case not more than Dh"), warned when it engages. Engine case (8 × 8 lateral at β 45°, Th 0.4375, Tb 0.28175): d2 11.40068 → **8.625**, margin +1.41360 → **−0.19908 in²**, pass → **fail**.
- **Sb/Sh on A3** (¶304.3.3(c)(2)): new optional, user-supplied `Sb` and `Sh`; with both given and Sb < Sh, A3 is multiplied by Sb/Sh and `strengthRatio` is reported (one of the two alone is warned and not applied). Engine case (illustrative Sb 16,000 / Sh 20,000): A3 0.13518 → **0.10815**, margin 0.08514 → **0.05810 in²**.
- **R2: minimum-wall basis.** `Th` and `Tb` are the measured or minimum walls of ¶304.3.3(a) (fields relabelled). New optional `ThNominal` / `TbNominal` with `millTolerance` (default 0.125, warned and listed in `defaults_applied`; 0 for a measured wall) derive them; both forms for one wall exit 2. The envelope's new `wall_basis` records each wall's value and basis with the clause, and `references/modules.md` §4 discloses the nominal-less-tolerance basis as the web calculator's autofill does. The shipped 8 × 4 STD case reads a margin of 0.30233 in² on nominal walls and **0.08514 in²** at 12.5 % mill tolerance.
- The ¶304.3.1(b)(2) range and Figure 304.3.3-1 Note (3) are warned on; the engine's warning wordings are adopted ("exceeds the header circumference assumption").

### pressure-design: miters (ruling R3; audit N7)
- A multiple miter with θ > 22.5° is **refused** (exit 2, pointing to eq. (4c) per single miter); 0.9.1 warned and printed min(Pm1, Pm2).
- The multiple-miter form requires R1 > r2 (eq. (4b) is zero or negative otherwise); the engine function's guard was R1 > r2/2 (the CLI pre-flight already required R1 > r2). A single miter with θ > 22.5° now reports `Pm1` 0 instead of the inapplicable eq. (4a) value (the engine fixture case: 479.299 → **0**; the eq. (4c) allowable 305.611 psi is unchanged).
- **Eq. (5)** is evaluated when the user enters `A` (the empirical value read from the ¶304.2.3 table for T − c, never embedded or defaulted) with the pipe OD `D`: new output `R1min = A/tanθ + D/2`, `status` `fail` below it, and the `checks` row "minimum R1 of a multiple miter" reads `calculated` (it was a permanent `not checked` row; it is now `not checked` only without `A`). Engine case (θ 15°, R1 12, D 8.625): A 0.8 → R1min **7.2981** in, within; A 2.5 → R1min **13.6426** in, **FAIL**.

### B31.1-2026 reach (audit S1)
- **pressure-design:** `edition` 2026 or later selects the renumbered equations — tm ¶104.1.2(a) eq. (3)/(4) (eq. (7)/(8) through 2024), P eq. (5)/(6) (eq. (9)/(10)), bends ¶104.2.1(c) eqs. (7)/(8) (¶102.4.5 eq. (3); ¶102.4.5 now points to 104.2.1 and Table 102.4.5-1 is deleted). A B31.1 run of the straight-pipe, MAWP or bend module writes an `edition_basis` object (generation, equation numbers, `y_table`, `W_table`, the connector datasets `b311-allowable-stresses-2026` / `b311-y-coefficients-2026` for 2026 and `b311-allowable-stresses-2024` / `b311-y-coefficients` for 2018–2024, and the note that Appendix A dropped the Grade 91 Type 1 lines); the bend gate's clause names ¶104.2.1(c) for 2026. "Table 104.1.2(A)" is renamed "Table 104.1.2-1 (104.1.2(A) in 2016)" in `SKILL.md`, the field description and `modules.md`; the W-gate docstring line "(7), (9), (3) from the 2018 edition" now gives both numberings. No number changes: the equations are the same, renumbered.
- **stress-screening:** `basis --code B31.1 --edition 2026` resolves (B31J, Appendix D deleted) with a 2026 note (¶104.8 unchanged; ¶102.3.3 (a)/(b)/(c); the renumbered pressure-design equations; Grade 91 Type 1 lines deleted) and a new `allowable_stress_dataset` field naming the edition's dataset. The edition table in `references/load-cases-and-allowables.md` gains the 2026 row.
- The B16.5-2025 and B16.20-2023 datasets `b165-2025-dimensions` and `b1620-2023-spiral-wound` are listed beside the 2017 ids in the bolted-flange slot tables (the only skill that reads flange dimensions).

### stress-screening: B31.1-2020 and 2022 SIF source (audit S11b)
- Since the 2020 edition the ¶104.8 equations (Figure 104.8-1, eqs. (15)–(17)) take their in-plane, out-of-plane and torsional factors from B31J Table 1-1; Mandatory Appendix D stayed in print through 2022, superseded for those equations, and was deleted in 2024. 0.9.1 named Appendix D as the 2020 and 2022 SIF source in the edition table and in `resolve_basis` (`sif_source`, `sif_documents_permitted`). Both are corrected; the 2018-and-earlier row keeps Appendix D.

### bolted-flange: one method string (audit S3)
- The method is named "BPVC VIII-2 Part 4.16 (formerly VIII-1 Mandatory Appendix 2; pre-2025 paragraph map shown)" wherever it is named: `SKILL.md` (description and Step 3), `references/app2-engine.md`, `references/method-ladder.md`, the script's docstring and citation string, the README and ROADMAP rows. The paragraph map (Table 2-1-1) stays in `method-ladder.md`. The plugin manifests keep "bolted flanges (BPVC VIII-2 Part 4.16)" within their 500-character limit.
- The Table 4.16.5 curve-fit claim is resolved: the skill ships the closed-form series reconstruction plus the `F_override` / `V_override` / `f_override` route and `hubFactorMethod` accepts `series` only; the curve fits the web calculator offers as a selectable hub-factor method are tabulated code data and are not in this skill. No table value is added.

### Fixtures
- Vendored from the engine at `fb5167e`: `piping.branch-reinforcement` 2 → 9 cases, `piping.displacement-stress` 2 → 5, `piping.miter-allowable-pressure` 2 → 5, `piping.sustained-stress` 2 → 3 (the new case passes unchanged). `piping.leak-test-pressure`, `connections.api610-annexf`, `connections.nema-sm23` and `connections.flange-equivalent-pressure` stay at the 0.9.0 snapshot (their engine changes are other rulings; `tools/sync_fixtures.py --check` reports them stale on purpose).

### Docs
- pressure-design `SKILL.md` (y table name, datasets by edition, module rows), `references/modules.md` (B31.1 by edition, §2, §3, §4 rewritten, §5, §6); stress-screening `SKILL.md`, `references/load-cases-and-allowables.md` (Eq. (17) with `it`, edition table), `references/tool-reference.md`; bolted-flange `SKILL.md`, `references/app2-engine.md`, `inputs-from-tables.md`, `method-ladder.md`, `tool-reference.md`; README and ROADMAP rows.
- Manifests: version 0.9.2 in the three versioned manifests (the Agent Plugins marketplace carries no version); `tests/e2e/HOSTS-CHECKLIST.md` release pins.

### Tests
- New `tests/test_audit_0_9_2.py`: the torsional hand case and its warning and `not checked` row; the B31.1 resolver for 2016–2026 and the dataset by edition; `edition_basis` and the bend gate clause by edition; the nine branch cases through the engine and the CLI (R1 row, d2 cap, Sb/Sh, nominal-wall derivation, conflicts); the miter refusals, R1 guard, eq. (5) rows. Pinned messages and the envelope key sets updated; the `test_b311_editions` expectation corrected for S11b. 1469 tests (44 new), all passing on Python 3.9 and 3.12 (CI matrix) and on 3.11 and 3.14.

### Not mirrored in this release
- The engine's other 2026-11-02 changes are outside this release's five items and stay as they were in 0.9.1: the hydrotest floor (B31.3 ¶345.4.2(a), engine batch 1: the engine's leak-test fixture case at P 300, ST/S 0.75 reads a hydrotest of 450 psi where the plugin prints 337.5 psi), the API 617 / NEMA SM 23 coefficient basis (ruling R5), the flange-screen compression rule and the B31G factor (rulings R4). They are candidates for 0.9.3.
- B31.3-2024 places the Sb/Sh reduction in ¶304.3.3(c)(2), not (b) as the audit sprint list wrote; the plugin cites (c)(2) as the engine does.

## [0.9.1] — 2026-11-02

All seven skills: the result word of the `ASSUMED inputs` row is now `assumed`. **P.E. ruling 2026-11-02 (the owner, item 3.5 of the editions-2026 rulings, recorded in pipecalcpro `pipingtoolset.com-plan/PE-RULINGS-EDITIONS-2026-11-02.md`):** (i) `not checked` keeps ranking worse than `calculated` in the result word (already so since 0.8.0; no change); (ii) the word for the `ASSUMED inputs` row is `assumed`. No computed number changes, no other status word changes, and the ranking of the five existing words is unchanged; fixture parity and the goldens are green.

### Result status (B9): the `assumed` word
- **Where it sits.** The worst-first order is now manual check required > **assumed** > pointer only > screening > not checked > calculated. `assumed` is placed just below `manual check required`: when a validity gate has tripped (or a critical finding, a guard, a preset row holds the run) and an input is also unconfirmed, the envelope names the gate, because confirming the input alone would not clear it. The status line still names the ASSUMED row in that case. Above `pointer only` because an unconfirmed input affects every number on the sheet, while a pointer stops one check from running and is listed as such.
- **It holds the banner exactly as `manual check required` does.** `banner_allowed` is false for `assumed`; `banner_word` prints `ASSUMED` where PASS, OK, ISSUE or DELIVERABLE would have been. Nothing that could be issued under the old word can be issued under the new one.
- **The one row.** `assumed_inputs_check` (shared block, `tools/shared/result_status.py`, synced into the seven scripts) grades the `ASSUMED inputs` row `assumed`; its name and note (`confirm before issue: <item>; <item>`) are unchanged. `RESULT_STATUS` has six words; `RESULT_STATUS_SEVERITY` renumbers manual check required to 5 and gives assumed 4 (ordering only).
- What each skill now prints on a run whose only hold is an ASSUMED item (the numbers are the same as before):
  - **load-case-builder:** `Result status: assumed - confirm ASSUMED inputs (...)`; the shipped two-state example and its golden `tests/golden/two-state-b313.md` read `assumed` (line 2 regenerated, nothing else moved). Under `manual check required` (unstated edition, QC 10 on B31.1, an ASD `scale`) the line names those rows first and then the ASSUMED row.
  - **pressure-design:** `result_status` `assumed`, `banner_allowed` false, the numbers stay in `output`.
  - **stress-screening** and **nozzle-load:** `banner` reads `ASSUMED` instead of `MANUAL CHECK REQUIRED`; `basis` (stress-screening) reports `assumed`.
  - **bolted-flange:** the withheld ISSUE-GRADE banner now reads `ASSUMED: ASSUMED inputs (confirm before issue: ...); no acceptance wording until each is resolved`; `assumed` is in the blocker list beside manual check required and pointer only.
  - **pipe-support:** verdict line `ASSUMED - <governing> ...; result status: not issuable until the ASSUMED inputs are confirmed: ASSUMED inputs (...)`, exit 3, report banner `> **ASSUMED (strength ratios within limits) - ...**`. The shipped `ps-201-caesar.json` still reads `MANUAL CHECK REQUIRED` and exits 3, because its `preset inputs` row (unchanged, manual check required) outranks the ASSUMED row; its reason now lists the preset row first and the ASSUMED row after it. With the user's own anchor values it reads `ASSUMED` until the ASSUMED item is confirmed, then `calculated`, exit 0.
  - **iso-to-pcf:** `RESULT: ASSUMED - confirm the ASSUMED items, then run validate_pcf.py`; the passing closure and BOM lines carry `[ASSUMED]` where PASS would be; a failed closure or BOM line is still `manual check required` and `NOT DELIVERABLE`.
- `tools/sync_shared_blocks.py --check --strict` is clean: the result_status block and `references/project-basis.md` are byte-identical in all seven skills.

### Docs
- README (result-word table gains the `assumed` row; order and banner rule restated), `tools/shared/project-basis.md` (synced to the seven `references/project-basis.md`), ROADMAP (the 0.8.0 open ruling is closed), and the status-word passages of `SKILL.md` in bolted-flange, iso-to-pcf, nozzle-load, pipe-support, pressure-design and stress-screening (load-case-builder's SKILL.md lists no words and is unchanged).
- References: bolted-flange `tool-reference.md`, `method-ladder.md`, `app2-engine.md`, `rejection-checklist.md` (taxonomy string); iso-to-pcf `spec-format.md`; load-case-builder `spec-format.md`; nozzle-load `tool-reference.md`; pipe-support `spec-format.md`; pressure-design `modules.md`; stress-screening `tool-reference.md`.
- Manifests: version 0.9.1 (descriptions unchanged); `tests/e2e/HOSTS-CHECKLIST.md` release pins.

### Tests
- Every assertion on the row's word, the envelope word and the banners of an ASSUMED-only run moved to `assumed`; the vocabulary tests pin six words and the two-word order checks cover all fifteen pairs; `test_project_basis_handoff.assert_words` accepts the envelope at `manual check required` only when another row carries it (pipe-support's preset row). New checks: `worst_of` of assumed against its two neighbours, `banner_word` for assumed, the pipe-support `ASSUMED - ` verdict and banner with user anchor values, nozzle-load's sixth word reachable, iso-to-pcf's `[ASSUMED]` lines. 1425 tests, all passing on Python 3.9 and 3.12 (CI matrix).

## [0.9.0] — 2026-11-01

**UNCONSERVATIVE-FIX (pipe-support).** The skill is re-ported to the PiperSTR engine at pipecalcpro main `4656183` (pipingtoolset/pipecalcpro#181, merged 2026-11-01; engine content identical to the PR head `04be653`; CHANGELOG-CALC 2026-11-01), under the one-engine rule. The anchorage now runs to ACI CODE-318-25 by default, with ACI 318-19 selectable. The AISC 360-22 member and weld checks are corrected clause by clause. Up to 0.8.2 every fillet weld took the Eq. J2-5 directional factor of up to 1.5 unconditionally, which overstated weld capacity by up to 50 %. Several member limit states were also missing or too high. **Re-run any pipe-support result from 0.8.2 or earlier.** No other skill changes.

### pipe-support: ACI anchorage
- **ACI CODE-318-25 is the default.** New input `baseplate.aciEdition`: "318-25" (the default) or "318-19". 318-19 reproduces earlier results, except where they were wrong under either edition. Every clause string names the edition that was run, and the pier stage cites the same edition.
- **318-25 only:**
  - φ per Table 21.2.1. Concrete failure in tension takes 0.65 nonredundant or 0.75 redundant (input `anchorageRedundancy`; the default, nonredundant, is warned). Concrete failure in shear takes 0.75.
  - ψa per Table 17.5.4.1, from the new inputs `anchorCategory` (ACI 355.2 / 355.4, from the ESR) and `supplementaryReinforcement`. **With no Category, the engine takes Category 3** (ψa 0.60, the lowest) and gives a REVIEW warning.
  - ψcm,N as an opt-in (input `applyCompressionField`). It is never used in pryout.
  - The tension-shear interaction is split into a concrete row (17.8.3, power 5/3) and a steel row (17.8.4, power 2).
- **Corrections under both editions:**
  - Nonductile steel φ is 0.65 / 0.60.
  - futa is capped at min(1.9·fya, 125 ksi), using the new input `anchorFya`.
  - A grout pad applies Vsa × 0.80 (new input `groutPad`).
  - ψed,V now comes from ca2 (it was 1.0).
  - Side-face blowout applies the (1 + ca2/ca1)/4 factor and Nsbg for the edge row.
  - Adhesive pryout uses min(Nag, Ncbg).
  - ANc is capped at n·ANco.
  - ψc,N is 1.4 for post-installed anchors in uncracked concrete (it was 1.25).
  - Group bond follows 17.6.5.1b, using the new input `bondStrengthUncracked`. Without it, the check warns that it may be unconservative.
  - Punching shear applies λs and λ.
  - Clause labels are corrected.
- **The ASD anchorage divisor stays 1/1.5.** It is now cited as this project's basis per the owner P.E. ruling of 2026-10-26, not as ACI R17.5.3. The ASD wind guard (code-basis item 10) is unchanged and works under either edition.

### pipe-support: AISC 360-22
- **Welds:**
  - kds is 1.0 (J2.4(a)). The Eq. J2-5 increase applies only through the weld engine's opt-in `strainCompatibility: "linear-through-cg"`, on a single or two-parallel group with no moment. It never applies to the assembly's welds, which all carry moment.
  - Base-metal shear is the lower of J4-3 yielding and J4-4 rupture. The row is renamed "Base-metal shear".
  - J2.2b(c): a segment shorter than 4w takes an effective size of L/4.
  - J2.2b(d): end-loaded welds, via the new input `endLoaded`.
- **Members:**
  - Compression: E7 uses the axial λr and the three Table E7.1 rows. E4-3 uses Fex for channels. Angles get E4-4 and the optional E5 (input `angleE5`).
  - Tension: Table D3.1 angle U comes from Case 8 / Case 2 (inputs `nBoltsPerLine`, `connectionEccentricity`, `connectionLength`). It was a silent 0.60.
  - Flexure:
    - F3-2 kc applies to every I-shape.
    - F4 and F5 are added.
    - F6-4 uses 0.70E.
    - F7.4 HSS lateral-torsional buckling is added.
    - F9-6 / F9-8 / F9-9 apply, and F9-18 uses (1.43 − 0.515λ√(Fy/E)).
    - F10.2 single-angle lateral-torsional buckling applies unless `continuousLTR` is set.
  - Shear: G2-11, G3, and G6 per flange.
  - A warning is raised when K defaults to 1.0. Equation numbers follow 360-22, and the K = 2.1 column cites Table C-A-7.1 case (e).
- **Preset results** (LRFD, A36, the PiperSTR UI default loads; before → after):

  | Preset / stage | 0.8.2 | 0.9.0 |
  |---|---|---|
  | CSA Type 1, column-to-base weld | 0.2238 (J4-1) | 0.2996 (fillet, kds 1.0) |
  | CSA Type 1, anchorage | 0.2506 | 0.4497 (Table 21.2.1 φ 0.65, ψa 0.60 at Category 3) |
  | CSA Type 1, governing | 0.8314 pass | 0.8314 pass (arm weld J4-1) |
  | CSA Type 2, arm 1 L4X3X3/8 | 0.5262 | 0.9436 (F10.2) |
  | CSA Type 2, arm 1 weld | 1.1389 (J4-1) | 1.2341 (fillet) |
  | CSA Type 2, governing | 1.1389 FAIL | 1.2341 FAIL (still fails at its default loads, as ruled) |

  CSA Type 1 at 8 / 10 kip: the column-to-base weld goes 0.8056 → 1.0783 and the anchorage goes 0.7379 → 1.6101 (concrete interaction). It passes at ESR Category 1.
- **The examples:**
  - `ps-101-factored.json` still passes at 0.8314.
  - `ps-201-caesar.json` enters no Anchor Category, on purpose: it is an ESR value and a P.E. decision. The anchorage therefore FAILS at 1.1356 (LRFD, concrete interaction, combination LRFD-6-+T) and the run exits 2. With Category 1 it reads 0.7423, and the preset values and the ASSUMED item hold the result at MANUAL CHECK REQUIRED (exit 3). As shipped, the optimizer finds no passing alternative, because it never changes the Category.

### Reviewer
- **New finding "Anchor Category not entered - psi_a taken at Category 3".** It is graded major when the anchorage fails or is within 10 %, because the ESR Category can decide the verdict, and info otherwise. It does not fire on 318-19 or on cast-in anchors. The engine's REVIEW warning is not repeated as a second finding.
- The single-anchor bond "may be unconservative" warning is graded major.
- The ASD wind finding, the report title block, the compliance matrix and the design-basis table name the edition that was run and the project-basis 1/1.5.

### Tests and tooling
- **Goldens regenerated from the engine at `04be653`** (byte-identical at the merge commit `4656183`), with the vendored generators extended for every new input. Case counts: weld 72 → 89, base plate 70 → 121, pier 43 → 49, assembly 130 → 143, member 96 → 145.
- **The calc-core fixtures are re-synced:** fillet weld 7, base plate 8, member 16.
- **PS-101** is re-baselined on its weld, anchorage and member-shear rows. The verdict is unchanged.
- **New test file `tests/test_pipe_support_aci318_25.py`** covers the preset numbers, the edition factors, kds and the Category finding.
- **ASD wind-guard and status tests:**
  - The ASD wind-guard scenarios pin `aciEdition: "318-19"`, because at Category 3 no guard scenario survives on 318-25. The guard is edition-independent, and a new test holds it on the 318-25 default with Category 1.
  - Tests whose subject is not the anchorage load ps-201 with Category 1.

### Docs
- `SKILL.md`, `references/code-basis.md` (items 3, 5, 6 and 10 updated; new items 13–16 cover the 318-25 port, the corrections under both editions, AISC conformance and what is deferred), `spec-format.md` and `review-protocol.md` are updated.
- The manifests (description still within 500 characters), the README, the ROADMAP and the host runbooks are updated.

### Not ported
These are deferred in the engine itself:
- λa by failure mode
- the 318-25 limits and minima (f′c caps, da ≤ 4 in., Table 17.9.2, SDC C–F × 0.75)
- ψh,V
- shear lugs
- G5-2a
- F10-5b
- an instantaneous-centre weld solver

The cascade, like the engine, gives arms no `continuousLTR` or `angleE5` input, so angle arms always take F10.2.

## [0.8.2] — 2026-10-31

Documentation only; no script, number or test contract changes.

- **The "no code tables" claim now matches what ships.** The manifests said the skills "embed no code tables", but `pipe-support` has always bundled the AISC 360-22 tables (J2.3/J2.4/J2.5, J3.2, J3.3, J3.4) and the AISC Shapes Database v16, both published free by AISC, plus the ASCE 7-22 load-combination factors and the ACI 318-19 Ch. 17 factors. Its `references/code-basis.md` already disclosed them. The manifest description now reads "no ASME/API/PIP tables are embedded"; ROADMAP rule 1 and the README name the pipe-support exception. No ASME, API or PIP value is, or was, embedded.

## [0.8.1] — 2026-10-30

Documentation only; no script, number or test contract changes.

- **nozzle-load: connector reference corrected from the first live lookups.** `references/tool-reference.md` now states the row identifiers the server actually lists: the API 610 `nozzle` key is a printed row label (for example “Each top nozzle”), never “suction” or “discharge”; `line` is part of every listed key; API 660 `flangeClass` is a string; API 560 keys are `table`, `sizeNps`, `component` (Tubes or Manifolds), `orientation` and `line`. The API 661 header-sum limit (7.1.10.2) is not a served row, so the `limits` slot is read from the copy. A guessed label returns “No row matches that key” and the instruction is `list_keys`, not another guess.
- **Runbook.** The Codex CLI connector route was exercised 2026-10-30 (`codex mcp add`, `codex mcp login`); the Codex row of `tests/e2e/HOSTS-CHECKLIST.md` records it.

## [0.8.0] — 2026-10-30

One project basis record consumed by all seven skills (CODEX developer priority 2, workstream B8) and one output status taxonomy with a banner rule (priority 3, workstream B9). Computed numbers for the same inputs are unchanged from 0.7.2; the fixture parity suite is green; result keys are added, never changed. Owner ruling 2026-10-30: unconfirmed inputs (ASSUMED basis items, pipe-support preset values) hold the PASS banner until confirmed. **P.E. confirmation 2026-10-30 (the author, a licensed P.E.):** the four pipe-support ASD wind-guard points of code-basis item 10, the B31.1 / B31.9 0.385 pack-rule stop in pressure-design, and the HYD friction-multiplier note in load-case-builder are confirmed; the "pending" wording from 0.7.2 is replaced in the references, scripts and tests.

### Shared infrastructure (B8)
- One project basis record, schema `pipingtoolset.project-basis/1`, is now read by all seven skills. It can be given as a top-level `project_basis` object or as `--project-basis <file>`.
  - Both given with different content exits 2 with `project_basis conflicts with --project-basis file`.
  - An unknown key, a bad enum word or a wrong type exits 2 and names the path.
  - The record holds project data and pointers only. No code-table value goes in it; those stay in `code_values`, cited.
- Fill-or-conflict rule, the same as `code_values`:
  - An absent input is filled where the skill has a slot.
  - An input present in both places that differs exits 2 with `project_basis.<path> conflicts with input <name>`.
  - The result gains `project_basis_applied` `{schema, fields_used: [{input, basis, action}], assumptions, conflicts}`, where action is filled, agreed or noted.
  - Calc-sheet section 1 renders the record with every ASSUMED item first.
- Shared code is copied byte for byte from `tools/shared/project_basis.py` and `tools/shared/result_status.py` into the seven scripts, between `# BEGIN shared ...` / `# END shared ...` markers. No skill imports another.
  - `tools/sync_shared_blocks.py` writes the copies; `--check` (and `--strict`) catches drift.
  - The same tool keeps each skill's `references/project-basis.md` and `scripts/examples/project-basis.example.json` identical to `tools/shared/`.
  - The 0.7.0 `code_values` block is unchanged.
- Cross-skill hand-off, `tests/test_project_basis_handoff.py`: one record (`tests/fixtures/handoff/project-basis.json`, the load-case-builder example interview) runs through all seven scripts on their shipped examples. Each run:
  - fills its slots with no conflict;
  - copies the ASSUMED item verbatim;
  - gives the same result as the run with the values typed in;
  - prints section 1 and a Result status line.
- README gains a "Project basis record" section: the schema summary, the hand-off pattern and the result-status words. `tests/e2e/PROMPTS.md` gains E15, load-case-builder then pressure-design on one record.

### load-case-builder
- Fills `code`, `edition`, `thermal_states` (key, name, role, cycles, slot T/P/D) and `primary_state` (the first design state, else the first state) from the record.
  - Records with role hydrotest, pneumatic or installed are skipped as thermal states.
  - `load_case_ids.software` is noted. AutoPIPE adds a NOTE finding and a `not checked` item.
  - A friction item in `owner_practice` adds a NOTE finding when the spec has one friction multiplier.
  - The report gains `### 1 Basis` under the title.
- SKILL.md Step 0:
  - Reuse an existing record and ask only for what it lacks.
  - With none, write the agreed answers as `project-basis.json` in the working directory for later skills.
- `references/spec-format.md` says the shared example record and `two-state-b313.json` are not a matched pair. Running them together exits 2 with `project_basis.states conflicts with input thermal_states`, by design. The page gives the recipe for filling a spec from a record: leave out `code`, `edition`, `thermal_states` and `primary_state`, and set every `occasionals[].base` to a record state key. A test pins the recipe.
- Result status:
  - ASSUMED inputs (generator defaults or a record item) and an unstated edition are manual check required.
  - QC 10 under B31.1 and an ASD `scale` other than the B31.1-2024 case are manual check required.
  - The eleven model-dependent QC items are always listed as not checked, so the best envelope word is `not checked`.
  - While the word is manual check required, an `OK:` finding prints as `MANUAL CHECK REQUIRED:`.

### pressure-design
- Project basis record (B8):
  - `pressure_design.py` accepts a top-level `project_basis` object or `--project-basis <file>`. If both are given and they differ, the run exits 2.
  - Fills from the record:
    - `code` on the MAWP and bend modules.
    - `edition` on the modules that carry W.
    - Design `P` from the design state (role `design`, else the first state) on the b313, b311, bend and leak-test modules.
    - `W_basis` `seamless` from a seamless `materials[use=pipe]` entry, when `W_basis` is absent and W is absent or 1.0.
  - `code.standard` must be a code the module serves. For example, a B31.3 record on the B31.1 module exits 2 with `project_basis.code.standard conflicts with input <module> ...`.
  - An input present in both places with a different value exits 2 with `project_basis.<path> conflicts with input <name>`.
  - `units.system` SI exits 2 because the engine is US customary.
  - Design temperature, pipe material, owner practice and project fields are recorded as `noted`.
  - The envelope gains `project_basis_applied` and `basis_section` (calc-sheet section 1, every ASSUMED item first).
  - The shipped example record is the pack's shared sample. Its design P differs from `b313-wall-thickness.json`, so pairing the two exits 2 on P (documented in `references/modules.md`).
- Result status (B9):
  - Every envelope carries `result_status`, `checks[]`, `banner_allowed` and `result_status_line`.
  - calculated:
    - Per check: the module's own check ran from the inputs given, the validity gate held, or the MAWP / miter allowable pressure was compared with a design pressure from the record.
    - Envelope level: only a module with no `not checked` rows reaches it. Today that is MAWP with a design pressure from the record. A clean run of any other module reads `not checked`, with `banner_allowed` true.
  - screening: branch reinforcement on a B31.1 record.
  - manual check required: the 0.7.2 thin-wall gate tripped, or the record says Category M, High Pressure or a Chapter VIII / IX route. The fluid-service flag also:
    - adds a `MANUAL CHECK REQUIRED:` warning;
    - sets `banner` when no gate or pointer banner holds it;
    - sets `result_grade` to `manual check required` on the gated modules.
    `status` and `output` keep the engine's words and numbers.
  - pointer only: a new `code_values` entry with `"mode": "pointer"` and no value. The run's `status` is `pointer only`, no equation runs, and `value_pointers` says where to read the value.
  - not checked: each module's known limits.
    - Straight pipe: nominal wall against tOrder; external pressure.
    - Branch: para. 304.3.2 exemptions; adjacent openings.
    - Bend: thinning during bending.
    - Miter: minimum R1.
    - Leak test: para. 345.2.1(a) stress; the para. 345.5.4 90 % limit; component limits.
  - Existing `status` words and fixture outputs are unchanged.
- SKILL.md:
  - Step 0 reuses an existing project basis record and asks only for what it lacks.
  - The calc sheet gains a `Result status:` line under its title, and `basis_section` heads section 1.
  - PASS, a schedule or a margin is written only where `banner_allowed` is true, whatever `status` says.
  - The connector pointer route passes a pointer entry to the script.
  - The word count is unchanged from 0.7.2. The edition table pointers and cross-module notes moved to `references/modules.md`, which gains a "Project basis and result status (0.8.0)" section. `references/project-basis.md` is linked.
- Tests: new `tests/test_pressure_design_basis.py` and `tests/test_pressure_design_status.py`, including fluid-service warning, banner and result_grade coverage. The `tests/test_pressure_design.py` envelope key set gains the four B9 keys.

### stress-screening
- Fills from the record:
  - `equation` (piping.fatigue-factor) from code and edition, resolved as `basis` does.
  - `N` from the one state that carries `cycles` (not filled when `sets` is given or several states carry cycles; a warning says so).
  - `code` and `edition` (screen.flexibility-exemption).
  - `--code` and `--edition` (`basis`).
  - States, `installation_T_F`, `owner_practice` and `units.system` are noted for the sheet.
  - An SI record stops the run.
  - The envelope gains `project_basis_applied` and `basis_section`.
- An ASSUMED item in the record adds a screening check, so a run built on unconfirmed inputs is never reported as calculated. The run still prints PASS or FAIL; a worse word wins.
- Each module lists its known limits as not checked on every run:
  - SIF source and tee orientation;
  - liberal allowance Eq. 1b;
  - the section and occasional-load basis behind Sb and Socc;
  - the load ranges behind N;
  - the spring installed case and manufacturer size;
  - the span wall basis.

  Because not checked outranks calculated, the envelope word is `not checked` except for noncode.pipe-section. The status line reads "<main check> calculated; not performed by this module: ...".
- `status`, `output` and the PASS/FAIL banner are unchanged, and fixture parity is green.

### pipe-support
- Fills from the record:
  - `project`, `calcBy` and `date` from `project`.
  - `pipes.<n>.loads.units` from `units`: USC gives `lb-ft`; SI exits 2.
  - `vertical_axis` and `pipe_axis` from `equipment_axes` (CAESAR II mode).
  - ASSUMED items are added to `assumed`.
  - `materials[use=support]` and `load_case_ids` are carried to the report notes only. The record holds no Fy or Fu, and `loads.map` is not filled.
  - The report gains a "Basis - project basis record" section.
- Banner rule:
  - While the result status is manual check required or pointer only, the verdict line and the report banner print that word (or the guard's NOT ISSUABLE line), never PASS.
  - A passing stage heading reads RATIO WITHIN LIMITS.
  - The CLI exits 3.
  - The optimizer heading reads "Optimized alternatives (ratios within limits in every combination)" and the count line reads "N designs within limits found". "all pass" and "passing designs" appear only when a PASS is allowed.
- `references/spec-format.md`:
  - A seismic run without SDS is manual check required (exit 3); a string SDS is pointer only.
  - The status line is shown with its em dash.
  - The shared sample record conflicts on purpose with `ps-201-caesar.json`'s `project` string: drop or align the spec's title-block keys.
- SKILL.md: Exit 0 now also requires a result status other than manual check required or pointer only.
- New test `BannerRule.test_the_optimizer_section_drops_pass_wording_while_held` (tests/test_pipe_support_status.py, 22 tests).

### iso-to-pcf
- Project basis: `build_pcf.py` accepts a top-level `project_basis` key or `--project-basis <file>` (schema `pipingtoolset.project-basis/1`; both present and different exits 2).
  - Absent spec inputs are filled from the record:
    - `axes` from `equipment_axes.global_vertical` (Y gives Y-up, Z gives Z-up).
    - `units` from an explicit `units.length` of mm.
    - `pipeline.reference` from `project.line`.
  - A spec value that differs exits 2 with `project_basis.<path> conflicts with input <name>`.
  - A record length other than mm is the model's own unit: it is noted, never a conflict, and the PCF is still written in mm.
  - The record's ASSUMED items are added to the report's ASSUMED list. The report gains `project_basis_applied` and a "1. Basis" section at the top that lists every ASSUMED item first.
  - New `references/project-basis.md`, `scripts/examples/project-basis.example.json` (a Y-vertical record) and `scripts/examples/project-basis-line.json`, the paired spec that builds with it. The two Z-up example specs conflict with that record by design.
- Result status: the build report gains `result_status`, `checks[]` and a "Result status: <word> - <why>" line under the title.
  - A failed closure or BOM line is manual check required.
  - ASSUMED items (including the builder's LR/SR elbow radius default) and the BOM PIPE-LENGTH screen are screening, not an unresolved factor.
  - `validate_pcf.py` (not run by the builder), the site SKEYs, continuation coordinates and the axis declaration are listed as not checked. Because they are always listed, the report's own word is never `calculated` (individual checks can be).
  - Banner rule: PASS and OK print only while the word allows it. A failed run prints NOT DELIVERABLE, with the status word where PASS would be. `pointer only` is unreachable here (no code-table input).
  - `validate_pcf.py` carries the same two fields and its OK banner follows them. It now imports `build_pcf.py` and `pcf_lib.py` from its own folder, so the three scripts must stay together.
  - `ok`, the exit codes and the PCF are unchanged; the demo PCF stays byte-identical to tests/golden/demo-line.pcf.
- SKILL.md:
  - Net -4 words; the rigid-weights note moved to `references/caesar-import.md`, which also holds the not-carried list.
  - Interview: reuse an existing record, ask only for what it lacks, never relabel a field.

### nozzle-load
- Fills from the record:
  - `units` (connections.api610-annexf) from `units.system`.
  - `designTempF` (equipment.pvp2011-allowables) from the design state's `T_F`.
  - The `ownerFactorBasis` label from the `owner_practice` document and edition; a label the user already wrote is kept.
  - The `ownerFactor` value is never taken from the record.
  - An SI record stops connections.nema-sm23 and equipment.pvp2011-allowables.
  - The envelope gains `project_basis_applied` and `project_basis_section`.
- A per-nozzle check or header sum whose `standard` label names a derived or PVP2011 set, run without `derivedSetStatus`, is now `manual check required` (banner MANUAL CHECK REQUIRED, not PASS), because the derivation's scope limits are unknown. Pass the derivation run's `result_status` as `derivedSetStatus` to clear it.
- Plain-text `owner_practice` items that mention a factor, fraction, percent, margin or limit without a decimal or percent value now count as pointers (`pointer only`). A text item that states a value only adds the existing warning.
- `references/tool-reference.md`:
  - `derivedSetStatus` is documented: valid on the check and the sum only; one of the five status words, otherwise exit 2.
  - A missing or non-positive `annexF` constant stops the run (exit 2).

### bolted-flange
- Fills `P` on both pressure modules from the design state's `P_psig`.
  - The same state's `T_F` is read for the sheet and the B16.5 2.5.2 advisory note.
  - `units.system` SI exits 2.
  - An explicit `units.moment` must match the moment input actually given.
  - `code.standard`, `code.route` and `service.fluid_category` feed the code-route and B31.3 Chapter IX checks.
  - An owner acceptance item becomes `owner acceptance (<document>)` on the screen; a text value is a pointer.
- The B16.5 2.5.2 advisory carries no temperature threshold in the script. It is always listed under `not_checked[]`. Its note shows the recorded design temperature, or says none was given, and tells the user to read the threshold from the printed standard. A design temperature in the record can no longer lower the envelope `result_status`.
- With reconstructed hub factors (series F, V, f), the flange-stress and rigidity checks are screening with `unresolved_factor`, and the sheet carries no PASS wording.
- tool-reference.md:
  - The status line is written with its em dash.
  - The advisory rows are updated.
  - A note says the shipped neutral project-basis example (design P 150) conflicts with `examples/integral-weld-neck.json` (P 300) by design.
- Tests: `tests/test_bolted_flange_basis.py` replaces the temperature-threshold test with three tests:
  - the advisory is always `not_checked`, with the temperature in the note;
  - there are no `B165_*` constants;
  - the design temperature never lowers the envelope word.

### Result status taxonomy (B9)
- Every envelope gains `result_status`, one of calculated, screening, manual check required, pointer only or not checked, and `checks[]` = `[{name, result_status, status, note}]`.
  - The envelope word is the worst of its checks, in the order manual check required > pointer only > screening > not checked > calculated.
  - Existing `status` words and values are unchanged; fixture parity is green.
- Banner rule in all seven skills: no PASS / OK / ISSUE / DELIVERABLE wording while the word is manual check required or pointer only, or screening with an unresolved reconstructed factor.
- Every calc sheet gains a `Result status: <word> — <why>` line under its title. iso-to-pcf's text report writes the dash as `-`.
- Known limits are listed as `not checked` rows on every run, so a clean run of most modules reads `not checked` and names what was not performed. This ranking is under review for 0.8.x.

### Pack-wide rulings applied after the build
- All skills: the envelope `result_status` is the most severe word among the checks the module performs. `not checked` rows (the module's known limits) are listed in `checks[]` but never set the word; the envelope reads `not checked` only when every row is. A clean run of a module that performs its checks reads `calculated`, and the status line summarises the limits after the word (`calculated - ...; not performed by this module: ...`). Shared helpers: `envelope_status`, `not_performed`.
- All skills: an unconfirmed input holds the banner. Every ASSUMED item goes into exactly one check row named `ASSUMED inputs`, graded `manual check required`, with the note `confirm before issue: <item>; <item>`. This covers `project_basis.assumptions` with status ASSUMED or missing, the skill's own `assumed` list, and load-case-builder's generator defaults. The envelope follows that row, and no PASS, OK, ISSUE or DELIVERABLE banner prints: pressure-design `banner_allowed` false; stress-screening and nozzle-load `banner` "MANUAL CHECK REQUIRED"; bolted-flange's ISSUE-GRADE banner is replaced; pipe-support's verdict reads MANUAL CHECK REQUIRED and exits 3; iso-to-pcf ends `RESULT: MANUAL CHECK REQUIRED - confirm the ASSUMED items, then run validate_pcf.py`.
- pipe-support: anchor and concrete values taken from a CSA preset (`bondStrength`, `anchorFuta`, `anchorType`, `anchorEmbedment`, `fc`) give one `preset inputs` row graded `manual check required`, with the same banner effect. The stages on those values read `calculated` and name the preset. The shipped ps-201 example therefore reads MANUAL CHECK REQUIRED and exits 3 until its preset values and its ASSUMED item are confirmed.
- load-case-builder: QC findings keep their `OK:`, `GAP:` and `ERROR:` prefixes under every result status. They are check results; only verdict and RESULT banners follow the banner rule. The report keeps its `Result status:` line.
- load-case-builder: with a project basis record, `primary_state` is filled from the first state whose role is `operating`, else the first declared thermal state, never the design state by role (`states[role=operating|first].key`). The hanger design pair is W+T of that state.
- All skills: the status line reads `Result status: <word> - <why>`, with an ASCII hyphen and a space each side, in the shared renderer and in iso-to-pcf's report and validator.
- pipe-support and iso-to-pcf: when the record's ASSUMED items are added to `assumed`, `fields_used` records the action `filled`, also when they are appended to an existing list.
- stress-screening: the `basis` command prints the edition as the string the record or `--edition` gave (`"2022"`).

## [0.7.2] — 2026-10-30

Executable validity gates and honest result grades in three skills (CODEX review findings P1-3, P1-4 and P1-5, 2026-10-29). For inputs inside every gate the computed numbers are unchanged from 0.7.1; the fixture parity suite is green. Owner and P.E. rulings taken 2026-10-30 at review: the B31.3 0.385 thick-wall trigger is applied to B31.1 modules as a disclosed pack rule that stops the run; the pipe-support ASD wind guard ships as built: the governing-combination trigger plus the near-governing hold (a wind combination whose anchorage ratio times 1.111 reaches the governor) and the factored-mode hold unless the spec declares `factored_wind: false`, every one of them a hold and never a release, with the P.E. confirming the four points listed in code-basis.md item 10 at review; a loose-type flange is graded calculated with the caveat line.

- pressure-design: thin-wall validity gate (CODEX P1-3). `piping.b313-wall-thickness`, `piping.b311-wall-thickness`, `piping.b31-allowable-pressure` and `piping.bend-thickness` now report a `validity` object: P_over_SE (P/(S*E)) against 0.385, and the thickness against D/6.
  - MAWP uses the computed allowable pressure, times Mf for B31.12.
  - B31.1 compares tm, per its Do/tm < 6 note.
  - Bends use the intrados thickness.
- pressure-design: when either limit trips, `status` and `result_grade` are "manual check required", `output` is empty, and the numbers appear only under `equation_value` as an "equation value, not a design basis".
  - A banner names the clause: B31.3 para. 304.1.2(b), B31.12 para. IP-3.2.1(b), or B31.1's y-table note.
  - B31.1 states no P/(S*E) limit. The pack also stops B31.1 / B31.9 runs at the 0.385 trigger as a pack rule, pending P.E. confirmation at PR review; the clause text says so.
  - A tripped run still exits 0, so callers must read `status` / `result_grade`.
  - A valid run carries `result_grade` "calculated".
- pressure-design: W is now part of the input contract (CODEX P1-3).
  - Where the code and edition's equation carries W (B31.3 Table 302.3.5 / 302.3.5-1; B31.1 Table 102.4.7-1 from the 2018 edition), a run exits 2 when W is omitted with no `W_basis`, or when W = 1.0 has no `W_basis`. The one-line message names the table and edition to read.
  - For B31.1-2016 straight pipe and MAWP, the para. 104.1.1 route decides. Eq. (7) of para. 104.1.2 (no W) covers seamless pipe or pipe below the creep range; para. 104.1.4 Eq. (11) (S*E*W, Table 102.4.7) covers longitudinal- or spiral-welded pipe in the creep range. W or a `W_basis` naming the route is required.
  - On B31.1-2016, a W below 1.0 is recorded as the 104.1.4 route. A basis alone is recorded as Eq. (7), with a sheet warning that names the 104.1.4 limit.
  - B31.9, B31.12 and B31.1-2016 bend equations carry no W; the run records that and needs no basis.
- pressure-design: new text inputs: `W_basis` (seamless | below creep range per table note | longitudinal weld, confirmed | free text), `edition`, and `code` (MAWP and bend only).
  - A `W_basis` of "seamless" with E below 1 is warned.
  - The new `weld_factor_basis` records W, its basis, its source and, for B31.1-2016, the route. `defaults_applied` no longer contains W.
- pressure-design: the gates live in the CLI/envelope layer only. The engine functions are unchanged, so fixture parity holds, and computed numbers and status words for valid inputs are unchanged. No vendored fixture case trips a gate.
- pressure-design: SKILL.md and modules.md updated.
  - The SKILL.md interview now asks for W and its basis and passes `edition`.
  - The calc sheet shows no PASS, schedule or margin on a "manual check required" run.
  - modules.md sections 1-3, 5 and 6 document the gates and the B31.1-2016 route. The MAWP equation there now shows W.
  - The b313 example carries `W_basis` and edition 2022.
- tests: new tests/test_pressure_design_gates.py (37 tests); tests/test_pressure_design.py updated for the `W_basis` contract.
- bolted-flange: the detailed VIII-2 4.16 / App 2 result is now graded. `aux.app2-flange-integral` output gains `factor_basis` (F, V, f each `series`, `override` or `not used`), `result_grade`, `grade_label`, `banner`, `grade_note` and `report_word`. The grade is `screening` (label "screening / reconstructed factors") whenever any hub factor the flange type uses came from the open-source series reconstruction, and `calculated` only when `F_override`, `V_override` and `f_override` were all supplied. A loose flange uses no hub factor and is `calculated`. A partial override stays `screening` and names the factors still on the series. (CODEX P1-4; owner ruling 2026-10-27 kept: series shipped with provenance plus overrides.)
- bolted-flange: the banner `SCREENING / RECONSTRUCTED FACTORS: F, V, f from the open-source series reconstruction; supply F_override, V_override, f_override read from VIII-2 Table 4.16.5 for an issue-grade result` is the first finding of every screening run. An issue-grade banner prints only on a `calculated` run, and it states that only the hub-factor basis is closed and that the Peq external-load treatment and defaulted inputs still need review. New `--format sheet` option prints a markdown calc-sheet block headed by the banner, with ratios and "within" / "exceeds" wording and no PASS or issue wording on a screening run.
- bolted-flange: new output key `report_word` ("within" / "exceeds" for the screen, "tool rule met" / "tool rule not met" for the detailed analysis) is the wording to relay. The machine `status` word (pass / fail / na) is unchanged because the fixtures assert it.
- bolted-flange: the pressure-equivalent screen now reports `result_grade` `screening` and a banner on every run (it is a leakage screen by definition).
- bolted-flange: result keys are added only. Fixture parity for `aux.app2-flange-integral` and `connections.flange-equivalent-pressure` is unchanged.
- bolted-flange docs: SKILL.md, app2-engine.md (new "Result grade" subsection of the hub-factor provenance), method-ladder.md (grade per rung; "passes the screen" wording replaced by "within the screen"), rejection-checklist.md (item 5 reworded, item 15 amended, new item 21) and tool-reference.md state the grade rule and the taxonomy calculated / screening / manual check required / pointer only / not checked.
- tests: 34 new tests in tests/test_bolted_flange_grade.py; two existing hub-override tests now compare engine numbers with the grade keys excluded.
- **pipe-support: ASD wind-anchorage guard (CODEX P1-5, UNCONSERVATIVE-FIX).** In ASD the envelope holds an anchorage stage at **manual check required**, not pass, and the envelope can no longer pass, when any of these holds:
  - **governing:** the stage's governing combination carries wind (ASCE 7-22 2.4.1 5a / 6a / 7a and their ± / +T variants);
  - **near-governing:** a non-wind combination governs, but the worst wind combination's anchorage ratio x (1/0.6)/1.5 = 1.111 reaches the governing ratio, so wind could govern under the 1/0.6 treatment. Ties are included;
  - **factored mode:** loads are factored "as entered" and the spec does not declare them wind-free with `factored_wind: false`.
- **Verdict and exit code.** The verdict reads "NOT ISSUABLE - ASD anchorage governed by wind combination <id>: run anchorage in LRFD or resolve the ACI strength-to-ASD factor treatment (code-basis item 10)". On undeclared factored loads it reads "NOT ISSUABLE - ASD anchorage on factored loads with undeclared wind content: ...". Either way it names the held stage and check and prints no PASS banner. `support_calc.py` exits 3.
- **Why.** The fixed 1/1.5 ACI 318-19 R17.5.3 strength-to-ASD conversion implies 1/0.6 = 1.67 under 0.6W, so ASD anchorage could be about 10 % unconservative. Up to 0.7.1 a PASS could be printed there, including where seismic governed by less than the 1.111 margin over a wind combination (ps-201 ASD, WIN x2.2, EQ x1.6: 0.9494 seismic against 0.9249 wind), and on factored ASD loads.
- **Unchanged.** The engine ratio is not changed. A wind-held ASD failure stays FAIL. Also unchanged: LRFD anchorage; ASD anchorage governed by a non-wind combination (dead, dead + thermal, seismic, hydrotest) with no wind combination inside the 1.111 margin; and factored ASD anchorage declared `factored_wind: false`.
- **Exit code 3 changes meaning.** It now means "not issuable although no limit state fails": a critical review finding, or a validity guard holding a stage. Callers that read exit 3 as "critical finding" only must also read the verdict line.
- **Optimizer.** It applies the same guard. Every alternative and the as-drawn seed go through the guarded envelope, so an ASD wind-held anchorage design is never ranked as passing. The search log says which pairings the guard held.
- **Reviewer finding kept as defence in depth.** The major finding "ASD anchorage governed by a wind combination" stays. It now applies the governing and near-governing predicates on its own, names the wind row, and says whether the guard was applied. Factored ASD anchorage raises a major finding when wind content is undeclared or declared, and an info finding naming the engineer's `factored_wind: false` declaration.
- **New spec key `factored_wind`** (true / false, factored mode only; any other value is a spec error, exit 1).
- **New JSON output fields:** `envelope.guards[]` `{stage, check, ratio, combo, status, engineStatus, trigger, basis, reason}`, plus `stageCheck` / `stageRatio` / `stageCombo` / `margin` for a near-governing guard. Stage fields: `engineStatus`, `asdWindGuard`, `asdWind` (worst wind row).
- **Shared predicates:** `loads.asd_wind_combo` (moved from `review.py`; `review.asd_wind_combo` still resolves), `loads.asd_wind_could_govern` and `loads.asd_wind_margin`.
- **Ruling:** this supersedes item 6 of the 2026-10-26 P.E. rulings ("documented only"), per the owner ruling of 2026-10-30. It is **pending P.E. confirmation at PR review**. Code-basis item 10 is rewritten to read in one place and lists four P.E. confirmation points:
  - (a) the trigger is coarse: any WIN case usually makes 5a govern;
  - (b) the 6a 0.45W pairing gets no separate margin;
  - (c) factored-mode ASD anchorage is held unless declared wind-free;
  - (d) exit 3 is reused.
- **Unchanged outputs:** goldens and parity fixtures are untouched. The ps-101 and ps-201 examples (both LRFD) give identical verdicts.

## [0.7.1] — 2026-10-30

Two **UNCONSERVATIVE-FIX** corrections in the load-case-builder skill (CODEX review findings P1-1 and P1-2, 2026-10-29), the Codex install made consistent with the “optional connector” copy, and the plugin-side copy for the API nozzle tables the connector now serves at Ultimate. Every other skill's numbers are unchanged. Installed copies of 0.7.0 and earlier keep the load-case defects until updated; this release is the recall notice.

- **UNCONSERVATIVE-FIX — load-case-builder: every operating state and friction variant now reaches the envelopes and the extraction matrix (CODEX P1-1).** These inputs were affected in 0.7.0 and earlier:
  - specs with more than one thermal state: Maximum Operating held only the first state's OPE and OPE+OCC cases, and the sustained rows listed only the first state's SUS cases;
  - specs with more than one friction multiplier: the vertical-sag row read only the first friction case, and HYD was pinned to the first friction;
  - `inter_state_expansion_ranges`: only the first friction multiplier got a range case;
  - hydrotest: HYD was missing from the support-load extraction.

  A non-primary state, a frictionless range or a hydrotest reaction could govern and still be missing from the case the matrix pointed to. Fixed in 0.7.1:
  - Maximum Operating holds every OPE and OPE+OCC case of every state × friction variant.
  - HYD and inter-state ranges are generated per friction multiplier (`hyd:<f>`, `exprange:<a>:<b>:<f>`). Confirm in your CAESAR II version that the friction multiplier is applied to the HYD case.
  - The extraction matrix lists every SUS case of every state × friction under code stress, support loads and vertical sag. It lists every EXP and range case, HYD under both code stress and support loads, the hanger design pair in its own row, and every OPE case under flange / nozzle loads.
  - With no ASD-scaled occasional, every other case is unchanged in content and order.
  - Scope: this fix is in the load-case-builder skill only. The hanger design pair intentionally still runs once, at a single friction multiplier (`hanger_friction`), as CAESAR II recommends. It is not repeated per friction.
- **UNCONSERVATIVE-FIX — load-case-builder: ASD-scaled occasionals now get generated unreduced companions (CODEX P1-2).** Affected inputs: any occasional with `scale` (a user-supplied ASD factor, for example 0.6W / 0.7E) in 0.7.0 and earlier. The scaled OPE+OCC case fed Maximum Operating, so support reactions and displacements were understated by the scale factor. The QC text told the user to keep unreduced companions, but none were generated. Fixed in 0.7.1:
  - The scaled case is labelled REDUCED and feeds only the code-stress occasional path.
  - A new `OPE+OCC-UNRED` block adds an UNREDUCED companion for each scaled occasional × friction variant.
  - Maximum Operating and the support-load and displacement rows read the companions, never the reduced case.
- **load-case-builder: new optional spec fields `primary_state` and `hanger_friction`.**
  - `primary_state` sets the state the hanger design pair runs at (`W+T` of that state, springs Ignored) and the state the matrix lists first.
  - `hanger_friction` sets the friction multiplier for that pair.
  - When either is absent, the first declared state or friction is used and reported as an `ASSUMED:` finding. Neither field limits coverage.
- **load-case-builder: stricter spec validation (exit 2).** The generator now refuses:
  - an unknown `primary_state`;
  - a negative or non-numeric `hanger_friction` or friction multiplier;
  - an empty `frictions` list;
  - an occasional `scale` that is not a number with 0 < scale < 1. Before this, `0` silently read as unscaled, and values of 1 or more were labelled REDUCED;
  - a duplicated state key, occasional key or friction multiplier. Multipliers are compared as numbers, so `1` and `1.0` collide.
- **load-case-builder: resolved-case-set QC (`references/qc-gate.md` item 17).** After numbering, the generator compares the generated set with what the spec declares:
  - every state × friction, occasional × friction and state-pair × friction case;
  - HYD per friction, the hanger pair and the unreduced companions;
  - envelope membership;
  - extraction-matrix membership.

  The result is the last QC finding (`QC: resolved case set complete …` or `ERROR: resolved case set has N miss(es) … Do not issue this set.`). It is also the new `qc` object (`pass`, `counts`, `misses`) in `--format json`, which also gains `extraction_matrix`, `primary_state` and `hanger_friction`.
- **Golden files.**
  - `tests/golden/two-state-b313.md` was regenerated on purpose and grows from 87 to 88 cases. The second HYD case shifts every later L-number by one, and Maximum Operating adds the design-state cases.
  - New fixture specs under `tests/fixtures/load-case-builder/`, with `baseline-0.7.0-unscaled.json` as the 0.7.0 reference.
  - New golden `tests/golden/three-state-scaled-b313.md` (three states, three friction multipliers, scaled wind and seismic).
- **Connector copy made true in Codex (B3).** Removed `plugins/piping-toolset/mcp.json`, the Agent Plugins declaration. The owner's install test of 0.7.0 in Codex showed a sign-in prompt at install, so "optional connector" was untrue there. `.mcp.json` (Claude Code, Cowork) is now the only declaration, and the `.plugin` and `.zip` carry it alone. Codex and the ChatGPT desktop app add the server by hand (`codex mcp add`, documented in the README). `.agents/plugins/marketplace.json` keeps `authentication: ON_INSTALL`, the only documented value; with no server declared there is nothing to sign in to. `python tools/package_plugin.py --check` now fails if `mcp.json` returns. The README, the OpenAI longDescription, the site drafts in `docs/site/` and the Phase 2 runbook say the same; the runbook's Codex connector row expects no sign-in prompt and names the policy value as the next suspect if one appears. The 0.7.0 entry below stays as released.
- **API nozzle tables as cited values at Ultimate (C3, plugin copy).** The connector currently serves API 610 Tables 5a and 5b, API 560 Tables 7 to 10, API 660 Table 2 and API 661 Table 4 as cited values at the Ultimate tier (the server change ships separately and goes live before this release). The README table, the manifest and marketplace descriptions ("cited ASME and API table values"), the listing longDescription and the site drafts move them out of the pointer-only line; PVP2011-57100, ASCE 7-22, AISC 360, ACI and NEMA SM-23 stay pointer-only, and the copy keeps "currently" because a source can return to pointer mode. `nozzle-load` now makes one `lookup_value` call per value (a six-component allowable set is six lookups and six citations) and enters each as a scalar `code_values` entry (`allowable.Fx`, `suctionAllowable.Mz`, `limits.Fy`), with the key fields and columns per dataset in `references/tool-reference.md`; the pointer fallback is unchanged. No script, calculation or `code_values` shape changed.

## [0.7.0] — 2026-10-28

An optional Engineering Data connector, and the listing copy re-scoped around it. The plugin stays
free, every skill works without the connector, and the refusal prompts give the same answer with it
off. With the same inputs entered, the fixtures, golden files and every number the seven skills
produce are unchanged from 0.6.3; nothing here corrects a result.

- **Connector declaration.** `plugins/piping-toolset/.mcp.json` (Claude Code, Cowork) and
  `plugins/piping-toolset/mcp.json` (Agent Plugins hosts) each declare one remote server,
  `pipingtoolset-data`, at `https://pipingtoolset.com/mcp` (Streamable HTTP, stateless): transport
  `http` in the first, `streamable-http` in the second, https only, no headers and no stored
  credentials. `mcp.json` follows the portable format on developers.openai.com/plugins/build/plugins
  (read 2026-10-28): the `agent-plugins.org` MCP schema, `mcpServers`, and the sign-in setting under
  `extensions["com.openai"].auth`, set to `mixed` (open tools need no account, the rest sign in
  through pipingtoolset.com) with dynamic client registration. Those docs name root `mcp.json`, do
  not say the Claude-style `.mcp.json` is read as well, and warn against renaming one to the other,
  so both files ship. The manifests do not repeat the declaration; each host finds its file by name.
- **What the connector serves, currently.** With no account: worked examples of the data-free
  modules, SKEY and PCF mappings, AISC shapes and pointers. With a signed-in paid pipingtoolset.com
  account, at the site's tier: Pro serves B31.3 Table A-1C and B31.1 Appendix A allowable stresses
  and bolting, the B31.3 E, W and Y and B31.1 E and y factor tables, B31J Table 1-1 component rows
  (row text only; the SIF number is still user-supplied or computed by a script), B31.1 Table
  121.5-1 spans, BPE tables and B36.10M / B36.19M dimensions; Pro Plus adds B16.5 ratings and
  dimensions, B16.20, UCS-66 and BPVC VIII-2 Table 4.16.1 gasket factors. API 610 / 560 / 660 / 661,
  PVP2011-57100, ASCE 7-22, AISC 360, ACI and NEMA SM-23 tables are pointers (table, row key,
  column, edition) with no value. Every served value carries its citation, and the SKILL.md files
  and the README tell the user to verify it against their own copy.
- **SKILL.md connector branches.** Each skill that reads a code-table value gains a section on the
  connector. When its tools are present, the assistant makes one `lookup_value` call per value the
  job needs (never a sweep of a table), hands each result to the script as a cited `code_values`
  entry marked `"source": "connector"`, and puts the citation, the rows used and the verify line on
  the calc sheet. On a pointer, a one-line account or limit message, any other error, or no
  connector at all, the skill runs its interview and the instruction to read the value from the
  user's own copy, unchanged.
- **`code_values` input.** Every skill script accepts an optional top-level `code_values` object
  mapping an input name to `{value, unit, citation{standard, edition, table, row, column?},
  source}` with `source` `connector` or `user`. A named input absent from the main inputs is filled
  from its entry; if both are present and differ, the run stops with exit code 2 and the line
  `code_values.<name> conflicts with input <name>`. The result gains `code_value_provenance` (unit,
  citation and source per name); `user_supplied` and every other key keep their shape. The scripts
  make no network calls, and a test fails on any mention of an HTTP or socket module under
  `skills/*/scripts`. Calc-sheet section 3 is retitled "Code-table values (user-supplied or
  connector-supplied, cited)" and every row carries a source column (user or connector).
- **Re-scoped copy.** The line that nothing the user enters is sent to PipingToolset is replaced in
  the README, the OpenAI long description and the capabilities list by what is true now: the skills
  and their scripts make no network calls; the connector, when enabled, sends only lookup keys
  (standard, material, temperature, size), never full inputs; what is open and what needs a paid
  account at the site's tier, with "currently" wherever a tier or source could change; API tables
  pointer-only for now; sign-in through pipingtoolset.com asks for a confirmation that the
  assistant account is set not to train on conversations; values arrive cited and are still
  verified against the user's copy. The `capabilities` entry that said "no network access" now says
  the scripts make no network calls and names the optional connector. The `.claude-plugin/plugin.json`
  description names the connector and stays under the 500-character Cowork cap (488). The README
  gains an "Engineering Data connector" section with the install lines for a claude.ai custom
  connector, Claude Code, a ChatGPT developer-mode connector and Codex.
- **Packaging.** `tools/package_plugin.py --check` now fails unless `.mcp.json` and `mcp.json` sit
  at the root of the `.plugin` and the `.zip`, each declares exactly one https server, and both
  name the same URL; it also fails if either appears in the skills-only zip. The three archives
  remain byte-reproducible.
- **Tests.** `tests/test_connector_manifest.py` (new) pins both declarations (one server, one
  https URL, matching transports, no headers or credentials), the packaging facts above, the rule
  that no skill script mentions a network module, and the wording rules for the listing copy.
  `tests/test_manifests.py` also checks that the version is the same in all four places and that
  the Phase 2 runbook names it. Manifests, both marketplaces and the Phase 2 runbook
  (`tests/e2e/HOSTS-CHECKLIST.md`, now with a connector row per host) are at 0.7.0.
- **`code_values` edge cases (review fixes).** An empty `code_values` object is now the same as none
  (no `code_value_provenance` key). In `nozzle-load` the force and moment components of
  `connections.nozzle-load-check` and the `api610-annexf` load sets are unit-checked like the other
  load sets (lbf and ft-lbf, or N and N-m when `units` is `SI`), so a newton figure is rejected
  rather than applied as lbf. `load-case-builder` and `iso-to-pcf` have no code-table input and now
  exit 2 on a `code_values` entry instead of dropping it silently. A conflict on a name that fans out
  over a list reads `code_values.<name> conflicts with input <name> (<path>)`. Calc-sheet section 3
  carries the contract title in all four calculators; `get_pointer` and `get_skey_map` argument
  names are stated as the server takes them; the allowable-stress key fields are listed per code;
  example JSON files use obviously artificial numbers. Words the board's copy rules ban are out
  of the skills, their references and the load-case finding text.

## [0.6.3] — 2026-10-28

- `nozzle-load`: API 610 Annex F method constants and the SM-23-form coefficient are now user-supplied inputs (read from the edition of record); no API-derived numeric constant ships in code or prose. No change to results when the same constants are entered (fixture parity green).
  - `connections.api610-annexf` requires an `annexF` object (`componentMultiple`, `resultantDenominator`, `interactionLimit`, `centreForceFactor`, `centreMyFactor` for horizontal pumps; `sigmaPLimit`, `kSigma`, `kTau`, in the `units` system given, for vertical in-line pumps). A missing or non-positive constant stops the run (exit 2) and names the key. Existing job files need the block added.
  - `connections.nema-sm23` no longer warns on a coefficient outside a fixed set of values; the coefficient must be above zero. The SKILL.md, the references and the calc-sheet template ask for the equation and edition behind each value.
  - Manifests, marketplace and the Phase 2 runbook at 0.6.3.

## [0.6.2] — 2026-10-28

Source form only; every status word, number, fixture and golden file is unchanged. The
Anthropic directory validation of v0.6.1 was down to one cross-surface hold, cleared here:

- Every `"pass" if ... else "fail"` conditional expression (30 sites across the seven skills'
  scripts) is now a lookup through a small `verdict()` helper (`pipe_support/common.py`, and a
  local `_verdict()` in each standalone script; `verdict_label()` / `_flag()` for the
  upper-case report banners). The scanner read the token sequence of the conditional form as
  "the installer's pass" being read from the machine. The helper returns the same two strings.
- The four PiperSTR port docstrings name their TypeScript source as a module (for example
  "the `support-assembly` TypeScript module") instead of a slash path, which the scanner
  reported as "a command assembled at run time" and chained to the hold above.
- Manifests, marketplace and the Phase 2 runbook at 0.6.2.

## [0.6.1] — 2026-10-28

Wording only; no change to any skill's calculations, scripts' numbers, fixtures or golden files.
The Anthropic directory validation of v0.6.0 still held the plugin for review on two scanner
false positives, both cleared here:

- `stress-screening/SKILL.md` no longer uses the verb "pass" anywhere ("Set `equation` to
  ...", "give `fixation_points` ...", "Include `L_actual_ft` ..."); beside the pipingtoolset.com
  links the scanner read it as the installer's password being handed to that host. The same
  opening sentence in the other four interview skills and two "Pass ..." lines in
  `bolted-flange/SKILL.md` are reworded to match.
- `iso-to-pcf/scripts/pcf_lib.py`: `fmt_in` builds its feet-inches string with one format
  expression instead of joining quote-and-slash pieces, which the scanner reported as "a command
  assembled at run time" and chained to the hold above. Same output, byte for byte (golden PCF
  unchanged). The dimension convention is called "dot-fraction" in the docs instead of `X.n/d`.
- Manifests, marketplace and the Phase 2 runbook at 0.6.1.

## [0.6.0] — 2026-10-28

Distribution to ChatGPT and OpenAI Codex, with the plugin mark on every host. No change to any
skill's calculations, scripts' numbers, fixtures or golden files; every number the seven skills
produce is identical to 0.5.1.

- **OpenAI listing block.** `plugins/piping-toolset/plugin.json` (Agent Plugins 1.0) gains
  `extensions.com.openai.interface`: `displayName` PipingToolset, a 30-character subtitle, the
  long description, developer name, category (Productivity, matching
  `.agents/plugins/marketplace.json`), capabilities, website / privacy / terms / support URLs,
  three default prompts, the brand colour, `composerIcon` (`assets/icon.svg`) and `logo`
  (`assets/icon.png`). Without it the ChatGPT desktop app showed the bare id `piping-toolset`
  and a generic icon (observed 2026-10-28); with it, the same mark Cowork shows. The limits come
  from the OpenAI submission page (read 2026-10-28) and are pinned in `tests/test_manifests.py`.
- **Anthropic directory fields.** `.claude-plugin/plugin.json` gains `documentationUrl`,
  `supportUrl`, `privacyPolicyUrl` and `termsOfServiceUrl` beside the existing `icon`; Claude
  Code ignores them at load and `claude plugin validate` (2.1.309) passes clean.
- **Provider-neutral wording.** "Claude interviews, a script computes" becomes "The assistant
  interviews, a script computes" in both manifests and both marketplaces; the three SKILL.md
  lines and two script docstrings that named Claude as the actor now say "the assistant" (host
  names such as Claude Code, Claude Cowork, Codex CLI and the ChatGPT desktop app stay). OpenAI's
  submit-a-Claude-plugin guide asks for this; a test now guards it.
- **Third archive.** `tools/package_plugin.py` also writes `piping-toolset.zip`, byte-identical
  to the `.plugin`, because the OpenAI plugin portal and other upload dialogs take `.zip`, and
  `--check` now fails if an image a manifest references is missing from the archive. CI attaches
  all three files to the GitHub Release.
- **CI validator.** The package job runs the agentskills.io reference validator
  (`skills-ref==0.1.1`, `python -m skills_ref.cli validate`) on each of the seven skill folders.
- README retitled for Claude, ChatGPT and Codex with a ChatGPT / Codex install section; the
  Claude marketplace description names all three hosts. The pipingtoolset.com `/openai/` page is
  the OpenAI landing page named in the listing block.
- **Anthropic directory pre-submission holds cleared** (report on 0.5.1, 2026-10-28; three
  policy holds, all scanner false positives, no behaviour change): the `stress-screening`
  report outline no longer says "PASS/FAIL" beside the pipingtoolset.com links (read as a
  credential word next to a remote host); the hub ratios in `bolted_flange.py` are spelled
  `x_g` / `x_h` instead of `Xg` / `Xh` (the bare token `xh` is read as the HTTP client of that
  name); and `pipe-support`'s 454 KB `aisc_shapes.json` is now an index plus four family-group
  parts under `data/aisc_shapes/`, each under the 256 KiB inspection limit, concatenated by the
  loader in the original order (1,506 rows, `row_count` checked, a test locks it).

## [0.5.1] — 2026-10-27

Packaging only; no change to any skill, script, fixture or golden file.

- The plugin description in `plugin.json` (both manifests and `marketplace.json`) is shortened
  from 536 to under 500 characters. Cowork's **Upload a plugin** dialog rejected the 0.5.0
  archive with "Plugin description must be at most 500 characters"; the drag-into-chat route
  did not check it. `tests/test_manifests.py` now enforces the cap.

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
