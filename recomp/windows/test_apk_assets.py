"""Build the native APK asset reader and compare independent ZIP fixtures."""
import argparse
import io
from pathlib import Path
import struct
import subprocess
import tempfile
import warnings
import zipfile

HERE = Path(__file__).resolve().parent


class Streaming(io.BytesIO):
    def seekable(self):
        return False

    def seek(self, *args):
        raise io.UnsupportedOperation("non-seekable")


def archive(entries, streaming=False, comment=b""):
    data = Streaming() if streaming else io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(data, "w") as output:
            for name, body, method in entries:
                output.writestr(name, body, compress_type=method)
            output.comment = comment
    return data.getvalue()


def set16(data, offset, value):
    out = bytearray(data)
    struct.pack_into("<H", out, offset, value)
    return bytes(out)


def set32(data, offset, value):
    out = bytearray(data)
    struct.pack_into("<I", out, offset, value)
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="C:/mingw64/bin/g++.exe")
    parser.add_argument("--zlib-include", type=Path, default=HERE.parent / "work/zlib-native/zlib-1.3.2")
    parser.add_argument("--zlib-library", type=Path, default=HERE.parent / "work/zlib-native/libz-inflate.a")
    parser.add_argument("--out", type=Path, default=HERE.parent / "work/apk-assets")
    parser.add_argument("--apk", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    executable = args.out.resolve() / ("test.exe" if "mingw" in args.cxx or args.cxx.endswith(".exe") else "test")
    command = [args.cxx, "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I" + str(args.zlib_include),
               str(HERE / "apk_assets.cpp"), str(HERE / "apk_assets_test.cpp"), str(args.zlib_library), "-o", str(executable)]
    if executable.suffix == ".exe":
        command.insert(1, "-static")
    subprocess.run(command, check=True)
    checks = 0
    with tempfile.TemporaryDirectory(dir=args.out) as temporary:
        path = Path(temporary) / "test.apk"

        def check(data, name="test.bin", expected=b"", error=0):
            nonlocal checks
            path.write_bytes(data)
            result = subprocess.run([str(executable), str(path.resolve()), name], capture_output=True, timeout=15)
            assert result.returncode == error, (checks, result.returncode, error, result.stderr)
            if not error:
                assert result.stdout == expected, (checks, len(result.stdout), len(expected))
            checks += 1

        body = bytes(range(256)) * 19 + b"\0tail\xff"
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            for value in (b"", b"x", body):
                for streaming in (False, True):
                    check(archive([("assets/test.bin", value, method)], streaming), expected=value)
        check(archive([("assets/nested/日本語.bin", body, 8)]), "#unicode", body)
        check(archive([("assets/", b"", 0), ("assets/test.bin", body, 0), ("outside", b"", 0)]), expected=body)
        valid = archive([("assets/test.bin", body, 8)])
        for name in ("missing", "Test.bin", "../test.bin", "/test.bin", "a//b", "a/./b", "a/../b", "a\\b", "test.bin/", "#nul", ""):
            check(valid, name, error=10)
        check(archive([("elsewhere/test.bin", body, 0)]), error=10)
        check(archive([("assets/test.bin", body, 0), ("assets/test.bin", b"x", 0)]), error=11)
        for name in ("assets/../test.bin", "assets/a//b", "assets/a/./b"):
            check(archive([(name, body, 0)]), error=11)
        check(archive([("assets/a/b", body, 0)]).replace(b"assets/a/b", b"assets/a\\b"), error=11)
        check(archive([("assets/test.bin", body, zipfile.ZIP_BZIP2)]), error=12)
        central = valid.index(b"PK\x01\x02")
        end = valid.rindex(b"PK\x05\x06")
        for flag in (1, 0x10, 0x40, 0x2000):
            check(set16(set16(valid, 6, flag), central + 8, flag), error=12)
        for offset in (6, 8, 14, 18, 22):
            check(set16(valid, offset, 0x1234), error=11)
        bad_name = bytearray(valid); bad_name[30] ^= 1
        check(bad_name, error=11)
        for offset in (central + 20, central + 24, central + 42, end + 12, end + 16):
            check(set32(valid, offset, 0xffffffff), error=12)
        check(set16(set16(valid, end + 8, 0xffff), end + 10, 0xffff), error=12)
        check(set16(valid, end + 4, 1), error=12)
        check(set16(valid, central + 34, 1), error=11)
        check(set16(valid, end + 10, 0), error=12)
        check(set16(set16(valid, end + 8, 0), end + 10, 0), error=11)
        for cut in (1, 21, len(valid) - 1):
            check(valid[:cut], error=11)
        check(set32(valid, end + 16, central + 1), error=11)
        check(set16(valid, central + 28, 0xffff), error=11)
        check(set32(valid, central + 20, central), error=11)
        # A valid outer comment containing an EOCD-shaped false marker.
        fake = bytearray(22); struct.pack_into("<I", fake, 0, 0x06054b50)
        check(archive([("assets/test.bin", body, 8)], comment=bytes(fake)), expected=body)
        # CRC corruption with consistent metadata must fail integrity, not parse.
        wrong_crc = set32(set32(valid, 14, 123), central + 16, 123)
        check(wrong_crc, error=13)
        corrupt = bytearray(valid); corrupt[30 + len("assets/test.bin")] ^= 0xff
        check(corrupt, error=13)
        check(set32(set32(valid, 22, len(body) + 1), central + 24, len(body) + 1), error=13)
        stored = archive([("assets/test.bin", body, 0)])
        stored_central = stored.index(b"PK\x01\x02")
        check(set32(set32(stored, 22, len(body) + 1), stored_central + 24, len(body) + 1), error=11)
        # Both legal descriptor forms, then contradictory/missing descriptors.
        stream = archive([("assets/test.bin", body, 8)], streaming=True)
        descriptor = stream.index(b"PK\x07\x08")
        stream_end = stream.rindex(b"PK\x05\x06")
        no_signature = stream[:descriptor] + stream[descriptor + 4:]
        no_signature = set32(no_signature, stream_end - 4 + 16, struct.unpack_from("<I", stream, stream_end + 16)[0] - 4)
        check(no_signature, expected=body)
        check(set32(stream, descriptor + 4, 123), error=11)
        check(set32(stream, descriptor + 8, 123), error=11)
        check(set32(stream, descriptor + 12, 123), error=11)
        missing = stream[:descriptor] + stream[descriptor + 16:]
        missing = set32(missing, stream_end - 16 + 16, struct.unpack_from("<I", stream, stream_end + 16)[0] - 16)
        check(missing, error=11)
        if args.apk:
            with zipfile.ZipFile(args.apk) as original:
                expected = original.read("assets/bin/Data/boot.config")
            result = subprocess.run([str(executable), str(args.apk.resolve()), "bin/Data/boot.config"], capture_output=True, check=True)
            assert result.stdout == expected
            checks += 1
            print(f"Actual APK boot.config: {len(expected)} exact bytes, CRC32 {zipfile.crc32(expected):08x}")
    print(f"APK asset reader: {checks} independent fixture checks passed")


if __name__ == "__main__":
    main()
