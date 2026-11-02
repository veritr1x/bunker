# Native pop-up and localized text recovery

Recovered on 2026-11-02 from the shared Drive master snapshots and the existing
Android asset dump. The reader is `inputs/native-popups/index.html`; the
portable package is `inputs/bunker-native-popups.zip`.

## Repaired exports

A read-only JSON syntax check of 607 local master exports found five truncated
files. Each stops immediately before its first localized string. The preserved
dump helper writes unescaped non-ASCII text without an explicit output
encoding; failure under a legacy Windows code page is a plausible explanation,
not a preserved observation of the original exception.

The five tables were recovered directly from `20240404193219.bin.e`, using the
previously pinned decoder and schema. The source ZIP member CRC and encrypted
binary SHA-256 were verified. Repaired named exports and positional rows are
written as UTF-8, without changing the backup master directory.

| Table | Localized records recovered |
| --- | ---: |
| Native Mama pop-up text | 3,684 |
| Gift text | 602 |
| Navigation cut-in text | 633 |
| Web mission titles | 24 |
| Web panel-mission completion flavor text | 48 |
| Total | 4,991 |

The pop-up table contains 1,304 Japanese, 1,190 English and 1,190 Korean records.
Of the English rows, 1,088 contain non-placeholder text, representing 620 distinct
strings. Repeated dialogue and `-` placeholders are retained rather than counted
as unique announcements.

## Native panels and artwork

The final master has 515 pop-up definitions and 1,489 panel rows. Available
English artwork was linked using the actual client resource-format literal:

```text
ui)mom_promotion){0})banner)prm{1:D3}
```

This literal was read from the certificate-verified global 2.12.0 APK's IL2CPP
string table. Its locale and image-ID format agree with the asset catalog.
787 of 865 distinct nonzero stored image IDs have corresponding images in the
English banner export. Those PNGs were fully decoded and hash-checked. The 78
unmatched IDs are recorded explicitly. Thirty-one have matching numeric
filenames in other regional trees: 31 Japanese and one Korean image were
exported into a separate gallery. These are not assigned to global panels:
Japanese and Korean `prm001` visibly depict different campaigns, so matching
numbers alone do not establish campaign equivalence. Forty-seven image IDs
have no matching filename in the checked English, Japanese or Korean paths.
Movie IDs are retained but videos are not
exported here. Thirteen panel rows without a final pop-up definition are also
preserved in the raw data.

The reader preserves native IDs, panel order, language variants and stored
schedules. Dates are not inferred notice publication dates. Distant-future
values and placeholder strings are not silently corrected.

## Historical versions

All 660 supplied global master snapshots were checked, representing 379
distinct binaries. Text and panel tables were decoded with CRC/SHA-256 checks;
the existing verified extracts supply historical pop-up definitions. Raw row
widths are retained instead of assuming every historical schema was identical.

Across the five repaired text tables, 360 historical row versions are absent
from the final master, including 65 English versions: 38 pop-up, eight gift,
eleven navigation cut-in, one mission-title and seven completion-text versions.
These include changed or removed rows; they are not automatically 65 additional
unique messages. Only twenty of these English versions contain non-placeholder
text; forty-five are placeholder rows. First/last snapshot labels describe observations in files,
not publication dates or guaranteed continuous availability. The English
historical readers do not assign final images to older text variants.

## Independent Japanese-language supplement

The [archived Marie's Wonderland repository](https://archive.org/details/github.com-BillyCool-MariesWonderland_-_2026-03-18_09-50-05)
also contains Japanese-language versions of the five text tables. At archived
commit `98d5b1ea1eda29e95b0d526bd1749aa78f362cc3`, 92 row versions are absent
from all 660 global snapshots: 58 pop-up, eleven gift, twenty navigation cut-in
and three completion-flavor-text versions. They are preserved in a separate
supplement with their original JSON bytes, Git blob IDs and SHA-256 hashes.
The verified Git bundle is retained too.

The underlying game snapshot version of this independent source is not
established. Its rows are not merged into the final global data or assigned
global images, notice IDs or publication dates.

The later [Japanese master recovery](JAPANESE-MASTER-RECOVERY.md) independently
matches all 607 archived tables to the data in JP `20240405123139.bin.e` under
their declared numeric schemas. This supplies matching-source evidence while
leaving the author's exact original snapshot unproven. The separate Japanese
history reader includes eleven further historical strings beyond this packet's
final-repository supplement; the older packet is preserved as its own snapshot.

## Scope

These are original native game data and artwork, separate from the website
notice archive. Native pop-up IDs and text IDs must not be interpreted as game
website notice IDs. No new exact website image path or original notice ID is
established by this recovery; 764 website image paths remain unrecovered.
