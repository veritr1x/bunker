"""Language packs on the device, for Pod Programs › Language.

The server applies <assetRoot>/translation/active.json (a copy of the chosen pack) the next time it
starts and reports what it did in status.json beside it (overlays/server/internal/translation).
Packs come shipped with Bunker (shipped_languages/, scripts/language_packs.py) or loaded by the player
into translation/packs/. A loaded pack comes from strangers: it is read with the server's own rules
(pack.go), and only its language code, once it looks like one, becomes a file name.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

MAX_PACK_BYTES = 64 << 20  # pack.go MaxPackBytes
ENGLISH_TEXTS = 143565  # the game's English texts (3.7.1, the only version Bunker accepts)
CODE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}")  # whole string (fullmatch): "pt\n" is not a code
FIELDS = ("format", "language", "name", "version", "game", "master", "bunker")


def _reject_constant(name):
    raise ValueError(f"{name} is not a number the server reads")


class PackError(ValueError):
    """Why a pack or a choice was refused, in words for the player."""


@dataclass
class PackInfo:
    source: str  # "shipped" or "loaded"
    language: str
    name: str
    version: str
    texts: int  # translated texts the server will use
    path: Path

    @property
    def percent(self) -> int:
        return min(100, round(100 * self.texts / ENGLISH_TEXTS))


def read_pack(data: bytes, source: str = "loaded", path: Path = Path()) -> PackInfo:
    """A pack's description, or PackError when the server would not use it."""
    if len(data) > MAX_PACK_BYTES:
        raise PackError("This pack is too large (over 64 MB).")
    try:
        pack = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise PackError("Not a language pack: the file is not readable JSON.") from None
    if not isinstance(pack, dict) or type(pack.get("format")) is not int or pack["format"] != 1:
        raise PackError("Not a language pack: it has no \"format\": 1. Translation files must be built into a pack first.")
    # The server matches these names ignoring case and keeps the last: a second spelling would change what it reads.
    if any(key.lower() in FIELDS and key != key.lower() for key in pack):
        raise PackError("Not a language pack: a field name is written in capitals.")
    language = pack.get("language")
    if not isinstance(language, str) or not CODE.fullmatch(language):
        raise PackError("This pack's language code is not valid.")
    if any(field in pack and not isinstance(pack[field], str) for field in ("name", "version")):
        raise PackError("Not a language pack: its name and version must be text.")
    game = pack.get("game", {})
    if not isinstance(game, dict):
        raise PackError("Not a language pack: its \"game\" texts are not a list of keys.")
    if not isinstance(pack.get("bunker", {}), dict):
        raise PackError("Not a language pack: its \"bunker\" texts are not a list of keys.")
    texts = sum(1 for value in game.values() if isinstance(value, str) and value and "\n" not in value and "\r" not in value)
    return PackInfo(source, language, pack.get("name") or language, pack.get("version", ""), texts, path)


def _write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name("." + path.name + ".tmp")
    pending.write_bytes(data)
    os.replace(pending, path)


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


SHIPPED_DIR = Path(__file__).resolve().parent / "shipped_languages"


def for_config(config, shipped_dir: Path | None = None) -> "Languages":
    """The device's packs at Pod Programs' paths: the server's translation folder beside its assets,
    the choice of a shipped pack in Pod Programs' own folder (where the launchers look for it)."""
    return Languages(config.ASSETS_DIR.parent / "translation", shipped_dir or SHIPPED_DIR, config.DATA_DIR / "language.json")


class Languages:
    """The packs on the device and the choice between them."""

    def __init__(self, translation_dir: Path, shipped_dir: Path, choice_path: Path | None = None):
        self.translation_dir = Path(translation_dir)
        self.shipped_dir = Path(shipped_dir)
        # A shipped pack chosen: kept so that a Bunker update's revised pack replaces the active copy (refresh).
        self.choice_path = Path(choice_path) if choice_path else None
        self.loaded_dir = self.translation_dir / "packs"
        self.active_path = self.translation_dir / "active.json"
        self.status_path = self.translation_dir / "status.json"

    def _folder(self, source: str) -> Path:
        return self.shipped_dir if source == "shipped" else self.loaded_dir

    def packs(self) -> list[PackInfo]:
        """Shipped packs, then loaded ones, each by language; unreadable files are left out."""
        found = []
        for source in ("shipped", "loaded"):
            for path in sorted(self._folder(source).glob("*.json")):
                data = _read(path)
                try:
                    info = read_pack(data, source, path) if data is not None else None
                except PackError:
                    info = None
                if info and path.stem == info.language:
                    found.append(info)
        return found

    def load(self, data: bytes) -> PackInfo:
        """Keep a pack the player chose, replacing a loaded pack of the same language."""
        info = read_pack(data)
        path = self.loaded_dir / f"{info.language}.json"
        _write(path, data)
        info.path = path
        return info

    def _pack_path(self, source: str, language: str) -> Path:
        if source not in ("shipped", "loaded") or not CODE.fullmatch(language or ""):
            raise PackError("Unknown language.")
        path = self._folder(source) / f"{language}.json"
        if not path.is_file():
            raise PackError(f"There is no {source} pack for {language}.")
        return path

    def remove(self, language: str):
        """Delete a loaded pack; when it is the active one, go back to English."""
        path = self._pack_path("loaded", language)
        if self.active() == f"loaded:{language}":
            self.active_path.unlink(missing_ok=True)
        path.unlink()

    def choose(self, choice: str):
        """"en", "shipped:<code>" or "loaded:<code>"."""
        if choice == "en":
            self.active_path.unlink(missing_ok=True)
            self._record(None)
            return
        source, _, language = (choice or "").partition(":")
        path = self._pack_path(source, language)
        _write(self.active_path, path.read_bytes())
        self._record(choice if source == "shipped" else None)

    def _record(self, choice: str | None):
        if not self.choice_path:
            return
        if choice:
            _write(self.choice_path, json.dumps({"choice": choice}).encode())
        else:
            self.choice_path.unlink(missing_ok=True)

    def refresh(self) -> bool:
        """After a Bunker update: a chosen shipped pack the update revised replaces the active copy.
        True when the active pack changed. A language no longer shipped keeps its last copy."""
        try:
            choice = json.loads(self.choice_path.read_text(encoding="utf-8"))["choice"] if self.choice_path else ""
        except (OSError, ValueError, KeyError, TypeError):
            return False
        source, _, language = str(choice).partition(":")
        if source != "shipped" or not CODE.fullmatch(language):
            return False
        shipped = _read(self.shipped_dir / f"{language}.json")
        if shipped is None or shipped == _read(self.active_path):
            return False
        try:
            read_pack(shipped)
        except PackError:
            return False
        _write(self.active_path, shipped)
        return True

    def active(self, packs: list[PackInfo] | None = None) -> str:
        """The choice the active pack matches, "en" without one, or "other" (packs: from packs(), to read them once)."""
        data = _read(self.active_path)
        if data is None:
            return "en"
        for info in self.packs() if packs is None else packs:
            if _read(info.path) == data:
                return f"{info.source}:{info.language}"
        return "other"

    def status(self) -> dict:
        """What the server last reported (status.json), or off."""
        try:
            status = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"state": "off"}
        return status if isinstance(status, dict) and isinstance(status.get("state"), str) else {"state": "off"}
