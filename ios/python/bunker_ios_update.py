"""Builds the next Bunker IPA on the device from the installed app and the release's bundles.

iOS installs only apps signed by the player's own certificate, which Bunker
doesn't have, so the launcher hands the IPA to the player's sideloading tool
(SideStore, AltStore, or a Mac). The game's files are copied from the
installed app as they are; Bunker's launcher framework and Python runtime
come from the release. The old signatures are left out; the tool signs it.
"""
import hashlib
import json
from pathlib import Path
import plistlib
import zipfile

GAME_PATCH_FILE = "Frameworks/LunarTear.framework/build.json"
NOTICES = "notices.zip"  # the notice pack the server reads (package_ipa.add_notices)
SETTINGS = "Data/globalgamemanagers"
# The analytics libraries' own off switches (Android's are in assemble_apk.SDK_SWITCHES).
# The game starts its ad libraries from its code; AdMob needs GADApplicationIdentifier to stay.
# FirebaseDataCollectionDefaultEnabled also stops Firebase's own diagnostics (firebaselogging-pa).
SDK_SWITCHES = {"FirebaseDataCollectionDefaultEnabled": False,
                "FIREBASE_ANALYTICS_COLLECTION_DEACTIVATED": True, "FirebaseCrashlyticsCollectionEnabled": False,
                "FirebaseMessagingAutoInitEnabled": False, "FacebookAutoInitEnabled": False,
                "FacebookAutoLogAppEventsEnabled": False, "FacebookAdvertiserIDCollectionEnabled": False}


UNITY = "Frameworks/UnityFramework.framework/UnityFramework"
# The game starts Adjust (install attribution, app.adjust.com) with +[Adjust appDidLaunch:]; it
# returns at once instead, and Adjust's other calls only log that it isn't started.
# File offset in the 3.7.1 UnityFramework: stp x22, x21, [sp, #-0x30]! -> ret.
ADJUST_SITES = ((0x18F10C4, 0xA9BD57F6, 0xD65F03C0),)


def patch_adjust(source, target):
    """Copies UnityFramework from the open file source to target with Adjust's start turned off.

    Streams the 100 MB library: on iOS this runs in the game's process. Already off is fine."""
    sites = {offset: (original, patched) for offset, original, patched in ADJUST_SITES}
    position = 0
    while True:
        chunk = bytearray(source.read(1 << 20))
        if not chunk:
            break
        for offset, (original, patched) in sites.items():
            if position <= offset and offset + 4 <= position + len(chunk):
                word = int.from_bytes(chunk[offset - position:offset - position + 4], "little")
                if word not in (original, patched):
                    raise RuntimeError(f"Unsupported game binary: expected 3.7.1 UnityFramework at 0x{offset:X}")
                chunk[offset - position:offset - position + 4] = patched.to_bytes(4, "little")
                sites[offset] = None
        target.write(chunk)
        position += len(chunk)
        sites = {k: v for k, v in sites.items() if v}
    if sites:
        raise RuntimeError("Unsupported game binary: UnityFramework is too short")


def patch_unity_connect(settings):
    """Turn off Unity Connect, which sends Unity's own analytics to cdp.cloud.unity3d.com.

    UnityConnectSettings in globalgamemanagers starts with m_Enabled and
    m_TestMode (aligned to 4 bytes), then its old event URL. Already off is fine.
    The same as assemble_apk.patch_unity_connect, which Android's build uses."""
    url = b"\x2b\x00\x00\x00https://api.uca.cloud.unity3d.com/v1/events"
    at = settings.find(url)
    if at < 4 or settings.find(url, at + 1) != -1 or settings[at - 4:at] not in (b"\x01\0\0\0", b"\0\0\0\0"):
        raise RuntimeError("Unsupported game data: expected 3.7.1 Unity Connect settings")
    return settings[:at - 4] + b"\0" + settings[at - 3:]


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _python_framework(folder):
    """Python.framework and the module frameworks build_python.py makes (they hold a .origin file)."""
    return folder.name == "Python.framework" or any(folder.glob("*.origin"))


def _replaced(relative, python_frameworks):
    parts = relative.parts
    if "_CodeSignature" in parts or relative.name == "embedded.mobileprovision":
        return True
    if parts[0] == "python":
        return True
    if len(parts) >= 2 and parts[0] == "Frameworks" and parts[1] == "LunarTear.framework":
        # The player's master data stays: release bundles never contain it.
        return not relative.name.endswith(".bin.e")
    if len(parts) >= 2 and parts[0] == "Frameworks" and parts[1] in python_frameworks:
        return True
    return False


def build_ipa(app_dir, framework_zip, python_zip, sha_framework, sha_python, output_ipa, reporter,
              notices_zip=None, sha_notices=None):
    """Writes output_ipa and returns its path; raises RuntimeError with a message for the player.

    notices_zip is the release's notice pack, downloaded only when it differs
    from the app's (Info.plist BunkerNotices); without it the app's notices.zip stays."""
    app, output = Path(app_dir), Path(output_ipa)
    reporter("Checking the download…")
    if _sha256(framework_zip) != sha_framework or _sha256(python_zip) != sha_python:
        raise RuntimeError("The download is damaged; try again")
    if notices_zip and _sha256(notices_zip) != sha_notices:
        raise RuntimeError("The download is damaged; try again")
    with zipfile.ZipFile(framework_zip) as framework:
        new_build = json.loads(framework.read("LunarTear.framework/build.json"))
    old_build = json.loads((app / GAME_PATCH_FILE).read_text()) if (app / GAME_PATCH_FILE).is_file() else {}
    if old_build.get("gamePatch") != new_build.get("gamePatch"):
        raise RuntimeError("This update needs the web builder: it changes how the game itself is patched")
    python_frameworks = {p.name for p in (app / "Frameworks").iterdir() if p.is_dir() and _python_framework(p)}
    prefix = "Payload/" + app.name + "/"
    temporary = output.with_name(output.name + ".partial")
    try:
        reporter("Building the app…")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED) as out:
            for path in sorted(app.rglob("*")):
                relative = path.relative_to(app)
                if path.is_dir() or _replaced(relative, python_frameworks):
                    continue
                if notices_zip and relative.as_posix() == NOTICES:
                    continue
                if relative.as_posix() == "Info.plist":
                    info = plistlib.loads(path.read_bytes())
                    info["BunkerVersion"] = new_build.get("version", "dev")
                    info.update(SDK_SWITCHES)  # earlier builds left them on
                    if notices_zip:
                        info["BunkerNotices"] = sha_notices
                    plist = zipfile.ZipInfo(prefix + "Info.plist")
                    plist.external_attr = 0o100644 << 16
                    out.writestr(plist, plistlib.dumps(info))
                elif path.is_symlink():
                    continue  # app bundles have none; never follow one out of the app
                elif relative.as_posix() == SETTINGS:  # earlier builds left Unity Connect on
                    settings = zipfile.ZipInfo(prefix + SETTINGS)
                    settings.external_attr = 0o100644 << 16
                    out.writestr(settings, patch_unity_connect(path.read_bytes()))
                elif relative.as_posix() == UNITY:  # earlier builds let the game start Adjust
                    unity = zipfile.ZipInfo(prefix + UNITY)
                    unity.external_attr = 0o100755 << 16
                    with path.open("rb") as source, out.open(unity, "w", force_zip64=True) as target:
                        patch_adjust(source, target)
                else:
                    out.write(path, prefix + relative.as_posix())
            if notices_zip:
                out.write(notices_zip, prefix + NOTICES)
            for bundle, base in ((framework_zip, "Frameworks/"), (python_zip, "")):
                with zipfile.ZipFile(bundle) as source:
                    for entry in source.infolist():
                        if not entry.is_dir():
                            copied = zipfile.ZipInfo(prefix + base + entry.filename, entry.date_time)
                            copied.external_attr = entry.external_attr or (0o100644 << 16)  # keeps executables executable
                            out.writestr(copied, source.read(entry))
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return str(output)
