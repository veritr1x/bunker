#include "runtime.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <stdexcept>
#include <cstring>
struct Case{const char*name;unsigned width,exhaustive;};
static const Case fmla_cases[]={
#define CASE(name,width,exhaustive,d,n,m,lanes,index) {#name,width,exhaustive},
#include "fp_fmla_generated.h"
#undef CASE
};
#include "fp_fmla_driver.h"
static recomp::Runtime runtime;
static elf_image image;
static void invoke(unsigned index,uint8_t*out,const uint8_t*acc,const uint8_t*lhs,const uint8_t*rhs,uint64_t fpcr,uint64_t status){
  alignas(16) static uint8_t stack[65536];State s{};
  s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(acc);
  s.gpr.x2.qword=reinterpret_cast<addr_t>(lhs);s.gpr.x3.qword=reinterpret_cast<addr_t>(rhs);
  s.gpr.x4.qword=fpcr;s.gpr.x5.qword=status;s.gpr.x30.qword=0xfeedffff;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));
  const auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,fmla_cases[index].name));
  if(!entry)throw std::runtime_error("missing FMLA fixture export");
  runtime.Run(s,entry);
  if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))throw std::runtime_error("FMLA fixture corrupted PC/SP");
}
int main(){
  if(elf_load(FMLA_IMAGE,0x5d000000,nullptr,&image))throw std::runtime_error("FMLA fixture ELF load failed");
  runtime.AddTraces(kTraces,std::size(kTraces));return run_fmla_cases(invoke);
}
