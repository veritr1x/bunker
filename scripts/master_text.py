"""The master data's translatable texts: the tables with one row per language (LanguageType)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "upstream/lunar-base/tools"))

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
    """Language code → "<table>.<id>" → text."""
    out: dict[str, dict[str, str]] = {code: {} for code in LANGUAGES.values()}
    for table, (id_column, text_column) in MASTER_TEXT_TABLES.items():
        for row in tables.get(table, []):
            code = LANGUAGES.get(row.get("LanguageType"))
            if code:
                out[code][f"{table}.{row[id_column]}"] = row[text_column]
    return out


def load_master_tables(master_path: Path, names) -> dict[str, list[dict]]:
    """The named tables of the encrypted master data (the .bin.e file), as lists of rows."""
    import dump_masterdata
    import msgpack
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    key, iv = bytes.fromhex(dump_masterdata.DEFAULT_KEY), bytes.fromhex(dump_masterdata.DEFAULT_IV)
    decoded = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(master_path.read_bytes()), AES.block_size)
    try:
        toc, blob = msgpack.unpackb(decoded, raw=False, strict_map_key=False), b""
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    schemas = dump_masterdata.load_schemas()
    tables = {}
    for name in names:
        if name in toc and name in schemas:
            offset, length = toc[name]
            rows = dump_masterdata.decompress_table(blob, offset, length)
            tables[name] = dump_masterdata.rows_to_dicts(rows, schemas[name][1])
    return tables
