"""The root Makefile's lines the menu runs, read with `make -n`, which prints them and runs none.

make -n still runs a `$(MAKE)` line, with -n passed on, so a sub-make prints its lines too; nothing
here starts docker or touches a file.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from app_cli.commands import child_env

ROOT = Path(__file__).resolve().parents[2]  # the repo root


def make(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["make", "--no-print-directory", "-f", str(ROOT / "Makefile"), *args], cwd=cwd,
                          env=child_env(os.environ), capture_output=True, text=True, timeout=60)


def dry_run(*args: str, cwd: Path = ROOT) -> list[str]:
    """`make -n <args>` with the root Makefile, run in `cwd` (the root unless a test gives a scratch one)."""
    done = make("-n", *args, cwd=cwd)
    assert done.returncode == 0, done.stdout + done.stderr
    return [line for line in done.stdout.splitlines() if line != ":"]  # not the argument words' own `@:`


def builds(lines: list[str]) -> list[str]:
    """The images the build loop goes through, like ["backend"]."""
    loops = [re.match(r"for service in (.*?); do", line) for line in lines]
    return [image for match in loops if match for image in match[1].split()]


def test_menu_runs_the_menu():
    lines = dry_run("menu")
    assert "uv run --project app_cli app-menu" in lines
    assert any(line.startswith("command -v uv") and "make menu needs uv, like brew install uv" in line
               for line in lines)


def test_a_bare_make_and_make_help_list_make_menu_first():
    done = make()
    assert done.returncode == 0, done.stderr
    assert done.stdout == make("help").stdout
    commands = [line.split()[1] for line in done.stdout.splitlines() if line.startswith("  make ")]
    assert commands[0] == "menu"


def test_up_build_backend_builds_backend_only():
    assert builds(dry_run("up", "BUILD=backend")) == ["backend"]
    assert builds(dry_run("up", "BUILD=frontend")) == ["frontend"]
    assert builds(dry_run("up")) == ["backend", "frontend"]
    lines = dry_run("up", "BUILD=none", "DETACH=1")
    assert builds(lines) == []
    assert lines[-1].rstrip().endswith(" up -d")


def test_env_picks_the_env_files(tmp_path):
    assert dry_run("logs", "ENV=dev") == ["docker compose --env-file .env.dev logs -f --tail 200"]
    assert dry_run("down", cwd=tmp_path) == ["docker compose down"]  # no .env yet
    (tmp_path / ".env").write_text("")
    (tmp_path / ".env.local").write_text("")
    assert dry_run("down", cwd=tmp_path) == ["docker compose --env-file .env --env-file .env.local down"]


def test_setup_runs_the_ticked_step_only():
    lines = dry_run("setup", "git-hook")
    assert lines == ["git config core.hooksPath .githooks"]
    both = dry_run("setup")
    assert any("cp .env.example .env" in line for line in both) and both[-1] == lines[0]


def test_bad_words_and_flags_say_how_to_type_them():
    assert 'goes after a command, like make build backend' in make("-n", "backend").stderr
    assert "BUILD is backend, frontend or none" in make("-n", "up", "BUILD=all").stderr
    assert "ENV is local or dev" in make("-n", "up", "ENV=prod").stderr


def test_clean_keeps_the_data_without_yes(tmp_path):
    (tmp_path / ".data").mkdir()
    done = subprocess.run(["make", "--no-print-directory", "-f", str(ROOT / "Makefile"), "clean"], cwd=tmp_path,
                          env=child_env(os.environ), input="no\n", capture_output=True, text=True, timeout=60)
    assert done.returncode != 0
    assert "make clean: kept .data/" in done.stdout
    assert (tmp_path / ".data").is_dir()
