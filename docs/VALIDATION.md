# Validation

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
