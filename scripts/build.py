#!/usr/bin/env python3
"""Build one offline app from your original game and master data.

Pass --apk to build the Android APK or --ipa to build the iPhone IPA.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile

from prepare import ROOT, prepare

# Gradle runs on JDK 17 or newer; Java itself is compiled with a JDK 21 toolchain (android/app/build.gradle),
# which Gradle finds or downloads, so the newest JDK works too.
OLDEST_JDK = 17
# Where a JDK is usually installed, when the java found is older than that or missing.
JDK_PLACES = [
    "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
    "/usr/local/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home",
    "/usr/lib/jvm/java-21-openjdk-amd64",
    "/usr/lib/jvm/java-21-openjdk",
    "/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home",
    "/usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home",
    "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home",
    "/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home",
    "/usr/lib/jvm/java-17-openjdk-amd64",
    "/usr/lib/jvm/java-17-openjdk",
]


def java_major(version_output):
    """The major version in `java -version` output ("21.0.5": 21, "1.8.0": 8), or None."""
    import re
    found = re.search(r'version "(\d+)(?:\.(\d+))?', version_output)
    if not found:
        return None
    major = int(found.group(1))
    return int(found.group(2) or 0) if major == 1 else major


def choose_jdk(current, candidates):
    """The JDK home to run Gradle with: None to keep the current java (17 or newer), else a candidate
    (home, major): 21 first, else the newest 17 or newer. LookupError when there is none."""
    if current is not None and current >= OLDEST_JDK:
        return None
    usable = [(home, major) for home, major in candidates if major is not None and major >= OLDEST_JDK]
    if not usable:
        raise LookupError("no JDK 17 or newer")
    return min(usable, key=lambda c: (c[1] != 21, -c[1]))[0]


def installed_jdks():
    """(home, major) for the JDKs found in the usual places and by macOS's java_home."""
    homes = []
    for version in ("21", "17+"):
        try:
            out = subprocess.run(["/usr/libexec/java_home", "-v", version], capture_output=True, text=True).stdout.strip()
        except OSError:
            out = ""
        if out:
            homes.append(out)
    homes += JDK_PLACES
    found = []
    for home in dict.fromkeys(homes):
        java = Path(home) / "bin/java"
        if java.is_file():
            out = subprocess.run([java, "-version"], capture_output=True, text=True)
            found.append((Path(home), java_major(out.stderr + out.stdout)))
    return found


def use_supported_jdk(parser, env):
    """Points JAVA_HOME and PATH at a JDK Gradle runs on (17 or newer), if the current java is older or missing."""
    java = shutil.which("java", path=env["PATH"])
    current = None
    if java:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, env=env)
        current = java_major(out.stderr + out.stdout)
    try:
        home = choose_jdk(current, installed_jdks())
    except LookupError:
        parser.error(f"The Android build needs JDK 17 or newer (this java is {current or 'missing'}). "
                     "Install one (JDK 21 is best) and set JAVA_HOME. See docs/BUILD.md.")
    if home is not None:
        print(f"Using the JDK at {home} (java {current or 'is missing'}; Gradle needs 17 or newer)")
        env["JAVA_HOME"] = str(home)
        env["PATH"] = str(home / "bin") + os.pathsep + env["PATH"]

def addresses(port_offset):
    """The game's loopback addresses (game, assets, accounts), moved by --port-offset."""
    return tuple(f"127.0.0.1:{port + port_offset}" for port in (8003, 8080, 3000))


def port_in_use(port):
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


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


def notices_args(args):
    if args.notices == ROOT / "inputs/bunker-notices.zip":
        from notices import fetch_synced
        fetch_synced()  # the pinned pack, its prices synced to the summon rules
    elif not args.notices.is_file():
        raise FileNotFoundError(f"Notice pack is missing: {args.notices}")
    return ["--notices", args.notices.resolve(strict=True)]


def build_android(args, env, python, master, sdk):
    work = ROOT / ".build"
    run(ROOT / "android/tools/build_native.sh", env=env)
    run(ROOT / "android/gradlew", "assembleDebug", "lintDebug", cwd=ROOT / "android", env=env)
    output = ROOT / "artifacts/bunker.apk"
    with tempfile.TemporaryDirectory(prefix="game-", dir=work) as temp:
        decoded = Path(temp) / "decoded"
        run("apktool", "d", args.apk, "-o", decoded, env=env)
        _, _, auth = addresses(args.port_offset)
        run(python, ROOT / "android/tools/game_patch.py", "--decoded-dir", decoded, "--game-apk", args.apk,
            "--port-offset", args.port_offset, "--auth-host", auth, env=env)
        run(python, ROOT / "android/tools/package_game.py", "--decoded-dir", decoded,
            "--companion-apk", ROOT / "android/app/build/outputs/apk/debug/app-debug.apk", "--game-apk", args.apk,
            "--output", output, "--sdk", sdk, "--keystore", args.keystore.resolve(), "--port-offset", args.port_offset,
            *notices_args(args), env=env)
    record_checksum(output)
    print(f"\nReady: {output}\nKeep your signing key: {args.keystore.resolve()}")


def build_ios(args, env, python, master):
    work = ROOT / ".build/ios"
    work.mkdir(parents=True, exist_ok=True)
    output = ROOT / "artifacts/bunker.ipa"
    with tempfile.TemporaryDirectory(prefix="game-", dir=work) as temp:
        patched = Path(temp) / "patched.ipa"
        grpc, http, auth = addresses(args.port_offset)
        run(python, ROOT / "upstream/lunar-scripts/ios/patch_ipa.py", args.ipa,
            "--grpc-addr", grpc, "--http-addr", http, "--auth-host", auth, "-o", patched, env=env)
        run(ROOT / "ios/tools/build_framework.sh", master, Path(temp) / "framework", args.master.resolve(), env=env)
        run(python, ROOT / "ios/tools/build_python.py", Path(temp) / "python", env=env)
        command = [python, ROOT / "ios/tools/package_ipa.py", "--patched-ipa", patched,
                   "--framework", Path(temp) / "framework/LunarTear.framework", "--python", Path(temp) / "python",
                   "--output", output, "--port-offset", args.port_offset, *notices_args(args)]
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
    target.add_argument("--apk", type=Path, help="Original Global (English/Korean) or Japanese ARM64 game 3.7.1 APK (builds Android)")
    target.add_argument("--ipa", type=Path, help="Original decrypted game 3.7.1 IPA (builds iPhone)")
    parser.add_argument("--master", type=Path, required=True, help="Original 20240404193219.bin.e")
    parser.add_argument("--keystore", type=Path, default=ROOT / "inputs/lunar-local.keystore", help="Android signing key")
    parser.add_argument("--bundle-id", help="iPhone: bundle ID for signing with your own Apple team. Use the same one for every build: "
                        "saves stay with the bundle ID (com.square-enix.NieRSPww, the game's own, if your profile allows it)")
    parser.add_argument("--sign-identity", help="iPhone: codesign identity; requires --profile")
    parser.add_argument("--profile", type=Path, help="iPhone: provisioning profile for --bundle-id")
    parser.add_argument("--notices", type=Path, default=ROOT / "inputs/bunker-notices.zip",
                        help="The notice pack for Notices; the default pinned pack is fetched if missing")
    parser.add_argument("--port-offset", type=int, default=0,
                        help="Move the game's local ports 8003/8080/3000 by this amount, for devices where another app uses them")
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
    if android:
        use_supported_jdk(parser, env)
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
    run(python, ROOT / "android/app/src/main/python/patcher/patch_masterdata.py", "--input", master,
        "--output", patched_master, env=env)
    env["LUNAR_TEST_MASTER"] = str(patched_master)
    # Bunker's own tests replay the live service's dates, so they read the original data.
    env["BUNKER_TEST_MASTER"] = str(Path(master).resolve())
    env["GOBIN"] = str(work / "bin")
    Path(env["GOBIN"]).mkdir(exist_ok=True)
    env["PATH"] = env["GOBIN"] + os.pathsep + env["PATH"]
    run("go", "install", "google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.11", env=env)
    run("go", "install", "google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.1", env=env)
    run("make", "proto", cwd=ROOT / "server", env=env)
    if any(port_in_use(port) for port in (8003, 8080, 3000)):
        # The server tests open the game's ports; move them past a dev server.
        print("Ports 8003/8080/3000 are in use; testing on 28003/28080/23000.")
        env["LUNAR_PORT_OFFSET"] = "20000"
    run("go", "test", "./...", cwd=ROOT / "server", env=env)
    if android:
        build_android(args, env, python, patched_master, sdk)
    else:
        build_ios(args, env, python, patched_master)


if __name__ == "__main__":
    main()
