#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyodbc>=5"]
# ///
"""A SQL Server on 127.0.0.1 to build and test against, so dev work never runs in a real environment.

Usage: uv run ~/.claude/scripts/dev/localdb.py <command> ...

  up                                start the server (colima + docker compose), wait for a login
  down                              stop it; the databases stay in .local-db/mssql/ next to this script
  list                              the databases on it, with their size
  create <db>                       an empty database
  drop <db>                         delete a database
  load <file> <db>                  a .sql (sqlcmd), .bacpac (import) or .dacpac (publish) into <db>
  clone <db> --from <env file>      the schema and rows of the database that file names, into <db>
  env <db>                          the lines a .env.local needs to point at <db>
  sql <db> "<T-SQL>"                run a query on <db> and print what it returns
  backup <db> [--keep 3]            BACKUP <db> into .local-db/mssql/backups/, keeping its newest 3
  restore <db> [--file <name>]      put <db>'s newest backup back, or the one named
  check <db> [--from F --need S]    what <db> holds against DEV per schema.table[:where], and its health; writes nothing
  copy-rows <db> --from F --only S  DEV's rows of each schema.table[:where] into <db> by key; backs up first

Options:
  --port N        use another local server, like OM.Robot's 1434 (default 1436, or LOCALDB_PORT)
  --prefix P      the env file's keys are P_DB_PARAMS and P_DB_PASSWORD, like OMEGA (default: DB_PARAMS)
  --replace       clone or load over a <db> that is already there
  --resume        clone keeps <db>, its schema and every table a stopped run finished; copies the rest
  --delta         clone keeps <db> and brings only what the source changed since its last run there
  --skip-rows-of S  clone copies schema S's tables empty, like ev; repeat for more
  --max-rows N    clone copies at most N rows of each table (default 100000)
  --tenant ID     clone copies only this tenant's rows, and -999's, of a table with a tenant_id column,
                  all of them; --max-rows still cuts the rest; repeat for more, like --tenant 109 --tenant 501
  --schema-only   clone the schema, copy no rows

Each clone records itself in the copy, in local.sync_run, local.sync_step and local.sync_status,
and prints one line per table: `  12/105 tables  om.tenant`.

The env file is the one the project already has, like OM.Robot's `.env.dev`:
  DB_PARAMS='user=<login>;host=<server>.database.windows.net;db=<database>'
  DB_PASSWORD='<password>'
Any other project: write those two lines to a file and pass that.

Every target is 127.0.0.1. A clone only reads its source, and refuses a prod one.
The sa password is LocalRobot#2026, the one OM.Robot and Omega use locally, or LOCALDB_PASSWORD.
Needs docker (colima on macOS), sqlpackage (`dotnet tool install -g microsoft.sqlpackage`),
sqlcmd for .sql files, and ODBC Driver 18 for SQL Server.
"""
import argparse
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import pyodbc

# Off: a pooled connection comes back with the autocommit of its last user, so a one-line UPDATE
# after the row copy sat in an open transaction and rolled back when the process ended.
pyodbc.pooling = False

COMPOSE = pathlib.Path(__file__).resolve().parent / "localdb.compose.yml"
DRIVER = "ODBC Driver 18 for SQL Server"
# Not `localhost`: it resolves to ::1 first, and colima forwards IPv4 only.
HOST = "127.0.0.1"
PASSWORD = os.environ.get("LOCALDB_PASSWORD", "LocalRobot#2026")
SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}

# Publish an Azure SQL schema onto the Edge engine. Logins and users belong to
# the server the schema came from, and none of them exist here.
PUBLISH = [
    "/p:AllowIncompatiblePlatform=true",
    "/p:BlockOnPossibleDataLoss=false",
    "/p:ExcludeObjectTypes=Users;Logins;RoleMembership;Permissions;Credentials;"
    "DatabaseScopedCredentials;ExternalDataSources;ExternalFileFormats;ExternalTables",
]


def q(name):
    return "[" + name.replace("]", "]]") + "]"


def odbc_value(value):
    return "{" + value.replace("}", "}}") + "}"


def local(port, db="master", autocommit=True):
    return pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER={HOST},{port};DATABASE={odbc_value(db)};UID=sa;"
        f"PWD={odbc_value(PASSWORD)};Encrypt=yes;TrustServerCertificate=yes",
        autocommit=autocommit, timeout=60)


def local_ado(port, db):
    return (f"Server={HOST},{port};Initial Catalog={db};User ID=sa;Password=\"{PASSWORD}\";"
            "Encrypt=True;TrustServerCertificate=True;")


def exists(port, db):
    return local(port).execute("SELECT DB_ID(?)", db).fetchone()[0] is not None


def drop_database(port, db):
    if db.lower() in SYSTEM_DATABASES:
        sys.exit(f"refusing: {db} is a system database")
    local(port).execute(
        f"IF DB_ID(?) IS NOT NULL BEGIN ALTER DATABASE {q(db)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
        f"DROP DATABASE {q(db)} END", db)


def make_room(args):
    """`--replace` drops what is there; without it an existing <db> stops the command."""
    if exists(args.port, args.db):
        if not args.replace:
            sys.exit(f"{args.db} is already on {HOST},{args.port} — pass --replace to write over it, or pick another name")
        drop_database(args.port, args.db)


# Inside the server's container: both compose files bind its /var/opt/mssql to a .local-db/mssql/ folder,
# so a backup lands on the host at .local-db/mssql/backups/ and goes with the copy it belongs to.
BACKUPS = "/var/opt/mssql/backups"
KEEP_BACKUPS = 3


def container(port):
    """The docker container publishing <port>; the backups are read and pruned inside it."""
    names = subprocess.run(["docker", "ps", "--filter", f"publish={port}", "--format", "{{.Names}}"],
                           capture_output=True, text=True).stdout.split()
    if not names:
        sys.exit(f"no docker container publishes {HOST},{port}: a backup needs the server's container")
    return names[0]


def in_container(port, *cmd):
    out = subprocess.run(["docker", "exec", container(port), *cmd], capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"{' '.join(cmd)} in the server's container failed: {(out.stdout + out.stderr).strip()[-300:]}")
    return out.stdout


def backup_name(db, when):
    return f"{db}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(when))}.bak"


def backup_pattern(db):
    return re.compile(re.escape(db) + r"-\d{8}T\d{6}Z\.bak")


def backups(port, db):
    """<db>'s backups, oldest first; the name's UTC stamp sorts them."""
    listing = in_container(port, "sh", "-c", f"mkdir -p {BACKUPS} && ls -1 {BACKUPS}")
    return sorted(name for name in listing.split() if backup_pattern(db).fullmatch(name))


def to_prune(files, db, keep=KEEP_BACKUPS):
    """The backups of <db> past the newest `keep`, oldest first; another database's files are never named."""
    mine = sorted(name for name in files if backup_pattern(db).fullmatch(name))
    return mine[:-keep] if len(mine) > keep else []


def drain(cursor):
    # BACKUP and RESTORE report progress as result sets; the statement only finishes once all are read.
    while cursor.nextset():
        pass


def backup_database(port, db, keep=KEEP_BACKUPS):
    """BACKUP <db> before anything writes it, then keep its newest `keep`. None when <db> is not there yet."""
    if not exists(port, db):
        return None
    files = backups(port, db)
    name = backup_name(db, time.time())
    drain(local(port).execute(f"BACKUP DATABASE {q(db)} TO DISK = ? WITH COPY_ONLY, INIT, FORMAT", f"{BACKUPS}/{name}"))
    for old in to_prune(files + [name], db, keep):
        in_container(port, "rm", "-f", f"{BACKUPS}/{old}")
    print(f"  backup: {name} in .local-db/mssql/backups/ (newest {keep} kept)")
    return name


def cmd_backup(args):
    if backup_database(args.port, args.db, args.keep) is None:
        sys.exit(f"{args.db} is not on {HOST},{args.port}")


def cmd_restore(args):
    files = backups(args.port, args.db)
    pick = args.file or (files[-1] if files else None)
    if pick is None:
        sys.exit(f"no backup of {args.db} in .local-db/mssql/backups/")
    if pick not in files:
        sys.exit(f"{pick} is not a backup of {args.db}; there are: {', '.join(files) or 'none'}")
    connection = local(args.port)
    connection.execute(f"IF DB_ID(?) IS NOT NULL ALTER DATABASE {q(args.db)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE",
                       args.db)
    try:
        drain(connection.execute(f"RESTORE DATABASE {q(args.db)} FROM DISK = ? WITH REPLACE", f"{BACKUPS}/{pick}"))
    finally:
        connection.execute(f"IF DB_ID(?) IS NOT NULL ALTER DATABASE {q(args.db)} SET MULTI_USER", args.db)
    print(f"restored {args.db} from {pick}")


def run(cmd, env=None, secret=None):
    """Run a tool, printing its tail. The secret never reaches the screen, also not on failure."""
    out = subprocess.run(cmd, env=env, capture_output=True, text=True)
    text = (out.stdout + out.stderr).strip()
    if secret:
        text = text.replace(secret, "***")
    if out.returncode:
        # A Stop reaches the tool too, since it shares this process group; it ends, and that is not a failure.
        stop_point()
        sys.exit(f"{pathlib.Path(cmd[0]).name} failed:\n" + "\n".join(text.splitlines()[-25:]))
    return text


class Stopped(Exception):
    """A SIGINT, like the menu's Stop, raised between two statements, never inside a driver call."""


stop_asked = 0.0


def ask_stop(signum, frame):
    # A KeyboardInterrupt inside pyodbc breaks its connection, so the first SIGINT only asks:
    # the clone stops at the next table or batch of rows. One sent to the process group arrives
    # twice, ~0.2 s apart, since `uv run` forwards it too; a second one 3 s later stops at once.
    global stop_asked
    if stop_asked and time.monotonic() - stop_asked > 3:
        raise KeyboardInterrupt
    stop_asked = stop_asked or time.monotonic()


def stop_point():
    if stop_asked:
        raise Stopped


def sqlpackage(arguments, secret=None):
    path = shutil.which("sqlpackage") or str(pathlib.Path.home() / ".dotnet/tools/sqlpackage")
    if not os.path.exists(path):
        sys.exit("sqlpackage is missing: dotnet tool install -g microsoft.sqlpackage")
    env = dict(os.environ)
    if "DOTNET_ROOT" not in env and (pathlib.Path.home() / ".dotnet").is_dir():
        env["DOTNET_ROOT"] = str(pathlib.Path.home() / ".dotnet")
    return run([path, *arguments], env=env, secret=secret)


def read_env_file(path, prefix):
    values = {}
    for line in pathlib.Path(path).read_text().splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if m:
            values[m[1]] = m[2].strip().strip("'\"")
    key = f"{prefix}_DB_PARAMS" if prefix else "DB_PARAMS"
    if key not in values:
        sys.exit(f"{path} has no {key} — pass --prefix, like --prefix OMEGA for OMEGA_DB_PARAMS")
    params = dict(part.split("=", 1) for part in values[key].split(";") if "=" in part)
    missing = {"user", "host", "db"} - set(params)
    if missing:
        sys.exit(f"{key} in {path} has no {', '.join(sorted(missing))}")
    password = values.get(key.replace("_PARAMS", "_PASSWORD"))
    if not password:
        sys.exit(f"{path} has no {key.replace('_PARAMS', '_PASSWORD')}")
    host = params["host"] if "," in params["host"] else params["host"] + ",1433"
    return {"user": params["user"], "host": host, "db": params["db"], "password": password}


def wait(port):
    # Edge takes ~10 s after the container starts before it answers a login.
    for attempt in range(40):
        try:
            local(port).close()
            return
        except pyodbc.Error:
            if attempt == 39:
                raise
            time.sleep(3)


def cmd_up(args):
    if shutil.which("colima") and subprocess.run(["colima", "status"], capture_output=True).returncode:
        run(["colima", "start"])
    env = dict(os.environ, LOCALDB_PORT=str(args.port), LOCALDB_PASSWORD=PASSWORD)
    # Bind mounts, never a docker volume: deleting .local-db/ deletes every database.
    for folder in ("mssql", "mssql-extensibility/data", "mssql-extensibility/log"):
        (COMPOSE.parent / ".local-db" / folder).mkdir(parents=True, exist_ok=True)
    run(["docker", "compose", "-f", str(COMPOSE), "up", "-d"], env=env)
    wait(args.port)
    print(f"up: {HOST},{args.port}  user sa")


def cmd_down(args):
    run(["docker", "compose", "-f", str(COMPOSE), "down"])
    print(f"down: the databases stay in {COMPOSE.parent / '.local-db' / 'mssql'}")


def cmd_list(args):
    rows = local(args.port).execute(
        "SELECT d.name, SUM(f.size) * 8 / 1024 FROM sys.databases d JOIN sys.master_files f "
        "ON f.database_id = d.database_id WHERE d.database_id > 4 GROUP BY d.name ORDER BY d.name").fetchall()
    for name, mb in rows:
        print(f"{name}\t{mb} MB")
    if not rows:
        print(f"no databases on {HOST},{args.port}")


def cmd_create(args):
    make_room(args)
    local(args.port).execute(f"CREATE DATABASE {q(args.db)}")
    print(f"created {args.db} on {HOST},{args.port}")


def cmd_drop(args):
    if not exists(args.port, args.db):
        sys.exit(f"{args.db} is not on {HOST},{args.port}")
    drop_database(args.port, args.db)
    print(f"dropped {args.db}")


def cmd_load(args):
    path = pathlib.Path(args.file)
    if not path.is_file():
        sys.exit(f"no file {path}")
    kind = path.suffix.lower()
    if kind == ".sql":
        # A script can add to a database that is there already, like a seed file.
        if args.replace:
            drop_database(args.port, args.db)
        if not exists(args.port, args.db):
            local(args.port).execute(f"CREATE DATABASE {q(args.db)}")
        if not shutil.which("sqlcmd"):
            sys.exit("sqlcmd is missing: brew install sqlcmd")
        run(["sqlcmd", "-S", f"{HOST},{args.port}", "-U", "sa", "-C", "-b", "-d", args.db, "-i", str(path)],
            env=dict(os.environ, SQLCMDPASSWORD=PASSWORD))
    elif kind == ".bacpac":
        make_room(args)
        sqlpackage(["/Action:Import", f"/SourceFile:{path}", f"/TargetConnectionString:{local_ado(args.port, args.db)}"])
    elif kind == ".dacpac":
        # Onto an existing database this changes its schema to the file's; with --replace it starts empty.
        if args.replace:
            drop_database(args.port, args.db)
        sqlpackage(["/Action:Publish", f"/SourceFile:{path}",
                    f"/TargetConnectionString:{local_ado(args.port, args.db)}", *PUBLISH])
    else:
        sys.exit(f"{path.name}: load takes .sql, .bacpac or .dacpac")
    print(f"loaded {path.name} into {args.db} on {HOST},{args.port}")


def ensure_bookkeeping(port, db):
    """local.sync_run, local.sync_step and local.sync_status, made here and only in a copy on 127.0.0.1,
    never by a migration, so no real env ever gets them. Running it again changes nothing."""
    connection = local(port, db)
    connection.execute("IF SCHEMA_ID(N'local') IS NULL EXEC(N'CREATE SCHEMA [local]')")
    connection.execute("""IF OBJECT_ID(N'local.sync_run', N'U') IS NULL
CREATE TABLE [local].sync_run (
    id INT IDENTITY CONSTRAINT PK_sync_run PRIMARY KEY,
    source_host NVARCHAR(256) NOT NULL,
    source_db NVARCHAR(128) NOT NULL,
    mode NVARCHAR(20) NOT NULL CONSTRAINT CK_sync_run_mode CHECK (mode IN (N'fresh', N'resume', N'delta')),
    skipped_schemas NVARCHAR(200) NULL,
    status NVARCHAR(20) NOT NULL CONSTRAINT CK_sync_run_status
        CHECK (status IN (N'running', N'done', N'failed', N'stopped')),
    tables_total INT NOT NULL CONSTRAINT DF_sync_run_tables_total DEFAULT 0,
    tables_done INT NOT NULL CONSTRAINT DF_sync_run_tables_done DEFAULT 0,
    rows_changed BIGINT NULL,
    created_time DATETIME2 NOT NULL CONSTRAINT DF_sync_run_created_time DEFAULT getutcdate(),
    updated_time DATETIME2 NOT NULL CONSTRAINT DF_sync_run_updated_time DEFAULT getutcdate())""")
    connection.execute("""IF OBJECT_ID(N'local.sync_step', N'U') IS NULL
CREATE TABLE [local].sync_step (
    step NVARCHAR(20) NOT NULL CONSTRAINT PK_sync_step PRIMARY KEY
        CONSTRAINT CK_sync_step_step CHECK (step IN (N'schema', N'sequences')),
    run_id INT NOT NULL CONSTRAINT FK_sync_step_run FOREIGN KEY REFERENCES [local].sync_run (id),
    status NVARCHAR(20) NOT NULL CONSTRAINT CK_sync_step_status CHECK (status IN (N'running', N'done')),
    source_schema_hash INT NULL,
    created_time DATETIME2 NOT NULL CONSTRAINT DF_sync_step_created_time DEFAULT getutcdate(),
    updated_time DATETIME2 NOT NULL CONSTRAINT DF_sync_step_updated_time DEFAULT getutcdate())""")
    connection.execute("""IF OBJECT_ID(N'local.sync_status', N'U') IS NULL
CREATE TABLE [local].sync_status (
    id INT IDENTITY CONSTRAINT PK_sync_status PRIMARY KEY,
    run_id INT NOT NULL CONSTRAINT FK_sync_status_run FOREIGN KEY REFERENCES [local].sync_run (id),
    table_schema NVARCHAR(128) NOT NULL,
    table_name NVARCHAR(128) NOT NULL,
    status NVARCHAR(20) NOT NULL CONSTRAINT CK_sync_status_status
        CHECK (status IN (N'copying', N'done', N'failed', N'skipped')),
    method NVARCHAR(20) NOT NULL CONSTRAINT CK_sync_status_method
        CHECK (method IN (N'rowversion', N'updated_time', N'valid_from', N'identity', N'full')),
    source_rows BIGINT NOT NULL,
    copied_rows BIGINT NULL,
    changed_rows BIGINT NULL,
    watermark_rv BINARY(8) NULL,
    watermark_time DATETIME2 NULL,
    watermark_id BIGINT NULL,
    columns_hash INT NOT NULL,
    error NVARCHAR(400) NULL,
    created_time DATETIME2 NOT NULL CONSTRAINT DF_sync_status_created_time DEFAULT getutcdate(),
    updated_time DATETIME2 NOT NULL CONSTRAINT DF_sync_status_updated_time DEFAULT getutcdate(),
    CONSTRAINT UQ_sync_status_table UNIQUE (table_schema, table_name))""")


def plan_tables(tables, status, skip_schemas, resume):
    """Which tables to copy, keep, empty first or skip; `local` is in none of them.
    tables: [("om", "tenant"), ("ev", "dealer_institution"), …]
    status: {("om", "tenant"): "done", …} from local.sync_status; a fresh run reads none of it
      keep  done before, and resume
      redo  copying or failed before, and resume: emptied, then copied
      skip  its schema is in skip_schemas, like ev with omega only
    """
    plan = {"copy": [], "redo": [], "keep": [], "skip": []}
    for table in tables:
        if table[0] == "local":
            continue
        before = status.get(table) if resume else None
        if before == "done":
            plan["keep"].append(table)
        elif table[0] in skip_schemas:
            plan["skip"].append(table)
        elif before in ("copying", "failed"):
            plan["redo"].append(table)
        else:
            plan["copy"].append(table)
    return plan


def count_line(done, total, schema, table, changed=None):
    """One line per table, empty ones too, so a progress bar moves on every table."""
    return f"  {done}/{total} tables  {schema}.{table}" + ("" if changed is None else f"  {changed} changed")


def source_connection(src):
    # ApplicationIntent=ReadOnly: the source is read, and a read replica takes it when there is one.
    # A source on this Mac, like a copy on 127.0.0.1, has a self-signed certificate.
    trust = "TrustServerCertificate=yes;" if src["host"].split(",")[0] in (HOST, "localhost") else ""
    source = pyodbc.connect(
        f"DRIVER={{{DRIVER}}};SERVER=tcp:{src['host']};DATABASE={odbc_value(src['db'])};"
        f"UID={odbc_value(src['user'])};PWD={odbc_value(src['password'])};Encrypt=yes;{trust}"
        "ApplicationIntent=ReadOnly", timeout=60)
    source.autocommit = True
    return source


def catalogue(source):
    """Every table on the source but `local` and history tables: its columns, primary key, rows and column hash."""
    tables = {}
    for schema, table, column, kind, is_identity, generated in source.execute(
            "SELECT SCHEMA_NAME(t.schema_id), t.name, c.name, TYPE_NAME(c.system_type_id), c.is_identity, "
            "c.generated_always_type FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id "
            "WHERE t.is_ms_shipped = 0 AND t.temporal_type <> 1 AND SCHEMA_NAME(t.schema_id) <> N'local' "
            "ORDER BY t.schema_id, t.name, c.column_id").fetchall():
        info = tables.setdefault((schema, table), {"columns": [], "key": [], "rows": 0, "hash": 0})
        info["columns"].append((column, kind, bool(is_identity), generated))
    for schema, table, column in source.execute(
            "SELECT SCHEMA_NAME(t.schema_id), t.name, c.name FROM sys.tables t "
            "JOIN sys.indexes i ON i.object_id = t.object_id AND i.is_primary_key = 1 "
            "JOIN sys.index_columns k ON k.object_id = i.object_id AND k.index_id = i.index_id "
            "JOIN sys.columns c ON c.object_id = k.object_id AND c.column_id = k.column_id "
            "ORDER BY t.schema_id, t.name, k.key_ordinal").fetchall():
        if (schema, table) in tables:
            tables[schema, table]["key"].append(column)
    for schema, table, rows in source.execute(
            "SELECT SCHEMA_NAME(t.schema_id), t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p "
            "ON p.object_id = t.object_id AND p.index_id IN (0, 1) GROUP BY t.schema_id, t.name").fetchall():
        if (schema, table) in tables:
            tables[schema, table]["rows"] = int(rows or 0)
    # A table's own column hash: a different one after a Publish means its columns changed.
    for schema, table, value in source.execute(
            "SELECT SCHEMA_NAME(t.schema_id), t.name, CHECKSUM_AGG(CHECKSUM(c.name, TYPE_NAME(c.user_type_id), "
            "c.max_length, c.precision, c.scale, c.is_nullable)) FROM sys.tables t "
            "JOIN sys.columns c ON c.object_id = t.object_id GROUP BY t.schema_id, t.name").fetchall():
        if (schema, table) in tables:
            tables[schema, table]["hash"] = value or 0
    return tables


def set_status(cursor, table, **fields):
    """The table's local.sync_status row, written in the cursor's transaction; the caller commits."""
    names = list(fields)
    # A NULL bound for a binary column arrives as varchar, which SQL Server will not convert implicitly.
    marks = ["CONVERT(binary(8), ?)" if name == "watermark_rv" else "?" for name in names]
    values = [fields[name] for name in names]
    if not cursor.execute(
            f"UPDATE [local].sync_status SET {', '.join(f'{n} = {m}' for n, m in zip(names, marks))}, "
            "updated_time = getutcdate() WHERE table_schema = ? AND table_name = ?", *values, *table).rowcount:
        cursor.execute(f"INSERT INTO [local].sync_status (table_schema, table_name, {', '.join(names)}) "
                       f"VALUES (?, ?, {', '.join(marks)})", *table, *values)


def set_step(book, step, run_id, status, schema_hash=None):
    if not book.execute("UPDATE [local].sync_step SET run_id = ?, status = ?, source_schema_hash = ?, "
                        "updated_time = getutcdate() WHERE step = ?", run_id, status, schema_hash, step).rowcount:
        book.execute("INSERT INTO [local].sync_step (step, run_id, status, source_schema_hash) VALUES (?, ?, ?, ?)",
                     step, run_id, status, schema_hash)


def target_columns(target, name):
    """The columns an INSERT can write: no computed, period or rowversion column."""
    return target.execute(
        "SELECT name, TYPE_NAME(system_type_id), is_identity FROM sys.columns WHERE object_id = OBJECT_ID(?) "
        "AND is_computed = 0 AND generated_always_type = 0 AND TYPE_NAME(system_type_id) <> 'timestamp' "
        "ORDER BY column_id", name).fetchall()


def change_method(columns, has_key, source_rows, max_rows):
    """How Delta finds a table's changes on the source, from its columns there.
    columns: [(name, type, is_identity, generated_always_type), …] from sys.columns
    → "rowversion"    a timestamp column, like ev.transactions.upd_timestamp: new and edited rows
      "updated_time"  updated_time >= since, or an id past the last id: new and edited rows
      "valid_from"    a system-versioned table's ValidFrom: new and edited rows
      "identity"      over max_rows with only an identity: new rows only
      "full"          no key, or none of the above: emptied and copied again (a delta upserts by key instead)
    """
    if has_key:
        if any(kind == "timestamp" for _, kind, _, _ in columns):
            return "rowversion"
        if any(name.lower() == "updated_time" and kind in ("datetime", "datetime2", "smalldatetime")
               for name, kind, _, _ in columns):
            return "updated_time"
        if any(generated == 1 for _, _, _, generated in columns):
            return "valid_from"
    if source_rows > max_rows and any(is_identity for _, _, is_identity, _ in columns):
        return "identity"
    return "full"


def watermarks(method, columns):
    """The local.sync_status watermark columns a method reads and moves."""
    identity = any(is_identity for _, _, is_identity, _ in columns)
    return {"rowversion": {"watermark_rv"},
            "updated_time": {"watermark_time", "watermark_id"} if identity else {"watermark_time"},
            "valid_from": {"watermark_time"},
            "identity": {"watermark_id"}}.get(method, set())


def plan_delta(tables, status, hashes, skip_schemas, schema_run=None):
    """Which tables Delta checks past their watermark, copies in full, keeps or skips; `local` is in none.
    status: {("om", "tenant"): {"status": "done", "method": "updated_time", "columns_hash": 1762427118, "run_id": 3}, …}
    hashes: {("om", "tenant"): 1762427118, …}, each table's column hash on the source now
    schema_run: the run that last published the schema, this one when it published again
      check  done, its columns the same, and a method that finds changes
      full   anything else: new, never finished, skipped before, columns changed, or method full
      keep   done before, in a schema this run skips
      skip   in a schema this run skips, and never done
    An alembic_version is in none: the copy's revision is your branch's, like a 0052 DEV does not have yet, and a
    delta never publishes over the copy, so DEV's revision has nothing to come with (2026-11-09: it overwrote 0052).
    """
    plan = {"check": [], "full": [], "keep": [], "skip": []}
    for table in tables:
        if table[0] == "local":
            continue
        if table[1] == "alembic_version":
            continue
        row = status.get(table)
        done = row is not None and row["status"] == "done"
        if table[0] in skip_schemas:
            plan["keep" if done else "skip"].append(table)
        elif done and row["method"] != "full" and row["columns_hash"] == hashes.get(table):
            plan["check"].append(table)
        else:
            plan["full"].append(table)
    return plan


def schema_hash(source):
    """One number for every column of every table on the source: its table, name, type, length,
    precision, scale and nullability. A different one means Publish has to run again."""
    return source.execute(
        "SELECT CHECKSUM_AGG(CHECKSUM(SCHEMA_NAME(t.schema_id), t.name, c.name, TYPE_NAME(c.user_type_id), "
        "c.max_length, c.precision, c.scale, c.is_nullable)) FROM sys.tables t "
        "JOIN sys.columns c ON c.object_id = t.object_id "
        "WHERE t.is_ms_shipped = 0 AND SCHEMA_NAME(t.schema_id) <> N'local'").fetchone()[0]


def take_watermark(source, name, method, columns):
    """Read on the source just before the table is: a row changed during the read comes again next time,
    and delete-then-insert makes that harmless."""
    marks = watermarks(method, columns)
    found = {"watermark_rv": None, "watermark_time": None, "watermark_id": None}
    if "watermark_rv" in marks:
        found["watermark_rv"] = bytes(source.execute("SELECT MIN_ACTIVE_ROWVERSION()").fetchone()[0])
    if "watermark_time" in marks:
        # 5 minutes back: an app writes updated_time from its own clock, and a long transaction
        # stamps ValidFrom when it begins, not when it commits.
        found["watermark_time"] = source.execute("SELECT DATEADD(MINUTE, -5, SYSUTCDATETIME())").fetchone()[0]
    if "watermark_id" in marks:
        # last_value is NULL until the first insert, so the first row's id is still past it.
        found["watermark_id"] = source.execute(
            "SELECT COALESCE(CAST(last_value AS bigint), CAST(seed_value AS bigint) - CAST(increment_value AS bigint)) "
            "FROM sys.identity_columns WHERE object_id = OBJECT_ID(?)", name).fetchone()[0]
    return found


def statements(target, name):
    """The SELECT list and the INSERT for a table, from the columns an INSERT can write."""
    columns = target_columns(target, name)
    # pyodbc cannot read datetimeoffset; as text it goes back in without loss.
    select = ", ".join(f"CAST({q(c)} AS nvarchar(34))" if kind == "datetimeoffset" else q(c) for c, kind, _ in columns)
    insert = (f"INSERT INTO {name} ({', '.join(q(c) for c, _, _ in columns)}) "
              f"VALUES ({', '.join('?' * len(columns))})")
    return [c for c, _, _ in columns], select, insert, any(is_identity for _, _, is_identity in columns)


def tenant_rows(columns, tenants):
    """The WHERE that keeps those tenants' rows and -999's, the platform tenant pipeline_ops writes for;
    "" for a table with no tenant_id column, or no --tenant."""
    if not tenants or not any(name.lower() == "tenant_id" for name, _, _, _ in columns):
        return ""
    return f" WHERE [tenant_id] IN ({', '.join(str(int(tenant)) for tenant in sorted({-999, *tenants}))})"


def copy_table(source, target, run_id, table, info, max_rows, changed_rows=None, tenants=(), keep_local=False):
    """Empties the table in the copy and copies its rows from the source again, at most max_rows, with the
    method and watermark Delta reads next time; with tenants, those tenants' rows whole. `copying` commits
    first; `done` commits with the rows and the watermark, so it never claims rows the copy does not hold.
    keep_local: never empties; each source row replaces the copy's row with its key, and a row only the copy
    holds, like a seed of your branch, stays. The table needs a key."""
    name = f"{q(table[0])}.{q(table[1])}"
    method = change_method(info["columns"], bool(info["key"]), info["rows"], max_rows)
    set_status(target, table, run_id=run_id, status="copying", method=method, source_rows=info["rows"],
               columns_hash=info["hash"], error=None)
    target.commit()
    names, select, insert, identity = statements(target, name)
    key = [names.index(column) for column in info["key"] if column in names]
    if keep_local and not key:
        raise ValueError(f"{name} has no key, so keep_local cannot tell its rows apart")
    remove = f"DELETE FROM {name} WHERE " + " AND ".join(f"{q(names[i])} = ?" for i in key) if key else None
    writer = target.cursor()
    writer.fast_executemany = True
    copied = 0
    try:
        if identity:
            writer.execute(f"SET IDENTITY_INSERT {name} ON")
        if not keep_local:
            writer.execute(f"DELETE FROM {name}")
        mark = take_watermark(source, name, method, info["columns"])
        reader = source.cursor()
        where = tenant_rows(info["columns"], tenants)
        reader.execute(f"SELECT {select} FROM {name}{where}" if where else f"SELECT TOP ({max_rows}) {select} FROM {name}")
        while batch := reader.fetchmany(5000):
            stop_point()
            if keep_local:
                writer.executemany(remove, [tuple(r[i] for i in key) for r in batch])
            writer.executemany(insert, batch)
            copied += len(batch)
        held = writer.execute(f"SELECT COUNT_BIG(*) FROM {name}").fetchone()[0] if keep_local else copied
        set_status(writer, table, run_id=run_id, status="done", method=method,
                   source_rows=max(info["rows"], copied) if copied < max_rows else info["rows"],
                   copied_rows=held, changed_rows=changed_rows, columns_hash=info["hash"], error=None, **mark)
        writer.execute("UPDATE [local].sync_run SET tables_done = tables_done + 1, updated_time = getutcdate() "
                       "WHERE id = ?", run_id)
        target.commit()
        return copied
    except pyodbc.Error as exc:
        target.rollback()
        set_status(target, table, run_id=run_id, status="failed", error=str(exc.args[-1])[:400])
        target.commit()
        raise
    except BaseException:
        # A Stop: the rows roll back and the table stays `copying`, so --resume empties and copies it again.
        target.rollback()
        raise
    finally:
        # Per connection: left ON, the next table's IDENTITY_INSERT fails.
        if identity:
            try:
                writer.execute(f"SET IDENTITY_INSERT {name} OFF")
            except pyodbc.Error:
                pass


def copy_changed(source, target, run_id, table, info, row, max_rows):
    """The rows past the table's watermark on the source, at most max_rows, oldest change first: their keys
    deleted from the copy, the rows inserted and the watermark moved, in one commit.
    Returns (rows brought, a line when the copy's count differs from DEV's, None otherwise): a row only the copy
    holds, like a seed your branch added, looks the same as one DEV deleted, so the table is never emptied for it."""
    name = f"{q(table[0])}.{q(table[1])}"
    method = row["method"]
    names, select, insert, identity = statements(target, name)
    identity_column = next((c for c, _, is_identity, _ in info["columns"] if is_identity), None)
    mark = take_watermark(source, name, method, info["columns"])
    reader = source.cursor()
    rows = []
    # Each query adds the column it orders by at the end, as localdb_mark since it may be selected already,
    # so the last row read can move the watermark.
    if method == "rowversion":
        column = next(c for c, kind, _, _ in info["columns"] if kind == "timestamp")
        rows = reader.execute(f"SELECT TOP ({max_rows}) {select}, {q(column)} AS [localdb_mark] FROM {name} "
                              f"WHERE {q(column)} >= ? ORDER BY [localdb_mark]", row["watermark_rv"]).fetchall()
        if len(rows) == max_rows:
            mark["watermark_rv"] = (int.from_bytes(rows[-1][-1], "big") + 1).to_bytes(8, "big")
    if method == "identity" or (method == "updated_time" and identity_column):
        rows = reader.execute(f"SELECT TOP ({max_rows}) {select}, {q(identity_column)} AS [localdb_mark] FROM {name} "
                              f"WHERE {q(identity_column)} > ? ORDER BY [localdb_mark]",
                              row["watermark_id"]).fetchall()
        if len(rows) == max_rows:
            mark["watermark_id"] = rows[-1][-1]
            # The edited rows were not read this time: their watermark stays.
            mark["watermark_time"] = row["watermark_time"] if method == "updated_time" else None
    if method in ("updated_time", "valid_from") and len(rows) < max_rows:
        column = next(c for c, kind, _, generated in info["columns"]
                      if (c.lower() == "updated_time" if method == "updated_time" else generated == 1))
        older = method == "updated_time" and identity_column
        edited = reader.execute(
            f"SELECT TOP ({max_rows - len(rows)}) {select}, {q(column)} AS [localdb_mark] FROM {name} "
            f"WHERE {q(column)} >= ?" + (f" AND {q(identity_column)} <= ?" if older else "") + " ORDER BY [localdb_mark]",
            row["watermark_time"], *([row["watermark_id"]] if older else [])).fetchall()
        if edited and len(rows) + len(edited) == max_rows:
            mark["watermark_time"] = edited[-1][-1]
        rows += edited
    cut = len(rows) == max_rows

    key = [names.index(column) for column in info["key"] if column in names]
    writer = target.cursor()
    writer.fast_executemany = True
    try:
        if identity:
            writer.execute(f"SET IDENTITY_INSERT {name} ON")
        if rows and method != "identity":
            # An edited row replaces the old one by its key.
            writer.executemany(f"DELETE FROM {name} WHERE " + " AND ".join(f"{q(names[i])} = ?" for i in key),
                               [tuple(r[i] for i in key) for r in rows])
        if rows:
            writer.executemany(insert, [tuple(r)[:-1] for r in rows])
        held = writer.execute(f"SELECT COUNT_BIG(*) FROM {name}").fetchone()[0]
        counts = {"copied_rows": held, "source_rows": info["rows"]}
        whole = row["copied_rows"] is not None and row["copied_rows"] >= row["source_rows"]
        if whole and cut:
            # More to come next time; the counts still say the copy holds the table whole.
            counts = {}
        elif whole:
            # A table the copy holds whole has DEV's count; fewer on DEV means DEV deleted rows.
            counts["source_rows"] = source.execute(f"SELECT COUNT_BIG(*) FROM {name}").fetchone()[0]
        differs = whole and not cut and counts["source_rows"] != held
        set_status(writer, table, run_id=run_id, status="done", changed_rows=len(rows), error=None, **counts, **mark)
        writer.execute("UPDATE [local].sync_run SET tables_done = tables_done + 1, updated_time = getutcdate() "
                       "WHERE id = ?", run_id)
        target.commit()
        line = f"{table[0]}.{table[1]}: local {held} · DEV {counts['source_rows']}, local rows kept" if differs else None
        return len(rows), line
    except pyodbc.Error as exc:
        target.rollback()
        set_status(target, table, run_id=run_id, status="failed", error=str(exc.args[-1])[:400])
        target.commit()
        raise
    except BaseException:
        target.rollback()
        raise
    finally:
        if identity:
            try:
                writer.execute(f"SET IDENTITY_INSERT {name} OFF")
            except pyodbc.Error:
                pass


def switch_checks(target, names, on):
    """Constraints and triggers off while rows go in: a table cut at max_rows leaves its children pointing
    at rows that never came. Back on WITH NOCHECK afterwards, so every new write is checked again."""
    for name in names:
        if on:
            target.execute(f"ALTER TABLE {name} WITH NOCHECK CHECK CONSTRAINT ALL")
            target.execute(f"ENABLE TRIGGER ALL ON {name}")
        else:
            target.execute(f"ALTER TABLE {name} NOCHECK CONSTRAINT ALL")
            target.execute(f"DISABLE TRIGGER ALL ON {name}")
    target.commit()


def copy_rows(source, target, run_id, mode, skip, max_rows, schema_run=None, tenants=()):
    """The rows of every table the run's plan names; `local` is never touched. Returns what to print last."""
    info = catalogue(source)
    tables = [table for table in map(tuple, target.execute(
        # A history table fills itself from its system-versioned table and refuses an insert.
        "SELECT SCHEMA_NAME(schema_id), name FROM sys.tables WHERE temporal_type <> 1 AND is_ms_shipped = 0 "
        "AND SCHEMA_NAME(schema_id) <> N'local' ORDER BY 1, 2").fetchall()) if table in info]
    before = {(row.table_schema, row.table_name): {
        "status": row.status, "method": row.method, "source_rows": row.source_rows, "copied_rows": row.copied_rows,
        "watermark_rv": row.watermark_rv, "watermark_time": row.watermark_time, "watermark_id": row.watermark_id,
        "columns_hash": row.columns_hash, "run_id": row.run_id} for row in target.execute(
        "SELECT table_schema, table_name, status, method, source_rows, copied_rows, watermark_rv, watermark_time, "
        "watermark_id, columns_hash, run_id FROM [local].sync_status").fetchall()}
    if mode == "delta":
        plan = plan_delta(tables, before, {table: info[table]["hash"] for table in tables}, skip, schema_run)
        check = set(plan["check"])
        todo = set(plan["check"] + plan["full"])
    else:
        plan = plan_tables(tables, {table: row["status"] for table, row in before.items()}, skip,
                           resume=mode == "resume")
        check = set()
        todo = set(plan["copy"] + plan["redo"])
    todo = [table for table in tables if table in todo]
    target.execute("UPDATE [local].sync_run SET tables_total = ?, tables_done = ?, updated_time = getutcdate() "
                   "WHERE id = ?", len(plan["keep"]) + len(todo), len(plan["keep"]), run_id)
    target.commit()
    if mode == "delta":
        print(f"  rows: {len(todo)} tables to check, {len(todo) - len(check)} to copy in full")
    else:
        print(f"  rows: {len(plan['keep'])} tables kept, {len(todo)} to copy")

    names = [f"{q(s)}.{q(t)}" for s, t in tables]
    switch_checks(target, names, on=False)
    copied, sampled, failed, kept, left = 0, [], [], [], []
    changed_rows = changed_tables = full = 0
    try:
        for table in plan["skip"]:
            stop_point()
            state = before.get(table, {}).get("status")
            if state == "skipped":
                continue
            if state in ("copying", "failed"):
                # Half a copy of a schema this run leaves empty.
                target.execute(f"DELETE FROM {q(table[0])}.{q(table[1])}")
            item = info[table]
            set_status(target, table, run_id=run_id, status="skipped",
                       method=change_method(item["columns"], bool(item["key"]), item["rows"], max_rows),
                       source_rows=item["rows"], copied_rows=None, changed_rows=None, watermark_rv=None,
                       watermark_time=None, watermark_id=None, columns_hash=item["hash"], error=None)
        target.commit()
        for index, table in enumerate(todo, 1):
            stop_point()
            row = before.get(table)
            count = None if mode != "delta" else 0
            try:
                # A method that needs a watermark the copy never got copies the table in full instead.
                needed = watermarks(row["method"], info[table]["columns"]) if table in check else {None}
                # A table a delta finished before holds rows your branch may have added: never emptied.
                keep_local = mode == "delta" and row is not None and row["status"] == "done"
                checked = table in check and all(row[mark] is not None for mark in needed)
                held = None
                if keep_local and not checked and not info[table]["key"]:
                    # No key to tell rows apart: still the count the last copy left means nobody added a row here,
                    # so emptying it and copying again loses nothing; any other count is left as it is.
                    held = target.execute(f"SELECT COUNT_BIG(*) FROM {q(table[0])}.{q(table[1])}").fetchone()[0]
                    if held == row["copied_rows"]:
                        keep_local, held = False, None
                if checked:
                    count, differs = copy_changed(source, target, run_id, table, info[table], row, max_rows)
                    changed_rows += count
                    changed_tables += count > 0
                    if differs:
                        kept.append(differs)
                elif held is not None:
                    left.append(f"{table[0]}.{table[1]}: no key, {held} rows here against {row['copied_rows']} "
                                "copied last time, left as it is")
                else:
                    rows = copy_table(source, target, run_id, table, info[table], max_rows,
                                      changed_rows=None if mode != "delta" else 0, tenants=tenants,
                                      keep_local=keep_local)
                    copied += 1
                    full += mode == "delta"
                    if info[table]["rows"] > rows == max_rows and not tenant_rows(info[table]["columns"], tenants):
                        sampled.append(f"{table[0]}.{table[1]}: {max_rows} of {info[table]['rows']}")
            except pyodbc.Error as exc:
                failed.append(f"{table[0]}.{table[1]}: {str(exc.args[-1])[:200]}")
            print(count_line(index, len(todo), *table, changed=count))
    except BaseException:
        # Back on even after a Stop, or the copy runs with no trigger; an error here must not hide the Stop.
        try:
            target.rollback()
            switch_checks(target, names, on=True)
        except pyodbc.Error:
            pass
        raise
    switch_checks(target, names, on=True)
    if mode == "delta":
        target.execute("UPDATE [local].sync_run SET rows_changed = ? WHERE id = ?", changed_rows, run_id)
        target.commit()
        lines = [f"  delta: {changed_rows} rows changed in {changed_tables} tables, {full} copied in full, "
                 f"{len(kept)} differ from DEV"]
    else:
        lines = [f"  copied: {copied} tables, {len(plan['keep'])} kept"]
    return (lines + [f"  kept {line}" for line in kept] + [f"  left {line}" for line in left]
            + [f"  sampled {line}" for line in sampled] + [f"  FAILED {line}" for line in failed])


def restart_sequences(source, book, run_id):
    # A sequence is published at its START WITH, so the next id it hands out is one a copied row holds.
    # current_value and increment are sql_variant, which pyodbc cannot read; cast them.
    set_step(book, "sequences", run_id, "running")
    for schema, name, current, step in source.execute(
            "SELECT SCHEMA_NAME(schema_id), name, CAST(current_value AS decimal(38, 0)), "
            "CAST(increment AS decimal(38, 0)) FROM sys.sequences").fetchall():
        if current is not None:
            book.execute(f"ALTER SEQUENCE {q(schema)}.{q(name)} RESTART WITH {int(current) + int(step)}")
    set_step(book, "sequences", run_id, "done")


def publish_schema(src, args):
    """sqlpackage Extract on the source, Publish into the copy; logins and users stay behind."""
    password = '"' + src["password"].replace('"', '""') + '"'
    trust = "TrustServerCertificate=True;" if src["host"].split(",")[0] in (HOST, "localhost") else ""
    source_ado = (f"Server=tcp:{src['host']};Initial Catalog={src['db']};User ID={src['user']};"
                  f"Password={password};Encrypt=True;{trust}Connection Timeout=60;")
    with tempfile.TemporaryDirectory() as tmp:
        dacpac = pathlib.Path(tmp) / "schema.dacpac"
        print(f"  schema: reading {src['db']} on {src['host']}")
        sqlpackage(["/Action:Extract", f"/SourceConnectionString:{source_ado}", f"/TargetFile:{dacpac}",
                    "/p:ExtractAllTableData=false", "/p:IgnoreUserLoginMappings=true", "/p:IgnorePermissions=true",
                    "/p:VerifyExtraction=false"], secret=src["password"])
        print(f"  schema: writing into {args.db}")
        sqlpackage(["/Action:Publish", f"/SourceFile:{dacpac}",
                    f"/TargetConnectionString:{local_ado(args.port, args.db)}", *PUBLISH])


def sync_schema(src, args, book, run_id, mode, source):
    """Publishes the source's schema; resume keeps it when an earlier run finished it, and delta keeps it
    while the source's schema hash is the one recorded when it was published. Returns the run that published it."""
    step = book.execute("SELECT run_id, status, source_schema_hash FROM [local].sync_step "
                        "WHERE step = N'schema'").fetchone()
    if mode == "resume" and step and step.status == "done":
        print(f"  schema: kept, run {step.run_id} published it")
        return step.run_id
    now = schema_hash(source)
    if mode == "delta" and step and step.status == "done":
        if now == step.source_schema_hash:
            print(f"  schema: kept, same as DEV since run {step.run_id}")
            return step.run_id
        # Publish takes the copy to DEV's schema with data loss allowed, dropping what your branch's revision added.
        sys.exit(f"DEV's schema changed since the last sync (run {step.run_id}), and a delta never publishes over your "
                 "copy, since that drops what your branch added. Make a fresh copy yourself (make local-db sync FRESH=1), "
                 "or bring just the tables you need (make local-db sync ONLY=\"schema.table[:where]\").")
    set_step(book, "schema", run_id, "running")
    try:
        publish_schema(src, args)
    except SystemExit as exc:
        if mode == "delta":
            # Never half a schema: a fresh copy starts from an empty database.
            sys.exit(f"the schema changed on DEV in a way Publish cannot apply; run Sync, fresh\n{exc.code}")
        raise
    set_step(book, "schema", run_id, "done", now)
    tables = book.execute("SELECT COUNT(*) FROM sys.tables WHERE SCHEMA_NAME(schema_id) <> N'local'").fetchone()[0]
    print(f"  schema: {tables} tables")
    return run_id


def cmd_clone(args):
    src = read_env_file(args.source_file, args.prefix)
    if "prod" in (src["host"] + src["db"]).lower():
        sys.exit(f"refusing: {src['db']} on {src['host']} is prod — clone a dev env file, like .env.dev")
    mode = "resume" if args.resume else "delta" if args.delta else "fresh"
    if args.schema_only and mode != "fresh":
        sys.exit(f"--schema-only makes a new copy; it does not go with --{mode}")
    if args.tenant and mode == "delta":
        sys.exit("--tenant does not go with --delta, which would bring every tenant's changes; run a fresh sync")
    skip = {schema.strip() for value in args.skip_rows_of for schema in value.split(",") if schema.strip()}
    if mode == "fresh":
        if args.replace and exists(args.port, args.db):
            backup_database(args.port, args.db)
        make_room(args)
    elif not exists(args.port, args.db):
        sys.exit(f"{args.db} is not on {HOST},{args.port}: nothing to continue from; run a fresh sync")
    print(f"clone {src['db']} on {src['host']} -> {args.db} on {HOST},{args.port}" + ("" if mode == "fresh" else f", {mode}"))
    if mode == "fresh":
        # Azure SQL's native json type is not in the Edge (2019) engine, so a json column fails the
        # publish; an alias of nvarchar(max) stands in, like Omega's local_db/sync_schema.py does.
        local(args.port).execute(f"CREATE DATABASE {q(args.db)}")
        local(args.port, args.db).execute("CREATE TYPE [json] FROM nvarchar(max)")
    ensure_bookkeeping(args.port, args.db)
    book = local(args.port, args.db)
    if mode != "fresh":
        last = book.execute("SELECT TOP 1 id, source_host, source_db, status FROM [local].sync_run "
                            "ORDER BY id DESC").fetchone()
        if last is None:
            sys.exit(f"{args.db} has no run in local.sync_run: nothing to continue from; run a fresh sync")
        if (last.source_host.lower(), last.source_db.lower()) != (src["host"].lower(), src["db"].lower()):
            sys.exit(f"{args.db}'s last run came from {last.source_db} on {last.source_host}, not {src['db']}: "
                     "nothing to continue from; run a fresh sync")
        if last.status == "running":
            # It died without a word, like a SIGKILL or a laptop shut, so it never marked itself.
            book.execute("UPDATE [local].sync_run SET status = N'stopped', updated_time = getutcdate() WHERE id = ?",
                         last.id)
        backup_database(args.port, args.db)
    run_id = book.execute(
        "INSERT INTO [local].sync_run (source_host, source_db, mode, skipped_schemas, status) OUTPUT INSERTED.id "
        "VALUES (?, ?, ?, ?, N'running')", src["host"], src["db"], mode, ",".join(sorted(skip)) or None).fetchone()[0]
    started = time.time()
    signal.signal(signal.SIGINT, ask_stop)
    # Python's handler interrupts a blocking read (EINTR), and the ODBC driver takes that for a lost link.
    signal.siginterrupt(signal.SIGINT, False)
    try:
        source = source_connection(src)
        schema_run = sync_schema(src, args, book, run_id, mode, source)
        if args.schema_only:
            print("  rows: none, --schema-only")
        else:
            lines = copy_rows(source, local(args.port, args.db, autocommit=False), run_id, mode, skip, args.max_rows,
                              schema_run, tenants=args.tenant)
            restart_sequences(source, book, run_id)
            print(*lines, sep="\n")
        local(args.port, args.db).execute(
            "UPDATE [local].sync_run SET status = N'done', updated_time = getutcdate() WHERE id = ?", run_id)
    except (Stopped, KeyboardInterrupt):
        done, total = local(args.port, args.db).execute(
            "UPDATE [local].sync_run SET status = N'stopped', updated_time = getutcdate() "
            "OUTPUT INSERTED.tables_done, INSERTED.tables_total WHERE id = ?", run_id).fetchone()
        print(f"  stopped: run {run_id} after {int(time.time() - started)} s, {done} of {total} tables done; "
              + ("--delta again picks up from there" if mode == "delta" else "--resume continues it"))
        sys.exit(130)
    except BaseException:
        local(args.port, args.db).execute(
            "UPDATE [local].sync_run SET status = N'failed', updated_time = getutcdate() WHERE id = ?", run_id)
        raise
    print(f"  run {run_id} done in {int(time.time() - started)} s")
    print("point the project at it with:")
    cmd_env(args)


class Spec(tuple):
    """One `schema.table[:where]` of a --need or --only, like `ev.security:sec_id in (590,594,599)`."""
    __slots__ = ()

    def __new__(cls, schema, table, where):
        return super().__new__(cls, (schema, table, where))

    schema = property(lambda self: self[0])
    table = property(lambda self: self[1])
    where = property(lambda self: self[2])

    def name(self):
        return f"{q(self.schema)}.{q(self.table)}"

    def label(self):
        return f"{self.schema}.{self.table}" + (f" where {self.where}" if self.where else "")


SPEC_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# The filter runs as SQL on the copy and on DEV: one condition, never a second statement or a write.
SPEC_WRITES = re.compile(r";|--|/\*|\b(drop|delete|insert|update|alter|exec|execute|create|truncate|merge|grant|"
                         r"revoke|backup|restore|shutdown|into|dbcc|openrowset|opendatasource)\b", re.I)


def parse_spec(text):
    """`ev.security:sec_id in (590,594,599); om.app_setting` → [Spec("ev", "security", "sec_id in (…)"), …].
    The table names are checked, since they go into the SQL bracketed; the filter is yours, as typed."""
    specs = []
    for part in (piece.strip() for piece in text.split(";")):
        if not part:
            continue
        name, _, where = part.partition(":")
        schema, _, table = name.strip().partition(".")
        if not (SPEC_NAME.fullmatch(schema) and SPEC_NAME.fullmatch(table)):
            sys.exit(f"{name.strip()!r} is not schema.table, like ev.security or om.app_setting")
        if where and SPEC_WRITES.search(where):
            sys.exit(f"the filter {where.strip()!r} is one condition, like sec_id in (590,594,599): no ;, no comment, no write")
        specs.append(Spec(schema, table, where.strip() or None))
    if not specs:
        sys.exit("give at least one schema.table[:where], like \"ev.security:sec_id in (590,594,599)\"")
    return specs


def count_where(connection, spec):
    """Rows of the spec's table its filter picks; None when the table is not in that database."""
    if connection.execute("SELECT OBJECT_ID(?, N'U')", spec.name()).fetchone()[0] is None:
        return None
    where = f" WHERE {spec.where}" if spec.where else ""
    return connection.execute(f"SELECT COUNT_BIG(*) FROM {spec.name()}{where}").fetchone()[0]


def cmd_check(args):
    """What the copy holds against DEV, for each --need, and the copy's health. Writes nothing anywhere."""
    copy = local(args.port, args.db)
    missing = 0
    if args.need:
        source = source_connection(read_env_file(args.source_file, args.prefix))
        for spec in parse_spec(args.need):
            here, there = count_where(copy, spec), count_where(source, spec)
            if here is None:
                print(f"  {spec.label()}\tnot in the copy: a FRESH copy, or the migration that adds it")
                missing += 1
                continue
            gap = max((there or 0) - here, 0)
            missing += gap
            print(f"  {spec.label()}\tlocal {here} · DEV {there if there is not None else 'none'} · missing {gap}")
    def one(sql):
        try:
            row = copy.execute(sql).fetchone()
            return row[0] if row else None
        except pyodbc.Error:
            return None
    revision = one("SELECT TOP 1 version_num FROM om.alembic_version") or one("SELECT TOP 1 version_num FROM dbo.alembic_version")
    settings = one("SELECT COUNT(*) FROM om.app_setting")
    last = one("SELECT TOP 1 CONCAT(N'run ', id, N' ', mode, N' ', status, N' ', CONVERT(nvarchar(16), created_time, 120)) "
               "FROM [local].sync_run ORDER BY id DESC")
    newest = (backups(args.port, args.db) or [None])[-1]
    print(f"  alembic_version\t{revision or 'none'}")
    print(f"  om.app_setting\t{settings if settings is not None else 'none'} rows")
    print(f"  last sync\t{last or 'none'}")
    print(f"  newest backup\t{newest or 'none'}")
    if missing:
        print(f"missing {missing}: bring just those with copy-rows --only, or make local-db sync ONLY=\"…\"")
        sys.exit(1)


def primary_key(connection, name):
    return [row[0] for row in connection.execute(
        "SELECT c.name FROM sys.indexes i JOIN sys.index_columns k ON k.object_id = i.object_id AND k.index_id = i.index_id "
        "JOIN sys.columns c ON c.object_id = k.object_id AND c.column_id = k.column_id "
        "WHERE i.object_id = OBJECT_ID(?) AND i.is_primary_key = 1 ORDER BY k.key_ordinal", name).fetchall()]


def cmd_copy_rows(args):
    """DEV's rows of each --only into the copy, replacing the copy's row with the same key; the schema,
    om.alembic_version and every other table stay as they are. Backs the copy up first."""
    specs = parse_spec(args.only)
    if not exists(args.port, args.db):
        sys.exit(f"{args.db} is not on {HOST},{args.port}: copy-rows fills a copy that is there")
    target = local(args.port, args.db, autocommit=False)
    for spec in specs:
        if count_where(target, spec) is None:
            sys.exit(f"{spec.schema}.{spec.table} is not in {args.db}; copy-rows never changes the schema")
        if not primary_key(target, spec.name()):
            sys.exit(f"{spec.schema}.{spec.table} has no primary key, so a row cannot replace its own; pick another table")
    source = source_connection(read_env_file(args.source_file, args.prefix))
    backup_database(args.port, args.db)
    for spec in specs:
        name = spec.name()
        names, select, insert, identity = statements(target, name)
        key = [names.index(column) for column in primary_key(target, name)]
        where = f" WHERE {spec.where}" if spec.where else ""
        rows = source.execute(f"SELECT {select} FROM {name}{where}").fetchall()
        writer = target.cursor()
        writer.fast_executemany = True
        switch_checks(target, [name], on=False)
        try:
            if identity:
                writer.execute(f"SET IDENTITY_INSERT {name} ON")
            if rows:
                writer.executemany(f"DELETE FROM {name} WHERE " + " AND ".join(f"{q(names[i])} = ?" for i in key),
                                   [tuple(row[i] for i in key) for row in rows])
                writer.executemany(insert, [tuple(row) for row in rows])
            if identity:
                writer.execute(f"SET IDENTITY_INSERT {name} OFF")
            target.commit()
        except BaseException:
            target.rollback()
            raise
        finally:
            switch_checks(target, [name], on=True)
        print(f"  copy-rows: {spec.schema}.{spec.table} {len(rows)} rows from DEV" + (f" where {spec.where}" if spec.where else ""))


def cmd_env(args):
    prefix = f"{args.prefix}_" if args.prefix else ""
    print(f"{prefix}DB_PARAMS='user=sa;host={HOST},{args.port};db={args.db}'")
    print(f"{prefix}DB_PASSWORD='{PASSWORD}'")


def cmd_sql(args):
    try:
        cursor = local(args.port, args.db).execute(args.query)
    except pyodbc.Error as exc:
        sys.exit(str(exc.args[-1]))
    while True:
        if cursor.description:
            print("\t".join(c[0] for c in cursor.description))
            for row in cursor.fetchall():
                print("\t".join("NULL" if v is None else str(v) for v in row))
        elif cursor.rowcount >= 0:
            print(f"({cursor.rowcount} rows affected)")
        if not cursor.nextset():
            break


def main():
    if len(sys.argv) == 1:
        sys.exit(__doc__)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                     usage=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)

    def command(name, func, *positional):
        sub = commands.add_parser(name)
        for arg in positional:
            sub.add_argument(arg)
        sub.add_argument("--port", type=int, default=int(os.environ.get("LOCALDB_PORT", "1436")))
        sub.set_defaults(func=func)
        return sub

    command("up", cmd_up)
    command("down", cmd_down)
    command("list", cmd_list)
    command("create", cmd_create, "db").add_argument("--replace", action="store_true")
    command("drop", cmd_drop, "db")
    command("load", cmd_load, "file", "db").add_argument("--replace", action="store_true")
    clone = command("clone", cmd_clone, "db")
    clone.add_argument("--from", dest="source_file", required=True)
    clone.add_argument("--prefix", default="")
    mode = clone.add_mutually_exclusive_group()
    mode.add_argument("--replace", action="store_true", help="drop <db> first, then copy it again")
    mode.add_argument("--resume", action="store_true",
                      help="keep <db>, its schema and the tables done before; copy the rest")
    mode.add_argument("--delta", action="store_true",
                      help="keep <db>; bring only the rows the source changed since its last run")
    clone.add_argument("--skip-rows-of", action="append", default=[], metavar="SCHEMA",
                       help="copy this schema's tables empty, like ev; repeat for more")
    clone.add_argument("--max-rows", type=int, default=100_000)
    clone.add_argument("--tenant", type=int, action="append", default=[], metavar="ID",
                       help="copy only this tenant's rows, and -999's, of a table with a tenant_id column; repeat")
    clone.add_argument("--schema-only", action="store_true")
    command("env", cmd_env, "db").add_argument("--prefix", default="")
    command("sql", cmd_sql, "db", "query")
    command("backup", cmd_backup, "db").add_argument("--keep", type=int, default=KEEP_BACKUPS)
    check = command("check", cmd_check, "db")
    check.add_argument("--from", dest="source_file", help="the env file of the DEV database to count against")
    check.add_argument("--prefix", default="")
    check.add_argument("--need", help='schema.table[:where], ";" between them, like "ev.security:sec_id in (590,594,599)"')
    copy_rows = command("copy-rows", cmd_copy_rows, "db")
    copy_rows.add_argument("--from", dest="source_file", required=True)
    copy_rows.add_argument("--prefix", default="")
    copy_rows.add_argument("--only", required=True, help="schema.table[:where], \";\" between them")
    command("restore", cmd_restore, "db").add_argument("--file", help="a backup's name; the newest by default")

    args = parser.parse_args()
    # One line at a time, also into a pipe, so a menu reading it shows each table as it is done.
    sys.stdout.reconfigure(line_buffering=True)
    args.func(args)


if __name__ == "__main__":
    main()
