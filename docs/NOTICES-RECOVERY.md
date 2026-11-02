# Notice and banner recovery findings

Checked on 2026-11-01 against the pack pinned in `notices.lock.json`
(`d207500c96b0672e4468866c399aa26fa2dfdcf1347b07eb2305fae2e6985afa`).

## Expanded search results

The subsequent [event-by-event web pass](EVENT-WEB-CONTENT.md) adds a searchable
reader for 98 Record/Variation/Abyss Tower entries and 139 preserved Guide runs. It separately
saves 13 event-story pages, twelve early 2021 community news posts, 37 news
images, and eleven additional Guide image URLs (seven payloads, six already
preserved). Wayback also supplied four verified HTML captures covering three
official Radiant Cell social announcements, and the launch post's promotional
image. These are in `inputs/bunker-event-web-content.zip`; no new original
notice ID or missing-original image-path match is inferred from them.

The reader also saves summaries and galleries from eleven weekly editorial
reports, including **69 published image URLs and 67 distinct payloads**, all
decoded and hashed. These add event, chapter, campaign,
summons and SINoALICE costume/companion artwork, with source attribution and
visually checked captions; they do not reduce the exact-original-path gap.

Eight live official publisher website articles and their 1920 × 1080 banners
or social previews are also linked from the reader. Seven article sources and
seven image payloads are new to the publisher collection; Sun and Moon was
already archived. Dates and image-derived campaign details retain their source
context. The [publisher report](ALTERNATE-NOTICE-SOURCES.md) covers the complete
13-article English publisher collection and its 31 distinct image payloads.

The expanded pass preserved **347 exact original web images** (338 thumbnails,
eight character/weapon profile images and one inline icon), **262 game banner
textures linked to 103 notices**, **99 game profile/portrait images linked to 40 notices**, **191 native item/UI icons**, and **1,504
public event images** referenced by the Guide's 394 event records. Every counted
image was fully decoded and has a recorded SHA-256; the final check loaded all
2,407 recovered files with zero errors, including three older promotional images
found in the public 2021 CMS backup. The game banner artwork covers 91 of the
136 notices currently using stand-ins; it is supplemental artwork, not a claim
to have recovered their original full-size website banners.

A local candidate pack is at `inputs/bunker-notices-recovered.zip`. It contains
**951 notices and 89 exact thumbnail repairs**: 22 formerly blank thumbnails
and 67 formerly using Twitter artwork. It also repairs ten CSS background
image references across notices 897, 1058 and 1255 using eight exact archived
originals. It adds **91 distinct WebP files**, converted losslessly from verified
originals. Existing notice text and packed assets remain unchanged; only the
verified background URLs and repaired thumbnail fields were replaced. The four added bodies retain their source text with offline HTML
attributes. The expired survey's external link is rendered as text. Validation
confirmed all local ZIP image references resolve, the permitted edits reproduce
the candidate exactly, existing assets are byte-identical, and all new image
pixels are visually lossless. **39 existing notices still
contain 89 distinct original image URLs in inline CSS backgrounds.** Those
assets are absent from the pack and remain unresolved in the candidate.

The separate `inputs/bunker-notice-recovery-sources.zip` holds the source corpus,
portable image filenames, checksums, revision URLs and retrieval tools. The
published lock and default `inputs/bunker-notices.zip` remain unchanged.

### Additional early notice evidence

The live [NieR Re[in]carnation fan wiki](https://nier-rein.fandom.com/) is a
different source from the `nier_reincarnationfandomcom` Internet Archive dump.
Its API exposed 67 notice blog pages. Comparing normalized titles found 52
unmatched titles: 43 are empty placeholders, six have short excerpts, and three
have substantial text:

- [Apology for the Issue that Prevented Players from Logging In](https://nier-rein.fandom.com/wiki/User_blog:Aosquith/Apology_for_the_Issue_that_Prevented_Players_from_Logging_In): a complete-looking community transcript of the September 2021 apology and 300-gem gift.
- [NieR Replicant ver.1.22 Event Quest "Record: Pure Hills" On Now](https://nier-rein.fandom.com/wiki/User_blog:Aosquith/NieR_Replicant_ver.1.22_Event_Quest_%22Record:_Pure_Hills%22_On_Now): partial event text and exchange dates.
- [NieR Replicant ver.1.22 Crossover Campaign On Now](https://nier-rein.fandom.com/wiki/User_blog:Aosquith/NieR_Replicant_ver.1.22_Crossover_Campaign_On_Now): partial campaign text and the login reward table.

Their original game notice IDs and original publication timestamps are not
verified. Wiki creation/revision dates are not treated as game publication
dates, and these records are not inserted into the candidate pack. Recurring
titles can belong to different runs, so title matches alone are insufficient
to establish coverage.

The wiki's full public blog-namespace revision history was subsequently
retrieved: **187 revisions across all 67 notice pages**, with pagination
exhausted. Every revision retains its original wikitext, source link and wiki
timestamp in `inputs/bunker-wiki-notice-history.zip`. Comparing the full
historical content found only one corrected internal wiki link and added HTML
line breaks; older revisions supplied no additional notice body, game notice
ID or original publication timestamp. Suppressed/deleted revisions are outside
this public inventory.

The same pass inventoried all **68 uploaded-file metadata records** and
preserved two ambiguous early uploads after visual inspection: a 9S/Divergent
Scanner promotional card and an Automata crossover illustration. The CDN
served WebPs with different hashes and sizes from the uploaded PNG/JPEG
originals, so these are recorded as served promotional images. They do not
reduce the 764 missing-original-path count or change the 2,407-image main
source corpus. The separate history package passed ZIP CRC and payload hash
checks.

### Coverage and remaining gaps

The full Guide corpus has 946 notice bodies. The final audit covers both inline
images and CSS backgrounds; the latter revealed 95 additional missing character
and weapon image paths that the first pass had missed. Eight
readable archived Guide indexes and 869 archived bot reposts were also saved.
The bot corpus has 26 empty/deleted bodies; posts can arrive days after the
original notice, so Reddit timestamps are not substituted for publication
dates. The archived indexes add no further IDs beyond the four listed below.

After normalizing absolute URLs, duplicate slashes and the pack's SHA-1 names
for shared icons, **1,111 distinct original image paths** are absent from the
baseline pack: 528 thumbnail paths and 583 body-image paths. These are missing
source files, not 1,111 blank places in the UI. Of the Guide records with a
source thumbnail and a matching pack notice, 478 already use another packed
image, commonly a larger body banner. The audit keeps that reuse separate from
blank thumbnails and Twitter stand-ins.

The recovered originals cover 347 of those paths. **764 original paths remain
unrecovered**, including 574 body-image paths. The original website lead-image
files remain unverified for the 136 stand-in notices. Game artwork provides
mapped alternatives for 91 of them; 45 still lack such an alternative. Five additional
same-event artwork matches are saved as candidates for review, without being
counted as direct mappings.

### Character, weapon and companion artwork

A targeted check of 94 character and weapon URLs found nine available archive
records. Eight decoded as original 460-by-426 PNG profile images; one returned
HTML and is excluded. The originals cover all two profile backgrounds in
notice 897, all six in notice 1058, and two of ten in notice 1255. These ten
background uses now reference their local WebP copies in the candidate pack.

The notice captions and the game's preserved English text/master data also
identify specific profile artwork for **98 of 101 original profile paths**.
Extraction preserved 99 game images across 40 notices, including three small
portraits linked only by character identity. Most mappings use exact
displayed names; three companions with hidden names use a unique combination
of skill name and element, checked against the master table. The files are
authentic supplemental artwork, with different crops, dimensions or frames
from the website originals. They do not reduce the missing-original count.
Two previously unmatched names are resolved through independent master-table
fields: Akeha's Deathbloom skill, rarity and weapon type identify the costume
named "F. Guardian Assassin" in the final game data; the companion's Ward
effect, element and Luminous Shutdown ability identify the asset despite
"Wisdomtime"/"Wisdomtide" spelling differences. Three other paths identify
Gayle, Priyet and 10H without identifying a particular costume. Their small
standard portrait icons are retained as identity references, not as verified
replacements for the original website illustrations.

The local text archive was checked for notice, notification and announcement
keys. It contains UI labels and notification settings, not a notice-body
table; it supplied no additional notice bodies.

### Native possession and item icons

The source corpus also preserves **191 native icons** linked to **115 notices**:
99 weapons, 26 costumes, 42 memoirs, eight consumables, 15 important items and
one numbered Karma badge from a verified APK.
Notice captions, preserved English names and literal asset IDs identify
alternatives for **188 original image paths**. Of these, 185 have a single
asset mapping. Three website paths are reused for different memoirs in notices
1489 and 1570; their six native images are mapped per notice, not substituted
globally. These alternatives do not reduce the missing-original count.

The abbreviated game name "M. Phosphorescence" is resolved through an
independent costume-to-weapon association: notice 799 says Monster's
Phosphorescence unlocks Levania/Lacrima Monster, and the
[Guide's costume page](https://nierrein.guide/characters/levania/lacrima-monster)
associates that costume with the `wp004029` weapon.

Notices 708 and 709 label `consumable118077_icon.png` as Shards (P5R Crossover C).
That literal asset filename is absent from both platform inventories. The
unique native English item name and description identify `consumable118076`,
and master item 8076 selects asset category 118, variation 76. Its native icon
is now preserved as a semantic alternative for the named shard; the original
website path is retained unchanged, and no original-byte or visual identity
match is claimed. `native-icon-path-evidence.json` records this explicit
path-specific exception to literal-ID matching.

The signature-verified Japanese 3.7.1 APK supplies the unique 30 × 34 Sprite
`costume_lottery_effect_icon_3`, matching the original URL basename used in
notice 1439. This numbered badge is now preserved as a native alternative;
the original website PNG bytes and RGBA identity remain unverified. Its source
APK, serialized file, object ID, dimensions and hashes are recorded in
`native-gap-investigation/karma-apk-icon-evidence.json`.
The earlier 42 × 63 `status` glyph remains a separate, unmapped native UI
component and is not substituted for the numbered badge.

The [Japanese APK report](JAPANESE-APK-RECOVERY.md) documents all three verified
builds, their 4,448 sprite files and 897 distinct decoded pixel images absent
from the three prior global APK exports. These counts include historical UI
designs and pixel/resolution variants; they do not establish new characters or
exact missing website banners.

### Additional promotional banner library

The English `ui/mom_promotion/en/banner/` directory contains **863 promotional
banner textures**. These were extracted and indexed with local text recognition.
Comparing exact archived thumbnails with these textures found 44 strong
matches. All 44 pairs were reviewed side by side for characters, wording,
paid/free qualifiers, pack volumes and layout. The 44 corresponding
720-by-365 game images are preserved in the source bundle's `promotions`
family, alongside the 218 earlier banner textures.

This adds mapped game alternatives for eight stand-in notices that lacked
one: **595, 640, 645, 745, 788, 1522, 1559 and 1605**. The comparison establishes
the thumbnail's artwork composition; it does not establish the bytes of the
notice's separately addressed original lead-image URL. Looser visual matches
remain candidates and are not included in the 44 verified mappings. The other
819 extracted promotion textures remain a local search library.

### Other preservation sources checked

The [Accord's Library backup](https://archive.org/details/accordslibrarybackup)
allowed bounded HTTP range reads of its four ZIP directories: 2,674 main-site
entries, 31 gallery-site entries, 30,838 image-host entries and 16,626 large
resource entries. This avoided downloading the 43 GB resource archive.
The 36 Record event-story HTML pages were also read. They contain story text,
not additional notice bodies or original operations-image URLs. The directory
review did not identify a notice collection; this is not a full content scan
of every file in those archives.

The current public source trees of
[Lunar Tear](https://github.com/Walter-Sparrow/lunar-tear) and
[Marie's Wonderland](https://github.com/BillyCool/MariesWonderland) supplied
no notice corpus. Their notification handlers concern header badge counts.
The small `nier-rein-offline` archive contains a repository PDF and nested
source ZIP, not a separately named notice pack. The larger Lunar Tear binary
archive was subsequently inventoried through its public storage host. Its 13
entries contain executables, a README and a license, without a separately
packaged notice, website-image or snapshot collection. This was a directory
inspection, not an exhaustive examination of embedded executable data.

The [Common Crawl index](https://index.commoncrawl.org/) was queried across
17 collections from July 2021 through April 2024. Six returned no captures,
ten failed with HTTP 502/504, and one returned only the app's root page. An
earlier successful probe found another root-page capture. One downloaded root
page contains the web app shell and JavaScript links; it is not a notice-body
export. The other WARC retrieval failed. These failures leave coverage
inconclusive; neither the records found nor the successful retrieval supplied
additional notices or images. Narrow Wayback thumbnail-directory queries
also timed out, including an unfiltered query.

The master data also contains 89 distinct announcement target IDs absent from
the pack. Some are reused across unrelated early banners or carry 2099 dates;
these are a discovery ledger, not proof of 89 recoverable original notices.

The [old CMS repository's public dump](https://github.com/NieR-Rein-Guide/old-strapi.nierrein.guide/blob/main/dump)
contains nine early event records and their media relationships. It supplied
three additional 1920-pixel promotional images absent from the current event
asset collection, but no additional notice bodies. Only relevant event/media
records were retained in the corpus. Anonymous bucket listing was denied, and
the public upload-list endpoint was unavailable; known public image URLs worked.

The first exact-URL availability audit, run before adding the CSS paths, saved
177 valid API responses before rate limiting. A later pass used one worker
with a delay and stopped on its first HTTP 429: 603 queued checks were deferred,
not checked. Across the cached results for the 764 still-unrecovered paths,
378 have a negative availability response, two have archive records whose
replay did not yield an image, 230 retain request failures, and 154 have no
cached response. Negative results cover the requested URL spelling only.
Broader binary-image CDX queries also returned HTTP 503. Rate-limit failures,
deferred checks and other URL spellings remain unresolved.

A subsequent bounded retry checked 22 URLs: 20 returned no exact-URL capture,
one failed during TLS negotiation, and one returned HTTP 429. Network checks
stopped at that rate limit. No image is counted as recovered from these probes.

### Reproducing the offline audit

With the preserved source files in `.build/notice-audit/`:

```sh
python scripts/audit_notices.py
python -m unittest discover -s scripts -p test_audit_notices.py
```

`audit.json` records every missing path, its roles, source notice IDs and
recovery status. A file counts as recovered only if it still exists and matches
its recorded SHA-256. The seven audit tests cover URL normalization, existing
shared-icon naming, reused artwork versus blank thumbnails, and rejection of
changed or missing recovery files, plus portable filenames in an exported
corpus and inline CSS artwork, and rejection of a global/original claim for
notice-specific native icon mappings. The five existing notice-pack tests also
pass. `candidate-validation.json` records the separate candidate-pack checks.

Other useful evidence files are `additional-2021-notices.json`,
`reddit-bot-all.json`, `guide-events-index.json`, `event-assets-manifest.json`,
`game-banners/manifest.json`, `browser-recovered-images.json`,
`master-missing-notice-links.json`, `same-event-artwork-candidates.json` and
`image-validation.json`. The historical CMS evidence is in
`old-strapi-game-content.json` and `historical-event-assets.json`.
The profile evidence is in `background-availability-results.json`,
`background-recovered-images.json`, `profile-artwork-mapping.json`, and the
`profiles` family of the portable `data/image-manifests.json` export.
Promotion evidence is in `verified-promotion-banners.json`,
`promotion-thumbnail-candidates.json` and `promotion-banner-ocr.json`.
The extra source checks are recorded in `preservation-source-assessment.json`,
`preservation-server-notice-check.json` and the `commoncrawl-*.json` files.

## Initial audit

The sections below record the first, narrower pass before the expanded search.

## Confirmed additions

The pack contains 947 notices and 1,391 WebP images. Its local `img/*.webp`
references resolve to files in the ZIP. The first pass did not inspect original
image URLs in CSS backgrounds; the expanded audit above found them in 41
notices. Other missing artwork was omitted or replaced during pack creation.

The current [Guide notice index](https://nierrein.guide/notices) contains 946
notices. Comparing **IDs**, rather than totals, finds four notices absent from
the pack. Their full bodies were successfully retrieved from the site's public
Next.js page data:

| ID | Published (UTC) | Notice |
| --- | --- | --- |
| 1183 | 2023-06-07 02:00 | [Player Survey](https://nierrein.guide/notice/1183) |
| 1394 | 2023-10-11 11:00 | [Regarding Certain DRAGON QUEST X ONLINE Text](https://nierrein.guide/notice/1394) |
| 1472 | 2023-11-15 08:00 | [Regarding the Issue in Daily Quest](https://nierrein.guide/notice/1472) |
| 1606 | 2024-01-29 09:55 | [Issue that Causes an Error When Attempting to Log In](https://nierrein.guide/notice/1606) |

Keep the five pack-only notices: 1656, 1670, 1672, 1675 and 1676. Merging the
confirmed additions would give 951 notices. Replacing the pack with the Guide's
index would lose those five.

Of 160 pack notices without a thumbnail, 29 have an original thumbnail path in
the Guide. Wayback has usable image captures for 22 of those notices, sharing
18 distinct images. **All 18 originals were downloaded and validated as PNGs,
218 × 110 pixels.** These are list thumbnails, not full-size detail banners.

The 22 notice IDs are:

`10, 175, 200, 201, 222, 313, 330, 541, 542, 626, 650, 659, 679, 691,
695, 801, 880, 1070, 1082, 1087, 1096, 1107`.

The remaining seven known thumbnail paths did not match the downloaded banner
index: `1160, 1181, 1193, 1199, 1320, 1488, 1506`.

## Full-size banners

136 notices use an image marked `class="stand-in"`, usually Twitter artwork.
The original image paths were retrieved for all 136 notices. None of their
first body banners matched the downloaded English banner CDX index.

Two additional inline banner URLs for notice 707 (Record: Rebellion's Reality)
appeared in CDX, but usable image bytes were **not** confirmed: replay returned
HTML or a connection failure. Do not count these as recovered artwork. A CDX
HTTP 200 record alone does not establish that an image survives.

## Repeating and extending the search

1. Fetch and verify the pinned pack with `python scripts/notices.py`. Audit
   notice IDs, thumbnail keys, body image references and `stand-in` markers.
   That script downloads a fixed pack; it does not discover or rebuild notices.
2. Open the Guide in a browser and read its public `#__NEXT_DATA__` JSON.
   `/notices` exposes `props.pageProps.notifications` with IDs, release times,
   types, titles and original thumbnail paths. Direct Python requests received
   HTTP 403 during this audit; browser requests worked.
3. Read each detail page's `props.pageProps.notification`, or request
   `/_next/data/<buildId>/notice/<id>.json?id=<id>` in that browser session.
   Read the current build ID from the page; it changes with deployments.
   Details contain the original body HTML. This behavior is also visible in
   the Guide's [notice page source](https://github.com/NieR-Rein-Guide/nierrein.guide/blob/main/src/pages/notice/%5Bid%5D.tsx).
4. Extract exact `/images/en/operations/banner/<hash>` paths from both thumbnail
   metadata and body HTML. They are often **different hashes**. Match exact
   paths or hashes, not similar titles, especially for reruns and paid banners.
5. Query Wayback CDX for
   `web.app.nierreincarnation.com/images/en/operations/banner/*`, requesting
   `original,timestamp,mimetype`, with successful status. Include binary
   `application/octet-stream` records: many genuine PNG thumbnails use that
   MIME type, so filtering only `image/*` misses valid images.
   Fetch raw replay bytes with
   `https://web.archive.org/web/<timestamp>id_/<original-url>` and actually
   decode each image. Browser downloads/fetches recovered 185 images that
   command-line requests could not retrieve. Cache successes and failures, use a small worker pool,
   and retry transient failures. Reject HTML, redirects to dead live hosts and
   soft error pages even when the HTTP status is 200.
6. Expand discovery to other saved URL spellings, double slashes, HTTP/HTTPS,
   other original asset hosts and older Guide page-data snapshots. The early
   Guide CDX query in this audit found 60 captured pages through 2022; none
   added notice IDs absent from the pack. A broader image-MIME CDX request
   returned HTTP 503, so expanded archive coverage remains unverified.
7. For earlier notices missing from the Guide, compare dated Reddit `[NOTICE]`
   reposts and their image URLs against the pack. For example, the
   [September 2022 Monthly Featured Summons repost](https://www.reddit.com/r/NieRReincarnation/comments/xocvhp)
   preserves substantial notice content. This is a further source to audit,
   not a verified additional notice from this check. Match dates and content
   before assigning an original game notice ID.
8. If archive searches stall, an export of the Guide's notification table and
   any preserved operations-image directory from its maintainers would be the
   most direct next source. No maintainer was contacted. The public repository
   is the frontend and does not include that database export. The
   [resource dump](https://archive.org/details/nier_reincarnation_assets) lists
   Android/iOS resource archives, but this audit did not verify that they hold
   the separate website's operations banners.

When rebuilding, merge the four new bodies, sanitize their HTML and links for
offline use, preserve source publish/update dates where available, and repair
the 22 thumbnails using the exact recovered originals. Retain the stand-ins
until exact full-size replacements are verified. Then validate every image
reference and preview the changed notices before publishing a new pack.

## Local evidence

The subsequent search across eight other archival services and Square Enix's
own sites is recorded in [ALTERNATE-NOTICE-SOURCES.md](ALTERNATE-NOTICE-SOURCES.md).
It preserved five live English publisher announcements, an archived English
Square Enix update, a Japanese official countdown notice and 24 publisher
images. These are separate evidence from the original in-game notice corpus.

The later older-APK and user-supplied Drive scan is documented in
[HISTORICAL-DATA-RECOVERY.md](HISTORICAL-DATA-RECOVERY.md). It preserved all
660 global master snapshots and found 30 announcement targets absent from the
final banner table. These remain unconfirmed historical links; this pass did
not add notice bodies or exact original website images.

The ignored `.build/notice-audit/` folder contains:

- `guide-index.json`: all 946 source index records and the observed build ID.
- `guide-details.json`: raw detail data for the four missing notices, plus
  notice 196 as an example of original banner paths.
- `missing-thumbnails.json`: the 29 source records with missing pack thumbnails.
- `stand-in-original-paths.json`: original image paths for all 136 stand-in notices.
- `no-thumb-original-paths.json`: original image paths for the 29 thumbnail gaps.
- `banner-cdx.json`: the downloaded archive index (936 URL records, including
  records that may be HTML).
- `image-candidates.json`: 18 thumbnail candidates and two unconfirmed inline candidates.
- `recovered-images.json`: retrieval results, source/replay URLs, image dimensions,
  SHA-256 hashes and local filenames.
- `recovered/`: the original images, expanded from the first 18 PNGs to 347 files.
- `recover_image_candidates.py`: downloader for those saved candidates; requires Pillow.

The published pack and its lock were not changed by this audit.

The [native quest-art follow-up](NATIVE-QUEST-EVENT-ART.md) adds scoped native
event artwork for notices 1442 and 1630. Both omit the original “Coming Soon”
badge. The source corpus now has 220 game-family images plus 44 promotion
images, and 43 stand-in notices without mapped native game artwork. The exact
original website image gap remains 764.

The [official developer announcement collection](DEVELOPER-ANNOUNCEMENT-RECOVERY.md)
adds 33 Applibot/CyberAgent source pages and 165 distinct published image files
for individual events and campaigns. It preserves source dates and languages
separately and adds no original in-game notice IDs or exact missing banner files.

The later [currency-image investigation](NOTICE-CURRENCY-IMAGES.md) identifies
six direct native reward counterparts among 27 missing coin paths. It raises
the supplemental native-icon corpus to 197 records covering 194 original paths.
Six further identities remain explicitly inferred in a separate reader, and 15
paths retain multiple candidates. The exact website-image gap remains 764.

The separate [native pop-up collection](NATIVE-POPUPS.md) now preserves 515
native definitions, 819 image files and five repaired text exports containing
4,991 records. It includes historical and Japanese source supplements with
their provenance. Native IDs and regional filenames remain separate from the
951 recovered website notices; no new exact missing website path is claimed.
