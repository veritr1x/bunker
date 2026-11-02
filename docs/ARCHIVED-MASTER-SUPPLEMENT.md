# Archived native master supplement

Open `inputs/archived-master-supplement/index.html` for the table comparison,
or `images.html` in that directory for the Japanese native artwork gallery.
The portable collection is `inputs/bunker-archived-master-supplement.zip`.

## Source and comparison

The source is the verified Git bundle from
[Internet Archive's March 18, 2026 preservation of BillyCool/MariesWonderland](https://archive.org/details/github.com-BillyCool-MariesWonderland_-_2026-03-18_09-50-05),
at commit `98d5b1ea1eda29e95b0d526bd1749aa78f362cc3`. The underlying game build
is not established. The bundle contains one reachable commit introducing
the master export files; it does not supply multiple historical master versions.
No archived code was checked out or executed.

A subsequent [JP master recovery](JAPANESE-MASTER-RECOVERY.md) independently
downloaded `20240405123139.bin.e`. All 607 archived tables agree with it under
their declared numeric schemas: 605 match exactly, while two differ only in
float32/decimal JSON representations. This establishes a matching data payload,
without uniquely identifying the snapshot originally used by the author.

Every one of the **607 master JSON tables** was compared with a direct decode
of final global master `20240404193219.bin.e`, whose SHA-256 is
`60555788242de9a0580b0d86f6d109d67bd9cabd16d7bcda9b9a99745f270778`.
The comparison verifies all 607 source Git blob hashes and uses exact typed
named-row multisets, preserving duplicate occurrences and ignoring JSON field
order. The source binary literally calls one table `m_abiliwy`; the comparison
explicitly applies the `m_ability` field map to that raw key and records this
alias. Other table keys use their direct schema mappings.

**483 tables are identical and 124 differ.** There are no field-set differences
between tables nonempty in both sources. Of the 124 changed tables, 33 become
identical when fields containing `Datetime` are removed; 91 have other row
differences. Empty versus populated tables remain differences.

The exact comparison contains 30,770 archived row versions absent from the
global final snapshot. This is not a count of new game entities, distinct
messages, or notices. It includes regional schedules and acquisition timestamps,
including thousands of NPC records. The complete raw source and difference
files for all 124 changed tables are preserved. The verified Git bundle also
preserves the 483 unchanged source files.
After removing fields containing `Datetime`, the remaining multiset difference
is 7,295 archived row occurrences. This still includes regional changes and
repeated content and is not a count of new entities.

The character, costume, weapon and companion tables were included. Existing
character/costume/weapon IDs must not be counted again merely because a
schedule or other value differs. This collection remains separate from the
global final master.

## Announcement references and artwork

Comparison with the previously decoded announcement history from all **660
global snapshots** found:

- **27 home-banner asset names** absent from the checked global home-banner rows.
- **14 promotion image IDs** absent from the checked global panel rows.
- **39 exact panel row versions** absent from the checked global panel history.

The 39 rows can combine existing image and text IDs differently. None of these
counts establishes a new website notice ID or publication date.

For those references, the local native JA bundle paths supplied **23 image
exports: 11 home banners and 12 promotion images**. Eighteen other referenced
JA paths were not found. Each export uses the exact named Unity Sprite and
records the source bundle SHA-256, Sprite name/object ID, PNG SHA-256 and
dimensions. The PNGs were fully decoded and a contact sheet was visually
reviewed. The original transparent canvas is preserved.

The gallery includes Automata/Replicant/Drakengard 3 campaign artwork,
mission and pack banners, event graphics, and two icon-group images. These are
native Japanese assets selected by filename references; the intended campaign
and underlying archived game build are not independently established. Where
present, Japanese panel text is shown verbatim from the same archived source.
Regional IDs can be reused, so these images are not substituted into global
pop-ups or assigned to missing English website paths.

The earlier **92 Japanese text row versions absent from global history** are
already preserved in the [native pop-up collection](NATIVE-POPUPS.md). They
overlap this full-table comparison and must not be added again as a new count.

## Verification and limits

The packet includes `comparison.json`, original changed source tables,
per-table difference files, announcement reference differences, image provenance,
unavailable JA paths, both readers, the Git bundle, the encrypted global source,
decoder/schema copies and inspection scripts. The saved global history extracts
and snapshot hash inventory support the scoped reference comparison.

Browser checks verified all 607 comparison entries, the table filter, and
successful decoding of all 23 gallery images. Local HTML references, packet
file hashes, archive CRCs and image dimensions are checked during packaging.

The 607-table comparison is against the final global snapshot. Only the
explicitly documented announcement/text subsets have been compared against all
660 historical snapshots. Other changed tables have not yet had that broader
historical comparison. No exact missing original website image was recovered;
the gap remains **764 paths**.

The later full JP history scan preserves 665 snapshots. Its reader contains
91 distinct non-placeholder strings absent from the checked global history,
including eleven beyond the earlier final-repository supplement. These counts
overlap the earlier 92 row versions and must not be added together.
