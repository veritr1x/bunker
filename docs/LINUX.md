# Linux

On Linux, the same program as `Bunker.exe` plays the Android build. If
Waydroid is installed, it uses Waydroid. Otherwise it uses Google's
Android Emulator, as on Windows (see [Windows](WINDOWS.md)).

Experimental.

## Waydroid

With Waydroid, Android runs in a container on the computer itself, so there is no emulator to
download or boot. Bunker installs `bunker.apk` and copies the game files into the Bunker's own
storage inside Waydroid, the same place they go on a phone. There is no shared folder to mount,
and nothing to set up again after Waydroid restarts.

### What you need

- Waydroid, set up (`sudo waydroid init`) and started once.
- Waydroid able to run ARM64 apps. On an ARM computer it can. On an Intel or AMD computer,
  Waydroid needs an ARM translation layer (libndk or libhoudini) installed first. Bunker checks
  and says so if it is missing.
- `sudo`: Waydroid's root shell needs it to put the game files into the Bunker's storage.
  Bunker asks for your password once, at the start.
- About 21 GB of free space for the game files in Waydroid. The 15 GB `.7z` comes on top of
  that, and you can delete it afterwards.
- The same files as for Android: `bunker.apk` from the
  [web builder](https://veritr1x.github.io/bunker/) and `resource_dump_android.7z`.

### First start

1. Download `Bunker-<version>-linux-x86_64` (Intel or AMD) or `Bunker-<version>-linux-arm64`
   from the [latest release](https://github.com/veritr1x/bunker/releases/latest).
2. Put it in one folder with `bunker.apk` and `resource_dump_android.7z`, and make it
   executable: `chmod +x Bunker-*-linux-*`.
3. Start Waydroid, then run the program from a terminal in that folder:
   `./Bunker-<version>-linux-x86_64`.
4. Enter your password when `sudo` asks.
5. Bunker installs NieR in Waydroid and unpacks the game files into it, then opens the Bunker
   with the game files ready.

The console shows each step:

```
  LUNAR TEAR // WAYDROID
  B U N K E R
  [ 01 WAYDROID ]
    WAYDROID         READY        1.6.3
    SESSION          RUNNING
  [ 02 NIER ]
    INSTALL          INSTALLED    bunker.apk
  [ 03 GAME FILES ]
    UNPACK           STREAMING    41% · 8.0 of 19.5 GB
  [ 04 DEPLOY ]
    OPEN             STANDING BY
```

If Waydroid is not running and you are in a Wayland session, Bunker starts it. Waydroid
pauses Android when none of its apps is on screen; Bunker keeps it running until the game files
are in, so you can hide Waydroid's window while they copy. Copying takes about 12 minutes at
30 MB/s.

### Every day

Open NieR from Waydroid, or run the program again: it opens the game. It installs a newer
`bunker.apk` if you put one in the folder, and skips game files it has already copied.

### Saves

The save is in the Bunker's storage in Waydroid, as on Android. Use ⋮ → **Export save backup**
in the Bunker to back it up and **Import save backup** to restore it. Backups also move between
Linux, Windows and phones.

### Options

| Option | |
| --- | --- |
| `-apk PATH` | Use this APK instead of `bunker.apk` next to the program |
| `-data PATH` | Keep Bunker's record of what it installed here instead of `BunkerData` |
| `-emulator` | Use Google's Android Emulator even though Waydroid is installed |
| a file name | Game files to copy into Waydroid |

## Google's Android Emulator

Without Waydroid, or with `-emulator`, the program sets up Google's Android Emulator in
`BunkerData` next to it, as `Bunker.exe` does on Windows. See [Windows](WINDOWS.md); the steps
and options are the same.
