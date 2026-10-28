#!/usr/bin/env python3
"""Merge the 4 dev-reviewer outputs into one findings list for the terminal.

Usage: review-findings.py --plan plan/<slug>/plan.md <lens-output.json>...

Each lens output is the JSON array a dev-reviewer returned (one file per lens).
Writes, next to each other:
  dev/<slug>/review/findings.json   merged findings, the input for fix mode
  dev/<slug>/review/findings.md     what the coordinator prints in the terminal, as it is
Prints {"findings": N, "by_lens": {...}, "findings_file": "...", "markdown": "..."}.
Findings at the same file:line are merged into one, listing every lens that raised them.
"""
import json
import pathlib
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
                for part in ("cause", "impact", "scenario", "fix"):
                    if f.get(part) and f[part] not in m.get(part, ""):
                        m[part] = (m[part] + " / " if m.get(part) else "") + f[part]
            else:
                merged[key] = {**f, "where": key, "lenses": [f["lens"]]}
    findings = list(merged.values())
    by_lens = {lens: sum(lens in f["lenses"] for f in findings) for lens in LENSES}

    lines = [f"## Review: {slug}", "", "| Lens | T0 |", "|---|---|"]
    lines += [f"| {lens} | {count} |" for lens, count in by_lens.items()]
    for f in findings:
        lines += ["", f"### {f['id']}. {f['title']}", "", f"Where: `{f['where']}` · {', '.join(f['lenses'])}", ""]
        # Root cause and impact in the reviewer's own words, uncut; older outputs only have `scenario`.
        if f.get("cause"):
            lines += [f"- Root cause: {f['cause']}", f"- Impact: {f['impact']}"]
        else:
            lines.append(f"- What: {f.get('scenario', '')}")
        if f.get("fix"):
            lines.append(f"- Fix: {f['fix']}")

    out = pathlib.Path("dev") / slug / "review"
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False))
    (out / "findings.md").write_text("\n".join(lines) + "\n")

    print(json.dumps({"findings": len(findings), "by_lens": by_lens,
                      "findings_file": str(out / "findings.json"), "markdown": str(out / "findings.md")}))


if __name__ == "__main__":
    main()
