#include "runtime.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "nonlocal_entries.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <set>
namespace {
void *Resolve(const char*){
  // The dispatch-availability gate never calls a save/transfer import.
  // Any unexpected import execution is a decisive failure below.
  return reinterpret_cast<void*>(0x7ff460100000ULL);
}
}
int main(){
  recomp::Runtime runtime;runtime.AddTraces(kTraces,std::size(kTraces));
  runtime.AddImport(0x7ff460100000ULL,[](State&){
    std::fputs("unexpected import in continuation-only gate\n",stderr);std::abort();
  });
  elf_image image{};if(elf_load(NONLOCAL_LIBRARY,0x5c000000,Resolve,&image))return 2;
  std::set<addr_t> entries;for(auto&t:kTraces)entries.insert(t.address);
  unsigned checks=0;
  for(size_t i=0;i<std::size(kNonlocalEntries);++i){
    alignas(16)std::array<uint64_t,128> stack{};uint32_t output=0;
    auto sp=reinterpret_cast<addr_t>(&stack[120]);stack[120]=0x123456789abcdef0ULL;stack[121]=0xfeedfff0;
    State state{};state.gpr.sp.qword=sp;state.gpr.x19.qword=reinterpret_cast<addr_t>(&output);state.gpr.x30.qword=0xbad0;
    // The baseline is expected to stop here for its missing entry.
    runtime.Run(state,kNonlocalEntries[i]);
    if(output!=0x31+i||state.gpr.x0.qword!=0x31+i||state.gpr.sp.qword!=sp+16||
       state.gpr.x19.qword!=0x123456789abcdef0ULL||state.gpr.pc.qword!=0xfeedfff0||
       !entries.count(kNonlocalEntries[i])){
      std::fputs("nonlocal continuation dispatch effects/PC/SP mismatch\n",stderr);return 3;
    }
    checks+=6;
  }
  std::printf("Nonlocal roots: %u continuation dispatch checks pass; no longjmp transfer executed.\n",checks);
  return 0;
}
