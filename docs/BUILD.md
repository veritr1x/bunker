# Build once, then play on the phone

## 1. Get your files

You need your own **original Android ARM64 game APK, version 3.7.1**, the original
`20240404193219.bin.e` master-data file, and an extracted Android resource dump.
The guarded binary patch supports the tested 3.7.1 ARM64 APK; other binaries may
be rejected. The scripts read your originals and work on separate copies.

## 2. Install the build tools

Use macOS or Linux with:

- Git, Make, Go 1.25.8 or newer, `protoc`, and `apktool`.
- Python 3.11.9 or newer, available as `python3.11`. Run the build with it; an
  older `python3` (such as macOS's 3.9) cannot run it.
- JDK 21, with `JAVA_HOME` pointing to it. Newer JDKs fail in Android's build.
  Android Studio's bundled JDK works:
  `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`.
- Android SDK platform 36, build-tools 36.0.0, and NDK 27.2.12479018.

Install the SDK components with Android Studio's SDK Manager. The build finds
the SDK at `~/Library/Android/sdk` on macOS or `~/Android/Sdk` on Linux if
`ANDROID_HOME` is unset. Build dependencies need Internet access on the computer.
On macOS with Homebrew: `brew install go protobuf apktool python@3.11`.

For the iPhone build, see [iOS](IOS.md): it needs a Mac with Xcode and
Python 3.13 instead of the Android tools.

## 3. Clone and build

```sh
git clone --recurse-submodules https://github.com/veritr1x/lunar-tear-all-in-one.git
cd lunar-tear-all-in-one
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

Your APK is **`artifacts/game-Offline.apk`**. Its checksum is in
`artifacts/SHA256SUMS`. Keep **`inputs/lunar-local.keystore`**: later APKs need the
same key to update your installation without removing its data. To reuse a key:

```sh
python3.11 scripts/build.py --apk /path/to/game.apk --master /path/to/master.bin.e \
  --keystore /path/to/lunar-local.keystore
```

Use this integration's key format (alias `lunar-local`, local-build password
`android`). Keep the file private. Keys and game files are ignored by Git.

## 4. Prepare the phone's game files

Copy `resource_dump_android.7z` to the phone and choose it in the launcher
(**Choose → Archive (.7z or .zip)**). Only revision 0 is used: the server
always serves it, and the dump's 817 other revisions are 28 GB of old catalogs.
The app unpacks revision 0 only, decompressing just the parts of the archive
that hold it. A `.zip` of the dump works too.

Or extract `revisions/0` yourself, on the computer
(`7zz x resource_dump_android.7z 'revisions/0/*' -oandroid-dump`) or on the
phone (for example ZArchiver), and choose the folder (**Choose → Extracted
folder: copy into the app**). It copies revision 0 only, so a full extraction works too.

**Extracted folder: use in place** (Android 11+) reads the folder where it is
instead of copying it, saving 21 GB. It needs **All files access**, which the
app asks you to turn on in Settings once. The app links the folder rather than
owning it: choosing other files later removes only the link. If the folder is
moved or deleted, the launcher says so; choose it again.

The import refuses a dump whose revision 0 points at files in other revisions;
the tested dump does not. `scripts/prepare_assets.py --source <extracted folder>`
is optional: it writes a checked, ready `phone-assets/assets` folder with only
revision 0, which is smaller to copy. Its output is about 20.9 GB. Allow at least 50 GB free on the phone during import; the game's cache
may need more. Patched master data is already bundled in the APK.

## 5. Install and play

1. Install `game-Offline.apk` on an ARM64 Android 9+ phone.
2. Open it. Under **1 Game files**, tap **Choose** and select the `.7z` or the copied folder.
3. Wait for import. It first counts the files, then shows a progress bar with
   the time left. The server starts and the game opens. Tap **3 Play** to retry.

Subsequent launches start the server and game automatically. In-game download
prompts load files from this same phone, including in airplane mode.

The APK uses a different signature from the publisher's APK. Preserve existing
saves before removing a conflicting installation. A later build signed with
your same local key can update this installation normally.

Tap the server notification to return to the launcher. **⋮ → Tools** opens:

- Content presets, custom configuration, master import/export and rollback.
- Player inventory, gems/materials, costumes, weapons, companions and upgrades.
- Karma, slabs, debris, memoir sets and stats.
- Automatic game-save snapshots, manual backups and restoration.

Tools stops the game while editing. Its first launch prepares names from your
imported resources. Close Tools and tap Play to resume with the changed data.

Use **⋮ → Stop server** when finished. If Samsung pauses the server, set the
app's battery usage to **Unrestricted**.

## Keep your saves

Stop the server and use **⋮ → Export save backup** before uninstalling or clearing
app storage. It exports `game.db`, `auth.db`, and `auth.key` in a ZIP.

To restore, stop the server and use **⋮ → Import save backup**. It accepts such
a ZIP from Android or iOS, or a bare `game.db`, checks it before replacing
anything, and keeps the current save as a safety copy. A save from another
device takes over this device's player: open the game once on a new device
first, so it has a player to take over.

Tools keeps the latest 50 game-database snapshots and can restore them on the
phone. Those snapshots remain inside the app and are removed by uninstalling.
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

Edit overlays or patches rather than generated copies. `scripts/prepare.py`
refuses to overwrite edits to generated sources. Source pins live in both Git
submodule entries and `upstream.lock.json`; update them together only after
testing an upstream upgrade. Do not use `git submodule update --remote` for a
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

With a development ARM64 Android emulator connected, the standalone companion's
JNI smoke test can be run using `cd android && ./gradlew connectedDebugAndroidTest`.
It does not install or clear the combined game's save. Full device testing is
separate from these checks; see [validation](VALIDATION.md).

The small asset-preparation safety checks need no game files:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```
