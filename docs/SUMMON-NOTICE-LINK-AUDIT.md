# Summon and event notice link audit

Follow-up: [the repair candidate](SUMMON-NOTICE-REPAIR-PACK.md) prepares **106 direct links and 19 labelled reconstructions**, leaving **203** of the original 328 unresolved. The counts below preserve the earlier baseline audit.

Checked 2 November 2026. **65 events have an existing same-run notice but no event-to-notice mapping. 328 reconstructed summon entries have no notice link; 27 of those already have a verified notice association in the available data.** These are separate kinds of links, with overlap in the notices they target.

This expands the initial Sunset Port investigation. Counts come from original master JSON, English Archive text, both notice packs, and the current catalog-loading code. The audit reconstructs non-chapter catalog membership, including summons without home banners. It does not query a running phone or count only banners visible at the current game date. Permanent chapter-ticket summons are excluded.

## Missing event links with an existing notice

| Event kind | Existing same-run notice, missing association |
|---|---:|
| Record | **45** |
| Variation | **17** |
| Fate Board | **1** |
| Special quest | **2** |
| **Total** | **65** |

Examples include Sunset Port (event 509 → notice 1208), Seat of Shadow (507 → 1445), City of Discontent (505 → 1406), Garden of Benediction (584 → 1610), and Foundation of Fortune (585 → 1631). Each match uses the native title and exact start time, preserving the specific rerun.

There are 53 Record chapters: 45 have matches, seven lack a verified notice for that particular run, and one has a placeholder date. A notice for a different rerun is retained as a research lead rather than counted as the missing association's target.

Across all 274 native event chapters, 209 lack a unique match under this conservative method. This includes permanent content, character quests, repeated generic titles, historical runs and placeholder dates. **It is not a count of 209 lost announcements.**

Two narrowly reviewed aliases handle the native abbreviations “Variation: A. Dynast” and “Variation: B. Resentful Witch.” They match Aurora Dynast (notice 1244) and Blazing Resentful Witch (1310), respectively, at the same start times. The audit does not expand arbitrary initials or use fuzzy title similarity.

Notice 1574 is incorrectly categorized as type 3 in the source despite announcing the Wishing Space event. Notice 1168 has a damaged closing quotation mark. Those source quirks are normalized for matching; their stored records are unchanged.

## Summon notice links

| Reconstructed non-chapter catalog | Count |
|---|---:|
| Total summon entries | **529** |
| Existing link with a notice present in the pack | **201** |
| No notice link | **328** |
| Of those: an existing notice association is established | **27** |
| Of those: no verified association established yet | **301** |

The 328 unlinked entries comprise 74 loaded from native home banners, 129 recovered through medal exchanges, 94 added by catalog rules, and 31 event-box summons. Missing home-banner links alone therefore undercount the gap. The earlier 146 figure described raw native home-banner targets, not the generated catalog.

The 27 established summon associations split into:

- **16 event-box summons** whose event has an existing notice matching the event title and exact start. They are a subset of the 65 event associations above. The other 15 of the 31 event-box summons lack a verified same-run match.
- **11 paid summons** whose notice IDs are already declared in `summon_rules.json`, but whose entries are created earlier by the medal-exchange loader. The added-summon loader skips existing IDs, so their declared notice IDs never reach the catalog entry. The notice pack has no fallback mapping for these IDs.

| Summon ID | Existing notice ID | Notice title |
|---|---:|---|
| 566001 | 1164 | Paid Only: Phantasmal Gateway Multi-Step Summons On Now |
| 567001 | 1166 | Paid Only: Again Into Fantasy Multi-Step Summons On Now |
| 578001 | 1325 | Paid Only: Reverie's Garb Multi-Step Summons On Now |
| 590001 | 1405 | Paid Only: Abyssal Student Multi-Step Summons On Now |
| 600001 | 1419 | Paid Only: Divine Boor Multi-Step Summons On Now |
| 602001 | 1444 | Paid Only: Abyssal Pupil Multi-Step Summons On Now |
| 603001 | 1455 | Paid Only: Abyssal Werebeast Multi-Step Summons On Now |
| 604001 | 1476 | Paid-Only Yuletide Weapon Multi-Step Summons On Now |
| 609001 | 1573 | Paid Only: Abyssal Songstress Summons On Now |
| 610001 | 1514 | Paid-Only Hallowed Winter's Night Multi-Step Summons On Now |
| 611001 | 1569 | Paid Only: Divine Girl Multi-Step Summons On Now |

The remaining 301 unlinked summons are **unresolved associations**, not necessarily 301 missing notices. They include weekly summons, tickets, early banners and possible shared announcements. No title-only, parent-banner, paid/free, or date-agnostic substitutions were accepted.

The pack also contains two summon-link keys, 557001 and 560001, absent from this reconstructed non-chapter catalog. Their notice records exist. These keys need separate ID/run verification; the audit does not silently redirect them.

## Verification and files

The old and recovered packs have identical summon maps and produce identical event matches. All 201 existing catalog notice targets are present in the pack. Both pack hashes remain unchanged. Nine focused tests pass, covering rerun isolation, duplicate candidates, damaged quotation marks, source category errors, text IDs, reviewed aliases, base-catalog precedence and medal-exchange eligibility.

The reproducible auditor is `scripts/audit_summon_links.py`, with tests in `scripts/test_audit_summon_links.py`. It emits the following into `.build/notice-audit/summon-link-audit/`:

- `available-event-links.csv`: all **65** event/notice pairs, including all 45 Records.
- `available-summon-links.csv`: all **27** summon/notice associations with evidence reasons.
- `events.csv` / `events.json`: all **274** event chapters and match statuses.
- `summons.csv` / `summons.json`: all **529** reconstructed summon entries and link statuses.
- `summary.json`: totals, compared-pack checks, source hashes and audit scope.
- `validation.json`: independent output consistency, source-hash and pack-integrity checks.

Run with `python scripts/audit_summon_links.py --master-dir <original master JSON folder> --text-db <Archive archive.db>`. The recovered and old pack paths are the defaults and can be overridden.

No application mappings, catalog rules, notice records or image files were changed by this audit.
