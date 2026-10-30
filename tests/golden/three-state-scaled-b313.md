## Load case set - B31.3 2022

| L | Combination | Description | Stress Type | Method | Friction | Hanger | Output |
|---|---|---|---|---|---|---|---|
| 1 | W | WEIGHT FOR HANGER LOADS | HGR | - | 0.0 | Rigid | Include |
| 2 | W+T2 | OPERATING FOR HANGER TRAVEL | HGR | - | 0.0 | Ignore | Include |
| 3 | WW+HP+H | HYDRO TEST CASE (w/ Friction) | HYD | - | 1.0 | - | Include |
| 4 | WW+HP+H | HYDRO TEST CASE (half Friction) | HYD | - | 0.5 | - | Include |
| 5 | WW+HP+H | HYDRO TEST CASE (w/o Friction) | HYD | - | 0.0 | - | Include |
| 6 | W+D1+T1+P1+H | NORMAL OPERATING w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 7 | W+D1+T1+P1+H | NORMAL OPERATING half Friction | OPE | - | 0.5 | As Designed | Include |
| 8 | W+D1+T1+P1+H | NORMAL OPERATING w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 9 | W+D2+T2+P2+H | MAXIMUM OPERATING w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 10 | W+D2+T2+P2+H | MAXIMUM OPERATING half Friction | OPE | - | 0.5 | As Designed | Include |
| 11 | W+D2+T2+P2+H | MAXIMUM OPERATING w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 12 | W+T3+P3+H | COLD UPSET w/ Friction | OPE | - | 1.0 | As Designed | Include |
| 13 | W+T3+P3+H | COLD UPSET half Friction | OPE | - | 0.5 | As Designed | Include |
| 14 | W+T3+P3+H | COLD UPSET w/o Friction | OPE | - | 0.0 | As Designed | Include |
| 15 | W+D1+T1+P1+H+0.7U1 | NORMAL OPERATING with 0.7 Seismic +X REDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 16 | W+D1+T1+P1+H-0.7U1 | NORMAL OPERATING with 0.7 Seismic -X REDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 17 | W+D1+T1+P1+H-U2 | NORMAL OPERATING with Seismic -Y (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 18 | W+D2+T2+P2+H+0.6WIN1 | MAXIMUM OPERATING with 0.6 Wind +X REDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 19 | W+D2+T2+P2+H+0.6WIN2 | MAXIMUM OPERATING with 0.6 Wind -X REDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 20 | W+T3+P3+H+F1 | COLD UPSET with PSV Pop Off at upset (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 21 | W+D1+T1+P1+H+0.7U1 | NORMAL OPERATING with 0.7 Seismic +X REDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 22 | W+D1+T1+P1+H-0.7U1 | NORMAL OPERATING with 0.7 Seismic -X REDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 23 | W+D1+T1+P1+H-U2 | NORMAL OPERATING with Seismic -Y (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 24 | W+D2+T2+P2+H+0.6WIN1 | MAXIMUM OPERATING with 0.6 Wind +X REDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 25 | W+D2+T2+P2+H+0.6WIN2 | MAXIMUM OPERATING with 0.6 Wind -X REDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 26 | W+T3+P3+H+F1 | COLD UPSET with PSV Pop Off at upset (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 27 | W+D1+T1+P1+H+0.7U1 | NORMAL OPERATING with 0.7 Seismic +X REDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 28 | W+D1+T1+P1+H-0.7U1 | NORMAL OPERATING with 0.7 Seismic -X REDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 29 | W+D1+T1+P1+H-U2 | NORMAL OPERATING with Seismic -Y (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 30 | W+D2+T2+P2+H+0.6WIN1 | MAXIMUM OPERATING with 0.6 Wind +X REDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 31 | W+D2+T2+P2+H+0.6WIN2 | MAXIMUM OPERATING with 0.6 Wind -X REDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 32 | W+T3+P3+H+F1 | COLD UPSET with PSV Pop Off at upset (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 33 | W+D1+T1+P1+H+U1 | NORMAL OPERATING with Seismic +X UNREDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 34 | W+D1+T1+P1+H-U1 | NORMAL OPERATING with Seismic -X UNREDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 35 | W+D2+T2+P2+H+WIN1 | MAXIMUM OPERATING with Wind +X UNREDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 36 | W+D2+T2+P2+H+WIN2 | MAXIMUM OPERATING with Wind -X UNREDUCED (w/ Friction) | OPE | - | 1.0 | As Designed | Include |
| 37 | W+D1+T1+P1+H+U1 | NORMAL OPERATING with Seismic +X UNREDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 38 | W+D1+T1+P1+H-U1 | NORMAL OPERATING with Seismic -X UNREDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 39 | W+D2+T2+P2+H+WIN1 | MAXIMUM OPERATING with Wind +X UNREDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 40 | W+D2+T2+P2+H+WIN2 | MAXIMUM OPERATING with Wind -X UNREDUCED (half Friction) | OPE | - | 0.5 | As Designed | Include |
| 41 | W+D1+T1+P1+H+U1 | NORMAL OPERATING with Seismic +X UNREDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 42 | W+D1+T1+P1+H-U1 | NORMAL OPERATING with Seismic -X UNREDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 43 | W+D2+T2+P2+H+WIN1 | MAXIMUM OPERATING with Wind +X UNREDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 44 | W+D2+T2+P2+H+WIN2 | MAXIMUM OPERATING with Wind -X UNREDUCED (w/o Friction) | OPE | - | 0.0 | As Designed | Include |
| 45 | W+P1+H | SUSTAINED NORMAL OPERATING (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 46 | W+P1+H | SUSTAINED NORMAL OPERATING (half Friction) | SUS | - | 0.5 | As Designed | Include |
| 47 | W+P1+H | SUSTAINED NORMAL OPERATING (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 48 | W+P2+H | SUSTAINED MAXIMUM OPERATING (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 49 | W+P2+H | SUSTAINED MAXIMUM OPERATING (half Friction) | SUS | - | 0.5 | As Designed | Include |
| 50 | W+P2+H | SUSTAINED MAXIMUM OPERATING (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 51 | W+P3+H | SUSTAINED COLD UPSET (w/ Friction) | SUS | - | 1.0 | As Designed | Include |
| 52 | W+P3+H | SUSTAINED COLD UPSET (half Friction) | SUS | - | 0.5 | As Designed | Include |
| 53 | W+P3+H | SUSTAINED COLD UPSET (w/o Friction) | SUS | - | 0.0 | As Designed | Include |
| 54 | L6-L45 | EXPANSION NORMAL OPERATING (w/ Friction) | EXP | Algebraic | - | - | Include |
| 55 | L7-L46 | EXPANSION NORMAL OPERATING (half Friction) | EXP | Algebraic | - | - | Include |
| 56 | L8-L47 | EXPANSION NORMAL OPERATING (w/o Friction) | EXP | Algebraic | - | - | Include |
| 57 | L9-L48 | EXPANSION MAXIMUM OPERATING (w/ Friction) | EXP | Algebraic | - | - | Include |
| 58 | L10-L49 | EXPANSION MAXIMUM OPERATING (half Friction) | EXP | Algebraic | - | - | Include |
| 59 | L11-L50 | EXPANSION MAXIMUM OPERATING (w/o Friction) | EXP | Algebraic | - | - | Include |
| 60 | L12-L51 | EXPANSION COLD UPSET (w/ Friction) | EXP | Algebraic | - | - | Include |
| 61 | L13-L52 | EXPANSION COLD UPSET (half Friction) | EXP | Algebraic | - | - | Include |
| 62 | L14-L53 | EXPANSION COLD UPSET (w/o Friction) | EXP | Algebraic | - | - | Include |
| 63 | L6-L9 | EXPANSION RANGE NORMAL OPERATING to MAXIMUM OPERATING (w/ Friction) | EXP | Algebraic | - | - | Include |
| 64 | L7-L10 | EXPANSION RANGE NORMAL OPERATING to MAXIMUM OPERATING (half Friction) | EXP | Algebraic | - | - | Include |
| 65 | L8-L11 | EXPANSION RANGE NORMAL OPERATING to MAXIMUM OPERATING (w/o Friction) | EXP | Algebraic | - | - | Include |
| 66 | L6-L12 | EXPANSION RANGE NORMAL OPERATING to COLD UPSET (w/ Friction) | EXP | Algebraic | - | - | Include |
| 67 | L7-L13 | EXPANSION RANGE NORMAL OPERATING to COLD UPSET (half Friction) | EXP | Algebraic | - | - | Include |
| 68 | L8-L14 | EXPANSION RANGE NORMAL OPERATING to COLD UPSET (w/o Friction) | EXP | Algebraic | - | - | Include |
| 69 | L9-L12 | EXPANSION RANGE MAXIMUM OPERATING to COLD UPSET (w/ Friction) | EXP | Algebraic | - | - | Include |
| 70 | L10-L13 | EXPANSION RANGE MAXIMUM OPERATING to COLD UPSET (half Friction) | EXP | Algebraic | - | - | Include |
| 71 | L11-L14 | EXPANSION RANGE MAXIMUM OPERATING to COLD UPSET (w/o Friction) | EXP | Algebraic | - | - | Include |
| 72 | L15-L6 | Pure Seismic +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 73 | L16-L6 | Pure Seismic -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 74 | L17-L6 | Pure Seismic -Y (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 75 | L18-L9 | Pure Wind +X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 76 | L19-L9 | Pure Wind -X (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 77 | L20-L12 | Pure PSV Pop Off at upset (w/ Friction) | OCC | Algebraic | - | - | Suppress |
| 78 | L21-L7 | Pure Seismic +X (half Friction) | OCC | Algebraic | - | - | Suppress |
| 79 | L22-L7 | Pure Seismic -X (half Friction) | OCC | Algebraic | - | - | Suppress |
| 80 | L23-L7 | Pure Seismic -Y (half Friction) | OCC | Algebraic | - | - | Suppress |
| 81 | L24-L10 | Pure Wind +X (half Friction) | OCC | Algebraic | - | - | Suppress |
| 82 | L25-L10 | Pure Wind -X (half Friction) | OCC | Algebraic | - | - | Suppress |
| 83 | L26-L13 | Pure PSV Pop Off at upset (half Friction) | OCC | Algebraic | - | - | Suppress |
| 84 | L27-L8 | Pure Seismic +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 85 | L28-L8 | Pure Seismic -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 86 | L29-L8 | Pure Seismic -Y (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 87 | L30-L11 | Pure Wind +X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 88 | L31-L11 | Pure Wind -X (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 89 | L32-L14 | Pure PSV Pop Off at upset (w/o Friction) | OCC | Algebraic | - | - | Suppress |
| 90 | L45+L72 | Seismic +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 91 | L45+L73 | Seismic -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 92 | L45+L74 | Seismic -Y Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 93 | L48+L75 | Wind +X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 94 | L48+L76 | Wind -X Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 95 | L51+L77 | PSV Pop Off at upset Code Stress Case (w/ Friction) | OCC | Scalar | - | - | Include |
| 96 | L46+L78 | Seismic +X Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 97 | L46+L79 | Seismic -X Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 98 | L46+L80 | Seismic -Y Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 99 | L49+L81 | Wind +X Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 100 | L49+L82 | Wind -X Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 101 | L52+L83 | PSV Pop Off at upset Code Stress Case (half Friction) | OCC | Scalar | - | - | Include |
| 102 | L47+L84 | Seismic +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 103 | L47+L85 | Seismic -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 104 | L47+L86 | Seismic -Y Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 105 | L50+L87 | Wind +X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 106 | L50+L88 | Wind -X Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 107 | L53+L89 | PSV Pop Off at upset Code Stress Case (w/o Friction) | OCC | Scalar | - | - | Include |
| 108 | L6, L33, L34, L17, L9, L35, L36, L12, L20, L7, L37, L38, L23, L10, L39, L40, L13, L26, L8, L41, L42, L29, L11, L43, L44, L14, L32 | Maximum Operating | OPE | Max | - | - | Include |
| 109 | L95, L101, L107 | Maximum Psv Occasional | OCC | Max | - | - | Include |
| 110 | L90, L91, L92, L96, L97, L98, L102, L103, L104 | Maximum Seismic Occasional | OCC | Max | - | - | Include |
| 111 | L93, L94, L99, L100, L105, L106 | Maximum Wind Occasional | OCC | Max | - | - | Include |
| 112 | L109, L110, L111 | Maximum Occasional | OCC | Max | - | - | Include |

### Report extraction matrix

| Purpose | Load Case(s) | Basis |
|---|---|---|
| Code stress - Sustained | 45, 46, 47, 48, 49, 50, 51, 52, 53 | B31.3 sustained; every state x friction |
| Code stress - Expansion | 54, 55, 56, 57, 58, 59, 60, 61, 62 | B31.3 expansion, S_A; every state x friction |
| Code stress - Expansion range between states | 63, 64, 65, 66, 67, 68, 69, 70, 71 | inter-state range, every state pair x friction; take the greatest S_E |
| Code stress - Occasional | 112 | B31.3 occasional envelope; ASD-scaled terms are REDUCED here (stress path only) |
| Code stress - Hydrotest | 3, 4, 5 | test case; every friction variant |
| Hanger design - Rigid load / Ignore travel | 1, 2 | CAESAR II hanger design pair; primary state max, friction 0.0 |
| Support loads - Sustained | 45, 46, 47, 48, 49, 50, 51, 52, 53 | hanger/restraint design; every state x friction |
| Support loads - Hydrotest | 3, 4, 5 | restraint load under test weight; every friction variant |
| Support loads - Max Operating | 108 | governing operating reaction; every OPE and OPE+OCC case, all states x friction; scaled occasionals enter UNREDUCED |
| Support loads / displacements - Occasional UNREDUCED | 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44 | ASD-scaled occasionals at full magnitude; never read the REDUCED OPE+OCC cases for loads or movements |
| Displacements - Sustained | 45, 46, 47, 48, 49, 50, 51, 52, 53 | vertical sag limit; every state x friction |
| Displacements - Max Operating | 108 | lateral movement; every OPE and OPE+OCC case, all states x friction; scaled occasionals enter UNREDUCED |
| Flange / nozzle loads - Operating | 9, 10, 11, 6, 7, 8, 12, 13, 14 | manufacturer or WRC allowable; every state x friction, take the governing; primary state max listed first |

### QC findings

- OK: wind and seismic are separate envelopes; they are never combined (B31.1 101.5.2; B31.3 302.3.6(a)).
- OK: Maximum Occasional envelope covers every occasional kind present.
- ALLOWABLE: B31.3 302.3.6(a) - sustained + occasional <= 1.33*Sh (flat); Chapter IX high-pressure piping uses 1.20 (K302.3.6(a)).
- ASD: 0.6W / 0.7E reduction applied for stress. B31.3 is silent on the factor; cite the owner or EOR direction. Unreduced companions (12 OPE+OCC-UNRED cases) are generated for every scaled occasional x friction and feed Maximum Operating, support loads and displacements; the REDUCED cases feed the code-stress occasional path only.
- QC: resolved case set complete - 112 cases match the 112 the spec declares (3 states x 3 friction variants, 6 occasionals, 4 scaled with unreduced companions, 3 inter-state pairs); 249 coverage, reference, envelope and matrix checks, 0 misses.

Total cases: 112
