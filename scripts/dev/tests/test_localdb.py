"""Checks for ~/.claude/scripts/dev/localdb.py, which no repo tracks: these tests are its only check.

Run them with:
  uv run --with pytest==9.1.1 --with pyodbc pytest -q ~/.claude/scripts/dev/tests/test_localdb.py

The delta tests clone between two scratch databases, zz_delta_source and zz_delta_copy, on a local
SQL Server, 127.0.0.1,1437 or LOCALDB_TEST_PORT, write nowhere else, and drop both at the end.
With no server on that port they are skipped.
"""
import importlib.util
import os
import pathlib
import re
import signal
import subprocess
import sys
from decimal import Decimal

import pyodbc
import pytest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("localdb", HERE.parent / "localdb.py")
localdb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(localdb)

# What a copy of dev5's omega database holds: 105 tables outside ev, 1,465 in ev.
OMEGA = [("om", f"table_{n:03}") for n in range(105)]
EV = [("ev", f"table_{n:04}") for n in range(1465)]
LOCAL = [("local", "sync_run"), ("local", "sync_step"), ("local", "sync_status")]

# The menu's count line, from omega_cli/omega_cli/progress.py in the plan's Code structure.
COUNT = re.compile(r"^\s+(?P<done>\d+)/(?P<total>\d+) (?P<unit>tables|files)(?:\s+(?P<item>\S+))?"
                   r"(?:\s+(?P<changed>\d+) changed)?$")


def test_fresh_copies_every_table():
    plan = localdb.plan_tables(OMEGA + EV, {}, set(), resume=False)
    assert plan == {"copy": OMEGA + EV, "redo": [], "keep": [], "skip": []}

    # A fresh run never reads an old status, even when one is passed.
    stale = {table: "done" for table in OMEGA}
    assert localdb.plan_tables(OMEGA + EV, stale, set(), resume=False)["copy"] == OMEGA + EV


def test_fresh_omega_only_skips_ev():
    plan = localdb.plan_tables(OMEGA + EV, {}, {"ev"}, resume=False)
    assert (len(plan["copy"]), len(plan["skip"])) == (105, 1465)
    assert plan["copy"] == OMEGA and plan["skip"] == EV
    assert plan["keep"] == plan["redo"] == []


def test_resume_keeps_done_tables():
    status = {**{table: "done" for table in OMEGA[:61]}, **{table: "skipped" for table in EV}}
    plan = localdb.plan_tables(OMEGA + EV, status, {"ev"}, resume=True)
    assert (len(plan["keep"]), len(plan["copy"]), len(plan["skip"])) == (61, 44, 1465)
    assert plan["keep"] == OMEGA[:61] and plan["copy"] == OMEGA[61:]

    # An ev table copied by an earlier omega + ev run keeps its rows on an omega only resume.
    status[EV[0]] = "done"
    plan = localdb.plan_tables(OMEGA + EV, status, {"ev"}, resume=True)
    assert EV[0] in plan["keep"] and EV[0] not in plan["skip"]


def test_resume_redoes_copying_and_failed():
    status = {**{table: "done" for table in OMEGA[:61]}, OMEGA[61]: "copying", OMEGA[62]: "failed"}
    plan = localdb.plan_tables(OMEGA, status, set(), resume=True)
    assert plan["redo"] == [OMEGA[61], OMEGA[62]]
    assert (len(plan["keep"]), len(plan["copy"])) == (61, 42)

    # Not on a fresh run: everything is copied, nothing is redone.
    assert localdb.plan_tables(OMEGA, status, set(), resume=False)["redo"] == []


def test_resume_with_ev_copies_skipped_ev():
    status = {**{table: "done" for table in OMEGA[:61]}, **{table: "skipped" for table in EV}}
    plan = localdb.plan_tables(OMEGA + EV, status, set(), resume=True)
    assert (len(plan["keep"]), len(plan["copy"]), len(plan["skip"])) == (61, 1509, 0)
    assert plan["copy"] == OMEGA[61:] + EV


def test_local_schema_is_never_copied():
    status = {LOCAL[0]: "copying", LOCAL[1]: "done", LOCAL[2]: "failed"}
    for skip in (set(), {"ev"}, {"local"}):
        for resume in (False, True):
            plan = localdb.plan_tables(LOCAL + OMEGA[:3] + EV[:3], status, skip, resume=resume)
            listed = [table for tables in plan.values() for table in tables]
            assert not [table for table in listed if table[0] == "local"], (skip, resume, plan)
            assert len(listed) == 6


def test_count_line_names_each_table():
    line = localdb.count_line(212, 1509, "ev", "dealer_institution")
    assert line == "  212/1509 tables  ev.dealer_institution"
    match = COUNT.match(line)
    assert match and match["done"] == "212" and match["total"] == "1509"
    assert match["item"] == "ev.dealer_institution" and match["changed"] is None

    line = localdb.count_line(212, 1570, "ev", "trade_order", changed=41)
    assert line == "  212/1570 tables  ev.trade_order  41 changed"
    match = COUNT.match(line)
    assert match and match["item"] == "ev.trade_order" and match["changed"] == "41"

    # A table with no rows still gets its line, so the bar moves on every table.
    assert COUNT.match(localdb.count_line(1, 105, "om", "empty_table", changed=0))["changed"] == "0"


# Columns as dev1's catalogue gave them on 2026-11-03, read only: (name, type, is_identity, generated_always_type).
TRANSACTIONS = [("tenant_id", "int", False, 0), ("tns_id", "int", False, 0), ("trade_date", "datetime", False, 0),
                ("upd_datetime", "datetime", False, 0), ("upd_timestamp", "timestamp", False, 0),
                ("ValidFrom", "datetime2", False, 1), ("ValidTo", "datetime2", False, 2)]
IMPORT_STAGING_ROW = [("id", "bigint", True, 0), ("import_staging_id", "bigint", False, 0),
                      ("is_valid", "bit", False, 0), ("row_index", "int", False, 0),
                      ("created_time", "datetime2", False, 0), ("updated_time", "datetime2", False, 0)]
COMPLIANCE_RULE = [("id", "bigint", True, 0), ("rule", "nvarchar", False, 0),
                   ("updated_datetime", "datetime2", False, 0), ("tenant_id", "int", False, 0),
                   ("ValidFrom", "datetime2", False, 1), ("ValidTo", "datetime2", False, 2)]
TOKEN_WALLET_TRANSACTION = [("id", "bigint", True, 0), ("wallet_id", "int", False, 0), ("tx_hash", "nchar", False, 0),
                            ("block_time", "datetime2", False, 0), ("created_time", "datetime2", False, 0)]
VALIDATION_DOMAIN = [("id", "int", False, 0), ("code", "nvarchar", False, 0), ("name", "nvarchar", False, 0),
                     ("engine", "nvarchar", False, 0), ("account_type_code", "nvarchar", False, 0)]


def test_rowversion_table_is_rowversion():
    # ev.transactions: 41,288,761 rows, a primary key, upd_timestamp, and a ValidFrom it does not need.
    assert localdb.change_method(TRANSACTIONS, True, 41_288_761, 100_000) == "rowversion"
    assert localdb.watermarks("rowversion", TRANSACTIONS) == {"watermark_rv"}


def test_updated_time_table_also_takes_new_ids():
    # om.import_staging_row: updated_time is nullable, so a new row comes by its id past the last one.
    assert localdb.change_method(IMPORT_STAGING_ROW, True, 54_776, 100_000) == "updated_time"
    assert localdb.watermarks("updated_time", IMPORT_STAGING_ROW) == {"watermark_time", "watermark_id"}
    no_identity = [(name, kind, False, generated) for name, kind, _, generated in IMPORT_STAGING_ROW]
    assert localdb.change_method(no_identity, True, 54_776, 100_000) == "updated_time"
    assert localdb.watermarks("updated_time", no_identity) == {"watermark_time"}


def test_valid_from_when_no_updated_time():
    # om.compliance_rule: updated_datetime is not updated_time, so its ValidFrom finds the changes.
    assert localdb.change_method(COMPLIANCE_RULE, True, 4_616, 100_000) == "valid_from"
    assert localdb.watermarks("valid_from", COMPLIANCE_RULE) == {"watermark_time"}


def test_big_identity_table_is_new_rows_only():
    # om.token_wallet_transaction: 2,594,285 rows, an identity and no column that moves on an edit.
    assert localdb.change_method(TOKEN_WALLET_TRANSACTION, True, 2_594_285, 100_000) == "identity"
    assert localdb.watermarks("identity", TOKEN_WALLET_TRANSACTION) == {"watermark_id"}
    # Held whole, it is cheaper to copy it again than to miss an edit.
    assert localdb.change_method(TOKEN_WALLET_TRANSACTION, True, 100_000, 100_000) == "full"


def test_no_key_is_full():
    # om.validation_domain: 6 rows, no identity, no column that moves on a change.
    assert localdb.change_method(VALIDATION_DOMAIN, True, 6, 100_000) == "full"
    assert localdb.watermarks("full", VALIDATION_DOMAIN) == set()
    # With no primary key an edited row cannot replace the old one, whatever column moves.
    for columns in (TRANSACTIONS, IMPORT_STAGING_ROW, COMPLIANCE_RULE):
        assert localdb.change_method(columns, False, 4_616, 100_000) == "full"


def test_delta_plan_checks_done_tables_and_copies_the_rest():
    tables = [("om", "kept"), ("om", "edited_columns"), ("om", "small"), ("om", "stopped"), ("om", "new"),
              ("ev", "skipped"), ("ev", "done_before"), ("om", "now_with_ev")] + LOCAL
    row = {"status": "done", "method": "rowversion", "columns_hash": 7}
    status = {("om", "kept"): row, ("om", "edited_columns"): row, ("om", "small"): {**row, "method": "full"},
              ("om", "stopped"): {**row, "status": "copying"}, ("ev", "skipped"): {**row, "status": "skipped"},
              ("ev", "done_before"): row, ("om", "now_with_ev"): {**row, "status": "skipped"}}
    hashes = {table: 7 for table in tables} | {("om", "edited_columns"): 8}
    plan = localdb.plan_delta(tables, status, hashes, {"ev"})
    assert plan == {"check": [("om", "kept")],
                    "full": [("om", "edited_columns"), ("om", "small"), ("om", "stopped"), ("om", "new"),
                             ("om", "now_with_ev")],
                    "keep": [("ev", "done_before")],
                    "skip": [("ev", "skipped")]}


def test_delta_leaves_alembic_version_out_while_the_schema_is_kept():
    # The copy's own revision: your branch may have upgraded it past DEV's, like 0048 over DEV's 0047.
    tables = [("om", "alembic_version"), ("dbo", "alembic_version"), ("om", "tenant")] + LOCAL
    row = {"status": "done", "method": "full", "columns_hash": 7, "run_id": 1}
    status = {table: row for table in tables}
    hashes = {table: 7 for table in tables}
    assert localdb.plan_delta(tables, status, hashes, set(), schema_run=1) == {
        "check": [], "full": [("om", "tenant")], "keep": [], "skip": []}
    # A delta never publishes over the copy any more, so no run brings DEV's revision over your branch's.
    assert localdb.plan_delta(tables, status, hashes, set(), schema_run=2)["full"] == [("om", "tenant")]
    # A fresh copy and Continue still copy it: the copy has no revision of its own yet.
    assert ("om", "alembic_version") in localdb.plan_tables(tables, {}, set(), resume=False)["copy"]


def test_delta_never_plans_an_alembic_version():
    # 2026-11-09: a revision only your branch ran, 0052, was overwritten by DEV's; a delta never touches it now.
    tables = [("om", "alembic_version"), ("dbo", "alembic_version"), ("ev", "alembic_version"),
              ("audit", "alembic_version"), ("om", "tenant")] + LOCAL
    row = {"status": "done", "method": "full", "columns_hash": 7}
    status = {("om", "alembic_version"): {**row, "run_id": 1}, ("dbo", "alembic_version"): {**row, "run_id": 4},
              ("ev", "alembic_version"): {**row, "status": "copying", "run_id": 4}, ("om", "tenant"): {**row, "run_id": 1}}
    hashes = {table: 7 for table in tables}
    assert localdb.plan_delta(tables, status, hashes, set(), schema_run=4) == {
        "check": [], "full": [("om", "tenant")], "keep": [], "skip": []}


PORT = int(os.environ.get("LOCALDB_TEST_PORT", "1437"))
SOURCE, COPY = "zz_delta_source", "zz_delta_copy"


def on_source(sql, *params):
    connection = localdb.local(PORT, SOURCE)
    cursor = connection.execute(sql, *params)
    return cursor.fetchall() if cursor.description else None


def on_copy(sql, *params):
    return localdb.local(PORT, COPY).execute(sql, *params).fetchall()


@pytest.fixture(scope="module")
def scratch(tmp_path_factory):
    """A source with one table per way Delta finds a change, cloned fresh into the copy; both dropped at the end."""
    try:
        localdb.local(PORT).close()
    except pyodbc.Error:
        pytest.skip(f"no SQL Server on {localdb.HOST},{PORT}; start this worktree's mssql first")
    for db in (SOURCE, COPY):
        localdb.drop_database(PORT, db)
    localdb.local(PORT).execute(f"CREATE DATABASE {SOURCE}")
    for sql in (
            "CREATE SCHEMA om", "CREATE SCHEMA ev",
            "CREATE TABLE ev.trade (trade_id INT PRIMARY KEY, amount DECIMAL(18, 2) NOT NULL, upd_timestamp ROWVERSION)",
            "CREATE TABLE om.item (id INT IDENTITY PRIMARY KEY, name NVARCHAR(50) NOT NULL, updated_time DATETIME2 NULL)",
            "CREATE TABLE om.[rule] (id INT IDENTITY PRIMARY KEY, body NVARCHAR(50) NOT NULL, "
            "ValidFrom DATETIME2 GENERATED ALWAYS AS ROW START NOT NULL, "
            "ValidTo DATETIME2 GENERATED ALWAYS AS ROW END NOT NULL, PERIOD FOR SYSTEM_TIME (ValidFrom, ValidTo)) "
            "WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = om.rule_history))",
            "CREATE TABLE om.wallet_tx (id BIGINT IDENTITY PRIMARY KEY, amount INT NOT NULL)",
            "CREATE TABLE om.domain (code NVARCHAR(20) NOT NULL, name NVARCHAR(50) NOT NULL)",
            "CREATE TABLE om.alembic_version (version_num VARCHAR(32) NOT NULL "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY)",
            "INSERT INTO om.alembic_version (version_num) VALUES ('0047')",
            "INSERT INTO ev.trade (trade_id, amount) VALUES (1, 10.50), (2, 20.25)",
            "INSERT INTO om.item (name, updated_time) VALUES (N'first', DATEADD(HOUR, -1, SYSUTCDATETIME())), "
            "(N'second', NULL)",
            "INSERT INTO om.[rule] (body) VALUES (N'cap 7000'), (N'cap 9000')",
            "INSERT INTO om.wallet_tx (amount) SELECT TOP (12) 1 FROM sys.all_columns",
            "INSERT INTO om.domain (code, name) VALUES (N'tfsa', N'TFSA'), (N'rrsp', N'RRSP')"):
        on_source(sql)
    folder = tmp_path_factory.mktemp("env")
    env = folder / ".env.local.zz_delta"
    env.write_text(f"DB_PARAMS='user=sa;host={localdb.HOST},{PORT};db={SOURCE}'\nDB_PASSWORD='{localdb.PASSWORD}'\n")
    other = folder / ".env.local.zz_other"
    other.write_text(f"DB_PARAMS='user=sa;host={localdb.HOST},{PORT};db=zz_delta_elsewhere'\n"
                     f"DB_PASSWORD='{localdb.PASSWORD}'\n")

    def command(*arguments, source=env):
        # --max-rows 10 by default, so the 12-row wallet_tx is cut and finds new rows by its id.
        if "--max-rows" not in arguments:
            arguments += ("--max-rows", "10")
        return [sys.executable, str(HERE.parent / "localdb.py"), "clone", COPY, "--from", str(source),
                "--port", str(PORT), *arguments]

    def clone(*arguments, source=env):
        out = subprocess.run(command(*arguments, source=source), capture_output=True, text=True, timeout=240)
        # A table that fails prints a FAILED line and the run still ends 0; no test here expects one.
        assert "  FAILED " not in out.stdout, out.stdout
        return out.returncode, out.stdout + out.stderr

    code, output = clone("--replace")
    assert code == 0, output
    yield {"clone": clone, "command": command, "other": other}
    for db in (SOURCE, COPY):
        localdb.drop_database(PORT, db)
    for name in localdb.backups(PORT, COPY):
        localdb.in_container(PORT, "rm", "-f", f"{localdb.BACKUPS}/{name}")


def changed(output, table):
    """The `K changed` of a table's count line, or None when the line has none."""
    for line in output.splitlines():
        match = COUNT.match(line)
        if match and match["item"] == table:
            return None if match["changed"] is None else int(match["changed"])
    raise AssertionError(f"no count line for {table} in:\n{output}")


def test_every_copy_writes_its_method_and_watermark(scratch):
    rows = {(schema, table): (method, rv, time, ident) for schema, table, method, rv, time, ident in on_copy(
        "SELECT table_schema, table_name, method, watermark_rv, watermark_time, watermark_id FROM local.sync_status "
        "WHERE status = N'done'")}
    assert {key: value[0] for key, value in rows.items()} == {
        ("ev", "trade"): "rowversion", ("om", "item"): "updated_time", ("om", "rule"): "valid_from",
        ("om", "wallet_tx"): "identity", ("om", "domain"): "full", ("om", "alembic_version"): "full"}
    assert rows["ev", "trade"][1] is not None
    assert rows["om", "item"][2] is not None and rows["om", "item"][3] == 2
    assert rows["om", "rule"][2] is not None
    assert rows["om", "wallet_tx"][3] == 12
    hash_row = on_copy("SELECT source_schema_hash FROM local.sync_step WHERE step = N'schema'")
    assert hash_row[0][0] is not None


def test_delta_keeps_the_copys_alembic_version(scratch):
    # Your branch upgraded the copy to 0048; DEV is still on 0047.
    assert on_copy("SELECT version_num FROM om.alembic_version")[0][0] == "0047"
    localdb.local(PORT, COPY).execute("UPDATE om.alembic_version SET version_num = '0048'")
    code, output = scratch["clone"]("--delta")
    assert code == 0, output
    assert [tuple(row) for row in on_copy("SELECT version_num FROM om.alembic_version")] == [("0048",)]
    assert "om.alembic_version" not in output, output  # never checked, so no count line


def test_delta_brings_a_new_row(scratch):
    on_source("INSERT INTO ev.trade (trade_id, amount) VALUES (3, 30.00)")
    # No updated_time: it comes by its id past the last one.
    on_source("INSERT INTO om.item (name, updated_time) VALUES (N'third', NULL)")
    on_source("INSERT INTO om.wallet_tx (amount) VALUES (5)")
    code, output = scratch["clone"]("--delta")
    assert code == 0, output
    assert re.search(r"^  schema: kept, same as DEV since run \d+$", output, re.M), output
    assert re.search(r"^  rows: 5 tables to check, 1 to copy in full$", output, re.M), output
    # Exact where no margin applies; updated_time and valid_from read 5 minutes back, so they may bring more.
    assert (changed(output, "ev.trade"), changed(output, "om.wallet_tx")) == (1, 1)
    assert changed(output, "om.item") >= 1
    assert on_copy("SELECT amount FROM ev.trade WHERE trade_id = 3")[0][0] == 30
    assert on_copy("SELECT COUNT(*) FROM om.item WHERE name = N'third'")[0][0] == 1
    assert on_copy("SELECT COUNT(*) FROM om.wallet_tx")[0][0] == 11
    assert re.search(r"^  delta: \d+ rows changed in \d+ tables, 1 copied in full, 0 differ from DEV$",
                     output, re.M), output
    # Nothing new on DEV: the next one finds nothing where no margin applies.
    code, output = scratch["clone"]("--delta")
    assert code == 0, output
    assert (changed(output, "ev.trade"), changed(output, "om.wallet_tx")) == (0, 0)


def test_delta_brings_an_edited_row(scratch):
    on_source("UPDATE ev.trade SET amount = 99.99 WHERE trade_id = 1")
    on_source("UPDATE om.item SET name = N'first, edited', updated_time = SYSUTCDATETIME() WHERE name = N'first'")
    on_source("UPDATE om.[rule] SET body = N'cap 7500' WHERE body = N'cap 7000'")
    code, output = scratch["clone"]("--delta")
    assert code == 0, output
    assert changed(output, "ev.trade") == 1
    assert changed(output, "om.item") >= 1 and changed(output, "om.rule") >= 1
    assert on_copy("SELECT amount FROM ev.trade WHERE trade_id = 1")[0][0] == Decimal("99.99")
    assert on_copy("SELECT name FROM om.item WHERE id = 1")[0][0] == "first, edited"
    assert on_copy("SELECT body FROM om.[rule] WHERE id = 1")[0][0] == "cap 7500"
    # Replaced by its key, never added twice.
    for table in ("ev.trade", "om.item", "om.[rule]"):
        assert on_copy(f"SELECT COUNT(*) FROM {table}") == on_source(f"SELECT COUNT(*) FROM {table}")


def test_delta_keeps_a_row_dev_deleted(scratch):
    # A row only the copy holds looks the same as one DEV deleted; the delta keeps it and says so.
    on_source("DELETE FROM om.item WHERE name = N'second'")
    code, output = scratch["clone"]("--delta")
    assert code == 0, output
    assert re.search(r"^  kept om\.item: local \d+ · DEV \d+, local rows kept$", output, re.M), output
    assert on_copy("SELECT COUNT(*) FROM om.item WHERE name = N'second'")[0][0] == 1


def test_delta_stops_at_max_rows_and_continues(scratch):
    on_source("INSERT INTO ev.trade (trade_id, amount) VALUES (10, 1), (11, 2), (12, 3), (13, 4), (14, 5)")
    code, output = scratch["clone"]("--delta", "--max-rows", "3")
    assert code == 0, output
    assert changed(output, "ev.trade") == 3
    assert on_copy("SELECT COUNT(*) FROM ev.trade WHERE trade_id >= 10")[0][0] == 3
    code, output = scratch["clone"]("--delta", "--max-rows", "3")
    assert code == 0, output
    assert changed(output, "ev.trade") == 2
    assert on_copy("SELECT COUNT(*) FROM ev.trade") == on_source("SELECT COUNT(*) FROM ev.trade")


def test_delta_stops_when_devs_schema_moved(scratch):
    # Publishing DEV's schema over the copy drops what your branch added, so the delta stops and says how to go on.
    on_source("ALTER TABLE om.item ADD colour NVARCHAR(20) NULL")
    try:
        code, output = scratch["clone"]("--delta")
        assert code != 0, output
        assert "DEV's schema changed since the last sync" in output and "FRESH=1" in output and "ONLY=" in output, output
        assert on_copy("SELECT COL_LENGTH('om.item', 'colour')")[0][0] is None
    finally:
        on_source("ALTER TABLE om.item DROP COLUMN colour")
    code, output = scratch["clone"]("--delta")
    assert code == 0 and re.search(r"^  schema: kept, same as DEV since run \d+$", output, re.M), output


def test_delta_refuses_another_source(scratch):
    runs = on_copy("SELECT COUNT(*) FROM local.sync_run")[0][0]
    code, output = scratch["clone"]("--delta", source=scratch["other"])
    assert code != 0
    assert "nothing to continue from; run a fresh sync" in output, output
    assert on_copy("SELECT COUNT(*) FROM local.sync_run")[0][0] == runs


def test_tenant_copies_those_tenants_whole_and_keeps_minus_999(tmp_path):
    """--tenant: a table with a tenant_id column brings only those tenants' rows and -999's, all of them;
    --max-rows still cuts a table without one. A delta would bring every tenant's changes, so it refuses."""
    try:
        localdb.local(PORT).close()
    except pyodbc.Error:
        pytest.skip(f"no SQL Server on {localdb.HOST},{PORT}; start this worktree's mssql first")
    source, copy = "zz_tenant_source", "zz_tenant_copy"
    for db in (source, copy):
        localdb.drop_database(PORT, db)
    localdb.local(PORT).execute(f"CREATE DATABASE {source}")
    for sql in ("CREATE SCHEMA ev",
                "CREATE TABLE ev.rate (tenant_id INT NOT NULL, rat_id INT NOT NULL, PRIMARY KEY (tenant_id, rat_id))",
                "CREATE TABLE ev.currency_kind (code NVARCHAR(10) PRIMARY KEY)",
                "INSERT INTO ev.rate VALUES (109, 1), (109, 2), (109, 3), (501, 1), (101, 1), (101, 2), (-999, 1)",
                "INSERT INTO ev.currency_kind VALUES (N'a'), (N'b'), (N'c')"):
        localdb.local(PORT, source).execute(sql)
    env = tmp_path / ".env.local.zz_tenant"
    env.write_text(f"DB_PARAMS='user=sa;host={localdb.HOST},{PORT};db={source}'\nDB_PASSWORD='{localdb.PASSWORD}'\n")
    command = [sys.executable, str(HERE.parent / "localdb.py"), "clone", copy, "--from", str(env), "--port", str(PORT)]
    try:
        out = subprocess.run([*command, "--replace", "--tenant", "109", "--tenant", "501", "--max-rows", "2"],
                             capture_output=True, text=True, timeout=240)
        assert out.returncode == 0, out.stdout + out.stderr
        rows = localdb.local(PORT, copy).execute("SELECT tenant_id, rat_id FROM ev.rate ORDER BY 1, 2").fetchall()
        assert [tuple(row) for row in rows] == [(-999, 1), (109, 1), (109, 2), (109, 3), (501, 1)]
        assert localdb.local(PORT, copy).execute("SELECT COUNT(*) FROM ev.currency_kind").fetchone()[0] == 2
        delta = subprocess.run([*command, "--delta", "--tenant", "109"], capture_output=True, text=True, timeout=60)
        assert delta.returncode != 0 and "--tenant" in delta.stdout + delta.stderr, delta.stdout + delta.stderr
    finally:
        for db in (source, copy):
            localdb.drop_database(PORT, db)


# --- backup and restore (plan/local-database-guards-a-e-so, step 2) -------------------------------------------

def test_backup_name_sorts_oldest_first():
    names = [localdb.backup_name("aisql-omega5-dev-local", t) for t in (1794254400, 1794168000, 1794340800)]
    assert names[0] == "aisql-omega5-dev-local-20261109T200000Z.bak"
    assert sorted(names) == [names[1], names[0], names[2]]


def test_backup_keeps_the_newest_three():
    db = "aisql-omega5-dev-local"
    files = [f"{db}-2026110{day}T000000Z.bak" for day in range(1, 6)] + ["aisql-omega-audit5-dev-local-20261101T000000Z.bak",
                                                                         "notes.txt"]
    assert localdb.to_prune(files, db, keep=3) == [f"{db}-20261101T000000Z.bak", f"{db}-20261102T000000Z.bak"]
    assert localdb.to_prune(files[:2], db, keep=3) == []


def test_backup_skips_a_missing_database():
    try:
        localdb.local(PORT).close()
    except pyodbc.Error:
        pytest.skip(f"no SQL Server on {localdb.HOST},{PORT}; start this worktree's mssql first")
    assert localdb.backup_database(PORT, "zz_never_made") is None


def test_backup_then_restore_brings_the_rows_back():
    try:
        localdb.local(PORT).close()
    except pyodbc.Error:
        pytest.skip(f"no SQL Server on {localdb.HOST},{PORT}; start this worktree's mssql first")
    db = "zz_backup_round_trip"
    localdb.drop_database(PORT, db)
    localdb.local(PORT).execute(f"CREATE DATABASE {db}")
    try:
        localdb.local(PORT, db).execute("CREATE TABLE dbo.seed (code INT PRIMARY KEY)")
        localdb.local(PORT, db).execute("INSERT INTO dbo.seed VALUES (11), (20), (34)")
        first = localdb.backup_database(PORT, db)
        assert first and first.startswith(f"{db}-") and first.endswith(".bak")
        assert first in localdb.backups(PORT, db)
        localdb.local(PORT, db).execute("DELETE FROM dbo.seed")
        out = subprocess.run([sys.executable, str(HERE.parent / "localdb.py"), "restore", db, "--port", str(PORT)],
                             capture_output=True, text=True, timeout=120)
        assert out.returncode == 0, out.stdout + out.stderr
        assert f"restored {db} from {first}" in out.stdout
        assert localdb.local(PORT, db).execute("SELECT COUNT(*) FROM dbo.seed").fetchone()[0] == 3
    finally:
        localdb.drop_database(PORT, db)
        for name in localdb.backups(PORT, db):
            localdb.in_container(PORT, "rm", "-f", f"{localdb.BACKUPS}/{name}")


# --- a delta keeps what only the branch has (plan/local-database-guards-a-e-so, step 3) -----------------------

GUARD_SOURCE, GUARD_COPY = "zz_guard_source", "zz_guard_copy"


@pytest.fixture(scope="module")
def guarded(tmp_path_factory):
    """A source with a keyed seed table like om.validation_redemption_reason_code, a table with no key and a
    revision, cloned fresh into the copy; both dropped, and the copy's backups removed, at the end."""
    try:
        localdb.local(PORT).close()
    except pyodbc.Error:
        pytest.skip(f"no SQL Server on {localdb.HOST},{PORT}; start this worktree's mssql first")
    for db in (GUARD_SOURCE, GUARD_COPY):
        localdb.drop_database(PORT, db)
    localdb.local(PORT).execute(f"CREATE DATABASE {GUARD_SOURCE}")
    for sql in ("CREATE SCHEMA om",
                "CREATE TABLE om.reason_code (code SMALLINT PRIMARY KEY, label NVARCHAR(60) NOT NULL)",
                "CREATE TABLE om.note_nokey (body NVARCHAR(40) NOT NULL)",
                "CREATE TABLE om.alembic_version (version_num VARCHAR(32) NOT NULL CONSTRAINT alembic_version_pkc PRIMARY KEY)",
                "INSERT INTO om.reason_code VALUES (11, N'Cash withdrawal'), (20, N'Account closed')",
                "INSERT INTO om.note_nokey VALUES (N'from DEV')",
                "INSERT INTO om.alembic_version VALUES ('0051')"):
        localdb.local(PORT, GUARD_SOURCE).execute(sql)
    env = tmp_path_factory.mktemp("guard") / ".env.local.zz_guard"
    env.write_text(f"DB_PARAMS='user=sa;host={localdb.HOST},{PORT};db={GUARD_SOURCE}'\nDB_PASSWORD='{localdb.PASSWORD}'\n")

    def clone(*arguments):
        out = subprocess.run([sys.executable, str(HERE.parent / "localdb.py"), "clone", GUARD_COPY, "--from", str(env),
                              "--port", str(PORT), *arguments], capture_output=True, text=True, timeout=240)
        return out.returncode, out.stdout + out.stderr

    code, output = clone("--replace")
    assert code == 0, output
    yield clone
    for db in (GUARD_SOURCE, GUARD_COPY):
        localdb.drop_database(PORT, db)
    for name in localdb.backups(PORT, GUARD_COPY):
        localdb.in_container(PORT, "rm", "-f", f"{localdb.BACKUPS}/{name}")


def on_guard(db, sql):
    cursor = localdb.local(PORT, db).execute(sql)
    return [tuple(row) for row in cursor.fetchall()] if cursor.description else None


def test_clone_backs_up_first(guarded):
    code, output = guarded("--delta")
    assert code == 0, output
    made = re.search(r"^  backup: (zz_guard_copy-\d{8}T\d{6}Z\.bak) in \.local-db/mssql/backups/", output, re.M)
    assert made, output
    assert made[1] in localdb.backups(PORT, GUARD_COPY)
    assert output.index("  backup: ") < output.index("  rows: ")


def test_delta_keeps_local_only_rows(guarded):
    # The branch seeded 34 and wrote a note DEV never had; DEV edited 11 and added 35.
    on_guard(GUARD_COPY, "INSERT INTO om.reason_code VALUES (34, N'Other')")
    on_guard(GUARD_COPY, "INSERT INTO om.note_nokey VALUES (N'only here')")
    on_guard(GUARD_SOURCE, "UPDATE om.reason_code SET label = N'Cash withdrawal, edited' WHERE code = 11")
    on_guard(GUARD_SOURCE, "INSERT INTO om.reason_code VALUES (35, N'Successor holder TFSA rollover')")
    code, output = guarded("--delta")
    assert code == 0, output
    assert on_guard(GUARD_COPY, "SELECT code, label FROM om.reason_code ORDER BY code") == [
        (11, "Cash withdrawal, edited"), (20, "Account closed"), (34, "Other"), (35, "Successor holder TFSA rollover")]
    assert ("only here",) in on_guard(GUARD_COPY, "SELECT body FROM om.note_nokey")
    assert "  left om.note_nokey: no key, 2 rows here against 1 copied last time, left as it is" in output, output


def test_delta_skips_alembic_version(guarded):
    on_guard(GUARD_COPY, "UPDATE om.alembic_version SET version_num = '0052'")
    on_guard(GUARD_SOURCE, "UPDATE om.alembic_version SET version_num = '0048'")
    code, output = guarded("--delta")
    assert code == 0, output
    assert on_guard(GUARD_COPY, "SELECT version_num FROM om.alembic_version") == [("0052",)]


def test_delta_stops_on_a_moved_schema(guarded):
    on_guard(GUARD_SOURCE, "ALTER TABLE om.reason_code ADD note NVARCHAR(20) NULL")
    try:
        code, output = guarded("--delta")
        assert code != 0, output
        assert "DEV's schema changed since the last sync" in output, output
        assert on_guard(GUARD_COPY, "SELECT COL_LENGTH('om.reason_code', 'note')") == [(None,)]
        assert on_guard(GUARD_COPY, "SELECT COUNT(*) FROM om.reason_code") == [(4,)]
    finally:
        on_guard(GUARD_SOURCE, "ALTER TABLE om.reason_code DROP COLUMN note")


# --- check and copy-rows (plan/local-database-guards-a-e-so, step 4) ---------------------------------------------

def test_spec_reads_table_and_filter():
    assert localdb.parse_spec("ev.security:sec_id in (590,594,599); om.app_setting") == [
        localdb.Spec("ev", "security", "sec_id in (590,594,599)"), localdb.Spec("om", "app_setting", None)]


def test_spec_refuses_a_name_that_is_not_one():
    for text in ("security", "ev.secu rity", "ev.[security]", ";"):
        with pytest.raises(SystemExit):
            localdb.parse_spec(text)


def guard_env(tmp_path):
    env = tmp_path / ".env.local.zz_guard_check"
    env.write_text(f"DB_PARAMS='user=sa;host={localdb.HOST},{PORT};db={GUARD_SOURCE}'\nDB_PASSWORD='{localdb.PASSWORD}'\n")
    return env


def toolkit(*arguments):
    out = subprocess.run([sys.executable, str(HERE.parent / "localdb.py"), *arguments, "--port", str(PORT)],
                         capture_output=True, text=True, timeout=240)
    return out.returncode, out.stdout + out.stderr


def test_check_reports_missing(guarded, tmp_path):
    on_guard(GUARD_SOURCE, "INSERT INTO om.reason_code VALUES (40, N'only on DEV'), (41, N'also only on DEV')")
    code, output = toolkit("check", GUARD_COPY, "--from", str(guard_env(tmp_path)), "--need", "om.reason_code:code in (40,41)")
    assert code == 1, output
    assert re.search(r"^  om\.reason_code where code in \(40,41\)\s+local 0 · DEV 2 · missing 2$", output, re.M), output
    revision = on_guard(GUARD_COPY, "SELECT version_num FROM om.alembic_version")[0][0]
    assert re.search(rf"^  alembic_version\s+{revision}$", output, re.M), output
    assert on_guard(GUARD_COPY, "SELECT COUNT(*) FROM om.reason_code WHERE code IN (40, 41)") == [(0,)]


def test_copy_rows_leaves_other_tables(guarded, tmp_path):
    env = str(guard_env(tmp_path))
    notes = on_guard(GUARD_COPY, "SELECT COUNT(*) FROM om.note_nokey")
    revision = on_guard(GUARD_COPY, "SELECT version_num FROM om.alembic_version")
    code, output = toolkit("copy-rows", GUARD_COPY, "--from", env, "--only", "om.reason_code:code in (40,41)")
    assert code == 0, output
    assert re.search(r"^  backup: zz_guard_copy-", output, re.M), output
    assert "  copy-rows: om.reason_code 2 rows from DEV" in output, output
    assert on_guard(GUARD_COPY, "SELECT code FROM om.reason_code WHERE code IN (40, 41) ORDER BY code") == [(40,), (41,)]
    assert on_guard(GUARD_COPY, "SELECT COUNT(*) FROM om.note_nokey") == notes
    assert on_guard(GUARD_COPY, "SELECT version_num FROM om.alembic_version") == revision
    code, output = toolkit("check", GUARD_COPY, "--from", env, "--need", "om.reason_code:code in (40,41)")
    assert code == 0 and "local 2 · DEV 2 · missing 0" in output, output


def test_spec_refuses_a_filter_that_writes():
    # The filter runs as SQL on the copy and on DEV: never a second statement or a write.
    for text in ("ev.security:1=1; DROP TABLE ev.security", "om.app_setting:[key] IN (SELECT 1) OR 1=1 --",
                 "ev.security:sec_id = 1 delete from ev.security", "om.tenant:exec('x')"):
        with pytest.raises(SystemExit):
            localdb.parse_spec(text)
    assert localdb.parse_spec("om.app_setting:[key] = N'LAKEHOUSE_SQL_DATABASE'")[0].where == "[key] = N'LAKEHOUSE_SQL_DATABASE'"
