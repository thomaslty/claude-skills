#!/usr/bin/env python3
"""Read a docs/plans/<slug>.md and report where it stands, instead of counting by eye.

Usage: plan-status.py <docs/plans/<slug>.md>

Prints: {"status": "approved", "ticked": 27, "total": 30, "left": ["4", "19", "review:sec-1"], "done": false}
`done` is true only when the plan is approved and every step under ## Steps is ticked.
"""
import json
import pathlib
import re
import sys

STEP = re.compile(r"^\s*- \[( |x|X)\] (review:\s*\S+|\d+)")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    text = pathlib.Path(sys.argv[1]).read_text()

    m = re.search(r"^Status:\s*(\w+)", text, re.M)
    status = m.group(1).lower() if m else "missing"

    steps = re.search(r"^## Steps\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    ticked, left = 0, []
    for line in (steps.group(1) if steps else "").splitlines():
        s = STEP.match(line)
        if not s:
            continue
        if s.group(1) == " ":
            left.append(s.group(2).replace(" ", ""))
        else:
            ticked += 1

    total = ticked + len(left)
    print(json.dumps({
        "status": status,
        "ticked": ticked,
        "total": total,
        "left": left,
        "done": status == "approved" and total > 0 and not left,
    }))


if __name__ == "__main__":
    main()
