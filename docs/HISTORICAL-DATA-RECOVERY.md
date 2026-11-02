# Historical APK and shared Drive recovery

Inspected on 2026-11-01. This evidence supplements the notice recovery work;
the published notice pack and its lock are unchanged.

## Older APKs

Downloaded three global Android APKs from APKMirror:

| Version | Code | APK bytes | Exported sprites |
| --- | ---: | ---: | ---: |
| 1.5.7 | 10 | 99,924,598 | 1,161 |
| 2.2.1 | 68 | 111,914,660 | 1,291 |
| 2.12.0 | 105 | 119,031,501 | 1,603 |

The APKs are in `inputs/historical-apks/`. `source-manifest.json` records
download pages, versions, hashes and certificate checks. Android's `apksigner`
verified all three with certificate SHA-256
`8575d97a796e08f9fe8887c3d83ab78c5275ba4a691494ed47f566abdac5e495`.
Their ZIP checksums were checked. No APK was installed or run.

The portable artwork package is `inputs/bunker-historical-apk-artwork.zip`
(101,658,050 bytes). Its 4,106 members passed ZIP CRC checks; every archived
PNG and raw text file was checked against its manifest SHA-256.

Static Unity extraction produced **4,055 PNGs**, representing **2,605 distinct
PNG hashes**, and 36 selected text assets. Of those distinct images, 1,011
occur in the older two versions and are absent from the 2.12.0 sprite export.
This compares these three APKs, not every asset in the final game dump.
Images include maintenance banners, UI controls, status icons, ranks and
summon presentation graphics. The separate character, costume, weapon and
companion export remains the main illustrated asset library.

Each version has a searchable `artwork/<version>/index.html`, PNGs, selected
raw text, and a manifest identifying the APK hash, Unity serialized file,
object ID, image dimensions and PNG hash. All PNGs decoded successfully,
with zero extraction errors. The launch gallery's search and image loading
were checked in a browser. `english-ui-text.json` contains identified English
bootstrap/UI text: 1,372 distinct keys across the three versions, 109 absent
from the preserved final text database. Some are obsolete or translation
placeholders; they are not automatically substituted for current text.

Reproduce a version's export with the scoped UnityPy/Pillow dependencies used
by `scripts/export_asset_images.py`:

```powershell
python scripts/export_apk_images.py inputs/historical-apks/nier-global-1.5.7-10.apk --output inputs/historical-apks/artwork/1.5.7 --scratch .build/historical-apks/1.5.7 --python-deps .build/notice-audit/python
```

## User-supplied shared Drive

The later [Japanese APK pass](JAPANESE-APK-RECOVERY.md) separately preserves
verified JP builds 1.0.3, 2.12.1 and 3.7.1. Its 4,448 sprite files include 897
distinct decoded RGBA images absent from the three global APK exports above.
The final build also supplies the exact named native Karma badge referenced
by notice 1439; it is a native alternative with original website bytes still
unverified.

Source: [Nier Reincarnation shared folder](https://drive.google.com/drive/folders/1I9j0aFjVQ4m3hqQcW6uJGbE9imAVyIsW).
Its public README identifies extracted assets, raw Unity bundles, historical
databases, community contributions and videos. Public metadata and downloads
were accessible without authentication.

The [global binary master folder](https://drive.google.com/drive/folders/1skvq4O7OfPh8zUJ_cWn0qqOgCOglDApt)
provided **660 snapshots**, from `20210408232257.bin.e` through
`20240404193219.bin.e`. Both complete download ZIPs are preserved under
`inputs/shared-drive-recovery/archives/` (3,853,485,671 bytes together).
There are 379 distinct binary hashes; several timestamped files are identical.
Every member's ZIP CRC was checked. All 660 decrypted and decompressed
successfully for the banner scan.

Decoding used pinned lunar-base revision
`b39154099b8f09f5926239e5838abc37260b9b9b`, specifically its
[`tools/dump_masterdata.py`](https://github.com/NMeliksah/lunar-base/blob/b39154099b8f09f5926239e5838abc37260b9b9b/tools/dump_masterdata.py).
Raw positional rows retain their historical widths; they are not silently
assigned all columns of the final schema.

The complete scan extracted `m_mom_banner` and `m_dokan` from every snapshot
and inventoried table names. It found 1,097 distinct banner row versions across
855 banner IDs. All IDs survive in the final snapshot, but targets, dates or
artwork names sometimes changed. **30 announcement target IDs are absent from
the final banner table**; 19 are also absent from the 951-notice candidate pack.
These are discovery clues, not recovered notice bodies. Some targets were
corrected or reassigned, and values such as 999 and 9999 are placeholder-like.
Independent body, title and date evidence is still needed.

For example, banner 2 points to target 12 in some launch snapshots and target
156 in the final snapshot. Its asset name stays `event_mom_banner_500`.
No new notice body or exact missing website image was established by this scan.

Twenty-eight selected snapshots also have raw character, costume, weapon,
companion, catalog, item and quest table extracts. Costume first-column ID
33004 occurs in prelaunch snapshots and disappears later; its skeleton and
variation match the final Fio/Abyssal Girl record 34026. This is historical ID
evidence, not an additional character illustration.

The Drive's **379 English home-banner filenames** and **863 English promotion
banner filenames** all have counterparts in the existing Android dump.
This establishes filename coverage, not byte equality. The information banner
was downloaded as an additional sample. `assets/grpcs` contains a certificate
text file, not saved API responses. Community 3D collections, Japanese/Korean
artwork, videos and the remainder of the raw-asset tree were not exhaustively
downloaded or compared by this pass.

## Saved evidence

Under `inputs/shared-drive-recovery/`:

- `history-scan-summary.json`: archive hashes, counts and scan errors (none).
- `all-snapshot-manifest.json`: SHA-256 and table counts for all 660 snapshots.
- `global-snapshot-inventory.json`: observed public Drive file IDs and names.
- `banner-history/`: decoded banner/dokan rows and table-name inventories.
- `historical-banners.json`: distinct rows with first/last observed snapshots.
- `historical-announcement-targets.json`: historical target and asset links.
- `announcement-targets-removed-from-final.json`: 30 changed-target clues and
  their presence or absence in the candidate notice pack.
- `decoded/`: broader raw table extracts for the 28 selected snapshots.

Scoped inspection scripts, public folder listings and download evidence are
also retained under `.build/notice-audit/`. The remaining original website
image gap is unchanged at 764 paths; native game artwork remains supplemental.

## Additional preservation inventory

The [iOS resource archive](https://archive.org/details/nier_reincarnation_assets)
was inventoried using 1,992,115 bytes of bounded range reads rather than a full
14.9 GB download. Its 245,950 entries contain 202,709 files. All 200,801
revision-zero Unity bundle paths match the local Android dump; no additional
bundle path or Crow shard icon was found. This compares filenames, not bytes
or platform texture formats.

The archive also contains 819 `info.json` deduplication maps and 819 native
Octo `list.bin` files across revision folders 0–818. The folder numbers alone
do not establish independent historical snapshots. Their solid-compression block boundaries
are inventoried in `.build/notice-audit/ios-resource-solid-blocks.json`.
Selected folders 790, 800, 810 and 818 have now been extracted and decoded.
All four native lists report database revision 818; their deduplication maps
point to existing revision-zero files, and no new bundle path was found.
See [the validation and interpretation](WAYBACK-CONTINUATION.md). Catalog
references and surviving downloadable asset bytes remain separate evidence.

A large community archive formerly linked as
`https://archive.org/details/nierreincarnation` was also checked. Its public
metadata now returns `is_dark: true` and exposes no file inventory. This is an
unavailable source, not evidence that it never contained relevant files; no
attempt was made to access its alternate storage locations. The metadata
response is retained under `.build/notice-audit/new-preservation-sources/`.

## Restored native pop-up and localized text exports

The final encrypted master was subsequently decoded directly to recover five
truncated localized JSON exports, restoring 4,991 records. All 660 global
snapshots were also checked for the selected text and panel tables. The
separate [native pop-up report](NATIVE-POPUPS.md) documents 515 pop-ups,
787 English native images, 32 separately labeled regional images, historical
row versions and an independent archived Japanese text supplement. The reader
is `inputs/native-popups/index.html`; its validated portable archive is
`inputs/bunker-native-popups.zip`. These records do not add website notice IDs
or establish missing original website image bytes.

## Japanese master history follow-up

The [Japanese recovery report](JAPANESE-MASTER-RECOVERY.md) now covers the
public JP folder's complete 665-file listing and both downloaded ZIP parts.
All members passed CRC checks; 356 distinct binaries decoded successfully for
nine selected tables. Together with the global collection this preserves
1,325 snapshot files and 735 distinct encrypted payloads. The latest JP binary
also supplies all 607 decoded tables, and matches the archived repository data
under its declared numeric schema. Eleven historical text strings add to the
earlier final-repository supplement. Original website image coverage remains
unchanged.
