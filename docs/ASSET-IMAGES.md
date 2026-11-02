# Native artwork exported from the Android data

Historical APK sprites and the shared Drive database scan are documented in
[HISTORICAL-DATA-RECOVERY.md](HISTORICAL-DATA-RECOVERY.md).

The local library is `inputs/asset-images/index.html`; the portable download is
`inputs/bunker-asset-images.zip` (about 550 MiB). It contains **5,095 PNGs**:

| Family | Assets | Image variants |
| --- | ---: | ---: |
| Character portraits | 33 | 33 |
| Costumes | 483 | 2,982 |
| Weapons | 641 | 1,921 |
| Companions | 53 | 159 |

An additional item library at `inputs/item-images/index.html`, packaged as
`inputs/bunker-item-images.zip`, contains **2,927 PNGs**: 1,081 consumable
variants, 409 important items, 788 materials, 288 memoir variants, 180 memoir
frame variants and 181 debris images. Its manifest preserves source identity
even when a bundle contains an unexpectedly named sprite. All images decoded
and passed the same dimension/checksum checks, with zero extraction errors.

The separate `inputs/bunker-historical-apk-artwork.zip` contains 4,055 sprites
from three older APKs, with version-specific galleries and provenance. See
the historical recovery report linked above for scope and source details.

These are existing 2D illustrations, portraits, icons and battle images decoded
from the preserved Android Unity asset bundles. They retain native sprite
dimensions and transparency. Full illustrations are available for some assets;
others have only icons or battle images. This export does not invent missing
views, upscale images or render new views of 3D models.

The gallery searches English names, character names and asset IDs, filters by
family, and offers every exported variant. It includes smaller WebP previews;
the download control links to the native PNG. All gallery data and image links
are local, so the extracted ZIP can be browsed without an external service.

`manifest.json` records the bundle path, sprite/object identity, native image
dimensions, transparency, source-bundle SHA-256 and PNG SHA-256. `manifest.csv`
provides a flat catalog. English labels come from the preserved text and master
tables where available; unnamed entries retain their asset IDs.

Every one of the 5,095 source bundles produced an image, with zero extraction
errors or bundles lacking images. Every PNG was fully decoded again and checked
against its recorded dimensions and checksum. The ZIP's CRCs were also checked.
The gallery's search, filters, pagination, image dialog and variant selection
were exercised in a browser.

To reproduce the export with Python, install UnityPy and Pillow into a scoped
dependency directory. The checked runtime used UnityPy 1.25.4 and Pillow 13.0.0.

```powershell
python -m pip install --target .build/asset-image-python UnityPy==1.25.4 Pillow==13.0.0
python scripts/export_asset_images.py --source C:/path/to/android-dump --labels-db C:/path/to/archive.db --master C:/path/to/master --python-deps .build/asset-image-python --output inputs/asset-images --zip inputs/bunker-asset-images.zip
```

`--source` also accepts the `revisions/0` or `assetbundle` directory. Labels and
master tables are optional; image extraction still works without them. Use
`--families costumes weapons companions` to select families. `--limit 5` makes
an explicitly incomplete sample. A resumed run reuses files only when both the
source and PNG checksums still match.

For notice recovery, these images are supplemental game artwork. The notice
website sometimes used different framing, crops or dimensions, so an exported
sprite alone does not establish the bytes of a missing website image.
The local `notice-image-map.json` links the prior audit's 101 profile paths to
these PNGs: 98 specific artwork mappings and three character-identity portrait
references. Reproduce this extra index with
`--notice-mapping .build/notice-audit/profile-artwork-mapping.json`.
