#!/usr/bin/env python3
"""
loadcase_gen.py - B31-compliant static load case set generator for CAESAR II / AutoPIPE.

Part of the Piping Toolset skill pack (pipingtoolset.com).

WHY THIS EXISTS
    Hand-maintained load case templates break in one specific way: every combination
    case references other cases by NUMBER (L4-L30, L30+L37). Insert one operating
    state and every downstream reference silently points at the wrong case. The
    analysis still runs. The numbers are still plausible. The calc is wrong.

    This generator holds every reference SYMBOLICALLY and resolves to L-numbers in a
    single final pass, so a reference can never go stale. Numbers are an output,
    never an input.

DESIGN BASIS
    CAESAR II load-case semantics as published by COADE / Hexagon (component letters,
    hanger-design sequence, Suppress on intermediate cases, combination methods), the
    nonlinear-restraint argument for the three-tier occasional pattern, ASME B31.1 /
    B31.3 / B31E occasional-load clauses, and ASCE 7 Chapter 13. Clause-level
    citations are in SKILL.md. No tabulated code values are embedded here.

USAGE
    python loadcase_gen.py --example                  # built-in two-state B31.3 example
    python loadcase_gen.py --spec my_job.json         # your project spec
    python loadcase_gen.py --spec my_job.json --format csv > cases.csv
    python loadcase_gen.py --spec my_job.json --format json

    Exit status: 0 = built, 2 = spec error (unknown or forward reference, bad field).

UNITS / CONVENTIONS
    Y is vertical (CAESAR II default). Friction values are CAESAR II FRICTION
    MULTIPLIERS on the modelled mu, not mu itself.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal

# --------------------------------------------------------------------------------------
# Domain model
# --------------------------------------------------------------------------------------

StressType = Literal["HGR", "HYD", "OPE", "SUS", "EXP", "OCC", "FAT"]
Method = Literal["", "Algebraic", "Scalar", "ABS", "SRSS", "Max", "Min", "SignMax", "SignMin"]

# Occasional kinds that each get their own Max envelope. Wind and earthquake are never
# combined with each other (B31.1 101.5.2; B31.3 302.3.6(a)).
ENVELOPE_KINDS = ("psv", "seismic", "snow", "wind", "other")


@dataclass
class ThermalState:
    """One operating condition: a paired temperature / pressure / displacement set."""
    key: str                      # symbolic handle, e.g. "op"
    name: str                     # "OPERATING CASE CONDITION"
    T: str                        # "T1"
    P: str                        # "P1"
    D: str | None = None          # "D1" or None
    role: str = "operating"       # "operating" | "design" | "upset" | "steamout" | ...
    cycles: int | None = None     # N for this state, for the f-factor / FAT work


@dataclass
class Occasional:
    """One occasional load vector riding on one thermal state, in one direction."""
    key: str                      # "seis_px"
    name: str                     # "Seismic +X"
    vector: str                   # "U1", "WIN1", "F1"
    sign: str = "+"               # "+" or "-"
    base: str = "op"              # ThermalState.key this rides on
    kind: str = "other"           # one of ENVELOPE_KINDS
    scale: float | None = None    # ASD reduction (0.6 wind / 0.7 seismic) only if policy says so


@dataclass
class Case:
    """A single CAESAR II static load case."""
    key: str
    block: str
    stress: StressType
    desc: str
    terms: list[str] = field(default_factory=list)            # primitive: ["W","D1","T1","P1","H"]
    refs: list[tuple[int, str]] = field(default_factory=list)  # combination: [(+1,"key"),(-1,"key")]
    method: Method = ""
    friction: float | None = None
    hanger: str | None = None                                 # "Rigid" | "Ignore" | "As Designed"
    suppress: bool = False
    number: int = 0                                           # assigned at resolve time

    @property
    def is_combination(self) -> bool:
        return bool(self.refs)


class SpecError(ValueError):
    """The project spec cannot produce a valid case set."""


def _edition_year(edition: str) -> int | None:
    digits = "".join(ch for ch in edition if ch.isdigit())
    return int(digits[:4]) if len(digits) >= 4 else None


# --------------------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------------------

class LoadCaseSet:
    """Builds, resolves and renders a complete static load case set."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        try:
            self.code: str = spec["code"]                       # "B31.1" | "B31.3"
            self.states = [ThermalState(**s) for s in spec["thermal_states"]]
            self.occ = [Occasional(**o) for o in spec.get("occasionals", [])]
        except (KeyError, TypeError) as exc:
            raise SpecError(f"spec is missing or has an unknown field: {exc}") from exc
        if self.code not in ("B31.1", "B31.3"):
            raise SpecError(f"code must be 'B31.1' or 'B31.3', got {self.code!r}")
        if not self.states:
            raise SpecError("thermal_states must list at least one operating state")
        self.edition: str = str(spec.get("edition", "UNSTATED"))
        self.frictions: list[tuple[str, float]] = [tuple(f) for f in spec.get(
            "frictions", [["w/ Friction", 1.0], ["w/o Friction", 0.0]])]
        self.hangers: bool = spec.get("hangers", True)
        self.hydrotest: bool = spec.get("hydrotest", True)
        self.inter_state_ranges: bool = spec.get("inter_state_expansion_ranges", True)
        self.occ_combine: Method = spec.get("occ_combine_method", "Scalar")  # Scalar or ABS
        self.cases: list[Case] = []
        self.findings: list[str] = []
        self._by_state = {s.key: s for s in self.states}
        for o in self.occ:
            if o.base not in self._by_state:
                raise SpecError(f"occasional {o.key!r} rides on unknown state {o.base!r}")
            if o.kind not in ENVELOPE_KINDS:
                raise SpecError(f"occasional {o.key!r} has kind {o.kind!r}; "
                                f"use one of {', '.join(ENVELOPE_KINDS)}")

    # -- helpers ------------------------------------------------------------------------

    def _add(self, c: Case) -> Case:
        self.cases.append(c)
        return c

    def _primitive_terms(self, st: ThermalState, *, thermal: bool, hanger: bool) -> list[str]:
        """W [+D] [+T] +P [+H]. Sustained drops D and T; that is the whole difference."""
        terms = ["W"]
        if thermal:
            if st.D:
                terms.append(st.D)
            terms.append(st.T)
        terms.append(st.P)
        if hanger and self.hangers:
            terms.append("H")
        return terms

    @staticmethod
    def _k(*parts: str) -> str:
        return ":".join(parts)

    # -- blocks -------------------------------------------------------------------------

    def _block_hanger(self) -> None:
        """Hanger design, CAESAR II's recommended pair: W with springs Rigid sizes the load;
        W+T1 with springs Ignored sizes the travel. H is the OUTPUT of these two cases, so it
        first appears in the As-Designed cases that follow. Both must precede them."""
        if not self.hangers:
            return
        primary = self.states[0]
        self._add(Case(key="hgr:rigid", block="HGR", stress="HGR", desc="WEIGHT FOR HANGER LOADS",
                       terms=["W"], hanger="Rigid", friction=self.frictions[0][1]))
        self._add(Case(key="hgr:travel", block="HGR", stress="HGR",
                       desc="OPERATING FOR HANGER TRAVEL",
                       terms=["W", primary.T],
                       hanger="Ignore", friction=self.frictions[0][1]))

    def _block_hydro(self) -> None:
        """WW = water-filled weight, HP = hydro pressure. Insulation weight in the hydro case
        is a CAESAR II configuration choice; state it."""
        if not self.hydrotest:
            return
        terms = ["WW", "HP"] + (["H"] if self.hangers else [])
        self._add(Case(key="hyd", block="HYD", stress="HYD", desc="HYDRO TEST CASE",
                       terms=terms, friction=self.frictions[0][1]))

    def _block_operating(self) -> None:
        """Base operating cases: every thermal state x every friction multiplier."""
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("ope", st.key, str(fval)), block="OPE", stress="OPE",
                               desc=f"{st.name} {fname}",
                               terms=self._primitive_terms(st, thermal=True, hanger=True),
                               friction=fval, hanger="As Designed" if self.hangers else None))

    def _block_operating_with_occ(self) -> None:
        """The occasional is solved FROM the operating position, because nonlinear restraint
        status (gaps, one-way supports, friction) differs there from the modelled position."""
        for fname, fval in self.frictions:
            for o in self.occ:
                st = self._by_state[o.base]
                term = f"{o.sign}{o.scale}{o.vector}" if o.scale else f"{o.sign}{o.vector}"
                terms = self._primitive_terms(st, thermal=True, hanger=True) + [term]
                self._add(Case(key=self._k("opeocc", o.key, str(fval)), block="OPE+OCC",
                               stress="OPE", desc=f"{st.name} with {o.name} ({fname})",
                               terms=terms, friction=fval,
                               hanger="As Designed" if self.hangers else None))

    def _block_sustained(self) -> None:
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("sus", st.key, str(fval)), block="SUS", stress="SUS",
                               desc=f"SUSTAINED {st.name} ({fname})",
                               terms=self._primitive_terms(st, thermal=False, hanger=True),
                               friction=fval, hanger="As Designed" if self.hangers else None))

    def _block_expansion(self) -> None:
        """EXP = OPE - SUS, Algebraic. Plus inter-state ranges: when one leg runs hot and
        another cold, the governing range is between two operating states, not between
        either one and ambient."""
        for st in self.states:
            for fname, fval in self.frictions:
                self._add(Case(key=self._k("exp", st.key, str(fval)), block="EXP", stress="EXP",
                               desc=f"EXPANSION {st.name} ({fname})", method="Algebraic",
                               refs=[(+1, self._k("ope", st.key, str(fval))),
                                     (-1, self._k("sus", st.key, str(fval)))]))
        if self.inter_state_ranges and len(self.states) > 1:
            fval = self.frictions[0][1]
            for i in range(len(self.states)):
                for j in range(i + 1, len(self.states)):
                    a, b = self.states[i], self.states[j]
                    self._add(Case(key=self._k("exprange", a.key, b.key), block="EXP", stress="EXP",
                                   desc=f"EXPANSION RANGE {a.name} to {b.name}",
                                   method="Algebraic",
                                   refs=[(+1, self._k("ope", a.key, str(fval))),
                                         (-1, self._k("ope", b.key, str(fval)))]))

    def _block_pure_occasional(self) -> None:
        """(OPE + occ) - OPE, Algebraic. Intermediate only, so output is suppressed."""
        for fname, fval in self.frictions:
            for o in self.occ:
                self._add(Case(key=self._k("pure", o.key, str(fval)), block="OCC-PURE", stress="OCC",
                               desc=f"Pure {o.name} ({fname})", method="Algebraic", suppress=True,
                               refs=[(+1, self._k("opeocc", o.key, str(fval))),
                                     (-1, self._k("ope", o.base, str(fval)))]))

    def _block_code_occasional(self) -> None:
        """SUS + pure occ, Scalar. Scalar sums the STRESSES, which is the form the code
        check needs (S_L + S_L,occ <= k*Sh). Algebraic here would be wrong."""
        for fname, fval in self.frictions:
            for o in self.occ:
                self._add(Case(key=self._k("occ", o.key, str(fval)), block="OCC-CODE", stress="OCC",
                               desc=f"{o.name} Code Stress Case ({fname})", method=self.occ_combine,
                               refs=[(+1, self._k("sus", o.base, str(fval))),
                                     (+1, self._k("pure", o.key, str(fval)))]))

    def _block_envelopes(self) -> None:
        """Max envelopes. The overall occasional envelope must include every occasional kind;
        an envelope that omits one silently drops it from the code check."""
        # Every friction variant: a reaction or movement that governs only with friction
        # off must still reach the support-load and displacement envelope.
        primary = self.states[0].key
        max_ope: list[str] = []
        for _, fv in self.frictions:
            max_ope.append(self._k("ope", primary, str(fv)))
            max_ope += [self._k("opeocc", o.key, str(fv)) for o in self.occ if o.base == primary]
        self._add(Case(key="max:ope", block="MAX", stress="OPE", desc="Maximum Operating",
                       method="Max", refs=[(+1, k) for k in max_ope]))

        group_keys: list[str] = []
        for kind in ENVELOPE_KINDS:
            members = [self._k("occ", o.key, str(f)) for _, f in self.frictions
                       for o in self.occ if o.kind == kind]
            if not members:
                continue
            gk = f"max:{kind}"
            self._add(Case(key=gk, block="MAX", stress="OCC",
                           desc=f"Maximum {kind.capitalize()} Occasional", method="Max",
                           refs=[(+1, m) for m in members]))
            group_keys.append(gk)

        if group_keys:
            self._add(Case(key="max:occ", block="MAX", stress="OCC", desc="Maximum Occasional",
                           method="Max", refs=[(+1, g) for g in group_keys]))

    # -- build / resolve ----------------------------------------------------------------

    def build(self) -> "LoadCaseSet":
        self._block_hanger()
        self._block_hydro()
        self._block_operating()
        self._block_operating_with_occ()
        self._block_sustained()
        self._block_expansion()
        self._block_pure_occasional()
        self._block_code_occasional()
        self._block_envelopes()
        self._resolve()
        self._qc()
        return self

    def _resolve(self) -> None:
        """Assign L-numbers in list order, then verify every symbolic reference points
        BACKWARD. A forward reference is a hard error, not a warning."""
        for i, c in enumerate(self.cases, start=1):
            c.number = i
        index = {c.key: c for c in self.cases}
        for c in self.cases:
            for _, ref in c.refs:
                if ref not in index:
                    raise SpecError(f"L{c.number} '{c.desc}' references unknown case '{ref}'")
                if index[ref].number >= c.number:
                    raise SpecError(
                        f"L{c.number} '{c.desc}' references L{index[ref].number} which is not "
                        f"earlier in the set. CAESAR II combination cases must reference "
                        f"previously defined cases.")

    def combo_string(self, c: Case) -> str:
        if not c.is_combination:
            s = c.terms[0]
            for t in c.terms[1:]:
                s += t if t[0] in "+-" else f"+{t}"
            return s
        index = {x.key: x for x in self.cases}
        if c.method == "Max":
            return ", ".join(f"L{index[r].number}" for _, r in c.refs)
        out = ""
        for sign, ref in c.refs:
            n = index[ref].number
            out += (f"L{n}" if not out else (f"+L{n}" if sign > 0 else f"-L{n}"))
        return out

    # -- QC -----------------------------------------------------------------------------

    def _qc(self) -> None:
        f = self.findings
        year = _edition_year(self.edition)
        if self.edition == "UNSTATED" or year is None:
            f.append("BASIS: code edition not stated. An undeclared edition is a review finding.")

        kinds = {o.kind for o in self.occ}
        if "seismic" in kinds and "wind" in kinds:
            f.append("OK: wind and seismic are separate envelopes; they are never combined "
                     "(B31.1 101.5.2; B31.3 302.3.6(a)).")

        # Vertical seismic
        vert = [o for o in self.occ if o.kind == "seismic" and o.vector.upper() == "U2"]
        seis = [o for o in self.occ if o.kind == "seismic"]
        snow = [o for o in self.occ if o.kind == "snow"]
        if seis and not vert:
            f.append("GAP: no vertical seismic component. ASCE 7 Ch. 13 requires concurrent "
                     "Ev = 0.2*SDS*Wp. U2 is the only vertical uniform vector in CAESAR II.")
        if snow and any(o.vector.upper() == "U2" for o in snow) and seis and not vert:
            f.append("CONFLICT: U2 carries snow, so no vector remains for Ev. 'Uniform Load in "
                     "G's' is a GLOBAL flag, so a snow vector entered in lb/ft while it is on "
                     "is read as g's. Dedicate U2 to Ev and carry snow as weight, or run snow "
                     "and seismic as separate sets.")

        # Envelope completeness
        env = next((c for c in self.cases if c.key == "max:occ"), None)
        if env:
            covered = {r.split(":")[1] for _, r in env.refs}
            missing = kinds - covered
            if missing:
                f.append(f"ERROR: Maximum Occasional envelope omits {sorted(missing)}.")
            else:
                f.append("OK: Maximum Occasional envelope covers every occasional kind present.")

        # Friction policy
        if len(self.frictions) < 2:
            f.append("NOTE: only one friction multiplier. Where PIP PNC00004 is invoked, "
                     "3.2.3 requires running with and without friction and taking the "
                     "governing result.")

        # Occasional allowable
        if self.code == "B31.3":
            f.append("ALLOWABLE: B31.3 302.3.6(a) - sustained + occasional <= 1.33*Sh (flat); "
                     "Chapter IX high-pressure piping uses 1.20 (K302.3.6(a)).")
        else:
            f.append("ALLOWABLE: B31.1 104.8.2 - k = 1.15 (<= 8 h at one time AND <= 800 h/yr) "
                     "or 1.20 (<= 1 h AND <= 80 h/yr). Set the CAESAR II occasional factor to "
                     "match and write the duration justification into the calc.")

        # ASD reduction policy - the software documentation, the software wizard and the code
        # do not agree; the position must be stated either way.
        scaled = [o for o in self.occ if o.scale]
        if self.code == "B31.1" and scaled:
            if year is not None and year >= 2024:
                f.append("ERROR: B31.1-2024 101.5.2 / 101.5.3 state the ASD reduction factor "
                         "shall not be applied, but occasional terms carry a scale factor. "
                         "Remove it.")
            else:
                f.append("CHECK: occasional terms carry an ASD scale factor under B31.1 "
                         f"{self.edition}. B31.1-2024 prohibits it; for earlier editions cite "
                         "the owner or EOR direction that permits it.")
        elif scaled:
            f.append("ASD: 0.6W / 0.7E reduction applied for stress. B31.3 is silent on the "
                     "factor; cite the owner or EOR direction, and keep UNREDUCED companion "
                     "cases for support loads and displacements.")
        elif self.occ:
            f.append("ASD: no 0.6W / 0.7E reduction applied (strength level). This matches "
                     "B31.1-2024 and the conservative reading of B31.3, and differs from the "
                     "CAESAR II help topic on ASCE 7 load combinations. State the position "
                     "and who approved it.")

        # Expansion completeness
        n_exp = sum(1 for c in self.cases if c.block == "EXP" and c.key.startswith("exp:"))
        expect = len(self.states) * len(self.frictions)
        if n_exp < expect:
            f.append(f"GAP: {n_exp} expansion cases for {expect} state x friction pairs.")

    # -- render -------------------------------------------------------------------------

    def rows(self) -> list[dict[str, Any]]:
        return [{
            "L": c.number, "Combination": self.combo_string(c), "Description": c.desc,
            "Stress Type": c.stress, "Method": c.method or "-",
            "Friction": "-" if c.friction is None else f"{c.friction:.1f}",
            "Hanger": c.hanger or "-", "Output": "Suppress" if c.suppress else "Include",
        } for c in self.cases]

    def to_markdown(self) -> str:
        rows = self.rows()
        hdr = list(rows[0].keys())
        out = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
        out += ["| " + " | ".join(str(r[h]) for h in hdr) + " |" for r in rows]
        return "\n".join(out)

    def to_csv(self) -> str:
        buf = io.StringIO()
        rows = self.rows()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    def to_json(self) -> str:
        return json.dumps({
            "code": self.code, "edition": self.edition, "total_cases": len(self.cases),
            "cases": self.rows(), "findings": self.findings,
        }, indent=2)

    def report_matrix(self) -> str:
        """Which load cases feed which qualification. Regenerated from the resolved
        numbering; this is the table that goes stale when a template is copied."""
        n = {c.key: c.number for c in self.cases}
        p = self.states[0].key
        sus = [str(n[self._k("sus", p, str(fv))]) for _, fv in self.frictions]
        exp = [str(n[self._k("exp", s.key, str(fv))])
               for s in self.states for _, fv in self.frictions]
        rows = [
            ("Code stress - Sustained", ", ".join(sus), f"{self.code} sustained"),
            ("Code stress - Expansion", ", ".join(exp), f"{self.code} expansion, S_A"),
        ]
        if "max:occ" in n:
            rows.append(("Code stress - Occasional", f"{n['max:occ']}",
                         f"{self.code} occasional envelope"))
        if "hyd" in n:
            rows.append(("Code stress - Hydrotest", f"{n['hyd']}", "test case"))
        rows += [
            ("Support loads - Sustained", ", ".join(sus), "hanger/restraint design"),
            ("Support loads - Max Operating", f"{n['max:ope']}", "governing operating reaction"),
            ("Displacements - Sustained", sus[0], "vertical sag limit"),
            ("Displacements - Max Operating", f"{n['max:ope']}", "lateral movement"),
            ("Flange / nozzle loads - Operating",
             ", ".join(str(n[self._k("ope", p, str(fv))]) for _, fv in self.frictions),
             "manufacturer or WRC allowable; both friction variants, take the governing"),
        ]
        out = ["| Purpose | Load Case(s) | Basis |", "|---|---|---|"]
        out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
        return "\n".join(out)

    def to_autopipe(self) -> str:
        """CAESAR II -> AutoPIPE component mapping. VERIFY against your AutoPIPE version:
        whether AutoPIPE needs the same subtract-then-scalar occasional construction has
        not been confirmed."""
        m = {"W": "GR (Gravity)", "WW": "GR with water content / Hydrotest weight",
             "WNC": "GR, empty (no contents)", "HP": "Hydrotest pressure",
             "H": "Spring hanger preload (automatic)", "T#": "T1..Tn thermal",
             "P#": "P1..Pn pressure", "D#": "Imposed displacement (anchor movement)",
             "U#": "Uniform / static-g earthquake E1..En", "WIN#": "Wind W1..Wn",
             "F#": "User-defined point force (PSV thrust)"}
        out = ["| CAESAR II | AutoPIPE equivalent |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in m.items()]
        return "\n".join(out)


# --------------------------------------------------------------------------------------
# Example spec - a generic two-state B31.3 line with PSV, seismic, snow and wind
# --------------------------------------------------------------------------------------

EXAMPLE_SPEC: dict[str, Any] = {
    "code": "B31.3", "edition": "2022",
    "thermal_states": [
        {"key": "op",  "name": "OPERATING CASE CONDITION", "T": "T1", "P": "P1", "D": "D1",
         "role": "operating"},
        {"key": "des", "name": "DESIGN CASE CONDITION", "T": "T2", "P": "P2", "D": "D2",
         "role": "design"},
    ],
    "frictions": [["w/ Friction", 1.0], ["w/o Friction", 0.0]],
    "hangers": True, "hydrotest": True,
    "inter_state_expansion_ranges": False,
    "occasionals": [
        {"key": "psv_op",  "name": "PSV Pop Off",        "vector": "F1",   "base": "op",  "kind": "psv"},
        {"key": "psv_des", "name": "Design PSV Pop Off", "vector": "F2",   "base": "des", "kind": "psv"},
        {"key": "seis_px", "name": "Seismic +X", "vector": "U1", "sign": "+", "base": "op", "kind": "seismic"},
        {"key": "seis_mx", "name": "Seismic -X", "vector": "U1", "sign": "-", "base": "op", "kind": "seismic"},
        {"key": "seis_pz", "name": "Seismic +Z", "vector": "U3", "sign": "+", "base": "op", "kind": "seismic"},
        {"key": "seis_mz", "name": "Seismic -Z", "vector": "U3", "sign": "-", "base": "op", "kind": "seismic"},
        {"key": "snow",    "name": "Snow -Y",   "vector": "U2", "sign": "-", "base": "op", "kind": "snow"},
        {"key": "win_px",  "name": "Wind +X", "vector": "WIN1", "base": "op", "kind": "wind"},
        {"key": "win_mx",  "name": "Wind -X", "vector": "WIN2", "base": "op", "kind": "wind"},
        {"key": "win_pz",  "name": "Wind +Z", "vector": "WIN3", "base": "op", "kind": "wind"},
        {"key": "win_mz",  "name": "Wind -Z", "vector": "WIN4", "base": "op", "kind": "wind"},
    ],
}


def render_report(s: LoadCaseSet) -> str:
    parts = [
        f"## Load case set - {s.code} {s.edition}\n",
        s.to_markdown(),
        "\n### Report extraction matrix\n",
        s.report_matrix(),
        "\n### QC findings\n",
        "\n".join(f"- {x}" for x in s.findings),
        f"\nTotal cases: {len(s.cases)}",
    ]
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a B31 static load case set.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="path to a JSON project spec")
    src.add_argument("--example", action="store_true", help="use the built-in example spec")
    ap.add_argument("--format", choices=("md", "csv", "json", "autopipe"), default="md")
    args = ap.parse_args(argv)

    if args.example:
        spec = EXAMPLE_SPEC
    else:
        try:
            with open(args.spec, encoding="utf-8") as fh:
                spec = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"spec error: {exc}", file=sys.stderr)
            return 2

    try:
        s = LoadCaseSet(spec).build()
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2

    if args.format == "csv":
        sys.stdout.write(s.to_csv())
    elif args.format == "json":
        print(s.to_json())
    elif args.format == "autopipe":
        print(s.to_autopipe())
    else:
        sys.stdout.write(render_report(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
