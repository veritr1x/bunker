# Android telemetry controls

Android packaging removes the game's advertising-ID permission (`AD_ID`) and
Adjust install-referrer receiver, and applies the 12 ARM64 patches listed in
[telemetry_patches.json](../android/tools/telemetry_patches.json). These stop
identified Unity Analytics, Crashlytics, Facebook event, Adjust and IronSource
entry points. Instruction fingerprints and executable mappings guard the patches;
unsupported binaries are rejected, and applying the patches again is safe.

Both APK builders and `assemble_apk.update` apply these controls. Updates preserve
other game patches, DEX files, metadata, master data and port offsets. Existing
Unity Connect settings and manifest SDK switches remain in the packagers.
The advertising-ID permission restricts access on Android 13 and later.

## Updating

`GAME_PATCH` stays at 1, so these changes do not force a rebuild through the web
builder. Normal version and signing-key checks still apply.

The updater runs the tools already installed in the app. An older launcher's
first update installs the new tools; the next compatible update built with them
applies these controls. Fresh builds include them immediately.

## Tests

Run `python3 -m unittest discover -s android/tools -p 'test_privacy.py'` and
`python3 -m unittest discover -s android/tools -p 'test_update_apk.py'`.
Synthetic fixtures cover manifest preservation, binary guards, repeated updates,
compression, signing and failure cleanup. Tests requiring the original game APK
skip when it is absent.
