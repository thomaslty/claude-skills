---
name: create-readme
description: "Write or rewrite a project README in the house style — logo, badges, one-line summary, disclaimer, screenshot, contents, at most 5 benefit-framed features, quick start, config table with a Required column. Triggers on 'write the readme', 'clean up the readme', 'rewrite my readme', or /dev:create-readme. Features describe what the user gets, never how the code works."
---

# Create README

## Overview

A README is a product page, not design notes. The reader decides in about forty lines whether to
run the thing. Sell first, explain later, and put the mechanism somewhere else.

Derived from [bichon](https://github.com/rustmailer/bichon)'s shape.

## The nine sections, in this order

Nothing else goes above the config table.

```markdown
<div align="center">
<img src="docs/logo.png" alt="<name>" width="112">

# <name>

[![release](…)](…) [![image](…)](…) [![build](…)](…) [![stars](…)](…)

**<One line: what you do with it, in your words.>**
</div>

> <name> is an <X>, not a <Y>. It only <does the narrow thing> — it never <the thing
> people will fear>.

<div align="center"><img src="docs/screenshot.png" alt="…" width="860"></div>

## Contents
## Features
## Quick start
## Configuration
```

The disclaimer earns its place: it kills the biggest wrong assumption in one line.

## Features — at most 5, and they are benefits

**`- **Label**: the worry it removes`** — never the mechanism. If a bullet would make sense only to
someone who has read the source, it is the wrong bullet.

The failure mode, from a real session where this got rejected twice:

```
WRONG  - **Albums stay one collection** — an album is debounced back together
         instead of arriving as five separate sends
WRONG  - **Files up to 2 GB** — a local telegram-bot-api container lifts the 20 MB cap
WRONG  - **Full-text search** over title, caption, notes and properties (sqlite FTS5)

RIGHT  - **Save your Telegram photos and videos**: they sit on your own disk, big files
         included, so nothing goes when a chat is cleared or an account disappears
RIGHT  - **Tags, notes and search**: you can still find the collection you care about
         years later
RIGHT  - **Nothing to lock you in**: plain dated folders you can copy anywhere, and
         copying them is the whole backup
```

Rules that follow from it:

- five bullets maximum — a list of seventeen is a spec sheet, and nobody reads it
- name the fear, not the feature: "never worry about X", "still find it years later", "open it anywhere"
- no library names, no algorithms, no file names, no test names in a feature bullet
- if two bullets are the same benefit, merge them and use the slot for something else
- a guarantee about your internals ("every removal goes through one function") is not a feature — it goes in `docs/`

## Quick start — easiest first

Docker Compose, then build from source, then without docker. If you publish an image, paste the
whole compose file inline so the first path works with nothing cloned — a `curl` of a compose file
that says `build: .` is a broken quick start.

## Configuration — four columns

| Variable | Required | Default | What it does |

`Required` says **what it is required for**, never yes/no:

```
no · for the bot · for login · for big files · over 2 GB · behind a proxy
```

Put one line above the table saying whether anything is needed to boot at all. Group rows by
purpose, not alphabetically, so the "for big files" rows sit together.

Split anything nobody tunes into a second **Tuning** table, and keep those out of `.env.example`
entirely — the file you copy should hold only lines you would actually set.

## When a section grows

Any section past two bullets is probably repeating something. Before you write the third:

| Detail | Where it belongs |
|---|---|
| What a variable does | the config table |
| A gotcha about one variable | a comment beside it in `.env.example` |
| Operational depth, backup, mounts | `docs/<topic>.md`, linked in one line |
| Why the code is built that way | code comments |

Move it, do not delete it. Hard-won operational knowledge (why a marker file exists, which fstab
option hangs the app) is the most valuable prose in the repo — it just does not belong on the
product page.

## Assets

- **Logo** — build it from the app's own mark and real palette, not a stock icon on a random gradient. Pull the exact colours out of the running app rather than eyeballing them: paint the token onto a 1×1 canvas and read the pixel back, which converts `oklch()`/`color-mix()` to hex for you.
- **Screenshot** — must match what ships. If the UI gained a nav item since the mockup was made, inject it before capturing; a hero that shows a stale app is worse than none.
- **Size** — render at 2×, then `magick shot.png -resize 1800x -strip` . A 1.4 MB hero is a bug.
- Add `docs` to `.dockerignore` so images never enter the build context.

## Voice

Follow `~/.claude/user_wording_style.md`. Short version: second person, one bullet one action, point
at a real path with "like `<example>`", link the authority instead of explaining the mechanism, keep
honest hedges, and treat the existing line count as the budget.

## Checklist before you hand it over

- [ ] five features or fewer, every one a benefit
- [ ] no feature mentions a library, algorithm or file
- [ ] disclaimer kills the biggest wrong assumption
- [ ] `Required` column present, and no cell says "yes"
- [ ] quick start's first path works with nothing cloned
- [ ] every `docs/…` link and image resolves
- [ ] no section runs past two bullets without a reason
