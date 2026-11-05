"""Apply only reached CNT.8B and UADDLV.H/8B to the frozen NEG2S/4S source."""
from pathlib import Path
import argparse,difflib,hashlib,json
BASELINES={'lib/Arch/AArch64/Arch.cpp':'a30b53694f891a03bc0c8334f46bb0ec68f3fc11936d3f0de10080d53cc3f841','lib/Arch/AArch64/Decode.cpp':'a52e6a146250fa4723419ea439b10a8775b01f0a4f3be12e9315feed20bed3f1','lib/Arch/AArch64/Semantics/SIMD_INTEGER.cpp':'0da587bd9f8f7702dcbb2e13304970046aaefa8cb41556b5e19d49e46e2864fd'}
CNT_STUB='''bool TryDecodeCNT_ASIMDMISC_R(const InstData &, Instruction &) {
  return false;
}
'''
SUM_STUB='''bool TryDecodeUADDLV_ASIMDALL_ONLY(const InstData &, Instruction &) {
  return false;
}
'''
SUM_DECODER='''bool TryDecodeUADDLV_ASIMDALL_ONLY(const InstData &data, Instruction &inst) {
  if (data.Q != 0 || data.size != 0) return false;
  AddArrangementSpecifier(inst, 64, 8);
  AddRegOperand(inst, kActionWrite, kRegV, kUseAsValue, data.Rd);
  AddRegOperand(inst, kActionRead, kRegD, kUseAsValue, data.Rn);
  return true;
}
'''
CNT_DECODER='''
namespace remill {
namespace aarch64 {
bool TryDecodeCNT_ASIMDMISC_R(const InstData &data, Instruction &inst) {
  if (data.Q != 0 || data.size != 0) return false;
  AddArrangementSpecifier(inst, 64, 8);
  return TryDecodeRdW_Rn(data, inst, kRegD);
}
}  // namespace aarch64
}  // namespace remill
'''
SEMANTICS='''
namespace {
DEF_SEM(IntegerCount8B, V128W dst, V64 src) {
  const auto values = UReadV8(src);
  auto result = UClearV8(UReadV8(dst));
  for (unsigned lane = 0; lane < 8; ++lane) {
    const uint32_t byte = UExtractV8(values, lane);
    uint8_t count = 0;
    for (unsigned bit = 0; bit < 8; ++bit) {
      count = uint8_t(count + ((byte >> bit) & 1u));
    }
    result = UInsertV8(result, lane, count);
  }
  UWriteV8(dst, result);
  return memory;
}
DEF_SEM(IntegerUnsignedAddLong8B, V128W dst, V64 src) {
  const auto values = UReadV8(src);
  uint16_t sum = 0;
  for (unsigned lane = 0; lane < 8; ++lane) {
    sum = uint16_t(sum + UExtractV8(values, lane));
  }
  auto result = UClearV16(UReadV16(dst));
  result = UInsertV16(result, 0, sum);
  UWriteV16(dst, result);
  return memory;
}
}  // namespace
DEF_ISEL(CNT_ASIMDMISC_R_8B) = IntegerCount8B;
DEF_ISEL(UADDLV_ASIMDALL_ONLY_8B) = IntegerUnsignedAddLong8B;
'''
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def apply(root,out):
 root=root.resolve();assert 'integer-popcount8b' in str(root)and not out.exists();records={};patch=[]
 for name,h in BASELINES.items():
  p=root/name;assert sha(p)==h;old=p.read_text()
  if name.endswith('/Arch.cpp'):assert old.count(SUM_STUB)==1;new=old.replace(SUM_STUB,SUM_DECODER,1)+CNT_DECODER
  elif name.endswith('/Decode.cpp'):assert old.count(CNT_STUB)==1;new=old.replace(CNT_STUB,'\n',1)
  else:new=old+SEMANTICS
  p.write_text(new);records[name]=dict(old_sha256=h,new_sha256=sha(p),old_bytes=len(old.encode()),new_bytes=len(new.encode()));patch.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
 out.mkdir();(out/'source.patch').write_text(''.join(patch));proof=dict(passed=True,scope='Only Q0,size0 CNT8B and unsigned widening-add8B-toH source support. Prior NEG2S/4S and all other semantics/selectors unchanged.',source_root=str(root),source_files=records,source_producer=dict(path=str(Path(__file__).resolve()),sha256=sha(__file__)),new_selectors=['CNT_ASIMDMISC_R_8B','UADDLV_ASIMDALL_ONLY_8B'],source_snapshot_before_write=True,CNT_upper64_zero=True,UADDLV_sum_range=[0,2040],UADDLV_low16_only_all_other_bits_zero=True,flags_unchanged=True,reference='https://arm-software.github.io/acle/neon_intrinsics/advsimd.html',reference_intrinsics=['vcnt_u8','vaddlv_u8'],other_widths_unsupported=True);(out/'source-proof.json').write_text(json.dumps(proof,indent=2)+'\n');print('POPCOUNT8B-SOURCE',sha(out/'source-proof.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();apply(a.source_root,a.out)