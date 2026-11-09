#!/usr/bin/env python3
"""Fetches the notice pack that builds put in the game's Notices screen.

The pack (the official notices recovered from archives, with their images) is
not kept in this repository. notices.lock.json pins the published file by
address, size and SHA-256; this downloads it to inputs/bunker-notices-pinned.zip
and writes inputs/bunker-notices.zip from it, where scripts/build.py, the web
builder and releases pick it up. That copy has the reconstructed notices'
summon prices brought in line with the summon rules (sync_notice_prices.py),
so a price corrected there reaches the Notices screen without a new pack.

  notices.py            fetch the pinned pack (kept if the copy already matches) and sync it
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "notices.lock.json"
OUTPUT = ROOT / "inputs/bunker-notices.zip"
PINNED = ROOT / "inputs/bunker-notices-pinned.zip"
RULES = ROOT / "overlays/server/internal/masterdata/summon_rules.json"


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
        # GitHub's release downloads answer 504 now and then: a few tries, waiting longer each time.
        for attempt in range(5):
            try:
                with urllib.request.urlopen(pin["url"], timeout=120) as response, open(partial, "wb") as out:
                    shutil.copyfileobj(response, out, 1 << 20)
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                if attempt == 4 or (isinstance(error, urllib.error.HTTPError) and error.code < 500 and error.code != 429):
                    raise
                print(f"Notice pack download failed ({error}); trying again")
                time.sleep(10 * (attempt + 1))
        if partial.stat().st_size != pin["size"] or _sha256(partial) != pin["sha256"]:
            raise RuntimeError(f"The downloaded notice pack does not match {Path(lock).name}")
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return output


def fetch_synced(lock=LOCK, pinned=PINNED, output=OUTPUT, rules=RULES):
    """The pinned pack (fetch) with its notices synced to the summon rules, at
    output. Written again only when the pinned pack or the rules change."""
    pin = json.loads(Path(lock).read_text())
    pinned, output = Path(pinned), Path(output)
    stamp = output.with_name(output.name + ".synced")
    if not pinned.is_file() and output.is_file() and not stamp.is_file() and output.stat().st_size == pin["size"] and _sha256(output) == pin["sha256"]:
        os.replace(output, pinned)  # a copy fetched before the pack was synced
    fetch(lock, pinned)
    made = {"pinned": pin["sha256"], "rules": _sha256(rules)}
    if output.is_file() and stamp.is_file() and json.loads(stamp.read_text()) == made:
        return output
    import sync_notice_prices
    stamp.unlink(missing_ok=True)
    sync_notice_prices.write(pinned, output, rules)
    stamp.write_text(json.dumps(made))
    return output


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    print(f"Notice pack: {fetch_synced()}")


if __name__ == "__main__":
    main()
