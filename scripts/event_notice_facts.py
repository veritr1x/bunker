"""The facts a rebuilt event notice shows (event_notice_pages.py), from the game data.

Run facts (exchange, medal, quest bonuses) come from the weekly master published
during the run (event_runs.run_view); characters, weapons, skills and abilities
from the final data through Deck Builder's tables, whose stat pipeline is the
client's. Panel stats follow the official panels: the costume at its maximum
level (four limit breaks) with its awakening status-ups and its own stat
abilities; the fully evolved weapon at its maximum level with its abilities at
their top level. check_event_notices.py compares both with every official panel.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
from pathlib import Path

import calendar_history as ch
import event_runs as er

ROOT = ch.ROOT
sys.path.insert(0, str(ch.PYTHON))
from deckbuilder import power as P  # noqa: E402
from deckbuilder.tables import Tables  # noqa: E402

TEXTS = ROOT / "translations/game"
COSTUME, WEAPON, MEDAL = 1, 2, 6  # PossessionType
SHOP_TABLES = ("m_shop", "m_shop_item", "m_shop_item_cell", "m_shop_item_cell_group", "m_shop_item_content_possession")
HP, ATK, VIT, AGI = P.HP, P.ATK, P.VIT, P.AGI


class Images:
    """Images from the resource dump, as WebP pack members; missing bundles are recorded for extraction."""

    def __init__(self, assets: Path):
        self.assets, self.members, self.missing, self._cache = assets, {}, set(), {}

    def image(self, rel):
        if rel in self._cache:
            return self._cache[rel]
        path = self.assets / (rel + ".assetbundle")
        if not path.exists():
            self.missing.add(rel + ".assetbundle")
            self._cache[rel] = None
            return None
        import UnityPy
        from export_asset_images import unmask
        env = UnityPy.load(unmask(path.read_bytes(), rel + ".assetbundle"))
        textures = [o.read() for o in env.objects if o.type.name == "Texture2D"]
        image = max(textures, key=lambda t: t.m_Width * t.m_Height).image.convert("RGBA") if textures else None
        if image is not None:
            box = image.getchannel("A").getbbox()
            image = image.crop(box) if box else image
        self._cache[rel] = image
        return image

    def _webp(self, image):
        buf = io.BytesIO()
        image.save(buf, format="WEBP", lossless=True, exact=True)
        return buf.getvalue()

    def img(self, rel):
        """A pack member img/<sha>.webp for a dump image, or None."""
        image = self.image(rel)
        if image is None:
            return None
        data = self._webp(image)
        member = f"img/{hashlib.sha256(data).hexdigest()}.webp"
        self.members[member] = data
        return member

    def portrait(self, rel, kind):
        """A web image the panels name by URL (/images/en/operations/<kind>/<sha>), or ''."""
        image = self.image(rel)
        if image is None:
            return ""
        data = self._webp(image)
        sha = hashlib.sha256(data).hexdigest()
        self.members[f"web/images/en/operations/{kind}/{sha}"] = data
        return f"/images/en/operations/{kind}/{sha}"


class Facts:
    def __init__(self, masters, deckbuilder_master: Path, deckbuilder_names: Path, images: Images, pack_titles=()):
        self.schemas = ch.dm.load_schemas()
        self.by_time = {ch.file_time(p): p for p in masters if ch.file_time(p) is not None}
        self.times = sorted(self.by_time)
        self.m = Tables(deckbuilder_master, deckbuilder_names)
        self.images = images
        self.text = {}
        for part in ("quest", "possession", "shop", "skill", "ability"):
            self.text.update(json.loads((TEXTS / part / "en.json").read_text()))
        self.crossovers = {n for t in pack_titles for n in re.findall(r'Crossover Quest "([^"]+)"', t)}
        self._masters = {}

    # -- the run's own data ---------------------------------------------------------
    def tables_at(self, at):
        before = [t for t in self.times if t <= at]
        t = max(before) if before else self.times[0]
        if t not in self._masters:
            toc, blob = ch.load(self.by_time[t])
            self._masters[t] = er.read(toc, blob, self.schemas, names=er.TABLES + SHOP_TABLES)
        return self._masters[t]

    def chapter_name(self, row):
        return self.text.get(f"quest.event.chapter_title.{row['NameEventQuestTextId']}", "")

    # -- names and stats -------------------------------------------------------------
    def costume_names(self, cid):
        ch_name = self.m.character_name(cid)
        return ch_name, self.m.costume_name(cid).removesuffix(" " + ch_name)

    def weapon_name(self, wid):
        return self.m.name("weapons", wid).strip()

    def max_level(self, table, rarity, lb=4):
        row = next(x for x in self.m.T(table) if x["RarityType"] == rarity)
        f = self.m.nf(row["MaxLevelNumericalFunctionId"])
        return P.calc_parameter(f[0], f[1], lb)

    def evolved(self, wid):
        rows = self.m.T("WeaponEvolutionGroup")
        mine = next((g for g in rows if g["WeaponId"] == wid), None)
        if not mine:
            return wid
        return max((g for g in rows if g["WeaponEvolutionGroupId"] == mine["WeaponEvolutionGroupId"]),
                   key=lambda g: g["EvolutionOrder"])["WeaponId"]

    def ability(self, ability_id, level):
        rows = self.m.grp("AbilityLevelGroup", "AbilityLevelGroupId").get(ability_id, [])
        row = P.closest_lower(rows, "LevelLowerLimit", level)
        if not row:
            return None
        d = self.m.idx("AbilityDetail", "AbilityDetailId")[row["AbilityDetailId"]]
        icon = self.images.img(f"ui/ability/ability{d['AssetCategoryId']}{d['AssetVariationId']:03d}/"
                               f"ability{d['AssetCategoryId']}{d['AssetVariationId']:03d}_standard")
        return {"name": self.text.get(f"ability.name.{d['NameAbilityTextId']}", ""),
                "description": self.text.get(f"ability.description.long.{d['DescriptionAbilityTextId']}", ""), "icon": icon}

    def skill(self, skill_id):
        s = next((r for r in self.m.T("Skill") if r["SkillId"] == skill_id), None)
        if not s:
            return None
        levels = [r for r in self.m.T("SkillLevelGroup") if r["SkillLevelGroupId"] == s["SkillLevelGroupId"]]
        d = self.m.idx("SkillDetail", "SkillDetailId")[max(levels, key=lambda r: r["LevelLowerLimit"])["SkillDetailId"]]
        cat, var = d["SkillAssetCategoryId"], d["SkillAssetVariationId"]
        icon = self.images.img(f"ui/skill/skillcategory{cat}/skill{cat}{var:03d}/skill{cat}{var:03d}_standard")
        return {"name": self.text.get(f"skill.name.{d['NameSkillTextId']}", ""),
                "description": self.text.get(f"skill.description.long.{d['DescriptionSkillTextId']}", ""),
                "cooldown": d["SkillCooltimeValue"] // 30, "icon": icon}

    def costume_panel(self, cid, lb=4, aw=5):
        m = self.m
        c = m.idx("Costume", "CostumeId")[cid]
        level = self.max_level("CostumeRarity", c["RarityType"], lb)
        base = P.costume_base_status(m, cid, level)
        awaken = {k: 0 for k in (HP, ATK, VIT, AGI)}
        abilities, shown = [], []
        aw_row = m.idx("CostumeAwaken", "CostumeId").get(cid)
        slots = sorted(m.grp("CostumeAbilityGroup", "CostumeAbilityGroupId").get(c["CostumeAbilityGroupId"], []),
                       key=lambda r: r["SlotNumber"])
        for r in slots:
            lvr = P.closest_lower(m.grp("CostumeAbilityLevelGroup", "CostumeAbilityLevelGroupId").get(r["CostumeAbilityLevelGroupId"], []),
                                  "CostumeLimitBreakCountLowerLimit", lb)
            level_a = lvr["AbilityLevel"] if lvr else 0
            abilities.append(P.Ability(m, r["AbilityId"], level_a, "slot"))
            shown.append(self.ability(r["AbilityId"], level_a))
        if aw_row:
            ups = m.grp("CostumeAwakenStatusUpGroup", "CostumeAwakenStatusUpGroupId")
            for e in sorted(m.grp("CostumeAwakenEffectGroup", "CostumeAwakenEffectGroupId").get(aw_row["CostumeAwakenEffectGroupId"], []),
                            key=lambda e: e["AwakenStep"]):
                if e["AwakenStep"] > aw:
                    continue
                if e["CostumeAwakenEffectType"] == 1:
                    for u in ups.get(e["CostumeAwakenEffectId"], []):
                        if u["StatusCalculationType"] == 2 and u["StatusKindType"] in awaken:
                            awaken[u["StatusKindType"]] += u["EffectValue"]
                elif e["CostumeAwakenEffectType"] == 2:
                    a = m.idx("CostumeAwakenAbility", "CostumeAwakenAbilityId").get(e["CostumeAwakenEffectId"])
                    if a:
                        abilities.append(P.Ability(m, a["AbilityId"], a["AbilityLevel"], "awaken"))
                        shown.append(self.ability(a["AbilityId"], a["AbilityLevel"]))
        status = {}
        for k in awaken:
            v = base[k] + P.permil(base[k], awaken[k])
            for a in abilities:
                for st in a.statuses:
                    if st["org"] == 4 and st["value"].get(k):
                        v += P.permil(base[k], st["value"][k]) if st["change"] == 2 else st["value"][k]
            status[k] = v
        group = P.closest_lower(m.grp("CostumeActiveSkillGroup", "CostumeActiveSkillGroupId").get(c["CostumeActiveSkillGroupId"], []),
                                "CostumeLimitBreakCountLowerLimit", lb)
        skill = self.skill(group["CostumeActiveSkillId"]) if group else None
        character, costume = self.costume_names(cid)
        asset = f"ch{c['ActorSkeletonId']:03d}{c['AssetVariationId']:03d}"
        return {"id": cid, "character": character, "costume": costume, "stars": c["RarityType"] // 10,
                "weapon_type": c["SkillfulWeaponType"],
                "status": {"HP": status[HP], "Attack": status[ATK], "Defense": status[VIT], "Agility": status[AGI]},
                "skill": skill, "abilities": [a for a in shown if a],
                "portrait": self.images.portrait(f"ui/costume/{asset}/{asset}_full", "character")}

    def weapon_panel(self, wid):
        m = self.m
        wid = self.evolved(wid)
        w = m.idx("Weapon", "WeaponId")[wid]
        level = self.max_level("WeaponRarity", w["RarityType"])
        base = P.weapon_base_status(m, wid, level)
        slots = sorted(m.grp("WeaponAbilityGroup", "WeaponAbilityGroupId").get(w.get("WeaponAbilityGroupId"), []),
                       key=lambda r: r["SlotNumber"])
        status = {}
        abilities = [P.Ability(m, r["AbilityId"], 99, "weapon") for r in slots]
        for k in (HP, ATK, VIT):
            v = base[k]
            for a in abilities:
                for st in a.statuses:
                    if st["org"] == 4 and st["value"].get(k):
                        v += P.permil(base[k], st["value"][k]) if st["change"] == 2 else st["value"][k]
            status[k] = v
        shown = [self.ability(r["AbilityId"], 99) for r in slots]
        shown = [a for a in shown if a]
        barriers = [dict(a, name=re.sub(r" Rank (\d+)$", r"・Rank\1", a["name"])) for a in shown if a["name"].startswith("Barrier:")]
        skills = []
        for r in sorted(m.grp("WeaponSkillGroup", "WeaponSkillGroupId").get(w["WeaponSkillGroupId"], []), key=lambda r: r["SlotNumber"]):
            s = self.skill(r["SkillId"])
            if s:
                skills.append(s)
        asset = f"wp{w['WeaponType']:03d}{w['AssetVariationId']:03d}"
        return {"id": wid, "name": self.weapon_name(wid), "stars": w["RarityType"] // 10, "element": w["AttributeType"],
                "weapon_type": w["WeaponType"], "status": {"HP": status[HP], "Attack": status[ATK], "Defense": status[VIT]},
                "skills": skills, "abilities": [a for a in shown if not a["name"].startswith("Barrier:")], "barriers": barriers,
                "portrait": self.images.portrait(f"ui/weapon/{asset}/{asset}_full", "weapon")}

    def weapon_icon(self, wid):
        w = self.m.idx("Weapon", "WeaponId").get(wid)
        if not w:
            return None
        asset = f"wp{w['WeaponType']:03d}{w['AssetVariationId']:03d}"
        return self.images.img(f"ui/weapon/{asset}/{asset}_standard")

    def costume_icon(self, cid):
        c = self.m.idx("Costume", "CostumeId").get(cid)
        if not c:
            return None
        asset = f"ch{c['ActorSkeletonId']:03d}{c['AssetVariationId']:03d}"
        return self.images.img(f"ui/costume/{asset}/{asset}_standard")

    def consumable_icon(self, item_id):
        base = f"ui/consumable_item/consumable{item_id}/consumable{item_id}"
        return self.images.img(base + "_icon") or self.images.img(base + "_standard")

    # -- one run -----------------------------------------------------------------------
    def event(self, chapter, run):
        """Facts for chapter's run (start, end)."""
        start, end = run
        t = self.tables_at(start + (min(end, start + 30 * 86_400_000) - start) // 2)
        row = next((r for r in t["m_event_quest_chapter"] if r["EventQuestChapterId"] == chapter), None)
        if row is None:
            return None
        name = self.chapter_name(row)
        family = "variation" if name.startswith("Variation:") else "tower" if name.startswith("Abyss Tower:") else "record"
        view = er.run_view(t, chapter) or {}
        facts = {"name": name, "family": family, "start": start, "end": end, "crossover": name in self.crossovers}
        link = view.get("link_row") or {}
        medal_id = 110000 + link["possession_id"] if link.get("possession_type") == MEDAL else None
        if medal_id:
            # The notices name a tiered medal by its family: "Happy Home Medals", not "Bronze Happy Home Medals".
            medal_name = re.sub(r"^(Bronze|Silver|Gold) ", "", self.text.get(f"consumable_item.name.{medal_id}", ""))
            facts["medal"] = {"id": medal_id, "name": medal_name, "plural": medal_name + "s", "icon": self.consumable_icon(medal_id)}
            shop = next((s for s in t["m_shop"] if s["ShopId"] == link.get("shop")), None)
            if shop:
                facts["exchange"] = self.text.get(f"shop.name.{shop['NameShopTextId']}", "")
                facts["exclusive"] = self.exclusive(t, shop)
        if family == "variation":
            facts["summons_name"] = name.removeprefix("Variation: ")
        facts["weapon_bonus"], facts["costume_bonus"] = self.bonuses(view, medal_id)
        return facts

    def exclusive(self, t, shop):
        cells = {c["ShopItemCellId"]: c for c in t["m_shop_item_cell"]}
        contents = {}
        for p in t["m_shop_item_content_possession"]:
            contents.setdefault(p["ShopItemId"], []).append(p)
        out = []
        for g in sorted((g for g in t["m_shop_item_cell_group"] if g["ShopItemCellGroupId"] == shop["ShopItemCellGroupId"]),
                        key=lambda g: g["SortOrder"]):
            cell = cells.get(g["ShopItemCellId"])
            items = contents.get(cell["ShopItemId"], []) if cell else []
            costume = next((p["PossessionId"] for p in items if p["PossessionType"] == COSTUME), None)
            if costume is None or costume not in self.m.idx("Costume", "CostumeId"):
                continue
            weapon = next((p["PossessionId"] for p in items if p["PossessionType"] == WEAPON), None)
            out.append({"costume": self.costume_panel(costume),
                        "weapon": self.weapon_panel(weapon) if weapon in self.m.idx("Weapon", "WeaponId") else None})
        return out

    def bonuses(self, view, medal_id):
        """Resonant weapons and costumes as (icon, name, additional medals by ascension 0-4, medal icons).
        A bonus can pay several medals (an event's Bronze, Silver and Gold): every one is shown."""
        rules = {}
        for rows in (view.get("bonuses") or {}).values():
            for kind, who, lower, payout in rows:
                for t_, item, n in payout:
                    if t_ != MEDAL or not n:
                        continue
                    by_lb = rules.setdefault((kind, who), {}).setdefault(item, {})
                    by_lb[lower] = max(by_lb.get(lower, 0), n)
        weapons, costumes, seen = [], [], set()
        for (kind, who), medals in sorted(rules.items(), key=lambda kv: kv[0][1]):
            values = max(([m.get(lb, 0) for lb in range(5)] for m in medals.values()), key=lambda v: v[-1])
            icons = tuple(i for i in (self.consumable_icon(110000 + item) for item in sorted(medals)) if i)
            if kind == "weapon" and who in self.m.idx("Weapon", "WeaponId"):
                name = self.weapon_name(who)  # a weapon and its evolution share a name and a row
                if ("w", name) not in seen:
                    seen.add(("w", name))
                    weapons.append((self.weapon_icon(who), name, values, icons))
            elif kind == "costume" and who in self.m.idx("Costume", "CostumeId"):
                character, costume = self.costume_names(who)
                if ("c", costume) not in seen:
                    seen.add(("c", costume))
                    costumes.append((self.costume_icon(who), f"{character} ({costume})", values, icons))
        # Rows with the same medals and bonus together (they share cells), smaller bonuses first, as officially.
        order = lambda rows: sorted(rows, key=lambda r: (len(r[3]), r[2]))
        return order(weapons), order(costumes)
