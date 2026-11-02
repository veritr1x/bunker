# Summon notice repair candidate

Follow-up: [the complete generated candidate](GENERATED-SUMMON-NOTICES.md) covers the remaining entries with **201 generated summaries and two additional surviving-notice links**. The earlier candidate and counts below are preserved.

Audited 2 November 2026 against Bunker **1.7.0**, main commit `a80365259e276b929afaa7883fbac50c72ad032d`.

**125 of the original 328 unlinked entries now have a prepared association: 106 point to surviving notices and 19 point to clearly labelled reconstructed summaries. 203 remain unresolved.** This repairs 38.1% of that missing-link cohort. Within the original 529-entry reconstruction, coverage becomes 326 linked and 203 unlinked, counting the labelled summaries.

These are comparisons to the fixed cohort in `SUMMON-NOTICE-LINK-AUDIT.md`, not a claim that the latest server contains exactly 529 summons. A read of the existing BlueStacks user's 1.7.0 catalog returned 534 distinct base IDs, including 323 of the original 328 targets; all 323 still lacked a notice ID before this candidate. Locked/expired entries can be omitted by that response.

## Direct repairs

| Evidence | Links |
|---|---:|
| Individual weekly announcement duration and costume roster | 37 |
| Monthly weekly schedule: start, end minute, character and shard | 37 |
| Event-box summon and same-run event notice | 17 |
| Explicit rule notice lost because the catalog entry already existed | 11 |
| Premium summon: same start, format and full costume roster | 4 |
| **Direct links to surviving notices** | **106** |

The monthly schedule notices are 906, 956, 1010, 1071 and 1106. Their schedules explain many links missed by publication-date matching: a monthly notice legitimately covers several later banners. HTML5 parsing recovers orphan table cells and an unclosed character cell in the archived HTML. Matches require the specific schedule row, character and shard; a shared title alone does not qualify.

The four premium associations are 535001 → 811 (Woven Tales), 554001 → 977 (Congratulatory Dress), 556001 → 998 (Resolute Dress), and 589001 → 1412 (Never-Ending Adventure).

Two stale titles needed separate review:

- **Notice 756** is titled Cascading Mage, but its body, original thumbnail, event 318 artwork, tickets and start identify **Aurora Phantom**. The candidate corrects that title and maps 318001 → 756. Its body is preserved.
- **Summon 556001** has stale Replicant native text. Its original banner, February 2023 start and Celebratory Captive/Pupil/Student lineup identify **Resolute Dress**, matching notice 998. Its notice association is repaired; the native English database is not changed.

## The 19 reconstructions

| Original target entries | Count | Surviving reference |
|---|---:|---|
| Weekly 10019–10030 and 10047–10048 | 14 | Nearest verified single-character weekly notice with matching exchange roster, or a later superset trimmed to the target roster |
| Replicant 8 and 165 | 2 | Notice 1050 |
| Paid Replicant 515001 | 1 | Notice 1051 |
| FFXIV 159 | 1 | Notice 1163 |
| Paid Phantasmal Gateway 517001 | 1 | Notice 1164 |

Each target was checked against one of **10 original-run binary master snapshots** from the recovered global archive. Scoped raw shop, item, currency, costume, weapon and banner rows plus binary hashes are included in the evidence file. Exact exchange lineups are checked for missing and extra costumes. Five-column 2021 medal rows retain CeilingCount and omit the later ConversionRate field.

The output uses factual summaries rather than replacing dates in a later announcement:

- Original Replicant exchanges require **200 shards**, versus **150** in the reference rerun. The original paid Replicant summary also uses 200.
- Free FFXIV remains **200**; paid Phantasmal Gateway uses a different currency and **150**. Those exchanges are kept separate.
- Weekly 10030 (Griff) excludes the later **Bloody Captain** costume. Only its three original exchange options are listed.
- Original native banners are used, with lossless WebP conversion checked against their decoded RGBA pixels. No generated artwork is included.

All pages visibly say **Reconstructed**. They identify verified exchange options rather than claiming verified individual appearance rates. Original gem costs, step guarantees, bonus/duplicate/awakening rewards and individual rates are omitted where not recovered. Available native English names can differ from historical wording.

**Four** reconstructed availability windows are independently recorded in original native home banners. The other **15** are explicitly labelled inferred: exchange opening through shard conversion minus two days, following Bunker's catalog convention. Original publication times are unknown; synthetic pages are placed at the run start for archive ordering. Synthetic IDs use the separate `1500000000 + gacha ID` range and fit signed int32.

## Still unresolved

| Remaining group | Entries |
|---|---:|
| Weekly 10073/10074: notice 906 agrees on character, shard and start, but disagrees with the exchange-derived end by two days | 2 |
| Earlier two-character weekly banners without a matching original-format notice | 17 |
| Event boxes without a verified same-run notice | 14 |
| Other premium, ticket, generic and historical entries needing further run-specific evidence | 170 |
| **Remaining** | **203** |

Automata exchange overlap is insufficient to assign volume-specific featured lineups and guarantees. Generic Mama, New Chapter and elemental titles likewise do not establish equivalent runs. These entries have not received guessed links or copied later-run rules.

## Files and checks

- `inputs/bunker-notices-linked-reconstructed.zip`: separate candidate, **970 notices**, **279 pack-level summon-map keys**, 17 additional distinct native banner images. The source contains 951 notices and 154 pack-map keys; catalog-level explicit links are additional and explain why these map counts differ from cohort coverage.
- `inputs/summon-notice-repair-evidence.json`: every direct association, scoped historical reconstruction evidence, native banner provenance and unresolved date conflict.
- `artifacts/summon-notice-repair-review/index.html`: searchable offline reader for all 328 entries and all candidate notice pages.
- `artifacts/summon-notice-repair-audit/all-328.csv`: complete status sheet.
- `artifacts/summon-notice-repair-audit/summary.json`: counts, candidate hash and pixel checks.
- `.build/notice-audit/rerun-reconstruction/`: extraction and research scripts, complete selected historical tables, source snapshots and intermediate matches.

The pack starts with a member-exact extraction from the web-built 1.7.0 APK. Every source member except `notices.json` is preserved byte for byte, including 1,665 notice images and 962 other web assets. All original notice bodies and existing summon-map keys are unchanged. The only original notice field changed is the reviewed title of 756. Every new map target exists; ZIP CRCs and synthetic ID uniqueness pass.

Ten focused tests pass, including historical schema layout, roster contamination, price contamination, original banner periods, paid/free currency separation, existing-link protection and date-conflict exclusion. Browser checks verified the filter, original-banner loading, source links, Replicant's 200-shard table, Griff's trimmed roster and mobile layout. An already missing weapon background in original notice 756 remains an archival image gap; its thumbnail and 61 inline images load. This candidate does not claim to fill all old image gaps.

Rebuild with the prepared evidence and extracted native images:

```powershell
python scripts/build_summon_notice_repair_pack.py --source-pack .build/notice-audit/rerun-reconstruction/notices-1.7.0-from-apk.zip
python -m unittest discover -s scripts -p test_build_summon_notice_repair_pack.py -v
```

Latest code uses the pack's gacha map as a fallback when the catalog has no InformationId, so these additions require no loader change. This is a prepared candidate; the default notice packs, notice lock, native text DB and installed APK have not been replaced. The running game has not been tested with this candidate installed.
