#!/usr/bin/env python3
"""Merge the 4 dev-reviewer outputs and build the review decision page.

Usage: review-page.py --plan docs/plans/<slug>.md <lens-output.json>...

Each lens output is the JSON array a dev-reviewer returned (one file per lens).
Writes, next to each other:
  docs/reviews/<slug>.findings.json   merged findings, the input for fix mode
  docs/reviews/<slug>.json            page data
  docs/reviews/<slug>.html            the page
Prints {"findings": N, "by_lens": {...}, "page": "...", "findings_file": "..."}.
Findings at the same file:line are merged into one, listing every lens that raised them.
"""
import json
import pathlib
import re
import subprocess
import sys

LENSES = ["correctness", "security", "feature", "completeness"]
BULLET = 100


def wrap(label, text):
    """Bullets of at most BULLET chars, split on sentences then words."""
    out, line = [], f"{label}: "
    for word in " ".join(text.split()).split(" "):
        if len(line) + len(word) + 1 > BULLET:
            out.append(line.rstrip())
            line = "  "
        line += word + " "
    out.append(line.rstrip())
    return out


def main():
    args = sys.argv[1:]
    if "--plan" not in args:
        sys.exit(__doc__)
    i = args.index("--plan")
    plan = pathlib.Path(args[i + 1])
    inputs = args[:i] + args[i + 2:]
    slug = plan.stem

    merged = {}
    for path in inputs:
        for f in json.loads(pathlib.Path(path).read_text()):
            key = f["where"].strip()
            if key in merged:
                m = merged[key]
                m["lenses"] = sorted(set(m["lenses"]) | {f["lens"]}, key=LENSES.index)
                if f["scenario"] not in m["scenario"]:
                    m["scenario"] += " / " + f["scenario"]
            else:
                merged[key] = {**f, "lenses": [f["lens"]]}
    findings = list(merged.values())

    by_lens = {lens: sum(lens in f["lenses"] for f in findings) for lens in LENSES}
    ticket = re.search(r"^Ticket:\s*(\S+)", plan.read_text(), re.M)

    nodes = {}
    for f in findings:
        bullets = wrap("what", f["scenario"]) + wrap("fix", f.get("fix", ""))
        nodes[f["id"]] = {
            "title": f["title"][:120],
            "severity": "T0",
            "where": f["where"],
            "context": [
                {"type": "table", "head": ["Lens", "Where"], "rows": [[", ".join(f["lenses"])[:40], f["where"][:40]]]},
                {"type": "bullets", "items": bullets[:5]},
            ],
            "options": [
                {"id": "fix", "label": "Fix it", "result": "implementer applies the fix", "recommended": True},
                {"id": "skip", "label": "Skip", "result": "kept as is, noted in the plan"},
            ],
        }
    page = {
        "title": f"{slug} — review",
        "kind": "review",
        "ticket": ticket.group(1) if ticket else None,
        "plan": str(plan),
        "summary": [{"type": "table", "head": ["Lens", "T0"], "rows": [[k, str(v)] for k, v in by_lens.items()]}],
        "roots": [f["id"] for f in findings],
        "nodes": nodes,
    }

    out = pathlib.Path("docs/reviews")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.findings.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
    (out / f"{slug}.json").write_text(json.dumps(page, indent=1, ensure_ascii=False))
    html = out / f"{slug}.html"
    build = pathlib.Path(__file__).resolve().parent.parent.parent / "templates" / "dev" / "build-page.py"
    done = subprocess.run([sys.executable, str(build), str(out / f"{slug}.json"), str(html)], capture_output=True, text=True)
    if done.returncode:
        sys.exit(done.stderr or done.stdout)

    print(json.dumps({"findings": len(findings), "by_lens": by_lens,
                      "page": str(html), "findings_file": str(out / f"{slug}.findings.json")}))


if __name__ == "__main__":
    main()
