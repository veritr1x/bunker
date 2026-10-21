#!/usr/bin/env python3
"""Makes a release's files: Bunker's own bundles, update.json and the notes.

  release_assets.py --version 1.0.0 --companion-apk APK --framework DIR --python DIR --out DIR

The bundles are the ones the web builder uses (web/build_site.py): the Android
launcher, the iOS launcher framework and the iOS Tools runtime. They never hold
game files or master data. update.json lists each bundle's size and SHA-256
for the launcher's self-update, and the game patch version (build_info.py).
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "android/tools"))
import build_info  # noqa: E402
import build_site  # noqa: E402


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make(version, companion_apk, framework_dir, python_dir, out_dir, notices=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(companion_apk) as companion:
        built = companion.read(build_info.VERSION_ENTRY).decode().strip()
    framework_version = json.loads((Path(framework_dir) / "build.json").read_text())["version"]
    if built != version or framework_version != version:
        raise ValueError(f"Bundles are version {built} (Android) and {framework_version} (iOS), not {version}")
    files = {"android": f"bunker-android-{version}.zip", "iosFramework": f"bunker-ios-framework-{version}.zip",
             "iosPython": f"bunker-ios-python-{version}.zip"}
    build_site.android_bundle(companion_apk, out / files["android"])
    build_site.folder_bundle(framework_dir, out / files["iosFramework"], "LunarTear.framework/")
    build_site.folder_bundle(python_dir, out / files["iosPython"])
    assets = {}
    for key, name in files.items():
        path = out / name
        with zipfile.ZipFile(path) as bundle:
            if any(build_site.is_master(n) for n in bundle.namelist()):
                raise ValueError(f"{name} contains master data")
        assets[key] = {"name": name, "size": path.stat().st_size, "sha256": _sha256(path)}
    if notices:
        # Named by its content: launchers download it only when it changes.
        digest = _sha256(notices)
        name = f"bunker-notices-{digest[:12]}.zip"
        shutil.copyfile(notices, out / name)
        assets["notices"] = {"name": name, "size": (out / name).stat().st_size, "sha256": digest}
    update = {"version": version, "gamePatch": build_info.GAME_PATCH, "assets": assets}
    (out / "update.json").write_text(json.dumps(update, indent=1) + "\n")
    return update


def changelog_section(text, version):
    """The CHANGELOG text under "## <version> (date)", up to the previous release."""
    m = re.search(rf"^## {re.escape(version)} \(.*?\)\n(.*?)(?=^## \d+\.\d+\.\d+ \(|\Z)", text, re.S | re.M)
    if not m:
        raise ValueError(f"CHANGELOG.md has no section for {version}")
    return unwrap(m.group(1).strip())


def unwrap(text):
    """Joins the file's wrapped lines: GitHub release notes keep every line break."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        continued = out and out[-1] and not fenced and line.strip() and not out[-1].startswith(("#", "```")) \
            and not re.match(r"\s*([-*+]|\d+\.)\s|#", line)
        if continued:
            out[-1] += " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", required=True)
    p.add_argument("--companion-apk", type=Path, required=True)
    p.add_argument("--framework", type=Path, required=True)
    p.add_argument("--python", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--notices", type=Path, help="The notice pack (scripts/notices.py)")
    args = p.parse_args()
    make(args.version, args.companion_apk, args.framework, args.python, args.out, args.notices)
    notes = args.out / "notes.md"
    notes.write_text(changelog_section((ROOT / "CHANGELOG.md").read_text(), args.version) + "\n")
    print(notes)


if __name__ == "__main__":
    main()
