"""make menu: pick a page, its options and a verb, and the menu runs the make line they give.

    make menu               # at the repo root; or: uv run --project app_cli app-menu

Every page is pickers, ticks and verbs; no page shows a make line. Show command shows it, and a
run's Output starts with it. What a command does stays in the root Makefile, so a terminal user
gets the same lines.
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, Log, OptionList, Static
from textual.widgets.option_list import Option

from app_cli.commands import (
    ASKS,
    BUILDS,
    ENVS,
    SETUP_STEPS,
    VERBS,
    Docker,
    FirstTimeSetup,
    Picks,
    child_env,
    docker_args,
    setup_args,
    title,
)
from app_cli.progress import Progress, steps_for

ROOT = Path(__file__).resolve().parents[2]  # the repo root, whose Makefile every run uses
REPO = "App"
# The app's own up and down never reach a modal screen, so the ones with ticks or buttons bind them too.
ARROWS = [
    Binding("up", "app.focus_previous", show=False),
    Binding("down", "app.focus_next", show=False),
]

BAR = 54  # cells in a progress bar
BLOCK = 10  # the sliding block's cells, for a step with no count
WIDTH = 64  # a run screen's text, inside its border
MARKS = {"": "·", "now": ">", "done": "✓", "skipped": "-", "stopped": "-", "failed": "✗"}
# make's own last words, like `make: *** [up] Error 1` or `make[1]: *** [build] Error 2`
MAKE_ERROR = re.compile(r"^g?make(?:\[\d+\])?: \*\*\* ")
LOGS = "Logs · the stack, the last 200 lines, then live"


def mark(on: bool) -> str:
    return "(X)" if on else "( )"


def bar(fraction: float) -> str:
    """Like ██████░░░░  25%; 100% only when it is all in."""
    fraction = min(max(fraction, 0.0), 1.0)
    percent = round(fraction * 100) if fraction == 1 else min(round(fraction * 100), 99)
    filled = int(BAR * fraction)
    return "█" * filled + "░" * (BAR - filled) + f" {percent:>3}%"


def sliding(seconds: float) -> str:
    """A step with no count: a block that slides 2 cells a second, so the screen moves while it runs."""
    at = int(seconds * 2) % (BAR - BLOCK + 1)
    return "░" * at + "█" * BLOCK + "░" * (BAR - BLOCK - at)


def elapsed(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def spread(left: str, right: str) -> str:
    return left + " " * max(2, WIDTH - len(left) - len(right)) + right


def cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[:width - 1] + "…"


def reason(lines: list[str], code: int) -> str:
    """Why make failed: the last line before its own `make: *** … Error` lines."""
    said = [line.strip() for line in lines if line.strip()]
    errors = [index for index, line in enumerate(said) if MAKE_ERROR.match(line)]
    if errors:
        first = errors[-1]
        while first > 0 and MAKE_ERROR.match(said[first - 1]):
            first -= 1
        return said[first - 1] if first else said[first]
    return said[-1] if said else f"make exited {code} and printed nothing"


class Tick(Checkbox):
    """A checkbox drawn [X] or [ ]."""

    def render(self) -> Content:
        label = self.label.stylize_before(self.get_visual_style("toggle--label"))
        return Content.assemble("[X] " if self.value else "[ ] ", label)


class Picker(ModalScreen[str | None]):
    """One of a list: Enter picks the highlighted option, Esc keeps the current one; a greyed one cannot be picked."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, box_title: str, options: list[Option], current: str) -> None:
        super().__init__()
        self.box_title = box_title
        self.options = options
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(classes="box") as box:
            box.border_title = f"{self.box_title} (one of)"
            yield OptionList(*self.options)
            yield Static("Enter picks · Esc keeps the current one", classes="hint")

    def on_mount(self) -> None:
        options = self.query_one(OptionList)
        options.highlighted = options.get_option_index(self.current)
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option.id)


class ShowCommand(ModalScreen[None]):
    """The make line the picks give: the only place a page shows it."""

    BINDINGS = [Binding("escape", "dismiss", "Back")]

    def __init__(self, heading: str, command: str) -> None:
        super().__init__()
        self.heading = heading
        self.command = command

    def compose(self) -> ComposeResult:
        with Vertical(classes="box", id="command_box") as box:
            box.border_title = "Command"
            yield Static(Content(self.heading), id="heading")
            yield Static(Content(self.command), id="command")
            with Horizontal(classes="buttons"):
                yield Button("< Back >", id="back", compact=True)

    def on_mount(self) -> None:
        self.query_one("#back").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss()


class Confirm(ModalScreen[bool]):
    """Run this? for a pick that loses something; a typed one keeps Run off until you type yes."""

    BINDINGS = [Binding("escape", "dismiss(False)", "Back"), *ARROWS]

    def __init__(self, heading: str, text: str, typed: bool) -> None:
        super().__init__()
        self.heading = heading
        self.text = text
        self.typed = typed

    def compose(self) -> ComposeResult:
        with Vertical(classes="box", id="confirm") as box:
            box.border_title = "Run this?"
            yield Static(Content(self.heading), id="heading")
            yield Static(Content(self.text), id="summary")
            if self.typed:
                yield Static("This cannot be undone. Type yes to turn Run on:", id="prompt")
                yield Input(id="typed", compact=True)
            with Horizontal(classes="buttons"):
                yield Button("< Run >", id="confirm_run", disabled=self.typed, compact=True)
                yield Button("< Back >", id="back", compact=True)

    def on_mount(self) -> None:
        self.query_one("#typed" if self.typed else "#confirm_run").focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.query_one("#confirm_run", Button).disabled = event.value != "yes"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm_run")


class Page(Screen[None]):
    """A framed page: its title, a hint, the bordered #menu of rows, then the buttons row."""

    HEADING = ""
    HINT = ""
    BINDINGS = [Binding("escape", "back", show=False), *ARROWS]

    def compose(self) -> ComposeResult:
        with Vertical(classes="box frame") as frame:
            frame.border_title = self.HEADING
            yield Static(self.HINT, classes="hint")
            with Vertical(id="menu"):
                yield from self.rows()
            with Horizontal(classes="buttons"):
                yield from self.buttons()

    def rows(self) -> ComposeResult:
        yield from ()

    def buttons(self) -> ComposeResult:
        yield from ()

    def action_back(self) -> None:
        self.app.pop_screen()

    def line(self, widget_id: str, text: str) -> None:
        self.query_one(f"#{widget_id}", Static).update(Content(text))

    def show_command(self, heading: str, args: list[str]) -> None:
        self.app.push_screen(ShowCommand(heading, "make " + " ".join(args)))


# ------------------------------------------------------------ the pages: replace these with the repo's own


class Home(Page):
    """ENV, which every page uses, then the Operation areas and Others."""

    HINT = "↑↓ move · Enter opens ---> · Esc Esc exits"
    BINDINGS = [Binding("escape", "escape", show=False), *ARROWS]

    def __init__(self) -> None:
        super().__init__()
        self.escaped_at = 0.0

    def rows(self) -> ComposeResult:
        yield Button("", id="env", compact=True)
        yield Static("", id="target", classes="line")
        yield Static("--- Operation ---", classes="line")
        yield Button("Docker stack management  --->", id="docker", compact=True)
        yield Static("--- Others ---", classes="line")
        yield Button("First time setup  --->", id="setup", compact=True)

    def buttons(self) -> ComposeResult:
        yield Button("< Exit >", id="exit", compact=True)

    def on_mount(self) -> None:
        root = self.app.root.name
        self.query_one(".frame").border_title = REPO if root == REPO else f"{REPO} · {root}"
        self.refresh_rows()

    def refresh_rows(self) -> None:
        env = self.app.env
        self.query_one("#env", Button).label = Content(f"ENV ({env})  --->")
        self.line("target", f"the stack runs {ENVS[env]}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        app = self.app
        if event.button.id == "env":
            options = [Option(f"{mark(env == app.env)} {env:<7} {does}", id=env) for env, does in ENVS.items()]
            app.push_screen(Picker("ENV", options, app.env), self.picked)
        elif event.button.id == "docker":
            app.push_screen(DockerPage())
        elif event.button.id == "setup":
            app.push_screen(FirstTimeSetupPage())
        elif event.button.id == "exit":
            app.exit()

    def picked(self, value: str | None) -> None:
        if value is not None:
            self.app.env = value
            self.refresh_rows()

    def action_escape(self) -> None:
        now = time.monotonic()
        if now - self.escaped_at < 1.5:
            self.app.exit()
        else:
            self.escaped_at = now
            self.notify("Esc again to exit")


class DockerPage(Page):
    """The Build picker, then the verbs; Enter on a verb runs it at once, Delete .data/ asks first."""

    HEADING = "Docker stack management"
    HINT = "↑↓ move · Enter runs or opens ---> · s Show command · Esc back"
    # ↓ from a verb row to < Show command > passes the other verbs, so only s reaches the ones below Up.
    BINDINGS = [Binding("s", "show_command", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self.build = "both"
        self.verb = "up"  # the verb row last focused, which Show command shows

    def rows(self) -> ComposeResult:
        yield Static("", id="target", classes="line")
        yield Button("", id="build", compact=True)
        yield Static("--- Run ---", classes="line")
        for verb, text in VERBS.items():
            yield Button(text, id=f"verb_{verb}", compact=True)

    def buttons(self) -> ComposeResult:
        yield Button("< Show command >", id="show", compact=True)
        yield Button("< Back >", id="back", compact=True)

    def on_mount(self) -> None:
        self.line("target", f"the stack runs {ENVS[self.app.env]}")
        self.refresh_rows()
        self.query_one("#build").focus()

    def refresh_rows(self) -> None:
        self.query_one("#build", Button).label = Content(f"Build ({BUILDS[self.build][0]})  --->")
        self.query_one("#verb_build", Button).disabled = self.build == "none"

    def on_descendant_focus(self, event) -> None:
        if (event.widget.id or "").startswith("verb_"):
            self.verb = event.widget.id.removeprefix("verb_")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        app, button = self.app, event.button.id or ""
        if button == "build":
            options = [Option(f"{mark(build == self.build)} {text:<21}{does}".rstrip(), id=build)
                       for build, (text, does) in BUILDS.items()]
            app.push_screen(Picker("Build before Up", options, self.build), self.picked)
        elif button.startswith("verb_"):
            picks = Docker(button.removeprefix("verb_"), self.build)
            args = docker_args(picks, app.env)
            if picks.verb in ASKS:
                app.push_screen(Confirm(title(picks, app.env), "stops the stack, then deletes .data/,\n"
                                        "the files its containers keep", typed=True),
                                lambda run: app.start_run(picks, args, typed=True) if run else None)
            else:
                app.start_run(picks, args)
        elif button == "show":
            self.action_show_command()
        elif button == "back":
            self.action_back()

    def action_show_command(self) -> None:
        """The verb row that has focus, or the one last focused."""
        picks = Docker(self.verb if self.verb != "build" or self.build != "none" else "up", self.build)
        self.show_command(title(picks, self.app.env), docker_args(picks, self.app.env))

    def picked(self, value: str | None) -> None:
        if value is not None:
            self.build = value
            self.refresh_rows()


class FirstTimeSetupPage(Page):
    """make setup, every step or the ticked ones: run once after clone."""

    HEADING = "First time setup"
    HINT = "↑↓ move · Space ticks · Esc back"

    def rows(self) -> ComposeResult:
        yield Static("once after clone", classes="line")
        for name, (label, _) in SETUP_STEPS.items():
            yield Tick(label, True, id=name, compact=True)

    def buttons(self) -> ComposeResult:
        yield Button("< Run >", id="run", compact=True)
        yield Button("< Show command >", id="show", compact=True)
        yield Button("< Back >", id="back", compact=True)

    def on_mount(self) -> None:
        self.query_one(Tick).focus()

    def picks(self) -> FirstTimeSetup:
        return FirstTimeSetup(**{name: self.query_one(f"#{name}", Tick).value for name in SETUP_STEPS})

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        event.stop()
        nothing = not any(self.query_one(f"#{name}", Tick).value for name in SETUP_STEPS)
        self.query_one("#run", Button).disabled = nothing
        self.query_one("#show", Button).disabled = nothing

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        app, picks = self.app, self.picks()
        if event.button.id == "run":
            app.start_run(picks, setup_args(picks))
        elif event.button.id == "show":
            self.show_command(title(picks, app.env), setup_args(picks))
        elif event.button.id == "back":
            self.action_back()


# ------------------------------------------------------------ the app and the Run screen: keep as they are


class Menu(App[None]):
    """Home is the bottom screen; each page, and each run, opens over it."""

    TITLE = "make menu"
    CSS = """
    Screen { align: center middle; }
    ModalScreen { align: center middle; }
    .box { width: auto; max-width: 96%; height: auto; border: round $accent;
           border-title-align: center; padding: 0 1; }
    .frame { width: 70; }
    .hint { width: 100%; text-align: center; color: $text-muted; }
    #menu { height: auto; border: solid $panel-lighten-2; }
    #menu Button { width: 100%; text-align: left; content-align: left middle; padding-left: 2; }
    #menu Checkbox { width: 100%; padding-left: 3; }
    #menu .line { padding-left: 4; color: $text-muted; }
    .buttons { width: 100%; height: 1; align: center middle; margin-top: 1; }
    .buttons Button { margin: 0 3; }
    #confirm, #command_box { width: 70; padding: 0 1; }
    #confirm #summary, #command_box #command { margin-top: 1; }
    #prompt { margin-top: 1; }
    #run_box { width: 70; padding: 0 1; }
    #header, #steps { margin-bottom: 1; }
    #steps, #item, #bar, #counts { text-wrap: nowrap; }
    #outcome { margin-bottom: 1; }
    #output { height: 7; border: round $panel-lighten-2; border-title-align: left;
              scrollbar-size-vertical: 1; scrollbar-size-horizontal: 0; }
    #elapsed { margin-top: 1; }
    #ended Button { margin: 0 1; }
    #ask { width: 70; padding: 1 2; }
    Picker .box { width: auto; min-width: 46; padding: 1 2; }
    Picker OptionList { width: auto; height: auto; border: none; }
    Picker .hint { margin-top: 1; text-align: left; }
    """
    BINDINGS = [*ARROWS]

    def __init__(self, root: Path = ROOT) -> None:
        super().__init__()
        self.root = root
        self.env = "local"

    def get_default_screen(self) -> Screen:
        return Home()

    def start_run(self, picks: Picks, args: list[str], typed: bool = False) -> None:
        """Open a Run over the page; Back on it shows the page again."""
        heading = LOGS if args[0] == "logs" else title(picks, self.env)
        self.push_screen(Run(args, heading, self.subtitle(args), typed))

    def subtitle(self, args: list[str]) -> str:
        """The Run screen's second line: what the run does, in a few words; "" when the title says it."""
        return {"logs": "Stop ends the logs only; the stack keeps running",
                "clean": "stops the stack, then deletes .data/"}.get(args[0], "")

    async def action_quit(self) -> None:
        """Ctrl-Q: while make runs, ask to stop it instead of leaving it behind."""
        runs = [screen for screen in self.screen_stack if isinstance(screen, Run) and screen.running()]
        if runs:
            runs[-1].action_ask_stop()
        else:
            self.exit()


class StopAsk(ModalScreen[bool]):
    """Stop? first, from Stop, Ctrl-C or Ctrl-Q."""

    BINDINGS = [Binding("escape", "dismiss(False)", "Keep going"), *ARROWS]

    def __init__(self, label: str, text: str) -> None:
        super().__init__()
        self.label = label
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(classes="box", id="ask") as box:
            box.border_title = f"Stop {self.label}?"
            yield Static(Content(self.text), id="stop_text")
            with Horizontal(classes="buttons"):
                yield Button("< Keep going >", id="keep_going", compact=True)
                yield Button("< Stop >", id="stop_now", compact=True)

    def on_mount(self) -> None:
        self.query_one("#keep_going").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "stop_now")


class Run(Screen[None]):
    """One make run: its steps, a bar and the current item, the Output; then Finished, Failed or Stopped."""

    BINDINGS = [
        Binding("ctrl+c", "ask_stop", show=False, priority=True),
        Binding("escape", "back", show=False),
        *ARROWS,
    ]

    def __init__(self, args: list[str], heading: str, subtitle: str, typed: bool = False) -> None:
        super().__init__()
        self.args = args
        self.heading = heading
        self.subtitle = subtitle
        self.typed = typed  # make asks for yes on its own, and Run writes it once
        self.logs = args[0] == "logs"
        self.progress = Progress(steps_for(args))
        self.lines: list[str] = []  # everything make printed
        self.process: asyncio.subprocess.Process | None = None
        self.code: int | None = None  # make's exit code, once it ended
        self.stopped = False  # you pressed Stop
        self.started = time.monotonic()
        self.ended: float | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="box", id="run_box") as box:
            self.box = box
            box.border_title = "Logs" if self.logs else "Running"
            yield Static("", id="header")
            yield Static("", id="steps")
            yield Static("", id="item")
            yield Static("", id="bar")
            yield Static("", id="counts")
            yield Static("", id="outcome")
            yield Log(id="output", auto_scroll=True)
            yield Static("", id="elapsed")
            with Horizontal(classes="buttons", id="running"):
                yield Button("< Show details >", id="details", compact=True)
                yield Button("< Stop >", id="stop", compact=True)
            with Horizontal(classes="buttons", id="ended"):
                yield Button("< Show details >", id="show", compact=True)
                yield Button("< Back >", id="back", compact=True)
                yield Button("< Exit >", id="exit", compact=True)

    def on_mount(self) -> None:
        self.query_one("#output", Log).border_title = "Output"
        for widget in ("#outcome", "#ended"):
            self.query_one(widget).display = False
        self.query_one("#output").display = self.logs
        self.query_one("#details").display = not self.logs
        for widget in ("#steps", "#item", "#bar", "#counts"):
            self.query_one(widget).display = not self.logs
        self.query_one("#stop").focus()
        self.progress.begin(self.started)
        self.show()
        self.set_interval(0.25, self.show)
        self.run_worker(self.run_child(), exclusive=True)

    async def run_child(self) -> None:
        # Its own group, so Stop reaches make's children too; Windows has CTRL_BREAK for a group instead.
        group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32"
                 else {"start_new_session": True})
        output = self.query_one(Log)
        output.write_line("$ make " + shlex.join(self.args))
        try:
            self.process = await asyncio.create_subprocess_exec(
                "make", *self.args, cwd=self.app.root, env=child_env(os.environ),
                stdin=asyncio.subprocess.PIPE if self.typed else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, limit=1 << 20, **group,
            )
        except OSError as error:  # no make on PATH
            self.lines.append(str(error))
            output.write_line(str(error))
            self.code = 127
        else:
            if self.typed:
                self.process.stdin.write(b"yes\n")
                await self.process.stdin.drain()
                self.process.stdin.close()
            async for raw in self.process.stdout:
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                self.lines.append(line)
                self.progress.feed(line, time.monotonic())
                output.write_line(line)
                self.show()
            self.code = await self.process.wait()
        self.ended = time.monotonic()
        self.progress.end(self.code, self.stopped, self.ended)
        self.finished()

    def running(self) -> bool:
        return self.code is None

    def stop_child(self) -> None:
        """Stop? said Stop."""
        if self.interrupt():
            self.stopped = True
            stop = self.query_one("#stop", Button)
            stop.label, stop.disabled = "< Stopping >", True

    def interrupt(self) -> bool:
        """Ctrl-C to make and everything it started, the way Ctrl-C does in a terminal; False once it ended."""
        if self.process is None or self.process.returncode is not None:
            return False
        try:
            if sys.platform == "win32":
                self.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(self.process.pid, signal.SIGINT)
        except ProcessLookupError:  # it ended on its own just now
            return False
        return True

    def on_unmount(self) -> None:
        self.interrupt()  # never leave make behind, even when the menu goes

    # ------------------------------------------------------------ what you see

    def now(self) -> float:
        return self.ended or time.monotonic()

    def show(self) -> None:
        if not self.is_mounted:
            return
        now = self.now()
        lines = [self.heading]
        if self.code is None:
            lines += [self.subtitle] if self.subtitle else []
        else:
            lines.append(self.ended_line())
        self.query_one("#header", Static).update(Content("\n".join(lines)))
        self.query_one("#elapsed", Static).update(Content(f"Elapsed {elapsed(now - self.started)}"))
        if self.logs:
            return
        self.query_one("#steps", Static).update(Content(self.steps_text(now)))
        p = self.progress
        if self.code is None and p.current >= 0 and p.state[p.current] == "now":
            step = p.steps[p.current]
            if p.building():
                item = cut(f"{step.name}  {p.item}", WIDTH)
            else:
                said = p.item or next((line.strip() for line in reversed(self.lines) if line.strip()), "")
                item = spread(step.name, cut(said, WIDTH - len(step.name) - 2))
            self.query_one("#item", Static).update(Content(item))
            self.query_one("#bar", Static).update(bar(p.fraction()) if p.total else sliding(now - p.started))
            self.query_one("#counts", Static).update(
                Content(spread(p.counts(), f"step {p.current + 1} of {len(p.steps)}")))

    def steps_text(self, now: float) -> str:
        """The steps in two columns, each with its mark and its own time."""
        p = self.progress
        cells = []
        for index, step in enumerate(p.steps):
            state = p.state[index]
            seconds = p.step_seconds(index, now)
            ran = state in ("now", "done", "failed", "stopped") or (state == "skipped" and seconds > 0)
            cells.append(f"{MARKS[state]} {step.name:<19}{elapsed(seconds) if ran else '':>6}")
        half = (len(cells) + 1) // 2
        left, right = cells[:half], cells[half:]
        return "\n".join(f" {a}   {b}".rstrip() for a, b in zip(left, right + [""] * (half - len(right))))

    def ended_line(self) -> str:
        """Under the title once make ended: how long it took, and how it ended."""
        took = elapsed(self.ended - self.started)
        if self.stopped:
            return f"stopped after {took}"
        return f"ended after {took}" if self.code == 0 else f"make exited {self.code} after {took}"

    def outcome(self) -> str:
        """Why it failed; "" when it finished or you stopped it."""
        return reason(self.lines, self.code) if self.code and not self.stopped else ""

    def finished(self) -> None:
        """Finished, Failed or Stopped, with the buttons each one has."""
        self.box.border_title = "Stopped" if self.stopped else "Finished" if self.code == 0 else "Failed"
        text = self.outcome()
        self.query_one("#outcome", Static).update(Content(text))
        self.query_one("#outcome").display = bool(text)
        for widget in ("#item", "#bar", "#counts", "#running"):
            self.query_one(widget).display = False
        self.query_one("#ended").display = True
        self.query_one("#show").display = not self.stopped and not self.logs
        self.show()
        self.query_one("#back", Button).focus()

    # ------------------------------------------------------------ what you do

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button = event.button
        if button.id in ("details", "show"):
            output = self.query_one("#output", Log)
            output.display = not output.display
            button.label = "< Hide details >" if output.display else "< Show details >"
        elif button.id == "stop":
            self.action_ask_stop()
        elif button.id == "back":
            self.action_back()
        elif button.id == "exit":
            self.app.exit()

    def action_ask_stop(self) -> None:
        """Stop, Ctrl-C and Ctrl-Q: Stop? first."""
        if not self.running() or isinstance(self.app.screen, StopAsk):
            return
        text = "Stop sends Ctrl-C to make and everything it started,\nthe way Ctrl-C does in a terminal."
        if self.logs:
            text += "\nThe logs end; the stack keeps running."
        self.app.push_screen(StopAsk(self.heading.split(" · ")[0], text),
                             lambda stop: self.stop_child() if stop else None)

    def action_back(self) -> None:
        if not self.running():
            self.app.pop_screen()


def main() -> int:
    Menu(ROOT).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
