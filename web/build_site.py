#!/usr/bin/env python3
"""Assemble the in-browser builder as a static site.

  build_site.py --companion-apk APK --framework DIR --python DIR [--output DIR]

The site holds the page, the Python build code and three bundles built from
this repository: the Android launcher, the iOS launcher framework and the iOS
Tools runtime. Master data is stripped from them; the player supplies it.
No game files are included. Serve the output folder over HTTP to test it.
"""
import argparse
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
    "android/tools/package_game.py",
    "ios/tools/package_ipa.py",
    "upstream/lunar-scripts/android/patch_apk.py",
    "upstream/lunar-scripts/ios/patch_ipa.py",
    "upstream/lunar-scripts/patch_masterdata.py",
    "web/signing/bunker-key.pem",
    "web/signing/bunker-cert.der",
]
PAGES_LIMIT = 100 * 1024 * 1024  # GitHub Pages refuses larger files.


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


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--companion-apk", type=Path, required=True, help="android/app build output")
    p.add_argument("--framework", type=Path, required=True, help="LunarTear.framework from ios/tools/build_framework.sh")
    p.add_argument("--python", type=Path, required=True, help="Output of ios/tools/build_python.py")
    p.add_argument("--output", type=Path, default=ROOT / ".build/site")
    args = p.parse_args()
    out = args.output.resolve()
    shutil.rmtree(out, ignore_errors=True)
    (out / "bundles").mkdir(parents=True)
    for name in ("index.html", "app.js", "worker.js"):
        shutil.copy2(ROOT / "web" / name, out / name)
    shutil.copy2(ROOT / "web/signing/bunker-key.p12", out / "bunker-key.p12")
    for name in PYTHON:
        target = out / "py" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    (out / "py/manifest.json").write_text(json.dumps(PYTHON))
    android_bundle(args.companion_apk, out / "bundles/android.zip")
    folder_bundle(args.framework, out / "bundles/ios-framework.zip", "LunarTear.framework/")
    folder_bundle(args.python, out / "bundles/ios-python.zip")
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
