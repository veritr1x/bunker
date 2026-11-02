# Historical regional UI image versions

This collection preserves 143 PNG file occurrences from the eleven update
folders currently listed under `assets_latest` in the user's supplied
[public Drive source](https://drive.google.com/drive/folders/1I9j0aFjVQ4m3hqQcW6uJGbE9imAVyIsW).
The downloads contain 137 distinct file payloads. English, Japanese and Korean
paths and update-folder labels remain separate.

Open `inputs/historical-drive-ui/index.html` for the comparison reader.
`inputs/bunker-historical-ui-versions.zip` contains the original community PNG
exports, their source metadata, and the matching current native textures.

## Six visibly different files

Folder **794** supplies two image families in each of three locales:

- `mom_banner_main_quest_mom_banner_03_05.png`;
- `prm015.png`.

Their chapter wording is **Satellite** in English, **衛星** in Japanese, and
**위성** in Korean. The same-path current native textures use **Cherished
Memories**, **大切ナ記憶**, and **소중한 기억**, respectively. All six pairs were
reviewed visually. These are two native UI designs in three locales, not six
new illustrations or six original website notices.

The current global `MomBannerId` 864 links the home-banner asset to notice
1589. That current master row and its source hash are preserved as context.
It does not prove that a particular earlier graphic was served at an original
website URL. The community folder labels are not independently authenticated
game client versions or publication dates.

## Inventory and pixel comparison

The public metadata walk covers eleven update roots, eleven UI-family lists,
fourteen banner/promotion family lists, and sixty-four regional/intermediate
and image-leaf listings. There are **41 PNG-bearing leaf folders**, and none
of the queried inventories reached the initial 50-entry truncation boundary.
Every one of their 143 PNG file occurrences was downloaded and decoded.
Other asset families in those update folders are outside this pass.

All files were compared with Texture2D exports from the same filename,
family and locale in the preserved Android resource tree: 137 native bundle
paths in total. The comparison includes alpha and premultiplied RGB, so hidden
transparent colors do not falsely establish a visible artwork change.

Apart from the six changed-wording files, **137 file occurrences** differ only
by rendered channel values of at most 2/255. None is an exact PNG-byte or RGBA
match. These small export differences are retained as such; they are not
counted as additional recovered designs. The comparison preserves hashes,
dimensions, maximum and mean rendered-channel differences and changed-pixel
counts for every occurrence.

The reader defaults to the six changed files. Filters expose all 143 source
occurrences or just the 137 minor-difference comparisons. All source PNGs and
137 current native texture files are included unmodified, with their paths
and provenance. The one reader page has 576 checked local references and no
broken local links. All 280 image file paths fully decode and match their
recorded hashes.

The HTML reader needs only a browser. The portable validator requires Python,
Pillow and NumPy; run `tools/validate_remaining_ui_packet.py --kind historical
--folder .` after extracting the ZIP. It checks every image and recomputes all
143 pixel comparisons. Capture helpers retain working-session paths and
require configuration to read the original resource dump.

No exact missing website image path is marked recovered. The original and
951-notice candidate packs remain unchanged; these older native versions stay
in a separate source collection.
