#!/usr/bin/env python3
"""Run the PROMPTS.md examples as headless Claude Code sessions with the plugin loaded.

    python tests/e2e/run_e2e.py --out <dir> [--only E1,E3] [--model sonnet]

Writes <dir>/<id>.txt (final answer) and <dir>/<id>.json (full result). Grading is
done by a human or a reviewer against the "Pass checks" column; this script only runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(ROOT, "plugins", "piping-toolset")


def prompts() -> list[tuple[str, str]]:
    text = open(os.path.join(ROOT, "tests", "e2e", "PROMPTS.md"), encoding="utf-8").read()
    out = []
    for line in text.splitlines():
        m = re.match(r"\|\s*(E\d+)\s*\|[^|]*\|\s*`(.+?)`\s*\|", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    for pid, prompt in prompts():
        if only and pid not in only:
            continue
        t0 = time.time()
        cmd = ["claude", "-p", prompt, "--plugin-dir", PLUGIN, "--model", a.model,
               "--output-format", "json",
               "--allowedTools", "Bash(python:*)", "Bash(python3:*)", "Read", "Glob", "Grep", "Skill"]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           timeout=900)
        try:
            data = json.loads(r.stdout)
            answer = data.get("result", "")
        except json.JSONDecodeError:
            data, answer = {"raw": r.stdout, "stderr": r.stderr}, r.stdout
        json.dump(data, open(os.path.join(a.out, f"{pid}.json"), "w", encoding="utf-8"), indent=2)
        open(os.path.join(a.out, f"{pid}.txt"), "w", encoding="utf-8").write(answer)
        print(f"{pid} exit={r.returncode} {time.time() - t0:.0f}s turns={data.get('num_turns')} "
              f"cost=${data.get('total_cost_usd', 0):.3f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
