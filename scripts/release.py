#!/usr/bin/env python3
"""Cuts a release: checks it, bumps VERSION, runs the unit tests, commits and tags.

  scripts/release.py 1.10.5            # check, commit "Release 1.10.5", tag v1.10.5
  scripts/release.py 1.10.5 --push     # ... and push main and the tag (release.yml builds it)
  scripts/release.py 1.10.5 --dry-run  # the checks only

Write the release's CHANGELOG.md section first ("## 1.10.5 (YYYY-MM-DD)", its
summary and the dated sections under it); README.md and docs/VALIDATION.md may
change with it. The release commit takes those three and VERSION; anything else
changed stops it. The tests are scripts/unit_tests.sh (PYTHON picks the
interpreter), the ones release.yml runs before it builds.
"""
import argparse
import datetime
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import release_assets  # noqa: E402

RELEASE_FILES = {"VERSION", "CHANGELOG.md", "README.md", "docs/VALIDATION.md"}


class ReleaseError(Exception):
    pass


def parse(version):
    """(1, 10, 5) from "1.10.5"; anything else is refused."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ReleaseError(f"{version!r} is not a version like 1.10.5")
    return tuple(int(part) for part in version.split("."))


def check_changelog(text, version, today=None):
    """The section release.yml takes the notes from, dated today."""
    try:
        release_assets.changelog_section(text, version)
    except ValueError:
        raise ReleaseError(f"CHANGELOG.md has no section for {version}: write \"## {version} ({today or datetime.date.today()})\" and its notes first")
    heading = re.search(rf"^## {re.escape(version)} \((.*?)\)$", text, re.M)
    date = today or datetime.date.today().isoformat()
    if heading.group(1) != date:
        raise ReleaseError(f"CHANGELOG.md dates {version} {heading.group(1)}, not today ({date})")
    first = re.search(r"^## \d+\.\d+\.\d+ \(", text, re.M)
    if first.start() != heading.start():
        raise ReleaseError(f"{version} is not the newest release in CHANGELOG.md")


def git(*args, capture=True):
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=capture, text=True)
    if result.returncode:
        raise ReleaseError(f"git {' '.join(args)}: {(result.stderr or result.stdout).strip()}")
    return result.stdout.rstrip("\n") if capture else ""  # rstrip: status lines start with a space


def changed_files(porcelain):
    """The paths in `git status --porcelain` output ("XY path")."""
    return {line[3:] for line in porcelain.splitlines() if len(line) > 3}


def check_repository(version):
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise ReleaseError("Release from main")
    changed = changed_files(git("status", "--porcelain", "--untracked-files=no"))
    others = sorted(changed - RELEASE_FILES)
    if others:
        raise ReleaseError("Commit or set aside these first: " + ", ".join(others))
    git("fetch", "--quiet", "origin", "main", "--tags")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise ReleaseError("main is not the same as origin/main: pull or push first")
    if git("tag", "--list", f"v{version}"):
        raise ReleaseError(f"v{version} is already tagged")
    current = (ROOT / "VERSION").read_text().strip()
    if git("show", "HEAD:VERSION") != current and current != version:
        raise ReleaseError(f"VERSION says {current}")
    if parse(version) <= parse(git("show", "HEAD:VERSION")):
        raise ReleaseError(f"{version} is not after {git('show', 'HEAD:VERSION')}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("version")
    p.add_argument("--push", action="store_true", help="push main and the tag (release.yml builds and publishes it)")
    p.add_argument("--dry-run", action="store_true", help="the checks and the tests only; nothing is written")
    args = p.parse_args(argv)
    try:
        parse(args.version)
        check_repository(args.version)
        check_changelog((ROOT / "CHANGELOG.md").read_text(), args.version)
        version_file = ROOT / "VERSION"
        before = version_file.read_text()
        version_file.write_text(args.version + "\n")
        try:
            print("Running the unit tests…")
            subprocess.run([str(ROOT / "scripts/unit_tests.sh")], check=True, env={**os.environ})
        except subprocess.CalledProcessError:
            version_file.write_text(before)
            raise ReleaseError("The unit tests failed; nothing was committed")
        if args.dry_run:
            version_file.write_text(before)
            print(f"{args.version} is ready to release (dry run: nothing written)")
            return 0
        changed = changed_files(git("status", "--porcelain", "--untracked-files=no"))
        git("add", *sorted(changed & RELEASE_FILES))
        git("commit", "--quiet", "-m", f"Release {args.version}")
        git("tag", "-a", f"v{args.version}", "-m", f"Bunker {args.version}")
        print(f"Committed \"Release {args.version}\" and tagged v{args.version}")
        if args.push:
            git("push", "--quiet", "origin", "main", capture=False)
            git("push", "--quiet", "origin", f"v{args.version}", capture=False)
            print("Pushed: release.yml builds and publishes it, then the web builder")
        else:
            print(f"To publish: git push origin main && git push origin v{args.version}")
        return 0
    except ReleaseError as error:
        print(f"Not released: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
