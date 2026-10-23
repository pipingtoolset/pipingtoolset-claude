# Changelog

All notable changes to the `piping-toolset` plugin are recorded here. Dates are UTC.

Labels: **UNCONSERVATIVE-FIX** marks a correction where a previous release could
have produced a result less conservative than the code requires. Installed copies
keep a defect until the plugin is updated, so each such entry names the skill, the
affected inputs and the release that fixed it. GitHub Releases carry the same
label and are the recall channel.

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
  support); no `ITEM-CODE`/`ITEM-DESCRIPTION`/`WEIGHT`/`NAME` unless
  `"annotate": true`; branch legs written after the main run; `UNITS-WEIGHT LBS`.
  The validator now errors on bore/coordinate unit mismatch, inch bores under
  `UNITS-BORE MM`, `ELBOW` records and supports off a node. New
  `examples/minimal-proven.json`.
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
