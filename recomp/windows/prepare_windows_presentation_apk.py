#!/usr/bin/env python3
"""Reproduce the verified data-only Windows presentation APK from one pinned input."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

SOURCE_SHA256 = "36e15676053734a225f55bdf89acd375adaf298872d4d1dfc06c140e5a0ed394"
ASSET_SHA256 = "bd9fb9a8c4e9680d7fa7cfe1dfebe99e7fd6b21aa41b90fcb5c039fc9448d9b8"
OUTPUT_SHA256 = "fd0d0d357a4e8c316d0e732783d795f0e100a675d0c7a0fcf252873deb84f538"
RECORD_SHA256 = "26e1818f9a57caf8e66bd0e2e960d9d7d7d02750ba779dc9f2b300f1007ed5c7"
ASSET = "assets/bin/Data/globalgamemanagers"
FIELD_OFFSET = 219900
RECORD_START, RECORD_BYTES = 219600, 636
ENTRY_COUNT = 4968


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def descriptor(path):
    return {"path": str(path.resolve()), "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}


def prepare(source, output_dir):
    require(source.is_file(), "Input APK does not exist")
    require(not output_dir.exists(), "Output directory must be fresh")
    original = source.read_bytes()
    require(digest(original) == SOURCE_SHA256, "Input is not the exact qualified audio-disabled APK")
    with zipfile.ZipFile(source) as old:
        infos = old.infolist()
        require(len(infos) == ENTRY_COUNT == len({i.filename for i in infos}), "Unexpected ZIP entry inventory")
        target = old.getinfo(ASSET)
        asset = old.read(target)
        require(len(asset) == 20495308 and digest(asset) == ASSET_SHA256, "Unexpected globalgamemanagers")
        require(digest(asset[RECORD_START:RECORD_START + RECORD_BYTES]) == RECORD_SHA256, "Unexpected PlayerSettings")
        require(asset[FIELD_OFFSET] == 1 and asset[223600] == 1, "Unexpected Swappy/audio settings")
        changed = asset[:FIELD_OFFSET] + b"\0" + asset[FIELD_OFFSET + 1:]
        require(sum(a != b for a, b in zip(asset, changed)) == 1, "Mutation is not exactly one byte")
        require(target.flag_bits == 0 and target.compress_type == 8, "Unsupported target ZIP encoding")

        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        compressed = compressor.compress(changed) + compressor.flush()
        crc = zlib.crc32(changed) & 0xffffffff
        at = target.header_offset
        sig, _, flags, method, _, _, old_crc, old_compressed, old_size, name_size, extra_size = struct.unpack_from(
            "<4s5H3I2H", original, at)
        require(sig == b"PK\x03\x04" and flags == 0 and method == 8, "Unexpected local header")
        require((old_crc, old_compressed, old_size) == (target.CRC, target.compress_size, len(asset)), "Local header mismatch")
        data_at = at + 30 + name_size + extra_size
        require(original[at + 30:at + 30 + name_size].decode() == ASSET, "Wrong local member")
        old_end = data_at + old_compressed
        delta = len(compressed) - old_compressed
        local_header = bytearray(original[at:data_at])
        struct.pack_into("<III", local_header, 14, crc, len(compressed), len(changed))

        central = old.start_dir
        eocd = original.rfind(b"PK\x05\x06")
        require(eocd >= 0, "EOCD missing")
        _, disk, central_disk, n1, n2, central_bytes, central_offset, comment_bytes = struct.unpack_from(
            "<4s4H2IH", original, eocd)
        require(disk == central_disk == 0 and n1 == n2 == ENTRY_COUNT, "Unsupported ZIP layout")
        require(central_offset == central and central + central_bytes == eocd, "Unexpected central directory")
        require(eocd + 22 + comment_bytes == len(original), "Unexpected ZIP tail")
        directory = bytearray(original[central:eocd])
        position = hits = shifted = 0
        for _ in range(n2):
            require(directory[position:position + 4] == b"PK\x01\x02", "Bad central header")
            name_len, extra_len, comment_len = struct.unpack_from("<3H", directory, position + 28)
            name = bytes(directory[position + 46:position + 46 + name_len]).decode()
            local = struct.unpack_from("<I", directory, position + 42)[0]
            if name == ASSET:
                require(local == at, "Target central/local mismatch")
                struct.pack_into("<III", directory, position + 16, crc, len(compressed), len(changed))
                hits += 1
            if local > at:
                struct.pack_into("<I", directory, position + 42, local + delta)
                shifted += 1
            position += 46 + name_len + extra_len + comment_len
        require(position == len(directory) and hits == 1, "Unexpected directory traversal")
        tail = bytearray(original[eocd:])
        struct.pack_into("<I", tail, 16, central + delta)
        derived = original[:at] + local_header + compressed + original[old_end:central] + directory + tail
        require(len(derived) == len(original) + delta, "Unexpected output size")
        require(digest(derived) == OUTPUT_SHA256,
                "Compressor/output differs from the qualified APK; no output written")

        # Verify logical entry contents and exact raw non-target local records before publication.
        import io
        rows = []
        with zipfile.ZipFile(io.BytesIO(derived)) as new:
            require([i.filename for i in new.infolist()] == [i.filename for i in infos], "Entry order changed")
            require(new.comment == old.comment, "ZIP comment changed")
            for info in infos:
                current = new.getinfo(info.filename)
                before, after = old.read(info), new.read(current)
                require(after == (changed if info.filename == ASSET else before), "Unexpected entry mutation")
                if info.filename != ASSET:
                    name_len, extra_len = struct.unpack_from("<HH", original, info.header_offset + 26)
                    length = 30 + name_len + extra_len + info.compress_size
                    require(derived[current.header_offset:current.header_offset + length]
                            == original[info.header_offset:info.header_offset + length], "Non-target local bytes changed")
                for key in ("filename", "date_time", "compress_type", "comment", "extra", "create_system",
                            "create_version", "extract_version", "flag_bits", "volume", "internal_attr",
                            "external_attr", "file_size"):
                    require(getattr(info, key) == getattr(current, key), "Unexpected entry metadata mutation")
                rows.append({"name": info.filename, "bytes": len(before), "old_sha256": digest(before),
                             "new_sha256": digest(after), "uncompressed_byte_exact": before == after})
        require(sum(not row["uncompressed_byte_exact"] for row in rows) == 1, "Wrong changed-entry count")
    require(digest(source.read_bytes()) == SOURCE_SHA256, "Input changed during preparation")

    output_dir.mkdir(parents=True)
    apk = output_dir / "game-audio-disabled-swappy-disabled.apk"
    apk.write_bytes(derived)
    inventory = output_dir / "zip-entry-verification.json"
    inventory.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "passed": True,
        "scope": "Exact-pinned, data-only Windows presentation configuration; no game launch",
        "source_apk": descriptor(source), "derived_apk": descriptor(apk), "asset_name": ASSET,
        "original_asset_sha256": ASSET_SHA256, "derived_asset_sha256": digest(changed),
        "mutation": {"field": "PlayerSettings.androidUseSwappy", "path_id": 1, "class_id": 129,
                     "object_byte_start": RECORD_START, "object_byte_size": RECORD_BYTES,
                     "object_field_offset": 300, "asset_byte_offset": FIELD_OFFSET,
                     "old": 1, "new": 0, "changed_asset_bytes": 1},
        "entry_count": ENTRY_COUNT, "uncompressed_entries_changed": 1,
        "all_other_uncompressed_entries_exact": True,
        "non_target_local_records_and_compressed_bytes_preserved": True,
        "DEX_and_native_entries_uncompressed_byte_exact": True,
        "existing_audio_disabled_byte_preserved": True, "source_apk_unchanged": True,
        "target_compressed_delta": delta, "central_offsets_shifted": shifted,
        "zip_entry_verification": descriptor(inventory), "producer": descriptor(Path(__file__)),
        "qualified_output_sha256": OUTPUT_SHA256,
        "field_provenance": "Unity2019.4.29f1 class129/path1: pinned UnityPy1.25.4 named type tree, Python reader position, exact no-op writer and one-byte named-field write; original reader maps androidUseSwappy to PlayerSettings+0x41e. See windows_presentation.md.",
        "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
        "Android_installable_or_signature_valid_claimed": False,
        "limits": "Native-port input only. Retained signing metadata does not authenticate modified data. No original code/predicate patch, game launch, swap or frame claim. This script intentionally rejects other APKs and compressor outputs."
    }
    (output_dir / "acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-apk", type=Path, required=True, help="Exact qualified audio-disabled APK")
    parser.add_argument("--out", type=Path, required=True, help="Fresh output directory")
    args = parser.parse_args()
    result = prepare(args.source_apk.resolve(), args.out.resolve())
    print(json.dumps({"derived_apk": result["derived_apk"], "receipt": str(args.out.resolve() / "acceptance.json")}))


if __name__ == "__main__":
    main()
