# CAESAR II PCF import: the contract

The PCF import is run by `PCFInterface.exe` / `C2Isogen.exe`, driven by four editable map files
in the CAESAR II `System` folder (under the program-data directory, `Intergraph CAS\CAESAR II\<version>\System`).
Read them on the target machine before generating. They are the contract the PCF must satisfy,
and sites customise them.

## The import-proven format

The builder's default output mirrors Isogen "SISO" PCFs that import cleanly into CAESAR II:

```
ISOGEN-FILES ISOGEN.FLS
UNITS-BORE MM                 <- bore in mm too: NPS 4 -> 101.6000
UNITS-CO-ORDS MM
UNITS-WEIGHT LBS
UNITS-BOLT-DIA MM
UNITS-BOLT-LENGTH MM
PIPELINE-REFERENCE <line>
    PROJECT-IDENTIFIER
    AREA
PIPE                          END-POINT x2, no ITEM-CODE / ITEM-DESCRIPTION
BEND                          END-POINT x2, CENTRE-POINT (corner), SKEY BEBW, ANGLE 9000, BEND-RADIUS <mm>
TEE                           END-POINT x2, CENTRE-POINT, BRANCH1-POINT, SKEY TEBW
FLANGE / VALVE / REDUCER-CONCENTRIC   END-POINT x2, SKEY
SUPPORT                       CO-ORDS (on a node), SKEY ANCH|SKID|GUID|SPRG, SUPPORT-DIRECTION
```

Main run first, then each branch leg. CRLF line endings.

**The first release failed to import** because it wrote `UNITS-BORE INCH` with bores like `6.0000`
under mm coordinates, free text in `ATTRIBUTE1`, `ELBOW` records without `BEND-RADIUS`, a `TEE`
without `CENTRE-POINT`, and supports in the middle of pipe elements. `validate_pcf.py` now flags
each of these.

Other importer behaviour below was observed on **one CAESAR II v15 installation** (PCF interface
build 15.0.0.405, default maps). Treat it as a strong starting point, not a guarantee for other
releases.

| Map file | What it controls |
|---|---|
| `PCF_RES_MAP.TXT` | **Supports → restraints**, where a site uses it. It can match restraints on the support's `NAME` attribute (prefix-style, longest key first) in plant-axis vocabulary (`ANC`, `VERT`, `NS`, `EW`, local `A`/`B`/`C`, `GUI`, `LIM`, hanger types). The import-proven files carry **no** `NAME`: the restraint comes from the support SKEY (`ANCH`, `SKID`, `GUID`, `SPRG`) plus `SUPPORT-DIRECTION`. That is the builder's default |
| `PCF_SIF_MAP.TXT` | **SKEY → SIF type.** Decides whether a tee imports as a welding tee, an unreinforced fabricated tee, a weldolet, and so on. Check the tee and olet SKEYs you use against it. A reducing tee with the wrong SKEY silently gets the wrong SIF |
| `PCF_MAP.xml` | **Pipeline attributes → job data.** In the default map: `DESIGN-TEMPERATURE` → T1, `ALT-DESIGN-TEMPERATURE` → T2, `OPERATING-TEMPERATURE` → T3, `DESIGN-PRESSURE` → P1, `OPERATING-PRESSURE` → P3, `TEST-PRESSURE` → hydro pressure, `INSULATION-THICKNESS`, `SPECIFIC-GRAVITY`, and `PIPELINE-REFERENCE` → line number. `MATERIAL` and `WALLTHK` keys exist but are unmapped by default; the site can wire them to a PCF attribute name. If the line list is available, put these in `pipeline.attributes` and the design data imports with the geometry. Unit strings must be ones `PCF_Units_Map.txt` declares |
| `PCF_Units_Map.txt` | Conversion filters for **attribute** values (pressure, temperature, thickness, weight, density) written with a bracketed unit such as `[BARg]` or `[C]`. Use only strings that appear in it |
| `PCF_MAT_MAP.TXT` | Material name → CAESAR II material number (for example `A106-B` → 106). Used only if a material attribute is mapped |

Consequences for the spec:

- Give each support a proven SKEY and direction. If the site relies on `PCF_RES_MAP.TXT`
  `NAME` matching instead, set `annotate` and name supports `TYPE_TAG` (for example
  `PG-2A_PS-0235`), then test the import.
- Because restraints use `VERT`/`NS`/`EW`, the importer resolves the vertical axis itself. Still
  **check the orientation in the CAESAR II graphics after import**, and rebuild with the other
  `axes` value if it is wrong.
- Put design data in `pipeline.attributes` **only** under names the site's `PCF_MAP.xml` reads.
  Anything else is ignored.
- Editing the map files needs write access to the program-data folder. Supply additions as a
  paste-in block for the user, append only, and never overwrite existing entries.

## Why the builder writes a "safe" record set

On the v15 build above, `PCFINTERFACE.EXE` failed fast (exception `0xc0000409` in
`ucrtbase.dll`) on PCFs containing record types outside the set below, six times in a row. The
import dialog closed silently, the warnings file was empty, and nothing was logged. The only
trace was an Application event-log crash entry (Event ID 1000, faulting application
`PCFINTERFACE.EXE`). Check there when an import "finishes" with nothing to show.

Other releases may accept more. The safe set is **conservative**, not a statement about every
version. To test a richer file on your build, use `"full_vocabulary": true`, import it, and check
the event log.

So by default `build_pcf.py` writes only the **import-proven** records

`PIPE, PIPE-FIXED, BEND, TEE, FLANGE, VALVE, VALVE-ANGLE, REDUCER-CONCENTRIC, SUPPORT`

plus two **accepted but not yet proven** ones, `GASKET` and `OLET`, which the validator warns
about until an import confirms them. Everything else is mapped onto that set, with no geometric
loss:

| Native record | Written as | Identity kept in |
|---|---|---|
| `FLANGE-BLIND` | `FLANGE` | SKEY `FLBL` + build report |
| `CAP` | `PIPE` | build report |
| `ELBOW` | `BEND` (SKEY `BEBW`, with `BEND-RADIUS`) | SKEY |
| `MISC-COMPONENT` (instruments, specials) | `VALVE` (rigid) | build report |
| `COUPLING` | `PIPE` | build report |
| `REDUCER-ECCENTRIC` + `FLAT-DIRECTION` | `REDUCER-CONCENTRIC` | the offset end points + build report (state the flat side in `desc`) |

Every mapping is listed in the build report under *Record substitutions*. Set
`"full_vocabulary": true` only for a reader known to accept the native records.

**AutoPIPE's PCF reader is far more tolerant.** A file that imports into AutoPIPE proves the
geometry, not CAESAR II compatibility.

## What a PCF cannot carry

Set these in CAESAR II after import, and say so at handover:

- Material identity and allowable stress basis
- Design and operating temperatures and pressures, and every load case (unless mapped through
  `PCF_MAP.xml`)
- Insulation thickness and density, fluid density
- Restraint stiffness, gaps and friction coefficients beyond what `PCF_RES_MAP.TXT` assigns
- Spring hanger design data
- Wind and seismic parameters
- Corrosion allowance and mill tolerance
