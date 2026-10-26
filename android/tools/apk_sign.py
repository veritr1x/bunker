#!/usr/bin/env python3
"""Sign an APK in place with APK Signature Scheme v2.

  apk_sign.py bunker.apk [--key KEY.pem --cert CERT.der]

Needs only pycryptodome, so the web builder can run it in the browser. By
default it uses the public Bunker build key in web/signing, which every web
build shares so that one build can update another. v2 covers every Android
version the game supports (7.0 and newer).
"""
import argparse
import hashlib
import os
from pathlib import Path
import struct

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

KEYS = Path(__file__).resolve().parents[2] / "web/signing"
CHUNK = 1 << 20
V2_BLOCK_ID = 0x7109871A
RSA_PKCS1_SHA256 = 0x0103
MAGIC = b"APK Sig Block 42"


def _prefixed(data):
    return struct.pack("<I", len(data)) + data


def _end_of_central_directory(f):
    """Offset of the end-of-central-directory record, the directory's offset and the file size."""
    size = f.seek(0, os.SEEK_END)
    f.seek(max(0, size - 65557))
    tail = f.read()
    at = tail.rfind(b"PK\x05\x06")
    if at < 0:
        raise RuntimeError("Not a ZIP file")
    eocd = size - len(tail) + at
    directory = struct.unpack_from("<I", tail, at + 16)[0]
    f.seek(directory - 16)
    if f.read(16) == MAGIC:
        raise RuntimeError("The APK is already signed")
    return eocd, directory, size


def _chunk(data):
    return hashlib.sha256(b"\xa5" + struct.pack("<I", len(data)) + data).digest()


def _combine(chunks):
    return hashlib.sha256(b"\x5a" + struct.pack("<I", len(chunks)) + b"".join(chunks)).digest()


def _section_chunks(section):
    return [_chunk(section[position:position + CHUNK]) for position in range(0, len(section), CHUNK)]


def _digest(f, entries_end, central, eocd):
    """The v2 content digest: SHA-256 over 1 MB chunks of the entries, central directory and end record."""
    chunks = []
    f.seek(0)
    for position in range(0, entries_end, CHUNK):
        chunks.append(_chunk(f.read(min(CHUNK, entries_end - position))))
    return _combine(chunks + _section_chunks(central) + _section_chunks(eocd))


def _block(digest, key_pem, cert_der):
    """The APK Signing Block with the v2 signature over digest; returns it and the certificate."""
    key = RSA.import_key(Path(key_pem).read_bytes())
    cert = Path(cert_der).read_bytes()
    signed_data = (_prefixed(_prefixed(struct.pack("<I", RSA_PKCS1_SHA256) + _prefixed(digest)))
                   + _prefixed(_prefixed(cert)) + _prefixed(b""))
    signature = pkcs1_15.new(key).sign(SHA256.new(signed_data))
    signer = (_prefixed(signed_data)
              + _prefixed(_prefixed(struct.pack("<I", RSA_PKCS1_SHA256) + _prefixed(signature)))
              + _prefixed(key.publickey().export_key("DER")))
    value = _prefixed(_prefixed(signer))
    pair = struct.pack("<QI", len(value) + 4, V2_BLOCK_ID) + value
    block_size = len(pair) + 8 + len(MAGIC)
    return struct.pack("<Q", block_size) + pair + struct.pack("<Q", block_size) + MAGIC, cert


def _moved(eocd, directory, block):
    # The block goes between the entries and the central directory, which moves after it.
    moved = bytearray(eocd)
    struct.pack_into("<I", moved, 16, directory + len(block))
    return bytes(moved)


def sign(apk, key_pem=KEYS / "bunker-key.pem", cert_der=KEYS / "bunker-cert.der"):
    with open(apk, "r+b") as f:
        eocd_at, directory, size = _end_of_central_directory(f)
        f.seek(directory)
        central = f.read(eocd_at - directory)
        eocd = f.read()
        block, cert = _block(_digest(f, directory, central, eocd), key_pem, cert_der)
        f.seek(directory)
        f.write(block + central + _moved(eocd, directory, block))
        f.truncate()
    return hashlib.sha256(cert).hexdigest()


class StreamSigner:
    """Something to write an APK to that signs it on the way: the entries pass straight
    through to out and are hashed in 1 MB chunks; finish() writes the signing block, central
    directory and end record. The result equals writing the APK to a file and sign()ing it,
    without ever holding it (assemble_apk.ApkWriter calls finish() when it closes)."""

    def __init__(self, out, key_pem=KEYS / "bunker-key.pem", cert_der=KEYS / "bunker-cert.der"):
        self.out, self.key_pem, self.cert_der = out, key_pem, cert_der
        self.position, self.chunks, self.pending = 0, [], bytearray()

    def tell(self):
        return self.position

    def write(self, data):
        self.out.write(data)
        self.position += len(data)
        self.pending += data
        while len(self.pending) >= CHUNK:
            self.chunks.append(_chunk(bytes(self.pending[:CHUNK])))
            del self.pending[:CHUNK]
        return len(data)

    def finish(self, central, eocd):
        if self.pending:
            self.chunks.append(_chunk(bytes(self.pending)))
            self.pending = bytearray()
        directory = self.position
        digest = _combine(self.chunks + _section_chunks(central) + _section_chunks(eocd))
        block, cert = _block(digest, self.key_pem, self.cert_der)
        self.out.write(block + central + _moved(eocd, directory, block))
        return hashlib.sha256(cert).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("apk", type=Path)
    p.add_argument("--key", type=Path, default=KEYS / "bunker-key.pem", help="RSA private key, PEM")
    p.add_argument("--cert", type=Path, default=KEYS / "bunker-cert.der", help="Certificate for the key, DER")
    args = p.parse_args()
    print(f"Signed {args.apk} (certificate SHA-256 {sign(args.apk, args.key, args.cert)})")


if __name__ == "__main__":
    main()
