#!/usr/bin/env python3
"""Add English texts to Bunker's catalogue, or files to the converted lists, safely from several editors at once.

  bunker_catalogue.py add KEYS.json          merge {"key": "English", ...} into translations/bunker/en.json
  bunker_catalogue.py converted PATH...      add template (.html) or module (.py) paths to the converted lists

A key already in the catalogue with different English is refused (choose another key). The catalogue stays
sorted and ends with a newline; the lists stay sorted. A file lock serialises concurrent runs.
"""
from __future__ import annotations

import fcntl
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "translations/bunker/en.json"
CONVERTED = ROOT / "android/tools/bunker_text_converted.json"
LOCK = ROOT / ".bunker_catalogue.lock"


def _write(path: Path, data) -> None:
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def add(texts: dict[str, str]) -> list[str]:
    current = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    clashes = [k for k, v in texts.items() if k in current and current[k] != v]
    if clashes:
        raise SystemExit("Already in the catalogue with other English: " + ", ".join(clashes))
    current.update(texts)
    _write(CATALOGUE, dict(sorted(current.items())))
    return sorted(texts)


def converted(paths: list[str]) -> None:
    lists = json.loads(CONVERTED.read_text(encoding="utf-8"))
    for p in paths:
        rel = Path(p).resolve().relative_to(ROOT).as_posix() if Path(p).is_absolute() else Path(p).as_posix()
        if not (ROOT / rel).is_file():
            raise SystemExit(f"No such file: {rel}")
        key = "templates" if rel.endswith(".html") else "python"
        if rel not in lists[key]:
            lists[key].append(rel)
        lists[key].sort()
    _write(CONVERTED, lists)


def main(argv: list[str]) -> None:
    if len(argv) < 2 or argv[0] not in ("add", "converted"):
        raise SystemExit(__doc__)
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if argv[0] == "add":
            keys = add(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
            print(f"added {len(keys)} keys")
        else:
            converted(argv[1:])
            print("converted lists updated")


if __name__ == "__main__":
    main(sys.argv[1:])
