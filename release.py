#!/usr/bin/env python3
"""Publish an update to a Yoso microsite, moving its beta number up by one.

    python3 release.py "What changed"

This:
  1. moves the number in VERSION up by one step (Beta 0.1 -> 0.2 -> 0.3 ...);
  2. writes the new number into the footer of every page;
  3. runs check.py, and puts everything back as it was if the check fails;
  4. commits all your changes with the message 'Beta 0.x: What changed' and pushes.

Options:
  --no-push     commit, but do not push yet
  --no-commit   only move the number and run the check (you commit yourself)

The same file is used on every site. Each site counts its own updates.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
SKIP_DIRS = {".git", ".github", "node_modules", "archive"}
# The footer's version mark: <span class="version" data-version>Beta 0.1</span>
MARK = re.compile(r'(<span class="version" data-version>)Beta [0-9]+\.[0-9]+(</span>)')


def bump(v):
    major, minor = v.split(".")
    return f"{major}.{int(minor) + 1}"


def run(*cmd):
    return subprocess.run(cmd, cwd=ROOT).returncode


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    commit = "--no-commit" not in flags
    if commit and not args:
        sys.exit('Say what changed, for example:  python3 release.py "New painting added"')

    old = VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else "0.0"
    if not re.fullmatch(r"[0-9]+\.[0-9]+", old):
        sys.exit(f"VERSION should hold a number like 0.4, not '{old}'")
    new = bump(old)

    pages = sorted(p for p in ROOT.rglob("*.html") if not SKIP_DIRS & set(p.relative_to(ROOT).parts))
    saved = {p: p.read_text(encoding="utf-8") for p in pages}
    missing = [p.relative_to(ROOT).as_posix() for p, t in saved.items() if not MARK.search(t)]
    if missing:
        sys.exit("These pages have no version mark in the footer: " + ", ".join(missing))

    VERSION_FILE.write_text(new + "\n", encoding="utf-8")
    for p, t in saved.items():
        p.write_text(MARK.sub(rf"\g<1>Beta {new}\g<2>", t), encoding="utf-8")

    if run(sys.executable, "check.py") != 0:
        VERSION_FILE.write_text(old + "\n", encoding="utf-8")
        for p, t in saved.items():
            p.write_text(t, encoding="utf-8")
        sys.exit(f"Not released: fix the problems above. The site is still Beta {old}.")

    print(f"Beta {old} -> Beta {new}")
    if not commit:
        return
    if run("git", "add", "-A") or run("git", "commit", "-q", "-m", f"Beta {new}: {' '.join(args)}"):
        sys.exit("The commit did not go through; see the message above.")
    if "--no-push" in flags:
        print("Committed. Push when ready with:  git push")
        return
    if run("git", "pull", "-q", "--rebase") or run("git", "push", "-q"):
        sys.exit("Committed, but the push did not go through; see the message above.")
    print(f"Published Beta {new}.")


if __name__ == "__main__":
    main()
