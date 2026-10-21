#!/usr/bin/env python3
"""Fill decision-page.html with a page-data JSON file.

Usage: python3 ~/.claude/templates/dev/build-page.py <data.json> <out.html>
"""
import json
import pathlib
import sys

data_path, out_path = sys.argv[1], sys.argv[2]
data = json.loads(pathlib.Path(data_path).read_text())

for root in data.get("roots", []):
    if root not in data["nodes"]:
        sys.exit(f"root {root!r} has no node")
for nid, node in data["nodes"].items():
    for opt in node.get("options", []):
        for nxt in [opt["next"]] if isinstance(opt.get("next"), str) else opt.get("next") or []:
            if nxt not in data["nodes"]:
                sys.exit(f"{nid}.{opt['id']} points at missing node {nxt!r}")

# Structured content only: no paragraphs. Each limit fails the build with a reason,
# so the agent rewrites the content instead of shipping prose.
LIMITS = {"text": 120, "bullet": 100, "bullets": 5, "cell": 40, "label": 40, "result": 70}
errors = []


def check_blocks(where, blocks):
    if not isinstance(blocks, list):
        errors.append(f"{where}: must be a list of blocks, not {type(blocks).__name__}")
        return
    for i, b in enumerate(blocks):
        at = f"{where}[{i}]"
        kind = b.get("type")
        if kind == "text":
            if len(b["text"]) > LIMITS["text"]:
                errors.append(f"{at}: text is {len(b['text'])} chars, max {LIMITS['text']}; use bullets or a table")
        elif kind == "bullets":
            if len(b["items"]) > LIMITS["bullets"]:
                errors.append(f"{at}: {len(b['items'])} bullets, max {LIMITS['bullets']}")
            for item in b["items"]:
                if len(item) > LIMITS["bullet"]:
                    errors.append(f"{at}: bullet is {len(item)} chars, max {LIMITS['bullet']}: {item[:40]!r}")
        elif kind == "table":
            for row in [b["head"]] + b["rows"]:
                if len(row) != len(b["head"]):
                    errors.append(f"{at}: row {row!r} has {len(row)} cells, head has {len(b['head'])}")
                for cell in row:
                    if len(cell) > LIMITS["cell"]:
                        errors.append(f"{at}: cell is {len(cell)} chars, max {LIMITS['cell']}: {cell[:40]!r}")
        elif kind != "graph":
            errors.append(f"{at}: unknown block type {kind!r}; use text, bullets, table or graph")


if "summary" in data:
    check_blocks("summary", data["summary"])
for nid, node in data["nodes"].items():
    if "context" in node:
        check_blocks(f"{nid}.context", node["context"])
    for opt in node.get("options", []):
        for key in ("label", "result"):
            if len(opt.get(key, "")) > LIMITS[key]:
                errors.append(f"{nid}.{opt['id']}.{key} is {len(opt[key])} chars, max {LIMITS[key]}")
if errors:
    sys.exit("page rejected:\n  " + "\n  ".join(errors))

template = pathlib.Path(__file__).with_name("decision-page.html").read_text()
# "</" would close the <script> tag early
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
pathlib.Path(out_path).write_text(template.replace("__PAGE_DATA__", payload))
print(out_path)
