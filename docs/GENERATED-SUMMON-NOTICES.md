# Generated summaries for the remaining summons

Follow-up: [the template-based candidate](NOTICE-TEMPLATE-BASES.md) matches every synthetic page to a surviving notice base, promotes **17** further entries to original notices and rebuilds **203** remaining reconstructions around those bases. The earlier candidate and counts below are preserved.

Prepared 2 November 2026. **The remaining 203 entries are covered by 201 generated data-summary notices and two additional links to surviving notice 906.** Combined with the earlier candidate, all 328 entries in the original missing-link cohort now have a page: **108 surviving-notice links, 19 rerun reconstructions and 201 generated summaries**.

The complete candidate contains **1,171 notices and 482 pack-level summon keys**. Those key counts differ from catalog coverage because many existing links are declared directly in catalog rules.

## What the new pages contain

| Page source | New generated pages |
|---|---:|
| Native shard exchange data | 119 |
| Event quest, tickets and Bunker's reconstructed box rewards | 14 |
| Native banner identity and available Bunker summon configuration | 68 |
| **Generated pages** | **201** |

Of the 119 exchange pages, **117** use a snapshot observed within the original run. Two (94 and 9000035) use the final native master and explicitly mark period-specific availability unverified. Preparation decoded **67 historical binary snapshots**. Scoped raw rows, archive member names and SHA-256 hashes accompany the evidence.

Exchange rows are labelled as recorded snapshot options, rather than a complete featured pool for the entire run. This matters for Automata volumes and other banners sharing a currency, and for rosters expanded during a run. Five entries differ from the final master roster. The generated pages retain what the selected historical snapshot records instead of silently including later entries.

**198** new pages have extracted native banner art. Lossless conversion preserves the decoded RGBA pixels; deduplication adds **187** distinct images. Entries 70, 85 and 160 have no recovered original banner and remain text-only. No AI-generated artwork is used.

Visual review of native art supplies **45** English titles, recovering 40 otherwise unidentified titles and improving five existing identities. For example, 580001 is Tale of Resistance / Paid-Only Mechanical Captain, matching its art and historical exchange; its stale Japanese text refers to a hunter.

All generated notices visibly say **Generated data summary**. Original announcement wording, complete featured pools, historical individual odds and unverified guarantees/rewards are not claimed. Bunker configuration tables are explicitly labelled as reconstructed game behavior. Original publication dates remain unknown; pages are placed at the catalog start, or global launch when only placeholder dates exist. No 2099 placeholder is presented as a historical run date.

## Two January conflicts resolved

Summons **10073 (Gayle)** and **10074 (Akeha)** now link directly to **notice 906**.

The original-run snapshot `20230110173655.bin.e` records conversion at **Jan. 17, 2023, 17:59:59 PST**. Two days earlier is Jan. 15, agreeing to the minute with the notice's schedule. The final native master had moved conversion to Jan. 19, creating the earlier apparent two-day conflict. The original start, character and shard also match. The historical rows and schedule evidence are retained; redundant generated pages are excluded.

## Twelve payment conflicts kept out of the notice facts

| Banner IDs | Original native artwork | Reconstructed configuration |
|---|---|---|
| 405 | Paid gems only | Unrestricted gems |
| 456, 457 | Free 10x daily | Gem prices, no free option |
| 554 | Crossover commemorative 10 free summons | Gem prices, no free option |
| 600, 601, 602, 603, 604, 605, 609, 610 | Story Completion Countdown 10x free per day | Gem prices, no free option |

The generated pages show the terms visible in the native artwork, flag the mismatch and omit the disputed cost table. The index can filter `payment conflict` to find all twelve. This work does **not** change gameplay prices. Free bonus steps in an otherwise paid sequence are allowed and do not create a false conflict; 9000086 is covered by that check.

## Outputs and validation

- `inputs/bunker-notices-complete-generated.zip`: complete separate candidate.
- `inputs/remaining-summon-notice-evidence.json`: all 203 reviewed targets, including the two direct links and historical evidence.
- `inputs/generated-notice-banner-title-review.json`: reviewed native banner titles, payment terms and image hashes.
- `artifacts/generated-summon-notice-review/index.html`: searchable offline reader.
- `artifacts/generated-summon-notice-audit/all-328.csv`: complete cohort status sheet.
- `artifacts/generated-summon-notice-audit/payment-conflicts.csv`: the twelve configuration conflicts.
- `artifacts/generated-summon-notice-audit/summary.json`: counts and candidate hash.
- `.build/notice-audit/rerun-reconstruction/prepare_remaining_notice_data.py`: preparation script; selected native tables are cached in `remaining-target-history/`.

Rebuild from the prepared evidence with `python scripts/build_remaining_summon_notices.py`. Run focused checks with `python -m unittest discover -s scripts -p test_*summon*.py`.

**35 tests pass**, including historical roster contamination, shared-volume handling, paid/free conflicts, specific ticket currencies, placeholder dates, missing art, original-run schedule matching and previous-link protection. The builder checks ZIP CRCs, ID uniqueness, every new image reference, lossless image identity and byte-for-byte preservation of all previous pack members except the extended JSON index. All 970 previous notice records and their existing links remain unchanged.

The candidate is separate. Default packs, the earlier repair candidate, notice lock, native text DB and installed APK are unchanged. These pages fill navigation gaps; they do not establish that all original historical notice content has been recovered.
