#!/usr/bin/env python3
"""Assemble the in-browser builder as a static site.

  build_site.py --companion-apk APK --framework DIR --python DIR [--output DIR]

The site holds the page, the Python build code and three bundles built from
this repository: the Android launcher, the iOS launcher framework and the iOS
Tools runtime. Master data is stripped from them; the player supplies it.
The optional Windows runtime contains translated game code. Serve the output folder over HTTP to test it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON = [
    "LICENSE",
    "web/webbuild.py",
    "android/tools/apk_sign.py",
    "android/tools/axml.py",
    "android/tools/assemble_apk.py",
    "android/tools/game_patch.py",
    "android/tools/game_fonts.py",
    "android/tools/build_info.py",
    "android/tools/notice_pack.py",
    "android/tools/privacy.py",
    "android/tools/telemetry_patches.json",
    "android/tools/telemetry_patches_jp.json",
    "android/tools/package_game.py",
    "ios/tools/package_ipa.py",
    "ios/tools/ipa_stream.py",
    "ios/python/bunker_ios_update.py",
    "ios/python/gimmick_capacity.py",
    "ios/python/remain_days.py",
    "ios/python/guerrilla_unlock.py",
    "ios/python/scroll_snap.py",
    "ios/python/text_buffer.py",
    "upstream/lunar-scripts/android/patch_apk.py",
    "upstream/lunar-scripts/ios/patch_ipa.py",
    "android/app/src/main/python/patcher/patch_masterdata.py",  # prepared: scripts/prepare.py
    "web/signing/bunker-key.pem",
    "web/signing/bunker-cert.der",
    # The letters game_fonts.py adds to the game's fonts, and their licence.
    *sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "fonts/noto").iterdir()),
]
PAGES_LIMIT = 100 * 1024 * 1024  # GitHub Pages refuses larger files.
NOTICE_PART_SIZE = 64 * 1024 * 1024
WINDOWS_FILES = {
    "compiler.mjs", "build-objects.mjs", "shard-worker.mjs", "compile-library.mjs",
    "toolchain.mjs", "translate.mjs", "apk.mjs", "game-plan.json", "heads-il2cpp.txt",
    "heads-unity.txt", "player-methods.mjs", "spring_group.entries", "liveness-edge.mjs",
    "lift.mjs", "lift.wasm", "poll.mjs", "poll.wasm", "coff.mjs", "coff.wasm", "gnu-link.mjs",
    "gnu-link.wasm", "binutils.mjs", "aarch64.bc", "link/runtime-link.json", "player.json",
    "package-exe.mjs", "player.part01", "master-worker.js", "master_digest.py", "patch_masterdata.py",
    "pyodide/pyodide.js", "pyodide/pyodide.asm.js", "pyodide/pyodide.asm.wasm",
    "pyodide/pyodide-lock.json", "pyodide/python_stdlib.zip",
}


def linux_release(path, metadata):
    pin = json.loads(path.read_bytes())
    version = pin.get("reincompVersion")
    if (not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or version != metadata.get("reincompVersion") or pin.get("bunkerVersion") != metadata["version"]
            or pin.get("asset") != f"reincomp-linux-x86_64-{version}.tar.gz"
            or not isinstance(pin.get("sha256"), str) or not re.fullmatch("[a-f0-9]{64}", pin["sha256"])
            or type(pin.get("size")) is not int or pin["size"] <= 0):
        raise ValueError("The Linux release must match the desktop browser kit and Bunker version")
    return pin


def windows_bundle(source, target, bunker_version):
    source = source.resolve(strict=True)
    manifest = json.loads((source / "kit.json").read_text(encoding="utf-8"))
    files = manifest.get("files")
    if manifest.get("format") != 1 or not isinstance(files, dict) or not WINDOWS_FILES <= files.keys():
        raise ValueError("Incomplete Windows browser compiler manifest")
    if manifest.get("bunkerVersion") != bunker_version:
        raise ValueError(f"Expected a Windows compiler kit for Bunker {bunker_version}")
    reincomp = manifest.get("reincompVersion")
    if reincomp is not None and (not isinstance(reincomp, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", reincomp)):
        raise ValueError("Invalid reincomp release version")
    for name, expected in files.items():
        path = Path(name)
        if (not name or "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts
                or path.as_posix() != name or is_master(name) or path.suffix.lower() in {".apk", ".ipa", ".so", ".bin", ".e"}):
            raise ValueError(f"Unexpected file in public Windows compiler kit: {name}")
        member = (source / path).resolve(strict=True)
        if not member.is_relative_to(source) or member.stat().st_size > PAGES_LIMIT:
            raise ValueError(f"Invalid Windows compiler file: {name}")
        with member.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError(f"Windows compiler file does not match its manifest: {name}")
        dest = target / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(member, dest)
    return reincomp


def prepared_windows_runtime(source, kit, target):
    """Copy the explicitly selected, verified Windows runtime into the site."""
    manifest = (source / "runtime.json").read_bytes()
    info = json.loads(manifest)
    kit_file = kit / "kit.json"
    if json.loads(kit_file.read_bytes()).get("preparedRuntimeFormat") != 1:
        raise ValueError("Rebuild the Windows kit with prepared runtime support")
    if info.get("format") != 1 or info.get("kitSHA256") != hashlib.sha256(kit_file.read_bytes()).hexdigest():
        raise ValueError("The prepared runtime was made for a different Windows kit")
    parts = info.get("parts")
    if not isinstance(parts, list) or not parts or not isinstance(info.get("size"), int) or info["size"] <= 0:
        raise ValueError("Incomplete prepared runtime manifest")
    chunks = info.get("chunks")
    if (not isinstance(chunks, list) or len(chunks) != (info["size"] + 4 * 1024**2 - 1) // (4 * 1024**2)
            or not all(isinstance(h, str) and re.fullmatch("[0-9a-f]{64}", h) for h in chunks)):
        raise ValueError("Invalid prepared runtime installation checksums")
    dest = target / "runtime"
    dest.mkdir()
    for i, part in enumerate(parts, 1):
        name = f"runtime.part{i:03}"
        part_file = source / name
        length = part_file.stat().st_size
        if length != part["size"] or not 0 < length <= 32 * 1024**2:
            raise ValueError(f"Invalid prepared Windows runtime part {i}")
        data = part_file.read_bytes()
        if hashlib.sha256(data).hexdigest() != part["sha256"]:
            raise ValueError(f"Invalid prepared Windows runtime part {i}")
        (dest / name).write_bytes(data)
    (dest / "runtime.json").write_bytes(manifest)
    shutil.copyfile(kit_file, target / "kit.json")
    return hashlib.sha256(manifest).hexdigest()


def is_master(name):
    return name.endswith(".bin.e")


def android_bundle(companion_apk, target):
    with zipfile.ZipFile(companion_apk) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for name in source.namelist():
            wanted = name == "AndroidManifest.xml" or re.fullmatch(r"classes\d*\.dex", name) \
                or name.startswith(("lib/arm64-v8a/", "assets/chaquopy/", "assets/lunar/"))
            if wanted and not is_master(name):
                out.writestr(name, source.read(name))


def folder_bundle(folder, target, prefix=""):
    folder = Path(folder)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and not is_master(path.name):
                out.write(path, prefix + str(path.relative_to(folder)))


def notice_bundle(source, folder, part_size=NOTICE_PART_SIZE):
    """Publish the archive in bounded files, keeping its original ZIP bytes."""
    source, folder = Path(source), Path(folder)
    if not 0 < part_size <= PAGES_LIMIT:
        raise ValueError("Notice parts must fit GitHub Pages' file limit")
    with zipfile.ZipFile(source) as archive:
        if any(is_master(name) for name in archive.namelist()):
            raise SystemExit("The notice pack contains master data")
    folder.mkdir(parents=True, exist_ok=True)
    size = source.stat().st_size
    parts = []
    with source.open("rb") as stream:
        while chunk := stream.read(part_size):
            name = "notices.zip" if size <= part_size else f"notices.zip.{len(parts) + 1:03d}"
            (folder / name).write_bytes(chunk)
            parts.append(name)
    (folder / "notices.json").write_text(json.dumps({"parts": parts, "size": size}))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--companion-apk", type=Path, required=True, help="android/app build output")
    p.add_argument("--framework", type=Path, required=True, help="LunarTear.framework from ios/tools/build_framework.sh")
    p.add_argument("--python", type=Path, required=True, help="Output of ios/tools/build_python.py")
    p.add_argument("--output", type=Path, help="Defaults to .build/site or .build/private-site for a prepared runtime")
    p.add_argument("--windows-kit", type=Path, help="Public Windows browser compiler bundle from re[in]comp")
    p.add_argument("--windows-runtime", type=Path, help="Include a matching precompiled game runtime in the output site")
    p.add_argument("--linux-release", type=Path, help="Enable the Linux build using a verified native release pin")
    p.add_argument("--notices", type=Path, default=ROOT / "inputs/bunker-notices.zip", help="Pinned notice pack (scripts/notices.py)")
    args = p.parse_args()
    local_kit = ROOT / ".build/windows-kit"
    if args.windows_kit is None and (local_kit / "kit.json").is_file():
        args.windows_kit = local_kit
    if not args.notices.is_file():
        p.error("The notice pack is missing. Run python scripts/notices.py before building the site.")
    if args.windows_runtime and not args.windows_kit:
        p.error("--windows-runtime requires a Windows compiler kit")
    default_output = ROOT / (".build/private-site" if args.windows_runtime else ".build/site")
    out = (args.output or default_output).resolve()
    if args.windows_runtime and (args.windows_runtime.resolve().is_relative_to(out) or args.windows_kit.resolve().is_relative_to(out)):
        p.error("Choose a site output outside the source kit and runtime directories")
    shutil.rmtree(out, ignore_errors=True)
    (out / "bundles").mkdir(parents=True)
    for name in ("index.html", "app_identity.js", "app.js", "worker.js", "windows-worker.js", "desktop-inputs.js", "linux-worker.js", "linux-play.sh"):
        shutil.copy2(ROOT / "web" / name, out / name)
    shutil.copy2(ROOT / "web/signing/bunker-key.p12", out / "bunker-key.p12")
    for name in PYTHON:
        target = out / "py" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (out / "py/manifest.json").write_text(json.dumps(PYTHON))
    android_bundle(args.companion_apk, out / "bundles/android.zip")
    # The version this site builds, shown in the page header.
    with zipfile.ZipFile(args.companion_apk) as companion:
        version = companion.read("assets/lunar/bunker-version.txt").decode().strip()
    metadata = {"version": version, "windows": bool(args.windows_kit)}
    if args.windows_kit:
        try:
            reincomp = windows_bundle(args.windows_kit, out / "windows", version)
            if reincomp:
                metadata["reincompVersion"] = reincomp
        except (OSError, ValueError) as error:
            p.error(str(error))
    if args.windows_runtime:
        try:
            metadata["windowsRuntime"] = prepared_windows_runtime(args.windows_runtime, args.windows_kit, out / "windows")
        except (KeyError, OSError, ValueError) as error:
            p.error(str(error))
    if args.linux_release:
        try:
            metadata["linuxRelease"] = linux_release(args.linux_release, metadata)
        except (OSError, ValueError) as error:
            p.error(str(error))
    (out / "version.json").write_text(json.dumps(metadata))
    folder_bundle(args.framework, out / "bundles/ios-framework.zip", "LunarTear.framework/")
    folder_bundle(args.python, out / "bundles/ios-python.zip")
    notice_bundle(args.notices, out / "bundles")
    for path in out.rglob("*"):
        if path.is_file() and path.stat().st_size > PAGES_LIMIT:
            raise SystemExit(f"{path.name} is over GitHub Pages' 100 MB limit")
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as bundle:
                if any(is_master(n) for n in bundle.namelist()):
                    raise SystemExit(f"{path.name} contains master data")
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"Site ready: {out} ({total / 1048576:.0f} MB). Test with: python3 -m http.server -d {out}")


if __name__ == "__main__":
    main()
