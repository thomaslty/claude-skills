---
name: create-readme-tldr
description: "Write or rewrite a project README as a tl;dr in Thomas's own style — three sections only (Overview, Quick start, Configuration), about 30 lines, one plain sentence of what it does, commands with a short # comment saying why, one bullet per config file. Triggers on 'tldr readme', 'short readme', 'simplify the readme', or /dev:create-readme-tldr. For a product page with logo, badges and features, use /dev:create-readme instead."
---

# Create README — tl;dr

## Overview

The README tells you what the thing is, how to get it running, and which files you edit. Nothing else. Everything a reader can get from `--help`, the code or the config files stays there.

The shape comes from a README Thomas rewrote by hand after a 35-line draft was "too many bullshit". His version is the reference below. Copy its shape, its length and its voice.

## The reference, Omega.Sync's README as Thomas wrote it

````markdown
# Omega.Sync

## Overview

Sync EV database data into Omega database

- Support Delta Sync
  - `ev.sync_status` table keep track the progress

## Quick start

You need Python 3.12, ODBC Driver 18 for SQL Server and [uv](https://docs.astral.sh/uv/).

### First time setup
```bash
uv tool install keyring --with artifacts-keyring   # authorize azure credential, in order to install omega-import dependency
uv sync                                            # download dependency, create venv
cp config.yml.example config.yml
cp .env.example .env                               # then fill in the passwords
```

### Run
```bash
# menu TUI
make sync
```

- You can also run the script directly without the menu
  - eg `uv run sync-tenant --tenant ev_dev_lyz_new --tables-file tables/core.txt --dry-run`

## Configuration

- `config.yml`: database configuration, tenant mapping config, etc
- `.env`: secret reference
````

## The shape

Three `##` sections, in this order, and no others:

| Section | Holds |
|---|---|
| Overview | one plain sentence, then 1–3 capability bullets |
| Quick start | one line of what you need, `### First time setup`, `### Run` |
| Configuration | one bullet per file you edit |

The whole file is about 30 lines. Past 40, something does not belong.

## Overview

- one sentence, what it does in the plainest words, like `Sync EV database data into Omega database`
- no full stop needed, no "with ... on every row" detail
- then a capability bullet, like `- Support Delta Sync`
- at most one nested bullet under it, naming the one thing that makes it work, like `` - `ev.sync_status` table keep track the progress ``

## Quick start

- the runtimes on one line, like `You need Python 3.12, ODBC Driver 18 for SQL Server and [uv](...)`
- `### First time setup` is one bash block of the commands you run once, in order
- each command gets a short `#` comment saying why you run it, not how it works, like `# download dependency, create venv`
- line the `#` comments up in one column
- a command that needs no comment gets none, like `cp config.yml.example config.yml`
- `### Run` is one bash block with the comment on its own line above, like `# menu TUI` then `make sync`
- another way to run goes in a bullet after the block, with the real command nested under `eg`, like `` - eg `uv run sync-tenant --tenant ev_dev_lyz_new ...` ``

## Configuration

- one bullet per file you edit, `file`: what it holds in a few words, like `` - `config.yml`: database configuration, tenant mapping config, etc ``
- "etc" is fine, the file itself is the detail
- no table of keys, no lookup order, no gitignore warning

## What to cut

What the 35-line draft had and Thomas took out:

```
MINE   Copies a tenant's tables from its EV database (`dbo`, read only) into the omega
       database's `ev` schema, with that tenant's `tenant_id` on every row.
       - each table deletes the tenant's rows on the target, then copies them again ...
       - `ev.sync_status` keeps each table's progress, so a stopped run can continue ...
       - the lists you sync are in `tables/`, like `tables/core.txt`
       - in a standalone zone it also pauses Omega's writes and turns the capture ...
       - every run writes a log file, like `log/sync-tenant-ev_dev_lyz_new-...log`

THOMAS Sync EV database data into Omega database
       - Support Delta Sync
         - `ev.sync_status` table keep track the progress
```

```
MINE   - `config.yml` lists the databases by id, `ev[]` the sources and `omega[]` ...
       - you pass an `ev[]` id to `--tenant`, like `ev_dev_lyz_new`, and its ...
       - that tenant id has to be in `om.tenant` on the target, and the log's first ...
       - a `${NAME}` is filled from `variables` first, then `.env`, then the shell ...
       - `config.yml`, `.env` and `log/` are gitignored, and `.env` holds live ...

THOMAS - `config.yml`: database configuration, tenant mapping config, etc
       - `.env`: secret reference
```

So never put these in:

- how it works inside, like the delete-then-copy per table or the batch size
- safety notes and edge cases, like the standalone-zone trigger guard
- examples of output, like a log line or a log file name
- a flag table, `--help` has it
- links into source files, like `omega_sync/services/standalone_zone.py`
- rules the config enforces, like "the tenant id has to be in `om.tenant`"
- the `${NAME}` lookup order, or what is gitignored

## Voice

- Thomas's own words over polished ones, like "keep track the progress" and "secret reference", leave them as they are
- a bullet starts with a capital when it is a full thought, like `- You can also run the script directly without the menu`
- "eg" and "etc" are fine, and an example goes nested under `eg`, not inline
- no bold, no hedging paragraph

## Before you write

1. Read the current README. If Thomas edited it by hand, his wording wins over this file.
2. Find the one sentence: what does a user get from it.
3. Find the commands you run once, and the one command you run every time.
4. Find the files you edit.
5. Write the three sections, then count the lines.

## Checklist before you hand it over

- [ ] three `##` sections, Overview, Quick start and Configuration, nothing else
- [ ] Overview opens with one plain sentence
- [ ] every setup command has a short "why" comment, or needs none
- [ ] Configuration is one bullet per file
- [ ] no internals, no warnings, no output examples, no flag table
- [ ] about 30 lines

## Cross-References

- A product page with logo, badges and features → `/dev:create-readme`
