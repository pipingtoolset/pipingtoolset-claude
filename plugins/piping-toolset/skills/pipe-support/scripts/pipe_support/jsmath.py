"""JavaScript-semantics helpers for exact numerical parity with the TypeScript
engine (which runs under V8): division by zero yields Infinity/NaN rather than raising,
Math.min/max propagate NaN, Math.sqrt/pow of invalid arguments yield NaN, and numbers
embedded in template-literal messages print the JS way (6 not 6.0).

Standard library only.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Dict


def js_num(x: Any) -> str:
    """Format a number the way a JS template literal does (6.0 -> '6', 1e-7 -> '1e-7')."""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if x != x:
        return "NaN"
    if x in (math.inf, -math.inf):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    t = Decimal(repr(abs(float(x)))).normalize().as_tuple()
    digits = "".join(str(i) for i in t.digits)
    k = len(digits)
    n = k + t.exponent  # value = 0.DIGITS x 10^n
    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        m = digits[0] + ("." + digits[1:] if k > 1 else "")
        s = f"{m}e{'+' if e >= 0 else '-'}{abs(e)}"
    return sign + s


def div(a: float, b: float) -> float:
    """JS division: x/0 is +-Infinity or NaN, never an exception."""
    try:
        return a / b
    except ZeroDivisionError:
        if a != a or a == 0:
            return math.nan
        neg = (a < 0) != (math.copysign(1.0, b) < 0)
        return -math.inf if neg else math.inf


def sqrt(x: float) -> float:
    """Math.sqrt: NaN for negative or NaN input."""
    return math.nan if x != x or x < 0 else math.sqrt(x)


def pow_(a: float, b: float) -> float:
    """Math.pow (never raises, never returns complex)."""
    try:
        return math.pow(a, b)
    except OverflowError:
        return math.inf
    except ValueError:
        return math.inf if a == 0 and b < 0 else math.nan


def jmin(*a: float) -> float:
    """Math.min: NaN if any argument is NaN."""
    if any(v != v for v in a):
        return math.nan
    return min(a)


def jmax(*a: float) -> float:
    """Math.max: NaN if any argument is NaN."""
    if any(v != v for v in a):
        return math.nan
    return max(a)


def truthy(x: Any) -> bool:
    """JS truthiness for numbers / None (0, NaN and undefined/null are falsy)."""
    return x is not None and x == x and x != 0


def nn(d: Dict[str, Any], key: str, default: Any) -> Any:
    """JS ``d[key] ?? default`` (a missing key or null falls through to the default)."""
    v = d.get(key)
    return default if v is None else v


def finite(x: Any) -> bool:
    """Number.isFinite."""
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
