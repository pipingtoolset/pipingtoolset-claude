## Load case set - B31.3 2022
Result status: manual check required - confirm ASSUMED inputs (confirm before issue: primary state = op (first declared) for the hanger design pair and the primary-labelled matrix rows; hanger design pair (W Rigid, W+T1 Ignore) runs at friction multiplier 1.0 (first declared friction variant)); fails: QC 4 vertical seismic and U2; not performed by this module: 12 items that need the model

### 1 Basis

**ASSUMED - confirm before issue:**
- primary state = op (first declared) for the hanger design pair and the primary-labelled matrix rows. Set primary_state to the maximum operating state to confirm it. Coverage does not depend on it: every state is enveloped and extracted; note: generator default
- hanger design pair (W Rigid, W+T1 Ignore) runs at friction multiplier 1.0 (first declared friction variant). Set hanger_friction to confirm it; note: generator default

No project basis record was given; code, edition and states are the spec's.

| L | Combination | Description | Stress Type | Method | Friction | Hanger | Output |
|---|---|---|---|---|---|---|---|
| 1 | W | WEIGHT FOR HANGER LOADS | HGR | - | 1.0 | Rigid | Include |
| 2 | W+T1 | OPERATING FOR HANGER TRAVEL | HGR | - | 1.0 | Ignore | Include |
| 3 | WW+HP+H | HYDRO TEST CASE (w/ Friction) | HYD | - | 1.0 | - | Include |
| 4 | WW+HP+H | HYDRO TEST CASE (w/o Friction) | HYD | - | 0.0 | - | Include |
| 5 | W+D1+T1+P1+H | OPERATING CASE CONDITION w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 6 | W+D1+T1+P1+H | OPERATING CASE CONDITION w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 7 | W+D2+T2+P2+H | DESIGN CASE CONDITION w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 8 | W+D2+T2+P2+H | DESIGN CASE CONDITION w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 9 | W+D1+T1+P1+H+F1 | OPERATING CASE CONDITION with PSV Pop Off (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 10 | W+D2+T2+P2+H+F2 | DESIGN CASE CONDITION with Design PSV Pop Off (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 11 | W+D1+T1+P1+H+U1 | OPERATING CASE CONDITION with Seismic +X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 12 | W+D1+T1+P1+H-U1 | OPERATING CASE CONDITION with Seismic -X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 13 | W+D1+T1+P1+H+U3 | OPERATING CASE CONDITION with Seismic +Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 14 | W+D1+T1+P1+H-U3 | OPERATING CASE CONDITION with Seismic -Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 15 | W+D1+T1+P1+H-U2 | OPERATING CASE CONDITION with Snow -Y (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 16 | W+D1+T1+P1+H+WIN1 | OPERATING CASE CONDITION with Wind +X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 17 | W+D1+T1+P1+H+WIN2 | OPERATING CASE CONDITION with Wind -X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 18 | W+D1+T1+P1+H+WIN3 | OPERATING CASE CONDITION with Wind +Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 19 | W+D1+T1+P1+H+WIN4 | OPERATING CASE CONDITION with Wind -Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 20 | W+D1+T1+P1+H+F1 | OPERATING CASE CONDITION with PSV Pop Off (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 21 | W+D2+T2+P2+H+F2 | DESIGN CASE CONDITION with Design PSV Pop Off (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 22 | W+D1+T1+P1+H+U1 | OPERATING CASE CONDITION with Seismic +X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 23 | W+D1+T1+P1+H-U1 | OPERATING CASE CONDITION with Seismic -X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 24 | W+D1+T1+P1+H+U3 | OPERATING CASE CONDITION with Seismic +Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 25 | W+D1+T1+P1+H-U3 | OPERATING CASE CONDITION with Seismic -Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 26 | W+D1+T1+P1+H-U2 | OPERATING CASE CONDITION with Snow -Y (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 27 | W+D1+T1+P1+H+WIN1 | OPERATING CASE CONDITION with Wind +X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 28 | W+D1+T1+P1+H+WIN2 | OPERATING CASE CONDITION with Wind -X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 29 | W+D1+T1+P1+H+WIN3 | OPERATING CASE CONDITION with Wind +Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 30 | W+D1+T1+P1+H+WIN4 | OPERATING CASE CONDITION with Wind -Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 31 | W+P1+H | SUSTAINED OPERATING CASE CONDITION (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 32 | W+P1+H | SUSTAINED OPERATING CASE CONDITION (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 33 | W+P2+H | SUSTAINED DESIGN CASE CONDITION (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 34 | W+P2+H | SUSTAINED DESIGN CASE CONDITION (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 35 | L5-L31 | EXPANSION OPERATING CASE CONDITION (w/ Friction) | EXP | Algebraic | - | - | Include |
| 36 | L6-L32 | EXPANSION OPERATING CASE CONDITION (w/o Friction) | EXP | Algebraic | - | - | Include |
| 37 | L7-L33 | EXPANSION DESIGN CASE CONDITION (w/ Friction) | EXP | Algebraic | - | - | Include |
| 38 | L8-L34 | EXPANSION DESIGN CASE CONDITION (w/o Friction) | EXP | Algebraic | - | - | Include |
| 39 | L9-L5 | Pure PSV Pop Off (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 40 | L10-L7 | Pure Design PSV Pop Off (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 41 | L11-L5 | Pure Seismic +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 42 | L12-L5 | Pure Seismic -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 43 | L13-L5 | Pure Seismic +Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 44 | L14-L5 | Pure Seismic -Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 45 | L15-L5 | Pure Snow -Y (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 46 | L16-L5 | Pure Wind +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 47 | L17-L5 | Pure Wind -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 48 | L18-L5 | Pure Wind +Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 49 | L19-L5 | Pure Wind -Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 50 | L20-L6 | Pure PSV Pop Off (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 51 | L21-L8 | Pure Design PSV Pop Off (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 52 | L22-L6 | Pure Seismic +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 53 | L23-L6 | Pure Seismic -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 54 | L24-L6 | Pure Seismic +Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 55 | L25-L6 | Pure Seismic -Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 56 | L26-L6 | Pure Snow -Y (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 57 | L27-L6 | Pure Wind +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 58 | L28-L6 | Pure Wind -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 59 | L29-L6 | Pure Wind +Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 60 | L30-L6 | Pure Wind -Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 61 | L31+L39 | PSV Pop Off Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 62 | L33+L40 | Design PSV Pop Off Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 63 | L31+L41 | Seismic +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 64 | L31+L42 | Seismic -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 65 | L31+L43 | Seismic +Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 66 | L31+L44 | Seismic -Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 67 | L31+L45 | Snow -Y Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 68 | L31+L46 | Wind +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 69 | L31+L47 | Wind -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 70 | L31+L48 | Wind +Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 71 | L31+L49 | Wind -Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 72 | L32+L50 | PSV Pop Off Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 73 | L34+L51 | Design PSV Pop Off Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 74 | L32+L52 | Seismic +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 75 | L32+L53 | Seismic -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 76 | L32+L54 | Seismic +Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 77 | L32+L55 | Seismic -Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 78 | L32+L56 | Snow -Y Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 79 | L32+L57 | Wind +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 80 | L32+L58 | Wind -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 81 | L32+L59 | Wind +Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 82 | L32+L60 | Wind -Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 83 | L5, L9, L11, L12, L13, L14, L15, L16, L17, L18, L19, L7, L10, L6, L20, L22, L23, L24, L25, L26, L27, L28, L29, L30, L8, L21 | Maximum Operating | OPE | Max | - | - | Include |
| 84 | L61, L62, L72, L73 | Maximum Psv Occasional | OCC | Max | - | - | Include |
| 85 | L63, L64, L65, L66, L74, L75, L76, L77 | Maximum Seismic Occasional | OCC | Max | - | - | Include |
| 86 | L67, L78 | Maximum Snow Occasional | OCC | Max | - | - | Include |
| 87 | L68, L69, L70, L71, L79, L80, L81, L82 | Maximum Wind Occasional | OCC | Max | - | - | Include |
| 88 | L84, L85, L86, L87 | Maximum Occasional | OCC | Max | - | - | Include |

### Report extraction matrix

| Purpose | Load Case(s) | Basis |
|---|---|---|
| Code stress - Sustained | 31, 32, 33, 34 | B31.3 sustained; every state x friction |
| Code stress - Expansion | 35, 36, 37, 38 | B31.3 expansion, S_A; every state x friction |
| Code stress - Occasional | 88 | B31.3 occasional envelope |
| Code stress - Hydrotest | 3, 4 | test case; every friction variant |
| Hanger design - Rigid load / Ignore travel | 1, 2 | CAESAR II hanger design pair; primary state op, friction 1.0 |
| Support loads - Sustained | 31, 32, 33, 34 | hanger/restraint design; every state x friction |
| Support loads - Hydrotest | 3, 4 | restraint load under test weight; every friction variant |
| Support loads - Max Operating | 83 | governing operating reaction; every OPE and OPE+OCC case, all states x friction |
| Displacements - Sustained | 31, 32, 33, 34 | vertical sag limit; every state x friction |
| Displacements - Max Operating | 83 | lateral movement; every OPE and OPE+OCC case, all states x friction |
| Flange / nozzle loads - Operating | 5, 6, 7, 8 | manufacturer or WRC allowable; every state x friction, take the governing; primary state op listed first |

### QC findings

- ASSUMED: primary state = op (first declared) for the hanger design pair and the primary-labelled matrix rows. Set primary_state to the maximum operating state to confirm it. Coverage does not depend on it: every state is enveloped and extracted.
- ASSUMED: hanger design pair (W Rigid, W+T1 Ignore) runs at friction multiplier 1.0 (first declared friction variant). Set hanger_friction to confirm it.
- OK: wind and seismic are separate envelopes; they are never combined (B31.1 101.5.2; B31.3 302.3.6(a)).
- GAP: no vertical seismic component. ASCE 7 Ch. 13 requires concurrent Ev = 0.2*SDS*Wp. U2 is the only vertical uniform vector in CAESAR II.
- CONFLICT: U2 carries snow, so no vector remains for Ev. 'Uniform Load in G's' is a GLOBAL flag, so a snow vector entered in lb/ft while it is on is read as g's. Dedicate U2 to Ev and carry snow as weight, or run snow and seismic as separate sets.
- OK: Maximum Occasional envelope covers every occasional kind present.
- ALLOWABLE: B31.3 302.3.6(a) - sustained + occasional <= 1.33*Sh (flat); Chapter IX high-pressure piping uses 1.20 (K302.3.6(a)).
- ASD: no 0.6W / 0.7E reduction applied (strength level). This matches B31.1-2024 and the conservative reading of B31.3, and differs from the CAESAR II help topic on ASCE 7 load combinations. State the position and who accepted it.
- QC: resolved case set complete - 88 cases match the 88 the spec declares (2 states x 2 friction variants, 11 occasionals); 169 coverage, reference, envelope and matrix checks, 0 misses.

Total cases: 88
