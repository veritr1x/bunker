#!/usr/bin/env python3
"""Prepare two pinned files from a locally supplied Firebase Unity 9.6.0 archive."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile


SOURCE_URL = (
    "https://dl.google.com/games/registry/unity/com.google.firebase.app/"
    "com.google.firebase.app-9.6.0.tgz"
)
ARCHIVE_SHA256 = "0e356342d3fccabc032ba2578c0874e4e03a82b18f02ea83d1f2c0d8efde88b5"
FILES = (
    (
        "package/Firebase/Plugins/x86_64/FirebaseCppApp-9_6_0.dll",
        "FirebaseCppApp-9_6_0.dll",
        10628608,
        "f85bb9f82d79176d3d5da322780d437c023191370e608c45723ad6d83c4d1a12",
    ),
    (
        "package/LICENSE.md",
        "LICENSE.md",
        11560,
        "3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5",
    ),
)


def prepare(archive: Path, out: Path) -> dict:
    archive = archive.resolve(strict=True)
    out = out.resolve()
    if out.exists():
        raise ValueError(f"output directory must be fresh: {out}")
    payloads = []
    # Keep one input handle throughout verification and reading. Never unpack
    # archive paths, follow archive links, or use extract/extractall.
    with archive.open("rb") as source:
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise ValueError("archive SHA-256 does not match Firebase Unity 9.6.0")
        source.seek(0)
        with tarfile.open(fileobj=source, mode="r:gz") as package:
            members = package.getmembers()
            for member_name, filename, size, expected in FILES:
                selected = [member for member in members if member.name == member_name]
                if len(selected) != 1:
                    raise ValueError(f"expected exactly one archive member: {member_name}")
                member = selected[0]
                if not member.isfile() or member.size != size:
                    raise ValueError(f"unexpected member type or size: {member_name}")
                with package.extractfile(member) as stream:
                    data = stream.read(size + 1)
                if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(f"member SHA-256 does not match: {member_name}")
                payloads.append((filename, data))
    # All bytes are authenticated before creating any output.
    out.mkdir(parents=True, exist_ok=False)
    for filename, data in payloads:
        with (out / filename).open("xb") as destination:
            destination.write(data)
    receipt = {
        "source_url": SOURCE_URL,
        "archive": {"path": str(archive), "sha256": ARCHIVE_SHA256},
        "files": [
            {"member": member, "path": str(out / filename), "size": size, "sha256": sha}
            for member, filename, size, sha in FILES
        ],
    }
    with (out / "preparation.json").open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(receipt, destination, indent=2)
        destination.write("\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="already downloaded exact .tgz")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    args = parser.parse_args()
    try:
        prepare(args.archive, args.out)
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f"Firebase SDK preparation failed: {error}\n")
    print(f"Prepared pinned Firebase Windows DLL and license in {args.out.resolve()}")


if __name__ == "__main__":
    main()
