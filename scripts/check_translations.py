"""Check the language files in translations/ before they are merged.

    python3 scripts/check_translations.py [translations folder]

Language files live at translations/game/<area>/<code>.json and translations/master/<code>.json,
beside the en.json they translate (en, ja and ko are the game's own). Every language must be listed
in translations/languages.json: {"pt-BR": {"name": "Português (Brasil)", "ship": false}}.

A translation is refused when it would break a language pack, the release build or the game's text:
it must be a flat JSON object of text, use only keys of en.json, keep each value's tags (<i>, <br>,
<align="right">), placeholders ({0}) and other braces exactly, and contain no broken character
escapes. Game and master texts may only use characters the game's fonts can show, with the letters
Bunker adds (fonts/coverage.json, written by android/tools/game_fonts.py coverage). Game texts may have no real line break (it would split the game's key:value line); escaped
ones (\\n) may differ from the English, since translations re-wrap lines. Empty values are fine:
they show the English.
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
PLACEHOLDER = re.compile(r"\{[^{}]{0,20}\}")
MARKUP = re.compile(r"<[^<>]{1,64}>|\{[^{}]{0,20}\}")
COMPONENTS = ("master", "bunker")  # translations/<component>/<code>.json; the game's text is game/<area>/<code>.json
LIMIT = 200


def markup(value: str) -> collections.Counter:
    """The tags, placeholders and lone braces in a value."""
    found = collections.Counter(MARKUP.findall(value))
    rest = PLACEHOLDER.sub("", value)
    for brace in "{}":
        if rest.count(brace):
            found[brace] = rest.count(brace)
    return found


def _shown(path: Path) -> str:
    parts = path.parts
    return "/".join(parts[parts.index("translations"):]) if "translations" in parts else path.name


def _load(path: Path):
    """(JSON object or None, problems): the file read strictly; never raises."""
    if path.is_symlink():
        return None, ["is a link to another file; add the file itself"]
    if not path.is_file():
        return None, ["is not a file"]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, [f"cannot be read ({exc.strerror})"]
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

    def constant(name):
        raise ValueError(f"{name} is not allowed")

    try:
        data = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError as exc:
        return None, [f"is not valid JSON ({exc})"]
    except RecursionError:
        return None, ["is not valid JSON (nested too deeply)"]
    if not isinstance(data, dict):
        return None, ["must be a JSON object of key: text"]
    return data, [f"{key}: appears more than once" for key in dict.fromkeys(duplicates)]


def check_file(path: Path, template: dict[str, str], line_breaks: bool = False,
               coverage: frozenset[int] | None = None) -> list[str]:
    """Every problem in one translation file. line_breaks: real line breaks allowed (master texts have them).
    coverage: the characters the game can show (load_coverage); None skips that check."""
    shown = _shown(path)
    data, problems = _load(path)
    found = [f"{shown}: {problem}" for problem in problems]
    if data is None:
        return found
    for key, value in data.items():
        if key not in template:
            found.append(f"{shown}: {key}: not a key of en.json")
        elif not isinstance(value, str):
            found.append(f"{shown}: {key}: must be text (in quotes)")
        elif any("\ud800" <= ch <= "\udfff" for ch in value):
            found.append(f"{shown}: {key}: has a broken character escape (half of an emoji or a \\u code)")
        elif value and not value.strip():
            found.append(f"{shown}: {key}: is only spaces; leave it empty (\"\") to show the English")
        elif not line_breaks and ("\n" in value or "\r" in value):
            found.append(f"{shown}: {key}: has a real line break; write \\\\n (two backslashes) instead")
        elif value and markup(value) != markup(template[key]):
            missing = markup(template[key]) - markup(value)
            extra = markup(value) - markup(template[key])
            what = "; ".join(filter(None, [
                ("missing " + " ".join(missing.elements())) if missing else "",
                ("not in the English " + " ".join(extra.elements())) if extra else ""]))
            found.append(f"{shown}: {key}: tags, placeholders and braces must match the English ({what})")
        if coverage is not None and key in template and isinstance(value, str) \
                and not any("\ud800" <= ch <= "\udfff" for ch in value):
            unshown = list(dict.fromkeys(ch for ch in value if ch not in "\n\r\t" and ord(ch) not in coverage))
            if unshown:
                letters = unshown[:3]
                found.append(f"{shown}: {key}: the game's fonts cannot show {' '.join(letters)} "
                             f"({' '.join(f'U+{ord(ch):04X}' for ch in letters)})")
    return found


def load_coverage(path: Path) -> frozenset[int]:
    """The characters the game's fonts can show, with Bunker's added letters (fonts/coverage.json)."""
    ranges = json.loads(path.read_text())["ranges"]
    return frozenset(c for first, last in ranges for c in range(first, last + 1))


def _check_languages(path: Path) -> tuple[list[str], set[str]]:
    """(problems, the listed codes)."""
    shown = _shown(path)
    if not path.exists() and not path.is_symlink():
        return [f"{shown}: missing; it lists the languages ({{\"pt-BR\": {{\"name\": \"Português (Brasil)\", \"ship\": false}}}})"], set()
    data, problems = _load(path)
    found = [f"{shown}: {problem}" for problem in problems]
    if data is None:
        return found, set()
    seen: dict[str, str] = {}
    for code, about in data.items():
        if code.lower() in CONTEXT:
            found.append(f"{shown}: {code}: the game's own language, not a translation")
        elif not CODE.fullmatch(code):
            found.append(f"{shown}: {code}: not a language code (like pt-BR or pl)")
        elif code.lower() in seen:
            found.append(f"{shown}: {code}: the same language as {seen[code.lower()]}")
        seen.setdefault(code.lower(), code)
        if not isinstance(about, dict) or not isinstance(about.get("name"), str) or not isinstance(about.get("ship"), bool):
            found.append(f'{shown}: {code}: must be {{"name": "<the language\'s own name>", "ship": false}}')
    return found, set(data)


def _place(translations: Path, path: Path) -> bool:
    """A language file's folder is one the packs read: game/<area>/ or master/ (bunker/)."""
    parts = path.relative_to(translations).parts
    return (len(parts) == 3 and parts[0] == "game") or (len(parts) == 2 and parts[0] in COMPONENTS)


def check_tree(translations: Path, coverage: frozenset[int] | None = None) -> list[str]:
    """Every problem in the translations folder. coverage applies to game and master texts (the game shows them)."""
    languages = translations / "languages.json"
    found, listed = _check_languages(languages)
    templates: dict[Path, dict | None] = {}
    for path in sorted(translations.rglob("*.json")):
        if path == languages:
            continue
        shown = _shown(path)
        if path.stem in CONTEXT and not path.is_symlink():
            continue  # the template and the game's own text, not translations
        if not _place(translations, path):
            found.append(f"{shown}: not a folder of translations (game/<area>/ or master/)")
            continue
        if not CODE.fullmatch(path.stem):
            found.append(f"{shown}: the file name must be a language code (like pt-BR.json or pl.json)")
            continue
        if path.stem not in listed:
            found.append(f"{shown}: {path.stem} is not in languages.json; add it with its name and \"ship\": false")
        folder = path.parent
        if folder not in templates:
            english = folder / "en.json"
            if english.exists() or english.is_symlink():
                template, problems = _load(english)
                found += [f"{_shown(english)}: {problem}" for problem in problems]
                templates[folder] = template
            else:
                templates[folder] = None
                found.append(f"{shown}: there is no en.json in this folder to translate")
        if templates[folder] is not None:
            component = path.relative_to(translations).parts[0]
            found += check_file(path, templates[folder], line_breaks=component != "game",
                                coverage=coverage if component in ("game", "master") else None)
    return found


def _translations(translations: Path) -> int:
    return sum(1 for p in translations.rglob("*.json") if p.name != "languages.json" and p.stem not in CONTEXT)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    translations = Path(args[0]) if args else ROOT / "translations"
    found = check_tree(translations, load_coverage(ROOT / "fonts/coverage.json"))
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
