"""Shared conventions for the pipe-support engine (a stdlib-Python port of the
pipingtoolset.com PiperSTR engine).

Every calculator takes ONE plain dict whose keys are the TypeScript engine's own
camelCase field names, and returns a CalcResult-shaped dict:

    {"module": "structural.aisc-member", "output": {...}, "status": "pass"|"fail"|"na",
     "warnings": [str, ...]}

Keeping the TypeScript key names means a pipingtoolset.com PiperSTR payload, an engine
fixture and a skill spec are the same document, and parity tests feed fixture inputs
straight in.

Units: US customary - in, in^2, in^3, in^4, kip, ksi, kip*in (psi only for f'c, ksf for
soil), exactly as the TypeScript engine.

Standard library only (Python 3.9+).
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Dict, List, Optional


def round_half_up(x: float, decimals: int) -> float:
    """Port of the web engine's roundHalfUp (string-exponent scaling, half away
    from zero), so reported values match the web engine digit for digit."""
    if not isinstance(x, (int, float)) or not math.isfinite(x):
        return x
    # Exactly rounding.ts: scaled = Number(`${x}e${decimals}`) is parsed to a DOUBLE first, so a value a hair
    # under a half (13.893749999999999e4 -> 138937.5) still rounds up; Math.round is half-up on that double.
    scaled = float(Decimal(repr(float(x))).scaleb(decimals))
    a = abs(scaled)
    f = math.floor(a)
    r = float(f + 1 if a - f >= 0.5 else f)
    rounded = r if scaled > 0 else (-r if scaled < 0 else 0.0)
    factor = 10 ** decimals
    if abs(rounded) < 1e21:
        out = float(Decimal(int(rounded)).scaleb(-decimals))
        if out:
            return out
    return rounded / factor


class InputError(ValueError):
    """A defective or incomplete input. Raised, never silently defaulted."""


def result(module: str, output: Dict[str, Any], status: str = "na",
           warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    """Mirror of the web engine's CalcResult."""
    return {"module": module, "output": output, "status": status,
            "warnings": list(warnings or [])}


def need(d: Dict[str, Any], key: str, what: str = "") -> Any:
    """Required input lookup with a readable error."""
    if key not in d or d[key] is None:
        raise InputError(f"missing required input '{key}'{' (' + what + ')' if what else ''}")
    return d[key]
