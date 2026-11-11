# CAESAR II: APCF settings, the mapping files, the neutral file, and reading the OUT

Proven on CAESAR II v15 with an 883-element, 311-support central-plant model imported from two
PCFs: 0 errors, informational B31J warnings only. `caesar-import.md` is the builder's contract
for a drawing-built PCF; this file is the import and repair side for any PCF.

## 1. APCF (Tools > External Interfaces > PCF)

| Setting | Use | Why |
|---|---|---|
| Start node / increment | **cannot be set per file** in practice: every file numbers 10, 20, 30 ... | Two lines imported into one job collide. Renumber afterwards with `scripts/fix_cii.py`, never by hand |
| Condense rigids | **off** | On merges flanges, valves and couplings and loses their weights |
| Condense tees / elbows | on | Keeps the node count sane |
| Diameter limit | job dependent (2 in is common) | Drops the small bore the PCF still carries |
| Material | the job material | The importer writes "MAT No Material specified ... using Default" once per component; on a clean import that is the only content of the `.wrn` file |
| Schedule | from `ITEM-DESCRIPTION`; set the default to what the fabrication model says | One job's 18 in pipe was STD (0.375), not Sch 40 |
| Attribute map (`PCF_MAP.xml`) | Super PCF template | DESIGN-TEMPERATURE to T1, DESIGN-PRESSURE to P1, INSULATION-THICKNESS, PIPELINE-REFERENCE to the line number. The stress-iso template maps different names |

Per-line T/P only land from **per-line PCFs**. A combined PCF carries none, so import the
per-line files, or import the combined file and let `fix_cii.py` set T1/P1 by line.

**Job names:** no periods (a name like `CHR_11.03` left a 0-byte database and a stray job).
Work from a local folder, not a synced cloud drive.

**Fluid:** the neutral file carries a **density in lb/in^3**, not a specific gravity.
`SPECIFIC-GRAVITY 1.0` in a PCF imported as 1.0 lb/in^3 (27.7 x water) and the centre-of-gravity
report showed 3.7 million lb of fluid in a 100,000 lb system. Do not write `SPECIFIC-GRAVITY` in
the PCF; set the density in the fixer (water 62.4/1728 = 0.03611) or in Classic Input as
`1.0SG`. Read the centre-of-gravity report before any run.

## 2. PCF_RES_MAP.TXT (CAESAR II System folder)

Keywords: `<SUPPORT_NAME> Name`, `<SUPPORT_TAG> Name`, `<SUPPORT_GUID> UCI`. The `NAME` in the
PCF `SUPPORT` record is matched by **substring, longest entry first**, so list longer names
first. Functions: `ANC VERT NS EW A B C GUI LIM VHGR CHGR` with `+` / `-`, `MU=`, `GAP=`.

```
PTS-BASE 1
  +VERT   MU=0.3
PTS-BHGR 1
  +VERT
PTS-BTRP 1
  +VERT   MU=0.3
PTS-RSR 2
  +VERT   MU=0.3
  GUI     MU=0.3
PTS-HGR 1
  +VERT
PTS-ANC 1
  ANC
```

`+ANC` is **wrong**: it imports as restraint code 6 (a nameless one-directional type), not
code 1 (ANC). Use `ANC` with no sign. `fix_cii.py` converts code 6 to 1 if the map was wrong.
Without a map entry the importer falls back to SKEY + SUPPORT-DIRECTION: `ANCH` gives an
anchor, `SKID` + `UP` gives +Y, and friction and guides are lost.

Name supports `<prefix>-<TYPE>_<line><nnn>` (for example `PTS-BTRP_CHW028`; the prefix is the
job's `support_prefix`). The prefix maps the restraint; the tag survives into CAESAR II
(`Tag = PTS-BTRP_CHW028` in the OUT) and ties the restraint back to the support list and the
BIM hanger. The friction values above are placeholders: the analyst sets friction.

## 3. PCF_SIF_MAP (SKEY to CAESAR II SIF type)

| SKEY | CAESAR II SIF type | B31J sketch family |
|---|---|---|
| `TEBW` | 3 welding tee | welding tee |
| `TERF` | 2 unreinforced fabricated tee | fabricated branch (fishmouths, stub-ins) |
| reinforced pad | 1 | reinforced fabricated tee |
| weldolet / `OLBW` | 4 | branch welded-on fitting |

Read the map on the user's machine: sites edit it, and a reducing tee with the wrong SKEY
silently gets the wrong SIF. Grooved couplings are rigid couplings per the manufacturer's data,
which gives no SIF or stiffness, and B31J Table 1-1 has no grooved sketch: model them as short
rigids with the vendor weight, i = 1.0, and list the assumption for the analyst. B31.3 Table
326.1.1-1 lists the AWWA standard for grooved joints; cite it from the user's copy.

## 4. The neutral file (`.CII`, format 5.0, CAESAR II 15)

Sections are headed `#$ NAME`. Reals are `%13.6E` fields, two leading spaces, six per line.
`scripts/cii.py` parses it; `fix_cii.py` edits it; `verify_cii.py` proves the edit.

| Section | Layout the scripts rely on |
|---|---|
| CONTROL | counts: elements, bends, rigids, restraints |
| ELEMENTS | 15 lines per element: 9 real lines (53 values: from, to, dx, dy, dz, OD, wall, insulation, _, T1 ... P1 at index 18, insulation density 30, **fluid density 31**, ... 9999.99 markers at 46-47), 2 name lines, one `-1 -1` line, 3 pointer lines (15 ints: bend, rigid, _, restraint, ..., SIF at 9, _, reducer at 12) |
| BEND | 3 lines (14 values) per bend: radius, _, _, mid node, _, near node, _, far node ... wall. Mid and near nodes are TO-1 and TO-2 of the bend element |
| RIGID | 1 line per rigid: weight, _ |
| RESTRANT | 24 lines per record, 6 slots x (values, direction, tag, guid). Values: node, **type** (1 ANC, 8 GUI, 14 +Y as the importer writes it, 17 +Y in the NTXT), stiffness 1e12, gap, mu, cnode |
| SIF&TEES | 84 values per element record (2 slots x 42): node, SIF type, ... |
| REDUCERS | 2 lines (10 values): D2, t2, ... |
| COORDS | count, then `%15d` node + 3 reals in **ft**, one line per piece start |
| UNITS | conversion constants and labels |

CAESAR II frame is X, **Y up**, Z. PCF frame is X, Y, **Z up**. Map CAESAR II (x, y, z) to PCF
(x, -z, y): that is what `fix_cii.py` uses to match nodes to PCF points (0.009 in residual on
the proven job).

Node coordinates: seed from COORDS, then propagate element deltas both ways until every node
is placed. A run whose first node is not in COORDS and is only reached from a later
loop-closure element is normal ("back-defined").

Renumbering: element order is the importer's walk order, so renumbering in element order makes
node numbers rise along each run (the standing complaint about scrambled numbering). Keep every
band below 9999: AutoPIPE renames CAESAR II nodes at 10000 and above alphanumerically.

Workflow: APCF import, export the neutral file (Tools > External Interfaces > CAESAR II Neutral
File), `fix_cii.py`, `verify_cii.py` PASS, convert back under a new job name, error checker,
export the NTXT and OUT for the audit. Extend the fixer (and its checks) before touching a
section it does not yet handle: it refuses a file whose DISPLMNT, FORCMNT, EQUIPMNT, FLANGES,
EXPJT, UNIFORM, WIND or OFFSETS section is not empty.

## 5. Reading the OUT and the NTXT

- `WARNINGS REPORT (FROM ERROR CHECKER)`: search `WARNING` and `ERROR`; 0 errors is the target.
- `MATERIAL ALLOWABLE VALUES`: SC, SH1-9 by element. Flat across temperature means the
  material database value: VERIFY against the user's copy of the allowable-stress table for the grade and
  form (the `pipe-stress-check` skill), never reproduced here.
- `INTERSECTION SIF, SSI, FLEX & STIFF VALUES`: per tee, type, D, T, d, t, SIFs and
  flexibilities. A large unreinforced fabricated branch runs a double-digit out-of-plane SIF:
  expect it, and list it for the analyst.
- `CENTER OF GRAVITY REPORT`: pipe, insulation and **fluid** weights. Hand-check the fluid
  (bore area x length x density) before trusting any run.
- `BILL OF MATERIALS`: pipe length by size, bends by radius and angle. Compare with the PCF.
- NTXT `REST` lines: node, type (0 = ANC, 17 = +Y, 7 = GUI), mu; `ELMT` / `EL03`: T1, P1.

## 6. Warning catalogue (B31J, CAESAR II 15)

| Code | Seen | Meaning | Action |
|---|---|---|---|
| 293E | 1 per tee | No surface node specified; CAESAR II generates one | None |
| 283E | per welding tee | Crotch data not given; B31J reduction not applied | Conservative; optionally enter the B16.9 crotch data |
| 286E / 287E / 288E | per reducer | r2, L2, alpha not given; B31J defaults | Optional; cone angles of 7 to 10 deg are mild |
| 282E | per reducer or tee | Geometry outside the B31J range | Reducers written small-to-large trigger it; reverse them or accept |
| MAT (`.wrn`) | per component | No material in the PCF; default used | None if the default is the job material |
