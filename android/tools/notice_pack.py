"""The notice pack: the game's Notices for Bunker's server (notices.json and img/<key>.webp in one zip),
and the official web app the Anecdotes' panel mission page runs on (web/...).

Android APKs carry its files under assets/notices/, where the server reads them
from the installed APK; iPhone apps carry the zip itself as notices.zip.
"""
import hashlib
import re
import zipfile

PREFIX = "assets/notices/"
_NAME = re.compile(r"notices\.json|img/[A-Za-z0-9_-]+\.webp|web/(?:[A-Za-z0-9_@~-][A-Za-z0-9_.@~-]*/)*[A-Za-z0-9_@~-][A-Za-z0-9_.@~-]*")
# Already compressed: stored, so the server reads them without inflating.
_STORED = (".webp", ".png", ".jpg", ".wav")


def entries(path):
    """(APK entry name, data, compression) for each file in the pack."""
    with zipfile.ZipFile(path) as pack:
        names = [n for n in pack.namelist() if not n.endswith("/")]
        if "notices.json" not in names:
            raise ValueError(f"{path} is not a notice pack: no notices.json")
        for name in names:
            if not _NAME.fullmatch(name):
                raise ValueError(f"Unexpected file in the notice pack: {name}")
        for name in names:
            data = pack.read(name)
            stored = name.endswith(_STORED) or data[:3] == b"\xff\xd8\xff"  # sheet images are JPEGs named by hash
            yield PREFIX + name, data, zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED


def sha256(path):
    """Identifies the pack in build.json and update.json."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
