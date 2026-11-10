"""Why a deck: a strategy title, a two-line reason for the card, a longer plan
from one simulated fight, a line per character and per piece, and each data
override with its evidence.

Every text must agree with the mechanics (design §6): Compromised blocks *new*
beneficial statuses only and never removes one already on; the defender's
start-of-battle skills resolve first on Auto; Crush can be cleansed.
BANNED_CLAIMS lists the known-wrong claims; tests check nothing matches them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import bunker_text
from deckbuilder import equip
from deckbuilder.generate import EFFECT_LABEL, EFFECTS, Advantage, costume_flags
from deckbuilder.text import Later

SHORT_MAX = 110
BANNED_CLAIMS = [
    re.compile(r"Compromis\w* (removes|cancels|ends|strips|dispels|clears)", re.I),
    re.compile(r"blocks? (her|his|their|the) first Dauntless", re.I),
    re.compile(r"Crush (can't|cannot|can not) be cleansed|Crush is not cleansable", re.I),
    re.compile(r"removes? (her|his|their|the|an?) (active )?Dauntless", re.I),
]


def _short(strategy, target, element):
    """A strategy's reason, in the chosen language (one whole sentence per strategy)."""
    t = bunker_text.t
    return {
        "compromise_counter": lambda: (t("pods.decks.reason.compromise_counter", target=target) if target
                                       else t("pods.decks.reason.compromise_counter_any")),
        "dauntless": lambda: t("pods.decks.reason.dauntless"),
        "tank": lambda: t("pods.decks.reason.tank"),
        "stall": lambda: t("pods.decks.reason.stall"),
        "mono": lambda: t("pods.decks.reason.mono", element=t(f"pods.decks.element_in_text.{element}", default=element)),
        "burst": lambda: t("pods.decks.reason.burst"),
    }[strategy]()


def _slot(i):
    t = bunker_text.t
    return (t("pods.decks.slot.left"), t("pods.decks.slot.middle"), t("pods.decks.slot.right"))[i]


def _percent(x):
    return f"{x:.0%}"


@dataclass
class Explanation:
    title: str
    why_short: str
    why_long: str
    per_character: list
    per_piece: dict          # (costume_id, slot) -> text
    overrides: list


def _target(against, tables):
    """The opponent's Dauntless (else strongest) character, by name."""
    if against is None:
        return None
    chars = [c for c in against.characters() if c]
    daunt = [c for c in chars if "dauntless" in costume_flags(c.costume.id, tables)]
    pick = (daunt or chars[1:2] or chars)[:1]
    return tables.character_name(pick[0].costume.id) if pick else None


def _fit(text):
    return text if len(text) <= SHORT_MAX else text[:SHORT_MAX - 1].rsplit(" ", 1)[0] + "…"


def short_reason(strategy, elements, tags, against, tables) -> Later:
    """The card's reason: two lines at most, no fight simulated; made when shown (deckbuilder.text)."""
    name = _target(against, tables)
    adv = [t for t in tags if isinstance(t, Advantage)]

    def make():
        short = _short(strategy, name, elements[0])
        if adv and len(short) + len(adv[0]) + 3 <= SHORT_MAX:
            short = bunker_text.t("pods.decks.reason.with_note", reason=short.removesuffix("."), note=str(adv[0]))
        return _fit(short)
    return Later(make)


def explain(result, against, tables, experts=None) -> Explanation:
    from deckbuilder import sim
    t = bunker_text.t   # explain runs for one request: its words are made now, in the chosen language
    title = result.name
    short = str(short_reason(result.strategy, result.elements, result.tags, against, tables))
    rate = _percent(result.win_rate)
    if against is not None:
        f = sim.simulate(result.deck, against, tables, seed=0)
        s = round(f["t"])
        if f["win"] == "A":
            fight = t("pods.decks.long.wins_ko", s=s, rate=rate) if f["how"] == "KO" else t("pods.decks.long.wins_time", s=s, rate=rate)
        else:
            fight = t("pods.decks.long.loses_ko", s=s, rate=rate) if f["how"] == "KO" else t("pods.decks.long.loses_time", s=s, rate=rate)
        parts = [fight]
        if f["first_kill"]:
            k = f["first_kill"]
            name, at = tables.character_name(k["victim"]), f"{k['t']:.0f}"
            parts.append(t("pods.decks.long.your_first_kill", name=name, s=at) if k["side"] == "A"
                         else t("pods.decks.long.their_first_kill", name=name, s=at))
        for c in f["compromise"][:1]:
            name, at = tables.character_name(c["target"]), f"{c['t']:.1f}"
            parts.append(t("pods.decks.long.compromise_before", name=name, s=at) if c["before_target_buff"]
                         else t("pods.decks.long.compromise_after", name=name, s=at))
        why_long = " ".join(parts)
    else:
        why_long = t("pods.decks.long.meta", rate=rate)
    per_char = []
    for i, c in enumerate(result.lineup):
        roles = sorted(experts.roles(c) - {"video"}) if experts else []
        roles = ", ".join(r.replace("_", " ") for r in roles)       # the experts' own role names (data)
        slot, costume = _slot(i), tables.costume_name(c)
        if experts and experts.weight(c) > 0:
            line = (t("pods.decks.line.expert_roles", slot=slot, costume=costume, roles=roles) if roles
                    else t("pods.decks.line.expert", slot=slot, costume=costume))
        else:
            line = (t("pods.decks.line.data_roles", slot=slot, costume=costume, roles=roles) if roles
                    else t("pods.decks.line.data", slot=slot, costume=costume))
        brings = ", ".join(str(EFFECT_LABEL[e]) for e in EFFECTS if e in costume_flags(c, tables))
        per_char.append(t("pods.decks.line.brings", line=line, effects=brings) if brings else t("pods.decks.line.end", line=line))
    overrides = []
    for o in result.equipped.overrides:
        wr = o.evidence.get("win_rate", {})
        data, expert = _percent(wr.get("data", 0)), _percent(wr.get("expert", 0))
        overrides.append(t("pods.decks.override_evidence", reason=str(o.reason), data=data, expert=expert))
    pieces = {k: str(v) for k, v in result.equipped.reasons.items()}
    return Explanation(title, short, why_long, per_char, pieces, overrides)
