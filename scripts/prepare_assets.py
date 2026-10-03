#!/usr/bin/env python3
"""Copy revision 0 of an extracted dump into a ready assets folder (optional).

The apps' own import already copies only revision 0 from an extracted dump, so
this is needed only to make a smaller folder to copy, or one to drag into the
iOS app with Finder (which skips the app's import). The tested dumps have their
complete resource set in revision 0; the other revisions are old catalogs this
pinned server never reads. The input is only read; the output must be a new
directory.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile


def prepare_assets(source, output):
    source = source.resolve(strict=True)
    if (source / "assets/revisions").is_dir():
        source = source / "assets"
    revision = source / "revisions/0"
    if not (revision / "list.bin").is_file() and not (revision / "android/list.bin").is_file():
        raise ValueError("Select the extracted assets directory containing revisions/0/list.bin")
    if not any(revision.rglob("*.assetbundle")):
        raise ValueError("Revision 0 has no asset bundles")
    # A different dump may rely on historical revisions; do not silently omit them.
    for info in revision.rglob("info.json"):
        aliases = json.loads(info.read_text())
        if any(str(item.get("to-revision", 0)) != "0" for item in aliases):
            raise ValueError(f"{info} refers to another revision; this dump needs separate preparation")
    output = output.resolve()
    if output == source or source in output.parents:
        raise ValueError("Choose an output outside the extracted source")
    if output.exists():
        raise FileExistsError(f"Choose a new output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    print("Copying game files. This may take several minutes…", flush=True)
    with tempfile.TemporaryDirectory(prefix=".assets-", dir=output.parent) as temp:
        stage = Path(temp) / "assets"
        stage.mkdir()
        (stage / ".nomedia").touch()
        shutil.copytree(revision, stage / "revisions/0")
        if output.exists():
            raise FileExistsError(f"Output appeared while copying: {output}")
        stage.rename(output)
    # The APK supplies master data on first launch; no release folder is needed.
    print(f"Ready: choose {output} in the launcher.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("phone-assets/assets"))
    args = parser.parse_args()
    prepare_assets(args.source, args.output)
