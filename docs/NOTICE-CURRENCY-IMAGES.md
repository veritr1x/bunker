# Notice currency image recovery

This pass investigates all 27 missing `/images/{en|ko}/operations/coin/`
paths in the current notice audit. It identifies six native reward counterparts
directly and six further identities under explicit inferences. Fifteen paths
remain ambiguous. No original website image bytes were recovered: the exact
website-image gap remains 764.

Open `inputs/notice-currency-icons/index.html` for the portable reader. It
contains 54 native PNGs (icon and standard variants for 27 candidate currency
assets), four already-preserved notice WebPs, the source notices, native tables,
and per-path evidence. These currency assets were already in the item library;
this pass adds their relationship to missing notice images.

## Six direct native reward matches

The original HTML identifies resonant weapons and five reward bonuses, one
for each ascension count. Weapon names map to native weapon asset IDs. Native
`QuestBonusWeaponGroup`, `QuestBonusEffectGroup` (type 3), and
`QuestBonusDropReward` rows identify the consumable rewards for those weapons.
Intersecting candidates across observations gives these six unique identities.

| Original coin basename prefix | Native consumable ID | Native image asset | Identity |
| --- | ---: | --- | --- |
| `0cfeb82a11` | 6068 | `consumable200109` | Tempestuous Armed Aberration Summons Ticket |
| `0f11ec7921` | 6023 | `consumable200057` | Cascading Mage: Bronze Summon Ticket |
| `13e57841a1` | 177 | `consumable110177` | Bronze FFXIV Medal |
| `6ac17f68a1` | 6049 | `consumable200083` | C. R. Witch: Bronze Summons Ticket |
| `95bc20dde2` | 221 | `consumable110221` | Bronze Hallowed Struggle Medal |
| `b581233121` (EN path) | 74 | `consumable110074` | Bronze Rebellion's Illusion Medal |

All 253 checked target weapon/bonus observations match native reward vectors.
Both table layouts are covered: a separate currency column, and repeated coin
icons inside each ascension cell. HTML5 parsing repairs malformed source rows
before expanding row spans. Monster's Phosphorescence uses the independently
documented `wp004029` name association, rather than guessing an abbreviation.
Native currency descriptions resolve the abbreviated C. R. Witch event name.

Only these six direct mappings are added to the main recovery corpus. All 191
previous native-icon records remain exactly unchanged. The corpus now contains
197 supplemental icon records covering 194 original paths; three reused memoir
paths retain their per-notice scopes.

## Further inferences and remaining ambiguity

The separate reader records six further identities under stated assumptions:

- Different currency icons displayed together in one bonus cell represent
  different reward items. This narrows the Cascading Mage silver/gold tickets,
  Silver A Question of Decorum Medal, and Gold The Devil's Tray Medal.
- A reviewed surviving WebP has a silver border matching native Silver Eternal
  Steps Medal. Together with the directly identified bronze medal, this narrows
  the missing Eternal Steps icon to gold. The PNG and WebP pixels differ.
- The KO Rebellion's Illusion bronze path shares its opaque basename and
  displayed currency set with the directly identified EN path. Its original URL
  remains a separate record.

The reader marks these six identities as inferred and excludes them from the
main corpus mappings. It shows all candidates for the remaining 15 paths,
including silver/gold pairs with identical weapon-bonus vectors and all three
Rebellion's Reality medal tiers. Display order alone is not treated as proof.

## Further Wayback check

An all-status CDX query searched the English notice host's `/images/` prefix
for the 24 distinct opaque basenames, including regional and double-slash
spellings under that prefix. Three double-slash URLs were found, all for
Rebellion's Reality currencies. All three replay payloads were retrieved and
their SHA-1 digests verified against CDX. They contain the same 1,556-byte
application shell, not images; its linked script/style version was already
preserved. This closes that spelling-variant lead without recovering a coin.

This query does not cover every possible host or every archive. The existing
764-path exact-URL coverage remains separate evidence.

## Validation and provenance

The reader retains the original notice excerpts and tables, all five native
tables used in the join, native text labels and descriptions, the independently
established weapon-name association, native bonus rows, image source bundle
paths and hashes, and the inference steps. Source hashes identify the input
files; no original-byte identity is inferred from semantic asset matching.

Both reader pages have 146 checked local references and no broken local links.
All 54 PNGs and four WebPs fully decode and match their recorded hashes. The
archive manifest records every packaged file's SHA-256. The default notice pack
and candidate notice pack remain unchanged.
