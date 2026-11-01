#include "runtime.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <stdexcept>
struct Case{const char *name;unsigned width,full;};
static const Case multiply_cases[]={
#define CASE(name,width,full) {#name,width,full},
#include "fp_fmul_indexed_generated.h"
#undef CASE
};
#include "fp_fmul_indexed_driver.h"
static recomp::Runtime runtime;static elf_image image;
static void invoke(unsigned index,uint8_t*out,const uint8_t*old,const uint8_t*lhs,const uint8_t*rhs,uint64_t fpcr,uint64_t status){
  alignas(16) static uint8_t stack[65536];State s{};
  s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(old);
  s.gpr.x2.qword=reinterpret_cast<addr_t>(lhs);s.gpr.x3.qword=reinterpret_cast<addr_t>(rhs);
  s.gpr.x4.qword=fpcr;s.gpr.x5.qword=status;s.gpr.x30.qword=0xfeedffff;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
  auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,multiply_cases[index].name));if(!entry)throw std::runtime_error("missing indexed FMUL export");
  runtime.Run(s,entry);if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))throw std::runtime_error("indexed FMUL fixture corrupted PC/SP");
}
int main(){
  if(elf_load(FMUL_INDEXED_IMAGE,0x5f000000,nullptr,&image))throw std::runtime_error("indexed FMUL ELF load failed");
  runtime.AddTraces(kTraces,std::size(kTraces));return run_multiply_cases(invoke);
}
