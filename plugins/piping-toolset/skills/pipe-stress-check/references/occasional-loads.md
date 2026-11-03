# Occasional loads: wind and seismic from ASCE 7 and B31E, and the ASD question

Most "no OCC case" rejections are really "nobody knew how to build it". Build it in this order.
Every coefficient below (Kz, Kzt, Kd, Ke, G, Cf, ap, Rp, CAR, Rpo, R, Omega0, SDS) is read by the
user from the load standard's own tables and figures and cited; none is embedded here. The
`load-case-builder` skill turns the resulting loads into the case set.

## 1. Pick the load-standard edition and say where it came from

The jurisdiction's adopted building code sets the ASCE 7 edition. The piping codes' own
reference lists are the fallback (B31.1-2024 and B31.3-2024 both list ASCE/SEI 7-16, and B31.1
adds that the authority having jurisdiction may require another; B31.3-2016 listed 7-10). Put
both facts in the basis. It is a separate edition question from the piping code.

## 2. Decide the ASD question explicitly

ASCE 7 wind speeds and seismic E are strength level; ASCE 7's own allowable-stress combinations
apply 0.6 to wind and 0.7 to earthquake. The piping codes differ:

- **B31.1-2024, 101.5.2 (wind) and 101.5.3 (earthquake), both new in 2024:** loads may be per
  ASCE 7 "except the Allowable Stress Design reduction factor shall not be applied." Using 0.6W
  or 0.7E under B31.1-2024 is a finding.
- **B31.3, 301.5.2 and 301.5.3:** loads "may be as described in ASCE 7" and nothing is said about
  the factor. Default to **no reduction**, mark it ASSUMED, and apply 0.6 / 0.7 only on written
  direction of the owner specification or the engineer of record, citing that document.
- If stress is reduced, keep **unreduced** companion cases for support loads and displacements.
  The difference is 1/0.6 = 1.67 on wind force; never leave it unstated.

## 3. Wind on the pipe

```
7-10:  qz = 0.00256 Kz Kzt Kd V^2              w = qz G Cf D_eff
7-16:  qz = 0.00256 Kz Kzt Kd Ke V^2   (26.10-1)   w = qz G Cf D_eff
7-22:  qz = 0.00256 Kz Kzt Ke V^2      (26.10-1)   w = qz Kd G Cf D_eff   (from F = qz Kd G Cf Af, 29.4-1)

qz psf, V mph (Risk Category map), G = 0.85 rigid, D_eff = OD over insulation or jacket in ft,
Cf = round-section force coefficient (7-16 / 7-22 Fig. 29.4-1; 7-10 Fig. 29.5-1) by h/D, D sqrt(qz) and roughness
```

**Kd moved out of qz in 7-22.** A calc ported between editions without moving Kd drops it or
counts it twice. Ke did not exist before 7-16. Evaluate qz at the line's elevation, or split the
model into elevation bands, and say which. Wind area is the insulated OD, not the bare pipe.
Apply +/-X and +/-Z as separate cases. For pipe racks, ASCE 7-22 section 29.4 points
open-frame petrochemical structures to the ASCE petrochemical wind report (2011 edition) for
tributary area and a minimum force coefficient; cite the report edition you used.

## 4. Seismic on the pipe

First decide whether a seismic calculation is required at all:

- ASCE 7 13.1.4 exemptions (a numbered list in 7-10 and 7-16; Table 13.1-1 in 7-22).
- The piping exceptions: **7-10 section 13.6.8.3; 7-16 and 7-22 section 13.6.7.3**. They combine
  rod length, rod diameter, weight per support and a pipe-size limit that depends on the Seismic
  Design Category and Ip. All conditions must hold together; the 12 in rod rule alone is not an
  exemption.
- **"Deemed to comply" is not "exempt."** ASME B31 piping with its supports is deemed to meet
  Chapter 13 (7-16 and 7-22 section 13.6.7.1; 7-10 section 13.6.8.1), but it still needs seismic
  forces and displacements. In 7-16 and 7-22, **section 13.6.8 is the trapeze clause**, so citing
  13.6.8 for piping against those editions is a clause error.

If required, the horizontal coefficient Fp/Wp:

```
7-10 / 7-16:  Fp = 0.4 ap SDS Wp (1 + 2 z/h) / (Rp/Ip)                (13.3-1)
7-22:         Fp = 0.4 SDS Ip Wp (Hf/R_mu) (CAR/Rpo)                   (13.3-1)
              Hf = 1 + a1 (z/h) + a2 (z/h)^10, or 1 + 2.5 (z/h) if Ta is unknown; Hf = 1.0 at grade
              R_mu = [1.1 R / (Ie Omega0)]^0.5 >= 1.3, using the SUPPORTING structure's R and Omega0; 1.0 at grade
all editions: 0.3 SDS Ip Wp <= Fp <= 1.6 SDS Ip Wp
```

ap/Rp (7-10, 7-16) and CAR/Rpo (7-22) come from Table 13.6-1 by component row: ask for the row
and the value, and cite it. Apply the horizontal force in each orthogonal direction as a
separate case with the concurrent vertical 0.2 SDS Wp (7-22 section 13.3.1.6 through 12.4.2.2).
Where the pipe spans between independently moving structures (building to rack, rack to
vessel), add seismic relative displacement as a displacement case (7-22 section 13.3.2; rack
drift from the structure's Cd, delta_xe and Ie), in the expansion check, not the occasional one.

## 5. B31E as the alternate path

B31.1 101.5.3 names ASME B31E as an alternate seismic method. B31E-2008 as amended by
B31Ea-2010: Table 1 triages each line into no analysis, design by rule or design by analysis
from criticality, size and acceleration. Design by analysis checks

```
S = P D / (4 t) + 0.75 i (M_sustained + M_seismic) / Z  <=  min[2.4 S, 1.5 Sy, 60 ksi]      (B31E 3.4)
```

plus a separate seismic anchor motion check. The 2010 addenda changed the design-by-rule span
coefficient and Table 2, and set ap = 2.5, Rp <= 3.5 when forces come from ASCE 7 13.3.1; those
parameters were written against ASCE 7-05, so feeding B31E with a 7-22 Fp needs a statement
that nobody has calibrated the two together.

## 6. Bracing

Where lateral restraint is sway bracing, MSS SP-127 governs the brace: design forces, maximum
brace spacing, brace angle at least 30 deg from vertical (45 deg preferred), slenderness, and
the rod-hung exemption. Its tables use an ASCE 7-10, LRFD basis and are not converted to ASD;
flag that when the project is on a later edition.

## 7. Checks before issue

- ASCE 7 edition undeclared, or clause numbers from one edition cited against another (13.6.8
  against 13.6.7; Kd inside or outside qz).
- ASD 0.6W / 0.7E applied under B31.1-2024, or under B31.3 without a cited basis.
- Seismic "exempt" claimed on the 12 in rod rule alone, or "deemed to comply" read as exempt.
- Wind area on bare OD when the line is insulated.
- Wind and seismic combined into one occasional case.
- Relief thrust, water hammer and slug flow not run or not dismissed with a reason.
