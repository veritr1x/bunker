#!/usr/bin/env python3
"""Export native character, costume, weapon and companion artwork from game data.

Requires UnityPy and Pillow. The source is read only; PNGs, a searchable offline
gallery and a provenance manifest are written to the output directory.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
import zipfile

FAMILIES = {"characters": "character", "costumes": "costume", "weapons": "weapon", "companions": "companion",
            "consumables": "consumable_item", "important_items": "important_item", "materials": "material",
            "memoirs": "memory", "memoir_frames": "memory_frame", "debris": "thought"}
DEFAULT_FAMILIES = ("characters", "costumes", "weapons", "companions")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_root(source):
    source = source.resolve(strict=True)
    for candidate in (source, source / "assetbundle", source / "revisions/0/assetbundle",
                      source / "assets/revisions/0/assetbundle"):
        if (candidate / "ui/costume").is_dir():
            return candidate
    raise ValueError("Choose the extracted assetbundle directory or its dump/revision parent")


def unmask(raw, relative_path):
    """Reverse the game's Octo mask; follows mobile/unityasset/bundle.go."""
    if raw.startswith(b"UnityFS"):
        return raw
    if not raw or raw[0] not in (0x31, 0x32):
        raise ValueError("Unknown or empty Unity bundle")
    name = relative_path.removesuffix(".assetbundle").replace("/", ")").encode()
    if not name:
        raise ValueError("Missing bundle name for Octo mask")
    mask = bytearray(len(name) * 2)
    for index, char in enumerate(name):
        mask[index * 2] = char
        mask[len(name) * 2 - 1 - index * 2] = char ^ 255
    key = 0xBB
    for char in mask:
        key = (((key & 1) << 7) | (key >> 1)) ^ char
    mask = bytes(char ^ key for char in mask)
    result = bytearray(raw)
    end = min(256, len(raw)) if raw[0] == 0x31 else len(raw)
    for index in range(1, end):
        result[index] ^= mask[index % len(mask)]
    result[0] = ord("U")
    return bytes(result)


def load_labels(database=None, master=None):
    names, characters = defaultdict(set), defaultdict(set)
    if database is None:
        return names, characters
    database = database.resolve(strict=True)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        text = dict(connection.execute("SELECT key,value FROM text WHERE key LIKE 'costume.name.%' "
                                       "OR key LIKE 'weapon.name.%' OR key LIKE 'companion.name.%' "
                                       "OR key LIKE 'character.name.%' OR key LIKE 'consumable_item.name.%' "
                                       "OR key LIKE 'important_item.name.%' OR key LIKE 'material.name.%' "
                                       "OR key LIKE 'thought.name.%' OR key LIKE 'parts.group.name.%'"))
    for key, value in text.items():
        if not value.strip():
            continue
        match = re.fullmatch(r"(?:costume|weapon|companion)\.name\.((?:ch|wp|mw|cm)\d{6})(?:\.\d+)?", key)
        if match:
            names[match[1]].add(value.strip())
        match = re.fullmatch(r"(consumable_item|important_item|material|thought)\.name\.(\d{6})", key)
        if match:
            prefix = {"consumable_item": "consumable", "important_item": "important",
                      "material": "material", "thought": "thought"}[match[1]]
            names[prefix + match[2]].add(value.strip())
    if master is not None:
        character_table = json.loads((master / "EntityMCharacterTable.json").read_text(encoding="utf-8"))
        by_id = {}
        for row in character_table:
            label = text.get("character.name." + str(row["NameCharacterTextId"]), "").strip()
            if label:
                by_id[row["CharacterId"]] = label
                names[f'character{row["CharacterAssetId"]:06d}'].add(label)
        costumes = json.loads((master / "EntityMCostumeTable.json").read_text(encoding="utf-8"))
        for row in costumes:
            label = by_id.get(row["CharacterId"])
            if label:
                characters[f'ch{row["ActorSkeletonId"]:03d}{row["AssetVariationId"]:03d}'].add(label)
        parts = master / "EntityMPartsGroupTable.json"
        if parts.is_file():
            for row in json.loads(parts.read_text(encoding="utf-8")):
                label = text.get("parts.group.name." + str(row["PartsGroupId"]), "").strip()
                if label:
                    names[f'memory{row["PartsGroupAssetId"]:03d}'].add(label)
    return names, characters


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value).strip(".") or "image"


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def make_preview(output, rows, Image):
    from PIL import ImageDraw, ImageFont
    groups = ("costumes", "weapons", "companions")
    preferred = {"costumes": "ch001003", "weapons": "wp001001", "companions": "cm005011"}
    if not any(r["family"] in groups for r in rows):
        available = {r["family"] for r in rows}
        groups = tuple(f for f in ("characters", "memoirs", "consumables", "debris", "important_items", "materials", "memoir_frames")
                       if f in available)[:3]
    samples = []
    for family in groups:
        options = [r for r in rows if r["family"] == family and r["variant"] == "full"]
        if not options:
            options = [r for r in rows if r["family"] == family]
        row = next((r for r in options if r["asset"] == preferred.get(family)), options[0] if options else None)
        if row:
            samples.append(row)
    preview = Image.new("RGB", (360 * len(samples), 540), (31, 35, 39))
    draw = ImageDraw.Draw(preview)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        small = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = small = ImageFont.load_default()
    for index, row in enumerate(samples):
        left = index * 360
        draw.text((left + 22, 18), row["family"].title(), font=small, fill=(160, 176, 190))
        with Image.open(output / row["file"]) as art:
            art = art.convert("RGBA")
            art.thumbnail((320, 420), Image.Resampling.LANCZOS)
            position = (left + (360-art.width)//2, 50 + (420-art.height)//2)
            preview.paste(art, position, art)
        label = " / ".join(row["names"]) or row["asset"]
        draw.text((left + 22, 485), label[:30], font=font, fill="white")
        draw.text((left + 22, 514), " / ".join(row["characters"]) or row["asset"], font=small, fill=(160,176,190))
    preview.save(output / "preview.jpg", quality=93)


def make_gallery(output, rows, image_module):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["family"], row["asset"])].append(row)
    preference = {name: index for index, name in enumerate(("full", "portrait", "gacha", "large", "standard"))}
    items = []
    for (family, asset), variants in sorted(grouped.items()):
        variants.sort(key=lambda r: (preference.get(r["variant"], 99), -r["width"] * r["height"], r["file"]))
        best = variants[0]
        target = output / "previews" / family / (asset + ".webp")
        target.parent.mkdir(parents=True, exist_ok=True)
        with image_module.open(output / best["file"]) as image:
            image.thumbnail((240, 280), image_module.Resampling.LANCZOS)
            image.save(target, "WEBP", quality=85)
        items.append({"family": family, "asset": asset, "name": " / ".join(best["names"]) or asset,
                      "character": " / ".join(best["characters"]), "preview": target.relative_to(output).as_posix(),
                      "variants": [{k: r[k] for k in ("variant", "file", "width", "height")} for r in variants]})
    embedded = json.dumps(items, ensure_ascii=False).replace("<", "\\u003c")
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Game artwork library</title><link rel="icon" href="data:,"><style>
*{box-sizing:border-box}body{margin:0;background:#17191b;color:#eee;font:15px system-ui,sans-serif}
header{padding:30px 5vw 20px;border-bottom:1px solid #3a3d40}h1{font-size:28px;margin:0 0 8px}p{color:#afb6bc;margin:5px 0 20px}
.filters{display:flex;gap:12px;flex-wrap:wrap}input,select,button{font:inherit;background:#272c30;color:#eee;border:1px solid #525b63;border-radius:5px;padding:10px}
input{width:min(460px,100%)}main{padding:22px 5vw}#count{margin-bottom:20px;color:#adb6bf}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:20px}
.tile{background:#222629;padding:12px;text-align:left;border:1px solid #353c42;cursor:pointer}.tile img{width:100%;height:220px;object-fit:contain;display:block;margin-bottom:12px}
.tile strong{display:block;font-size:14px}.tile small{display:block;color:#abb5bd;margin-top:5px}#more{display:block;margin:30px auto}
dialog{background:#222629;color:#eee;border:1px solid #58636c;border-radius:8px;width:min(900px,94vw)}dialog::backdrop{background:#000b}
#art{width:100%;height:60vh;object-fit:contain;background:repeating-conic-gradient(#30363b 0% 25%,#282d32 0% 50%) 50%/24px 24px}
#details{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:14px}a{color:#b9dcff}#close{float:right}
</style><header><h1>Game artwork library</h1><p>Native artwork exported from the Android data. Full illustrations, portraits, icons and battle images.</p>
<div class="filters"><input id="search" placeholder="Search a name or asset ID" aria-label="Search artwork"><select id="family" aria-label="Asset family"><option value="">All assets</option><option>costumes</option><option>characters</option><option>weapons</option><option>companions</option></select></div></header>
<main><div id="count"></div><div id="grid"></div><button id="more">Show more</button></main><dialog id="modal"><button id="close">Close</button><h2 id="title"></h2><img id="art" alt=""><div id="details"><select id="variant" aria-label="Image variant"></select><span id="size"></span><a id="download" download>Download PNG</a></div></dialog>
<script>const library=__DATA__;let shown=120,current=null;const $=id=>document.getElementById(id);const esc=s=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){const query=$('search').value.toLowerCase().trim(),family=$('family').value;const found=library.filter(x=>(!family||x.family===family)&&(!query||[x.name,x.character,x.asset].join(' ').toLowerCase().includes(query)));$('count').textContent=found.length+' assets · '+library.reduce((n,x)=>n+x.variants.length,0)+' PNG images in the library';$('grid').innerHTML=found.slice(0,shown).map(x=>'<button class="tile" data-asset="'+x.asset+'" data-family="'+x.family+'"><img loading="lazy" src="'+x.preview+'" alt=""><strong>'+esc(x.name)+'</strong><small>'+esc(x.character||x.family)+' · '+x.variants.length+' variants</small><small>'+x.asset+'</small></button>').join('');$('more').hidden=shown>=found.length;}
function image(){const v=current.variants[+$('variant').value];$('art').src=v.file;$('art').alt=current.name;$('size').textContent=v.width+' × '+v.height+' pixels';$('download').href=v.file;}
$('grid').onclick=e=>{const tile=e.target.closest('[data-asset]');if(!tile)return;current=library.find(x=>x.asset===tile.dataset.asset&&x.family===tile.dataset.family);$('title').textContent=[current.character,current.name].filter(Boolean).join(' — ');$('variant').innerHTML=current.variants.map((v,i)=>'<option value="'+i+'">'+esc(v.variant)+'</option>').join('');image();$('modal').showModal();};$('variant').onchange=image;$('close').onclick=()=>$('modal').close();for(const id of ['search','family'])$(id).oninput=()=>{shown=120;render();};$('more').onclick=()=>{shown+=120;render();};render();</script></html>"""
    present_families = {row["family"] for row in rows}
    old_options = '<option>costumes</option><option>characters</option><option>weapons</option><option>companions</option>'
    new_options = ''.join(f'<option value="{f}">{f.replace("_", " ").title()}</option>' for f in FAMILIES if f in present_families)
    (output / "index.html").write_text(page.replace("__DATA__", embedded).replace(old_options, new_options), encoding="utf-8")
    return items


def link_notice_images(output, rows, mapping_file):
    """Link prior notice-source evidence to native PNG alternatives."""
    by_asset = defaultdict(list)
    for row in rows:
        by_asset[row["asset"]].append(row)
    rank = {v: i for i, v in enumerate(("full", "gacha", "large", "standard", "portrait"))}
    linked, unresolved = [], []
    for reference in json.loads(mapping_file.read_text(encoding="utf-8")):
        assets = reference.get("assets", [])
        if len(assets) != 1 or assets[0] not in by_asset:
            unresolved.append(reference["path"])
            continue
        image = min(by_asset[assets[0]], key=lambda r: rank.get(r["variant"], 99))
        linked.append({"website_path": reference["path"], "asset": assets[0], "file": image["file"],
                       "width": image["width"], "height": image["height"], "sha256": image["sha256"],
                       "notice_ids": sorted({o["notice"] for o in reference["observations"]}),
                       "mapping_scope": reference.get("mapping_scope", "named profile artwork"),
                       "mapping_methods": sorted({o["mapping_method"] for o in reference["observations"]})})
    write_json(output / "notice-image-map.json", {
        "description": "Native game artwork alternatives; these are not the original notice website files or frames.",
        "mapped": linked, "unresolved": unresolved})


def export(args):
    if args.python_deps:
        sys.path.insert(0, str(args.python_deps.resolve(strict=True)))
    import UnityPy
    from PIL import Image
    source = bundle_root(args.source)
    output = args.output.resolve()
    if output == source or output.is_relative_to(source):
        raise ValueError("Choose an output directory outside the source data")
    output.mkdir(parents=True, exist_ok=True)
    labels, characters = load_labels(args.labels_db, args.master)
    paths = [(family, path) for family in args.families
             for path in sorted((source / "ui" / FAMILIES[family]).rglob("*.assetbundle"))]
    if not paths:
        raise ValueError("No image bundles found for the selected families")
    expected = len(paths)
    if args.limit is not None:
        paths = paths[:args.limit]
    manifest_path = output / "manifest.json"
    cached = defaultdict(list)
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        for row in old.get("images", []):
            cached[row["bundle"]].append(row)
    rows, errors, skipped = [], [], []
    start = time.monotonic()
    state = {"format": 1, "source_root": str(source), "source_type": "Android Unity/Octo UI asset bundles",
             "libraries": {name: importlib.metadata.version(name) for name in ("UnityPy", "Pillow")},
             "expected_bundles": expected, "processed_bundles": 0, "complete": False,
             "images": rows, "errors": errors, "bundles_without_images": skipped}
    for index, (family, path) in enumerate(paths, 1):
        relative = path.relative_to(source).as_posix()
        directory_asset = path.parent.name
        asset = directory_asset
        label_asset = directory_asset
        source_name = re.fullmatch(r"((?:ch|wp|mw|cm)\d{6}|character\d{6}|consumable\d{6}|important\d{6}|material\d{6}|thought\d{6}|memory\d{3})_(.+)", path.stem)
        if source_name:
            filename_asset, variant = source_name.groups()
            label_asset = filename_asset
            # Some source directories contain an extra bundle named for another
            # item. Keep both addressable paths instead of overwriting its peer.
            if filename_asset != directory_asset:
                asset = directory_asset + "/" + filename_asset
        else:
            variant = path.stem.removeprefix(asset + "_")
            # The dump includes one frame whose filename has an extra zero.
            if family == "memoir_frames" and re.fullmatch(r"memory_frame\d+_(?:full|standard)", path.stem):
                variant = path.stem.rsplit("_", 1)[-1]
        metadata = {"family": family, "asset": asset, "variant": variant,
                    "names": sorted(labels[label_asset]), "characters": sorted(characters[label_asset]),
                    "asset_directory": directory_asset, "named_asset": label_asset}
        try:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            prior = cached.get(relative, [])
            valid_cache = prior and all(r.get("source_sha256") == digest and r["asset"] == asset and r["variant"] == variant and
                                       (output / r["file"]).resolve().is_relative_to(output) and
                                       (output / r["file"]).is_file() and sha256(output / r["file"]) == r["sha256"] for r in prior)
            if valid_cache:
                rows.extend({**r, **metadata} for r in prior)
            else:
                env = UnityPy.load(unmask(raw, relative))
                sprites = [o for o in env.objects if o.type.name == "Sprite"]
                objects = sprites or [o for o in env.objects if o.type.name == "Texture2D"]
                if not objects:
                    skipped.append(relative)
                for obj in objects:
                    data = obj.read()
                    image = data.image
                    suffix = "" if len(objects) == 1 else "__" + safe_name(data.m_Name) + "-" + str(obj.path_id)
                    target = output / family / asset / (safe_name(path.stem) + suffix + ".png")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    image.save(target, "PNG", compress_level=4)
                    rows.append({**metadata, "file": target.relative_to(output).as_posix(), "width": image.width,
                                 "height": image.height, "mode": image.mode, "texture": data.m_Name,
                                 "object_type": obj.type.name, "object_id": obj.path_id,
                                 "has_transparency": "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255,
                                 "bundle": relative, "source_sha256": digest, "sha256": sha256(target), "bytes": target.stat().st_size})
                del env
        except Exception as error:
            errors.append({"bundle": relative, "error": str(error)})
        state["processed_bundles"] = index
        if index % 100 == 0 or index == len(paths):
            write_json(manifest_path, state)
            print(f'{index}/{len(paths)} bundles; {len(rows)} PNGs; {len(errors)} errors', flush=True)
    # Verify actual saved PNG bytes and pixels before producing the final catalog.
    for row in rows:
        file = output / row["file"]
        assert sha256(file) == row["sha256"], str(file)
        with Image.open(file) as image:
            image.load()
            assert image.size == (row["width"], row["height"]), str(file)
    items = make_gallery(output, rows, Image)
    make_preview(output, rows, Image)
    if args.notice_mapping:
        link_notice_images(output, rows, args.notice_mapping)
    state.update(complete=not errors and len(paths) == expected, validated_images=len(rows),
                 image_counts=dict(Counter(r["family"] for r in rows)),
                 asset_counts=dict(Counter(r["family"] for r in items)),
                 elapsed_seconds=round(time.monotonic()-start, 1))
    write_json(manifest_path, state)
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["family", "asset", "name", "character", "variant", "file", "width", "height", "sha256", "source_bundle"])
        writer.writerows([r["family"], r["asset"], " / ".join(r["names"]), " / ".join(r["characters"]), r["variant"],
                          r["file"], r["width"], r["height"], r["sha256"], r["bundle"]] for r in rows)
    (output / "README.txt").write_text(
        "Native game artwork exported from preserved Android data.\nOpen index.html for the offline gallery.\n"
        "The family/asset folders contain PNG images at their native sprite dimensions, preserving transparency.\n"
        "Every available variant is exported. Some NPCs/assets have only icons or battle art, not full illustrations.\n"
        "Sprite rectangles are preferred over padded texture atlases. No AI upscaling or invented artwork is used.\n"
        "Names come from the preserved English text/master data where available; asset IDs are retained for unnamed images.\n"
        "These are game-native images, not byte-exact replacements for differently framed notice website images.\n"
        "manifest.json records each source bundle, dimensions and source/output SHA-256. manifest.csv is a flat catalog.\n"
        "Previews are smaller WebPs for browsing; download the original PNG for the native resolution.\n"
        "Original artwork belongs to Square Enix/Applibot and the respective collaboration rights holders.\n", encoding="utf-8")
    if args.zip:
        archive_path = args.zip.resolve()
        if archive_path.is_relative_to(output):
            raise ValueError("Place the ZIP outside the image directory")
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        delivered = [output / r["file"] for r in rows] + [output / r["preview"] for r in items]
        delivered += [output / n for n in ("manifest.json", "manifest.csv", "README.txt", "index.html", "preview.jpg")]
        if args.notice_mapping:
            delivered.append(output / "notice-image-map.json")
        with zipfile.ZipFile(archive_path, "w") as archive:
            for file in delivered:
                archive.write(file, file.relative_to(output).as_posix(),
                              compress_type=zipfile.ZIP_STORED if file.suffix in (".png", ".webp") else zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
        state_summary = {k: state[k] for k in ("complete", "processed_bundles", "validated_images", "image_counts", "asset_counts", "elapsed_seconds")}
        write_json(archive_path.with_suffix(".json"), {**state_summary, "file": archive_path.name,
                                                     "bytes": archive_path.stat().st_size, "sha256": sha256(archive_path)})
    print(json.dumps({k: state[k] for k in ("complete", "processed_bundles", "validated_images", "image_counts", "asset_counts", "elapsed_seconds")}, indent=2))
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("inputs/asset-images"))
    parser.add_argument("--labels-db", type=Path, help="Preserved archive.db with the English text table")
    parser.add_argument("--master", type=Path, help="Directory containing decrypted master JSON tables")
    parser.add_argument("--python-deps", type=Path, help="Optional directory containing UnityPy/Pillow")
    parser.add_argument("--families", nargs="+", choices=FAMILIES, default=list(DEFAULT_FAMILIES))
    parser.add_argument("--limit", type=int, help="Export a sample; the manifest remains marked incomplete")
    parser.add_argument("--zip", type=Path, help="Optional portable ZIP destination, outside --output")
    parser.add_argument("--notice-mapping", type=Path, help="Optional prior profile-artwork-mapping.json to link notice artwork")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    return export(args)


if __name__ == "__main__":
    raise SystemExit(main())
