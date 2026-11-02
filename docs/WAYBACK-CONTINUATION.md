# Continued Wayback recovery

Checked on 2026-11-02 following the request to keep trying Wayback.

## Working capture-index route

The `archive.org/wayback/available` endpoint again returned HTTP 429, and that
batch stopped immediately. The public `web.archive.org/cdx/search/cdx` index
and raw replay URLs worked. These are different public capabilities of
Wayback; no alternate mirror, IP rotation or authentication bypass was used.

The refreshed notice-host index returned **1,635 URL records**, with a separate
banner query returning 947 capture-version records. Records are not counts of
notices or recovered files. The host's 71 PNG records contain no new match to
the remaining missing-path inventory.

Nineteen missing paths occur in the returned host index: six HTML captures
and thirteen revisit records whose payload digests resolve to HTML. One raw
banner replay was saved and its SHA-1 verified against the index. It is the
game's application shell, not image bytes. This prevents treating a successful
archive lookup as a recovered banner.

The other distinct HTML payload, from a character-image URL, was subsequently
downloaded and SHA-1 verified too. All nineteen captured missing-image paths
resolve to these two verified application-shell HTML digests; this conclusion
now uses actual payload bytes rather than MIME labels alone. The raw replays
and `non-image-digest-verification.json` are preserved in the evidence package.

The exact-URL first pass is complete for **all 764 unrecovered full paths**:
745 returned no capture in the tested exact query, and nineteen had only the
verified HTML payloads above. There are zero remaining query errors. Three
English/Korean coin-image filename collisions were checked separately by full
path after correcting the cache key. `exact-coverage-validation.json` verifies
coverage against the audit inventory, including its SHA-256. These checks do
not prove that every URL spelling or later capture is absent. The cache and
coverage proof are preserved in the portable package.

## Official Radiant Cell announcements recovered

A contemporary community post linked an official October 2021 tweet. Its
exact CDX query returned two captures, both downloaded and SHA-1 verified
against the index. The first capture exposed earlier official conversation
links; their exact queries and replays also succeeded. **Four verified HTML
captures now preserve three official announcements**: the event launch,
maintenance investigation, and loading-issue fix with compensation.

The launch capture includes a public `pbs.twimg.com` media URL. Its 1200 × 675
Radiant Cell promotional JPEG was saved and visually checked. The tweet bodies,
raw HTML, capture digests, image hash and source links are included in the
event reader and Wayback evidence packages. The social posts have no verified
in-game notice ID, and the artwork is not counted as an exact missing website
image. See [the event report](EVENT-WEB-CONTENT.md) for source links and scope.

## Original website files recovered

Eighteen original capture files were downloaded and verified against their
CDX SHA-1 digests, with additional SHA-256 records. They represent fifteen
distinct payloads:

- Five dated versions each of the main JavaScript, outlink JavaScript and
  stylesheet: September 2022, October and December 2023, January and June 2024.
- The original **1174 × 150 maintenance PNG**.
- An English static maintenance HTML fragment.
- The maintenance route's compressed application-shell response. Its original
  gzip bytes are retained alongside a separately checksummed decoded HTML file.

The three intermediate build versions were linked from digest-verified Common
Crawl homepage captures and replayed from Wayback. Nine additional capture
files supplied six distinct payloads absent from the earlier package. Repeated
outlink/style payloads retain their separate capture provenance. Their service
URLs still identify the same notice backend; no additional notice body or
missing original image path was established.

Five verified stylesheets also embed nine distinct decodable PNGs: button and
border artwork and a back arrow. These were extracted without modifying their
bytes and visually checked. Five occurrences of one malformed base64 literal
are recorded as failures; no repaired original is claimed. The extracted UI
files and their stylesheet offsets are under `embedded-images/`.

Files and provenance are in `inputs/wayback-notice-web-assets/`. The portable
package is `inputs/bunker-wayback-web-evidence.zip`. These website sources and
system artwork are separate from the missing in-game notice-image inventory;
they do not reduce its **764 unrecovered paths**.

The recovered JavaScript identifies
`https://api-web.app.nierreincarnation.com` as the notice backend, including
the `/api/information/list/get`, `/api/information/detail/get` and banner-list
routes. A host-wide archive lookup initially timed out; both the narrower public
`/api/information/*` query and a subsequent full backend-host prefix query
returned HTTP 200 with empty indexes. These results cover the tested public
queries, not all private holdings or possible request variants. No authenticated
API calls were made.

## Resource catalog extraction completed

Four native Octo `list.bin` files and four accompanying `info.json` files were
extracted for archive folders 790, 800, 810 and 818. All eight files match their
7-Zip member sizes and CRC-32 values. Decoding used the archive author's
`octo.proto`, verified against its published SHA-1.

The content corrects an earlier assumption: **`info.json` is an archive
deduplication map**, not the native catalog. Every selected `list.bin` reports
database revision **818**. The lists contain 9,938, 8,255, 6,455 and zero
asset/resource entries respectively. This pattern indicates final-revision
update responses rather than independent snapshots of older asset bytes.

Every mapping MD5 agrees with its native list entry, and all mapping
destinations exist under the archive's revision zero. No new bundle path was
found in these selected lists; six literal video-name aliases resolve to
existing files. This is a path/mapping check, not a byte comparison of every
iOS bundle against Android.

The raw files, decoded JSON, schema and validation are preserved in
`inputs/bunker-octo-catalog-evidence.zip`. Other archive revision folders have
not all been decoded. No additional original notice body or exact missing
notice-image payload was established in this pass.

## Japanese client notice services

Static inspection of three signature-verified Japanese APKs identifies the
separate JP web/API/resource hosts. The later
[Japanese APK report](JAPANESE-APK-RECOVERY.md) records this source evidence.
Extracted URL reports omit any embedded userinfo; authentication was not used.

The JP notice host has two captured URLs in the checked public Wayback index,
including an all-status pass: `/information/` and `/robots.txt`. Both March 13,
2022 HTML payloads were recovered and their SHA-1 digests match CDX. They are
application shells. Five exact linked script/style paths returned successful
empty CDX queries. The two payloads, index queries and redacted client evidence
are now included separately under `jp-notice-services/` in the Wayback packet.

The JP app-service subtree was also checked in all 55 collections in the saved
September 2020–October 2026 Common Crawl inventory. Covering ZipNum index blocks
and 796 HTTP range-cache files passed checksum, boundary and full gzip checks;
there are no matching capture rows under that prefix. One SSL failure was
retried successfully before the pass was marked complete. Raw evidence is in
the Japanese APK packet. Arquivo returned an empty HTTP 200 CDX response for
the JP notice host. These are scoped results, not a claim about every archive
or possible domain alias.

The existing 764-path English/Korean exact-check cache was revalidated against
the updated audit after adding a native Karma badge alternative. Its missing
original path set is unchanged; this revalidation did not submit 764 new queries.
