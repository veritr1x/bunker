# iPhone and iPad

The iOS build puts the Lunar Tear server inside the game itself. iOS pauses
apps in the background, so a separate server app could not answer the game
while you play. Once the game files are on the device, you can play
without a computer or Internet.

## How it works

- `ios/launcher/` is a small framework, `LunarTear.framework`. It contains
  the same Go server as Android, built for iOS, plus a native launcher screen.
- The build adds the framework to your patched game and adds one load
  instruction to the game's executable. The server starts when the game
  opens, before Unity's first request, and listens only on `127.0.0.1`.
- Game files live in the app's Documents folder, which Finder and the Files
  app can see. Saves are in `Documents/saves`.
- The launcher screen appears when game files are missing or the server
  fails. A three-finger double-tap during play opens it at any time.
- With the radios off, Unity sees no network and refuses downloads. Like the
  Android build, the launcher tells only Unity that a local network exists.

## Build

You need a Mac with Xcode, plus the tools in [BUILD.md](BUILD.md) except the
Android ones, and Python 3.13 (`uv python install 3.13` is enough). Use your
own decrypted 3.7.1 IPA.

```sh
python3.11 scripts/build.py \
  --ipa /path/to/com.square-enix.NieRSPww_3.7.1.ipa \
  --master /path/to/20240404193219.bin.e
```

This writes an unsigned `artifacts/bunker.ipa`. Sideloadly or
AltStore can sign and install it with your Apple ID.

To sign it yourself, give it a bundle ID your team owns and a development
profile that includes your device. One way to get the profile is to let
Xcode create it with the helper project:

```sh
python3 ios/devtools/generate_project.py
xcodebuild -project ios/devtools/LunarDevice.xcodeproj -scheme Provision \
  -destination 'id=<device UDID>' -derivedDataPath .build/ios-devtools \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration \
  LUNAR_TEAM=<team ID> LUNAR_BUNDLE_ID=<bundle ID> build
cp .build/ios-devtools/Build/Products/Debug-iphoneos/Provision.app/embedded.mobileprovision \
  inputs/ios-development.mobileprovision

python3.11 scripts/build.py --ipa ... --master ... \
  --bundle-id <bundle ID> --sign-identity '<codesign identity>' \
  --profile inputs/ios-development.mobileprovision
xcrun devicectl device install app --device <device UDID> artifacts/bunker.ipa
```

The provisioning build only creates the profile. It does not install anything.
Profiles expire. To keep saves, rebuild and reinstall with the same bundle ID.

## Updates

From 1.0.0, the launcher looks for a newer release when it opens. It checks
only when online, and ⋮ › Check for updates turns it off. **Update** downloads
Bunker's launcher framework and Python runtime from the release. It then builds
`Bunker-<version>.ipa` from the installed app, in Documents (Files › On My
iPhone/iPad › NieR). It copies the game's files, including the patched
UnityFramework, unchanged, and leaves out the old signatures.
Then the share sheet opens. SideStore or AltStore can sign and install the IPA on
the device. Or copy it to a Mac and sideload it with the same bundle ID and
team, so the saves stay. The new version deletes the IPA when it first
opens. Before a new version updates a save, it copies the save to Pod Programs'
snapshots ("Before update").

To test an update before a release exists, put `Documents/update-test.json`
containing `{"latest": "http://<mac>:8000/latest.json"}` on the device. That URL
serves a GitHub-style release with `update.json` and the two bundles, made by
`scripts/release_assets.py`.

## Game files

iOS needs the iOS dump. Android asset bundles do not render on iPhone or iPad.
The launcher can import `resource_dump_ios.7z` directly (or a `.zip` of it) and
unpacks only `revisions/0`, the revision the server uses. Or extract that folder
yourself:

```sh
7zz x resource_dump_ios.7z 'revisions/0/*' -oclient/ios-dump
```

Then put the 20 GB of files on the device in one of these ways:

- Tap **Choose** under **Game files** on the launcher screen. It shows the same three
  options as on Android. Pick the `.7z`, or the
  extracted folder (the one containing `revisions`), from Files, iCloud Drive or
  a USB drive. Only revision 0 is used, so a full extraction works too. A split
  `.tar` of it works as well. The app copies or unpacks it into the app, so you need
  about 25 GB free, plus space for the archive. If the folder is already inside
  NieR's own files (put there with Finder or the Files app), the app moves it
  instead. This is instant. Your
  current files stay in place until the import completes. A progress bar shows
  the time left.
- **Extracted folder: use in place**: for a folder outside NieR's own files,
  nothing is copied. The app keeps a bookmark and reads the folder from where it
  is (on the device, another app's folder or a USB drive). Keep the folder there,
  and keep a drive connected while playing. Otherwise, the launcher asks you to
  reconnect it or choose again. iCloud Drive folders can only be copied, because
  iOS can remove their local copies.
- Finder: run `python3.11 scripts/prepare_assets.py --source client/ios-dump
  --output phone-assets/ios/assets`, then select the device, open **Files**, and
  drag `assets` onto **NieR**. Then tap **Check again**. (Finder skips the
  app's import, so use the prepared folder.)
- From a Mac with developer tools:
  `xcrun devicectl device copy to --device <UDID> --domain-type appDataContainer --domain-identifier <bundle ID> --source phone-assets/ios/assets --destination Documents/assets`

## Options menu

The launcher is the **Bunker**. **Open Pod Programs** (the save editors and
content presets, as on Android) is on the Bunker itself. Tap **⋮** for:

- **Display**: light, dark or the system setting (the default).
- **Stop Lunar Tear** or **Start Lunar Tear**, and **Check Lunar Tear**.
- **Import master data** replaces the bundled master-data file.
- **Export save backup** saves `game.db`, `auth.db` and `auth.key` in a ZIP.
- **Import save backup** restores such a ZIP, from iOS or Android, or a bare
  `game.db`. The current save is kept in `saves.before-import`.
- **Lunar Tear log** shows the latest lines. **Export Lunar Tear log** saves a ZIP with
  the log and the iOS version. The log is kept between sessions (`Documents/logs`,
  up to about 10 MB, also visible in Files).
- **App settings**, **Help** and **About**.

Stopping the server, importing master data or exporting saves disconnects the
game. Close it from the app switcher and open it again. After importing a save,
tap **Close game**, then open NieR again. Export a save backup before deleting
the app.

A save from another device takes over this device's player, because the game
finds its player by an ID it creates on each device. Open the game once on a
new device before importing, so that ID exists.

## Tools

Tools runs lunar-base's editors and the content patcher with the same code as
Android, on a Python 3.13 built for iOS
([BeeWare Python-Apple-support](https://github.com/beeware/Python-Apple-support),
pinned in `ios/python/native.json`). `ios/tools/build_python.py` builds it.
It compiles lz4 and pycryptodome for iOS and turns every compiled module into
its own framework, as iOS requires.

- Python loads only when Tools opens, so normal play is unaffected.
- Opening Tools stops the game server. Edits go through the server's own
  save code, and each one is backed up first.
- The game keeps its own copy of your data, so closing Tools asks you to
  restart the game: tap **Close game**, then open NieR again.
- The original master data is bundled, so content presets work without
  importing it.

## Sign-in

The game's account page opens in Safari, which sends the game to the
background. The launcher asks iOS for a short time to keep running in the
background, so the page can still reach the server. Finish signing in quickly.

## Checks

```sh
python3 -m unittest discover -s ios/tools -p 'test_*.py'
ios/tools/simulator_smoke.sh .build/ios/master/20240404193219.bin.e
```

The simulator check runs the real launcher and server in a stand-in app. It
covers the setup screen, server start, sign-in page, saves, restart and folder
import. It cannot run the game itself.

To drive a connected device, build the controller once and use
`ios/devtools/device.py`:

```sh
xcodebuild -project ios/devtools/LunarDevice.xcodeproj -scheme Control \
  -destination 'id=<UDID>' -derivedDataPath .build/ios-devtools \
  -allowProvisioningUpdates LUNAR_TEAM=<team ID> LUNAR_BUNDLE_ID=<bundle ID> build-for-testing
export LUNAR_DEVICE=<UDID> LUNAR_BUNDLE_ID=<bundle ID>
python3 ios/devtools/device.py screenshot shot.png
python3 ios/devtools/device.py tap 0.5 0.5
```
