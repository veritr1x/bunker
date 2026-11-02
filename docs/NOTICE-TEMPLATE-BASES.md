# Surviving notice bases for reconstructed pages

> Latest full fidelity audit (2 November 2026): all 203 reconstructed pages were rebuilt and rendered at 360px and 640px. See `artifacts/notice-template-review/fidelity.html` and `artifacts/notice-fidelity-audit/fidelity.json`. Earlier counts in this research history describe previous passes.

Checked 2 November 2026. **Every one of the 220 synthetic pages has a surviving notice base. Seventeen are covered by surviving same-run notices and link directly to them. The remaining 203 are reconstructions with varying amounts of recovered content.**

The first template candidate reused heading order and a few generic Notes sentences. It was substantially thinner than the original pages: Paid-Only Fractured Prisoner had one small banner and about 600 text characters, compared with 29 images and about 5,800 characters in the Fractured Songstress reference. Calling that a full template adaptation overstated the result. The revised candidate restores native presentation assets and target-specific summon facts as described below.

This includes the previous 201 generated summaries and the 19 earlier rerun reconstructions. Within the original 328-entry missing-link cohort, the new candidate has **125 links to surviving notices and 203 adapted reconstructions**. The candidate holds **1,154 notices and 482 pack-level summon keys**.

## New direct links

| Summon IDs | Surviving notice | Evidence |
|---|---:|---|
| 540001 | 895 | Same New Year's Luck of the Draw paid banner, original start and recorded costume roster |
| 580001 | 1336 | Tale of Resistance / paid Mechanical Captain, same start and original-run exchange roster |
| 583001 | 1371 | Tale of Resistance paid all-character banner, same start and roster |
| 588001 | 1380 | Never-Ending Adventure / paid Oathbound Songstress, same start and roster |
| 608001 | 1557 | New Year's Luck of the Draw paid multi-step, same start and roster |
| 612001 | 1615 | Japanese 3rd Anniversary paid multi-step, same start and roster |
| 456, 457 | 903 | Exact January schedule slots and native free-daily banner terms |
| 554 | 1382 | Explicit DQX commemorative one-time free 10-summon section, matching native display period |
| 600, 601, 602, 603, 604, 605, 609, 610 | 1592 | Exact rotating Story Completion Countdown schedule slots and native free-daily banner terms |

The free crossover uses its campaign notice, not the same-date gem-priced DQX summon announcement. The new direct links are validated against notice text and original native banner periods; a similar title alone cannot create a direct association.

## Bases used for the remaining pages

The audit uses **73 distinct original notices** across all 220 matches, including the 17 direct links.

| Basis | Pages |
|---|---:|
| Previously verified rerun reference | 19 |
| Same notice family and compatible format | 160 |
| Same Automata crossover franchise | 5 |
| Manually reviewed format reference | 9 |
| Broader structural analogue | 10 |
| **Adapted reconstructions** | **203** |

Examples include:

- Fractured Prisoner → **1012**, Fractured Songstress: ordinary premium summon structure.
- Abstract Captain → **733**, Abstract Ruler; paid counterpart → **734**.
- Early two-character weekly banners → matching later weekly announcements, such as **699** for Argo/Noelle.
- Old Variation boxes → matching Variation announcements: **1015** for Senior Officer, **918** for Daemon, and **1489** for Armed Aberration.
- Automata Vol. 1/2 → **1052**, with paid multi-step → **1053**. Their shared exchange is not treated as proof of each volume's featured pool.
- Earlier Replicant → **1050/1051**, retaining the original 200-shard exchanges.
- Paid elemental banners → **962** as a broader paid weapon-support layout; generic elemental banners use **801**. Their support-specific guarantees are excluded.
- Permanent premium tickets → **683** or **650** as ticket-notice formats. A normal gem banner's optional premium-ticket payment does not misclassify it as a permanent ticket summon.

The ten broader structural matches are 43, 52, 60, 70, 71, 85, 124, 970124, 9000007 and 9000011. They have usable presentation bases, not established equivalence of historical mechanics. Each row in the audit records the exact base and match strength.

## What adaptation copies

The builder reads each base's actual section order and heading markup, then fills the relevant sections with the target's own content: Duration, Characters & Weapons, Summons Details, Shards/Exchange, event instructions and Notes. A small whitelist of generic Notes sentences can be reused. The rich renderer adds native title graphics, promotional panels, costume and weapon icons, rarity graphics, gem and shard icons, original-style period bands and Notes lists. Source-only sections for later costumes, duplicate-material campaigns, resonant bonuses, memoirs or event missions are excluded unless target evidence supplies them.

Across 203 reconstructed pages, **200 have recovered title graphics, 180 have promotional panels (269 panels total), and 86 have supported detailed summon configuration tables**. The tables restore draw counts, prices, payment type, guarantees, use limits and known bonuses from each target's configuration. There are 715 additional image members, extracted from native bundles or existing extracted native images and encoded as lossless WebP. Decoded RGBA equality is verified and image provenance is embedded under `templates/rich-assets.json`.

For Paid-Only Fractured Prisoner (39), the revised page has 18 image tags: its own title graphic and 700×370 original promotional panel, native costume/weapon icons, stars, gems and shards. It explains its 3,000-paid-gem 10x summon, five-use limit, guaranteed minimum rarity, featured character condition and 200-shard exchange. The later Songstress notice's Black Pearl bonus, 1.5× rate, Subjugation season effects, event bonuses and awakening rewards are not evidence for this 2021 run. Its period is labelled Estimated Period because the available historical window belongs to the explicitly paired regular banner 38.

### Further detail recovery

An additional pass through **66 original-run binary snapshots** recovers event medal/ticket drop bonuses for **94 reconstructed pages**, with **433 weapon/event/reward rows**. Each association follows native foreign keys from the event chapter and period through sequence, quest, quest bonus, weapon group, effect group and consumable reward. Ascension thresholds are evaluated separately at counts 0–4. Partial or unresolved date terms are withheld; absent values are not replaced with zero.

For Fractured Prisoner, **Record: Coffin of Repose** is now included with Faulty Greatsword and Phoenix Dagger each granting **+2 / +5 / +8 / +11 / +15 Coffin of Repose Medals** at ascension counts 0–4. These facts come from its own historical snapshot, not the later Fractured Songstress event. This adds four image tags to the earlier 18-image revision. The earlier Replicant notice receives its own Replicant Medal bonus table. All 14 reconstructed Variation box pages also receive recovered native weapon drop bonuses.

The earlier “117 missing phase tables” figure included **14 event-box pages where gem-price phases do not apply**. The remaining **103 non-event pages** comprise 83 without explicit phase configuration, 19 earlier verified rerun reconstructions without explicit phase configuration, and one withheld payment conflict (405). Event-box reward tables already existed; their drop bonuses are the newly restored content.

This still does not recover complete historical summon pools or original per-item rates. Some costume stat bonuses, Subjugation effects, full featured weapon lists, guarantee/step terms and duplicate rewards also require further evidence. A costume or weapon appearing in an exchange does not independently establish its featured rate. An event without a recovered bonus association is not automatically missing one; the banner might not have granted such bonuses.

Evidence is in `inputs/summon-notice-event-bonuses.json` and embedded as `templates/event-bonus-evidence.json`. Regenerate it with `python scripts/recover_notice_event_bonuses.py` before building the candidate. The per-page remaining-detail audit is `artifacts/notice-template-audit/remaining-details.json`.

The base's dates, artwork, featured lists, stats, odds, guarantees, rewards, costs and publication timestamp are **not** transferred. When the featured pool is unverified, character cards are labelled Exchange Characters. The earlier Griff roster correction, original Replicant shard price, inferred dates and payment conflicts remain protected. Three entries still have no recovered title or banner artwork. These reconstructions do not establish missing individual rates, full historical pools, duplicate rewards or event bonuses merely by sharing a notice format.

Titles retain the **[Reconstructed]** label. Player-facing bodies contain the useful summon and event content; audit explanations, snapshot filenames, source panels and repeated limitations are kept in the external audit and embedded pack metadata. The base-comparison reader links each target to its original base. Short headings such as **Estimated Period** and **Banner Period** distinguish date types without explanatory paragraphs.

The UI cleanup preserves dates, rosters, currencies, prices and rewards, while leaving unavailable or disputed values omitted. The base map retains the removed HTML under `player_ui_removed_html` for review. Original announcement text is not claimed to have been recovered merely because the format has a close match.

## Files and checks

- `inputs/bunker-notices-template-based.zip`: new separate candidate.
- `inputs/bunker-notices-template-runtime.zip`: builder-compatible export with the same notice and image content; audit metadata is excluded.
- `inputs/summon-notice-template-map.json`: all 220 target/base associations, source-body hashes, direct-link evidence, section order and excluded headings.
- `artifacts/notice-template-review/index.html`: searchable side-by-side navigation to each target page and its base.
- `artifacts/notice-template-review/comparison.html`: original 1013 versus reconstructed 1500000039, using the same actual game CSS and viewport widths.
- `artifacts/notice-template-audit/base-notices.csv`: complete base audit.
- `artifacts/notice-template-audit/all-328.csv`: updated cohort status.
- `artifacts/notice-template-audit/summary.json`: counts and candidate hash.
- `scripts/build_notice_templates.py`: reproducible matching, validation and adaptation.
- `scripts/rich_notice_content.py`: native presentation extraction and target-specific detail rendering.
- `scripts/recover_notice_event_bonuses.py`: historical event/weapon/ascension bonus recovery.

Run `python scripts/build_notice_templates.py --audit-only` to regenerate the associations, or omit `--audit-only` to build the candidate and reader. Tests run with `python -m unittest discover -s scripts -p test_notice_templates.py`.

Thirteen template tests cover direct matches, wrong campaigns, year rollover, ticket/payment classification, target shard prices and rosters, omitted source rewards and preservation of uncertainties. Five rich-content checks cover the paid Prisoner rules, pixel equality with its native graphics, all image references and hashes, player-text cleanup, and unchanged original records/assets. Eight event-bonus checks reject unrelated weapons, broken quest links, wrong possession types, unknown ascension values and partial date terms, and verify the real Prisoner snapshot. The earlier premium-ticket label correction uses native item 1002 instead of item 3001's Small Stamina Recovery name.

ZIP CRCs, target IDs, original-record preservation and all retained asset bytes are checked during the build. All 951 original notice records stay unchanged; only synthetic pages and their proven direct replacements change.

This pack changes notice content and navigation only. The twelve previously identified gameplay-payment configuration conflicts are not fixed by a notice pack; their disputed price tables remain withheld. The APK currently installed in BlueStacks contains the earlier sparse pack, not this rich revision. Default and source packs are unchanged.

## Full reconstruction fidelity pass

The latest candidate keeps all 951 original notice records and original assets unchanged, and audits all 203 reconstructed pages. It has 202 usable draw-option tables and one deliberately withheld payment conflict (405). Pricing sources are native promotional panels for 17 pages, existing target configurations for 77 pages and observed running-game configurations for 108 pages. Native advertised prices take priority over generic fallbacks; the 108 runtime-sourced cases are not claims that their complete historical rules were recovered.

The pass checks 267 native promotional bundles (269 placements), restores original rewards, relative rate boosts, elemental guarantees, guaranteed-slot details, round limits and duplicate-material features, and adds full configured rewards to all 14 Variation boxes. Native event bonuses now appear on 100 notices: 437 weapon/reward rows and 259 costume/character stat rows on 86 pages. The explicitly shared Half-Year Anniversary currency connects the short festival to the original-run exchange and only overlapping event bonus chapters.

Examples corrected by direct panel review include 1,500-paid-gem Wind/Dark/Water 10x summons, 2,000-gem bonus banners with Advanced Handbook or Black Pearl pieces and use limits, New Chapter step rewards and three-round limits, and elemental step guarantees. The final catalog's unsupported four-star label on summon 49 is replaced by its own native title graphic's NieR Day Bonus Summons title. Exchange rewards on the festival's 50-medal trade are kept separate from free-summon rewards.

All 203 pages have a proper opening, consistent section order, Notes and a functioning live Details/Rates link. Two hundred use their native title graphic; three without recovered art use styled text title panels. Step-up overviews remain visible and individual step panels are expandable. Original exact per-item rates, full historical pools, some conditional effects and unavailable original artwork are not invented. They remain archival gaps in the audit.

Validation: 81 focused tests pass, including original-record/asset preservation, native image hashes and lossless pixels, historical bonus foreign keys, source-specific prices, ticket labels, distinct free-summon opportunities and native reward/slot terms. Every reconstructed page rendered at both 360px and 640px without broken images, root horizontal overflow or missing navigation. Twenty-three representative pages have saved screenshots under `artifacts/notice-fidelity-audit/browser/`; final machine results are `browser-audit-final.json`.

The runtime export is `inputs/bunker-notices-template-runtime.zip`; the canonical candidate also retains its audit metadata. The installed APK is unchanged. Confirmed original-price versus running-server differences are recorded in `artifacts/notice-fidelity-audit/gameplay-alignment.json`; notice corrections do not silently change game costs, rates, grants or saves.

## Native costume and weapon thumbnail backgrounds

The reconstructed pages now use 253 complete native thumbnails (94 costumes and 159 weapons), appearing on 161 pages. Other reconstructed pages do not display costume or weapon thumbnails. The native 1.5.7 APK supplies `thumbnail_bg_*_a`, `thumbnail_frame_*`, `weapon_icon_*` and `attribute_*` layers. Rarity, weapon type and element come from each item's native master record, so evolutions sharing artwork keep their own rarity border.

The renderer reads the full 102×102 texture rather than a trimmed Sprite export, places it at (4,4) inside the 110×110 frame, and adds the appropriate native badges. Background RGB is baked opaque to match the published web icons. Recovered web examples from original notice 175 validate placement and approximate colors; original web compression differs from the native texture compression. These are native asset compositions, not AI-generated illustrations. All source hashes, layer identities and placement are recorded in `templates/rich-assets.json`.

`scripts/native_notice_icons.py` implements the composition. Four additional tests cover original-icon similarity, different rarity borders for shared weapon artwork, native badge identity and the absence of bare costume/weapon images in reconstructed pages. All 85 focused tests pass, and all 203 pages still render at 360px and 640px without failures. The icon revision's browser report is `artifacts/notice-icon-frames/browser-audit.json`. Original notices and their existing icon assets remain byte-for-byte unchanged.

## Installed Android revision

The later installed artifact is `artifacts/bunker-1.7.0-native-icons.apk`, SHA-256 `b6f26ff34eba45d23d749948996f9220958376205adcc0075904367c95fed49b`. Its runtime notice pack is `5a6fa82f5ba34a132d3343431e398e08633e0ea5579159d2e1fad098d68e0f28`; all 3,664 embedded notice members were verified byte-for-byte. APK Signature Scheme v2 verification passed. ADB installed it over the existing app, preserving all eight save files and the resource link. The game activity launched with an empty crash log; its server served the updated notice, icon references and table CSS. Full gameplay was not retested.

The published web build completed, but its output was not saved after browser control was lost. The installed APK was rebuilt locally using the exact 22 published builder source files and the same original APK/master inputs. The published launcher library's uniquely matched notice CSS constant was replaced within its original 6,793-byte extent by 6,790 bytes of compressed updated CSS plus whitespace. All other library bytes and ELF offsets stayed unchanged; other launcher ZIP members stayed unchanged. Computed styles matched the source CSS on original 175 and reconstructed 39, 70 and step-up 507001. This deployment step is recorded under `.build/web-builder-native-icons-run/`; a future normal native build should compile the checked-in CSS directly.

The repository commit contains source, tests and research documentation. Native game assets, generated notice packs, APKs, browser captures, private saves and deployment evidence remain local ignored files; this does not publish a new default pack or a release. A requested Claude review did not run because its CLI returned an invalid OAuth token, so the changes are not Claude-reviewed.
