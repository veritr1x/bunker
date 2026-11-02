"""Re-derive the JP runtime map from private Il2CppDumper outputs and original ELF files.

Each input directory contains libil2cpp.so, global-metadata.dat and
dump/script.json. No APKs, dumps or game data belong in Git.
"""
import argparse
import bisect
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
import game_patch

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--global-dir', type=Path, required=True)
p.add_argument('--jp-dir', type=Path, required=True)
p.add_argument('--output', type=Path, default=root / 'android/app/src/main/cpp/game_region.h')
args = p.parse_args()

g = (args.global_dir / 'libil2cpp.so').read_bytes()
j = (args.jp_dir / 'libil2cpp.so').read_bytes()
assert game_patch.identify(g, (args.global_dir / 'global-metadata.dat').read_bytes()) == 'global'
assert game_patch.identify(j, (args.jp_dir / 'global-metadata.dat').read_bytes()) == 'jp'
methods = sorted([m for m in json.loads((args.global_dir / 'dump/script.json').read_text())['ScriptMethod'] if m['Address']], key=lambda m:m['Address'])
addresses = [m['Address'] for m in methods]
jmethods = json.loads((args.jp_dir / 'dump/script.json').read_text())['ScriptMethod']
by_signature = {}
def signature(m):
    return m['Name'], re.sub(r'MethodInfo_[0-9A-F]+', 'MethodInfo', m['Signature'])
for m in jmethods:
    by_signature.setdefault(signature(m), []).append(m)
sources = {name:(root / 'android/app/src/main/cpp' / name).read_text() for name in ['display_patch.c', 'text_buffer.c', 'remain_days.c', 'camera_edge.c', 'guerrilla_unlock.c']}
mapping = {}
for source in sources.values():
    # Only code, never the crash addresses and branch-target annotations in comments.
    source = re.sub(r'//[^\n]*', '', source)
    source = re.sub(r'^.*init_rva.*$', '', source, flags=re.M)
    for match in re.finditer(r'0x[0-9A-Fa-f]{7}\b', source):
        a = int(match.group(),16)
        if a == 0x3291FB4: continue  # JP has no IronSource assembly.
        m = methods[bisect.bisect_right(addresses,a)-1]
        matches = by_signature[signature(m)]
        assert len(matches) == 1, (hex(a),m['Name'])
        b = matches[0]['Address'] + a - m['Address']
        # JP adds two instructions before BattleUpdate's tail call. Resolve
        # the actual unique four-word hook and its following B Process.
        if a == 0x2A6530C:
            needle = g[a:a+16]
            start = matches[0]['Address']
            offsets = [i for i in range(start,start+0x100,4) if j[i:i+16] == needle]
            assert len(offsets) == 1
            b = offsets[0]
        mapping[a] = b

triples = re.findall(r'\{(0x[0-9A-Fa-f]+), (0x[0-9a-f]+)u, (0x[0-9a-f]+)u\}', sources['text_buffer.c'])
overrides = []
triples += re.findall(r'\{(0x[0-9A-Fa-f]+), (0x[0-9a-f]+)u, (0x[0-9a-f]+)u\}', sources['camera_edge.c'])
for ra, old, new in triples:
    a,old,new = int(ra,16),int(old,16),int(new,16)
    b=mapping[a]
    assert int.from_bytes(g[a:a+4],'little')==old
    jp_old=int.from_bytes(j[b:b+4],'little')
    jp_new=new
    # Two capacity patches shift a PC-relative ADRP/LDR pair by one word.
    # Use the JP instructions and require the ADRP stays on the same page.
    if new & 0xFC000000 in (0x14000000, 0x94000000):
        delta = (new & 0x3FFFFFF) << 2
        if delta & (1 << 27): delta -= 1 << 28
        target = a + delta
        method = methods[bisect.bisect_right(addresses,target)-1]
        candidates = by_signature[signature(method)]
        assert len(candidates) == 1
        jp_target = candidates[0]["Address"] + target - method["Address"]
        jp_new = (new & 0xFC000000) | (((jp_target - b) >> 2) & 0x3FFFFFF)
    elif a in [0x53B5C94,0x53B6068]:
        assert (b-4)//4096 == b//4096
        jp_new=int.from_bytes(j[b-4:b],'little')
    elif a in [0x53B5C98,0x53B606C]:
        jp_new=int.from_bytes(j[b-4:b],'little')
    if jp_old!=old or jp_new!=new:
        overrides.append((a,jp_old,jp_new))

# The remaining patches and hook prologues must be byte-for-byte identical.
for name in ['display_patch.c','remain_days.c']:
    s=sources[name]
    for ra,old in re.findall(r'\{(0x[0-9A-Fa-f]+), (0x[0-9a-f]+)u',s):
        a,old=int(ra,16),int(old,16)
        assert int.from_bytes(j[mapping[a]:mapping[a]+4],'little')==old,(ra,'site mismatch')
    words={n:bytes.fromhex(''.join(int(w,16).to_bytes(4,'little').hex() for w in re.findall(r'0x([0-9a-f]+)u',v))) for n,v in re.findall(r'static const uint32_t (\w+)\[4\] = \{([^}]*)\}',s)}
    for ra,n in re.findall(r'\{(0x[0-9A-F]+), (k\w+)\}',s):
        a=int(ra,16);b=mapping[a];assert j[b:b+16]==words[n],(ra,n)

lines=['// Japanese 3.7.1 RVAs resolved by method name AND full signature, then',
       '// checked against both original binaries. See docs/ANDROID-REGIONS.md.',
       '#ifndef BUNKER_GAME_REGION_H', '#define BUNKER_GAME_REGION_H', '#include <stdint.h>',
       'extern int bunker_game_japanese;', '',
       'static inline uint32_t game_rva(uint32_t global) {',
       '    if (!bunker_game_japanese) return global;', '    switch (global) {']
lines += [f'    case 0x{a:X}: return 0x{b:X};' for a,b in sorted(mapping.items())]
lines += ['    default: return global;', '    }', '}', '',
          'static inline uint32_t game_original(uint32_t global, uint32_t word) {',
          '    if (!bunker_game_japanese) return word;', '    switch (global) {']
lines += [f'    case 0x{a:X}: return 0x{old:08x}u;' for a,old,new in overrides]
lines += ['    default: return word;', '    }', '}', '',
          'static inline uint32_t game_patched(uint32_t global, uint32_t word) {',
          '    if (!bunker_game_japanese) return word;', '    switch (global) {']
lines += [f'    case 0x{a:X}: return 0x{new:08x}u;' for a,old,new in overrides]
lines += ['    default: return word;', '    }', '}', '#endif','']
args.output.write_text('\n'.join(lines), newline='\n')
print('Mapped',len(mapping),'runtime RVAs;',len(overrides),'regional instruction overrides')

# Native SDK entry points introduced by upstream's telemetry hardening.
# Keep the same exact method/signature match as the runtime map. JP has no
# IronSource assembly, so its two initialization methods are intentionally absent.
telemetry = []
for site in json.loads((root / 'android/tools/telemetry_patches.json').read_text())['sites']:
    a = site['rva']
    method = methods[bisect.bisect_right(addresses, a) - 1]
    assert method['Address'] == a
    matches = by_signature.get(signature(method), [])
    if not matches:
        assert method['Name'].startswith(('IronSource$$init', 'Facebook.Unity.Mobile.Android.AndroidFacebook$$')), method['Name']
        continue
    assert len(matches) == 1, method['Name']
    b = matches[0]['Address']
    expected = bytes.fromhex(site['original'])
    assert g[a:a + len(expected)] == expected
    telemetry.append(dict(site, rva=b, original=j[b:b + len(expected)].hex()))
(root / 'android/tools/telemetry_patches_jp.json').write_text(
    json.dumps({'client': 'Japanese 3.7.1 ARM64', 'sites': telemetry}, indent=2) + '\n', newline='\n')
print('Mapped', len(telemetry), 'Japanese telemetry entry points; Facebook Android and IronSource methods are absent')
