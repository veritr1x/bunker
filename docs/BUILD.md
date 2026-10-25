# Build once, then play on the phone

## 1. Get your files

You need your own **original Android ARM64 game APK, version 3.7.1**, the original
`20240404193219.bin.e` master-data file, and an extracted Android resource dump.
The guarded binary patch supports the tested 3.7.1 ARM64 APK. It may reject
other binaries. The scripts read your original files and change only copies.

## 2. Install the build tools

Use macOS or Linux with:

- Git, Make, Go 1.25.8 or newer, `protoc`, and `apktool`.
- Python 3.11.9 or newer, available as `python3.11`. Run the build with it. An
  older `python3` (such as macOS's 3.9) cannot run it.
- JDK 21, with `JAVA_HOME` pointing to it. The Android build fails with newer JDKs.
  Android Studio's bundled JDK works:
  `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`.
- Android SDK platform 36, build-tools 36.0.0, and NDK 27.2.12479018.

Install the SDK components with Android Studio's SDK Manager. If `ANDROID_HOME` is not
set, the build looks for the SDK at `~/Library/Android/sdk` on macOS or `~/Android/Sdk` on
Linux. The computer needs Internet access to download build dependencies.
On macOS with Homebrew: `brew install go protobuf apktool python@3.11`.

For the iPhone build, see [iOS](IOS.md): it needs a Mac with Xcode and
Python 3.13 instead of the Android tools.

## 3. Clone and build

```sh
git clone --recurse-submodules https://github.com/veritr1x/bunker.git
cd bunker
python3.11 scripts/build.py \
  --apk /path/to/original-game.apk \
  --master /path/to/20240404193219.bin.e
```

If you already cloned without submodules, run:

```sh
git submodule update --init --recursive
```

The build prepares the pinned sources, installs build-only Python packages in a
local virtual environment, generates protobuf code, runs Go tests and Android
lint, and signs the combined APK.

Your APK is **`artifacts/bunker.apk`**. Its checksum is in
`artifacts/SHA256SUMS`. Keep **`inputs/lunar-local.keystore`**: later APKs need the
same key to update the installed app without deleting its data. To reuse a key:

```sh
python3.11 scripts/build.py --apk /path/to/game.apk --master /path/to/master.bin.e \
  --keystore /path/to/lunar-local.keystore
```

Use this project's key format (alias `lunar-local`, local-build password
`android`). Keep the file private. Git ignores keys and game files.

The game's Notices screen shows the official notices, recovered from archives.
They come from a notice pack that is not in this repository. Fetch the pinned
pack before building, or the build has no notices:

```sh
python3.11 scripts/notices.py
```

It downloads the file named in `notices.lock.json` to `inputs/bunker-notices.zip`.
`build.py` uses that file. To use another path, pass `--notices`.

## 4. Prepare the phone's game files

Copy `resource_dump_android.7z` to the phone and choose it in the launcher
(**Choose → Archive (.7z or .zip)**). Only revision 0 is used, because the
server always serves it. The dump's 817 other revisions are 28 GB of old catalogs.
The app unpacks only revision 0. It decompresses only the parts of the archive
that hold it. A `.zip` of the dump works too.

Or extract `revisions/0` yourself, on the computer
(`7zz x resource_dump_android.7z 'revisions/0/*' -oandroid-dump`) or on the
phone (for example ZArchiver), and choose the folder (**Choose → Extracted
folder: copy into the app**). The app copies only revision 0, so a full extraction works too.

**Extracted folder: use in place** (Android 11+) reads the folder from where it
is instead of copying it. This saves 21 GB. It needs **All files access**. The
app asks you once to turn it on in Settings. The app only links to the folder;
it does not own it. If you choose other files later, the app removes only the
link. If the folder is moved or deleted, the launcher tells you. Choose it again.

The import refuses a dump if its revision 0 points to files in other revisions.
The tested dump does not do this. `scripts/prepare_assets.py --source <extracted folder>`
is optional. It writes a ready `phone-assets/assets` folder with only revision 0
and checks it. This folder is smaller to copy. Its output is about 20.9 GB.
Allow at least 50 GB free on the phone during import. The game's cache may need
more. The APK already includes patched master data.

## 5. Install and play

1. Install `bunker.apk` on an ARM64 Android 9+ phone.
2. Open it. Under **1 Game files**, tap **Choose** and select the `.7z` or the copied folder.
3. Wait for the import. It first counts the files, then shows a progress bar with
   the time left. Lunar Tear starts and the game opens. Tap **Deploy** to retry.

Later launches start the server and the game automatically. When the game asks
to download files, it loads them from this phone, even in airplane mode.

The APK is signed with a different key than the publisher's APK. Before you
remove a conflicting installation, back up its saves. A later build signed with
the same local key can update this app normally.

Tap the Lunar Tear notification to return to the Bunker (the launcher). **Open Pod Programs** opens:

- Content presets, custom configuration, master import/export and rollback.
- Player inventory, gems/materials, costumes, weapons, companions and upgrades.
- Karma, slabs, debris, memoir sets and stats.
- Automatic game-save snapshots, manual backups and restoration.
- **Users**: the player marked IN USE is the one the game signs in as on this
  device. **Use this player** switches to another player in the save, and
  **New player** starts a fresh one; the previous player is always kept, and
  the save is backed up first.

Pod Programs stops the game while you edit. The first time it opens, it prepares
names from your imported resources. Close Pod Programs and tap Deploy to resume with the changed data.

Use **⋮ → Display** to choose light, dark or the phone's setting (the default) for
the Bunker and Pod Programs.

Each time the server starts, the launcher checks that the game can reach it on
its three local ports (8003, 8080 and 3000). It also checks that the server
answering is this app's own. If another app already uses one of the ports, the
launcher does not start the server. It shows which port is taken instead. **⋮ → Check server** runs the same check while the
server is running. If you cannot free the port, build with an offset. The
offset moves all three ports. This is experimental; use the same offset for every update:

```sh
python3.11 scripts/build.py --apk /path/to/game.apk --master /path/to/master.bin.e \
  --keystore /path/to/lunar-local.keystore --port-offset 30000
```

The server log is also kept between sessions in
`Android/data/<package>/files/logs/server.log`. At 5 MB, it is moved to
`server.log.1`. Read it with `adb pull` (no root needed), or use **⋮ → Export server
log**. It saves a ZIP with the log, the phone's model and the Android version.

Use **⋮ → Stop server** when finished. If Samsung pauses the server, set the
app's battery usage to **Unrestricted**.

VPN, proxy and "network accelerator" apps no longer slow the game down. Android
sends even requests to `127.0.0.1` through the phone's proxy. The proxy cannot
reach the game's server on the phone. So loading used to stall for minutes, and
it worked only in airplane mode. The app now sends the game's requests to its
own server directly. Everything else still uses the phone's proxy.

## Keep your saves

Stop the server and use **⋮ → Export save backup** before uninstalling or clearing
app storage. It exports `game.db`, `auth.db`, and `auth.key` in a ZIP.

To restore, stop the server and use **⋮ → Import save backup**. It accepts such
a ZIP from Android or iOS, or a bare `game.db`. It checks the file before it
replaces anything, and it keeps the current save as a safety copy. A save from
another device takes over this device's player. On a new device, open the game
once first, so it has a player to take over.

Tools keeps the latest 50 game-database snapshots and can restore them on the
phone. Those snapshots stay inside the app. Uninstalling the app deletes them.
Master-data changes have a separate history of the latest 10 versions.

## Source layout and checks

- `upstream/`: pinned, unmodified submodules.
- `android/`: launcher, service, JNI build/packaging helpers and Python adapters.
- `ios/`: in-game launcher framework, IPA packaging, simulator check and device helpers. See [iOS](IOS.md).
- `web/`: the in-browser builder. `web/build_site.py` assembles it; `.github/workflows/pages.yml` builds
  its bundles from this repository and publishes it on GitHub Pages.
- `android/tools/assemble_apk.py`: builds the APK by editing the original's files directly (with
  `axml.py` for the manifest), with no apktool or Android SDK. The web builder runs it in the browser.
- `overlays/`, `patches/`: mobile adaptations applied to upstream sources. Both platforms share the embedded server.
- `server/` and the third-party Python packages: generated, ignored build inputs.
- `notices.lock.json`, `scripts/notices.py`: the pinned notice pack. Android builds carry it under
  `assets/notices/` and the server reads it from the installed APK; iOS builds carry `notices.zip`.
  Updates download it only when a release brings a different pack.

Edit overlays or patches, not the generated copies. `scripts/prepare.py`
refuses to overwrite edits to generated sources. Source pins are in both the Git
submodule entries and `upstream.lock.json`. Update both together, and only after
you test an upstream upgrade. Do not use `git submodule update --remote` for a
normal build.

For optional editor integration checks, use a disposable copy of a save with
player 1 and the prepared resources. The test makes its own working copies:

```sh
.build/venv/bin/pip install -r scripts/requirements-test.txt
.build/venv/bin/python android/tools/test_tools.py \
  --save /path/to/game.db \
  --assets /path/to/prepared/assets \
  --master android/app/src/main/assets/lunar/20240404193219.bin.e \
  --original-master /path/to/original/20240404193219.bin.e
```

To run the standalone companion's JNI smoke test, connect a development ARM64
Android emulator and run `cd android && ./gradlew connectedDebugAndroidTest`.
It does not install or clear the combined game's save. Full device testing is
separate from these checks. See [validation](VALIDATION.md).

The small asset-preparation safety checks need no game files:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```
