# AutoPIPE: the Bentley PCF Translator, the checks around it, and the crash playbook

The user runs the translator and AutoPIPE. This skill supplies the file, the settings and the
checks on both sides of the translation. **Fix geometry in a script, never in the translator:**
a loose tolerance or a hand-edited coordinate hides defects the analyst inherits, and a
tolerance of 1/8 in or more collapses real short parts.

## 1. Before translating: `ap_bendcheck.py`

```
python scripts/ap_bendcheck.py model.pcf          # before translating
python scripts/ap_bendcheck.py model.ntl          # after translating
```

It emulates the translator's bend-radius choice and AutoPIPE's two consistency checks, and was
calibrated to reproduce AutoPIPE's actual error lists on two revisions of one job exactly, in
both PCF and NTL mode:

- The translator writes a bend as `L` (R = 1.5 x NPS) when R = mean(T1, T2) / tan(theta/2) is
  within about 2.5 % of nominal; otherwise it writes R explicitly.
- **E726-15 (undefined bend)** when R tan(theta/2) exceeds the room to the nearest written point
  by more than about 0.01 in. Every written point obstructs: pipe ends, elbow ends, flange
  points, valve and reducer ends, tee points, supports.
- **W726-8 (kink)** when adjacent straight elements meet at more than about 1 deg, except where
  either element is a reducer or a valve.

Target before translating: networks = the number expected, near-miss pairs 0, E726-15 0,
W726-8 0. The usual causes are Revit elbow legs that differ by 1/16 to 1/8 in butted against a
reducer or another elbow (the tangent overshoots), and a two-component joint a few hundredths
off-axis after healing. `pcf_prep.py` has `normalize_elbows` (equal legs about the fixed
corner, only on elbows butted to another elbow or with unequal legs on a reducer) and
`straighten_inline` (project a two-component joint back onto the run, up to 0.25 in). Leave
`normalize_elbows` off unless the bend check fails: a blanket trim adds needless filler pipes.

## 2. Translator settings for a prepared file

| Tab | Setting | Use | Why |
|---|---|---|---|
| Model | Piping code and edition | the project's | The translator has written `CTL B31.1` into the NTL with another code selected: check General Model Options after import |
| Model | Material library | the one matching the code | The material prompt appears once per new material; a wrong default silently assigns another alloy (one job defaulted a stainless to duplex). Map it and tick "use for all" |
| Component | **Tolerance** | **0.01 in** | The preprocessor already closed every gap. Do not use 0.125 or more |
| Component | Ignore OD below | 0.5 in | |
| Component | Ignore continuation / remove overlapping | on / on | Harmless once there are no END-POSITION records and no overlaps |
| Component | **Add anchors at free ends** | **off** | The job's `boundary_rules` write explicit ANCH supports (cuts, coil connections, riser ties); blind-flanged stubs stay free |
| Component | Import two-point supports | on | |
| Component | Create RIGID section for flange | off | Flanges come in as flanges |
| Component | Prompt user for component mapping | off | |
| Coordinates | PCF +X (East) to AutoPIPE +X, +Y vertical | as is | The PCF is Z-up; the NTL confirms Y = elevation |
| Coordinates | Shift first point to origin | optional | Only for coordinates above 8 digits |
| Support gap defaults | guide, 0 gaps, mu 0 | leave | Applies only to SUPPORTs with no SKEY map; set friction in AutoPIPE |
| Attribute mapping | 1 operating pressure, 2 temperature, 3 material name, 4 wall thickness, 5 insulation thickness, 6 insulation density, 7 corrosion allowance, 8 rigid weight, 9 fluid density | keep exactly | `pcf_prep.py` writes `COMPONENT-ATTRIBUTE1..9` in this order |

Support SKEYs the translator maps through `PCFIn.map`: `HANG` V-stop with rod-hanger symbol,
`SKID` V-stop shoe or rest, `GUID` guide, `ANCH` anchor. Bridged in-line items are written as
`VALVE` records (rigid, full weight); a `MISC-COMPONENT` / `SP` stand-in comes through as a
rigid with half its weight as a point load.

## 3. After translating, before the NTL is opened: closures and cards

```
python scripts/ntl_closures.py model.ntl           # list loop-closure points and what sits on them
python scripts/fix_closures.py model.ntl fixed.ntl # move closures off flange and valve points
```

AutoPIPE 2025 and 2026 treat a loop-closure point (a point that starts a SEG and is later
re-entered by a RUN card) as a junction. When that point also carries a flange and the start of
a valve, AutoPIPE reports **E751-1 "Invalid tee at point N. SIF not calculated"** and then
crashes (`0xc0000005` at the same offset, Windows Application log event 1000). It is not
memory. `fix_closures.py` moves the closure to the adjacent plain pipe point; cards, geometry
and properties are unchanged. **Run it on every translated NTL.**

Then scan the NTL: no `SSTD` on a PIPE card where the line is Sch 10S or 40 (the schedule
defaults to STD without a SCH token in the description); card counts (VSTP, ANC, VALV, BEND,
FLA, TEE, RED) match the PCF; the first point's elevation is the one on the drawings.

## 4. Crash playbook

1. Ask for the **MSG and CHK files or a screen recording** first. The on-screen error (E751-1
   at a named point) is the fastest path to root cause. Do not bisect blindly.
2. Red herrings that cost hours on one job: anchor count, rack anchors, memory, B31J tee
   warnings. Read the error first.
3. A stray `.lck` file left by a crash is safe to delete.
4. A translator crash (`PCFin.exe 0xc0000409`, partial NTL) came from two BIM supports 5 in
   apart at an elbow tangent; the support placer now merges supports within 12 in on one run.

## 5. Expected warnings that are not defects

- **W2261-117** (B31J): header diameter or thickness not maintained within 2 Dm at a tee with a
  flange-and-valve 9 in away or a long-radius elbow 10 in away. Real geometry: leave the
  welding tee and list it for the analyst.
- **W2261-45 / -47 / -64** crotch radius and thickness on welding tees; **W2164-198** tee header
  and branch data updated; "NO NEW PIPE DATA GIVEN IMMEDIATELY AFTER RED" notes.

## 6. Model size

If a model is large or has many closed loops (pod headers), split by system from the start.
It halves the file and isolates problems. Cross-system bypasses become free ends: log them
`VFY`.
