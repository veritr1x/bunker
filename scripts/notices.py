#!/usr/bin/env python3
"""Fetches the notice pack that builds put in the game's Notices screen.

The pack (the official notices recovered from archives, with their images) is
not kept in this repository. notices.lock.json pins the published file by
address, size and SHA-256; this downloads it to inputs/bunker-notices.zip,
where scripts/build.py, the web builder and releases pick it up.

  notices.py            fetch the pinned pack (kept if the copy already matches)
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "notices.lock.json"
OUTPUT = ROOT / "inputs/bunker-notices.zip"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(lock=LOCK, output=OUTPUT):
    pin = json.loads(Path(lock).read_text())
    output = Path(output)
    if output.is_file() and output.stat().st_size == pin["size"] and _sha256(output) == pin["sha256"]:
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    try:
        with urllib.request.urlopen(pin["url"], timeout=120) as response, open(partial, "wb") as out:
            shutil.copyfileobj(response, out, 1 << 20)
        if partial.stat().st_size != pin["size"] or _sha256(partial) != pin["sha256"]:
            raise RuntimeError(f"The downloaded notice pack does not match {Path(lock).name}")
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return output


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    print(f"Notice pack: {fetch()}")


if __name__ == "__main__":
    main()
