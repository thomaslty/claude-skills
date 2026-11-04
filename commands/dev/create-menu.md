---
name: create-menu
description: "Add `make menu` to a repo: a root Makefile whose bare `make` lists every command with an example, and a Textual terminal menu in its own `<name>_cli/` uv project that picks options and runs those same make lines, with steps, a progress bar, Show command and a Stop that leaves nothing running. Copies the look of Omega.Sync's `make sync` menu and Omega.Next.AIO's `make menu` from the template in ~/.claude/scripts/dev/menu/. Triggers on 'make menu', 'add a menu', 'a TUI for the Makefile', 'menuconfig', or /dev:create-menu."
---

# Create menu

## Overview

`make menu` opens a menu in the terminal that runs the repo's own make lines. You pick, like Build `backend only` then `Up (detached)`, and it runs `make up BUILD=backend DETACH=1` and shows how far it got. What a command does stays in the Makefile, so a terminal user gets the same lines and the menu holds no logic of its own.

Two menus are the reference. Read them when a rule here is not enough:

| Menu | Take from it |
|---|---|
| Omega.Sync `make sync` | the look: pickers, ticks, Run this? |
| Omega.Next.AIO `make menu` | pages over make lines, the Run screen |

- Omega.Sync: `/Users/thomaslau/Desktop/toogood/git/ai/Omega.Sync/omega_sync/cli/sync_menu.py`
- Omega.Next.AIO: `/Users/thomaslau/orca/workspaces/Omega.Next.AIO/feat-dealer-request-round2/omega_cli/`, and its plan with every screen drawn, `plan/make-tui-menuconfig/plan.md`

The template in `~/.claude/scripts/dev/menu/` is the AIO menu cut down to one example page of each kind, on an example docker compose `Makefile`, with 38 passing tests. You copy it, keep its screens, and swap its example pages and targets for the repo's own.

`$ARGUMENTS` is optional notes on what goes in the menu, like `only the docker commands`. The repo is the current directory.

## What you end up with

```
<repo>/
├── Makefile                 # new, or the existing one with help: and menu: added
└── <name>_cli/              # its own uv project, so any repo can have one, Python or not
    ├── pyproject.toml       # textual==8.2.8, pytest==8.4.2, the <name>-menu script
    ├── .python-version
    ├── <name>_cli/
    │   ├── menu.py          # the app, the pages, the Run screen
    │   ├── commands.py      # each page's picks → make arguments
    │   └── progress.py      # the steps a make line goes through
    └── tests/
        ├── conftest.py      # a scratch root whose Makefile only echoes
        ├── test_commands.py
        ├── test_makefile.py # make -n, runs nothing
        └── test_menu.py     # the menu headless
```

`<name>` is the repo name's first word in lower case, like `Omega.Next.AIO` → `omega_cli` and `omega-menu`.

## Steps

1. Read the repo
   - the Makefile if there is one: its targets, flags and help
   - what else you type to run it, like README run lines, `package.json` scripts, `docker-compose*.yml`, `[project.scripts]`, `scripts/`
   - the values every command takes, like AIO's `ENV` and `Zone`, read from the real files, like the `.env.dev<N>` names
2. Draw the menu, then stop
   - every screen as a box like the two below, with the repo's real values, Home first
   - under them, the `make help` text the Makefile will print
   - which targets are kept, new, or get a new flag
   - wait for go or changes, and write nothing before
3. Write the Makefile, rules below
4. Copy the template
   ```bash
   cp -R ~/.claude/scripts/dev/menu/app_cli <name>_cli
   cd <name>_cli && mv app_cli <name>_cli
   grep -rl 'app_cli\|app-cli\|app-menu' . | xargs sed -i '' -e 's/app_cli/<name>_cli/g' -e 's/app-cli/<name>-cli/g' -e 's/app-menu/<name>-menu/g'
   ```
   - set `REPO = "App"` in `menu.py` to the repo's name, like `"Omega.Next.AIO"`
   - drop the template's `.gitignore` when the root one covers `.venv/` already
5. Fill in the pages
   - `commands.py`: each page's picks and the args they give, in place of `ENVS`, `VERBS`, `BUILDS`, `SETUP_STEPS`, `DROPPED`
   - `menu.py`: the pages between the two `# ---` lines, in place of `Home`, `DockerPage`, `FirstTimeSetupPage`; leave the shared screens and `Run` as they are
   - `progress.py`: `steps_for` and the `Step` regexes for each make line
6. Tests: rewrite the three test files for the real pages and targets, keep their helpers, then `uv run --directory <name>_cli pytest -q` until green
7. Check it in a terminal, below
8. Hand over: the files, the test count, and `make menu`

What step 2 draws, from the template:

```
╭──────────────────────────── App · menu ────────────────────────────╮
│             ↑↓ move · Enter opens ---> · Esc Esc exits             │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │   ENV (local)  --->                                            │ │
│ │    the stack runs with .env.local over .env                    │ │
│ │    --- Operation ---                                           │ │
│ │   Docker stack management  --->                                │ │
│ │    --- Others ---                                              │ │
│ │   First time setup  --->                                       │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                              < Exit >                              │
╰────────────────────────────────────────────────────────────────────╯

╭───────────────────────────── Running ──────────────────────────────╮
│ Up (detached) · build backend + frontend · ENV local               │
│                                                                    │
│  ✓ Build backend        0:07   · Start the stack                   │
│  > Build frontend       0:00                                       │
│                                                                    │
│ Build frontend  RUN step 1                                         │
│ ███████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  14%        │
│ 1 of 7 in the frontend image                         step 2 of 3   │
│                                                                    │
│ Elapsed 0:07                                                       │
│                < Show details >        < Stop >                    │
╰────────────────────────────────────────────────────────────────────╯
```

Step 7, in the repo root:

```bash
tmux new-session -d -s menu -x 92 -y 40 "make menu"
tmux send-keys -t menu Down Enter     # a few keys, then
tmux capture-pane -p -t menu          # read the screen before the next keys
tmux kill-session -t menu
```

- go through every screen, one run to the end, and one Stop
- wait for the screen to change between keys, a key sent while a run ends lands on the next screen, like on `< Exit >`
- ↑↓ move between rows and buttons, ← → do nothing, like in both reference menus
- a run that would touch something real, like `docker compose up`, runs with a stand-in on `PATH` that prints the same lines, like a `docker` script that echoes ` Image x-backend Building` and `#5 [stage-0 3/7] RUN …`
- after Stop, `pgrep -fl` the child it ran, nothing of make may be left

## The Makefile

Follow the template's `Makefile`: keep its shape, replace its targets.

- the header comment says what the commands are for, that a bare `make` lists them, and `make menu` picks them
- `.DEFAULT_GOAL := help` in a new Makefile; an existing one keeps its first target
- `define HELP … endef` and `help:` print it: `make menu` first, then a section per area, one line per command with its flags, then a flags line like `ENV=local|dev (default local) · DETACH=1`, then Examples of real tasks
- `menu:` checks for uv, like `make menu needs uv, like brew install uv`, then runs `uv run --project <name>_cli <name>-menu`
- every target has a `# comment` after it, in the same column
- a sub-command is an argument word, like `make build backend`, through `COMMAND`, `ARGS`, `ARGWORDS` and `$(ARGWORDS): @:`
- a bad value, or an argument word typed first, stops with `$(error …)` saying how to type it, like `BUILD is backend, frontend or none, like make up BUILD=backend`
- a recipe that needs something first says what to run, like `make up: no .env yet; run make setup env-file first`, then `exit 1`
- a recipe that deletes what you cannot get back asks for `yes` itself, like the template's `clean:`, so a terminal user is asked too
- a step with no line of its own echoes a plain `--- <step>` line, so the menu can tell where the run is
- an existing target keeps its recipe, the menu may only add a flag or a new target

## The menu

Keep the template's shared screens as they are, they are what makes it look like the other two. What goes on the pages:

- the menu builds make arguments and nothing else
- Home: the values every page uses as pickers, like `ENV (local)  --->`, a line saying what they mean, then `--- Operation ---` with one row per area, `--- Others ---` with `First time setup  --->`, then `< Exit >`
- a page is pickers, ticks and verbs for the things you do, not one row per make target, like AIO's Docker page: a Build picker, then Up, Up (detached), Down, Logs, Build only
- a picker row is `Name (value)  --->`, its box lists `(X)` or `( )`, the value and what it does; an option that cannot run now is greyed
- a tick is `[X]` or `[ ]`; Run and Show command grey out when nothing is ticked
- no page shows a make line: Show command, or `s` on a page of verbs, opens it in its own box, and a run's Output starts with `$ make …`
- Enter on a verb runs it at once when nothing is lost; Run this? asks first when something is, and when it cannot be undone Run stays off until you type `yes`
- the Run screen's first line is the picks, like `Up (detached) · build backend only · ENV local`; a second line says what it does when the first does not
- each long make line gets its steps in `steps_for`, so the screen shows `✓ > · - ✗`, each step's own time, and a bar from a count line like `  3/40 files  a.ttf` or BuildKit, or a sliding block when there is no count
- Logs has no steps, only the Output
- a failed run shows the line before make's own `make: *** … Error`, not the whole log
- nothing is saved between runs

## Tests

- `test_commands.py`: every pick gives its make args
- `test_makefile.py`: `make -n` of every line the menu runs, `make menu` itself, and each `$(error …)`; nothing starts
- `test_menu.py`: each page's rows in order, no make line on any page, Show command per verb, and each Run on a scratch Makefile: steps and bar, a failure's reason, Stop leaving nothing behind, Logs, the typed yes, Ctrl-Q

## Don't

- put logic in the menu that the Makefile does not have
- restyle the shared screens, change the 70-column boxes, or add a header or footer
- add a dependency besides textual and pytest, every pin is exact
- change an existing target's recipe beyond a new flag
- leave the example docker pages or targets in a repo that has no such stack

## Checklist before you hand it over

- [ ] the screens and `make help` were shown, and you got a go
- [ ] a bare `make` and `make help` list `make menu` first
- [ ] what `make help` lists, the menu can do, as a pick or a verb
- [ ] no page shows a make line
- [ ] tests green
- [ ] checked in tmux: every screen, one run to the end, one Stop with nothing left running

## Cross-References

- the README's `### Run` gets `make menu` → `/dev:create-readme-tldr`
