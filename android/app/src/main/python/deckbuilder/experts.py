"""What experienced Arena players picked (data/experts.json: ids and weights
reduced from the nierrein.guide tier lists and loadouts and decks read from
Arena videos; scripts/build_deckbuilder_experts.py).

Experts pick the lineup; the data equips it, and may overrule an expert
choice only with a stated reason (deckbuilder.equip, deckbuilder.generate).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("deckbuilder.experts")
DATA = Path(__file__).resolve().parent / "data" / "experts.json"


@dataclass(frozen=True)
class ExpertLineup:
    name: str
    costumes: tuple          # left, middle, right
    loadout: dict | None     # costume id (str) -> {weapons, memoir_set, companion, debris}
    source: str
    role: str = "attack"
    weight: float = 0.0      # share of the meta pool


class Experts:
    def __init__(self, costumes: dict, lineups: list):
        self._costumes = costumes
        self._lineups = lineups

    @classmethod
    def load(cls, tables, path: Path | None = None) -> "Experts":
        data = json.loads(Path(path or DATA).read_text())
        known = tables.idx("Costume", "CostumeId")
        costumes = {}
        for k, v in data.get("costumes", {}).items():
            if int(k) not in known:
                log.warning("expert costume %s is not in the game data; skipped", k)
                continue
            costumes[int(k)] = v
        lineups = []
        for l in data.get("lineups", []):
            missing = [c for c in l["costumes"] if c not in known]
            if missing:
                log.warning("expert lineup %r names %s, not in the game data; skipped", l["name"], missing)
                continue
            lineups.append(ExpertLineup(l["name"], tuple(l["costumes"]), l.get("loadout") or None, l.get("source", ""), l.get("role", "attack")))
        return cls(costumes, lineups)

    def weight(self, costume_id: int) -> float:
        return float(self._costumes.get(costume_id, {}).get("weight", 0.0))

    def roles(self, costume_id: int) -> set:
        return set(self._costumes.get(costume_id, {}).get("roles", []))

    def costumes(self) -> list:
        """Expert picks, best first."""
        return sorted(self._costumes, key=lambda c: (-self.weight(c), c))

    def lineups(self) -> list:
        return list(self._lineups)

    def meta_pool(self) -> list:
        """The lineups General best is measured against, weighted (summing to 1)
        by how strong their costumes are rated; each lineup appears once."""
        seen, pool = set(), []
        for l in self._lineups:
            if l.costumes in seen:
                continue
            seen.add(l.costumes)
            pool.append(l)
        raw = [sum(self.weight(c) for c in l.costumes) or 0.1 for l in pool]
        total = sum(raw)
        return [ExpertLineup(l.name, l.costumes, l.loadout, l.source, l.role, w / total) for l, w in zip(pool, raw)]
