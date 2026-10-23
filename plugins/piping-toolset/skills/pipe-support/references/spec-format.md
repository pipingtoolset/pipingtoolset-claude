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
| `columnSpacing` | Goalpost / trapeze |
| `arms` | `[{shape, elevation, projection, pipes, weldSize?, deflectionLimit? (default 240)}]` |
| `material` | `{Fy, Fu, E?}` |
| `weldSize`, `weldFEXX` | Default fillet (in), electrode (ksi) |
| `baseplate` | `{plateLength, plateWidth, plateThickness, plateFy, fc, pierLength, pierWidth, anchorType ("cast-in" \| "post-installed-adhesive" \| "post-installed-mechanical"), anchorCount, anchorDiameter, anchorEmbedment, anchorFuta, anchorSpacingLength, anchorSpacingWidth, anchorEdgeDistance, bondStrength (psi, ESR), ...}` |
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
