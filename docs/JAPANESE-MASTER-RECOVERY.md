# Japanese master history recovery

The [public JP binary folder](https://drive.google.com/drive/folders/1DVZ7vciYoMN0uWhEoCsLj3Yjq_-yKpPf)
contains **665 snapshots**, from `20210202000742.bin.e` through
`20240405123139.bin.e`. The earlier saved listing contained its first 50 files.
The browser inventory now matches the initial 50 plus all 13 additional network
pages; the final page contains 15 files and no continuation token.

## Preserved source and coverage

Google Drive's normal folder export supplied two ZIPs, totaling **3,729,746,255
bytes**, now under `inputs/japanese-master-recovery/archives/`. Every member
was read with ZIP CRC verification and recorded with its SHA-256. Their names
match all 665 observed source files, with no missing or additional members.
There are **356 distinct encrypted binary hashes**. Each was decrypted and
decompressed for nine selected native tables, with no errors:

- Home banners, pop-up definitions, panels and pop-up text.
- Gift, navigation, webview mission-title and mission-completion text.
- Event quest chapter metadata.

All table-name inventories are retained. Other table payloads remain preserved
in their original encrypted binaries; this pass does not claim to have exported
every historical table. Historical row widths stay raw. In particular, early
two-field text rows have no encoded language column and are not forced into
the later three-field schema. First/last snapshot labels are observations,
not notice publication dates or proof of continuous availability.

Together with the earlier 660 global snapshots, the collection now preserves
**1,325 snapshot files and 735 distinct encrypted payloads**. No binary hash is
shared between the checked JP and global sets.

## Matching the archived repository

The latest JP binary was also downloaded independently as a single file. Its
7,584,512 bytes have SHA-256
`13730fb40bafaeace7a4eedb3dc9029200bac3ccdc334035bb6d2aebc2209b69`,
matching the corresponding member of the full folder export. A complete decode
produced **607 UTF-8 tables containing 888,391 rows**.

These were compared against every archived export at MariesWonderland commit
`98d5b1ea1eda29e95b0d526bd1749aa78f362cc3`. All source Git blob hashes were
verified. **605 tables match exactly as ordered named rows**. The other two
match when their declared numeric types are considered:

- Gimmick coordinates use the same IEEE754 binary32 bits despite JSON
  spellings such as `19.1` and `19.100000381469727`.
- Payment prices use equal exact decimal values despite JSON representations
  such as `120.0` and `"120.00"`.

Only fields declared `float` or `decimal` receive those comparisons. Original
values and exact differences are preserved. Thus **all 607 tables agree under
the declared numeric schema** with this community-preserved JP snapshot. This
establishes a matching data payload; it does not prove which of potentially
identical snapshots the repository author originally decoded, nor authenticate
the community filename as an official release identifier.

The supplementary comparison against global data also separates numeric
representation from values. All 124 originally changed tables still have
differences after float32/decimal normalization. Their source-only multiset
count falls from 30,770 exact JSON row occurrences to 29,165 after numeric
normalization, then 5,690 after additionally removing fields containing
`Datetime`. These remain row occurrences, not new entities or notices.

## Historical text recovered

Across the five selected text tables, comparison with all 660 global histories
finds **308 raw row versions** absent from the global set. Of those, 201 already
have the same ID and text in a global row of another schema; they are not
counted as new messages.

The text comparison establishes **91 distinct non-placeholder strings absent
from the checked global history in any language**. Eleven are absent from the
earlier final-repository text supplement and were recovered by the historical
scan. The reader labels that distinction. The earlier supplement's 92 row
versions must not be added to these totals as if they were disjoint messages.

The eleven additional strings include old anniversary/campaign pop-up wording,
gift labels and one mission-completion narrative. All text is preserved verbatim,
with raw rows and first/last observed snapshots; no translation, inferred notice
ID or invented publication date is added.

## Missing artwork checks

The Japanese source history adds the same 27 home-banner asset names absent
from global announcement history that the final archived export exposed.
Eleven have local JA bundles and are already in the separate artwork supplement.

The public Drive JA artwork folders were also scrolled to stable final rows:
**359 home-banner PNG names** and **881 promotion PNG names**. Both sets equal
the corresponding local native bundle filename sets. None supplies one of the
18 specifically missing JA paths. This is filename coverage, not a byte
comparison of every PNG; the earlier six-file sample comparison remains scoped.

## Reader and portable packet

Open `inputs/japanese-master-recovery/index.html` for all 607 latest table links,
or `text-history.html` in the same directory for the 91 historical text strings.
`inputs/bunker-japanese-master-evidence.zip` contains those readers, the latest
binary and all decoded tables, source proofs, selected raw historical row
versions, global comparison excerpts, the archived Git bundle and inspection
scripts. Its file manifest records SHA-256 for every member.

The two original 3.73 GB historical ZIPs are preserved separately and are not
duplicated inside the portable evidence packet. Their full hashes and per-member
inventories are included. No original website notice body or exact missing
website image path was established by this native-data scan. The website image
gap remains **764 paths**.
