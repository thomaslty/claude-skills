"""A scratch repo root per test, and the helpers that drive the menu on it headless.

The menu runs make at the root it is given, so a run test writes its own Makefile into the scratch root
and nothing reaches docker or the repo's own files.
"""

from __future__ import annotations

import asyncio
import time

import pytest

# Each target says it ran; a run test writes the recipe it needs over this.
TARGETS = "up down build logs clean setup backend frontend env-file git-hook"
MAKEFILE = f"""\
.PHONY: {TARGETS}
up down build logs clean setup:
\t@echo "ran $(MAKECMDGOALS)"
backend frontend env-file git-hook:
\t@:
"""


@pytest.fixture
def scratch_root(tmp_path):
    """A repo root named like a worktree of App, with the Makefile above."""
    root = tmp_path / "feat-some-branch"
    root.mkdir()
    (root / "Makefile").write_text(MAKEFILE)
    return root


@pytest.fixture
def drive(scratch_root):
    """`drive(steps)` runs the menu headless on the scratch root, awaits `steps(pilot)`, and returns the app."""
    from app_cli.menu import Menu

    def run(steps, size=(84, 44)):
        async def go():
            app = Menu(scratch_root)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await steps(pilot)
            return app

        return asyncio.run(go())

    return run


def makefile(root, recipes: str) -> None:
    """The scratch root's Makefile: `recipes` with each recipe line starting `> ` in place of a tab."""
    (root / "Makefile").write_text(f".PHONY: {TARGETS}\n" + recipes.replace("\n> ", "\n\t")
                                   + "\nbackend frontend env-file git-hook:\n\t@:\n")


async def until(pilot, condition, seconds: float = 15.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        await pilot.pause(0.05)


def screen_text(app) -> str:
    """What the terminal shows now, as plain text, borders and all."""
    return "\n".join(strip.text for strip in app.screen._compositor.render_strips())


def screen_lines(app) -> list[str]:
    """Each line of the screen with the box borders and padding taken off both ends."""
    return [line.strip(" │┃╭╮╰╯┌┐└┘─") for line in screen_text(app).splitlines()]
