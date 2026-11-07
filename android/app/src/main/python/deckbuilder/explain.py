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

from deckbuilder import equip
from deckbuilder.generate import EFFECT_LABEL, EFFECTS, costume_flags

SHORT_MAX = 110
SLOTS = ("Left", "Middle", "Right")
BANNED_CLAIMS = [
    re.compile(r"Compromis\w* (removes|cancels|ends|strips|dispels|clears)", re.I),
    re.compile(r"blocks? (her|his|their|the) first Dauntless", re.I),
    re.compile(r"Crush (can't|cannot|can not) be cleansed|Crush is not cleansable", re.I),
    re.compile(r"removes? (her|his|their|the|an?) (active )?Dauntless", re.I),
]
SHORT = {
    "compromise_counter": "Land Compromise before their Dauntless or revive goes up, then finish {target}.",
    "dauntless": "Dauntless keeps your team above 1 HP while it deals its damage.",
    "tank": "A provoke tank draws their hits while the others deal damage.",
    "stall": "Revives and damage cuts outlast their burst; then it finishes them.",
    "mono": "All {element}: every {element} damage boost on the team stacks.",
    "burst": "Skills ready at the start hit first and break their team early.",
}


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
        return "them"
    chars = [c for c in against.characters() if c]
    daunt = [c for c in chars if "dauntless" in costume_flags(c.costume.id, tables)]
    pick = (daunt or chars[1:2] or chars)[:1]
    return tables.character_name(pick[0].costume.id) if pick else "them"


def _fit(text):
    return text if len(text) <= SHORT_MAX else text[:SHORT_MAX - 1].rsplit(" ", 1)[0] + "…"


def short_reason(strategy, elements, tags, against, tables) -> str:
    """The card's reason: two lines at most, no fight simulated."""
    short = SHORT[strategy].format(target=_target(against, tables), element=elements[0])
    adv = [t for t in tags if "×1.2" in t]
    if adv and len(short) + len(adv[0]) + 3 <= SHORT_MAX:
        short = f"{short[:-1]} ({adv[0]})."
    return _fit(short)


def explain(result, against, tables, experts=None) -> Explanation:
    from deckbuilder import sim
    title = result.name
    short = short_reason(result.strategy, result.elements, result.tags, against, tables)
    if against is not None:
        f = sim.simulate(result.deck, against, tables, seed=0)
        verb = "wins" if f["win"] == "A" else "loses"
        how = f"in {round(f['t'])} s" if f["how"] == "KO" else f"on time ({round(f['t'])} s, on remaining HP)"
        parts = [f"In a simulated fight it {verb} {how}; across seeds it wins {result.win_rate:.0%}."]
        if f["first_kill"]:
            k = f["first_kill"]
            side = "Your" if k["side"] == "A" else "Their"
            parts.append(f"{side} first kill: {tables.character_name(k['victim'])} at {k['t']:.0f} s.")
        for c in f["compromise"][:1]:
            when = "before" if c["before_target_buff"] else "after"
            parts.append(f"Compromise lands on {tables.character_name(c['target'])} at {c['t']:.1f} s, {when} their first "
                         f"beneficial status; it stops new ones from going on and leaves any already on.")
        why_long = " ".join(parts)
    else:
        why_long = f"Against the meta decks it wins {result.win_rate:.0%} of simulated fights."
    per_char = []
    for i, c in enumerate(result.lineup):
        roles = sorted(experts.roles(c) - {"video"}) if experts else []
        expert = "expert pick" if experts and experts.weight(c) > 0 else "data pick"
        roles = [r.replace("_", " ") for r in roles]
        brings = [EFFECT_LABEL[e] for e in EFFECTS if e in costume_flags(c, tables)]
        per_char.append(f"{SLOTS[i]} · {tables.costume_name(c)} ({expert}{', ' + ', '.join(roles) if roles else ''})"
                        + (f". Brings: {', '.join(brings)}." if brings else "."))
    overrides = []
    for o in result.equipped.overrides:
        wr = o.evidence.get("win_rate", {})
        overrides.append(f"{o.reason} Evidence: wins {wr.get('data', 0):.0%} with the data's choice, "
                         f"{wr.get('expert', 0):.0%} with the expert's.")
    return Explanation(title, short, why_long, per_char, dict(result.equipped.reasons), overrides)
