"""Additional Android telemetry controls for the Global 3.7.1 ARM64 client.

Manifest SDK switches and Unity Connect settings are handled by assemble_apk
and package_game. This module only removes the advertising-ID permission and the
Adjust referrer receiver, and blocks identified native SDK entry points.
"""
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import axml
from axml import Element

PATCH_FILE = Path(__file__).with_name("telemetry_patches.json")
SITES = json.loads(PATCH_FILE.read_text(encoding="utf-8"))["sites"]

TRACKING_RECEIVERS = {"com.adjust.sdk.AdjustReferrerReceiver"}
AD_PERMISSIONS = {"com.google.android.gms.permission.AD_ID"}


def harden_manifest(manifest):
    """Remove the advertising-ID permission and Adjust receiver after merging."""
    manifest.children[:] = [entry for entry in manifest.children
                            if not (isinstance(entry, Element) and entry.name == "uses-permission"
                                    and entry.get("name") and entry.get("name").raw in AD_PERMISSIONS)]
    app = manifest.find_all("application")[0]
    app.children[:] = [entry for entry in app.children
                       if not (isinstance(entry, Element) and entry.name == "receiver"
                               and entry.get("name") and entry.get("name").raw in TRACKING_RECEIVERS)]


def harden_text_manifest(path):
    """Apply the same removals in the apktool/command-line path."""
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise ValueError("Game manifest has no application")
    name_attr = "{" + axml.ANDROID_NS + "}name"
    for entry in list(root):
        if entry.tag == "uses-permission" and entry.get(name_attr) in AD_PERMISSIONS:
            root.remove(entry)
    for entry in list(app):
        if entry.tag == "receiver" and entry.get(name_attr) in TRACKING_RECEIVERS:
            app.remove(entry)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _segments(data):
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Telemetry hardening requires the Android ARM64 ELF library")
    table = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride < 56 or not count or table + stride * count > len(data):
        raise ValueError("Invalid ELF program headers")
    segments = []
    for index in range(count):
        kind, flags, offset, address, _, size, _, _ = struct.unpack_from("<IIQQQQQQ", data, table + index * stride)
        if kind == 1 and flags & 1 and offset + size <= len(data):
            segments.append((offset, address, size))
    return segments


def patch_library(data):
    """Validate every site first, then patch. Recognize our own output idempotently.

    Return a new bytearray without changing the input. Keeping the mutable buffer
    avoids another full-library copy during updates on memory-constrained phones.

    Sites were resolved with Il2CppDumper 6.7.46 from the original Global 3.7.1
    metadata; instruction guards include unchanged surrounding instructions.
    No task-returning method is replaced with null or an incomplete task.
    """
    segments = _segments(data)
    changes = []
    for site in SITES:
        expected = bytes.fromhex(site["original"])
        replacement = bytes.fromhex(site["replacement"])
        offset = next((file + site["rva"] - address for file, address, size in segments
                       if address <= site["rva"] and site["rva"] + len(expected) <= address + size), None)
        if offset is None:
            raise ValueError("Telemetry site outside executable ELF data: " + site["name"])
        actual = data[offset:offset + len(expected)]
        patched = replacement + expected[len(replacement):]
        if actual not in (expected, patched):
            raise ValueError("Unsupported game binary at telemetry site: " + site["name"])
        changes.append((offset, replacement))
    result = bytearray(data)
    for offset, replacement in changes:
        result[offset:offset + len(replacement)] = replacement
    return result
