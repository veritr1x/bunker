# Windows presentation APK configuration

`prepare_windows_presentation_apk.py` reproduces a data-only APK variant that sets
`PlayerSettings.androidUseSwappy` to false. Unity then selects its existing EGL
presentation path rather than the Android Swappy path. Original guest code, host
code, shaders, DEX and the existing disabled-audio setting remain unchanged.

Use an executable with the presentation-APK admission change. Older executables
reject this container during their initial SHA-256 check. The bootstrap admits
this exact additional digest only with `--mute-audio --collector-delivery --first-frame`;
both original native-library hashes remain mandatory.
The asset-pack wrapper receives the actual mounted APK digest and still requires
the verified, closed application-code catalog.

The script uses Python's standard library and accepts only the qualified muted
APK with SHA-256
`36e15676053734a225f55bdf89acd375adaf298872d4d1dfc06c140e5a0ed394`.
Use a fresh output directory:

```sh
python recomp/windows/prepare_windows_presentation_apk.py \
  --source-apk recomp/work/windows-first-frame-guest-transfer1/game-audio-disabled.apk \
  --out recomp/work/windows-presentation-reproduction1
```

The output APK must have SHA-256
`fd0d0d357a4e8c316d0e732783d795f0e100a675d0c7a0fcf252873deb84f538`.
The script refuses a different compressor result before writing output. It also
writes an acceptance receipt and an inventory comparing all 4,968 ZIP entries.
Only `assets/bin/Data/globalgamemanagers` changes: one byte at offset 219900,
from 1 to 0. Its PlayerSettings object is class 129/path ID 1, starts at 219600,
and occupies 636 bytes; the field is object-relative offset 300.

The field was identified using UnityPy 1.25.4's named type tree for Unity
2019.4.29f1. A Python reader-position trace found that boolean at offset 219900;
the following three bytes are alignment padding. A no-op type-tree write
reproduced the entire object exactly. Changing only the named boolean produced
exactly the one-byte difference, and reparsing read false. The original Unity
registration at `0x702fb038` binds the same name to runtime field `+0x41e`;
the original binary reader at `0x70302190..0x70302194` reads/stores one byte.
The swap selector at `0x70412a00` tests that field. This is a serialized project
setting; this recipe does not assume a same-named `boot.config` override.

The original qualification is recorded under
`recomp/work/swappy-disabled-config1/acceptance.json` (SHA-256
`5c47102545862a53731a3d6adb4f5081841b1643dc8df0e0d7cfdcba48e3573d`).
Its field proof, type tree, original/modified object records and original-code
disassembly are retained beside that receipt and under
`recomp/work/swappy-init-callers-audit1`.
An independent metadata/type-tree walk and complete ZIP comparison are recorded
in `recomp/work/swappy-disabled-config-peer1/acceptance.json` (SHA-256
`6fd07f09c566990a863d8566482e05ad66dfecf343a6b501a30b5acca6a16548`).

The preparation script does not reserialize the asset. It patches the proven
byte, recompresses that member and updates its CRC/length plus ZIP directory
offsets. Every other entry's uncompressed contents and raw local/compressed
bytes are checked for exact preservation. The original APK is retained.

This variant is native-port input. Retaining signing metadata does not make a
modified APK signature-valid, and Android installation is not claimed. The
recipe does not launch the game or establish a presented frame; the runtime
must separately admit the exact APK and observe normal presentation.
