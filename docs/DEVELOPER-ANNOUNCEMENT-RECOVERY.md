# Official developer announcement recovery

This collection preserves 33 surviving official source pages and 165 distinct
published image files from Applibot and its parent company CyberAgent. It adds
individual event and campaign content to the preservation sources. It does not
establish additional original in-game notice IDs or recover any of the 764
remaining exact website image paths.

Open `inputs/developer-news-recovery/index.html` for the offline reader, or
`gallery.html` in the same directory for the image gallery. The archive is
`inputs/bunker-developer-announcements.zip`.

## Sources and coverage

Four searches of Applibot's public WordPress post API returned 38 distinct
records. Twenty-nine have game-announcement titles and were selected; the nine
other results are retained in the raw search responses with exclusion reasons.
These are bounded public searches, not proof that every historical developer
announcement survives or has been indexed.

The selected Applibot releases cover 2020–2022, including the original game
announcement, beta and preregistration, Japanese and overseas release plans,
Replicant and Drakengard 3 crossovers, Automata and 2P, Persona 5 Royal,
anniversary campaigns, and main-story chapter updates. For example, the
[Persona 5 Royal release](https://www.applibot.co.jp/news/202209091312543867/)
preserves campaign text and 13 published images. The
[Automata and 2P release](https://www.applibot.co.jp/news/202107301838433592/)
also remains available on the developer's site.

Four further CyberAgent releases preserve Japanese and English versions of
the Japanese launch and English/Korean launch announcements. They are parallel
language sources for two launches, not four newly identified game notices.
The [English overseas launch release](https://www.cyberagent.co.jp/en/news/detail/id=26518)
preserves the launch crossover's characters, login rewards and quest details.
Overall, the reader contains 31 Japanese source pages and two English pages.

Publication dates and original language are retained. Short English labels
provide navigation; they are summaries rather than replacements for the source
titles. Japanese campaign dates are not assigned to global notice IDs.

## Published images and banner comparison

All 171 observed image URLs were retrieved and decoded successfully, producing
165 distinct files. The collection includes banners, promotional illustrations,
screenshots and campaign material. Where a CyberAgent page explicitly offered
a larger `srcset` variant, that observed variant was preserved as well.

None of the 165 file hashes occurs among the 14,050 distinct file hashes in the
checked previous export manifests. This is a file-level comparison: it does not
mean 165 new illustrations or native asset identities. Language, resolution,
encoding and layout can differ while the underlying artwork is the same. The
comparison report names every baseline manifest and its hash.

Twenty-two of the 45 stand-in notices without mapped game artwork had a
preserved thumbnail available in the checked sources. Perceptual comparisons
produced three candidates close enough for visual review, all rejected:

- Notice 668 shares the Mama illustration with a Japanese gold-bouquet
  campaign, but its afterparty campaign title and layout differ.
- Notice 998's nearest candidate depicts Persona 5 rather than the required
  Resolute Dress characters.
- Notice 1442's candidate belongs to a different crossover quest and character.

The review page preserves these comparisons. No banner mapping was added to
the main corpus, and its 45 unresolved stand-in mappings remain unchanged.
The three comparison thumbnails are reused evidence, separate from the 165
published image files.

## Further public media and archive checks

Public WordPress media searches for `prm`, `mom_banner`, `limited_`, `item_`
and `step_up` completed with response pagination metadata. They returned five
distinct attachments, all already present in the selected articles. None of
their filenames matches the 18 explicit missing Japanese native asset names.
This does not cover names absent from those search fragments or other hosts.

An initial Wayback query across the entire upload prefix timed out. Five
narrower queries then checked the developer's WordPress upload prefixes for
2020 through 2024, filtering for those 18 native filename fragments and
including all capture statuses. Two initial HTTP 503 responses were retried
successfully. All five final year queries returned HTTP 200 with no matching
capture rows. A narrower June 2022 `prm512` prefix check also returned an empty
successful response. Arquivo's upload-prefix query returned HTTP 200 with an
empty body. Raw queries, failures, retries and responses are preserved; these
results are not an all-host or all-filename archive search.

Targeted Square Enix support and Bridge searches did not establish a
product-specific surviving support-news URL in this pass. A decoded string
literal check of the already-preserved global 2.12.0 APK also supplied no
Square Enix support URL. Neither observation proves that no such page existed.
No credentials were used and no publisher or developer was contacted.

## Verification

All 33 raw HTML files match their recorded SHA-256 hashes. Their article body
text matches the preserved records after whitespace normalization. The 36
reader pages have 812 checked local references, no broken local links and no
external rendering resources. All 165 published image payloads fully decode
and match their hashes. Browser checks covered the searchable index, Japanese
Persona page, English launch page, image gallery and rejection comparisons.

The archive includes the original source HTML, public API responses, per-URL
image provenance, gallery, comparison evidence and validation results. Its
file manifest records every packaged file's hash. The portable validator
requires Python and Pillow; the HTML reader itself needs only a browser.

The default and recovered candidate notice packs were not modified. The main
source corpus remains at 197 supplemental native-icon records covering 194
original paths; this separate developer collection does not change those
mapping counts.
