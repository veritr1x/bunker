# Summon and event notice link investigation

**Expanded audit:** [Summon and event notice link audit](SUMMON-NOTICE-LINK-AUDIT.md) covers all native events and reconstructs non-chapter summons, including medal-exchange entries. Use its totals; this initial investigation has a narrower scope.

Checked 2 November 2026 against the pinned notice pack, recovered candidate, native master data, English Archive text, catalog rules and configured event summons. This is an investigation; application code and notice packs were not changed.

## Record: Sunset Port

The native event is chapter **509**. Both packs contain notice **1201** (Coming Soon) and **1208** (On Now). Notice 1208 was published at the event's exact start, **30 June 2023, 02:00 UTC**. The earlier 2021 event must not silently be treated as this 2023 rerun.

The native event navigation points to **exchange shop 6079** (destination type 3), not a summon. Sunset Port is absent from the 31 configured event-box summons. No direct summon ID can therefore be inferred from that navigation. The event's notice is available, but the current notice system exposes only summon-to-notice links; it has no event-chapter-to-notice map.

The separate **Seasonal Sunset Swimwear Summons** is summon 44, dated August 2021 in the native home banner. It has no dedicated notice in either pack. Linking it to the June 2023 Sunset Port notice would misidentify both the announcement and the run.

## Wider results

| Check | Result |
|---|---:|
| Summon links stored in each pack | 154, identical between packs |
| Distinct native home-banner summon targets | 300 |
| Native targets with a pack or explicit rule notice link | 154 |
| Native targets without either mapping | 146 |
| Configured event-box summons | 31 |
| Event-box summons with an existing notice link | 0 |
| Event boxes with one notice matching the exact native title and start time | 14 |

Of the 146 unmapped native targets, first master start years are 2021: 39; 2022: 64; 2023: 4; 2024: 8; placeholder 2099: 31. These are source-data target counts, not a count of currently visible summons or a claim that all have recoverable announcements. Exchange dates and catalog rules can make placeholder-dated banners usable.

The 14 exact event-box candidates include Cascading Mage (682), Blazing Dynast (857), Tempestuous Daemon (918), Aurora Senior Officer (1015), Gloomy Dynast (1122), Cascading Resentful Witch (1176), Blazing Personality Amalgam (1218), Gloomy Binding Oculus (1254), Blazing Mage (1323), Nelgel the Netherfiend (1381), Cascading Phantom (1432), Tempestuous Armed Aberration (1489), Cascading Personality Amalgam (1570), and Blazing Binding Oculus (1598). These are proposed associations, not newly recovered notice bodies.

## Cause and scope

`bunker_notices.go` resolves a summon through its explicit InformationId or the pack's gacha map. The mobile bootstrap registers reverse links only for explicit InformationId values. `bunker_event_summons.go` sets RelatedEventQuestChapterId but no InformationId, so all 31 event-box entries miss this route. The recovered candidate repaired image content and added four notices but retained the same gacha mapping.

Some links can therefore be repaired using content already held; earlier announcements still require additional verified data. Event-to-notice associations and summon-to-notice associations must be represented separately, with rerun dates preserved.

Machine-readable evidence is in `.build/notice-audit/summon-link-investigation/summary.json`, `native-banner-link-audit.json`, and `event-box-link-audit.json`. Source hashes and the exact Sunset Port master rows are preserved there. The default and recovered pack hashes remain unchanged.
