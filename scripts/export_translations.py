"""Write the translation templates from a game dump.

    python3 scripts/export_translations.py --dump <revisions/0 folder> --master <bin.e> --out translations

writes translations/game/<area>/{en,ja,ko}.json and translations/master/{en,ja,ko}.json:
English is the template translators work from; Japanese and Korean (the game's own text)
are kept beside it as context. Other files in the output folder (translators' language
files) are never touched. The same dump always gives byte-identical files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from game_text import Text, area_of, read_language
from master_text import MASTER_TEXT_TABLES, load_master_tables, texts_from_tables

CONTEXT_LANGUAGES = ("ja", "ko")


def game_catalogue(en: dict[str, Text], context: dict[str, dict[str, Text]]) -> dict[str, dict[str, dict[str, str]]]:
    """area → language → key → text; the context languages keep only English keys, in the English key's area."""
    catalogue: dict[str, dict[str, dict[str, str]]] = {}
    for key, text in en.items():
        area = catalogue.setdefault(area_of(text.bundle), {lang: {} for lang in ("en", *CONTEXT_LANGUAGES)})
        area["en"][key] = text.value
        for lang in CONTEXT_LANGUAGES:
            other = context.get(lang, {}).get(key)
            if other is not None:
                area[lang][key] = other.value
    return catalogue


def dump_json(data: dict[str, str]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_catalogue(out: Path, game: dict[str, dict[str, dict[str, str]]], master: dict[str, dict[str, str]]) -> list[Path]:
    """Write the game and master templates under out; returns the files written."""
    files = {out / "game" / area / f"{lang}.json": texts for area, langs in game.items() for lang, texts in langs.items()}
    files.update({out / "master" / f"{lang}.json": texts for lang, texts in master.items()})
    for path, texts in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump_json(texts))
    # An area the game no longer has: its templates go; translations of it stay for the check to name.
    for stale in sorted((out / "game").glob("*/*.json")):
        if stale.stem in ("en", *CONTEXT_LANGUAGES) and stale not in files:
            stale.unlink()
    return list(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dump", type=Path, required=True, help="the game dump's revisions/0 folder")
    parser.add_argument("--master", type=Path, required=True, help="the master data (.bin.e)")
    parser.add_argument("--out", type=Path, default=Path("translations"))
    args = parser.parse_args()

    assetbundle = args.dump / "assetbundle"
    en = read_language(assetbundle, "en")
    context = {lang: read_language(assetbundle, lang) for lang in CONTEXT_LANGUAGES}
    game = game_catalogue(en, context)
    master = texts_from_tables(load_master_tables(args.master, MASTER_TEXT_TABLES))
    write_catalogue(args.out, game, master)
    for area in sorted(game):
        texts = game[area]["en"]
        print(f"{area:12} {len(texts):7} keys {sum(map(len, texts.values())):9} characters")
    print(f"{'master':12} {len(master['en']):7} keys")
    print(f"{'total':12} {len(en):7} game keys")


if __name__ == "__main__":
    main()
