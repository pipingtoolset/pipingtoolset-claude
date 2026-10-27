# Detailed flange analysis - every equation in engine order

Module `aux.app2-flange-integral`, a port of the pipingtoolset.com calculation engine's flange module. Clause path: ASME BPVC VIII-2 Part 4.16 (4.16.6 bolt loads, 4.16.7 moments, stresses, acceptance and rigidity, Tables 4.16.4 to 4.16.11). The retired VIII-1 Mandatory Appendix 2 carried the same method; the 2025 edition of VIII-1 sends the reader to 4.16. B31.3 304.5.1(b) permits either route with B31.3 allowables.

**Verify on the printed page.** The bodies of Eq. 4.16.4 to 4.16.19 and of Tables 4.16.4, 4.16.5 and 4.16.8 to 4.16.12 could not be verified here; confirm them on the printed page. The equations below are what the tool runs, and they reproduce a commercial pipe-stress program's flange report to the digits it prints. They are not offered as a transcription of the Code. The user checks the sequence against the printed 4.16.6 and 4.16.7 before a sealed issue.

## Symbols

| Symbol | Meaning | Units |
|---|---|---|
| P, Peq | Design pressure; equivalent pressure including external loads | psi |
| Fax, Mext | External axial force (tension positive); external bending moment (ft-lbf; `Mext_in_lbf` for in-lbf) | lbf, ft-lbf |
| A, B, C, t | Flange OD, bore, bolt circle, thickness | in |
| g0, g1, h | Hub small-end thickness, large-end thickness, length | in |
| G, N, b0, b | Gasket reaction diameter, contact width, basic and effective seating width | in |
| m, y | Gasket factor; gasket seating stress | -, psi |
| Sa, Sb | Bolt allowable at ambient (seating) and at design temperature | psi |
| Sf, SfAmbient | Flange allowable at design temperature and at ambient | psi |
| Sn, SnAmbient | Attached pipe or neck allowable at design temperature and at ambient | psi |
| n, aRoot, Ab, Am | Bolt count; root area of one bolt; actual and required total bolt area | -, in^2 |
| H, Hp, Wm1, Wm2, Wg | Hydrostatic end force; gasket compression load; operating bolt load; seating minimum bolt load; seating design bolt load | lbf |
| HD, HT, HG | Hydrostatic end force on the bore area; the remainder; gasket load (operating) | lbf |
| hD, hT, hG | Moment arms of HD, HT, HG | in |
| Mo, Mg | Operating and gasket seating moments | in-lbf |
| SH, SR, ST | Longitudinal hub, radial and tangential stresses | psi |
| K, T, Z, Y, U | Terms involving K = A/B | - |
| F, V, f, e, d, L | Hub factors and derived hub terms | - |
| J, KI | Rigidity index; rigidity factor | -, - |

## Equations in the order the engine runs them

**0. External loads as an equivalent pressure.** The moment is a magnitude.

```
momentTerm = 16 |M_in_lbf| / (pi G^3)        M_in_lbf = 12 Mext
forceTerm  = 4 Fax / (pi G^2)
Peq        = P + momentTerm + forceTerm       (must be > 0)
```

This is the same expression as the screen. VIII-2 4.16.13 defines FA as the external tensile net-section force and neglects compression (FA = 0), whereas the engine keeps F signed, so a negative `Fax` lowers Peq and draws a warning. To follow the Code, pass `Fax` = max(F, 0) unless the owner agrees to credit compression, and state the choice on the sheet. This is a documentation point; the engine's parity behaviour is unchanged. It is the common practice but it is **not** the Code's own external-moment construction, which uses the flange ring properties. Both P-only and Peq results are visible in the output so the effect of the external loads is not buried.

**1. Gasket.**

```
b0 = N/2
b  = b0 if b0 <= 0.25 in, else 0.5 sqrt(b0)         (or the supplied b)
```

The 0.25 in is the 6 mm limit of Eq. 4.16.1 versus 4.16.2 and 4.16.3. For a ring joint, or any facing other than the flat rule, derive b with `connections.flange-derive` or read it from the effective-width table and supply `b`. G is an input.

**2. Bolt loads.**

```
H   = (pi/4) G^2 Peq                  pi/4, not the rounded 0.785 (0.05 percent difference)
Hp  = 2 b pi G m Peq
Wm1 = H + Hp                          operating
Wm2 = pi b G y                        seating minimum
Am  = max(Wm1 / Sb, Wm2 / Sa)
Ab  = n aRoot
Wg  = ((Am + Ab)/2) Sa                seating design load
```

`Ab >= Am` is required. Note that Wg grows with Ab: oversized bolting raises the seating moment.

**3. Terms involving K (Table 4.16.4).** K = A/B, K must exceed 1.

```
T = (K^2 (1 + 8.55246 log10 K) - 1) / ((1.0472 + 1.9448 K^2)(K - 1))
Z = (K^2 + 1) / (K^2 - 1)
Y = (1/(K - 1)) (0.66845 + 5.7169 K^2 log10 K / (K^2 - 1))
U = (K^2 (1 + 8.55246 log10 K) - 1) / (1.36136 (K^2 - 1)(K - 1))
```

**4. Hub terms (integral only).**

```
ho = sqrt(B g0)               (loose: sqrt(B t))
Xg = g1/g0     Xh = h/ho
F, V, f  from the hub factor method (below)
e = F/ho
d = (U/V) ho g0^2
L = (t e + 1)/T + t^3/d       (loose: L = 1)
```

**5. Moment arms (Table 4.16.6).**

```
hG = (C - G)/2
integral:  R = (C - B)/2 - g1     hD = R + g1/2     hT = (R + g1 + hG)/2
loose:     hD = (C - B)/2         hT = (hD + hG)/2
```

A non-positive R draws a warning: check the bolt circle against the hub.

**6. Forces.**

```
HD = (pi/4) B^2 Peq        HT = H - HD        HG = Wm1 - H  (= Hp)
```

**7. Bolt-spacing correction (Table 4.16.11) and moments.**

```
Bs      = pi C / n
limit   = 2 d_bolt + t          (d_bolt = boltDia, or 2 sqrt(aRoot/pi) when omitted)
Bsc     = max(1, sqrt(Bs / limit))        (1 when applyBoltSpacing is false)
Mo_bare = HD hD + HT hT + HG hG           Mo = Bsc Mo_bare
Mg_bare = Wg hG                           Mg = Bsc Mg_bare
```

The output field `boltSpacingMax` is the 2 d_bolt + t threshold above which the correction starts. Confirm the maximum-spacing and correction expressions in Table 4.16.11 on the printed page; the tool does not check a separate maximum spacing. The correction is on by default (conservative); VIII-2 applies it when specified by the user or designated agent, so state on the sheet whether it was required. **Bsc scales the stress moments only; the rigidity moment is the uncorrected one.** Applying Bsc to both puts J high by the same factor as Bsc.

**8. Stresses (Table 4.16.8).** Operating case: Mo, Sf, Sn. Seating case: Mg, SfAmbient, SnAmbient.

```
SH = f M / (L g1^2 B)                       (0 for a loose ring)
SR = (1.33 t e + 1) M / (L t^2 B)           (0 for a loose ring)
ST = Y M / (t^2 B) - Z SR
```

**9. Acceptance (Table 4.16.9).** Five checks per case; the case utilization is the largest ratio.

```
SH <= min(1.5 Sf, 2.5 Sn)      (hub welded to pipe: the 2-8(a) cap)
SR <= Sf     ST <= Sf     (SH + SR)/2 <= Sf     (SH + ST)/2 <= Sf
```

If Sn is not supplied the cap is 1.5 Sf alone and the tool says the 2.5 Sn cap is unchecked. The 1.5 and 2.5 multipliers are named constants in the script. Sn must come from the same table line basis as Sf (B31.3 304.5.1(b): the product S x E x W).

**10. Rigidity (Table 4.16.10).** Uses the uncorrected moments. E at design temperature for the operating case, at ambient for seating.

```
integral:  J = 52.14 V M_bare / (L E g0^2 KI ho)
loose:     J = 109.4 M_bare / (E t^3 KI ln K)
KI = 0.3 integral, 0.2 loose, unless the user specifies otherwise
```

J is the ratio of the flange's rotation under the moment to the rotation the rigidity criterion allows. J <= 1 is required. A flange can meet every stress limit and still have J above 1: it is too flexible to hold the gasket load, so leakage and seating are at risk. Do not ignore J.

**11. Pass rule.** `pass` requires Ab >= Am, the worst case utilization <= 1 and both J <= 1. `governing` names the case with the larger utilization.

## Integral versus loose

| | Integral (weld-neck, hubbed) | Loose (ring, no hub) |
|---|---|---|
| Hub inputs | g0, g1, h required (h, g1 > 0; g1 >= g0) | Ignored |
| Stresses | SH, SR, ST | ST only (SH and SR report 0) |
| L | (t e + 1)/T + t^3/d | 1 |
| Moment arm hD | R + g1/2 | (C - B)/2 |
| Rigidity | 52.14 form, uses V, L, ho | 109.4 form, uses ln K |
| ho | sqrt(B g0) | sqrt(B t) |

Running a loose flange as integral, or the reverse, changes the result materially; the flange type is on the basis interview. Not modelled: welded slip-on, loose with hub, reverse, split loose, nut-stop and non-circular flanges.

## Hub-factor provenance

F, V and f come from one of two sources, chosen per run and stated on the sheet.

1. **`series` (default).** A closed-form constant-chain elastic solution evaluated in the script. It is a **reconstruction**, assembled from published open-source implementations and cross-checked term by term against a published reproduction. It matches a commercial pipe-stress program's flange report to four digits. It is **not transcribed from licensed Code text**, and a term-by-term check against Table 4.16.5 could not be made here.
2. **Overrides.** `F_override`, `V_override`, `f_override` bypass the computed factor with a value the user reads from the Table 4.16.5 equations (or the retired figures). With all three given nothing is evaluated. This is the route for a sealed calc: it removes the reconstruction from the chain. A warning names the overridden factors; carry it into the findings. f has a floor of 1.

The Table 4.16.5 curve-fit option is not shipped, because its coefficients are tabulated code data. `hubFactorMethod` accepts only `series`; any other value exits 2 with a message to use the overrides. The Table 4.16.4 constants in the K terms (8.55246, 1.0472, 1.9448, 0.66845, 5.7169, 1.36136) are equation constants; confirm them on the printed page. The overrides do not change any engine result when absent.

## Known limits

- External load treatment is the pressure-equivalent method (equation 0 above), not the Code's Moe.
- Peq also enters the gasket-seating case, because Wg = (Am + Ab)/2 x Sa and Am includes Wm1/Sb, which depends on Peq. This is conservative for the seating bolt load, and the seating-case result moves with the external loads even though seating takes place before pressurisation.
- The VIII-2 4.16.7.2 Step 9(b) shear check (0.8 Sno or Sng on lap-joint and weld shear) and the Code's own Moe term (4.16.16, Table 4.16.7) are not computed.
- Self-energizing gaskets (N = 0 in 4.16.13) cannot be run: the tool requires N > 0.
- G, N, b are gasket-geometry inputs; the tool does not check the facing against Table 4.16.3.
- Temperature effects (creep relaxation, thermal gradients) are not modelled; B16.5 2.5.2 advises caution above 200 C (Class 150) and 400 C (other classes).
- Hydrotest: run the detailed module again with the test pressure and the test-condition allowables the user cites, if the owner requires the test case.
