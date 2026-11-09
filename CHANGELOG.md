# Changelog

What changed in Bunker, newest first. Each day lists its changes by area.
Commit ids are in brackets. A release's notes are the dated sections
under its heading, down to the previous release.

## 1.10.4 (2026-11-09)

The iPad game on a TV fills its window again, and Deck Builder keeps loading
decks on a big screen. With upscaling on, a window resized or moved to an
external display could show the picture in a corner, or offset, with the rest
black; the upscaler now follows the window. The picture keeps the game's own
shape (1.10.3 gave it the window's, and in an upright window the game broke).
An exported log now shows the display settings and what the window and the
upscaler did.

## 2026-11-09 (after 1.10.3)

### iPhone and iPad
- With upscaling on (Pod Programs › Display), a window resized or moved to an
  external display could show the game's picture in its top-left corner, or
  offset, with the rest black. The upscaler now follows the window's size each
  frame. [f9914c6]
- The picture keeps the game's own shape again, stretched to the window, as
  before 1.10.3. 1.10.3 gave it the window's shape (16:9 on a TV); in an
  upright Stage Manager window that made the game's screen upright, and the
  game broke. [f9914c6]
- Export Lunar Tear log shows the display: the Display settings, the screen
  and the window's size once it settles, the display's mode, the size the
  game draws at and the size the upscaler writes, as "[Display]" lines.
  [f9914c6]

### Pod Programs
- Deck Builder: on a screen tall enough for the first six decks (an iPad, a
  TV) the list stopped there with "Scroll for more" and nothing to scroll; it
  now loads more while the end of the list is in view. In Filters, tapping a
  character no longer loads every portrait again. [28c7145]

## 1.10.3 (2026-11-09)

The iPad game on a TV, and updates in the game work again. With Stage
Manager the game's window can be resized and moved to an external display,
and its picture takes the window's shape: 16:9 on a TV instead of the iPad's
shape stretched. An update made in the game no longer stops with "ZIP does
not support timestamps before 1980", and the Bunker menu keeps its layout
while an update is offered. With the Original calendar, limited-time packs
open on what opened them, one player at a time, and an event that reran
replays each run with its own medals and exchange.

## 2026-11-09 (after 1.10.1)

### Calendar
- Limited-time packs open as they did, one player at a time. With the
  Original calendar every pack (Jumpstart, the chapter completion packs,
  The Sun and The Moon packs at each difficulty, the Overture packs) opened
  on the loop's first day for about two years, the 1.10.1 fix sending them
  for their whole sale period. Now each opens when the player does what
  opened it, while the calendar has it on sale, for its own hours, once:
  a completion pack on clearing its chapter at its difficulty (72 hours;
  the Overtures 24), at the next login for a chapter cleared before, as the
  notices said; a Jumpstart pack on finishing the chapter 2 loadout tutorial
  (48 hours, 24 from 30 March 2023); the Ch. 6 pack from 1 November 2021
  (notice 140). The Mythic Slab Material Pack opening when Mythic Slabs
  unlock is a guess. Triggers and hours come from the packs' own texts and
  chapter names. With everything open every pack stays open. [f66af2d]
- An event that reran replays each run as it was. Its quests drop that
  run's own medal, its quest bonuses pay it, its page shows it and its
  Exchange button opens that run's exchange; a run shows only the quests it
  had (later reruns added up to six). The final game data keeps the last run
  only, so every replayed run dropped the last run's medals while the
  earlier runs' exchanges, taking medals nothing dropped, opened beside the
  last run's, which stayed open from the first run to the last: two
  Automata Medal Exchanges on a new calendar. 29 events, 33 runs,
  read from the game data published during each run
  (scripts/event_runs.py, event_runs.json). Coffin of Repose, Path of
  Longing and Rhythm's Citadel ran once, in 2021, but their quests were later
  switched to medals for reruns that never ran on Global (exchanges 6025 and
  6030 were never dated): their only run had an exchange taking a medal
  nothing dropped. They drop their 2021 medals again. Garden of Benediction's 2021 run
  had its drops and its exchange's link rewritten for the January 2022 run;
  both come from the 2021 data. Bonuses that paid a medal whose exchange had
  already closed (a reused bonus effect in four runs from late 2022) are left
  out. The result screen still names the last run's bonus medals: the game
  works them out from its own data. Calendars in use rebuild their data
  (data version 4, view copy 5). [3a420c0]

### iPhone and iPad
- On an iPad with Stage Manager the game's window can be resized, and moved
  to an external display and made full screen there; it was a fixed window
  in the iPad's own shape, even on a 16:9 TV. The game's picture takes the
  window's shape (it drew in the iPad's shape and was stretched): at 1080 on
  a 16:9 display it is 1920×1080. An app updated in place gets this too.
  Without a pointer, a window on an external display opens small. [a8671e8]
- An update made in the game no longer fails with "ZIP does not support
  timestamps before 1980". The updater dated the files it changes
  (Info.plist, the Unity settings, UnityFramework) 1980-01-01 00:00, and
  IPAs built or signed on a Mac dated every file so; installed, they read as
  1979 in a time zone further west, and the next update refused them. The
  updater dates them now and takes older dates as 1980, and IPAs built or
  signed on a Mac keep each file's date. An app updated in the game before
  this needs one install with the web builder (same bundle ID, so the save
  stays); the update after that works. [7753994]
- The Bunker menu no longer shrinks to a narrow column while an update the
  game can make is offered (CHANGE past its border, the status chips cut
  off). [60a6c42]

## 1.10.1 (2026-11-09)

Story Jump and stronger Force decks. Pod Programs' Story Jump brings a save
forward to the start of any main-story chapter, or a quest in one, with the
characters and rewards the story gives on the way. Deck Builder's memoirs
are built to the original game's limits, the Force list has its own memoirs
and karma, and Subjugation is simulated as the game plays it. Subjugation
scores are counted as the game counted them, and fixes from the Lunar Tear
forks bring back the limited-sale banners and the Limited shop's packs, keep
dailies running after the calendar is turned off and clear first-day login
missions. Memoir Editor has a Game-legal only toggle.

## 2026-11-08 (after 1.10.0)

### Server
- Subjugation scores are counted as the game counted them. The base score
  is the total damage / 100 (it was the damage itself, so every score was
  100 times too high). The survival bonus
  depends on how many characters died over the run (+200% with none,
  +150%, +100%, +50%, then nothing from four), and the max-combo bonus
  has nine tiers (+20% from 6 up to +180% from 46); they were a flat
  +50% and three tiers. The old guide's damage-per-grade tables match this
  exactly. From the JCalandre/lunar-tear fork. High scores already saved
  are divided by 100 once, so new runs can beat them.
- The game gets every table it asks for when it loads the save. Three of
  Bunker's tables were sent empty there. One holds the limited-time
  offers' sale dates, so the game's "on sale for a limited time" banners
  never appeared, and with the Original calendar the Limited shop's 34
  packs didn't either (with everything open the game data keeps them in
  the shop). The other two are the beginner and comeback campaigns, which
  the game forgot after a restart. From the WoefulWolf and JCalandre forks.
- Turning the calendar off after a jump or a faster speed no longer freezes
  the daily things until the real date catches up. Times saved on the
  jumped-to day (logins, daily missions, login stamps, shop stock and
  refreshes, Subjugation dailies, guerrilla opens, the roulette, daily quest
  plays) move to the day before, and the Arena week to the current week.
  The login streak carries on. Found in the lovelyzy7 fork.
- Daily "Log in" missions clear on the day a player is created, and on a
  day such a mission opens after the first login. From the lovelyzy7 fork.
- Loading a map is lighter. The game sends one request per gimmick sequence
  as a map loads, and each loaded the whole save about five times and wrote
  it twice; now each adds its one row and sends the game that row. A save
  already holding 1000 sequences takes the old way. From the JCalandre fork.
- A memoir drop gives its count: under a drop-rate campaign the reward
  showed 2 memoirs and gave 1. From the JCalandre fork.
- 25 event chapters show three memoirs that none of their quests drop (the
  second and third series, and the first at a higher rarity than its
  quests'); they were random enemy drops whose tables never shipped. One
  clear in two now adds one of them at random. The chance is an estimate.
  The gap was found in the JCalandre fork.

### Pod Programs
- Deck Builder's All maxed builds every memoir at its fullest under the
  original game's rules: a sub stat's rolls stack, and the top sub stat
  reaches the guide's limits (25% crit rate, 36% crit damage, 12.5% HP,
  ATK or DEF, 72 agility). An attacker's memoir set carries crit rate
  +70% and crit damage +73% (it gave every sub stat one roll: 7.5% crit
  rate, 14% crit damage). The Force list has its own memoirs, built for
  the stats Force counts most: flat ATK and DEF mains with HP% at its
  top and ATK% and DEF% (twice the Force of the crit set), and its own
  karma, chosen for Force (written with the deck).
- Memoir Editor has a Game-legal only toggle. Off (the default), it
  writes whatever you enter, as before. On, Build a Set and Fix Slots
  make only memoirs the original game could: HP%, ATK%, DEF%, crit and
  agility sub stats, each once, none past its top and only one at it,
  with legal values filled in; the save editor refuses anything else. Characters are
  rank 10, as fully raised characters are (they were rank 1).
- The simulator hits as the game does: the client's own damage formula
  (DEF can at most halve a hit; a hit is at most 1,500,000), in place of
  a guess calibrated on one video hit; the same hit now comes out within
  7% of the video. All maxed was baked again for these.
- Deck Builder's Subjugation damage is simulated as the game plays it on
  Auto, and checked against fights recorded on the emulator: a whole D5
  fight comes out within half again of the game's (it predicted five
  times too much). From the game client: two-minute waves; the boss's
  own skill AI (one skill at a time, with cast times; its main attack
  never targets a character it is weak against); the boss takes half
  damage from every element but its weakness; a knock-down stops the
  clock for 35 seconds and multiplies hits after the 1.5M cap; a wave
  without one hands its gauge to the next; weapon cooldowns at the game's
  pace; on Auto only weapon skills fire (never character or companion
  skills); units act one at a time in agility rounds, the boss's turn
  holding the rest. Decks main weapons of the boss's weakness, the
  hardest-hitting first.
- **Story Jump** (Programs › Story Jump): bring a save forward to the
  start of a main-story chapter, or to a quest in one, without playing
  through what comes before. Each skipped quest is cleared as the server
  clears a quest the story moves past: its exp, gold and first-clear
  rewards once (the characters, weapons, companions, key items and gems
  the story gives), its missions marked clear without their rewards, no
  drops. The story tutorials before it are finished (the companion choice
  gives the first companion offered). Season 2 asks which route; a save
  already on one route stays on it. Forward only: chapters behind the save
  have no Jump. A preview lists what a jump will clear and give (only what
  the save gains), and every jump is backed up first; a refused jump leaves
  no backup. The game keeps running for a preview. With the Original
  calendar in its first loop the game data is built again, so the chapter
  jumped to is open. It opens for the player in use, and works with the
  Global and Japanese game data, whose stories are laid out the same. A
  companion already chosen in the tutorial is kept.

## 1.10.0 (2026-11-08)

Deck Builder, Gift and more mods. Pod Programs has a Deck Builder that
builds Arena, Loadout and Subjugation decks from what you own or with
everything maxed, explains every piece and writes the deck into your save;
All maxed is ranked from 3.2 million decks fought ahead of time. Gift sends
you anything the game can hold, to the in-game Gift Box. The mods add
unlimited daily plays, free skips, an EXP multiplier, friends from the story
and three challenges that pay a reward bonus, and Start a new day restarts
everything daily at once. Pod Programs fits a phone on its side and reads
the same on every page. With the calendar on, auto-repeat runs every
repeat again. Summons give the shards and medals their notices and art
name, at the prices they show.

## 2026-11-08 (after 1.9.0)

### Pod Programs
- **Deck Builder**: decks for the Arena (attack or defense) and for
  Subjugation, built from what you own (with up to a set number of pieces
  added) or with everything maxed. Each deck lists its characters, their
  weapons, companion, memoirs and debris, why each was picked, the game's
  exact Force and how often it wins. Filter by element, strategy, effects
  and characters to require or leave out, build against the general meta or
  an Arena opponent, and sort by best match, Force or fewest pieces to add.
  WRITE DECK opens a deck picker with your Arena and Loadout decks, each
  showing what it holds, and lists what the write replaces before you
  confirm; Save Data keeps a snapshot first. [0741446] [bcb9152] [9143370]
- All maxed ranks the best decks in a world where you own everything: all
  3,177,096 decks of the 280 playable costumes were fought ahead of time,
  each costume in the gear and karma that serve it best, against 50
  opponents (the experts' 23 meta decks and the 27 strongest decks). The list
  shows the numbers it was ranked by, so it reads in order and pages load at
  once; Sort Force uses each costume's loadout with the most Force. A
  costume you're missing lowers its character's stats, so a deck can do a
  little worse for you than shown. [3329806] [e3cde14] [97573c6] [abb2432]
- Explanations wait behind an ⓘ in portrait as in landscape: each page's
  intro beside its title, and longer notes beside what they explain.
  [438cb09]
- Every page uses one set of text sizes, at least 12 px, with form fields
  at 16 px so iPhone no longer zooms into them; owned rows are no longer
  faded, long names wrap instead of being cut off, buttons are easier to
  tap and the light theme has enough contrast. [5c0b0a4]
- On a phone on its side Pod Programs uses the whole screen: the title,
  Close and the tabs in a column on the left, each page's controls beside
  its content. [9950d37]

### Arena
- Computer players field real lineups with full loadouts from Deck
  Builder's deck table. The top 100 ranks field the strongest decks; below
  them, opponents scale to how strong your own Arena decks are, not only
  their Force. The table is written when you open Deck Builder; until then
  computer players are as before. [2335ebe] [a66ce12]

### Bunker menu
- Auto deploy, in the ⋮ menu: on (the default), opening Bunker starts Lunar
  Tear and the game as before; off, it opens on the launcher until you tap
  Deploy. Android. [b02fe24]

### Content
- With the calendar on, auto-repeat runs every repeat again. Since the
  calendar put back events that ran more than once, every subquest's
  auto-repeat stopped after one clear with "The quest period has ended":
  the copies sat out of order in the game data, and the game, which looks
  rows up by binary search, missed their chapters. A calendar in use
  rebuilds its data when this version first starts. [b5c4e8f]

## 2026-11-07 (after 1.9.0)

### Server
- Quests drop Slab Fragments again. Story quests drop Small Slab Fragment
  x1-3 and, one clear in two, Medium Slab Fragment x1; guerrilla quests and
  the dungeons (The Dynast's Memories and the other memories) drop Small
  Slab Fragment x1. The live game rolled these as random enemy drops whose
  tables never shipped, so no story quest dropped any and Small ones
  only came from missions, login bonuses and shops. Drop-rate campaigns
  and the mods' reward multiplier apply to them. The amounts are an
  estimate from the notices and the item's Location list.

### Mods
- The Mods page is in five groups: Quests, Items & shops, Summons, World
  and Challenges. Each one folds away, and the page remembers which.
  [27beb49] [1421a6d]
- New mods: Unlimited daily plays (daily-limited quests don't count their
  clears), Free skips (no skip tickets used) and an EXP multiplier (×1–×10
  for you, your characters and their costumes). [15e7587] Friends from the
  story: 2B, 9S, A2, Fio, Lars, Akeha, Noelle and 20 more join your friends,
  cheer every day and fight in the Arena, each leading with their own
  costume. They aren't written to your save, and they fill only the free
  places in your friend list (100). [feaa1cd]
- Challenges, for harder battles that pay more: Hard enemies (enemy HP,
  attack and defense ×1.5, ×2, ×3 or ×5; subjugation bosses stay), Weakness
  only (hits that aren't super-effective do half damage; the Arena stays)
  and Slow skills (your skills take 50% longer to come back). They change the
  game data, so the game goes back to its title screen to load them, and
  turning them off gives the game data back exactly. Each pays a reward
  bonus: ×2 to ×6 for Hard enemies, ×2 for the other two, multiplied, up to
  ×10, while the Quests, Items & shops and Summons mods are off. [b52580f]
  [5a3e55d] [5aa63c4]
- Presets: Comfort is the Comfort Mod's eight mods, as before; Everything
  turns on every mod but the challenges, with rewards and EXP ×10. [5aa63c4]

### Content
- Start a new day: everything daily starts over at once (quest plays,
  missions, shop restocks, free summons, cheers and the login bonus).
  Weekly limits and the calendar don't move. The game closes so it starts
  the day fresh; tap Deploy to play. The challenge bonus pauses until the
  next day. [0d18580] [2f54d36] [8c49603]

### Bunker menu
- The Bunker's own text, on Android and iPhone, says the same thing the
  same way. "Server" and "Tools" became Lunar Tear and Pod Programs, Play
  became Deploy, and "phone" became "device" where both apply. "Could
  not", "Unable to" and "Native call failed" became plain "Couldn't" and
  "didn't respond" messages that say what to do next. The help on both
  covers the same points in the same order, and the notification says the
  game goes to its title screen to load a change instead of closing.
  Copying an extracted folder on iPhone asks for 21 GB, as Android does.
  [d8bdde1]
- On a phone on its side, the whole Bunker fits on the screen. The
  Programs panel's bottom sat under the edge until you scrolled. [a96e90d]

## 2026-11-06 (after 1.9.0)

### Summons
- Banners give the shards and medals their notices and art name. Vol. 2
  and 3 of four summons and five shard summons (59, 123, 467, 471, 531001
  and 546) got the medal another summon has; 186, 194 and 405 take paid
  gems only; 554 is one free 10x; 600-605, 609 and 610 a free 10x every
  day. [a906ed5] Ten paid-only twins whose own notices name a shard get it.
  [b81b4df]
- Every summon in the Global and Japanese masters checked against its
  notice and art: 17 more give their shard, among them the Healer & Support
  summons and their reruns, the May 2023 weekly summons, the DQX, Tale of
  Resistance and Never-Ending Adventure multi-steps and the free
  Hallowed Winter's Night 10x. The Healer & Support reruns offer the ★4
  weapons their exchange had when each began; the August 2023 one also
  listed February 2024's. [84e8758]
- With the calendar off, All content and Gacha shops open every
  summon-medal exchange. 135 of the 289 stayed closed (the weekly summons,
  Healer & Support, Tale of Resistance, Never-Ending Adventure and others),
  so their summons gave no shard and had no Exchange. Apply the preset again
  to get them. [d0641d4]
- Summons whose prices were the usual ones by default, checked against their
  art by eye (198 summons): the element summons (43, 52, 60, 85, 9000007) are
  a 10x for 1,500 paid gems; eight bonus summons (9000021 and others) a 10x
  for 2,000 gems, 5 or 20 times; 9000082 a free 10x once a day; 9002's 10x
  gives Advanced Handbook x2, 10 times. [a9c4d27]
- The draw buttons no longer show the price struck through beside itself
  ("300 300", "3000 3000"), as if every summon were on sale. [38629bd]

### Notices
- Reconstructed notices show the summon prices the server charges. Ten
  showed old prices (Summer[in]carnation and Pre-1.5-Year Anniversary
  summons as gems instead of paid gems only, multi-steps with the wrong
  steps). The notice pack is brought in line with the summon rules as it is
  fetched, so later price fixes reach the Notices screen too. [3ede598]

### Pod Programs
- **Gift**: send yourself anything the game can hold, from gems and summon
  tickets to characters, weapons, memoirs and debris, sorted by what each is
  for: Currency, Summoning, Character growth, Weapon growth, Collection and
  Everyday. It arrives in the game's own Gift Box as "From Bunker, with
  love." and is claimed there like any other gift; the game keeps running.
  [a6c5da2] A count above what can still be claimed is refused, not cut
  down, and debris you already own or that is already waiting can't be
  sent. [b250f00] The Item, Costume and Weapon editors say how many gifts
  are waiting. [52e6392]
  Game data without the gift text (made before this version, imported or
  restored) gets it with the first gift, which sends the game to its title
  screen once; there is nothing to apply first. [3650b8f] Gift is also on
  the Programs page. [da9e0fa] Choosing the Original calendar under Content
  now hides the presets, which are off while it runs. [662745f]
- Turning the calendar off and "Show original dates" close the game without
  asking; the "Close the game?" dialog is gone. Tap Deploy to start it again.
  [0ae30da]
- After the calendar's clock goes back (turned off after a jump, "Show
  original dates" on, a new loop with it on), the login bonus, Mama's News
  and the FREE badges show again from the next start. The game kept the
  jumped-to day as the last one it showed them, and turning the calendar off
  never cleared it. [0ae30da]

## 1.9.0 (2026-11-06)

Mods and changes that reach the running game. Pod Programs has a Mods
program: free stamina, stamina items as gold, premium tickets as gems,
shop items that never run out, Lost Items that give gems, quest rewards ×2
to ×10, no duplicate ★4 and summon medals traded for gems, each off until
you turn it on, with Original and Comfort presets (most from the Lunar Tear
Comfort Mod by NavHobbyDev, MIT). A change to the save, the players, the
master data or the calendar no longer closes the game: Lunar Tear restarts
around it and the game goes straight back to its title screen to load it.
The Bunker menu and Pod Programs fit a phone or tablet on its side, and on
an iPad held upright the menu turns upright too. Busy screens such as
Quests and Summons run faster at 60 and 120 fps. Coffin of Repose and
Rhythm's Citadel medals can be spent, and an edited save no longer drops
back to level 1.

## 2026-11-06 (after 1.8.4)

### Bunker menu
- Landscape on a phone: System on the left; Play and a Programs panel on
  the right, with Pod Programs and Archive as rows that say what each
  holds. Everything fits on one screen, Deploy included. A tablet on its
  side gets the same two columns with the full top bar; portrait is
  unchanged. [b538fa4] The same on iPhone and iPad. [91fc7bf]
- iOS: the Bunker menu, Pod Programs and the Archive turn upright with
  the device; the game stays on its side. On an iPad held upright the menu
  used to open in a window on its side. [4b3450f, a00d7af]

### Game
- The in-game Bunker button no longer slows busy screens. The game has two
  headers, and with one shared state the button looked its row up again
  and searched the whole interface for the counters every frame; on an
  iPad at 120 fps that took about a third of the main thread on Quests.
  [0c72350] It now looks only under the heads-up display. [88c928f]
- Above 30 fps, campaign badges ("Left: 999d") set their remaining time
  once a second instead of every frame; each update rebuilt the label and
  its layout, and open campaigns put a badge on many Subquests rows.
  [a90b04a]
- A header or campaign badge the game makes where a destroyed one was is
  set up as new instead of taking the destroyed one's state. [160582d]

### Pod Programs
- After a change beside the running game, the game goes back to its title
  screen at once instead of on its next call: its own "Returning to title
  screen." dialog shows as you return to it. During a battle it waits for the
  battle to end. Without that, the next call does it, as before. On Android
  and iPhone/iPad. [9fea028]
- A change that was refused, sent back with an error or changed nothing
  (choosing the player already in use) no longer sends the game to its
  title screen; Lunar Tear still starts again. [ea82989]
- Two changes in a row no longer close the game: the launcher's own check
  as Lunar Tear started again was taken for the game's next call and
  failed. [1c8737f]
- Android: when the save backup before a change fails and Lunar Tear then
  cannot start again, the game is closed instead of being left without a
  server. [ea82989]

### Server
- The desktop server's master data reload builds the tables derived from
  the master data again, as a restart does. [97135ff]
- Mods: a gift that arrives as something else (a premium ticket as gems) is
  checked against the limit of what arrives, not the ticket's. [4cd5f74]
  mods.json is looked at once a second at most instead of for every item
  granted; a change in Pod Programs is in use within a second. [1cd99ff]
- Coffin of Repose and Rhythm's Citadel medals can be spent. The events
  dropped medal variants (Coffin of Repose 53 and 54, Rhythm's Citadel 63,
  64 and 65) that their exchanges do not take; drops now arrive as the
  medal the exchange takes (22 and 29), and medals already held are turned
  into it, one for one. As in the Lunar Tear Comfort Mod by NavHobbyDev
  (MIT). [bc8f5ca]

### Mods
- Each mod's description no longer ends with when it applies ("From the
  next quest." and the like). [821b8cd]

## 2026-11-05 (after 1.8.4)

### Pod Programs
- Landscape on a phone: the top bar shrinks to one short line and the tabs
  move to a column on the left, so a page shows its content instead of a
  strip under the tabs. Tablets and unfolded phones keep the tabs on top;
  portrait is unchanged. On Android and iPhone. [851da47]

### Mods
- Pod Programs has a Mods program: changes to how the game plays, for the
  whole device, each off until you turn it on. Free stamina; stamina items
  that arrive as gold and premium summon tickets that arrive as free gems
  (items received from then on; items already held stay); shop items that
  restock daily, weekly or monthly never run out; Lost Items give 100 to
  1,000 free gems; quest drops and gold ×2 to ×10 (not Dark Memory quests,
  memoirs, costumes, weapons or limit-break materials); no duplicate ★4
  from a premium summon until you own every one; every 100 summon medals
  become 1,000 paid gems and 100 Mama Points in the gift box. Presets:
  Original (every mod off) and Comfort (every mod on, ×10). Changes apply
  without a restart, also while the game runs. Most mods come from the
  Lunar Tear Comfort Mod by NavHobbyDev (MIT). [2160919] [86aa0f4]

### Server
- The player level no longer falls back when exp is added to a save whose
  level is higher than its exp (a save edited to level 100 dropped to
  level 1 on its next quest). [ac954a3]

### Pod Programs
- Changes reach the running game without restarting it. Pod Programs opened
  beside the game no longer closes the game for a change to the save, the
  players, the master data or the calendar: Lunar Tear stops for the change,
  starts again, and the game's next call shows its own "Refresh / Process
  failed. Returning to title screen." dialog. OK returns to the title screen,
  and signing in again loads the change, with fresh master data when it
  changed. A battle or exploration result still in flight is kept. On Android
  and iPhone/iPad alike; only "Show original dates" and turning the calendar
  off still close the game, because the game reads them as it launches.
  [913f155]
- The Archive's index no longer fails with "unable to open database file"
  when the launcher builds it before the Archive has ever been opened.
  [c9e3d1f]

### Server
- Tables built from the master data are built again whenever Lunar Tear
  starts in the same process, so a server restarted after a master data
  change no longer mixes old and new data. [b607091]

## 1.8.4 (2026-11-04)

Arena seasons end. With Everything open, the seasons that share the latest
season's rewards take four-week turns; a season's final rank pays its season
reward and the next starts from 0 points. The Arena's Period line shows the
turn's dates instead of 2099, and a season reward still unclaimed when the
next season ends is kept and paid with it. The Original calendar, at any
speed, keeps the game's own season dates.

## 2026-11-04 (after 1.8.3)

### Docs
- The Arena validation notes and the Windows guide no longer name other
  Android emulators. [4b7867f]
- Validation notes: the Arena's dates checked on an iPad with the Original
  calendar [6f7765d] and on an iPhone with Everything open [52abf9e].

### Arena
- The Arena's Period line shows the season's four-week turn (for example
  10/26 to 11/23) instead of 2099, on Android and on iPhone and iPad. The
  game reads season dates from its master data, so when the game starts,
  Bunker gives the seasons that take turns the dates of their turns, the
  same seasons on the same weekly resets as the server. The game's own
  season check also sees an ended turn's end date pass. With the Original
  calendar, at any speed, nothing changes: its seasons keep the game's own
  dates. [5f6f483]
- A season reward is no longer lost when a second season ends before the
  first one's reward is claimed (an Arena visit after a turn, then no Home
  visit for four weeks): both stay due and are paid together; the game's
  report shows the later season. [03c2ea4]
- Seasons end. Bunker's content patcher keeps every Arena season open, so
  one season used to last forever and its rank reward was never paid. Now the
  seasons with the latest season's grades and rewards take turns, four weeks
  each, changing at the Arena's weekly reset (Monday 00:00 GMT-8). When a
  season ends, its final rank pays the season rank reward with the week's
  rewards, and the next season starts from 0 points with its own ladder of
  computer players. Battle points, the defense deck and past weekly results
  carry over. The Original calendar keeps the game's own season dates.
  The first visit after updating ends the season in progress; its reward
  comes with that week's rewards once the week is over, as the game claims
  Arena rewards only for finished weeks. [e395b33]
- A season that ends mid-week no longer leaves two results for one week.
  [e395b33]
- A server test covers season ends with the Original calendar at 7× speed:
  when the game clock jumps a week past a season's end, the next Arena visit
  still records the final rank and the last week played, and the next login
  claims them once. [b62da3d]

## 1.8.3 (2026-11-04)

Pod Programs opens while the game keeps running. Browsing and settings the
game reads later need nothing closed; a change to the save, the master data
or the calendar asks first, backs up the save and closes the game. Summon
Rates saves with its default costume shares, and the Android launcher's
ARCHIVE row shows the index check when opened from the game.

## 2026-11-03 (after 1.8.2)

### Pod Programs
- Pod Programs opens while the game keeps running, on Android and on iPhone
  and iPad. Browsing, summon and roulette rates, Display, the timeline filter
  and new backups need nothing closed. A change to the save (editors, players,
  Restore), the master data or the calendar first asks "Close the game?";
  confirming stops the server, backs up the save and closes the game, then
  makes the change. Closing Pod Programs without such a change leaves the
  game playing. Restore is no longer disabled while the game runs. [6edb1e8]

- Summon Rates: Save works with the default costume shares. The page shows
  the ★3 costume share as 33.33, which its field refused (it allowed only one
  decimal place); both costume shares now take any decimal. [9038060]

### Archive
- On Android, the launcher's ARCHIVE row no longer says NOT CHECKED when it
  is opened from the game or reopens after Pod Programs: it shows the check
  made before the game started, or checks (and builds if needed) then. [9038060]

## 1.8.2 (2026-11-03)

Japanese APKs work with the Japanese master data (20240405123139.bin.e):
missions follow its own rules and the Yuletide multi-step summon is offered.
The Anecdotes' panel pages show in the game's language, with item names
instead of raw IDs. The Archive's index now builds by itself: on Android
before the game starts, on iPhone and iPad in the background. Master data
files are accepted by their contents, so a renamed download works.

## 2026-11-03 (after 1.8.1)

### Japanese
- The Japanese APK's in-game Bunker button is labelled "バンカー". [b04cd9a]
- Mission rules check the loaded mission definitions before using a Global or
  Japanese rule. Japanese master data no longer lets a levelled weapon complete
  a costume-ascension mission with the same ID. Shifted skill, exploration and
  mission-pass conditions and seven Japanese-only stamina missions are covered.
  Unclaimed progress recorded under a mismatched rule resets before rewards
  can be claimed; already received rewards stay received. [b04cd9a]

### Japanese master
- The Yuletide multi-step summon is offered on the Japanese master, which
  keeps it under its own ID (503001) with no medal row of its own; it gets
  the Yuletide medal it ran beside. Global's summon list is unchanged. Three
  server tests that check Global's dates skip on the Japanese master, so
  `build.py` builds with it. [1031577]

### Anecdote panel pages
- The panel sheets follow the game's language. The Archive also indexes the
  game's Japanese and Korean text, and on a Japanese or Korean page the sheet
  title, panel titles, reward names, gems and completion stories are the
  game's own words in that language. Panel titles come from the game's
  mission names (with the panel's numbers); the few with no matching text
  stay English. Completion stories no longer come out empty on the Japanese
  master. The Archive index rebuilds once and grows by about 45 MB. [c7c7736]

### Archive
- On Android, the launcher checks the Archive's index before it starts the
  game. When the index is missing or out of date (new game files, or an update
  that indexes more), it builds it first and shows the progress in a new
  ARCHIVE row under System, then starts the game; a current index starts the
  game as before. Panel pages and summon details name things from the index,
  so they no longer show raw IDs before the Archive is opened. Opening the
  Archive during the build shows the same build. Tapping Deploy starts the
  game without waiting. [f249379]
- On iPhone and iPad the game starts with the app, so the index builds in the
  background as the app starts instead, with the same ARCHIVE row in the
  Bunker. When nothing it depends on has changed, the check is skipped without
  loading the Archive's code into the game's memory. [d48ba61]

### Master data
- Import master data accepts the file by its contents, not its name: a
  browser's second download, `20240405123139.bin (1).e`, was refused with a
  message naming only the Global file. The message now names both
  `20240404193219.bin.e` (Global) and `20240405123139.bin.e` (Japanese), and a
  file over 64 MB (the resource dump picked by mistake) is refused without
  being read. [123bfe9]

### Web builder
- The master data line says which file goes with which APK:
  `20240404193219.bin.e` for Global, `20240405123139.bin.e` for Japanese. [76ec585]

## 1.8.1 (2026-11-03)

Linux builds: with Waydroid installed they install the APK and put the game
files into Waydroid for you, with no folder to mount. The Bunker button hides
in the art viewer and the 3D viewer. Early Subjugation Battles are named
instead of "unknown", and with the calendar off each summon banner is listed
once.

## 2026-11-03 (after 1.8.0)

### Subjugations
- The first five Subjugation schedules (October 2021 to February 2022) came
  before named seasons, so the Subjugations screen headed them "unknown On
  Now"; Everything open keeps the first of them open. They are now
  "Subjugation Battles On Now", and the Results dialog names them the same.
  The game's own title text is added for them on Android and iPhone/iPad; no
  game code or data changes. [812b347]

### Summons
- With the calendar off (Everything open), a summon Bunker reran showed its
  banner two or three times in the list: each run it added (506 and 507's
  2023 and 2024 reruns, 124's second chance, the weekly 10094 and 10095
  reruns) is a summon of its own with its own dates, and all were open at
  once. The list shows each banner once, its first summon; the Original
  calendar still runs each rerun on its dates. [3dd64df]

### Bunker button
- The art viewer (the magnifier on a character, weapon or companion) hides
  the game's top row, but the Bunker button stayed on the picture. It now
  shows only while one of the game's own top-row buttons does, so it hides
  and comes back with them. [5c941ca]

### Linux
- Releases include the desktop Bunker for Linux (`Bunker-<version>-linux-x86_64`
  and `-linux-arm64`). With Waydroid installed it uses Waydroid: it starts
  the session, installs `bunker.apk`, and unpacks revision 0 from the `.7z`
  straight into the Bunker's own storage in Waydroid, so no shared folder has
  to be mounted after each Waydroid start. It asks for the sudo password once
  (Waydroid's root shell needs it) and keeps the container awake while it
  works: Waydroid froze it when no app was on screen and the copy stopped.
  Without Waydroid, or with `-emulator`, it uses Google's Android Emulator as
  on Windows. Tested in an arm64 Ubuntu 24.04 VM with Waydroid 1.6.3: first
  start to the title screen in 11.5 minutes, later starts in 15 seconds.
  See docs/LINUX.md. [9244bb4]
- Game files copied in before NieR's first start (the desktop Bunker on
  Windows or Linux) left NieR's files folder owned by root, and the Bunker
  could not make its saves folder ("permission denied"). It is NieR's now.
  [9244bb4]

### Calendar
- Jump to lists what a jump skips in singular and plural without a trailing
  comma ("1 Arena season", not "1 Arena seasons,"). [812b347]

## 1.8.0 (2026-11-03)

Summons give what their banners promised: 24 summons the game data lacked
are back on their original dates, element, character and barrier summons
draw from their own lineups, step-ups have their real steps, and blank
summon panels show their characters. The i button on event and Mama's
Dream summons opens their notice. Notice pack 5 adds 13 summon notices.
Japanese 3.7.1 APKs can be built (experimental), and the companion app is
named Bunker.

## 2026-11-02 (after 1.7.0)

### Notices
- Tables fill the page on wide screens instead of stopping at the column
  widths the notices were written for, and gem and weapon icons keep their
  size in them. [1dcdfd0]
- Pages for summons whose original notice is lost: rebuilt from the game's
  own data and surviving notices, with their artwork, under the summon's own
  title. The tools that build and check them are in scripts/.
  [1dcdfd0, b28ba09]
- Notice pack 4: the 951 original notices and 203 rebuilt summon pages
  (1,154 notices, 2,701 images). Builds now fetch it; it is twice the size
  of pack 3 (135 MB). [de85587]
- Notice images show at their own size, up to the page's width: small title
  logos and banners are no longer stretched across the window. [b74ce18]
- Notice pack 5: 13 summons without a notice (Yuletide Wishes, the 220 free
  summons, the Congratulatory and Resolute Dress summons, the YoRHa Stage
  Play free summon and eight step-ups) have one written from their banner
  art and game data: their title logo, period, promotional panel, featured
  characters and weapons, and each step's cost, guarantee and bonus. Their
  i button opens it. [70d02d2]
- The notice tools' tests run in CI (Pillow and BeautifulSoup in
  scripts/requirements-notices.txt). [b772a20]

### Summons
- The i button on the Event tab's summons (31 event box summons and the
  three Mama's Dream summons) opened an empty page. It now opens the
  summon's notice: the event's own notice, Mama's Dream's announcement, or
  for 14 early events their rebuilt summon page. [3412d48]
- Their Summons Details (from the notice, and the Rates button) list every
  level's prizes with its targets, the player's level and what is left in
  it, and the shared prizes; Mama's Dream lists only its prizes. Neither
  shows the premium summons' rates any more, which they never drew from.
  An event summon's dates are its event's run. [3412d48]
- Summons Details name each event's tickets (Bronze, Silver and Gold
  where an event has three) instead of "Summon Ticket", and Mama's Dream
  summons are named after their announcement. [bf14e2d]
- 75 premium summons (the daily and campaign free 10x summons, the DQX
  crossover's, element and campaign summons) had one appeal image and no
  character cards, and the panel's arrows turned that one page onto itself,
  leaving it empty. Each now shows the characters its appeal art shows
  (matched to the costume art), with their weapons; the Debilitating Bane
  weapon summon shows its three weapons. They are not featured: the odds
  are unchanged. [8b10c49]
- The barrier weapon summons (Vol. 1-3) gave any ★4 weapon of the standard
  pool. Every ★4 weapon each gives now has its volume's rank 4 barrier
  skill (Debilitating Bane, Miasma of Indolence, Curtain of Darkness), as
  the notice says: 80, 79 and 77 weapons. Vol. 2 and 3, missing from the
  game data, are added with their art and the weapons it shows. [2a05d9e]
- 23 summons drew from the standard pool alone though their art or notice
  names a lineup. They now feature or give what it names: the element
  weapon summons their element's ★★★★ weapons; the Sun and the Moon
  countdowns their three characters at double ★★★★ rate, with 10 Skip
  Tickets; the Abyssal, Abyssal Weapon/Prisoner and NieR Lineage summons
  only those characters at ★★★★, at 1.5× rate; the New Year daily free
  summons an Abstract, Bloody or Fractured character at ★★★★, free once a
  day; the Healer & Support summons only their exchange's weapons of their
  elements, a ★★★★ weapon guaranteed, once a day. [c905c84]
- Seven step-up summons had placeholder steps (or one 50x draw): each step
  now has its art's price, ★★★★ guarantee and bonus items, and the summons
  whose art names characters feature them. The ★★★★ rates, featured weapon
  guarantee and free daily draws above also apply to the summons the game
  data lacks (they were left at placeholder prices). [e46060e]
- 24 summons the game data has art for but no summon: Yuletide Wishes,
  Abyssal Assassin, Abstract Ruler, Yuletide Snowfall, two Merry[in]carnation
  festivals, the Congratulatory and Resolute Dress summons, the YoRHa Stage
  Play free summon, Automata Vol. 2 (2023), the 220 free summons, New Year
  Countdown Vol. 2 and 3 (2022), and the Automata, Replicant, SINoALICE,
  Drakengard 3, Blessed Dress, Mechanical Hunter and Weapon, Oathbound Exile
  and Belle, and Lacrima Soldier step-ups. Each has its art's prices, steps,
  bonuses and lineup, on its run's dates from its notice or the event guide;
  none repeats a summon open at the same time. [e22a986]
- Twins and volumes as their notices give them [6f4a16b]:
  - Paid Only: Abyssal Assassin had Abyssal Festival Vol. 3's art; it shows
    its own and Abyssal Festival Vol. 2 and 3 are added (Vol. 1 gives only
    its three characters, as the notice says).
  - The regular Abstract Ruler summon ran the paid-only one's rules, and a
    November Subjugation Conquest summon ran Paid Only: Yuletide Snowfall's;
    each now has its own, and the paid-only ones run separately.
  - The Merry[in]carnation festival's three volumes give only their three
    characters each; New Year Countdown Vol. 1 has its ×1.5 rate and
    featured character and weapons.
  - Six recovered summons had another event's dates; they have their own.
  - The i button on the regular Abstract Ruler, Subjugation Conquest and
    Paid Only Automata Vol. 2 step-up summons opens their own notice. [48d07f9]
  - Summons Details and the Archive's Schedule title summons where the game
    text has another summon's title (the two Abstract Ruler summons are
    swapped, Subjugation Conquest is called Paid Only: Yuletide Snowfall,
    the Replicant and SINoALICE step-ups each carry the next one's), only a
    Japanese title, or none; festival volumes are numbered. [21d5272]

### Sources
- Summon, event box and panel mission data note their sources as an event
  guide, gameplay video, player or social post, without naming sites or
  linking to them. [b91d989]

### Android
- Japanese 3.7.1 APKs (experimental) build alongside Global (English and
  Korean) ones: the builder recognises the client from its files and patches
  each with its own addresses. [a1b9179]
- The standalone companion app is named Bunker instead of Lunar Tear.
  [4a427ba]
- An icon test compares pixels instead of PNG bytes, so it passes with any
  encoder. [dc117a4]

### Web builder
- Notice packs over GitHub Pages' 100 MB file limit (packs 4 and 5 are) are
  published in 64 MiB parts the page joins before building; web builds need
  the notice pack. [b93a10e]
- The page fetches its Python files and bundles fresh each time, so after a
  release a browser can't build with files cached from the last one. [7a6daa3]

## 1.7.0 (2026-11-02)

Below the screen's own resolution, the picture can be upscaled instead of
stretched: MetalFX on iPhone and iPad, FSR 1 or SGSR on Android. 1080p
upscaled looks close to the screen's own resolution for about half the GPU
work. The Display page is grouped into sections.

## 2026-11-02

### Display
- iPhone and iPad: Upscaling › MetalFX. Below the screen's own resolution,
  each frame is upscaled with MetalFX instead of plain stretching. Measured
  on an iPad Pro: rendering at 1080p takes 2.7 ms of GPU time per frame in
  the field against 6.6 ms at the screen's own resolution. Off by default.
  [d98ed39]
- Android: Upscaling › FSR 1 or SGSR (AMD FidelityFX FSR 1, Qualcomm
  Snapdragon Game Super Resolution). Below the screen's own resolution, each
  frame is upscaled with the chosen one instead of being stretched by the
  display hardware. Off by default. Their licences ship in the APK and are
  credited in About. [cbc1b79]
- The Display page is grouped under Frame rate, Resolution, Effects and
  Screen. [2dfa2d5]

## 1.6.4 (2026-11-01)

Above 30 fps the game draws 30 frames a second when idle and slows down when
the device is hot, and shadows, reflections and bloom can be turned off: an
iPad at 120 fps and its own resolution no longer runs hot in menus.

## 2026-11-01 (after 1.6.3)

### Display
- Above 30 fps, after 2 seconds without a touch outside battles, the game
  draws 30 frames a second; a touch brings the chosen rate back at once.
  Measured on an iPad Pro at 120 fps: 30 when idle, 120 while touching.
  Pod Programs › Display › When idle, on by default. [ae51c8c]
- While the device reports it is hot, the game draws 60 frames a second,
  and 30 when very hot, until it cools down. When hot, on by default.
  [ae51c8c]
- Shadows, reflections and bloom can each be turned off, in every graphics
  preset; each costs GPU work every frame. On by default. [0333e8f]
- Shorter notes on the Display page. [7839624]

### iPhone and iPad
- A developer-only GPU frame capture for finding what each frame costs
  (launch setting; players cannot turn it on). [5f66240]

## 1.6.3 (2026-11-01)

After an update, Content presets are applied again with the new version, so
Dark Memories and Recollections of Dusk come back without opening Pod
Programs.

## 2026-11-01

### Pod Programs
- After an update, a Content preset is applied again with the new version
  when the app starts, so preset fixes reach the game without opening Pod
  Programs: with a preset applied before 1.6.2, Dark Memories and
  Recollections of Dusk stayed empty until the preset was applied again.
  Only master data the preset made is rebuilt; imported or restored master
  data is left alone, and the old copy is kept under Previous versions. The
  Bunker menu shows "Updating your game data for this version…" meanwhile
  on iPhone and iPad. [71cfe73]

## 1.6.2 (2026-11-01)

Content presets keep Dark Memories, Recollections of Dusk and the other
permanent quests. With "Show original dates", the character lists are filled
again, and story chapters open on their release dates. Calendar fixes reach
the game when the updated app starts.

## 2026-11-01

### Pod Programs
- Content presets (Full, Story, Gacha and the rest) no longer hide Dark
  Memories, Recollections of Dusk, the cage, Abyss Towers or the Labyrinth:
  after applying any preset their menus were empty. Presets choose limited
  events only. Apply the preset again to bring them back. [bef8716]

### Calendar
- With "Show original dates" on, Enhance › Characters and the other
  character lists were empty: the game data lists the starting cast only
  from 2022. Characters are listed from launch, and so are filters,
  Character Viewer backgrounds and the like, as without the setting. The
  copy for original dates is rebuilt when the updated app starts.
  [427944d, 3c35230, 52866ff]
- Story chapters open on their release dates in the first loop, as in the
  live game, with or without "Show original dates"; from the second loop
  all are open. Chapters a player has already reached stay open. The loop's
  game data is rebuilt once when the updated app starts. [2c41097]
- After an update, the calendar's game data is brought up to the new
  version when the app starts, before the game connects; before, that
  waited until Pod Programs opened, so calendar fixes did not reach the
  game. The Bunker menu shows "Updating the calendar for this version…"
  meanwhile on iPhone and iPad. [99053f2, 2d2be46]

## 1.6.1 (2026-11-01)

With the Original calendar, Notices come out as the loop reaches them. The
Bunker emblem replaces the notification, shortcut and quick action icons.

## 2026-11-01

### Server
- With the Original calendar, Notices come out as the loop reaches their
  dates instead of all at once, and show the same dates as the rest of the
  game (this loop's, or the original ones with "Show original dates").
  [dbb4a0b]

### Android, iOS
- The Bunker emblem replaces Bunker's other marks: the notification icon
  (the crescent moon), the "Bunker menu" shortcut on the app icon, the iOS
  home-screen quick action and the web builder's tab icon. The notification
  reads "Bunker · Running". [5c4fb22]

## 1.6.0 (2026-11-01)

A **Bunker** button in the game's own top row opens the launcher. The Schedule
page shows a timeline of summons, events, shops and Arena seasons with their
banner art, and the Original calendar can show the dates the live service
had (2021–2024).

## 2026-11-01

### Calendar
- A **Timeline** on Content › Schedule replaces the "Open now" list: summons,
  events, time-limited shops and Arena seasons as bars across the weeks, from
  a week back to three months ahead, with a TODAY line. Each bar shows the
  game's banner art (summons and events), the full name, its dates and how
  long is left or until it opens; an "Ending in 7 days" strip sits on top.
  Zoom 2 weeks / 6 weeks / 3 months; rows can be hidden and stay hidden.
  Dates are in the phone's time zone and follow "Show original dates", as
  the game does. Content the game never closes shows as open, not until
  2099. [3e4ea8b, 24025d9, e567c94, df94298, 3ac9c7a, 8573cfb]
- Abyss Towers and other rerun events are listed on their runs in this loop:
  they showed as open since 2023 (the original service's dates). [b8d32e4]
- **Show original dates (2021–2024)** under Content › Schedule: with the
  Original calendar on, the game shows the dates the live service had, so
  summons, events, exchanges, missions and Arena seasons read 2021 onwards
  instead of this loop's dates. It can be switched on and off at any time
  (then Deploy); the save is not changed, only what the game is shown. The
  game data copy for it is built the first time it is switched on.
  [dc41292, c956ea5, 0726b71, dee6a13, c8769cb, cf46134, 8cbc080]

### Android, iOS
- A **Bunker** button, first in the game's top row (before Notices), opens
  the Bunker launcher from any menu screen: Archive, Pod Programs and the
  rest are a tap away. It is drawn like the game's own buttons, with the
  Bunker's floor emblem as its icon, and locks with the row while the game
  is busy. When the row would run into the counters (Summons shows Help and
  Mission Pass too), its buttons move closer together. [61f0483, 9302494,
  d45b237, 996303d]
- When "Show original dates" changes, the game's own day markers (kept on
  the phone, outside the save) are cleared before it starts. They hold the
  last day the game showed something once a day, and after the clock moved
  by years they hid the roulette's **FREE** badge, Mama's News and the other
  once-a-day reminders. The game shows them again the next time it starts.
  [cc0539a]
- Tapping a summon or an event on the Schedule timeline opens it in the
  Archive; closing the Archive returns to Pod Programs. An entry the Archive
  doesn't list opens its Schedule tab. [14592a2, e102f50]

## 1.5.0 (2026-11-01)

The update notice can be put off with **Later** or **Skip**, and a long press
on the app icon opens the Bunker menu. Players who filled weapon storage early
can finish the chapter 2 loadout tutorial again. The Dark Memory summon opens
after the first Hard chapter and its **To Quests** works. Memoirs open their
full menu on a long press, and several summon, mission and calendar links go
where they should.

## 2026-11-01

### Server
- A long press on a memoir opens its full menu (**Enhance**, **Show Story**)
  instead of a small preview. The game shows the menu only for a memoir with
  a secondary stat, and rank-1 memoirs had none: every memoir now has at
  least one, and memoirs without one get it when the game starts. [4200f58]
- A player stuck at the chapter 2 loadout tutorial whose Rion weapon gift
  has expired gets the weapon again when the game starts. [4200f58]
- The starter costume and weapons of the first story scene are no longer
  given again when the game reports that scene a second time. [6723c55]
- **To Event** on a Mama's Dream summon opens the daily quest that gives its
  tickets, instead of the first event tab. [f33e818]
- With the Original calendar, event summons are listed only while one of
  their event's runs is on, and **To Event** opens the run that is on (during
  a rerun it opened the first event tab). [f33e818]
- Six missions that unlock with the first page of an Anecdote no longer
  count before that page is complete. [d4dc1ad]
- With the Original calendar, the weekly reruns of May 2023 (10107, 10108)
  no longer show an **Exchange** for medals whose exchange is closed then.
  [63c5f17]

### Calendar
- Two home banners whose summons Bunker doesn't list at that time stay
  hidden, instead of opening the Summons screen on another summon. [eadd1cc]

## 2026-10-31 (after 1.4.4)

### Launcher (Android, iPhone and iPad)
- The update notice is two rows instead of four, and has **Later** (hide it
  until the app next starts) and **Skip** (hide that version until a newer
  one). ⋮ → **Check for updates now** checks straight away and shows a
  skipped version again. [9e383d4]
- Long-pressing the app icon offers **Open the Bunker menu** (**Bunker menu**
  on iOS), which opens the launcher without starting the game. [df27920]

### Server
- Story weapons are no longer sent to the Gift Box when weapon storage is
  full. A player who had filled it with early summons got Rion's weapon
  (quest 2) as a gift, and **Select** in the chapter 2 loadout tutorial
  did nothing. First-clear weapons and parts now always go to the
  inventory, and a story weapon already sent to the Gift Box this way is
  moved back to the inventory when the game starts. [ff95fea]
- A player already stuck there can finish the tutorial: when the game
  starts, Rion's weapon is also put back in Rion's empty main weapon slot in
  the first loadout, which the tutorial had set up while the weapon was in
  the Gift Box. [4577dc2]
- **To Quests** on the Dark Memory chapter summon opens EX Character Quests
  instead of stopping on an empty Quests screen. [229aabf]
- The Dark Memory chapter summon appears once Dark Memories are unlocked,
  after the first Hard chapter, as in the original game. Since 1.4.4 it
  appeared at the end of Season 1, which unlocks Recollections of Dusk
  instead. [756e716]

## 1.4.4 (2026-10-31)

Flying Mama plays at its normal speed above 30 fps, and the Dark Memory
chapter summon no longer leaves the game stuck before Dark Memories open.

## 2026-10-31 (after 1.4.3)

### Display (Android, iPhone and iPad)
- Flying Mama plays at its normal speed with a frame rate above 30 chosen in
  Display. The minigame counts frames, so at 60 fps the stage scrolled and
  Mama fell twice as fast against the same clock; its logic now runs 30 times
  a second, and taps still count on every frame. [7869f1e]

### Summons
- The Dark Memory chapter summon appears once Dark Memories open (clearing
  the last quest of Season 1, Chapter 14). Before that, its To Quests opened
  an empty screen that the game could not leave. [c0554ce]

### Tools
- The Android tools tests run as a folder again: the two scripts that need
  private game files are skipped there. [13d48c5]

## 1.4.3 (2026-10-30)

On iPhone and iPad the game no longer crashes now and then as it opens.

## 2026-10-30 (after 1.4.2)

### iPhone and iPad
- The game no longer crashes now and then as it opens, most often with a
  frame rate chosen in Display: the display settings wait until the game's
  engine has started. [f61537a]

## 1.4.2 (2026-10-30)

On iPhone and iPad the game starts about 8 seconds sooner, and iOS no
longer ends it while it loads.

## 2026-10-30 (after 1.4.1)

### iPhone and iPad
- The game starts about 8 seconds sooner. The launcher no longer waits for
  the server before the game starts (the server could not start until that
  wait ran out), so iOS no longer ends a slow launch. [fe40c38]

## 1.4.1 (2026-10-29)

Bunker reads better on iPads and in landscape: Pod Programs shows every
tab and full names, notices keep a readable column, and the Archive's
stories fill the screen. The guides show their pictures (notice pack 3).

## 2026-10-29 (after 1.4.0)

### Display
- On tablets and in landscape, every Pod Programs tab shows (on two rows
  when they don't fit), and long costume, weapon and upgrade names wrap
  instead of being cut off. [03e995b]
- Notices and summon details keep their text in a readable column on wide
  screens. [03e995b]
- In the Archive, weapon stories, records, companion and costume texts
  reflow to the screen instead of keeping the game's narrow line breaks;
  lists, reports and the like keep their own breaks. [a8c9870]

### Anecdotes
- The sub-quest guides and the Anecdotes' How to Play pages show their
  pictures, from notice pack 3. [f2b976b] [9af79be]
- The completed sheet's story marks every panel's word, also where the
  story uses a longer form of it ("nightmares", "wished"). [b0a3a65]

## 1.4.0 (2026-10-29)

The Anecdotes are playable again on the game's own panel mission page, the
Library lists their stories, and notice pack 2 brings more of the official
notices back. With the Original calendar, the Abyss Towers and the Anecdotes
rerun on their own schedules, and many summons run as long as their notices
say.

## 2026-10-29

### Calendar
- With the Original calendar, the Abyss Towers rerun on their own schedule:
  each tower opens for each of its runs (both Fivefold Unveilings included)
  and closes between them, with the floors that run had (20, then 30, 40
  and 50), and stays open for good from March 2023 as notice 1037 says.
  Before, a tower opened at its first run with all its floors and never
  closed. A tower's accumulation rewards are still claimed once. [ba0ccbe]
- With the Original calendar, every Anecdote run plays, not only the
  first (15 runs in all). [095eac0]
- Record: Seat of Shadow (Resurrected) ends on 2 December 2023 as its
  notices say, a day earlier than before. [9c8b65c]

### Anecdotes
- The Anecdotes are playable. Each of the eight has its two sheets of
  panels again (from guides and gameplay videos; 26 panels whose exact
  condition isn't recorded count the nearest thing). A run's panels count
  what the player does while it is open, a reached panel's reward goes to
  the gift box, and a finished sheet pays its own reward and unlocks its
  story in the Library. [c55ecc4] [cadd148]
- The sheets are the game's own page, restored from a preserved copy of the
  official web app in the notice pack: the panels over the hidden picture,
  each received panel opening onto its piece and word, and a finished sheet
  assembling its card beside its story. The words of every sheet come from
  gameplay videos. Mama's banners open the run that is on. [a32d3d7]
- Three panels paid an item that doesn't exist instead of a Premium Summon
  Ticket, a Skip Ticket or a Small Stamina Recovery. [a32d3d7]
- With the Original calendar, Library › Card Stories lists each Anecdote
  once, as the live game did. Before, it was listed once per run (Doll three
  times). [438f7a1]
- When a sub-quest type unlocks, its guide opens on the official page
  (Dark Memory and Recollections of Dusk; the other guides weren't
  preserved). Before, the page was blank. [dcaa007]

### Notices
- Notice pack 2: four notices that were missing, the later versions of
  "Known issues" (#4) and three more, no garbled characters, and 274 more
  images: banners and pictures from the Wayback Machine and gameplay videos
  (where a banner is lost, the official X account's poster for the notice),
  item icons rebuilt from the game's own art (and the event medal and
  ticket coins), and 22 thumbnails. It also carries the official web app
  the Anecdotes run on. [28608b6]
- Updates from 1.3.x get the new notices without the web app, which their
  launchers can't take; 1.4 and later updates take the whole pack.
  [e240558]

### Summons
- The Paid Only Unacquired ★★★★ Witch and Assassin summons now give a
  Witch (Saryu) or an Assassin (Akeha) the player lacks, any of them if the
  player has them all, and their details list them. Before, they could give
  any ★4 character. [9874b88]
- The Healer & Support ★★★★ Guaranteed summons have their lineup: their
  panels show its characters, their ★4s come from it, and their details
  list it, taken from the Healer & Support Summon Medal Exchange. Before,
  the panel had only the banner art. [9874b88]
- With the Original calendar, 29 summons run as long as their notices say.
  The game data dated them by their 3-day home banner, so they closed early,
  such as the Unacquired ★★★★ Assassin summon after 3 of its 13 days and
  the RoD Resonant Character summons. [05974bd]
- The Re[in]carnation Appreciation Gala's free summons (July to September
  2023) are back: seven free summons of 40 draws each, one a week, each
  giving ★4 characters of one costume series. The game data lacked them.
  [db8c595]
- The Story Completion festivals (February to April 2024) have all three
  volumes each, as their notices say; the game data had only the first.
  Each volume's ★4 characters are its own lineup (limited-time characters,
  or the series its art names), with the notices' 10% ★4 rate, as the
  Black Friday Karma Festival now has too. [5a3fe20]
- Guarantees that name a group of characters now give one of them: the
  RoD Resonant Character, Abyssal, Celebratory and Yuletide summons, the
  Season 1 summon (whose characters are now all it gives) and the
  limited-time character summons. Before, the guaranteed slot gave any ★4.
  The limited-time sets are a best guess, as no notice lists them.
  [c4cd7c6]

### Tests
- The real-save tests pass on any save and game data: the arena season
  and play history checks follow the save's own dates. [a2b6660]

## 2026-10-28

### Calendar
- With the Original calendar, a rerun event's medal exchange now opens with
  the event. The game data keeps only an event's last run, so events that
  reopen from an earlier run (26 of them, such as "Record: The Cage of
  Reincarnation" from July 2021) dropped medals for months before their
  exchange and the medal itself opened. The exchange, its offers and the
  medal now open when the event first does and stay until its last run
  ends. Reported in GitHub issue #5. [bcd55ab]
- With the Original calendar, the medals and tickets an event gives are
  valid while it runs. Like the exchanges, they kept the dates of the
  event's last run: silver and gold medals of events reopened from an
  earlier run were not valid yet, story events' summon tickets were valid
  in another year than the event, and three 2021 events dropped medals
  never valid. Every item an event gives is now valid from its first run
  to its last (100 medals and tickets). [3f0934d]
- With the Original calendar, a story event's summon stays open for every
  run of the event. Its 2023 reruns had no summon to spend their tickets
  in (chapters 300 and 301). [9b7624b]
- The Original calendar no longer replays 25 placeholder dates as runs:
  dates content carried in the game data before it was used, such as
  chapter 513's medal dated August 2021 for a November event, one-day
  quests and home-screen pop-ups that were parked on their own days, and
  a few tips and missions. A date range now counts only if the game data
  published during it had the content live. [db9374f]

## 1.3.5 (2026-10-27)

Chapter 4's "A Tool of the Master" can be finished on very wide Android
screens, the guerrilla quests' unlock follows the game's rules, iOS updates
bring the game fixes, and new builds start with all content open and no ads.

## 2026-10-26

### Game client
- Guerrilla quests: the "Use 100 gems" unlock now takes the 100 gems.
  The first unlock each day stays free and comes back at the daily reset.
  Before, every unlock was free and the day's count never reset. With
  fewer than 100 gems the game's Unlock button does nothing; that is the
  game's own check. [087b373]
- With the Original calendar, the guerrilla quests' Force Unlock button
  appears when the unlock did in the live service, about six weeks into
  each loop. Before, the game showed it from the start, offering an unlock
  "for 0m" that opened nothing; it is now hidden until then, on Android
  and iOS, and the server takes no gems for it either. [1319534, ccda6e3]
- Android, story rooms: on screens wider than 19.5:9 (2.4:1 phones with
  "Full screen, around the camera") the camera now goes all the way to the
  room's edge, where the invisible walls are. Before, it stopped short, the
  wall stopped the player the same distance short, and a story trigger near
  the edge could not be reached (chapter 4, "A Tool of the Master"). iOS
  screens are not that wide. [b0b1121]

### Game data
- New builds (APK, IPA and the web page) start with the game data Pod
  Programs makes when nothing is picked: content stays open until 31
  December 2099, which the server treats as never ending, and the menu's
  ad banners, the home screen's news cut-ins and the login popup are hidden.
  Before, a fresh install was open only to 2030 and showed the ads until
  Pod Programs patched it. Installed apps keep their current game data.
  [0b195b6]

### Web builder
- The Android build needs much less memory: about 1.2 GB in Chrome instead
  of 2 GB. The game library is patched where it lies, and the APK is signed
  as it is written and passed to the page in pieces. The APK is the same as
  before. [4205647]

### iOS
- In-app updates now bring Bunker's game fixes to an installed app: the
  999-day campaign badges, the guerrilla Force Unlock button, and the
  summon list and long-text fixes for installs older than those. Before,
  an update kept the game binary as it was, so those fixes needed a new
  build. Because each update runs the installed app's updater, an app gets
  this from its second update after this release. [707a6bf]
- New: `ios/tools/sign_ipa.py` signs an IPA that is already built, such as
  the web builder's, with your certificate and profile. It changes only the
  bundle ID and keeps the builder's settings. docs/IOS.md now says to keep
  one bundle ID for every install, the game's own `com.square-enix.NieRSPww`
  where your profile allows it: saves stay with the bundle ID. [814b222]

### Development
- The unit tests now run on every push to main, not only at release, plus
  the iOS packaging tests on macOS and a check that the web builder still
  goes through lunar-scripts' IPA patcher as it expects. [9588b6e]

## 1.3.1 (2026-10-25)

The web page can now build for iPhone/iPad with much less memory, and on
Android more of the game's tracking stays off.

## 2026-10-25

### Privacy
- On Android, more of the game's tracking stays off: Unity Analytics,
  Crashlytics, Facebook events, Adjust and ironSource no longer start, and
  the advertising-ID permission and Adjust's install tracker are removed
  from the app. New builds get this at once; an existing install gets it
  from its second in-app update after this one, because each update runs
  the tools already installed. See docs/PRIVACY.md. Contributed by
  nathangerday (PR #3). [962eb57, 6ba7d42]

### Web builder
- The iPhone/iPad build needs much less memory: about 1.1 GB in Chrome
  instead of 2.7 GB. It no longer unpacks the whole game; only the files
  the patches change are taken out, and the IPA is passed to the page in
  pieces as it is written. Before, iPhone and iPad browsers closed the tab
  mid-build and the page reloaded. The IPA has the same files as before.
  [dbaec6a]

## 1.3.0 (2026-10-25)

Bunker now runs on Windows, with keyboard controls. The music comes back
after you leave the game, and campaign badges no longer show a jumbled
number.

## 2026-10-25

### Windows
- New: `Bunker-<version>.exe` plays the Android build on a Windows PC, in
  Google's Android Emulator. The first time, it downloads the emulator
  from Google, sets up a phone, installs your APK and copies the game
  files in from the `.7z`. Each step shows on screen, and it asks for any
  file it can't find. See docs/WINDOWS.md. [550840e]
- Keyboard controls: WASD or the arrow keys move, and Ctrl+B opens the
  Bunker. [7cb3539]
- Release notes end with a Downloads list that says what `Bunker.exe`
  is for and which files you don't need. The Windows guide now says
  gameplay was tested: the field with the keyboard, and the music after a
  pause. [0934243]

### Web builder
- After an Android build, a separate paragraph explains how to play the
  APK on Windows with `Bunker.exe`. It's hidden for iPhone/iPad builds.
  [0764eb1]

### Game client
- Music no longer stops for good after you leave the game. Before, after
  opening the Bunker, the home screen or another app, the game stayed
  silent until it was restarted. Now the music comes back about a second
  after you return. [03f176e]
- Campaign badges (such as half stamina on EX Character Quests) no longer
  show a jumbled number: campaigns left open end in 2099, 26,000 days away,
  too long for the badge. Remaining times now stop at "999d", on Android
  and iOS. [d7b1ed6]

### Docs
- The README, guides, changelog and on-screen messages use shorter,
  plainer sentences. Facts, commands and button names are unchanged.
  [c6639f3]

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
  Prize Replenishment. The main prizes come from an event guide where it
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
  in-game screenshots and social posts. [af52e6e, b15c461]
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
