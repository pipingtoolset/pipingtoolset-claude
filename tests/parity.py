"""Shared parity harness: runs vendored fixtures against a skill's Python REGISTRY.

Mirrors calc-core's src/verify.ts exactly, so "green" means the same thing in both
repos:
  - numeric expect: |actual - expected| <= tol (tol defaults to 1e-9)
  - string expect: exact equality
  - status (if given): exact equality with result["status"]
  - a case that asserts nothing is a failure

A skill REGISTRY maps module id -> fn(input: dict) -> {"module", "output", "status", "warnings"}.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALC_CORE = os.path.join(ROOT, "tests", "fixtures", "calc-core")
HAND = os.path.join(ROOT, "tests", "fixtures", "hand")


def load(module: str, *, hand: bool = False) -> dict[str, Any]:
    path = os.path.join(HAND if hand else CALC_CORE, f"{module}.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def modules_for(skill: str) -> list[str]:
    with open(os.path.join(CALC_CORE, "MANIFEST.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    return sorted(m for m, v in man["modules"].items() if v["skill"] == skill)


def run_case(fn: Callable[[dict], dict], case: dict) -> list[str]:
    failures: list[str] = []
    tol = case.get("tol", 1e-9)
    result = fn(dict(case["input"]))
    output = result["output"]
    if "expect" not in case and "status" not in case:
        failures.append("case asserts nothing: provide expect and/or status")
    for key, expected in (case.get("expect") or {}).items():
        actual = output.get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if not isinstance(actual, (int, float)) or abs(actual - expected) > tol:
                failures.append(f"{key}: expected {expected}, got {actual!r}")
        elif actual != expected:
            failures.append(f"{key}: expected {expected!r}, got {actual!r}")
    if "status" in case and result["status"] != case["status"]:
        failures.append(f"status: expected {case['status']}, got {result['status']}")
    return failures


def run_fixture(registry: dict[str, Callable], module: str, *, hand: bool = False) -> list[str]:
    """Return a flat list of failure strings ('' list == green)."""
    fx = load(module, hand=hand)
    fn = registry.get(fx["module"])
    if fn is None:
        return [f"{module}: no function registered"]
    out = []
    for i, case in enumerate(fx["cases"]):
        try:
            fails = run_case(fn, case)
        except Exception as exc:  # a throw is a failure unless the case expects one
            fails = [f"raised {type(exc).__name__}: {exc}"]
        out += [f"{module} case {i}: {f}" for f in fails]
    return out
