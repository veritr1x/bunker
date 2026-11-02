"""Checked Android 3.7.1 patches shared by the CLI and the Pyodide builder.

Profiles identify the original library AND metadata, not an APK filename or
language label. Korean/English is the global nierspww client. Japanese has a
separate method layout. Do not pass regional binaries to the upstream patcher's
global-only, unchecked RVA writer.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import zipfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

LIB = "lib/arm64-v8a/libil2cpp.so"
METADATA = "assets/bin/Data/Managed/Metadata/global-metadata.dat"
PACKAGE_PREFIX = "com.square_enix.android_googleplay.niersp"

# RVAs resolved with Il2CppDumper 6.7.46 against each hash-pinned pair.
# The three interior purchase sites were also compared instruction by
# instruction, including their branch destinations (see docs/ANDROID-REGIONS.md).
PROFILES = {
    "global": {
        "label": "Global (English/Korean)", "package": PACKAGE_PREFIX + "ww", "domain": "com",
        "lib_sha256": "ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522",
        "metadata_sha256": "7ae75b594082b3a603a82f68d497d6c3aea30881b94496b2c11d8de71f8321d2",
        "rvas": (0x35C8670, 0x279410C, 0x279420C, 0x4C27038, 0x2831CA8,
                 0x282CE78, 0x2834028, 0x2831CAC, 0x2830834, 0x2F11900,
                 0x361D54C, 0x2DEAF68, 0x2E1B278, 0x4910D4C, 0x361D500),
    },
    "jp": {
        "label": "Japanese", "package": PACKAGE_PREFIX + "jp", "domain": "jp",
        "lib_sha256": "37a0335eb3eef53610c0cfab41ee4e210d5f1eb363d3ddd417845996e2643cda",
        "metadata_sha256": "6004b4008cbe633b4391f8c86327564e337995a1336e4f35c98e1cc849acc048",
        "rvas": (0x3622514, 0x274AC64, 0x274AD64, 0x4B55B5C, 0x2839CCC,
                 0x2834E9C, 0x283C04C, 0x2839CD0, 0x2838858, 0x304F32C,
                 0x366B620, 0x2DB90CC, 0x2DFBCB4, 0x4883AB0, 0x366B5D4),
    },
}

# name, replacement. The three port overrides are supplied per build.
PATCHES = (
    ("gRPC credentials", "000080d2c0035fd6"),
    ("request encryption", "e00301aac0035fd6"),
    ("response decryption", "e00301aac0035fd6"),
    ("Octo plain list", "000080d2c0035fd6"),
    ("purchase initialization check", "1f2003d5"),
    ("store product availability", "20008052c0035fd6"),
    ("null store cancellation", "751600b4"),
    ("purchase alert", "19000014"),
    ("purchase initialization wait", "1f2003d5"),
    ("title menu after service end", "c0035fd6"),
    ("gRPC port", None), ("conductor port", None), ("calculator port", None),
    ("offline reachability", "40008052c0035fd6"),
    # NetworkConfig's serialized _serverAddress overrides the metadata default
    # in the JP APK. Fall through to Config.Api's patched loopback host even
    # when that asset field is populated. The original is TBZ W0, #0, +0x30.
    ("serialized API host override", "1f2003d5"),
)


def profile_for_manifest(package, version):
    if version != "3.7.1":
        raise RuntimeError("Choose an original 3.7.1 ARM64 APK")
    for name, profile in PROFILES.items():
        if package == profile["package"]:
            return name
    raise RuntimeError(f"Unsupported game package: {package}")


def identify(lib, metadata, expected=None):
    hashes = hashlib.sha256(lib).hexdigest(), hashlib.sha256(metadata).hexdigest()
    return identify_hashes(*hashes, expected)


def identify_hashes(lib_hash, metadata_hash, expected=None):
    hashes = lib_hash, metadata_hash
    for name, profile in PROFILES.items():
        if hashes == (profile["lib_sha256"], profile["metadata_sha256"]):
            if expected is not None and name != expected:
                raise RuntimeError("APK manifest and game binaries belong to different regions")
            return name
    raise RuntimeError("Unsupported game binaries: choose an original Global (English/Korean) or Japanese 3.7.1 ARM64 APK")


def elf_offset(data, rva, size):
    """Map a code RVA through executable, file-backed ELF64 PT_LOAD data."""
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise RuntimeError("Expected the Android ARM64 game library")
    table = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride < 56 or table + stride * count > len(data):
        raise RuntimeError("Invalid game ELF program headers")
    for i in range(count):
        kind, flags, start, address, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", data, table + i * stride)
        if kind == 1 and flags & 1 and address <= rva and rva + size <= address + length:
            offset = start + rva - address
            if offset + size <= len(data):
                return offset
    raise RuntimeError(f"Game patch at 0x{rva:X} is outside executable ELF data")


def patch_library(lib, profile, port_offset=0):
    if not isinstance(port_offset, int) or not 0 <= port_offset <= 65535 - 8080:
        raise ValueError("Port offset must be a whole number from 0 to 57455")
    # This function is also public: never allow a guessed profile/RVA write.
    if hashlib.sha256(lib).hexdigest() != PROFILES[profile]["lib_sha256"]:
        raise RuntimeError("Unsupported original game library for " + profile)
    data = bytearray(lib)
    port = 8003 + port_offset
    # Patch get_OriginalServerPort, not its four-byte get_ServerPort branch
    # wrapper: an eight-byte replacement there would corrupt the next getter.
    overrides = (struct.pack("<II", 0x52800000 | port << 5, 0xD65F03C0),
                 struct.pack("<I", 0x52800002 | port << 5),
                 struct.pack("<I", 0x52800014 | port << 5))
    for i, ((_, replacement), rva) in enumerate(zip(PATCHES, PROFILES[profile]["rvas"])):
        code = overrides[i - 10] if 10 <= i <= 12 else bytes.fromhex(replacement)
        offset = elf_offset(data, rva, len(code))
        data[offset:offset + len(code)] = code
    return bytes(data)


def patch_library_file(path, profile, port_offset=0):
    """Check and patch where the library lies, without a full-library memory copy."""
    with open(path, "r+b") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
        if digest.hexdigest() != PROFILES[profile]["lib_sha256"]:
            raise RuntimeError("Unsupported original game library for " + profile)
        handle.seek(0)
        header = handle.read(64)
        table = struct.unpack_from("<Q", header, 32)[0]
        stride, count = struct.unpack_from("<HH", header, 54)
        handle.seek(0)
        headers = handle.read(table + stride * count)
        size = handle.seek(0, 2)
        if not isinstance(port_offset, int) or not 0 <= port_offset <= 57455:
            raise ValueError("Port offset must be a whole number from 0 to 57455")
        port = 8003 + port_offset
        overrides = (struct.pack("<II", 0x52800000 | port << 5, 0xD65F03C0),
                     struct.pack("<I", 0x52800002 | port << 5), struct.pack("<I", 0x52800014 | port << 5))
        for i, ((_, replacement), rva) in enumerate(zip(PATCHES, PROFILES[profile]["rvas"])):
            code = overrides[i - 10] if 10 <= i <= 12 else bytes.fromhex(replacement)
            offset = None
            for segment in range(count):
                kind, flags, start, address, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", headers, table + segment * stride)
                if kind == 1 and flags & 1 and address <= rva and rva + len(code) <= address + length:
                    offset = start + rva - address
                    break
            if offset is None or offset + len(code) > size:
                raise RuntimeError("Game patch outside executable ELF data")
            handle.seek(offset)
            handle.write(code)


def patch_metadata(metadata, profile, port_offset=0):
    """Rewrite whole string literals, including JP's credential-bearing web URL.

    Credentials are neither needed for loopback nor copied into diagnostics.
    Never search for a substring inside the blob: a literal's length/table
    reference must agree, and every required endpoint must be present.
    """
    if len(metadata) < 24 or struct.unpack_from("<II", metadata) != (0xFAB11BAF, 24):
        raise RuntimeError("Unsupported game metadata header")
    table, table_size, blob, blob_size = struct.unpack_from("<4I", metadata, 8)
    if table_size % 8 or table + table_size > len(metadata) or blob + blob_size > len(metadata):
        raise RuntimeError("Invalid game metadata string sections")
    suffix = "app.nierreincarnation." + PROFILES[profile]["domain"]
    http = f"http://127.0.0.1:{8080 + port_offset}"
    data, found = bytearray(metadata), set()
    for at in range(table, table + table_size, 8):
        length, index = struct.unpack_from("<II", metadata, at)
        if index + length > blob_size:
            raise RuntimeError("Invalid game metadata string literal")
        raw = metadata[blob + index:blob + index + length]
        if raw == ("api." + suffix).encode():
            kind, new = "grpc", b"127.0.0.1"
        elif raw.startswith(b"https://"):
            # Only interpret endpoint literals. Other game strings can be arbitrary bytes.
            try:
                url = urlsplit(raw.decode("utf-8"))
                if url.query or url.fragment or url.port is not None:
                    continue
                if url.hostname == "web." + suffix and url.path in ("", "/"):
                    kind, new = "web", (http + url.path).encode()
                elif url.hostname == "web." + suffix and url.path == "/assets/release/{0}/database.bin":
                    kind, new = "master", (http + url.path).encode()
                elif url.hostname == "resources-api." + suffix and url.path == "/":
                    kind, new = "resources", (http + "/").encode()
                else:
                    continue
            except (UnicodeDecodeError, ValueError):
                continue
        else:
            continue
        if len(new) > length:
            raise RuntimeError("Loopback endpoint does not fit game metadata")
        data[blob + index:blob + index + length] = new + bytes(length - len(new))
        struct.pack_into("<I", data, at, len(new))
        found.add(kind)
    if found != {"grpc", "web", "master", "resources"}:
        raise RuntimeError("Missing regional game endpoints: " + ", ".join(sorted({"grpc", "web", "master", "resources"} - found)))
    return bytes(data)


def patch_files(lib, metadata, port_offset=0, expected=None):
    profile = identify(lib, metadata, expected)
    patched_lib = patch_library(lib, profile, port_offset)
    return patched_lib, patch_metadata(metadata, profile, port_offset)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decoded-dir", type=Path, required=True)
    p.add_argument("--game-apk", type=Path, required=True, help="Original APK (apktool may remove the decoded version attributes)")
    p.add_argument("--port-offset", type=int, default=0)
    p.add_argument("--auth-host", help="CLI only: also redirect decompiled Facebook login")
    args = p.parse_args()
    game = args.decoded_dir
    import axml
    with zipfile.ZipFile(args.game_apk) as original:
        manifest = axml.parse(original.read("AndroidManifest.xml")).root
    profile = profile_for_manifest(manifest.get("package", ns=None).raw, manifest.get("versionName").raw)
    if ET.parse(game / "AndroidManifest.xml").getroot().get("package") != PROFILES[profile]["package"]:
        raise RuntimeError("Decoded directory and original APK belong to different regions")
    lib, metadata = patch_files((game / LIB).read_bytes(), (game / METADATA).read_bytes(), args.port_offset, profile)
    (game / LIB).write_bytes(lib)
    (game / METADATA).write_bytes(metadata)
    # Keep upstream's decompiler-dependent Facebook patches, never its RVA writer.
    import assemble_apk
    upstream = assemble_apk.load("patch_apk", assemble_apk.SCRIPTS / "android/patch_apk.py")
    upstream.patch_manifest(str(game / "AndroidManifest.xml"))
    upstream.create_network_security_config(str(game / "res/xml"))
    if args.auth_host:
        upstream.patch_facebook_smali(str(game), args.auth_host)
        upstream.bypass_cct_redirect_check(str(game))
        upstream.force_webview_only_login_behavior(str(game))
        upstream.patch_customtab_use_plain_view_intent(str(game))
        upstream.patch_webdialog_request_overload(str(game))
    print("Patched " + PROFILES[profile]["label"] + " 3.7.1 for loopback")


if __name__ == "__main__":
    main()
