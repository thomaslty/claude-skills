#!/usr/bin/env python3
"""Style mockups with the project's real CSS, compiled by the project's own Tailwind.

Usage:
  screen-css.py --css <entry.css> [--css <entry.css>...] [--node-modules <dir>] <page.html> [<page.html>...] [-o <out>]

  --css            the app's real CSS entries, in the order the app imports them,
                   like frontend/libs/shadcn/ui/src/styles/globals.css then frontend/libs/app-theme/src/theme.css
  --node-modules   where the app's packages are installed. Defaults to the nearest node_modules
                   above the first --css file. A worktree often has none: point at a clone that does.
  -o <file.css>    write the CSS as one stylesheet every page links, like a canvas's
                   project/project.css compiled from all its project/*.dc.html artboards.

Only the classes the pages use are generated, from the app's own theme tokens, so a mock
cannot drift into an invented style. Without -o <file.css>, the compiled CSS replaces
<!-- project-css --> in the one page given (or goes at the end of its <head>).
The Tailwind version is the one the app has installed.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


def nearest_node_modules(start):
    for d in [start, *start.parents]:
        if (d / "node_modules" / "tailwindcss").is_dir():
            return d / "node_modules"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--css", action="append", required=True)
    ap.add_argument("--node-modules")
    ap.add_argument("-o", "--out")
    ap.add_argument("pages", nargs="+")
    a = ap.parse_args()

    entries = [pathlib.Path(c).resolve() for c in a.css]
    pages = [pathlib.Path(p).resolve() for p in a.pages]
    out = pathlib.Path(a.out).resolve() if a.out else pages[0]
    to_css = out.suffix == ".css"
    if len(pages) > 1 and not to_css:
        sys.exit("several pages share one stylesheet: pass -o <file.css>")
    nm = pathlib.Path(a.node_modules).resolve() if a.node_modules else nearest_node_modules(entries[0].parent)
    if not nm or not (nm / "tailwindcss").is_dir():
        sys.exit("no node_modules with tailwindcss found; pass --node-modules <clone>/node_modules")
    version = json.loads((nm / "tailwindcss" / "package.json").read_text())["version"]

    with tempfile.TemporaryDirectory(prefix="dev-screen-") as tmp:
        tmp = pathlib.Path(tmp)
        # The entries import packages (tailwindcss, tw-animate-css, ag-grid) relative to
        # themselves, so copy each entry's folder next to a node_modules that has them.
        (tmp / "node_modules").symlink_to(nm, target_is_directory=True)
        lines = []
        for i, e in enumerate(entries):
            dest = tmp / f"css{i}"
            shutil.copytree(e.parent, dest, ignore=shutil.ignore_patterns("*.js", "*.jsx", "*.ts", "*.tsx"))
            lines.append(f'@import "./css{i}/{e.name}";')
        for i, p in enumerate(pages):
            shutil.copy(p, tmp / f"page{i}.html")
            lines.append(f'@source "./page{i}.html";')
        (tmp / "entry.css").write_text("\n".join(lines) + "\n")
        run = subprocess.run(
            ["npx", "-y", f"@tailwindcss/cli@{version}", "-i", "entry.css", "-o", "out.css"],
            cwd=tmp, capture_output=True, text=True, timeout=300,
        )
        if run.returncode:
            sys.exit(run.stderr[-2000:])
        css = (tmp / "out.css").read_text()

    header = f"/* compiled by tailwindcss {version} from {', '.join(map(str, entries))} */\n"
    if to_css:
        out.write_text(header + css)
    else:
        html = pages[0].read_text()
        style = f"<style>{header}{css}</style>"
        if "<!-- project-css -->" in html:
            html = html.replace("<!-- project-css -->", style)
        else:
            html = html.replace("</head>", style + "\n</head>", 1)
        out.write_text(html)
    print(json.dumps({"out": str(out), "pages": len(pages), "tailwind": version, "css_kb": round(len(css) / 1024)}))


if __name__ == "__main__":
    main()
