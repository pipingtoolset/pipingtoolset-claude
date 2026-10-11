## Load case set - B31.3 2022

| L | Combination | Description | Stress Type | Method | Friction | Hanger | Output |
|---|---|---|---|---|---|---|---|
| 1 | W | WEIGHT FOR HANGER LOADS | HGR | - | 1.0 | Rigid | Include |
| 2 | W+T1 | OPERATING FOR HANGER TRAVEL | HGR | - | 1.0 | Ignore | Include |
| 3 | WW+HP+H | HYDRO TEST CASE | HYD | - | 1.0 | - | Include |
| 4 | W+D1+T1+P1+H | OPERATING CASE CONDITION w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 5 | W+D1+T1+P1+H | OPERATING CASE CONDITION w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 6 | W+D2+T2+P2+H | DESIGN CASE CONDITION w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 7 | W+D2+T2+P2+H | DESIGN CASE CONDITION w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 8 | W+D1+T1+P1+H+F1 | OPERATING CASE CONDITION with PSV Pop Off (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 9 | W+D2+T2+P2+H+F2 | DESIGN CASE CONDITION with Design PSV Pop Off (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 10 | W+D1+T1+P1+H+U1 | OPERATING CASE CONDITION with Seismic +X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 11 | W+D1+T1+P1+H-U1 | OPERATING CASE CONDITION with Seismic -X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 12 | W+D1+T1+P1+H+U3 | OPERATING CASE CONDITION with Seismic +Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 13 | W+D1+T1+P1+H-U3 | OPERATING CASE CONDITION with Seismic -Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 14 | W+D1+T1+P1+H-U2 | OPERATING CASE CONDITION with Snow -Y (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 15 | W+D1+T1+P1+H+WIN1 | OPERATING CASE CONDITION with Wind +X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 16 | W+D1+T1+P1+H+WIN2 | OPERATING CASE CONDITION with Wind -X (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 17 | W+D1+T1+P1+H+WIN3 | OPERATING CASE CONDITION with Wind +Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 18 | W+D1+T1+P1+H+WIN4 | OPERATING CASE CONDITION with Wind -Z (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 19 | W+D1+T1+P1+H+F1 | OPERATING CASE CONDITION with PSV Pop Off (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 20 | W+D2+T2+P2+H+F2 | DESIGN CASE CONDITION with Design PSV Pop Off (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 21 | W+D1+T1+P1+H+U1 | OPERATING CASE CONDITION with Seismic +X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 22 | W+D1+T1+P1+H-U1 | OPERATING CASE CONDITION with Seismic -X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 23 | W+D1+T1+P1+H+U3 | OPERATING CASE CONDITION with Seismic +Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 24 | W+D1+T1+P1+H-U3 | OPERATING CASE CONDITION with Seismic -Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 25 | W+D1+T1+P1+H-U2 | OPERATING CASE CONDITION with Snow -Y (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 26 | W+D1+T1+P1+H+WIN1 | OPERATING CASE CONDITION with Wind +X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 27 | W+D1+T1+P1+H+WIN2 | OPERATING CASE CONDITION with Wind -X (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 28 | W+D1+T1+P1+H+WIN3 | OPERATING CASE CONDITION with Wind +Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 29 | W+D1+T1+P1+H+WIN4 | OPERATING CASE CONDITION with Wind -Z (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 30 | W+P1+H | SUSTAINED OPERATING CASE CONDITION (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 31 | W+P1+H | SUSTAINED OPERATING CASE CONDITION (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 32 | W+P2+H | SUSTAINED DESIGN CASE CONDITION (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 33 | W+P2+H | SUSTAINED DESIGN CASE CONDITION (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 34 | L4-L30 | EXPANSION OPERATING CASE CONDITION (w/ Friction) | EXP | Algebraic | - | - | Include |
| 35 | L5-L31 | EXPANSION OPERATING CASE CONDITION (w/o Friction) | EXP | Algebraic | - | - | Include |
| 36 | L6-L32 | EXPANSION DESIGN CASE CONDITION (w/ Friction) | EXP | Algebraic | - | - | Include |
| 37 | L7-L33 | EXPANSION DESIGN CASE CONDITION (w/o Friction) | EXP | Algebraic | - | - | Include |
| 38 | L8-L4 | Pure PSV Pop Off (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 39 | L9-L6 | Pure Design PSV Pop Off (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 40 | L10-L4 | Pure Seismic +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 41 | L11-L4 | Pure Seismic -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 42 | L12-L4 | Pure Seismic +Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 43 | L13-L4 | Pure Seismic -Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 44 | L14-L4 | Pure Snow -Y (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 45 | L15-L4 | Pure Wind +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 46 | L16-L4 | Pure Wind -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 47 | L17-L4 | Pure Wind +Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 48 | L18-L4 | Pure Wind -Z (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 49 | L19-L5 | Pure PSV Pop Off (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 50 | L20-L7 | Pure Design PSV Pop Off (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 51 | L21-L5 | Pure Seismic +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 52 | L22-L5 | Pure Seismic -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 53 | L23-L5 | Pure Seismic +Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 54 | L24-L5 | Pure Seismic -Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 55 | L25-L5 | Pure Snow -Y (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 56 | L26-L5 | Pure Wind +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 57 | L27-L5 | Pure Wind -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 58 | L28-L5 | Pure Wind +Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 59 | L29-L5 | Pure Wind -Z (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 60 | L30+L38 | PSV Pop Off Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 61 | L32+L39 | Design PSV Pop Off Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 62 | L30+L40 | Seismic +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 63 | L30+L41 | Seismic -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 64 | L30+L42 | Seismic +Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 65 | L30+L43 | Seismic -Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 66 | L30+L44 | Snow -Y Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 67 | L30+L45 | Wind +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 68 | L30+L46 | Wind -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 69 | L30+L47 | Wind +Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 70 | L30+L48 | Wind -Z Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 71 | L31+L49 | PSV Pop Off Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 72 | L33+L50 | Design PSV Pop Off Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 73 | L31+L51 | Seismic +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 74 | L31+L52 | Seismic -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 75 | L31+L53 | Seismic +Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 76 | L31+L54 | Seismic -Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 77 | L31+L55 | Snow -Y Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 78 | L31+L56 | Wind +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 79 | L31+L57 | Wind -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 80 | L31+L58 | Wind +Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 81 | L31+L59 | Wind -Z Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 82 | L4, L8, L10, L11, L12, L13, L14, L15, L16, L17, L18, L5, L19, L21, L22, L23, L24, L25, L26, L27, L28, L29 | Maximum Operating | OPE | Max | - | - | Include |
| 83 | L60, L61, L71, L72 | Maximum Psv Occasional | OCC | Max | - | - | Include |
| 84 | L62, L63, L64, L65, L73, L74, L75, L76 | Maximum Seismic Occasional | OCC | Max | - | - | Include |
| 85 | L66, L77 | Maximum Snow Occasional | OCC | Max | - | - | Include |
| 86 | L67, L68, L69, L70, L78, L79, L80, L81 | Maximum Wind Occasional | OCC | Max | - | - | Include |
| 87 | L83, L84, L85, L86 | Maximum Occasional | OCC | Max | - | - | Include |

### Report extraction matrix

| Purpose | Load Case(s) | Basis |
|---|---|---|
| Code stress - Sustained | 30, 31 | B31.3 sustained |
| Code stress - Expansion | 34, 35, 36, 37 | B31.3 expansion, S_A |
| Code stress - Occasional | 87 | B31.3 occasional envelope |
| Code stress - Hydrotest | 3 | test case |
| Support loads - Sustained | 30, 31 | hanger/restraint design |
| Support loads - Max Operating | 82 | governing operating reaction |
| Displacements - Sustained | 30 | vertical sag limit |
| Displacements - Max Operating | 82 | lateral movement |
| Flange / nozzle loads - Operating | 4, 5 | manufacturer or WRC allowable; both friction variants, take the governing |

### QC findings

- OK: wind and seismic are separate envelopes; they are never combined (B31.1 101.5.2; B31.3 302.3.6(a)).
- GAP: no vertical seismic component. ASCE 7 Ch. 13 requires concurrent Ev = 0.2*SDS*Wp. U2 is the only vertical uniform vector in CAESAR II.
- CONFLICT: U2 carries snow, so no vector remains for Ev. 'Uniform Load in G's' is a GLOBAL flag, so a snow vector entered in lb/ft while it is on is read as g's. Dedicate U2 to Ev and carry snow as weight, or run snow and seismic as separate sets.
- OK: Maximum Occasional envelope covers every occasional kind present.
- ALLOWABLE: B31.3 302.3.6(a) - sustained + occasional <= 1.33*Sh (flat); Chapter IX high-pressure piping uses 1.20 (K302.3.6(a)).
- ASD: no 0.6W / 0.7E reduction applied (strength level). This matches B31.1-2024 and the conservative reading of B31.3, and differs from the CAESAR II help topic on ASCE 7 load combinations. State the position and who approved it.

Total cases: 87
