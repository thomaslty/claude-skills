"""The make arguments each page's picks become, and the env make runs in."""

from __future__ import annotations

import os

import pytest

from app_cli.commands import Docker, FirstTimeSetup, child_env, docker_args, setup_args, title


@pytest.mark.parametrize(("picks", "env", "args"), [
    (Docker("up"), "local", ["up"]),
    (Docker("up-detached", "backend"), "local", ["up", "BUILD=backend", "DETACH=1"]),
    (Docker("up", "none"), "dev", ["up", "ENV=dev", "BUILD=none"]),
    (Docker("build"), "local", ["build"]),
    (Docker("build", "frontend"), "dev", ["build", "frontend", "ENV=dev"]),
    (Docker("down", "backend"), "local", ["down"]),
    (Docker("logs"), "dev", ["logs", "ENV=dev"]),
    (Docker("clean"), "local", ["clean"]),
])
def test_docker_args(picks, env, args):
    assert docker_args(picks, env) == args


def test_build_only_needs_something_to_build():
    with pytest.raises(ValueError, match="needs something to build"):
        docker_args(Docker("build", "none"), "local")


def test_setup_args():
    assert setup_args(FirstTimeSetup()) == ["setup"]
    assert setup_args(FirstTimeSetup(env_file=False)) == ["setup", "git-hook"]
    assert setup_args(FirstTimeSetup(git_hook=False)) == ["setup", "env-file"]
    with pytest.raises(ValueError, match="tick at least one step"):
        setup_args(FirstTimeSetup(False, False))


def test_title():
    assert title(Docker("up-detached", "backend"), "dev") == "Up (detached) · build backend only · ENV dev"
    assert title(Docker("down"), "local") == "Down · ENV local"
    assert title(FirstTimeSetup(), "local") == "First time setup · every step"
    assert title(FirstTimeSetup(env_file=False), "local") == "First time setup · Point git at .githooks/"


def test_child_env_drops_what_make_menu_and_uv_put_in():
    venv = "/repo/app_cli/.venv"
    environ = {"PATH": os.pathsep.join([f"{venv}/bin", "/usr/bin"]), "VIRTUAL_ENV": venv, "ENV": "dev",
               "MAKELEVEL": "1", "MAKEFLAGS": "w", "HOME": "/home/you"}
    env = child_env(environ)
    assert env == {"PATH": "/usr/bin", "HOME": "/home/you", "PYTHONUNBUFFERED": "1"}
