"""All maxed results baked at build time (scripts/bake_deckbuilder.py): every three-costume deck of every playable
costume, each costume in the gear its own search chose, simulated against the general meta as Attack and as Defense.

Shipped here (data/baked): meta.json (the costumes, each one's baked loadout and element, the fighter fingerprint)
and two ranked lists, attack.bin.z and defense.bin.z (zlib), of 18-byte records:

    left, middle, right (indices into meta["costumes"], slot order) uint16 x3
    attack win, attack margin, defense win, defense margin (x10000)  uint16 int16 uint16 int16
    Force                                                            uint32

The results hold for a phone whose fighters are those the bake simulated: the fingerprint (fingerprint()) covers
every costume's fighter in its baked loadout, its Force, and the meta decks' fighters. Deck Builder compares it after
preparing its stage and uses its own search when it differs (a mod that changes battle data, another game version).
"""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import NamedTuple

DATA = Path(__file__).parent / "data" / "baked"
REC = struct.Struct("<HHHHhHhI")
FREC = struct.Struct("<HHHI")           # the Force list: left, middle, right, Force (each costume in its Force loadout)
SCALE = 10000
KEEP = 300000           # decks kept per list (the bake ranks them all; the rest win nothing against the meta)


class Record(NamedTuple):
    lineup: tuple           # costume ids, left to right
    attack_win: float
    attack_margin: float
    defense_win: float
    defense_margin: float
    force: int


def _key(deck_for):
    if deck_for == "defense":
        return lambda r: (-r.defense_win, -r.defense_margin, -r.force, r.lineup)
    return lambda r: (-r.attack_win, -r.attack_margin, -r.force, r.lineup)


def write(path, loadouts: dict, fingerprint: str, rows, keep: int = KEEP, extra: dict | None = None,
          force_rows=None, force_loadouts: dict | None = None):
    """Write the baked data: loadouts {costume id: loadout} (each with its "element"), rows of Record; and the Force
    list: force_rows of (lineup, Force) with each costume in force_loadouts (its loadout with the most Force)."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    costumes = sorted(loadouts)
    index = {c: i for i, c in enumerate(costumes)}
    rows = list(rows)
    lists = {}
    for deck_for in ("attack", "defense"):
        top = sorted(rows, key=_key(deck_for))[:keep]
        blob = b"".join(REC.pack(*(index[c] for c in r.lineup), round(r.attack_win * SCALE), round(r.attack_margin * SCALE),
                                 round(r.defense_win * SCALE), round(r.defense_margin * SCALE), r.force) for r in top)
        (path / f"{deck_for}.bin.z").write_bytes(zlib.compress(blob, 9))
        lists[deck_for] = len(top)
    if force_rows is not None:
        top = sorted(force_rows, key=lambda r: (-r[1], tuple(r[0])))[:keep]
        (path / "force.bin.z").write_bytes(zlib.compress(b"".join(FREC.pack(*(index[c] for c in l), f) for l, f in top), 9))
        lists["force"] = len(top)
    meta = dict(extra or {}, costumes=costumes, loadouts={str(c): loadouts[c] for c in costumes},
                fingerprint=fingerprint, decks=lists)
    if force_loadouts is not None:
        meta["force_loadouts"] = {str(c): force_loadouts[c] for c in costumes if c in force_loadouts}
    (path / "meta.json").write_text(json.dumps(meta, sort_keys=True))
    return path


class Baked:
    def __init__(self, path: Path, meta: dict):
        self.path, self.meta = path, meta
        self.costumes = meta["costumes"]
        self.loadouts = {int(k): v for k, v in meta["loadouts"].items()}
        self.force_loadouts = {int(k): v for k, v in (meta.get("force_loadouts") or {}).items()}
        self.fingerprint = meta["fingerprint"]
        self._records = {}

    @classmethod
    def load(cls, path=DATA):
        path = Path(path)
        if not (path / "meta.json").exists():
            return None
        return cls(path, json.loads((path / "meta.json").read_text()))

    def element(self, costume_id) -> str | None:
        lo = self.loadouts.get(costume_id)
        return lo["element"] if lo else None

    def has_force(self) -> bool:
        return bool(self.force_loadouts) and (self.path / "force.bin.z").exists()

    def loadouts_for(self, sort: str) -> dict:
        """The loadouts a list's decks are in: the Force list's for sort "force", else the fights'."""
        return self.force_loadouts if sort == "force" and self.force_loadouts else self.loadouts

    def records(self, deck_for: str) -> list:
        """The decks in rank order for "attack", "defense" or "force" (the Force list; win fields 0) (read once)."""
        if deck_for == "force" and "force" not in self._records:
            blob = zlib.decompress((self.path / "force.bin.z").read_bytes())
            cs = self.costumes
            self._records["force"] = [Record((cs[a], cs[b], cs[c]), 0.0, 0.0, 0.0, 0.0, f) for a, b, c, f in FREC.iter_unpack(blob)]
        if deck_for not in self._records:
            blob = zlib.decompress((self.path / f"{'defense' if deck_for == 'defense' else 'attack'}.bin.z").read_bytes())
            cs = self.costumes
            self._records[deck_for] = [Record((cs[a], cs[b], cs[c]), aw / SCALE, am / SCALE, dw / SCALE, dm / SCALE, f)
                                       for a, b, c, aw, am, dw, dm, f in REC.iter_unpack(blob)]
        return self._records[deck_for]


def fingerprint(cache, keys: dict, meta_sides) -> str:
    """A hash of what the baked results depend on: every costume's fighter in each of its baked loadouts (keys:
    ("fight" or "force", costume id) -> its key in the fighters.FighterCache) and its Force, and the meta decks'
    fighters (battle sides). Equal on two machines, their fights and Force are equal."""
    h = hashlib.sha256()
    for k in sorted(keys):
        h.update(json.dumps([list(k), cache._templates[keys[k]], cache.force((keys[k],))], sort_keys=True, default=_plain).encode())
    for side in meta_sides:
        h.update(json.dumps(sorted(side.items()), sort_keys=True, default=_plain).encode())
    return h.hexdigest()


def _plain(x):
    if isinstance(x, (set, frozenset)):
        return sorted(x)
    if isinstance(x, tuple):
        return list(x)
    return str(x)


def loadout_spec(lo: dict, stage, tables):
    """A baked loadout as a model.CharacterSpec of the stage's pieces (the stage holds every baked piece)."""
    from deckbuilder import equip, model
    P = lambda kind, col, i: model.PieceRef(kind, stage.pick(kind, **{col: i}), "stage") if i else None
    memoirs = equip._memoirs(equip._Picker(stage, stage, tables, equip.Mode("best")), lo["memoir_set"], lo["role"], tables) \
        if lo.get("memoir_set") else []
    return model.CharacterSpec(P("costume", "costume_id", lo["costume_id"]), P("weapon", "weapon_id", lo["main_weapon"]),
                               [P("weapon", "weapon_id", w) for w in lo["subs"]], P("companion", "companion_id", lo["companion"]),
                               memoirs, P("debris", "thought_id", lo["debris"]))


def deck_loadouts(lineup, loadouts: dict, order) -> list:
    """The loadouts of a deck, left to right. The game holds one of each debris: one an earlier character already has
    is replaced on the later one by the first of order(its element) that no character of the deck has or picked
    (None when none is left). The bake
    simulates the deck so, and Deck Builder writes it so."""
    taken, out = set(), []
    chosen = [loadouts[c].get("debris") for c in lineup]
    for i, c in enumerate(lineup):
        lo = loadouts[c]
        d = lo.get("debris")
        if d is not None and d in taken:
            keep = set(chosen[i + 1:])                 # a substitute does not take a later character's own pick
            d = next((x for x in order(lo.get("element")) if x not in taken and x not in keep), None)
            lo = dict(lo, debris=d)
        if d is not None:
            taken.add(d)
        out.append(lo)
    return out


def debris_order(loadouts: dict):
    """order() for deck_loadouts: the ranking data's debris for an element (its kinds in turn), kept to those some
    baked loadout uses (so a stage holding the baked pieces holds them)."""
    from deckbuilder import equip
    used = {lo["debris"] for lo in loadouts.values() if lo.get("debris")}
    cache = {}

    def order(element):
        if element not in cache:
            seen, out = set(), []
            for kind in ("gauge", "weapon_stats", "other"):
                for t in equip.debris_candidates(element, kind):
                    if t in used and t not in seen:
                        seen.add(t); out.append(t)
            cache[element] = out
        return cache[element]
    return order
