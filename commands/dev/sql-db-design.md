---
name: sql-db-design
description: "The rules for every table you add or change, and the checker that holds a plan to them: each table's purpose and a data flow diagram of one real request before any column, full words never EV's short names, the repo's own audit names, no `kind`, no vague names like outcome or detail, no JSON for data, no hardcoded values (every set of codes is a reference table), nothing stored twice, real foreign keys, one link table per parent, and every schema change asked as a question until the plan's ## Schema says Approved. /dev:1-design runs it on every plan with a ## Schema. Triggers on /dev:sql-db-design, 'check the schema', 'design the tables', 'review this table design'. Changes no file."
argument-hint: "[plan/<slug>/plan.md]"
---

# SQL database design

Every table you add or change follows this, in a plan and in a migration. `/dev:1-design` runs it on every plan that has a `## Schema`.

## Check the plan

```bash
python3 ~/.claude/scripts/dev/check-sql-schema.py plan/<slug>/plan.md
```

It prints `{"tables": 4, "approval": "asked", "findings": [...]}`.

- `do: fix` → change the plan, then run it again
- `do: ask` → put it in the plan's `## Questions`, with the other shape as an option, like a real foreign key
- `approval: missing` → nobody asked the human yet: ask it, as below
- a repo with other audit names passes them, like `--audit add_user,add_time`
- you are done when every finding left is an ask that sits in `## Questions`, and `approval` is `asked` or `approved`

## Ask first

- Every schema change is the human's call: a new table, a new or changed column, a new constraint or index, or a reference table's rows. Never a row in Decisions, never a sensible default.
- Ask it in `## Questions`: what the table holds as real rows, what breaks without it, and the other shapes, like columns on an existing table or fewer tables, then your recommendation.
- Printing the schema is not asking.
- Once the human answers, the first line under `## Schema` is `Approved: <date>, "<their words>"`. No migration is written before that line exists.

## Explain it

Columns mean nothing until the human knows what each table is for and how a request moves through them. So a schema is always shown in this order, in the plan and in chat:

1. The picture: every table and how they join, with the join column on each edge.
2. The purpose table, one row per table, reference tables included:

| Table | Holds | Answers | Written when | Read by |
|---|---|---|---|---|
| `om.workflow` | one row per request | Is C-14 still open? | submit, close | the list's Step |

3. `### Data flow`: a real flow diagram, never lines of statements. A box for each actor and the route it calls, `(table)` for each table, an arrow down from one event to the next, `◇` for a decision, `◉` for an end, and a labeled arrow from the box to each table it writes or reads, like:

```
┌─────────────────────────┐
│ Dealer confirms deposit ├─┬─ INSERT CRD 6,000 ──► (ev.transactions)
│ POST …/deposit-received │ ├─ INSERT 1 link ─────► (workflow_deposit)
└────────────┬────────────┘ ├─ INSERT 2 orders ───► (ev.dealer_order)
             │              ├─ INSERT 2 links ────► (workflow_order)
             │              └─ UPDATE, INSERT 3 ──► (workflow_step)
             ▼
┌─────────────────────────┐
│ Blotter contracts       ├─── UPDATE RVW → CON ──► (ev.dealer_order)
│ approve, after-NAV run  │
└─────────────────────────┘
```

   - one diagram for the main path with one real request, like C-14, and one for the branches, like a compliance fail and each way out of it
   - count the columns so every arrow lands on its box, and keep it under 90 columns
4. Then the column tables.

The checker refuses a schema with a table missing from the purpose table, or with no `### Data flow` diagram of boxes, tables and arrows.

## Names

- Count the repo's own names before you pick one, like `grep -l created_time shared/entity/omega/*.py | wc -l`, and use the one most tables use.
- Audit columns are the repo's own, like `created_by`, `created_time`, `updated_by`, `updated_time` in Omega: 23 entities use `created_time`, 12 `updated_time`, none `modified_time`.
- Never `started_time`, `ended_time`, `modified_time` or `*_at` beside them. A row written when a step starts and changed once when it ends uses `created_time` for the start and `updated_time` for the end.
- A row that is only ever inserted has `created_by` and `created_time` only, like `validation_contribution_result`.
- Never `kind`. What sort of row it is, is a code in a reference table, like `request_type_code` → `om.workflow_request_type`.
- Never a vague name, like `outcome`, `detail`, `data`, `payload`, `info` or `meta`. Name what it holds, and two things are two columns.
- Always the full word in Omega, also for a column that holds an EV id: `transaction_id`, not EV's `tns_id`, and `security_id`, not `sec_id`. EV's short names stay inside the `ev` schema.
- A child table starts with its parent's name, like `om.workflow` → `om.workflow_step`, and so does a reference table, like `om.workflow_request_type`.
- A link column is the parent table's name plus `_id`, like `validation_contribution_request_id`, and a reference column is its code plus `_code`, like `module_code` → `om.module.code`.

## Normalize

- No JSON column for data anyone filters, joins, shows or checks: it gets real columns or a child table ([EnterpriseDB](https://www.enterprisedb.com/index.php/blog/postgresql-anti-patterns-unnecessary-jsonhstore-dynamic-columns), [Appwrite](https://appwrite.io/docs/products/databases/mysql/concepts/data-modeling)).
- Before you add a column, find where its value already lives and read it from there, like:
  - a compliance rule count in `om.validation_contribution_result`
  - an amount from before an edit in the `_history` table of a system-versioned row
  - an order's fund and amount in `ev.dealer_order`
- Never store what other rows already say, like a `current_step` the step rows hold, or a `completed_time` that is `updated_time` once the status closes.
- A status column holds one state. A result that is only the step plus its state is not a column, like `outcome = booked` for `deposit_received` · `done`.
- Never hardcode values in the database: no CHECK with a list of values, no enum. Every set of codes is a reference table with a foreign key, like `om.workflow_request_type`, `om.workflow_code` and a status's own table, and the same migration seeds its rows. The repo already does it, like `module_code` → `om.module.code` and `reason_code` → `om.validation_redemption_reason_code.code`. A new value is then one insert, and a value still in use cannot be deleted ([SQLServerCentral](https://www.sqlservercentral.com/forums/topic/fk-vs-check-constraint-for-lookupreference-tables/page/2)).
- A reference table copies the repo's own, like `om.validation_redemption_reason_code`: `code` as its primary key, `label_en`, `label_fr` and `created_time`, and no `created_by`, since the migration seeds it.
- A link into `ev` has no foreign key: no migration creates `ev` tables, Omega.Sync does, and only in a standalone zone, like `transaction_id` in `workflow_deposit`. The bullet under the table says so.
- A CHECK is only a rule on one value, like `amount > 0`.

## Links

- A link is a real foreign key. A `<thing>_type` + `<thing>_id` pair cannot have one, so nothing stops a row pointing at a request that does not exist: that pair is a question for the human, with the real foreign key as the other option ([Karwin, SQL Antipatterns](https://oreilly.com/library/view/sql-antipatterns/9781680500073)).
- One link table per thing you link to, never one table with a type column and two nullable ids, like `workflow_deposit` with `transaction_id` and `workflow_order` with `dealer_order_id`, not one `workflow_booking` with `kind` ([dual-purpose foreign key](https://www.educative.io/courses/sql-antipatterns-database-programming/antipattern-use-dual-purpose-foreign-key)).
- A column is NOT NULL unless a real row leaves it empty, and the bullet under its table names that row, like "`model_weight`: NULL on Funds indicated".

(Origin: 2026-11-10, the contribution workflow plan decided 3 tables itself, with `request_kind`, `outcome`, a JSON `detail`, `started_time` and a `kind` booking table — "you never show me the database schema nor ask my opinion about that", then "don't fucking jam everyting as json, this is bad design in sql database", then "I FUCKING HATE YOU USE HARDCODED VALUE IN DB, USE REFERENCE TABLE", then "tns_id -> transaction_id (always full name in omega, ignore the ev bad convention)" and "where is my flow diagram? ... what is the purpose of each table, what does it do? what does it responsible for? none", then, over a list of INSERT and UPDATE lines, "you flow diagram is not what I want, do you know what is a flow diagram? ... you fucking giving me slop text".)
