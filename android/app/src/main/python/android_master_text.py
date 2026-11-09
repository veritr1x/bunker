"""A language pack's master section in the game data the game loads.

The game shows some text from its game data rather than its text bundles: the shop mascot's lines, cut-ins, gift
texts, mission titles and flavour (one row per language, LanguageType 1 Japanese, 2 English, 3 Korean). The pack's
master section ("<table>.<id>": text) replaces the English rows' text; the game keeps reading those. Bunker's own
gift row (m_gift_text 90000, "From Bunker, with love.", added by the patcher) takes the bunker catalogue's word.

Applied as a layer with Mods › Challenges (android_challenges.transform): the game data keeps an untouched copy, so
English again gives back the game data exactly.
"""
from __future__ import annotations

import hashlib
import json

# table → (id column, text column); the same tables scripts/master_text.py exports (a test keeps them equal)
TABLES = {
    "m_dokan_text": ("DokanTextId", "Text"),
    "m_gift_text": ("GiftTextId", "Text"),
    "m_navi_cut_in_text": ("NaviCutInTextId", "Text"),
    "m_webview_mission_title_text": ("WebviewMissionTitleTextId", "Text"),
    "m_webview_panel_mission_complete_flavor_text": ("WebviewPanelMissionCompleteFlavorTextId", "CompleteFlavorText"),
}
ENGLISH = 2
BUNKER_GIFT = "m_gift_text.90000"  # patch_masterdata.TABLE_ROW_ADDITIONS
BUNKER_GIFT_KEY = "pods.gift.sender_in_game"


def texts(pack: dict) -> dict[str, str]:
    """The pack's words for the game data: "<table>.<id>" → text, only for the five tables, only non-empty strings
    (a loaded pack is untrusted), and Bunker's gift row from the pack's bunker section."""
    out = {}
    master = pack.get("master") if isinstance(pack, dict) else None
    if isinstance(master, dict):
        for key, value in master.items():
            table, _, ident = str(key).rpartition(".")
            if table in TABLES and ident.isdigit() and isinstance(value, str) and value:
                out[f"{table}.{int(ident)}"] = value
    bunker = pack.get("bunker") if isinstance(pack, dict) else None
    if isinstance(bunker, dict) and isinstance(bunker.get(BUNKER_GIFT_KEY), str) and bunker[BUNKER_GIFT_KEY]:
        out[BUNKER_GIFT] = bunker[BUNKER_GIFT_KEY]
    return out


def fingerprint(words: dict[str, str]) -> str:
    """Which words are in the game data: "" for none."""
    if not words:
        return ""
    return hashlib.sha256(json.dumps(words, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def apply(toc, blob, changed, words: dict[str, str]) -> int:
    """Puts words in the English rows (into changed, as the challenges do). Returns how many rows changed."""
    import android_challenges as challenges
    count = 0
    for table, (id_column, text_column) in TABLES.items():
        mine = {int(key.rpartition(".")[2]): text for key, text in words.items() if key.rpartition(".")[0] == table}
        if not mine:
            continue

        def change(row, mine=mine, id_column=id_column, text_column=text_column):
            text = mine.get(row.get(id_column))
            if row.get("LanguageType") == ENGLISH and text is not None and text != row.get(text_column):
                return {text_column: text}
            return None
        trial = dict(changed)  # a table no row of which changes stays out of changed
        n = challenges._rewrite(toc, blob, trial, table, change)
        if n:
            changed.update(trial)
            count += n
    return count
