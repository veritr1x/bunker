"""Builds the next Bunker APK on the device from the installed one and a release bundle.

The launcher (Updater.java) downloads the release's Android bundle and calls
build_android; the result is signed with the public Bunker key, like a web
build, so it installs over the running app. The build tools come from
android/tools (copied into bunker_tools by build_native.sh).
"""
import hashlib
from pathlib import Path
import sys


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tools():
    # The copied tools import each other by plain name (axml, build_info).
    import bunker_tools
    folder = str(Path(bunker_tools.__path__[0]))
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import apk_sign
    import assemble_apk
    return assemble_apk, apk_sign


def build_android(installed, bundle_zip, expected_sha256, work_dir, key_pem, cert_der, reporter,
                  notices_zip=None, notices_sha256=None):
    """Returns the path of the signed APK; raises RuntimeError with a message for the player.

    notices_zip is the release's notice pack, downloaded only when it differs
    from the installed one; without it the installed notices stay."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    reporter("Checking the download…")
    if _sha256(bundle_zip) != expected_sha256:
        raise RuntimeError("The download is damaged; try again")
    if notices_zip and _sha256(notices_zip) != notices_sha256:
        raise RuntimeError("The download is damaged; try again")
    assemble_apk, apk_sign = _tools()
    output = work / "bunker-update.apk"
    reporter("Building…")
    assemble_apk.update(Path(installed), Path(bundle_zip), output, log=reporter,
                        notices=Path(notices_zip) if notices_zip else None)
    reporter("Signing…")
    apk_sign.sign(output, key_pem, cert_der)
    return str(output)
