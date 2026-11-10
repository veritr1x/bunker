"""Launcher UI for NavHobbyDev's standard presets, splits and configuration."""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import re
import shutil
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web import config
import android_runtime as runtime

router = APIRouter()
templates = Jinja2Templates(directory=str(config.ROOT / "web" / "templates"))
import bunker_text  # noqa: E402
from bunker_text import t  # noqa: E402
bunker_text.install(templates)  # Bunker's own text, in the chosen language
# Each preset: its name for the patcher, and its words' key in Bunker's catalogue (a split's takes its number, n).
PRESETS = [("Full", "pods.patcher.label.full"), ("Clear", "pods.patcher.label.story"), ("Gacha", "pods.patcher.label.gacha"),
           ("Rec", "pods.patcher.label.record"), ("Var", "pods.patcher.label.variation"), ("Bonus", "pods.patcher.label.bonus")]
SPLITS = [(f"{key}_{index}", "pods.patcher.label.split_" + key.lower()) for key, count in (("Gacha", 5), ("Rec", 5), ("Var", 4), ("Bonus", 4))
          for index in range(1, count + 1)]
# active.json's label: what made the master data, as an id the page puts in words (shown_label): a preset's key
# ("Full", "Gacha_3"), RESTORED, or calendar_id(loop). Other text (Mods, Gift: "Imported master data" in the chosen
# language) is shown as it is.
RESTORED = "restored"
# Labels written before ids were kept (the English names of Bunker 1.x), read as their ids.
LEGACY = {"All content": "Full", "Story": "Clear", "Gacha shops": "Gacha", "Record events": "Rec", "Variation events": "Var",
          "Bonus quests": "Bonus", "Gacha 1": "Gacha_1", "Gacha 2": "Gacha_2", "Gacha 3": "Gacha_3", "Gacha 4": "Gacha_4",
          "Gacha 5": "Gacha_5", "Record 1": "Rec_1", "Record 2": "Rec_2", "Record 3": "Rec_3", "Record 4": "Rec_4",
          "Record 5": "Rec_5", "Variation 1": "Var_1", "Variation 2": "Var_2", "Variation 3": "Var_3", "Variation 4": "Var_4",
          "Bonus 1": "Bonus_1", "Bonus 2": "Bonus_2", "Bonus 3": "Bonus_3", "Bonus 4": "Bonus_4",
          "Restored snapshot": RESTORED}


def calendar_id(loop):
    """The label of the Original calendar's game data for a loop."""
    return f"calendar-{loop}"


def label_id(label):
    """A stored label as an id: an old English name becomes its id; anything else stays as it is."""
    if label in LEGACY:
        return LEGACY[label]
    old_calendar = re.fullmatch(r"Original calendar · loop (\d+)", label)
    return calendar_id(old_calendar.group(1)) if old_calendar else label


def preset_label(preset):
    """A preset's name ("All content", "Gacha 3") in the chosen language."""
    key, n = dict(PRESETS + SPLITS)[preset], preset.partition("_")[2]
    return t(key, n=n)


def shown_label(label):
    """active.json's label in the chosen language; text of another kind as it is."""
    label = label_id(label)
    if label in dict(PRESETS + SPLITS):
        return preset_label(label)
    if label == RESTORED:
        return t("pods.patcher.label.restored")
    loop = re.fullmatch(r"calendar-(\d+)", label)
    if loop:
        return t("pods.patcher.label_calendar", loop=loop.group(1))
    return label


def active_label():
    """active.json, its label read as an id; an old English label is rewritten as its id once."""
    path = folder() / "active.json"
    active = runtime.read_json(path)
    if not (isinstance(active, dict) and isinstance(active.get("label"), str)):
        return active
    label = label_id(active["label"])
    if label != active["label"]:
        active["label"] = label
        runtime.write_json(path, active)
    return active


def folder():
    path = config.DATA_DIR / "patcher"
    path.mkdir(exist_ok=True)
    return path


def get_config():
    path = folder() / "config.json"
    cfg = runtime.read_json(path)
    if not isinstance(cfg, dict):
        # Missing or damaged: start again from the bundled configuration.
        import patcher
        cfg = json.loads((Path(patcher.__file__).parent / "config.json").read_text())
        runtime.write_json(path, cfg, indent=2)
    return cfg


def expand(cfg, key, seen=()):
    if key in seen or len(seen) > 20:
        raise ValueError(t("pods.patcher.circular"))
    value = cfg.get(key, "")
    if isinstance(value, list):
        return ", ".join(expand(cfg, entry, (*seen, key)) for entry in value)
    if not isinstance(value, str):
        raise ValueError(t("pods.patcher.bad_value"))
    return value.strip()


# Presets choose limited-time events; the patcher expires every event chapter
# a preset doesn't list. These kinds of chapter are part of the game, not
# events, and the configuration leaves many out (every Dark Memory and
# Recollections of Dusk chapter: their menus were empty), so every preset keeps
# them. EventQuestType: 6 character quests, 7 Dark Memories, 8 the cage,
# 10 Abyss Towers, 11 Recollections of Dusk, 12 the Labyrinth.
PERMANENT_EVENT_TYPES = {6, 7, 8, 10, 11, 12}


def permanent_chapters():
    rows = runtime.read_json(config.MASTERDATA_DIR / "EntityMEventQuestChapterTable.json", []) or []
    return sorted(r["EventQuestChapterId"] for r in rows if isinstance(r, dict) and r.get("EventQuestType") in PERMANENT_EVENT_TYPES)


def medal_exchanges():
    """Every shop selling for a summon medal or shard (m_gacha_medal). The
    configuration lists the exchanges of its own summons only, but with the
    calendar off Lunar Tear opens every summon (the weekly ones, the
    multi-steps, those recovered from notices), and a summon gives its shard
    only while its exchange is open."""
    table = lambda name: [r for r in runtime.read_json(config.MASTERDATA_DIR / f"EntityM{name}Table.json", []) or [] if isinstance(r, dict)]
    medals = {r.get("ConsumableItemId") for r in table("GachaMedal")}
    items = {r.get("ShopItemId") for r in table("ShopItem") if r.get("PriceType") == 1 and r.get("PriceId") in medals}
    cells = {r.get("ShopItemCellId") for r in table("ShopItemCell") if r.get("ShopItemId") in items}
    groups = {r.get("ShopItemCellGroupId") for r in table("ShopItemCellGroup") if r.get("ShopItemCellId") in cells}
    return sorted(r["ShopId"] for r in table("Shop") if r.get("ShopItemCellGroupId") in groups and isinstance(r.get("ShopId"), int))


def arguments(preset, cfg):
    if preset not in dict(PRESETS + SPLITS):
        raise ValueError(t("common.unknown_preset"))
    get = lambda key: expand(cfg, key)
    join = lambda *keys: ", ".join(get(k) for k in keys)
    events = get("EVENTS_MAIN")
    banners = join("GACHA_PREM_ALL", "GACHA_EVENT")
    shops = join("SHOPS_MAIN", "SHOPS_EXTRA")
    if preset == "Full":
        events = join("EVENTS_MAIN", "EVENTS_REC_ALL", "EVENTS_VAR_ALL", "EVENTS_BONUS_ALL")
        shops = join("SHOPS_MAIN", "SHOPS_EXTRA", "SHOPS_GACHA_ALL", "SHOPS_EVENT_ALL")
    elif preset == "Gacha":
        shops += ", " + get("SHOPS_GACHA_ALL")
    elif preset == "Rec":
        events += ", " + get("EVENTS_REC_ALL")
        shops += ", " + get("SHOPS_EVENT_ALL")
    elif preset in ("Var", "Bonus"):
        events += ", " + get("EVENTS_" + preset.upper() + "_ALL")
    elif "_" in preset:
        family, index = preset.split("_")
        if family == "Gacha":
            banners = join("GACHA_PREM_" + index, "GACHA_EVENT")
            shops += ", " + get("SHOPS_GACHA_" + index)
        else:
            events += ", " + get("EVENTS_" + family.upper() + "_" + index)
            if family == "Rec":
                shops += ", " + get("SHOPS_EVENT_" + index)
    if preset in ("Full", "Gacha") or preset.startswith("Gacha_"):
        exchanges = medal_exchanges()
        if exchanges:
            shops = ", ".join(filter(None, [shops, ", ".join(str(s) for s in exchanges)]))
    permanent = permanent_chapters()
    if permanent:
        events = ", ".join(filter(None, [events, ", ".join(str(c) for c in permanent)]))
    return ["--event-quests", events, "--banners", banners, "--premium-shops", get("SHOP_PREM"), "--exchange-shops", shops,
            "--exclude-consumables", get("CONSUMABLES_ALL"), "--rewrite-shop-content", join("SHOPCONTENT_COMP", "SHOPCONTENT_MEDAL"),
            "--rewrite-shop-count", get("SHOPCOUNT"), "--rewrite-shop-type", get("SHOPTYPE")]


def validate_master(path):
    from tools import dump_masterdata
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    import msgpack
    raw = Path(path).read_bytes()
    if not 1_000_000 < len(raw) < 32_000_000:
        raise ValueError(t("pods.patcher.wrong_file"))
    decoded = unpad(AES.new(bytes.fromhex(dump_masterdata.DEFAULT_KEY), AES.MODE_CBC, bytes.fromhex(dump_masterdata.DEFAULT_IV)).decrypt(raw), AES.block_size)
    try:
        msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        raise ValueError(t("pods.patcher.no_tables"))
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    for name in ("m_costume", "m_weapon", "m_event_quest_chapter", "m_shop", "m_mom_banner"):
        if name not in toc:
            raise ValueError(t("pods.patcher.missing_table", table=name))
    for offset, length in toc.values():
        if offset < 0 or length <= 0 or offset + length > len(blob):
            raise ValueError(t("pods.patcher.bad_bounds"))
        dump_masterdata.decompress_table(blob, offset, length)


def master_history():
    return sorted(folder().glob("master_*.bin.e"), reverse=True)


def activate(candidate, label):
    import android_challenges as challenges
    validate_master(candidate)
    challenges.on_activate(candidate)  # Mods › Challenges, applied once
    master = config.find_master_data_bin()
    source = challenges.unchallenged(master)  # snapshots hold the game data without challenges or texts
    newest = master_history()[:1]
    if newest and runtime.fingerprint(newest[0]) == runtime.fingerprint(source):
        backup = newest[0]  # the same data as the last snapshot (a language switched back and forth): no copy
    else:
        backup = folder() / ("master_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f") + ".bin.e")
        shutil.copyfile(source, backup)
        with backup.open("rb") as handle:
            os.fsync(handle.fileno())
    with candidate.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(candidate, master)
    try:
        runtime.prepare_data()
    except BaseException:
        # Keep the old playable master active if catalog preparation fails.
        rollback = master.with_suffix(".rollback")
        shutil.copyfile(backup, rollback)
        os.replace(rollback, master)
        challenges.finish(master)  # the backup holds the game data without challenges
        (config.DATA_DIR / "catalog-version.json").unlink(missing_ok=True)
        runtime.prepare_data()
        raise
    runtime.write_json(folder() / "active.json", {"label": label, "sha256": runtime.fingerprint(master)})
    for old in master_history()[10:]:
        old.unlink()
    challenges.after_activate()


def redirect(**kwargs):
    return RedirectResponse("/patcher?" + urlencode(kwargs), status_code=303)


# Start a new day: day-start.json beside the save holds when it was pressed
# (real time); the server's day starts there until the next game day
# (gametime.StartOfDay), so everything daily starts over. The game keeps day
# markers in memory, so it is closed (android_runtime.CLOSES) and the markers
# are cleared before it starts again (client-days.reset).
def day_start_file():
    return config.GAME_DB_PATH.parent / "day-start.json"


def start_new_day(now_ms=None):
    import android_calendar as calendar
    now_ms = calendar.now_ms() if now_ms is None else int(now_ms)
    pending = day_start_file().with_suffix(".tmp")
    pending.write_text(json.dumps({"pressedRealMillis": now_ms}) + "\n")
    os.replace(pending, day_start_file())
    calendar.mark_client_days_reset()


def new_day_today(now_ms=None):
    """Whether Start a new day was pressed on today's game day (it pauses the
    challenge bonus until the next one, as gametime.NewDayPausesBonus)."""
    import android_calendar as calendar
    saved = runtime.read_json(day_start_file())
    pressed = saved.get("pressedRealMillis") if isinstance(saved, dict) else None
    if not isinstance(pressed, int) or pressed <= 0:
        return False
    now_ms = calendar.now_ms() if now_ms is None else int(now_ms)
    state = calendar.peek_state()
    game = (lambda real: calendar.game_now(state, real)) if state else (lambda real: real)
    return calendar.start_of_day(game(now_ms)) <= game(pressed) <= game(now_ms)


@router.post("/patcher/new-day")
def new_day():
    try:
        start_new_day()
    except Exception as exc:
        return redirect(error=str(exc))
    return redirect(message=t("pods.patcher.new_day_started", next=t("pods.runtime.deploy")))


@router.get("/patcher")
def view(request: Request, message: str = "", error: str = ""):
    current = t("pods.patcher.imported")
    metadata = active_label()
    if isinstance(metadata, dict) and isinstance(metadata.get("label"), str) and metadata["label"]:
        if metadata.get("sha256") == runtime.fingerprint(config.find_master_data_bin()):
            current = shown_label(metadata["label"])
    import android_calendar as calendar
    state = calendar.read_state()
    schedule = start = None
    if state:
        try:
            if calendar.roll_over(state):
                message = message or t("pods.patcher.loop_started", loop=state["loop"], next=t("pods.runtime.deploy"))
            else:
                # Calendars started before loops opened at the first summons.
                changed = calendar.open_at_first_summons(state)
                if not calendar.next_file().exists():
                    calendar.prepare_next(state)
                    changed = True
                if changed:
                    calendar.write_state(state)
        except Exception as exc:
            error = error or str(exc)
        schedule = calendar.context(state)
        current = calendar.label(state)
    else:
        start = calendar.start_preview()
    return templates.TemplateResponse(request, "patcher.html", {"active": "patcher", "current": current,
        "presets": [(key, preset_label(key)) for key, _ in PRESETS], "splits": [(key, preset_label(key)) for key, _ in SPLITS],
        "configuration": json.dumps(get_config(), indent=2), "history": [p.name for p in master_history()], "message": message, "error": error,
        "calendar": schedule, "start": start})


def apply_preset(preset, cfg):
    """Builds the master data for a preset from the original and makes it the game's."""
    candidate = folder() / "candidate.bin.e"
    try:
        args = arguments(preset, cfg)
        origin = folder() / "origin.bin.e"
        if not origin.exists():
            raise ValueError(t("pods.patcher.load_original"))
        from patcher import patch_masterdata
        patch_masterdata = importlib.reload(patch_masterdata)
        log = runtime.cli(patch_masterdata, ["--input", origin, "--output", candidate, *args])
        (folder() / "last-patch.log").write_text(log)
        activate(candidate, preset)  # its key: active.json
    finally:
        candidate.unlink(missing_ok=True)


def reapply_preset():
    """Builds the preset's master data again with this build's patcher when the
    master data is still what that preset made (active.json). Returns True when it did."""
    active = active_label()
    presets = dict(PRESETS + SPLITS)
    if not (isinstance(active, dict) and active.get("label") in presets):
        return False
    master = config.find_master_data_bin()
    if not master.is_file() or runtime.fingerprint(master) != active.get("sha256"):
        return False  # Imported, restored or changed since.
    apply_preset(active["label"], get_config())
    return True


def updated_file():
    """The Bunker version update_for last ran for, beside the save (DataUpdate.java, LunarTools.m read it)."""
    return config.GAME_DB_PATH.parent / "data.updated"


def update_for(version):
    """Brings the game data up to this build once per Bunker version: the
    calendar's (android_calendar.read_state) or a preset's (reapply_preset).
    The launchers call it before the server starts, so an update reaches the
    game without opening Pod Programs. Returns True when it ran."""
    import android_calendar as calendar
    stamp = updated_file()
    if stamp.exists() and stamp.read_text().strip() == version:
        return False
    if not calendar.read_state():
        reapply_preset()
    stamp.write_text(version)
    return True


@router.post("/patcher/apply")
def apply(preset: str = Form(...), configuration: str = Form("")):
    import android_calendar as calendar
    if calendar.read_state():
        return redirect(error=t("pods.patcher.calendar_on"))
    try:
        cfg = json.loads(configuration) if configuration.strip() else get_config()
        if not isinstance(cfg, dict):
            raise ValueError(t("pods.patcher.not_object"))
        apply_preset(preset, cfg)
        runtime.write_json(folder() / "config.json", cfg, indent=2)
        return redirect(message=t("pods.patcher.applied", next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))


@router.post("/patcher/restore")
def restore(filename: str = Form(...)):
    if filename not in [p.name for p in master_history()]:
        return redirect(error=t("pods.runtime.snapshot_not_found"))
    candidate = folder() / "candidate.bin.e"
    try:
        shutil.copyfile(folder() / filename, candidate)
        activate(candidate, RESTORED)
        return redirect(message=t("pods.patcher.restored_next", next=runtime.next_step()))
    except Exception as exc:
        return redirect(error=str(exc))
    finally:
        candidate.unlink(missing_ok=True)


@router.post("/patcher/origin")
def import_origin(source: UploadFile = File(...)):
    candidate = folder() / "source.pending"
    try:
        data = source.file.read(32_000_001)
        if len(data) > 32_000_000:
            raise ValueError(t("pods.patcher.too_large"))
        candidate.write_bytes(data)
        validate_master(candidate)
        origin = folder() / "origin.bin.e"
        if origin.exists():
            shutil.copyfile(origin, folder() / "origin.previous.bin.e")
        os.replace(candidate, origin)
        return redirect(message=t("pods.patcher.original_updated"))
    except Exception as exc:
        return redirect(error=str(exc))
    finally:
        candidate.unlink(missing_ok=True)


@router.get("/patcher/export")
def export():
    import android_challenges as challenges
    return FileResponse(challenges.unchallenged_master(), filename="20240404193219.bin.e", media_type="application/octet-stream")
