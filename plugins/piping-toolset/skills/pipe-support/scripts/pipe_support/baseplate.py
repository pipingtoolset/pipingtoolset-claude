"""Base plate and anchorage - AISC Design Guide 1 + AISC 360-22 J8 + ACI 318-19 Ch. 17.

Exact port of the Piping Toolset PiperSTR engine's ``baseplate-anchorage`` TypeScript module. Units: in,
kip, ksi, psi for f'c. Input/output dict keys are the TypeScript names unchanged.

Data boundary (as the TS engine): proprietary anchor qualification values (bond
stress tau_cr, manufacturer Np, product kc) are NEVER embedded; they arrive as inputs
from the user's ESR / ICC evaluation report. The generic cast-in defaults are ACI
318-19's own values and the output flags them.

Public API: ``base_plate_anchorage(input)``, ``thread_stress_area(d)``.
"""

from __future__ import annotations

import math
import re

from .common import InputError, result, round_half_up, verdict
from .jsmath import div, finite, jmax, jmin, js_num, nn, pow_, sqrt, truthy

MODULE = "structural.baseplate-anchorage"

# ACI 318-19 strength-reduction factors (17.5.3) - baseplate-anchorage.ts PHI_ANCHOR.
_PHI_ANCHOR = {
    "steelTension": 0.75,
    "steelShear": 0.65,
    "concreteTension": 0.70,
    "concreteShear": 0.70,
    "pullout": 0.70,
    "bond": 0.65,
}
# ASD conversion: service-level demand vs an LRFD-derived capacity (ACI R17.5.3).
_ASD_ANCHOR_FACTOR = 1.5

# UNC threads per inch, keyed by String(d) exactly as the TS record.
_UNC_THREADS_PER_INCH = {
    "0.375": 16, "0.5": 13, "0.625": 11, "0.75": 10, "0.875": 9,
    "1": 8, "1.125": 7, "1.25": 7, "1.5": 6, "1.75": 5, "2": 4.5,
}


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

    # ACI capacities are LRFD; in ASD mode divide by 1.5 (ACI 318-19 R17.5.3).
    def aci_design(nominal, phi):
        return phi * nominal if method == "LRFD" else (phi * nominal) / _ASD_ANCHOR_FACTOR

    # --- concrete bearing, AISC J8 ---------------------------------------------
    A1 = N * B
    A2 = jmin(pierLength * pierWidth, 4 * A1)  # geometrically similar frustum
    bearingRatio = jmin(2.0, sqrt(div(A2, A1)))
    Pp = 0.85 * fcKsi * A1 * bearingRatio  # J8-2
    bearingCapacity = _design(Pp, method, 0.65, 2.31)  # phi_c = 0.65
    checks.append(_row("Concrete bearing", P, bearingCapacity, "AISC J8-2 / ACI 318-19 14.5.6.2"))

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

    # --- anchor steel, ACI 17.6.1.2 / 17.7.1.2 --------------------------------
    Nsa = Ase * anchorFuta
    phiNsa = aci_design(Nsa, _PHI_ANCHOR["steelTension"])
    checks.append(_row("Anchor rod tensile (steel)", anchorTension, phiNsa, "ACI 318-19 17.6.1.2"))

    Vsa = 0.6 * Ase * anchorFuta
    phiVsa = aci_design(Vsa, _PHI_ANCHOR["steelShear"])
    checks.append(_row("Anchor rod shear (steel)", anchorShear, phiVsa, "ACI 318-19 17.7.1.2b"))

    # --- concrete breakout in tension, ACI 17.6.2 ------------------------------
    kc = 24 if anchorType == "cast-in" else 17

    caEdgeN = (pierLength - sL) / 2
    caEdgeB = (pierWidth - sW) / 2
    closeEdges = (2 if caEdgeN < 1.5 * hef else 0) + (2 if caEdgeB < 1.5 * hef else 0)
    sMax = jmax(sL, sW)
    caMax = jmax(caEdgeN, caEdgeB)
    hefEff = jmax(caMax / 1.5, sMax / 3) if closeEdges >= 3 else hef
    if closeEdges >= 3 and hefEff < hef:
        warnings.append(
            f"ACI 318-19 17.6.2.1.2 applies — anchors are within 1.5·hef of {js_num(closeEdges)} edges, so the breakout calculation uses a reduced "
            f"hef of {js_num(round_half_up(hefEff, 3))} in (max of ca,max/1.5 and s/3) instead of the {js_num(hef)} in actual embedment. "
            "Deeper embedment will not raise breakout capacity on a pier this size; widen the pier or add supplementary reinforcement."
        )

    Nb = (kc * lam_c * sqrt(fc) * pow_(hefEff, 1.5)) / 1000  # 17.6.2.2a, kip
    ANco = 9 * hefEff * hefEff  # 17.6.2.1c
    spanN = sL + 2 * jmin(1.5 * hefEff, caEdgeN)
    spanB = sW + 2 * jmin(1.5 * hefEff, caEdgeB)
    ANc = jmin(spanN, pierLength) * jmin(spanB, pierWidth)
    psiEdN = 1.0 if ca1 >= 1.5 * hefEff else 0.7 + div(0.3 * ca1, 1.5 * hefEff)  # 17.6.2.4
    psiCN = 1.0 if cracked else 1.25  # 17.6.2.5
    # 17.6.2.6 splitting, post-installed anchors in UNCRACKED concrete (no supplementary
    # reinforcement): psi_cp,N = 1.0 when ca,min >= cac, else max(ca,min/cac, 1.5*hef/cac).
    # Cracked concrete and cast-in anchors: 1.0. Until 2026-10-26 an inner max() pinned this
    # at 1.0 in every case; cac comes from the ESR or the Table 17.9.5 default.
    psiCpN = 1.0
    cp_note = ""
    if anchorType != "cast-in" and not cracked:
        cac_default = 2 * hef if anchorType == "post-installed-adhesive" else 4 * hef
        cac_in = input.get("cac")
        has_cac = truthy(cac_in) and cac_in > 0
        cac = cac_in if has_cac else cac_default
        if not has_cac:
            warnings.append(
                f"Uncracked concrete with {anchorType} anchors and no critical edge distance cac supplied — psi_cp,N (ACI 17.6.2.6) "
                f"uses the Table 17.9.5 default cac = {'2' if anchorType == 'post-installed-adhesive' else '4'}·hef = {js_num(round_half_up(cac, 3))} in. "
                "Enter cac from the product's ESR to replace it."
            )
        psiCpN = 1.0 if ca1 >= cac else jmin(1.0, jmax(div(ca1, cac), div(1.5 * hef, cac)))
        cp_note = f", psi_cp,N = {js_num(round_half_up(psiCpN, 4))} (17.6.2.6, cac = {js_num(round_half_up(cac, 3))} in)"
    Ncbg = div(ANc, ANco) * psiEdN * psiCN * psiCpN * Nb  # 17.6.2.1b
    phiNcbg = aci_design(Ncbg, _PHI_ANCHOR["concreteTension"])
    checks.append(_row("Concrete breakout (tension)", Tanchor, phiNcbg, f"ACI 318-19 17.6.2.1b{cp_note}"))

    # --- pullout, ACI 17.6.3 ---------------------------------------------------
    if anchorType == "cast-in":
        Abrg = 1.5 * da * da
        Np = (8 * Abrg * fc) / 1000  # 17.6.3.2.2a, kip
        psiCP = 1.0 if cracked else 1.4  # 17.6.3.3
        phiNpn = aci_design(psiCP * Np, _PHI_ANCHOR["pullout"])
        checks.append(_row("Anchor pullout", anchorTension, phiNpn,
                           "ACI 318-19 17.6.3.2.2a (headed anchor, Abrg = 1.5da²)"))

    # --- adhesive bond, ACI 17.6.5 ---------------------------------------------
    if anchorType == "post-installed-adhesive":
        bond = input.get("bondStrength")
        if bond and bond > 0:
            Nba = (lam_c * bond * math.pi * da * hef) / 1000  # 17.6.5.2.2b
            phiNa = aci_design(Nba, _PHI_ANCHOR["bond"])
            checks.append(_row("Adhesive bond strength", anchorTension, phiNa,
                               f"ACI 318-19 17.6.5.2.2b (tau_cr = {js_num(bond)} psi, user-supplied)", True))
        else:
            warnings.append(
                "Adhesive anchor selected but no characteristic bond stress (tau_cr) supplied — the ACI 17.6.5 bond check was NOT run. "
                "Bond commonly governs adhesive anchors. Enter tau_cr from the product's ICC-ES evaluation report (e.g. the Hilti HVU2 ESR) to complete the check."
            )

    # --- side-face blowout, ACI 17.6.4 -----------------------------------------
    if anchorType == "cast-in" and ca1 < 0.4 * hef:
        Abrg = 1.5 * da * da
        Nsb = (160 * ca1 * sqrt(Abrg) * lam_c * sqrt(fc)) / 1000  # 17.6.4.1
        phiNsb = aci_design(Nsb, _PHI_ANCHOR["concreteTension"])
        checks.append(_row("Concrete side-face blowout", anchorTension, phiNsb, "ACI 318-19 17.6.4.1"))

    # --- concrete breakout in shear, ACI 17.7.2 --------------------------------
    if V > 0:
        le = jmin(hef, 8 * da)  # 17.7.2.2.1
        Vb = jmin(
            7 * pow_(div(le, da), 0.2) * sqrt(da) * lam_c * sqrt(fc) * pow_(ca1, 1.5),
            9 * lam_c * sqrt(fc) * pow_(ca1, 1.5),
        ) / 1000  # 17.7.2.2.1a/b, kip
        AVco = 4.5 * ca1 * ca1  # 17.7.2.1c
        AVc = jmin(pierWidth, sW + 3 * ca1) * jmin(1.5 * ca1, pierLength)
        psiEdV = 1.0
        psiCV = 1.0 if cracked else 1.4  # 17.7.2.5
        Vcbg = div(AVc, AVco) * psiEdV * psiCV * Vb  # 17.7.2.1b
        phiVcbg = aci_design(Vcbg, _PHI_ANCHOR["concreteShear"])
        checks.append(_row("Concrete breakout (shear)", V, phiVcbg, "ACI 318-19 17.7.2.1b"))

        # Pryout, 17.7.3: kcp = 2.0 for hef >= 2.5 in.
        kcp = 2.0 if hef >= 2.5 else 1.0
        phiVcp = aci_design(kcp * Ncbg, _PHI_ANCHOR["concreteShear"])
        checks.append(_row("Concrete pryout (shear)", V, phiVcp, "ACI 318-19 17.7.3.1b"))

    # --- tension-shear interaction, ACI 17.8.3 ---------------------------------
    if Tanchor > 0 and V > 0:
        tension_re = re.compile(r"tensile|breakout \(tension\)|pullout|blowout|bond", re.I)
        shear_re = re.compile(r"shear", re.I)
        tensionChecks = [c for c in checks if tension_re.search(c["label"])]
        shearChecks = [c for c in checks
                       if shear_re.search(c["label"]) and c["label"] != "Base plate yield (bearing interface)"]
        maxT = jmax(0, *[(c["ratio"] if finite(c["ratio"]) else 0) for c in tensionChecks])
        maxV = jmax(0, *[(c["ratio"] if finite(c["ratio"]) else 0) for c in shearChecks])
        # 17.8.3 permits full strength in one direction when the other is <= 0.2.
        one_dir = maxT <= 0.2 or maxV <= 0.2
        interaction = jmax(maxT, maxV) if one_dir else maxT + maxV
        limit = 1.0 if one_dir else 1.2
        checks.append({
            "label": "Tension-shear interaction", "demand": interaction, "capacity": limit,
            "ratio": interaction / limit, "clause": "ACI 318-19 17.8.3",
            "status": verdict(interaction <= limit),
        })

    # --- warnings --------------------------------------------------------------
    if anchorType != "cast-in":
        warnings.append(
            f"Post-installed anchor: kc = {js_num(kc)} is ACI 318-19's generic value. A product-specific ESR normally lists a higher kc and its own edge/spacing limits — enter those for a final design."
        )
    if input.get("ductile") is False:
        warnings.append("Anchors declared non-ductile — ACI 17.5.3 requires the lower phi factors and, for seismic, a ductile failure mode or an overstrength design.")
    if ca1 < 1.5 * hef:
        warnings.append(
            f"Edge distance {js_num(ca1)} in is less than 1.5·hef = {js_num(round_half_up(1.5 * hef, 2))} in — the breakout cone is clipped and psi_ed,N reduces the capacity.")
    if tp < requiredThickness:
        warnings.append(
            f"Plate is {js_num(tp)} in but {js_num(round_half_up(requiredThickness, 3))} in is required for the bearing-interface yield line.")
    if method == "ASD":
        warnings.append("ACI 318-19 Chapter 17 is a strength-design (LRFD) chapter. Anchor capacities shown were divided by 1.5 to compare against service-level ASD demands, per ACI R17.5.3.")

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
