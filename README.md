## AI usage disclosure

This is a **personal hobby project** built with extensive AI assistance from OpenAI Codex for coding, integration, testing, and documentation. It is an unofficial, experimental project, not an official game release.

# lunar-tear-all-in-one-android

Run NieR Re[in]carnation and its Lunar Tear server on the same Android phone. One APK includes the launcher, server, content patcher, and save editors. After setup, no computer connection or Internet is needed to play.

## Play

1. Install your locally built APK.
2. Open it and **Choose** your prepared `assets` folder.
3. Tap **Play**. The server starts and the game opens automatically.

The launcher is simply **1 Game files → 2 Server → 3 Play**.
Open **⋮ → Tools** for content presets, inventory, upgrades, and save backup/restore. Close Tools and tap Play to resume.

## Build and setup

```sh
git clone --recurse-submodules https://github.com/veritr1x/lunar-tear-all-in-one-android.git
cd lunar-tear-all-in-one-android
python3 scripts/build.py --apk /path/to/original-game.apk --master /path/to/20240404193219.bin.e
```

See the [setup guide](docs/BUILD.md) for required tools and preparing the assets folder. Building needs a computer once; playing does not.

Game APKs, master data, resources, saves, and signing keys are not included. Keep your signing key and export a save backup before uninstalling.

## Pinned upstream projects

All four are Git submodules fixed to the tested commits. The build uses these exact versions.

| Project | Pinned commit |
| --- | --- |
| [Lunar Tear](https://gitlab.com/walter-sparrow-group/lunar-tear) | `63df7d70556a7` |
| [Lunar Scripts](https://gitlab.com/walter-sparrow-group/lunar-scripts) | `942dced617ea` |
| [Lunar Base](https://github.com/NMeliksah/lunar-base) | `b39154099b8f` |
| [Master-data patcher](https://github.com/NavHobbyDev/lunar-tear-masterdata-patcher) | `9b6cd167b51d` |

Full pins: [upstream.lock.json](upstream.lock.json). Credits: [third-party notes](android/THIRD-PARTY.md).

## Status

Android 9+ on ARM64. Offline opening gameplay, touch movement, content patching, and save restoration were tested on an Android 16 emulator. Physical Samsung Fold testing and full campaign coverage are still pending. See [validation](docs/VALIDATION.md).

This repository is private for now.
