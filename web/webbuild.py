"""Browser build driver: the same Python as scripts/build.py, run in Pyodide.

The page mirrors the repository under /repo, mounts the player's own files
read-only under /input and the prebuilt bundles under /bundles. Nothing is
uploaded anywhere; everything runs in the browser.
"""
import os
from pathlib import Path
import shutil
import sys
import zipfile

REPO = Path("/repo")
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


def build_android(apk, master, companion, output, log=print, port_offset=0, notices=None):
    addresses(port_offset)  # Validate before the slow steps.
    assemble_apk.assemble(Path(apk), Path(master), Path(companion), Path(output), log=log, port_offset=int(port_offset),
                          notices=Path(notices) if notices else None)
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


def build_ios(ipa, master, framework_zip, python_zip, output, log=print, port_offset=0, notices=None):
    """Builds the unsigned IPA without unpacking the game (ipa_stream): a browser holds every file in memory.

    output is a path, or a function that takes the IPA in pieces. The bundles are
    moved into the app or deleted once unpacked."""
    grpc, http, auth = addresses(port_offset)
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
                             port_offset=int(port_offset), move=True)
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
