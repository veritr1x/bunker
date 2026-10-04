"""Browser build driver: the same Python as scripts/build.py, run in Pyodide.

The page mirrors the repository under /repo, mounts the player's own files
read-only under /input and the prebuilt bundles under /bundles. Nothing is
uploaded anywhere; everything runs in the browser.
"""
from pathlib import Path
import shutil
import sys
import zipfile

REPO = Path("/repo")
sys.path.insert(0, str(REPO / "android/tools"))
sys.path.insert(0, str(REPO / "ios/tools"))

import assemble_apk  # noqa: E402

MASTER = "20240404193219.bin.e"


def addresses(port_offset=0):
    """The game's loopback addresses (game, assets, accounts), moved by the port offset."""
    port_offset = int(port_offset)
    if not 0 <= port_offset <= 65535 - 8080:
        raise ValueError(f"Port offset must be 0–{65535 - 8080}")
    return tuple(f"127.0.0.1:{port + port_offset}" for port in (8003, 8080, 3000))


def build_android(apk, master, companion, output, log=print, port_offset=0):
    addresses(port_offset)  # Validate before the slow steps.
    assemble_apk.assemble(Path(apk), Path(master), Path(companion), Path(output), log=log, port_offset=int(port_offset))


def build_ios(ipa, master, framework_zip, python_zip, output, log=print, port_offset=0):
    grpc, http, auth = addresses(port_offset)
    work = Path("/work/ios")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        log("Patching the game…")
        patcher = assemble_apk.load("patch_ipa", REPO / "upstream/lunar-scripts/ios/patch_ipa.py")
        patched = work / "patched.ipa"
        assemble_apk.run_cli(patcher, ipa, "--grpc-addr", grpc, "--http-addr", http, "--auth-host", auth, "-o", patched)
        log("Patching master data…")
        original = Path(master).read_bytes()
        patched_master = assemble_apk.patch_master(original)
        log("Adding the launcher and Tools…")
        with zipfile.ZipFile(framework_zip) as bundle:
            bundle.extractall(work / "framework")
        framework = work / "framework/LunarTear.framework"
        (framework / MASTER).write_bytes(patched_master)
        (framework / "original-master.bin.e").write_bytes(original)
        with zipfile.ZipFile(python_zip) as bundle:
            bundle.extractall(work / "python")
        log("Writing the IPA…")
        packager = assemble_apk.load("package_ipa", REPO / "ios/tools/package_ipa.py")
        assemble_apk.run_cli(packager, "--patched-ipa", patched, "--framework", framework,
                             "--python", work / "python", "--output", output, "--port-offset", str(int(port_offset)))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    log(f"Unsigned IPA ready. Sign it with Sideloadly, AltStore or your own certificate.")
