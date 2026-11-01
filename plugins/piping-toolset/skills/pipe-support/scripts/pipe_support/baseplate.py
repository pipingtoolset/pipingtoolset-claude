"""Base plate and anchorage - AISC Design Guide 1 + AISC 360-22 J8 + ACI CODE-318-25 Ch. 17.

ACI CODE-318-25 is the default; ACI 318-19 stays selectable (``aciEdition: "318-19"``) so
legacy projects reproduce. Edition differences carried here:
  - phi from Table 21.2.1: concrete failure in tension 0.65 nonredundant / 0.75 redundant
    (breakout, pullout, side-face blowout, bond), concrete failure in shear 0.75. 318-19
    keeps the old set (concrete 0.70, bond 0.65).
  - psi_a, Table 17.5.4.1 (318-25 only), on every concrete failure mode.
  - psi_cm,N, 17.6.2.7 (318-25 only), an opt-in breakout credit, never used in pryout.
  - 17.8.3 concrete (5/3 power) and 17.8.4 steel (power 2) interactions replace the 318-19
    trilinear 0.2 / 1.2 rule.
Provisions present in both editions (futa cap, grout pad 0.80, psi_ed,V, side-face blowout
ca2 and group terms, adhesive pryout, ANc <= n*ANco, psi_c,N 1.4 for post-installed anchors,
bond group terms) apply under either edition.

Exact port of the Piping Toolset PiperSTR engine's ``baseplate-anchorage`` TypeScript module. Units: in,
kip, ksi, psi for f'c. Input/output dict keys are the TypeScript names unchanged.

Data boundary (as the TS engine): proprietary anchor qualification values (bond stress
tau_cr / tau_uncr, manufacturer Np, product kc, the ACI 355.2/355.4 Anchor Category) are
NEVER embedded; they arrive as inputs from the user's ESR / ICC evaluation report. The
generic cast-in defaults are ACI's own values and the output flags them.

Public API: ``base_plate_anchorage(input)``, ``thread_stress_area(d)``, ``anchor_phi``,
``psi_a``, ``aci_label``.
"""

from __future__ import annotations

import math
import re

from .common import InputError, result, round_half_up, verdict
from .jsmath import div, finite, jmax, jmin, js_num, nn, pow_, sqrt, truthy

MODULE = "structural.baseplate-anchorage"

# ASD conversion: service-level demand vs an LRFD-derived capacity. ACI is a strength-design
# code and prints no ASD conversion; the 1.5 divisor is this project's basis per the owner
# P.E. ruling of 2026-10-26 (not an ACI provision).
_ASD_ANCHOR_FACTOR = 1.5

# UNC threads per inch, keyed by String(d) exactly as the TS record.
_UNC_THREADS_PER_INCH = {
    "0.375": 16, "0.5": 13, "0.625": 11, "0.75": 10, "0.875": 9,
    "1": 8, "1.125": 7, "1.25": 7, "1.5": 6, "1.75": 5, "2": 4.5,
}


def aci_label(edition):
    """Report label for an edition - every clause string is built from this."""
    return "ACI 318-19" if edition == "318-19" else "ACI CODE-318-25"


def anchor_phi(edition, ductile, redundancy):
    """Strength-reduction factors for the anchorage.

    318-25: Table 21.2.1 - concrete failure in tension 0.65 nonredundant / 0.75 redundant
    (breakout, pullout, side-face blowout, bond); concrete failure in shear 0.75; steel
    0.75 / 0.65 ductile and 0.65 / 0.60 nonductile. 318-19: the set used through 2026-10
    (concrete 0.70, bond 0.65), with the nonductile steel factors in both editions.
    """
    steelTension = 0.75 if ductile else 0.65
    steelShear = 0.65 if ductile else 0.60
    if edition == "318-19":
        return {"steelTension": steelTension, "steelShear": steelShear, "concreteTension": 0.70,
                "concreteShear": 0.70, "pullout": 0.70, "bond": 0.65, "source": "ACI 318-19 17.5.3"}
    ct = 0.75 if redundancy == "redundant" else 0.65
    return {"steelTension": steelTension, "steelShear": steelShear, "concreteTension": ct,
            "concreteShear": 0.75, "pullout": ct, "bond": ct,
            "source": f"ACI CODE-318-25 Table 21.2.1 ({redundancy})"}


def psi_a(edition, castIn, category, supplementary, mode):
    """Anchor strength modification factor psi_a, ACI CODE-318-25 Table 17.5.4.1 (1.0 under 318-19).

                         no supplementary reinf.   supplementary reinf.
                         tension     shear         tension     shear
      cast-in            0.95        0.95          1.00        1.00
      post-inst. Cat 1   0.85        0.95          1.00        1.00
      post-inst. Cat 2   0.75        0.95          0.85        1.00
      post-inst. Cat 3   0.60        0.95          0.75        1.00
    """
    if edition == "318-19":
        return 1.0
    if castIn or mode == "shear":
        return 1.0 if supplementary else 0.95
    noSupp = {1: 0.85, 2: 0.75, 3: 0.60}
    supp = {1: 1.0, 2: 0.85, 3: 0.75}
    return supp[category] if supplementary else noSupp[category]


def power_interaction(tensionRatio, shearRatio, power):
    """sum (ratio_i)^p - the 17.8.3 (p = 5/3) and 17.8.4 (p = 2) interaction."""
    return pow_(jmax(0, tensionRatio), power) + pow_(jmax(0, shearRatio), power)


def _design(nominal, method, phi, omega):
    """aisc-section.ts design(): LRFD -> phi*Rn, otherwise (ASD) Rn/omega."""
    return phi * nominal if method == "LRFD" else div(nominal, omega)


def thread_stress_area(d):
    """UNC thread tensile stress area, in^2 - Ase = 0.7854*(d - 0.9743/n)^2."""
    n = _UNC_THREADS_PER_INCH.get(js_num(d))
    if not n:
        return 0.7854 * pow_(d - 0.9743 / 8, 2)  # fall back to 8-UN
    return 0.7854 * pow_(d - 0.9743 / n, 2)


def _row(label, demand, capacity, clause, userSupplied=False):
    d = abs(demand)
    if d <= 1e-12:
        return {"label": label, "demand": 0, "capacity": capacity, "ratio": 0, "clause": clause,
                "status": "na", "userSupplied": userSupplied}
    ratio = d / capacity if capacity > 0 else math.inf
    return {"label": label, "demand": d, "capacity": capacity, "ratio": ratio, "clause": clause,
            "status": verdict(ratio <= 1.0), "userSupplied": userSupplied}


_REQUIRED = (
    "method", "columnDepth", "columnWidth", "plateLength", "plateWidth", "plateThickness",
    "plateFy", "fc", "pierLength", "pierWidth", "anchorType", "anchorCount", "anchorDiameter",
    "anchorEmbedment", "anchorFuta", "anchorSpacingLength", "anchorSpacingWidth",
    "anchorEdgeDistance",
)

_CONCRETE_TENSION = ("Concrete breakout (tension)", "Anchor pullout", "Concrete side-face blowout",
                     "Adhesive bond strength")
_CONCRETE_SHEAR = ("Concrete breakout (shear)", "Concrete pryout (shear)")


def base_plate_anchorage(input):
    """Full base-plate and anchorage check (see baseplate-anchorage.ts for the model)."""
    if not isinstance(input, dict):
        raise InputError("input must be a dict")
    for k in _REQUIRED:
        if input.get(k) is None:
            raise InputError(f"missing required input '{k}'")
    method = input["method"]
    d = input["columnDepth"]
    bf = input["columnWidth"]
    N = input["plateLength"]
    B = input["plateWidth"]
    tp = input["plateThickness"]
    plateFy = input["plateFy"]
    fc = input["fc"]
    pierLength = input["pierLength"]
    pierWidth = input["pierWidth"]
    anchorCount = input["anchorCount"]
    da = input["anchorDiameter"]
    hef = input["anchorEmbedment"]
    anchorFuta = input["anchorFuta"]
    ca1 = input["anchorEdgeDistance"]
    sL = input["anchorSpacingLength"]
    sW = input["anchorSpacingWidth"]
    anchorType = input["anchorType"]

    if N <= 0 or B <= 0 or tp <= 0:
        raise InputError("plate dimensions must be positive")
    if fc <= 0:
        raise InputError("f'c must be positive")
    if anchorCount <= 0:
        raise InputError("anchorCount must be positive")
    if hef <= 0:
        raise InputError("anchor embedment must be positive")

    warnings = []
    checks = []
    lam_c = nn(input, "lambda", 1.0)
    cracked = nn(input, "cracked", True)
    fcKsi = fc / 1000
    Ase = nn(input, "anchorStressArea", None)
    if Ase is None:
        Ase = thread_stress_area(da)
    P = nn(input, "P", 0)
    uplift = nn(input, "uplift", 0)
    M = nn(input, "M", 0)
    V = nn(input, "V", 0)

    edition = nn(input, "aciEdition", "318-25")
    ACI = aci_label(edition)

    # ACI capacities are LRFD; in ASD mode divide by 1.5 so a service-level demand is compared
    # consistently. Project basis per the owner P.E. ruling 2026-10-26 - ACI prints no ASD conversion.
    def aci_design(nominal, phi):
        return phi * nominal if method == "LRFD" else (phi * nominal) / _ASD_ANCHOR_FACTOR

    # --- concrete bearing, AISC J8 ---------------------------------------------
    A1 = N * B
    A2 = jmin(pierLength * pierWidth, 4 * A1)  # geometrically similar frustum
    bearingRatio = jmin(2.0, sqrt(div(A2, A1)))
    Pp = 0.85 * fcKsi * A1 * bearingRatio  # J8-2
    bearingCapacity = _design(Pp, method, 0.65, 2.31)  # phi_c = 0.65
    checks.append(_row("Concrete bearing", P, bearingCapacity,
                       f"AISC J8-2 / {ACI} Table 22.8.3.2, phi = 0.65 (Table 21.2.1(d))"))

    # --- bearing distribution and anchor tension -------------------------------
    e = abs(M) / P if P > 1e-9 else math.inf
    kern = N / 6
    fpMax = (0.85 * fcKsi * bearingRatio) * (0.65 if method == "LRFD" else 1 / 2.31)
    anchorsInTension = False
    Tanchor = 0

    if (not math.isfinite(e)) or e > kern or uplift > 0:
        # Beyond the kern, or with net uplift (Design Guide 1 section 3.4).
        anchorsInTension = True
        bearingPressure = fpMax
        f = sL / 2
        q = fpMax * B
        dPrime = N / 2 + f

        netCompression = P - uplift  # uplift relieves the bearing block first
        if netCompression > 1e-9 and math.isfinite(e) and q > 0:
            disc = dPrime * dPrime - div(2 * netCompression * (e + f), q)
            if disc >= 0:
                bearingLength = jmin(N, dPrime - sqrt(disc))
                Tanchor = jmax(0, q * bearingLength - netCompression)
            else:
                # No real root: fall back to the anchor-couple-only model and flag it.
                bearingLength = 0
                Tanchor = abs(M) / sL if sL > 0 else abs(M) / jmax(N / 2, 1)
                warnings.append(
                    "Bearing block cannot equilibrate the applied moment at f_p,max — the plate is too short or the pressure too high for this eccentricity. "
                    "Anchor tension was taken from the moment couple alone; enlarge the plate or the pier."
                )
        else:
            # Net tension on the base: the anchor group carries uplift plus the moment couple.
            bearingLength = 0
            lever = sL if sL > 0 else jmax(N / 2, 1)
            Tanchor = jmax(0, uplift - P) + abs(M) / lever
    else:
        # Small eccentricity: full-length trapezoidal bearing.
        bearingLength = N
        bearingPressure = (P / (B * N)) * (1 + (6 * abs(M)) / (P * N))

    # --- plate thickness, DG-1 -------------------------------------------------
    m = (N - 0.95 * d) / 2
    n = (B - 0.8 * bf) / 2
    X = div(4 * d * bf, pow_(d + bf, 2)) * (div(P, bearingCapacity) if bearingCapacity > 0 else 0)
    if X < 1:
        lam = jmin(1, div(2 * sqrt(X), 1 + sqrt(jmax(0, 1 - X))))
    else:
        lam = 1
    nPrime = sqrt(d * bf) / 4
    cantilever = jmax(m, n, lam * nPrime)

    fp = bearingPressure
    loadedLength = jmin(bearingLength, cantilever)
    if loadedLength >= cantilever:
        Mplate = (fp * cantilever * cantilever) / 2
    else:
        Mplate = fp * loadedLength * (cantilever - loadedLength / 2)
    plateFb = 0.9 * plateFy if method == "LRFD" else div(plateFy, 1.67)
    requiredThickness = sqrt(div(4 * Mplate, plateFb))
    checks.append(_row(
        "Base plate yield (bearing interface)", requiredThickness, tp,
        f"AISC Design Guide 1 §3.1 (yield-line cantilever {js_num(round_half_up(cantilever, 3))} in, bearing over {js_num(round_half_up(loadedLength, 3))} in)"))

    # Tension-interface plate bending.
    if anchorsInTension and Tanchor > 0:
        x = jmax(0.5, (sL - 0.95 * d) / 2)
        Mpl = (Tanchor * x) / B
        tReqTension = sqrt(div(4 * Mpl, 0.9 * plateFy if method == "LRFD" else div(plateFy, 1.67)))
        checks.append(_row("Base plate yield (tension interface)", tReqTension, tp,
                           "AISC Design Guide 1 §3.4 (anchor-side cantilever)"))

    # --- anchor demands --------------------------------------------------------
    nTensionAnchors = jmax(1, math.floor(anchorCount / 2))
    anchorTension = Tanchor / nTensionAnchors if anchorsInTension else 0
    anchorShear = V / anchorCount

    # --- edition-dependent factors ---------------------------------------------
    castIn = anchorType == "cast-in"
    ductile = input.get("ductile") is not False
    redundancy = nn(input, "anchorageRedundancy", "nonredundant")
    supplementary = input.get("supplementaryReinforcement") is True
    phi = anchor_phi(edition, ductile, redundancy)
    category = nn(input, "anchorCategory", 3)
    if edition == "318-25" and not castIn and input.get("anchorCategory") is None:
        warnings.append(
            "REVIEW: post-installed anchor with no ACI 355.2/355.4 Anchor Category supplied — psi_a (ACI CODE-318-25 Table 17.5.4.1) "
            "was taken for Category 3, the lowest value. Enter the Category from the product's ICC-ES evaluation report (ESR) to replace it."
        )
    psiAT = psi_a(edition, castIn, category, supplementary, "tension")
    psiAV = psi_a(edition, castIn, category, supplementary, "shear")
    psiANote = f", psi_a = {js_num(psiAT)} (Table 17.5.4.1)" if edition == "318-25" else ""
    psiAVNote = f", psi_a = {js_num(psiAV)} (Table 17.5.4.1)" if edition == "318-25" else ""

    def phi_note(p):
        return f", phi = {js_num(p)} ({phi['source']})"

    # --- anchor steel, ACI 17.6.1.2 / 17.7.1.2 --------------------------------
    # futa used shall not exceed 1.9*fya or 125 ksi (17.6.1.2, 17.7.1.2).
    fya = input.get("anchorFya")
    hasFya = fya is not None and fya > 0
    futaCap = jmin(1.9 * fya, 125) if hasFya else 125
    futa = jmin(anchorFuta, futaCap)
    if futa < anchorFuta:
        warnings.append(f"Anchor futa {js_num(anchorFuta)} ksi exceeds the {ACI} 17.6.1.2 limit min(1.9·fya, 125 ksi) = "
                        f"{js_num(round_half_up(futaCap, 3))} ksi; the limit was used.")
    if not hasFya:
        warnings.append(f"Anchor fya not supplied — futa was capped only at 125 ksi; the {ACI} 17.6.1.2 / 17.7.1.2 limit "
                        "futa <= 1.9·fya was not checked. Enter fya to apply it.")
    Nsa = Ase * futa  # 17.6.1.2
    phiNsa = aci_design(Nsa, phi["steelTension"])
    checks.append(_row("Anchor rod tensile (steel)", anchorTension, phiNsa,
                       f"{ACI} 17.6.1.2{phi_note(phi['steelTension'])}"))

    grout = truthy(input.get("groutPad"))
    groutFactor = 0.8 if grout else 1.0  # 17.7.1.2.1
    Vsa = 0.6 * Ase * futa * groutFactor  # 17.7.1.2b
    phiVsa = aci_design(Vsa, phi["steelShear"])
    checks.append(_row("Anchor rod shear (steel)", anchorShear, phiVsa,
                       f"{ACI} 17.7.1.2b{' x 0.80 grout pad (17.7.1.2.1)' if grout else ''}{phi_note(phi['steelShear'])}"))

    # --- concrete breakout in tension, ACI 17.6.2 ------------------------------
    # kc = 24 cast-in, 17 post-installed (17.6.2.2.1; a specific ESR may list more).
    kc = 24 if castIn else 17

    caEdgeN = (pierLength - sL) / 2
    caEdgeB = (pierWidth - sW) / 2
    closeEdges = (2 if caEdgeN < 1.5 * hef else 0) + (2 if caEdgeB < 1.5 * hef else 0)
    sMax = jmax(sL, sW)
    caMax = jmax(caEdgeN, caEdgeB)
    hefEff = jmax(caMax / 1.5, sMax / 3) if closeEdges >= 3 else hef
    if closeEdges >= 3 and hefEff < hef:
        warnings.append(
            f"{ACI} 17.6.2.1.2 applies — anchors are within 1.5·hef of {js_num(closeEdges)} edges, so the breakout calculation uses a reduced "
            f"hef of {js_num(round_half_up(hefEff, 3))} in (max of ca,max/1.5 and s/3) instead of the {js_num(hef)} in actual embedment. "
            "Deeper embedment will not raise breakout capacity on a pier this size; widen the pier or add supplementary reinforcement."
        )

    Nb = (kc * lam_c * sqrt(fc) * pow_(hefEff, 1.5)) / 1000  # 17.6.2.2.1, kip
    ANco = 9 * hefEff * hefEff  # 17.6.2.1.4
    # Projected area of the anchor GROUP, clipped by the pier edges, and not more than n*ANco (17.6.2.1.1).
    spanN = sL + 2 * jmin(1.5 * hefEff, caEdgeN)
    spanB = sW + 2 * jmin(1.5 * hefEff, caEdgeB)
    ANcGeom = jmin(spanN, pierLength) * jmin(spanB, pierWidth)
    ANc = jmin(ANcGeom, anchorCount * ANco)
    psiEdN = 1.0 if ca1 >= 1.5 * hefEff else 0.7 + div(0.3 * ca1, 1.5 * hefEff)  # 17.6.2.4.1
    # 17.6.2.5.1: uncracked 1.25 cast-in, 1.4 post-installed with the generic kc = 17.
    psiCN = 1.0 if cracked else (1.25 if castIn else 1.4)
    # 17.6.2.6 splitting, post-installed anchors in UNCRACKED concrete (no supplementary
    # reinforcement): psi_cp,N = 1.0 when ca,min >= cac, else max(ca,min/cac, 1.5*hef/cac).
    # Cracked concrete and cast-in anchors: 1.0. cac from the ESR or the Table 17.9.5 default.
    psiCpN = 1.0
    cp_note = ""
    cac_default = 2 * hef if anchorType == "post-installed-adhesive" else 4 * hef
    cac_in = input.get("cac")
    has_cac = truthy(cac_in) and cac_in > 0
    cac = cac_in if has_cac else cac_default
    if not castIn and not cracked:
        if not has_cac:
            warnings.append(
                f"Uncracked concrete with {anchorType} anchors and no critical edge distance cac supplied — psi_cp,N (ACI 17.6.2.6) "
                f"uses the Table 17.9.5 default cac = {'2' if anchorType == 'post-installed-adhesive' else '4'}·hef = {js_num(round_half_up(cac, 3))} in. "
                "Enter cac from the product's ESR to replace it."
            )
        psiCpN = 1.0 if ca1 >= cac else jmin(1.0, jmax(div(ca1, cac), div(1.5 * hef, cac)))
        cp_note = f", psi_cp,N = {js_num(round_half_up(psiCpN, 4))} (17.6.2.6, cac = {js_num(round_half_up(cac, 3))} in)"
    if not castIn and cracked:
        warnings.append(f"Post-installed anchors in cracked concrete must be qualified for cracked concrete per ACI 355.2 / 355.4 "
                        f"({ACI} 17.6.2.5.2) — confirm on the ESR.")

    # psi_cm,N, 17.6.2.7 (318-25 only, opt-in): tension anchors >= 1.5*hef from every free edge,
    # no net uplift, C/T > 0.8 from the bearing solve; z = f + N/2 - Y/2 is the couple's lever arm.
    psiCmN = 1.0
    cm_note = ""
    if truthy(input.get("applyCompressionField")):
        f = sL / 2
        C = fpMax * B * bearingLength
        z = f + N / 2 - bearingLength / 2
        reasons = []
        if edition != "318-25":
            reasons.append("psi_cm,N is a 318-25 provision (17.6.2.7) and the anchorage is set to ACI 318-19")
        if jmin(ca1, caEdgeN, caEdgeB) < 1.5 * hef:
            reasons.append(f"an edge distance is below 1.5·hef = {js_num(round_half_up(1.5 * hef, 3))} in")
        if uplift > 0:
            reasons.append("the base is in net uplift")
        if not (anchorsInTension and Tanchor > 0 and bearingLength > 0):
            reasons.append("there is no tension-compression couple from the bearing solve")
        elif not (C / Tanchor > 0.8):
            reasons.append(f"C/T = {js_num(round_half_up(C / Tanchor, 3))} is not greater than 0.8")
        if not reasons:
            psiCmN = jmax(1.0, 2 - z / (1.5 * hef))
            cm_note = (f", psi_cm,N = {js_num(round_half_up(psiCmN, 4))} (17.6.2.7.1, z = {js_num(round_half_up(z, 3))} in, "
                       f"C/T = {js_num(round_half_up(C / Tanchor, 3))})")
            if psiCmN == 1.0:
                warnings.append(f"psi_cm,N opt-in: z = {js_num(round_half_up(z, 3))} in >= 1.5·hef, so psi_cm,N = 1.0 (no credit).")
        else:
            warnings.append(f"psi_cm,N opt-in was not applied (taken as 1.0, 17.6.2.7.2): {'; '.join(reasons)}.")
    elif edition == "318-25" and anchorsInTension and Tanchor > 0:
        warnings.append("psi_cm,N (ACI CODE-318-25 17.6.2.7 breakout compression field) taken as 1.0 — always conservative "
                        "(R17.6.2.7.2). Opt in to evaluate the credit.")

    NcbgNoCm = div(ANc, ANco) * psiAT * psiEdN * psiCN * psiCpN * Nb  # 17.6.2.1b without psi_cm,N
    Ncbg = NcbgNoCm * psiCmN
    phiNcbg = aci_design(Ncbg, phi["concreteTension"])
    anc_note = ", ANc = n·ANco (17.6.2.1.1)" if ANcGeom > ANc else ""
    checks.append(_row("Concrete breakout (tension)", Tanchor, phiNcbg,
                       f"{ACI} 17.6.2.1b{psiANote}{cp_note}{cm_note}{anc_note}{phi_note(phi['concreteTension'])}"))

    # --- pullout, ACI 17.6.3 ---------------------------------------------------
    if castIn:
        Abrg = 1.5 * da * da
        Np = (8 * Abrg * fc) / 1000  # 17.6.3.2.2a, kip
        psiCP = 1.0 if cracked else 1.4  # 17.6.3.3.1
        phiNpn = aci_design(psiAT * psiCP * Np, phi["pullout"])  # 17.6.3.1
        checks.append(_row("Anchor pullout", anchorTension, phiNpn,
                           f"{ACI} 17.6.3.1 / 17.6.3.2.2a (headed anchor, Abrg = 1.5da²{psiANote}){phi_note(phi['pullout'])}"))
    elif anchorType == "post-installed-mechanical":
        warnings.append(f"Post-installed mechanical anchor: pullout strength Np is test-based ({ACI} 17.6.3.2.1) and is not "
                        "calculated here — check it with the ESR value. Steel shear Vsa must also come from the ESR "
                        "(17.7.1.2c), not 0.6·Ase·futa.")

    # --- adhesive bond, ACI 17.6.5 ---------------------------------------------
    # NagAll: nominal bond strength of the WHOLE group, for adhesive pryout (17.7.3.1.2).
    NagAll = None
    if anchorType == "post-installed-adhesive":
        bond = input.get("bondStrength")
        if truthy(bond) and bond > 0:
            tu = input.get("bondStrengthUncracked")
            tauUncr = tu if truthy(tu) and tu > 0 else None
            # 17.6.5.2.1: tau_cr, replaced by tau_uncr for anchors in uncracked concrete.
            tau = tauUncr if (not cracked and tauUncr is not None) else bond
            Nba = (lam_c * tau * math.pi * da * hef) / 1000  # 17.6.5.2.1, kip
            if tauUncr is not None:
                # Group bond, 17.6.5.1b, over the TENSION ROW (nTensionAnchors along B at ca1 from
                # the edge): ANa projects cNa from the row, clipped by the pier.
                cNa = 10 * da * sqrt(tauUncr / 1100)  # 17.6.5.1.2b
                ANao = 4 * cNa * cNa  # 17.6.5.1.2a
                across = (sW if nTensionAnchors > 1 else 0) + 2 * jmin(cNa, caEdgeB)
                along = jmin(cNa, ca1) + jmin(cNa, jmax(0, pierLength - ca1))
                ANa = jmin(across * along, nTensionAnchors * ANao)  # 17.6.5.1.1
                caMin = jmin(ca1, caEdgeB)
                psiEdNa = 1.0 if caMin >= cNa else 0.7 + div(0.3 * caMin, cNa)  # 17.6.5.4.1
                psiCpNa = jmin(1.0, div(jmax(caMin, cNa), cac)) if (not cracked and caMin < cac) else 1.0  # 17.6.5.5.1
                Nag = div(ANa, ANao) * psiAT * psiEdNa * psiCpNa * Nba
                checks.append(_row(
                    "Adhesive bond strength", Tanchor, aci_design(Nag, phi["bond"]),
                    f"{ACI} 17.6.5.1b (group of {js_num(nTensionAnchors)}, cNa = {js_num(round_half_up(cNa, 3))} in, "
                    f"ANa/ANao = {js_num(round_half_up(div(ANa, ANao), 4))}, "
                    f"psi_ed,Na = {js_num(round_half_up(psiEdNa, 4))}, psi_cp,Na = {js_num(round_half_up(psiCpNa, 4))}{psiANote}; "
                    f"tau = {js_num(tau)} psi, user-supplied){phi_note(phi['bond'])}", True))
                acrossAll = sW + 2 * jmin(cNa, caEdgeB)
                alongAll = sL + 2 * jmin(cNa, caEdgeN)
                ANaAll = jmin(acrossAll * alongAll, anchorCount * ANao)
                NagAll = div(ANaAll, ANao) * psiAT * psiEdNa * psiCpNa * Nba
            else:
                Na = psiAT * Nba
                checks.append(_row(
                    "Adhesive bond strength", anchorTension, aci_design(Na, phi["bond"]),
                    f"{ACI} 17.6.5.2.1 single anchor (tau = {js_num(tau)} psi, user-supplied{psiANote}){phi_note(phi['bond'])}",
                    True))
                NagAll = anchorCount * Na
                warnings.append(
                    f"No tau_uncr supplied — the adhesive bond check used the single-anchor Nba ({ACI} 17.6.5.2.1) without the group terms "
                    "cNa, ANa/ANao, psi_ed,Na and psi_cp,Na (17.6.5.1). This MAY BE UNCONSERVATIVE when anchors are closer than 2·cNa "
                    "to each other or cNa to an edge. Enter tau_uncr from the ESR to run the group equation."
                )
        else:
            warnings.append(
                "Adhesive anchor selected but no characteristic bond stress (tau_cr) supplied — the ACI 17.6.5 bond check was NOT run. "
                "Bond commonly governs adhesive anchors. Enter tau_cr from the product's ICC-ES evaluation report (e.g. the Hilti HVU2 ESR) to complete the check."
            )

    # --- side-face blowout, ACI 17.6.4 -----------------------------------------
    # Headed anchors with deep embedment close to an edge (hef > 2.5*ca1).
    if castIn and ca1 < 0.4 * hef:
        Abrg = 1.5 * da * da
        Nsb0 = (psiAT * 160 * ca1 * sqrt(Abrg) * lam_c * sqrt(fc)) / 1000  # 17.6.4.1
        sEdge = sW
        if nTensionAnchors > 1 and sEdge < 6 * ca1:
            # 17.6.4.2: the row along the edge, Nsbg = (1 + s/6ca1)*Nsb, against the row's tension.
            Nsbg = (1 + sEdge / (6 * ca1)) * Nsb0
            checks.append(_row("Concrete side-face blowout", Tanchor, aci_design(Nsbg, phi["concreteTension"]),
                               f"{ACI} 17.6.4.2 (Nsbg = (1 + s/6ca1)·Nsb, s = {js_num(sEdge)} in{psiANote}){phi_note(phi['concreteTension'])}"))
        else:
            # 17.6.4.1.1: ca2 < 3*ca1 -> x (1 + ca2/ca1)/4, with 1.0 <= ca2/ca1 <= 3.0.
            ca2 = caEdgeB
            k = (1 + jmin(3, jmax(1, ca2 / ca1))) / 4 if ca2 < 3 * ca1 else 1.0
            k_note = f" x {js_num(round_half_up(k, 4))} (17.6.4.1.1, ca2 = {js_num(round_half_up(ca2, 3))} in)" if k < 1 else ""
            checks.append(_row("Concrete side-face blowout", anchorTension, aci_design(k * Nsb0, phi["concreteTension"]),
                               f"{ACI} 17.6.4.1{k_note}{psiANote}{phi_note(phi['concreteTension'])}"))

    # --- concrete breakout in shear, ACI 17.7.2 --------------------------------
    if V > 0:
        le = jmin(hef, 8 * da)  # 17.7.2.2.1
        Vb = jmin(
            7 * pow_(div(le, da), 0.2) * sqrt(da) * lam_c * sqrt(fc) * pow_(ca1, 1.5),
            9 * lam_c * sqrt(fc) * pow_(ca1, 1.5),
        ) / 1000  # 17.7.2.2.1a/b, kip
        AVco = 4.5 * ca1 * ca1  # 17.7.2.1.3
        AVc = jmin(pierWidth, sW + 3 * ca1) * jmin(1.5 * ca1, pierLength)
        # 17.7.2.4.1: ca2 is the pier side distance from the outer anchor.
        ca2 = caEdgeB
        psiEdV = 1.0 if ca2 >= 1.5 * ca1 else 0.7 + div(0.3 * ca2, 1.5 * ca1)
        psiCV = 1.0 if cracked else 1.4  # 17.7.2.5.1
        Vcbg = div(AVc, AVco) * psiAV * psiEdV * psiCV * Vb  # 17.7.2.1b
        phiVcbg = aci_design(Vcbg, phi["concreteShear"])
        checks.append(_row("Concrete breakout (shear)", V, phiVcbg,
                           f"{ACI} 17.7.2.1b (psi_ed,V = {js_num(round_half_up(psiEdV, 4))}, ca2 = {js_num(round_half_up(ca2, 3))} in"
                           f"{psiAVNote}){phi_note(phi['concreteShear'])}"))

        # Pryout, 17.7.3: kcp = 2.0 for hef >= 2.5 in. Ncpg = Ncbg (cast-in, mechanical) or the
        # lesser of Nag and Ncbg (adhesive, 17.7.3.1.2). psi_cm,N is NOT used here.
        kcp = 2.0 if hef >= 2.5 else 1.0
        Ncpg = jmin(NagAll, NcbgNoCm) if NagAll is not None else NcbgNoCm
        phiVcp = aci_design(kcp * Ncpg, phi["concreteShear"])
        pry_note = (f" (Ncpg = min(Nag, Ncbg) = {'Nag' if NagAll < NcbgNoCm else 'Ncbg'}, 17.7.3.1.2)"
                    if NagAll is not None else "")
        checks.append(_row("Concrete pryout (shear)", V, phiVcp,
                           f"{ACI} 17.7.3.1b{pry_note}{phi_note(phi['concreteShear'])}"))

    # --- tension-shear interaction, ACI 17.8 -----------------------------------
    if Tanchor > 0 and V > 0:
        def ratio_of(match):
            return jmax(0, *[(c["ratio"] if finite(c["ratio"]) else 0) for c in checks if match(c["label"])])

        if edition == "318-19":
            tension_re = re.compile(r"tensile|breakout \(tension\)|pullout|blowout|bond", re.I)
            shear_re = re.compile(r"shear", re.I)
            maxT = ratio_of(lambda lb: tension_re.search(lb) is not None)
            maxV = ratio_of(lambda lb: shear_re.search(lb) is not None)
            # 318-19 17.8.3 permits full strength in one direction when the other is <= 0.2.
            one_dir = maxT <= 0.2 or maxV <= 0.2
            interaction = jmax(maxT, maxV) if one_dir else maxT + maxV
            limit = 1.0 if one_dir else 1.2
            checks.append({
                "label": "Tension-shear interaction", "demand": interaction, "capacity": limit,
                "ratio": interaction / limit, "clause": "ACI 318-19 17.8.3 (trilinear 0.2 / 1.2)",
                "status": verdict(interaction <= limit),
            })
        else:
            # 318-25: concrete and steel are checked independently (R17.8.1).
            rtc = ratio_of(lambda lb: lb in _CONCRETE_TENSION)
            rvc = ratio_of(lambda lb: lb in _CONCRETE_SHEAR)
            conc = power_interaction(rtc, rvc, 5 / 3)
            checks.append({
                "label": "Tension-shear interaction (concrete)", "demand": conc, "capacity": 1.0, "ratio": conc,
                "clause": f"ACI CODE-318-25 17.8.3: ({js_num(round_half_up(rtc, 4))})^(5/3) + ({js_num(round_half_up(rvc, 4))})^(5/3) <= 1",
                "status": verdict(conc <= 1.0),
            })
            rts = ratio_of(lambda lb: lb == "Anchor rod tensile (steel)")
            rvs = ratio_of(lambda lb: lb == "Anchor rod shear (steel)")
            steel = power_interaction(rts, rvs, 2)
            checks.append({
                "label": "Tension-shear interaction (steel)", "demand": steel, "capacity": 1.0, "ratio": steel,
                "clause": f"ACI CODE-318-25 17.8.4: ({js_num(round_half_up(rts, 4))})^2 + ({js_num(round_half_up(rvs, 4))})^2 <= 1",
                "status": verdict(steel <= 1.0),
            })

    # --- warnings --------------------------------------------------------------
    if not castIn:
        warnings.append(
            f"Post-installed anchor: kc = {js_num(kc)} is {ACI}'s generic value. A product-specific ESR normally lists a higher kc and its own edge/spacing limits — enter those for a final design."
        )
    if not ductile:
        src = "ACI CODE-318-25 Table 21.2.1 (p)/(r)" if edition == "318-25" else "ACI 318-19 17.5.3"
        warnings.append(f"Anchors declared non-ductile — steel phi lowered to {js_num(phi['steelTension'])} tension / "
                        f"{js_num(phi['steelShear'])} shear ({src}). For SDC C-F, {ACI} 17.10 requires a ductile failure mode or an overstrength design.")
    if edition == "318-25" and input.get("anchorageRedundancy") is None:
        warnings.append("Anchorage taken as NONREDUNDANT (concrete-tension phi 0.65, ACI CODE-318-25 Table 21.2.1 (l)). "
                        "Select redundant only where redundancy is inherent in the connection (R17.5.3).")
    if ca1 < 1.5 * hef:
        warnings.append(
            f"Edge distance {js_num(ca1)} in is less than 1.5·hef = {js_num(round_half_up(1.5 * hef, 2))} in — the breakout cone is clipped and psi_ed,N reduces the capacity.")
    if tp < requiredThickness:
        warnings.append(
            f"Plate is {js_num(tp)} in but {js_num(round_half_up(requiredThickness, 3))} in is required for the bearing-interface yield line.")
    if method == "ASD":
        warnings.append(f"{ACI} Chapter 17 is a strength-design (LRFD) chapter. Anchor capacities shown were divided by 1.5 to "
                        "compare against service-level ASD demands — a project basis per the owner P.E. ruling of 2026-10-26, "
                        "not an ACI provision.")

    # Infinity (zero capacity) must win the roll-up.
    real = [c for c in checks if c["status"] != "na"]
    if real:
        governing = real[0]
        for b in real[1:]:
            if b["ratio"] > governing["ratio"]:
                governing = b
    else:
        governing = checks[0]

    def r4(v):
        return round_half_up(v, 4)

    out_checks = []
    for c in checks:
        cc = dict(c)
        cc["demand"] = r4(c["demand"])
        cc["capacity"] = r4(c["capacity"])
        cc["ratio"] = r4(c["ratio"]) if math.isfinite(c["ratio"]) else c["ratio"]
        out_checks.append(cc)

    out = {
        "A1": r4(A1), "A2": r4(A2), "bearingRatio": r4(bearingRatio),
        "bearingCapacity": r4(bearingCapacity), "bearingPressure": r4(bearingPressure),
        "eccentricity": r4(e) if math.isfinite(e) else e,
        "anchorsInTension": anchorsInTension,
        "requiredThickness": r4(requiredThickness), "cantilever": r4(cantilever),
        "anchorTension": r4(anchorTension), "anchorShear": r4(anchorShear),
        "checks": out_checks,
        "governingRatio": r4(governing["ratio"]) if math.isfinite(governing["ratio"]) else governing["ratio"],
        "governingCheck": governing["label"],
    }
    return result(MODULE, out, verdict(all(c["status"] != "fail" for c in checks)), warnings)
