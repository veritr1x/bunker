"""Master data as Deck Builder reads it: the JSON dump of the active game data
(config.MASTERDATA_DIR on device), plus English names when available."""
from __future__ import annotations

import collections
import functools
import json
from pathlib import Path

# m_weapon AttributeType (masterdata/bunker_elements.go)
ELEMENTS = {1: "dark", 2: "fire", 3: "light", 5: "water", 6: "wind"}
REBORN = range(41000, 45004)
FROZEN_HEART = range(51001, 55004)


PLAYER_CHARACTER_LIMIT = 10000


class Tables:
    def __init__(self, master_dir, names_dir=None):
        self.master_dir = Path(master_dir)
        self.names_dir = Path(names_dir) if names_dir else None

    # -- raw access (the names power.py was verified with) --------------------
    @functools.lru_cache(None)
    def T(self, name):
        path = self.master_dir / f"EntityM{name}Table.json"
        if not path.exists():
            return []
        return [r for r in json.loads(path.read_text()) if isinstance(r, dict)]

    @functools.lru_cache(None)
    def idx(self, name, key):
        return {r[key]: r for r in self.T(name)}

    @functools.lru_cache(None)
    def grp(self, name, key):
        d = collections.defaultdict(list)
        for r in self.T(name):
            d[r[key]].append(r)
        return d

    @functools.lru_cache(None)
    def config(self, key):
        for r in self.T("Config"):
            if r["ConfigKey"] == key:
                return int(r["Value"])
        raise KeyError(key)

    @functools.lru_cache(None)
    def power_consts(self):
        # DeckPowerCalculationConstantValues.Setup 0x27F7F2C: type -> field; absent types stay 0.
        c = collections.defaultdict(int)
        for r in self.T("PowerCalculationConstantValue"):
            c[r["PowerCalculationConstantValueType"]] = r["ConstantValue"]
        return c

    @functools.lru_cache(None)
    def nf(self, fid):
        f = self.idx("NumericalFunction", "NumericalFunctionId").get(fid)
        if not f:
            return None
        rows = self.grp("NumericalFunctionParameterGroup", "NumericalFunctionParameterGroupId")[f["NumericalFunctionParameterGroupId"]]
        params = [r["ParameterValue"] for r in sorted(rows, key=lambda r: r["ParameterIndex"])]
        return f["NumericalFunctionType"], tuple(params)

    # -- public names ----------------------------------------------------------
    def table(self, name: str) -> list[dict]:
        return self.T(name)

    def by_id(self, name: str, key: str) -> dict:
        return self.idx(name, key)

    @functools.lru_cache(None)
    def _names(self, kind):
        if not self.names_dir:
            return {}
        path = self.names_dir / f"{kind}.json"
        if not path.exists():
            return {}
        data = json.loads(path.read_text())
        recs = data.get("records", data) if isinstance(data, dict) else data
        return {r["id"]: r for r in recs if isinstance(r, dict) and r.get("name_found", True) and r.get("name")}

    def name(self, kind: str, id: int) -> str:
        r = self._names(kind).get(id)
        if not r:
            return f"{kind[:-1] if kind.endswith('s') else kind} {id}"
        cn = r.get("character_name")
        return f"{r['name']} {cn}" if kind == "costumes" and cn else r["name"]

    def character_name(self, costume_id: int) -> str:
        r = self._names("costumes").get(costume_id)
        if r and r.get("character_name"):
            return r["character_name"]
        return f"costume {costume_id}"

    def costume_name(self, costume_id: int) -> str:
        """"Yuletide Soldier Lars"."""
        return self.name("costumes", costume_id)

    def icon_asset(self, kind: str, id: int) -> str | None:
        """A piece's icon in the game's files: its _standard art, as the game's notices show it.
        kind: weapon, companion, memoir (a part id) or debris (a thought id)."""
        asset = folder = None
        if kind == "weapon":
            folder, asset = "weapon", self._names("weapons").get(id, {}).get("weapon_actor_asset_id")
        elif kind == "companion":
            folder, asset = "companion", self._names("companions").get(id, {}).get("companion_actor_asset_id")
        elif kind == "memoir":
            part = self.idx("Parts", "PartsId").get(id)
            group = part and self.idx("PartsGroup", "PartsGroupId").get(part["PartsGroupId"])
            folder, asset = "memory", group and f"memory{group['PartsGroupAssetId']:03d}"
        elif kind == "debris":
            thought = self.idx("Thought", "ThoughtId").get(id)
            folder, asset = "thought", thought and f"thought{thought['ThoughtAssetId']:06d}"
        return f"ui/{folder}/{asset}/{asset}_standard.assetbundle" if asset else None

    def memoir_set_name(self, part_id: int) -> str:
        """The set a memoir belongs to ("Solemnity")."""
        part = self.idx("Parts", "PartsId").get(part_id)
        return self.name("parts", part["PartsGroupId"]) if part else ""

    def costume_element(self, costume_id: int) -> str | None:
        """The element a costume is usually fielded with: costume ids 3EXXX
        encode it (1 fire, 2 water, 3 wind, 4 light, 5 dark); other costumes
        take their element from the main weapon, so None."""
        if 30000 <= costume_id < 40000:
            return {1: "fire", 2: "water", 3: "wind", 4: "light", 5: "dark"}.get(costume_id // 1000 % 10)
        return None

    def is_fieldable(self, costume_id: int) -> bool:
        """Playable and with an active skill in the data: a costume a deck can field (some playable-flagged
        variants have none)."""
        c = self.idx("Costume", "CostumeId").get(costume_id)
        return bool(c) and self.is_playable(costume_id) and bool(self.grp("CostumeActiveSkillGroup", "CostumeActiveSkillGroupId").get(c["CostumeActiveSkillGroupId"]))

    def is_playable(self, costume_id: int) -> bool:
        r = self._names("costumes").get(costume_id)
        if r is not None and "is_playable_character_costume" in r:
            return bool(r["is_playable_character_costume"])
        c = self.idx("Costume", "CostumeId").get(costume_id)
        # No name record: a playable character's id is below 10000 (enemies and bosses are 10001, 1000001, ...).
        return bool(c) and 0 < c.get("CharacterId", 0) < PLAYER_CHARACTER_LIMIT

    def is_ex(self, costume_id: int) -> bool:
        return costume_id in REBORN or costume_id in FROZEN_HEART
