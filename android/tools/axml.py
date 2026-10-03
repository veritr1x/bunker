"""Read and write Android's binary XML (AXML), as used by AndroidManifest.xml.

Enough to edit a compiled manifest without apktool or aapt2: elements,
attributes (with typed values), namespaces and text. Pure Python, so it also
runs in the browser under Pyodide.
"""
import struct

ANDROID_NS = "http://schemas.android.com/apk/res/android"

RES_XML = 0x0003
STRING_POOL = 0x0001
RESOURCE_MAP = 0x0180
NS_START, NS_END, ELEM_START, ELEM_END, CDATA = 0x0100, 0x0101, 0x0102, 0x0103, 0x0104
NO_INDEX = 0xFFFFFFFF
UTF8_FLAG = 0x100

# Typed value kinds used in manifests.
TYPE_REFERENCE, TYPE_STRING, TYPE_INT_DEC, TYPE_INT_HEX, TYPE_INT_BOOLEAN = 0x01, 0x03, 0x10, 0x11, 0x12


class Attr:
    def __init__(self, name, ns=ANDROID_NS, resid=0, raw=None, type=TYPE_STRING, data=0):
        self.ns, self.name, self.resid, self.raw, self.type, self.data = ns, name, resid, raw, type, data

    @classmethod
    def string(cls, name, value, resid):
        return cls(name, resid=resid, raw=value, type=TYPE_STRING)

    @classmethod
    def boolean(cls, name, value, resid):
        return cls(name, resid=resid, type=TYPE_INT_BOOLEAN, data=0xFFFFFFFF if value else 0)

    @classmethod
    def integer(cls, name, value, resid, hex=False):
        return cls(name, resid=resid, type=TYPE_INT_HEX if hex else TYPE_INT_DEC, data=value & 0xFFFFFFFF)

    @classmethod
    def reference(cls, name, value, resid):
        return cls(name, resid=resid, type=TYPE_REFERENCE, data=value)


class Element:
    def __init__(self, name, attrs=(), children=(), ns=None, line=0):
        self.ns, self.name, self.attrs, self.children, self.line = ns, name, list(attrs), list(children), line
        self.text = []  # CDATA nodes kept in order, as (index among children, text, typed)

    def get(self, name, ns=ANDROID_NS):
        for a in self.attrs:
            if a.name == name and a.ns == ns:
                return a
        return None

    def set(self, attr):
        old = self.get(attr.name, attr.ns)
        if old:
            self.attrs[self.attrs.index(old)] = attr
        else:
            self.attrs.append(attr)

    def find_all(self, name):
        return [c for c in self.children if isinstance(c, Element) and c.name == name]

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, Element):
                yield from c.iter()


class Document:
    def __init__(self, root, namespaces):
        self.root, self.namespaces = root, namespaces  # namespaces: [(prefix, uri, line)]


def _read_pool(data, off):
    _, header_size, size = struct.unpack_from("<HHI", data, off)
    count, _, flags, strings_start, _ = struct.unpack_from("<IIIII", data, off + 8)
    offsets = struct.unpack_from("<%dI" % count, data, off + header_size)
    base = off + strings_start
    strings = []
    for o in offsets:
        p = base + o
        if flags & UTF8_FLAG:
            n = data[p]; p += 2 if n & 0x80 else 1  # character count, then byte count
            n = data[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | data[p + 1]; p += 2
            else:
                p += 1
            strings.append(bytes(data[p:p + n]).decode("utf-8"))
        else:
            n = struct.unpack_from("<H", data, p)[0]; p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", data, p)[0]; p += 2
            strings.append(bytes(data[p:p + 2 * n]).decode("utf-16-le"))
    return strings, flags, size


def parse(data):
    data = bytes(data)
    kind, header_size, total = struct.unpack_from("<HHI", data, 0)
    if kind != RES_XML:
        raise ValueError("Not a binary XML file")
    off, strings, ids, utf8 = header_size, [], [], False
    stack, root, namespaces = [], None, []
    while off < total:
        kind, header_size, size = struct.unpack_from("<HHI", data, off)
        if kind == STRING_POOL:
            strings, flags, _ = _read_pool(data, off)
            utf8 = bool(flags & UTF8_FLAG)
        elif kind == RESOURCE_MAP:
            ids = list(struct.unpack_from("<%dI" % ((size - header_size) // 4), data, off + header_size))
        elif kind in (NS_START, NS_END, ELEM_START, ELEM_END, CDATA):
            line = struct.unpack_from("<I", data, off + 8)[0]
            body = off + header_size
            s = lambda i: None if i == NO_INDEX else strings[i]
            if kind == NS_START:
                prefix, uri = struct.unpack_from("<II", data, body)
                namespaces.append((s(prefix), s(uri), line))
            elif kind == ELEM_START:
                ns, name, attr_start, attr_size, count = struct.unpack_from("<IIHHH", data, body)
                el = Element(s(name), ns=s(ns), line=line)
                for i in range(count):
                    a = body + attr_start + i * attr_size
                    ans, aname, raw, _, _, dtype, value = struct.unpack_from("<IIIHBBI", data, a)
                    el.attrs.append(Attr(s(aname), ns=s(ans), resid=ids[aname] if aname < len(ids) else 0,
                                         raw=s(raw), type=dtype, data=value))
                (stack[-1].children if stack else []).append(el)
                if not stack:
                    root = el
                stack.append(el)
            elif kind == ELEM_END:
                stack.pop()
            elif kind == CDATA:
                text = s(struct.unpack_from("<I", data, body)[0])
                stack[-1].children.append(text)
        off += size
    doc = Document(root, namespaces)
    doc.utf8 = utf8
    return doc


def _encode_pool(strings, utf8):
    blobs, offsets, pos = [], [], 0
    for s in strings:
        if utf8:
            raw = s.encode("utf-8")
            def length(n):
                return bytes([n]) if n < 0x80 else bytes([0x80 | (n >> 8), n & 0xFF])
            blob = length(len(s)) + length(len(raw)) + raw + b"\0"
        else:
            raw = s.encode("utf-16-le")
            n = len(raw) // 2
            blob = (struct.pack("<H", n) if n < 0x8000 else struct.pack("<HH", 0x8000 | (n >> 16), n & 0xFFFF)) + raw + b"\0\0"
        offsets.append(pos); blobs.append(blob); pos += len(blob)
    data = b"".join(blobs)
    data += b"\0" * (-len(data) % 4)
    header = 28
    strings_start = header + 4 * len(strings)
    size = strings_start + len(data)
    return struct.pack("<HHIIIIII", STRING_POOL, header, size, len(strings), 0, UTF8_FLAG if utf8 else 0, strings_start, 0) \
        + struct.pack("<%dI" % len(strings), *offsets) + data


def serialize(doc):
    """Encode a Document. Attributes are sorted by resource ID, as Android expects."""
    # Attribute names with resource IDs come first, matching the resource map.
    res_names, others = [], []
    for el in doc.root.iter():
        el.attrs.sort(key=lambda a: (a.resid == 0, a.resid))
        for a in el.attrs:
            if a.resid and (a.name, a.resid) not in res_names:
                res_names.append((a.name, a.resid))
    index = {}
    strings = []
    for name, resid in res_names:
        index[(name, resid)] = len(strings); strings.append(name)

    def ref(s):
        if s is None:
            return NO_INDEX
        if s not in index:
            index[s] = len(strings); strings.append(s)
        return index[s]

    chunks = []

    def node(kind, line, body):
        chunks.append(struct.pack("<HHIII", kind, 16, 16 + len(body), line, NO_INDEX) + body)

    for prefix, uri, line in doc.namespaces:
        node(NS_START, line, struct.pack("<II", ref(prefix), ref(uri)))

    def element(el):
        attrs = b""
        id_index = class_index = style_index = 0
        for i, a in enumerate(el.attrs, 1):
            name = index[(a.name, a.resid)] if a.resid else ref(a.name)
            raw = ref(a.raw) if a.raw is not None else NO_INDEX
            value = raw if a.type == TYPE_STRING else a.data
            attrs += struct.pack("<IIIHBBI", ref(a.ns), name, raw, 8, 0, a.type, value)
            if a.ns is None and a.name == "id": id_index = i
            if a.ns is None and a.name == "class": class_index = i
            if a.ns is None and a.name == "style": style_index = i
        node(ELEM_START, el.line, struct.pack("<IIHHHHHH", ref(el.ns), ref(el.name), 20, 20, len(el.attrs),
                                             id_index, class_index, style_index) + attrs)
        for c in el.children:
            if isinstance(c, Element):
                element(c)
            else:
                node(CDATA, el.line, struct.pack("<IHBBI", ref(c), 8, 0, TYPE_STRING, ref(c)))
        node(ELEM_END, el.line, struct.pack("<II", ref(el.ns), ref(el.name)))

    element(doc.root)
    for prefix, uri, line in reversed(doc.namespaces):
        node(NS_END, line, struct.pack("<II", ref(prefix), ref(uri)))

    pool = _encode_pool(strings, getattr(doc, "utf8", False))
    resmap = struct.pack("<HHI", RESOURCE_MAP, 8, 8 + 4 * len(res_names)) + struct.pack("<%dI" % len(res_names), *(r for _, r in res_names))
    body = pool + resmap + b"".join(chunks)
    return struct.pack("<HHI", RES_XML, 8, 8 + len(body)) + body
