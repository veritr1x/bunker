"""Inventory the real APK/native-library boundaries for the Windows host.

Reports ELF imports, executable JNI entries, native-registration tables, and
Unity Java declarations from DEX. It does not claim that a listed API is ported.
Requires pyelftools. Game binaries and generated JSON stay outside Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection


def valid_signature(value):
    def field(at, allow_void=False):
        if at >= len(value):
            return -1
        if value[at] in 'ZBCSIJFD' or (allow_void and value[at] == 'V'):
            return at + 1
        if value[at] == '[':
            return field(at + 1)
        if value[at] == 'L':
            end = value.find(';', at + 1)
            return end + 1 if end > at + 1 else -1
        return -1
    if not value.startswith('('):
        return False
    at = 1
    while at < len(value) and value[at] != ')':
        at = field(at)
        if at < 0:
            return False
    return at < len(value) and field(at + 1, True) == len(value)


def category(name):
    for kind, pattern in [
        ('android_native', r'^(AAsset|ANative|ASensor|ALooper|AInput|AConfiguration|AChoreographer|__android_)'),
        ('graphics', r'^(egl|gl[A-Z])'), ('audio', r'^(AAudio|sl[A-Z])'),
        ('threads', r'^pthread_'), ('dynamic_loading', r'^(dlopen|dlsym|dlclose|dlerror|dladdr)$'),
    ]:
        if re.search(pattern, name):
            return kind
    return 'c_runtime_posix_math'


def elf_inventory(path):
    content = path.read_bytes()
    with path.open('rb') as source:
        elf = ELFFile(source)
        if elf['e_machine'] != 'EM_AARCH64':
            raise ValueError(f'{path} is not AArch64')
        loads = [seg for seg in elf.iter_segments() if seg['p_type'] == 'PT_LOAD']
        code = [(sec['sh_addr'], sec['sh_addr'] + sec['sh_size']) for sec in elf.iter_sections() if sec['sh_flags'] & 4]

        def read(address, count):
            for seg in loads:
                if seg['p_vaddr'] <= address and address + count <= seg['p_vaddr'] + seg['p_filesz']:
                    offset = seg['p_offset'] + address - seg['p_vaddr']
                    return content[offset:offset + count]
            return b''

        def string(address):
            for seg in loads:
                if seg['p_vaddr'] <= address < seg['p_vaddr'] + seg['p_filesz']:
                    offset = seg['p_offset'] + address - seg['p_vaddr']
                    end = content.find(b'\0', offset, min(seg['p_offset'] + seg['p_filesz'], offset + 1024))
                    if end >= 0:
                        try:
                            return content[offset:end].decode('ascii')
                        except UnicodeDecodeError:
                            return ''
            return ''

        executable = lambda address: address % 4 == 0 and any(lo <= address < hi for lo, hi in code)
        imports, exports = {}, {}
        dynsym = elf.get_section_by_name('.dynsym')
        if dynsym:
            for symbol in dynsym.iter_symbols():
                if not symbol.name:
                    continue
                if symbol['st_shndx'] == 'SHN_UNDEF':
                    imports[symbol.name] = {'category': category(symbol.name), 'binding': symbol['st_info']['bind'], 'type': symbol['st_info']['type']}
                else:
                    exports[symbol.name] = {'rva': symbol['st_value'], 'size': symbol['st_size'], 'type': symbol['st_info']['type']}
        pointer_values = {}
        relocations = {}
        for section in elf.iter_sections():
            if not isinstance(section, RelocationSection):
                continue
            symbols = elf.get_section(section['sh_link'])
            for rel in section.iter_relocations():
                kind = rel['r_info_type']
                relocations[str(kind)] = relocations.get(str(kind), 0) + 1
                value = rel.entry.get('r_addend', 0)
                if kind == 1027:  # R_AARCH64_RELATIVE
                    pointer_values[rel['r_offset']] = value
                elif kind in (257, 1025, 1026) and rel['r_info_sym']:
                    sym = symbols.get_symbol(rel['r_info_sym'])
                    if sym['st_shndx'] != 'SHN_UNDEF':
                        pointer_values[rel['r_offset']] = sym['st_value'] + value
        natives = []
        class_names = {}
        for offset, value in sorted(pointer_values.items()):
            name = string(value)
            if name.startswith(('com/', 'java/', 'android/', 'dalvik/')) and re.fullmatch(r'[\w$]+(?:/[\w$]+)+', name):
                class_names[f'{offset:#x}'] = name
            if offset + 8 not in pointer_values or offset + 16 not in pointer_values:
                continue
            signature = string(pointer_values[offset + 8])
            entry = pointer_values[offset + 16]
            if re.fullmatch(r'[A-Za-z_$][\w$]*', name) and valid_signature(signature) and executable(entry):
                natives.append({'table_rva': offset, 'name': name, 'signature': signature, 'entry_rva': entry})
        needed = []
        dynamic = elf.get_section_by_name('.dynamic')
        if dynamic:
            for tag in dynamic.iter_tags():
                if tag.entry.d_tag == 'DT_NEEDED':
                    needed.append(tag.needed)
        def entries(name):
            section = elf.get_section_by_name(name)
            return [pointer_values.get(section['sh_addr'] + index,
                    int.from_bytes(read(section['sh_addr'] + index, 8), 'little'))
                    for index in range(0, section['sh_size'], 8)] if section else []
        initializers, finalizers = entries('.init_array'), entries('.fini_array')
        onload = exports.get('JNI_OnLoad')
        calls = []
        if onload:
            body = read(onload['rva'], onload['size'])
            for offset in range(0, len(body), 4):
                instruction = int.from_bytes(body[offset:offset + 4], 'little')
                if instruction >> 26 == 0b100101:
                    immediate = instruction & ((1 << 26) - 1)
                    if immediate & (1 << 25):
                        immediate -= 1 << 26
                    calls.append(onload['rva'] + offset + (immediate << 2))
        return {
            'file': str(path), 'sha256': hashlib.sha256(content).hexdigest(),
            'needed': needed, 'imports': imports, 'import_count': len(imports),
            'jni_exports': {name: value for name, value in exports.items() if name.startswith(('JNI_', 'Java_'))},
            'jni_onload_direct_calls': calls, 'initializers': initializers, 'finalizers': finalizers,
            'native_registration_candidates': natives, 'relocated_class_names': class_names,
            'relocation_type_counts': relocations,
        }


class Dex:
    def __init__(self, content):
        if not content.startswith(b'dex\n') or len(content) < 112:
            raise ValueError('not a DEX file')
        self.data, self.strings = content, {}
        if self.u32(40) != 0x12345678:
            raise ValueError('unsupported DEX endian tag')

    def u16(self, at):
        return struct.unpack_from('<H', self.data, at)[0]

    def u32(self, at):
        return struct.unpack_from('<I', self.data, at)[0]

    def uleb(self, at):
        value = 0
        for shift in range(0, 35, 7):
            byte = self.data[at]
            at += 1
            value |= (byte & 127) << shift
            if byte < 128:
                return value, at
        raise ValueError('oversized DEX ULEB128')

    def string(self, index):
        if index not in self.strings:
            offset = self.u32(self.u32(60) + index * 4)
            _, offset = self.uleb(offset)
            end = self.data.index(0, offset)
            self.strings[index] = self.data[offset:end].decode('utf-8', 'replace')
        return self.strings[index]

    def type(self, index):
        return self.string(self.u32(self.u32(68) + index * 4))

    def method(self, index, flags):
        at = self.u32(92) + index * 8
        proto = self.u32(76) + self.u16(at + 2) * 12
        result = self.type(self.u32(proto + 4))
        parameters = self.u32(proto + 8)
        args = ''.join(self.type(self.u16(parameters + 4 + i * 2)) for i in range(self.u32(parameters))) if parameters else ''
        return {'name': self.string(self.u32(at + 4)), 'signature': f'({args}){result}',
                'access_flags': flags, 'static': bool(flags & 8), 'native': bool(flags & 0x100)}

    def unity_classes(self):
        classes = {}
        for index in range(self.u32(96)):
            at = self.u32(100) + index * 32
            name = self.type(self.u32(at))
            if not name.startswith('Lcom/unity3d/player/'):
                continue
            data = self.u32(at + 24)
            methods = []
            if data:
                counts = []
                for _ in range(4):
                    count, data = self.uleb(data)
                    counts.append(count)
                for _ in range(counts[0] + counts[1]):
                    _, data = self.uleb(data)
                    _, data = self.uleb(data)
                for count in counts[2:]:
                    method_index = 0
                    for _ in range(count):
                        delta, data = self.uleb(data)
                        flags, data = self.uleb(data)
                        _, data = self.uleb(data)
                        method_index += delta
                        methods.append(self.method(method_index, flags))
            classes[name[1:-1]] = {'access_flags': self.u32(at + 4), 'methods': methods}
        return classes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lib-dir', type=Path, required=True)
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--libraries', nargs='+', help='Limit inspection to these library filenames')
    args = parser.parse_args()
    paths = sorted(args.lib_dir.glob('*.so'))
    if args.libraries:
        paths = [args.lib_dir / name for name in args.libraries]
    result = {'libraries': {path.name: elf_inventory(path) for path in paths}}
    if args.apk:
        classes = {}
        with zipfile.ZipFile(args.apk) as apk:
            for name in apk.namelist():
                if re.fullmatch(r'classes\d*\.dex', name):
                    for class_name, declaration in Dex(apk.read(name)).unity_classes().items():
                        declaration['dex'] = name
                        classes[class_name] = declaration
        result['unity_java_classes'] = classes
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    for name, library in result['libraries'].items():
        print(f'{name}: {library["import_count"]} imports, {len(library["initializers"])} initializers, {len(library["native_registration_candidates"])} candidate JNI natives')
    loader = result.get('unity_java_classes', {}).get('com/unity3d/player/NativeLoader')
    if loader:
        print('Actual APK NativeLoader methods:', loader['methods'])


if __name__ == '__main__':
    main()
