# Other web archives and Square Enix notice sources

Checked on 2026-11-02. Square Enix still hosts relevant English announcements,
and Arquivo.pt supplied additional archived official pages and an image.
These findings supplement the existing notice corpus. They do not establish
a complete mirror of the game's original in-game notice service.

The subsequent [Wayback continuation](WAYBACK-CONTINUATION.md) recovered nine
original website capture payloads, including JavaScript, stylesheets and a
maintenance banner. Direct CDX checks work while the availability endpoint
remains rate-limited; queued exact-path checks retain their results.

## Square Enix sources found

Five complete English announcements were downloaded from the North American
press hub, with displayed publication dates and SHA-256 provenance:

| Date displayed by publisher | Announcement |
| --- | --- |
| May 11, 2021 | [Pre-register today](https://press.na.square-enix.com/PRE-REGISTER-TODAY-FOR-NIER-REINCARNATION) |
| June 28, 2021 | [July 28 release date](https://press.na.square-enix.com/NIER-REINCARNATION-ARRIVES-ON-MOBILE-DEVICES-ON-JULY-28) |
| July 13, 2021 | [Launch and NieR:Automata crossover](https://press.na.square-enix.com/NIER-REINCARNATION-TO-LAUNCH-JULY-28-WITH-SPECIAL-NIERAUTOMATA-CROSSOV) |
| July 29, 2021 | [Mobile launch announcement](https://press.na.square-enix.com/NIER-REINCARNATION-NOW-AVAILABLE-ON-MOBILE-DEVICES) |
| September 14, 2021 | [15-million-download celebration](https://press.na.square-enix.com/NIER-REINCARNATION-COMMEMORATES-15-MILLION-DOWNLOADS-WORLDWIDE-WITH-CE) |

The public search must retain the spelling `Re[in]carnation`; searching the
unpunctuated `Reincarnation` returned no press results. Search results are
loaded through the site's normal public AJAX requests. Nine promotional
images embedded in the announcements were downloaded as served, fully decoded
and checksummed. These are mostly 500- or 600-pixel previews, not inferred
full-resolution originals.

The [public product listing](https://press.na.square-enix.com/Items/Details/NieR-Reincarnation)
exposes **five asset collections** dated May 11, June 28, July 13, July 29 and
September 14, 2021. The May collection did not appear in the earlier search
results. All **14 original files** were downloaded through the public download
controls, without a login. Their native dimensions, byte lengths and SHA-256
hashes were verified; the collection dates are publisher dates, not inferred
in-game notice dates. The original files total 18,840,919 bytes and include two
1920 × 1080 September celebration banners. All 14 hashes differ from the
existing 2,404-image notice recovery source corpus.

The files are saved under `original-press-assets/`, with provenance in
`original-press-manifest.json` and a contact sheet in
`original-press-preview.jpg`. The complete product listing returned five
announcements and these five collections; its following page was empty.

The UK press hub was also searched. Its returned results mention the game in
broader series announcements, but did not add another game-specific English
notice. Live NA, EU and Japanese support-center title searches for `NieR`
returned other NieR products and no Re[in]carnation support entry. This is a
search result, not proof that every retired support URL is unavailable.

Square's official [Japanese NieR blog category](https://blog.jp.square-enix.com/nier/title/nier_reincarnation/)
and its second index page remain online. They contain series, preregistration,
release-date and broadcast announcements rather than the full day-to-day
in-game notice corpus. Exact-title searches on Square's domains for the
missing login apology and Pure Hills notice did not find a matching page.

## Official material recovered through Arquivo.pt

- [Square Enix's English Sun and Moon update](https://arquivo.pt/wayback/20220123093721/https://square-enix-games.com/en_us/home/sun-moon-releases-nier-re-carnation), captured January 23, 2022. The saved HTML contains the article body, including its December 17, 2021 story-release reference. That event date is not asserted to be the article's publication date. The live URL returned HTTP 403 during this pass.
- Its **1920 × 1080 JPEG** was recovered from a separate January 28, 2022 capture of Square's CDN. The live CDN request returned HTTP 403; the archived replay decoded successfully. This is a verified original publisher-blog image, not proof of the bytes behind a missing in-game notice-image URL.
- [The Japanese story-completion countdown page](https://arquivo.pt/wayback/20240206015926/https://nierreincarnation.jp/news/story_completion_countdown/), captured February 6, 2024. It displays a January 23, 2024 publication date and retains the Japanese notice body and schedule sections. It has not been substituted for an English notice.
- The English marketing homepage at launch was recovered from July 31, 2021. Its news section directs readers to social media; it does not contain an embedded in-game notice archive.

## Additional live publisher website announcements

The main Square Enix website exposes additional individual announcements that
did not appear in the press-hub product listing. Eight live article captures
were saved, representing **seven previously unpreserved article sources** plus
a live version of the already archived Sun and Moon article:

| Publisher date | Official article |
| --- | --- |
| September 24, 2020 | [Western announcement](https://www.square-enix-games.com/en_US/home/nier-re-in-carnation-announced-for-the-west) |
| July 29, 2021 | [Available Now](https://www.square-enix-games.com/en_US/home/nier-re-carnation-available-now) |
| December 21, 2021 | [Sun and Moon](https://www.square-enix-games.com/en_US/home/sun-moon-releases-nier-re-carnation) |
| January 24, 2022 | [Half-year countdown and Blazing Armed Aberration](https://www.square-enix-games.com/en_US/home/half-year-anniversary-countdown-campaign-nier-reincarnation) |
| March 16, 2022 | [Mama's Anniversary Celebration Vol. 1](https://www.square-enix-games.com/en_US/home/mamas-anniversary-celebration-vol-1-nier-reincarnation) |
| May 26, 2022 | [FFXIV crossover and Vestiges of Paradise](https://www.square-enix-games.com/en_US/home/final-fantasy-xiv-crossover-has-arrived-in-nier-reincarnation) |
| August 1, 2022 | [Global celebration of the Japanese 1.5-year anniversary](https://www.square-enix-games.com/en_US/home/nier-reincarnation-global-celebration-japan-1-5-year-anniversary) |
| April 14, 2023 | [NieR series crossover reissue](https://www.square-enix-games.com/en_US/home/nier-series-crossover-back-nier-reincarnation) |

The article fragments, text and source hashes are in
`official-event-page-manifest.json`; the local reader opens at `index.html`.
Publisher dates remain separate from game notice publication timestamps. These
pages were also added to the event reader, with direct event links where the
event name appears in the article text.

Eight banner/Open Graph preview URLs returned decodable **1920 × 1080 JPEGs**
through ordinary browser fetches. Their unmodified served bytes and the observed
`quality=65` URLs are retained. Seven image hashes are new to the publisher
collection; the Sun and Moon JPEG exactly matches the earlier Arquivo payload.
These are served publisher images, with no claim of an exact missing game
website-image-path match. A preview is in `official-event-images-preview.jpg`.

The 1.5-year anniversary article lists six campaigns, while its banner contains
seven cards. The additional card describes reduced dungeon stamina and extra
drops, ending July 31 at 17:59 PST. The article is dated August 1. All seven
cards' dates are recorded separately as image-derived facts, without altering
the article or inserting a year into period labels that do not print one.

The game's public tag page rendered an empty listing. The exact read-only news
query from its published client returned HTTP 200 with zero results for both
US and GB locales, without authentication or cookies. The advertised sitemap
lists only six locale roots. These results do not exhaust the individual
article URLs; ordinary search still found the pages above. The tested UK press
search added a broader September 2020 series announcement, rather than another
game-specific in-game notice.

## Archive checks and their limits

| Archive | Check performed | Observed result |
| --- | --- | --- |
| Arquivo.pt | Domain/host CDX searches, URL histories, full-text searches and actual replays | 1,362 capture records for the English marketing domain and 519 for the Japanese domain; no records for `web.app.nierreincarnation.com` in the tested host query. Recovered the official material above. |
| UK Web Archive | Public domain and notice-host CDX lookups | Empty responses for the tested targets. The service currently exposes searches only for captures before October 2022; later coverage is unproven. |
| Japan's NDL WARP | Public keyword search for `nierreincarnation` | Zero public results. A broader access-category/domain request returned HTTP 403, so unrestricted and reading-room holdings were not exhaustively checked. |
| Ghostarchive | URL searches through HTTP and the normal browser | HTTP 403 and an empty browser result page; coverage remains inconclusive. |
| Archive.today / archive.ph | Public service lookup | HTTP 429; no repeated requests or mirror-domain retries after rate limiting. |
| Archive-It | Public all-collections CDX request | HTTP 403. Its own documentation says the `/all` endpoint is temporarily blocked because of DDoS activity; this is not a negative capture result. |
| Library of Congress | Web-archive page and public JSON catalog search | HTTP 403; coverage remains inconclusive. |
| Stanford Web Archive Portal | Public portal access | HTTP 403; no capture inventory established. |
| urlscan.io | Existing public scans for the notice frontend, backend and parent game domain | All three public API queries returned HTTP 200, zero results and no pagination. A known-domain positive control returned results. No scans were submitted; private or unlisted holdings were not accessed. |

Archive counts are index records, not counts of distinct notices or recovered
bodies. Arquivo's broad full-text queries also returned unrelated matches;
only inspected official pages and decoded image payloads are counted here.

Useful service documentation:
[Arquivo.pt API](https://github.com/arquivo/pwa-technologies/wiki/APIs),
[UK archive scope](https://www.webarchive.org.uk/),
[WARP search help](https://warp.ndl.go.jp/en/info/help),
[Archive-It CDX availability](https://support.archive-it.org/hc/en-us/articles/115001790023-Access-Archive-It-s-Wayback-index-with-the-CDX-C-API).

The [urlscan search reference](https://urlscan.io/docs/search/) defines `domain`
as any contacted domain, including subdomains. The tested parent-domain query
therefore covers more than primary page URLs. Responses and the positive
control are retained in `.build/notice-audit/urlscan-public-search/`; this
describes the public query results, not all possible private scan holdings.

## Saved evidence and remaining gaps

`inputs/publisher-notice-evidence/` contains raw publisher HTML, archived
official pages, image files and source manifests. The portable package is
`inputs/bunker-publisher-notice-evidence.zip`. The separate working directory
`.build/notice-audit/alternate-archives/` retains query URLs, raw API responses,
capture indexes and failed-request evidence.

The saved collection now establishes **13 English publisher announcements/articles**, **one
Japanese official countdown notice**, the archived English launch homepage,
and **31 distinct publisher image payloads** across 32 image records: the earlier
24 payloads plus seven new served website images. The eight live website-image
records include the already preserved Sun and Moon payload. No additional original in-game notice ID
or exact missing image path has yet been established from these publisher
sources. The candidate still contains 951 notices and **764 original image
paths remain unrecovered**. Separately, eight already recovered exact profile
images have now been integrated into the candidate to repair ten CSS background
references across three notices; see `NOTICES-RECOVERY.md` for validation.

## Common Crawl public index-file pass

The public query service repeatedly failed, so the follow-up used the published
ZipNum secondary indexes and compressed blocks at `data.commoncrawl.org`.
HTTP byte ranges, response lengths, ETags, gzip checks and block boundaries were
validated. A known December 2023 homepage capture calibrated the lookup.

All **55 published collections from September 2020 through October 2026** were
checked for the English notice frontend and backend host prefixes. The indexes
contain six frontend homepage capture rows, with no image or notice-detail URL
rows under the tested prefixes and no backend-host rows. This is index coverage;
it does not establish that every possible host, URL alias or archive is empty.
The query-service failures are not counted as negative results. Evidence and
range caches are in `.build/notice-audit/commoncrawl-offline/`.

All six compressed WARC records were subsequently downloaded with exact byte
ranges and verified. Five contain homepage HTML with payload SHA-1 matching
the crawl index; the sixth is a bodyless HTTP 304 revisit referring to the
May 2024 URL/date, with the same HTTP ETag. Its referenced record UUID differs
from the retrieved May response UUID, so exact record-ID resolution remains
unverified and is recorded separately. The five HTML bodies contain the application shell rather
than notice exports. Three intermediate script/style builds linked from those
bodies were then recovered from Wayback. The portable evidence archive is
`inputs/bunker-commoncrawl-notice-evidence.zip`.

## Additional Japanese official event sources

The [Japanese source report](OFFICIAL-JP-EVENT-CONTENT.md) covers twenty Square
Enix Presents broadcast pages and two official DQX crossover articles, all now
preserved in a separate reader. Its 44 published image files include twenty
broadcast images, crossover artwork and screenshots, plus explicitly labeled
site icons and product promotions. This collection adds surviving official
context without assigning unverified in-game notice IDs or original image paths.

## Additional public archive checks

The [additional source report](ADDITIONAL-ARCHIVE-CHECKS.md) records ten selected
nested WACZ/ZIP scopes in the Accord backup, a complete reachable-blob scan of
an archived public repository, six public Drive PNG comparisons and a live
Guide notice recheck. None yielded an exact missing website image. The archived
repository did yield Japanese native text absent from the global master
history; that supplement is preserved separately in the native pop-up reader.
