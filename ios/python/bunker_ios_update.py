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
                    if notices_zip:
                        info["BunkerNotices"] = sha_notices
                    plist = zipfile.ZipInfo(prefix + "Info.plist")
                    plist.external_attr = 0o100644 << 16
                    out.writestr(plist, plistlib.dumps(info))
                elif path.is_symlink():
                    continue  # app bundles have none; never follow one out of the app
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
