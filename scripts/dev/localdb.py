#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyodbc>=5"]
# ///
"""A SQL Server on 127.0.0.1 to build and test against, so dev work never runs in a real environment.

Usage: uv run ~/.claude/scripts/dev/localdb.py <command> ...

  up                                start the server (colima + docker compose), wait for a login
  down                              stop it; the databases stay in its volume
  list                              the databases on it, with their size
  create <db>                       an empty database
  drop <db>                         delete a database
  load <file> <db>                  a .sql (sqlcmd), .bacpac (import) or .dacpac (publish) into <db>
  clone <db> --from <env file>      the schema and rows of the database that file names, into <db>
  env <db>                          the lines a .env.local needs to point at <db>
  sql <db> "<T-SQL>"                run a query on <db> and print what it returns

Options:
  --port N        use another local server, like OM.Robot's 1434 (default 1436, or LOCALDB_PORT)
  --prefix P      the env file's keys are P_DB_PARAMS and P_DB_PASSWORD, like OMEGA (default: DB_PARAMS)
  --replace       clone or load over a <db> that is already there
  --max-rows N    clone copies at most N rows of each table (default 100000)
  --schema-only   clone the schema, copy no rows

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
import subprocess
import sys
import tempfile
import time

import pyodbc

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


def run(cmd, env=None, secret=None):
    """Run a tool, printing its tail. The secret never reaches the screen, also not on failure."""
    out = subprocess.run(cmd, env=env, capture_output=True, text=True)
    text = (out.stdout + out.stderr).strip()
    if secret:
        text = text.replace(secret, "***")
    if out.returncode:
        sys.exit(f"{pathlib.Path(cmd[0]).name} failed:\n" + "\n".join(text.splitlines()[-25:]))
    return text


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
    run(["docker", "compose", "-f", str(COMPOSE), "up", "-d"], env=env)
    wait(args.port)
    print(f"up: {HOST},{args.port}  user sa")


def cmd_down(args):
    run(["docker", "compose", "-f", str(COMPOSE), "down"])
    print("down: the databases stay in the volume")


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


def copy_rows(source, target, max_rows):
    """Every table's rows, up to max_rows each. Returns (copied, sampled, failed)."""
    tables = target.execute(
        # A history table fills itself from its system-versioned table and refuses an insert.
        "SELECT SCHEMA_NAME(schema_id), name FROM sys.tables WHERE temporal_type <> 1 AND is_ms_shipped = 0 "
        "ORDER BY 1, 2").fetchall()
    on_source = {(s, t): n for s, t, n in source.execute(
        "SELECT SCHEMA_NAME(t.schema_id), t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p "
        "ON p.object_id = t.object_id AND p.index_id IN (0, 1) GROUP BY t.schema_id, t.name").fetchall()}
    names = [f"{q(s)}.{q(t)}" for s, t in tables]

    # Off while rows go in: a table cut at max_rows leaves its children pointing at rows that
    # never came. Back on WITH NOCHECK afterwards, so every new write is checked again.
    for name in names:
        target.execute(f"ALTER TABLE {name} NOCHECK CONSTRAINT ALL")
        target.execute(f"DISABLE TRIGGER ALL ON {name}")
    target.commit()

    copied, sampled, failed = 0, [], []
    try:
        for index, ((schema, table), name) in enumerate(zip(tables, names), 1):
            rows = on_source.get((schema, table), 0)
            if not rows:
                continue
            columns = target.execute(
                "SELECT name, TYPE_NAME(system_type_id), is_identity FROM sys.columns WHERE object_id = OBJECT_ID(?) "
                "AND is_computed = 0 AND generated_always_type = 0 AND TYPE_NAME(system_type_id) <> 'timestamp' "
                "ORDER BY column_id", name).fetchall()
            # pyodbc cannot read datetimeoffset; as text it goes back in without loss.
            select = ", ".join(f"CAST({q(c)} AS nvarchar(34))" if kind == "datetimeoffset" else q(c)
                               for c, kind, _ in columns)
            insert = (f"INSERT INTO {name} ({', '.join(q(c) for c, _, _ in columns)}) "
                      f"VALUES ({', '.join('?' * len(columns))})")
            identity = any(is_identity for _, _, is_identity in columns)
            writer = target.cursor()
            writer.fast_executemany = True
            try:
                if identity:
                    writer.execute(f"SET IDENTITY_INSERT {name} ON")
                reader = source.cursor()
                reader.execute(f"SELECT TOP ({max_rows}) {select} FROM {name}")
                while batch := reader.fetchmany(5000):
                    writer.executemany(insert, batch)
                target.commit()
                copied += 1
                if rows > max_rows:
                    sampled.append(f"{schema}.{table}: {max_rows} of {rows}")
            except pyodbc.Error as exc:
                target.rollback()
                failed.append(f"{schema}.{table}: {str(exc.args[-1])[:200]}")
            finally:
                # Per connection: left ON, the next table's IDENTITY_INSERT fails.
                if identity:
                    writer.execute(f"SET IDENTITY_INSERT {name} OFF")
            if index % 200 == 0:
                print(f"  {index}/{len(tables)} tables", file=sys.stderr)
    finally:
        for name in names:
            target.execute(f"ALTER TABLE {name} WITH NOCHECK CHECK CONSTRAINT ALL")
            target.execute(f"ENABLE TRIGGER ALL ON {name}")
        target.commit()

    # A sequence is published at its START WITH, so the next id it hands out is one a copied row holds.
    for schema, name, current, step in source.execute(
            "SELECT SCHEMA_NAME(schema_id), name, current_value, increment FROM sys.sequences").fetchall():
        if current is not None:
            target.execute(f"ALTER SEQUENCE {q(schema)}.{q(name)} RESTART WITH {int(current) + int(step)}")
    target.commit()
    return copied, sampled, failed


def cmd_clone(args):
    src = read_env_file(args.source_file, args.prefix)
    if "prod" in (src["host"] + src["db"]).lower():
        sys.exit(f"refusing: {src['db']} on {src['host']} is prod — clone a dev env file, like .env.dev")
    make_room(args)
    print(f"clone {src['db']} on {src['host']} -> {args.db} on {HOST},{args.port}")

    password = '"' + src["password"].replace('"', '""') + '"'
    source_ado = (f"Server=tcp:{src['host']};Initial Catalog={src['db']};User ID={src['user']};"
                  f"Password={password};Encrypt=True;Connection Timeout=60;")
    with tempfile.TemporaryDirectory() as tmp:
        dacpac = pathlib.Path(tmp) / "schema.dacpac"
        sqlpackage(["/Action:Extract", f"/SourceConnectionString:{source_ado}", f"/TargetFile:{dacpac}",
                    "/p:ExtractAllTableData=false", "/p:IgnoreUserLoginMappings=true", "/p:IgnorePermissions=true",
                    "/p:VerifyExtraction=false"], secret=src["password"])
        sqlpackage(["/Action:Publish", f"/SourceFile:{dacpac}",
                    f"/TargetConnectionString:{local_ado(args.port, args.db)}", *PUBLISH])
    tables = local(args.port, args.db).execute("SELECT COUNT(*) FROM sys.tables").fetchone()[0]
    print(f"  schema: {tables} tables")
    if args.schema_only:
        print("  rows: none, --schema-only")
    else:
        # ApplicationIntent=ReadOnly: the source is read, and a read replica takes it when there is one.
        source = pyodbc.connect(
            f"DRIVER={{{DRIVER}}};SERVER=tcp:{src['host']};DATABASE={odbc_value(src['db'])};"
            f"UID={odbc_value(src['user'])};PWD={odbc_value(src['password'])};Encrypt=yes;"
            "ApplicationIntent=ReadOnly", timeout=60)
        source.autocommit = True
        started = time.time()
        copied, sampled, failed = copy_rows(source, local(args.port, args.db, autocommit=False), args.max_rows)
        print(f"  rows: {copied} tables copied in {int(time.time() - started)} s")
        for line in sampled:
            print(f"  sampled {line}")
        for line in failed:
            print(f"  FAILED {line}")
    print("point the project at it with:")
    cmd_env(args)


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
    clone.add_argument("--replace", action="store_true")
    clone.add_argument("--max-rows", type=int, default=100_000)
    clone.add_argument("--schema-only", action="store_true")
    command("env", cmd_env, "db").add_argument("--prefix", default="")
    command("sql", cmd_sql, "db", "query")

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
