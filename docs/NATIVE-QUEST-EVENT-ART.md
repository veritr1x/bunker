# Native event-art counterparts

Two native English quest images are now linked to previously unmapped stand-in
notices in the source corpus:

| Notice | Native banner | Event |
| --- | --- | --- |
| 1442 | `event_mom_banner_579` | Record: Seat of Shadow |
| 1630 | `event_mom_banner_541` | Record: Foundation of Fortune |

The preserved original thumbnails and native artwork share the character,
backdrop, event title and “Resurrected Event Quest” wording. **The native
images omit the original thumbnails' “Coming Soon” badge.** They are scoped
native event-art alternatives, not exact original website replacements. The
original coming-soon banner variants remain missing.

The native `EventQuestChapter` rows identify banner IDs 579 and 541, and their
English name keys identify the same events. The native start times agree with
the starts announced in the notice bodies; both notices were published 48
hours before those starts. The raw native end times and notice body text are
preserved without assuming that every time field has identical semantics.

The search exported all 377 checked English `ui/quest` image objects, containing
372 distinct PNG payloads. Twenty-two of the then-45 unmapped stand-in notices
had preserved thumbnails for comparison. Uniform-border trimming was used only
for analysis where a native UI texture contains opaque padding; the exported
and packaged PNGs are unmodified. Similarity scores selected candidates for
visual review and were not used as automatic proof of identity.

The two accepted images are included in the main source corpus's `game`
family, together with native bundle hashes and the explicit limitation
`safe_as_exact_original_website_replacement: false`. Their proof records retain
the source thumbnail, native image/object metadata, quest rows, names, start
times, source hashes and review conclusion. All previous 218 game-image records
are preserved exactly.

This raises the main game-family image count to 220, or 264 when the separate
44 promotion images are included. Stand-in notices without mapped native game
art decrease from 45 to **43**. This is an alternative-art mapping count: the
764 missing exact original website image paths do not decrease. Neither the
default notice ZIP nor the existing 951-notice candidate was changed.
