# Changelog

What changed in Bunker, newest first. Each day lists its changes by area.
Commit ids are in brackets. A release's notes are the dated sections
under its heading, down to the previous release.

## 2026-10-25

### Game client
- Music no longer stops for good after you leave the game. Before, after
  opening the Bunker, the home screen or another app, the game stayed
  silent until it was restarted. Now the music comes back about a second
  after you return. [03f176e]
- Campaign badges (such as half stamina on EX Character Quests) no longer
  show a jumbled number: campaigns left open end in 2099, 26,000 days away,
  too long for the badge. Remaining times now stop at "999d", on Android
  and iOS. [d7b1ed6]

## 1.2.0 (2026-10-25)

The web page can build for iPhone/iPad again, and the Display page is
tidier.

## 2026-10-25

### Web builder
- The web page can build for iPhone/iPad again. Since 1.1.3 the build
  stopped with "No module named 'bunker_ios_update'", because the page
  didn't include that file. [d69d157]

### Display
- The Display page is tidier: each setting has its own row, a full-width
  menu and a short note, instead of wrapped labels and one long
  paragraph. [dd6e3a0]

## 1.1.3 (2026-10-25)

Bunker uses less memory. Low-memory phones get lower resolutions and a
texture size setting. The game's ad and analytics libraries are off, and
a calendar bug after iOS updates is fixed.

## 2026-10-25

### Calendar
- The Original calendar now keeps the next loop's game data next to the
  master data. Before, it saved the file's full path, but iOS changes that
  path on every app install, so the move to loop 2 would not have found
  the file. For calendars started earlier, the file moves the next time
  Pod Programs opens. [e37c1ed]

### Memory
- Bunker's server uses much less memory: about 140 MB instead of 256 MB
  while you play, measured on an Android emulator. It now reads game data
  from its files only when needed, instead of keeping it all loaded. It
  also gives freed memory back. [5cbe846]
- Closing the Archive now frees its memory. On Android the Archive runs
  in its own process, which ends when you close it. On iOS its server
  stops. Before, the server kept about 450 MB after you had opened the
  Archive. [5cbe846]
- On Android, closing Pod Programs restarts the launcher, which also
  frees the memory Tools used. [5cbe846]

### Display
- For phones with little memory, there are two lower resolutions, 540p
  and 640p, below the game's own 720p. [6c9c123]
- On Android, Texture size draws characters and places with half or a
  quarter of their texture detail. Menus stay sharp. On the emulator,
  half size used about 440 MB less graphics memory and looks almost the
  same. Quarter size is visibly softer. [6c9c123]

### Privacy
- The game's ad and analytics libraries stay off. On Android, Bunker
  removes their start-up hooks. On both platforms, it sets Firebase's and
  Facebook's own off switches. [c99044c]
- Unity's own analytics, which the game sent to Unity's servers, are
  turned off. On iOS the Adjust install tracker no longer starts. While
  you play, the game now contacts only Bunker's update check (and, on
  iOS, Apple's App Store). If you update Bunker in the app, this also
  applies to the game you have installed. [c99044c]

## 1.1.2 (2026-10-25)

The game starts without Google Play services, events run on their
original dates again, and an Android 17 crash is fixed.

## 2026-10-25

### Android
- The game starts on phones without Google Play services (de-Googled
  phones, Waydroid) instead of stopping on a black screen after the
  logos. Firebase's start-up check and the Lilium attestation waited for
  Play services. Bunker now answers both. The attestation fails, just as
  it does on phones with Play services, because Google shut SafetyNet
  down. The server never read the attestation. [22b6059]
- Fixed a black screen on Android 17: Unity's frame pacer destroyed a
  fence sync twice, which stopped the game. [22b6059]

### Calendar
- The Original calendar runs events on their original dates. The final
  game data keeps only one date range per row. Reruns and parked dates
  had overwritten the earlier runs, so events such as the NieR:Automata
  crossover never opened. Bunker restores the runs from 153 weekly global
  master data files (167 rows in 13 tables). Each rerun of an event
  chapter is a copy of that chapter, with the same quests. Content that
  later stayed open for good is now open from its first run. [c61c907]
- Pod Programs' schedule names more events (254 of 274). It looks up
  titles by their text id, so Automata shows as "Record: The Cage of
  Reincarnation". [c61c907]

## 1.1.1 (2026-10-23)

Weapon stories that never unlocked.

## 2026-10-23

### Weapons
- The Arc 2 ★2 weapons' stories now unlock. Apprentice Witch's Staff,
  Sorrowful Echo, Ivory, Ebony, Ceremonial Scimitar and Ritual Pike showed
  only their first story. Their later stories unlock on either of two
  quests, and the server didn't read those quests. For weapons you
  already own, the stories for quests you've cleared unlock the next time
  the game starts. [af34a15]
- When a quest opens several of a weapon's stories, clearing it now opens
  all of them, not just the first (Scar and Sin's stories 2-4). [af34a15]

## 1.1.0 (2026-10-23)

Summons work as their official notices said. Event summons return, the
official notices appear in the game, and on Android the game fills the
screen around the camera.

## 2026-10-23

### Display
- On Android the game now fills the screen around the camera. Before, it
  left a black bar beside the camera in landscape. Its buttons stay clear
  of the camera. Pod Programs → Display → Screen area can turn this off
  ("Keep clear of the camera"). [1b42855]

## 2026-10-22

### Summons
- Event summons return. The Event tab has leveled box summons for 31
  story events. Each is open for its event's dates plus two days, and any
  of the event's tickets can draw from it. Each level shows its main
  prizes. Level Up opens once they're all drawn, and the last level has
  Prize Replenishment. The main prizes come from nierrein.guide where it
  lists them (17 events). Otherwise they are the event's own weapons and
  Advanced Handbooks. The rest of each box is modelled on the only box on
  record (Aurora Dynast, 2021): a level prize 35% of the time (30% on the
  last level), otherwise a common material. [61673b6]
- Mama's Dream moves to the Event tab, where the game shows its box
  screen and the prizes left. The Event tab opens once the story has
  opened side quests. [25f9571]
- 76 summons that are in the game data, but that Bunker left out, now
  run. They include Monthly Bonus and Bonus Summons, Healer & Support and
  its reruns, paid step-ups and others. Where a summon has a notice, it
  uses the notice's rules and dates. The last weekly summons (04-30-2023,
  Lars and Griff) reuse their 03-19 art and lineup. [0cc86f3]
- Ticket summons' panels show the characters their banner shows.
  [25f9571, 26b1f31]
- Lacrima Girl (153) is a regular summon again, and its Paid Gems Only
  twin (152) runs beside it. Fractured Weapon (163) also gets its paid
  twin (164). [0aa9980, 919e68e]

### Server log
- The saved server log says why the server last stopped unexpectedly. If
  the server crashes, the crash is kept and added to the log the next time
  the server starts. Exported logs include it. On Android 11 and later,
  the log also gives Android's reason for ending the server (for example
  low memory). Before, the log just stopped. [6e3fcd4]

## 2026-10-21

### Summons
- Summons cost what their official notices say. This covers price,
  regular or paid gems, free draws, use limits, daily draws and step-up
  steps (158 summons; Bunker had priced 81 of them differently). For
  2021-22 summons without a notice, the details come from archived
  in-game screenshots and tweets. [af52e6e, b15c461]
- Featured characters and weapons are the ones each notice lists (145
  summons). [ccf46d7]
- Guaranteed slots give what the notice promises (the featured character,
  one of a set, a ★4 character or weapon, one of an element, a ★4
  character you don't own). Step rate-ups and step bonus items also match
  the notices. Max Awakening summons bring their ★4 characters to
  awakening level 5. [35b60d6, 0e713f7, b2386de]
- The paid-only summons return. These are 88 Paid Gems Only summons that
  ran beside a regular one, each with its own art. Every ★4 drawn from
  them is a featured one, as promised. [403f4b4, c195942, 5c6013e]
- Ticket summons return, so you can use their tickets. They are ★★★ and
  ★★★★ Guaranteed, and the element and Argo ticket summons. The New
  Year's free ★★★★ summons return for their 2022 dates. [02ccfda, b2386de]
- Mama's Dream returns as a prize box. Each draw costs one ticket. It has
  the notice's prizes and gem stock (you have your own stock). Summons
  Details lists its prizes and what's left. [16cb647, 568b6ef]
- Summons Details lists a ticket summon's guaranteed-slot rates, says "no
  end date" instead of 2099/12/31, and shows days in UTC, as its labels
  say. [568665d]
- Added summons follow the calendar, like the game's own summons.
  Always-open ticket summons are listed after the summons of the day.
  [2926631]

### Notices
- The Notices screen shows the official notices. There are 947 of them,
  recovered from archives with their images, under News, Events and
  Issues. Each notice appears when the game clock reaches its date.
  Notices open inside the game. [2c1ab59]
- A summon's "i" button opens the notice that announced it (154 summons);
  the notice links to Summons Details and back. [2c1ab59]
- Builds include the notices. Updates download them only when a release
  has new ones. [aa8b064]

### Web builder
- iPhone and iPad builds on the website work again. They stopped at
  "Writing the IPA" because two of the packager's files were missing from
  the site. [36654fa]

## 1.0.2 (2026-10-18)

Safer master data imports and a quieter Android update.

### Files
- Import master data takes only master data. The file you pick must be a
  `.bin.e` file that decrypts to the game's tables. Bunker refuses any
  other file with a message and keeps the current master data. On iPhone
  and iPad the picker offers only `.e` files. [8c73a46]

### Updates
- On Android, Bunker no longer shows a false error over the installer's
  prompt after it hands over an update. [236618d]

## 1.0.1 (2026-10-15)

Summon fixes and smoother updates.

### Summons
- Step-up summons cost what their step pages in the game say. This covers
  the amount at each step, which steps are free, and whether only paid
  gems count. The prices come from all 429 step pages. Before, 33 of the
  43 step-up summons charged a made-up 2,000 / free / 3,000 / free / 5,000
  paid gems (for example Resolute Dress, now 3,000 / 1,500 / 3,000 / 1,500
  / 3,000 gems). [579fb8d]
- The Summon buttons now respond after you swipe the banner list. Above 30
  fps, the list could stop a fraction short of a banner far down the list.
  It then still counted as moving, so taps were ignored. [5c35088]

### Updates
- Network problems show as plain messages. Cancel shows only while the
  download can still be cancelled. Lunar Tear starts again when an install
  is refused. When you publish the web builder by hand, it builds the
  latest release. [4166ae0]

## 1.0.0 (2026-10-15)

The first release. Bunker now has a version. The launcher's About, the
Lunar Tear log and the web builder show it. From this version on, Bunker
can update itself: see Updates below and "Updating" in the README.
Everything before this date is part of 1.0.0 too.

## 2026-10-15

### Updates
- Every build knows its version: `1.0.0` for a release, `1.0.0+dev.<commit>`
  for any other build. About, the exported log, the server log and the web
  builder show it. [8ad1095, 01c86e0]
- When the launcher opens and the device is online, it looks for a newer
  release and offers it (⋮ › Check for updates turns this off). On
  Android, the phone rebuilds the app from Bunker's new files and the game
  files already in the app. Then Android asks you to confirm the install.
  Only builds signed with the public Bunker key can do this. iPhone and
  iPad build `Bunker-<version>.ipa` in Files and open the share sheet for
  SideStore, AltStore or a Mac. If the download is damaged, there is too
  little space or the install is refused, the app stays as it was.
  [6e7d8d3, b431cf7, aa9ebe8, e41af44, 8a020c9]
- Before a new version updates a save for the first time, it copies the
  save to Pod Programs' snapshots as "Before update" (the newest three are
  kept). An older Bunker refuses a save that a newer Bunker has updated,
  so it does not damage it. It also won't import such a save. [1389a05,
  1ebe33d, 8a020c9]
- Releases come from version tags. A workflow checks the tag, builds
  Bunker's own bundles (no game files), creates the GitHub Release with
  these notes and `update.json`, and publishes the web builder. Pushes to
  main only build. Release notes put each item on one line, without this
  file's line wrapping. [626f533, 0929939]

### Summons
- Fixed the crash after summoning on Android and iOS (often on Summon
  Again, a few minutes after starting the game). When text doesn't fit,
  the game's text builder makes its buffer only twice as big. A long text
  (the summon confirmation's "Available for purchase until") ran past the
  end of the buffer and damaged another game text. The game then crashed
  while freeing unused assets. Long texts now always fit. [0f82f23]

### Chapter summons
- A chapter summon appears in Summons only once its chapter's quest is
  cleared, as in the original game. The game never reads the server's lock
  flag. It shows every summon it receives as open, so all of them were
  listed. Drawing a locked one was refused, and the game went back to the
  title screen. [8673c63]

### Upgrades
- Glorious Success Rate Up campaigns raise the chance of a glorious success
  when you upgrade characters and weapons, as their names say. They use the
  game's own formula (+20 to +80 per thousand on top of the usual 10%).
  Before, the server treated them as a small experience bonus (2 to 8%)
  and did not change the chance. The server log records each roll and its
  chance. [da50bb5, 120704a]

### Step-up summons
- Multi-step summons move to the next step and show every step. The game
  builds the summon screen from one summon per step and shows the one for
  your current step. The server sent only step 1, so from step 2 on the
  screen was empty. A summon not drawn yet also stayed on step 1 after the
  first draw. Only the current step can be drawn. [fcb1f1e]
- Each summon has as many steps as the game has step pages for it (3 to
  5). Before, most had 5 steps and one had 7, so some showed blank steps.
  New Year's Luck of the Draw costs what its pages say: 3,000, free,
  2,000, free, 5,000 paid gems. Bunker still chooses the other step
  prices. A save that is past a summon's last step starts again at step 1.
  [fcb1f1e]

### Fortune draws
- The New Year and anniversary fortune draws (omikuji) now open with the
  Original calendar, on their original dates (seven draws, starting
  between weeks 23 and 134). When everything is open, they stay closed, as
  before. [d7eb4dd]
- A draw shows one of its fortunes at random (5 to 22 for each draw, from
  the game files). Before, the server sent the draw's own number, which
  has no result screen. The fortunes give no items, because the game data
  doesn't say which items they give. [d7eb4dd]

## 2026-10-14

### Server: missing game rules
- Event login bonuses: with the Original calendar, every dated login bonus
  card that is open that day takes one stamp a day, next to the everyday
  card. The game data has over a hundred of these cards, for events and
  anniversaries. Their rewards go to the gift box. A new calendar loop
  starts the cards again (it had also reset the everyday card's id). This
  does not happen with everything open, where the patched data keeps every
  card open.
- Weapon Evolve keeps each ability's level; a new slot starts at 1.
- Exploration pays by the score's grade (the game data has six). Each
  grade gives 5 to 30 stamina and its reward draws (1, or 11 on hard).
  Each draw gives gold or a costume or weapon experience material, and
  higher grades give more. Bunker chose the amounts; the game data has the
  grades, draw counts and ticket costs. Playing with tickets needs enough
  tickets.
- Labyrinth seasons now change. When you open a labyrinth in a new season,
  it pays the last season's reward for the furthest stage (the game plays it
  as the reach reward). Then the climb starts again: its quests and stage
  clear rewards reset, and accumulation rewards stay. It no longer showed
  every milestone.
- Item shop: an early restock costs the gems the game shows (10, 30, 50 ...
  500, by the day's refresh count). The count starts at 1 each day, because
  the game failed to price a refresh at 0. The 17 items are the whole lineup
  in the game data.
- Beginner and comeback campaigns: a new player who has cleared the first
  quest gets 7 days of the beginner campaigns. Logging in after 28 to 30
  days away starts the comeback campaigns (7 or 14 days). Their quest and
  enhance campaigns now apply, and the server sends the game both tables.
- Arena battle point items (4001-4005 and the recovery shop refill) restore
  battle points.
- Chapter summons are real boxes. Each chapter's box holds the materials
  its quests drop (10 of each common, 6 uncommon, 3 rare, and 1 of the
  rarest, which are its targets). Drawn items are not put back. The box
  refills on the 1st of the month (as the game says), and you can reset it
  once the targets are drawn. The Featured Items panel shows the rarest
  with their counts, and the details page lists the box. Bunker chose the
  box contents; they are not in the game data.
- Enhancing a costume or weapon can be a great success, with the game's
  animation. The chance is 10%, and it gives 50% more experience (Bunker
  chose these values).
- The Summon button shows its "free" badge while a free daily summon is
  unused.
- Limited-time offers (the Limited shop's 34 packs) open for their original
  sale periods (the cell's term, or the shop's dates). These follow the
  Original calendar. The game data doesn't say what opened them for a
  player. Each can be bought once while open (other packs still restock).
  [8d6485d]
- Tests drive handlers with the original game data (BUNKER_TEST_MASTER).
  [94343e5]

### Special Gift Roulette
The menu's roulette (Global only) gave free gems after a video ad, up to 6
spins a day. No ad can be shown any more, so the button did nothing, and the
server answered a spin with a summon item.
- A spin now pays free gems: 10 (60%), 30 (25%), 50 (10%), 100 (4.7%) or
  3,000 (0.3%). The wheel shows 15 slices, but the rates were never
  published. Players saw mostly 10s and very rarely the 3,000, so the draw
  is weighted.
- The video is skipped. When the game asks ironSource for it, the
  "rewarded" event comes at once and "closed" on the next frame, as the SDK
  sent them. On Android, Bunker replaces IronSource.showRewardedVideo. On
  iOS, Bunker can't change the game's code, so it points the ad agent's
  entry at the same function.
- Emulator: six spins showed the result dialog and added gems, and the
  counter went down to the reset countdown. [5450aee]
- iOS: the SDK on iOS keeps its listeners in underscore-named fields and
  sends "closed" with UnitySendMessage (Android's event dispatcher doesn't
  run on iOS), so the patch does the same. Pod Programs > Summon rates sets
  the roulette's chances. They are saved in roulette_rates.json next to the
  save and read on the next spin. They must add up to 100%, and Default
  brings back the rates above. Fold and iPad: spins play the wheel and pay.
  [fcd818b]

### Storage: links survive an iOS update
iOS gives an app a new data folder path when the app is updated. The
cache's symbolic links held absolute paths, so after an update they all
pointed nowhere. The game then downloaded those files again on every start
(19 MB and 170 MB on the iPad) and could not save them through the broken
links. The roulette's own art failed to load for the same reason.
- Symbolic links now use relative paths. At start, Bunker points absolute
  or broken links at the server's copy again. A broken link is removed
  before a file is served.
- iPad: the first start repaired 110,765 links (188 MB) in about 4 minutes.
  The next update moved the folder again, and all links still worked and
  nothing was downloaded. [fcd818b]

### Original calendar: opens with the launch summons
The first summons opened 20 hours into the launch week (28 July 2021, 22:00
UTC). The game hangs on a summon page when no summon is open. So a calendar
started in those first hours showed an empty summon screen and got stuck
there.
- A loop now starts only when the launch summons are open. When needed, it
  moves the clock forward by a whole day (the daily reset keeps its hour).
  A new loop does the same.
- Calendars that were already started move forward at the next Deploy or
  Pod Programs visit. [52cca2b]

### Names
- Big Hunt is called Subjugation Battles, as in the game: in the Archive's
  Schedule, Pod Programs' calendar and patcher, and this changelog. [5a02b2d]

### Storage: game files stored once
The game keeps its own copy of every file it downloads from the in-app
server, so played content took up space twice. Each cached file is now a
link to the server's copy.
- Files already in the cache are linked when the server starts. New
  downloads are linked a few seconds after the game saves them. A file is
  linked only when its bytes match the server's copy.
- Bunker uses hard links where the system allows them. Android doesn't
  allow hard links for apps. iOS doesn't allow them for game files used in
  place from another folder. In those cases, files of 4 KB or more become
  symbolic links instead (a smaller file takes no more space than its
  link).
- The game rewrites cache files in place, so the link is removed before a
  file is sent again. This way a new download can never change the
  server's copy.
- Emulator: the 9,811 files already cached (1.3 GB) were linked in 12
  seconds. A full Download Data run then cached 126,975 files (15 GB),
  while storage grew by about 1 GB (the game's own index files and the
  links).
  iPad: 5,271 cached files linked, 636 MB saved. [e774947]

### Android: Deploy starting the game
- On a Galaxy Fold, Deploy failed to start the game most times. Android
  stopped the game's process because it took over 10 seconds to start. The
  check for empty cached files followed each cached file's link to the game
  files on shared storage. It now reads the links themselves and stops
  after 3 seconds. [81b68ec]

### iOS: start-up after a full download
- After the game's data is fully downloaded, iOS no longer stops the game
  while it starts. The check for empty cached files read each of the
  100,000+ cached files one by one, which took longer than iOS's 20-second
  launch limit. It now reads them in bulk and stops after 4 seconds.
  [07e7627]
- Linking a new download no longer reads every cache folder. Each asset
  request took about 0.2 s and now takes well under a millisecond, so
  Download Data runs at full speed again. [30d4235]

### Archive: Schedule
A new section lists the live service's dated content from the original
master data, in UTC. [f6fd958]
- **Timeline:** what started each month, linked to its entry.
- **Summons:** banner art, runs, shards, pity and leftover conversion, and
  each shard exchange's items (costumes link to their pages). Summons without
  a banner, or with only placeholder rows, take their shard exchange's dates,
  as on the server.
- **Events, shops, home banners and the rest:** event quests by difficulty,
  shop items with prices and limits, every home banner, login bonuses, Arena
  seasons, Subjugation Battles, mission passes, campaigns and fortune draws.
- **No date in the game data:** about 150 rows carry a placeholder date
  (mostly 19 Aug–16 Sep 2099) instead of their real dates. They are listed
  separately, not as "never ran". Each row shows whether its art and title
  are in the English files and whether the same target ran on a dated row.
- **Names:** 62 summons whose title exists only in their banner art are named
  from the art; Pod Programs' schedule uses the same names. 13 have no English
  title or art.
- The Schedule is built along with the index, so it opens at once.

## 2026-10-13

### Pod Programs: Original calendar
Content › Schedule can replay the live service from global launch (28 July
2021) instead of keeping everything open. [36e881f, f8051fe, 921b5b3, 356d2d1]
- **Game data:** events, summons, shops, seasons, missions, login bonuses,
  campaigns and item terms move forward by whole weeks to start at the current
  week. The main story, character lists, collections and the character viewer
  count as already released.
- **Moving ahead:** Next update, Next week, or Jump to a week or an update,
  with a preview of what opens, what is still paid and what is skipped. The
  calendar only moves forward, in whole days.
- **Speed:** real time, 2×, 3.5× or 7×, one week at a time at the daily reset.
- **Loops:** a loop is 144 weeks. The next loop's game data is built ahead,
  and the server starts it when a loop ends.
- **Server:** an Arena season's final rank reward is paid after it ends. Event
  items leave the inventory when their term ends. A new loop resets event
  quests, event missions, exchange shop purchases, the mission pass, login
  bonuses, Labyrinth seasons, Subjugation Battle records and limited summon
  progress. Subjugation Battles follow the game clock while the server runs.
  [356d2d1]
- **Speed** is saved with a Save speed button, so scrolling can't change it.

### Summons
- NieR:Automata Crossover Vol. 2 (launch and rerun) is offered and gives
  Vol. 1's Shard (Automata). The server used to skip it. [8ddce67]
- Leftover shards become Medals once, at the medal's conversion date. The
  summon screen shows the conversion once. Before, ended summons added the
  shards a second time. [77c1b59, c9b4c25]
- The ticket draw takes the Premium Summon Ticket (item 1002), not Gold.
  [77c1b59]
- Each summon's pity ceiling comes from its medal (50, 100, 150 or 200).
- Summons with a placeholder 2099 row (50, 58) are listed once and open.
- With the calendar, featured items match catalog terms on original dates.
- The server sends the shard conversion popup until the next game start.
  The game only shows it when you open Summons, not when you return to it.
  [c9b4c25]
- Multi-step summons are one summon each, with 7, 5 or 3 steps from the game
  text (5 when unknown).
- Summons that start together get their own featured items: those their
  exchange shop also sells (e.g. Drakengard 3 rerun, FFXIV Resurrected).
- Chapter summons moved to ids 2100000+ (saved box progress moves with
  them), so "Mama's Dream" banners no longer open chapter 1 and 2 summons.
- 19 summons without a medal row get theirs from a matching exchange shop
  (Festive Dress, YoRHa Stage Play, Fortune's Dress, Blessed Dress, DQX,
  Yuletide and more).
- FFXIV (159) and Monthly Featured (414) reruns run on their shop's dates.
- Special summons follow their titles: free summons give one free 10-pull a
  day, "★★★★ guaranteed" ones a single 10-pull with a ★4 for 3000 gems, and
  "paid only" ones take paid gems. Bonus and newcomer summons are left out.
  [c83dcc1]
- Every draw includes a medal bonus, even an empty one. Without it, free
  summons hung. A used-up draw option is switched off, so the game can't
  send a draw that the server refuses (that restarted the game). [65dfca7]
- Summons with shards but no banner row are offered from their exchange
  shop's opening to two days before the shards convert: 106 weekly
  summons, 22 paid multi-step summons, Fortune's Dress and Blessed Dress.
  Pod Programs names them after their shards (e.g. "Weekly Summons B").
  Five without art are left out. [5d37688]
- Known issue: on the Android 16 emulator the game can crash (libil2cpp
  0x257da0c) during the first few summons after starting. A 6 October
  build without Bunker's display or server changes crashes the same way.
  The Galaxy Fold doesn't crash.

### Story events
- Chapter 6-4 (Levania's memory): the player could walk past Mama's lines and
  fall off the right edge of the map. The game misses a player who walks
  through an event's zone while a speech balloon fades out. Now that zone
  still counts. The fix applies on Android and iOS at every frame rate,
  including the game's own 30 fps. Chapter 6-7's tree still falls across the
  chasm. [4b4f8f8, 2e71e34]

### Server: behaving like the original game
Checked against the game's master data and the 3.7.1 client. [2aa0757]
- **Gifts:** claiming a gift now grants it. Before, login bonus rewards
  were lost. Expired gifts are dropped and reported. A gift over its storage
  limit stays in the box. Login gifts say "Earned from login bonus". The gift
  box filters and pages work, and history shows the newest 100.
- **Login bonus:** one stamp per day.
- **Duplicates:** duplicate costumes and companions from any source give their
  exchange items. Enhanced costumes and companions arrive at their proper level.
  Companions 49–51 and 53 below level 50 are raised to 50.
- **Summons:** a failed payment cancels the draw. Each chapter summon uses its
  own chapter ticket. The summon medal limit comes from master data.
- **Costumes:** level bonus stats and karma results now apply in battle.
- **Quests:**
  - Quest missions are judged from how the battle went and the deck used. They
    clear only on a win and pay when they clear.
  - Event, extra and Subjugation Battle first clears no longer lose their
    rewards after a story replay.
  - A lost or retired quest is marked "challenged", which unlocks quests that
    need it.
  - Quest bonus drops and key-item drop effects apply.
  - Recollections of Dusk locks the costumes and weapons used in a run.
  - Hidden stories and Lost Archives wait for the quests that unlock them.
  - Skips are refused without enough tickets or stamina.
- **Subjugation Battles:** pay only the highest score tier reached. Damage
  counts across all waves, and a crashed run no longer carries into the next.
- **Missions:** bosses defeated, Subjugation Battle knockdowns, reports, Arena
  play, wins, streaks and rank, library, ability level, exploration score and
  concert taps now count. 6,284 of 6,436 missions have rules.
- **Friends:** the Arena's computer players can be added as friends and sent
  support, so "Send a friend support" and "complete all dailies" can clear.
- **Profile:** shows the last deck used and its real total force.
- **Other:** exploring keeps natural stamina recovery. Visiting a cage ornament
  no longer marks its reward received.
- **Reliability:** an error in one request no longer stops the server. Database
  settings apply to every connection, and saves can't overwrite each other.

### Server: more of the original game
- **Daily reset:** days now start at 00:00 GMT-8, all year, as the game's own
  "Resets at 00:00 (PST)" says. Weeks start Monday 00:00 GMT-8. Older saves
  switch over without losing the week's Subjugation Battle and Arena
  results, and without a second daily reward on the day of the switch.
- **Daily quests:** quests that can be cleared a set number of times a day
  start over each day.
- **Stamina:** levelling up no longer lowers stamina that is above the maximum.
- **Shop:** limited stock refills each day, week or month, as the game data
  says, and a sold-out item can't be bought.
- **Storage limits:** items past the limit (999 weapons or memoirs, 99,999
  materials) go to the gift box, labelled as the game labels them. Summons,
  quests, missions and the shop all do this, and the shop shows its "sent to
  gift box" notice.
- **Debris** rewards are granted; they were dropped before.
- **Character viewer:** a field's unlock notice shows once, not on every visit.
- **Mama's summon banner** shows the latest chapter you've unlocked.
- **Missions:** 66 more missions count (6,350 of 6,436), including:
  - the Collection missions for sets of costumes;
  - event missions for a named weapon or costume;
  - "Update your profile comment" and the New Year missions.

  Event missions on Hard and EX Hard quests now match their quests.
- **Friends:** computer players each have their own level and total force.
- **Profile:** play history shows its 29 counts. The Cage's pedometer shows the
  distance walked.

### Server: fixes
- A new player's first load stopped at 60%. Two karma tables were sent as
  null; every table is now sent as a list. [ac566d3]

### iOS device tools
- `device.py hold` keeps a finger on the walking stick. The test controller
  runs under Xcode 27. [a937c20]

## 2026-10-10

### Docs
- README: summon details, server fixes, and where missions and the Arena were
  tested. [b74def2]

## 2026-10-08

### Server
- Arena against computer players: ladder, battles, points, rewards, defense
  battles and weekly results. [cb4988d]

## 2026-10-07

### Server
- Missions:
  - Daily, challenge, special and mission pass missions progress and pay their
    rewards.
  - Mission pass points and levels.
  - Progress already in a save counts once.
  - Rules come from the missions' names. [4683eba]
- Missing handlers added: the daily quest set reward, skipping several quests
  at once, costume level bonus confirmation, story choices, labyrinth season
  rewards, unread pop-ups and Portal Cage drops. [4683eba]
- Pod Programs → Summon rates sets the summon rates, which the game's Rates page
  shows. [4683eba]
- The summon Details page shows the banner's costs, exchange and item rates.
  [926046b]
- Friend actions are answered offline instead of failing. [b1d6100]
- A daily login counts for missions. Empty cached assets are dropped at game
  start, on Android and iOS. [108ec0a, 01660dc]

### Display
- Above 30 fps, battles move in whole 30 Hz steps. This fixes a crash in the
  summon reveal. [ecf7393]

### Archive
- Every costume is named. 10H's story variant is filed with her. Placeholder
  stills and blend layers are dropped. [2c4b9ac]
- Movies open full screen. The Archive is added to the iOS launcher. [be752ba]

### Launcher and docs
- About shows Bunker, its creator and credits. [0c34541]
- README: Archive and Display screenshots. [c9bb5d8]

## 2026-10-06

### Display
- Pod Programs → Display sets the frame rate (30, 60, 90, 120 or the screen's
  maximum) and resolution (1080p, 1440p or the screen's own). Walking and
  battles keep their 30 fps speed. [f81a3e9, da80e25]
- The same on iPhone and iPad, and Game Mode on both platforms. [1af9015]

### Archive
- Main-story lines show who says them, and chapters use the game's names.
  [fafe305]
- Stories are named by character or event; Library summaries are filed as the
  game files them. [f86dc2f, cf847b5]
- Weapons with art and 3D models; companions, memoirs, cast and enemies in 3D;
  a named gallery. [9fbc19c, 70a5056, 6c0d44f]
- Movies filed by season, title screen and announcement. The soundtrack is
  filed where each track is first heard, with every place it plays. [ef48d7a,
  b006fd2, ccc0fcd]
- Viewer fixes for very large models, and story characters' textures.
  [61ba3f8, 9ec5d22, b4b9c2a, 14f08b0]

### Docs
- README features section; display validation on the Fold, the iPad and the web
  build. [9a6b667, 52842c8, 4eaaf9c, e62b91d]

## 2026-10-05

### Archive
- A read-only Archive beside the game, with the story, records, movies and
  search. [fe481a0]
- Characters, costumes and a gallery, with textures decoded on the phone.
  [c524454]
- Voice lines and music, played on the phone. [cafcb97]
- A 3D viewer with costumes and character motions. [b0cc4bc]
- A full audit of every page and conversion, with the problems it found fixed.
  [187482b, 65baa4d]

### Web builder and launcher
- Web-built APKs are signed with a public Bunker key, and the download is fixed.
  [a37b411, a399acb]
- Internal identifiers renamed to org.veritr1x.bunker; existing installs update
  normally. [ffbb2f3]
- Mac: a Bunker menu with ⌘B opens the launcher. [a2ac31a]
- Pod Programs uses the launcher's colours. [c134238]

## 2026-10-04

### Launcher
- The game starts its server when reopened directly from Recent apps. [4c03fbb]
- Server self-checks, clear errors when another app holds a port, and an
  optional port offset. [1d9e1d8]
- Launcher and Pod Programs redesigned. The server log is kept between sessions.
  You can choose or start a player. [9a6db6a]
- Renamed to Bunker; the builds are now bunker.apk and bunker.ipa. [467a5eb]

### Docs
- README screenshots and a shorter description. [f2e727b, c7bd61f]

## 2026-10-03

### Platforms
- iPhone and iPad build: the server runs inside the game, offline. [d1045c2]
- Android:
  - Import shows progress with time left. [7372bbd]
  - Save backup import. [7372bbd]
  - The APK builds without apktool. [5f45d19]
  - The game keeps its own name, NieR. [1cf9aa8]
- Android 17: picked archives import correctly. [21f59cb]
- Android: the game reaches its own server even with VPN and proxy apps.
  [ea7b7b9]
- iOS: the launcher redraws after an import at launch. [0937b41]

### Game files
- The extracted resource dump can be imported directly, copying only revision
  0. [cdb901d, f126c53]
- Its .7z or .zip can be imported directly, or a folder used in place.
  [26858a8]
- Archive progress fixed; the iOS chooser matches Android. [328a1d0, 91d45fe]

### Web builder
- An in-browser builder, published by GitHub Actions. Your files are never
  uploaded. [37d74af, 9c70834]

### Docs
- Step-by-step build from a fresh clone; renamed outputs and repository URL.
  [24cd9ab, 7cfd8f0, 8cc3745, 7cd67f4, f6e7c95]

## 2026-09-20

- Android all-in-one launcher with pinned upstream projects. [649aab4]
