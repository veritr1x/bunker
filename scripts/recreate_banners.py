#!/usr/bin/env python3
"""Recreates event banners that no game file or archive kept, for the notice pack.

Record: Garden of Benediction's first run (August 2021) had banner 512. The
live game redrew 512 for the January 2022 rerun ("Resurrected Event Quests")
under the same number, so the 2021 drawing is gone: the resource dump keeps
one copy of each file, and no archive found (nierrein.guide, the NieR wiki, a
2022 asset archive) has it. Its home-screen strip (ui/mom_banner) and the
Japanese banner were never redrawn and still say "Event Quests".

The recreation is the redrawn banner with its subtitle line replaced by the
same line from a banner of the same template and time (Sunset Port's, 509):
the old line is painted out (OpenCV inpainting), and the other banner's text,
lifted off its own background, is laid in its place at the brightness of the
line it replaces. Nothing else changes.

Writes, for each language that needs it, banners/<lang>/event_banner_900.astc
(the texture as the game stores it: ASTC 6x6, rows bottom first, the size of
banner 512's) and a PNG to look at. Bunker's server wraps the .astc into a
bundle built from the player's own banner 512 (translation/banners.go).

  recreate_banners.py --assets DUMP/revisions/0/assetbundle --out DIR

Needs UnityPy, Pillow, numpy, opencv-python and astc-encoder-py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

RECREATED = 900
# language -> (banner to fix, banner whose subtitle it takes); Japanese 512 was never redrawn.
RECIPES = {"en": (512, 509), "ko": (512, 509)}
WIDTH, HEIGHT, BLOCK = 402, 490, 6
INNER = (8, 394)  # inside the frame


def banner(assets: Path, lang: str, number: int):
    """A banner's pixels (RGBA, top row first) from the dump."""
    import UnityPy
    from export_asset_images import unmask
    rel = f"ui/quest/{lang}/banner/event_banner_{number}.assetbundle"
    env = UnityPy.load(unmask((assets / rel).read_bytes(), rel))
    image = next(o.read().image for o in env.objects if o.type.name == "Texture2D")
    return np.asarray(image.convert("RGBA")).astype(float)


def text_bands(rgba, inner=INNER, bright=150):
    """The rows holding bright text, as (first, past last) bands, top to bottom."""
    lum = rgba[..., :3].mean(2) * (rgba[..., 3] / 255)
    rows = (lum[:, inner[0] + 52:inner[1] - 52] > bright).sum(1)
    out, start = [], None
    for y, count in enumerate(rows):
        if count > 3 and start is None:
            start = y
        if count <= 3 and start is not None:
            if y - start >= 3:
                out.append((start, y))
            start = None
    return out


def _text_mask(rgb, band, inner, thresh=40, pad=4):
    import cv2
    region = np.zeros(rgb.shape[:2], bool)
    region[band[0] - pad:band[1] + pad, inner[0]:inner[1]] = True
    background = cv2.medianBlur(rgb.astype(np.uint8), 31).mean(2)
    mask = region & (rgb.mean(2) - background > thresh)
    return cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8), iterations=2).astype(bool) & region


def _erase(rgb, mask):
    import cv2
    return cv2.inpaint(rgb.astype(np.uint8), mask.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA).astype(float)


def swap_subtitle(target, donor, inner=INNER):
    """target with its last text line (the subtitle) replaced by donor's."""
    tband, dband = text_bands(target, inner)[-1], text_bands(donor, inner)[-1]
    tm, dm = _text_mask(target[..., :3], tband, inner), _text_mask(donor[..., :3], dband, inner)
    tbg, dbg = _erase(target[..., :3], tm), _erase(donor[..., :3], dm)
    text = np.clip(donor[..., :3] - dbg, 0, None) * dm[..., None]
    old = np.percentile(np.clip(target[..., :3] - tbg, 0, None).mean(2)[tm], 99)
    new = np.percentile(text.mean(2)[dm], 99)
    text *= min(max(old / new, 0.8), 1.6)
    ty, tx = np.nonzero(tm)
    dy, dx = np.nonzero(dm)
    shift_y = int(round((ty.min() + ty.max()) / 2 - (dy.min() + dy.max()) / 2))
    shift_x = int(round((tx.min() + tx.max()) / 2 - (dx.min() + dx.max()) / 2))
    text = np.roll(np.roll(text, shift_y, 0), shift_x, 1)
    out = target.copy()
    out[..., :3] = np.clip(tbg + text, 0, 255)
    return out


def encode_astc(rgba) -> bytes:
    """ASTC 6x6 blocks as Unity stores a texture: bottom row first."""
    from astc_encoder import ASTCConfig, ASTCContext, ASTCImage, ASTCProfile, ASTCSwizzle, ASTCType
    flipped = np.ascontiguousarray(rgba[::-1].astype(np.uint8))
    height, width = flipped.shape[:2]
    context = ASTCContext(ASTCConfig(ASTCProfile.LDR, BLOCK, BLOCK, 1, 100))
    return context.compress(ASTCImage(ASTCType.U8, width, height, 1, flipped.tobytes()), ASTCSwizzle.from_str("RGBA"))


def astc_size(width=WIDTH, height=HEIGHT):
    return -(-width // BLOCK) * -(-height // BLOCK) * 16


def main():
    from PIL import Image
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", type=Path, required=True, help="The dump's revisions/0/assetbundle folder")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    made = {}
    for lang, (target, donor) in RECIPES.items():
        image = swap_subtitle(banner(args.assets, lang, target), banner(args.assets, lang, donor))
        data = encode_astc(image)
        if len(data) != astc_size():
            raise SystemExit(f"{lang}: {len(data)} bytes of ASTC, want {astc_size()}")
        folder = args.out / "banners" / lang
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"event_banner_{RECREATED}.astc").write_bytes(data)
        Image.fromarray(image.astype(np.uint8), "RGBA").save(args.out / f"event_banner_{RECREATED}_{lang}.png")
        made[lang] = len(data)
    print(json.dumps(made))


if __name__ == "__main__":
    main()
