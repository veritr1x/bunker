#!/usr/bin/env python3
"""Sign a built IPA (the web builder's, or an unsigned scripts/build.py one) for your devices.

  sign_ipa.py bunker.ipa --sign-identity 'Apple Development: Name (TEAM)' \\
      --profile team.mobileprovision [--bundle-id ID] [--output signed.ipa]

Only the bundle ID changes (when given); everything the builder set, such as
the port offset, stays. Keep the same bundle ID for every install of an app:
iOS keeps an app's saves and game files only under the ID they were made with.
Install the result with xcrun devicectl device install app --device <UDID>.
"""
import argparse
from pathlib import Path
import plistlib
import tempfile
import zipfile

from package_ipa import sign, write_ipa


def extract(ipa, root):
    """Unzips the IPA keeping file modes (zipfile drops them), so the game executable stays executable."""
    with zipfile.ZipFile(ipa) as archive:
        for info in archive.infolist():
            path = Path(archive.extract(info, root))
            mode = info.external_attr >> 16 & 0o777
            if mode and not info.is_dir():
                path.chmod(mode)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ipa", type=Path)
    p.add_argument("--sign-identity", required=True, help="codesign identity, e.g. 'Apple Development: Name (TEAM)'")
    p.add_argument("--profile", type=Path, required=True, help="Provisioning profile that covers the bundle ID and your devices")
    p.add_argument("--bundle-id", help="New bundle ID (default: keep the IPA's)")
    p.add_argument("--output", type=Path, help="Default: <name>-signed.ipa beside the IPA")
    args = p.parse_args(argv)
    output = (args.output or args.ipa.with_name(args.ipa.stem + "-signed.ipa")).resolve()
    with tempfile.TemporaryDirectory(prefix="sign-") as work:
        root = Path(work) / "root"
        extract(args.ipa, root)
        apps = list((root / "Payload").glob("*.app"))
        if len(apps) != 1:
            raise SystemExit("Expected one app in Payload/")
        app = apps[0]
        plist = app / "Info.plist"
        info = plistlib.loads(plist.read_bytes())
        if args.bundle_id:
            info["CFBundleIdentifier"] = args.bundle_id
            plist.write_bytes(plistlib.dumps(info))
        sign(app, args.sign_identity, args.profile, work)
        write_ipa(root, output)
    print(f"Signed {info['CFBundleIdentifier']}: {output}")


if __name__ == "__main__":
    main()
