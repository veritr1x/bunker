"""The language packs Bunker ships, built from the reviewed translations in translations/.

translations/languages.json lists the languages: {"pt-BR": {"name": "Português (Brasil)", "ship": true}}.
A shipped language's pack merges every translations/game/<area>/<code>.json and translations/master/<code>.json
into the file Pod Programs offers and the server reads (overlays/server/internal/translation/pack.go).
scripts/prepare.py writes them to android/app/src/main/python/shipped_languages/, which the Android and
iOS builds both carry.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# The game's own languages: never packs.
GAME_LANGUAGES = frozenset(("en", "ja", "ko"))
# The codes the device accepts (bunker_language.CODE): another would build a pack it never lists.
CODE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}")


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {key: value for key, value in data.items() if isinstance(value, str) and value}


def _canonical(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_pack(translations: Path, code: str, name: str) -> dict:
    """One language's pack; its version names its content."""
    game: dict[str, str] = {}
    for path in sorted((translations / "game").glob(f"*/{code}.json")):
        game.update(_read(path))
    master = _read(translations / "master" / f"{code}.json")
    version = hashlib.sha256(_canonical({"game": game, "master": master}).encode()).hexdigest()[:12]
    return {"format": 1, "language": code, "name": name, "version": version, "game": game, "master": master}


def write_shipped(translations: Path, out: Path) -> list[Path]:
    """Write the pack of each language marked to ship into out, removing any other pack there."""
    languages = json.loads((translations / "languages.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for code, about in sorted(languages.items()):
        if not about.get("ship") or code in GAME_LANGUAGES:
            continue
        if not CODE.fullmatch(code):
            raise ValueError(f"translations/languages.json: {code} is not a language code the device accepts (like pt-BR)")
        path = out / f"{code}.json"
        path.write_text(_canonical(build_pack(translations, code, about.get("name", code))) + "\n", encoding="utf-8")
        written.append(path)
    for stale in out.glob("*.json"):
        if stale not in written:
            stale.unlink()
    return written
