"""Bunker's launcher mark, without recompiling the game's resource table.

Keep every game resource ID and string/style index intact. A new resource type
in the game's package holds our emblem PNG; the browser and on-device updater use
the same pure Python implementation as the CLI.
"""
import struct
import base64

import axml
from axml import Attr, Document, Element

LABEL = "Bunker"
PACKAGE_ID, TYPE_ID = 0x7F, 0xFE
ICON_ID = PACKAGE_ID << 24 | TYPE_ID << 16
ICON_PATH = "res/drawable/bunker_icon.png"
LABEL_ATTR, ICON_ATTR, ROUND_ICON_ATTR = 0x01010001, 0x01010002, 0x0101052C

# Same generated emblem as the native Bunker button and launcher shortcut.
_PNG = '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'

def manifest(app):
    app.set(Attr.string("label", LABEL, LABEL_ATTR))
    app.set(Attr.reference("icon", ICON_ID, ICON_ATTR))
    app.set(Attr.reference("roundIcon", ICON_ID, ROUND_ICON_ATTR))
    # Component overrides otherwise take precedence over the application mark.
    for component in app.find_all("activity") + app.find_all("activity-alias"):
        if component.get("label"):
            component.set(Attr.string("label", LABEL, LABEL_ATTR))
        for name, resid in [("icon", ICON_ATTR), ("roundIcon", ROUND_ICON_ATTR)]:
            if component.get(name):
                component.set(Attr.reference(name, ICON_ID, resid))


def icon():
    return base64.b64decode(_PNG)


def _append_string(pool, value):
    """Append a file path without losing styled strings or moving their IDs."""
    _, header, size = struct.unpack_from("<HHI", pool)
    count, styles, flags, start, style_start = struct.unpack_from("<5I", pool, 8)
    if size != len(pool) or header < 28 or start < header + 4 * (count + styles):
        raise ValueError("Invalid Android resource string pool")
    encoded = axml._encode_pool([value], bool(flags & axml.UTF8_FLAG))
    encoded_start = struct.unpack_from("<I", encoded, 20)[0]
    added = encoded[encoded_start:]
    data_end = style_start or size
    if not start <= data_end <= size:
        raise ValueError("Invalid Android resource style offset")
    old_data = pool[start:data_end]
    strings = pool[header:header + 4 * count] + struct.pack("<I", len(old_data))
    style_offsets = pool[header + 4 * count: start]
    new_header = bytearray(pool[:header])
    struct.pack_into("<I", new_header, 4, size + 4 + len(added))
    struct.pack_into("<5I", new_header, 8, count + 1, styles, flags & ~1,
                     start + 4, style_start + 4 + len(added) if style_start else 0)
    return bytes(new_header) + strings + style_offsets + old_data + added + pool[data_end:], count


def _package(package, index):
    # Firebase uses the application's icon to discover the resource package for
    # its own strings. Keep this in the existing package, or startup fails even
    # though all original resources are present in the APK.
    header_size = struct.unpack_from("<H", package, 2)[0]
    if header_size < 288 or struct.unpack_from("<I", package, 284)[0]:
        raise ValueError("Unsupported Android resource package header")
    type_at, key_at = struct.unpack_from("<I", package, 268)[0], struct.unpack_from("<I", package, 276)[0]
    chunks, offset, type_index, key_index = [], header_size, None, None
    while offset < len(package):
        kind, header, size = struct.unpack_from("<HHI", package, offset)
        if size < header or header < 8 or offset + size > len(package):
            raise ValueError("Invalid Android resource package chunk")
        chunk = package[offset:offset + size]
        if kind in (0x0201, 0x0202) and chunk[8] == TYPE_ID:
            strings = axml._read_pool(package, type_at)[0]
            if len(strings) >= TYPE_ID and strings[TYPE_ID - 1] == "bunker_icon":
                return package
            raise ValueError("Bunker icon resource type ID is already in use")
        if offset == type_at:
            type_index = len(chunks)
        if offset == key_at:
            key_index = len(chunks)
        chunks.append(chunk)
        offset += size
    if type_index is None or key_index is None:
        raise ValueError("Missing Android resource type or key strings")
    types = chunks[type_index]
    count = len(axml._read_pool(types, 0)[0])
    if count >= TYPE_ID:
        raise ValueError("Bunker icon resource type ID is already in use")
    for i in range(count, TYPE_ID):
        types, _ = _append_string(types, "bunker_icon" if i == TYPE_ID - 1 else f"bunker_reserved_{i + 1}")
    chunks[type_index] = types
    chunks[key_index], key = _append_string(chunks[key_index], "bunker_icon")
    spec = struct.pack("<HHIBBHI", 0x0202, 16, 20, TYPE_ID, 0, 0, 1) + struct.pack("<I", 0x40000000)
    config = struct.pack("<I", 64) + bytes(60)
    entry = struct.pack("<HHI", 8, 2, key) + struct.pack("<HBBI", 8, 0, axml.TYPE_STRING, index)
    kind = struct.pack("<HHIBBHII", 0x0201, 84, 104, TYPE_ID, 0, 0, 1, 88) + config + bytes(4) + entry
    header = bytearray(package[:header_size])
    struct.pack_into("<I", header, 268, header_size + sum(map(len, chunks[:type_index])))
    struct.pack_into("<I", header, 276, header_size + sum(map(len, chunks[:key_index])))
    struct.pack_into("<I", header, 272, TYPE_ID)
    struct.pack_into("<I", header, 280, key + 1)
    body = b"".join(chunks) + spec + kind
    struct.pack_into("<I", header, 4, header_size + len(body))
    return bytes(header) + body


def resources(data):
    if len(data) < 12:
        raise ValueError("Missing Android resource table")
    kind, header, size, count = struct.unpack_from("<HHII", data)
    if kind != 0x0002 or header != 12 or size != len(data):
        raise ValueError("Invalid Android resource table")
    chunks, offset, pool_at = [], header, None
    while offset < size:
        kind, chunk_header, length = struct.unpack_from("<HHI", data, offset)
        if length < chunk_header or chunk_header < 8 or offset + length > size:
            raise ValueError("Invalid Android resource chunk")
        chunk = data[offset:offset + length]
        if kind == axml.STRING_POOL and pool_at is None:
            pool_at = len(chunks)
        chunks.append(chunk)
        offset += length
    if pool_at is None:
        raise ValueError("Android resource table has no string pool")
    strings = axml._read_pool(chunks[pool_at], 0)[0]
    if ICON_PATH in strings:
        index = strings.index(ICON_PATH)
    else:
        chunks[pool_at], index = _append_string(chunks[pool_at], ICON_PATH)
    found = False
    for i, chunk in enumerate(chunks):
        if struct.unpack_from("<H", chunk)[0] == 0x0200 and struct.unpack_from("<I", chunk, 8)[0] == PACKAGE_ID:
            chunks[i] = _package(chunk, index)
            found = True
    if not found:
        raise ValueError("Missing game's Android resource package")
    body = b"".join(chunks)
    return struct.pack("<HHII", 0x0002, 12, 12 + len(body), count) + body
