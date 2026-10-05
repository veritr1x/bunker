#!/usr/bin/env python3
"""Build the offline APK by editing the original APK's files directly.

  assemble_apk.py --apk ORIGINAL.apk --master 20240404193219.bin.e \\
      --companion-apk app-release.apk --output bunker.unsigned.apk

Unlike package_game.py, this needs no apktool, Android SDK or Java, so it can
also run in a browser. It patches the game library and metadata with the
pinned lunar-scripts code, edits the compiled manifest, appends the launcher
and server from the companion APK, and writes an unsigned, aligned APK.
Sign the result yourself, for example with apksigner or uber-apk-signer.

The Facebook-login code patches need a decompiler, so they are not applied:
the game's Facebook account link is unavailable. Offline play, Tools and save
import do not use it.
"""
import argparse
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import axml  # noqa: E402
from axml import Attr, Element  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "upstream/lunar-scripts"
GRPC, HTTP = "127.0.0.1:8003", "127.0.0.1:8080"


def addresses(port_offset=0):
    """The game's loopback addresses, moved by the build's port offset."""
    if not 0 <= port_offset <= 65535 - 8080:
        raise ValueError(f"Port offset must be 0–{65535 - 8080}")
    return f"127.0.0.1:{8003 + port_offset}", f"127.0.0.1:{8080 + port_offset}"
PACKAGE = "com.square_enix.android_googleplay.nierspww"
MASTER = "20240404193219.bin.e"
LIB, METADATA = "lib/arm64-v8a/libil2cpp.so", "assets/bin/Data/Managed/Metadata/global-metadata.dat"

# Android attribute resource IDs (stable across platform versions).
NAME, VALUE, THEME, AUTHORITIES = 0x01010003, 0x01010024, 0x01010000, 0x01010018
MIN_SDK, EXTRACT_NATIVE, CLEARTEXT, PAGE_SIZE_COMPAT = 0x0101020C, 0x010104EA, 0x010104EC, 0x010106AB
THEME_MATERIAL_LIGHT_NO_ACTION_BAR = 0x01030241
PAGE_SIZE_COMPAT_ENABLED = 32


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(module, *args):
    old = sys.argv
    sys.argv = [module.__name__, *map(str, args)]
    try:
        module.main()
    except SystemExit as e:
        if e.code not in (None, 0):
            raise RuntimeError(f"{module.__name__} failed: {e.code}")
    finally:
        sys.argv = old


def patch_game_files(lib, metadata, port_offset=0):
    """Apply lunar-scripts' library and metadata patches, plus local reachability."""
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / LIB).parent.mkdir(parents=True)
        (work / METADATA).parent.mkdir(parents=True)
        (work / LIB).write_bytes(lib)
        (work / METADATA).write_bytes(metadata)
        # The upstream patcher also edits a text manifest; that change is made
        # on the binary manifest below instead.
        (work / "AndroidManifest.xml").write_text("<application >")
        grpc, http = addresses(port_offset)
        run_cli(load("patch_apk", SCRIPTS / "android/patch_apk.py"), work, "--grpc-addr", grpc, "--http-addr", http)
        load("package_game", ROOT / "android/tools/package_game.py").patch_local_reachability(work)
        return (work / LIB).read_bytes(), (work / METADATA).read_bytes()


def patch_master(original):
    with tempfile.TemporaryDirectory() as work:
        source, target = Path(work) / "in.bin.e", Path(work) / "out.bin.e"
        source.write_bytes(original)
        run_cli(load("patch_masterdata", SCRIPTS / "patch_masterdata.py"), "--input", source, "--output", target)
        return target.read_bytes()


def patch_manifest(game_manifest, companion_manifest, port_offset=0):
    doc = axml.parse(game_manifest)
    companion = axml.parse(companion_manifest).root
    manifest = doc.root
    app = manifest.find_all("application")[0]
    for sdk in manifest.find_all("uses-sdk"):
        sdk.set(Attr.integer("minSdkVersion", 28, MIN_SDK))
    # Permissions the launcher and server need, ahead of the game's own.
    have = {p.get("name").raw for p in manifest.find_all("uses-permission")}
    position = manifest.children.index(manifest.find_all("uses-sdk")[0]) + 1
    for permission in companion.find_all("uses-permission"):
        if permission.get("name").raw not in have:
            manifest.children.insert(position, permission); position += 1
    app.set(Attr.boolean("extractNativeLibs", True, EXTRACT_NATIVE))
    app.set(Attr.boolean("usesCleartextTraffic", True, CLEARTEXT))
    # The game's Unity libraries use 4 KB pages; ask Android for compatibility.
    app.set(Attr.integer("pageSizeCompat", PAGE_SIZE_COMPAT_ENABLED, PAGE_SIZE_COMPAT))
    # The launcher replaces the game's launcher entry and opens the game itself.
    game_activity = None
    for activity in app.find_all("activity") + app.find_all("activity-alias"):
        for intent in activity.find_all("intent-filter"):
            if any(c.get("name") and c.get("name").raw == "android.intent.category.LAUNCHER" for c in intent.find_all("category")):
                game_activity = activity.get("name").raw
                activity.children.remove(intent)
    if not game_activity:
        raise RuntimeError("Cannot find the game's launcher activity")
    if game_activity.startswith("."):
        game_activity = PACKAGE + game_activity
    app.children.append(Element("meta-data", [Attr.string("name", "org.veritr1x.bunker.GAME_ACTIVITY", NAME),
                                              Attr.string("value", game_activity, VALUE)]))
    # The launcher and server read the ports the game was built for.
    app.children.append(Element("meta-data", [Attr.string("name", "org.veritr1x.bunker.PORT_OFFSET", NAME),
                                              Attr.integer("value", port_offset, VALUE)]))
    for source in companion.find_all("application")[0].children:
        if isinstance(source, Element) and source.name in ("activity", "service", "provider"):
            if source.name == "activity":
                source.set(Attr.reference("theme", THEME_MATERIAL_LIGHT_NO_ACTION_BAR, THEME))
            if source.name == "provider":  # Authorities are unique per device: use the game's.
                source.set(Attr.string("authorities", PACKAGE + ".lunar_loopback", AUTHORITIES))
            app.children.append(source)
    return axml.serialize(doc), game_activity


class ApkWriter:
    """Writes an APK: unchanged entries are copied raw; stored data is 4-byte aligned."""

    def __init__(self, out):
        self.out, self.entries, self.names = out, [], set()

    def _write(self, name, method, crc, compressed, size, data, flags=0):
        if name in self.names:
            raise RuntimeError(f"Duplicate file in the APK: {name}")
        self.names.add(name)
        encoded = name.encode()
        offset = self.out.tell()
        extra = b""
        if method == 0:
            # Pad the extra field so stored data starts on a 4-byte boundary
            # (16 KB for native libraries), as zipalign does.
            align = 16384 if name.endswith(".so") else 4
            start = offset + 30 + len(encoded)
            extra = b"\0" * ((-start) % align)
        self.out.write(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flags & ~0x8, method, 0, 0x21, crc,
                                   compressed, size, len(encoded), len(extra)) + encoded + extra)
        if isinstance(data, bytes):
            self.out.write(data)
        else:
            data(self.out)
        self.entries.append((name, method, crc, compressed, size, offset, flags & ~0x8))

    def add(self, name, data, compress=True):
        crc = zlib.crc32(data)
        if compress:
            deflater = zlib.compressobj(6, zlib.DEFLATED, -15)
            packed = deflater.compress(data) + deflater.flush()
            self._write(name, 8, crc, len(packed), len(data), packed)
        else:
            self._write(name, 0, crc, len(data), len(data), data)

    def copy(self, source, info):
        """Copy an entry's compressed bytes from the source APK unchanged."""
        source.seek(info.header_offset)
        header = source.read(30)
        name_length, extra_length = struct.unpack_from("<HH", header, 26)
        start = info.header_offset + 30 + name_length + extra_length

        def stream(out):
            source.seek(start)
            left = info.compress_size
            while left:
                chunk = source.read(min(left, 1 << 20))
                out.write(chunk); left -= len(chunk)
        self._write(info.filename, info.compress_type, info.CRC, info.compress_size, info.file_size, stream, info.flag_bits)

    def close(self):
        directory = self.out.tell()
        for name, method, crc, compressed, size, offset, flags in self.entries:
            encoded = name.encode()
            self.out.write(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, flags, method, 0, 0x21, crc,
                                       compressed, size, len(encoded), 0, 0, 0, 0, 0, offset) + encoded)
        end = self.out.tell()
        count = len(self.entries)
        self.out.write(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, count, count, end - directory, directory, 0))


def assemble(apk, master, companion_apk, output, log=print, port_offset=0):
    with zipfile.ZipFile(apk) as game, zipfile.ZipFile(companion_apk) as companion, open(apk, "rb") as raw:
        names = set(game.namelist())
        for required in ("AndroidManifest.xml", LIB, METADATA, "resources.arsc"):
            if required not in names:
                raise RuntimeError(f"Not the ARM64 game APK: {required} is missing")
        log("Patching the game library and metadata…")
        lib, metadata = patch_game_files(game.read(LIB), game.read(METADATA), port_offset)
        log("Updating the manifest…")
        manifest, game_activity = patch_manifest(game.read("AndroidManifest.xml"), companion.read("AndroidManifest.xml"), port_offset)
        log("Patching master data…")
        original_master = Path(master).read_bytes()
        patched_master = patch_master(original_master)
        replaced = {"AndroidManifest.xml": manifest, LIB: lib, METADATA: metadata}
        dex = [n for n in names if re.fullmatch(r"classes\d*\.dex", n)]
        next_dex = max(int(n[7:-4] or 1) for n in dex) + 1
        temporary = Path(str(output) + ".partial")
        with open(temporary, "wb") as out:
            writer = ApkWriter(out)
            log("Writing the APK…")
            for info in game.infolist():
                name = info.filename
                # The publisher's signature no longer applies; you sign the result.
                if name.startswith("META-INF/") and re.search(r"\.(SF|RSA|DSA|EC)$|MANIFEST\.MF$", name) or name == "stamp-cert-sha256":
                    continue
                if name in replaced:
                    writer.add(name, replaced[name], compress=name != LIB or info.compress_type != 0)
                else:
                    writer.copy(raw, info)
            for name in sorted(companion.namelist(), key=lambda n: (len(n), n)):
                if re.fullmatch(r"classes\d*\.dex", name):
                    writer.add("classes%d.dex" % next_dex, companion.read(name)); next_dex += 1
            ours = {"assets/lunar/" + MASTER, "assets/lunar/original-master.bin.e", "assets/lunar/LUNAR_TEAR_LICENSE.txt"}
            for name in sorted(companion.namelist()):
                if name.startswith(("lib/arm64-v8a/", "assets/chaquopy/", "assets/lunar/")) and name not in ours:
                    writer.add(name, companion.read(name))
            writer.add("assets/lunar/" + MASTER, patched_master)
            writer.add("assets/lunar/original-master.bin.e", original_master)
            writer.add("assets/lunar/LUNAR_TEAR_LICENSE.txt", (ROOT / "LICENSE").read_bytes())
            writer.close()
        os.replace(temporary, output)
    return game_activity


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apk", type=Path, required=True, help="Original ARM64 game 3.7.1 APK")
    p.add_argument("--master", type=Path, required=True, help="Original 20240404193219.bin.e")
    p.add_argument("--companion-apk", type=Path, required=True, help="Built launcher APK (android/app)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port-offset", type=int, default=0, help="Move the game's ports 8003/8080/3000 by this amount")
    args = p.parse_args()
    game_activity = assemble(args.apk.resolve(strict=True), args.master.resolve(strict=True), args.companion_apk.resolve(strict=True),
                             args.output.resolve(), port_offset=args.port_offset)
    print(f"Unsigned APK: {args.output}\nGame activity: {game_activity}\nSign it before installing.")


if __name__ == "__main__":
    main()
