"""Build the IPA without unpacking the game: the browser build keeps every file in memory.

The patches change only a few files of the 460 MB app. extract_for_patching
takes those out; after they are patched and Bunker's files are added beside
them, write_ipa writes the IPA front to back: the changed and added files from
that folder, every other entry copied from the game's IPA as it is, without
recompressing it. Nothing is ever seeked back, so the output can go straight to
the page as it is written.
"""
import os
from pathlib import Path
import plistlib
import stat
import struct
import time
import zipfile
import zlib

# What the store build carries that no longer applies once the app is changed.
LEFTOVERS = ("SC_Info", "_CodeSignature", "embedded.mobileprovision")

# Files of NieR.app the upstream patcher (lunar-scripts ios/patch_ipa.py) and
# package_ipa.prepare_app change, besides the game executable.
PATCHED = (
    "Info.plist",
    "Data/Managed/Metadata/global-metadata.dat",
    "Data/globalgamemanagers",
    "Frameworks/UnityFramework.framework/UnityFramework",
    "Frameworks/FBSDKCoreKit.framework/FBSDKCoreKit",
    "Frameworks/FBSDKLoginKit.framework/FBSDKLoginKit",
    "Frameworks/FBAEMKit.framework/FBAEMKit",
)

CHUNK = 1 << 20


def app_prefix(archive):
    """The one Payload/<name>.app/ folder in the IPA."""
    apps = {n.split("/")[1] for n in archive.namelist() if n.startswith("Payload/") and n.count("/") >= 2}
    apps = [a for a in apps if a.endswith(".app")]
    if len(apps) != 1:
        raise RuntimeError("Expected one app in Payload/")
    return f"Payload/{apps[0]}/"


def extract_for_patching(ipa, dest):
    """Extracts the files the patches change into dest, keeping their paths and modes."""
    dest = Path(dest)
    with zipfile.ZipFile(ipa) as archive:
        app = app_prefix(archive)
        info = plistlib.loads(archive.read(app + "Info.plist"))
        names = set(archive.namelist())
        for name in (*PATCHED, info["CFBundleExecutable"]):
            if app + name not in names:
                continue
            target = dest / (app + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(app + name) as source, open(target, "wb") as out:
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    out.write(chunk)
            mode = archive.getinfo(app + name).external_attr >> 16 & 0o777
            if mode:
                target.chmod(mode)


def dos_time(timestamp):
    t = time.localtime(timestamp)
    return (t.tm_hour << 11 | t.tm_min << 5 | t.tm_sec // 2,
            max(t.tm_year - 1980, 0) << 9 | t.tm_mon << 5 | t.tm_mday)


class _Writer:
    """A zip writer that only appends: unchanged entries go in raw, new ones are deflated in chunks."""

    def __init__(self, out):
        self.out, self.offset, self.entries = out, 0, []

    def _put(self, data):
        self.out.write(data)
        self.offset += len(data)

    def _check(self, *values):
        if any(v >= 0xFFFFFFFF for v in values) or len(self.entries) >= 0xFFFF:
            raise RuntimeError("The IPA is too large for a plain zip")

    def copy(self, raw, info):
        """The entry's stored bytes from the source archive, with its sizes moved into the header."""
        raw.seek(info.header_offset)
        header = raw.read(30)
        if header[:4] != b"PK\x03\x04":
            raise RuntimeError(f"Damaged IPA entry: {info.filename}")
        name_length, extra_length = struct.unpack_from("<HH", header, 26)
        start = info.header_offset + 30 + name_length + extra_length
        self._check(info.compress_size, info.file_size, self.offset)
        name = info.filename.encode()
        flags = info.flag_bits & ~0x8
        offset = self.offset
        dostime, dosdate = (info.date_time[3] << 11 | info.date_time[4] << 5 | info.date_time[5] // 2,
                            (info.date_time[0] - 1980) << 9 | info.date_time[1] << 5 | info.date_time[2])
        self._put(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flags, info.compress_type, dostime, dosdate,
                              info.CRC, info.compress_size, info.file_size, len(name), 0) + name)
        raw.seek(start)
        left = info.compress_size
        while left:
            chunk = raw.read(min(left, CHUNK))
            if not chunk:
                raise RuntimeError(f"Damaged IPA entry: {info.filename}")
            self._put(chunk)
            left -= len(chunk)
        self.entries.append((name, flags, info.compress_type, dostime, dosdate, info.CRC,
                             info.compress_size, info.file_size, info.external_attr, offset))

    def add(self, name, path, mode):
        """A file from disk, deflated in chunks; its CRC and sizes follow it in a data descriptor."""
        name = name.encode()
        offset = self.offset
        dostime, dosdate = dos_time(os.lstat(path).st_mtime)
        if stat.S_ISLNK(mode):
            data = os.readlink(path).encode()
            crc = zlib.crc32(data)
            self._put(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, 0, dostime, dosdate,
                                  crc, len(data), len(data), len(name), 0) + name + data)
            self.entries.append((name, 0, 0, dostime, dosdate, crc, len(data), len(data), mode << 16, offset))
            return
        flags = 0x8
        self._put(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flags, 8, dostime, dosdate, 0, 0, 0, len(name), 0) + name)
        deflater = zlib.compressobj(6, zlib.DEFLATED, -15)
        crc = size = packed = 0
        with open(path, "rb") as source:
            for chunk in iter(lambda: source.read(CHUNK), b""):
                crc = zlib.crc32(chunk, crc)
                size += len(chunk)
                data = deflater.compress(chunk)
                packed += len(data)
                self._put(data)
        data = deflater.flush()
        packed += len(data)
        self._put(data)
        self._check(size, packed, offset)
        self._put(struct.pack("<IIII", 0x08074B50, crc, packed, size))
        self.entries.append((name, flags, 8, dostime, dosdate, crc, packed, size, mode << 16, offset))

    def close(self):
        directory = self.offset
        for name, flags, method, dostime, dosdate, crc, packed, size, attributes, offset in self.entries:
            self._put(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 0x0314, 20, flags, method, dostime, dosdate,
                                  crc, packed, size, len(name), 0, 0, 0, 0, attributes, offset) + name)
        self._check(directory, self.offset)
        count = len(self.entries)
        self._put(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, self.offset - directory, directory, 0))


def write_ipa(source_ipa, edited, out):
    """Writes the IPA to out (anything with write): source_ipa's entries, with every file under
    edited replacing or added to them. The app's LEFTOVERS and folder entries are left out.
    Returns the number of bytes written."""
    edited = Path(edited)
    files = {}
    for folder, dirs, names in os.walk(edited):
        dirs.sort()
        for name in sorted(names) + sorted(d for d in dirs if (Path(folder) / d).is_symlink()):
            path = Path(folder) / name
            files[path.relative_to(edited).as_posix()] = path
    writer = _Writer(out)
    with zipfile.ZipFile(source_ipa) as archive, open(source_ipa, "rb") as raw:
        app = app_prefix(archive)
        for info in archive.infolist():
            name = info.filename
            inside = name[len(app):] if name.startswith(app) else ""
            if name.endswith("/") or inside.split("/")[0] in LEFTOVERS:
                continue
            path = files.pop(name, None)
            if path is None:
                writer.copy(raw, info)
            else:
                writer.add(name, path, info.external_attr >> 16 or os.lstat(path).st_mode)
    for name, path in files.items():
        writer.add(name, path, os.lstat(path).st_mode)
    writer.close()
    return writer.offset
