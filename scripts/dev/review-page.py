#!/usr/bin/env python3
"""Merge the 4 dev-reviewer outputs and build the review decision page.

Usage: review-page.py --plan plan/<slug>/plan.md <lens-output.json>...

Each lens output is the JSON array a dev-reviewer returned (one file per lens).
Writes, next to each other:
  dev/<slug>/review/findings.json   merged findings, the input for fix mode
  dev/<slug>/review/review.json     page data
  dev/<slug>/review/review.html     the page
Prints {"findings": N, "by_lens": {...}, "page": "...", "findings_file": "..."}.
Findings at the same file:line are merged into one, listing every lens that raised them.
"""
import json
import pathlib
import re
import subprocess
import sys

LENSES = ["correctness", "security", "feature", "completeness"]


def main():
    args = sys.argv[1:]
    if "--plan" not in args:
        sys.exit(__doc__)
    i = args.index("--plan")
    plan = pathlib.Path(args[i + 1])
    inputs = args[:i] + args[i + 2:]
    slug = plan.parent.name

    merged = {}
    for path in inputs:
        for f in json.loads(pathlib.Path(path).read_text()):
            # same file:line whether a reviewer wrote it absolute or relative
            key = f["where"].strip().removeprefix(str(pathlib.Path.cwd()) + "/")
            if key in merged:
                m = merged[key]
                m["lenses"] = sorted(set(m["lenses"]) | {f["lens"]}, key=LENSES.index)
                for part in ("cause", "impact", "scenario"):
                    if f.get(part) and f[part] not in m.get(part, ""):
                        joined = (m[part] + " / " if m.get(part) else "") + f[part]
                        # the page refuses a fact over 400 chars, so keep the first lens's words then
                        if len(joined) <= 400:
                            m[part] = joined
            else:
                merged[key] = {**f, "lenses": [f["lens"]]}
    findings = list(merged.values())

    by_lens = {lens: sum(lens in f["lenses"] for f in findings) for lens in LENSES}
    ticket = re.search(r"^Ticket:\s*(\S+)", plan.read_text(), re.M)

    nodes = {}
    for f in findings:
        # Root cause and impact in the reviewer's own words, uncut; older outputs only have `scenario`.
        facts = ([["Root cause", f["cause"]], ["Impact", f["impact"]]] if f.get("cause")
                 else [["What", f.get("scenario", "")]])
        facts += [["Fix", f.get("fix", "")], ["Lens", ", ".join(f["lenses"])]]
        nodes[f["id"]] = {
            "title": f["title"][:120],
            "severity": "T0",
            "where": f["where"],
            "context": [{"type": "facts", "items": [x for x in facts if x[1]]}],
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

    out = pathlib.Path("dev") / slug / "review"
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
    (out / "review.json").write_text(json.dumps(page, indent=1, ensure_ascii=False))
    html = out / "review.html"
    build = pathlib.Path(__file__).resolve().parent.parent.parent / "templates" / "dev" / "build-page.py"
    done = subprocess.run([sys.executable, str(build), str(out / "review.json"), str(html)], capture_output=True, text=True)
    if done.returncode:
        sys.exit(done.stderr or done.stdout)

    print(json.dumps({"findings": len(findings), "by_lens": by_lens,
                      "page": str(html), "findings_file": str(out / "findings.json")}))


if __name__ == "__main__":
    main()
