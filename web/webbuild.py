"""Browser build driver: the same Python as scripts/build.py, run in Pyodide.

The page mirrors the repository under /repo, mounts the player's own files
read-only under /input and the prebuilt bundles under /bundles. Nothing is
uploaded anywhere; everything runs in the browser.
"""
import os
import re
from pathlib import Path
import shutil
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "android/tools"))
sys.path.insert(0, str(REPO / "ios/tools"))

import apk_sign  # noqa: E402
import assemble_apk  # noqa: E402
import ipa_stream  # noqa: E402

MASTER = "20240404193219.bin.e"


def addresses(port_offset=0):
    """The game's loopback addresses (game, assets, accounts), moved by the port offset."""
    port_offset = int(port_offset)
    if not 0 <= port_offset <= 65535 - 8080:
        raise ValueError(f"Port offset must be 0–{65535 - 8080}")
    return tuple(f"127.0.0.1:{port + port_offset}" for port in (8003, 8080, 3000))


# A second copy (the builder's App ID and Name): web/app_identity.js checks the same rules
# as the player types, with the same messages; web/app_identity_cases.json holds both to them.
APP_ID_RULES = {
    "android": (re.compile(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+"), 255,
                "The App ID must be at least two parts separated by dots, each starting with a letter and using only letters, digits and _ (Android)."),
    "ios": (re.compile(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+"), 155,
            "The App ID must be at least two parts separated by dots, using only letters, digits and - (iOS)."),
}
GAME_IDS = {"com.square_enix.android_googleplay.nierspww", "com.square_enix.android_googleplay.nierspjp", "com.square-enix.nierspww"}
NAME_LIMIT = 30


def check_app_identity(platform, app_id, app_name, port_offset):
    """The App ID and Name for a second copy, trimmed (None when empty); raises ValueError with the page's message."""
    app_id, app_name = (app_id or "").strip() or None, (app_name or "").strip() or None
    if app_id:
        pattern, limit, message = APP_ID_RULES[platform]
        if len(app_id) > limit:
            raise ValueError("The App ID is too long.")
        if not pattern.fullmatch(app_id):
            raise ValueError(message)
        if app_id.lower() in GAME_IDS:
            raise ValueError("That is the game's own ID: leave the field empty for it.")
    if app_name and (len(app_name) > NAME_LIMIT or re.search(r"[\x00-\x1f\x7f]", app_name)):
        raise ValueError("The name must be 30 characters or fewer, without control characters.")
    if app_id and int(port_offset) == 0:
        raise ValueError("A second copy needs a port offset other than 0, and different from the other copy's (for example 10000).")
    return app_id, app_name


def build_android(apk, master, companion, output, log=print, port_offset=0, notices=None, app_id=None, app_name=None):
    """output is a path, or a function that takes the signed APK in pieces: it is then signed
    as it is written and never held whole (a browser keeps every file in memory)."""
    addresses(port_offset)  # Validate before the slow steps.
    app_id, app_name = check_app_identity("android", app_id, app_name, port_offset)
    if not notices or not Path(notices).is_file():
        raise ValueError("The notice pack is missing; download the builder's notices bundle before building the APK")
    notices = Path(notices)
    if callable(output):
        pieces = _Pieces(output)
        log("Signing with the public Bunker key as the APK is written…")
        assemble_apk.assemble(Path(apk), Path(master), Path(companion), apk_sign.StreamSigner(pieces), log=log,
                              port_offset=int(port_offset), notices=notices, app_id=app_id, app_name=app_name)
        pieces.flush()
    else:
        assemble_apk.assemble(Path(apk), Path(master), Path(companion), Path(output), log=log, port_offset=int(port_offset),
                              notices=notices, app_id=app_id, app_name=app_name)
        log("Signing with the public Bunker key…")
        apk_sign.sign(Path(output))
    log("Signed APK ready to install.")


class _Pieces:
    """Hands the IPA to the page's function in 4 MB pieces as it is written: it never sits whole in memory here."""

    def __init__(self, hand_over, size=4 << 20):
        self.hand_over, self.size, self.buffer = hand_over, size, bytearray()

    def write(self, data):
        self.buffer += data
        if len(self.buffer) >= self.size:
            self.flush()
        return len(data)

    def flush(self):
        if self.buffer:
            self.hand_over(bytes(self.buffer))
            self.buffer = bytearray()


def build_ios(ipa, master, framework_zip, python_zip, output, log=print, port_offset=0, notices=None, app_id=None, app_name=None):
    """Builds the unsigned IPA without unpacking the game (ipa_stream): a browser holds every file in memory.

    output is a path, or a function that takes the IPA in pieces. The bundles are
    moved into the app or deleted once unpacked."""
    grpc, http, auth = addresses(port_offset)
    app_id, app_name = check_app_identity("ios", app_id, app_name, port_offset)
    work = Path("/work/ios")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        log("Patching the game…")
        patcher = assemble_apk.load("patch_ipa", REPO / "upstream/lunar-scripts/ios/patch_ipa.py")
        # The patcher takes out only the files it and Bunker change, and keeps them instead of repacking.
        patcher.unpack_ipa = ipa_stream.extract_for_patching
        patcher.repack_ipa = shutil.move
        edited = work / "edited"
        assemble_apk.run_cli(patcher, ipa, "--grpc-addr", grpc, "--http-addr", http, "--auth-host", auth, "-o", edited)
        log("Patching master data…")
        original = Path(master).read_bytes()
        patched_master = assemble_apk.patch_master(original)
        log("Adding the launcher and Tools…")
        with zipfile.ZipFile(framework_zip) as bundle:
            bundle.extractall(work / "framework")
        os.remove(framework_zip)
        framework = work / "framework/LunarTear.framework"
        (framework / MASTER).write_bytes(patched_master)
        (framework / "original-master.bin.e").write_bytes(original)
        del original, patched_master
        with zipfile.ZipFile(python_zip) as bundle:
            bundle.extractall(work / "python")
        os.remove(python_zip)
        packager = assemble_apk.load("package_ipa", REPO / "ios/tools/package_ipa.py")
        app = next((edited / "Payload").glob("*.app"))
        packager.prepare_app(app, framework, work / "python", Path(notices) if notices else None,
                             bundle_id=app_id, port_offset=int(port_offset), move=True, display_name=app_name)
        log("Writing the IPA…")
        if callable(output):
            pieces = _Pieces(output)
            ipa_stream.write_ipa(ipa, edited, pieces)
            pieces.flush()
        else:
            with open(output, "wb") as out:
                ipa_stream.write_ipa(ipa, edited, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log("Unsigned IPA ready. Sign it with Sideloadly, AltStore or your own certificate.")
