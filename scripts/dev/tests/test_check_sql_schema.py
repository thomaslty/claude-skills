"""Checks for ~/.claude/scripts/dev/check-sql-schema.py, which no repo tracks: these tests are its only check.

Run them with:
  python3 -m pytest -q ~/.claude/scripts/dev/tests/test_check_sql_schema.py
"""
import importlib.util
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "check-sql-schema.py"
spec = importlib.util.spec_from_file_location("check_sql_schema", SCRIPT)
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)

AUDIT = """| `created_by` | BIGINT | no | FK om.user | 990117750 | 990117750 |
| `created_time` | DATETIME2 | no | getutcdate() | 2026-11-04 15:57 | 2026-11-06 10:09 |"""

# The step table the contribution workflow plan first drew, before Thomas took it apart on 2026-11-10.
OLD_STEP = f"""## Schema

### om.workflow_step

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `id` | BIGINT identity | no | PK | 7 | 8 |
| `workflow_instance_id` | BIGINT | no | FK, UQ part | 1 | 1 |
| `outcome` | NVARCHAR(30) | yes | CHECK | pass | booked |
| `detail` | NVARCHAR(MAX) | yes | JSON | {{"rules":3,"pass":3}} | {{"tns_ids":[10701]}} |
| `actor_user_id` | BIGINT | yes | FK om.user | NULL | 990117750 |
| `started_time` | DATETIME2 | no | getutcdate() | 2026-11-04 15:57 | 2026-11-04 15:57 |
| `ended_time` | DATETIME2 | yes | | 2026-11-04 15:57 | 2026-11-06 10:09 |

## Files
"""

OLD_INSTANCE = f"""## Schema

### om.workflow_instance

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `id` | BIGINT identity | no | PK | 1 | 2 |
| `request_kind` | NVARCHAR(20) | no | UQ part, CHECK | contribution | contribution |
| `request_id` | BIGINT | no | UQ part | 1 | 14 |
{AUDIT}
"""

OLD_BOOKING = f"""## Schema

### om.workflow_booking

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `id` | BIGINT identity | no | PK | 1 | 2 |
| `kind` | NVARCHAR(20) | no | CHECK | deposit | buy_order |
| `tns_id` | INT | yes | | 10701 | NULL |
| `dealer_order_id` | INT | yes | | NULL | 1 |
{AUDIT}
"""

# The tables as Thomas renamed and normalized them on 2026-11-10, codes in reference tables, approved.
NEW = f"""## Schema

Approved: 2026-11-10, "yes to all"

| Table | Holds | Answers | Written when | Read by |
|---|---|---|---|---|
| `om.workflow_step` | one row per step, per try | Who did each step, when? | a step starts, ends | the map |
| `om.workflow_step_status` | the valid step states | Which states exist? | migration seed | foreign keys |
| `om.workflow_order` | each buy order placed | Which orders are C-14's? | Confirm deposit | step 6 check |

### Data flow

```
┌─────────────────────────┐
│ Dealer confirms deposit ├─┬─ INSERT 2 links ────► (workflow_order)
│ POST …/deposit-received │ └─ UPDATE, INSERT 3 ──► (workflow_step)
└─────────────────────────┘
```

### om.workflow_step — one row per step, per attempt

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `id` | BIGINT identity | no | PK | 7 | 8 |
| `workflow_id` | BIGINT | no | FK, UQ part | 2 | 2 |
| `step_code` | NVARCHAR(40) | no | FK om.workflow_step_code, UQ part | compliance_check | deposit_received |
| `status_code` | NVARCHAR(20) | no | FK om.workflow_step_status | done | done |
{AUDIT}
| `updated_by` | BIGINT | yes | FK om.user | 990117750 | 990117750 |
| `updated_time` | DATETIME2 | yes | | 2026-11-04 15:57 | 2026-11-06 10:09 |

### om.workflow_step_status — reference table

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `code` | NVARCHAR(20) | no | PK | current | done |
| `label_en` | NVARCHAR(100) | no | | Current | Done |
| `label_fr` | NVARCHAR(100) | no | | En cours | Terminée |
| `created_time` | DATETIME2 | no | getutcdate() | 2026-11-10 09:00 | 2026-11-10 09:00 |

**om.workflow_order**

| Column | Type | Null | Key | Row 1 | Row 2 |
|---|---|---|---|---|---|
| `id` | BIGINT identity | no | PK | 1 | 2 |
| `workflow_id` | BIGINT | no | FK, UQ part | 2 | 2 |
| `dealer_order_id` | INT | no | UQ part | 1 | 2 |
| `model_weight` | DECIMAL(9,6) | yes | | 40.000000 | 60.000000 |
| `amount` | DECIMAL(18,2) | no | CHECK > 0 | 2400.00 | 3600.00 |
| `data_extract_id` | INT | yes | FK om.data_extract | 4 | 4 |
{AUDIT}
"""


def rules(text):
    return sorted((f["column"], f["rule"], f["do"]) for f in schema.check(text)["findings"])


def test_old_step_table_breaks_every_rule_thomas_named():
    found = rules(OLD_STEP)
    assert ("outcome", "vague-name", "fix") in found
    assert ("detail", "vague-name", "fix") in found
    assert ("detail", "json", "fix") in found
    assert ("started_time", "time-name", "fix") in found
    assert ("ended_time", "time-name", "fix") in found
    assert ("created_by", "missing-audit", "fix") in found
    assert ("created_time", "missing-audit", "fix") in found


def test_kind_is_a_fix_and_its_pair_with_id_is_an_ask():
    found = rules(OLD_INSTANCE)
    assert ("request_kind", "kind", "fix") in found
    assert ("request_id", "polymorphic", "ask") in found


def test_type_and_id_pair_with_a_foreign_key_is_fine():
    text = OLD_INSTANCE.replace("request_kind", "request_type").replace(
        "| `request_id` | BIGINT | no | UQ part |", "| `request_id` | BIGINT | no | FK, UQ part |")
    assert [f for f in rules(text) if f[1] in ("kind", "polymorphic")] == []


def test_one_booking_table_with_a_kind_and_two_nullable_ids_is_dual_purpose():
    found = rules(OLD_BOOKING)
    assert ("kind", "kind", "fix") in found
    assert ("tns_id, dealer_order_id", "dual-purpose", "fix") in found


def test_json_is_caught_by_its_sample_value_too():
    text = OLD_BOOKING.replace("| `kind` | NVARCHAR(20) | no | CHECK | deposit | buy_order |",
                               "| `fund_lines` | NVARCHAR(MAX) | yes | | [\"5000F\"] | NULL |")
    assert ("fund_lines", "json", "fix") in rules(text)


def test_the_approved_normalized_tables_are_clean():
    result = schema.check(NEW)
    assert result == {"tables": 3, "approval": "approved", "findings": []}


def test_a_name_that_only_starts_with_data_is_not_vague():
    assert not schema.is_vague("data_extract_id")
    assert schema.is_vague("payload") and schema.is_vague("detail_json")


def test_approval_is_asked_when_questions_name_every_table():
    text = OLD_BOOKING + "\n## Questions\n\n### Q3. Do you approve `om.workflow_booking`?\n"
    result = schema.check(text)
    assert result["approval"] == "asked"
    assert "approval" not in [f["rule"] for f in result["findings"]]


def test_approval_missing_is_an_ask():
    result = schema.check(OLD_BOOKING + "\n## Questions\n\n### Q1. Map or list?\n")
    assert result["approval"] == "missing"
    assert ("*", "approval", "ask") in [(f["column"], f["rule"], f["do"]) for f in result["findings"]]


def test_a_plan_with_no_schema_has_nothing_to_check():
    assert schema.check("# Plan\n\n## Goal\nSomething\n") == {"tables": 0, "approval": "none", "findings": []}


def test_another_repo_passes_its_own_audit_names(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(NEW.replace("created_by", "add_user").replace("created_time", "add_time"))
    out = subprocess.run([sys.executable, str(SCRIPT), str(plan), "--audit", "add_user,add_time"],
                         capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(out.stdout)["findings"] == []


def test_a_check_with_a_list_of_values_is_a_fix():
    assert ("kind", "hardcoded-values", "fix") in rules(OLD_BOOKING)
    assert ("outcome", "hardcoded-values", "fix") in rules(OLD_STEP)


def test_a_range_check_on_one_value_is_fine():
    assert "amount" not in [f[0] for f in rules(NEW)]


def test_a_code_column_with_no_reference_table_is_a_fix():
    plain = OLD_INSTANCE.replace("| `request_id` |",
                                 "| `status` | NVARCHAR(20) | no | | open | open |\n| `request_id` |")
    assert ("status", "code-without-reference", "fix") in rules(plain)
    referenced = plain.replace("| `status` | NVARCHAR(20) | no | |", "| `status` | NVARCHAR(20) | no | FK om.workflow_status |")
    assert "code-without-reference" not in [f[1] for f in rules(referenced) if f[0] == "status"]


def test_a_reference_table_needs_created_time_but_not_created_by():
    found = rules(NEW.replace("| `created_time` | DATETIME2 | no | getutcdate() | 2026-11-10 09:00 | 2026-11-10 09:00 |\n", ""))
    assert ("created_time", "missing-audit", "fix") in found
    assert ("created_by", "missing-audit", "fix") not in found


def test_ev_short_names_get_their_full_omega_names():
    text = OLD_BOOKING.replace("`tns_id`", "`tns_id`").replace("| `kind` |", "| `sec_id` | INT | no | | 2 | 2 |\n| `kind` |")
    found = schema.check(text)["findings"]
    short = {f["column"]: f["message"] for f in found if f["rule"] == "abbreviation"}
    assert "`transaction_id`" in short["tns_id"] and "`security_id`" in short["sec_id"]
    assert "abbreviation" not in [f["rule"] for f in schema.check(NEW)["findings"]]


def test_every_table_needs_a_row_in_the_purpose_table():
    text = NEW.replace("| `om.workflow_order` | each buy order placed | Which orders are C-14's? | Confirm deposit | step 6 check |\n", "")
    assert ("*", "missing-purpose", "fix") in [(f["column"], f["rule"], f["do"]) for f in schema.check(text)["findings"]
                                               if f["table"] == "om.workflow_order"]


def test_a_seeded_rows_table_is_not_a_purpose_table():
    text = NEW.replace("| Table | Holds | Answers | Written when | Read by |", "| Table | code | label_en | label_fr | x |")
    assert len([f for f in schema.check(text)["findings"] if f["rule"] == "missing-purpose"]) == 3


def test_a_schema_with_no_data_flow_heading_is_a_fix():
    text = NEW.replace("### Data flow", "### Notes")
    assert ("*", "missing-data-flow", "fix") in rules(text)


def test_lines_of_statements_are_not_a_flow_diagram():
    statements = """```
2 Dealer clicks Confirm deposit   POST /api/dealer/workflow/contribution/14/deposit-received
   om.workflow_step    UPDATE  deposit_received  current -> done
   om.workflow_order   INSERT  workflow 2 -> order 1, weight 40
```"""
    start = NEW.index("```", NEW.index("### Data flow"))
    end = NEW.index("```", start + 3) + 3
    assert ("*", "missing-data-flow", "fix") in rules(NEW[:start] + statements + NEW[end:])
