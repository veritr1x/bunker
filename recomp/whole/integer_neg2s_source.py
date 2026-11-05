"""Apply the exact NEG.2S addition to the qualified 14f6/6dd source snapshot.

No other widths, scalar NEG, SQNEG or floating-point semantics are admitted.
The source root must be an isolated copy, never the frozen baseline directory.
"""
from pathlib import Path
import argparse,difflib,hashlib,json

BASELINES={
 'lib/Arch/AArch64/Arch.cpp':'03aec799348dd0612a4f64ca360479cf395f7a0751eb7d3d45b639f67b9c6c67',
 'lib/Arch/AArch64/Decode.cpp':'26db9d04d2ad82c620a96ff87b1e59897c0e4def18a59aedd1b3df27ae6c83b9',
 'lib/Arch/AArch64/Semantics/SIMD_INTEGER.cpp':'51763cd0d00301390c9ad55ba57fac38e1d5818a91b4814db87dd4365c1d3813'}
DECODER='''
namespace remill {
namespace aarch64 {
// Only the reached two 32-bit integer lanes; every other NEG form stays out.
bool TryDecodeNEG_ASIMDMISC_R(const InstData &data, Instruction &inst) {
  if (data.Q != 0 || data.size != 2) return false;
  AddArrangementSpecifier(inst, 64, 32);
  return TryDecodeRdW_Rn(data, inst, kRegD);
}
}  // namespace aarch64
}  // namespace remill
'''
STUB='''bool TryDecodeNEG_ASIMDMISC_R(const InstData &, Instruction &) {
  return false;
}
'''
SEMANTICS='''
namespace {
DEF_SEM(IntegerNeg2S, V128W dst, V64 src) {
  // Snapshot both lanes before writing, including Vd == Vn. Unsigned
  // subtraction is modulo 2^32, so negating INT_MIN never invokes signed UB.
  const auto values = UReadV32(src);
  auto result = UClearV32(UReadV32(dst));
  result = UInsertV32(result, 0, uint32_t(0) - UExtractV32(values, 0));
  result = UInsertV32(result, 1, uint32_t(0) - UExtractV32(values, 1));
  // Ordinary full-vector write clears upper64 and leaves NZCV/FPSR/FPCR alone.
  UWriteV32(dst, result);
  return memory;
}
}  // namespace
DEF_ISEL(NEG_ASIMDMISC_R_2S) = IntegerNeg2S;
'''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def apply(root,out):
 root=root.resolve();assert 'integer-neg2s' in str(root) and not out.exists()
 records={};patch=[]
 for name,expected in BASELINES.items():
  p=root/name;assert sha(p)==expected,name;old=p.read_text()
  if name.endswith('/Arch.cpp'):new=old+DECODER
  elif name.endswith('/Decode.cpp'):
   assert old.count(STUB)==1;new=old.replace(STUB,'\n',1)
  else:new=old+SEMANTICS
  p.write_text(new);records[name]=dict(old_sha256=expected,new_sha256=sha(p),old_bytes=len(old.encode()),new_bytes=len(new.encode()),prefix_append_or_exact_stub_removal=True)
  patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 out.mkdir();(out/'source.patch').write_text(''.join(patch))
 proof=dict(passed=True,scope='Exact NEG.2S source addition only; no build or execution qualification.',source_root=str(root),source_files=records,source_producer=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),new_selector='NEG_ASIMDMISC_R_2S',unsigned_modulo32=True,upper64_zero=True,flags_unchanged=True,all_other_NEG_forms_unsupported=True)
 (out/'source-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('NEG2S-SOURCE-PATCH',sha(out/'source-proof.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();apply(a.source_root,a.out)
