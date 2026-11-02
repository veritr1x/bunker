#!/usr/bin/env python3
"""Compare a notice pack with saved Guide and preservation-source records.

This is an offline audit. It keeps missing original files separate from blank
thumbnails, social-post stand-ins and supplemental artwork extracted from the game.
Fetch the pinned pack with scripts/notices.py.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ImagePaths(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.paths = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            path = canonical_image_path(dict(attrs).get("src", ""))
            if path:
                self.paths.append(path)
        for name, value in attrs:
            if name == "style" and value:
                for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", value, re.IGNORECASE):
                    path = canonical_image_path(match[2])
                    if path:
                        self.paths.append(path)


def canonical_image_path(value):
    """Normalize archived absolute URLs and duplicate slashes, retaining language."""
    if value.startswith(("/https://", "/http://")):
        value = value[1:]
    url = urlsplit(value)
    if url.netloc and url.hostname != "web.app.nierreincarnation.com":
        return ""
    path = re.sub(r"/+", "/", url.path)
    return path if path.startswith("/images/") and path.rsplit("/", 1)[-1] else ""


def image_key(path):
    leaf = path.rsplit("/", 1)[-1]
    if re.fullmatch(r"[a-f0-9]{64}", leaf):
        return leaf
    return "c_" + hashlib.sha1(path.encode()).hexdigest()[:16]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def recovery_file(value, sources):
    """Resolve local manifests and portable paths in an unpacked source corpus."""
    path = Path(value)
    return next((p for p in (path, sources / path, sources.parent / path) if p.is_file()), None)


def verified_recoveries(sources):
    """Only count files that still exist and match their recorded SHA-256."""
    rows = []
    for name in ("recovered-images.json", "additional-recovered-images.json",
                 "availability-image-replays.json", "remaining-cdx-image-replays.json",
                 "browser-recovered-images.json", "background-recovered-images.json"):
        path = sources / name
        if path.is_file():
            rows.extend(read_json(path))
    for path in (sources / "image-replay-cache").glob("*.json"):
        rows.append(read_json(path))
    manifest = sources / "image-manifests.json"
    if manifest.is_file():
        rows.extend(read_json(manifest).get("original", []))
    verified = {}
    for row in rows:
        if not row.get("file") or not row.get("sha256"):
            continue
        path = recovery_file(row["file"], sources)
        if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]:
            verified[row["key"]] = row
    return verified


def audit(pack, sources):
    sources = Path(sources)
    with zipfile.ZipFile(pack) as archive:
        index = json.loads(archive.read("notices.json"))
        names = set(archive.namelist())
    notices = {n["id"]: n for n in index["notices"]}
    guide = read_json(sources / "guide-all-details.json")
    guide_ids = {n["notification_id"] for n in guide}
    inventory = {}
    source_files = [sources / "guide-all-details.json", *sorted((sources / "archive-pages").glob("*.json"))]
    for file in source_files:
        data = read_json(file)
        rows = data if isinstance(data, list) else data["props"]["pageProps"].get("notifications", [])
        for notice in rows:
            ident = notice["notification_id"]
            references = [(path, "body") for path in ImagePaths(notice.get("body", "")).paths]
            thumb = canonical_image_path(notice.get("thumbnail_path") or "")
            if thumb:
                references.append((thumb, "thumbnail"))
            for path, role in references:
                key = image_key(path)
                if f"img/{key}.webp" in names:
                    continue
                row = inventory.setdefault(path, {"key": key, "roles": set(), "notice_ids": set(), "sources": set()})
                row["roles"].add(role)
                row["notice_ids"].add(ident)
                row["sources"].add(str(file))

    pack_references = set()
    original_pack_references = []
    for notice in notices.values():
        if notice.get("thumb"):
            pack_references.add("img/" + notice["thumb"] + ".webp")
        pack_references.update(re.findall(r"img/[A-Za-z0-9_-]+\.webp", notice["body"]))
        original_paths = sorted(set(ImagePaths(notice["body"]).paths))
        if original_paths:
            original_pack_references.append({"id": notice["id"], "paths": original_paths})
            for path in original_paths:
                key = image_key(path)
                if f"img/{key}.webp" not in names:
                    row = inventory.setdefault(path, {"key": key, "roles": set(), "notice_ids": set(), "sources": set()})
                    row["roles"].add("body")
                    row["notice_ids"].add(notice["id"])
                    row["sources"].add(str(pack) + "!notices.json")
    recovered = verified_recoveries(sources)
    originals = []
    for path, row in sorted(inventory.items()):
        originals.append({"path": path, **{k: sorted(v) if isinstance(v, set) else v for k, v in row.items()},
                          "recovered": row["key"] in recovered})
    game = read_json(sources / "game-banners/manifest.json") if (sources / "game-banners/manifest.json").exists() else []
    if not game and (sources / "image-manifests.json").is_file():
        game = read_json(sources / "image-manifests.json").get("game", [])
    promotion_path = sources / "verified-promotion-banners.json"
    promotions = read_json(promotion_path) if promotion_path.is_file() else []
    if (sources / "image-manifests.json").is_file():
        promotions = read_json(sources / "image-manifests.json").get("promotions", promotions)
    game = [*game, *promotions]
    verified_game = []
    for row in game:
        path = recovery_file(row["file"], sources) if row.get("file") else None
        if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() == row.get("sha256"):
            verified_game.append(row)
    game = verified_game
    profile_path = sources / "profile-game-artwork/manifest.json"
    profiles = read_json(profile_path) if profile_path.is_file() else []
    if not profiles and (sources / "image-manifests.json").is_file():
        profiles = read_json(sources / "image-manifests.json").get("profiles", [])
    verified_profiles = []
    for row in profiles:
        path = recovery_file(row["file"], sources) if row.get("file") else None
        if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() == row.get("sha256"):
            verified_profiles.append(row)
    icon_manifest = sources / "native-notice-icons/manifest.json"
    icons = read_json(icon_manifest) if icon_manifest.is_file() else []
    if not icons and (sources / "image-manifests.json").is_file():
        icons = read_json(sources / "image-manifests.json").get("native_icons", [])
    verified_icons = []
    for row in icons:
        path = recovery_file(row["file"], sources) if row.get("file") else None
        if path is not None and hashlib.sha256(path.read_bytes()).hexdigest() == row.get("sha256"):
            verified_icons.append(row)
    game_notices = {ident for row in game for ident in row["notices"]}
    stand_ins = {n["id"] for n in notices.values() if "stand-in" in n["body"]}
    thumb_styles = Counter()
    for n in guide:
        if not n.get("thumbnail_path") or n["notification_id"] not in notices:
            continue
        thumb = notices[n["notification_id"]].get("thumb", "")
        style = ("blank" if not thumb else "social_post_stand_in" if thumb.startswith("tw_") else
                 "source_thumbnail" if thumb == image_key(canonical_image_path(n["thumbnail_path"])) else
                 "another_packed_image")
        thumb_styles[style] += 1
    return {
        "pack": {"notice_count": len(notices), "image_count": sum(n.endswith(".webp") for n in names),
                 "broken_local_image_references": sorted(pack_references - names),
                 "unmapped_original_image_references": original_pack_references,
                 "blank_thumbnails": sum(not n.get("thumb") for n in notices.values()),
                 "stand_in_notices": sorted(stand_ins)},
        "guide": {"notice_count": len(guide), "missing_from_pack": sorted(guide_ids - notices.keys()),
                  "pack_only": sorted(notices.keys() - guide_ids), "thumbnail_styles_in_pack": dict(thumb_styles)},
        "original_images": {"missing_from_pack": len(originals),
                            "roles": dict(Counter("+".join(row["roles"]) for row in originals)),
                            "validated_recovered_files": len(recovered),
                            "unrecovered_original_paths": sum(not row["recovered"] for row in originals),
                            "inventory": originals},
        "game_artwork": {"validated_textures": len(game), "notice_ids": sorted(game_notices),
                         "stand_in_notices_with_game_art": sorted(stand_ins & game_notices),
                         "stand_in_notices_without_game_art": sorted(stand_ins - game_notices)},
        "profile_artwork": {"validated_textures": len(verified_profiles),
                            "mapped_original_paths": sorted({p for row in verified_profiles
                                                              if row.get("mapping_scope") != "character identity only"
                                                              for p in row["original_paths"]}),
                            "entity_portrait_paths": sorted({p for row in verified_profiles
                                                              if row.get("mapping_scope") == "character identity only"
                                                              for p in row["original_paths"]}),
                            "notice_ids": sorted({i for row in verified_profiles for i in row["notice_ids"]})},
        "item_artwork": {"validated_textures": len(verified_icons),
                         "mapped_original_paths": sorted({p for row in verified_icons if row["scope"] == "global"
                                                          for p in row["original_paths"]}),
                         "contextual_mapped_paths": sorted({p for row in verified_icons if row["scope"] == "notice"
                                                            for p in row["original_paths"]}),
                         "contextual_mappings": [{"paths": row["original_paths"], "notice_ids": row["notice_ids"],
                                                  "asset": row["asset"]} for row in verified_icons if row["scope"] == "notice"],
                         "notice_ids": sorted({i for row in verified_icons for i in row["notice_ids"]})},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=ROOT / "inputs/bunker-notices.zip")
    parser.add_argument("--sources", type=Path, default=ROOT / ".build/notice-audit")
    parser.add_argument("--output", type=Path, default=ROOT / ".build/notice-audit/audit.json")
    args = parser.parse_args()
    result = audit(args.pack, args.sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"pack_notices": result["pack"]["notice_count"],
                      "missing_notice_ids": result["guide"]["missing_from_pack"],
                      "missing_original_paths": result["original_images"]["missing_from_pack"],
                      "recovered_original_files": result["original_images"]["validated_recovered_files"],
                      "game_art_notices": len(result["game_artwork"]["notice_ids"])}, indent=2))


if __name__ == "__main__":
    main()
