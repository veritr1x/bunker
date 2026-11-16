#!/usr/bin/env python3
"""Recreates the Mama's News images the game files lack in English and Korean.

Mama's News (m_dokan) pages each show an image, ui)mom_promotion)<lang>)banner)prm<id>.
Bunker's calendar restores the 2021 welcome-back pages for returning players
(m_dokan 51) whose two images survive only in Japanese, so the game drew them
pink. prm219 (the gifts, no text) is the Japanese image as it is, and the
Japanese-only pages of global events (prm9004, prm1072, prm1073) take the English
images; Bunker's server builds those by renaming bundles (translation/banners.go).
prm218 says "Comeback Campaign" in Japanese: its text is painted out (OpenCV
inpainting) and the "Welcome Back / Campaign" text of the game's later
welcome-back image of the same design (prm462) is lifted off its background and
laid in, for each language.

Writes promotion/<lang>/prm218.astc (ASTC 6x6, rows bottom first, the size of the
image's texture) and a PNG to look at.

  recreate_promotions.py --dump resource_dump_android.7z --assets DIR --out DIR

Needs UnityPy, Pillow, numpy, opencv-python and astc-encoder-py; bundles are extracted with 7zz.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

LANGUAGES = ("en", "ko")
TARGET, DONOR = 218, 462
SOURCE = "ja"
TEXT_BAND = {"target": (205, 350), "donor": (190, 352)}  # rows holding each image's title text
SIDES = (20, 700)


def rel(lang, image):
    return f"ui/mom_promotion/{lang}/banner/prm{image:03d}.assetbundle"


def text_mask(rgb, band, sides=SIDES, thresh=45):
    """The title text's pixels in band: brighter than the blurred background, grown to its glow."""
    import cv2
    region = np.zeros(rgb.shape[:2], bool)
    region[band[0]:band[1], sides[0]:sides[1]] = True
    background = cv2.medianBlur(rgb.astype(np.uint8), 31).mean(2)
    mask = region & (rgb.mean(2) - background > thresh)
    return cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=2).astype(bool) & region


def erase(rgb, mask):
    import cv2
    return cv2.inpaint(rgb.astype(np.uint8), mask.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA).astype(float)


def swap_title(target, donor):
    """target (RGBA, top row first) with its title text replaced by donor's, which is drawn in the same place."""
    target, donor = target.astype(float), donor.astype(float)
    clean = erase(target[..., :3], text_mask(target[..., :3], TEXT_BAND["target"]))
    mask = text_mask(donor[..., :3], TEXT_BAND["donor"])
    text = np.clip(donor[..., :3] - erase(donor[..., :3], mask), 0, None) * mask[..., None]
    out = target.copy()
    out[..., :3] = np.clip(clean + text, 0, 255)
    return out


def texture(assets: Path, path: str):
    import UnityPy
    from export_asset_images import unmask
    env = UnityPy.load(unmask((assets / path).read_bytes(), path))
    return np.asarray(next(o.read().image for o in env.objects if o.type.name == "Texture2D").convert("RGBA"))


def main():
    from PIL import Image
    import recreate_banners as rb
    from build_event_notices import extract
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump", type=Path, required=True, help="resource_dump_android.7z")
    parser.add_argument("--assets", type=Path, required=True, help="Where its bundles go: DIR/revisions/0/assetbundle")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    wanted = [rel(SOURCE, TARGET)] + [rel(lang, DONOR) for lang in LANGUAGES]
    extract(args.dump, args.assets, [w for w in wanted if not (args.assets / w).exists()])
    target = texture(args.assets, rel(SOURCE, TARGET))
    made = {}
    for lang in LANGUAGES:
        image = swap_title(target, texture(args.assets, rel(lang, DONOR)))
        data = rb.encode_astc(image)
        height, width = image.shape[:2]
        if len(data) != rb.astc_size(width, height):
            raise SystemExit(f"{lang}: {len(data)} bytes of ASTC, want {rb.astc_size(width, height)}")
        folder = args.out / "promotion" / lang
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"prm{TARGET}.astc").write_bytes(data)
        Image.fromarray(image.astype(np.uint8), "RGBA").save(args.out / f"prm{TARGET}_{lang}.png")
        made[lang] = len(data)
    print(json.dumps(made))


if __name__ == "__main__":
    main()
