#!/usr/bin/env python3
"""Prints Bunker's version: VERSION on a commit tagged v<VERSION>, else <VERSION>+dev.<commit>."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def version(root=ROOT):
    root = Path(root)
    value = (root / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError(f"VERSION must be MAJOR.MINOR.PATCH, not {value!r}")
    if not (root / ".git").exists():
        return value + "+dev"
    if "v" + value in _git(root, "tag", "--points-at", "HEAD").split():
        return value
    commit = _git(root, "rev-parse", "--short=7", "HEAD")
    return f"{value}+dev.{commit}" if commit else value + "+dev"


def base(value):
    """1.2.3 from 1.2.3 or 1.2.3+dev.abc1234, as numbers."""
    return tuple(int(x) for x in value.split("+", 1)[0].split("."))


def newer(candidate, current):
    """Whether release `candidate` should be offered to a build of version `current`.

    A dev build of 1.0.0 is not offered 1.0.0 itself."""
    return base(candidate) > base(current)


if __name__ == "__main__":
    print(version(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))
