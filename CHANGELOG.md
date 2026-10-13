# Changelog

What changed in Bunker, newest first. Each day lists its changes by area.
Commit ids are in brackets.

## 2026-10-13

### Pod Programs: Original calendar
Content › Schedule can replay the live service from global launch (28 July
2021) instead of keeping everything open. Not yet released; on branch
calendar.
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
- **Server:** an Arena season's final rank reward is paid after it ends.
  Event items leave the inventory when their term ends. A new loop resets
  event quests, event missions, exchange shop purchases, the mission pass,
  login bonuses, Labyrinth seasons, Big Hunt records and limited summon
  progress. Big Hunt picks its schedule by the game clock.

### Story events
- Chapter 6-4 (Levania's memory): the player could walk past Mama's lines and
  fall off the right edge of the map. The game misses a player who walks
  through an event's zone while a speech balloon fades out; that zone now
  still counts. Applies on Android and iOS at every frame rate, the game's own
  30 fps included. Chapter 6-7's tree still falls across the chasm. [4b4f8f8,
  2e71e34]

### Server: behaving like the original game
Checked against the game's master data and the 3.7.1 client. [9e760e4]
- **Gifts:** claiming a gift now grants it; login bonus rewards were lost
  before. Expired gifts are dropped and reported. A gift over its storage
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
  - Event, extra and Big Hunt first clears no longer lose their rewards after a
    story replay.
  - A lost or retired quest is marked "challenged", which unlocks quests that
    need it.
  - Quest bonus drops and key-item drop effects apply.
  - Recollections of Dusk locks the costumes and weapons used in a run.
  - Hidden stories and Lost Archives wait for the quests that unlock them.
  - Skips are refused without enough tickets or stamina.
- **Big Hunt:** pays only the highest score tier reached. Damage counts across
  all waves, and a crashed run no longer carries into the next.
- **Missions:** bosses defeated, Big Hunt knockdowns, reports, Arena play, wins,
  streaks and rank, library, ability level, exploration score and concert taps
  now count. 6,284 of 6,436 missions have rules.
- **Friends:** the Arena's computer players can be added as friends and sent
  support, so "Send a friend support" and "complete all dailies" can clear.
- **Profile:** shows the last deck used and its real total force.
- **Other:** exploring keeps natural stamina recovery. Visiting a cage ornament
  no longer marks its reward received.
- **Reliability:** an error in one request no longer stops the server. Database
  settings apply to every connection, and saves can't overwrite each other.

### Server: more of the original game
- **Daily reset:** days now start at 00:00 GMT-8, all year, as the game's own
  "Resets at 00:00 (PST)" says. Weeks start Monday 00:00 GMT-8. Saves made
  before move across without losing the week's Big Hunt and Arena results, and
  without a second daily reward on the day of the switch.
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
  null; every table is now sent as a list. [a9358bd]

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
- Battles step in whole 30 Hz steps above 30 fps, fixing a crash in the summon
  reveal. [ecf7393]

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
