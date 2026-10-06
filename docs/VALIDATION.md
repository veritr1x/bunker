# Validation

## The Archive — 2026-10-05

- Phase 0 on the real Android dump: revision 0 holds 6,633 English text
  bundles, 270 MP4 movies in `resources/`, ASTC textures (stills, art,
  icons), Vorbis-in-FSB5 audio clips (24k English voice lines, 524 music
  tracks) and Unity 2019.4 meshes and animations. Octo's header mask covers
  the first 256 bytes including the version byte; lunar-scripts'
  `decrypt_assetbundle.py` masks one byte too many by default, which breaks
  bundles whose data starts inside the header. Text bundles were unaffected.
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
  CRC32; the dump uses three, regenerated once with libvorbis 1.3.7 and
  checked against those CRCs (`vorbis_setups.go`). Go tests rebuild six real
  clips (music, story and character voices) and match python-fsb5's output
  packet for packet with the same granule positions; ffmpeg decodes the
  files without errors at the right length. 21,396 of 23,638 story lines
  have an English voice. On the emulator "Play scene" read a scene line by
  line (Android reported the app playing 44.1 kHz mono and moved to the next
  line), a soundtrack part played in stereo with loop and seek, and a
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
  the idle and run motions. On the emulator the first build drew it white:
  three.js fetches embedded textures from blob: URLs and the page policy
  blocked fetch(); reproduced on the PC with the same policy, fixed with
  connect-src blob: (now set by the Archive itself and covered by a test).
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
  7,909 main-story scene lines are named: those the maps name, and lines with
  the same voice code in the same scene, or in the season when that code is
  at least 90% one actor. Narration, title cards and the unnamed girl stay
  unlabelled, as do event, character and side scenes, which the game narrates
  without speakers (one voice code per scene). The maps are named by quest
  map number (season, route, chapter order), which regroups the main story
  into the game's chapters with their own names: both Season 2 routes, the
  intermissions and Season 1's Interval Prologue; the two Season 2 endings,
  played by both routes' finales, sit in the first route's. The other
  stories are named the same way: the event maps in `character`,
  `endcontents`, `limitcontents`, `marathon` and `side` name the text files
  they read, and their quest map numbers lead through the event quests to
  the Character Quest's character (shared by that character's Dark Memories
  and Recollections of Dusk), the Record event's title, or the side story's
  character. All 112 story groups are named; the battle prompts every side
  map shares are "Other scenes". Not checked on iOS or a physical phone.

## Signed web APKs and the download fix — 2026-10-04

- `android/tools/test_apk_sign.py` passed: an APK signed by `apk_sign.py`
  (APK Signature Scheme v2, public key in `web/signing`) verifies with
  `apksigner`, and a signed APK is refused a second signature.
- Download failure found and fixed: the page's `<main>` and the BUILD button
  both had `id="build"`, so the build handler was attached to the whole page
  section. Clicking the download link revoked the finished APK's link and
  started another build; Chrome reported the download as a network failure.
  The section is now `id="terminal"` and the page has no duplicate ids.
- The site was assembled as CI does and run in Chrome with real clicks: BUILD
  enabled once both files were chosen, the build ran once, and the download
  link saved `bunker.apk` (304,320,690 bytes) without starting another build.
  It verifies with `apksigner` (v2, Bunker public key).
- On the emulator, the downloaded APK was refused over a copy signed with a
  different key (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`), as documented. After
  uninstalling, it installed and opened the Bunker. A separately assembled APK
  signed with the same public key then installed over it as an update
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
  builds without `LunarPortOffset` reset a test offset to 0; the offset is now
  set only when the build has one. Export on iOS uses the same Go code as
  Android and is covered by the Go tests; the share sheet itself was not
  exercised on a device.

## Server checks, port conflicts and port offset — 2026-10-04

- Another device showed a black screen after the logo. Reproduced on an
  Android 17 emulator by holding port 8080 with another process: the old build
  showed the raw "address already in use" error with the server card still
  "Ready", and the game opened directly sat on a black screen. Now the server
  checks itself after starting (game, assets and accounts ports, and that this
  server answers), the launcher names the busy port and shows "Not running",
  and a game opened directly goes to the launcher instead. Same results on the
  Fold. Go tests cover the check, including another program on a port.
- Port offset (scripts/build.py --port-offset, and the web builder's
  experimental option): with port 8080 held, an offset build first still failed
  ("Failed to connect"). Unity extracts the game's code data to
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

- Report: on a OnePlus 13, entering the game sat at 20% for minutes unless
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
  were left intact. The first builds' progress bar showed 100% early:
  the time-left estimate was built from a partial total read while the archive was still being listed (12.7 of
  20.9 GB on a Mac). Totals are now published once the listing is complete.

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

These checks were performed before the sources were reorganized into this
repository; the newly packaged APK has not had another full emulator playthrough.

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

- Physical Samsung Fold behavior, folding/resizing, sustained performance,
  battery use and Samsung background-process management.
- Full campaign and battle coverage.
- Full-size import through a physical phone's document picker. The 20.9 GB
  emulator test used development access to seed files into app storage; normal
  app operation does not require root.
- Physical-phone Tools document import/export. Internal game-save snapshots can
  be restored, but importing the separately exported save ZIP is not implemented.

Private game files, saved games, screenshots and runtime logs remain outside Git.
