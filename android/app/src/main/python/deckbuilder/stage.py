"""The staging save: where Deck Builder has the server raise pieces to max.

Every step is an action the server already has (Upgrade Manager's grants and
upgrades), run on the staging save (the Android bridge's "deckbuilder_stage"
target; bunker-edit on desktop and in tests), never on the player's save. The
order matters: exalting raises the costume level cap, so it comes before the
costume upgrade.
"""
from __future__ import annotations

from typing import Callable

EXALT_MAX = 5
RANK_MAX = 10      # a character's top rank (CharacterLevelBonusAbilityGroup)
IMPORTANT_ITEM = 13        # model.PossessionTypeImportantItem
STAINED_GLASS = 5          # ImportantItemType: a stained glass, flat stats for a character or a weapon type
TARGET = "deckbuilder_stage"


def panels_by_character(tables) -> dict[int, list[int]]:
    """Every Mythic Slab panel of each character (as Upgrade Manager's Fill
    Mythic Slabs releases them)."""
    groups_by_cat, boards_by_group, panels_by_board = {}, {}, {}
    for g in tables.T("CharacterBoardGroup"):
        groups_by_cat.setdefault(g["CharacterBoardCategoryId"], []).append(g["CharacterBoardGroupId"])
    for b in tables.T("CharacterBoard"):
        boards_by_group.setdefault(b["CharacterBoardGroupId"], []).append(b["CharacterBoardId"])
    for p in tables.T("CharacterBoardPanel"):
        panels_by_board.setdefault(p["CharacterBoardId"], []).append(p["CharacterBoardPanelId"])
    out: dict[int, list[int]] = {}
    for a in tables.T("CharacterBoardAssignment"):
        ids = out.setdefault(a["CharacterId"], [])
        for gid in groups_by_cat.get(a["CharacterBoardCategoryId"], []):
            for bid in boards_by_group.get(gid, []):
                ids.extend(p for p in panels_by_board.get(bid, []) if p not in ids)
    return out


class Stager:
    def __init__(self, invoke: Callable[[dict], dict], tables):
        self.invoke = invoke
        self.tables = tables

    def _do(self, action: str, **fields):
        return self.invoke(dict(fields, action=action, target=TARGET))

    def build(self, costume_ids=(), weapon_ids=(), companion_ids=(), thought_ids=(), memoirs=(),
              karma: dict[int, list[tuple[int, int]]] | None = None, costume_karma: dict | None = None) -> None:
        """A new staging save holding these pieces, fully raised. Karma: each slot's first top-tier option (or the
        karma preferences), then costume_karma {costume id: {slot: odds number}} for the costumes it names."""
        self._do("stage_new")
        costumes = self.tables.idx("Costume", "CostumeId")
        characters = sorted({costumes[c]["CharacterId"] for c in costume_ids if c in costumes})
        if costume_ids:
            self._do("grant_costume_batch", costume_ids=list(costume_ids))
        if weapon_ids:
            self._do("grant_weapon_batch", weapons=[{"weapon_id": w} for w in weapon_ids])
        if companion_ids:
            self._do("grant_companion_batch", companion_ids=list(companion_ids))
        if thought_ids:
            self._do("grant_thought_batch", thought_ids=list(thought_ids))
        if characters:
            self._do("exalt_characters", exaltations=[{"character_id": c, "rebirth_count": EXALT_MAX} for c in characters])
            self._do("rank_characters", ranks=[{"character_id": c, "level": RANK_MAX} for c in characters])
            glass = [i["ImportantItemId"] for i in self.tables.T("ImportantItem") if i["ImportantItemType"] == STAINED_GLASS]
            if glass:
                self._do("grant_batch", grants=[{"possession_type": IMPORTANT_ITEM, "possession_id": g, "count": 1} for g in glass])
        if costume_ids:
            self._do("upgrade_all_costumes")
        if weapon_ids:
            self._do("upgrade_all_weapons")
        if companion_ids:
            self._do("upgrade_all_companions")
        panels = panels_by_character(self.tables)
        panel_ids = [p for c in characters for p in panels.get(c, [])]
        if panel_ids:
            self._do("release_panels", panel_ids=panel_ids)
        if costume_ids:
            prefs = {str(slot): [{"effect_type": et, "target_id": tid} for et, tid in v] for slot, v in (karma or {}).items() if v}
            self._do("fill_karma_slots", **({"karma_preferences": prefs} if prefs else {}))
            self.set_karma(costume_karma)
        if memoirs:
            self._do("grant_memoir_batch", memoirs=list(memoirs))

    def set_karma(self, costume_karma: dict | None) -> None:
        """Each named costume's karma, slot by slot ({costume id: {slot: odds number}}; slots must be unlocked)."""
        specs = [{"costume_id": int(c), "karma": {str(s): int(o) for s, o in k.items()}} for c, k in (costume_karma or {}).items() if k]
        if specs:
            self._do("set_costume_karma_batch", costume_karma=specs)
