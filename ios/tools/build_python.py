#!/usr/bin/env python3
"""Build the Python runtime that Tools uses inside the iOS app.

  build_python.py <output-dir> [--simulator]

Writes <output-dir>/Frameworks (Python.framework and one framework per
compiled module, as iOS requires) and <output-dir>/python (standard library,
Tools code and packages). package_ipa.py merges both into the app.
Needs a host Python 3.13 (python3.13 on PATH, or uv) to cross-compile lz4
and pycryptodome against the pinned Python for iOS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PINS = json.loads((ROOT / "ios/python/native.json").read_text())
CACHE = ROOT / ".build/cache"
VERSION = "3.13"
# Not needed at runtime; the test suite alone is 35 MB.
STDLIB_SKIP = {"test", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "__phello__", "pydoc_data"}


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, expected, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists() or sha256(path) != expected:
        partial = path.with_suffix(".partial")
        print("Downloading", url)
        with urllib.request.urlopen(url) as response, open(partial, "wb") as out:
            shutil.copyfileobj(response, out)
        if sha256(partial) != expected:
            partial.unlink()
            raise SystemExit(f"Checksum mismatch for {url}")
        os.replace(partial, path)
    return path


def support():
    pin = PINS["python"]
    target = ROOT / ".build/ios-python-support"
    marker = target / ".sha256"
    if not marker.exists() or marker.read_text() != pin["sha256"]:
        archive = fetch(pin["url"], pin["sha256"], Path(pin["url"]).name)
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        with tarfile.open(archive) as source:
            source.extractall(target, filter="tar")
        marker.write_text(pin["sha256"])
    return target / "Python.xcframework"


def host_python():
    found = shutil.which("python3.13")
    if not found and shutil.which("uv"):
        result = subprocess.run(["uv", "python", "find", VERSION], capture_output=True, text=True)
        found = result.stdout.strip() if result.returncode == 0 else None
    if not found:
        raise SystemExit("Install Python 3.13 (for example: uv python install 3.13)")
    venv = ROOT / ".build/ios-python-host"
    if not (venv / "bin/python").exists():
        run(found, "-m", "venv", venv)
        run(venv / "bin/python", "-m", "pip", "install", "-q", "setuptools==80.9.0", "wheel", "setuptools_scm", "pkgconfig")
    return venv / "bin/python"


def cross_build(python, xcframework, platform, work):
    """Compile the two packages with C code; returns {relative path: built file}."""
    slice_dir = xcframework / ("ios-arm64_x86_64-simulator" if platform == "iphonesimulator" else "ios-arm64")
    target = "arm64-apple-ios13.0" + ("-simulator" if platform == "iphonesimulator" else "")
    cc = f"xcrun --sdk {platform} clang -target {target}"
    env = dict(os.environ, CC=cc, LDSHARED=f"{cc} -bundle -F{slice_dir} -framework Python",
               CFLAGS=f"-I{slice_dir}/include/python{VERSION}", ARCHFLAGS="-arch arm64",
               PYLZ4_USE_SYSTEM_LZ4="False", SETUPTOOLS_SCM_PRETEND_VERSION=PINS["packages"]["lz4"]["version"])
    built = {}
    for name, pin in PINS["packages"].items():
        sdist = fetch(f"https://files.pythonhosted.org/packages/source/{name[0]}/{name}/{name}-{pin['version']}.tar.gz",
                      pin["sha256"], f"{name}-{pin['version']}.tar.gz")
        source = work / f"{name}-{pin['version']}"
        shutil.rmtree(source, ignore_errors=True)
        with tarfile.open(sdist) as archive:
            archive.extractall(work, filter="data")
        run(python, "setup.py", "-q", "build_ext", "--inplace", cwd=source, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        package = source / ("lib/Crypto" if name == "pycryptodome" else "lz4")
        for path in package.rglob("*"):
            if path.suffix in (".c", ".h") or "__pycache__" in path.parts or "SelfTest" in path.parts or path.is_dir():
                continue
            relative = path.relative_to(package.parent)
            if path.suffix == ".so" and ".cpython-" in path.name:
                # Built with the host's suffix; iOS looks for its own.
                relative = relative.with_name(path.name.split(".")[0] + f".cpython-{VERSION.replace('.', '')}-{platform}.so")
            built[relative] = path
    return built


def make_framework(app, so_file, base, bundle_prefix):
    """Move one compiled module into Frameworks/, leaving a .fwork link (as Python's iOS testbed does)."""
    relative = so_file.relative_to(base)
    module = ".".join(relative.with_name(relative.name.split(".")[0]).parts)
    framework = app / "Frameworks" / f"{module}.framework"
    framework.mkdir(parents=True)
    shutil.move(so_file, framework / module)
    with open(framework / "Info.plist", "wb") as handle:
        plistlib.dump({"CFBundleExecutable": module, "CFBundleIdentifier": f"{bundle_prefix}.{module}".replace("_", "-"),
                       "CFBundleName": module, "CFBundlePackageType": "FMWK", "CFBundleVersion": "1",
                       "CFBundleShortVersionString": "1.0", "CFBundleSupportedPlatforms": ["iPhoneOS"],
                       "MinimumOSVersion": "13.0", "CFBundleInfoDictionaryVersion": "6.0"}, handle)
    link = so_file.with_suffix(".fwork")
    link.write_text(f"Frameworks/{module}.framework/{module}")
    (framework / f"{module}.origin").write_text(str(link.relative_to(app)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output", type=Path)
    parser.add_argument("--simulator", action="store_true", help="Build for the Apple-silicon simulator (testing only)")
    args = parser.parse_args()
    platform = "iphonesimulator" if args.simulator else "iphoneos"
    sources = ROOT / "android/app/src/main/python"
    if not (sources / "web/app.py").exists():
        raise SystemExit("Generate the Tools sources first: python3.11 scripts/prepare.py")
    xcframework = support()
    python = host_python()
    out = args.output.resolve()
    shutil.rmtree(out, ignore_errors=True)
    work = ROOT / ".build/ios-python-work"
    work.mkdir(parents=True, exist_ok=True)

    slice_dir = xcframework / ("ios-arm64_x86_64-simulator" if args.simulator else "ios-arm64")
    framework = out / "Frameworks/Python.framework"
    framework.mkdir(parents=True)
    for name in ("Python", "Info.plist"):
        shutil.copy2(slice_dir / "Python.framework" / name, framework / name)

    lib = out / f"python/lib/python{VERSION}"
    ignore = lambda directory, names: [n for n in names if n == "__pycache__" or (Path(directory) == xcframework / f"lib/python{VERSION}" and n in STDLIB_SKIP)]
    shutil.copytree(xcframework / f"lib/python{VERSION}", lib, ignore=ignore)
    shutil.copytree(slice_dir / f"lib-arm64/python{VERSION}", lib, dirs_exist_ok=True, ignore=ignore)

    app_code = out / "python/app"
    shutil.copytree(sources, app_code, ignore=shutil.ignore_patterns("__pycache__"))
    for path in (ROOT / "ios/python").glob("*.py"):
        shutil.copy2(path, app_code / path.name)

    packages = out / "python/app_packages"
    run(python, "-m", "pip", "install", "-q", "--no-deps", "--no-compile", "--target", packages,
        "-r", ROOT / "ios/python/requirements.txt", ROOT / "android/vendor/wheels/msgpack-1.1.1-py3-none-any.whl")
    # Compiled speedups were built for the Mac; pydantic and markupsafe fall back to pure Python.
    for path in list(packages.rglob("*.so")):
        path.unlink()
    shutil.rmtree(packages / "bin", ignore_errors=True)
    for relative, path in cross_build(python, xcframework, platform, work).items():
        destination = packages / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)

    bundle_prefix = "org.lunartear.python"
    for base in (lib / "lib-dynload", packages):
        for so_file in sorted(base.rglob("*.so")):
            make_framework(out, so_file, base, bundle_prefix)
    count = len(list((out / "Frameworks").glob("*.framework")))
    print(f"Built Python {VERSION} for {platform}: {count} frameworks, {out}")


if __name__ == "__main__":
    sys.exit(main())
