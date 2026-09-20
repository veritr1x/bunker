#!/usr/bin/env python3
"""Build one offline APK from your original game APK and master data."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from prepare import ROOT, prepare


def run(*args, cwd=ROOT, env=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True, help="Original ARM64 game 3.7.1 APK")
    parser.add_argument("--master", type=Path, required=True, help="Original 20240404193219.bin.e")
    parser.add_argument("--keystore", type=Path, default=ROOT / "inputs/lunar-local.keystore")
    args = parser.parse_args()
    apk, master = args.apk.resolve(strict=True), args.master.resolve(strict=True)
    env = os.environ.copy()
    if env.get("JAVA_HOME"):
        env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    for command in ("git", "go", "make", "protoc", "apktool", "java", "keytool", "python3.11"):
        if not shutil.which(command, path=env["PATH"]):
            parser.error(f"Missing {command}. See docs/BUILD.md.")
    default_sdk = Path.home() / ("Library/Android/sdk" if os.uname().sysname == "Darwin" else "Android/Sdk")
    sdk = Path(env.get("ANDROID_HOME", default_sdk)).expanduser().resolve()
    ndk = Path(env.get("ANDROID_NDK_HOME", sdk / "ndk/27.2.12479018")).expanduser().resolve()
    for required in (sdk / "platforms/android-36/android.jar", sdk / "build-tools/36.0.0/apksigner", ndk):
        if not required.exists():
            parser.error(f"Missing Android SDK component: {required}. See docs/BUILD.md.")
    env["ANDROID_HOME"], env["ANDROID_NDK_HOME"] = str(sdk), str(ndk)
    prepare()
    work = ROOT / ".build"
    venv = work / "venv"
    if not (venv / "bin/python").exists():
        run("python3.11", "-m", "venv", venv, env=env)
    python = venv / "bin/python"
    run(python, "-m", "pip", "install", "-r", ROOT / "scripts/requirements-build.txt", env=env)
    assets = ROOT / "android/app/src/main/assets/lunar"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(master, assets / "original-master.bin.e")
    run(python, ROOT / "upstream/lunar-scripts/patch_masterdata.py", "--input", master,
        "--output", assets / "20240404193219.bin.e", env=env)
    env["LUNAR_TEST_MASTER"] = str(assets / "20240404193219.bin.e")
    env["GOBIN"] = str(work / "bin")
    Path(env["GOBIN"]).mkdir(exist_ok=True)
    env["PATH"] = env["GOBIN"] + os.pathsep + env["PATH"]
    run("go", "install", "google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.11", env=env)
    run("go", "install", "google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.1", env=env)
    run("make", "proto", cwd=ROOT / "server", env=env)
    run("go", "test", "./...", cwd=ROOT / "server", env=env)
    run(ROOT / "android/tools/build_native.sh", env=env)
    run(ROOT / "android/gradlew", "assembleDebug", "lintDebug", cwd=ROOT / "android", env=env)
    output = ROOT / "artifacts/NieR-Offline-arm64.apk"
    with tempfile.TemporaryDirectory(prefix="game-", dir=work) as temp:
        decoded = Path(temp) / "decoded"
        run("apktool", "d", apk, "-o", decoded, env=env)
        run(python, ROOT / "upstream/lunar-scripts/android/patch_apk.py", decoded,
            "--grpc-addr", "127.0.0.1:8003", "--http-addr", "127.0.0.1:8080",
            "--auth-host", "127.0.0.1:3000", env=env)
        run(python, ROOT / "android/tools/package_game.py", "--decoded-dir", decoded,
            "--companion-apk", ROOT / "android/app/build/outputs/apk/debug/app-debug.apk",
            "--output", output, "--sdk", sdk, "--keystore", args.keystore.resolve(), env=env)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.parent / "SHA256SUMS").write_text(f"{checksum}  {output.name}\n")
    print(f"\nReady: {output}\nKeep your signing key: {args.keystore.resolve()}")


if __name__ == "__main__":
    main()
