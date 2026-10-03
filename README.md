## AI usage disclosure

This is a **personal hobby project** built with extensive AI assistance from OpenAI Codex and Anthropic Claude for coding, integration, testing, and documentation. It is an unofficial, experimental project, not an official game release.

# lunar-tear-all-in-one

Run NieR Re[in]carnation and its Lunar Tear server on the same phone or tablet, on Android or iOS. After setup, no computer connection or Internet is needed to play.

- **Android:** one APK with the launcher, server, content patcher and save editors.
- **iPhone and iPad:** one IPA with the server and launcher inside the game. See [iOS](docs/IOS.md).

## Play on Android

1. Install your locally built APK.
2. Open it and **Choose** your prepared `assets` folder. A progress bar shows how much is copied and the time left.
3. Tap **Play**. The server starts and the game opens automatically.

The launcher is simply **1 Game files → 2 Server → 3 Play**.
Open **⋮ → Tools** for content presets, inventory, upgrades, and save backup/restore. Close Tools and tap Play to resume.

## Play on iPhone or iPad

1. Install your locally built and signed IPA.
2. Open it and tap **Choose assets folder** (a progress bar shows the time left), or drag the folder in with Finder.
3. The server starts and the game continues. Three-finger double-tap opens the launcher during play.

Tap **⋮** for server control, master-data import, save backup and restore, the server log, help and about.

## Build it yourself, step by step

Everything below runs on your computer once. Playing needs only the phone or tablet.
Commands are for macOS with [Homebrew](https://brew.sh); Linux works for the Android build
with the same tools from your package manager.

### 1. Gather your own game files

None of these are included in this repository. Put them anywhere; the commands below use
`~/Downloads`.

| File | Needed for |
| --- | --- |
| Original game APK, version 3.7.1, ARM64 (`…nierspww_3.7.1…apk`) | Android |
| Decrypted game IPA, version 3.7.1 (`com.square-enix.NieRSPww_3.7.1.ipa`) | iPhone/iPad |
| Master data `20240404193219.bin.e` | both |
| Resource dump: `resource_dump_android.7z` and/or `resource_dump_ios.7z` | Android / iPhone/iPad |

### 2. Install the tools

Both platforms:

```sh
brew install git go protobuf python@3.11 sevenzip
```

For **Android**, also:

```sh
brew install apktool
```

Then install [Android Studio](https://developer.android.com/studio) and, in its SDK Manager,
add **Android SDK Platform 36**, **Build-Tools 36.0.0** and **NDK 27.2.12479018**. Use its
bundled JDK 21 (newer JDKs break the Android build):

```sh
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
```

For **iPhone/iPad** (Mac only), also install Xcode from the App Store, open it once to finish
setup, then add Python 3.13 for the Tools runtime:

```sh
brew install uv
uv python install 3.13
```

### 3. Get the code

```sh
git clone --recurse-submodules https://github.com/veritr1x/lunar-tear-all-in-one.git
cd lunar-tear-all-in-one
```

If you cloned without `--recurse-submodules`, run `git submodule update --init --recursive`.

### 4. Build

Always run the build with `python3.11`. It checks its tools first and names anything missing.
The first build downloads dependencies and takes several minutes.

**Android:**

```sh
python3.11 scripts/build.py \
  --apk ~/Downloads/<original-game>.apk \
  --master ~/Downloads/20240404193219.bin.e
```

Result: `artifacts/game-Offline.apk`. The first build creates a signing key in
`inputs/lunar-local.keystore`. **Keep it:** later builds must use the same key to update the
app without losing its data.

**iPhone/iPad:**

```sh
python3.11 scripts/build.py \
  --ipa ~/Downloads/com.square-enix.NieRSPww_3.7.1.ipa \
  --master ~/Downloads/20240404193219.bin.e
```

Result: an unsigned `artifacts/game-Offline.ipa`. Install it with Sideloadly or
AltStore and your Apple ID, or sign it with your own Apple developer team as described in
[iOS](docs/IOS.md#build).

### 5. Prepare the game files (about 21 GB)

Extract the dump for your platform, then copy out the part the game needs:

```sh
# Android
7zz x ~/Downloads/resource_dump_android.7z -o"$HOME/Downloads/android-dump"
python3.11 scripts/prepare_assets.py --source ~/Downloads/android-dump --output phone-assets/android/assets

# iPhone/iPad
7zz x ~/Downloads/resource_dump_ios.7z -o"$HOME/Downloads/ios-dump"
python3.11 scripts/prepare_assets.py --source ~/Downloads/ios-dump --output phone-assets/ios/assets
```

Android and iOS files are not interchangeable; use the matching dump.

### 6. Install and play

**Android (9 or later, ARM64):**

1. Copy `phone-assets/android/assets` to the phone, for example into `Download/assets`, with
   a USB cable or `adb push phone-assets/android/assets /sdcard/Download/assets`.
2. Install the APK: open it on the phone, or run `adb install artifacts/game-Offline.apk`.
3. Open **NieR Re[in]carnation · Offline**, tap **Choose** and select the copied `assets` folder.
   A progress bar shows the time left.
4. Tap **Play**. The server starts on the phone and the game opens.

**iPhone/iPad (iOS 14 or later):**

1. Install the IPA (step 4).
2. Open **NieR**. The launcher appears because the game files are missing.
3. Tap **Choose assets folder** and pick `phone-assets/ios/assets` after copying it to the device
   (Files, iCloud Drive or a USB drive), or drag `assets` onto NieR in Finder (your device ›
   Files) and tap **Check again**. Allow about 25 GB free.
4. The server starts inside the game. Three-finger double-tap opens the launcher during play.

### 7. Update later

```sh
git pull
git submodule update --init --recursive
```

Then build again with the same command. On Android, the build reuses `inputs/lunar-local.keystore`
automatically. On iOS, sign with the same bundle ID. Either way, export a save backup from
**⋮** first; **⋮ → Import save backup** restores it, including on another device.

### Troubleshooting

| Message or symptom | Fix |
| --- | --- |
| `Missing <tool>` | Install it as in step 2; the build lists each missing tool. |
| Errors mentioning `filter` or `tarfile` | You ran `python3`; use `python3.11`. |
| Gradle or `jlink` fails | `JAVA_HOME` is not JDK 21; set it as in step 2. |
| `Missing the iOS SDK` | Install Xcode and open it once. |
| `Install Python 3.13` | Run `uv python install 3.13`. |
| The new APK will not install over the old one | It was signed with a different key. Build with `--keystore` pointing to your original key. |

More detail: [Android setup guide](docs/BUILD.md) and [iOS guide](docs/IOS.md).

## Pinned upstream projects

All four are Git submodules fixed to the tested commits. Both platforms build from these exact versions.

| Project | Pinned commit |
| --- | --- |
| [Lunar Tear](https://gitlab.com/walter-sparrow-group/lunar-tear) | `63df7d70556a7` |
| [Lunar Scripts](https://gitlab.com/walter-sparrow-group/lunar-scripts) | `942dced617ea` |
| [Lunar Base](https://github.com/NMeliksah/lunar-base) | `b39154099b8f` |
| [Master-data patcher](https://github.com/NavHobbyDev/lunar-tear-masterdata-patcher) | `9b6cd167b51d` |

Full pins: [upstream.lock.json](upstream.lock.json). Credits: [third-party notes](android/THIRD-PARTY.md).

## Status

iOS 14+ on iPhone and iPad: the opening story plays on an iPad Pro (M4), with the server running inside the game. Tools works on iOS too (tested on the iPad). See [validation](docs/VALIDATION.md).

Android 9+ on ARM64. Offline opening gameplay, touch movement, content patching, and save restoration were tested on an Android 16 emulator; folder import with progress and save import were tested on a Samsung Galaxy Z Fold. Full campaign coverage is still pending. See [validation](docs/VALIDATION.md).

