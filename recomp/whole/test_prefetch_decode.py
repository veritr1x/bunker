"""Exact immediate-prefetch decoder operands, exhaustive immediates and neighbors."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


PROBE = r'''
#include <remill/Arch/Arch.h>
#include <remill/Arch/Name.h>
#include <remill/OS/OS.h>
#include <remill/BC/Util.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
int main(int argc,char**argv) { try {
 if(argc!=2)throw std::runtime_error("requires frozen semantics directory");
 llvm::LLVMContext context;
 auto arch=remill::Arch::Build(&context,remill::kOSLinux,remill::kArchAArch64LittleEndian);
 auto semantics=remill::LoadArchSemantics(arch.get(),{std::filesystem::path(argv[1])});
 uint32_t word; int form,rn,rt; int64_t displacement; unsigned count=0;
 while(std::cin>>std::hex>>word>>std::dec>>form>>rn>>rt>>displacement) {
  char bytes[4];for(unsigned n=0;n<4;++n)bytes[n]=char(word>>(8*n));
  remill::Instruction inst;bool ok=arch->DecodeInstruction(0x1000,std::string_view(bytes,4),inst,arch->CreateInitialContext());
  bool hint=inst.function=="PRFM_P_LDST_POS"||inst.function=="PRFUM_P_LDST_UNSCALED";
  auto require=[&](bool b,const char*why){if(!b)throw std::runtime_error(std::to_string(word)+": "+why+" "+inst.Serialize());};
  if(form>=0) {
   require(ok&&hint,"valid exact hint");
   require(inst.function==(form?"PRFM_P_LDST_POS":"PRFUM_P_LDST_UNSCALED"),"instruction family");
   require(inst.next_pc==0x1004&&inst.operands.size()==2,"normal fallthrough/two operands");
   auto&a=inst.operands[0];auto&h=inst.operands[1];
   require(a.type==remill::Operand::kTypeAddress&&a.action==remill::Operand::kActionRead&&a.size==64,"EA input kind/action/width");
   require(a.addr.kind==remill::Operand::Address::kAddressCalculation&&a.addr.address_size==64&&!a.addr.IsMemoryAccess(),"calculation only, never a data access");
   require(a.addr.base_reg.name==(rn==31?"SP":"X"+std::to_string(rn))&&a.addr.base_reg.size==64,"Rn31 is SP; full-width GPR");
   require(a.addr.displacement==displacement&&a.addr.index_reg.name.empty()&&a.addr.segment_base_reg.name.empty(),"signed/scaled displacement; no index/writeback operand");
   require(h.type==remill::Operand::kTypeImmediate&&h.action==remill::Operand::kActionRead&&h.size==64&&!h.imm.is_signed&&h.imm.val==uint64_t(rt),"unsigned imm5 hint, not a register result");
  }else {
   require(!hint,"neighbor cannot become hint");
   if(form==-2)require(!ok,"unimplemented/reserved control remains unsupported");
   if(form==-3)require(ok,"ordinary load/store control remains supported");
  }
  std::cout<<"PASS "<<std::hex<<word<<std::dec<<" "<<inst.Serialize()<<"\n";++count;
 }
 if(!std::cin.eof())throw std::runtime_error("invalid input record");
 std::cout<<"PREFETCH-DECODE-SUCCESS "<<count<<"\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    recipe_path = a.toolchain / 'decoder-link-recipe.json'
    recipe = json.loads(recipe_path.read_text())
    files = [recipe_path, Path(__file__)] + [Path(x['frozen']) for x in recipe['libraries']]
    for x in recipe['libraries']:
        assert sha(x['frozen']) == x['sha256']
    pins = {str(f): sha(f) for f in files}
    source = out / 'decoder-probe.cpp'
    source.write_text(PROBE)
    binary = out / 'decoder-probe'
    command = [recipe['compiler'], *recipe['compile_flags'], str(source),
               *recipe['link_flags'], '-o', str(binary)]
    with (out / 'build.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    records = []

    def add(form, rn, rt, displacement):
        word = (0xf9800000 | ((displacement // 8) << 10) if form else
                0xf8800000 | ((displacement & 511) << 12)) | (rn << 5) | rt
        records.append((word, form, rn, rt, displacement))

    for form in (0, 1):
        for rn in range(32):
            for rt in range(32):
                add(form, rn, rt, 0)
    for raw in range(512):
        add(0, 20, 1, raw if raw < 256 else raw - 512)
    for raw in range(4096):
        add(1, 31, 31, raw * 8)
    for form, offsets in ((0, [-256, -255, -112, -1, 1, 7, 8, 15, 255]),
                          (1, [8, 16, 248, 256, 4096, 32760])):
        for rn in (0, 20, 30, 31):
            for offset in offsets:
                add(form, rn, 1, offset)
    original = [(0xf9800301, 1, 24, 1, 0), (0xf8990281, 0, 20, 1, -112),
                (0xf9800301, 1, 24, 1, 0), (0xf9800301, 1, 24, 1, 0),
                (0xf9800101, 1, 8, 1, 0), (0xf9800321, 1, 25, 1, 0)]
    records += original
    # Undefined fixed fields are distinct from the legal unsigned hint immediate.
    controls = [(0xffffffff, -2), (0xf9c00000, -2), (0xf8800400, -2),
                (0xd8000000, -2), (0xf8a06800, -2),
                (0xf9400002, -3), (0xf9000002, -3),
                (0xf8400002, -3), (0xf8000002, -3),
                (0xf8400402, -3), (0xf8400c02, -3),
                (0xf8000402, -3), (0xf8000c02, -3),
                (0xf8400802, -2), (0xf8000802, -2),
                (0xd503201f, -3), (0xd503203f, -2),
                (0xd503205f, -2), (0xd503207f, -2)]
    records += [(word, mode, 0, 0, 0) for word, mode in controls]
    corpus = out / 'cases.txt'
    corpus.write_text(''.join(f'{w:08x} {f} {n} {t} {d}\n' for w, f, n, t, d in records))
    with corpus.open() as data, (out / 'decoded.log').open('w') as log:
        subprocess.run([binary, a.toolchain], stdin=data, stdout=log, stderr=subprocess.STDOUT, check=True)
    lines = (out / 'decoded.log').read_text().splitlines()
    assert lines[-1] == f'PREFETCH-DECODE-SUCCESS {len(records)}'
    assert sum(x.startswith('PASS ') for x in lines) == len(records)
    for f, pin in pins.items():
        assert sha(f) == pin
    result = {'passed': True, 'controls': len(records), 'all_Rn_Rt_forms': 2048,
              'exhaustive_imm9': 512, 'exhaustive_imm12': 4096,
              'original_words': [f'{x[0]:08x}' for x in original],
              'neighbor_controls': [(f'{w:08x}', mode) for w, mode in controls],
              'frozen_inputs': pins, 'command': command,
              'evidence': {str(f.relative_to(out)): sha(f) for f in out.iterdir() if f.is_file()}}
    (out / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Prefetch structured decoder PASS {len(records)} controls', flush=True)


if __name__ == '__main__':
    main()
