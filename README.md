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

## Build it yourself

You need your own copies of the game (the 3.7.1 APK and/or a decrypted 3.7.1 IPA), its
`20240404193219.bin.e` master data, and the matching resource dump. None are included.

```sh
git clone --recurse-submodules https://github.com/veritr1x/lunar-tear-all-in-one-android.git lunar-tear-all-in-one
cd lunar-tear-all-in-one

# Android → artifacts/NieR-Reincarnation-Offline.apk
python3.11 scripts/build.py --apk /path/to/original-game.apk --master /path/to/20240404193219.bin.e

# iPhone/iPad (Mac with Xcode) → artifacts/NieR-Reincarnation-Offline.ipa
python3.11 scripts/build.py --ipa /path/to/original-game.ipa --master /path/to/20240404193219.bin.e
```

The build checks its tools and says what is missing. Install them as listed in the
[Android setup guide](docs/BUILD.md) and the [iOS guide](docs/IOS.md), which also cover
preparing the game files, signing, and installing. Building needs a computer once;
playing does not.

Game APKs and IPAs, master data, resources, saves, signing keys and profiles are not included. Keep your signing key and export a save backup before uninstalling.

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

This repository is private for now.
