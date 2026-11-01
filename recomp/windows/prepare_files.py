"""Prepare real APK byte-range and NDK-layout evidence for Windows file tests."""
import argparse
import binascii
import hashlib
import json
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path, required=True)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=HERE.parent / 'work/windows-files')
    parser.add_argument('--lift', type=Path, help='Also prepare translated ARM64 NDK callers for Windows')
    parser.add_argument('--cxx', default='clang++')
    parser.add_argument('--aapt', type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.apk) as apk:
        assets = [entry for entry in apk.infolist() if entry.filename.startswith('assets/') and entry.compress_size and entry.compress_size <= 4 * 1024 * 1024 and not entry.flag_bits & 1]
        if not assets:
            raise RuntimeError('No small asset sample found in real APK')
        selected = next((entry for entry in assets if entry.compress_type == zipfile.ZIP_STORED), assets[0])
    with args.apk.open('rb') as source:
        source.seek(selected.header_offset)
        local = source.read(30)
        if local[:4] != b'PK\x03\x04':
            raise RuntimeError('Invalid local ZIP header')
        name_length, extra_length = struct.unpack_from('<HH', local, 26)
        offset = selected.header_offset + 30 + name_length + extra_length
        source.seek(offset)
        sample = source.read(selected.compress_size)
    expected = {'apk_size': args.apk.stat().st_size, 'asset': selected.filename,
                'compression': selected.compress_type, 'offset': offset, 'length': len(sample),
                'crc32_raw': binascii.crc32(sample), 'apk_sha256': hashlib.sha256(args.apk.read_bytes()).hexdigest()}
    aapt = args.aapt
    if aapt is None:
        candidates = sorted((args.ndk.parent.parent / 'build-tools').glob('*/aapt'))
        if not candidates:
            raise RuntimeError('Pass --aapt or install Android SDK build-tools to verify real APK Java metadata')
        aapt = candidates[-1]
    badging = subprocess.check_output([str(aapt), 'dump', 'badging', str(args.apk)], text=True)
    expected['package_name'] = re.search(r"^package: name='([^']+)'", badging, re.M).group(1)
    expected['target_sdk'] = int(re.search(r"^targetSdkVersion:'(\d+)'", badging, re.M).group(1))
    expected['launch_activity'] = re.search(r"^launchable-activity: name='([^']+)'", badging, re.M).group(1).replace('.', '/')
    if selected.compress_type == zipfile.ZIP_STORED and expected['crc32_raw'] != selected.CRC:
        raise RuntimeError('Stored ZIP member CRC does not match actual raw bytes')
    shutil.copyfile(args.apk, out / 'base.apk')
    storage = out / 'sandbox'
    storage.mkdir(exist_ok=True)
    (storage / 'bytes.bin').write_bytes(bytes((i * 37 + 11) & 255 for i in range(1000)))
    (storage / 'empty.bin').write_bytes(b'')
    (out / 'sample.json').write_text(json.dumps(expected, indent=2) + '\n')
    (out / 'sample.h').write_text(
        f'static constexpr uint64_t kApkSize = {expected["apk_size"]}ULL;\n'
        f'static constexpr uint64_t kAssetOffset = {offset}ULL;\n'
        f'static constexpr uint64_t kAssetLength = {len(sample)}ULL;\n'
        f'static constexpr uint32_t kAssetCrc = {expected["crc32_raw"]}U;\n'
        f'static constexpr const char *kAssetName = {json.dumps(selected.filename)};\n'
        f'static constexpr const char16_t *kPackageName = u{json.dumps(expected["package_name"])};\n'
        f'static constexpr int32_t kTargetSdk = {expected["target_sdk"]};\n'
        f'static constexpr const char *kLaunchActivity = {json.dumps(expected["launch_activity"])};\n')
    probe = out / 'ndk_layout.c'
    labels = ['stat_size', 'stat_size_offset', 'stat_atime_offset', 'stat_mtime_offset', 'stat_ctime_offset',
              'off_t_size', 'long_size', 'o_directory', 'o_nofollow', 'o_largefile', 'o_cloexec', 'legacy_file_size']
    probe.write_text('#include <stdint.h>\n#include <stddef.h>\n#include <sys/stat.h>\n#include <fcntl.h>\n#include <bits/struct_file.h>\n'
        'const uint64_t ndk_layout[] = {sizeof(struct stat), offsetof(struct stat, st_size), '
        'offsetof(struct stat, st_atim), offsetof(struct stat, st_mtim), offsetof(struct stat, st_ctim), '
        'sizeof(off_t), sizeof(long), O_DIRECTORY, O_NOFOLLOW, O_LARGEFILE, O_CLOEXEC, sizeof(struct __sFILE)};\n')
    compiler = args.ndk / 'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang'
    obj = out / 'ndk_layout.o'
    subprocess.run([str(compiler), '-c', str(probe), '-o', str(obj)], check=True)
    with obj.open('rb') as source:
        elf = ELFFile(source)
        symbol = elf.get_section_by_name('.symtab').get_symbol_by_name('ndk_layout')[0]
        values = struct.unpack('<' + 'Q' * len(labels), elf.get_section(symbol['st_shndx']).data()[symbol['st_value']:symbol['st_value'] + symbol['st_size']])
    layout = dict(zip(labels, values))
    required = [128, 48, 72, 88, 104, 8, 8, 0x4000, 0x8000, 0x20000, 0x80000, 152]
    if list(values) != required:
        raise RuntimeError(f'Adapter constants do not match actual NDK: {layout}')
    (out / 'ndk_layout.json').write_text(json.dumps(layout, indent=2) + '\n')
    print(f'Real APK sample: {selected.filename}, {len(sample)} raw bytes at {offset}, CRC32 {expected["crc32_raw"]:08x}')
    print('Actual AArch64 NDK stat/off_t/open-flag layout matches the fixed Windows adapter.')
    if args.lift:
        guest = out / 'file-guest.so'
        subprocess.run([str(compiler), '-fPIC', '-shared', '-nostdlib', '-O1', '-fno-stack-protector',
                        '-D_FORTIFY_SOURCE=0', '-funwind-tables', str(HERE / 'file_guest_fixture.c'), '-o', str(guest)], check=True)
        translated = out / 'guest'
        subprocess.run([sys.executable, str(HERE.parent / 'whole/compile.py'), str(guest), '--out', str(translated),
                        '--lift', str(args.lift), '--base', '0x60000000', '--target', 'x86_64-w64-windows-gnu', '--cxx', args.cxx], check=True)
        shutil.copyfile(translated / 'traces.h', out / 'file_traces.h')


if __name__ == '__main__':
    main()
