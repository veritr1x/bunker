# Windows

The game only exists as ARM code for Android and iOS. On Windows, it runs in Google's Android
Emulator. `Bunker.exe` sets this up. The first time, it downloads the emulator and an Android 16
image from Google, creates a phone in a folder next to itself, installs your `bunker.apk`, adds
the game files and opens the game. After that, it needs no Internet connection.

`Bunker.exe` does not include the Android SDK or the game. Bunker is not allowed to ship
Google's emulator, so each player downloads it from Google and accepts Google's license.

Experimental. Tested on Windows 11 with a Ryzen 7 7800X3D: the first start set up the emulator,
added the 21 GB of game files and reached the title screen and the screen after Tap to Start.
Gameplay after that is not tested on Windows yet.

## What you need

- Windows 10 or 11, 64-bit, on an Intel or AMD processor. Windows on ARM does not work.
- Virtualization turned on in the BIOS (it usually is), and **Windows Hypervisor Platform**
  ticked in **Turn Windows features on or off**. Restart after ticking it.
- About 16 GB of memory, 8 GB at least. The phone gets 8 GB on a computer with 24 GB or
  more, 6 GB from 12 GB, and 4 GB otherwise. With 4 GB, Android can run out of memory and
  show **NieR isn't responding**.
- About 30 GB of free space: 7 GB for the emulator and 21 GB for the game files in the phone.
  The 15 GB `.7z` comes on top of that.
- The same files as for Android: the original 3.7.1 ARM64 APK, the master data and
  `resource_dump_android.7z`.

## First start

1. Build the Android APK in the [web builder](https://veritr1x.github.io/bunker/), or with
   `scripts/build.py`.
2. Download `Bunker-<version>.exe` from the
   [latest release](https://github.com/veritr1x/bunker/releases/latest).
3. Put both in one folder, such as `C:\Games\Bunker`, and name the APK `bunker.apk`. Put
   `resource_dump_android.7z` there too.
4. Double-click `Bunker.exe`. Windows may say **Windows protected your PC**, because the
   program is not signed. Click **More info**, then **Run anyway**.
5. Read Google's license, type `y` and press Enter. Bunker downloads about 2.3 GB: adb, the
   emulator and the Android 16 image. It checks each file against Google's checksum. If a
   download stops, start `Bunker.exe` again to resume it.
6. The phone starts (the first time takes a few minutes) and NieR is installed. Bunker copies
   the game files from the `.7z` into the phone. This takes 15 to 20 minutes. Then the Bunker
   opens with the game files ready and starts the game.
7. You no longer need the `.7z`. Delete it or keep it as a backup. Bunker does not copy the
   same archive twice.

While it works, `Bunker.exe` shows each step, how far it is and the time left:

```
  LUNAR TEAR // WINDOWS
  B U N K E R                                      1.2.0

  [ 01 EMULATOR ] ────────────────────────────────────────
    ADB              READY        37.0.1
    EMULATOR         READY        37.2.12
    ANDROID 16       READY        x86_64 · r7
  [ 02 PHONE ] ───────────────────────────────────────────
    ACCELERATION     READY        WHPX
    BOOT             RUNNING      emulator-5554
  [ 03 NIER ] ────────────────────────────────────────────
    INSTALL          INSTALLED    bunker.apk
  [ 04 GAME FILES ] ──────────────────────────────────────
    UNPACK           STREAMING    ▓▓▓▓▓░░░░░░░  41% · 8.0 of 19.5 GB · 9 min left
  [ 05 DEPLOY ] ──────────────────────────────────────────
    OPEN             STANDING BY

  > Copying the game files into the phone (21 GB).
    Keep this window open.
```

If a file is missing, it asks for it at the start, before downloading anything. Drag
`bunker.apk` or the `.7z` into the window and press Enter. After that, it runs on its own. To skip the game files, press Enter without a file. You can add them later in the
Bunker, or drop the `.7z` on `Bunker.exe`.

You do not need to choose the game files in the Bunker. Do not use **Archive (.7z or .zip)**
there on Windows. It works, but it takes about two hours, because the Bunker's unpacking is ARM
code and the emulator has to translate it.

The mouse works as touch, and the keyboard types into the game. You can resize the emulator
window from its corner.

Keyboard controls in the game:

| Key | Does |
| --- | --- |
| **W A S D** or the arrow keys | Move |
| **Shift** with a movement key | Walk instead of run |
| **Ctrl+B** | Open the Bunker (like ⌘B on a Mac) |

They work in the game window only, and on Android phones and tablets with a keyboard too.

The emulator passes a held key on as a stream of taps, and forgets a held key when you press
another. So while the emulator is open, `Bunker.exe` keeps a small helper running that reads
which movement keys are really held and tells the game. It changes no keys, so typing works as
before, and it quits when you close the emulator.

## Every day

Double-click `Bunker.exe`. The phone starts in under a minute and the game opens. To stop,
close the emulator window. The emulator saves the phone, so the next start is quick. If the
phone is already running, `Bunker.exe` just opens the game again.

## Updates

- **Bunker inside the phone** updates itself, as on Android (⋮ → **Check for updates**). If
  it says **This update needs the web builder**, build the APK again and put it in the folder
  as `bunker.apk`. Then start `Bunker.exe`. It installs the new APK over the old one and keeps
  your save.
- **Bunker.exe**: download the new one from the release and replace the old one.
- The emulator and the Android image stay at the version you first downloaded.

## Saves

The save is inside the phone, as on Android. In the Bunker, use ⋮ → **Export save backup** to
back it up and **Import save backup** to restore it. Backups also move between Windows and a
phone.

## The folder

| Path | What it holds |
| --- | --- |
| `Bunker.exe`, `bunker.apk` | The program and your build |
| `BunkerData\sdk` | adb, the emulator, the Android image and the accepted licenses |
| `BunkerData\home\avd\Bunker.avd` | The phone: its storage, with the game files and the save |
| `BunkerData\downloads` | Downloads in progress |
| `BunkerData\logs\emulator.log` | The emulator's log for the last start |

To move everything, close the emulator and move the folder. To remove everything, delete the
folder. Nothing is installed anywhere else. If the folder path has non-English letters (for
example, a user name with accents), the emulator may not start. Use a folder like
`C:\Games\Bunker`.

Options, for running `Bunker.exe` from a command prompt:

| Option | |
| --- | --- |
| `-apk PATH` | Use this APK instead of `bunker.apk` next to the program |
| `-data PATH` | Use this folder instead of `BunkerData` |
| `-ram MB` | The phone's memory (default: 4096, 6144 or 8192, from the computer's memory) |
| a file name | Game files to copy into the phone (the same as dropping them on the program) |

## Troubleshooting

| Message or symptom | Fix |
| --- | --- |
| **NieR isn't responding** in the emulator | The phone ran out of memory. Close the emulator window and start `Bunker.exe` again: it now gives the phone more memory if the computer has it. You can also set it with `-ram 6144`. |
| **The emulator cannot use hardware acceleration** | Turn on virtualization in the BIOS and Windows Hypervisor Platform in Windows features. Then restart. |
| **Android took too long to start** | Read `BunkerData\logs\emulator.log`. Close other emulators (BlueStacks, LDPlayer) and start again. |
| **different signing key** | The NieR in the phone came from an APK signed with another key. Use an APK signed with the same key. Bunker will not uninstall it for you, because that would delete the save. |
| **older than the NieR in the phone** | NieR updated itself in the phone. Remove the old `bunker.apk` from the folder, or build a new one. |
| The emulator window is black, or the game looks wrong | Update the graphics driver. |

## How it works

`Bunker.exe` is a small Go program (`windows/` in this repository). Apart from Go's standard
library, it uses one package: the 7z reader the Bunker uses (`github.com/bodgit/sevenzip`).

It reads Google's package lists (the same ones `sdkmanager` uses). It downloads the newest
stable emulator and adb for Windows, and `system-images;android-36;google_apis;x86_64`, into
its own SDK folder. That image runs ARM64 apps through Google's ARM translation, and Bunker
checks for it after the phone starts. Bunker writes the phone into `BunkerData\home\avd`. It
points `ANDROID_HOME`, `ANDROID_USER_HOME` and `ANDROID_AVD_HOME` at the folder, so nothing goes
into your user profile. adb uses its own port (5039), so it does not restart Android Studio's
adb, and it stops when `Bunker.exe` closes. The emulator runs separately from the console
window, so you can close that window while you play. The phone gets half the computer's
threads, from 4 to 6 (the emulator's limit), because the ARM translation needs them.

Bunker unpacks the game files on the computer. The Bunker's own unpacking is ARM code, and the
emulator would have to translate it: that takes about two hours for 21 GB. Like the Bunker,
`Bunker.exe` unpacks only revision 0. It only decompresses the parts of the 7z that hold it,
several at once (80 to 117 MB/s on a Ryzen 7 7800X3D). Windows' own `tar` can read the archive
too, but it skips 43 files with unusual characters in their names.

The files go to the phone as one tar stream through `adb exec-in`. The phone's own `tar`
unpacks them. It is an x86 program, so translation does not slow it down. Nothing is written
to the computer's disk. adb carries about 30 MB/s from the emulator. Copying the files one by
one with `adb push` reached 21 MB/s, and writing through the phone's shared storage
(`/sdcard`) only 4 MB/s.

The stream goes straight into the Bunker's private game files folder. That needs adb to run as
root, which Google APIs images allow. Then `Bunker.exe` does what the Bunker does after an
import:

- checks that every file arrived,
- checks that revision 0 does not need files from other revisions,
- keeps the master data and the calendar's next loop,
- swaps the new files in,
- gives the files NieR's owner and SELinux label.

To build it:

```sh
cd windows
go test ./...
GOOS=windows GOARCH=amd64 go build -o Bunker.exe .
```

The same program also builds for macOS and Linux. There it uses the arm64 or x86_64 image that
matches the computer.
