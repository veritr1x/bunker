"""Rebuilt event notices in the official notices' own markup and wording.

The facts come from the game data: the run's own (the weekly master published
during it, through event_runs.run_view: its exchange, medal, quests and quest
bonuses) and the final data's characters, weapons, skills and abilities (Deck
Builder's tables, which compute stats as the client does). Each template is the
one the official notices of the same kind use, with their most common wording:

  - Record events (a medal exchange), as 'Event Quest "Record: …" On Now'
  - Variation events (Event Summons), as 'Event Quest "Variation: …" On Now'
  - Abyss Towers, as 'Event Quest "Abyss Tower: …" On Now'
  - other home banners (campaigns, missions, the main story)

Crossover events are titled 'Crossover Quest "…"', as their official notices.
The greeting leaves out "This is a message from the management team.": the
pages are Bunker's. Panels show characters and
weapons at maximum level, as the official notices' Notes say; their stats match
the official panels' (check_event_notices.py).
"""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

PST = timezone(timedelta(hours=-8))  # the notices' "PST": always UTC-8
MONTHS = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
STAR = "img/c_c0591a6ed6321ab9.webp"
STATUS_ICONS = {"HP": "img/c_66c66da8e5aabb66.webp", "Attack": "img/c_8460b18d30f7ddf2.webp",
                "Defense": "img/c_51c5fa2d0e20a837.webp", "Agility": "img/c_57ebb88400193e02.webp"}
AWAKENING = "img/c_401bf3020eb3d8a7.webp"
CHANGE = "img/c_b1dc9844e1cd0748.webp"
ELEMENT_ICONS = {1: "img/c_b12402cccf574a37.webp", 2: "img/c_fb981984ea24b7a2.webp", 3: "img/c_f41a245db8594cae.webp",
                 5: "img/c_fe490143031299c8.webp", 6: "img/c_7f7a83c2cb5765ec.webp"}
WEAPON_TYPE_ICONS = {1: "img/c_b083068f901a8b57.webp", 2: "img/c_b8e3c5fb2b078a74.webp", 3: "img/c_f77459725f786faf.webp",
                     4: "img/c_dcb5da0da8bf844c.webp", 5: "img/c_644a6aafb7c446e8.webp", 6: "img/c_95b1263ee5358523.webp"}
GREETING = 'Hello, and thank you for playing NieR Re[in]carnation.<br /> <br /> '
CLOSING = '<section> <br> <p> Thank you very much for your ongoing support for NieR Re[in]carnation. </p> </section>'


def esc(text) -> str:
    return html.escape(str(text), quote=False)


def red(text) -> str:
    return f'<span class="text-red">{esc(text)}</span>'


def pst(ms) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=PST)


def day(ms) -> str:
    t = pst(ms)
    return f"{MONTHS[t.month - 1]} {t.day}"


def clock(ms) -> str:
    return pst(ms).strftime("%H:%M")


def duration(start, end) -> str:
    return f"{day(start)} {clock(start)} - {day(end)} {clock(end)} PST"


def kind_title(facts) -> str:
    return "Crossover Quest" if facts.get("crossover") else "Event Quest"


# -- sections -------------------------------------------------------------------

def header(facts, art) -> str:
    image = f'<div class="info-largeimage"> <img src="{art}" class="stand-in" alt=""> </div> ' if art else ""
    return (f'<section> {image}<p> {GREETING}The {kind_title(facts)} "{red(facts["name"])}" has begun as of '
            f'{day(facts["start"])} at {clock(facts["start"])} PST.<br /> </p> </section>')


def duration_section(facts, note) -> str:
    text = f' <p> {note} </p>' if note else ""
    return (f'<section> <h3>Duration</h3> <div class="holding-period"> {duration(facts["start"], facts["end"])} </div>'
            f'{text} </section>')


EXCHANGE_NOTE = "* The Exchange can be used until two days after the event duration ends. Please see the Exchange in game for details."
SUMMONS_NOTE = "* The Event Summons can be used until two days after the event period ends. Please see the Event Summons in game for details."
BONUS_LINE = ('Additionally, using certain characters, costumes, or weapons while playing the event quest will grant you a '
              '<span class="text-red">quest bonus</span> that will allow you to play more efficiently.<br>')


def how_to_play_record(facts) -> str:
    medal, exchange = facts.get("medal"), facts.get("exchange")
    if not medal or not exchange:
        return ""
    exclusive = facts.get("exclusive") or []
    reward = (f'for the event-exclusive character {red(exclusive[0]["costume"]["costume"])} as well as enhancements and other items'
              if len(exclusive) == 1 else "for various items")
    text = (f'Save up the {red(medal["plural"])} you receive for completing quests to trade in at the {red(exchange)} '
            f'{reward}.<br /> <br> The more difficult the quest, the more Medals you will earn as a reward.<br />')
    if facts.get("weapon_bonus") or facts.get("costume_bonus"):
        text += " " + BONUS_LINE
    return f'<section> <h3>How to Play Event Quests</h3> <p> {text} </p> </section>'


def how_to_play_variation(facts) -> str:
    tickets = facts.get("summons_name")
    if not tickets:
        return ""
    return ('<section> <h3>How to Play Event Quests</h3> <p>Clear the quests to get <span class="text-red">event-exclusive '
            f'memoirs</span>, {red(tickets + " Summon Tickets")}, and more.<br /> <br /> Collect {esc(tickets)} Summon Tickets '
            f'to use in the {red(tickets + " Summons")} and get various items <span class="text-red">like event-exclusive '
            'weapons or enhancement material</span>.<br /> <br /> The more difficult the quest, the easier it is to obtain '
            "better memoirs and the more Summon Tickets you'll receive.<br /> Additionally, using certain costumes or weapons "
            'will grant you a <span class="text-red">quest bonus</span> that will allow you to play the event quest more '
            'efficiently.<br /> </p> </section>')


def how_to_play_tower(facts) -> str:
    return ('<section> <h3>How to Play Event Quests</h3> <p> Abyss Tower is a high-difficulty event quest type that requires '
            'no repeats. Each tower has its own affinity, so put advantageous affinity weapons in your loadout to gain the '
            'upper hand.<br /> Since the enemies have high HP and use powerful attacks, use your allies\' recovery skills to '
            'your advantage in battle.<br /> <br /> You can earn a large amount of gems by completing the quests and quest '
            'missions. </p> </section>')


def stars(count) -> str:
    return "".join(f'<img src="{STAR}" class="star" />' for _ in range(count))


def skill_block(item, weapon=False) -> str:
    icon = f'<img src="{item["icon"]}" />' if item.get("icon") else ""
    if weapon and item.get("cooldown"):
        title = (f'<h6 class="flex"><span class="weapon_name">{esc(item["name"])}</span>'
                 f'<span class="recast_time">Cooldown: {item["cooldown"]} secs</span></h6>')
    else:
        title = f'<h6>{esc(item["name"])}</h6>'
    return (f'<div class="skill_profile-block"> <div class="skill_icon">{icon}</div> <div class="skill_detile"> '
            f'{title} <div class="description">{esc(item["description"])}</div> </div> </div>')


def status_list(values, keys) -> str:
    return "<ul> " + " ".join(f'<li><img class="status_icon" src="{STATUS_ICONS[k]}" />{k} '
                                f'<span class="status-value">{values[k]}</span></li>' for k in keys) + " </ul>"


def group(title, items, weapon=False) -> str:
    if not items:
        return ""
    return f'<div class="type-b"> <h5>{title}</h5> ' + " ".join(skill_block(i, weapon) for i in items) + " </div>"


def panel(p) -> str:
    """One exchange character and its weapon: the official pickup_content panel."""
    c, w = p["costume"], p["weapon"]
    character = (
        f'<div class="pickup_character-content on"> <div class="chara_image" style="background-image:url({c["portrait"]})"> '
        f'<div class="pickup_character-chara_image_area"> <div class="chara_profile"> <div class="chara_rarity">{stars(c["stars"])}</div> '
        f'<div class="item_name"><img class="weapon_icon" src="{WEAPON_TYPE_ICONS[c["weapon_type"]]}" />'
        f'<span class="character_name">{esc(c["character"])}</span>{esc(c["costume"])}<img src="{AWAKENING}" class="awakening_icon" /></div> </div> '
        f'<div class="blade_common-button-typeA switch_button"> <div class="morebtnparts_center"><img class="change_icon" src="{CHANGE}" /> '
        f'<div class="switch_button_label">Weapons</div> </div> </div> </div> <div class="pickup_character-status_area"> '
        f'<div class="type-a"> <h5>Status</h5> {status_list(c["status"], ("HP", "Attack", "Defense", "Agility"))} </div> '
        f'{group("Character Skill", [c["skill"]] if c.get("skill") else [])} {group("Character Abilities", c["abilities"])} </div> </div>')
    weapon = ""
    if w:
        weapon = (
            f'<div class="pickup_weapon-content off"> <div class="chara_image" style="background-image:url({w["portrait"]})"> '
            f'<div class="pickup_character-chara_image_area"> <div class="chara_profile"> <div class="chara_rarity">{stars(w["stars"])}</div> '
            f'<div class="item_name"><img class="weapon_icon" src="{ELEMENT_ICONS[w["element"]]}" />'
            f'<img class="weapon_icon" src="{WEAPON_TYPE_ICONS[w["weapon_type"]]}" />{esc(w["name"])}</div> </div> '
            f'<div class="blade_common-button-typeA switch_button"> <div class="morebtnparts_center"><img class="change_icon" src="{CHANGE}" /> '
            f'<div class="switch_button_label">Character</div> </div> </div> </div> <div class="pickup_character-status_area"> '
            f'<div class="type-a"> <h5>Status</h5> {status_list(w["status"], ("HP", "Attack", "Defense"))} </div> '
            f'{group("Weapon Skills", w["skills"], weapon=True)} {group("Weapon Abilities", w["abilities"])} '
            f'{group("Barrier Skills", w["barriers"])} </div> </div>')
    return f'<section> <div class="pickup_content"> {character} {weapon} </div> </section>'


def exchange_section(facts) -> str:
    panels = facts.get("exclusive") or []
    if not panels:
        return ""
    out = f'<section> <h3>Characters Available from the {esc(facts["exchange"])}</h3> </section> '
    out += " ".join(panel(p) for p in panels)
    for p in panels:
        if p["weapon"]:
            out += (f' <section> <p> Note: Acquire {esc(p["costume"]["character"])} ({esc(p["costume"]["costume"])}) by trading for '
                    f'the weapon {red(p["weapon"]["name"])} at the {esc(facts["exchange"])}. </p> </section>')
    return out


ASCENSIONS = ("None", "1", "2", "3", "4")


def bonus_table(rows, head) -> str:
    """Rows of (icon, name, [five values], medal icons): a run of rows with the same medals and values shares
    those cells (rowSpan), as the official tables do."""
    body = []
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1][2:] == rows[i][2:]:
            j += 1
        span = j - i + 1
        attr = f' rowSpan="{span}"' if span > 1 else ""
        coins = "<br /> ".join(f'<img class="coin_icon" src="{c}">' for c in rows[i][3])
        cells = "".join(f'<td{attr} style="text-align:center">+{v}</td> ' for v in rows[i][2])
        for k in range(i, j + 1):
            icon, name = rows[k][0], rows[k][1]
            image = f'<img src="{icon}" class="weapon_icon">' if icon else ""
            extra = f'<td{attr} style="text-align:center"> {coins} </td> {cells}' if k == i else ""
            body.append(f"<tr> <th>{image}{esc(name)}</th> {extra}</tr>")
        i = j + 1
    asc = " ".join(f'<th style="text-align:center">{a}</th>' for a in ASCENSIONS)
    return (f'<div class="information_table weapon_table"> <table> <thead> <tr> <th rowSpan="2" style="width:24%">{head}</th> '
            f'<th rowSpan="2" style="width:13%; text-align:center;">Medals</th> <th colspan="5" style="text-align:center">Ascension Count</th> '
            f'</tr> <tr> {asc} </tr> </thead> <tbody> {" ".join(body)} </tbody> </table> </div>')


def weapon_bonus_section(facts) -> str:
    rows = facts.get("weapon_bonus") or []
    if not rows:
        return ""
    medal = facts["medal"]
    return (f'<section> <h3>Quest Bonus: Resonant Weapon</h3> <p> Using certain weapons in "{esc(facts["name"])}" will grant the '
            f'<span class="text-red">quest bonus for resonant weapons</span>.<br> This bonus <span class="text-red">increases the amount of '
            f'{esc(medal["plural"])} dropped</span>, depending on the weapon.<br> Ascending these weapons <span class="text-red">further '
            f'increases the bonus effect.</span><br> </p> <h4> Quest Bonus: Resonant Weapons Effect List </h4> '
            f'{bonus_table(rows, "Weapon")} <p> * Equipping resonant weapons will grant you this bonus regardless of '
            'whether they are equipped as primary or secondary weapons.<br> * Resonant weapon drop increases will stack if multiple '
            'resonant weapons are equipped. </p> </section>')


def costume_bonus_section(facts) -> str:
    rows = facts.get("costume_bonus") or []
    if not rows:
        return ""
    medal = facts["medal"]
    return (f'<section> <h3>Quest Bonus: Resonant Costume</h3> <p> Using certain costumes in "{esc(facts["name"])}" will grant the '
            f'<span class="text-red">quest bonus for resonant costumes</span>.<br> This bonus <span class="text-red">increases the amount of '
            f'{esc(medal["plural"])} dropped</span>, depending on the costume.<br> Ascending these costumes <span class="text-red">further '
            f'increases the bonus effect.</span><br> </p> {bonus_table(rows, "Costume")} </section>')


NOTES_RECORD = (
    "Event duration and content are subject to change without notice.",
    "Illustrations shown in notices, etc. may differ from those in-game.",
    "The rarity, stats, skills, and abilities of characters and weapons displayed in notices, in the summons screen, and on the "
    "official Twitter account are shown at maximum levels.",
    "You cannot have more than one character with the same name in the same deck.",
)
NOTES_EXCHANGE = (
    'Once the exchange period has passed, <span class="text-red">you will be unable to exchange medals</span>.',
    'Event-specific medals can only be used during the exchange period and <span class="text-red">cannot be carried over to the next event.</span>',
)
NOTES_SUMMONS = (
    "After the Event Summons ends, you will no longer be able to use Event Summon Tickets and they will disappear from your item list.",
    "Event-limited summon tickets will expire and cannot be carried over to the next event.",
    "The event's limited weapons and limited memoirs may reappear in the future.",
)


def notes(facts, extra=()) -> str:
    items = [esc(n) if "<" not in n else n for n in NOTES_RECORD]
    for p in facts.get("exclusive") or []:
        weapon = f' and {esc(p["weapon"]["name"])}' if p["weapon"] else ""
        items.append(f'<span class="text-red">{esc(p["costume"]["character"])} ({esc(p["costume"]["costume"])}){weapon} may reappear in the future.</span>')
    items += list(extra)
    items.append("This event may reappear in the future.")
    lis = " ".join(f"<li> {i} </li>" for i in items)
    return f'<section> <h3> Notes </h3> <div class="attention_content"> <ul> {lis} </ul> </div> </section>'


def record_body(facts, art) -> str:
    parts = [header(facts, art), duration_section(facts, EXCHANGE_NOTE if facts.get("exchange") else None),
             how_to_play_record(facts), exchange_section(facts), weapon_bonus_section(facts), costume_bonus_section(facts),
             notes(facts, NOTES_EXCHANGE if facts.get("exchange") else ()), CLOSING]
    return " ".join(p for p in parts if p)


def variation_body(facts, art) -> str:
    parts = [header(facts, art), duration_section(facts, SUMMONS_NOTE), how_to_play_variation(facts),
             weapon_bonus_section(facts), costume_bonus_section(facts), notes(facts, NOTES_SUMMONS), CLOSING]
    return " ".join(p for p in parts if p)


def tower_body(facts, art) -> str:
    parts = [header(facts, art), duration_section(facts, None), how_to_play_tower(facts), notes(facts), CLOSING]
    return " ".join(p for p in parts if p)


def other_body(label, start, end, art) -> str:
    image = f'<div class="info-largeimage"> <img src="{art}" class="stand-in" alt=""> </div> ' if art else ""
    return " ".join([
        f'<section> {image}<p> {GREETING}The {esc(label)} has begun as of {day(start)} at {clock(start)} PST.<br /> </p> </section>',
        f'<section> <h3>Duration</h3> <div class="holding-period"> {duration(start, end)} </div> </section>',
        '<section> <h3> Notes </h3> <div class="attention_content"> <ul> <li> Event duration and content are subject to change '
        'without notice. </li> <li> Illustrations shown in notices, etc. may differ from those in-game. </li> </ul> </div> </section>',
        CLOSING])


def coming_body(soon, start, end, art) -> str:
    """An event announced before it opens: 'Event Quest "…" Coming Soon', as officially worded."""
    image = f'<div class="info-largeimage"> <img src="{art}" class="stand-in" alt=""> </div> ' if art else ""
    return " ".join([
        f'<section> {image}<p> {GREETING}The event quest "{red(soon["name"])}" will be available starting '
        f'{day(soon["start"])} at {clock(soon["start"])} PST.<br /> </p> </section>',
        '<section> <h3> Notes </h3> <div class="attention_content"> <ul> <li> Event duration and content are subject to change '
        'without notice. </li> <li> Illustrations shown in notices, etc. may differ from those in-game. </li> </ul> </div> </section>',
        CLOSING])


def title(facts) -> str:
    return f'{kind_title(facts)} "{facts["name"]}" On Now'


def body(facts, art) -> str:
    family = facts["family"]
    return {"record": record_body, "variation": variation_body, "tower": tower_body}[family](facts, art)
