"""The game's text in one language, read from its text bundles, for the translation templates.

Every key is read from text/<lang>/**.assetbundle. A key in more than one bundle
takes its text from the newest one: numbered bundles (ability/ability_0070250) are
later corrections of the unnumbered one, and a higher number is newer. Each bundle
belongs to an area (the translation file it goes in), named from its top folder.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "upstream/lunar-base/tools"))
import extract_names  # noqa: E402  lunar-base: Unity text bundle reader

AREA_OF_FOLDER = {
    "main": "story_main", "main_story_title": "story_main",
    "sub": "story_sub", "side": "story_side",
    "library": "library", "report": "library", "cage_memory": "library", "stained_glass": "library",
    "skill": "skill", "ability": "ability",
    "possession": "possession", "costume_emblem": "possession",
    "quest": "quest", "mission": "mission",
    "shop": "shop", "gacha": "shop", "gacha_title": "shop",
}
DEFAULT_AREA = "ui"
NUMBERED = re.compile(r"_(\d+)$")


@dataclass(frozen=True)
class Text:
    value: str
    bundle: str  # path under text/<lang>/ without suffix, e.g. "ability/ability_0090150"


class BundleError(Exception):
    """A text bundle that could not be read; the message starts with its path."""


def area_of(bundle: str) -> str:
    return AREA_OF_FOLDER.get(bundle.split("/")[0], DEFAULT_AREA)


def bundle_rank(bundle: str) -> int:
    match = NUMBERED.search(bundle.split("/")[-1])
    return int(match.group(1)) if match else -1


def read_text_bundle(path: Path, assetbundle_root: Path) -> list[tuple[str, str]]:
    """Every (TextAsset name, text) in one bundle."""
    mask = ")".join(path.relative_to(assetbundle_root).with_suffix("").parts)
    raw = extract_names.decrypt_text_bundle(path.read_bytes(), mask)
    # Text bundles hold serialized files only (no resource streams), so any parse
    # error is a real failure and must not drop the bundle's keys silently.
    return [asset for stream in extract_names.extract_bundle_streams(raw)
            for asset in extract_names.extract_text_assets(stream)]


def parse_lines(text: str) -> dict[str, str]:
    """key → value for each "key:value" line; values keep their spaces exactly (only a CR line end goes)."""
    entries: dict[str, str] = {}
    for line in text.split("\n"):
        line = line.removesuffix("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        separator = line.find(":")
        if separator < 0 or not line[:separator].strip():
            continue
        entries[line[:separator].strip()] = line[separator + 1:]
    return entries


def read_language(assetbundle_root: Path, lang: str, read=read_text_bundle) -> dict[str, Text]:
    """key → Text for every key in text/<lang>, the newest bundle's text for a repeated key."""
    folder = assetbundle_root / "text" / lang
    texts: dict[str, Text] = {}
    for path in sorted(folder.rglob("*.assetbundle")):
        bundle = path.relative_to(folder).with_suffix("").as_posix()
        try:
            assets = read(path, assetbundle_root)
        except Exception as error:
            raise BundleError(f"{path.relative_to(assetbundle_root).as_posix()}: {error}") from error
        rank = bundle_rank(bundle)
        for _, text in assets:
            for key, value in parse_lines(text).items():
                old = texts.get(key)
                # sorted paths: an equal rank later in the walk replaces the earlier one
                if old is None or rank >= bundle_rank(old.bundle):
                    texts[key] = Text(value, bundle)
    return texts
