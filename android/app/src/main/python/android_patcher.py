"""Launcher UI for NavHobbyDev's standard presets, splits and configuration."""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
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
PRESETS = [("Full", "All content"), ("Clear", "Story"), ("Gacha", "Gacha shops"), ("Rec", "Record events"), ("Var", "Variation events"), ("Bonus", "Bonus quests")]
SPLITS = [(f"{key}_{index}", f"{label} {index}") for key, label, count in (("Gacha", "Gacha", 5), ("Rec", "Record", 5), ("Var", "Variation", 4), ("Bonus", "Bonus", 4)) for index in range(1, count + 1)]


def folder():
    path = config.DATA_DIR / "patcher"
    path.mkdir(exist_ok=True)
    return path


def get_config():
    path = folder() / "config.json"
    if not path.exists():
        import patcher
        shutil.copyfile(Path(patcher.__file__).parent / "config.json", path)
    return json.loads(path.read_text())


def expand(cfg, key, seen=()):
    if key in seen or len(seen) > 20:
        raise ValueError("Configuration contains a circular reference")
    value = cfg.get(key, "")
    if isinstance(value, list):
        return ", ".join(expand(cfg, entry, (*seen, key)) for entry in value)
    if not isinstance(value, str):
        raise ValueError("Configuration values must be text or lists of keys")
    return value.strip()


def arguments(preset, cfg):
    if preset not in dict(PRESETS + SPLITS):
        raise ValueError("Unknown preset")
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
        raise ValueError("Select the original 3.7.1 master-data file")
    decoded = unpad(AES.new(bytes.fromhex(dump_masterdata.DEFAULT_KEY), AES.MODE_CBC, bytes.fromhex(dump_masterdata.DEFAULT_IV)).decrypt(raw), AES.block_size)
    try:
        msgpack.unpackb(decoded, raw=False, strict_map_key=False)
        raise ValueError("Master data has no tables")
    except msgpack.ExtraData as exc:
        toc, blob = exc.unpacked, exc.extra
    for name in ("m_costume", "m_weapon", "m_event_quest_chapter", "m_shop", "m_mom_banner"):
        if name not in toc:
            raise ValueError("Required game table is missing: " + name)
    for offset, length in toc.values():
        if offset < 0 or length <= 0 or offset + length > len(blob):
            raise ValueError("Invalid master-data table bounds")
        dump_masterdata.decompress_table(blob, offset, length)


def master_history():
    return sorted(folder().glob("master_*.bin.e"), reverse=True)


def activate(candidate, label):
    validate_master(candidate)
    master = config.find_master_data_bin()
    backup = folder() / ("master_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f") + ".bin.e")
    shutil.copyfile(master, backup)
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
        (config.DATA_DIR / "catalog-version.json").unlink(missing_ok=True)
        runtime.prepare_data()
        raise
    (folder() / "active.json").write_text(json.dumps({"label": label, "sha256": runtime.fingerprint(master)}))
    for old in master_history()[10:]:
        old.unlink()


def redirect(**kwargs):
    return RedirectResponse("/patcher?" + urlencode(kwargs), status_code=303)


@router.get("/patcher")
def view(request: Request, message: str = "", error: str = ""):
    current = "Imported master data"
    state = folder() / "active.json"
    if state.exists():
        metadata = json.loads(state.read_text())
        if metadata.get("sha256") == runtime.fingerprint(config.find_master_data_bin()):
            current = metadata["label"]
    return templates.TemplateResponse(request, "patcher.html", {"active": "patcher", "current": current, "presets": PRESETS, "splits": SPLITS,
        "configuration": json.dumps(get_config(), indent=2), "history": [p.name for p in master_history()], "message": message, "error": error})


@router.post("/patcher/apply")
def apply(preset: str = Form(...), configuration: str = Form("")):
    candidate = folder() / "candidate.bin.e"
    try:
        cfg = json.loads(configuration) if configuration.strip() else get_config()
        if not isinstance(cfg, dict):
            raise ValueError("Configuration must be a JSON object")
        args = arguments(preset, cfg)
        origin = folder() / "origin.bin.e"
        if not origin.exists():
            raise ValueError("Choose original master data under Advanced")
        from patcher import patch_masterdata
        patch_masterdata = importlib.reload(patch_masterdata)
        log = runtime.cli(patch_masterdata, ["--input", origin, "--output", candidate, *args])
        (folder() / "last-patch.log").write_text(log)
        activate(candidate, dict(PRESETS + SPLITS)[preset])
        (folder() / "config.json").write_text(json.dumps(cfg, indent=2))
        return redirect(message="Applied. Close Tools and tap Play.")
    except Exception as exc:
        return redirect(error=str(exc))
    finally:
        candidate.unlink(missing_ok=True)


@router.post("/patcher/restore")
def restore(filename: str = Form(...)):
    if filename not in [p.name for p in master_history()]:
        return redirect(error="Snapshot not found")
    candidate = folder() / "candidate.bin.e"
    try:
        shutil.copyfile(folder() / filename, candidate)
        activate(candidate, "Restored snapshot")
        return redirect(message="Master data restored. Close Tools and tap Play.")
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
            raise ValueError("Master file is too large")
        candidate.write_bytes(data)
        validate_master(candidate)
        origin = folder() / "origin.bin.e"
        if origin.exists():
            shutil.copyfile(origin, folder() / "origin.previous.bin.e")
        os.replace(candidate, origin)
        return redirect(message="Original master data updated.")
    except Exception as exc:
        return redirect(error=str(exc))
    finally:
        candidate.unlink(missing_ok=True)


@router.get("/patcher/export")
def export():
    return FileResponse(config.find_master_data_bin(), filename="20240404193219.bin.e", media_type="application/octet-stream")
