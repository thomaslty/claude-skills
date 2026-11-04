"""Where a make run is, from the lines it printed so far: its steps, the bar's count and the item.

Each step starts on a line make prints. A line that starts a later step closes the ones before it,
a count line fills the bar, and a step with no count leaves the bar at 0 so the Run screen slides a
block instead. A step with no line of its own gets one in the Makefile, a plain `--- <step>` echo,
so a terminal reads it too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    name: str  # "Build backend"
    starts: str = ""  # regex of the line that starts it; "" starts it with the run, like Down
    skip: str = ""  # regex of a line that skips it, from before it starts, like r"^\.env is there already"


# compose's ` Image app-backend Building`, or an older one's `#1 [backend internal] …`.
BUILD_STEPS = (Step("Build backend", r"^\s*Image \S+-backend Building|^#\d+ \[backend[ \]]"),
               Step("Build frontend", r"^\s*Image \S+-frontend Building|^#\d+ \[frontend[ \]]"))
# make echoes the compose line itself, like `docker compose --env-file .env up -d`, or `docker compose up` with no .env.
START_STACK = Step("Start the stack", r"^docker compose(?: .*)? up(?: -d)?$")
STACK_RUNNING = Step("Stack running", r"^Attaching to |Container \S+-(?:backend|frontend)-\d+\s+(?:Started|Running)$")
# A run of one thing has one step, named after the pick.
ONE_STEP = {"down": "Down", "clean": "Delete .data/", "setup": "First time setup"}

# `  3/40 files  fonts/arial.ttf`, `  212/1509 tables  ev.trade_order`: print one of these where you can.
COUNT = re.compile(r"^\s+(?P<done>\d+)/(?P<total>\d+) (?P<unit>[a-z]+)(?:\s+(?P<item>\S+))?$")
# BuildKit names the stage, not the image: `#9 [stage-0  7/11] RUN --mount=…`, `#8 [build 3/5] RUN npm ci`;
# an older compose wrote `#12 [backend 7/11] …`. The build step that runs says which image it is.
BUILD = re.compile(r"^#\d+ \[(?:[^\]/]*?\s)?(?P<done>\d+)/(?P<total>\d+)\] (?P<item>.+)$")


def steps_for(args: list[str]) -> tuple[Step, ...]:
    """The steps a make line goes through; () for Logs, which has none, only the Output."""
    if args[0] == "logs":
        return ()
    if args[0] in ONE_STEP:
        return (Step(ONE_STEP[args[0]]),)
    if args[0] == "build":  # make build, make build backend
        images = [arg for arg in args[1:] if arg in ("backend", "frontend")] or ["backend", "frontend"]
    elif args[0] == "up":  # BUILD=backend, BUILD=none, or both
        build = next((arg.split("=", 1)[1] for arg in args if arg.startswith("BUILD=")), "")
        images = [] if build == "none" else [build] if build else ["backend", "frontend"]
    else:
        raise ValueError(f"no steps for make {' '.join(args)}; give it its steps here")
    builds = tuple(step for step in BUILD_STEPS if step.name.removeprefix("Build ") in images)
    if args[0] == "build":
        return builds
    # Detached, make ends once compose started the stack; attached, the logs follow.
    return (*builds, START_STACK) if "DETACH=1" in args else (*builds, START_STACK, STACK_RUNNING)


@dataclass
class Progress:
    steps: tuple[Step, ...]
    state: list[str] = field(default_factory=list)  # per step: "", "now", "done", "skipped", "failed", "stopped"
    seconds: list[float] = field(default_factory=list)
    current: int = -1
    done: int = 0
    total: int = 0  # 0: no count, so the block slides
    item: str = ""
    unit: str = ""  # files, tables, or the image a build counts in, like backend
    started: float = 0.0  # when the current step started

    def __post_init__(self) -> None:
        self.state = [""] * len(self.steps)
        self.seconds = [0.0] * len(self.steps)

    def begin(self, now: float) -> None:
        """A first step with no line of its own starts with the run."""
        if self.steps and not self.steps[0].starts:
            self.enter(0, now)

    def enter(self, index: int, now: float) -> None:
        for before in range(index):
            self.close(before, now, "done" if self.state[before] == "now" else "skipped")
        self.current, self.started = index, now
        self.state[index] = "now"
        self.reset()

    def reset(self) -> None:
        """A new step starts with no count."""
        self.done = self.total = 0
        self.item = self.unit = ""

    def close(self, index: int, now: float, state: str) -> None:
        """End a step that runs as `state`; a step already ended keeps its mark."""
        if self.state[index] == "now":
            self.seconds[index] = now - self.started
            self.state[index] = state
        elif not self.state[index] and state in ("done", "skipped"):  # passed over, never reached
            self.state[index] = "skipped"

    def feed(self, line: str, now: float) -> None:
        self.move(line, now)
        self.count(line)

    def move(self, line: str, now: float) -> None:
        """Start, or skip, the step this line belongs to; a line of an earlier step moves nothing."""
        current = self.current
        if current >= 0 and self.state[current] == "now":
            step = self.steps[current]
            if step.starts and re.search(step.starts, line):  # its own line again
                return
        for index in range(max(current, 0), len(self.steps)):
            step = self.steps[index]
            if step.skip and re.search(step.skip, line):
                self.skip_from(index, line, now)
                return
            if index > current and step.starts and re.search(step.starts, line):
                self.enter(index, now)
                return

    def skip_from(self, index: int, line: str, now: float) -> None:
        """Skip this step and each one after it the same line skips."""
        last = index
        while last + 1 < len(self.steps) and self.steps[last + 1].skip and re.search(self.steps[last + 1].skip, line):
            last += 1
        for before in range(index):
            self.close(before, now, "done" if self.state[before] == "now" else "skipped")
        for skipped in range(index, last + 1):
            self.close(skipped, now, "skipped")
        self.current = last
        self.reset()

    def count(self, line: str) -> None:
        """Fill the current step's bar from a count line, or BuildKit's own while an image builds."""
        if self.current < 0 or self.state[self.current] != "now":
            return
        if match := COUNT.match(line):
            self.done, self.total, self.unit = int(match["done"]), int(match["total"]), match["unit"]
            self.item = match["item"] or ""
        elif (match := BUILD.match(line)) and self.steps[self.current].name.startswith("Build "):
            done, total = int(match["done"]), int(match["total"])
            # Cached steps come out of order, like 9/11 then 2/11: the bar keeps its highest in this stage.
            self.done = max(done, self.done) if total == self.total else done
            self.total, self.unit = total, self.steps[self.current].name.removeprefix("Build ")
            self.item = match["item"]

    def end(self, code: int, stopped: bool, now: float) -> None:
        """make ended: the step that ran is done, stopped or failed; the ones never reached stay waiting."""
        state = "stopped" if stopped else "done" if code == 0 else "failed"
        if self.current >= 0 and self.state[self.current] == "now":
            self.close(self.current, now, state)
        elif state == "failed":  # failed before its step's line, or right after a skip: the next one failed
            waiting = [index for index in range(max(self.current, 0), len(self.steps)) if not self.state[index]]
            if waiting:
                self.state[waiting[0]] = "failed"

    def step_seconds(self, index: int, now: float) -> float:
        """A step's own time: still ticking while it runs."""
        return now - self.started if index == self.current and self.state[index] == "now" else self.seconds[index]

    def fraction(self) -> float:
        return self.done / self.total if self.total else 0.0

    def building(self) -> bool:
        return self.current >= 0 and self.steps[self.current].name.startswith("Build ")

    def counts(self) -> str:
        """The line under the bar, like "212 of 1,509 tables" or "7 of 11 in the backend image"."""
        if not self.total:
            return "no count here: the block slides while it runs"
        if self.building():
            return f"{self.done} of {self.total} in the {self.unit} image"
        return f"{self.done:,} of {self.total:,} {self.unit}"
