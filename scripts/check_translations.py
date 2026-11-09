"""Check the language files in translations/ before they are merged.

    python3 scripts/check_translations.py [translations folder]

Every <code>.json beside an en.json (other than en, ja and ko) is a translation of it. A translation
is refused when it would break a language pack or the game's text: it must be a flat JSON object of
strings, use only keys of en.json, keep each value's tags (<i>, <align="right">) and placeholders
({0}) exactly, and contain no real line break (it would split the game's key:value line). Escaped
line breaks (\\n) may differ from the English, since translations re-wrap lines. Empty values are
fine: they show the English. translations/languages.json lists the languages: {"pt-BR": {"name":
"Português (Brasil)", "ship": false}}.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = frozenset(("en", "ja", "ko"))
CODE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}")  # the device's rule (bunker_language.CODE)
MARKUP = re.compile(r"<[^<>]{1,64}>|\{[^{}]{0,20}\}")
LIMIT = 200


def markup(value: str) -> collections.Counter:
    """The tags and placeholders in a value."""
    return collections.Counter(MARKUP.findall(value))


def _shown(path: Path) -> str:
    parts = path.parts
    return "/".join(parts[parts.index("translations"):]) if "translations" in parts else path.name


def _load(path: Path):
    """(object, problems): the file's JSON object, read strictly."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return None, ["starts with a byte-order mark; save it as UTF-8 without BOM"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, ["is not UTF-8 text"]
    duplicates = []

    def pairs(items):
        seen = {}
        for key, value in items:
            if key in seen:
                duplicates.append(key)
            seen[key] = value
        return seen

    try:
        data = json.loads(text, object_pairs_hook=pairs)
    except ValueError as exc:
        return None, [f"is not valid JSON ({exc})"]
    if not isinstance(data, dict):
        return None, ["must be a JSON object of key: text"]
    return data, [f"{key}: appears more than once" for key in dict.fromkeys(duplicates)]


def check_file(path: Path, template: dict[str, str]) -> list[str]:
    """Every problem in one translation file."""
    shown = _shown(path)
    data, problems = _load(path)
    if data is None:
        return [f"{shown}: {problem}" for problem in problems]
    found = [f"{shown}: {problem}" for problem in problems]
    for key, value in data.items():
        if key not in template:
            found.append(f"{shown}: {key}: not a key of en.json")
        elif not isinstance(value, str):
            found.append(f"{shown}: {key}: must be text (in quotes)")
        elif "\n" in value or "\r" in value:
            found.append(f"{shown}: {key}: has a real line break; write \\n instead")
        elif value and markup(value) != markup(template[key]):
            missing = markup(template[key]) - markup(value)
            extra = markup(value) - markup(template[key])
            what = "; ".join(filter(None, [
                ("missing " + " ".join(missing.elements())) if missing else "",
                ("not in the English " + " ".join(extra.elements())) if extra else ""]))
            found.append(f"{shown}: {key}: tags and placeholders must match the English ({what})")
    return found


def _check_languages(path: Path) -> list[str]:
    shown = _shown(path)
    data, problems = _load(path)
    if data is None:
        return [f"{shown}: {problem}" for problem in problems]
    found = [f"{shown}: {problem}" for problem in problems]
    for code, about in data.items():
        if code in CONTEXT:
            found.append(f"{shown}: {code}: the game's own language, not a translation")
        elif not CODE.fullmatch(code):
            found.append(f"{shown}: {code}: not a language code (like pt-BR or pl)")
        if not isinstance(about, dict) or not isinstance(about.get("name"), str) or not isinstance(about.get("ship"), bool):
            found.append(f'{shown}: {code}: must be {{"name": "<the language\'s own name>", "ship": false}}')
    return found


def check_tree(translations: Path) -> list[str]:
    """Every problem in the translations folder."""
    found = []
    languages = translations / "languages.json"
    if languages.exists():
        found += _check_languages(languages)
    templates: dict[Path, dict | None] = {}
    for path in sorted(translations.rglob("*.json")):
        if path == languages or path.stem in CONTEXT:
            continue
        shown = _shown(path)
        if not CODE.fullmatch(path.stem):
            found.append(f"{shown}: the file name must be a language code (like pt-BR.json or pl.json)")
            continue
        folder = path.parent
        if folder not in templates:
            english = folder / "en.json"
            templates[folder] = json.loads(english.read_text(encoding="utf-8")) if english.is_file() else None
        if templates[folder] is None:
            found.append(f"{shown}: there is no en.json in this folder to translate")
            continue
        found += check_file(path, templates[folder])
    return found


def _translations(translations: Path) -> int:
    return sum(1 for p in translations.rglob("*.json") if p.name != "languages.json" and p.stem not in CONTEXT)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    translations = Path(args[0]) if args else ROOT / "translations"
    found = check_tree(translations)
    if not found:
        count = _translations(translations)
        print(f"Translations OK: {count} language file{'' if count == 1 else 's'} checked.")
        return 0
    for line in found[:LIMIT]:
        print(line)
    if len(found) > LIMIT:
        print(f"… and {len(found) - LIMIT} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
