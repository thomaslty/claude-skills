#!/usr/bin/env python3
"""Fill decision-page.html with a page-data JSON file.

Usage: python3 ~/.claude/templates/dev/build-page.py <data.json> <out.html>
"""
import json
import pathlib
import re
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
LIMITS = {"text": 120, "bullet": 100, "bullets": 5, "cell": 40, "label": 40, "result": 70,
          "step_bullet": 140, "step_label": 14, "fact": 400, "diagram_lines": 60}
# Mermaid diagram types the page draws, and the label text inside ["..."], [..], (..), {..} and |..|.
DIAGRAMS = ("flowchart", "graph", "mindmap", "timeline", "quadrantChart", "sequenceDiagram",
            "stateDiagram-v2", "journey", "pie", "xychart-beta", "block-beta")
LABEL = re.compile(r'"([^"]*)"|\[([^\[\]"]*)\]|\(([^()"]*)\)|\{([^{}"]*)\}|\|([^|"]*)\|')
# Mockups live on a Claude Design canvas; the page only links it.
CANVAS_MOVED = "screens live on the Claude Design canvas now; set the top-level \"canvas\" url instead"
errors = []
if "canvas" in data and not str(data["canvas"]).startswith("https://claude.ai/"):
    errors.append(f"canvas must be the canvas url, like https://claude.ai/artifact/<id>, not {data['canvas']!r}")


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
        elif kind == "screen":
            errors.append(f"{at}: {CANVAS_MOVED}")
        elif kind == "heading":
            if len(b["text"]) > LIMITS["label"]:
                errors.append(f"{at}: heading is over {LIMITS['label']} chars")
        elif kind == "steps":
            check_steps(at, b["items"])
        elif kind == "facts":
            for label, text in b["items"]:
                if len(label) > LIMITS["step_label"] or len(text) > LIMITS["fact"]:
                    errors.append(f"{at}: fact {label!r} is over {LIMITS['step_label']}/{LIMITS['fact']} chars")
        elif kind == "mermaid":
            check_mermaid(at, b.get("code", ""))
        elif kind == "links":
            for label, url in b["items"]:
                if len(label) > LIMITS["label"] or not url.startswith(("http://", "https://")):
                    errors.append(f"{at}: link {label!r} needs a label of at most {LIMITS['label']} chars and an http(s) url")
        elif kind == "fold":
            if len(b.get("title", "")) > LIMITS["label"]:
                errors.append(f"{at}: fold title is over {LIMITS['label']} chars")
            check_blocks(f"{at}.fold", b.get("blocks", []))
        elif kind != "graph":
            errors.append(f"{at}: unknown block type {kind!r}; use text, bullets, table, graph, mermaid, links, fold, heading, facts or steps")


def check_mermaid(at, code):
    """A diagram, not prose in a box: a known type, every label short, the whole thing small."""
    lines = [l for l in code.strip().splitlines() if l.strip() and not l.strip().startswith("%%")]
    kind = lines[0].split()[0] if lines else ""
    if kind not in DIAGRAMS:
        errors.append(f"{at}: mermaid must start with one of {', '.join(DIAGRAMS)}, not {kind!r}")
        return
    if len(lines) > LIMITS["diagram_lines"]:
        errors.append(f"{at}: diagram has {len(lines)} lines, max {LIMITS['diagram_lines']}; split it")
    for line in lines[1:]:
        # mindmap and timeline nodes are bare text, one per line
        texts = [line.strip()] if kind in ("mindmap", "timeline") else [t for g in LABEL.findall(line) for t in g if t]
        for text in texts:
            if len(text) > LIMITS["label"]:
                errors.append(f"{at}: diagram label is {len(text)} chars, max {LIMITS['label']}: {text[:40]!r}")


def check_steps(at, items):
    """/show-plan detail: one card per step, header plus at most 5 one-line labelled bullets."""
    for step in items:
        name = f"{at} step {step.get('n')!r}"
        for key in ("n", "title", "status", "effort"):
            if not step.get(key):
                errors.append(f"{name}: missing {key!r}")
        if len(step.get("title", "")) > LIMITS["label"]:
            errors.append(f"{name}: title is over {LIMITS['label']} chars")
        bullets = step.get("bullets", [])
        if not bullets or len(bullets) > LIMITS["bullets"]:
            errors.append(f"{name}: {len(bullets)} bullets, need 1 to {LIMITS['bullets']}")
        for label, text in bullets:
            if len(label) > LIMITS["step_label"]:
                errors.append(f"{name}: bullet label {label!r} is over {LIMITS['step_label']} chars")
            if len(text) > LIMITS["step_bullet"]:
                errors.append(f"{name}: bullet is {len(text)} chars, max {LIMITS['step_bullet']}: {text[:40]!r}")


if "summary" in data:
    check_blocks("summary", data["summary"])
for nid, node in data["nodes"].items():
    if "context" in node:
        check_blocks(f"{nid}.context", node["context"])
    for opt in node.get("options", []):
        if "screen" in opt:
            errors.append(f"{nid}.{opt['id']}.screen: {CANVAS_MOVED}; name the option's artboard in its result")
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
