# CLAUDE.md

## Critical Rules

- **NEVER use symlinks.** When copying files between locations (e.g., this repo and `~/.claude`), always use real file copies. No symlinks, no references, no pointing one location at another. Two independent copies.
- **~/.claude is the live runtime. This repo is archive only.** All skills and plugins must exist as real, independent file copies inside `~/.claude`. The `installPath` in `installed_plugins.json` must ALWAYS point to a path under `~/.claude`, NEVER to this repo. After editing files in the repo, always re-copy them to `~/.claude`.
