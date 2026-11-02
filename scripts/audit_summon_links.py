"""Audit notice links using original master JSON, Archive English text and catalog sources.

This reconstructs non-chapter catalog membership from the checked-in loaders; it
does not inspect the running phone or apply mappings. Event matches require both
the event title and its exact original start time. No fuzzy rerun substitution.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DAY = 86_400_000
FOREVER = 1717200000000  # 2024-06-01: later master dates are placeholders.
KINDS = {1: "Record", 2: "Variation", 3: "Remnant", 4: "Daily", 5: "Guerrilla",
         6: "Character Quest", 7: "Character Quest", 8: "Hidden", 9: "Special",
         10: "Abyss Tower", 11: "Chambers of Dusk", 12: "Fate Board"}
# Reviewed against notices 1244/1310, which share the respective native start
# times. These are specific names, not a general initial-letter expansion rule.
ALIASES = {300: ("Variation: A. Dynast", "Variation: Aurora Dynast"),
           301: ("Variation: B. Resentful Witch", "Variation: Blazing Resentful Witch")}


def normalized(value):
    for damaged in ("â€\x9d", "â€œ", "â€˜", "â€™"):
        value = value.replace(damaged, " ")
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", html.unescape(value)).casefold()).strip()


def matches_title(title, notice_title):
    a, b = normalized(title), normalized(notice_title)
    return bool(a and a != "-" and f" {a} " in f" {b} ")


def exact_event_notices(title, start, notices):
    return [n for n in notices if n["publish"] == start
            and normalized(n["title"]).endswith(" on now")
            and matches_title(title, n["title"])]


def go_map(name, source, boolean=False):
    match = re.search(r"var " + name + r" = map\[[^\]]+\][^{]+\{(.*?)\}", source, re.S)
    if not match:
        raise ValueError("Loader map not found: " + name)
    values = re.findall(r"(\d+)\s*:\s*(true|false|\d+)", match[1])
    return {int(k): (v == "true" if boolean else int(v)) for k, v in values}


def add_rules(catalog, rules):
    """The Go loader checks only the base catalog, before adding any new rows."""
    base_ids = set(catalog)
    for n in rules:
        ident, pair = n["id"], n.get("pair", 0)
        if ident in base_ids or not n["steps"]:
            continue
        if pair not in base_ids and not n.get("start"):
            continue
        if ident in catalog:
            raise ValueError("Duplicate added summon: " + str(ident))
        catalog[ident] = {
            "gacha_id": ident, "source": "added_rule", "asset": n["asset"],
            "start": catalog[pair]["start"] if pair in base_ids else n["start"],
            "explicit_notice_id": n.get("notice", 0),
        }


def build_catalog(master, rules, boxes, patch, special_source):
    added_go = "\n".join(line[1:] for line in patch.splitlines()
                         if line.startswith("+") and not line.startswith("+++"))
    medals = master("GachaMedal")
    by_gacha = {r["ShopTransitionGachaId"]: r for r in medals}
    by_item = {r["ConsumableItemId"]: r for r in medals}
    for gacha, owner in go_map("sharedMedalGachas", added_go).items():
        if owner in by_gacha:
            by_gacha.setdefault(gacha, by_gacha[owner])
    for gacha, item in go_map("medalItemGachas", added_go).items():
        if item in by_item:
            by_gacha.setdefault(gacha, by_item[item])
    parked = go_map("parkedReruns", added_go)
    special = {int(k) for k in re.findall(r"^\s*(\d+):", special_source, re.M)}
    catalog = {}
    for b in sorted(master("MomBanner"), key=lambda r: r["StartDatetime"]):
        if b["DestinationDomainType"] != 1:
            continue
        gacha, asset = b["DestinationDomainId"], b["BannerAssetName"]
        if gacha in catalog:
            continue
        if asset.startswith("step_up_"):
            if gacha not in by_gacha:
                continue
        elif gacha not in by_gacha and gacha not in special:
            continue
        start = b["StartDatetime"]
        if gacha in parked and gacha in by_gacha:
            start = by_gacha[gacha]["AutoConvertDatetime"] - parked[gacha]
        catalog[gacha] = {"gacha_id": gacha, "source": "native_banner", "asset": asset,
                          "start": start, "explicit_notice_id": 0}
    items = {r["ShopItemId"]: r for r in master("ShopItem")}
    cells = {r["ShopItemCellId"]: r["ShopItemId"] for r in master("ShopItemCell")}
    groups = defaultdict(set)
    for r in master("ShopItemCellGroup"):
        item = items.get(cells.get(r["ShopItemCellId"]), {})
        groups[r["ShopItemCellGroupId"]].add(item.get("PriceId", 0))
    opens = {}
    for shop in master("Shop"):
        for price in groups[shop["ShopItemCellGroupId"]]:
            opens[price] = min(opens.get(price, shop["StartDatetime"]), shop["StartDatetime"])
    skipped = go_map("bannerlessSkipped", added_go, boolean=True)
    for m in medals:
        gacha, start = m["ShopTransitionGachaId"], opens.get(m["ConsumableItemId"])
        if (not gacha or gacha in catalog or skipped.get(gacha) or start is None
                or not m["AutoConvertDatetime"] or m["AutoConvertDatetime"] - 2 * DAY <= start):
            continue
        catalog[gacha] = {"gacha_id": gacha, "source": "medal_exchange",
                          "asset": ("step_up_" if gacha >= 500000 else "limited_") + str(gacha),
                          "start": start, "explicit_notice_id": 0}
    add_rules(catalog, rules)
    chapters = {r["EventQuestChapterId"]: r for r in master("EventQuestChapter")}
    for box in boxes:
        gacha = box["base"]
        if gacha in catalog or box["chapter"] not in chapters or not box["levels"] or not box["tickets"]:
            continue
        catalog[gacha] = {"gacha_id": gacha, "source": "event_box", "asset": box["assets"][0],
                          "start": chapters[box["chapter"]]["StartDatetime"],
                          "event_id": box["chapter"], "explicit_notice_id": 0}
    return catalog


def audit_events(chapters, texts, notices):
    rows = []
    for c in chapters:
        ident = c["EventQuestChapterId"]
        title = texts.get("quest.event.chapter_title." + str(c["NameEventQuestTextId"]), "")
        if not title or title == "-":
            title = texts.get("quest.event.chapter_title." + str(ident), "")
        alias = ALIASES.get(ident)
        alias_used = bool(alias and normalized(title) == normalized(alias[0]))
        matching_title = alias[1] if alias_used else title
        exact = exact_event_notices(matching_title, c["StartDatetime"], notices)
        related = [n["id"] for n in notices if matches_title(matching_title, n["title"])]
        status = "notice_available_link_absent" if len(exact) == 1 else (
            "ambiguous" if exact else "placeholder_date" if c["StartDatetime"] >= FOREVER
            else "no_exact_same_run_notice_match")
        rows.append({"event_id": ident, "kind": KINDS.get(c["EventQuestType"], str(c["EventQuestType"])),
                     "native_title": title, "matching_title": matching_title,
                     "reviewed_alias": alias_used, "start": c["StartDatetime"],
                     "start_utc": datetime.fromtimestamp(c["StartDatetime"] / 1000, timezone.utc).isoformat(),
                     "status": status, "notice_id": exact[0]["id"] if len(exact) == 1 else 0,
                     "notice_title": exact[0]["title"] if len(exact) == 1 else "",
                     "candidate_notice_ids": [n["id"] for n in exact],
                     "related_notice_ids_not_accepted_as_same_run": sorted(set(related) - {n["id"] for n in exact})})
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                             for k, v in r.items()})


def run(master_dir, text_db, pack_path, compare_pack, output):
    used = {Path(__file__).resolve()}

    def read(path):
        used.add(path)
        return path.read_text(encoding="utf-8")

    def master(name):
        return json.loads(read(master_dir / ("EntityM" + name + "Table.json")))

    def pack(path):
        used.add(path)
        with zipfile.ZipFile(path) as z:
            return json.loads(z.read("notices.json"))

    with sqlite3.connect(text_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        texts = dict(db.execute("SELECT key, value FROM text"))
    used.add(text_db)
    data, comparison = pack(pack_path), pack(compare_pack)
    rules = json.loads(read(ROOT / "overlays/server/internal/masterdata/summon_rules.json"))
    boxes = json.loads(read(ROOT / "overlays/server/internal/masterdata/summon_events.json"))["events"]
    patch = read(ROOT / "patches/lunar-tear-vanilla.patch")
    special = read(ROOT / "overlays/server/internal/masterdata/gacha_special.go")
    # Record the actual consumers as evidence of link precedence and absent event mapping.
    for name in ("overlays/server/internal/masterdata/bunker_summon_rules.go",
                 "overlays/server/internal/masterdata/bunker_event_summons.go",
                 "overlays/server/internal/service/bunker_notices.go", "overlays/server/mobile/server.go"):
        read(ROOT / name)
    catalog = build_catalog(master, rules["new"], boxes, patch, special)
    events = audit_events(master("EventQuestChapter"), texts, data["notices"])
    event_by_id = {r["event_id"]: r for r in events}
    notices = {n["id"]: n for n in data["notices"]}
    declared = {n["id"]: n.get("notice", 0) for n in rules["new"]}
    for ident, row in catalog.items():
        row["title"] = texts.get("gacha.title." + row["asset"], "")
        row["notice_id"] = row["explicit_notice_id"] or data["gacha"].get(str(ident), 0)
        row["declared_rule_notice_id"] = declared.get(ident, 0)
        candidate, reason = 0, ""
        if row["notice_id"]:
            row["status"] = "linked" if row["notice_id"] in notices else "linked_notice_missing"
        else:
            row["status"] = "no_verified_same_run_notice_candidate"
            if declared.get(ident) in notices:
                candidate, reason = declared[ident], "declared_notice_ignored_for_existing_catalog_entry"
            elif row["source"] == "event_box":
                candidate = event_by_id[row["event_id"]]["notice_id"]
                if candidate:
                    reason = "same_event_title_and_exact_start"
            if candidate:
                row["status"] = "notice_available_link_absent"
        row["candidate_notice_id"], row["candidate_reason"] = candidate, reason
        row.setdefault("event_id", 0)
    summon_rows = sorted(catalog.values(), key=lambda r: r["gacha_id"])
    # Unify CSV columns for rows originating in different loader stages.
    summon_rows = [{k: r[k] for k in summon_rows[0]} for r in summon_rows]
    available_events = [r for r in events if r["notice_id"]]
    available_summons = [r for r in summon_rows if r["candidate_notice_id"]]
    summary = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Static reconstruction from original master JSON and current catalog loaders; excludes permanent chapter-ticket summons. Not a live-device or currently-visible-banner census.",
        "event_chapters_audited": len(events),
        "event_links_to_existing_same_run_notice_absent": len(available_events),
        "available_event_links_by_kind": dict(Counter(r["kind"] for r in available_events)),
        "event_chapters_without_unique_exact_same_run_match": len(events) - len(available_events),
        "record_event_statuses": dict(Counter(r["status"] for r in events if r["kind"] == "Record")),
        "reconstructed_non_chapter_summons": len(summon_rows),
        "summons_with_working_notice_link": sum(r["status"] == "linked" for r in summon_rows),
        "summons_without_notice_link": sum(not r["notice_id"] for r in summon_rows),
        "unlinked_summons_by_loader_source": dict(Counter(r["source"] for r in summon_rows if not r["notice_id"])),
        "unlinked_summons_with_existing_notice_candidate": len(available_summons),
        "available_summon_links_by_reason": dict(Counter(r["candidate_reason"] for r in available_summons)),
        "unlinked_summons_without_verified_notice_candidate": sum(not r["notice_id"] and not r["candidate_notice_id"] for r in summon_rows),
        "configured_event_box_summons": len(boxes),
        "configured_event_box_summons_with_existing_notice_candidate": sum(r["source"] == "event_box" for r in available_summons),
        "packed_link_ids_absent_reconstructed_non_chapter_catalog": sorted(int(g) for g in data["gacha"] if int(g) not in catalog),
        "broken_existing_notice_targets": [r["gacha_id"] for r in summon_rows if r["status"] == "linked_notice_missing"],
        "same_summon_map_in_compared_packs": data["gacha"] == comparison["gacha"],
        "same_event_matches_in_compared_packs": [r["notice_id"] for r in events] == [r["notice_id"] for r in audit_events(master("EventQuestChapter"), texts, comparison["notices"])],
        "changes_applied_to_application_or_packs": False,
        "source_sha256": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(used)},
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("events", events), ("summons", summon_rows)):
        (output / (name + ".json")).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        write_csv(output / (name + ".csv"), rows)
    write_csv(output / "available-event-links.csv", available_events)
    write_csv(output / "available-summon-links.csv", available_summons)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-dir", type=Path, required=True)
    parser.add_argument("--text-db", type=Path, required=True)
    parser.add_argument("--pack", type=Path, default=ROOT / "inputs/bunker-notices-recovered.zip")
    parser.add_argument("--compare-pack", type=Path, default=ROOT / "inputs/bunker-notices.zip")
    parser.add_argument("--output", type=Path, default=ROOT / ".build/notice-audit/summon-link-audit")
    args = parser.parse_args()
    result = run(args.master_dir, args.text_db, args.pack, args.compare_pack, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "source_sha256"}, indent=2))
