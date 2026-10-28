# Spec format (`support_calc.py`)

Units: in, kip, ksi (f'c in psi; soil in ksf). Load blocks in CAESAR II mode may use
`"units": "lb-ft"` (CAESAR II English: lb and ft-lb, the default) or `"kip-in"`.

## Top level

| Key | Meaning |
|---|---|
| `design` | Assembly input, PiperSTR field names (below). Required, directly or via `preset`: `method`, `type`, `arms`, `material`, `weldSize`, `weldFEXX`, `columnHeight`. In CAESAR II mode, leave `arms[].pipes` empty, because the pipes come from `pipes` |
| `preset` | `"csa-type-1"` (t-post) or `"csa-type-2"` (two-tier). `design` keys override the preset; nested dicts (`baseplate`, `pier`) merge |
| `pipes` | CAESAR II mode: `[{tag, arm (0-based), offset (in from column CL), loads}]`. Omit it for factored mode |
| `T_factor` | Load factor on T. Default 1.0. LRFD must be ≥ 1.0 (2.3.4); ASD must be ≥ 0.75 (2.4.4) |
| `fabrication` | `{"armToColumn": "shop-weld" (default) \| "field-weld" \| "bolted"}`. Drives the field-work score. Any other value is a spec error |
| `optimize` | `{objectives: {weight, field, standard}, families: {arm: [...], column: [...]}, maxRatio, top, includeDesigns}` (all optional, defaults: weights 1, families W/HSS-SQ/PIPE/L/C for arms and W/HSS-SQ/PIPE for columns, maxRatio 1.0, top 5); `true` for defaults; `false` to skip. Works in both load modes |
| `assumed` | Strings copied into the report's assumptions |
| `code_values` | Optional. Values read from a code table, a report or an ESR, with their citation, for `design.material.Fy` and the other slots listed under [`code_values`](#code_values) below |
| `tag`, `project`, `calcBy`, `date` | Title block |

## `pipes[].loads` (CAESAR II restraint loads at the support node)

| Key | Meaning |
|---|---|
| `cases` | `{"SUS": [Fx,Fy,Fz(,Mx,My,Mz)], "OPE": [...], "WIN": [...], "EQ": [...], "HYD": [...]}`, as the restraint summary reports them (the load ON the restraint, global axes, signed) |
| `map` | Optional overrides, e.g. `{"W": "OPEW-OPE"}` (case names, `A-B` differences allowed, so case names themselves must not contain a hyphen). Defaults: D=SUS, T=OPE−SUS, W=WIN/WIND/W, Eh=EQ/SEIS/U/E, HYD=HYD/HYDRO |
| `SDS` | Design spectral acceleration. Gives Ev = 0.2 SDS D (12.4.2.2). Without it Ev = 0 and a note is raised |
| `L` | Optional live-load vector |
| `vertical_axis` | `"Y"` (CAESAR II default) or `"Z"` |
| `pipe_axis` | The global axis the pipe runs along at the support (default `"X"`). The third axis is "transverse" (along the arm) |

All pipes on one support must give the same case names.

**Occasional cases must be pure.** Give the wind or seismic load on its own (CAESAR II
`WIN1` / `U1` alone, or `OPE+WIN − OPE`), not the combined OPE+WIN case. Otherwise D and T
are counted twice.

## `design` (assembly input)

| Key | Meaning |
|---|---|
| `method` | `"LRFD"` or `"ASD"` |
| `type` | `t-post`, `multi-tier`, `cantilever`, `goalpost`, `trapeze` |
| `columnShape`, `columnHeight`, `columnK` | AISC label; height from top of base plate (in); K (default 2.1, fixed-free) |
| `columnSpacing` | Goalpost / trapeze: column centreline spacing (in). When given, each arm is also checked as a **header** spanning it (simple span, pipes as point loads at their `offset` from column A, Lb = span, K = 1). Without it the header is not checked and the engine warns. |
| `arms` | `[{shape, elevation, projection, pipes, weldSize?, deflectionLimit? (default 240), stemOrientation? ("down" \| "up", WT arms only; default "down" = flange up, pipes on the flange — stem in compression on a cantilever arm, in tension on a header)}]` |
| `material` | `{Fy, Fu, E?}` |
| `weldSize`, `weldFEXX` | Default fillet (in), electrode (ksi) |
| `baseplate` | `{plateLength, plateWidth, plateThickness, plateFy, fc, pierLength, pierWidth, anchorType ("cast-in" \| "post-installed-adhesive" \| "post-installed-mechanical"), anchorCount, anchorDiameter, anchorEmbedment, anchorFuta, anchorSpacingLength, anchorSpacingWidth, anchorEdgeDistance, bondStrength (psi, ESR), cracked? (default true — cracked concrete at service load), cac? (in, ESR critical edge distance for ACI 17.6.2.6 psi_cp,N; post-installed anchors in uncracked concrete only; omitted = Table 17.9.5 default 2·hef adhesive / 4·hef mechanical, with a warning), ...}` |
| `pier` | `{pierLength, pierWidth, pierHeight, fc, restraint ("anchored" \| "gravity"), footingLength, footingWidth, footingThickness, allowableBearing (ksf), frictionCoefficient, ...}` |

Factored mode: put `{tag, offset, vertical (+ down), transverse, longitudinal}` (kip) on
`arms[].pipes`. They are used exactly as entered, with no combinations applied.

## Outputs

- `--report` writes Markdown. `--json` writes the full result document: design, envelope
  per stage with the governing combination, findings, compliance matrix, optimizer and
  bolted alternative.
- Non-finite numbers are written as the strings `"Infinity"`, `"-Infinity"` and `"NaN"`.
  An infinite soil ratio means the resultant is outside the footing.

## Stand-alone modules

`pipe_support.bolts.bolt_group()`, `end_plate_no_prying()`, `pipe_support.detailing.fillet_detailing()`,
`groove_weld()` and `pipe_support.loads.combinations()` can be called directly from a short
Python script for a connection the parametric assemblies do not model (for example a bolted
clip to existing steel). Their docstrings list the inputs.

## `code_values`

An optional top-level object (the spelling `codeValues` is accepted too; give one of them): the route for a value the Engineering Data connector returned, or a value the user read, together with its citation. Shape (a template, not a code value):

```
"code_values": {
  "design.material.Fy": {"value": <number the user read>, "unit": "ksi",
                         "citation": {"standard": "...", "edition": "...", "table": "...", "row": "...", "column": "Fy"},
                         "source": "user"}
}
```

| Field | Meaning |
|---|---|
| name (the key) | The spec path it fills: `design.material.Fy`, `design.material.Fu`, `design.material.E`, `design.weldFEXX`, `design.baseplate.plateFy`, `design.baseplate.anchorFuta`, `design.baseplate.bondStrength`, `design.baseplate.cac`, `design.baseplate.anchorStressArea`, or `pipes.<n>.loads.SDS` (`n` the 0-based pipe position). Short spellings are accepted for the same slots (`Fy`, `Fu`, `bondStrength`, `cac`, `material.Fy`, `baseplate.bondStrength`); `SDS` or `loads.SDS` fills every pipe at once. Any other name is rejected |
| `value` | A number (or a string), the number as the lookup returned it or the user read it |
| `unit` | Required. The unit of `value`. The spec's units are ksi (`Fy`, `Fu`, `E`, `weldFEXX`, `plateFy`, `anchorFuta`), psi (`bondStrength`), in (`cac`), in^2 (`anchorStressArea`) and g for `SDS` (or `null`). The script converts a unit it can convert exactly and rejects any other mismatch |
| `citation` | `standard`, `edition`, `table` and `row` (all non-empty strings), and `column` when there is one, copied from the lookup's `citation` or from the pointer `get_pointer` returned |
| `source` | `connector` for a returned value, `user` for a value the user read |

- A key the spec leaves out is filled from `code_values[name].value`, and the value replaces the same key of a preset. A key the spec gives that disagrees stops the run, exit code 2, with `code_values.<name> conflicts with input <name>` on stderr and no verdict; a failed limit state also exits 2 but prints a verdict, so read the message. Fix the spec, do not edit one side to match.
- `SDS` needs CAESAR II mode (a `pipes` list).
- The result gains `code_value_provenance`, `{name: {unit, citation, source}}`, and `code_value_applied`, `{name: {value, unit}}`; the Markdown report gains a "Code-table values (user-supplied or connector-supplied, cited)" table. Every other key keeps its shape. The script makes no network calls.
