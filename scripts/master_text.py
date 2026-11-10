"""The master data's translatable texts: the tables with one row per language (LanguageType)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "upstream/lunar-base/tools"))
sys.path.insert(0, str(ROOT / "android/app/src/main/python"))
# Pod Programs' Archive reads the master data the same way; one loader serves both.
from archive.index import load_tables  # noqa: E402

# table → (id column, text column)
MASTER_TEXT_TABLES = {
    "m_dokan_text": ("DokanTextId", "Text"),
    "m_gift_text": ("GiftTextId", "Text"),
    "m_navi_cut_in_text": ("NaviCutInTextId", "Text"),
    "m_webview_mission_title_text": ("WebviewMissionTitleTextId", "Text"),
    "m_webview_panel_mission_complete_flavor_text": ("WebviewPanelMissionCompleteFlavorTextId", "CompleteFlavorText"),
}
LANGUAGES = {1: "ja", 2: "en", 3: "ko"}


def texts_from_tables(tables: dict[str, list[dict]]) -> dict[str, dict[str, str]]:
    """Language code → "<table>.<id>" → text; Japanese and Korean only for keys English has."""
    out: dict[str, dict[str, str]] = {code: {} for code in LANGUAGES.values()}
    for table, (id_column, text_column) in MASTER_TEXT_TABLES.items():
        for row in tables.get(table, []):
            code = LANGUAGES.get(row.get("LanguageType"))
            if code:
                out[code][f"{table}.{row[id_column]}"] = row[text_column]
    for code in out:
        if code != "en":
            out[code] = {key: text for key, text in out[code].items() if key in out["en"]}
    return out


def load_master_tables(master_path: Path, names) -> dict[str, list[dict]]:
    """The named tables of the encrypted master data (the .bin.e file), as lists of rows.

    A table the master data lacks is an error: its texts would silently go missing from the templates."""
    return load_tables(master_path, names, required=True)
