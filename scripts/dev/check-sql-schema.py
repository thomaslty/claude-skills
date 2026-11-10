#!/usr/bin/env python3
"""Check the ## Schema of a plan/<slug>/plan.md against /dev:sql-db-design, instead of by eye.
Rules: kind, abbreviation, vague-name, json, time-name, missing-audit, hardcoded-values,
code-without-reference, polymorphic, dual-purpose, missing-purpose, missing-data-flow, approval.

Usage: check-sql-schema.py <plan/<slug>/plan.md> [--audit created_by,created_time,updated_by,updated_time]

Prints: {"tables": 4, "approval": "asked", "findings": [{"table": "om.workflow_step", "column": "outcome",
         "rule": "vague-name", "do": "fix", "message": "..."}]}

- `do` is `fix` (change the plan) or `ask` (put it in the plan's ## Questions).
- `approval` is `approved` when ## Schema has an `Approved:` line, `asked` when ## Questions names
  every table, `missing` otherwise, and `none` when the plan has no ## Schema.
- `--audit` is the repo's own audit columns, the first two required on every table.
"""
import json
import pathlib
import re
import sys

DEFAULT_AUDIT = ["created_by", "created_time", "updated_by", "updated_time"]
VAGUE = {"outcome", "detail", "details", "data", "payload", "info", "meta", "metadata", "extra", "misc",
         "blob", "attributes", "attrs", "props", "properties", "json", "stuff"}
VAGUE_ENDINGS = ("_json", "_blob", "_payload", "_data", "_detail", "_details", "_info", "_meta", "_metadata")
TIME_NAMES = {"started_time", "ended_time", "start_time", "end_time", "modified_time", "modified_by",
              "modified_date", "started_at", "ended_at", "created_at", "updated_at", "deleted_at"}

CODE_ENDINGS = ("_status", "_type", "_code")
# EV's short names; an Omega column spells the word out, also when it holds an EV id.
ABBREVIATIONS = {"tns": "transaction", "txn": "transaction", "tty": "transaction_type", "sec": "security",
                 "prt": "portfolio", "usr": "user", "upd": "updated", "amt": "amount", "qty": "quantity",
                 "cur": "currency", "acct": "account", "desc": "description", "cnt": "count"}
PURPOSE_WORDS = ("purpose", "answers", "holds", "responsible")
DATA_FLOW = re.compile(r"^(?:#{3,6}\s+|\*\*)data flow[^\n]*\n(?P<rest>.*)", re.I | re.M | re.S)
FENCE = re.compile(r"```[^\n]*\n(?P<block>.*?)```", re.S)
# A CHECK on one value's range, like `CHECK > 0`, is fine; a CHECK on its own holds a list of values.
RANGE_CHECK = re.compile(r"check[^,]*?(?:[<>=]|\bbetween\b|\blike\b|\blen\b)")

SECTION = re.compile(r"^## (?P<name>[^\n]+?)\s*$(?P<body>.*?)(?=^## |\Z)", re.M | re.S)
TABLE_HEAD = re.compile(r"^(?:#{3,6}\s+|\*\*)`?(?P<name>\w+\.\w+)`?")
# A heading like "### om.request (one new column)" shows only what changes on an existing table.
PARTIAL = re.compile(r"\b(new columns?|changed)\b", re.I)
partial = set()


def cells(line):
    return [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]


def parse_tables(schema):
    """Each table heading in ## Schema with the rows of the first `| Column |` table under it."""
    tables, current, lines = {}, None, schema.splitlines()
    partial.clear()
    i = 0
    while i < len(lines):
        head = TABLE_HEAD.match(lines[i].strip())
        if head:
            current = head.group("name")
            if PARTIAL.search(lines[i]):
                partial.add(current)
        elif current and lines[i].strip().startswith("|") and cells(lines[i])[0].lower() == "column":
            header = [c.lower() for c in cells(lines[i])]
            rows = []
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = cells(lines[i])
                if not set("".join(row)) <= set("-: "):
                    rows.append(dict(zip(header, row)) | {"_samples": row[4:]})
                i += 1
            tables.setdefault(current, rows)
            current = None
            continue
        i += 1
    return tables


def is_vague(name):
    return name in VAGUE or name.endswith(VAGUE_ENDINGS)


def is_code(name):
    """A column that holds one of a set of codes: it needs a reference table."""
    return name == "status" or name.endswith(CODE_ENDINGS)


def finding(table, column, rule, do, message):
    return {"table": table, "column": column, "rule": rule, "do": do, "message": message}


def check_table(table, rows, audit):
    found, names = [], [r.get("column", "") for r in rows]
    for row in rows:
        name = row.get("column", "")
        typ, key = row.get("type", "").lower(), row.get("key", "").lower()
        if "kind" in name.split("_"):
            found.append(finding(table, name, "kind", "fix",
                                 "never `kind`: what sort of row it is, is a foreign key to a reference table, "
                                 "like `module_code` → `om.module`"))
        if "check" in key and not RANGE_CHECK.search(key):
            found.append(finding(table, name, "hardcoded-values", "fix",
                                 "no list of values in a CHECK: a foreign key to a reference table, like "
                                 "`module_code` → `om.module`, seeded by the same migration"))
        elif is_code(name) and "fk" not in key and "pk" not in key:
            found.append(finding(table, name, "code-without-reference", "fix",
                                 "a code column needs its reference table and a foreign key, like "
                                 "`module_code` → `om.module`"))
        if any(part in ABBREVIATIONS for part in name.split("_")):
            full = "_".join(ABBREVIATIONS.get(part, part) for part in name.split("_"))
            found.append(finding(table, name, "abbreviation", "fix",
                                 f"Omega spells words out, also for an EV id: `{full}`, not `{name}`"))
        if is_vague(name):
            found.append(finding(table, name, "vague-name", "fix",
                                 "a vague name: name what it holds, and two things are two columns"))
        if "json" in typ or "json" in key or any(s.startswith(("{", "[")) for s in row["_samples"]):
            found.append(finding(table, name, "json", "fix",
                                 "no JSON: each value gets its own column or a child table, or is read "
                                 "from the table that already holds it"))
        if name in TIME_NAMES or (name.endswith("_at") and name not in audit):
            found.append(finding(table, name, "time-name", "fix",
                                 f"the repo's audit columns are {', '.join(audit)}: created is the start, "
                                 f"updated is the end"))
    # A reference table is seeded by its migration, so it carries created_time only.
    reference = any(r.get("column") == "code" and "pk" in r.get("key", "").lower() for r in rows)
    for required in [] if table in partial else audit[1:2] if reference else audit[:2]:
        if required not in names:
            found.append(finding(table, required, "missing-audit", "fix",
                                 f"every table has {audit[0]} and {audit[1]}"))
    found += check_links(table, rows, names)
    return found


def check_links(table, rows, names):
    found = []
    by_name = {r.get("column", ""): r for r in rows}
    for name in names:
        stem = re.sub(r"_(type|type_code|kind)$", "", name)
        if stem != name and f"{stem}_id" in by_name and "fk" not in by_name[f"{stem}_id"].get("key", "").lower():
            found.append(finding(table, f"{stem}_id", "polymorphic", "ask",
                                 f"`{name}` + `{stem}_id` cannot carry a foreign key: ask the human, with a "
                                 f"real `<parent table>_id` foreign key as the other option"))
    has_type = any(n == "kind" or n.endswith(("_type", "_kind")) for n in names)
    nullable_ids = [r.get("column") for r in rows
                    if r.get("column", "").endswith("_id") and r.get("null", "").lower() in ("yes", "y", "null")]
    if has_type and len(nullable_ids) >= 2:
        found.append(finding(table, ", ".join(nullable_ids), "dual-purpose", "fix",
                             "one link table per thing you link to, each id NOT NULL, never a type column "
                             "saying which nullable id is filled"))
    return found


def explained_tables(schema):
    """First column of every `| Table | Holds | Answers | ...` table: the tables whose purpose is written down."""
    named, inside = set(), False
    for line in schema.splitlines():
        row = line.strip()
        if not row.startswith("|"):
            inside = False
            continue
        head = [c.lower() for c in cells(row)]
        if head[0] == "table" and any(w in " ".join(head) for w in PURPOSE_WORDS):
            inside = True
        elif inside and not set(head[0]) <= set("-: "):
            named.add(cells(row)[0])
    return named


def check_explained(schema, tables):
    found, named = [], explained_tables(schema)
    for name in tables:
        if name not in named and name.split(".", 1)[1] not in named:
            found.append(finding(name, "*", "missing-purpose", "fix",
                                 "the purpose table has no row for it: what it holds, the question it answers, "
                                 "when it is written and who reads it"))
    if tables and not has_flow_diagram(schema):
        found.append(finding("*", "*", "missing-data-flow", "fix",
                             "no `### Data flow` diagram: a box for each actor and route, `(table)` for each table, "
                             "and a labeled arrow for each write; lines of statements are not a diagram"))
    return found


def has_flow_diagram(schema):
    """A fenced block under `### Data flow` that draws boxes, tables and arrows."""
    heading = DATA_FLOW.search(schema)
    fence = FENCE.search(heading.group("rest")) if heading else None
    block = fence.group("block") if fence else ""
    return "┌" in block and "(" in block and any(a in block for a in "►▼◄▲")


def approval(schema, questions, tables):
    if re.search(r"^Approved:", schema, re.M):
        return "approved"
    if tables and all(t in questions or t.split(".", 1)[1] in questions for t in tables):
        return "asked"
    return "missing"


def check(text, audit=None):
    audit = audit or DEFAULT_AUDIT
    sections = {m.group("name").strip(): m.group("body") for m in SECTION.finditer(text)}
    if "Schema" not in sections:
        return {"tables": 0, "approval": "none", "findings": []}
    tables = parse_tables(sections["Schema"])
    findings = [f for name, rows in tables.items() for f in check_table(name, rows, audit)]
    findings += check_explained(sections["Schema"], list(tables))
    state = approval(sections["Schema"], sections.get("Questions", ""), list(tables))
    if state == "missing":
        findings.append(finding("*", "*", "approval", "ask",
                                "no question asks the human about this schema, and ## Schema has no "
                                "Approved: line"))
    return {"tables": len(tables), "approval": state, "findings": findings}


def main():
    args = sys.argv[1:]
    audit = None
    if "--audit" in args:
        at = args.index("--audit")
        audit = [a.strip() for a in args[at + 1].split(",")]
        del args[at:at + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    print(json.dumps(check(pathlib.Path(args[0]).read_text(), audit)))


if __name__ == "__main__":
    main()
