#!/usr/bin/env python3
"""Build one offline app from your original game and master data.

Pass --apk to build the Android APK or --ipa to build the iPhone IPA.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from prepare import ROOT, prepare

GRPC, HTTP, AUTH = "127.0.0.1:8003", "127.0.0.1:8080", "127.0.0.1:3000"


def run(*args, cwd=ROOT, env=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, check=True)


def record_checksum(output):
    sums = output.parent / "SHA256SUMS"
    lines = [line for line in (sums.read_text().splitlines() if sums.exists() else []) if not line.endswith("  " + output.name)]
    lines.append(f"{hashlib.sha256(output.read_bytes()).hexdigest()}  {output.name}")
    sums.write_text("\n".join(sorted(lines, key=lambda line: line.split("  ", 1)[-1])) + "\n")


def android_sdk(parser, env):
    default_sdk = Path.home() / ("Library/Android/sdk" if os.uname().sysname == "Darwin" else "Android/Sdk")
    sdk = Path(env.get("ANDROID_HOME", default_sdk)).expanduser().resolve()
    ndk = Path(env.get("ANDROID_NDK_HOME", sdk / "ndk/27.2.12479018")).expanduser().resolve()
    for required in (sdk / "platforms/android-36/android.jar", sdk / "build-tools/36.0.0/apksigner", ndk):
        if not required.exists():
            parser.error(f"Missing Android SDK component: {required}. See docs/BUILD.md.")
    env["ANDROID_HOME"], env["ANDROID_NDK_HOME"] = str(sdk), str(ndk)
    return sdk


def build_android(args, env, python, master, sdk):
    work = ROOT / ".build"
    run(ROOT / "android/tools/build_native.sh", env=env)
    run(ROOT / "android/gradlew", "assembleDebug", "lintDebug", cwd=ROOT / "android", env=env)
    output = ROOT / "artifacts/game-Offline.apk"
    with tempfile.TemporaryDirectory(prefix="game-", dir=work) as temp:
        decoded = Path(temp) / "decoded"
        run("apktool", "d", args.apk, "-o", decoded, env=env)
        run(python, ROOT / "upstream/lunar-scripts/android/patch_apk.py", decoded,
            "--grpc-addr", GRPC, "--http-addr", HTTP, "--auth-host", AUTH, env=env)
        run(python, ROOT / "android/tools/package_game.py", "--decoded-dir", decoded,
            "--companion-apk", ROOT / "android/app/build/outputs/apk/debug/app-debug.apk",
            "--output", output, "--sdk", sdk, "--keystore", args.keystore.resolve(), env=env)
    record_checksum(output)
    print(f"\nReady: {output}\nKeep your signing key: {args.keystore.resolve()}")


def build_ios(args, env, python, master):
    work = ROOT / ".build/ios"
    work.mkdir(parents=True, exist_ok=True)
    output = ROOT / "artifacts/game-Offline.ipa"
    with tempfile.TemporaryDirectory(prefix="game-", dir=work) as temp:
        patched = Path(temp) / "patched.ipa"
        run(python, ROOT / "upstream/lunar-scripts/ios/patch_ipa.py", args.ipa,
            "--grpc-addr", GRPC, "--http-addr", HTTP, "--auth-host", AUTH, "-o", patched, env=env)
        run(ROOT / "ios/tools/build_framework.sh", master, Path(temp) / "framework", args.master.resolve(), env=env)
        run(python, ROOT / "ios/tools/build_python.py", Path(temp) / "python", env=env)
        command = [python, ROOT / "ios/tools/package_ipa.py", "--patched-ipa", patched,
                   "--framework", Path(temp) / "framework/LunarTear.framework", "--python", Path(temp) / "python",
                   "--output", output]
        if args.bundle_id:
            command += ["--bundle-id", args.bundle_id]
        if args.sign_identity:
            command += ["--sign-identity", args.sign_identity, "--profile", args.profile.resolve(strict=True)]
        run(*command, env=env)
    record_checksum(output)
    print(f"\nReady: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--apk", type=Path, help="Original ARM64 game 3.7.1 APK (builds Android)")
    target.add_argument("--ipa", type=Path, help="Original decrypted game 3.7.1 IPA (builds iPhone)")
    parser.add_argument("--master", type=Path, required=True, help="Original 20240404193219.bin.e")
    parser.add_argument("--keystore", type=Path, default=ROOT / "inputs/lunar-local.keystore", help="Android signing key")
    parser.add_argument("--bundle-id", help="iPhone: bundle ID for signing with your own Apple team")
    parser.add_argument("--sign-identity", help="iPhone: codesign identity; requires --profile")
    parser.add_argument("--profile", type=Path, help="iPhone: provisioning profile for --bundle-id")
    args = parser.parse_args()
    android = args.apk is not None
    if not android and bool(args.sign_identity) != bool(args.profile):
        parser.error("--sign-identity and --profile must be used together")
    source = (args.apk or args.ipa).resolve(strict=True)
    if android:
        args.apk = source
    else:
        args.ipa = source
    master = args.master.resolve(strict=True)
    env = os.environ.copy()
    if env.get("JAVA_HOME"):
        env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    tools = ["git", "go", "make", "protoc", "python3.11"]
    tools += ["apktool", "java", "keytool"] if android else ["xcrun", "codesign", "zip"]
    for command in tools:
        if not shutil.which(command, path=env["PATH"]):
            parser.error(f"Missing {command}. See docs/BUILD.md.")
    sdk = android_sdk(parser, env) if android else None
    if not android and subprocess.run(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"], capture_output=True).returncode:
        parser.error("Missing the iOS SDK. Install Xcode. See docs/BUILD.md.")
    prepare()
    work = ROOT / ".build"
    venv = work / "venv"
    if not (venv / "bin/python").exists():
        run("python3.11", "-m", "venv", venv, env=env)
    python = venv / "bin/python"
    run(python, "-m", "pip", "install", "-r", ROOT / "scripts/requirements-build.txt", env=env)
    if android:
        assets = ROOT / "android/app/src/main/assets/lunar"
        assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(master, assets / "original-master.bin.e")
    else:
        assets = work / "ios/master"
        assets.mkdir(parents=True, exist_ok=True)
    patched_master = assets / "20240404193219.bin.e"
    run(python, ROOT / "upstream/lunar-scripts/patch_masterdata.py", "--input", master,
        "--output", patched_master, env=env)
    env["LUNAR_TEST_MASTER"] = str(patched_master)
    env["GOBIN"] = str(work / "bin")
    Path(env["GOBIN"]).mkdir(exist_ok=True)
    env["PATH"] = env["GOBIN"] + os.pathsep + env["PATH"]
    run("go", "install", "google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.11", env=env)
    run("go", "install", "google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.1", env=env)
    run("make", "proto", cwd=ROOT / "server", env=env)
    run("go", "test", "./...", cwd=ROOT / "server", env=env)
    if android:
        build_android(args, env, python, patched_master, sdk)
    else:
        build_ios(args, env, python, patched_master)


if __name__ == "__main__":
    main()
