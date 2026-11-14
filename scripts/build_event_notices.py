#!/usr/bin/env python3
"""Builds the next notice pack: the pinned pack, rebuilt notices for home
banners whose notice was lost, and the recreated banners.

A home-screen banner opens a notice by id. The pack lacks most 2021-2022
announcements, so with the Original calendar those banners opened "This notice
isn't available." Each home banner the calendar shows whose notice the pack
lacks (event_banners.home_notices) gets a notice of its own, id NOTICE_BASE +
its row, which the calendar points it at (event_banners.json "notices"). The
page is laid out and worded as the official notices of its kind
(event_notice_pages.py), from the game data (event_notice_facts.py): an
event's exchange, medal, exchange characters with their stats, skills and
abilities, and resonant weapons, as the run had them; checked against the
official notices that survive (check_event_notices.py). It says it was rebuilt.

The recreated banners (recreate_banners.py's banners/<lang>/*.astc) go in the
same pack, under banners/.

  build_event_notices.py --source-pack PINNED.ZIP --masters DIR --dump resource_dump_android.7z \\
                         --assets DIR --banners DIR --out DIR [--deckbuilder .build/deckbuilder]

Bundles the pages need are extracted from the dump into --assets (7zz). Needs
UnityPy, Pillow, pycryptodome, msgpack, lz4 and Deck Builder's master data dump.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import calendar_history as ch
import event_banners as eb

TRANSLATIONS = ch.ROOT / "translations/game"
NOT_EVENTS = ("Character Quest", "Dark Memory", "Dungeon")
KINDS = (("campaign_", "Campaign"), ("mission_", "Missions"), ("main_quest_", "Main Story"), ("big_hunt_", "Subjugation"))
STAMP = (2026, 11, 14, 0, 0, 0)


def kind(banner_name):
    """What a home banner that is not an event's advertised, by its image's name."""
    return next((label for prefix, label in KINDS if banner_name.startswith(prefix)), "Notice")


def event_at(start, runs, names):
    """(chapter, run index) of the event whose run starts with the banner, or None.
    runs: chapter -> [(start, end)] in order; names: chapter -> its name."""
    for chapter, chapter_runs in sorted(runs.items()):
        name = names.get(chapter, "")
        if not name or name.startswith(NOT_EVENTS):
            continue
        for n, (run_start, _) in enumerate(chapter_runs):
            if run_start == start:
                return chapter, n
    return None


def when(ms):
    t = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return f"{t.strftime('%b')}. {t.day}, {t.year} {t.strftime('%H:%M')}"


def banner_member(lang):
    """Where the pack keeps a recreated banner image: under web/, the one folder (besides img/*.webp) whose
    files every installed launcher accepts in a notice pack (android/tools/notice_pack.py). The server
    reads it from there (translation/banners.go) and does not serve web/bunker/."""
    return f"web/bunker/banners/{lang}/event_banner_900.astc"


def coming(chapter, at, runs):
    """(chapter, run index) of the chapter's next run after at, for a banner shown before it opens."""
    for n, (start, _) in enumerate(runs.get(chapter, [])):
        if start > at:
            return chapter, n
    return None


def make_notice(row, banner_name, run, facts, art, soon=None):
    """The rebuilt notice for home banner row: its event's (facts), an event coming soon (soon: name,
    start), else what the banner advertised."""
    import event_notice_pages as pages
    start, end = run
    thumb = art[len("img/"):-len(".webp")] if art else None
    if facts:
        title, body, kind_ = pages.title(facts), pages.body(facts, art), 2
    elif soon:
        title, body, kind_ = f'Event Quest "{soon["name"]}" Coming Soon', pages.coming_body(soon, start, end, art), 2
    else:
        label = kind(banner_name)
        title, body, kind_ = f"{label} On Now", pages.other_body(label, start, end, art), 1
    return {"id": eb.NOTICE_BASE + row, "type": kind_, "title": title, "publish": start,
            **({"thumb": thumb} if thumb else {}), "body": body}


def trim(image):
    """A home banner's strip, cut out of the transparent square it is drawn in."""
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def pages_for(source_pack, masters, assets, deckbuilder):
    """The rebuilt notices and the images they use; the dump bundles still missing from assets."""
    import sys
    sys.path.insert(0, str(ch.PYTHON))
    import android_calendar as cal
    import event_notice_facts as F
    with zipfile.ZipFile(source_pack) as z:
        pack = json.loads(z.read("notices.json"))
    images = F.Images(assets)
    facts = F.Facts(masters, deckbuilder / "master", deckbuilder / "names", images, [n["title"] for n in pack["notices"]])
    final = facts.tables_at(facts.times[-1])
    history = json.loads((ch.PYTHON / "calendar_history.json").read_text())["tables"]
    chapters = {c["EventQuestChapterId"]: c for c in final["m_event_quest_chapter"]}
    names = {c: facts.chapter_name(r) for c, r in chapters.items()}
    runs = {int(c): [tuple(x) for x in v] for c, v in history["m_event_quest_chapter"]["rows"].items() if int(c) in chapters}
    for c, r in chapters.items():
        runs.setdefault(c, [(r["StartDatetime"], r["EndDatetime"])])
    pack_ids = {n["id"] for n in pack["notices"]}
    home = {r["MomBannerId"]: r for r in final["m_mom_banner"]} if "m_mom_banner" in final else {}
    if not home:
        toc, blob = ch.load(masters[-1])
        cols = {c: i for i, _, c in facts.schemas["m_mom_banner"][1]}
        home = {r[cols["MomBannerId"]]: {c: r[i] for c, i in cols.items()} for r in ch.dm.decompress_table(blob, *toc["m_mom_banner"])}
    wanted = eb.home_notices({k: (r["DestinationDomainType"], r["DestinationDomainId"], r["StartDatetime"]) for k, r in home.items()},
                             history["m_mom_banner"]["rows"], pack_ids, unrestored=cal.UNRESTORED_BANNERS)
    notices = []
    for row_key, notice_id in sorted(wanted.items(), key=lambda kv: int(kv[0])):
        r = home[int(row_key)]
        restored = history["m_mom_banner"]["rows"].get(row_key)
        run = min(tuple(x) for x in restored) if restored else (r["StartDatetime"], r["EndDatetime"])
        found = event_at(run[0], runs, names) if r["BannerAssetName"].startswith(eb.EVENT_HOME) else None
        event = facts.event(found[0], runs[found[0]][found[1]]) if found else None
        soon = None
        number = r["BannerAssetName"].removeprefix(eb.EVENT_HOME)
        if not event and number.isdigit() and int(number) in names:
            later = coming(int(number), run[0], runs)
            if later:
                soon = {"name": names[later[0]], "start": runs[later[0]][later[1]][0]}
        art = images.img(f"ui/mom_banner/en/mom_banner_{r['BannerAssetName']}")
        notice = make_notice(int(row_key), r["BannerAssetName"], run, event, art, soon)
        assert notice["id"] == notice_id and notice_id not in pack_ids
        notices.append(notice)
    return pack, notices, images


def extract(dump: Path, assets: Path, wanted):
    """Takes the named bundles out of the resource dump into assets (revisions/0/assetbundle/…)."""
    import subprocess
    import tempfile
    if not wanted:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as listing:
        listing.write("".join(f"revisions/0/assetbundle/{w}\n" for w in sorted(wanted)))
    out = assets.parent.parent.parent
    subprocess.run(["7zz", "x", "-y", f"-o{out}", str(dump), f"@{listing.name}"], check=True, stdout=subprocess.DEVNULL)


def build(source_pack: Path, masters: list[Path], dump: Path, assets: Path, banners: Path, out_dir: Path, deckbuilder: Path):
    pack, notices, images = pages_for(source_pack, masters, assets, deckbuilder)
    if images.missing:
        extract(dump, assets, images.missing)
        pack, notices, images = pages_for(source_pack, masters, assets, deckbuilder)
    pack["notices"].extend(notices)
    assert len({n["id"] for n in pack["notices"]}) == len(pack["notices"])
    extra = dict(images.members)
    for astc in sorted(banners.glob("banners/*/event_banner_900.astc")):
        extra[banner_member(astc.parent.name)] = astc.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    temp = out_dir / "pack.zip.part"
    with zipfile.ZipFile(source_pack) as source, zipfile.ZipFile(temp, "w") as out:
        names_in = set(source.namelist())
        for item in source.infolist():
            data = json.dumps(pack, ensure_ascii=False, separators=(",", ":")).encode() if item.filename == "notices.json" \
                else source.read(item.filename)
            out.writestr(item, data, compress_type=item.compress_type)
        for name, data in sorted(extra.items()):
            if name in names_in:
                continue  # an image the pack already has, by its content
            info = zipfile.ZipInfo(name, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED if name.endswith(".astc") else zipfile.ZIP_STORED
            out.writestr(info, data)
    digest = hashlib.sha256(temp.read_bytes()).hexdigest()
    final = out_dir / f"bunker-notices-{digest[:12]}.zip"
    temp.replace(final)
    with zipfile.ZipFile(final) as check:
        assert check.testzip() is None
    return final, digest, notices, images.missing


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-pack", type=Path, required=True, help="The pinned pack (inputs/bunker-notices-pinned.zip)")
    parser.add_argument("--masters", type=Path, required=True, help="Folder of global .bin.e files named by date")
    parser.add_argument("--dump", type=Path, required=True, help="resource_dump_android.7z")
    parser.add_argument("--assets", type=Path, required=True, help="Where its bundles go: DIR/revisions/0/assetbundle")
    parser.add_argument("--banners", type=Path, required=True, help="recreate_banners.py's output folder")
    parser.add_argument("--deckbuilder", type=Path, default=ch.ROOT / ".build/deckbuilder", help="Deck Builder's master/ and names/")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    masters = sorted(args.masters.glob("*.bin.e"))
    final, digest, notices, missing = build(args.source_pack, masters, args.dump, args.assets, args.banners, args.out, args.deckbuilder)
    print(json.dumps({"pack": str(final), "sha256": digest, "size": final.stat().st_size, "rebuilt_notices": len(notices),
                      "events": sum(n["type"] == 2 for n in notices), "with_art": sum("thumb" in n for n in notices),
                      "images_not_in_dump": sorted(missing)}))


if __name__ == "__main__":
    main()
