# Japanese APK and notice-host recovery

Three Japanese APKs were downloaded from the observed Uptodown version catalog,
which exposed 56 releases. The selected builds are launch-era 1.0.3,
2.12.1 and final 3.7.1. All APK SHA-256 values match their source listings,
all ZIP member CRCs pass, and Android apksigner verifies the same signer used
by the three preserved global APKs:
`8575d97a796e08f9fe8887c3d83ab78c5275ba4a691494ed47f566abdac5e495`.
The packages identify `com.square_enix.android_googleplay.nierspjp`.
No APK was installed or executed.

The source APKs remain in `inputs/historical-jp-apks/`; the portable artwork ZIP
does not duplicate them. Source pages, file hashes, Android badging, signature
reports and extraction manifests identify the actual inspected bytes.

## Native sprites and text

| Version | APK bytes | Sprite files | Distinct RGBA images absent prior global APKs |
| --- | ---: | ---: | ---: |
| 1.0.3 | 87,074,859 | 1,113 | 354 |
| 2.12.1 | 111,856,171 | 1,603 | 0 |
| 3.7.1 | 254,131,762 | 1,732 | 545 |

Across the selected JP builds there are **4,448 sprite
files** and **897 distinct RGBA images absent from the three prior global
APK exports**. Exact pixel comparisons include dimensions and every decoded
RGBA byte. These are native UI components, frames, effects and other built-in
sprites; different resolutions or pixels can represent the same design. They
are not a count of new characters or original missing website banners. The
separate native character/costume/weapon/companion library remains relevant.

The raw selected TextAssets are preserved. Their exact key/value comparison
adds 331 pairs absent from the selected text in the three global
APKs. Comments and README lines are excluded from that count; raw files are
unchanged. No language is assigned from opaque serialized filenames. UI keys,
translation placeholders and repeated messages are not website notice bodies.

## Japanese notice services and public archives

Proper IL2CPP string-literal table decoding identifies the public host names
`web.app.nierreincarnation.jp`, `api.app.nierreincarnation.jp` and
`resources-api.app.nierreincarnation.jp`, plus the information route. Any
embedded URL userinfo is removed from extracted reports and was not used.

Wayback host discovery yielded two successful captured URLs: `/information/`
and `/robots.txt`, both from March 13, 2022. Both retrieved HTML payload SHA-1
digests match the CDX records. They contain Vue application shells, not notice
exports. Their five exact linked script/style paths, retaining observed query
strings, returned successful empty CDX results. A hypothesized JP `api-web`
alias derived from the observed global frontend was queried as an unconfirmed
lead and also returned no captured URL.

The public Common Crawl query service disconnected for both a JP query and
the known English positive control, so those failures are not negative evidence.
The public ZipNum indexes were then checked directly for the SURT prefix
`jp,nierreincarnation,app,` in all 55 collections in the saved September 2020
through October 2026 inventory. Covering-block boundaries, exact HTTP ranges,
ETags, SHA-256 and full gzip decoding/CRCs were verified. No capture row appears
under the checked prefix. This includes the observed service hosts and other
subdomains of that app subtree, not every possible domain alias. An earlier
known English capture calibrates the shared lookup method.

Arquivo's CDX request for the JP notice host returned HTTP 200 with an empty
body. This is a scoped empty response, not proof that every archival service
lacks relevant files. No original live service authentication was attempted.

The 18 previously identified JA native filenames were also searched by exact
basename across the local native UI tree, including the resource families
suggested by older client templates. No alternate basename path was found.

## Reading and verification

Open `index.html` for the version galleries and `new-native-sprites.html` for
the additional pixel-data gallery. Every exported PNG, raw TextAsset, image
dimension, local HTML reference and packet file SHA-256 is checked. Public
source observations, redacted client literals, archive indexes/range caches
and digest-verified HTML are preserved in `evidence/`. Research scripts retain
their workspace layout assumptions; the offline readers require no server.

The final APK also contains the exact named Sprite
`costume_lottery_effect_icon_3`, a 30 × 34 numbered Karma badge. Its basename
matches the original image reference in notice 1439. This supplies a documented
native alternative where the earlier dump provided only a generic status glyph.
The badge's original website PNG bytes and RGBA identity remain unverified.
The main source corpus now preserves this counterpart without changing the
default or candidate notice pack.

No new original website notice ID or exact missing website image path was
established. The original website image gap remains **764 paths**. The default
and candidate notice packs remain separate and unchanged.
