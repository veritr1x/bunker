#include "runtime.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <stdexcept>
#include "unity_matrix_driver.h"
static recomp::Runtime runtime;
static addr_t entry;
static void invoke(uint8_t*out,const uint8_t*a,const uint8_t*b,uint8_t*c,uint64_t fpcr,uint64_t status){
  alignas(16) static uint8_t stack[65536];State s{};
  s.gpr.x0.qword=reinterpret_cast<addr_t>(out);s.gpr.x1.qword=reinterpret_cast<addr_t>(a);
  s.gpr.x2.qword=reinterpret_cast<addr_t>(b);s.gpr.x3.qword=reinterpret_cast<addr_t>(c);
  s.gpr.x4.qword=fpcr;s.gpr.x5.qword=status;s.gpr.x30.qword=0xfeedffff;
  s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));runtime.Run(s,entry);
  if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))throw std::runtime_error("exact matrix wrapper corrupted caller PC/SP");
}
int main(int argc,char **argv){
  elf_image image;if(elf_load(MATRIX_IMAGE,0x5e000000,nullptr,&image))throw std::runtime_error("exact matrix ELF load failed");
  entry=reinterpret_cast<addr_t>(elf_symbol(&image,"unity_matrix_call"));if(!entry)throw std::runtime_error("matrix wrapper absent");
  runtime.AddTraces(kTraces,std::size(kTraces));return run_matrix_cases(invoke,argc>1&&!strcmp(argv[1],"diagnostic"));
}
