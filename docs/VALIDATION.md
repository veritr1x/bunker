# Validation — 2026-09-20

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
