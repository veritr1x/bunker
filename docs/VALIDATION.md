# Validation

## Fixes from the Lunar Tear forks — 2026-11-08

- Server Go tests with the patched game data and a save from 2026-10-06: 417
  pass, ten of them new. The same four tests fail as without these changes
  (TestBattle, TestEventSummonsOnTheGameData, TestLabyrinthSeasonsMoveOn,
  TestEventLoginBonusesStampDaily), with the same messages.
- Android 16 emulator (bunker_api36), calendar off, the save from 2026-11-08
  (backed up first), the APK built at bc369ac and signed with the web build
  key. Sign-in sent every table (GetUserData, then GameStart) with no new
  pop-up. A Subjugation battle left open was resumed and finished
  (FinishBigHuntQuest OK), and a Subjugation mission cleared during it. The
  Sun/Moon map loaded with its ornaments; its two UpdateSequence calls
  answered in the same second. The log had no errors.
- The Premium Shop showed the same limited packs on 1.10.0 and on this
  build: with the calendar off the patched game data keeps them open, so
  the IUserLimitedOpen fix shows only with the Original calendar, which was
  not tried.

## Auto-repeat with the calendar on — 2026-11-08

- Android emulator, Global, Original calendar (week 1). Character Quests ›
  Rion Quest 1, Auto-repeat ×10: the first clear finished
  (`autoOrbit iter cleared=1/10`), then the game showed "The quest period
  has ended." and sent FinishAutoOrbit without asking for the next run. With
  the calendar off, Record: Pure Hills Quest 1 went on to its second clear.
- In the game's code the retry (SubQuestResultAction.OnTapRetryButton) calls
  CalculatorQuest.IsValidStartQuestTerm, which checks the chapter's dates and
  then looks its type up with TryGetEventQuestType. A temporary hook on
  CalculatorDateTime.IsWithinThePeriod showed the chapter's dates passing
  (Aug 2025 to 9999) and no schedule check after it: the type lookup failed.
  The calendar's game data had m_event_quest_chapter and six tables keyed
  by it out of first-column order (338 chapter rows, 35 out of place), and the
  game finds rows by binary search.
- The same game data with those tables sorted: the run asked for its second
  clear (`autoOrbit continue cleared=1/10`). The build with the fix rebuilt
  the emulator's calendar data on its first start (data version 2), every
  table in order.

## Launcher Auto deploy — 2026-11-08

- Android emulator: ⋮ shows AUTO DEPLOY: ON by default. Turned off, a normal
  launch stayed on the launcher with Lunar Tear standing by after 15 s.
  Turned on again, a normal launch opened the game.

## Deck Builder — 2026-11-08

- iPhone 15 Pro, All maxed: pages of six decks loaded in about 2.4 s each
  when simulated against 50 opponents (stage preparation 12.5 s); with the
  baked numbers shown they load without simulating. On a copy of a real save
  the first 12 attack and defense decks show the values they were ranked by,
  in order.
- iPad: a deck written to Arena decks 1, 2 and 4 landed in the save (deck
  type 2), so the Loadout screen (deck type 1) did not show it. The deck
  picker now offers Loadout decks, ticks nothing by itself and lists what each
  pick replaces before REPLACE.
- The phone-style stage check: a stage prepared as the phone prepares it,
  with each costume's baked karma (set_costume_karma_batch), matches the
  bake's fingerprint (test_deckbuilder_session).
- Pod Programs readability: every page at phone and iPad sizes, portrait
  and landscape, light and dark, popups and ⓘ notes open: no text under 12
  px, none cut off or off screen, contrast at least 4.5:1, apart from
  checkboxes and radio buttons inside rows that can be tapped anywhere.

## Mods expansion — 2026-11-07

- Android emulator, Global, Comfort mods, game running. Mods page: six
  groups (Preset, Quests, Items & shops, Summons, World, Challenges), open,
  each folding; the bonus line read "×1 Turn on a challenge to earn it.".
- Hard enemies ×2 and Slow skills saved on the page: "Saved. Challenges are
  in the game data. The game returns to its title screen to load it." The
  device's game data then had 9,459 of 9,553 enemy costume rows at twice
  their level and 28,314 skill cooldowns ×1.5, with the gift text kept; an
  unchallenged copy sat beside it. The game showed its "Returning to title
  screen" and signed in again on the challenged data with no crash.
- Challenges off: the game data's SHA-256 matched the unchallenged original
  (a204a35b…) and no copy was left.
- Start a new day: saves/day-start.json and client-days.reset written beside
  mods.json, the game closed; after Deploy, Mama's News played again and the
  friend list's cheers read 0/100.
- Friends from the story: 2B and 9S in the game's friend list with their
  portraits, 28/100 friends.
- Dark Lair: Easy (1 time daily), deck force 216,226 against 66,000, on
  auto. No challenges: won in about a minute. Unlimited daily plays and EXP
  ×3: the clear left its daily count at 0 and Try Again played it again;
  each clear gave +1,944 player EXP (648 ×3) and +96 character rank EXP
  (32 ×3). Free skips: a skip kept the tickets at 2,680. With 0 tickets the
  game greys out Skip by itself, so Free skips needs one ticket in hand.
- Hard enemies ×2: the same quest was lost at its wave-3 boss. Weakness only
  with Slow skills: won in about 100 seconds against about 60.
- Start a new day after the build with the review fixes: Mama's News played
  again. The login bonus did not, because this save's last stamp is dated
  2028-12-22 from an earlier calendar jump; the server counts a stamp at or
  after today as received, so a stamp from the future blocks it whatever the
  day (a calendar-off issue, not Start a new day's).
- Comfort preset afterwards: "Comfort preset saved. Challenges are off: the
  game data is as it was."; the game data's SHA-256 was the original's again.
- Tests: 9,000+ enemy levels doubled on the real master, subjugation and
  player-range costumes untouched, ×1.5 rounding and the 66 cubic-curve
  enemies within 2%, weakness halving only the player's normal-battle table,
  27,000+ player cooldowns ×1.5 with enemy-only ones and the shared fill
  tables untouched, stat curves byte-identical; challenges applied once
  through activate, restore, gift text and the calendar's next loop, and
  removed exactly.

## Pod Programs › Gift — 2026-11-07

- Android emulator, Global, All content, game running throughout. Gift
  opened from the Bunker menu; Summoning › Summon tickets › Premium Summon
  Ticket: "Up to 99,999 more." Sent 3: "Sent: Premium Summon Ticket ×3. It is
  in the game's Gift Box."; the game process kept running and never went to
  the title screen. The Gift Box listed "Premium Summon Ticket x3 — From
  Bunker, with love. — Deadline 01/01/2100"; Receive gave it (with the
  Comfort mod's tickets-as-gems on, as 900 gems: 278,201 → 279,101).
- Small Character Enhancement held at 99,989 (limit 99,999): room 10; sending
  11 refused "only 10 more can be claimed now". Collection › Debris: 196 of
  233 shown as Owned and not selectable. The Item Editor showed "14 gifts are
  waiting in the Gift Box" linking to Gift; Gift's waiting list was empty
  after the claim.
- Found and fixed on the way: builds ran the upstream patcher, so built
  masters lacked the gift text; the room check was refused while the server
  ran; the shim's granter had no possession limits (room read 2,147,483,647);
  backups refused the reason "gift"; and a gift with no deadline made the
  game fetch the Gift Box but never open it (the same gift with a date
  opened, without one it did not), so Bunker gifts expire 2099-12-31.
- After the branch review: with the server running, the room comes from the
  running server's granter (32 ms, no second master-data load in the log);
  with the Comfort mods on, Small Stamina Recovery's room was 7,783,272
  (the gold cap left ÷ 120) and Premium Summon Ticket's 7,157,585 (gems ÷
  300). A count of 50 against a room of 10 was refused ("That is more than
  can be claimed now: up to 10.") with SEND disabled. The CI unit-test jobs
  now prepare the sources; a clean checkout's web builder test failed without
  that and passes with it.
- Game data without the gift text: restored a snapshot from before it
  (Content › Previous versions, the game running). Gift showed "The first
  gift also adds its text…" and a working Send. Sending Small Character
  Enhancement ×1 added the text (the result is byte for byte this build's
  All content, a204a35…; the old data kept as a snapshot; the label stays
  "Restored snapshot"), the game showed its Refresh dialog and went to the
  title screen, and after signing in the Gift Box listed "Small Character
  Enhancement — From Bunker, with love.".
- Content with the calendar off: choosing Original calendar hid the Content
  section and showed the start panel; Everything open brought it back.
- `go test ./...` passes with either master; all 31 Android tool test files
  and the notice and web builder tests pass. iOS not run; the Original
  calendar's gift dates not checked on a device.

## Draw buttons without a false sale — 2026-11-06

- Cause, from the iOS UnityFramework the dump was made from:
  GachaDrawButton.SetData(priceType, regularPrice, price) shows the sale group
  and the regular price, and colours the price, whenever regularPrice differs
  from kInvalidRegularPrice; the class has no static constructor, so that is 0.
  Lunar Tear sent each phase's price as its regular price.
- Fix [38629bd]: the regular price is cleared unless it is above the price. Tests
  pass with either master. Emulator: Mama's Exciting Festival shows "1 time
  300" and "10 times 3000", nothing struck through.

## Summon prices against their art — 2026-11-06

- Of 533 premium summons (Global), 235 take their prices from a recovered
  notice and 90 from their art; the other 198 used the usual prices by
  default. Their summon-screen art (297 images) read by eye on labelled
  sheets beside the server's prices.
- Wrong on the server: 43, 52, 60, 85 (Japanese art), 9000007 "10x summon for
  1,500 paid gems"; 9000021, 9000034, 9000046, 9000060, 9000069, 9000091,
  9000100, 9000104 "10x summon for 2,000 gems" with a bonus 5 or 20 times;
  9000082 "a 10x summon for free"; 9002 Advanced Handbook x2, 10 times. Their
  recovered notices agree. Fixed [a9c4d27]; both masters price them so.
- 9000086 (anniversary multi-step): its art gives no prices; its notice's
  steps (2,000 paid, free, 3,000 paid, free, 5,000 paid) are the server's.
  186, 194, 405 have no limit on their art, which states limits elsewhere.
- Notices: sync_notice_prices.py on the pinned pack rewrote 10 reconstructed
  notices [3ede598]. Emulator, from the device's server: notice 1500000186 one 10x
  for 3,000 paid gems with its bonuses, 1500000060 1,500 paid gems,
  1509000082 free once a day; Summon Details for 60 "1500 paid gems".

## Calendar off without the dialog — 2026-11-06

- Android emulator, 1.9.0 plus [0ae30da]. Before: after a jump to week 112
  (December 2028) and Calendar off, the game's day markers stayed on the 2028
  day (only "Show original dates" changes cleared them). With the clock moved
  to 2026-11-07, signing in showed no login bonus, Mama's News or FREE badges;
  with the markers cleared by hand, Mama's News and FREE on Gift Box and
  Summons came back.
- Tried first: clearing them inside the running game on its way to the title
  screen (PlayerPrefs.DeleteKey, the cached PreferenceKeyValue states and
  maps). The store was cleared, but signing in again in the same process still
  showed no Mama's News; the next start did. So the game is closed instead.
- After: calendar on and the jump with the game running (no reset file, the
  game back at the title screen); Mama's News at the 2028 date. Calendar off
  from the page's form: no dialog, the game process ended, client-days.reset
  written. Applied All content, Deploy: "the clock went back: cleared the
  game's day markers" before the game started, and Mama's News at
  2026-11-06.
- Android tool tests pass (test_calendar_view: the reset file only when the
  clock goes back; test_tools_live: the game closed without asking). The iOS
  launcher compiles (clang -fsyntax-only); not run on a device.

## Shards on every summon — 2026-11-06

- Both masters (Global 20240404193219, Japan 20240405123139) loaded through
  the runtime catalog. Premium summons without a shard: their real notice
  (Global, 1,167 notices) and the summon-screen art from the client bundles,
  read with text recognition (EN 166 images, JA 130).
- Notices or art name a shard on 17 summons that gave none: 506, 507,
  9505061/62/71/72 (notices 1142, 1300, 1620), 10107, 10108 (notice 1106),
  554, 581, 523001, 563001, 900003, 581001, 582001, 586001, 587001 (art).
  After the fix exactly these change: 17 on Global, 16 on Japan, where
  900003 stays without one because Japan's Lacrima Soldier exchange closed
  in 2021. Premium summons with a shard: 423 of 533 (Global), 404 of 514
  (Japan).
- The other date matches are other summons' shards: their notices and art
  name none (199, 405, 410, 433, 452, 494, 514, 529, 534, 589, 590,
  527001, 533001, 539001 and others).
- Healer & Support exchange (shop 8170): its offers dated in the shop data
  rebuild 506's and 507's notice lineups exactly; the reruns get the offers
  from their start. 9505071's ★4 weapons 33 → 29.
- Calendar on: both masters rebuilt by Pod Programs' calendar code
  (android_calendar.build_master) for a loop starting 2026-11-04, then
  loaded with the calendar set. All 17 give their shard (Japan 16), and each
  exchange is open for the whole moved run. Against the code before the
  audit, only those summons' shards changed: no date, price or kind. 554,
  581 and the Healer & Support reruns now feature their exchange as
  intended; 523001 and 900003 lose weapons of other summons starting the
  same week and now match 180 and 82, the main summons of their shards, as
  they already did with the calendar off. 183 and 184 start three days
  before their exchange opens, in the game's own dates too.
- `go test ./...` passes with either master.
- Android emulator, Global, calendar off, All content: 506's art showed the
  medal but no Held/Exchange bar, and a draw gave none. The preset had
  closed shop 8170 (end date 2020), with 134 other medal exchanges. After
  the fix [d0641d4] and applying All content again, all 135 were open; 507's
  daily draw gave Healer/Support medals 0 → 10 ("Held 10"), its two ★4s from
  the Light/Dark lineup, and Exchange opened its offers.
- Calendar on, loop from 2026-11-04, moved to week 112: 581001 (Tale of
  Resistance, Mechanical Hunter) listed for 12/22-12/29/2028 with Held 95 /
  Exchange; step 1 gave 10 shards (the Comfort mod then traded 100 for gems,
  95 → 5), and Exchange opened Moonbow Gun and Type-0 Sword at 90, open
  12/15/2028-01/07/2029. The Healer & Support rerun 9505071 showed Held 10 /
  Exchange. Calendar off and All content restored afterwards.

## Mods on the Android emulator — 2026-11-06

- 1.9.0 on the Android 16 emulator, the save from 2026-11-03 (backed up
  first). Mods page: Comfort set every mod and ×10 in mods.json, Original
  removed the file, saving single options wrote them; no restart or title
  request on either.
- Free stamina: Daily Quest: Easy logged "cost=5 free (mod)"; stamina stayed
  124. Rewards ×10: gold 1,400 against the quest's 140 in master data; drops
  ×10; mission and first-clear rewards unchanged.
- Stamina items as gold: 20 Small Stamina Recovery bought (2,400 gold) gave
  2,400 gold and no potion; two Medium ones from the gift box gave 480 gold.
  Tickets as gems: a Premium Summon Ticket from the gift box gave 3,000 free
  gems and no ticket. Shop restocks: "Remaining: 20" stayed 20 after buying
  20.
- No duplicate ★4 (Summon Rates at ★4 100%): swaps logged on banners 186,
  123 and 444, an owned weapon or a repeat within the summon each time; a
  costume pool fully owned (banner 439) was kept, as described.
- Medals as gems: banner 439 with its medals (8135) at 95: "1×100 medals of
  item 8135 -> gifts", 5 medals left, 1,000 paid gems and 100 Mama Points
  in the gift box.
- Not seen: Lost Items as gems (no Lost Item came up on the field; Go
  tests only).
- Found, not changed: banners 444 and 474 show "medals included" but the
  server's catalog has no medal for them, so they give none; banner 186
  ("Paid Gems Only") took free gems.

## Back to the title screen at once — 2026-11-06

- Android 16 emulator, the APK built at 9fea028: an item grant in Pod Programs
  beside the game wrote saves/title.now; after Close and Deploy, with no touch
  in the game, it showed "Process failed. Returning to title screen." at once
  ("Title now: back to the title screen" in the log) and the marker was gone.
  OK, Tap to Start: signed in (GetAndroidArgs ended the request), gold up by
  1, and no call was failed in between.
- iPad: the same, as checked by the player.
- interceptor tests: the marker is written with a request, removed by the
  redirect and by signing in, a removed marker lets the next call through,
  a marker that could not be written still redirects, and a stale one is
  removed when Lunar Tear starts.
- Not checked: a change while a battle runs (the dialog should wait for the
  battle to end).

## Review fixes on Android — 2026-11-06

- Android 16 emulator (bunker_api36), the APK built at 1c8737f, signed with
  the public build key over the installed app (save and game files kept),
  60 fps: the log showed "Badge pacing: ready" and "Bunker button: ready".
  The Bunker button sat in both headers (field and Quests) and opened the
  menu. Subquests showed every campaign badge's "Left: 999d", also straight
  after scrolling rows out of view and back.
- Pod Programs beside the game: POST /users/1/use for the player already in
  use restarted Lunar Tear and asked for no title screen [ea82989]. Two item
  grants in a row (1 gold each): both restarts passed the launcher's health
  check with the return pending [1c8737f], the game stayed open (same
  process), its next call (GetGiftList) showed "Process failed. Returning to
  title screen.", and Tap to Start signed in with gold up by 2. The Bunker
  button was in the top row again after the title screen.
- Not run on a device: a backup that fails with a restart that fails too
  (Android closes the game; Java compiled), the desktop master data reload,
  gifts that arrive as something else at a full stack (Go tests), and the
  once-a-second mods.json check (Go tests).

## Bunker menu in landscape — 2026-11-06

- Android 16 emulator on its side (about 914×411 dp): the Bunker menu
  showed BUNKER and the options button on one line, System on the left
  and Play (Deploy) above a Programs panel on the right, both columns
  ending level, with nothing below the screen. Tapping the Pod Programs
  row opened Pod Programs and the Archive row opened the Archive.
  Turned to portrait, the menu was as before.
- Not checked: a tablet on its side (two columns with the longer top bar
  and the footer) and the update panel shown in landscape.
- iOS: the launcher with the two-column layout compiled on a macOS runner
  (`ios-branch.yml`, Xcode, `-Wall`), and an unsigned IPA was packaged from
  it and the game's decrypted 3.7.1 IPA as the web builder does.
- iPad, installed with iloader: on its side the menu showed the two columns
  as on Android. Turned upright it stayed on its side (the game allows only
  landscape), and opening ⋮ then turned the menu upright inside part of the
  screen with the rest black. The menu, Pod Programs and the Archive now
  allow only landscape [219bfbf]; that build is packaged but not yet
  installed.
- iPad Pro 11-inch (M4), iPadOS 26.6.2, windowed apps, held upright,
  driven with WebDriverAgent [a00d7af]: the menu filled the screen upright
  with one column; a three-finger double tap during play opened it upright
  over the game; Deploy returned the game to its landscape window, and it
  took taps. Not checked: turning the device with the menu open (the
  driver's rotate did not turn the screen), Pod Programs and the Archive.

## Bunker button frame cost — 2026-11-06

- iPad Pro 11-inch (M4), 120 fps, 1080 with MetalFX, scrolling Subquests:
  Time Profiler put about 30% of the main thread's samples in the
  button's counter search. A temporary log showed `ingame_header` and
  `outgame_header` alternating every frame, each search over the whole
  interface taking about 1.3 ms. With a state per header [0c72350] the
  search fell to about 3%. The screen still showed 80 fps (frames of 8.3
  and 16.7 ms) with the GPU at about 7–9 ms a frame.
- `android/tools/test_bunker_button.py`: 13 tests passed. Not run on
  Android.
- The search under the heads-up display [88c928f]: it holds the same 9
  counters as the whole interface on Subquests; 0.2 ms a search against
  1.3. Function names from the game's metadata (Il2CppDumper) put the
  campaign badges' `UpdateRemainingTime` at 4.4% of the main thread and
  the label rebuilds it caused at about 5%. With badges once a second
  [a90b04a] the main thread was busy 39% of the time scrolling Subquests,
  against 63% before and 95% on the first build; neither shows in the
  profile. `test_display.py`: the badge tests and the frame pacing tests
  passed (the Settings tests need fastapi, missing on this Mac).
- Still 80 fps on Subquests. With the iPad cool, the field showed 109 fps
  at 4.2 ms of GPU a frame and 80 fps at 9.4 ms while opening Quests: the
  GPU is the limit there now. Not run on Android.
- Final build [5327e59] on the iPad Pro 11-inch (M4), 120 fps, 1080 with
  MetalFX, idle and heat pacing on: six camera drags under Time Profiler
  showed no hangs; scrolling Subquests was smooth; held upright, the Bunker
  menu turned upright and the game stayed on its side.
- Half-second freezes on every drag (the app's frames presented but not
  shown, Unity then waiting up to 1 s for a drawable) came with 1.8.4 too
  and with MetalFX, pacing and the Metal HUD all off; restarting the iPad
  ended them.

## Spendable event medals — 2026-11-06

- Master data (2024-04-04): event chapter 508 (Coffin of Repose) links shop
  6005, priced in medal 22, but its quests' pickup drops are 53 (33) and 54
  (2); chapter 513 (Rhythm's Citadel) links shop 6010, priced in 29, and
  drops 63 (35), 64 (4) and 65 (2). Only shop 6030 takes 63–65, and no
  chapter links to it; no shop takes 53 or 54.
- Go tests: `questflow` (53/54 drops become 22, 63–65 become 29, counts
  kept, other possession types untouched); full `go test ./...` in the
  build passed.
- The migration on a copy of the table: 22 ×10, 53 ×5, 54 ×2, 63 ×1,
  64 ×1 became 22 ×17 and 29 ×2, and another user's 65 ×7 became 29 ×7.
- Android 16 emulator, the save from 2026-11-03 with 53 ×5, 54 ×2 and
  63 ×3 added: after installing the build and starting the game, the save
  held 22 ×7 and 29 ×3 and none of the variants.
- Not checked in game: a drop from either event (neither was scheduled).
- Not changed: cage ornament visits and big hunt knocked-out costumes.
  The client has no table for either (no `IUserCageOrnament` access table;
  the big hunt report has no alive field), so storing them would show
  nothing. Story replay: the server already writes
  `IUserMainQuestReplayFlowStatus`, the only replay state the client reads.

## Pod Programs in landscape — 2026-11-06

- Android 16 emulator on its side (CSS height about 390 px): Pod Programs
  showed one short top bar (POD PROGRAMS, Close) and the tabs in a column
  on the left; the program list filled the rest of the screen. Turned to
  portrait, the screen rebuilt with the full top bar, the row of tabs and
  the sign-off at the bottom, as before.
- The same pages in a browser at 844×390 and 375×812, light and dark.
- Not checked: iPhone (the bar follows the compact height size class) and
  iPad, built but not run.

## Mods — 2026-11-05

- Go tests: `internal/mods` (no file means no mods, the file is read again
  when it changes, an invalid file turns every mod off), `questflow` (the
  multiplier scales consumables, materials and free gems but not memoirs,
  costumes or important items, nor Dark Memory quests; gold; the player
  level never falls back), `service` (unlimited stock only for daily,
  weekly and monthly restocks; Lost Item gems only for Lost Items, by
  weight), `gacha` (owned ★4 swapped for missing ones, also within one
  summon, only in premium summons and only with the mod; medals traded in
  whole hundreds for paid gems and Mama Points), `runtime` (stamina items
  to gold and tickets to gems only with their mods and only for items the
  master data has). Python: the Mods page and mods.json (8 tests).
- Android 16 emulator, the save from 2026-11-03, the game running beside
  Pod Programs: the Comfort preset saved with no prompt and no restart.
  In the Premium Shop, Anniversary Eve Pack D (lifetime stock 3, with 50
  stamina items, 30 skip tickets and 980 paid gems) gave 6,000 gold instead
  of the stamina items, the tickets and the gems; Remaining went 3 to 2.
  Skipping Story Quest 1-3 cost no stamina (999 stayed 999), paid 1,000
  gold (100 ×10) and showed its two drops as 10 each. A 10-summon of
  Mama's Exciting Festival ran with every mod on.
- That skip also showed the save's level 100 falling to 1: the save had
  been edited to level 100 with 0 exp. With the level set back to 100 and
  this build, the same skip showed Player Lv. 100 ▶ 100 (exp 40 → 80).
- Not checked in the game: restocking shop items, tickets arriving as gems,
  Lost Items, a duplicate ★4 swap and the medal trade (the summon used has
  no medals). Unit tests cover them.

## Changes beside the running game — 2026-11-05

- The 3.7.1 client's error handling, read from `libil2cpp.so` with the NDK's
  `llvm-objdump`, Il2CppDumper's `script.json` and the library's relative
  relocations: `ErrorHandlingInterceptor.ErrorHandling` reads the response
  trailers (`ResponseContextExtensions.GetCommonResponse`) and, for
  `x-apb-screen-transition-type: 3`, calls `HandleNet.ShowMoveTitleError`.
  The dialog's text comes from `x-apb-message-text-id`
  (`NetworkTextKey.ConvertTextKey`, falling back to the title error text);
  without it the game hides its menus and waits forever. Codes 100000-100002,
  102002 and 103000 open other dialogs, and 290041/290043/290044 are ignored.
  The server sends code 104000 (`HandleNet.DateUpdateId`) with text 900000.
- Android 16 emulator, Google APIs image, a save from 2026-11-03 (player
  level 100): from the home screen, the in-game Bunker button and Open Pod
  Programs; the banner said the game returns to its title screen. The Item
  Editor granted 1,000 paid gems with no prompt to close the game; the log
  showed Lunar Tear stop and start, and the game process kept its PID.
  Back in the game, opening the Gift Box showed "Refresh / Process failed.
  Returning to title screen."; OK reached the title screen, Tap to Start
  signed in with GetLatestMasterDataVersion and a full GetUserData, and the
  gems showed 1,098,000 (from 1,097,000).
- Same emulator, master data reloaded on the running server: the version
  changed and, after the title screen, the game cached a new copy of the
  master data (`cache/mst-…`).
- Go tests: `internal/bunkercache` (values built again after Invalidate),
  `internal/interceptor` (one call fails with the three trailers; battle
  results pass and keep it pending; signing in ends it), and the server's
  existing tests with the patched master data. Python: Pod Programs' guard
  (`android/tools/test_tools_live.py`, 11 tests).
- Not checked: iPhone/iPad (the launcher's pause and resume are built but not
  run), the content patcher's Apply and the calendar on the device, and a
  change made while a battle is in progress.

## Arena season dates in the game — 2026-11-04

- The game reads a season's dates from its master data, so the Arena's
  Period line showed 2099. `arena_season.c` (Android and iOS, called when
  the top row starts) gives the loaded master data's turn seasons the dates
  of their four-week turns: the season in force its current turn, the others
  their last turn, or their first when it is still to come. The season the
  game sees in force matches the server: a host build of the same code
  against the server's `Season` at 20,468 times from 2021 to 2029 (every
  3 h 17 min) picked the same season every time with Bunker's patched Global
  and Japanese master data, and changed nothing with the original Global and
  Japanese master data, a calendar loop's data and the original-dates view.
- Android emulator, global 3.7.1 APK built with this change, Everything open:
  the log said "9 season dates set to their four-week turns; season 202037
  in force", and the Arena showed Season 036 with the Period 10/26 13:30 to
  11/23 13:30 (India time, Monday 00:00 GMT-8), the turn holding 4 November.
- Same build with the Original calendar at 7× speed, moved to week 9 (game
  date Tuesday 5 January 2027, 62 days ahead of real time; original
  28 September 2021): the log said "the game's own dates (no turns)" and the
  Arena showed Season 002 with the Period 01/04 13:30 to 02/01 13:29, that
  season's dates as the calendar moved them. The emulator's save and master
  data were restored afterwards.
- Season end in the game: the emulator save was given 1,113 points in
  202037 and the clock moved to Tuesday 24 November, after that turn. The
  game asked for no reward at login: its check (`HasRewardReceiveArena`)
  needs a finished weekly result, which the server records at the first
  Arena visit after the turn. The Arena then showed Season 037 (202038),
  Period 11/23 13:30 to 12/21 13:30, and on the way back to Home the game
  claimed: the Season 036 report (rank 3919, three season rewards) and the
  week's report (1,113 points), paid once. That claim comes from the weekly
  check, which already worked before the dates change. The save and clock
  were restored afterwards.
- Two season ends before a claim (an Arena visit after a turn, then no Home
  visit until the next turn has ended) used to replace the first season's
  unpaid reward with the second's. The earlier one now stays due and the
  claim pays both (`TestTwoSeasonEndsBeforeAClaimKeepBothRewards`, patched
  Global and Japanese master data; it fails without the change).
- iPad Pro 11-inch (M4), iPadOS 26.6.2, a build of f422c7e installed over
  the user's app (Original calendar with original dates, loop 1, real-time
  speed). A copy of the save was given a cleared quest 61 to open the Arena.
  The Arena showed Season 001 with the Period 09/01 07:30 to 08/31 07:29
  (India time): season 202001's own dates, 1 September 2020 to 31 August
  2021, as the original-dates view shows them. Nothing was changed, as with
  the calendar on Android. The device log shows the Arena line as
  `<private>` (the Subjugation line before it is readable). The user's save
  was restored afterwards.
- iPhone 15 Pro, the same build, Everything open, a level-14 test player with
  the Arena open (1,113 points in 202038): the Arena showed Season 036 with
  the Period 10-26 13:30 to 11-23 13:30, the four-week turn holding
  4 November, as on Android. The save was restored afterwards.

## Arena season turns — 2026-11-04

- With Bunker's patched master data, 38 seasons are open at once (all end in
  2099), so the one that started last (202038) never ended. Nine of them use
  its grade, season rank and weekly rank tables (202029-202032,
  202034-202038); they now take four-week turns from 202038's first Monday,
  changing at the weekly reset. With the original master data at most one
  season is open at a time, and that season is used as before.
- `internal/pvp` unit tests: turns change only on a Monday reset, in order,
  every four weeks, and wrap around; seasons with other reward tables, invalid
  seasons and seasons not yet started are never chosen; with the game's own
  dates seasons follow each other and close after the last one.
- With the patched master data and the emulator's save: 6,000 points in season
  202037 gave final rank 2911 at the end of its turn, a pending season reward
  from its rank 1001-5000 tier (three items), the week's result kept and
  season 202038 started from 0 points. The other Arena tests pass with the
  patched and the original master data.
- An Android 9 emulator, global 1.7.0 APK with this server: the level-100
  test player had 47 points in season 202038 (shown as Season 036 after the
  change, Season 037 before: the game numbers seasons one below the id's last
  digits). The first Arena visit moved it to 202037 with 0 points and rank
  4931, and kept 202038's final rank for its reward. The Period line still
  showed the master data's dates (to 2099); see the entry below.
- No reward screen appeared, on that visit or after a restart. The client's
  `CalculatorArena.HasRewardReceiveArena` (disassembled) asks for Arena
  rewards only when the latest weekly result is for a finished week (else it
  looks at the one before) and its weekly version is not yet received; the
  season-only path also needs the season's master end date to have passed,
  which the patched 2099 dates never do. So the season reward is paid with
  the weekly claim. Turns change on the weekly reset, so the closing week is
  already finished then; the mid-week change after updating waits for the
  week's end. That second week result for the same week is now merged.
- With the emulator clock moved to Tuesday 10 November (after that week's
  reset), the game called `ReceivePvpReward` from the Home pop-ups at login,
  which paid 4 items. It then showed three reports in turn: Season 037
  (202038) at rank 4689 with its three season rewards; the closing week at
  weekly rank 4600 with its rank reward; and its 95 points (that grade pays
  nothing). Every reward said it was sent to the gift box. The first start
  on the moved clock reopened straight into the Arena and skipped the login
  pop-ups (no login bonus either), so the claim came at the next login.
  Automatic time was switched back on afterwards.
- Original calendar at 7×, with the original Japanese master data
  (`TestCalendarSpeedPaysSeasonEnd`): visiting once a real day, the game
  clock jumped a week three times; the visit after it passed season 202042's
  end recorded rank 3801 and the last week it was played (1,500 points),
  that week was over so the game would claim, the season reward (three
  items) and week were due once, and 202043 followed. Not run in the game.

## Arena against computer players — 2026-10-08

- The server had no Arena support at all: none of the nine PvP calls, the
  defense deck, weekly rewards or the three Arena tables. Each season has a
  ladder of 5,000 computer opponents. They use playable costumes and their
  paired weapons, raised to a share of the player's deck (a larger share for
  those with more points). These values come from the game: 100 battle
  points, 1 point back every 180 s, 10 points a battle and 5 a refresh.
  Grades and the win, weekly grade and weekly rank rewards come from the
  Arena tables. Season 202038 is the current one: Bunker's patched seasons
  all run to 2099, and it is the one that started last.
- `internal/pvp` tests with the patched master data and the emulator's save:
  the ladder is the same each start and ranks the player; a battle costs
  battle points that come back on time; opponent decks stay within the
  game's level limits; a win raises points and rank and pays the grade's win
  reward, a loss lowers them; 12 hours away gives 8 defense battles; a new
  week records last week's result and its rewards are due once.
- `mobile/pvp_test.go` runs every Arena call over gRPC on the on-device
  server: top data, matching list and refresh, battle start and finish with
  the reward in the diff, ranking with the player in place, season result,
  attack and defense logs, weekly reward claim, computer player profiles and
  the Arena info on the player's profile, and the Arena tables in the user data.
- Emulator, on a copy of the save with quest 61 marked cleared (the real
  save is restored afterwards): the Arena opened (season 037, rank 4934), the
  opponent screen listed three computer players, a battle played to the end
  and won (rank 4934 → 4574, 0 → 100 points, a coin and materials), and
  History showed it.
- Two client problems were found along the way. First, the opponent screen
  hangs without an Arena deck, so the first visit copies quest deck 1 to
  Arena deck 1 (also the defense deck). Second, battle loading stops on a
  null weapon awaken ability
  (`CalculatorDataBattleDeckForPvp.SetWeaponAwakenInfo`). A temporary hook on
  il2cpp's null-reference raise found it. The server now always sends it,
  even when empty.

## Missions, rewards and summon rates — 2026-10-07

- Checked against the 3.7.1 client: client and server define the same 40
  services and 174 calls, and 28 had no handler. This adds missions, the mission
  pass, the daily quest set reward, multi-skip, costume level bonus
  confirmation, story choices, labyrinth season rewards, unread pop-ups,
  Portal Cage drops and the friend actions (which succeed offline, with no
  friends). Arena (PvP, since added) and the Apple account calls remain
  unhandled.
- Mission rules: `scripts/gen_mission_rules.py` reads the 6,436 missions'
  English names; 5,635 get a rule. Most of the rest are Arena missions, named
  Mythic Slab boards and subjugation bosses, and missions with conditions the
  names only hint at.
- `internal/missions` tests on the emulator's save with the patched master
  data: the first request backfilled 53 missions (main quest and chapter
  clears, favourite character, logins), a quest clear counted for the daily
  quest mission, all 56 cleared missions paid their rewards, the state
  survived a reload, and the next day reset the daily missions. Checking the
  backfilled list found a fallback that cleared "conditional" quest missions,
  and it was removed.
- `mobile/missions_test.go` runs the on-device server with the same save over
  gRPC: mission progress and rewards arrive in the response diffs; bulk skip,
  the daily set reward (once a day), level bonus confirmation, story choices,
  `GetUnreadPop`, `GetDropItem` and the friend actions answer; the user data carries the new
  tables; the game's Rates page shows the rates saved in Pod Programs.
- `internal/gacha` tests: the defaults equal Lunar Tear's table, the settings
  file is read and validated, 20,000 draws land within 1 point of the set ★4
  rate and featured share, and the 10-draw guarantee follows the setting.
- Emulator (Android 16): the APK started, logged in through the new
  interceptor without errors, and Pod Programs > Summon rates saved a preset
  to `saves/gacha_rates.json`. The in-game Missions menu was not reached: the
  emulator's save is at the start of the story.

## Display settings and Game Mode — 2026-10-06

- Galaxy Fold (Android 16, 120 Hz): at 60 fps characters walked at 7.4 m/s
  instead of 3.7. ActorController.FixedUpdate runs once per rendered frame,
  while the physics step stays 1/30 s. With the physics step set to the
  frame time, walking measured 3.7-3.8 m/s at both 60 and 30 fps. Battles
  (30 x frame time per frame) kept their speed. The game ran at a steady 120
  fps at 1080p. At the screen's own 2448x1848, the GPU limits it to about 52.
- iPad Pro (M4): the same change through the IL2CPP API (LunarDisplay.m)
  gave 116-120 frames/s at Screen maximum and 1080p. Walking and battles
  were normal.
- Web builder (live site after the merge): the Android APK built in Chrome
  carries libbunkerdisplay.so, the Display page and appCategory="game";
  installed with the public key, it imported the game files, played, and
  switched frame rate and resolution from Pod Programs.
- Summon crash (2026-10-07): above 30 fps the summon reveal crashed on the
  Fold, the iPad and the emulator, always at the same address. Bisected on the
  emulator (host GPU): the frame rate alone, and the frame rate with the
  physics step, each ran three 10x summons without a crash. The frame rate
  with the fractional battle step crashed. Battles now get one whole step
  every 1/30 s and no step on the frames in between (BattleGame.Update skips
  a zero step). Three 10x summons at Screen maximum no longer crash.

## The Archive — 2026-10-05

- Phase 0 on the real Android dump: revision 0 holds 6,633 English text
  bundles, 270 MP4 movies in `resources/`, ASTC textures (stills, art,
  icons), Vorbis-in-FSB5 audio clips (24k English voice lines, 524 music
  tracks) and Unity 2019.4 meshes and animations. Octo's header mask covers
  the first 256 bytes, including the version byte. By default, lunar-scripts'
  `decrypt_assetbundle.py` masks one byte too many. This breaks bundles whose
  data starts inside the header. Text bundles were unaffected.
- `android/tools/test_archive.py` (8 tests) passed, including a full index
  build from the real dump: 0 of 6,633 bundles failed, 4,666 scenes and
  23,638 story lines in about 4 seconds on a PC, and every page answered.
  All 144,911 text entries render with balanced italics.
- Android 16 emulator (x86_64 with ARM translation), APK built with
  `scripts/build.py` in WSL: the Archive section sits below Pod Programs and
  stays off until game files are ready. With a reduced dump (English text,
  catalog, three movies), the Archive built its index on the device, listed
  Season 1 with chapter titles, paged scenes, showed the weapon stories,
  searched lines, played a movie streamed from its own server, and followed
  dark mode. Opening the Archive from adb is refused (not exported).
- Same emulator with a 64 GB data partition: the real 15 GB `.7z` imported
  20.91 GB in about 20 minutes. The Archive rebuilt its index on the device
  in under 30 seconds and listed all 145 movies with their Library titles.
  Deploy then reached the game's title screen.
- Characters and Gallery: textures decode in the Go library
  (`server/mobile/unityasset`: Octo mask, UnityFS, serialized files read by
  their type trees, Texture2D and a Go port of texture2ddecoder's ASTC
  decoder). Go tests compare eight real textures (ASTC 5x5, 6x6 and 8x8,
  102x102 to 2048x2048) with texture2ddecoder's output: every byte matches.
  On the emulator the Archive listed 35 characters and 284 costumes with
  portraits, showed a costume's 2048x2048 art trimmed to the figure with its
  story, and the gallery's stills, all decoded on the device. Decoded images
  are kept as PNGs under the Archive's folder.
- Voices and music: Unity's FSB5 Vorbis is rebuilt as Ogg in the Go library
  (`unityasset/audio.go`). FMOD strips the Vorbis setup header and keeps its
  CRC32. The dump uses three setup headers. They were regenerated once with
  libvorbis 1.3.7 and checked against those CRCs (`vorbis_setups.go`). Go
  tests rebuild six real clips (music, story and character voices) and match
  python-fsb5's output packet for packet, with the same granule positions.
  ffmpeg decodes the files without errors at the right length. 21,396 of 23,638
  story lines have an English voice. On the emulator "Play scene" read a scene
  line by line (Android reported the app playing 44.1 kHz mono and moved to the
  next line), a soundtrack part played in stereo with loop and seek, and a
  character's profile line played.
- 3D viewer: the Go library writes a costume as glTF (`unityasset/model.go`:
  the skeleton, every enabled skinned mesh with its weights and bind poses,
  and each material's colour texture, mirrored into glTF's right-handed
  space) and a Mecanim clip as three.js clip JSON (`animation.go`: streamed
  Hermite keys, dense and constant curves, bones named through the Avatar's
  path table, root motion kept in place). Go tests convert all 323 costumes
  that have a skeleton without a failure (3 variants have no linked
  materials and show untextured) and check a run cycle: unit rotations,
  finite values, moving legs. three.js r160 is bundled (MIT) so it works
  offline. On the PC the costume rendered textured in its rest pose and with
  the idle and run motions. On the emulator the first build drew it white.
  three.js fetches embedded textures from blob: URLs, and the page policy
  blocked fetch(). The same policy reproduced this on the PC. The fix is
  connect-src blob:, which the Archive now sets itself and a test covers.
- Audit of every page and conversion: a crawl of every link from the home
  page opened 7,951 pages without an error, then checked their text for
  template leftovers, escaped game markup and "1 lines". Every file the pages
  link to was converted by the Go library: 7,368 images, 21,921 sounds, 282
  models and 22,503 motions, all without a failure. Fixed on the way: story
  previews and search results showed raw `<i>`/`<align>` tags and cut words
  in half; "Rest pose" scattered multi-mesh costumes (three.js posed each
  skin from its own stale bind matrices; the saved pose is restored
  instead), and costumes with only battle motions opened in that pose; four
  costumes ship without an Avatar, so their motions now take bone paths
  from the skeleton (matching the Avatar's exactly where both exist); each
  costume listed every other costume's signature moves; three library
  backdrops are ETC2 (decoder ported from texture2ddecoder, every pixel
  matches); two costumes have no full art and show their large card;
  `bgm_delay_settings` was listed as a track; the viewer linked costumes
  without a model; "Save PNG" and the 3D snapshot did nothing in WebView and
  now open the system save dialog; tapping a second voice line quickly
  stopped both; uppercase `<I>`, a stray `</I.` and "<3" in game text were
  mishandled. `test_archive.py` (10 tests) and the Go tests pass. On the
  emulator: 2P's Mock Machine renders whole in its battle idle and rest
  pose, a snapshot and a still saved to Downloads as PNGs, and Noelle's
  Dissenting Weapon (no Avatar) played its motions.
- Speakers and chapters: the main story's event maps (`eventmap/main`, read
  by the Go library's `scenario.go`) list the lines each map plays, the actor
  each is attached to and any speaker shown instead; Go reads the same 6,751
  map lines as UnityPy. Names are the game's own actor names. 5,562 of the
  7,909 main-story scene lines are named. These are the lines the maps name,
  plus lines with the same voice code in the same scene, or in the same
  season when at least 90% of that code's lines are one actor's. Narration,
  title cards and the unnamed girl stay unlabelled, as do event, character and
  side scenes, which the game narrates without speakers (one voice code per
  scene). The maps are named by quest map number (season, route, chapter order).
  This regroups the main story into the game's chapters, with their own names:
  both Season 2 routes, the intermissions and Season 1's Interval Prologue. Both
  routes' finales play the two Season 2 endings, which are filed under the first
  route. The other stories are named the same way: the event maps in
  `character`, `endcontents`, `limitcontents`, `marathon` and `side` name the
  text files they read, and their quest map numbers lead through the event
  quests to the Character Quest's character (shared by that character's Dark
  Memories and Recollections of Dusk), the Record event's title, or the side
  story's character. All 112 story groups are named. The battle prompts that
  every side map shares are filed as "Other scenes". The Library's 535 summaries
  are filed the same way: the main story's under each season's chapter names
  (titled by quest where the game titles them), the events' by Record name
  (their key number is the event chapter's SortOrder; all 45 checked against the
  scenes they quote), and the Character Quests', Recollections of Dusk' and
  Dark Memories' by character.
- Weapons: 639 of the 640 weapon folders convert to glTF with the costume
  code (the last, wp003001, has no mesh or art). 52 variants have only a
  prefab, and their mesh is in a sibling's skeleton bundle. That sibling is
  in the same series (wp005528 draws wp005505's) or, for 19 of them, in
  another series of the same type. All 1,280 weapon art images decode. Records
  show each weapon's art and open it in the 3D viewer, standing up and framed
  whole; the two "Defective" weapons are listed too. The viewer now frames any
  model by its whole bounding sphere in the narrower view angle and zooms out to
  four times that.
- Movies: the Library's categories are the seasons (the game labels the
  first two "2020" and "2021" and leaves the third unnamed) plus the
  title-screen movies. Each season now also lists its story scenes, named
  by chapter from their codes (mm + season, route, chapter, part), and the
  English-voice cut plays where there is one. The 108 dated clips that the
  game's announcements played are grouped by the year they ran. Each is
  titled by its caption, preferring a line that names a character. 180 movies
  are listed (35 exist only in Korean or Japanese cuts and were hidden before);
  8 with no announcement or caption are "Other clips".
- Music: the game has no track titles (each event map's _bgm string is the
  same leftover default), but every map names the track it starts
  (_bgms: track and stem, bgm_1071_2), and the battle tables name theirs.
  Each track is filed where it is first heard (a season's chapter, a
  character's stories, a Record event, a side story, or battle) with the
  other places. 312 of the 352 tracks are placed. The other 40 never play
  anywhere and are filed as "Other". Track 9999 is 8 s of silence (3.9 KB of
  Vorbis) that maps play to stop the music. It is left out. Not checked on iOS
  or a physical phone.
- Gallery names: stills are filed by main-story chapter (still_main_ +
  season, route, chapter id, number), event scenes by Record event (the
  2d/ev folder's code is the event's) and part, and Library art by the
  summary it sits beside (bg + the summary key's numbers; 396 of 535
  summaries have one and now show it), report, Lost Archive, movie or
  record. Photos have no names in the data and are numbered.
- Companions, Memoirs, Debris: all 53 companions show their art,
  description and 3D model with motions; 144 Memoirs are listed by series
  with their art; 181 of 182 Debris show their picture.
- Other models: the Characters tab lists Mama and the cast (ma), story
  characters (np, pc, pe, sp, um) and enemies (mt) by family: 10, 248
  and 230 models (110 enemy looks borrow their family's skeleton; mt042001
  has none and is left out). An enemy is named by the game's own name for
  its model (costume.name.mt…, 148 looks: Beast Type, Puppet Type, Sea
  Creature Type…), otherwise by the boss names of the quests it fights in
  (quest -> scenes -> battle groups -> NPC deck -> boss-type member ->
  costume skeleton and variation). Event puppets are never marked as bosses.
  When a boss name has no marked boss, it goes to the look that is fought in
  every such quest and seldom elsewhere (Birthday Puppet is mt002046). Looks
  still unnamed take their family's name and element (variation 1xx-5xx is Fire,
  Wind, Water, Light, Dark in all 99 named looks). 9 enemy looks stay numbered
  and one family (mt043, whose boss name is the garbled "%ol13##") is
  unnamed. The cast's names come from actor.object.name (by actor object
  and by m_actor's name id: the um models are "Box"); 36 story families,
  mostly silent extras and props, have no English name anywhere ("-" or
  absent, and never a speaker) and are listed last under Unnamed. Garbled
  names (■ blocks, "&f33") are skipped.
  Enemy looks drew their textures from the family's first look, so the
  model code now loads those too (mt008101). The story characters (pc, pe,
  sp, um and one ma) came out untextured, because their shader keeps the
  colour map in _BaseMap, not _MainTex. pc009001's hair leaves the slot empty
  and takes the texture named for the part (t_pc009001_hair_aaaa). All 542 cast,
  enemy and companion models now convert textured except two enemy eyes
  that use another family's face texture (mt019 -> mt007001) and the Cursed
  Gods' grey placeholder material. The pc textures are greyscale in the
  game files, so those figures show in grey. The props (oa) are left out.
  mt043001 is modelled 85 units tall (a costume is about 2), and its idle
  motion holds it 60 units up. The viewer's clip planes and floor now
  follow the model's size. After a motion fades in, the viewer frames the
  model again if it has left the view (checked on the emulator).
  Character voice lines keep their numbered labels: the outgame voice
  files have no subtitles in the dump.
- Web builder (Edge-based pane on Windows, local test server, site assembled
  by web/build_site.py from this branch's launcher APK): the Android APK built
  in the browser in under a minute. Against the command-line build, the
  launcher's native libraries, all 20 Chaquopy assets (the Archive's Python
  among them) and the launcher dex holding the Archive are byte-identical, and
  the patched master data decodes to the same 607 tables. The rest differs as
  designed (the command line rebuilds resources and dex with apktool; the web
  builder edits the original in place). The APK verifies with the Bunker
  public key. Re-signed with the local key, it updated the emulator in place,
  reached the game's title screen, and its Archive showed a textured cast model
  in 3D and the Memoirs with their art.

## Signed web APKs and the download fix — 2026-10-04

- `android/tools/test_apk_sign.py` passed: an APK signed by `apk_sign.py`
  (APK Signature Scheme v2, public key in `web/signing`) verifies with
  `apksigner`, and an APK that is already signed can't be signed again.
- Download failure found and fixed: the page's `<main>` and the BUILD button
  both had `id="build"`, so the build handler was attached to the whole page
  section. Clicking the download link revoked the finished APK's link and
  started another build; Chrome reported the download as a network failure.
  The section is now `id="terminal"` and the page has no duplicate ids.
- The site was assembled as CI does and run in Chrome with real clicks: BUILD
  enabled once both files were chosen, the build ran once, and the download
  link saved `bunker.apk` (304,320,690 bytes) without starting another build.
  It verifies with `apksigner` (v2, Bunker public key).
- On the emulator, the downloaded APK could not install over a copy signed
  with a different key (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`), as documented.
  After uninstalling, it installed and opened the Bunker. A separately assembled
  APK signed with the same public key then installed over it as an update
  (first-install time kept) and opened with its server running.

## Web builder redesign and rename to Bunker — 2026-10-04

- The site was assembled as CI does (`web/build_site.py` with a fresh Android
  launcher, iOS framework and Python bundle) and both builds were run in Chrome
  against the real game files. Android produced `bunker.apk`: all 5,003 entries
  match `android/tools/assemble_apk.py` exactly except the patched master data,
  whose compression differs between Pyodide and native libraries; all 607 of its
  tables decode identically. iOS produced `bunker.ipa` with the current launcher
  framework, Pod Programs code and templates. Each build ran once even when the
  button was pressed twice, with no console errors. The command-line build now
  writes `artifacts/bunker.apk` / `artifacts/bunker.ipa`.

## Bunker and Pod Programs redesign, choosing players — 2026-10-04

- The launcher (Bunker) and Pod Programs use the NieR:Automata terminal look on
  Android and iOS, light or dark by the system or ⋮ → Display. Checked on the
  Android 17 emulator, the Galaxy Z Fold, the iPad and the iOS simulator smoke test.
- Every Pod Programs action was exercised on the emulator: create and restore a
  save backup; apply a content preset, restore the previous master data, export
  it and load an original; grant gems, an important item, a costume, a weapon
  and a memoir set; run an Upgrade Manager action. Fixed on the way: the
  content patcher no longer breaks on a half-written state file (writes are now
  atomic), unowned karma slots say "locked", and karma pickers fit a phone.
- Use this player: `android/tools/test_players.py` (6 tests) covers swapping,
  switching back, a device that has not signed in, and New player. On the
  emulator and iPad the game then signed in as the chosen player. New player
  needs the server to register a device ID it does not know
  (`patches/lunar-tear-new-player.patch`); on the emulator, iPad and Fold the
  game then asked for a name and started a new player, and switching back
  restored the original.

## Persistent server log and export — 2026-10-04

- Go tests: the log file keeps lines across restarts (one "log opened" marker
  per session), rotates to `server.log.1` at 5 MB, and the export ZIP holds both
  files and `info.txt`, also when written over a longer file through a descriptor.
- Galaxy Z Fold (Android 17): after an update and a restart, `server.log` in
  `Android/data/<package>/files/logs/` held both sessions and `adb pull` read it
  without root. ⋮ → **Export server log** saved a ZIP through the system picker
  with `server.log` and `info.txt` (package, Android version, model, port offset).
- iOS simulator smoke test: the server log is saved in `Documents/logs`. The
  log folder is set when the server starts, not while the app loads, because
  calling Go that early delayed the launcher. The smoke test also found that

  builds without `LunarPortOffset` reset a test offset to 0. The offset is now
  set only when the build has one. Export on iOS uses the same Go code as
  Android and is covered by the Go tests; the share sheet itself was not
  exercised on a device.

## Server checks, port conflicts and port offset — 2026-10-04

- Another device showed a black screen after the logo. Reproduced on an
  Android 17 emulator by holding port 8080 with another process: the old build
  showed the raw "address already in use" error with the server card still
  "Ready", and the game, opened directly, stayed on a black screen. Now the
  server checks itself after starting (game, assets and accounts ports, and that
  this server answers), the launcher names the busy port and shows "Not
  running", and a game opened directly goes to the launcher instead. Same
  results on the Fold. Go tests cover the check, including another program on a
  port.
- Port offset (scripts/build.py --port-offset, and the web builder's
  experimental option): at first, an offset build still failed with port 8080
  held ("Failed to connect"). Unity extracts the game's code data to
  Android/data/…/files/il2cpp on first launch and re-extracts only when the
  Unity version changes, so every update had kept running the first install's
  copy, including its addresses. The game process now deletes that copy after
  each install or update, and drops the cached asset list when the offset
  changes. Afterwards the web-built and command-line offset builds reached
  player registration on 38003/38080/33000 with 8080 held, and switching back
  to a default build re-extracted the copy and played normally, also on the
  Fold.

## Game reopened without its server — 2026-10-04

- On the Fold, after an update the game was reopened from Recent apps. Updating
  ends the server process, and Recent apps opens the game directly rather than
  through the launcher, so the game waited on a black screen after the logo;
  the server log ended with "Server stopped".
- Fix: the provider in the game's process checks that the server answers when
  the game opens, and otherwise replaces the game with the launcher, which
  starts the server and the game. On the Fold, after installing (server
  stopped) and opening the game directly, the launcher took over, the server
  was listening within about 2 seconds and the game reached its title screen
  without any taps.

## Proxy stall and Android 17 archive import — 2026-10-03

- Report: on a OnePlus 13, loading the game stayed at 20% for minutes unless
  the phone was in airplane mode. Reproduced on an Android 17 emulator with
  Google Play services and the full game files, with an HTTP proxy set that
  cannot reach the phone's loopback (as a VPN or accelerator app would be):
  loading stopped at 60% and showed "Failed to connect. Retrying." for over
  three minutes, while the game's asset requests to 127.0.0.1:8080 and its
  Facebook SDK requests to 127.0.0.1:3000 arrived at the proxy and were retried
  every 10 seconds (Octo's stall timeout). Without the proxy the same game
  loaded in about 20 seconds.
- Fix: a provider created in the game's process at start installs a proxy
  selector that sends loopback addresses directly and keeps the phone's proxy
  for everything else, and reinstalls it when Android replaces it. With the
  same proxy, the fixed build loaded to player registration in about 12
  seconds and no loopback request reached the proxy. Checked for both the
  command-line build and the web builder's APK.
- Android 17 refused to reopen a picked archive through /proc/self/fd
  ("permission denied"). The import now reads the descriptor Android opened,
  with positioned reads shared by the unpacking workers. A Go test imports an
  archive whose file was deleted after opening. On the Android 17 emulator the
  real 15 GB .7z imported 20.91 GB in about 11 minutes, with the progress bar
  following the real progress.

## Archive import and use in place — 2026-10-03

- Go tests: a .7z of the dump unpacks only revision 0 and decompresses only
  the archive blocks that hold it; a .zip unpacks only revision 0; unsafe
  paths, other formats and archives without a catalog are refused; cancel
  works. The real 15 GB Android .7z unpacked on a Mac to 201,073 files that
  match the prepared folder by name and size (3,002 also compared by hash).
- iOS Simulator smoke test, all cases passing, including: .7z and .zip import,
  moving a folder already inside the app's Documents, refusing a bad one and
  putting it back, and use in place (linked, survives relaunch, refuses to
  start without the folder, and a later copy removes only the link). Run on
  offset ports while another service used port 3000.
- iPad Pro 11-inch (M4): the real 14.9 GB iOS .7z, imported by the app,
  unpacked 20.96 GB in about 6½ minutes; the archive was removed and the game
  started.
- iPad, use in place: a copy of the game files in On My iPad (outside NieR)
  was chosen with Game files › Change › Extracted folder: use in place. NieR's
  revisions/0 became a link and its own copy was removed. After a cold
  relaunch the saved bookmark reopened the folder, the game reached its title
  screen and loaded into the 3D world from the linked files.
- Samsung Galaxy Z Fold: use in place on an extracted folder in Download, with
  All files access, linked the files without copying (the old 21 GB copy was
  freed) and opened Tools. Importing the real 15 GB Android .7z afterwards
  unpacked 20.91 GB in about 15 minutes, and the linked folder's 201,073 files
  were left intact. The first builds' progress bar showed 100% too early.
  The time-left estimate used a partial total, read while the archive was
  still being listed (12.7 of 20.9 GB on a Mac). Totals are now published
  once the listing is complete.

## iOS — 2026-10-03

- The combined repository still generates the same 291 Android sources
  byte for byte, and its Android build passed with the same signing key.
- The iOS build applied all 4 address patches, 11 sign-in framework patches
  and 13 game-code patches from the pinned lunar-scripts IPA patcher, injected
  the launcher, and signed for a development team. Go server tests passed.
- iOS Simulator (stand-in app, real launcher and server): setup screen, bundled
  master data, server start, sign-in page, save creation, restart with the
  same auth key, folder import, invalid-folder rejection and split-archive
  import with long paths all passed.
- iPad Pro 11-inch (M4), iPadOS 26.6.2, development-signed IPA: the launcher
  showed the setup screen without files. The 20.9 GB iOS assets were copied as
  11 archive pieces over USB and unpacked by the app in under two minutes.
  The embedded server started on the device. The game reached its title screen,
  accepted the terms, registered a new player, downloaded 19 MB from the
  device itself, and played the opening story.
- Remote control from the Mac (screenshots, taps and typing) worked through
  the UI-test helper.

- Tools in the iOS Simulator, with the real launcher framework and a copy of
  the iPad save: all 13 editor actions succeeded with a valid backup each,
  restoring a backup worked, the save passed SQLite's integrity check, and
  the server restarted on the edited save. The "All content" preset produced
  a master file identical to the same patch run on the Mac.
- Tools on the iPad: the three-finger gesture opened the launcher, ⋮ › Tools
  stopped the server and opened the editors on the iPadTest save. Granting
  50,000 free gems wrote `user_gem.free_gem = 50000`; "All content" applied;
  Close showed the restart screen, Close game ended the app, and the game
  reopened on the edited save and patched master data.

- Import progress: the Fold imported the 20.9 GB folder with a progress bar
  in the app and its notification; the 11:50 estimate of 15 minutes finished
  at about 12:06. The iOS Simulator showed the same bar for a 20.9 GB folder.
- Save import (Go tests, iOS Simulator, Fold): an iPad export imported on the
  Fold loaded in the game as the Fold's player (the server log shows the
  Fold's own game ID signing in to the imported player, with no new player
  registered). Re-importing the Fold's original export restored it exactly
  (identical database dump and sign-in key). Bad backups are refused without
  changing the save.

- Web builder (Chrome on macOS, local test server): the Android APK built in
  18 s and matched the command-line build entry for entry (master data decodes
  to identical tables); signed with the existing key, it updated the Fold and
  played offline in airplane mode. The same APK built by
  `android/tools/assemble_apk.py` on the command line also opened Tools offline. The iOS IPA built in
  37 s with the same files as the command-line build; signed and installed on
  the iPad, it kept the game files and save, reached the title screen and
  opened Tools.

- Raw dump import: none of the four pinned projects reads revisions other than
  0 (the server serves revision 0 for every request; lunar-base only scans for
  text bundles, which only revision 0 has). On the Fold, choosing a raw-dump
  layout (revisions/0 with the real files, plus catalog-only revisions 1-3)
  copied 20.91 GB, revision 0 only, and the game then loaded into a battle. The
  iOS Simulator check imports a raw-dump folder and a split archive of one,
  copies only revision 0, and refuses a dump that points at another revision.

Not yet verified on iOS: airplane-mode play, Safari sign-in for an existing
account, sustained play and battles, iPhone, and the folder picker with a
20 GB folder.

## Android — 2026-09-20

## Repository build

- All four submodules are fixed to the commits in `upstream.lock.json`.
- Preparing these pins plus the Android overlays and patches reproduced all
  291 generated source files byte-for-byte from the tested integration.
- The new repository's complete build passed: protobuf generation, Go tests
  with real master data, ARM64 native build, Gradle build and Android lint.
- The combined APK passed signature verification and 16 KB ZIP alignment.
  Its checksum is written locally to `artifacts/SHA256SUMS` on every build.
- Editor integration checks also passed against this repository's generated
  sources, using isolated copies of the private save and master data.
- Five synthetic asset-copy checks passed, including preservation of existing
  files, rejection of cross-revision dumps and cleanup after a failed copy.

## Runtime checks on the same integration sources

These checks ran before the sources were moved into this repository. The
newly packaged APK has not had another full emulator playthrough.

- Android 16 ARM64 emulator, airplane mode and no default network: player setup,
  opening story and touch-controlled movement passed. A cold restart rebuilt the
  game's download cache from the phone's embedded server and retained the save.
- All three server listeners belonged to the app and bound only to loopback.
  Playing required no desktop server. SQLite save integrity passed.
- Tools opened in portrait and landscape. Applying the Story preset, granting
  one free gem and restoring its automatic snapshot passed through the Android
  UI and native bridge; the gem balance changed 0 → 1 → 0.
- Host integration checks exercised every editor page and writes for inventory,
  costumes, weapons, companions, upgrades, karma, slabs, debris and memoirs.
  Session checks, inventory overflow rejection without partial writes, oldest
  retained snapshot restoration and master-data rollback passed.
- Native Android instrumentation passed master loading, SQLite, server health,
  stop/restart and backup preparation. A small folder import through Android's
  document picker passed and automatically opened the game.
- Android 17 with 16 KB kernel pages passed native server checks and game title
  startup. The original game's libraries use Android's page-size compatibility
  loader; full gameplay was checked on Android 16 with 4 KB pages.

## Still unverified

Updated 2026-11-04. Earlier items now covered by later checks: the Galaxy
Z Fold (120 fps play, a 20.9 GB folder import through the document picker,
use in place and a 15 GB `.7z` import, see 2026-10-03 and 2026-10-06), and
importing an exported save ZIP, which is implemented and passed on the
Fold, the iPad and the iOS Simulator.

- Folding and resizing on the Fold, sustained performance, battery use and
  Samsung background-process management.
- Full campaign and battle coverage.

Private game files, saved games, screenshots and runtime logs remain outside Git.
