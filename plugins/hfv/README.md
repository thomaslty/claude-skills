# HFV — Hypothesis-Fix-Verify

Systematic debugging plugin for Claude Code. One hypothesis, one fix, one verification — then stop.

## Sub-Skills

| Skill | Purpose |
|-------|---------|
| `hfv:full` | Complete explore -> hypothesize -> fix -> verify cycle |
| `hfv:hypothesis` | Deep exploration and hypothesis formation only (no code changes) |
| `hfv:fix` | Implement a fix for an accepted hypothesis |
| `hfv:archive` | Archive a verified fix as successfully resolved |

## Installation

Register the plugin by adding this entry to the `plugins` object in `~/.claude/plugins/installed_plugins.json`:

```json
"hfv@local": [
  {
    "scope": "user",
    "installPath": "<absolute-path-to-this-repo>/plugins/hfv",
    "version": "1.0.0",
    "installedAt": "<current-ISO-date>"
  }
]
```

Restart Claude Code after editing.

## When to Use

- Failures that can't be reproduced locally
- Issues requiring manual verification in a real environment (staging, production, remote infra)
- Multi-layered problems with potentially independent causes
- Bugs where trial-and-error would waste deploy cycles

## How It Works

All artifacts live in your project under `hfv/`:

```
hfv/
  <issue-name>/                    # Active investigation
    hypothesis-<desc>.md           # Each hypothesis attempt
  archive/                         # Verified fixes
    <issue-name>/
      hypothesis-<desc>.md
```

The workflow enforces discipline: explore evidence, form one hypothesis, make a minimal fix, then **stop** and wait for verification. No stacking unverified fixes.
