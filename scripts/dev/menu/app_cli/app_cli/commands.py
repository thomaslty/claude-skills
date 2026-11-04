"""Each page's picks, and the make arguments they become.

The menu builds make arguments and nothing else: what a command does stays in the root Makefile,
so a terminal user gets the same lines. Every page and the Run screen call these.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

# ENV: what the Home page says the stack runs with
ENVS = {"local": "with .env.local over .env", "dev": "with .env.dev, the dev server's settings"}
# verb: its label on Docker stack management
VERBS = {"up": "Up", "up-detached": "Up (detached)", "down": "Down", "logs": "Logs", "build": "Build only",
         "clean": "Delete .data/"}
# The verbs that lose something you cannot get back, so Run this? asks first, and you type yes.
ASKS = {"clean"}
# build: its label and what it does, as the Build picker shows them
BUILDS = {
    "both": ("backend + frontend", "both, one after the other"),
    "backend": ("backend only", ""),
    "frontend": ("frontend only", ""),
    "none": ("nothing", "the images built last"),
}
# First time setup's ticks: the label, and the word make setup takes for that step alone
SETUP_STEPS = {
    "env_file": ("Copy .env.example to .env", "env-file"),
    "git_hook": ("Point git at .githooks/", "git-hook"),
}


@dataclass(frozen=True)
class Docker:
    verb: str  # "up", "up-detached", "down", "logs", "build", "clean"
    build: str = "both"  # "both", "backend", "frontend", "none"


@dataclass(frozen=True)
class FirstTimeSetup:
    env_file: bool = True
    git_hook: bool = True


Picks = Docker | FirstTimeSetup


def env_flags(env: str) -> list[str]:
    """ENV local, the default, needs no flag; dev → ["ENV=dev"]."""
    return [] if env == "local" else [f"ENV={env}"]


def docker_args(picks: Docker, env: str) -> list[str]:
    """Docker("up-detached", "backend"), dev → ["up", "ENV=dev", "BUILD=backend", "DETACH=1"]."""
    flags = env_flags(env)
    if picks.verb == "build":
        if picks.build == "none":
            raise ValueError("Build only needs something to build")
        return ["build", *([] if picks.build == "both" else [picks.build]), *flags]
    if picks.verb in ("up", "up-detached"):
        build = [] if picks.build == "both" else [f"BUILD={picks.build}"]
        return ["up", *flags, *build, *(["DETACH=1"] if picks.verb == "up-detached" else [])]
    if picks.verb in ("down", "logs", "clean"):
        return [picks.verb, *flags]
    raise ValueError(f"unknown verb {picks.verb!r}")


def setup_args(picks: FirstTimeSetup) -> list[str]:
    """Both ticked → ["setup"]; one → ["setup", "git-hook"]."""
    words = [word for name, (_, word) in SETUP_STEPS.items() if getattr(picks, name)]
    if not words:
        raise ValueError("tick at least one step")
    return ["setup"] if len(words) == len(SETUP_STEPS) else ["setup", *words]


def title(picks: Picks, env: str) -> str:
    """The Run screen's first line, like "Up (detached) · build backend only · ENV dev"."""
    if isinstance(picks, Docker):
        parts = [VERBS[picks.verb]]
        if picks.verb in ("up", "up-detached", "build"):
            parts.append(f"build {BUILDS[picks.build][0]}")
        return " · ".join([*parts, f"ENV {env}"])
    ticked = [label for name, (label, _) in SETUP_STEPS.items() if getattr(picks, name)]
    if len(ticked) == len(SETUP_STEPS):
        return "First time setup · every step"
    return "First time setup · " + (", ".join(ticked) or "nothing ticked")


# make menu ENV=dev exports these into the menu; uv run adds VIRTUAL_ENV.
DROPPED = {"ENV", "DETACH", "BUILD", "MAKELEVEL", "MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "VIRTUAL_ENV"}


def child_env(environ: Mapping[str, str]) -> dict[str, str]:
    """Your shell's env for make, without what make menu and uv run put in, plus PYTHONUNBUFFERED=1."""
    env = {name: value for name, value in environ.items() if name not in DROPPED}
    if venv := environ.get("VIRTUAL_ENV"):
        bin_dir = str(Path(venv) / ("Scripts" if os.name == "nt" else "bin"))
        env["PATH"] = os.pathsep.join(part for part in env.get("PATH", "").split(os.pathsep) if part != bin_dir)
    env["PYTHONUNBUFFERED"] = "1"
    return env
