"""The make menu headless: its pages, the picks they hold, the make line each gives, and the Run screen.

Each test drives Menu on a scratch repo root (conftest.py), whose Makefile only says it ran, or prints
the lines a run test needs, so no test reaches docker.
"""

from __future__ import annotations

import os
import re
import time

import pytest
from conftest import makefile, screen_lines, until
from textual.widgets import Button, Input, Log, OptionList

from app_cli import menu


async def ready(pilot, selector: str):
    """The widget, once a Button takes presses again: it ignores one while it still shows the last (0.2 s)."""
    widget = pilot.app.screen.query_one(selector)
    await until(pilot, lambda: not widget.has_class("-active"))
    return widget


async def click(pilot, selector: str) -> None:
    await ready(pilot, selector)
    await pilot.click(selector)


async def open_row(pilot, row: str) -> None:
    """Press Enter on a row of the page on top."""
    (await ready(pilot, f"#{row}")).focus()
    await pilot.press("enter")
    await pilot.pause()


async def pick(pilot, row: str, option_id: str) -> None:
    """Open the `row` picker and choose `option_id` in it."""
    await open_row(pilot, row)
    options = pilot.app.screen.query_one(OptionList)
    options.highlighted = options.get_option_index(option_id)
    await pilot.press("enter")
    await pilot.pause()


def box_lines(screen) -> list[str]:
    """A modal box's own text, its title first, without the page drawn under it."""
    lines = [str(box.border_title) for box in screen.query(".box") if box.border_title]
    for widget in screen.query("Static, Button"):
        if widget.display:
            text = str(widget.label) if isinstance(widget, Button) else str(widget.render())
            lines += text.splitlines()
    return [line.strip() for line in lines if line.strip()]


async def show_command(pilot) -> list[str]:
    """Press s for Show command and read the box, then close it."""
    await pilot.press("s")
    await pilot.pause()
    assert isinstance(pilot.app.screen, menu.ShowCommand)
    lines = box_lines(pilot.app.screen)
    await pilot.press("escape")
    await pilot.pause()
    return lines


def in_order(lines: list[str], *wanted: str) -> bool:
    """Each wanted text is on its own line, top to bottom."""
    at = [next(i for i, line in enumerate(lines) if line == text) for text in wanted]
    return at == sorted(at)


def run_screen(pilot) -> menu.Run:
    assert isinstance(pilot.app.screen, menu.Run), type(pilot.app.screen).__name__
    return pilot.app.screen


def text_of(screen, widget_id: str) -> str:
    return str(screen.query_one(f"#{widget_id}").render())


def shown(screen, *ids: str) -> list[str]:
    return [i for i in ids if screen.query_one(f"#{i}").display]


def step_line(screen, name: str) -> str:
    """One step's mark, name and time, like `✓ Build backend     0:04`."""
    found = re.findall(rf"[✓>·\-✗] {re.escape(name)}(?:\s+\d+:\d\d)?", text_of(screen, "steps"))
    assert len(found) == 1, (name, text_of(screen, "steps"))
    return found[0].rstrip()


async def stop(pilot, screen) -> None:
    await click(pilot, "#stop")
    await pilot.pause()
    assert isinstance(pilot.app.screen, menu.StopAsk)
    await click(pilot, "#stop_now")
    await until(pilot, lambda: screen.code is not None)


# ------------------------------------------------------------ the pages


def test_home_shows_operation_and_others(drive):
    async def steps(pilot):
        lines = screen_lines(pilot.app)
        assert any("App · feat-some-branch" in line for line in lines)
        assert in_order(lines, "ENV (local)  --->", "the stack runs with .env.local over .env",
                        "--- Operation ---", "Docker stack management  --->",
                        "--- Others ---", "First time setup  --->", "< Exit >")
        await pick(pilot, "env", "dev")
        assert "the stack runs with .env.dev, the dev server's settings" in screen_lines(pilot.app)

    drive(steps)


def test_no_page_shows_a_make_line(drive):
    async def steps(pilot):
        for row in ("docker", "setup", None):
            if row:
                await open_row(pilot, row)
            assert not [line for line in screen_lines(pilot.app) if "make " in line], row
            if row:
                await pilot.press("escape")
                await pilot.pause()

    drive(steps)


def test_show_command_shows_the_make_line_of_the_focused_verb(drive):
    async def steps(pilot):
        await pick(pilot, "env", "dev")
        await open_row(pilot, "docker")
        await pick(pilot, "build", "backend")
        pilot.app.screen.query_one("#verb_up-detached").focus()
        assert await show_command(pilot) == [
            "Command", "Up (detached) · build backend only · ENV dev", "make up ENV=dev BUILD=backend DETACH=1",
            "< Back >"]
        pilot.app.screen.query_one("#verb_logs").focus()
        assert "make logs ENV=dev" in await show_command(pilot)

    drive(steps)


def test_build_nothing_greys_build_only(drive):
    async def steps(pilot):
        await open_row(pilot, "docker")
        await pick(pilot, "build", "none")
        assert str(pilot.app.screen.query_one("#build", Button).label) == "Build (nothing)  --->"
        assert pilot.app.screen.query_one("#verb_build", Button).disabled

    drive(steps)


def test_first_time_setup_ticks(drive):
    async def steps(pilot):
        await open_row(pilot, "setup")
        page = pilot.app.screen
        await pilot.press("space")  # unticks Copy .env.example to .env
        await pilot.pause()
        assert page.picks() == menu.FirstTimeSetup(env_file=False, git_hook=True)
        await click(pilot, "#show")
        await pilot.pause()
        assert "make setup git-hook" in box_lines(pilot.app.screen)
        await pilot.press("escape")
        page.query_one("#git_hook").focus()
        await pilot.press("space")
        await pilot.pause()
        assert page.query_one("#run", Button).disabled and page.query_one("#show", Button).disabled

    drive(steps)


def test_esc_backs_out_and_esc_esc_exits(drive):
    async def steps(pilot):
        await open_row(pilot, "docker")
        assert isinstance(pilot.app.screen, menu.DockerPage)
        await pilot.press("escape")
        await pilot.pause()
        assert len(pilot.app.screen_stack) == 1  # home
        await pilot.press("escape")
        await pilot.pause()
        assert pilot.app.return_code is None  # one Esc only says so
        await pilot.press("escape")
        await pilot.pause()

    app = drive(steps)
    assert app.return_code == 0


# ------------------------------------------------------------ the Run screen, each on a scratch Makefile

UP = """up:
> @echo ' Image feat-some-branch-backend Building'
> @echo '#5 [stage-0 3/7] RUN pip install -r requirements.txt'; sleep 1
> @echo '#6 [stage-0 7/7] COPY . .'
> @echo 'docker compose --env-file .env up -d'
> @echo ' Container feat-some-branch-backend-1  Started'
"""


def test_run_shows_steps_bar_and_finishes(drive, scratch_root):
    makefile(scratch_root, UP)

    async def steps(pilot):
        await open_row(pilot, "docker")
        await pick(pilot, "build", "backend")
        await open_row(pilot, "verb_up-detached")
        screen = run_screen(pilot)
        assert screen.args == ["up", "BUILD=backend", "DETACH=1"]
        assert screen.box.border_title == "Running"
        assert text_of(screen, "header").splitlines() == ["Up (detached) · build backend only · ENV local"]
        await until(pilot, lambda: screen.progress.done == 3)
        assert step_line(screen, "Build backend").startswith("> Build backend")
        assert step_line(screen, "Start the stack") == "· Start the stack"
        assert text_of(screen, "item") == "Build backend  RUN pip install -r requirements.txt"
        assert text_of(screen, "bar").endswith(" 43%")
        counts = text_of(screen, "counts")
        assert counts.startswith("3 of 7 in the backend image") and counts.endswith("step 1 of 2")
        await until(pilot, lambda: screen.code is not None)
        assert screen.box.border_title == "Finished"
        assert step_line(screen, "Build backend").startswith("✓ Build backend")
        assert step_line(screen, "Start the stack").startswith("✓ Start the stack")
        assert text_of(screen, "header").splitlines()[1].startswith("ended after 0:0")
        assert shown(screen, "show", "back", "exit", "running", "bar") == ["show", "back", "exit"]
        await click(pilot, "#show")
        await pilot.pause()
        assert screen.query_one("#output", Log).lines[0] == "$ make up BUILD=backend DETACH=1"
        await click(pilot, "#back")
        await pilot.pause()
        assert isinstance(pilot.app.screen, menu.DockerPage)

    drive(steps)


def test_a_step_with_no_count_slides_and_ticks(drive, scratch_root):
    makefile(scratch_root, "down:\n> @echo 'Container x-backend-1  Stopping'; sleep 2\n")

    async def steps(pilot):
        await open_row(pilot, "docker")
        await open_row(pilot, "verb_down")
        screen = run_screen(pilot)
        await until(pilot, lambda: screen.lines)
        first = text_of(screen, "bar")
        assert "██████████" in first and "%" not in first
        assert text_of(screen, "counts").startswith("no count here: the block slides while it runs")
        await until(pilot, lambda: text_of(screen, "bar") != first, seconds=3)
        assert step_line(screen, "Down").startswith("> Down")

    drive(steps)


@pytest.mark.parametrize("line", ["docker compose up -d", "docker compose up",
                                  "docker compose --env-file .env --env-file .env.local up -d"])
def test_start_the_stack_starts_on_each_compose_up_line(line):
    progress = menu.Progress(menu.steps_for(["up", "BUILD=none"]))
    progress.feed(line, 1.0)
    assert progress.steps[progress.current].name == "Start the stack"


def test_sliding_block_moves_two_cells_a_second():
    assert menu.sliding(0).startswith("█" * menu.BLOCK)
    assert menu.sliding(1).startswith("░░" + "█" * menu.BLOCK)
    assert len(menu.sliding(7.3)) == menu.BAR


def test_failed_marks_the_step_and_shows_the_reason(drive, scratch_root):
    makefile(scratch_root, """up:
> @echo ' Image feat-some-branch-backend Building'
> @echo "make up: no .env yet; run make setup env-file first"; exit 1
""")

    async def steps(pilot):
        await open_row(pilot, "docker")
        await pick(pilot, "build", "backend")
        await open_row(pilot, "verb_up")
        screen = run_screen(pilot)
        await until(pilot, lambda: screen.code is not None)
        assert screen.box.border_title == "Failed"
        assert step_line(screen, "Build backend").startswith("✗ Build backend")
        assert step_line(screen, "Start the stack") == "· Start the stack"
        assert text_of(screen, "header").splitlines()[1].startswith("make exited 2 after 0:0")
        assert text_of(screen, "outcome") == "make up: no .env yet; run make setup env-file first"
        await click(pilot, "#show")
        await pilot.pause()
        assert screen.query_one("#output", Log).lines[-1].startswith("make: *** [")

    drive(steps)


def test_reason_is_the_line_before_makes_own_error():
    lines = ["building", "ERROR: failed to solve: process did not complete", "make[1]: *** [build] Error 1",
             "make: *** [up] Error 2"]
    assert menu.reason(lines, 2) == "ERROR: failed to solve: process did not complete"
    assert menu.reason(["make: *** No rule to make target 'x'.  Stop."], 2) == (
        "make: *** No rule to make target 'x'.  Stop.")
    assert menu.reason([], 3) == "make exited 3 and printed nothing"


def test_stop_ends_make_and_its_sleep(drive, scratch_root):
    makefile(scratch_root, "down:\n> @echo stopping; sleep 30\n")
    seen = {}

    async def steps(pilot):
        await open_row(pilot, "docker")
        await open_row(pilot, "verb_down")
        screen = run_screen(pilot)
        await until(pilot, lambda: screen.lines == ["stopping"])
        seen["pid"] = screen.process.pid
        os.killpg(seen["pid"], 0)  # make leads its own group, with sh and sleep in it
        started = time.monotonic()
        await stop(pilot, screen)
        assert time.monotonic() - started < 3
        assert screen.box.border_title == "Stopped"
        assert step_line(screen, "Down").startswith("- Down")
        await pilot.press("escape")  # once it ended, Esc is Back
        await pilot.pause()
        assert isinstance(pilot.app.screen, menu.DockerPage)

    drive(steps)
    with pytest.raises(ProcessLookupError):
        os.killpg(seen["pid"], 0)  # nothing of make's group is left


def test_logs_has_no_steps_and_stop_only(drive, scratch_root):
    makefile(scratch_root, "logs:\n> @echo 'backend-1  | INFO:     Started server process [1]'; sleep 30\n")

    async def steps(pilot):
        await open_row(pilot, "docker")
        await open_row(pilot, "verb_logs")
        screen = run_screen(pilot)
        assert screen.box.border_title == "Logs"
        assert text_of(screen, "header").splitlines() == [
            "Logs · the stack, the last 200 lines, then live", "Stop ends the logs only; the stack keeps running"]
        assert shown(screen, "steps", "item", "bar", "counts", "output") == ["output"]
        assert shown(screen, "details", "stop") == ["stop"]
        output = screen.query_one("#output", Log)
        await until(pilot, lambda: len(output.lines) == 2)
        assert output.lines == ["$ make logs", "backend-1  | INFO:     Started server process [1]"]
        await stop(pilot, screen)
        assert screen.box.border_title == "Stopped"

    drive(steps)


def test_delete_data_stays_off_until_yes_and_sends_yes(drive, scratch_root):
    makefile(scratch_root, """clean:
> @read answer; test "$$answer" = yes || { echo "make clean: kept .data/"; exit 1; }
> @echo "deleted .data/; the next make up starts empty"
""")

    async def steps(pilot):
        await open_row(pilot, "docker")
        await open_row(pilot, "verb_clean")
        confirm = pilot.app.screen
        assert isinstance(confirm, menu.Confirm)
        assert box_lines(confirm)[:2] == ["Run this?", "Delete .data/ · ENV local"]
        assert confirm.query_one("#confirm_run", Button).disabled
        confirm.query_one("#typed", Input).value = "ye"
        await pilot.pause()
        assert confirm.query_one("#confirm_run", Button).disabled
        confirm.query_one("#typed", Input).value = "yes"
        await pilot.pause()
        await click(pilot, "#confirm_run")
        await pilot.pause()
        screen = run_screen(pilot)
        await until(pilot, lambda: screen.code is not None)
        assert screen.box.border_title == "Finished"
        assert screen.lines == ["deleted .data/; the next make up starts empty"]

    drive(steps)


def test_ctrl_q_while_running_asks_to_stop(drive, scratch_root):
    makefile(scratch_root, "down:\n> @echo stopping; sleep 30\n")

    async def steps(pilot):
        await open_row(pilot, "docker")
        await open_row(pilot, "verb_down")
        screen = run_screen(pilot)
        await until(pilot, lambda: screen.process is not None)
        await pilot.press("escape")  # Esc does nothing while make runs
        await pilot.pause()
        assert pilot.app.screen is screen
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert isinstance(pilot.app.screen, menu.StopAsk)
        await click(pilot, "#keep_going")
        await pilot.pause()
        assert pilot.app.screen is screen and screen.process.returncode is None  # still running
        await pilot.press("ctrl+q")
        await pilot.pause()
        await click(pilot, "#stop_now")
        await until(pilot, lambda: screen.code is not None)
        assert screen.box.border_title == "Stopped"
        await pilot.press("ctrl+q")  # nothing runs now: Ctrl-Q leaves
        await pilot.pause()

    app = drive(steps)
    assert app.return_code == 0


def test_main_runs_the_menu_at_the_repo_root(monkeypatch):
    ran = []
    monkeypatch.setattr(menu.Menu, "run", lambda self: ran.append(self.root))
    assert menu.main() == 0
    assert ran == [menu.ROOT]
    assert (menu.ROOT / "Makefile").is_file() and (menu.ROOT / "app_cli" / "pyproject.toml").is_file()
