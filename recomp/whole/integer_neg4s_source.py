"""Add only reached Q1/size2 integer NEG.4S to the frozen NEG.2S source snapshot."""
from pathlib import Path
import argparse,difflib,hashlib,json
BASELINES={'lib/Arch/AArch64/Arch.cpp':'08dcb7239647d7a3c4f42291913458f2eec7adce576c06cdbbf586e6d87bca34','lib/Arch/AArch64/Semantics/SIMD_INTEGER.cpp':'f81586a841c62c1839ac02137790fbf1b8fea9b680452fc83c66e906860c40e6'}
OLD='''  if (data.Q != 0 || data.size != 2) return false;
  AddArrangementSpecifier(inst, 64, 32);
  return TryDecodeRdW_Rn(data, inst, kRegD);'''
NEW='''  if (data.size != 2) return false;
  AddArrangementSpecifier(inst, data.Q ? 128 : 64, 32);
  return TryDecodeRdW_Rn(data, inst, data.Q ? kRegQ : kRegD);'''
SEMANTICS='''
namespace {
DEF_SEM(IntegerNeg4S, V128W dst, V128 src) {
  // Capture all four integer lanes before writing; aliasing is valid.
  const auto values = UReadV32(src);
  auto result = UClearV32(UReadV32(dst));
  result = UInsertV32(result, 0, uint32_t(0) - UExtractV32(values, 0));
  result = UInsertV32(result, 1, uint32_t(0) - UExtractV32(values, 1));
  result = UInsertV32(result, 2, uint32_t(0) - UExtractV32(values, 2));
  result = UInsertV32(result, 3, uint32_t(0) - UExtractV32(values, 3));
  UWriteV32(dst, result);
  return memory;
}
}  // namespace
DEF_ISEL(NEG_ASIMDMISC_R_4S) = IntegerNeg4S;
'''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def apply(root,out):
 root=root.resolve();assert 'integer-neg4s' in str(root) and not out.exists();records={};patch=[]
 for name,h in BASELINES.items():
  p=root/name;assert sha(p)==h;old=p.read_text()
  if name.endswith('/Arch.cpp'):
   assert old.count(OLD)==1
   new=old.replace(OLD,NEW,1).replace('// Only the reached two 32-bit integer lanes; every other NEG form stays out.','// Only two or four 32-bit integer lanes; every other NEG form stays out.',1)
  else:new=old+SEMANTICS
  p.write_text(new);records[name]=dict(old_sha256=h,new_sha256=sha(p),old_bytes=len(old.encode()),new_bytes=len(new.encode()))
  patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 out.mkdir();(out/'source.patch').write_text(''.join(patch));proof=dict(passed=True,scope='Only Q1/size2 NEG.4S addition; prior2S semantic body unchanged; no build or execution claim.',source_root=str(root),source_files=records,source_producer=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),new_selector='NEG_ASIMDMISC_R_4S',unsigned_modulo32=True,source_snapshot_before_write=True,all128_destination_bits_written=True,flags_unchanged=True,existing_NEG2S_preserved=True,other_NEG_widths_unsupported=True);(out/'source-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('NEG4S-SOURCE-PATCH',sha(out/'source-proof.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();apply(a.source_root,a.out)
