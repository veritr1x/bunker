#!/usr/bin/env python3
"""Merge the locally built launcher/server into a user-supplied patched IPA.

Run the upstream lunar-scripts IPA patcher first. This tool adds
LunarTear.framework, makes the game executable load it at launch, enables
Finder/Files access to the app's Documents folder for the game files, adds
the Python runtime for Tools when given, and optionally signs the result. It never edits the source IPA and does not
download or distribute game files.
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import tempfile
import zipfile

MH_MAGIC_64 = 0xFEEDFACF
LC_SEGMENT_64 = 0x19
LC_LOAD_DYLIB = 0xC
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_CODE_SIGNATURE = 0x1D
LAUNCHER = "@rpath/LunarTear.framework/LunarTear"
MIN_IOS = "14.0"


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def load_commands(data):
    if struct.unpack_from("<I", data, 0)[0] != MH_MAGIC_64:
        raise RuntimeError("Expected a thin 64-bit Mach-O executable")
    ncmds, size = struct.unpack_from("<II", data, 16)
    offset, commands = 32, []
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, offset)
        commands.append((cmd, offset, cmdsize))
        offset += cmdsize
    return ncmds, size, commands


def dylibs(data):
    _, _, commands = load_commands(data)
    names = []
    for cmd, offset, cmdsize in commands:
        if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB):
            start = offset + struct.unpack_from("<I", data, offset + 8)[0]
            names.append(bytes(data[start:offset + cmdsize]).split(b"\0", 1)[0].decode())
    return names


def insert_dylib(path, name=LAUNCHER):
    """Append LC_LOAD_DYLIB using the zero padding before the first section."""
    data = bytearray(Path(path).read_bytes())
    if name in dylibs(data):
        return False
    ncmds, size, commands = load_commands(data)
    first = None
    for cmd, offset, _ in commands:
        if cmd != LC_SEGMENT_64:
            continue
        for i in range(struct.unpack_from("<I", data, offset + 64)[0]):
            section = offset + 72 + i * 80
            file_offset = struct.unpack_from("<I", data, section + 48)[0]
            length = struct.unpack_from("<Q", data, section + 40)[0]
            if file_offset and length and (first is None or file_offset < first):
                first = file_offset
    end = 32 + size
    encoded = name.encode() + b"\0"
    cmdsize = (24 + len(encoded) + 7) // 8 * 8
    if first is None or end + cmdsize > first or any(data[end:end + cmdsize]):
        raise RuntimeError("No free load-command space in the game executable")
    command = struct.pack("<IIIIII", LC_LOAD_DYLIB, cmdsize, 24, 2, 0x10000, 0x10000) + encoded
    data[end:end + cmdsize] = command.ljust(cmdsize, b"\0")
    struct.pack_into("<II", data, 16, ncmds + 1, size + cmdsize)
    Path(path).write_bytes(data)
    return True


def version_tuple(value):
    return tuple(int(part) for part in str(value).split("."))


def patch_info(app, bundle_id=None, display_name=None, port_offset=0):
    path = app / "Info.plist"
    with path.open("rb") as handle:
        info = plistlib.load(handle)
    # The launcher uses iOS 14 UIKit APIs; Go's iOS runtime also needs a recent OS.
    if version_tuple(info.get("MinimumOSVersion", "11.0")) < version_tuple(MIN_IOS):
        info["MinimumOSVersion"] = MIN_IOS
    # The player copies the prepared assets folder into Documents with Finder or Files.
    info["UIFileSharingEnabled"] = True
    info["LSSupportsOpeningDocumentsInPlace"] = True
    # The ports the game was patched for (8003/8080/3000 plus this); the launcher reads it.
    info["LunarPortOffset"] = port_offset
    if display_name:  # By default the game keeps its own name, "NieR".
        info["CFBundleDisplayName"] = display_name
    ats = info.setdefault("NSAppTransportSecurity", {})
    ats["NSAllowsArbitraryLoads"] = True
    ats["NSAllowsLocalNetworking"] = True
    if bundle_id:
        info["CFBundleIdentifier"] = bundle_id
    with path.open("wb") as handle:
        plistlib.dump(info, handle)
    return info


def add_python(app, bundle):
    """Merge Python.framework, the module frameworks and the python/ folder."""
    for framework in sorted((bundle / "Frameworks").iterdir()):
        target = app / "Frameworks" / framework.name
        if target.exists():
            raise RuntimeError(f"The game already has {framework.name}")
        shutil.copytree(framework, target)
    if (app / "python").exists():
        raise RuntimeError("The game already has a python folder")
    shutil.copytree(bundle / "python", app / "python")


def write_ipa(root, output):
    """Zip Payload/ keeping permission bits and symlinks, in pure Python (so it
    also runs in a browser)."""
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for folder, dirs, files in os.walk(root / "Payload"):
            dirs.sort()
            for name in sorted(files) + sorted(d for d in dirs if (Path(folder) / d).is_symlink()):
                path = Path(folder) / name
                info = zipfile.ZipInfo(str(path.relative_to(root)))
                if path.is_symlink():
                    info.external_attr = (0o120755 << 16)
                    archive.writestr(info, os.readlink(path))
                    continue
                info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(path, "rb") as source, archive.open(info, "w", force_zip64=True) as target:
                    shutil.copyfileobj(source, target, 1 << 20)


def profile_entitlements(profile):
    decoded = subprocess.check_output(["security", "cms", "-D", "-i", str(profile)])
    data = plistlib.loads(decoded)
    return data["Entitlements"], data.get("TeamIdentifier", [""])[0]


def sign(app, identity, profile, work):
    shutil.copy2(profile, app / "embedded.mobileprovision")
    entitlements, team = profile_entitlements(profile)
    with (app / "Info.plist").open("rb") as handle:
        bundle_id = plistlib.load(handle)["CFBundleIdentifier"]
    app_id = entitlements.get("application-identifier", "")
    if not app_id.endswith(".*") and app_id != f"{team}.{bundle_id}":
        raise RuntimeError(f"Profile is for {app_id}, but the app's bundle ID is {bundle_id}")
    entitlements["application-identifier"] = f"{team}.{bundle_id}"
    # Keep only entitlements the profile grants; the store build's keychain
    # groups and push settings belong to the publisher's team.
    path = Path(work) / "entitlements.plist"
    with path.open("wb") as handle:
        plistlib.dump(entitlements, handle)
    nested = sorted((p for p in (app / "Frameworks").iterdir() if p.suffix in (".framework", ".dylib")), key=str)
    for item in nested:
        run("codesign", "-f", "-s", identity, "--timestamp=none", item)
    run("codesign", "-f", "-s", identity, "--timestamp=none", "--entitlements", path, app)
    run("codesign", "--verify", "--deep", "--strict", app)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--patched-ipa", type=Path, required=True, help="Output of lunar-scripts ios/patch_ipa.py")
    p.add_argument("--framework", type=Path, required=True, help="Built LunarTear.framework")
    p.add_argument("--python", type=Path, help="Output of build_python.py, for Tools")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--bundle-id", help="New bundle ID, required to sign with your own team")
    p.add_argument("--sign-identity", help="codesign identity, e.g. 'Apple Development: Name (TEAM)'")
    p.add_argument("--profile", type=Path, help="Provisioning profile for --bundle-id and your device")
    p.add_argument("--port-offset", type=int, default=0, help="The port offset the IPA was patched with")
    args = p.parse_args()
    if bool(args.sign_identity) != bool(args.profile):
        p.error("--sign-identity and --profile must be used together")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ipa-") as work:
        root = Path(work) / "root"
        with zipfile.ZipFile(args.patched_ipa) as source:
            source.extractall(root)
        apps = list((root / "Payload").glob("*.app"))
        if len(apps) != 1:
            raise RuntimeError("Expected one app in Payload/")
        app = apps[0]
        # Store encryption metadata and the publisher's signature no longer apply.
        for leftover in ("SC_Info", "_CodeSignature", "embedded.mobileprovision"):
            target = app / leftover
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        frameworks = app / "Frameworks"
        destination = frameworks / "LunarTear.framework"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(args.framework, destination)
        if args.python:
            add_python(app, args.python)
        info = patch_info(app, args.bundle_id, port_offset=args.port_offset)
        executable = app / info["CFBundleExecutable"]
        print("Launcher load command", "added" if insert_dylib(executable) else "already present")
        if args.sign_identity:
            sign(app, args.sign_identity, args.profile, work)
            print("Signed for", info["CFBundleIdentifier"] if not args.bundle_id else args.bundle_id)
        else:
            print("Unsigned: sign with Sideloadly/AltStore or rerun with --sign-identity and --profile")
        temporary = output.with_suffix(".partial.ipa")
        temporary.unlink(missing_ok=True)
        write_ipa(root, temporary)
        os.replace(temporary, output)
    print("Combined IPA:", output)


if __name__ == "__main__":
    main()
